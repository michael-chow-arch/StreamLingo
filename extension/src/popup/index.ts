import type { BackgroundRequest, BackgroundResponse, Snapshot } from "../shared/runtime-messages";
import { isYouTubeVideoUrl, validateSettings } from "../background/policy";
import { healthPresentation } from "./health-presentation";
import { AppError, DEFAULT_UI_LANGUAGE, errorInfo, errorFromInfo, formatError, formatStatus, isMessageKey, normalizeUiLanguage, t,
  type MessageKey, type UiErrorInfo, type UiLanguage, type UiStatus } from "../shared/i18n";
import { observeUiLanguage } from "../shared/language-preference";
import { isTranslationMode } from "../shared/config";
import { languageCapabilityIssue } from "../shared/language-capabilities";

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing popup element: ${id}`);
  return found as T;
}

const sessionButton = element<HTMLButtonElement>("session-button");
const saveButton = element<HTMLButtonElement>("save-button");
const healthButton = element<HTMLButtonElement>("health-button");
const languageSelect = element<HTMLSelectElement>("ui-language");
const modeSelect = element<HTMLSelectElement>("translation-mode");
const backendUrl = element<HTMLInputElement>("backend-url");
const fontSize = element<HTMLInputElement>("font-size");
const showSource = element<HTMLInputElement>("show-source");
const form = element<HTMLFormElement>("settings-form");
const formError = element("form-error");
const feedback = element("feedback");
let current: Snapshot | null = null;
let targetTabId: number | null = null;
let validTarget = false;
let busy = false;
let polling = false;
let dirty = false;
let startPending = false;
let startVersion = 0;
let language: UiLanguage = DEFAULT_UI_LANGUAGE;
let savedLanguage: UiLanguage = DEFAULT_UI_LANGUAGE;
let languageVersion = 0;
let languagePending = false;
let preferenceObserved = false;
let feedbackValue: UiStatus | null = null;
let formErrorValue: UiErrorInfo | null = null;
let healthCheckFailed = false;

async function request(message: BackgroundRequest): Promise<Snapshot> {
  const response: BackgroundResponse | undefined = await chrome.runtime.sendMessage(message);
  if (!response) throw new AppError("EXTENSION_UNRESPONSIVE");
  if (!response.ok) throw errorFromInfo(response.errorInfo ?? errorInfo(response.error));
  return response.snapshot;
}

function showFeedback(value: UiStatus, isError = false): void {
  feedbackValue = value;
  feedback.textContent = formatStatus(language, value);
  feedback.dataset.error = String(isError);
  feedback.hidden = false;
}

function applyLanguage(value: UiLanguage): void {
  language = value;
  document.documentElement.lang = language;
  languageSelect.value = language;
  languageSelect.setAttribute("aria-label", t(language, "interfaceLanguage"));
  for (const node of Array.from(document.querySelectorAll<HTMLElement>("[data-i18n]"))) {
    const key = node.dataset.i18n;
    if (key && isMessageKey(key)) node.textContent = t(language, key);
  }
  if (feedbackValue) feedback.textContent = formatStatus(language, feedbackValue);
  if (formErrorValue) formError.textContent = formatError(language, formErrorValue);
  // Re-render text only. Draft settings, validation, focus and open details stay intact.
  if (current) render(current);
  else {
    element("phase").textContent = t(language, "loading");
    element("session-description").textContent = t(language, "readingState");
    sessionButton.textContent = t(language, "start");
    element("health-status").textContent = t(language, "serviceUnchecked");
    element("mode-notice").textContent = t(language, "readingHealth");
    element("extension-origin").textContent = t(language, "reading");
  }
}

function render(snapshot: Snapshot, populate = false): void {
  current = snapshot;
  const { state, settings, health } = snapshot;
  const active = startPending || ["starting", "running", "stopping"].includes(state.phase);
  const visiblePhase = startPending && (state.phase === "idle" || state.phase === "error") ? "starting" : state.phase;
  if (populate) {
    backendUrl.value = settings.backendBaseUrl;
    fontSize.value = String(settings.fontSizePx);
    showSource.checked = settings.showSourceText;
    modeSelect.value = settings.translationMode;
    dirty = false;
  }
  const phase = element("phase");
  const labels: Record<typeof state.phase, MessageKey> = { idle: "phaseIdle", starting: "phaseStarting", running: "phaseRunning", stopping: "phaseStopping", error: "phaseError" };
  phase.textContent = t(language, labels[visiblePhase]);
  phase.dataset.state = visiblePhase;
  const description = element("session-description");
  description.textContent = visiblePhase === "starting" ? t(language, "connectingDescription") :
    state.phase === "error" ? formatError(language, state.errorInfo ?? errorInfo(state.message)) :
    state.phase === "running" ? t(language, state.tabId !== targetTabId ? "runningOther" : "runningHere") :
    state.phase === "stopping" ? t(language, "stoppingDescription") : t(language, validTarget ? "readyDescription" : "openYouTube");
  sessionButton.textContent = t(language, state.phase === "stopping" ? "stoppingButton" : active ? "stop" : busy ? "processing" : "start");
  sessionButton.dataset.action = active ? "stop" : "start";
  sessionButton.disabled = busy || state.phase === "stopping" || (!active && !validTarget);
  for (const input of [backendUrl, fontSize, showSource, modeSelect]) input.disabled = active || busy;
  saveButton.disabled = active || busy || !dirty;
  healthButton.disabled = busy || startPending || state.phase === "starting";
  element("extension-origin").textContent = `chrome-extension://${snapshot.extensionId}`;
  element("health-status").textContent = t(language, health ? health.status === "ready" ? "serviceConnected" :
    health.status === "starting" ? "serviceLoading" : "serviceError" : healthCheckFailed ? "serviceDisconnected" : "serviceUnchecked");
  const notice = element("mode-notice");
  const presentation = healthPresentation(health, language);
  notice.dataset.mode = presentation.mode;
  notice.textContent = presentation.notice;
  if (health && isTranslationMode(modeSelect.value)) {
    const issue = languageCapabilityIssue(health, modeSelect.value);
    if (issue) { notice.dataset.mode = "unsupported"; notice.textContent = formatError(language, issue); }
  }
}

