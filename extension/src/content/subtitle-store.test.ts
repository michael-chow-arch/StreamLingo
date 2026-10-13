import assert from "node:assert/strict";
import { test } from "node:test";
import type { SubtitleMessage } from "@streamlingo/protocol";
import { SubtitleStore, readingDurationMs } from "./subtitle-store";
import { paginateTranslation, visibleCharacterCount } from "./subtitle-pagination";

test("English pages get a word reading budget and remain lossless across hidden intervals", () => {
  const store = new SubtitleStore("a");
  const text = "Every translated sentence remains visible long enough for the viewer to read it comfortably. ".repeat(3);
  store.upsert({ ...translated(1, 2, text), source_language: "zh", target_language: "en" }, 0);
  const expected = paginateTranslation(text, 120, "en");
  const first = store.readingWindow(0);
  assert.equal(first.pendingCount, expected.length - 1);
  assert.ok((first.nextChangeAt ?? 0) >= 4000);
  assert.ok(readingDurationMs(expected[0]!, "en") >= 4000);
  assert.ok(readingDurationMs("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen", "en") >= 5000);
  store.setReadingVisible(false, 1000);
  assert.equal(store.readingWindow(20000).nextChangeAt, null);
  store.setReadingVisible(true, 20000);
  assert.equal(store.readingWindow(20000).items[0]?.translatedText, expected[0]);
  const shown = [expected[0]!];
  let now = store.readingWindow(20000).nextChangeAt!;
  for (let index = 1; index < expected.length; index++) {
    const window = store.readingWindow(now);
    shown.push(window.items[0]!.translatedText!);
    now = window.nextChangeAt!;
  }
  assert.equal(shown.join(""), text);
});

test("adjacent English short translations can share a page without mixing target languages", () => {
  const store = new SubtitleStore("a");
  store.upsert({ ...translated(1, 2, "The first sentence is now translated."), target_language: "en" }, 0);
  store.upsert({ ...translated(2, 2, "Here is another complete sentence."), target_language: "en" }, 0);
  assert.equal(store.readingWindow(0).items.length, 2);
  const mixed = new SubtitleStore("a");
  mixed.upsert({ ...translated(1, 2, "English."), target_language: "en" }, 0);
  mixed.upsert(translated(2), 0);
  assert.equal(mixed.readingWindow(0).items.length, 1);
});

function cue(id: number, revision = 1): SubtitleMessage {
  return { type: "subtitle", session_id: "a", segment_id: id, revision,
    start_ms: id * 100, end_ms: id * 100 + 99, source_text: `Cue ${id}`,
    source_final: true, translation: { status: "pending", text: null } };
}

function translated(id: number, revision = 2, text = `译文 ${id}`): SubtitleMessage {
  return { ...cue(id, revision), translation: { status: "complete", text, is_mock: false } };
}

test("rejects wrong sessions, old revisions and any mutation of finalized English", () => {
  const store = new SubtitleStore("a");
  assert.equal(store.upsert({ ...cue(1), session_id: "b" }, 0), false);
  assert.equal(store.upsert(cue(1), 0), true);
  assert.equal(store.upsert(cue(1), 1), false);
  for (const change of [{ source_text: "changed" }, { source_final: false }, { start_ms: 1 }, { end_ms: 1000 }]) {
    assert.equal(store.upsert({ ...cue(1, 2), ...change }, 2), false);
  }
  assert.equal(store.upsert(translated(1), 100), true);
  assert.equal(store.readingWindow(100).historyVersion, 2);
});

