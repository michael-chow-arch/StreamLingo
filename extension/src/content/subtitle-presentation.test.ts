import assert from "node:assert/strict";
import { test } from "node:test";
import type { TranslationState } from "@streamlingo/protocol";
import { presentCue } from "./subtitle-presentation";
import type { ReadingItem } from "./subtitle-store";

function item(translation: TranslationState, kind: ReadingItem["kind"] = "current"): ReadingItem {
  return { kind, expiresAt: 12000, cue: {
    type: "subtitle", session_id: "a", segment_id: 1, revision: 1, start_ms: 0, end_ms: 1000,
    source_text: "<img src=x onerror=alert(1)>", source_final: true, translation,
  } };
}

test("pending, failed, skipped and disabled translations keep English even with English display disabled", () => {
  for (const status of ["pending", "error", "skipped", "disabled"] as const) {
    const result = presentCue(item({ status, text: null }), false);
    assert.equal(result.showSource, true);
    assert.equal(result.translated, "");
    assert.equal(result.source, "<img src=x onerror=alert(1)>");
  }
  assert.match(presentCue(item({ status: "pending", text: null }), false).label, /翻译中/);
  assert.match(presentCue(item({ status: "error", text: null }), false).label, /暂不可用/);
  assert.match(presentCue(item({ status: "skipped", text: null }), false).label, /已跳过/);
});

test("completed translation honors the English setting and preserves the exact model text", () => {
  const translated = item({ status: "complete", text: "<b>原样中文</b>", is_mock: false }, "translated");
  assert.equal(presentCue(translated, false).showSource, false);
  assert.equal(presentCue(translated, true).showSource, true);
  assert.equal(presentCue(translated, true).translated, "<b>原样中文</b>");
});

test("older translated groups and mock translations have explicit independent labels", () => {
  const older = { ...item({ status: "complete", text: "测试", is_mock: true }), kind: "translated" as const };
  assert.equal(presentCue(older, true).label, "已译片段 · 测试译文");
  assert.equal(presentCue(older, true).isMock, true);
});

test("changing UI language changes labels without translating English or Chinese caption content", () => {
  const cue = item({ status: "complete", text: "这是中文译文。", is_mock: false }, "translated");
  const chinese = presentCue(cue, true, "zh-CN");
  const english = presentCue(cue, true, "en");
  assert.equal(chinese.label, "已译片段");
  assert.equal(english.label, "Translated segment");
  assert.equal(english.source, chinese.source);
  assert.equal(english.translated, "这是中文译文。");
  for (const status of ["pending", "error", "skipped", "disabled"] as const) {
    assert.doesNotMatch(presentCue(item({ status, text: null }), false, "en").label, /[\u4e00-\u9fff]/);
  }
});

test("a completed current preview never bypasses the reading queue or claims to be queued", () => {
  for (const isMock of [false, true]) {
    const current = item({ status: "complete", text: "尚未上屏的译文", is_mock: isMock });
    const preview = presentCue(current, false, "en");
    assert.equal(preview.translated, "");
    assert.equal(preview.showSource, true);
    assert.equal(preview.source, current.cue.source_text);
    assert.equal(preview.label, "Live transcript");
    assert.equal(preview.isMock, false);
  }
});

test("translated pages show the provided slice verbatim and keep the original matching English", () => {
  const complete = item({ status: "complete", text: "第一页。第二页。", is_mock: false }, "translated");
  const page = { ...complete, translatedText: "第二页。", pageIndex: 1, pageCount: 2 };
  const result = presentCue(page, true);
  assert.equal(result.translated, "第二页。");
  assert.equal(result.source, complete.cue.source_text);
  assert.equal(presentCue({ ...page, kind: "current" }, true).translated, "");
});
