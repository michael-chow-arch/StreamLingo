import assert from "node:assert/strict";
import test from "node:test";
import { TabAudioCapture } from "./capture";

function replaceGlobal(key: string, value: unknown): () => void {
  const previous = Object.getOwnPropertyDescriptor(globalThis, key);
  Object.defineProperty(globalThis, key, { configurable: true, value });
  return () => {
    if (previous) Object.defineProperty(globalThis, key, previous);
    else Reflect.deleteProperty(globalThis, key);
  };
}

test("tab capture uses only Chromium legacy mandatory constraints, without mixing standard fields", async () => {
  let requested: MediaStreamConstraints | undefined;
  const restore = replaceGlobal("navigator", {
    mediaDevices: {
      getUserMedia: async (constraints: MediaStreamConstraints) => {
        requested = constraints;
        throw new Error("Stop after recording browser constraints");
      },
    },
  });
  try {
    const capture = new TabAudioCapture(() => undefined, () => undefined);
    await assert.rejects(capture.open("authorized-tab-stream"), /Stop after recording/);
    assert.deepEqual(requested, {
      audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: "authorized-tab-stream" } },
      video: false,
    });
    await capture.close();
  } finally {
    restore();
  }
});

test("stop during getUserMedia releases a late stream without creating an audio graph", async () => {
  let completeCapture: ((stream: MediaStream) => void) | undefined;
  const mediaPromise = new Promise<MediaStream>((resolve) => { completeCapture = resolve; });
  let stops = 0;
  const stream = { getTracks: () => [{ stop: () => { stops += 1; } }] } as unknown as MediaStream;
  const restore = replaceGlobal("navigator", { mediaDevices: { getUserMedia: () => mediaPromise } });
  try {
    const capture = new TabAudioCapture(() => assert.fail("No packets before ready"), () => assert.fail("No failure on explicit close"));
    const opening = capture.open("authorized-tab-stream");
    await capture.close();
    completeCapture?.(stream);
    await assert.rejects(opening, /已取消/);
    await capture.close();
    assert.equal(stops, 1);
  } finally {
    restore();
  }
});

test("a browser that ignores the requested sample rate is rejected and all resources can be closed", async () => {
  let stops = 0;
  let closes = 0;
  let disconnects = 0;
  const track = { stop: () => { stops += 1; }, addEventListener: () => undefined };
  const stream = { getTracks: () => [track], getAudioTracks: () => [track] } as unknown as MediaStream;
  class WrongRateContext {
    readonly sampleRate = 48_000;
    readonly state = "running";
    readonly destination = {};
    createMediaStreamSource() {
      return { connect: () => undefined, disconnect: () => { disconnects += 1; } };
    }
    resume(): Promise<void> { return Promise.resolve(); }
    close(): Promise<void> { closes += 1; return Promise.resolve(); }
  }
  const restoreNavigator = replaceGlobal("navigator", { mediaDevices: { getUserMedia: async () => stream } });
  const restoreContext = replaceGlobal("AudioContext", WrongRateContext);
  try {
    const capture = new TabAudioCapture(() => assert.fail("No packets at the wrong rate"), () => undefined);
    await assert.rejects(capture.open("authorized-tab-stream"), { code: "AUDIO_SAMPLE_RATE", detail: "Actual sample rate: 48000 Hz" });
    await capture.close();
    await capture.close();
    assert.equal(stops, 1);
    assert.equal(closes, 2);
    assert.equal(disconnects, 1);
  } finally {
    restoreContext();
    restoreNavigator();
  }
});
