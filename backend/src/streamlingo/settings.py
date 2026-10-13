"""Explicit local-only runtime configuration; model credentials never enter the page."""

from dataclasses import dataclass
from ipaddress import ip_address
import re
import math
from typing import Literal
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Settings:
    mode: Literal["demo", "whisperlivekit"] = "whisperlivekit"
    host: str = "127.0.0.1"
    port: int = 8765
    allowed_origins: tuple[str, ...] = ()
    model: str = "base"
    model_dir: str | None = None
    model_cache_dir: str | None = None
    asr_beam_size: int = 1
    asr_coalesce_seconds: float = 0.8
    asr_buffer_seconds: float = 8.0
    handshake_timeout: float = 10.0
    close_timeout: float = 5.0
    audio_queue_bytes: int = 160_000
    max_audio_packet_bytes: int = 32_000
    max_control_bytes: int = 4096
    demo_interval_ms: int = 2000
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str | None = None
    translation_timeout: float = 20.0
    translation_max_age: float = 15.0
    translation_queue_size: int = 3

    def __post_init__(self) -> None:
        if self.mode not in ("demo", "whisperlivekit"):
            raise ValueError("Unsupported runtime mode")
        if self.host != "localhost" and not ip_address(self.host).is_loopback:
            raise ValueError("StreamLingo MVP binds only to loopback addresses")
        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        if type(self.asr_beam_size) is not int or not 1 <= self.asr_beam_size <= 5:
            raise ValueError("ASR beam size must be an integer between 1 and 5")
        if not math.isfinite(self.asr_coalesce_seconds) or not 0.1 <= self.asr_coalesce_seconds <= 2:
            raise ValueError("ASR coalescing must be between 0.1 and 2 seconds")
        if not math.isfinite(self.asr_buffer_seconds) or not 4 <= self.asr_buffer_seconds <= 30:
            raise ValueError("ASR buffer trimming must be between 4 and 30 seconds")
        for origin in self.allowed_origins:
            if not re.fullmatch(r"chrome-extension://[a-p]{32}", origin):
                raise ValueError("Allowed origins must be exact chrome-extension:// IDs")
        for value in (self.handshake_timeout, self.close_timeout, self.audio_queue_bytes,
                      self.max_audio_packet_bytes, self.max_control_bytes, self.demo_interval_ms,
                      self.translation_timeout, self.translation_max_age, self.translation_queue_size):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Runtime limits must be positive")
        if self.translation_queue_size > 16:
            raise ValueError("Translation queue must contain at most 16 waiting segments")
        endpoint = urlsplit(self.ollama_url)
        if (endpoint.scheme not in ("http", "https") or not endpoint.hostname or endpoint.username
                or endpoint.password or endpoint.query or endpoint.fragment
                or endpoint.path not in ("", "/")):
            raise ValueError("Ollama URL must be an HTTP(S) server origin without credentials or a path")
        if self.ollama_model is not None and (not self.ollama_model.strip() or len(self.ollama_model) > 200):
            raise ValueError("Ollama model must be a nonempty model name of at most 200 characters")
