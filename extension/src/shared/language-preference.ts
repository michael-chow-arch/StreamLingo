import { AppError, isUiLanguage, normalizeUiLanguage, type UiLanguage } from "./i18n";

export const UI_LANGUAGE_STORAGE_KEY = "uiLanguage";
let writeQueue: Promise<void> = Promise.resolve();

export async function readUiLanguage(): Promise<UiLanguage> {
  const saved = await chrome.storage.local.get(UI_LANGUAGE_STORAGE_KEY);
  return normalizeUiLanguage(saved[UI_LANGUAGE_STORAGE_KEY]);
}

export function writeUiLanguage(value: unknown): Promise<void> {
  if (!isUiLanguage(value)) return Promise.reject(new AppError("LANGUAGE_INVALID"));
  // A separate key avoids read/merge/write races with audio settings, including
  // saves from another popup. Rapid language choices keep their original order.
  const operation = writeQueue.then(() => chrome.storage.local.set({ [UI_LANGUAGE_STORAGE_KEY]: value }));
  writeQueue = operation.catch(() => undefined);
  return operation;
}

export function observeUiLanguage(onChange: (language: UiLanguage) => void): () => void {
  let revision = 0;
  let disposed = false;
  const listener = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
    if (area !== "local" || !Object.hasOwn(changes, UI_LANGUAGE_STORAGE_KEY)) return;
    revision++;
    if (!disposed) onChange(normalizeUiLanguage(changes[UI_LANGUAGE_STORAGE_KEY]?.newValue));
  };
  chrome.storage.onChanged.addListener(listener);
  void readUiLanguage().then((language) => {
    if (!disposed && revision === 0) onChange(language);
  }).catch(() => undefined);
  return () => { disposed = true; chrome.storage.onChanged.removeListener(listener); };
}
