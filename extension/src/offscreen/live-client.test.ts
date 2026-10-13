import assert from "node:assert/strict";
import test from "node:test";
import type { ServerMessage } from "@streamlingo/protocol";
import { LiveClient, liveSocketUrl } from "./live-client";
import { TRANSLATION_MODES, translationLanguages, type TranslationMode } from "../shared/config";

const SESSION = "f84428dc-f217-4a8b-b034-f3e5a0cc204c";
const ready = { type: "ready", protocol_version: 1, session_id: SESSION, mode: "demo", translation: "mock" };

class FakeSocket {
  readyState = 0;
  bufferedAmount = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  readonly sent: (string | ArrayBuffer)[] = [];
  closeCalls = 0;

  send(data: string | ArrayBuffer): void { this.sent.push(data); }
  close(): void { this.closeCalls += 1; this.readyState = 3; }
  open(): void { this.readyState = 1; this.onopen?.(); }
  receive(data: unknown): void { this.onmessage?.({ data: JSON.stringify(data) }); }
}

function fixture(overrides: { handshakeTimeoutMs?: number; maxBufferedBytes?: number; translationMode?: TranslationMode } = {}) {
  const socket = new FakeSocket();
  const messages: ServerMessage[] = [];
  const failures: string[] = [];
  const client = new LiveClient({
    sessionId: SESSION,
    backendBaseUrl: "http://127.0.0.1:8765",
    socketFactory: () => socket as unknown as WebSocket,
    onMessage: (message) => messages.push(message),
    onFailure: (message) => failures.push(message),
    ...overrides,
  });
  return { socket, client, messages, failures };
}

test("socket URL uses the protocol endpoint and rejects embedded credentials", () => {
  assert.equal(liveSocketUrl("http://127.0.0.1:8765/"), "ws://127.0.0.1:8765/ws/live");
  assert.equal(liveSocketUrl("https://localhost:8765/"), "wss://localhost:8765/ws/live");
  assert.throws(() => liveSocketUrl("file:///tmp/x"));
  assert.throws(() => liveSocketUrl("http://name:secret@localhost:8765"));
});

test("all four translation modes send their actual languages and reject a mismatched ready", async () => {
  for (const translationMode of TRANSLATION_MODES) {
    const { client, socket } = fixture({ translationMode });
    const start = client.start();
    socket.open();
    const sent = JSON.parse(socket.sent[0] as string);
    const expected = translationLanguages(translationMode);
    assert.equal(sent.source_language, expected.source);
    assert.equal(sent.target_language, expected.target);
    socket.receive({ ...ready, source_language: expected.source, target_language: expected.target });
    await start;
    client.close();
  }
  const { client, socket } = fixture({ translationMode: "zh-en" });
  const start = client.start();
  socket.open();
  socket.receive({ ...ready, source_language: "en", target_language: "zh-CN" });
  await assert.rejects(start, { code: "UNSUPPORTED_LANGUAGE" });
});

test("start sends handshake first and never sends audio before ready", async () => {
  const { client, socket, failures, messages } = fixture();
  const started = client.start();
  client.sendAudio(new ArrayBuffer(5120));
  assert.equal(socket.sent.length, 0);
  socket.open();
  assert.equal(JSON.parse(socket.sent[0] as string).type, "start");
  assert.equal(JSON.parse(socket.sent[0] as string).source_language, "en");
  assert.equal(JSON.parse(socket.sent[0] as string).target_language, "zh-CN");
  client.sendAudio(new ArrayBuffer(5120));
  assert.equal(socket.sent.length, 1);
  socket.receive(ready);
  await started;
  client.sendAudio(new ArrayBuffer(5120));
  assert.equal(socket.sent.length, 2);
  assert.equal(messages.length, 1);
  assert.deepEqual(failures, []);
  client.close();
  client.close();
  assert.equal(socket.closeCalls, 1);
  assert.equal(JSON.parse(socket.sent[2] as string).type, "stop");
  client.sendAudio(new ArrayBuffer(5120));
  assert.equal(socket.sent.length, 3);
});

test("slow audio transport has a bounded queue and closes instead of silently dropping frames", async () => {
  const { client, socket, failures } = fixture({ maxBufferedBytes: 10_240 });
  const started = client.start();
  socket.open();
  socket.receive(ready);
  await started;
  socket.bufferedAmount = 6_000;
  client.sendAudio(new ArrayBuffer(5120));
  assert.equal(failures.length, 1);
  assert.match(failures[0], /积压/);
  assert.equal(socket.closeCalls, 1);
  assert.equal(socket.sent.length, 1);
});

test("malformed server messages fail the handshake and close immediately", async () => {
  const { client, socket, failures } = fixture();
  const started = client.start();
  socket.open();
  socket.receive({ ...ready, mode: "unknown" });
  await assert.rejects(started, /无效/);
  assert.equal(failures.length, 1);
  assert.equal(socket.closeCalls, 1);
});

test("messages from an unrelated session cannot enter the subtitle stream", async () => {
  const { client, socket, messages } = fixture();
  const started = client.start();
  socket.open();
  socket.receive({ ...ready, session_id: "444428dc-f217-4a8b-b034-f3e5a0cc204c" });
  await assert.rejects(started, /不匹配/);
  assert.deepEqual(messages, []);
});

test("a stop during a pending handshake rejects startup and ignores late ready", async () => {
  const { client, socket, messages, failures } = fixture();
  const started = client.start();
  socket.open();
  const delayedMessage = socket.onmessage;
  client.close();
  await assert.rejects(started, { code: "START_CANCELLED" });
  delayedMessage?.({ data: JSON.stringify(ready) });
  assert.deepEqual(messages, []);
  assert.deepEqual(failures, []);
});

test("a server that never becomes ready is timed out", async () => {
  const { client, socket, failures } = fixture({ handshakeTimeoutMs: 5 });
  const started = client.start();
  socket.open();
  await assert.rejects(started, { code: "CONNECTION_TIMEOUT" });
  assert.equal(failures.length, 1);
  assert.equal(socket.closeCalls, 1);
});

test("fatal model errors retain the backend message without reporting duplicate transport errors", async () => {
  const { client, socket, failures, messages } = fixture();
  const started = client.start();
  socket.open();
  socket.receive({
    type: "error", session_id: SESSION, segment_id: null,
    code: "ASR_NOT_READY", message: "模型尚未准备好", fatal: true,
  });
  await assert.rejects(started, /模型尚未准备好/);
  assert.equal(messages.length, 1);
  assert.deepEqual(failures, []);
  assert.equal(socket.closeCalls, 1);
});

test("an unexpected peer disconnect stops the ready session", async () => {
  const { client, socket, failures } = fixture();
  const started = client.start();
  socket.open();
  socket.receive(ready);
  await started;
  socket.onclose?.();
  assert.equal(failures.length, 1);
  assert.match(failures[0], /断开/);
  assert.equal(socket.closeCalls, 1);
});

test("synchronous consumer cleanup cannot replace the original fatal error", async () => {
  const socket = new FakeSocket();
  const client = new LiveClient({
    sessionId: SESSION,
    backendBaseUrl: "http://127.0.0.1:8765",
    socketFactory: () => socket as unknown as WebSocket,
    onMessage: () => client.close(),
    onFailure: () => assert.fail("Backend errors must not be duplicated"),
  });
  const started = client.start();
  socket.open();
  socket.receive({
    type: "error", session_id: SESSION, segment_id: null,
    code: "ASR_NOT_READY", message: "模型尚未准备好", fatal: true,
  });
  await assert.rejects(started, /模型尚未准备好/);
  assert.equal(socket.closeCalls, 1);
});