function inputs() {
  return validateSettings({ backendBaseUrl: backendUrl.value, fontSizePx: fontSize.valueAsNumber, showSourceText: showSource.checked, translationMode: modeSelect.value });
}

async function save(): Promise<Snapshot> {
  formError.hidden = true;
  formErrorValue = null;
  backendUrl.removeAttribute("aria-invalid");
  fontSize.removeAttribute("aria-invalid");
  modeSelect.removeAttribute("aria-invalid");
  let settings;
  try { settings = inputs(); }
  catch (error) {
    formErrorValue = errorInfo(error);
    formError.textContent = formatError(language, formErrorValue);
    formError.hidden = false;
    const input = formErrorValue.code === "FONT_SIZE_INVALID" ? fontSize : formErrorValue.code === "TRANSLATION_MODE_INVALID" ? modeSelect : backendUrl;
    const details = input.closest("details");
    if (details) details.open = true;
    input.setAttribute("aria-invalid", "true");
    input.focus();
    throw error;
  }
  const snapshot = await request({ target: "background", type: "SAVE_SETTINGS", settings });
  healthCheckFailed = false;
  render(snapshot, true);
  return snapshot;
}

async function perform(operation: () => Promise<void>): Promise<void> {
  if (busy) return;
  busy = true;
  feedbackValue = null;
  feedback.hidden = true;
  if (current) render(current);
  try { await operation(); }
  catch (error) {
    showFeedback({ error: errorInfo(error) }, true);
    try { render(await request({ target: "background", type: "GET_SNAPSHOT" })); } catch { /* Keep the original actionable error. */ }
  } finally {
    busy = false;
    if (current) render(current);
  }
}

