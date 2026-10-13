import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest

from streamlingo.adapters.whisperlivekit import WhisperLiveKitSession
from streamlingo.application.session import SubtitleSession
from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import TranslationResult


@dataclass
class Token:
    text: str
    start: float
    end: float

    def has_punctuation(self):
        return any(char in ".!?。！？" for char in self.text)

    def is_silence(self):
        return False


class AlignmentFixture:
    def __init__(self):
        self.all_tokens = []
        self.groups = []

    def compute_punctuations_segments(self):
        # The upstream owns grouping. These fixtures exercise consuming its
        # already-grouped token references without implementing another splitter.
        return self.groups

    def speech(self, *tokens):
        self.all_tokens.extend(tokens)
        group = SimpleNamespace(speaker=-1, tokens=list(tokens))
        self.groups.append(group)
        return group


def fixture(**session_kwargs):
    alignment = AlignmentFixture()
    processor = SimpleNamespace(tokens_alignment=alignment, total_pcm_samples=0,
                                 sample_rate=16000, current_silence=None,
                                 state=SimpleNamespace(end_transcription_processed=0),
                                 transcription_queue=asyncio.Queue())
    response = SimpleNamespace(status="active_transcription", error="", remaining_time_transcription_processing=0,
                               buffer_transcription="")
    return alignment, processor, response, WhisperLiveKitSession(processor, **session_kwargs)


def test_punctuation_finalizes_without_waiting_for_silence():
    alignment, _, response, session = fixture()
    group = alignment.speech(Token("Hello", 0, 0.4))
    partial = session.map_snapshot(response)
    assert len(partial) == 1 and not partial[0].is_final
    committed = Token(" world.", 0.4, 1.0)
    alignment.all_tokens.append(committed)
    group.tokens.append(committed)
    final = session.map_snapshot(response)
    assert len(final) == 1 and final[0].is_final
    assert final[0].text == "Hello world." and final[0].result_id == partial[0].result_id
    assert session.map_snapshot(response) == []


@pytest.mark.parametrize("words,expected", [
    (["今天", "测试", "中文", "字幕。"], "今天测试中文字幕。"),
    (["今天", " we", " test", "中文。"], "今天 we test中文。"),
    (["Hello", " world", "."], "Hello world."),
])
def test_committed_multilingual_tokens_preserve_native_spacing(words, expected):
    alignment, _, response, session = fixture()
    alignment.speech(*(Token(word, index * 0.2, (index + 1) * 0.2) for index, word in enumerate(words)))
    events = session.map_snapshot(response)
    assert len(events) == 1 and events[0].is_final
    assert events[0].text == expected
    assert session.map_snapshot(response) == []


def test_tail_silence_finalizes_without_resuming_speech():
    alignment, processor, response, session = fixture()
    alignment.speech(Token("no punctuation", 0, 1.0))
    partial = session.map_snapshot(response)[0]
    processor.current_silence = SimpleNamespace(start=1.2)
    processor.total_pcm_samples = int(2.3 * 16000)
    session.note_stream_event(SimpleNamespace(kind="silence_transcription_ready", timestamp=1.2))
    final = session.map_snapshot(response)[0]
    assert final.is_final and final.result_id == partial.result_id
    assert final.start_ms == 0 and final.end_ms == 1000
    assert session.map_snapshot(response) == []


def test_long_pause_is_not_inference_backlog():
    _, processor, response, session = fixture()
    processor.current_silence = SimpleNamespace(start=0)
    processor.total_pcm_samples = 30 * 16000
    response.remaining_time_transcription_processing = 30
    # WLK's initial silence is implicit: it emits only audio_advanced until
    # the first speech_started, without a preceding silence_started event.
    stream_event(session, "audio_advanced", 30)
    assert session.map_snapshot(response) == []


def stream_event(session, kind, timestamp):
    session.note_stream_event(SimpleNamespace(kind=kind, timestamp=timestamp))


def advance_audio(processor, session, timestamp):
    processor.total_pcm_samples = round(timestamp * processor.sample_rate)
    stream_event(session, "audio_advanced", timestamp)


