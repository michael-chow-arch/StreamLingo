import asyncio
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from streamlingo.adapters.demo import DemoRecognitionSession
from streamlingo.adapters.whisperlivekit import WhisperLiveKitSession
from streamlingo.app import create_app
from streamlingo.application.session import SubtitleSession
from streamlingo.domain.errors import ServiceFailure
from streamlingo.settings import Settings

ORIGIN = "chrome-extension://" + "a" * 32
SETTINGS = Settings(mode="demo", allowed_origins=(ORIGIN,), demo_interval_ms=200)


def start(session_id=None):
    return {"type": "start", "protocol_version": 1, "session_id": session_id or str(uuid4()),
            "source_language": "en", "target_language": "zh-CN",
            "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1}}


@pytest.fixture
def client():
    with TestClient(create_app(SETTINGS), base_url="http://127.0.0.1") as client:
        yield client


def connect(client, origin=ORIGIN):
    return client.websocket_connect("ws://127.0.0.1/ws/live", headers={"origin": origin})


def test_health_and_origin_boundary(client):
    assert client.get("/health").json() == {
        "protocol_version": 1, "mode": "demo", "status": "ready", "asr": "ready", "translation": "mock",
        "source_languages": ["en", "zh", "auto"], "target_languages": ["zh-CN", "en"],
    }
    allowed = client.get("/health", headers={"origin": ORIGIN})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert client.get("/health", headers={"origin": "https://www.youtube.com"}).status_code == 403
    assert client.get("/health", headers={"host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("origin", [None, "null", "https://www.youtube.com", "chrome-extension://" + "b" * 32])
def test_ws_rejects_unlisted_and_missing_origin(client, origin):
    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect("ws://127.0.0.1/ws/live", headers={} if origin is None else {"origin": origin}):
            pass
    assert denied.value.code == 1008


def test_audio_drives_mock_subtitle_and_stop(client):
    config = start()
    with connect(client) as ws:
        ws.send_json(config)
        assert ws.receive_json() == {"type": "ready", "protocol_version": 1,
                                     "session_id": config["session_id"], "mode": "demo", "translation": "mock",
                                     "source_language": "en", "target_language": "zh-CN"}
        ws.send_bytes(bytes(6400))
        message = ws.receive_json()
        assert message["type"] == "subtitle"
        assert message["session_id"] == config["session_id"]
        assert message["segment_id"] == message["revision"] == 1
        assert message["start_ms"] == 0 and message["end_ms"] == 200
        assert "DEMO" in message["source_text"]
        assert message["translation"]["status"] == "pending"
        translated = ws.receive_json()
        assert translated["segment_id"] == message["segment_id"]
        assert translated["revision"] == 2
        assert translated["translation"]["status"] == "complete"
        assert translated["translation"]["is_mock"] is True
        ws.send_json({"type": "stop", "session_id": config["session_id"]})
        assert ws.receive_json() == {"type": "stopped", "session_id": config["session_id"], "reason": "user"}
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    assert client.app.state.runtime.registry.active_id is None


def test_stop_before_audio_has_no_subtitle(client):
    config = start()
    with connect(client) as ws:
        ws.send_json(config)
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "stop", "session_id": config["session_id"]})
        assert ws.receive_json()["type"] == "stopped"


def test_demo_emits_nothing_without_enough_audio():
    async def check():
        session = DemoRecognitionSession(200)
        iterator = session.events()
        pending = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0.01)
        assert not pending.done()
        await session.push_audio(bytes(3200))
        await asyncio.sleep(0.01)
        assert not pending.done()
        await session.push_audio(bytes(3200))
        event = await asyncio.wait_for(pending, 1)
        assert event.end_ms == 200
        await session.close()
        await iterator.aclose()
    asyncio.run(check())


@pytest.mark.parametrize("payload,code", [
    ({"type": "start", "protocol_version": 2}, "UNSUPPORTED_PROTOCOL"),
    ({"type": "start", "protocol_version": True}, "UNSUPPORTED_PROTOCOL"),
    ({"type": "stop", "session_id": str(uuid4())}, "INVALID_MESSAGE"),
    ({**start(), "session_id": "bad-id"}, "INVALID_MESSAGE"),
    ({**start(), "source_language": "zh"}, "UNSUPPORTED_LANGUAGE"),
    ({**start(), "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": True}}, "INVALID_MESSAGE"),
    ({**start(), "extra": True}, "INVALID_MESSAGE"),
    ([], "INVALID_MESSAGE"),
])
def test_invalid_handshake(client, payload, code):
    with connect(client) as ws:
        ws.send_json(payload)
        error = ws.receive_json()
        assert error["type"] == "error" and error["code"] == code and error["fatal"]
    assert client.app.state.runtime.registry.active_id is None


@pytest.mark.parametrize("payload", [b"\0", b"", bytes(32002), "not-json", "x" * 4097],
                         ids=["odd-pcm", "empty-pcm", "large-pcm", "bad-json", "large-json"])
def test_invalid_running_input(client, payload):
    with connect(client) as ws:
        ws.send_json(start())
        assert ws.receive_json()["type"] == "ready"
        if isinstance(payload, bytes):
            ws.send_bytes(payload)
        else:
            ws.send_text(payload)
        assert ws.receive_json()["code"] == "INVALID_MESSAGE"
    assert client.app.state.runtime.registry.active_id is None


@pytest.mark.parametrize("command", [start(), {"type": "stop", "session_id": str(uuid4())}])
def test_duplicate_start_and_wrong_session(client, command):
    with connect(client) as ws:
        ws.send_json(start())
        assert ws.receive_json()["type"] == "ready"
        ws.send_json(command)
        assert ws.receive_json()["code"] == "INVALID_MESSAGE"


