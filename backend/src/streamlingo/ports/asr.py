"""Streaming ASR boundary; no dependency on a particular recognition engine."""

from collections.abc import AsyncIterator
from typing import Protocol

from streamlingo.domain.models import AudioFormat, SourceLanguage, TranscriptEvent


class RecognitionSession(Protocol):
    async def push_audio(self, pcm: bytes) -> None:
        """Accept ordered PCM frames, applying bounded backpressure."""
        ...

    def events(self) -> AsyncIterator[TranscriptEvent]:
        """Yield revisions and final hypotheses for this session only."""
        ...

    async def close(self) -> None:
        """Idempotently cancel work, discard pending output, and release resources."""
        ...


class SpeechRecognizer(Protocol):
    source_languages: tuple[SourceLanguage, ...]

    async def open_session(
        self, *, audio_format: AudioFormat, language: SourceLanguage
    ) -> RecognitionSession:
        """Allocate per-session recognition state around a prepared engine."""
        ...
