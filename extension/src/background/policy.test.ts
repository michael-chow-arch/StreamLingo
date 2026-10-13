import assert from "node:assert/strict";
import test from "node:test";
import { isExtensionPage, isYouTubeVideoUrl, validateSettings } from "./policy";

const settings = { backendBaseUrl: "http://127.0.0.1:8765", fontSizePx: 24, showSourceText: true };

test("old settings migrate to English to Chinese and all new modes are validated", () => {
  assert.equal(validateSettings(settings).translationMode, "en-zh");
  for (const translationMode of ["en-zh", "zh-en", "auto-zh", "auto-en"] as const) {
    assert.equal(validateSettings({ ...settings, translationMode }).translationMode, translationMode);
  }
  assert.throws(() => validateSettings({ ...settings, translationMode: "hi-en" }), { code: "TRANSLATION_MODE_INVALID" });
});

test("settings permit loopback origins and reject remote/path/credential endpoints", () => {
  assert.equal(validateSettings({ ...settings, backendBaseUrl: " http://localhost:9000/ " }).backendBaseUrl, "http://localhost:9000");
  for (const backendBaseUrl of ["https://127.0.0.1:8765", "http://example.com", "http://localhost.evil.test", "http://user@localhost:8765", "http://127.0.0.1:8765/health", "http://127.0.0.1:8765?target=x"]) {
    assert.throws(() => validateSettings({ ...settings, backendBaseUrl }));
  }
  for (const fontSizePx of [NaN, 15, 49, 24.1]) assert.throws(() => validateSettings({ ...settings, fontSizePx }));
  assert.throws(() => validateSettings({ ...settings, showSourceText: "true" }));
});

test("only YouTube playback URLs may start capture", () => {
  assert.equal(isYouTubeVideoUrl("https://www.youtube.com/watch?v=abc"), true);
  assert.equal(isYouTubeVideoUrl("https://www.youtube.com/live/abc"), true);
  for (const url of ["https://www.youtube.com/", "https://www.youtube.com/watch", "https://www.youtube.com.evil.test/watch?v=abc", "http://www.youtube.com/watch?v=abc", "chrome://extensions"]) {
    assert.equal(isYouTubeVideoUrl(url), false);
  }
});

test("popup controls cannot be impersonated by a webpage or content script", () => {
  const sender = { id: "test", url: "chrome-extension://test/popup.html" };
  assert.equal(isExtensionPage(sender, "popup.html", "test"), true);
  assert.equal(isExtensionPage({ ...sender, tab: { id: 1 } as chrome.tabs.Tab }, "popup.html", "test"), false);
  assert.equal(isExtensionPage({ ...sender, url: "https://www.youtube.com/watch?v=abc" }, "popup.html", "test"), false);
  assert.equal(isExtensionPage({ ...sender, id: "another" }, "popup.html", "test"), false);
});
