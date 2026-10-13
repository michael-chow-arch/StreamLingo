import type { OffscreenRequest, OffscreenResponse } from "../shared/runtime-messages";
import { AppError } from "../shared/i18n";

const OFFSCREEN_URL = "offscreen.html";

export async function hasOffscreen(): Promise<boolean> {
  const contexts = await chrome.runtime.getContexts({
    contextTypes: [chrome.runtime.ContextType.OFFSCREEN_DOCUMENT],
    documentUrls: [chrome.runtime.getURL(OFFSCREEN_URL)],
  });
  return contexts.length > 0;
}

export async function ensureOffscreen(): Promise<void> {
  if (await hasOffscreen()) return;
  // Chrome's official tabcapture-recorder sample establishes this capture pattern.
  // https://github.com/GoogleChrome/chrome-extensions-samples/tree/main/functional-samples/sample.tabcapture-recorder
  await chrome.offscreen.createDocument({
    url: OFFSCREEN_URL,
    reasons: [chrome.offscreen.Reason.USER_MEDIA],
    justification: "Capture the user-selected YouTube tab and stream audio to the local subtitle service.",
  });
}

export async function closeOffscreen(): Promise<void> {
  if (await hasOffscreen()) await chrome.offscreen.closeDocument();
}

export function withTimeout<T>(promise: Promise<T>, milliseconds: number, error: Error): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => { timer = setTimeout(() => reject(error), milliseconds); });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

export async function sendOffscreen(message: OffscreenRequest, timeoutMs = 20000): Promise<OffscreenResponse> {
  const response: unknown = await withTimeout(chrome.runtime.sendMessage(message), timeoutMs, new AppError("OFFSCREEN_TIMEOUT"));
  if (!response || typeof response !== "object" || !("ok" in response)) {
    throw new AppError("OFFSCREEN_INVALID");
  }
  return response as OffscreenResponse;
}