def test_resume_with_stale_silence_snapshot_before_and_after_asr_catches_up():
    _, processor, response, session = fixture()
    stream_event(session, "speech_started", 0)
    advance_audio(processor, session, 4)
    processor.state.end_transcription_processed = 4
    processor.current_silence = SimpleNamespace(start=4)
    stream_event(session, "silence_started", 4)
    advance_audio(processor, session, 20)
    response.remaining_time_transcription_processing = 16
    assert session.map_snapshot(response) == []

    # Upstream clears input-side current_silence before the ASR consumes the
    # completed Silence marker. The last FrontData still carries the old lag.
    processor.current_silence = None
    stream_event(session, "speech_started", 20)
    advance_audio(processor, session, 20.2)
    assert session.map_snapshot(response) == []
    processor.state.end_transcription_processed = 20.2
    assert session.map_snapshot(response) == []


def test_two_long_pauses_and_resumptions_do_not_accumulate_fake_backlog():
    _, processor, response, session = fixture()
    stream_event(session, "speech_started", 0)
    for pause_start in (4, 24):
        advance_audio(processor, session, pause_start)
        processor.state.end_transcription_processed = pause_start
        processor.current_silence = SimpleNamespace(start=pause_start)
        stream_event(session, "silence_started", pause_start)
        advance_audio(processor, session, pause_start + 16)
        response.remaining_time_transcription_processing = 16
        assert session.map_snapshot(response) == []
        processor.current_silence = None
        stream_event(session, "speech_started", pause_start + 16)
        advance_audio(processor, session, pause_start + 16.2)
        assert session.map_snapshot(response) == []
        processor.state.end_transcription_processed = pause_start + 16.2
        assert session.map_snapshot(response) == []


def test_true_unprocessed_speech_still_fails_and_logs_only_numeric_progress(caplog):
    alignment, processor, response, session = fixture()
    alignment.speech(Token("private subtitle text", 0, 1))
    stream_event(session, "speech_started", 0)
    advance_audio(processor, session, 10)
    session.map_snapshot(response)  # Exactly 10 seconds remains permitted.
    advance_audio(processor, session, 10.2)
    # Even an old response reporting zero lag cannot hide real pending speech.
    with pytest.raises(ServiceFailure) as failure:
        session.map_snapshot(response)
    assert failure.value.code == "AUDIO_BACKLOG"
    assert "speech_backlog_seconds=10.200" in caplog.text
    assert "processed_seconds=0.000" in caplog.text
    assert "private subtitle text" not in caplog.text


def test_silence_only_discounts_overlap_with_unprocessed_audio():
    _, processor, response, session = fixture()
    stream_event(session, "speech_started", 0)
    stream_event(session, "silence_started", 2)
    stream_event(session, "speech_started", 18)
    advance_audio(processor, session, 20)
    processor.state.end_transcription_processed = 10
    assert session.map_snapshot(response) == []  # Eight silent + two spoken.
    advance_audio(processor, session, 28.2)
    with pytest.raises(ServiceFailure) as failure:
        session.map_snapshot(response)
    assert failure.value.code == "AUDIO_BACKLOG"  # 10.2 spoken, not 2.2.


def test_long_current_silence_does_not_hide_earlier_unprocessed_speech():
    _, processor, response, session = fixture()
    stream_event(session, "speech_started", 0)
    stream_event(session, "silence_started", 11)
    processor.current_silence = SimpleNamespace(start=11)
    advance_audio(processor, session, 41)
    with pytest.raises(ServiceFailure) as failure:
        session.map_snapshot(response)
    assert failure.value.code == "AUDIO_BACKLOG"


def test_new_input_state_before_vad_events_does_not_mix_clock_domains():
    _, processor, response, session = fixture()
    stream_event(session, "speech_started", 0)
    advance_audio(processor, session, 4)
    processor.state.end_transcription_processed = 4
    # Input has advanced past a whole pause; the event consumer has not yet
    # received its VAD boundaries. A snapshot may be mapped first.
    processor.total_pcm_samples = round(20.2 * processor.sample_rate)
    response.remaining_time_transcription_processing = 16
    assert session.map_snapshot(response) == []
    stream_event(session, "silence_started", 4)
    assert session.map_snapshot(response) == []
    stream_event(session, "speech_started", 20)
    assert session.map_snapshot(response) == []
    stream_event(session, "audio_advanced", 20.2)
    assert session.map_snapshot(response) == []


