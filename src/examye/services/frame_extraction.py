"""Extract frames from uploaded videos using OpenCV."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2  # type: ignore[import-untyped]

from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class FrameRecord:
    frame_index: int
    timestamp_seconds: float
    path: Path
    width: int
    height: int


@dataclass
class VideoMeta:
    fps: float
    width: int
    height: int
    frame_count: int
    duration_seconds: float


def probe_video(video_path: Path) -> VideoMeta:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {video_path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if fps > 0 else 0.0
        return VideoMeta(fps=fps, width=width, height=height, frame_count=frame_count, duration_seconds=duration)
    finally:
        cap.release()


def extract_frames(video_path: Path, video_id: int) -> tuple[VideoMeta, list[FrameRecord]]:
    """Extract frames at a fixed time interval. Returns metadata and records."""
    settings = get_settings()
    meta = probe_video(video_path)

    out_dir = settings.frame_dir / str(video_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    if meta.fps <= 0:
        logger.warning("video %s has no FPS metadata; defaulting to 25", video_path)
        meta.fps = 25.0

    step = max(int(round(meta.fps * settings.frame_interval_seconds)), 1)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {video_path}")

    records: list[FrameRecord] = []
    try:
        index = 0
        saved = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                ts = index / meta.fps
                fname = f"frame_{saved:05d}.jpg"
                fpath = out_dir / fname
                cv2.imwrite(str(fpath), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                h, w = frame.shape[:2]
                records.append(
                    FrameRecord(
                        frame_index=saved,
                        timestamp_seconds=ts,
                        path=fpath,
                        width=int(w),
                        height=int(h),
                    )
                )
                saved += 1
                if saved >= settings.max_frames_per_video:
                    logger.info(
                        "reached max_frames_per_video=%s for video %s",
                        settings.max_frames_per_video,
                        video_id,
                    )
                    break
            index += 1
    finally:
        cap.release()

    return meta, records
