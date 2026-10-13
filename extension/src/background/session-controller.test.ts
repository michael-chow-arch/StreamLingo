import assert from "node:assert/strict";
import test from "node:test";
import type { ReadyMessage, SubtitleMessage } from "@streamlingo/protocol";
import { DEFAULT_SETTINGS } from "../shared/config";
import type { ContentMessage, OffscreenResponse } from "../shared/runtime-messages";
import type { SessionState } from "../shared/session";
import { SessionController, type SessionHost } from "./session-controller";

function setup(initial: SessionState = { phase: "idle" }) {
  const delivered: { tabId: number; message: ContentMessage }[] = [];
  let starts = 0;
  let closes = 0;
  const host: SessionHost = {
    async query() { return initial; },
    async validateTab() {},
    async prepare() {},
    async start(tabId, sessionId) { starts++; return { ok: true, state: { phase: "running", tabId, sessionId } }; },
    async stop() {},
    async close() { closes++; },
    async content(tabId, message) { delivered.push({ tabId, message }); },
    changed() {},
  };
  return { host, delivered, starts: () => starts, closes: () => closes };
}

function subtitle(sessionId: string): SubtitleMessage {
  return { type: "subtitle", session_id: sessionId, segment_id: 1, revision: 1, start_ms: 0, end_ms: 500,
    source_text: "hello", source_final: true, translation: { status: "disabled", text: null } };
}

test("concurrent start requests create one capture and require an explicit stop", async () => {
  const fake = setup();
  const controller = new SessionController(fake.host);
  const results = await Promise.allSettled([controller.start(1, DEFAULT_SETTINGS), controller.start(2, DEFAULT_SETTINGS)]);
  assert.equal(results[0]?.status, "fulfilled");
  assert.equal(results[1]?.status, "rejected");
  assert.equal(fake.starts(), 1);
  await controller.stop();
  assert.equal(controller.state.phase, "idle");
});

test("ready messages are acknowledged while the start handshake is pending", async () => {
  const fake = setup();
  const controller = new SessionController(fake.host);
  fake.host.start = async (tabId, sessionId) => {
    const ready: ReadyMessage = { type: "ready", session_id: sessionId, protocol_version: 1, mode: "demo", translation: "mock" };
    await controller.receive(sessionId, ready);
    return { ok: true, state: { phase: "running", tabId, sessionId } };
  };
  await controller.start(1, DEFAULT_SETTINGS);
  assert.equal(controller.state.phase, "running");
  assert.match(JSON.stringify(fake.delivered), /statusDemo/);
});

test("stopping invalidates the session before late subtitles can render", async () => {
  const fake = setup();
  const controller = new SessionController(fake.host);
  const state = await controller.start(1, DEFAULT_SETTINGS);
  assert.ok("sessionId" in state && state.sessionId);
  await controller.stop();
  await controller.receive(state.sessionId, subtitle(state.sessionId));
  assert.equal(fake.delivered.filter(({ message }) => message.type === "CONTENT_SUBTITLE").length, 0);
});

test("a restarted worker recovers the real offscreen target before forwarding a subtitle", async () => {
  const fake = setup({ phase: "running", tabId: 42, sessionId: "existing" });
  const controller = new SessionController(fake.host);
  await controller.receive("existing", subtitle("existing"));
  assert.equal(fake.delivered[0]?.tabId, 42);
  assert.equal(fake.delivered[0]?.message.type, "CONTENT_SUBTITLE");
});

test("a fatal startup event releases capture and leaves an actionable error", async () => {
  const fake = setup();
  const controller = new SessionController(fake.host);
  fake.host.start = async (tabId, sessionId) => {
    await controller.receive(sessionId, { type: "error", session_id: sessionId, segment_id: null, code: "ASR_FAILED", message: "ASR unavailable", fatal: true });
    return { ok: true, state: { phase: "running", tabId, sessionId } };
  };
  await assert.rejects(controller.start(1, DEFAULT_SETTINGS), /ASR unavailable/);
  await controller.snapshot();
  assert.equal(controller.state.phase, "error");
  assert.ok(fake.closes() >= 1);
});