def test_events_replay_cached_snapshot_after_silence_ends_without_false_fatal():
    async def check():
        alignment, processor, response, session = fixture()
        processor.current_silence = SimpleNamespace(start=4)
        processor.state.end_transcription_processed = 4
        processor.total_pcm_samples = 20 * processor.sample_rate
        response.remaining_time_transcription_processing = 16
        for kind, timestamp in (("speech_started", 0), ("audio_advanced", 4),
                                ("silence_started", 4), ("audio_advanced", 20)):
            session.stream_events.put_nowait(SimpleNamespace(kind=kind, timestamp=timestamp))
        snapshot_published = asyncio.Event()

        async def upstream():
            yield response
            snapshot_published.set()
            await asyncio.Event().wait()  # There will be no fresher FrontData.

        session.results = upstream()
        stream = session.events()
        pending = asyncio.create_task(anext(stream))
        try:
            await asyncio.wait_for(snapshot_published.wait(), 1)
            await asyncio.wait_for(session.stream_events.join(), 1)
            assert not pending.done()

            processor.current_silence = None
            processor.total_pcm_samples = round(20.2 * processor.sample_rate)
            alignment.speech(Token("Speech resumed.", 20, 20.2))
            for kind in ("speech_started", "audio_advanced"):
                session.stream_events.put_nowait(SimpleNamespace(kind=kind, timestamp=20.2))
            resumed = await asyncio.wait_for(pending, 1)
            assert resumed.is_final and resumed.text == "Speech resumed."
        finally:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
            await stream.aclose()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("streamlingo-wlk-")]
    asyncio.run(check())


def test_events_detect_real_backlog_even_without_any_snapshot():
    async def check():
        _, processor, response, session = fixture()
        processor.total_pcm_samples = round(10.2 * processor.sample_rate)

        async def upstream():
            await asyncio.Event().wait()
            yield response

        session.results = upstream()
        for kind, timestamp in (("speech_started", 0), ("audio_advanced", 10.2)):
            session.stream_events.put_nowait(SimpleNamespace(kind=kind, timestamp=timestamp))
        stream = session.events()
        with pytest.raises(ServiceFailure) as failure:
            await asyncio.wait_for(anext(stream), 1)
        assert failure.value.code == "AUDIO_BACKLOG"
        await stream.aclose()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("streamlingo-wlk-")]
    asyncio.run(check())


def test_long_unpunctuated_speech_freezes_prefix_and_preserves_suffix():
    alignment, _, response, session = fixture()
    tokens = [Token(f" word{i}", i, i + 1) for i in range(8)]
    group = alignment.speech(*tokens)
    first = session.map_snapshot(response)
    assert [(event.text, event.is_final) for event in first] == [
        ("word0 word1 word2", True), ("word3 word4 word5", True), ("word6 word7", False),
    ]
    suffix = Token(" word8.", 8, 9)
    group.tokens.append(suffix)
    alignment.all_tokens.append(suffix)
    second = session.map_snapshot(response)
    assert len(second) == 1 and second[0].text == "word6 word7 word8."
    assert second[0].result_id == first[-1].result_id and second[0].is_final
    assert session.map_snapshot(response) == []


def test_multiple_sentences_with_equal_timestamps_are_not_lost_or_replayed():
    alignment, _, response, session = fixture()
    first_token = Token("First.", 1, 1)
    alignment.speech(first_token)
    first = session.map_snapshot(response)[0]
    alignment.speech(Token(" Second.", 1, 1))
    second = session.map_snapshot(response)[0]
    assert first.result_id != second.result_id
    assert second.text == "Second." and second.is_final
    assert session.map_snapshot(response) == []


def test_upstream_retention_does_not_replay_recent_finalized_tokens():
    alignment, _, response, session = fixture()
    old = Token("Old.", 0, 1)
    recent = Token(" Recent.", 65, 66)
    alignment.speech(old)
    alignment.speech(recent)
    assert len(session.map_snapshot(response)) == 2
    alignment.all_tokens = [recent]
    alignment.groups = alignment.groups[1:]
    assert session.map_snapshot(response) == []
    assert list(session._seen_tokens.values()) == [recent]


def test_character_budget_cannot_grow_unbounded_before_punctuation():
    alignment, _, response, session = fixture()
    alignment.speech(Token("a" * 60, 0, 0.1), Token("b" * 60, 0.1, 0.2), Token(" tail", 0.2, 0.3))
    events = session.map_snapshot(response)
    assert events[0].is_final and len(events[0].text) == 120
    assert not events[1].is_final and events[1].text == "tail"