sessionButton.addEventListener("click", () => { void perform(async () => {
  if (startPending || (current && ["starting", "running", "stopping"].includes(current.state.phase))) {
    startVersion++;
    startPending = false;
    render(await request({ target: "background", type: "STOP_SESSION" }));
    return;
  }
  if (targetTabId === null || !validTarget) throw new AppError("YOUTUBE_REQUIRED");
  if (dirty) await save();
  const version = ++startVersion;
  startPending = true;
  // Do not keep the popup busy while the backend handshake is pending. Its
  // independent stop request cancels capture, and this generation ignores the
  // old start response if the user stopped or started another session.
  void request({ target: "background", type: "START_SESSION", tabId: targetTabId }).then((snapshot) => {
    if (version === startVersion) render(snapshot);
  }, async (error: unknown) => {
    if (version !== startVersion) return;
    showFeedback({ error: errorInfo(error) }, true);
    try {
      const snapshot = await request({ target: "background", type: "GET_SNAPSHOT" });
      if (version === startVersion) render(snapshot);
    } catch { /* Preserve the startup error. */ }
  }).finally(() => {
    if (version === startVersion) {
      startPending = false;
      if (current) render(current);
    }
  });
}); });

languageSelect.addEventListener("change", () => {
  const choice = normalizeUiLanguage(languageSelect.value);
  const version = ++languageVersion;
  languagePending = true;
  applyLanguage(choice);
  void request({ target: "background", type: "SET_UI_LANGUAGE", language: choice }).then((snapshot) => {
    if (version !== languageVersion) return;
    savedLanguage = snapshot.uiLanguage;
    languagePending = false;
    applyLanguage(snapshot.uiLanguage);
    render(snapshot);
  }, () => {
    if (version !== languageVersion) return;
    languagePending = false;
    applyLanguage(savedLanguage);
    showFeedback({ error: { code: "LANGUAGE_SAVE_FAILED" } }, true);
  });
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void perform(async () => { await save(); showFeedback({ key: "settingsSaved" }); });
});

form.addEventListener("input", () => { dirty = true; if (current) render(current); });
healthButton.addEventListener("click", () => { void perform(async () => {
  if (dirty) await save();
  healthCheckFailed = false;
  let snapshot;
  try { snapshot = await request({ target: "background", type: "CHECK_HEALTH" }); }
  catch (error) { healthCheckFailed = true; throw error; }
  render(snapshot);
  showFeedback({ key: snapshot.health?.status === "ready" ? "connectionOk" : "modelNotReady" }, snapshot.health?.status !== "ready");
}); });

const stopLanguageObserver = observeUiLanguage((value) => {
  preferenceObserved = true;
  savedLanguage = value;
  if (!languagePending) applyLanguage(value);
});

async function init(): Promise<void> {
  applyLanguage(language);
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    targetTabId = tab?.id ?? null;
    validTarget = isYouTubeVideoUrl(tab?.url);
    const snapshot = await request({ target: "background", type: "GET_SNAPSHOT" });
    if (!preferenceObserved && languageVersion === 0) applyLanguage(snapshot.uiLanguage);
    render(snapshot, true);
    // A read-only connection probe keeps demo/translation status explicit before capture.
    try { render(await request({ target: "background", type: "CHECK_HEALTH" })); }
    catch { healthCheckFailed = true; if (current) render(current); }
  } catch (error) {
    showFeedback({ error: errorInfo(error) }, true);
  }
}

void init();
const pollTimer = window.setInterval(() => {
  if (busy || polling) return;
  polling = true;
  void request({ target: "background", type: "GET_SNAPSHOT" }).then((snapshot) => render(snapshot)).catch(() => undefined).finally(() => { polling = false; });
}, 1200);
window.addEventListener("pagehide", () => { window.clearInterval(pollTimer); stopLanguageObserver(); });
