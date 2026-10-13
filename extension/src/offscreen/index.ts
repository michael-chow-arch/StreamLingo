import type { ServerMessage } from "@streamlingo/protocol";
import type { BackgroundRequest, OffscreenRequest, OffscreenResponse } from "../shared/runtime-messages";
import type { SessionState } from "../shared/session";
import { TabAudioCapture } from "./capture";
import { LiveClient } from "./live-client";
import { AppError, errorInfo, type UiErrorInfo } from "../shared/i18n";

interface ActiveSession {
  readonly id: string;
  readonly tabId: number;
  readonly capture: TabAudioCapture;
  readonly client: LiveClient;
}

let active: ActiveSession | undefined;
let state: SessionState = { phase: "idle" };

function emit(message: BackgroundRequest): void {
  // START may be awaiting our response in the service worker. Never await a
  // round trip to it from this startup path (and avoid a circular message wait).
  void chrome.runtime.sendMessage(message).catch(() => undefined);
}

async function release(session: ActiveSession, nextState: SessionState): Promise<void> {
  if (active !== session) return;
  active = undefined; // Invalidate pending start and late packets synchronously.
  state = nextState;
  session.client.close();
  await session.capture.close();
}

function fail(session: ActiveSession, message: string, info = errorInfo(message)): void {
  if (active !== session) return;
  emit({ target: "background", type: "OFFSCREEN_FAILED", sessionId: session.id, message, errorInfo: info });
  void release(session, { phase: "error", sessionId: session.id, message, errorInfo: info });
}

function receive(session: ActiveSession, event: ServerMessage): void {
  if (active !== session) return;
  if (event.type === "ready") {
    state = { phase: "running", sessionId: session.id, tabId: session.tabId };
  }
  emit({ target: "background", type: "OFFSCREEN_EVENT", sessionId: session.id, event });
  if (event.type === "error" && event.fatal) {
    void release(session, { phase: "error", sessionId: session.id, message: event.message, errorInfo: { code: event.code, detail: event.message } });
  } else if (event.type === "stopped") {
    void release(session, { phase: "idle" });
  }
}

async function start(request: Extract<OffscreenRequest, { type: "OFFSCREEN_START" }>): Promise<OffscreenResponse> {
  if (active) return failure({ code: "SESSION_ACTIVE" });
  const session: ActiveSession = {
    id: request.sessionId,
    tabId: request.tabId,
    capture: new TabAudioCapture(
      (packet) => { if (active === session) session.client.sendAudio(packet); },
      (message, info) => fail(session, message, info),
    ),
    client: new LiveClient({
      sessionId: request.sessionId,
      backendBaseUrl: request.settings.backendBaseUrl,
      translationMode: request.settings.translationMode,
      onMessage: (event) => receive(session, event),
      onFailure: (message, info) => fail(session, message, info),
    }),
  };
  active = session;
  state = { phase: "starting", sessionId: session.id, tabId: session.tabId };
  try {
    // Consume Chrome's short-lived stream ID first, keeping original sound alive
    // while the server prepares. The worklet gate opens only after ready.
    await session.capture.open(request.streamId);
    if (active !== session) return failure({ code: "START_CANCELLED" });
    await session.client.start();
    if (active !== session) return failure({ code: "START_CANCELLED" });
    session.capture.startSending();
    return { ok: true, state };
  } catch (error) {
    const info = errorInfo(error);
    const message = error instanceof Error ? error.message : new AppError("START_FAILED").message;
    fail(session, message, info);
    return failure(info);
  }
}

function failure(info: UiErrorInfo): OffscreenResponse {
  return { ok: false, error: new AppError(info.code, info.detail).message, errorInfo: info };
}

async function handle(request: OffscreenRequest): Promise<OffscreenResponse> {
  switch (request.type) {
    case "OFFSCREEN_QUERY":
      return { ok: true, state };
    case "OFFSCREEN_START":
      return start(request);
    case "OFFSCREEN_STOP":
      if (active?.id === request.sessionId) await release(active, { phase: "idle" });
      else if (state.phase === "error" && state.sessionId === request.sessionId) state = { phase: "idle" };
      return { ok: true, state };
  }
}

chrome.runtime.onMessage.addListener((request: OffscreenRequest, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || sender.tab || request?.target !== "offscreen") return false;
  void handle(request).then(sendResponse, (error: unknown) => sendResponse(failure(errorInfo(error))));
  return true;
});

window.addEventListener("pagehide", () => {
  if (active) {
    emit({ target: "background", type: "OFFSCREEN_FAILED", sessionId: active.id, message: new AppError("OFFSCREEN_CLOSED").message, errorInfo: { code: "OFFSCREEN_CLOSED" } });
    void release(active, { phase: "idle" });
  }
});
