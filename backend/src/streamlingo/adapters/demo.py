"""Audio-driven transport fixture. This is deliberately not speech recognition."""

import asyncio
from collections.abc import AsyncIterator

from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import AudioFormat, SourceLanguage, TranscriptEvent, TranslationRequest, TranslationResult


class DemoRecognitionSession:
    def __init__(self, interval_ms: int, language: SourceLanguage = "en") -> None:
        self.language = language
        self._interval_samples = interval_ms * 16
        self._samples = 0
        self._segment = 0
        self._events: asyncio.Queue[TranscriptEvent] = asyncio.Queue(maxsize=8)
        self._closed = False

    async def push_audio(self, pcm: bytes) -> None:
        if self._closed:
            return
        self._samples += len(pcm) // 2
        while self._samples >= (self._segment + 1) * self._interval_samples:
            self._segment += 1
            end = self._segment * self._interval_samples // 16
            # Auto alternates known fixture languages; this is not detection.
            chinese = self.language == "zh" or (self.language == "auto" and self._segment % 2 == 0)
            text = (f"[DEMO — 非语音识别结果] 已收到 {end / 1000:.1f} 秒浏览器音频。" if chinese else
                    f"[DEMO — not recognized speech] Audio received: {end / 1000:.1f} s.")
            await self._events.put(TranscriptEvent(
                str(self._segment), text,
                end - self._interval_samples // 16, end, True,
            ))

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        while not self._closed:
            yield await self._events.get()

    async def close(self) -> None:
        self._closed = True


class DemoRecognizer:
    source_languages: tuple[SourceLanguage, ...] = ("en", "zh", "auto")

    def __init__(self, interval_ms: int = 2000) -> None:
        self.interval_ms = interval_ms

    async def open_session(self, *, audio_format: AudioFormat, language: SourceLanguage) -> DemoRecognitionSession:
        if language not in self.source_languages:
            raise ServiceFailure("UNSUPPORTED_LANGUAGE", "Unsupported demo source language")
        return DemoRecognitionSession(self.interval_ms, language)


class DemoTranslator:
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        text = ("【演示字幕，非识别或翻译结果】已收到浏览器音频。" if request.target_language == "zh-CN" else
                "[DEMO — not recognized or translated speech] Browser audio received.")
        return TranslationResult(text, is_mock=True)
