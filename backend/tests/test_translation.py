import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from streamlingo.adapters.demo import DemoRecognizer
from streamlingo.adapters.ollama import OllamaTranslator
from streamlingo.app import create_app
from streamlingo.application.session import SubtitleSession
from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import TranscriptEvent, TranslationRequest, TranslationResult
from streamlingo.settings import Settings


class ControlledRecognition:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def events(self):
        while True:
            yield await self.queue.get()

    def final(self, number):
        self.queue.put_nowait(TranscriptEvent(str(number), f"English sentence {number}.",
                                              (number - 1) * 1000, number * 1000, True))


class SlowTranslator:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.calls = []

    async def translate(self, request):
        self.calls.append(request)
        self.started.set()
        try:
            await self.release.wait()
            return TranslationResult("测试中文", is_mock=False)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


async def receive(stream):
    return await asyncio.wait_for(anext(stream), 1)


def make_session(recognizer, translator, **kwargs):
    return SubtitleSession(str(uuid4()), recognizer, translator, 160_000, **kwargs)


def test_english_continues_while_translation_is_pending():
    async def check():
        asr, translator = ControlledRecognition(), SlowTranslator()
        stream = make_session(asr, translator).subtitles()
        try:
            asr.final(1)
            first = await receive(stream)
            assert first["translation"]["status"] == "pending"
            await translator.started.wait()
            asr.final(2)
            second = await receive(stream)
            assert second["segment_id"] == 2 and second["source_text"] == "English sentence 2."
            translator.release.set()
            completed_first = await receive(stream)
            completed_second = await receive(stream)
            assert completed_first["segment_id"] == 1 and completed_first["revision"] == 2
            assert completed_second["segment_id"] == 2 and completed_second["revision"] == 2
            assert completed_first["translation"] == {"status": "complete", "text": "测试中文", "is_mock": False}
            assert translator.calls[1].context == ("English sentence 1.",)
        finally:
            await stream.aclose()
    asyncio.run(check())


def test_translation_queue_discards_oldest_waiting_segment():
    async def check():
        asr, translator = ControlledRecognition(), SlowTranslator()
        stream = make_session(asr, translator, translation_queue_size=1).subtitles()
        try:
            asr.final(1)
            await receive(stream)
            await translator.started.wait()
            asr.final(2)
            await receive(stream)
            asr.final(3)
            third = await receive(stream)
            assert third["segment_id"] == 3
            skipped = await receive(stream)
            warning = await receive(stream)
            assert skipped["segment_id"] == 2 and skipped["revision"] == 2
            assert skipped["translation"]["status"] == "skipped"
            assert warning["code"] == "TRANSLATION_BACKLOG" and warning["fatal"] is False
            translator.release.set()
            assert (await receive(stream))["segment_id"] == 1
            assert (await receive(stream))["segment_id"] == 3
            assert len(translator.calls) == 2
        finally:
            await stream.aclose()
    asyncio.run(check())


def test_successful_late_translation_is_kept_but_unstarted_expired_job_is_skipped(monkeypatch):
    import streamlingo.application.session as session_module
    clock = [0.0]
    monkeypatch.setattr(session_module, "monotonic", lambda: clock[0])
    async def check():
        asr, translator = ControlledRecognition(), SlowTranslator()
        stream = make_session(asr, translator, translation_max_age=1).subtitles()
        try:
            asr.final(1)
            original = await receive(stream)
            await translator.started.wait()
            asr.final(2)
            await receive(stream)
            clock[0] = 2.0
            translator.release.set()
            completed = await receive(stream)
            assert completed == {**original, "revision": 2, "translation": {
                "status": "complete", "text": "测试中文", "is_mock": False,
            }}
            expired = await receive(stream)
            assert expired["segment_id"] == 2 and expired["translation"]["status"] == "skipped"
            assert (await receive(stream))["code"] == "TRANSLATION_BACKLOG"
            assert len(translator.calls) == 1
        finally:
            await stream.aclose()
    asyncio.run(check())


