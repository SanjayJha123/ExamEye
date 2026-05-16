"""Frame and event listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Frame, Video
from ..schemas import EventOut, FrameOut

router = APIRouter(prefix="/api/videos/{video_id}", tags=["frames"])


@router.get("/frames", response_model=list[FrameOut])
def list_frames(
    video_id: int,
    suspicious_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[FrameOut]:
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    q = db.query(Frame).filter(Frame.video_id == video_id)
    if suspicious_only:
        from ..config import get_settings

        q = q.filter(Frame.suspicion_score >= get_settings().suspicion_threshold)
    rows = q.order_by(Frame.frame_index.asc()).all()
    return [FrameOut.model_validate(r) for r in rows]


@router.get("/events", response_model=list[EventOut])
def list_events(video_id: int, db: Session = Depends(get_db)) -> list[EventOut]:
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    rows = (
        db.query(Event)
        .filter(Event.video_id == video_id)
        .order_by(Event.timestamp_seconds.asc())
        .all()
    )
    return [EventOut.model_validate(r) for r in rows]
