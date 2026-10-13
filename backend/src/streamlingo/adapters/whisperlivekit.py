"""Thin bridge to the pinned upstream streaming engine, not a new ASR engine.

API inspected in the PyPI whisperlivekit 0.2.26 wheel. The adapter relies on
AudioProcessor's session queues/alignment state, so refuse other versions.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable
from importlib.metadata import version
import logging
import math
from time import monotonic
from typing import Any

from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import AudioFormat, SourceLanguage, TranscriptEvent
from streamlingo.settings import Settings

UPSTREAM_VERSION = "0.2.26"
MAX_SEGMENT_SECONDS = 3.0
MAX_SEGMENT_CHARACTERS = 120
MAX_STABLE_WAIT_SECONDS = 2.5
logger = logging.getLogger(__name__)


class RealtimeWhisperModel:
    """Override decoding cost, forwarding the pinned upstream model unchanged.

    WLK 0.2.26 hardcodes beam_size=5 in FasterWhisperASR.transcribe, so its
    transcribe_kargs cannot override it without duplicate-keyword errors. This
    model proxy changes only public faster-whisper decoding options; upstream
    still owns recognition, timestamps, LocalAgreement and buffer trimming.
    """

    def __init__(self, model: Any, *, beam_size: int) -> None:
        self.wrapped_model = model
        self.beam_size = beam_size

    def __getattr__(self, name: str) -> Any:
        return getattr(self.wrapped_model, name)

    def transcribe(self, audio: Any, **kwargs: Any) -> Any:
        # Avoid multiple temperature fallback decodes on difficult live audio.
        # These are separate feedback paths: condition_on_previous_text only
        # resets history between faster-whisper's internal windows, while WLK
        # independently injects a suffix of committed words as initial_prompt
        # on every call. Disable both so a mistaken phrase cannot prompt itself.
        # Leave decoded text untouched: genuine spoken repetitions remain valid.
        kwargs.update(beam_size=self.beam_size, best_of=1, temperature=0.0,
                      condition_on_previous_text=False, initial_prompt=None)
        return self.wrapped_model.transcribe(audio, **kwargs)


class WhisperLiveKitRecognizer:
    def __init__(self, engine: Any) -> None:
        self.engine = engine
        # Inspect the loaded model, not its directory/name: a renamed .en model
        # must not advertise auto/Chinese and silently fall back to English.
        supported = getattr(engine.asr.model, "supported_languages", ("en",))
        self.source_languages: tuple[SourceLanguage, ...] = (
            ("en", "zh", "auto") if "zh" in supported else ("en",)
        )

    @classmethod
    def load(cls, settings: Settings) -> "WhisperLiveKitRecognizer":
        if version("whisperlivekit") != UPSTREAM_VERSION:
            raise RuntimeError(f"Install whisperlivekit=={UPSTREAM_VERSION}")
        from whisperlivekit import TranscriptionEngine
        from whisperlivekit.config import WhisperLiveKitConfig

        config = WhisperLiveKitConfig(
            model_size=settings.model, model_dir=settings.model_dir,
            model_cache_dir=settings.model_cache_dir,
            backend="faster-whisper", backend_policy="localagreement",
            lan="en", pcm_input=True, diarization=False, target_language="",
            min_chunk_size=0.5, retention_seconds=60.0,
            pause_segmentation_seconds=1.0,
            asr_coalesce_min_s=settings.asr_coalesce_seconds,
            buffer_trimming="segment", buffer_trimming_sec=settings.asr_buffer_seconds,
        )
        engine = TranscriptionEngine(config=config)
        engine.asr.model = RealtimeWhisperModel(engine.asr.model, beam_size=settings.asr_beam_size)
        logger.info("ASR_PROFILE beam_size=%d coalesce_seconds=%.2f buffer_seconds=%.2f temperature=0 "
                    "condition_on_previous_text=false initial_prompt=none",
                    settings.asr_beam_size, settings.asr_coalesce_seconds, settings.asr_buffer_seconds)
        return cls(engine)

    async def open_session(self, *, audio_format: AudioFormat, language: SourceLanguage) -> "WhisperLiveKitSession":
        if language not in self.source_languages:
            raise ServiceFailure("UNSUPPORTED_LANGUAGE",
                                 "The loaded speech model only supports English; load a multilingual Whisper model for Chinese or auto")
        from whisperlivekit import AudioProcessor

        stream_events = asyncio.Queue(maxsize=64)
        processor = AudioProcessor(transcription_engine=self.engine, language=language,
                                   pcm_input=True, mode="diff", stream_event_queue=stream_events)
        # WLK creates alignment before online_factory resolves the ASR separator.
        # Faster-whisper tokens already include needed spaces; Chinese must not
        # acquire the alignment constructor's default English word separator.
        processor.tokens_alignment.sep = processor.sep
        # Upstream 0.2.26 constructs an unbounded asyncio.Queue. Replace it
        # before create_tasks: 125 VAC chunks * 40 ms = about 5 seconds.
        processor.transcription_queue = asyncio.Queue(maxsize=125)
        session = WhisperLiveKitSession(processor, stream_events=stream_events)
        try:
            session.results = await processor.create_tasks()
        except BaseException:
            await processor.cleanup()
            raise
        return session


class WhisperLiveKitSession:
    def __init__(self, processor: Any, *, stream_events: asyncio.Queue | None = None,
                 clock: Callable[[], float] = monotonic) -> None:
        self.processor = processor
        self.results: Any = None
        self._closed = False
        self._seen_tokens: dict[int, Any] = {}
        self._pending_tokens: list[Any] = []
        self._clock = clock
        self._pending_since: float | None = None
        self._segment_number = 0
        self._last_emitted: TranscriptEvent | None = None
        self.stream_events = stream_events if stream_events is not None else asyncio.Queue(maxsize=64)
        self._transcription_ready_silence: float | None = None
        self._audio_event_time = 0.0
        # 0.2.26 process_audio starts with an implicit silence at sample zero;
        # there is no silence_started event for this initial interval.
        self._input_silence_start: float | None = 0.0
        self._completed_silences: deque[tuple[float, float]] = deque()

    async def push_audio(self, pcm: bytes) -> None:
        if not self._closed:
            task = self.processor.transcription_task
            if task and task.done():
                raise ServiceFailure("ASR_FAILED", "Speech recognition task stopped unexpectedly")
            await self.processor.process_audio(pcm)

    def _check_backlog(self) -> None:
        """Count unprocessed speech on one audio clock, excluding VAD silence.

        FrontData lag has no capture timestamp and may be replayed after input
        silence has ended. Use the live processed clock and the last consumed
        audio_advanced event instead: upstream queues every VAD boundary before
        that event, so the silence history is complete through this frontier.
        Reading live total_pcm_samples instead could race ahead of those events.
        """
        processed = max(0.0, self.processor.state.end_transcription_processed)
        received = self._audio_event_time
        while self._completed_silences and self._completed_silences[0][1] <= processed:
            self._completed_silences.popleft()

        silent = sum(max(0.0, min(end, received) - max(start, processed))
                     for start, end in self._completed_silences)
        if self._input_silence_start is not None:
            silent += max(0.0, received - max(self._input_silence_start, processed))
        speech_backlog = max(0.0, received - processed - silent)
        if speech_backlog > 10:
            queue = self.processor.transcription_queue
            logger.warning(
                "ASR_BACKLOG input_seconds=%.3f event_input_seconds=%.3f "
                "processed_seconds=%.3f unprocessed_silence_seconds=%.3f "
                "speech_backlog_seconds=%.3f transcription_queue_items=%d stream_event_queue_items=%d",
                self.processor.total_pcm_samples / self.processor.sample_rate,
                received, processed, silent, speech_backlog,
                queue.qsize() if queue is not None else 0, self.stream_events.qsize(),
            )
            raise ServiceFailure("AUDIO_BACKLOG", "Speech recognition is over 10 seconds behind")

    def map_snapshot(self, response: Any) -> list[TranscriptEvent]:
        """Reuse upstream punctuation groups over committed tokens only.

        Upstream's non-diarized display lines do not close until speech resumes
        after a long pause. They are therefore unsuitable as translation jobs.
        Its existing punctuation grouping provides earlier stable boundaries;
        this adapter adds a display budget and trailing-silence flush. No decoder
        hypothesis is promoted to stable text, and each committed token is
        consumed once even when distinct words have identical timestamps.
        """
        if response.status == "error" or response.error:
            raise ServiceFailure("ASR_FAILED", "Speech recognition engine reported an error")
        audio_time = self.processor.total_pcm_samples / self.processor.sample_rate
        silence = self.processor.current_silence
        silence_age = max(0.0, audio_time - silence.start) if silence and silence.start is not None else 0.0
        self._check_backlog()

        alignment = self.processor.tokens_alignment
        window_ids = {id(token) for token in alignment.all_tokens}
        self._seen_tokens = {key: token for key, token in self._seen_tokens.items() if key in window_ids}
        events: list[TranscriptEvent] = []

        def emit(final: bool) -> None:
            if not self._pending_tokens:
                return
            # Faster-whisper supplies its own word spacing, for both English
            # and Chinese. Preserve it rather than inserting spaces per token.
            text = "".join(token.text for token in self._pending_tokens).strip()
            start = max(0, round(min(token.start for token in self._pending_tokens) * 1000))
            end = max(start, round(max(token.end for token in self._pending_tokens) * 1000))
            event = TranscriptEvent(f"wlk:{self._segment_number}", text, start, end, final)
            if text and event != self._last_emitted:
                events.append(event)
                self._last_emitted = event
            if final:
                self._pending_tokens = []
                self._pending_since = None

        punctuation_ends = {
            id(group.tokens[-1]) for group in alignment.compute_punctuations_segments()
            if group.tokens and group.tokens[-1].has_punctuation()
        }
        # Consume the original ordered token stream, including explicit Silence
        # objects. Timestamp comparisons cannot distinguish separate words or
        # an old pause when alignments overlap at a boundary.
        for token in alignment.all_tokens:
            if id(token) in self._seen_tokens:
                continue
            self._seen_tokens[id(token)] = token
            if token.is_silence():
                emit(True)
                continue
            if token.start is None or token.end is None or not all(
                math.isfinite(value) for value in (token.start, token.end)
            ):
                raise ServiceFailure("ASR_FAILED", "Speech engine returned invalid timestamps")
            if not token.text:
                continue
            if (self._pending_tokens
                    and sum(len(item.text) for item in self._pending_tokens) + len(token.text)
                    > MAX_SEGMENT_CHARACTERS):
                emit(True)
            if not self._pending_tokens:
                self._segment_number += 1
                self._pending_since = self._clock()
            self._pending_tokens.append(token)
            duration = token.end - self._pending_tokens[0].start
            text_length = sum(len(item.text) for item in self._pending_tokens)
            if (id(token) in punctuation_ends or duration >= MAX_SEGMENT_SECONDS
                    or text_length >= MAX_SEGMENT_CHARACTERS):
                emit(True)

        # Tokens in all_tokens are already committed by LocalAgreement. A
        # bounded wait may finalize that stable prefix while the engine keeps
        # decoding a variable suffix; the suffix starts a new result when it
        # commits. Repeated snapshots never restart this monotonic deadline.
        if self._pending_since is not None and self._clock() - self._pending_since >= MAX_STABLE_WAIT_SECONDS:
            emit(True)
        if (self._pending_tokens and silence_age >= 1.0
                and self._transcription_ready_silence is not None
                and abs(self._transcription_ready_silence - silence.start) < 1e-6
                and not response.buffer_transcription.strip()
                and self._pending_tokens[-1].end <= audio_time - 1.0):
            emit(True)
        emit(False)
        return events

    def note_stream_event(self, event: Any) -> None:
        """Use the same ASR progress barrier as upstream's Deepgram adapter.

        Input-side VAD silence can arrive seconds before inference catches up.
        AudioProcessor emits silence_transcription_ready only after processing
        the silence marker and publishing the resulting token/buffer snapshot.
        """
        silence = self.processor.current_silence
        if event.kind == "speech_started":
            if self._input_silence_start is not None:
                self._completed_silences.append((self._input_silence_start, event.timestamp))
                self._input_silence_start = None
            self._transcription_ready_silence = None
        elif event.kind == "silence_transcription_ready":
            if silence and silence.start is not None and abs(event.timestamp - silence.start) < 1e-6:
                self._transcription_ready_silence = event.timestamp
        elif event.kind == "silence_started":
            self._input_silence_start = event.timestamp
            if self._transcription_ready_silence != event.timestamp:
                self._transcription_ready_silence = None
        elif event.kind == "audio_advanced":
            self._audio_event_time = max(self._audio_event_time, event.timestamp)

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        # Advance both streams. The readiness event is deliberately emitted by
        # upstream *after* its result generator resumes from yielding a snapshot,
        # so only draining events from inside `async for response` would miss it
        # if the snapshot itself did not subsequently change.
        result_task = asyncio.create_task(anext(self.results), name="streamlingo-wlk-result")
        event_task = asyncio.create_task(self.stream_events.get(), name="streamlingo-wlk-event")
        last_response = None
        try:
            while not self._closed:
                timeout = (None if self._pending_since is None else
                           max(0.0, self._pending_since + MAX_STABLE_WAIT_SECONDS - self._clock()))
                done, _ = await asyncio.wait((result_task, event_task), timeout=timeout,
                                             return_when=asyncio.FIRST_COMPLETED)
                if not done and last_response is not None:
                    for event in self.map_snapshot(last_response):
                        yield event
                if result_task in done:
                    try:
                        last_response = result_task.result()
                    except StopAsyncIteration:
                        return
                    mapped = self.map_snapshot(last_response)
                    result_task = asyncio.create_task(anext(self.results), name="streamlingo-wlk-result")
                    for event in mapped:
                        yield event
                if event_task in done:
                    self.note_stream_event(event_task.result())
                    self.stream_events.task_done()
                    event_task = asyncio.create_task(self.stream_events.get(), name="streamlingo-wlk-event")
                    # Enforce the budget even if the result stream has not yet
                    # produced its first snapshot (or stops changing).
                    self._check_backlog()
                    if last_response is not None:
                        for event in self.map_snapshot(last_response):
                            yield event
        finally:
            result_task.cancel()
            event_task.cancel()
            await asyncio.gather(result_task, event_task, return_exceptions=True)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self.processor.cleanup()
        if self.results is not None:
            await self.results.aclose()
