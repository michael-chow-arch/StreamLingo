"""Run real streaming ASR against a supplied 16 kHz mono PCM16 WAV file.

The checked run uses a Microsoft Zira synthetic English voice, not a recording
of a person or YouTube. Model output is never replaced with the known text.
"""

import argparse
import asyncio
from contextlib import suppress
from dataclasses import asdict
import json
import logging
from pathlib import Path
import time
import wave

from streamlingo.adapters.whisperlivekit import WhisperLiveKitRecognizer
from streamlingo.domain.models import AudioFormat
from streamlingo.settings import Settings


async def run(args: argparse.Namespace) -> dict:
    with wave.open(str(args.audio), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
            raise ValueError("Expected 16 kHz, mono, PCM16 WAV")
        pcm = wav.readframes(wav.getnframes())
    model_started = time.monotonic()
    recognizer = WhisperLiveKitRecognizer.load(Settings(
        model="base.en", model_dir=str(args.model_dir.resolve()),
    ))
    model_seconds = time.monotonic() - model_started
    runtime_model = recognizer.engine.asr.model.model
    device = runtime_model.device
    compute_type = runtime_model.compute_type
    print(f"ASR model loaded in {model_seconds:.2f} seconds ({device}, {compute_type})", flush=True)
    recognition = await recognizer.open_session(audio_format=AudioFormat(), language="en")
    events = []
    started = time.monotonic()

    async def collect() -> None:
        previous = None
        async for event in recognition.events():
            payload = asdict(event)
            if payload == previous:
                continue
            previous = payload
            record = {**payload, "received_seconds": round(time.monotonic() - started, 3)}
            events.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)

    collector = asyncio.create_task(collect())
    try:
        # Browser-equivalent 160 ms packets; silence allows VAD to finalize.
        pcm += bytes(16000 * 2 * args.tail_seconds)
        for offset in range(0, len(pcm), 5120):
            if collector.done():
                collector.result()
                raise RuntimeError("ASR output stream ended before audio finished")
            await recognition.push_audio(pcm[offset:offset + 5120])
            await asyncio.sleep(0.16)
        await asyncio.sleep(args.settle_seconds)
        if collector.done():
            collector.result()
    finally:
        collector.cancel()
        with suppress(asyncio.CancelledError):
            await collector
        await asyncio.wait_for(recognition.close(), 15)

    report = {
        "source": "synthetic English speech supplied as WAV; actual ASR inference",
        "audio_path": str(args.audio.resolve()),
        "model_dir": str(args.model_dir.resolve()),
        "model_load_seconds": round(model_seconds, 3),
        "device": device,
        "compute_type": compute_type,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "events": events,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not events:
        raise RuntimeError("No ASR transcript events were produced")
    if not any(event["is_final"] for event in events):
        raise RuntimeError("ASR produced only interim events: no final sentence was available for translation")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=Path("output/asr/english-synthetic.wav"))
    parser.add_argument("--model-dir", type=Path, default=Path("models/whisper-base.en"))
    parser.add_argument("--report", type=Path, default=Path("output/asr/asr-smoke.json"))
    parser.add_argument("--tail-seconds", type=int, default=4)
    parser.add_argument("--settle-seconds", type=int, default=3)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