def test_explicit_silence_consumed_once_even_with_overlapping_timestamps():
    alignment, _, response, session = fixture()
    before = Token("before pause", 0, 1)
    silence = SimpleNamespace(start=1, end=3, is_silence=lambda: True)
    after = Token("after pause", 2.9, 3.0)
    alignment.speech(before)
    alignment.all_tokens.append(silence)
    alignment.groups.append(SimpleNamespace(speaker=-2, tokens=None))
    alignment.speech(after)
    events = session.map_snapshot(response)
    assert [(event.text, event.is_final) for event in events] == [
        ("before pause", True), ("after pause", False),
    ]
    # The old silence ends at the same time as a later word; it must not
    # finalize the later word again when the next snapshot repeats history.
    assert session.map_snapshot(response) == []


def test_input_silence_does_not_finalize_late_tokens_before_asr_ready():
    alignment, processor, response, session = fixture()
    first = Token("The next step is", 10, 11)
    group = alignment.speech(first)
    processor.current_silence = SimpleNamespace(start=15)
    processor.total_pcm_samples = 22 * 16000
    response.remaining_time_transcription_processing = 9
    initial = session.map_snapshot(response)[0]
    assert not initial.is_final
    for token in [Token(" to translate", 11, 12), Token(" these sentences", 12, 12.9)]:
        alignment.all_tokens.append(token)
        group.tokens.append(token)
        update = session.map_snapshot(response)[0]
        assert not update.is_final and update.result_id == initial.result_id
    assert session.map_snapshot(response) == []
    session.note_stream_event(SimpleNamespace(kind="silence_transcription_ready", timestamp=15))
    final = session.map_snapshot(response)[0]
    assert final.is_final and final.text == "The next step is to translate these sentences"
    assert final.result_id == initial.result_id


def test_ready_silence_with_decoder_buffer_does_not_finalize_prefix():
    alignment, processor, response, session = fixture()
    group = alignment.speech(Token("a stable prefix", 1, 2))
    processor.current_silence = SimpleNamespace(start=3)
    processor.total_pcm_samples = 5 * 16000
    session.note_stream_event(SimpleNamespace(kind="silence_transcription_ready", timestamp=3))
    response.buffer_transcription = "remaining words"
    partial = session.map_snapshot(response)[0]
    assert not partial.is_final
    tail = Token(" remaining words", 2, 2.8)
    group.tokens.append(tail)
    alignment.all_tokens.append(tail)
    response.buffer_transcription = ""
    final = session.map_snapshot(response)[0]
    assert final.is_final and final.text == "a stable prefix remaining words"
    assert final.result_id == partial.result_id


def test_ready_event_for_an_old_pause_cannot_finalize_current_pause():
    alignment, processor, response, session = fixture()
    alignment.speech(Token("current speech", 10, 11))
    processor.current_silence = SimpleNamespace(start=12)
    processor.total_pcm_samples = 15 * 16000
    session.note_stream_event(SimpleNamespace(kind="silence_transcription_ready", timestamp=4))
    assert not session.map_snapshot(response)[0].is_final


def test_ready_event_after_last_snapshot_can_finalize_and_cancel_cleanly():
    async def check():
        alignment, processor, response, session = fixture()
        alignment.speech(Token("waiting for inference", 1, 2))
        processor.current_silence = SimpleNamespace(start=3)
        processor.total_pcm_samples = 5 * 16000

        async def upstream():
            yield response
            await session.stream_events.put(SimpleNamespace(kind="silence_transcription_ready", timestamp=3))
            await asyncio.Event().wait()

        session.results = upstream()
        stream = session.events()
        first = await asyncio.wait_for(anext(stream), 1)
        assert not first.is_final
        final = await asyncio.wait_for(anext(stream), 1)
        assert final.is_final and final.result_id == first.result_id
        await stream.aclose()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("streamlingo-wlk-")]
    asyncio.run(check())


def test_stable_prefix_deadline_is_not_reset_by_partial_snapshots():
    clock = [0.0]
    alignment, _, response, session = fixture(clock=lambda: clock[0])
    alignment.speech(Token("these words are already stable", 1, 1.1))
    response.buffer_transcription = "a changing hypothesis must not be finalized"
    partial = session.map_snapshot(response)[0]
    for now in (1.0, 2.0, 2.49):
        clock[0] = now
        assert session.map_snapshot(response) == []
    clock[0] = 2.5
    final = session.map_snapshot(response)[0]
    assert final.is_final and final.result_id == partial.result_id
    assert final.text == "these words are already stable"
    assert session.map_snapshot(response) == []
    # A late suffix gets its own full wait, not the old prefix's expired timer.
    clock[0] = 2.6
    alignment.speech(Token(" later stable words", 1.1, 1.2))
    next_partial = session.map_snapshot(response)[0]
    assert not next_partial.is_final and next_partial.result_id != final.result_id
    clock[0] = 5.11
    next_final = session.map_snapshot(response)[0]
    assert next_final.is_final and next_final.result_id == next_partial.result_id


