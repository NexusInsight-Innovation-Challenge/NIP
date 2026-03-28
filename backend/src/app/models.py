from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    USER_MESSAGE = "user.message"
    STATUS = "status"
    ASSISTANT_DELTA = "assistant.delta"
    ASSISTANT_COMPLETE = "assistant.complete"
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_RESPONSE = "approval.response"
    APPROVAL_FINALIZED = "approval.finalized"
    ERROR = "error"


class EnvelopeMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    source: str | None = None
    intent: str | None = None
    processing_ms: int | None = None


class MessageEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    role: str = Field(default="system", min_length=1, max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: EnvelopeMetadata = Field(default_factory=EnvelopeMetadata)

    @field_validator("conversation_id", "correlation_id", "id")
    @classmethod
    def trim_ids(cls, value: str) -> str:
        return value.strip()


class UserMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    message: str = Field(min_length=1, max_length=4000)
    user_id: str = Field(default="demo-user", min_length=1, max_length=128)

    @field_validator("message")
    @classmethod
    def no_empty_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message cannot be empty")
        return stripped
