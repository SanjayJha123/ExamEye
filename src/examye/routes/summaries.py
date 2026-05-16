"""Per-video AI investigation summary endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Summary, Video
from ..schemas import SummaryOut
from ..services.summarization import generate_summary

router = APIRouter(prefix="/api/videos/{video_id}/summary", tags=["summary"])


@router.get("", response_model=SummaryOut)
def get_summary(video_id: int, db: Session = Depends(get_db)) -> SummaryOut:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    summary = db.query(Summary).filter(Summary.video_id == video_id).one_or_none()
    if summary is None:
        raise HTTPException(status_code=404, detail="summary not generated yet")
    return SummaryOut.model_validate(summary)


@router.post("", response_model=SummaryOut)
def regenerate_summary(video_id: int, db: Session = Depends(get_db)) -> SummaryOut:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    summary = generate_summary(db, video)
    return SummaryOut.model_validate(summary)
