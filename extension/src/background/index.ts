import { parseHealthResponse, parseServerMessage, type HealthResponse } from "@streamlingo/protocol";
import type { BackgroundRequest, BackgroundResponse, ContentMessage, Snapshot } from "../shared/runtime-messages";
import { closeOffscreen, ensureOffscreen, hasOffscreen, sendOffscreen } from "./offscreen-host";
import { isExtensionPage, isYouTubeVideoUrl } from "./policy";
import { SessionController } from "./session-controller";
import { readSettings, writeSettings } from "./settings-store";
import { AppError, errorInfo, errorFromInfo } from "../shared/i18n";
import { readUiLanguage, writeUiLanguage } from "../shared/language-preference";
import { assertLanguageSupport } from "../shared/language-capabilities";
import type { ExtensionSettings } from "../shared/config";

let health: HealthResponse | null = null;

async function sendContent(tabId: number, message: ContentMessage): Promise<void> {
  await chrome.tabs.sendMessage(tabId, message, { frameId: 0 });
}

async function clearSessionOverlays(sessionId: string): Promise<void> {
  // After worker suspension an error/idle offscreen state has no target tab.
  // Content scripts validate sessionId, so this only clears the ended session.
  const tabs = await chrome.tabs.query({ url: ["https://www.youtube.com/*", "https://youtube.com/*"] });
  await Promise.allSettled(tabs.flatMap((tab) => tab.id === undefined ? [] : [
    sendContent(tab.id, { target: "content", type: "CONTENT_STOP", sessionId }),
  ]));
}

const controller = new SessionController({
  async query() {
    if (!(await hasOffscreen())) return { phase: "idle" };
    const reply = await sendOffscreen({ target: "offscreen", type: "OFFSCREEN_QUERY" }, 3000);
    if (!reply.ok) throw errorFromInfo(reply.errorInfo ?? errorInfo(reply.error));
    if (reply.state.phase === "error") {
      if (reply.state.sessionId) await clearSessionOverlays(reply.state.sessionId);
      await closeOffscreen();
    }
    return reply.state;
  },
  async validateTab(tabId) {
    const tab = await chrome.tabs.get(tabId);
    if (!isYouTubeVideoUrl(tab.url)) throw new AppError("YOUTUBE_REQUIRED");
    if (!tab.active) throw new AppError("TAB_INACTIVE");
  },
  async prepare(tabId, sessionId, settings, signal) {
    signal.throwIfAborted();
    health = await probeHealth(settings, signal);
    assertLanguageSupport(health, settings.translationMode);
    signal.throwIfAborted();
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    signal.throwIfAborted();
    await sendContent(tabId, { target: "content", type: "CONTENT_START", sessionId, settings });
    signal.throwIfAborted();
    await ensureOffscreen();
    signal.throwIfAborted();
  },
  async start(tabId, sessionId, settings, signal) {
    signal.throwIfAborted();
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
    signal.throwIfAborted();
    return sendOffscreen({ target: "offscreen", type: "OFFSCREEN_START", tabId, sessionId, streamId, settings });
  },
  async stop(sessionId) {
    if (await hasOffscreen()) await sendOffscreen({ target: "offscreen", type: "OFFSCREEN_STOP", sessionId }, 3000);
  },
  close: closeOffscreen,
  content: sendContent,
  changed(state) {
    const text = state.phase === "running" ? "ON" : state.phase === "starting" ? "…" : state.phase === "error" ? "!" : "";
    void chrome.action.setBadgeText({ text }).catch(() => undefined);
    void chrome.action.setBadgeBackgroundColor({ color: state.phase === "error" ? "#B91C1C" : "#2563EB" }).catch(() => undefined);
  },
});

async function snapshot(waitForQueue = true): Promise<Snapshot> {
  return { state: waitForQueue ? await controller.snapshot() : controller.state,
    settings: await readSettings(), health, extensionId: chrome.runtime.id, uiLanguage: await readUiLanguage() };
}

async function checkHealth(): Promise<void> {
  health = null;
  const settings = await readSettings();
  health = await probeHealth(settings);
}

