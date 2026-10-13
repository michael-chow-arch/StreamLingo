"""Feed a known PCM WAV in real time through the running ASR + translation service.

This checks the local WebSocket/model path, not Chrome tab capture. The supplied
test recording and the resulting text stay on this machine.
"""

import argparse
import asyncio
from contextlib import suppress
import json
from pathlib import Path
from time import monotonic
from uuid import uuid4
import wave

from websockets.asyncio.client import connect


async def run(args):
    with wave.open(str(args.wav), "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            raise ValueError("Expected a 16 kHz, mono, PCM16 WAV")
        pcm = audio.readframes(audio.getnframes())
    session_id = str(uuid4())
    result = {"source": str(args.wav), "source_language": args.source_language,
              "target_language": args.target_language, "session_id": session_id, "events": []}
    began = monotonic()
    async with connect(args.url, origin=args.origin) as ws:
        await ws.send(json.dumps({"type": "start", "protocol_version": 1, "session_id": session_id,
                                 "source_language": args.source_language, "target_language": args.target_language,
                                 "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1}}))
        ready = json.loads(await asyncio.wait_for(ws.recv(), 20))
        if ready.get("type") != "ready" or ready.get("mode") != "whisperlivekit" or ready.get("translation") != "configured":
            raise RuntimeError(f"Real models are not ready: {ready}")
        if ready.get("source_language") != args.source_language or ready.get("target_language") != args.target_language:
            raise RuntimeError(f"Server did not acknowledge selected language mode: {ready}")
        result['ready'] = ready

        async def feed():
            # Trailing silence gives the streaming recognizer a natural boundary.
            recording = pcm + bytes(16000 * 2 * 12)
            clock = monotonic()
            for offset in range(0, len(recording), 5120):
                await asyncio.sleep(max(0, clock + offset / 32000 - monotonic()))
                await ws.send(recording[offset:offset + 5120])

        sender = asyncio.create_task(feed())
        latest = {}
        try:
            async with asyncio.timeout(max(75, len(pcm) / 32000 + 40)):
                while True:
                    try:
                        event = json.loads(await asyncio.wait_for(ws.recv(), 1))
                    except asyncio.TimeoutError:
                        if sender.done():
                            sender.result()
                            finals = [event for event in latest.values() if event["source_final"]]
                            if finals and all(event["translation"].get("status") == "complete" and
                                              event["translation"].get("is_mock") is False for event in finals):
                                result["passed"] = True
                                result["translated_segments"] = len(finals)
                                break
                        continue
                    result["events"].append({"received_after_s": round(monotonic() - began, 3), **event})
                    print(json.dumps(result["events"][-1], ensure_ascii=True), flush=True)
                    if event.get("type") == "error" and event.get("fatal"):
                        raise RuntimeError(event["message"])
                    if event.get("type") == "subtitle":
                        latest[event["segment_id"]] = event
        finally:
            sender.cancel()
            with suppress(asyncio.CancelledError):
                await sender
            await ws.send(json.dumps({"type": "stop", "session_id": session_id}))
            async with asyncio.timeout(10):
                while True:
                    if json.loads(await ws.recv()).get("type") == "stopped":
                        break
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: real ASR and non-mock {args.source_language}->{args.target_language} translation received; session stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws/live")
    parser.add_argument("--origin", default="chrome-extension://ggakbplmndfijhdcepbafoibilffbhmg")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-language", choices=['en', 'zh', 'auto'], default='en')
    parser.add_argument("--target-language", choices=['zh-CN', 'en'], default='zh-CN')
    asyncio.run(run(parser.parse_args()))
