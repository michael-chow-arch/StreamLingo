import assert from "node:assert/strict";
import { test } from "node:test";
import { parseHealthResponse, parseServerMessage } from "./validation";

const session = "f84428dc-f217-4a8b-b034-f3e5a0cc204c";
const base = {
  type: "subtitle", session_id: session, segment_id: 1, revision: 1,
  start_ms: 0, end_ms: 500, source_text: "Hello", source_final: true,
  translation: { status: "disabled", text: null },
};

test("accepts real and explicitly marked demo messages", () => {
  assert.equal(parseServerMessage(base).type, "subtitle");
  assert.equal(parseServerMessage({ ...base,
    translation: { status: "complete", text: "你好", is_mock: true } }).type, "subtitle");
  assert.equal(parseHealthResponse({ protocol_version: 1, mode: "demo", status: "ready",
    asr: "ready", translation: "mock" }).mode, "demo");
});

test("rejects malformed, ambiguous and excessive server data", () => {
  for (const value of [null, {}, { ...base, revision: -1 }, { ...base, session_id: "old" },
    { ...base, end_ms: -1 }, { ...base, start_ms: 900 }, { ...base, source_text: "x".repeat(8001) },
    { ...base, translation: { status: "complete", text: "你好" } },
    { ...base, source_final: false, translation: { status: "complete", text: "你好", is_mock: true } },
    { ...base, extra: "unexpected" }]) {
    assert.throws(() => parseServerMessage(value));
  }
  assert.throws(() => parseHealthResponse({ protocol_version: 2, mode: "demo",
    status: "ready", asr: "ready", translation: "mock" }));
});

test("language capability and subtitle metadata accept four selected modes while preserving old messages", () => {
  for (const [source_language, target_language] of [["en", "zh-CN"], ["zh", "en"], ["auto", "zh-CN"], ["auto", "en"]]) {
    const cue = parseServerMessage({ ...base, source_language, target_language });
    assert.equal(cue.type, "subtitle");
    if (cue.type === "subtitle") assert.equal(cue.target_language, target_language);
    assert.equal(parseServerMessage({ type: "ready", protocol_version: 1, session_id: session,
      mode: "whisperlivekit", translation: "configured", source_language, target_language }).type, "ready");
  }
  const health = { protocol_version: 1, mode: "whisperlivekit", status: "ready", asr: "ready", translation: "configured" };
  assert.deepEqual(parseHealthResponse({ ...health, source_languages: ["en", "zh", "auto"], target_languages: ["zh-CN", "en"] }).source_languages, ["en", "zh", "auto"]);
  assert.equal(parseHealthResponse(health).source_languages, undefined);
  for (const extra of [{ source_language: "unknown" }, { target_language: "auto" }]) {
    assert.throws(() => parseServerMessage({ ...base, ...extra }));
  }
  assert.throws(() => parseHealthResponse({ ...health, source_languages: [] }));
  assert.throws(() => parseHealthResponse({ ...health, target_languages: ["auto"] }));
  assert.equal(parseServerMessage({ type: "error", session_id: session, segment_id: null,
    code: "UNSUPPORTED_LANGUAGE", message: "A multilingual model is required", fatal: true }).type, "error");
});