test("navigation from another tab or an obsolete session cannot stop the active capture", async () => {
  const fake = setup();
  const controller = new SessionController(fake.host);
  const state = await controller.start(1, DEFAULT_SETTINGS);
  assert.ok("sessionId" in state && state.sessionId);
  await controller.navigated(2, state.sessionId);
  await controller.navigated(1, "old-session");
  await controller.snapshot();
  assert.equal(controller.state.phase, "running");
  await controller.navigated(1, state.sessionId);
  await controller.snapshot();
  assert.equal(controller.state.phase, "idle");
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

test("snapshot and stop complete without waiting for a pending start handshake", { timeout: 1000 }, async () => {
  const fake = setup();
  const entered = deferred<void>();
  const handshake = deferred<OffscreenResponse>();
  let sessionId = "";
  let signal: AbortSignal | undefined;
  fake.host.start = async (_tabId, id, _settings, abortSignal) => {
    sessionId = id;
    signal = abortSignal;
    entered.resolve();
    return handshake.promise;
  };
  const controller = new SessionController(fake.host);
  const starting = controller.start(1, DEFAULT_SETTINGS);
  const cancelled = assert.rejects(starting, /取消/);
  await entered.promise;
  assert.equal((await controller.snapshot()).phase, "starting");
  assert.equal((await controller.stop()).phase, "idle");
  assert.equal(signal?.aborted, true);
  handshake.resolve({ ok: true, state: { phase: "running", tabId: 1, sessionId } });
  await cancelled;
  await controller.receive(sessionId, { type: "ready", session_id: sessionId, protocol_version: 1, mode: "demo", translation: "mock" });
  assert.equal(controller.state.phase, "idle");
  assert.equal(fake.closes(), 1);
});

test("late completion of an old start neither revives it nor closes a newer session", { timeout: 1000 }, async () => {
  const fake = setup();
  const entered = deferred<void>();
  const handshake = deferred<OffscreenResponse>();
  const realStart = fake.host.start;
  let oldSessionId = "";
  fake.host.start = async (tabId, sessionId, settings, signal) => {
    if (tabId === 1) {
      oldSessionId = sessionId;
      entered.resolve();
      return handshake.promise;
    }
    return realStart(tabId, sessionId, settings, signal);
  };
  const controller = new SessionController(fake.host);
  const cancelled = assert.rejects(controller.start(1, DEFAULT_SETTINGS), /取消/);
  await entered.promise;
  await controller.stop();
  const newState = await controller.start(2, DEFAULT_SETTINGS);
  const closeCount = fake.closes();
  handshake.resolve({ ok: true, state: { phase: "running", tabId: 1, sessionId: oldSessionId } });
  await cancelled;
  assert.deepEqual(controller.state, newState);
  assert.equal(fake.closes(), closeCount);
});

test("navigation immediately cancels a pending handshake and drops its late result", { timeout: 1000 }, async () => {
  const fake = setup();
  const entered = deferred<void>();
  const handshake = deferred<OffscreenResponse>();
  let sessionId = "";
  fake.host.start = async (_tabId, id) => { sessionId = id; entered.resolve(); return handshake.promise; };
  const controller = new SessionController(fake.host);
  const cancelled = assert.rejects(controller.start(1, DEFAULT_SETTINGS), /取消/);
  await entered.promise;
  await controller.navigated(1);
  assert.equal(controller.state.phase, "idle");
  handshake.resolve({ ok: true, state: { phase: "running", tabId: 1, sessionId } });
  await cancelled;
  assert.equal(controller.state.phase, "idle");
});

test("cancellation during preparation stops promptly and never enters the capture handshake", { timeout: 1000 }, async () => {
  const fake = setup();
  const preparing = deferred<void>();
  const finishPrepare = deferred<void>();
  const stopped = deferred<void>();
  let signal: AbortSignal | undefined;
  fake.host.prepare = async (_tabId, _sessionId, _settings, abortSignal) => {
    signal = abortSignal;
    preparing.resolve();
    await finishPrepare.promise;
    abortSignal.throwIfAborted();
  };
  fake.host.stop = async () => { stopped.resolve(); };
  const controller = new SessionController(fake.host);
  const cancelled = assert.rejects(controller.start(1, DEFAULT_SETTINGS), /取消/);
  await preparing.promise;
  const stopping = controller.stop();
  await stopped.promise;
  assert.equal(signal?.aborted, true);
  assert.equal((await controller.snapshot()).phase, "stopping");
  finishPrepare.resolve();
  await stopping;
  await cancelled;
  assert.equal(fake.starts(), 0);
  assert.equal(controller.state.phase, "idle");
});

test("stop wins even when the initial settings read has not completed", { timeout: 1000 }, async () => {
  const fake = setup();
  const loaded = deferred<typeof DEFAULT_SETTINGS>();
  const stopped = deferred<void>();
  fake.host.stop = async () => { stopped.resolve(); };
  const controller = new SessionController(fake.host);
  const cancelled = assert.rejects(controller.start(1, () => loaded.promise), /取消/);
  const stopping = controller.stop();
  await stopped.promise;
  loaded.resolve(DEFAULT_SETTINGS);
  await stopping;
  await cancelled;
  assert.equal(fake.starts(), 0);
  assert.equal(controller.state.phase, "idle");
});

test("nonfatal translation failures stay attached to their subtitle without a stale global banner", async () => {
  const fake = setup();
  const controller = new SessionController(fake.host);
  const state = await controller.start(1, DEFAULT_SETTINGS);
  assert.ok("sessionId" in state && state.sessionId);
  const sessionId = state.sessionId;
  await controller.receive(sessionId, { ...subtitle(sessionId), translation: { status: "error", text: null } });
  for (const code of ["TRANSLATION_FAILED", "TRANSLATION_TIMEOUT", "TRANSLATION_BACKLOG"] as const) {
    await controller.receive(sessionId, { type: "error", session_id: sessionId, segment_id: 1, code, message: "Old segment failed", fatal: false });
  }
  assert.equal(fake.delivered.filter(({ message }) => message.type === "CONTENT_SUBTITLE").length, 1);
  assert.equal(fake.delivered.filter(({ message }) => message.type === "CONTENT_STATUS").length, 0);
  assert.equal(controller.state.phase, "running");
});
