"""End-to-end: upload synthetic video, run pipeline, fetch summary and query."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from examye.models import Event, Frame, Summary, Video
from examye.services import detection


def _make_video(path: Path, frames: int = 20, fps: int = 10) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (160, 120))
    for i in range(frames):
        img = np.full((120, 160, 3), (i * 10) % 256, dtype=np.uint8)
        writer.write(img)
    writer.release()


@pytest.fixture
def faked_detection(monkeypatch):
    """Mock YOLO so we don't pay for the model download mid-test."""

    def fake_analyze(image_path: Path, width: int, height: int) -> detection.FrameAnalysis:
        # Every other frame: phone + two people very close together => high severity.
        idx = int(image_path.stem.split("_")[-1])
        if idx % 2 == 0:
            return detection.score_from_detections(
                [
                    detection.Detection(label="person", confidence=0.9, bbox=(40, 30, 70, 110)),
                    detection.Detection(label="person", confidence=0.9, bbox=(72, 30, 100, 110)),
                    detection.Detection(label="cell phone", confidence=0.85, bbox=(60, 50, 80, 70)),
                ],
                width,
                height,
            )
        return detection.score_from_detections(
            [detection.Detection(label="person", confidence=0.9, bbox=(40, 30, 90, 110))],
            width,
            height,
        )

    monkeypatch.setattr("examye.pipeline.detection.analyze_frame", fake_analyze)


def test_full_pipeline_e2e(isolated_examye, tmp_path, faked_detection, monkeypatch):
    src = tmp_path / "exam_clip.mp4"
    _make_video(src, frames=20, fps=10)

    # Keep settings tight so the synthetic video produces a handful of frames.
    settings = isolated_examye["settings"]
    monkeypatch.setattr(settings, "frame_interval_seconds", 0.5)

    client = TestClient(isolated_examye["app"])

    # Upload the video — BackgroundTasks runs run_pipeline_sync after the response.
    with src.open("rb") as fh:
        r = client.post(
            "/api/videos",
            files={"file": ("exam_clip.mp4", fh, "video/mp4")},
        )
    assert r.status_code == 201, r.text
    video_id = r.json()["id"]

    # By the time TestClient returns from POST, BackgroundTasks have finished.
    db = isolated_examye["SessionLocal"]()
    try:
        video = db.get(Video, video_id)
        assert video is not None
        assert video.status in {"completed", "completed_with_warnings"}, f"status={video.status} error={video.error}"

        frames = db.query(Frame).filter(Frame.video_id == video_id).all()
        assert len(frames) >= 3
        assert any(f.suspicion_score >= settings.suspicion_threshold for f in frames)

        events = db.query(Event).filter(Event.video_id == video_id).all()
        assert events, "expected at least one suspicious event"
        assert any(e.kind == "phone_visible" for e in events)

        summary = db.query(Summary).filter(Summary.video_id == video_id).one_or_none()
        assert summary is not None
        assert summary.source == "stub"  # vLLM unreachable in tests
        assert summary.severity in {"high", "medium"}
    finally:
        db.close()

    # Detail page renders with events + frames + summary.
    detail = client.get(f"/videos/{video_id}")
    assert detail.status_code == 200
    assert "phone_visible" in detail.text
    assert "Investigation Summary" in detail.text

    # NL query against the data we just produced.
    q = client.post(
        "/api/query",
        json={"question": "Were any phones visible?", "video_id": video_id, "top_k": 5},
    )
    assert q.status_code == 200
    qdata = q.json()
    assert qdata["evidence"], "expected retrieval to find phone events"
    assert any("phone" in e["description"].lower() for e in qdata["evidence"])

    # Delete cleans up both DB row and stored file.
    d = client.delete(f"/api/videos/{video_id}")
    assert d.status_code == 204
    assert client.get(f"/api/videos/{video_id}").status_code == 404
