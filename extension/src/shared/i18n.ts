export type UiLanguage = "zh-CN" | "en";
export const DEFAULT_UI_LANGUAGE: UiLanguage = "zh-CN";
export function isUiLanguage(value: unknown): value is UiLanguage { return value === "zh-CN" || value === "en"; }
export function normalizeUiLanguage(value: unknown): UiLanguage { return isUiLanguage(value) ? value : DEFAULT_UI_LANGUAGE; }

const zh = {
  interfaceLanguage: "界面语言", eyebrow: "YouTube · 实时翻译字幕", sessionHeading: "当前会话", loading: "读取中",
  translationModeLabel: "翻译方向", modeEnZh: "英语 → 中文", modeZhEn: "中文 → 英语", modeAutoZh: "自动识别 → 中文", modeAutoEn: "自动识别 → 英语",
  localServiceRequired: "需要另行安装并启动本地识别与翻译服务。", projectLink: "项目与安装说明", contactLink: "联系作者", privacyLink: "隐私说明",
  readingState: "正在读取插件状态…", start: "开始字幕", stop: "停止字幕", stoppingButton: "正在停止…", processing: "正在处理…",
  captureHint: "开始后将标签页音频发送至本机服务以生成字幕。关闭弹窗后继续运行。", serviceHeading: "本地服务", serviceUnchecked: "尚未检查",
  serviceConnected: "已连接", serviceLoading: "模型加载中", serviceError: "服务异常", serviceDisconnected: "服务未连接",
  readingHealth: "正在读取本地服务的识别与翻译状态…", settingsSummary: "服务地址与字幕设置", backendLabel: "服务地址",
  backendHint: "支持本机 localhost 或 127.0.0.1 的 HTTP 地址。", fontLabel: "字幕字号", showSource: "显示原文",
  saveSettings: "保存设置", checkConnection: "测试连接", connectionInfo: "后端连接信息", originHint: "将此扩展来源加入后端的允许列表：",
  reading: "正在读取…", phaseIdle: "未启动", phaseStarting: "连接中", phaseRunning: "运行中", phaseStopping: "停止中", phaseError: "已停止 · 异常",
  connectingDescription: "正在连接服务并启动采集，可随时停止。", runningHere: "正在采集当前 YouTube 标签页的音频。",
  runningOther: "正在采集另一个 YouTube 标签页的音频。", stoppingDescription: "正在释放音频采集与连接…",
  readyDescription: "准备就绪。开始后，字幕将显示在视频播放器内。", openYouTube: "请先打开一个 YouTube 视频或直播播放页。",
  settingsSaved: "设置已保存，下次开始字幕时生效。", connectionOk: "本地服务连接正常。", modelNotReady: "服务可达，但识别模型尚未就绪。",
  healthUnknown: "连接本地服务后，显示语音识别与翻译的启用状态。",
  healthDemo: "测试模式：使用固定示例，不识别当前音频。用于检查采音与字幕显示链路。",
  healthMock: "原文使用实时识别；译文为测试输出，并非真实翻译。", healthConfigured: "语音识别与翻译已配置。译文在对应原文片段后补齐。",
  healthDisabled: "后端未启用翻译，目前仅显示原文识别结果。", subtitleRegion: "StreamLingo 实时字幕", subtitleConnecting: "正在连接字幕服务…",
  cueTranslated: "已译片段", cueCurrent: "当前字幕", cueEnglish: "实时原文", cueMock: "测试译文", cuePending: "翻译中",
  cueError: "翻译暂不可用", cueSkipped: "本句翻译已跳过", cueRecognizing: "识别中",
  readingPage: "第 {page}/{pages} 页", readingPending: "待读 {count} 页",
  statusDemo: "测试模式 · 固定示例，并非当前音频的识别结果", statusDisabled: "实时识别 · 翻译未启用",
  statusMock: "实时识别 · 译文为测试输出", statusConnected: "实时字幕已连接",
};
const en: Record<keyof typeof zh, string> = {
  interfaceLanguage: "Interface language", eyebrow: "YouTube · Live captions", sessionHeading: "Current session", loading: "Loading",
  translationModeLabel: "Translation direction", modeEnZh: "English → Chinese", modeZhEn: "Chinese → English", modeAutoZh: "Auto-detect → Chinese", modeAutoEn: "Auto-detect → English",
  localServiceRequired: "A separately installed local recognition and translation service is required.", projectLink: "Project & setup", contactLink: "Contact author", privacyLink: "Privacy",
  readingState: "Reading extension status…", start: "Start captions", stop: "Stop captions", stoppingButton: "Stopping…", processing: "Working…",
  captureHint: "Sends tab audio to your local service. Keeps running after this popup closes.", serviceHeading: "Local service", serviceUnchecked: "Not checked",
  serviceConnected: "Connected", serviceLoading: "Model loading", serviceError: "Service error", serviceDisconnected: "Disconnected",
  readingHealth: "Checking recognition and translation status…", settingsSummary: "Service and caption settings", backendLabel: "Service address",
  backendHint: "Local HTTP only: localhost or 127.0.0.1.", fontLabel: "Caption size", showSource: "Show original text",
  saveSettings: "Save settings", checkConnection: "Test connection", connectionInfo: "Backend connection details", originHint: "Add this extension origin to the backend allowlist:",
  reading: "Loading…", phaseIdle: "Idle", phaseStarting: "Connecting", phaseRunning: "Running", phaseStopping: "Stopping", phaseError: "Stopped · Error",
  connectingDescription: "Connecting and starting capture. You can stop at any time.", runningHere: "Capturing audio from this YouTube tab.",
  runningOther: "Capturing audio from another YouTube tab.", stoppingDescription: "Releasing audio capture and connection…",
  readyDescription: "Ready. Captions will appear inside the video player.", openYouTube: "Open a YouTube video or live stream first.",
  settingsSaved: "Settings saved. They apply when you next start captions.", connectionOk: "The local service is connected.", modelNotReady: "The service is reachable, but recognition is not ready yet.",
  healthUnknown: "Connect to the local service to check recognition and translation.",
  healthDemo: "Demo mode uses fixed samples, not the current audio. Use it to check capture and caption display.",
  healthMock: "Speech is recognized live. Translations are test output, not real translations.", healthConfigured: "Local recognition and translation are configured. Captions follow their source.",
  healthDisabled: "Translation is disabled on the backend. Only recognized source text is shown.", subtitleRegion: "StreamLingo live captions", subtitleConnecting: "Connecting to the caption service…",
  cueTranslated: "Translated segment", cueCurrent: "Current captions", cueEnglish: "Live transcript", cueMock: "Test translation", cuePending: "Translating",
  cueError: "Translation unavailable", cueSkipped: "Translation skipped", cueRecognizing: "Recognizing",
  readingPage: "Page {page}/{pages}", readingPending: "{count} pages queued",
  statusDemo: "Demo mode · Fixed samples, not recognition of the current audio", statusDisabled: "Live recognition · Translation disabled",
  statusMock: "Live recognition · Translations are test output", statusConnected: "Live captions connected",
};
export type MessageKey = keyof typeof zh;
export function t(language: UiLanguage, key: MessageKey): string { return (language === "en" ? en : zh)[key]; }
export function formatReadingProgress(language: UiLanguage, pageIndex: number, pageCount: number, pendingCount: number): string {
  const page = t(language, "readingPage").replace("{page}", String(pageIndex + 1)).replace("{pages}", String(pageCount));
  return pendingCount > 0 ? `${page} · ${t(language, "readingPending").replace("{count}", String(pendingCount))}` : page;
}
export function isMessageKey(value: string): value is MessageKey { return Object.hasOwn(zh, value); }

