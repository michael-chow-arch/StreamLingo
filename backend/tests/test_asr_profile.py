from dataclasses import replace
import sys
from types import ModuleType, SimpleNamespace

import pytest

from streamlingo.adapters.whisperlivekit import RealtimeWhisperModel, WhisperLiveKitRecognizer
from streamlingo.settings import Settings


def test_decoding_proxy_forwards_model_and_options_without_mutating_original():
    calls = []
    result = (iter(["segment"]), object())
    model = SimpleNamespace(device="cuda", transcribe=lambda audio, **kwargs: calls.append((audio, kwargs)) or result)
    original_method = model.transcribe
    wrapped = RealtimeWhisperModel(model, beam_size=1)
    audio = object()
    assert wrapped.transcribe(audio, beam_size=5, language="en", initial_prompt="context",
                              word_timestamps=True, condition_on_previous_text=True) is result
    assert wrapped.wrapped_model is model and wrapped.device == "cuda"
    assert model.transcribe is original_method
    assert calls == [(audio, {"beam_size": 1, "best_of": 1, "temperature": 0.0,
                             "language": "en", "initial_prompt": None,
                             "word_timestamps": True, "condition_on_previous_text": False})]
    quality = RealtimeWhisperModel(model, beam_size=5)
    quality.transcribe(audio, beam_size=5)
    assert calls[-1][1]["beam_size"] == 5


def test_load_configures_official_coalescing_and_trimming_without_loading_models(monkeypatch, caplog):
    import streamlingo.adapters.whisperlivekit as adapter

    model = SimpleNamespace(transcribe=lambda *args, **kwargs: None)
    configurations = []
    engine = SimpleNamespace(asr=SimpleNamespace(model=model))
    upstream = ModuleType("whisperlivekit")
    upstream.TranscriptionEngine = lambda config: configurations.append(config) or engine
    config_module = ModuleType("whisperlivekit.config")
    config_module.WhisperLiveKitConfig = SimpleNamespace
    monkeypatch.setitem(sys.modules, "whisperlivekit", upstream)
    monkeypatch.setitem(sys.modules, "whisperlivekit.config", config_module)
    monkeypatch.setattr(adapter, "version", lambda name: adapter.UPSTREAM_VERSION)
    with caplog.at_level("INFO"):
        recognizer = WhisperLiveKitRecognizer.load(Settings())
    assert recognizer.engine is engine
    config = configurations[0]
    assert config.asr_coalesce_min_s == 0.8
    assert config.buffer_trimming_sec == 8 and config.buffer_trimming == "segment"
    assert config.lan == "en" and config.backend_policy == "localagreement"
    assert config.model_size == "base"
    assert engine.asr.model.wrapped_model is model and engine.asr.model.beam_size == 1
    assert "condition_on_previous_text=false initial_prompt=none" in caplog.text


def test_every_call_discards_reinjected_history_without_mutating_caller_options():
    calls = []
    model = SimpleNamespace(transcribe=lambda audio, **kwargs: calls.append((audio, kwargs)))
    original_method = model.transcribe
    wrapper = RealtimeWhisperModel(model, beam_size=1)
    for prompt in ("the same mistaken phrase " * 8, "ordinary vocabulary context", [1, 2, 3, 1, 2, 3]):
        options = {"initial_prompt": prompt, "condition_on_previous_text": True,
                   "language": "en", "word_timestamps": True}
        before = options.copy()
        audio = object()
        wrapper.transcribe(audio, **options)
        assert options == before
        received_audio, received_options = calls[-1]
        assert received_audio is audio
        assert received_options["initial_prompt"] is None
        assert received_options["condition_on_previous_text"] is False
        assert received_options["language"] == "en" and received_options["word_timestamps"] is True
    assert len(calls) == 3
    assert wrapper.wrapped_model is model and model.transcribe is original_method


def test_real_spoken_repetitions_and_model_output_are_not_filtered_or_rewritten():
    words = [SimpleNamespace(word="very", start=0.0, end=0.4),
             SimpleNamespace(word=" very", start=0.4, end=0.8),
             SimpleNamespace(word=" good", start=0.8, end=1.2)]
    segment = SimpleNamespace(text="very very good", words=words)
    segments = iter([segment])
    info = object()
    result = (segments, info)
    model = SimpleNamespace(transcribe=lambda audio, **kwargs: result)
    wrapper = RealtimeWhisperModel(model, beam_size=1)
    returned = wrapper.transcribe(object(), initial_prompt="very very good")
    assert returned is result and returned[1] is info
    assert next(returned[0]) is segment
    assert segment.text == "very very good"
    assert segment.words is words and [word.word for word in words] == ["very", " very", " good"]


@pytest.mark.parametrize("field,value", [
    ("asr_beam_size", 0), ("asr_beam_size", 6), ("asr_beam_size", 1.5),
    ("asr_beam_size", True), ("asr_coalesce_seconds", 0), ("asr_coalesce_seconds", 3),
    ("asr_coalesce_seconds", float("nan")), ("asr_buffer_seconds", 3),
    ("asr_buffer_seconds", 31), ("asr_buffer_seconds", float("inf")),
])
def test_realtime_settings_reject_unbounded_or_invalid_values(field, value):
    with pytest.raises(ValueError):
        replace(Settings(), **{field: value})


def test_cli_forwards_realtime_options(monkeypatch):
    from streamlingo import app, cli

    invocations = []
    monkeypatch.setattr(sys, "argv", ["streamlingo-server", "--asr-beam-size", "5",
                                      "--asr-coalesce-seconds", "1", "--asr-buffer-seconds", "10"])
    monkeypatch.setattr(app, "create_app", lambda settings: settings)
    monkeypatch.setattr(cli, "require_windows_asr_runtime", lambda: None)
    monkeypatch.setattr(cli.uvicorn, "run", lambda settings, **kwargs: invocations.append(settings))
    cli.main()
    assert invocations[0].asr_beam_size == 5
    assert invocations[0].asr_coalesce_seconds == 1
    assert invocations[0].asr_buffer_seconds == 10
    assert invocations[0].model == "base"
