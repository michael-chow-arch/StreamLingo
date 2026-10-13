import { isTranslationMode, type ExtensionSettings } from "../shared/config";
import { AppError } from "../shared/i18n";

export function validateSettings(value: unknown): ExtensionSettings {
  if (!value || typeof value !== "object") throw new AppError("SETTINGS_INVALID");
  const input = value as Partial<ExtensionSettings>;
  if (typeof input.backendBaseUrl !== "string") throw new AppError("BACKEND_URL_REQUIRED");
  let url: URL;
  try { url = new URL(input.backendBaseUrl.trim()); }
  catch { throw new AppError("BACKEND_URL_INVALID"); }
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname) ||
      url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new AppError("BACKEND_URL_LOCAL_ONLY");
  }
  if (typeof input.fontSizePx !== "number" || !Number.isInteger(input.fontSizePx) ||
      input.fontSizePx < 16 || input.fontSizePx > 48) {
    throw new AppError("FONT_SIZE_INVALID");
  }
  if (typeof input.showSourceText !== "boolean") throw new AppError("SOURCE_SETTING_INVALID");
  const translationMode = input.translationMode === undefined ? "en-zh" : input.translationMode;
  if (!isTranslationMode(translationMode)) throw new AppError("TRANSLATION_MODE_INVALID");
  return { backendBaseUrl: url.origin, fontSizePx: input.fontSizePx, showSourceText: input.showSourceText, translationMode };
}

export function isYouTubeVideoUrl(value: string | undefined): boolean {
  if (!value) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ["www.youtube.com", "youtube.com"].includes(url.hostname) &&
      ((url.pathname === "/watch" && Boolean(url.searchParams.get("v"))) || /^\/live\/[^/]+\/?$/.test(url.pathname));
  } catch { return false; }
}

export function isExtensionPage(sender: chrome.runtime.MessageSender, page: string, extensionId: string): boolean {
  return sender.id === extensionId && !sender.tab && sender.url === `chrome-extension://${extensionId}/${page}`;
}
