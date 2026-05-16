"""ORM models for ExamEye."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    frames: Mapped[list["Frame"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", order_by="Frame.frame_index"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    summary: Mapped[Optional["Summary"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", uselist=False
    )
    queries: Mapped[list["QueryRecord"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class Frame(Base):
    __tablename__ = "frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    frame_index: Mapped[int] = mapped_column(Integer)
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    stored_path: Mapped[str] = mapped_column(String(1024))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    person_count: Mapped[int] = mapped_column(Integer, default=0)
    phone_count: Mapped[int] = mapped_column(Integer, default=0)
    suspicion_score: Mapped[float] = mapped_column(Float, default=0.0)
    detections: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    video: Mapped[Video] = relationship(back_populates="frames")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    frame_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("frames.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="low")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    video: Mapped[Video] = relationship(back_populates="events")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True
    )
    headline: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="low")
    source: Mapped[str] = mapped_column(String(32), default="stub")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    video: Mapped[Video] = relationship(back_populates="summary")


class QueryRecord(Base):
    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    evidence: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="stub")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    video: Mapped[Optional[Video]] = relationship(back_populates="queries")
