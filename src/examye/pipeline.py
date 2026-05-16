"""Per-video processing pipeline: extract frames -> detect -> emit events -> summarize."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal
from .models import Event, Frame, Summary, Video
from .services import detection, summarization
from .services.alerts import alert_hub
from .services.frame_extraction import FrameRecord, VideoMeta, extract_frames

logger = logging.getLogger(__name__)


def _set_status(db: Session, video: Video, status: str, error: Optional[str] = None) -> None:
    video.status = status
    video.error = error
    db.commit()


def _persist_meta(db: Session, video: Video, meta: VideoMeta) -> None:
    video.duration_seconds = meta.duration_seconds
    video.fps = meta.fps
    video.width = meta.width
    video.height = meta.height
    db.commit()


def _events_from_frame(
    video_id: int, frame: Frame, analysis: detection.FrameAnalysis
) -> list[Event]:
    """Promote a high-suspicion frame to one or more Event rows."""
    settings = get_settings()
    if analysis.suspicion_score < settings.suspicion_threshold:
        return []

    if analysis.suspicion_score >= 0.85:
        severity = "high"
    elif analysis.suspicion_score >= 0.7:
        severity = "medium"
    else:
        severity = "low"

    if analysis.phone_count > 0:
        kind = "phone_visible"
    elif analysis.book_count > 0:
        kind = "book_visible"
    elif analysis.person_count >= 2:
        kind = "close_contact"
    elif analysis.person_count == 0:
        kind = "candidate_absent"
    else:
        kind = "anomaly"

    description = "; ".join(analysis.reasons) or "Suspicion threshold exceeded."
    event = Event(
        video_id=video_id,
        frame_id=frame.id,
        kind=kind,
        severity=severity,
        score=analysis.suspicion_score,
        timestamp_seconds=frame.timestamp_seconds,
        description=description,
        extra={
            "person_count": analysis.person_count,
            "phone_count": analysis.phone_count,
            "book_count": analysis.book_count,
            "laptop_count": analysis.laptop_count,
            "reasons": analysis.reasons,
        },
    )
    return [event]


def _broadcast_event(video: Video, frame: Frame, event: Event) -> None:
    message = {
        "type": "event",
        "video_id": video.id,
        "video_filename": video.filename,
        "frame_id": frame.id,
        "frame_index": frame.frame_index,
        "timestamp_seconds": frame.timestamp_seconds,
        "kind": event.kind,
        "severity": event.severity,
        "score": event.score,
        "description": event.description,
        "frame_url": f"/media/frames/{video.id}/{Path(frame.stored_path).name}",
    }
    try:
        alert_hub.broadcast_threadsafe(message)
    except Exception as exc:  # pragma: no cover
        logger.warning("alert broadcast failed: %s", exc)


def run_pipeline(db: Session, video_id: int) -> None:
    video = db.get(Video, video_id)
    if video is None:
        logger.warning("run_pipeline: video %s not found", video_id)
        return

    logger.info("pipeline start: video_id=%s file=%s", video_id, video.filename)
    _set_status(db, video, "extracting")

    try:
        meta, records = extract_frames(Path(video.stored_path), video_id)
    except Exception as exc:
        logger.exception("frame extraction failed for video %s", video_id)
        _set_status(db, video, "failed", error=f"frame extraction: {exc}")
        return

    _persist_meta(db, video, meta)

    # Persist frame rows first so we have ids for events.
    frame_models: list[Frame] = []
    for r in records:
        f = Frame(
            video_id=video_id,
            frame_index=r.frame_index,
            timestamp_seconds=r.timestamp_seconds,
            stored_path=str(r.path),
            width=r.width,
            height=r.height,
        )
        db.add(f)
        frame_models.append(f)
    db.commit()
    for f in frame_models:
        db.refresh(f)

    _set_status(db, video, "detecting")

    for record, frame in zip(records, frame_models):
        try:
            analysis = detection.analyze_frame(record.path, record.width, record.height)
        except Exception as exc:
            logger.exception("detection failed for frame %s of video %s", record.frame_index, video_id)
            continue

        frame.person_count = analysis.person_count
        frame.phone_count = analysis.phone_count
        frame.suspicion_score = analysis.suspicion_score
        frame.detections = [
            {
                "label": d.label,
                "confidence": round(d.confidence, 4),
                "bbox": [round(v, 2) for v in d.bbox],
            }
            for d in analysis.detections
        ]
        db.commit()

        for event in _events_from_frame(video_id, frame, analysis):
            db.add(event)
            db.commit()
            db.refresh(event)
            if event.severity in {"medium", "high"}:
                _broadcast_event(video, frame, event)

    _set_status(db, video, "summarizing")
    try:
        summarization.generate_summary(db, video)
    except Exception as exc:
        logger.exception("summary generation failed for video %s", video_id)
        _set_status(db, video, "completed_with_warnings", error=f"summary: {exc}")
        _broadcast_completion(video)
        return

    _set_status(db, video, "completed")
    _broadcast_completion(video)
    logger.info("pipeline done: video_id=%s", video_id)


def _broadcast_completion(video: Video) -> None:
    try:
        alert_hub.broadcast_threadsafe(
            {
                "type": "video_completed",
                "video_id": video.id,
                "video_filename": video.filename,
                "status": video.status,
            }
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("completion broadcast failed: %s", exc)


def run_pipeline_sync(video_id: int) -> None:
    """Top-level entry used by FastAPI BackgroundTasks; opens its own session."""
    db = SessionLocal()
    try:
        run_pipeline(db, video_id)
    except Exception as exc:
        logger.exception("pipeline crashed for video %s: %s", video_id, exc)
        video = db.get(Video, video_id)
        if video is not None:
            video.status = "failed"
            video.error = str(exc)
            db.commit()
    finally:
        db.close()


__all__ = ["run_pipeline", "run_pipeline_sync"]


# Helpers re-exported for tests
def reset_summary(db: Session, video_id: int) -> None:
    existing = db.query(Summary).filter(Summary.video_id == video_id).one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()
