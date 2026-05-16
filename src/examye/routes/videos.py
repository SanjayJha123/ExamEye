"""Video upload, list, retrieve, delete."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Video
from ..pipeline import run_pipeline_sync
from ..schemas import VideoOut

router = APIRouter(prefix="/api/videos", tags=["videos"])

_ALLOWED_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_CHUNK = 1024 * 1024


@router.get("", response_model=list[VideoOut])
def list_videos(db: Session = Depends(get_db)) -> list[VideoOut]:
    rows = db.query(Video).order_by(Video.created_at.desc()).all()
    return [VideoOut.model_validate(r) for r in rows]


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: int, db: Session = Depends(get_db)) -> VideoOut:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    return VideoOut.model_validate(video)


@router.post("", response_model=VideoOut, status_code=201)
async def upload_video(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported video format {suffix!r}; allowed: {sorted(_ALLOWED_SUFFIXES)}",
        )

    settings = get_settings()
    settings.ensure_dirs()

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = settings.upload_dir / stored_name

    size = 0
    async with aiofiles.open(stored_path, "wb") as out:
        while True:
            chunk = await file.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            await out.write(chunk)

    video = Video(
        filename=file.filename,
        stored_path=str(stored_path),
        size_bytes=size,
        status="uploaded",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    background.add_task(run_pipeline_sync, video.id)
    return VideoOut.model_validate(video)


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: int, db: Session = Depends(get_db)) -> None:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")

    stored = Path(video.stored_path)
    if stored.exists():
        stored.unlink(missing_ok=True)

    settings = get_settings()
    frame_dir = settings.frame_dir / str(video_id)
    if frame_dir.exists():
        shutil.rmtree(frame_dir, ignore_errors=True)

    db.delete(video)
    db.commit()
