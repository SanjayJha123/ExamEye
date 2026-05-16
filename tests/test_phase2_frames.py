"""Phase 2: OpenCV frame extraction."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from examye.services.frame_extraction import extract_frames, probe_video


def _make_synthetic_video(path: Path, *, frames: int = 30, fps: int = 10, size: tuple[int, int] = (160, 120)) -> None:
    w, h = size
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError("could not open VideoWriter (mp4v) — opencv build may lack ffmpeg")
    try:
        for i in range(frames):
            img = np.zeros((h, w, 3), dtype=np.uint8)
            color = (i * 8 % 256, (i * 13) % 256, (i * 21) % 256)
            img[:] = color
            cv2.putText(img, str(i), (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            writer.write(img)
    finally:
        writer.release()


def test_probe_video(isolated_examye, tmp_path):
    src = tmp_path / "synthetic.mp4"
    _make_synthetic_video(src, frames=20, fps=10, size=(160, 120))

    meta = probe_video(src)
    assert meta.fps > 0
    assert meta.width == 160
    assert meta.height == 120
    assert meta.frame_count == 20


def test_extract_frames_at_interval(isolated_examye, tmp_path, monkeypatch):
    # 30 frames at 10 fps = 3.0s. With interval=1.0s we expect ~3 frames.
    src = tmp_path / "synthetic.mp4"
    _make_synthetic_video(src, frames=30, fps=10, size=(160, 120))

    settings = isolated_examye["settings"]
    monkeypatch.setattr(settings, "frame_interval_seconds", 1.0)

    meta, records = extract_frames(src, video_id=42)
    assert meta.fps == pytest.approx(10.0, rel=0.1)
    assert 3 <= len(records) <= 4
    for r in records:
        assert r.path.exists()
        assert r.width == 160 and r.height == 120
        assert r.timestamp_seconds >= 0

    # Files live under the configured frame_dir/video_id/
    frame_dir = settings.frame_dir / "42"
    assert frame_dir.exists()
    assert sorted(p.name for p in frame_dir.iterdir()) == sorted(r.path.name for r in records)


def test_extract_frames_respects_max(isolated_examye, tmp_path, monkeypatch):
    src = tmp_path / "synthetic.mp4"
    _make_synthetic_video(src, frames=60, fps=30, size=(80, 60))

    settings = isolated_examye["settings"]
    monkeypatch.setattr(settings, "frame_interval_seconds", 0.1)
    monkeypatch.setattr(settings, "max_frames_per_video", 5)

    _meta, records = extract_frames(src, video_id=99)
    assert len(records) == 5
