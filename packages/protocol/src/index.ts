export { parseHealthResponse, parseServerMessage } from "./validation";

/** Wire types shared by the extension and the runtime validation boundary. */
export type ProtocolVersion = 1;
export type SourceLanguage = "en" | "zh" | "auto";
export type TargetLanguage = "zh-CN" | "en";

export interface AudioFormat {
  readonly encoding: "pcm_s16le";
  readonly sample_rate: 16000;
  readonly channels: 1;
}

export interface HealthResponse {
  readonly protocol_version: ProtocolVersion;
  readonly mode: "demo" | "whisperlivekit";
  readonly status: "starting" | "ready" | "error";
  readonly asr: "loading" | "ready" | "error";
  readonly translation: "disabled" | "mock" | "configured";
  /** Absent on older servers or while the speech model is loading. */
  readonly source_languages?: readonly SourceLanguage[] | undefined;
  readonly target_languages?: readonly TargetLanguage[] | undefined;
}

export interface StartMessage {
  readonly type: "start";
  readonly protocol_version: ProtocolVersion;
  readonly session_id: string;
  readonly source_language: SourceLanguage;
  readonly target_language: TargetLanguage;
  readonly audio: AudioFormat;
}

export interface StopMessage {
  readonly type: "stop";
  readonly session_id: string;
}

export type ClientMessage = StartMessage | StopMessage;

export interface ReadyMessage {
  readonly type: "ready";
  readonly protocol_version: ProtocolVersion;
  readonly session_id: string;
  readonly mode: HealthResponse["mode"];
  readonly translation: HealthResponse["translation"];
  readonly source_language?: SourceLanguage | undefined;
  readonly target_language?: TargetLanguage | undefined;
}

export type TranslationState =
  | { readonly status: "disabled"; readonly text: null }
  | { readonly status: "pending"; readonly text: null }
  | { readonly status: "complete"; readonly text: string; readonly is_mock: boolean }
  | { readonly status: "error"; readonly text: null }
  | { readonly status: "skipped"; readonly text: null };

export interface SubtitleMessage {
  readonly type: "subtitle";
  readonly session_id: string;
  readonly segment_id: number;
  readonly revision: number;
  readonly start_ms: number;
  readonly end_ms: number;
  readonly source_text: string;
  readonly source_final: boolean;
  /** Selected session mode, not a per-word language detection claim. */
  readonly source_language?: SourceLanguage | undefined;
  readonly target_language?: TargetLanguage | undefined;
  readonly translation: TranslationState;
}

export type ErrorCode =
  | "INVALID_MESSAGE"
  | "UNSUPPORTED_PROTOCOL"
  | "UNSUPPORTED_LANGUAGE"
  | "ASR_NOT_READY"
  | "ASR_FAILED"
  | "TRANSLATION_FAILED"
  | "TRANSLATION_TIMEOUT"
  | "TRANSLATION_BACKLOG"
  | "AUDIO_BACKLOG"
  | "SESSION_CONFLICT"
  | "INTERNAL_ERROR";

export interface ErrorMessage {
  readonly type: "error";
  /** Null is permitted before a valid start message has been accepted. */
  readonly session_id: string | null;
  readonly segment_id: number | null;
  readonly code: ErrorCode;
  readonly message: string;
  readonly fatal: boolean;
}

export interface StoppedMessage {
  readonly type: "stopped";
  readonly session_id: string;
  readonly reason: "user" | "error";
}

export type ServerMessage =
  | ReadyMessage
  | SubtitleMessage
  | ErrorMessage
  | StoppedMessage;