test("a burst of 300 short translations is fully retained and displayed in 150 ordered groups", () => {
  const store = new SubtitleStore("a");
  for (let id = 1; id <= 300; id++) store.upsert(translated(id), 0);
  assert.equal(store.values().length, 300);
  assert.equal(store.completedValues().length, 300);
  const displayed: number[] = [];
  for (let index = 0; index < 150; index++) {
    const window = store.readingWindow(index * 4000);
    assert.equal(window.items.length, 2);
    assert.ok(window.items.every(item => item.kind === "translated"));
    displayed.push(...window.items.map(item => item.cue.segment_id));
    assert.equal(window.pendingCount, 298 - index * 2);
    assert.equal(window.completedCount, 300);
    assert.equal(window.items[0]?.expiresAt, window.items[1]?.expiresAt);
    if (index < 149) assert.equal(window.nextChangeAt, (index + 1) * 4000);
  }
  assert.deepEqual(displayed, Array.from({ length: 300 }, (_, index) => index + 1));
  assert.deepEqual(store.readingWindow(149 * 4000 + 11999).items.map(item => item.cue.segment_id), [299, 300]);
  assert.equal(store.readingWindow(149 * 4000 + 12000).items.length, 0);
  assert.equal(store.readingWindow(149 * 4000 + 12000).nextChangeAt, null);
  assert.equal(store.completedValues().length, 300, "Natural hiding must not delete any cue");
});

test("source records and late translations survive both the old eight-cue limit and long delays", () => {
  const store = new SubtitleStore("a", 2);
  for (let id = 1; id <= 320; id++) store.upsert(cue(id), id);
  assert.equal(store.values().length, 320);
  assert.equal(store.upsert(translated(1), 1_000_000), true);
  const window = store.readingWindow(1_000_000);
  assert.equal(window.items[0]?.cue.segment_id, 1);
  assert.equal(window.nextChangeAt, 1_012_000);
  assert.equal(store.latest()?.segment_id, 320);
  assert.deepEqual(store.completedValues().map(item => item.segment_id), [1]);
});

test("out-of-order first arrivals and completions are accepted and history is sorted by segment", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(3), 0);
  store.upsert(translated(1), 1);
  store.upsert(translated(2), 2);
  assert.equal(store.latest()?.segment_id, 3);
  assert.deepEqual(store.values().map(item => item.segment_id), [1, 2, 3]);
  assert.deepEqual(store.completedValues().map(item => item.segment_id), [1, 2, 3]);
  assert.deepEqual(store.readingWindow(2).items.map(item => item.cue.segment_id), [3, 1]);
  assert.equal(store.readingWindow(4002).items[0]?.cue.segment_id, 2);
});

test("a page stays for its reading budget and queued pages advance without more audio", () => {
  assert.equal(readingDurationMs("短句。"), 4000);
  assert.equal(readingDurationMs("读".repeat(48)), 6000);
  assert.equal(readingDurationMs("读".repeat(100)), 8000);
  const store = new SubtitleStore("a");
  store.upsert(translated(1, 2, "读".repeat(48)), 0);
  assert.equal(store.readingWindow(0).items[0]?.cue.segment_id, 1);
  store.upsert(translated(2), 500);
  assert.equal(store.readingWindow(500).nextChangeAt, 6000);
  assert.equal(store.readingWindow(5999).items[0]?.cue.segment_id, 1);
  assert.equal(store.readingWindow(6000).items[0]?.cue.segment_id, 2);
});

test("a delayed timer advances just one group with a fresh full reading budget", () => {
  const store = new SubtitleStore("a");
  for (let id = 1; id <= 6; id++) store.upsert(translated(id), 0);
  store.readingWindow(0);
  const late = store.readingWindow(60_000);
  assert.deepEqual(late.items.map(item => item.cue.segment_id), [3, 4]);
  assert.equal(late.pendingCount, 2, "No TTL may discard the other waiting pages");
  assert.equal(late.nextChangeAt, 64_000);
  assert.deepEqual(store.readingWindow(63_999).items.map(item => item.cue.segment_id), [3, 4]);
  assert.deepEqual(store.readingWindow(64_000).items.map(item => item.cue.segment_id), [5, 6]);
});

test("pages not yet displayed never expire even before the reader's first render", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1), 0);
  store.upsert(translated(2), 0);
  store.upsert(translated(3), 0);
  const first = store.readingWindow(90_000);
  assert.equal(first.items[0]?.cue.segment_id, 1);
  assert.equal(first.nextChangeAt, 94_000);
  assert.equal(first.pendingCount, 1);
});

