"""HTML pages rendered with Jinja2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Frame, Summary, Video

router = APIRouter(tags=["pages"])


def _templates(request: Request):
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return _templates(request).TemplateResponse(
        "index.html", {"request": request, "videos": videos}
    )


@router.get("/videos/{video_id}", response_class=HTMLResponse)
def video_detail(video_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")

    frames = (
        db.query(Frame)
        .filter(Frame.video_id == video_id)
        .order_by(Frame.frame_index.asc())
        .all()
    )
    events = (
        db.query(Event)
        .filter(Event.video_id == video_id)
        .order_by(Event.timestamp_seconds.asc())
        .all()
    )
    summary = db.query(Summary).filter(Summary.video_id == video_id).one_or_none()

    return _templates(request).TemplateResponse(
        "video_detail.html",
        {
            "request": request,
            "video": video,
            "frames": frames,
            "events": events,
            "summary": summary,
        },
    )


@router.get("/query", response_class=HTMLResponse)
def query_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return _templates(request).TemplateResponse(
        "query.html", {"request": request, "videos": videos}
    )


@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request) -> HTMLResponse:
    return _templates(request).TemplateResponse("alerts.html", {"request": request})
