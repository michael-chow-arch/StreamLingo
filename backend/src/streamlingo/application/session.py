"""One bounded audio session and subtitle revisions, independent of HTTP/ASR libraries."""

import asyncio
from collections import OrderedDict, deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import monotonic

from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import SourceLanguage, TargetLanguage, TranslationRequest, validate_language_pair
from streamlingo.ports.asr import RecognitionSession
from streamlingo.ports.translator import TranslationProvider


class SessionRegistry:
    """Claim/release run synchronously on the service event loop."""

    active_id: str | None = None

    def claim(self, session_id: str) -> None:
        if self.active_id is not None:
            raise ServiceFailure("SESSION_CONFLICT", "Another subtitle session is active")
        self.active_id = session_id

    def release(self, session_id: str) -> None:
        if self.active_id == session_id:
            self.active_id = None


@dataclass(frozen=True, slots=True)
class TranslationJob:
    result_id: str
    queued_at: float
    request: TranslationRequest
    # Cue dictionaries are replaced, never mutated. Retain this final revision
    # only for the bounded queued/inflight job, independently of the ASR cache.
    final_cue: dict


class SubtitleSession:
    def __init__(self, session_id: str, recognition: RecognitionSession,
                 translator: TranslationProvider | None, max_queue_bytes: int, *,
                 translation_queue_size: int = 3, translation_timeout: float = 20.0,
                 translation_max_age: float = 15.0, source_language: SourceLanguage = "en",
                 target_language: TargetLanguage = "zh-CN") -> None:
        validate_language_pair(source_language, target_language)
        self.session_id = session_id
        self.source_language = source_language
        self.target_language = target_language
        self.recognition = recognition
        self.translator = translator
        self._audio: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
        self._queued_bytes = 0
        self._max_queue_bytes = max_queue_bytes
        self._segments: OrderedDict[str, dict] = OrderedDict()
        self._next_segment = 0
        self._translation_queue: asyncio.Queue[TranslationJob] = asyncio.Queue(maxsize=translation_queue_size)
        self._output: asyncio.Queue[dict | BaseException | None] = asyncio.Queue(maxsize=64)
        self._translation_timeout = translation_timeout
        self._translation_max_age = translation_max_age
        self._context: deque[str] = deque(maxlen=2)

    def enqueue(self, pcm: bytes) -> None:
        if self._queued_bytes + len(pcm) > self._max_queue_bytes or self._audio.full():
            raise ServiceFailure("AUDIO_BACKLOG", "Audio processing cannot keep up; restart the session")
        self._audio.put_nowait(pcm)
        self._queued_bytes += len(pcm)

    async def feed_audio(self) -> None:
        while True:
            pcm = await self._audio.get()
            try:
                await asyncio.wait_for(self.recognition.push_audio(pcm), timeout=5)
            except asyncio.TimeoutError as exc:
                raise ServiceFailure("AUDIO_BACKLOG", "Speech engine audio input timed out") from exc
            finally:
                self._queued_bytes -= len(pcm)
                self._audio.task_done()

    async def _collect_transcripts(self) -> None:
        async for event in self.recognition.events():
            if not event.text.strip():
                continue
            if len(event.text) > 8000:
                raise ServiceFailure("ASR_FAILED", "Speech segment exceeded the subtitle size limit")
            previous = self._segments.get(event.result_id)
            if previous and previous["source_final"]:
                continue
            if previous and (previous["source_text"], previous["source_final"],
                             previous["start_ms"], previous["end_ms"]) == (
                                 event.text, event.is_final, event.start_ms, event.end_ms):
                continue
            if not previous:
                self._next_segment += 1
            message = {
                "type": "subtitle", "session_id": self.session_id,
                "segment_id": previous["segment_id"] if previous else self._next_segment,
                "revision": previous["revision"] + 1 if previous else 1,
                "start_ms": event.start_ms, "end_ms": event.end_ms,
                "source_text": event.text, "source_final": event.is_final,
                "source_language": self.source_language, "target_language": self.target_language,
                "translation": {"status": "disabled", "text": None},
            }
            if self.translator and event.is_final:
                message["translation"] = {"status": "pending", "text": None}
            self._segments[event.result_id] = message
            while len(self._segments) > 256:
                self._segments.popitem(last=False)
            await self._output.put(message)
            if self.translator and event.is_final:
                job = TranslationJob(event.result_id, monotonic(), TranslationRequest(
                    event.text, source_language=self.source_language, target_language=self.target_language,
                    context=tuple(self._context),
                ), message)
                self._context.append(event.text[-1000:])
                if self._translation_queue.full():
                    dropped = self._translation_queue.get_nowait()
                    self._translation_queue.task_done()
                    await self._translation_update(dropped, "skipped", error_code="TRANSLATION_BACKLOG",
                                                   error_message="Translation queue is full; skipped an older segment")
                # No await between checking capacity and enqueueing after the
                # output update: the single producer owns this queue.
                self._translation_queue.put_nowait(job)
        if self.translator:
            await self._translation_queue.join()
        await self._output.put(None)

    async def _translation_update(self, job: TranslationJob, status: str, *, text: str | None = None,
                                  is_mock: bool = False, error_code: str | None = None,
                                  error_message: str = "") -> None:
        # Every job has one terminal update: either the queue drops it, or the
        # single worker consumes it. Cache eviction must not erase its result.
        previous = job.final_cue
        state: dict = {"status": status, "text": text}
        if status == "complete":
            state["is_mock"] = is_mock
        message = {**previous, "revision": previous["revision"] + 1, "translation": state}
        if self._segments.get(job.result_id) is previous:
            self._segments[job.result_id] = message
        await self._output.put(message)
        if error_code:
            await self._output.put({"type": "error", "session_id": self.session_id,
                                    "segment_id": previous["segment_id"], "code": error_code,
                                    "message": error_message, "fatal": False})

    async def _translate(self) -> None:
        assert self.translator is not None
        while True:
            job = await self._translation_queue.get()
            try:
                remaining_age = self._translation_max_age - (monotonic() - job.queued_at)
                if remaining_age <= 0:
                    await self._translation_update(job, "skipped", error_code="TRANSLATION_BACKLOG",
                                                   error_message="Queued translation expired; source subtitles remain available")
                    continue
                try:
                    effective_timeout = min(self._translation_timeout, remaining_age)
                    result = await asyncio.wait_for(self.translator.translate(job.request),
                                                    timeout=effective_timeout)
                    if not result.text.strip() or len(result.text) > 8000:
                        raise ServiceFailure("TRANSLATION_FAILED", "Translation result is empty or too long")
                except asyncio.TimeoutError:
                    if remaining_age <= self._translation_timeout:
                        await self._translation_update(job, "skipped", error_code="TRANSLATION_BACKLOG",
                                                       error_message="Translation expired; source subtitles remain available")
                    else:
                        await self._translation_update(job, "error", error_code="TRANSLATION_TIMEOUT",
                                                       error_message="Translation timed out; source subtitles remain available")
                except Exception as exc:
                    code = (exc.code if isinstance(exc, ServiceFailure) and exc.code == "TRANSLATION_TIMEOUT"
                            else "TRANSLATION_FAILED")
                    await self._translation_update(job, "error", error_code=code,
                                                   error_message="Translation failed; source subtitles remain available")
                else:
                    # Results are addressed to their original segment, never to
                    # a global current line. Other source text can arrive meanwhile.
                    # The age/timeout budget limits unfinished work. Once the
                    # provider has returned valid text, preserve that result
                    # even if scheduling has carried it past the age budget.
                    await self._translation_update(job, "complete", text=result.text, is_mock=result.is_mock)
            finally:
                self._translation_queue.task_done()

    async def subtitles(self) -> AsyncIterator[dict]:
        async def guarded(coroutine):
            try:
                await coroutine
            except Exception as exc:
                await self._output.put(exc)

        collector = asyncio.create_task(guarded(self._collect_transcripts()), name="streamlingo-asr-events")
        tasks = [collector]
        if self.translator:
            tasks.append(asyncio.create_task(guarded(self._translate()), name="streamlingo-translate"))
        try:
            while True:
                message = await self._output.get()
                if message is None:
                    return
                if isinstance(message, BaseException):
                    raise message
                yield message
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
