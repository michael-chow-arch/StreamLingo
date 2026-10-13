"""Protocol v1 WebSocket adapter and deterministic session teardown."""

import asyncio
from contextlib import suppress
import logging

from anyio import CancelScope
from fastapi import WebSocket, WebSocketDisconnect

from streamlingo.application.session import SubtitleSession
from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import AudioFormat
from streamlingo.transport.messages import StartMessage, StopMessage, error_message, parse_control

logger = logging.getLogger(__name__)


async def serve_live(websocket: WebSocket) -> None:
    runtime = websocket.app.state.runtime
    settings = runtime.settings
    if websocket.headers.get("origin") not in settings.allowed_origins:
        await websocket.close(code=1008, reason="Extension origin is not allowed")
        return
    await websocket.accept()
    session_id = None
    claimed = False
    recognition = None
    tasks: list[asyncio.Task] = []
    outcome = "error"
    failure = None
    try:
        first = await asyncio.wait_for(websocket.receive(), settings.handshake_timeout)
        if first["type"] == "websocket.disconnect":
            outcome = "disconnected"
            return
        if first.get("text") is None:
            raise ServiceFailure("INVALID_MESSAGE", "The first message must be a start object")
        start = parse_control(first["text"], settings.max_control_bytes)
        if not isinstance(start, StartMessage):
            raise ServiceFailure("INVALID_MESSAGE", "The first message must be start")
        session_id = start.session_id
        if runtime.recognizer is None:
            raise ServiceFailure("ASR_NOT_READY", "Speech engine is not ready; inspect /health and server logs")
        if start.source_language not in getattr(runtime.recognizer, "source_languages", ("en",)):
            raise ServiceFailure("UNSUPPORTED_LANGUAGE",
                                 "The loaded speech model only supports English; load a multilingual Whisper model for Chinese or auto")
        runtime.registry.claim(session_id)
        claimed = True
        recognition = await asyncio.wait_for(
            runtime.recognizer.open_session(audio_format=AudioFormat(), language=start.source_language), timeout=15,
        )
        session = SubtitleSession(
            session_id, recognition, runtime.translator, settings.audio_queue_bytes,
            translation_queue_size=settings.translation_queue_size,
            translation_timeout=settings.translation_timeout,
            translation_max_age=settings.translation_max_age,
            source_language=start.source_language, target_language=start.target_language,
        )
        await websocket.send_json({"type": "ready", "protocol_version": 1,
                                   "session_id": session_id, "mode": settings.mode,
                                   "translation": runtime.translation_status,
                                   "source_language": start.source_language,
                                   "target_language": start.target_language})

        async def receive_audio() -> str:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return "disconnected"
                if message.get("bytes") is not None:
                    pcm = message["bytes"]
                    if not pcm or len(pcm) % 2 or len(pcm) > settings.max_audio_packet_bytes:
                        raise ServiceFailure("INVALID_MESSAGE", "PCM packet must contain 2 to 32000 even bytes")
                    session.enqueue(pcm)
                elif message.get("text") is not None:
                    command = parse_control(message["text"], settings.max_control_bytes)
                    if not isinstance(command, StopMessage) or command.session_id != session_id:
                        raise ServiceFailure("INVALID_MESSAGE", "Expected stop for the active session")
                    return "user"
                else:
                    raise ServiceFailure("INVALID_MESSAGE", "Unsupported WebSocket message")

        async def send_subtitles() -> None:
            stream = session.subtitles()
            try:
                async for message in stream:
                    await asyncio.wait_for(websocket.send_json(message), timeout=5)
            finally:
                await stream.aclose()

        receiver = asyncio.create_task(receive_audio(), name="streamlingo-receive")
        feeder = asyncio.create_task(session.feed_audio(), name="streamlingo-feed")
        sender = asyncio.create_task(send_subtitles(), name="streamlingo-subtitles")
        tasks = [receiver, feeder, sender]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if receiver in done:
            outcome = receiver.result()
        else:
            for task in done:
                task.result()
            raise ServiceFailure("ASR_FAILED", "Speech recognition stream ended unexpectedly")
    except WebSocketDisconnect:
        outcome = "disconnected"
    except ServiceFailure as exc:
        failure = exc
    except asyncio.TimeoutError:
        failure = ServiceFailure("INVALID_MESSAGE", "Session operation timed out")
    except Exception:
        logger.exception("Live subtitle session failed")
        failure = ServiceFailure("ASR_FAILED" if claimed else "INTERNAL_ERROR", "Subtitle session failed; check server logs")
    finally:
        # ASGI hosts/test clients may cancel their surrounding AnyIO scope on
        # disconnect. Shield the bounded cleanup so the session slot and HTTP
        # translation request are released even under that cancellation.
        with CancelScope(shield=True):
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if recognition is not None:
                try:
                    await asyncio.wait_for(recognition.close(), settings.close_timeout)
                except Exception:
                    logger.exception("Speech session cleanup failed")
                    runtime.asr_status = "error"
                    runtime.recognizer = None
            if claimed:
                runtime.registry.release(session_id)
            if outcome != "disconnected":
                with suppress(WebSocketDisconnect, RuntimeError, OSError):
                    if failure:
                        await websocket.send_json(error_message(failure, session_id))
                    elif outcome == "user":
                        await websocket.send_json({"type": "stopped", "session_id": session_id, "reason": "user"})
                    await websocket.close(code=1000 if outcome == "user" else 1008)