def test_reject_conflicting_session_without_disturbing_first(client):
    first = start()
    with connect(client) as ws:
        ws.send_json(first)
        assert ws.receive_json()["type"] == "ready"
        with connect(client) as other:
            other.send_json(start())
            assert other.receive_json()["code"] == "SESSION_CONFLICT"
        ws.send_bytes(bytes(6400))
        assert ws.receive_json()["type"] == "subtitle"
        assert ws.receive_json()["translation"]["status"] == "complete"
        ws.send_json({"type": "stop", "session_id": first["session_id"]})
        assert ws.receive_json()["type"] == "stopped"


def test_disconnect_closes_asr_and_releases_session(client):
    from streamlingo.adapters.demo import DemoRecognizer
    closed = []

    class TrackedRecognizer(DemoRecognizer):
        async def open_session(self, **kwargs):
            session = await super().open_session(**kwargs)
            original = session.close
            async def close():
                await original()
                closed.append(True)
            session.close = close
            return session

    client.app.state.runtime.recognizer = TrackedRecognizer(200)
    with connect(client) as ws:
        ws.send_json(start())
        assert ws.receive_json()["type"] == "ready"
        ws.close()
    # A health request round-trip lets disconnect cleanup run on the same loop.
    client.get("/health")
    assert closed == [True]
    assert client.app.state.runtime.registry.active_id is None


def test_audio_before_start_is_rejected(client):
    with connect(client) as ws:
        ws.send_bytes(bytes(6400))
        assert ws.receive_json()["code"] == "INVALID_MESSAGE"


def test_asr_not_ready_is_explicit(client):
    client.app.state.runtime.recognizer = None
    client.app.state.runtime.asr_status = "error"
    with connect(client) as ws:
        ws.send_json(start())
        assert ws.receive_json()["code"] == "ASR_NOT_READY"


def test_queue_byte_limit_is_fatal():
    session = SubtitleSession(str(uuid4()), DemoRecognitionSession(200), None, max_queue_bytes=6400)
    session.enqueue(bytes(6400))
    with pytest.raises(ServiceFailure) as failure:
        session.enqueue(bytes(2))
    assert failure.value.code == "AUDIO_BACKLOG"


def test_slow_asr_backlog_fails_and_cleans_up(client):
    closed = []
    class SlowSession:
        async def push_audio(self, pcm):
            await asyncio.Event().wait()
        async def events(self):
            await asyncio.Event().wait()
            yield
        async def close(self):
            closed.append(True)
    class SlowRecognizer:
        async def open_session(self, **kwargs):
            return SlowSession()
    client.app.state.runtime.recognizer = SlowRecognizer()
    with connect(client) as ws:
        ws.send_json(start())
        assert ws.receive_json()["type"] == "ready"
        for _ in range(7):
            ws.send_bytes(bytes(32000))
        assert ws.receive_json()["code"] == "AUDIO_BACKLOG"
    assert closed == [True]


def test_whisper_mapping_uses_upstream_final_boundaries():
    first_token = SimpleNamespace(text="Hello", start=0.1, end=0.5, has_punctuation=lambda: False,
                                  is_silence=lambda: False)
    tokens = [first_token]
    line = SimpleNamespace(speaker=-1, tokens=tokens)
    alignment = SimpleNamespace(all_tokens=tokens, compute_punctuations_segments=lambda: [line])
    session = WhisperLiveKitSession(SimpleNamespace(tokens_alignment=alignment, total_pcm_samples=16000,
                                                     sample_rate=16000, current_silence=None,
                                                     state=SimpleNamespace(end_transcription_processed=1),
                                                     transcription_queue=asyncio.Queue()))
    response = SimpleNamespace(status="active_transcription", error="", lines=[line],
                               remaining_time_transcription_processing=0, buffer_transcription="")
    first = session.map_snapshot(response)
    assert len(first) == 1 and not first[0].is_final
    tokens.append(SimpleNamespace(text=" world.", start=0.5, end=1.0, has_punctuation=lambda: True,
                                  is_silence=lambda: False))
    final = session.map_snapshot(response)
    assert final[0].result_id == first[0].result_id
    assert final[0].is_final and final[0].end_ms == 1000
    assert session.map_snapshot(response) == []
    session.note_stream_event(SimpleNamespace(kind="speech_started", timestamp=0))
    session.note_stream_event(SimpleNamespace(kind="audio_advanced", timestamp=12))
    with pytest.raises(ServiceFailure) as backlog:
        session.map_snapshot(response)
    assert backlog.value.code == "AUDIO_BACKLOG"


def test_settings_enforce_local_and_explicit_origins():
    with pytest.raises(ValueError):
        Settings(host="0.0.0.0")
    with pytest.raises(ValueError):
        Settings(allowed_origins=("*",))
    with pytest.raises(ValueError):
        Settings(allowed_origins=("https://www.youtube.com",))


def test_missing_upstream_is_health_error(monkeypatch):
    from streamlingo.adapters.whisperlivekit import WhisperLiveKitRecognizer
    def fail(settings):
        raise ModuleNotFoundError("Test: optional ASR not installed")
    monkeypatch.setattr(WhisperLiveKitRecognizer, "load", fail)
    with TestClient(create_app(replace(SETTINGS, mode="whisperlivekit")), base_url="http://127.0.0.1") as client:
        # Wait for the injected startup worker through the test portal, not a
        # guessed wall-clock sleep.
        async def wait_for_loading():
            for _ in range(100):
                if client.app.state.runtime.asr_status != "loading":
                    return
                await asyncio.sleep(0.01)
        client.portal.call(wait_for_loading)
        assert client.get("/health").json() == {
            "protocol_version": 1, "mode": "whisperlivekit", "status": "error",
            "asr": "error", "translation": "disabled",
        }