const errorMessages = {
  UNKNOWN: ["操作失败，请重试。", "Something went wrong. Please try again."],
  SETTINGS_INVALID: ["设置格式无效。", "The settings format is invalid."],
  BACKEND_URL_REQUIRED: ["请输入本地服务地址。", "Enter the local service address."],
  BACKEND_URL_INVALID: ["服务地址无效，例如 http://127.0.0.1:8765。", "Enter a valid address, such as http://127.0.0.1:8765."],
  BACKEND_URL_LOCAL_ONLY: ["仅支持本机 HTTP 根地址，例如 http://127.0.0.1:8765。", "Use a local HTTP base address, such as http://127.0.0.1:8765."],
  FONT_SIZE_INVALID: ["字幕字号必须为 16–48 之间的整数。", "Caption size must be a whole number from 16 to 48."],
  SOURCE_SETTING_INVALID: ["原文显示设置无效。", "The original text display setting is invalid."],
  TRANSLATION_MODE_INVALID: ["翻译方向设置无效。", "The translation direction is invalid."],
  LANGUAGE_CAPABILITIES_UNKNOWN: ["当前服务未提供语言能力信息。请升级后端后使用此模式，或选择英语 → 中文。", "This service does not report language capabilities. Update the backend for this mode, or select English → Chinese."],
  UNSUPPORTED_LANGUAGE: ["当前识别模型或服务不支持所选语言。中文和自动识别需要多语言模型，不能使用 base.en 等仅英语模型。", "The model or service does not support this language. Chinese and auto-detection require a multilingual model, not an English-only model such as base.en."],
  LANGUAGE_INVALID: ["不支持此界面语言。", "This interface language is not supported."],
  LANGUAGE_SAVE_FAILED: ["界面语言未能保存，请重试。", "The interface language could not be saved. Please try again."],
  YOUTUBE_REQUIRED: ["请在 YouTube 视频或直播播放页启动字幕。", "Start captions on a YouTube video or live stream page."],
  TAB_INACTIVE: ["请先切换到需要字幕的 YouTube 标签页。", "Switch to the YouTube tab you want to caption first."],
  TAB_MISSING: ["没有找到目标标签页。", "The target tab could not be found."],
  SESSION_ACTIVE: ["已有会话运行，请先停止当前字幕。", "A session is already active. Stop it before starting another."],
  SETTINGS_LOCKED: ["请先停止字幕，再修改设置。", "Stop captions before changing these settings."],
  START_CANCELLED: ["字幕启动已取消。", "Caption startup was cancelled."],
  START_FAILED: ["音频采集未能启动，请重试。", "Audio capture could not start. Please try again."],
  SESSION_ENDED: ["字幕服务已结束会话，请重新开始。", "The caption service ended the session. Start again to reconnect."],
  RECOVERY_FAILED: ["无法恢复音频进程，已释放采集，请重新开始。", "The audio process could not be recovered. Capture was released; please start again."],
  OFFSCREEN_TIMEOUT: ["音频进程响应超时，请重新开始。", "The audio process timed out. Please start again."],
  OFFSCREEN_INVALID: ["音频进程未返回有效状态。", "The audio process returned an invalid state."],
  OFFSCREEN_CLOSED: ["音频采集页面已关闭。", "The audio capture page was closed."],
  INVALID_SENDER: ["插件消息来源无效。", "The extension message came from an invalid source."],
  INVALID_REQUEST: ["不支持或无效的插件请求。", "The extension request is invalid or unsupported."],
  SERVICE_UNREACHABLE: ["无法连接本地服务，请检查地址、服务状态和扩展来源配置。", "Cannot connect to the local service. Check its address, status, and allowed extension origin."],
  SERVICE_HTTP: ["本地服务返回 HTTP 错误。", "The local service returned an HTTP error."],
  EXTENSION_UNRESPONSIVE: ["插件未响应，请重新打开弹窗。", "The extension did not respond. Reopen the popup."],
  CAPTURE_DENIED: ["浏览器未允许标签页采音，请重新点击开始字幕。", "Tab audio capture was not allowed. Click Start captions again."],
  CAPTURE_FAILED: ["浏览器无法采集此标签页的音频，请重新开始。", "The browser could not capture this tab's audio. Please start again."],
  NO_AUDIO_TRACK: ["标签页没有可采集的音轨。", "The tab has no audio track to capture."],
  AUDIO_ENDED: ["标签页音频采集已结束，请重新开始字幕。", "Tab audio capture ended. Start captions again."],
  AUDIO_SAMPLE_RATE: ["浏览器未提供所需的 16 kHz 音频处理。", "The browser did not provide the required 16 kHz audio processing."],
  AUDIO_PROCESSING: ["浏览器音频处理失败，请重新开始字幕。", "Browser audio processing failed. Start captions again."],
  AUDIO_RESUME: ["浏览器未启动音频处理，请重新点击开始字幕。", "Browser audio processing did not start. Click Start captions again."],
  CONNECTION_CLOSED: ["本地服务连接已断开，请重新开始字幕。", "The local service disconnected. Start captions again."],
  CONNECTION_TIMEOUT: ["本地服务未及时就绪，请检查服务状态。", "The local service was not ready in time. Check its status."],
  AUDIO_SEND_FAILED: ["发送音频失败，请重新连接本地服务。", "Audio could not be sent. Reconnect to the local service."],
  AUDIO_INVALID: ["音频编码格式错误，已停止采集。", "The audio format was invalid. Capture was stopped."],
  SESSION_MISMATCH: ["本地服务返回了不匹配的音频会话。", "The local service returned a different audio session."],
  INVALID_MESSAGE: ["本地服务返回了无效的协议消息。", "The local service returned an invalid protocol message."],
  UNSUPPORTED_PROTOCOL: ["本地服务协议不兼容，请更新插件或服务。", "The service protocol is incompatible. Update the extension or backend."],
  ASR_NOT_READY: ["语音识别尚未就绪，请等待模型加载后重试。", "Speech recognition is not ready. Wait for the model to load, then retry."],
  ASR_FAILED: ["语音识别失败，请检查本地服务后重试。", "Speech recognition failed. Check the local service and retry."],
  TRANSLATION_FAILED: ["本句翻译失败，继续显示原文。", "Translation failed for this segment. Source text remains available."],
  TRANSLATION_TIMEOUT: ["本句翻译超时，继续显示原文。", "Translation timed out for this segment. Source text remains available."],
  TRANSLATION_BACKLOG: ["翻译处理落后，本句翻译已跳过。", "Translation is falling behind. This segment was skipped."],
  AUDIO_BACKLOG: ["音频处理积压过多，已停止字幕，请检查本地服务负载。", "Audio processing fell too far behind. Captions stopped; check the service load."],
  SESSION_CONFLICT: ["服务已有活动会话，请先结束原有会话。", "The service already has an active session. End it first."],
  INTERNAL_ERROR: ["本地服务发生内部错误，请检查服务后重新开始。", "The local service encountered an internal error. Check it and start again."],
} as const;
export type UiErrorCode = keyof typeof errorMessages;
export interface UiErrorInfo { readonly code: UiErrorCode; readonly detail?: string }
export type UiStatus = { readonly key: MessageKey } | { readonly error: UiErrorInfo };
export function isUiErrorCode(value: unknown): value is UiErrorCode { return typeof value === "string" && Object.hasOwn(errorMessages, value); }
function safeDetail(value: unknown): string { return typeof value === "string" ? value.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 400).trim() : ""; }
export class AppError extends Error {
  constructor(readonly code: UiErrorCode, readonly detail?: string) {
    super(detail || errorMessages[code][0]);
    this.name = "AppError";
  }
}
export function errorInfo(value: unknown): UiErrorInfo {
  if (value && typeof value === "object") {
    if ("code" in value && isUiErrorCode(value.code)) {
      const detail = "detail" in value ? safeDetail(value.detail) : "";
      return detail ? { code: value.code, detail } : { code: value.code };
    }
    const name = "name" in value ? value.name : "";
    if (name === "NotAllowedError" || name === "SecurityError") return { code: "CAPTURE_DENIED" };
    if (name === "NotFoundError") return { code: "NO_AUDIO_TRACK" };
    if (name === "NotReadableError") return { code: "CAPTURE_FAILED" };
    if (name === "AbortError") return { code: "START_CANCELLED" };
  }
  const detail = safeDetail(value instanceof Error ? value.message : typeof value === "string" ? value : "");
  return detail ? { code: "UNKNOWN", detail } : { code: "UNKNOWN" };
}
export function errorFromInfo(info: UiErrorInfo): AppError {
  const normalized = errorInfo(info);
  return new AppError(normalized.code, normalized.detail);
}
export function formatError(language: UiLanguage, info: UiErrorInfo): string {
  const code = isUiErrorCode(info.code) ? info.code : "UNKNOWN";
  const message = errorMessages[code][language === "en" ? 1 : 0];
  const detail = safeDetail(info.detail);
  return detail && (code === "UNKNOWN" || code === "SERVICE_HTTP") ? `${message} ${detail}` : message;
}
export function formatStatus(language: UiLanguage, status: UiStatus): string { return "key" in status ? t(language, status.key) : formatError(language, status.error); }
