import type { SourceLanguage, TargetLanguage } from "@streamlingo/protocol";

export const TRANSLATION_MODES = ["en-zh", "zh-en", "auto-zh", "auto-en"] as const;
export type TranslationMode = typeof TRANSLATION_MODES[number];
export function isTranslationMode(value: unknown): value is TranslationMode {
  return typeof value === "string" && TRANSLATION_MODES.some((mode) => mode === value);
}
export function translationLanguages(mode: TranslationMode): { source: SourceLanguage; target: TargetLanguage } {
  return { source: mode.startsWith("auto-") ? "auto" : mode.startsWith("zh-") ? "zh" : "en",
    target: mode.endsWith("-en") ? "en" : "zh-CN" };
}

/** Browser-owned settings. Model credentials stay in the backend. */
export interface ExtensionSettings {
  readonly backendBaseUrl: string;
  readonly showSourceText: boolean;
  readonly fontSizePx: number;
  readonly translationMode: TranslationMode;
}

export const DEFAULT_SETTINGS: ExtensionSettings = {
  backendBaseUrl: "http://127.0.0.1:8765",
  showSourceText: true,
  fontSizePx: 24,
  translationMode: "en-zh",
};