def test_successful_translation_retains_final_cue_after_metadata_eviction():
    async def check():
        asr, translator = ControlledRecognition(), SlowTranslator()
        session = make_session(asr, translator)
        stream = session.subtitles()
        try:
            asr.queue.put_nowait(TranscriptEvent("1", "English", 0, 400, False))
            await receive(stream)
            asr.final(1)
            original = await receive(stream)
            assert original["revision"] == 2
            await translator.started.wait()

            # Recognition keeps running while the translator is blocked. These
            # partials do not create translation jobs, but evict its old cue.
            for number in range(2, 259):
                asr.queue.put_nowait(TranscriptEvent(str(number), f"Partial {number}",
                                                     number * 1000, number * 1000 + 500, False))
                assert (await receive(stream))["translation"]["status"] == "disabled"
            assert "1" not in session._segments
            assert len(session._segments) == 256

            translator.release.set()
            completed = await receive(stream)
            assert completed == {**original, "revision": 3, "translation": {
                "status": "complete", "text": "测试中文", "is_mock": False,
            }}
            assert "1" not in session._segments
            assert len(session._segments) == 256

            # The next job still completes, without an outstanding-job archive.
            asr.final(259)
            pending = await receive(stream)
            following = await receive(stream)
            assert following["segment_id"] == pending["segment_id"]
            assert following["translation"]["status"] == "complete"
            assert len(translator.calls) == 2
            assert session._translation_queue.empty()
            assert len(session._segments) == 256
        finally:
            await stream.aclose()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("streamlingo-")]
    asyncio.run(check())


def test_total_age_budget_cancels_an_active_request():
    async def check():
        asr, translator = ControlledRecognition(), SlowTranslator()
        stream = make_session(asr, translator, translation_max_age=0.02, translation_timeout=1).subtitles()
        try:
            asr.final(1)
            await receive(stream)
            expired = await receive(stream)
            assert expired["translation"]["status"] == "skipped"
            assert (await receive(stream))["code"] == "TRANSLATION_BACKLOG"
            assert translator.cancelled.is_set()
        finally:
            await stream.aclose()
    asyncio.run(check())


@pytest.mark.parametrize("failure", ["timeout", "failure"])
def test_translation_failure_keeps_english_and_continues_next_segment(failure):
    class FailsOnce:
        calls = 0
        async def translate(self, request):
            self.calls += 1
            if self.calls == 1:
                if failure == "timeout":
                    await asyncio.Event().wait()
                raise RuntimeError("provider unavailable")
            return TranslationResult("下一句正常")
    async def check():
        asr = ControlledRecognition()
        stream = make_session(asr, FailsOnce(), translation_timeout=0.02).subtitles()
        try:
            asr.final(1)
            original = await receive(stream)
            error_subtitle = await receive(stream)
            warning = await receive(stream)
            assert error_subtitle["source_text"] == original["source_text"]
            assert error_subtitle["translation"]["status"] == "error"
            assert warning["fatal"] is False
            assert warning["code"] == ("TRANSLATION_TIMEOUT" if failure == "timeout" else "TRANSLATION_FAILED")
            asr.final(2)
            await receive(stream)
            assert (await receive(stream))["translation"]["text"] == "下一句正常"
        finally:
            await stream.aclose()
    asyncio.run(check())


def test_generator_close_cancels_inflight_translation_and_discards_queue():
    async def check():
        asr, translator = ControlledRecognition(), SlowTranslator()
        stream = make_session(asr, translator).subtitles()
        asr.final(1)
        await receive(stream)
        await translator.started.wait()
        asr.final(2)
        await receive(stream)
        await stream.aclose()
        assert translator.cancelled.is_set()
        assert len(translator.calls) == 1
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("streamlingo-")]
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    asyncio.run(check())


def test_ollama_request_disables_thinking_and_ignores_thinking_response():
    async def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert body["model"] == "qwen3.5:9b" and body["stream"] is False and body["think"] is False
        assert body["options"]["num_predict"] > 0
        source = json.loads(body["messages"][1]["content"])
        assert source["source_text"] == "Hello." and source["context"] == ["previous sentence"]
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
                                        "message": {"content": "  你好。  ", "thinking": "private model reasoning"}})
    async def check():
        translator = OllamaTranslator(base_url="http://127.0.0.1:11434", model="qwen3.5:9b",
                                      transport=httpx.MockTransport(handler))
        try:
            result = await translator.translate(TranslationRequest("Hello.", context=("previous sentence",)))
            assert result == TranslationResult("你好。", is_mock=False)
        finally:
            await translator.aclose()
        assert translator.client.is_closed
    asyncio.run(check())


