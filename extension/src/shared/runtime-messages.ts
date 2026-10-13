import type { HealthResponse, ServerMessage, SubtitleMessage } from "@streamlingo/protocol";
import type { ExtensionSettings } from "./config";
import type { SessionState } from "./session";
import type { UiErrorInfo, UiLanguage, UiStatus } from "./i18n";

export interface Snapshot {
  readonly state: SessionState;
  readonly settings: ExtensionSettings;
  readonly extensionId: string;
  readonly health: HealthResponse | null;
  readonly uiLanguage: UiLanguage;
}

export type BackgroundRequest =
  | { target: "background"; type: "GET_SNAPSHOT" }
  | { target: "background"; type: "CHECK_HEALTH" }
  | { target: "background"; type: "START_SESSION"; tabId: number }
  | { target: "background"; type: "STOP_SESSION" }
  | { target: "background"; type: "SAVE_SETTINGS"; settings: ExtensionSettings }
  | { target: "background"; type: "SET_UI_LANGUAGE"; language: UiLanguage }
  | { target: "background"; type: "OFFSCREEN_EVENT"; sessionId: string; event: ServerMessage }
  | { target: "background"; type: "OFFSCREEN_FAILED"; sessionId: string; message: string; errorInfo?: UiErrorInfo }
  | { target: "background"; type: "CONTENT_NAVIGATED"; sessionId: string };

export type BackgroundResponse =
  | { ok: true; snapshot: Snapshot }
  | { ok: false; error: string; errorInfo?: UiErrorInfo };

export type OffscreenRequest =
  | { target: "offscreen"; type: "OFFSCREEN_START"; sessionId: string; tabId: number; streamId: string; settings: ExtensionSettings }
  | { target: "offscreen"; type: "OFFSCREEN_STOP"; sessionId: string }
  | { target: "offscreen"; type: "OFFSCREEN_QUERY" };

export type OffscreenResponse =
  | { ok: true; state: SessionState }
  | { ok: false; error: string; errorInfo?: UiErrorInfo };

export type ContentMessage =
  | { target: "content"; type: "CONTENT_START"; sessionId: string; settings: ExtensionSettings }
  | { target: "content"; type: "CONTENT_SUBTITLE"; subtitle: SubtitleMessage }
  | { target: "content"; type: "CONTENT_STATUS"; sessionId: string; status: UiStatus }
  | { target: "content"; type: "CONTENT_STOP"; sessionId: string };
