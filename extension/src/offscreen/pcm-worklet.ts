// Reference: WhisperLiveKit's PCMForwarder (Apache-2.0). See README.md.
// StreamLingo adds mono downmix, PCM16 packetization and an explicit start gate.
import { PcmPacketizer } from "./pcm";

// lib.dom intentionally omits AudioWorkletGlobalScope. Keep declarations local.
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
}
declare function registerProcessor(name: string, processor: typeof AudioWorkletProcessor): void;

class StreamLingoPcmProcessor extends AudioWorkletProcessor {
  private enabled = false;
  private readonly packetizer = new PcmPacketizer();

  constructor() {
    super();
    this.port.onmessage = (event: MessageEvent<unknown>) => {
      if (event.data === "start") {
        this.packetizer.reset();
        this.enabled = true;
      } else if (event.data === "stop") {
        this.enabled = false;
        this.packetizer.reset();
      }
    };
  }

  process(inputs: Float32Array[][]): boolean {
    if (this.enabled) {
      this.packetizer.push(inputs[0] ?? [], (packet) => this.port.postMessage(packet, [packet]));
    }
    // Output remains silent; the original audio has its own playback path.
    return true;
  }
}

registerProcessor("streamlingo-pcm", StreamLingoPcmProcessor);
