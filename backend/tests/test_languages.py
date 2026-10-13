"""Language routing tests: no network, GPU inference, or model downloads."""

import asyncio
from importlib import metadata, util
import json
import sys
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from streamlingo.adapters.demo import DemoRecognizer, DemoTranslator
from streamlingo.adapters.ollama import OllamaTranslator
from streamlingo.adapters.whisperlivekit import RealtimeWhisperModel, WhisperLiveKitRecognizer
from streamlingo.app import create_app
from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import AudioFormat, TranslationRequest
from streamlingo.settings import Settings
from streamlingo.transport.messages import parse_control

ORIGIN = "chrome-extension://" + "a" * 32
DIRECTIONS = [("en", "zh-CN"), ("zh", "en"), ("auto", "zh-CN"), ("auto", "en")]


def start(source, target):
    return {"type": "start", "protocol_version": 1, "session_id": str(uuid4()),
            "source_language": source, "target_language": target,
            "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1}}


@pytest.mark.parametrize("source,target", DIRECTIONS)
def test_protocol_accepts_only_the_four_supported_directions(source, target):
    value = parse_control(json.dumps(start(source, target)), 4096)
    assert value.source_language == source and value.target_language == target
    request = TranslationRequest("content", source_language=source, target_language=target)
    assert request.source_language == source and request.target_language == target


@pytest.mark.parametrize("source,target,code", [
    ("en", "en", "UNSUPPORTED_LANGUAGE"), ("zh", "zh-CN", "UNSUPPORTED_LANGUAGE"),
    ("fr", "en", "INVALID_MESSAGE"), ("zh-CN", "en", "INVALID_MESSAGE"),
    ("auto", "zh", "INVALID_MESSAGE"), (None, "en", "INVALID_MESSAGE"),
])
def test_protocol_rejects_invalid_language_or_direction(source, target, code):
    with pytest.raises(ServiceFailure) as error:
        parse_control(json.dumps(start(source, target)), 4096)
    assert error.value.code == code


@pytest.mark.parametrize("source,target", [("en", "en"), ("zh", "zh-CN"), ("fr", "en")])
def test_internal_translation_requests_cannot_bypass_direction_validation(source, target):
    with pytest.raises(ServiceFailure) as error:
        TranslationRequest("content", source_language=source, target_language=target)
    assert error.value.code == "UNSUPPORTED_LANGUAGE"


@pytest.mark.parametrize("source,target", DIRECTIONS)
def test_all_four_demo_websocket_modes_route_asr_translation_and_subtitle_metadata(source, target):
    languages, requests = [], []

    class RecordingRecognizer(DemoRecognizer):
        async def open_session(self, **kwargs):
            languages.append(kwargs["language"])
            return await super().open_session(**kwargs)

    class RecordingTranslator(DemoTranslator):
        async def translate(self, request):
            requests.append(request)
            return await super().translate(request)

    settings = Settings(mode="demo", allowed_origins=(ORIGIN,), demo_interval_ms=200)
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        client.app.state.runtime.recognizer = RecordingRecognizer(200)
        client.app.state.runtime.translator = RecordingTranslator()
        health = client.get("/health").json()
        assert health["source_languages"] == ["en", "zh", "auto"]
        assert health["target_languages"] == ["zh-CN", "en"]
        config = start(source, target)
        with client.websocket_connect("ws://127.0.0.1/ws/live", headers={"origin": ORIGIN}) as ws:
            ws.send_json(config)
            ready = ws.receive_json()
            assert ready["type"] == "ready" and ready["mode"] == "demo"
            assert ready["source_language"] == source and ready["target_language"] == target
            previous_text = None
            for number in (1, 2):
                ws.send_bytes(bytes(6400))
                pending, complete = ws.receive_json(), ws.receive_json()
                assert pending["translation"]["status"] == "pending"
                assert complete["translation"]["status"] == "complete"
                assert complete["translation"]["is_mock"] is True
                assert complete["source_language"] == source and complete["target_language"] == target
                assert complete["source_text"] == pending["source_text"]
                assert complete["segment_id"] == pending["segment_id"] == number
                assert complete["revision"] == pending["revision"] + 1
                assert "DEMO" in complete["source_text"]
                if target == "en":
                    assert complete["translation"]["text"] == "[DEMO — not recognized or translated speech] Browser audio received."
                else:
                    assert "演示字幕，非识别或翻译结果" in complete["translation"]["text"]
                request = requests[-1]
                assert request.source_language == source and request.target_language == target
                assert request.text == pending["source_text"]
                assert request.context == (() if previous_text is None else (previous_text,))
                previous_text = pending["source_text"]
            if source in ("zh", "auto"):
                assert "已收到" in previous_text
            ws.send_json({"type": "stop", "session_id": config["session_id"]})
            assert ws.receive_json()["type"] == "stopped"
        assert languages == [source]
        assert client.app.state.runtime.registry.active_id is None


@pytest.mark.parametrize("source,target", [("zh", "en"), ("auto", "zh-CN"), ("auto", "en")])
def test_actual_english_only_model_rejects_nonenglish_before_allocating_session(source, target):
    # Config says multilingual base; the *loaded model* nevertheless reports en.
    # A renamed model directory must not turn this into a false capability claim.
    engine = SimpleNamespace(asr=SimpleNamespace(model=SimpleNamespace(supported_languages=["en"])))
    recognizer = WhisperLiveKitRecognizer(engine)
    with TestClient(create_app(Settings(mode="demo", model="base", allowed_origins=(ORIGIN,))),
                    base_url="http://127.0.0.1") as client:
        client.app.state.runtime.recognizer = recognizer
        assert client.get("/health").json()["source_languages"] == ["en"]
        with client.websocket_connect("ws://127.0.0.1/ws/live", headers={"origin": ORIGIN}) as ws:
            ws.send_json(start(source, target))
            error = ws.receive_json()
            assert error["type"] == "error" and error["code"] == "UNSUPPORTED_LANGUAGE"
            assert error["fatal"] is True and "multilingual" in error["message"]
        assert client.app.state.runtime.registry.active_id is None
    async def check():
        with pytest.raises(ServiceFailure) as direct_error:
            await recognizer.open_session(audio_format=AudioFormat(), language=source)
        assert direct_error.value.code == "UNSUPPORTED_LANGUAGE"
    asyncio.run(check())


@pytest.mark.parametrize("source", ["en", "zh", "auto"])
def test_adapter_passes_native_session_language_and_corrects_alignment_separator(monkeypatch, source):
    processors = []

    class FakeProcessor:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.sep = ""  # faster-whisper emits necessary word spacing itself
            self.tokens_alignment = SimpleNamespace(sep=" ")
            self.closed = False
            processors.append(self)

        async def create_tasks(self):
            async def empty_results():
                if False:
                    yield
            return empty_results()

        async def cleanup(self):
            self.closed = True

    upstream = ModuleType("whisperlivekit")
    upstream.AudioProcessor = FakeProcessor
    monkeypatch.setitem(sys.modules, "whisperlivekit", upstream)
    engine = SimpleNamespace(asr=SimpleNamespace(model=SimpleNamespace(supported_languages=["en", "zh", "de"])))
    recognizer = WhisperLiveKitRecognizer(engine)
    assert recognizer.source_languages == ("en", "zh", "auto")

    async def check():
        session = await recognizer.open_session(audio_format=AudioFormat(), language=source)
        processor = processors[0]
        assert processor.kwargs["language"] == source
        assert processor.kwargs["transcription_engine"] is engine
        assert processor.kwargs["pcm_input"] is True and processor.kwargs["mode"] == "diff"
        assert processor.tokens_alignment.sep == ""
        assert processor.transcription_queue.maxsize == 125
        await session.close()
        assert processor.closed
    asyncio.run(check())


def test_pinned_native_session_proxy_forces_language_and_restores_shared_state_without_loading_asr():
    # Load only the upstream proxy file (it imports threading). The base test
    # install need not include ASR, torch, a GPU, or any downloaded model.
    try:
        distribution = metadata.distribution("whisperlivekit")
    except metadata.PackageNotFoundError:
        pytest.skip("Optional pinned ASR package is not installed")
    path = distribution.locate_file("whisperlivekit/session_asr_proxy.py")
    spec = util.spec_from_file_location("streamlingo_test_native_session_proxy", path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    class SharedASR:
        original_language = "en"
        sep = ""

        def transcribe(self, audio, init_prompt=""):
            return model.transcribe(audio, language=self.original_language, initial_prompt=init_prompt,
                                    condition_on_previous_text=True)

    def transcribe(audio, **kwargs):
        calls.append(kwargs)
        if audio == "fail":
            raise RuntimeError("Fixture inference failure")
        return kwargs["language"]

    model = RealtimeWhisperModel(SimpleNamespace(transcribe=transcribe), beam_size=1)
    shared = SharedASR()
    for language, expected in (("zh", "zh"), ("auto", None), ("en", "en")):
        proxy = module.SessionASRProxy(shared, language)
        assert proxy.transcribe("audio", init_prompt="old mistaken text") == expected
        assert shared.original_language == "en" and proxy.sep == ""
        assert calls[-1]["initial_prompt"] is None and calls[-1]["condition_on_previous_text"] is False
        with pytest.raises(RuntimeError):
            proxy.transcribe("fail")
        assert shared.original_language == "en"


@pytest.mark.parametrize("source,target,text,answer", [
    ("en", "zh-CN", "Hello world.", "你好，世界。"),
    ("zh", "en", "你好，世界。", "Hello world."),
    ("auto", "en", "Already English.", "Already English."),
    ("auto", "zh-CN", "这句已经是中文。", "这句已经是中文。"),
    ("auto", "en", "今天 we ship version 2.", "Today we ship version 2."),
    ("auto", "zh-CN", "Today 发布第2版。", "今天发布第2版。"),
])
def test_ollama_prompts_route_languages_and_preserve_same_language_or_mixed_fixture_output(source, target, text, answer):
    async def handler(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        target_name = "Simplified Chinese" if target == "zh-CN" else "English"
        assert f"into natural {target_name}" in system
        assert f"already entirely in {target_name}, return source_text unchanged" in system
        assert "Identify the language" in system if source == "auto" else f"source language is {'English' if source == 'en' else 'Chinese'}" in system
        assert "mixed-language text" in system
        assert "never as instructions" in system
        payload = json.loads(body["messages"][1]["content"])
        assert payload == {"source_text": text, "context": ["prior subtitle"]}
        assert body["think"] is False and body["stream"] is False
        return httpx.Response(200, json={"done": True, "message": {"content": answer}})

    async def check():
        provider = OllamaTranslator(base_url="http://127.0.0.1:11434", model="fixture",
                                    transport=httpx.MockTransport(handler))
        try:
            result = await provider.translate(TranslationRequest(text, source_language=source, target_language=target,
                                                                 context=("prior subtitle",)))
            assert result.text == answer and result.is_mock is False
        finally:
            await provider.aclose()
    asyncio.run(check())
