import type { HealthResponse } from "@streamlingo/protocol";
import { translationLanguages, type TranslationMode } from "./config";
import { AppError, type UiErrorInfo } from "./i18n";

export function languageCapabilityIssue(health: HealthResponse, mode: TranslationMode): UiErrorInfo | null {
  // New backends may omit capabilities until their speech model has loaded.
  if (health.status !== "ready" || health.asr !== "ready") return null;
  const { source, target } = translationLanguages(mode);
  if ((health.source_languages && !health.source_languages.includes(source)) ||
      (health.target_languages && !health.target_languages.includes(target))) return { code: "UNSUPPORTED_LANGUAGE" };
  if (mode !== "en-zh" && (!health.source_languages || !health.target_languages)) return { code: "LANGUAGE_CAPABILITIES_UNKNOWN" };
  return null;
}

export function assertLanguageSupport(health: HealthResponse, mode: TranslationMode): void {
  if (health.status === "error" || health.asr === "error") throw new AppError("ASR_FAILED");
  if (health.status !== "ready" || health.asr !== "ready") throw new AppError("ASR_NOT_READY");
  const issue = languageCapabilityIssue(health, mode);
  if (issue) throw new AppError(issue.code);
}
