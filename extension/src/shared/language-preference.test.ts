import assert from "node:assert/strict";
import test from "node:test";
import { DEFAULT_SETTINGS } from "./config";
import { observeUiLanguage, readUiLanguage, writeUiLanguage } from "./language-preference";
import { writeSettings } from "../background/settings-store";

function storageFixture(initial: Record<string, unknown> = {}) {
  const values = { ...initial };
  const writes: Record<string, unknown>[] = [];
  const listeners = new Set<(changes: Record<string, chrome.storage.StorageChange>, area: string) => void>();
  const local = {
    get: async (key: string): Promise<Record<string, unknown>> => ({ [key]: values[key] }),
    set: async (update: Record<string, unknown>): Promise<void> => {
      writes.push({ ...update });
      const changes = Object.fromEntries(Object.entries(update).map(([key, newValue]) => [key, { oldValue: values[key], newValue }]));
      Object.assign(values, update);
      for (const listener of listeners) listener(changes, "local");
    },
  };
  const previous = Object.getOwnPropertyDescriptor(globalThis, "chrome");
  Object.defineProperty(globalThis, "chrome", { configurable: true, value: { storage: { local, onChanged: {
    addListener: (listener: (changes: Record<string, chrome.storage.StorageChange>, area: string) => void) => listeners.add(listener),
    removeListener: (listener: (changes: Record<string, chrome.storage.StorageChange>, area: string) => void) => listeners.delete(listener),
  } } } });
  return { local, values, writes, listeners, restore: () => { if (previous) Object.defineProperty(globalThis, "chrome", previous); else Reflect.deleteProperty(globalThis, "chrome"); } };
}

test("language and settings saves preserve each other during concurrent updates", async () => {
  const fake = storageFixture({ settings: DEFAULT_SETTINGS });
  try {
    assert.equal(await readUiLanguage(), "zh-CN");
    const changedSettings = { ...DEFAULT_SETTINGS, backendBaseUrl: "http://localhost:9000", fontSizePx: 30 };
    await Promise.all([writeUiLanguage("en"), writeSettings(changedSettings)]);
    assert.equal(fake.values.uiLanguage, "en");
    assert.deepEqual(fake.values.settings, changedSettings);
    assert.deepEqual(fake.writes.find((write) => "uiLanguage" in write), { uiLanguage: "en" });
    await writeUiLanguage("zh-CN");
    assert.deepEqual(fake.values.settings, changedSettings);
  } finally { fake.restore(); }
});

test("rapid language changes persist in order and reject unsupported values", async () => {
  const fake = storageFixture();
  try {
    await Promise.all([writeUiLanguage("en"), writeUiLanguage("zh-CN"), writeUiLanguage("en")]);
    assert.equal(await readUiLanguage(), "en");
    assert.deepEqual(fake.writes.map((write) => write.uiLanguage), ["en", "zh-CN", "en"]);
    await assert.rejects(writeUiLanguage("hi"), { code: "LANGUAGE_INVALID" });
  } finally { fake.restore(); }
});

test("a late initial storage read cannot revert a newer language event", async () => {
  const fake = storageFixture();
  let finish!: (value: Record<string, unknown>) => void;
  fake.local.get = () => new Promise((resolve) => { finish = resolve; });
  const seen: string[] = [];
  const stop = observeUiLanguage((language) => seen.push(language));
  try {
    await fake.local.set({ uiLanguage: "en" });
    finish({ uiLanguage: "zh-CN" });
    await Promise.resolve();
    await Promise.resolve();
    assert.deepEqual(seen, ["en"]);
    stop();
    assert.equal(fake.listeners.size, 0);
    await fake.local.set({ uiLanguage: "zh-CN" });
    assert.deepEqual(seen, ["en"]);
  } finally { stop(); fake.restore(); }
});