@pytest.mark.parametrize("payload", [
    {"done": False, "message": {"content": "unfinished"}},
    {"done": True, "message": {"content": ""}},
    {"done": True, "done_reason": "length", "message": {"content": "truncated"}},
    {"done": True, "message": {"content": "x" * 8001}},
    ["unexpected"],
], ids=["incomplete", "empty", "truncated", "oversized", "bad-shape"])
def test_invalid_ollama_output_is_not_displayed(payload):
    async def check():
        translator = OllamaTranslator(base_url="http://localhost:11434", model="qwen3.5:9b",
                                      transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
        try:
            with pytest.raises(ServiceFailure) as failure:
                await translator.translate(TranslationRequest("Hello"))
            assert failure.value.code == "TRANSLATION_FAILED"
        finally:
            await translator.aclose()
    asyncio.run(check())


@pytest.mark.parametrize("failure_kind", ["http", "timeout"])
def test_http_failures_have_safe_codes(failure_kind):
    async def handler(request):
        if failure_kind == "timeout":
            raise httpx.ReadTimeout("sensitive upstream details", request=request)
        return httpx.Response(500, text="sensitive upstream details")
    async def check():
        translator = OllamaTranslator(base_url="http://localhost:11434", model="qwen3.5:9b",
                                      transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ServiceFailure) as failure:
                await translator.translate(TranslationRequest("Hello"))
            assert failure.value.code == ("TRANSLATION_TIMEOUT" if failure_kind == "timeout" else "TRANSLATION_FAILED")
            assert "sensitive" not in failure.value.message
        finally:
            await translator.aclose()
    asyncio.run(check())


def test_configured_health_and_client_lifecycle(monkeypatch):
    from streamlingo.adapters.whisperlivekit import WhisperLiveKitRecognizer
    monkeypatch.setattr(WhisperLiveKitRecognizer, "load", lambda _: DemoRecognizer())
    app = create_app(Settings(ollama_model="qwen3.5:9b"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        health = client.get("/health").json()
        assert health["translation"] == "configured"
        assert app.state.runtime.translator is app.state.runtime.ollama
        assert not app.state.runtime.ollama.client.is_closed
    assert app.state.runtime.ollama.client.is_closed


@pytest.mark.parametrize("finish", ["stop", "disconnect"])
def test_websocket_finish_cancels_inflight_ollama(finish):
    origin = "chrome-extension://" + "a" * 32
    app = create_app(Settings(mode="demo", allowed_origins=(origin,), demo_interval_ms=200))
    translator = SlowTranslator()
    with TestClient(app, base_url="http://127.0.0.1") as client:
        app.state.runtime.translator = translator
        session_id = str(uuid4())
        with client.websocket_connect("ws://127.0.0.1/ws/live", headers={"origin": origin}) as ws:
            ws.send_json({"type": "start", "protocol_version": 1, "session_id": session_id,
                          "source_language": "en", "target_language": "zh-CN",
                          "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1}})
            assert ws.receive_json()["type"] == "ready"
            ws.send_bytes(bytes(6400))
            assert ws.receive_json()["translation"]["status"] == "pending"
            client.portal.call(translator.started.wait)
            if finish == "stop":
                ws.send_json({"type": "stop", "session_id": session_id})
                assert ws.receive_json()["type"] == "stopped"
            else:
                ws.close()
        assert translator.cancelled.is_set()
        assert app.state.runtime.registry.active_id is None


def test_stop_during_websocket_send_closes_generator_before_ack(monkeypatch):
    from fastapi import WebSocket
    origin = "chrome-extension://" + "a" * 32
    app = create_app(Settings(mode="demo", allowed_origins=(origin,), demo_interval_ms=200))
    translator = SlowTranslator()
    send_blocked = asyncio.Event()
    original_send = WebSocket.send_json

    async def blocked_send(websocket, data, mode="text"):
        if data["type"] == "subtitle":
            send_blocked.set()
            await asyncio.Event().wait()
        if data["type"] == "stopped":
            assert translator.cancelled.is_set(), "stop acknowledged before translation was cancelled"
        await original_send(websocket, data, mode)

    monkeypatch.setattr(WebSocket, "send_json", blocked_send)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        app.state.runtime.translator = translator
        session_id = str(uuid4())
        with client.websocket_connect("ws://127.0.0.1/ws/live", headers={"origin": origin}) as ws:
            ws.send_json({"type": "start", "protocol_version": 1, "session_id": session_id,
                          "source_language": "en", "target_language": "zh-CN",
                          "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1}})
            assert ws.receive_json()["type"] == "ready"
            ws.send_bytes(bytes(6400))
            client.portal.call(send_blocked.wait)
            client.portal.call(translator.started.wait)
            ws.send_json({"type": "stop", "session_id": session_id})
            assert ws.receive_json()["type"] == "stopped"
        assert app.state.runtime.registry.active_id is None


@pytest.mark.parametrize("kwargs", [
    {"ollama_url": "http://user:password@localhost:11434"}, {"ollama_url": "ftp://localhost"},
    {"ollama_url": "http://localhost/api/chat"}, {"ollama_model": " "},
    {"translation_queue_size": 0}, {"translation_queue_size": 17},
    {"translation_timeout": float("nan")},
])
def test_invalid_translation_configuration(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)
