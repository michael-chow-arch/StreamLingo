import assert from "node:assert/strict";
import { test } from "node:test";
import type { HealthResponse } from "@streamlingo/protocol";
import { healthPresentation } from "./health-presentation";

const healthy: HealthResponse = { protocol_version: 1, mode: "whisperlivekit", status: "ready", asr: "ready", translation: "configured" };

test("popup describes the actual backend translation mode", () => {
  assert.equal(healthPresentation(null).mode, "unknown");
  assert.match(healthPresentation(null).notice, /连接本地服务后/);
  assert.match(healthPresentation(healthy).notice, /翻译已配置/);
  assert.doesNotMatch(healthPresentation(healthy).notice, /预留/);
  assert.match(healthPresentation({ ...healthy, translation: "disabled" }).notice, /后端未启用/);
  assert.match(healthPresentation({ ...healthy, translation: "mock" }).notice, /并非真实翻译/);
  assert.match(healthPresentation({ ...healthy, mode: "demo" }).notice, /不识别当前音频/);
});

test("all backend modes have English descriptions", () => {
  const modes = [null, healthy, { ...healthy, translation: "disabled" as const }, { ...healthy, translation: "mock" as const }, { ...healthy, mode: "demo" as const }];
  for (const mode of modes) assert.doesNotMatch(healthPresentation(mode, "en").notice, /[\u4e00-\u9fff]/);
});
