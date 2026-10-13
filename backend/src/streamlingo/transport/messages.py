"""Validate protocol v1 at runtime. Internal values are not wire schemas."""

import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from streamlingo.domain.errors import ServiceFailure
from streamlingo.domain.models import SourceLanguage, TargetLanguage, validate_language_pair


class StrictMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AudioMessage(StrictMessage):
    encoding: Literal["pcm_s16le"]
    sample_rate: Literal[16000]
    channels: Literal[1]

    @field_validator("sample_rate", "channels", mode="before")
    @classmethod
    def integer_only(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Integer required")
        return value


class SessionMessage(StrictMessage):
    session_id: str

    @field_validator("session_id")
    @classmethod
    def valid_uuid(cls, value: str) -> str:
        if len(value) != 36 or str(UUID(value)) != value.lower():
            raise ValueError("session_id must be a UUID")
        return value


class StartMessage(SessionMessage):
    type: Literal["start"]
    protocol_version: Literal[1]
    source_language: SourceLanguage
    target_language: TargetLanguage
    audio: AudioMessage

    @model_validator(mode="after")
    def supported_direction(self) -> "StartMessage":
        validate_language_pair(self.source_language, self.target_language)
        return self


class StopMessage(SessionMessage):
    type: Literal["stop"]


def parse_control(text: str, max_bytes: int) -> StartMessage | StopMessage:
    if len(text.encode("utf-8")) > max_bytes:
        raise ServiceFailure("INVALID_MESSAGE", "Control message is too large")
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Object required")
        if data.get("type") == "start":
            if type(data.get("protocol_version")) is not int or data["protocol_version"] != 1:
                raise ServiceFailure("UNSUPPORTED_PROTOCOL", "Only protocol version 1 is supported")
            return StartMessage.model_validate(data)
        if data.get("type") == "stop":
            return StopMessage.model_validate(data)
        raise ValueError("Unknown message type")
    except (ValueError, ValidationError, RecursionError) as exc:
        raise ServiceFailure("INVALID_MESSAGE", "Invalid control message or session identifier") from exc


def error_message(error: ServiceFailure, session_id: str | None) -> dict:
    return {"type": "error", "session_id": session_id, "segment_id": None,
            "code": error.code, "message": error.message, "fatal": True}
