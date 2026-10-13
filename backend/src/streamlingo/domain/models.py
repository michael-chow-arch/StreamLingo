"""Internal values, deliberately independent of WebSocket serialization."""

from dataclasses import dataclass
from typing import Literal

from streamlingo.domain.errors import ServiceFailure

SourceLanguage = Literal["en", "zh", "auto"]
TargetLanguage = Literal["zh-CN", "en"]
LANGUAGE_PAIRS = frozenset({("en", "zh-CN"), ("zh", "en"), ("auto", "zh-CN"), ("auto", "en")})


def validate_language_pair(source_language: str, target_language: str) -> None:
    if (source_language, target_language) not in LANGUAGE_PAIRS:
        raise ServiceFailure("UNSUPPORTED_LANGUAGE",
                             "Supported directions: en to zh-CN, zh to en, auto to zh-CN, auto to en")


@dataclass(frozen=True, slots=True)
class AudioFormat:
    encoding: Literal["pcm_s16le"] = "pcm_s16le"
    sample_rate: Literal[16000] = 16000
    channels: Literal[1] = 1


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    """An ASR hypothesis; the pipeline maps it to a display segment.

    result_id identifies a hypothesis within one recognition session.
    Later events with this ID replace its text until is_final becomes true.
    Times are milliseconds since the beginning of captured session audio.
    """

    result_id: str
    text: str
    start_ms: int
    end_ms: int
    is_final: bool


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    text: str
    source_language: SourceLanguage = "en"
    target_language: TargetLanguage = "zh-CN"
    context: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_language_pair(self.source_language, self.target_language)


@dataclass(frozen=True, slots=True)
class TranslationResult:
    text: str
    is_mock: bool = False
