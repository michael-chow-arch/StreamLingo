/** Observable UI states, distinct from the wire protocol. */
export type SessionState =
  | { readonly phase: "idle" }
  | {
      readonly phase: "starting" | "running" | "stopping";
      readonly sessionId: string;
      readonly tabId: number;
    }
  | {
      readonly phase: "error";
      readonly sessionId: string | null;
      readonly message: string;
      readonly errorInfo?: UiErrorInfo;
    };
import type { UiErrorInfo } from "./i18n";