test("all pages of a long cue are displayed contiguously and reconstruct its exact original text", () => {
  const store = new SubtitleStore("a");
  const original = " 这是第一句话，包含一些空格。\n" + "这是没有句号的长中文内容".repeat(20) + "\n最后一行！  ";
  const expected = paginateTranslation(original);
  store.upsert(translated(1, 2, original), 0);
  store.upsert(translated(2), 0);
  const displayed: string[] = [];
  let now = 0;
  for (let index = 0; index < expected.length; index++) {
    const window = store.readingWindow(now);
    assert.equal(window.items.length, 1, "Do not group any page of a multi-page translation");
    const page = window.items[0]!;
    assert.equal(page.cue.segment_id, 1);
    assert.equal(page.pageIndex, index);
    assert.equal(page.pageCount, expected.length);
    assert.equal(page.cue.translation.text, original, "A page must not overwrite the complete cue");
    assert.ok(visibleCharacterCount(page.translatedText!) <= 48);
    displayed.push(page.translatedText!);
    now = window.nextChangeAt!;
  }
  assert.equal(displayed.join(""), original);
  assert.equal(store.readingWindow(now).items[0]?.cue.segment_id, 2);
  assert.equal(store.completedValues()[0]?.translation.text, original);
});

test("revision-only completion updates never restart the clock or enqueue duplicate pages", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1), 0);
  store.readingWindow(0);
  store.upsert(translated(1, 3), 11_000);
  const window = store.readingWindow(11_000);
  assert.equal(window.pendingCount, 0);
  assert.equal(window.nextChangeAt, 12_000);
  assert.equal(window.items[0]?.cue.revision, 2, "Keep the page snapshot stable while reading");
  assert.equal(store.completedValues()[0]?.revision, 3);
  assert.equal(store.readingWindow(12_000).items.length, 0);
});

test("a changed completed translation queues its correction without interrupting the active page", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1, 2, "原译文"), 0);
  store.readingWindow(0);
  store.upsert(translated(1, 3, "更正后的完整译文"), 1000);
  assert.equal(store.readingWindow(1000).items[0]?.translatedText, "原译文");
  assert.equal(store.readingWindow(1000).pendingCount, 1);
  assert.equal(store.readingWindow(4000).items[0]?.translatedText, "更正后的完整译文");
  assert.equal(store.completedValues().length, 1);
  assert.equal(store.completedValues()[0]?.translation.text, "更正后的完整译文");
});

test("genuine repeated text in separate segments remains two independent reading obligations", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1, 2, "请稍等。"), 0);
  store.upsert(translated(2, 2, "请稍等。"), 1);
  const window = store.readingWindow(1);
  assert.deepEqual(window.items.map(item => item.cue.segment_id), [1, 2]);
  assert.deepEqual(window.items.map(item => item.translatedText), ["请稍等。", "请稍等。"]);
  assert.deepEqual(window.items.map(item => item.cue.source_text), ["Cue 1", "Cue 2"]);
  assert.equal(store.completedValues().length, 2);
});

test("live English uses only an empty reader and never bypasses a waiting Chinese page", () => {
  const store = new SubtitleStore("a");
  store.upsert({ ...cue(1), source_final: false }, 0);
  assert.equal(store.readingWindow(0).items[0]?.kind, "current");
  store.upsert({ ...cue(1, 2), source_final: false, source_text: "A revised partial" }, 1000);
  assert.equal(store.readingWindow(1000).nextChangeAt, 13_000);
  store.upsert({ ...translated(1, 3), source_text: "A revised partial" }, 2000);
  store.upsert(cue(2), 3000);
  const window = store.readingWindow(3000);
  assert.equal(window.items.length, 1);
  assert.equal(window.items[0]?.kind, "translated");
  assert.equal(window.items[0]?.cue.segment_id, 1);
  store.upsert(translated(2), 4000);
  assert.equal(store.readingWindow(4000).items[0]?.cue.segment_id, 1);
  assert.equal(store.readingWindow(7000).items[0]?.cue.segment_id, 2);
});

