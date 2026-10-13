import assert from "node:assert/strict";
import test from "node:test";
import { PACKET_SAMPLES, PcmPacketizer } from "./pcm";

function samples(packet: ArrayBuffer): number[] {
  const view = new DataView(packet);
  return Array.from({ length: packet.byteLength / 2 }, (_, i) => view.getInt16(i * 2, true));
}

test("PCM16 clips saturated samples, keeps little-endian order and handles non-finite input", () => {
  const packetizer = new PcmPacketizer(7);
  const packets: ArrayBuffer[] = [];
  packetizer.push([new Float32Array([-2, -1, -0.5, 0.5, 1, 2, NaN])], (packet) => packets.push(packet));
  assert.deepEqual(samples(packets[0]), [-32768, -32768, -16384, 16383, 32767, 32767, 0]);
  assert.deepEqual(Array.from(new Uint8Array(packets[0]).slice(0, 2)), [0, 128]);
});

test("stereo downmix averages channels and preserves render-quantum boundaries", () => {
  const packetizer = new PcmPacketizer(4);
  const packets: ArrayBuffer[] = [];
  const emit = (packet: ArrayBuffer) => packets.push(packet);
  packetizer.push([new Float32Array([1, 0]), new Float32Array([-1, 1])], emit);
  assert.equal(packets.length, 0);
  packetizer.push([new Float32Array([-1, 1, 0]), new Float32Array([0, 1, 0])], emit);
  assert.deepEqual(samples(packets[0]), [0, 16383, -16384, 32767]);
  packetizer.push([new Float32Array([1, 1, 1])], emit);
  assert.deepEqual(samples(packets[1]), [0, 32767, 32767, 32767]);
});

test("default packets are 160 ms and silence is transmitted without collapsing the audio timeline", () => {
  const packetizer = new PcmPacketizer();
  const packets: ArrayBuffer[] = [];
  for (let quantum = 0; quantum < 40; quantum += 1) {
    packetizer.push([new Float32Array(128)], (packet) => packets.push(packet));
  }
  assert.equal(packets.length, 2);
  assert.equal(packets[0].byteLength, PACKET_SAMPLES * 2);
  assert.ok(samples(packets[0]).every((sample) => sample === 0));
});

test("reset discards a previous partial packet", () => {
  const packetizer = new PcmPacketizer(2);
  const packets: ArrayBuffer[] = [];
  packetizer.push([new Float32Array([-1])], (packet) => packets.push(packet));
  packetizer.reset();
  packetizer.push([new Float32Array([1, 1])], (packet) => packets.push(packet));
  assert.deepEqual(samples(packets[0]), [32767, 32767]);
});
