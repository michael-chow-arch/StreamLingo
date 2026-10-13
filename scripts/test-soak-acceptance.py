"""Offline harness failure-path checks; fake WS/HTTP, no real service or inference."""
import asyncio
from copy import deepcopy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("soak", ROOT / "scripts/soak-acceptance.py")
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


async def check(kind):
    folder = ROOT / "output/release-acceptance/harness-unit-tests" / str(uuid4())
    fixture = folder / "fixtures/en"
    fixture.mkdir(parents=True)
    with wave.open(str(fixture / "speech.wav"), "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(bytes(320))
    soak.write_json(fixture / "manifest.json", {"looped_audio": False, "voice": "SOFTWARE UNIT TEST ONLY",
        "wav_sha256": hashlib.sha256((fixture / "speech.wav").read_bytes()).hexdigest()})
    (fixture / "reference.txt").write_text("Software unit test only.", encoding="utf-8")
    arguments = SimpleNamespace(fixtures=folder / "fixtures", minimum_seconds=.01, tail_seconds=.01,
        drain_seconds=.01, max_translation_gap=20, max_send_lateness=1, url="ws://never-connect.invalid/",
        health_url="http://never-connect.invalid/", origin="fixture", service_log=None)
    sent = []

    class FakeHTTP:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url):
            return SimpleNamespace(json=lambda: {"mode": "whisperlivekit", "status": "ready", "translation": "configured"})

    class FakeSocket:
        def __init__(self):
            self.responses = asyncio.Queue()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def send(self, data):
            if isinstance(data, bytes):
                return
            message = json.loads(data)
            sent.append(message)
            session_id = message["session_id"]
            if message["type"] == "stop":
                await self.responses.put({"type": "stopped", "session_id": session_id, "reason": "user"})
            elif kind == "conflict":
                await self.responses.put({"type": "error", "session_id": session_id, "segment_id": None,
                    "code": "SESSION_CONFLICT", "message": "Software fixture", "fatal": True})
            else:
                await self.responses.put({"type": "ready", "session_id": session_id, "protocol_version": 1,
                    "mode": "whisperlivekit", "translation": "configured", "source_language": "en", "target_language": "zh-CN"})
                await self.responses.put({"type": "error", "session_id": session_id, "segment_id": None,
                    "code": "AUDIO_BACKLOG", "message": "Software fixture", "fatal": True})
        async def recv(self):
            return json.dumps(await self.responses.get())

    with patch("httpx.AsyncClient", FakeHTTP), patch("websockets.asyncio.client.connect", lambda *a, **kw: FakeSocket()):
        with redirect_stdout(io.StringIO()):
            report = await soak.run_one(arguments, "en", folder / "result")
    assert report["passed"] is False
    assert len(report["errors"]) == 1 and report["errors"][0]["fatal"] is True
    assert report["failure"] and report["acceptance_failures"]
    assert report["stopped_acknowledged"] is (kind != "conflict")
    assert sum(m["type"] == "stop" for m in sent) == (0 if kind == "conflict" else 1)
    summary = json.loads((folder / "result/summary.json").read_text(encoding="utf-8"))
    raw = [json.loads(line) for line in (folder / "result/events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert summary["events"] == raw and raw
    assert all("received_after_s" in event for event in raw)
    print(f"PASS offline {kind}: failure and raw events retained; stop ownership respected")


def completed_recording():
    events = []
    for segment_id in (1, 2):
        cue = {"type": "subtitle", "segment_id": segment_id, "session_id": "offline-unit-test",
               "source_final": True, "source_text": f"Original sentence {segment_id}.",
               "start_ms": (segment_id - 1) * 300, "end_ms": segment_id * 300,
               "received_after_s": segment_id * .4, "stream_after_s": segment_id * .4}
        events.append({**cue, "revision": 1, "translation": {"status": "pending"}})
        events.append({**cue, "revision": 2, "translation": {"status": "complete", "is_mock": False, "text": f"译文{segment_id}。"}})
    return {"session_id": "offline-unit-test", "metadata": {"speech_seconds": 1}, "events": events,
            "feed_finished": True, "stopped_acknowledged": True, "max_send_lateness_s": .01,
            "errors": [], "violations": [], "disconnects": [], "passed": True,
            "acceptance_failures": [], "quality_review_required": False}


def check_delivery_and_review():
    complete = completed_recording()
    before = deepcopy(complete)
    result = soak.assess_recording(complete)
    assert result["passed"] and complete == before
    assert result["translation_integrity"]["final_segment_count"] == result["translation_integrity"]["valid_complete_segment_count"] == 2

    cases = []
    # The original bug: another segment completed, so a blank final completion
    # escaped the old nonzero-count check and could produce a false PASS.
    for text in ("", " \n\t", None, 7):
        report = deepcopy(complete)
        report["events"][-1]["translation"]["text"] = text
        cases.append((f"empty or invalid text {text!r}", report, [2], True))
    for status in ("pending", "skipped", "error", "disabled", "unknown"):
        report = deepcopy(complete)
        report["events"][-1]["translation"] = {"status": status}
        cases.append((f"missing completion {status}", report, [2], False))
    report = deepcopy(complete)
    report["events"].pop()  # A final pending message with no following complete.
    cases.append(("last complete never arrived", report, [2], False))
    report = deepcopy(complete)
    report["events"][-1]["translation"] = {}
    cases.append(("translation status absent", report, [2], False))
    report = deepcopy(complete)
    report["events"][-1]["translation"]["is_mock"] = True
    cases.append(("mock complete", report, [2], True))
    report = deepcopy(complete)
    report["events"][-1]["segment_id"] = 3
    cases.append(("different segment cannot fill missing final", report, [2], False))
    report = deepcopy(complete)
    report["events"][-1]["source_final"] = False
    cases.append(("complete for mutable source", report, [2], True))
    for name, report, missing, invalid in cases:
        unchanged = deepcopy(report)
        checked = soak.assess_recording(report)
        assert not checked["passed"], name
        assert checked["translation_integrity"]["missing_translation_segment_ids"] == missing, name
        assert bool(checked["translation_integrity"]["invalid_completions"]) is invalid, name
        assert checked["acceptance_failures"] and report == unchanged

    report = deepcopy(complete)
    report["events"].insert(2, deepcopy(report["events"][1]))
    assert soak.translation_integrity(report["events"])["valid_complete_segment_count"] == 2
    report = deepcopy(complete)
    report["events"].append({"type": "error", "fatal": False, "code": "TRANSLATION_FAILED"})
    assert not soak.assess_recording(report)["passed"]  # Cannot hide an error by omitting errors[].
    report = deepcopy(complete)
    report["passed"] = False
    report["acceptance_failures"] = ["Previously recorded real failure"]
    assert "Previously recorded real failure" in soak.assess_recording(report)["acceptance_failures"]

    directory = ROOT / "output/release-acceptance/harness-unit-tests" / str(uuid4())
    directory.mkdir(parents=True)
    for name, recording, expected_exit in (("valid", complete, 0), ("blank", cases[0][1], 1)):
        path = directory / f"{name}.json"
        path.write_text(json.dumps(recording, ensure_ascii=False), encoding="utf-8")
        original = path.read_bytes()
        names_before = set(directory.iterdir())
        process = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/soak-acceptance.py"),
                                  "review", "--input", str(path)], capture_output=True, text=True,
                                 encoding="utf-8", timeout=10)
        assert process.returncode == expected_exit, process.stderr
        reviewed = json.loads(process.stdout)
        assert reviewed["passed"] is (expected_exit == 0)
        assert reviewed["input_sha256"] == hashlib.sha256(original).hexdigest()
        assert path.read_bytes() == original and set(directory.iterdir()) == names_before
        assert reviewed["validation_kind"].startswith("offline reassessment")
    print(f"PASS offline delivery: valid result and {len(cases)} missing/invalid completion cases; review CLI is read-only and preserves failures")


if __name__ == "__main__":
    soak.self_test()
    check_delivery_and_review()
    asyncio.run(check("conflict"))
    asyncio.run(check("fatal"))