test("expired English stays in the session record and a new session starts empty", () => {
  const store = new SubtitleStore("a");
  store.upsert(cue(1), 0);
  assert.equal(store.readingWindow(12_000).items.length, 0);
  assert.equal(store.values().length, 1);
  const next = new SubtitleStore("b");
  assert.equal(next.upsert(translated(1), 20_000), false);
  assert.deepEqual(next.readingWindow(20_000), {
    items: [], nextChangeAt: null, pendingCount: 0, historyVersion: 0, completedCount: 0,
  });
});

test("short pages group only at a cycle boundary and never fill a slot during reading", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1), 0);
  assert.deepEqual(store.readingWindow(0).items.map(item => item.cue.segment_id), [1]);
  store.upsert(translated(2), 1000);
  store.upsert(translated(3), 1500);
  assert.deepEqual(store.readingWindow(1500).items.map(item => item.cue.segment_id), [1]);
  assert.equal(store.readingWindow(1500).pendingCount, 2);
  assert.deepEqual(store.readingWindow(4000).items.map(item => item.cue.segment_id), [2, 3]);
  store.upsert(translated(4), 4500);
  const window = store.readingWindow(7999);
  assert.deepEqual(window.items.map(item => item.cue.segment_id), [2, 3]);
  assert.equal(window.nextChangeAt, 8000);
  assert.equal(window.pendingCount, 1);
  assert.equal(store.readingWindow(8000).items[0]?.cue.segment_id, 4);
});

test("a grouped pair shares a combined reading budget and never exceeds 48 visible characters", () => {
  const store = new SubtitleStore("a");
  for (const [id, length] of [[1, 24], [2, 24], [3, 25], [4, 24]] as const) {
    store.upsert(translated(id, 2, "字".repeat(length)), 0);
  }
  const first = store.readingWindow(0);
  assert.deepEqual(first.items.map(item => item.cue.segment_id), [1, 2]);
  assert.equal(first.items.reduce((count, item) => count + visibleCharacterCount(item.translatedText!), 0), 48);
  assert.equal(first.nextChangeAt, 6000);
  assert.deepEqual(store.readingWindow(5999).items.map(item => item.cue.segment_id), [1, 2]);
  assert.deepEqual(store.readingWindow(6000).items.map(item => item.cue.segment_id), [3]);
  assert.deepEqual(store.readingWindow(10_000).items.map(item => item.cue.segment_id), [4]);
});

test("grouping never skips an intervening page or combines two revisions of the same segment", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1, 2, "字".repeat(30)), 0);
  store.upsert(translated(2, 2, "字".repeat(30)), 0);
  store.upsert(translated(3, 2, "短句"), 0);
  assert.deepEqual(store.readingWindow(0).items.map(item => item.cue.segment_id), [1]);
  assert.deepEqual(store.readingWindow(4000).items.map(item => item.cue.segment_id), [2, 3]);
  const revisions = new SubtitleStore("a");
  revisions.upsert(translated(1, 2, "初译"), 0);
  revisions.upsert(translated(1, 3, "修改后的译文"), 1);
  revisions.upsert(translated(2, 2, "下一段"), 2);
  assert.deepEqual(revisions.readingWindow(2).items.map(item => item.cue.revision), [2]);
  assert.deepEqual(revisions.readingWindow(4002).items.map(item => item.cue.segment_id), [1, 2]);
});

test("a hidden minute freezes remaining reading time while 300 new subtitles stay queued", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1), 0);
  store.upsert(translated(2), 0);
  assert.deepEqual(store.readingWindow(0).items.map(item => item.cue.segment_id), [1, 2]);
  store.setReadingVisible(false, 1000);
  for (let id = 3; id <= 302; id++) store.upsert(translated(id), 1000 + id * 100);
  const hidden = store.readingWindow(61_000);
  assert.deepEqual(hidden.items.map(item => item.cue.segment_id), [1, 2]);
  assert.equal(hidden.nextChangeAt, null);
  assert.equal(hidden.pendingCount, 300);
  assert.equal(hidden.completedCount, 302);
  store.setReadingVisible(true, 61_000);
  const resumed = store.readingWindow(61_000);
  assert.deepEqual(resumed.items.map(item => item.cue.segment_id), [1, 2]);
  assert.equal(resumed.nextChangeAt, 64_000, "The first group retains its unread three seconds");
  assert.equal(resumed.items[0]?.expiresAt, 72_000);
  assert.deepEqual(store.readingWindow(63_999).items.map(item => item.cue.segment_id), [1, 2]);
  const displayed = [1, 2];
  for (let index = 0; index < 150; index++) {
    displayed.push(...store.readingWindow(64_000 + index * 4000).items.map(item => item.cue.segment_id));
  }
  assert.deepEqual(displayed, Array.from({ length: 302 }, (_, index) => index + 1));
  assert.equal(store.readingWindow(64_000 + 149 * 4000).pendingCount, 0);
});

