"""Composition root for the single local service process."""

import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from streamlingo.adapters.demo import DemoRecognizer, DemoTranslator
from streamlingo.adapters.ollama import OllamaTranslator
from streamlingo.application.session import SessionRegistry
from streamlingo.settings import Settings
from streamlingo.transport.live import serve_live

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry = SessionRegistry()
        self.recognizer = None
        self.translator = None
        self.ollama: OllamaTranslator | None = None
        self.asr_status = "loading"
        self.translation_status = ("mock" if settings.mode == "demo" else
                                   "configured" if settings.ollama_model else "disabled")

    def configure_translation(self) -> None:
        if self.settings.mode != "demo" and self.settings.ollama_model:
            self.ollama = OllamaTranslator(base_url=self.settings.ollama_url,
                                           model=self.settings.ollama_model,
                                           timeout=self.settings.translation_timeout)
            self.translator = self.ollama

    async def close(self) -> None:
        if self.ollama is not None:
            await self.ollama.aclose()

    async def prepare(self) -> None:
        try:
            if self.settings.mode == "demo":
                self.recognizer = DemoRecognizer(self.settings.demo_interval_ms)
                self.translator = DemoTranslator()
            else:
                from streamlingo.adapters.whisperlivekit import WhisperLiveKitRecognizer
                self.recognizer = await asyncio.to_thread(WhisperLiveKitRecognizer.load, self.settings)
            self.asr_status = "ready"
        except Exception:
            self.asr_status = "error"
            logger.exception("ASR initialization failed. Install .[asr] and configure a usable Whisper model.")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    runtime = Runtime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime.configure_translation()
        # Demo preparation is instantaneous. Real model loading runs in a worker
        # so /health can report 'starting' while initialization proceeds.
        if settings.mode == "demo":
            await runtime.prepare()
            loading = None
        else:
            loading = asyncio.create_task(runtime.prepare())
        try:
            yield
        finally:
            if loading and not loading.done():
                loading.cancel()
                with suppress(asyncio.CancelledError):
                    await loading
            await runtime.close()

    app = FastAPI(title="StreamLingo local subtitle service", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runtime = runtime
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                       allow_methods=["GET"], allow_headers=[])

    @app.middleware("http")
    async def check_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin is not None and origin not in settings.allowed_origins:
            return JSONResponse({"detail": "Extension origin is not allowed"}, status_code=403)
        return await call_next(request)

    @app.get("/health")
    async def health():
        result = {"protocol_version": 1, "mode": settings.mode,
                  "status": "starting" if runtime.asr_status == "loading" else runtime.asr_status,
                  "asr": runtime.asr_status, "translation": runtime.translation_status}
        if runtime.recognizer is not None:
            result.update(source_languages=list(getattr(runtime.recognizer, "source_languages", ("en",))),
                          target_languages=["zh-CN", "en"])
        return result

    app.add_api_websocket_route("/ws/live", serve_live)
    return app
