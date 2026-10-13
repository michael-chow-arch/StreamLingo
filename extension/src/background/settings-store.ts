import { DEFAULT_SETTINGS, type ExtensionSettings } from "../shared/config";
import { validateSettings } from "./policy";

export async function readSettings(): Promise<ExtensionSettings> {
  const stored = await chrome.storage.local.get("settings");
  try { return validateSettings(stored.settings); }
  catch { return { ...DEFAULT_SETTINGS }; }
}

export async function writeSettings(value: unknown): Promise<ExtensionSettings> {
  const settings = validateSettings(value);
  await chrome.storage.local.set({ settings });
  return settings;
}
