/*!
 * PCM16 conversion adapted from WhisperLiveKit recorder_worker.js (Apache-2.0).
 * StreamLingo adds stateful packetization, downmix and non-finite-value handling.
 * See README.md and LICENSE.apache-2.0.txt in the source directory.
 */
/** Encoding adapter only: sample-rate conversion belongs to Web Audio. */
export const SAMPLE_RATE = 16_000;
export const PACKET_SAMPLES = 2_560; // 160 ms at 16 kHz.

/** Stateful packetization preserves samples across AudioWorklet render quanta. */
export class PcmPacketizer {
  private buffer: ArrayBuffer;
  private view: DataView;
  private position = 0;

  constructor(private readonly packetSamples = PACKET_SAMPLES) {
    if (!Number.isSafeInteger(packetSamples) || packetSamples <= 0) {
      throw new Error("packetSamples must be a positive integer");
    }
    this.buffer = new ArrayBuffer(packetSamples * 2);
    this.view = new DataView(this.buffer);
  }

  push(channels: readonly Float32Array[], emit: (packet: ArrayBuffer) => void): void {
    if (channels.length === 0) return;
    const frames = channels[0].length;
    for (let frame = 0; frame < frames; frame += 1) {
      let sum = 0;
      for (const channel of channels) {
        const sample = channel[frame];
        sum += Number.isFinite(sample) ? sample : 0;
      }
      const mono = Math.max(-1, Math.min(1, sum / channels.length));
      this.view.setInt16(this.position * 2, mono < 0 ? mono * 0x8000 : mono * 0x7fff, true);
      this.position += 1;
      if (this.position === this.packetSamples) {
        const completed = this.buffer;
        this.buffer = new ArrayBuffer(this.packetSamples * 2);
        this.view = new DataView(this.buffer);
        this.position = 0;
        emit(completed);
      }
    }
  }

  reset(): void {
    this.position = 0;
  }
}
