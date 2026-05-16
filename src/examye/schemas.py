"""Pydantic schemas for HTTP IO."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    status: str
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FrameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    frame_index: int
    timestamp_seconds: float
    width: int
    height: int
    person_count: int
    phone_count: int
    suspicion_score: float
    detections: Optional[list[Any]] = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    frame_id: Optional[int] = None
    kind: str
    severity: str
    score: float
    timestamp_seconds: float
    description: str
    extra: Optional[dict[str, Any]] = None
    created_at: datetime


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    headline: str
    body: str
    severity: str
    source: str
    created_at: datetime


class QueryIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    video_id: Optional[int] = None
    top_k: int = Field(default=5, ge=1, le=20)


class QueryEvidence(BaseModel):
    event_id: int
    video_id: int
    frame_id: Optional[int] = None
    timestamp_seconds: float
    description: str
    score: float


class QueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: Optional[int] = None
    question: str
    answer: str
    evidence: list[QueryEvidence] = Field(default_factory=list)
    source: str
    created_at: datetime
