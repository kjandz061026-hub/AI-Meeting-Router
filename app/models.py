from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class AIConfigBase(BaseModel):
    name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    system_prompt: str = ""
    context_window: int = 8192
    is_compressor: bool = False
    enabled: bool = True
    self_intro: str = ""
    confidence_calibration: int = Field(default=0, description="置信度校准值，会加到AI输出的置信度上。负值可惩罚过度自信的AI，正值可提升保守AI的置信度。范围[-100, 100]")

    @field_validator("context_window")
    @classmethod
    def validate_context_window(cls, value: int) -> int:
        return max(1024, value)

    @field_validator("confidence_calibration")
    @classmethod
    def validate_confidence_calibration(cls, value: int) -> int:
        return max(-100, min(100, value))


class AIConfigCreate(AIConfigBase):
    pass


class AIConfigUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    context_window: int | None = None
    is_compressor: bool | None = None
    enabled: bool | None = None
    self_intro: str | None = None
    confidence_calibration: int | None = None


class AIConfig(AIConfigBase):
    id: str = Field(default_factory=lambda: str(uuid4()))
    order: int = 0


class AIOrderUpdate(BaseModel):
    ids: list[str]


class DiscussionRequest(BaseModel):
    question: str = Field(min_length=1)
    confidence_threshold: int = Field(default=95, ge=0, le=100)
    max_rounds: int = Field(default=5, ge=1)
    compressor_id: str | None = None


class DiscussionMessage(BaseModel):
    ai_id: str
    ai_name: str
    round_number: int
    content: str
    confidence: int | None = None
    final_answer_candidate: str | None = None
    compressed: bool = False


class DiscussionRecord(BaseModel):
    id: str
    question: str
    confidence_threshold: int
    max_rounds: int
    final_answer: str
    stop_reason: str
    messages: list[DiscussionMessage]
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscussionSummary(BaseModel):
    id: str
    question: str
    final_answer: str
    stop_reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SSEEvent(BaseModel):
    event: str
    data: dict[str, Any]