test("a session starting hidden displays no completed pages until visible, then gives a new full budget", () => {
  const store = new SubtitleStore("a");
  store.setReadingVisible(false, 0);
  for (let id = 1; id <= 6; id++) store.upsert(translated(id), id * 100);
  const hidden = store.readingWindow(50_000);
  assert.deepEqual(hidden.items, []);
  assert.equal(hidden.pendingCount, 6);
  assert.equal(hidden.nextChangeAt, null);
  store.setReadingVisible(true, 50_000);
  const shown = store.readingWindow(50_000);
  assert.deepEqual(shown.items.map(item => item.cue.segment_id), [1, 2]);
  assert.equal(shown.nextChangeAt, 54_000);
  assert.equal(shown.pendingCount, 4);
  assert.deepEqual(store.readingWindow(53_999).items.map(item => item.cue.segment_id), [1, 2]);
  assert.deepEqual(store.readingWindow(54_000).items.map(item => item.cue.segment_id), [3, 4]);
});

test("duplicate visibility notifications are idempotent and do not extend or shorten deadlines", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1), 0);
  store.upsert(translated(2), 0);
  store.upsert(translated(3), 0);
  store.readingWindow(0);
  store.setReadingVisible(true, 500);
  store.setReadingVisible(false, 1000);
  store.setReadingVisible(false, 4000);
  store.setReadingVisible(true, 11_000);
  store.setReadingVisible(true, 12_000);
  assert.equal(store.readingWindow(12_000).nextChangeAt, 14_000);
  assert.equal(store.readingWindow(12_000).items[0]?.expiresAt, 22_000);
  assert.equal(store.readingWindow(14_000).items[0]?.cue.segment_id, 3);
});

test("the last page does not expire in the background and retains only its remaining visible lifetime", () => {
  const store = new SubtitleStore("a");
  store.upsert(translated(1), 0);
  store.readingWindow(0);
  store.setReadingVisible(false, 5000);
  assert.equal(store.readingWindow(100_000).items[0]?.cue.segment_id, 1);
  assert.equal(store.readingWindow(100_000).nextChangeAt, null);
  store.setReadingVisible(true, 105_000);
  assert.equal(store.readingWindow(105_000).nextChangeAt, 112_000);
  assert.equal(store.readingWindow(111_999).items[0]?.cue.segment_id, 1);
  assert.equal(store.readingWindow(112_000).items.length, 0);
});

test("English previews preserve remaining visible time while new hidden text gets a full preview", () => {
  const store = new SubtitleStore("a");
  store.upsert({ ...cue(1), source_final: false }, 0);
  store.setReadingVisible(false, 5000);
  assert.equal(store.readingWindow(60_000).items[0]?.kind, "current");
  assert.equal(store.readingWindow(60_000).nextChangeAt, null);
  store.setReadingVisible(true, 65_000);
  assert.equal(store.readingWindow(65_000).nextChangeAt, 72_000);
  store.setReadingVisible(false, 66_000);
  store.upsert({ ...cue(1, 2), source_final: false, source_text: "New English while hidden" }, 67_000);
  store.setReadingVisible(true, 90_000);
  assert.equal(store.readingWindow(90_000).nextChangeAt, 102_000);
  assert.equal(store.readingWindow(90_000).items[0]?.cue.source_text, "New English while hidden");
});
