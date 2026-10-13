/*!
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * Modified for StreamLingo: audio-only capture, native-rate playback, browser
 * resampling, PCM worklet, cancellation and explicit resource cleanup.
 * Based on chrome-extensions-samples/sample.tabcapture-recorder/offscreen.js.
 */
import { SAMPLE_RATE } from "./pcm";
import { AppError, type UiErrorInfo } from "../shared/i18n";

interface TabAudioConstraints extends MediaTrackConstraints {
  mandatory: { chromeMediaSource: "tab"; chromeMediaSourceId: string };
}

/** Owns capture resources even while asynchronous initialization is pending. */
export class TabAudioCapture {
  private closed = false;
  private media: MediaStream | undefined;
  private playback: AudioContext | undefined;
  private processing: AudioContext | undefined;
  private playbackSource: MediaStreamAudioSourceNode | undefined;
  private processingSource: MediaStreamAudioSourceNode | undefined;
  private worklet: AudioWorkletNode | undefined;

  constructor(
    private readonly onPacket: (packet: ArrayBuffer) => void,
    private readonly onFailure: (message: string, errorInfo?: UiErrorInfo) => void,
  ) {}

  async open(streamId: string): Promise<void> {
    const audio: TabAudioConstraints = {
      // tabCapture uses Chromium's legacy constraint syntax. Mixing mandatory
      // with standard echoCancellation/noiseSuppression/autoGainControl fields
      // causes Chromium to reject the entire request as malformed.
      mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId },
    };
    const media = await navigator.mediaDevices.getUserMedia({ audio, video: false });
    if (this.closed) {
      media.getTracks().forEach((track) => track.stop());
      throw new AppError("START_CANCELLED");
    }
    this.media = media;
    if (media.getAudioTracks().length === 0) throw new AppError("NO_AUDIO_TRACK");
    for (const track of media.getTracks()) {
      track.addEventListener("ended", () => {
        if (!this.closed) this.onFailure(new AppError("AUDIO_ENDED").message, { code: "AUDIO_ENDED" });
      });
    }

    // Chrome mutes the tab's original output while it is captured. Restore it
    // immediately at the device's native rate; ASR does not lower playback quality.
    this.playback = new AudioContext();
    this.playbackSource = this.playback.createMediaStreamSource(media);
    this.playbackSource.connect(this.playback.destination);
    await this.resume(this.playback);
    this.ensureOpen();

    this.processing = new AudioContext({ sampleRate: SAMPLE_RATE });
    if (this.processing.sampleRate !== SAMPLE_RATE) {
      throw new AppError("AUDIO_SAMPLE_RATE", `Actual sample rate: ${this.processing.sampleRate} Hz`);
    }
    await this.processing.audioWorklet.addModule(chrome.runtime.getURL("pcm-worklet.js"));
    this.ensureOpen();
    this.processingSource = this.processing.createMediaStreamSource(media);
    this.worklet = new AudioWorkletNode(this.processing, "streamlingo-pcm", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
      channelCountMode: "max",
    });
    this.worklet.port.onmessage = (event: MessageEvent<unknown>) => {
      if (!this.closed && event.data instanceof ArrayBuffer) this.onPacket(event.data);
    };
    this.worklet.onprocessorerror = () => {
      if (!this.closed) this.onFailure(new AppError("AUDIO_PROCESSING").message, { code: "AUDIO_PROCESSING" });
    };
    this.processingSource.connect(this.worklet);
    // A connected destination keeps the graph rendered. Worklet output is zero.
    this.worklet.connect(this.processing.destination);
    await this.resume(this.processing);
    this.ensureOpen();
  }

  startSending(): void {
    this.ensureOpen();
    this.worklet?.port.postMessage("start");
  }

  async close(): Promise<void> {
    if (this.closed) return;
    this.closed = true;
    if (this.worklet) {
      this.worklet.port.onmessage = null;
      this.worklet.onprocessorerror = null;
      this.worklet.port.postMessage("stop");
      this.worklet.port.close();
      this.worklet.disconnect();
    }
    this.processingSource?.disconnect();
    this.playbackSource?.disconnect();
    // Stopping the tracks releases Chrome's tab capture and restores native sound.
    this.media?.getTracks().forEach((track) => track.stop());
    await Promise.allSettled([this.processing?.close(), this.playback?.close()]);
  }

  private ensureOpen(): void {
    if (this.closed) throw new AppError("START_CANCELLED");
  }

  private async resume(context: AudioContext): Promise<void> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([
        context.resume(),
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => reject(new AppError("AUDIO_RESUME")), 5_000);
        }),
      ]);
      if (context.state !== "running") throw new AppError("AUDIO_RESUME");
    } finally {
      clearTimeout(timer);
    }
  }
}
