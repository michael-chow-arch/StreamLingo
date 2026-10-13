import type { HealthResponse } from "@streamlingo/protocol";
import { t, type UiLanguage } from "../shared/i18n";

export function healthPresentation(health: HealthResponse | null, language: UiLanguage = "zh-CN"): { mode: string; notice: string } {
  if (!health) return { mode: "unknown", notice: t(language, "healthUnknown") };
  if (health.mode === "demo") return { mode: "demo", notice: t(language, "healthDemo") };
  if (health.translation === "mock") return { mode: "mock", notice: t(language, "healthMock") };
  if (health.translation === "configured") return { mode: "configured", notice: t(language, "healthConfigured") };
  return { mode: "disabled", notice: t(language, "healthDisabled") };
}