async function probeHealth(settings: ExtensionSettings, signal?: AbortSignal): Promise<HealthResponse> {
  const abort = new AbortController();
  const cancel = () => abort.abort();
  const timeout = setTimeout(cancel, 5000);
  signal?.addEventListener("abort", cancel, { once: true });
  if (signal?.aborted) cancel();
  try {
    const response = await fetch(`${settings.backendBaseUrl}/health`, { signal: abort.signal, cache: "no-store", redirect: "error" });
    if (!response.ok) throw new AppError("SERVICE_HTTP", `HTTP ${response.status}`);
    return parseHealthResponse(await response.json());
  } catch (error) {
    if (signal?.aborted) throw new AppError("START_CANCELLED");
    throw error instanceof AppError ? error : new AppError("SERVICE_UNREACHABLE");
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", cancel);
  }
}

async function dispatch(message: BackgroundRequest, sender: chrome.runtime.MessageSender): Promise<BackgroundResponse> {
  const fromPopup = isExtensionPage(sender, "popup.html", chrome.runtime.id);
  const fromOffscreen = isExtensionPage(sender, "offscreen.html", chrome.runtime.id);
  if (message.type === "OFFSCREEN_EVENT" || message.type === "OFFSCREEN_FAILED") {
    if (!fromOffscreen || typeof message.sessionId !== "string") throw new AppError("INVALID_SENDER");
    if (message.type === "OFFSCREEN_EVENT") await controller.receive(message.sessionId, parseServerMessage(message.event));
    else {
      if (typeof message.message !== "string") throw new AppError("INVALID_REQUEST");
      // Restore a session after service-worker suspension before applying the failure.
      await controller.reportFailure(message.sessionId, message.errorInfo ?? errorInfo(message.message));
    }
    if (controller.state.phase === "error" || controller.state.phase === "idle") {
      void clearSessionOverlays(message.sessionId).catch(() => undefined);
    }
    // Never wait for the control queue here: its start operation may await this reply.
    return { ok: true, snapshot: await snapshot(false) };
  }
  if (message.type === "CONTENT_NAVIGATED") {
    if (sender.id !== chrome.runtime.id || sender.frameId !== 0 || typeof sender.tab?.id !== "number" || typeof message.sessionId !== "string") {
      throw new AppError("INVALID_SENDER");
    }
    void controller.navigated(sender.tab.id, message.sessionId).catch(() => undefined);
    return { ok: true, snapshot: await snapshot(false) };
  }
  if (!fromPopup) throw new AppError("INVALID_SENDER");
  switch (message.type) {
    case "GET_SNAPSHOT": break;
    case "CHECK_HEALTH": await checkHealth(); break;
    case "SET_UI_LANGUAGE": await writeUiLanguage(message.language); break;
    case "SAVE_SETTINGS": {
      const state = await controller.snapshot();
      if (["starting", "running", "stopping"].includes(state.phase)) throw new AppError("SETTINGS_LOCKED");
      await writeSettings(message.settings);
      health = null;
      break;
    }
    case "START_SESSION":
      if (!Number.isInteger(message.tabId) || message.tabId < 0) throw new AppError("TAB_MISSING");
      await controller.start(message.tabId, readSettings);
      break;
    case "STOP_SESSION": await controller.stop(); break;
    default: throw new AppError("INVALID_REQUEST");
  }
  return { ok: true, snapshot: await snapshot() };
}

chrome.runtime.onMessage.addListener((value: unknown, sender, sendResponse: (response: BackgroundResponse) => void) => {
  if (!value || typeof value !== "object" || !("target" in value) || value.target !== "background") return false;
  void dispatch(value as BackgroundRequest, sender).then(sendResponse, (error: unknown) => {
    const info = errorInfo(error);
    sendResponse({ ok: false, error: error instanceof Error ? error.message : "Extension operation failed", errorInfo: info });
  });
  return true;
});

chrome.tabs.onRemoved.addListener((tabId) => { void controller.navigated(tabId).catch(() => undefined); });
chrome.tabs.onUpdated.addListener((tabId, changes) => {
  // A full navigation/reload destroys the injected overlay. SPA video changes are
  // also reported by the content script, with a session ID to reject stale reports.
  if (changes.status === "loading") void controller.navigated(tabId).catch(() => undefined);
});
