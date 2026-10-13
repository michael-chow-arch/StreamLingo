import assert from "node:assert/strict";
import test from "node:test";
import { AppError, errorInfo, errorFromInfo, formatError, formatReadingProgress, formatStatus, normalizeUiLanguage, t } from "./i18n";
import type { ErrorCode } from "@streamlingo/protocol";

test("UI language defaults to Chinese and accepts only the supported choices", () => {
  assert.equal(normalizeUiLanguage(undefined), "zh-CN");
  assert.equal(normalizeUiLanguage("hi"), "zh-CN");
  assert.equal(normalizeUiLanguage("en"), "en");
  assert.equal(t("en", "start"), "Start captions");
  assert.equal(t("zh-CN", "start"), "开始字幕");
});

test("backend error codes are localized independently of the original server text", () => {
  const codes: ErrorCode[] = ["INVALID_MESSAGE", "UNSUPPORTED_PROTOCOL", "UNSUPPORTED_LANGUAGE", "ASR_NOT_READY", "ASR_FAILED", "TRANSLATION_FAILED", "TRANSLATION_TIMEOUT", "TRANSLATION_BACKLOG", "AUDIO_BACKLOG", "SESSION_CONFLICT", "INTERNAL_ERROR"];
  for (const code of codes) {
    const info = errorInfo(new AppError(code, "Original backend diagnostic"));
    assert.match(formatError("zh-CN", info), /[\u4e00-\u9fff]/);
    assert.doesNotMatch(formatError("en", info), /[\u4e00-\u9fff]/);
    assert.doesNotMatch(formatError("en", info), /Original backend diagnostic/);
  }
  assert.equal(errorInfo(new DOMException("denied", "NotAllowedError")).code, "CAPTURE_DENIED");
});

test("unknown error details are bounded, plain text and use a localized fallback", () => {
  const info = errorInfo(new Error("<script>raw</script>\u0000\n" + "x".repeat(900)));
  assert.equal(info.code, "UNKNOWN");
  assert.ok((info.detail?.length ?? 0) <= 400);
  assert.doesNotMatch(info.detail ?? "", /[\u0000-\u001f]/);
  assert.match(formatError("en", info), /^Something went wrong/);
  assert.match(formatError("zh-CN", info), /^操作失败/);
  assert.equal(errorFromInfo({ code: "unrecognized" as never }).code, "UNKNOWN");
});

test("stored status descriptors can change language without changing their meaning", () => {
  const status = { key: "statusDemo" as const };
  assert.match(formatStatus("en", status), /Demo mode/);
  assert.match(formatStatus("zh-CN", status), /测试模式/);
});

test("automatic reading progress localizes page and queued-page counts", () => {
  assert.equal(formatReadingProgress("zh-CN", 1, 3, 5), "第 2/3 页 · 待读 5 页");
  assert.equal(formatReadingProgress("en", 1, 3, 5), "Page 2/3 · 5 pages queued");
  assert.equal(formatReadingProgress("en", 0, 1, 0), "Page 1/1");
});
