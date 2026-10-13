import assert from "node:assert/strict";
import { test } from "node:test";
import { pageCapacity, pageCharacterCount, paginateTranslation, visibleCharacterCount } from "./subtitle-pagination";

test("English uses a larger word-aware budget and preserves every character", () => {
  const text = "Automatic subtitles should give viewers enough time to read every translated sentence without cutting words in half. ".repeat(8);
  const pages = paginateTranslation(text, pageCapacity("en"), "en");
  assert.equal(pages.join(""), text);
  assert.ok(pages.length < paginateTranslation(text).length);
  assert.ok(pages.every(page => pageCharacterCount(page, "en") <= 120));
  for (let index = 1; index < pages.length; index++) {
    assert.ok(!/[a-z]$/i.test(pages[index - 1]!) || !/^[a-z]/i.test(pages[index]!), "A word must not be split");
  }
  const unusual = "A\n\n\nB " + "x".repeat(400) + " 😀".repeat(100);
  const unusualPages = paginateTranslation(unusual, 120, "en");
  assert.equal(unusualPages.join(""), unusual);
  assert.ok(unusualPages.every(page => pageCharacterCount(page, "en") <= 120));
});

test("empty input and whitespace are preserved without artificial text", () => {
  assert.deepEqual(paginateTranslation(""), []);
  assert.deepEqual(paginateTranslation("  \n\t  "), ["  \n\t  "]);
  assert.equal(visibleCharacterCount(" A 中 😀 \n"), 3);
});

test("native sentence and word boundaries avoid cutting a short sentence or English word", () => {
  assert.deepEqual(paginateTranslation("第一句。第二句。", 5), ["第一句。", "第二句。"]);
  const pages = paginateTranslation("alpha beta gamma delta", 10);
  assert.equal(pages.join(""), "alpha beta gamma delta");
  assert.ok(pages.every(page => !page.includes("ga") || page.includes("gamma")));
  assert.ok(pages.every(page => visibleCharacterCount(page) <= 10));
});

test("long unpunctuated Chinese, identifiers, URLs and Unicode retain every code point", () => {
  for (const original of ["无标点长译文".repeat(100), "X".repeat(173),
    "https://example.test/" + "longpath".repeat(40), " 😀 𝄞 中文 é \n".repeat(100)]) {
    const pages = paginateTranslation(original);
    assert.ok(pages.length > 1);
    assert.equal(pages.join(""), original);
    assert.ok(pages.every(page => page.length > 0 && visibleCharacterCount(page) <= 48));
    assert.ok(pages.every(page => !/^[\uDC00-\uDFFF]|[\uD800-\uDBFF]$/u.test(page)), "Do not split surrogate pairs");
  }
});

test("spaces, punctuation and newlines remain in their original order across tiny pages", () => {
  const original = " 你好， 世界！\n\nNext sentence.  尾巴\t";
  for (const limit of [1, 2, 3, 7, 48]) {
    const pages = paginateTranslation(original, limit);
    assert.equal(pages.join(""), original);
    assert.ok(pages.every(page => visibleCharacterCount(page) <= limit));
  }
});

test("invalid page capacities are rejected instead of looping or silently losing text", () => {
  for (const limit of [0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.throws(() => paginateTranslation("测试", limit), RangeError);
  }
});
