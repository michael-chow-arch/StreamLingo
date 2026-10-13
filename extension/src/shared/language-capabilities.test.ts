import assert from "node:assert/strict";
import test from "node:test";
import type { HealthResponse } from "@streamlingo/protocol";
import { TRANSLATION_MODES } from "./config";
import { assertLanguageSupport, languageCapabilityIssue } from "./language-capabilities";

const legacy: HealthResponse = { protocol_version: 1, mode: "whisperlivekit", status: "ready", asr: "ready", translation: "configured" };
test("loading models without capabilities are not misreported as outdated or unsupported", () => {
  const loading = { ...legacy, status: "starting" as const, asr: "loading" as const };
  assert.equal(languageCapabilityIssue(loading, "auto-en"), null);
  assert.throws(() => assertLanguageSupport(loading, "auto-en"), { code: "ASR_NOT_READY" });
  assert.throws(() => assertLanguageSupport({ ...legacy, asr: "error" }, "en-zh"), { code: "ASR_FAILED" });
});
test("legacy services retain the original mode but never silently downgrade new modes", () => {
  assert.equal(languageCapabilityIssue(legacy, "en-zh"), null);
  for (const mode of ["zh-en", "auto-zh", "auto-en"] as const) {
    assert.throws(() => assertLanguageSupport(legacy, mode), { code: "LANGUAGE_CAPABILITIES_UNKNOWN" });
  }
});
test("explicit capabilities allow each mode and English-only models reject Chinese and auto", () => {
  const multilingual = { ...legacy, source_languages: ["en", "zh", "auto"] as const, target_languages: ["zh-CN", "en"] as const };
  for (const mode of TRANSLATION_MODES) assert.equal(languageCapabilityIssue(multilingual, mode), null);
  const englishOnly = { ...multilingual, source_languages: ["en"] as const };
  assert.equal(languageCapabilityIssue(englishOnly, "en-zh"), null);
  for (const mode of ["zh-en", "auto-zh", "auto-en"] as const) {
    assert.equal(languageCapabilityIssue(englishOnly, mode)?.code, "UNSUPPORTED_LANGUAGE");
  }
  assert.equal(languageCapabilityIssue({ ...multilingual, target_languages: ["zh-CN"] }, "auto-en")?.code, "UNSUPPORTED_LANGUAGE");
});
