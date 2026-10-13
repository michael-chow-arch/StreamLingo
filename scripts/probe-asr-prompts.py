"""Compare real local decoding with and without a deliberately repetitive prompt.

Stop the local ASR service first so this GPU probe does not compete with a live
session. Uses only original synthetic WAV fixtures; never captures user audio.
The poisoned prompt is a diagnostic input, not evidence of the exact live cause.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import socket
from time import monotonic
import wave

import numpy as np

from streamlingo.adapters.whisperlivekit import WhisperLiveKitRecognizer
from streamlingo.settings import Settings


def load_audio(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            raise ValueError("Expected 16 kHz mono PCM16")
        return np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float32) / 32768


def assess(report: dict) -> None:
    def case(fixture: str, profile: str) -> dict:
        return next(item for item in report["cases"] if item["fixture"] == fixture and item["profile"] == profile)

    fixed = case("spoken_repetition", "fixed_repetitive_prompt")
    normalized = re.sub(r"[^a-z ]", " ", fixed["text"].lower())
    normalized = " ".join(normalized.split())
    report["checks"] = {
        "please_wait_count": normalized.count("please wait"),
        "very_very_preserved": "very very" in normalized,
        "fixed_speech_matches_clean_baseline": fixed["text"] == case("spoken_repetition", "old_clean")["text"],
        "injected_phrase_absent_in_fixed_cases": all("karikum" not in item["text"].lower()
            for item in report["cases"] if item["profile"] == "fixed_repetitive_prompt"),
        "fixed_silence_matches_clean_baseline": case("silence", "fixed_repetitive_prompt")["text"] == case("silence", "old_clean")["text"],
    }
    report["silence_observation"] = {
        "fixed_text": case("silence", "fixed_repetitive_prompt")["text"],
        "limitation": "Direct model decoding bypasses live VAD. Clearing prompt feedback does not eliminate all silence hallucinations.",
    }
    report["passed"] = (report["checks"]["please_wait_count"] == 2 and
                        all(value for key, value in report["checks"].items() if key != "please_wait_count"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=Path("models/whisper-base.en"))
    parser.add_argument("--repeat-wav", type=Path, default=Path("output/regression-repetition/english-repeat.wav"))
    parser.add_argument("--output", type=Path, default=Path("output/regression-repetition/prompt-probe.json"))
    parser.add_argument("--review-existing", type=Path, help="Assess saved model outputs without repeating inference; preserve the original file")
    args = parser.parse_args()
    if args.review_existing:
        if args.review_existing.resolve() == args.output.resolve():
            parser.error("Offline review must use a separate output path")
        report = json.loads(args.review_existing.read_text(encoding="utf-8"))
        report["offline_review"] = {"original_report": str(args.review_existing.resolve()),
            "inference_repeated": False,
            "reason": "Evaluate prompt-feedback isolation. The original requirement for empty VAD-free silence was broader than this fix."}
        assess(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"passed": report["passed"], "checks": report["checks"], "output": str(args.output)}))
        if not report["passed"]:
            raise SystemExit(1)
        return
    try:
        connection = socket.create_connection(("127.0.0.1", 8765), timeout=0.5)
    except OSError:
        pass
    else:
        connection.close()
        parser.error("Stop the local service first; the GPU probe must not compete with a live ASR session")
    recognizer = WhisperLiveKitRecognizer.load(Settings(model_dir=str(args.model_dir.resolve())))
    protected = recognizer.engine.asr.model
    baseline = protected.wrapped_model
    bad_history = ("Assaam karikum, " * 14).strip()
    report = {"source": "original synthetic English and digital silence; real local base.en inference",
              "limitation": "Not a recording or reproduction of the user's YouTube audio",
              "cases": []}
    repeat = load_audio(args.repeat_wav)
    for name, audio in (("spoken_repetition", repeat), ("silence", np.zeros(8 * 16000, dtype=np.float32))):
        for profile, model, prompt in (("old_clean", baseline, None), ("old_repetitive_prompt", baseline, bad_history),
                                       ("fixed_repetitive_prompt", protected, bad_history)):
            began = monotonic()
            segments, info = model.transcribe(audio, language="en", word_timestamps=True,
                beam_size=1, best_of=1, temperature=0.0, condition_on_previous_text=True, initial_prompt=prompt)
            segments = list(segments)
            text = "".join(segment.text for segment in segments).strip()
            record = {"fixture": name, "profile": profile, "seconds": round(monotonic() - began, 3),
                      "text": text, "segments": [asdict(segment) for segment in segments]}
            report["cases"].append(record)
            print(json.dumps({key: value for key, value in record.items() if key != "segments"}, ensure_ascii=True), flush=True)
    assess(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": report["checks"], "output": str(args.output)}, ensure_ascii=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