def test_long_text_with_compressed_word_timestamps_is_bounded_and_lossless():
    alignment, _, response, session = fixture()
    words = [f"word{index:02d}" for index in range(50)]
    alignment.speech(*(Token(" " + word, 0, 0.1) for word in words))
    emitted = session.map_snapshot(response)
    assert len(emitted) >= 3 and all(event.is_final for event in emitted[:-1])
    assert all(len(event.text) <= 120 for event in emitted)
    assert " ".join(event.text for event in emitted).split() == words
    assert len({event.result_id for event in emitted}) == len(emitted)
    assert session.map_snapshot(response) == []


def test_uncommitted_hypothesis_is_never_finalized_by_timer():
    clock = [0.0]
    _, _, response, session = fixture(clock=lambda: clock[0])
    response.buffer_transcription = "uncommitted " * 100
    assert session.map_snapshot(response) == []
    clock[0] = 60.0
    assert session.map_snapshot(response) == []


def test_stable_prefix_timer_fires_even_if_both_upstream_streams_are_idle():
    async def check():
        clock = [0.0]
        alignment, _, response, session = fixture(clock=lambda: clock[0])
        alignment.speech(Token("stable words without punctuation", 0, 0.1))
        response.buffer_transcription = "still uncertain"

        async def upstream():
            yield response
            await asyncio.Event().wait()

        session.results = upstream()
        stream = session.events()
        first = await asyncio.wait_for(anext(stream), 1)
        assert not first.is_final
        clock[0] = 2.5
        final = await asyncio.wait_for(anext(stream), 1)
        assert final.is_final and final.result_id == first.result_id
        assert final.text == first.text and "uncertain" not in final.text
        await stream.aclose()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("streamlingo-wlk-")]
    asyncio.run(check())


def test_timed_stable_prefix_reaches_translation_scheduler_and_preserves_suffix():
    async def check():
        clock = [0.0]
        alignment, _, response, recognition = fixture(clock=lambda: clock[0])
        alignment.speech(Token("a stable prefix with no punctuation", 0, 0.1))
        response.buffer_transcription = "uncertain suffix"
        next_snapshot = asyncio.Queue()

        async def upstream():
            yield response
            while True:
                yield await next_snapshot.get()

        calls = []

        async def translate(request):
            calls.append(request)
            return TranslationResult("稳定前缀的中文", is_mock=True)

        recognition.results = upstream()
        application = SubtitleSession(str(uuid4()), recognition, SimpleNamespace(translate=translate), 160_000)
        stream = application.subtitles()
        try:
            partial = await asyncio.wait_for(anext(stream), 1)
            assert not partial["source_final"] and calls == []
            clock[0] = 2.5
            # Ongoing audio wakes the already waiting collector; the stable
            # text and engine response do not need to change to start translation.
            recognition.stream_events.put_nowait(SimpleNamespace(kind="audio_advanced", timestamp=1))
            pending = await asyncio.wait_for(anext(stream), 1)
            complete = await asyncio.wait_for(anext(stream), 1)
            assert pending["source_final"] and pending["translation"]["status"] == "pending"
            assert complete["translation"]["status"] == "complete"
            assert pending["segment_id"] == complete["segment_id"] == partial["segment_id"]
            assert complete["revision"] > pending["revision"] > partial["revision"]
            assert calls[0].text == partial["source_text"] and "uncertain" not in calls[0].text

            alignment.speech(Token(" later committed suffix.", 0.1, 0.2))
            await next_snapshot.put(response)
            suffix = await asyncio.wait_for(anext(stream), 1)
            assert suffix["segment_id"] != complete["segment_id"]
            assert suffix["source_text"] == "later committed suffix." and suffix["source_final"]
            translated_suffix = await asyncio.wait_for(anext(stream), 1)
            assert translated_suffix["translation"]["status"] == "complete"
            assert len(calls) == 2
        finally:
            await stream.aclose()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("streamlingo-")]
    asyncio.run(check())
