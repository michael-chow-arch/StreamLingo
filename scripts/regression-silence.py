"""Exercise synthetic English speech through real ASR + translation.

Uses only the existing Microsoft Zira test WAV; never captures user audio.
Two rounds means initial speech, 16 s silence, resumed speech, 16 s silence,
and resumed speech again, all within one WebSocket session. No model is loaded
by this script. Run only after the local service is available for the test.
With --continuous, send a long natural passage without inserted pauses and
require regular final/Chinese arrivals before speaking stops. Prepare its
default WAV using scripts/make-continuous-fixture.ps1.
"""

import argparse
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from time import monotonic
from uuid import uuid4
import wave

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


BYTES_PER_SECOND = 32_000
PACKET_BYTES = 5_120


def make_fixture(args: argparse.Namespace) -> tuple[bytes, list[dict]]:
    with wave.open(str(args.wav), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
            raise ValueError("Expected 16 kHz, mono, PCM16 synthetic test WAV")
        speech = wav.readframes(wav.getnframes())
    if not speech:
        raise ValueError("Test WAV is empty")
    pieces = []
    phases = []
    offset = 0

    def append(kind: str, audio: bytes, round_number: int) -> None:
        nonlocal offset
        phases.append({
            "kind": kind,
            "round": round_number,
            "start_ms": round(offset / 32),
            "end_ms": round((offset + len(audio)) / 32),
        })
        pieces.append(audio)
        offset += len(audio)

    append("speech", speech, 0)
    for round_number in range(1, 1 if args.continuous else args.rounds + 1):
        append("silence", bytes(args.silence_seconds * BYTES_PER_SECOND), round_number)
        append("speech", speech, round_number)
    append("tail_silence", bytes(args.tail_seconds * BYTES_PER_SECOND), 0 if args.continuous else args.rounds)
    return b"".join(pieces), phases


def summarize_windows(latest: dict[int, dict], phases: list[dict]) -> list[dict]:
    windows = [{**phase, "final_segments": [], "translated_segments": []}
               for phase in phases if phase["kind"] == "speech"]
    for segment_id, event in sorted(latest.items()):
        if not event.get("source_final"):
            continue
        start, end = event["start_ms"], event["end_ms"]
        overlaps = [max(0, min(end, item["end_ms"]) - max(start, item["start_ms"])) for item in windows]
        if not overlaps or max(overlaps) <= 0:
            continue
        window = windows[overlaps.index(max(overlaps))]
        window["final_segments"].append(segment_id)
        translation = event.get("translation", {})
        if (translation.get("status") == "complete" and translation.get("is_mock") is False
                and re.search(r"[\u3400-\u9fff]", translation.get("text") or "")):
            window["translated_segments"].append(segment_id)
    return windows


def check_revision(latest: dict[int, dict], event: dict) -> None:
    segment_id = event["segment_id"]
    previous = latest.get(segment_id)
    if previous:
        if event["revision"] <= previous["revision"]:
            raise RuntimeError(f"Subtitle revision did not increase for segment {segment_id}")
        if previous["source_final"] and (
            not event["source_final"] or
            any(event[key] != previous[key] for key in ("source_text", "start_ms", "end_ms"))
        ):
            raise RuntimeError(f"Final source changed for segment {segment_id}")
    latest[segment_id] = event


def continuous_metrics(events: list[dict], latest: dict[int, dict], duration: float) -> dict:
    """Measure arrival cadence while speech is still being sent, not after stop."""
    first_final: dict[int, dict] = {}
    first_complete: dict[int, dict] = {}
    first_chinese: dict[int, dict] = {}
    for event in events:
        if event.get("type") != "subtitle" or not event.get("source_final"):
            continue
        segment_id = event["segment_id"]
        first_final.setdefault(segment_id, event)
        translation = event.get("translation", {})
        if (translation.get("status") == "complete" and translation.get("is_mock") is False
                and (translation.get("text") or "").strip()):
            first_complete.setdefault(segment_id, event)
            # Numbers/names can be valid completed translations without a Han
            # character. Still require actual Chinese regularly in the stream.
            if re.search(r"[\u3400-\u9fff]", translation["text"]):
                first_chinese.setdefault(segment_id, event)

    def active_times(items: dict[int, dict]) -> list[float]:
        return sorted(item["stream_after_s"] for item in items.values()
                      if 0 <= item.get("stream_after_s", duration) < duration)

    def longest_gap(times: list[float]) -> float:
        boundaries = [0.0, *times, duration]
        return round(max(right - left for left, right in zip(boundaries, boundaries[1:])), 3)

    final_times, chinese_times = active_times(first_final), active_times(first_chinese)
    windows = []
    for start in range(0, int(duration), 30):
        end = min(start + 30, duration)
        windows.append({
            "start_s": start, "end_s": round(end, 3),
            "final_arrivals": sum(start <= item < end for item in final_times),
            "real_chinese_arrivals": sum(start <= item < end for item in chinese_times),
        })
    finals = [item for item in latest.values() if item.get("source_final")]
    partials = [item for item in events if item.get("type") == "subtitle" and not item.get("source_final")]
    return {
        "speech_seconds": duration,
        "active_windows": windows,
        "finals_during_speech": len(final_times),
        "real_chinese_during_speech": len(chinese_times),
        "first_real_chinese_s": chinese_times[0] if chinese_times else None,
        "last_real_chinese_s": chinese_times[-1] if chinese_times else None,
        "max_final_arrival_gap_s": longest_gap(final_times),
        "max_real_chinese_arrival_gap_s": longest_gap(chinese_times),
        "max_segment_characters": max((len(item["source_text"]) for item in finals), default=0),
        "max_segment_duration_s": round(max(((item["end_ms"] - item["start_ms"]) / 1000
                                              for item in finals), default=0), 3),
        "max_partial_characters": max((len(item["source_text"]) for item in partials), default=0),
        "total_final_segments": len(finals),
        "total_real_chinese_segments": len(first_chinese),
        "total_real_complete_segments": len(first_complete),
        "unfinished_source_ids": [item["segment_id"] for item in latest.values() if not item.get("source_final")],
        "unfinished_translation_ids": [item["segment_id"] for item in finals
                                       if item["segment_id"] not in first_complete],
    }


def continuous_failures(metrics: dict, args: argparse.Namespace) -> list[str]:
    failures = []
    for key, limit in (("max_final_arrival_gap_s", args.max_final_gap),
                       ("max_real_chinese_arrival_gap_s", args.max_translation_gap),
                       ("max_segment_characters", args.max_segment_chars),
                       ("max_segment_duration_s", args.max_segment_seconds)):
        if metrics[key] > limit:
            failures.append(f"{key}={metrics[key]} exceeds {limit}")
    if any(not window["final_arrivals"] or not window["real_chinese_arrivals"]
           for window in metrics["active_windows"] if window["end_s"] - window["start_s"] >= 10):
        failures.append("A speech window lacked final/real Chinese arrivals while speaking")
    if metrics["unfinished_translation_ids"]:
        failures.append("Some final segments did not receive real Chinese translations")
    if metrics["unfinished_source_ids"]:
        failures.append("Some source segments remained partial after the tail silence")
    return failures


def compare_transcript(latest: dict[int, dict], reference: Path) -> dict:
    """Diagnostic word alignment only: no assumption of perfect TTS recognition."""
    source = reference.read_text(encoding="utf-8-sig")
    recognized = " ".join(event["source_text"] for _, event in sorted(latest.items())
                          if event.get("source_final"))
    expected_words = re.findall(r"[a-z0-9]+", source.lower())
    actual_words = re.findall(r"[a-z0-9]+", recognized.lower())
    matcher = SequenceMatcher(None, expected_words, actual_words, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    differences = [{"operation": tag, "expected": " ".join(expected_words[a:b]),
                    "recognized": " ".join(actual_words[c:d])}
                   for tag, a, b, c, d in matcher.get_opcodes() if tag != "equal"]
    return {
        "reference_path": str(reference.resolve()),
        "expected_words": len(expected_words), "recognized_words": len(actual_words),
        "reference_word_coverage": round(matched / max(1, len(expected_words)), 4),
        "recognized_word_alignment": round(matched / max(1, len(actual_words)), 4),
        "diagnostic_only": True,
        "differences": differences,
        "recognized_final_text": recognized,
    }


async def run(args: argparse.Namespace) -> dict:
    pcm, phases = make_fixture(args)
    speech_seconds = phases[0]["end_ms"] / 1000
    if args.continuous and speech_seconds < 180:
        raise ValueError("Continuous regression requires at least 180 seconds of synthetic speech")
    if args.describe:
        report = {"audio_seconds": len(pcm) / BYTES_PER_SECOND, "phases": phases}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report

    session_id = str(uuid4())
    report = {
        "passed": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Microsoft Zira Desktop synthetic English WAV; no user audio captured",
        "profile": "continuous" if args.continuous else "long_silence",
        "wav": str(args.wav.resolve()),
        "url": args.url,
        "session_id": session_id,
        "audio_seconds": len(pcm) / BYTES_PER_SECOND,
        "phases": phases,
        "phase_transitions": [],
        "events": [],
        "fatal_errors": [],
        "nonfatal_errors": [],
        "stopped_acknowledged": False,
    }
    latest: dict[int, dict] = {}
    begin = monotonic()
    stream_begin: float | None = None
    feed_finished: float | None = None
    failure: Exception | None = None

    def record(event: dict) -> None:
        if event.get("session_id") not in (None, session_id):
            raise RuntimeError("Received a message for another session")
        item = {"received_after_s": round(monotonic() - begin, 3), **event}
        if stream_begin is not None:
            item["stream_after_s"] = round(monotonic() - stream_begin, 3)
        report["events"].append(item)
        if event.get("type") == "error":
            report["fatal_errors" if event.get("fatal") else "nonfatal_errors"].append(item)
            print(json.dumps(item, ensure_ascii=True), flush=True)
            if event.get("fatal"):
                raise RuntimeError(f"{event.get('code')}: {event.get('message')}")
        elif event.get("type") == "subtitle":
            check_revision(latest, event)
            if event.get("source_final"):
                print(json.dumps(item, ensure_ascii=True), flush=True)

    try:
        async with connect(args.url, origin=args.origin, open_timeout=10, close_timeout=5) as ws:
            await ws.send(json.dumps({
                "type": "start", "protocol_version": 1, "session_id": session_id,
                "source_language": "en", "target_language": "zh-CN",
                "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1},
            }))
            ready = json.loads(await asyncio.wait_for(ws.recv(), 20))
            record(ready)
            if (ready.get("type") != "ready" or ready.get("mode") != "whisperlivekit"
                    or ready.get("translation") != "configured"):
                raise RuntimeError(f"Expected real ASR and configured translation: {ready}")
            stream_begin = monotonic()

            async def feed() -> None:
                nonlocal feed_finished
                phase_index = 0
                for offset in range(0, len(pcm), PACKET_BYTES):
                    await asyncio.sleep(max(0, stream_begin + offset / BYTES_PER_SECOND - monotonic()))
                    while phase_index < len(phases) and offset / 32 >= phases[phase_index]["start_ms"]:
                        phase = {**phases[phase_index], "stream_after_s": round(monotonic() - stream_begin, 3)}
                        report["phase_transitions"].append(phase)
                        print("PHASE " + json.dumps(phase), flush=True)
                        phase_index += 1
                    await ws.send(pcm[offset:offset + PACKET_BYTES])
                await asyncio.sleep(max(0, stream_begin + len(pcm) / BYTES_PER_SECOND - monotonic()))
                feed_finished = monotonic()

            sender = asyncio.create_task(feed(), name="regression-silence-feed")
            try:
                deadline = stream_begin + len(pcm) / BYTES_PER_SECOND + args.settle_seconds
                while monotonic() < deadline:
                    if sender.done():
                        sender.result()
                    try:
                        event = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
                    except asyncio.TimeoutError:
                        if feed_finished is not None and monotonic() - feed_finished >= 2:
                            windows = summarize_windows(latest, phases)
                            completed = all(window["final_segments"] and window["translated_segments"] for window in windows)
                            if args.continuous:
                                metrics = continuous_metrics(report["events"], latest, speech_seconds)
                                completed = (completed and not metrics["unfinished_translation_ids"]
                                             and not metrics["unfinished_source_ids"])
                            if completed:
                                break
                        continue
                    record(event)
                    if event.get("type") == "stopped":
                        raise RuntimeError("Service ended the session before the client requested stop")
                else:
                    raise RuntimeError("Continuous regression did not fully settle" if args.continuous
                                       else "Missing final/Chinese subtitle after one or more resumed speech windows")
            finally:
                sender.cancel()
                with suppress(asyncio.CancelledError, ConnectionClosed):
                    await sender
                # Stop only this script's acknowledged session. A SESSION_CONFLICT
                # rejection occurs before this block, so existing user work is safe.
                try:
                    await ws.send(json.dumps({"type": "stop", "session_id": session_id}))
                    async with asyncio.timeout(10):
                        while True:
                            event = json.loads(await ws.recv())
                            record(event)
                            if event.get("type") == "stopped":
                                report["stopped_acknowledged"] = True
                                break
                except (ConnectionClosed, asyncio.TimeoutError):
                    pass
        report["speech_windows"] = summarize_windows(latest, phases)
        if not report["stopped_acknowledged"]:
            raise RuntimeError("Server did not acknowledge stop")
        if not all(item["final_segments"] and item["translated_segments"] for item in report["speech_windows"]):
            raise RuntimeError("At least one speech window lacked a final or real Chinese subtitle")
        if args.continuous:
            errors = continuous_failures(continuous_metrics(report["events"], latest, speech_seconds), args)
            if errors:
                raise RuntimeError("; ".join(errors))
        report["passed"] = True
    except Exception as exc:
        failure = exc
        report["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = round(monotonic() - begin, 3)
        report["speech_windows"] = summarize_windows(latest, phases)
        report["latest_segments"] = list(latest.values())
        if args.continuous:
            report["continuous_metrics"] = continuous_metrics(report["events"], latest, speech_seconds)
            report["continuous_failures"] = continuous_failures(report["continuous_metrics"], args)
            reference = args.reference or args.wav.with_suffix(".txt")
            if reference.is_file():
                report["transcript_alignment"] = compare_transcript(latest, reference)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if failure:
        raise failure
    print("PASS: continuous speech produced bounded finals + real Chinese before stop; no fatal; stopped."
          if args.continuous else
          f"PASS: {args.rounds} long-silence resumptions, all windows have final + real Chinese, no fatal; stopped.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", type=Path)
    parser.add_argument("--reference", type=Path, help="Original synthetic text for diagnostic word alignment")
    parser.add_argument("--continuous", action="store_true", help="Feed one long synthetic passage without inserted pauses")
    parser.add_argument("--max-final-gap", type=float, default=12)
    parser.add_argument("--max-translation-gap", type=float, default=15)
    parser.add_argument("--max-segment-chars", type=int, default=180)
    parser.add_argument("--max-segment-seconds", type=float, default=6)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws/live")
    parser.add_argument("--origin", default="chrome-extension://ggakbplmndfijhdcepbafoibilffbhmg")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--silence-seconds", type=int, default=16)
    parser.add_argument("--tail-seconds", type=int, default=6)
    parser.add_argument("--settle-seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("output/asr/silence-regression.json"))
    parser.add_argument("--describe", action="store_true", help="Print the test schedule without connecting")
    args = parser.parse_args()
    if args.wav is None:
        args.wav = Path("output/asr/english-continuous.wav" if args.continuous else "output/asr/english-synthetic.wav")
    if args.rounds < 1 or min(args.silence_seconds, args.tail_seconds, args.settle_seconds) <= 0:
        parser.error("Rounds and timing parameters must be positive")
    if min(args.max_final_gap, args.max_translation_gap, args.max_segment_chars, args.max_segment_seconds) <= 0:
        parser.error("Continuous regression limits must be positive")
    asyncio.run(run(args))
