"""Phase 4: investigation summary — vLLM path and stub fallback."""

from __future__ import annotations

import pytest

from examye.models import Event, Summary, Video
from examye.services import summarization


@pytest.fixture
def make_video(isolated_examye):
    def _make(filename: str = "exam.mp4") -> Video:
        db = isolated_examye["SessionLocal"]()
        try:
            v = Video(
                filename=filename,
                stored_path=f"/tmp/{filename}",
                size_bytes=1024,
                duration_seconds=120.0,
                status="detecting",
            )
            db.add(v)
            db.commit()
            db.refresh(v)
            return v
        finally:
            db.close()
    return _make


@pytest.fixture
def make_event(isolated_examye):
    def _make(video_id: int, **fields) -> Event:
        db = isolated_examye["SessionLocal"]()
        try:
            defaults = dict(
                kind="phone_visible",
                severity="high",
                score=0.92,
                timestamp_seconds=42.0,
                description="phone visible near candidate",
            )
            defaults.update(fields)
            e = Event(video_id=video_id, **defaults)
            db.add(e)
            db.commit()
            db.refresh(e)
            return e
        finally:
            db.close()
    return _make


def test_summary_stub_when_no_events(isolated_examye, make_video):
    video = make_video("clean.mp4")
    db = isolated_examye["SessionLocal"]()
    try:
        summary = summarization.generate_summary(db, db.get(Video, video.id))
    finally:
        db.close()

    assert summary.source == "stub"
    assert "No suspicious activity" in summary.headline
    assert summary.severity in {"info", "low"}


def test_summary_stub_with_events_summarizes_them(isolated_examye, make_video, make_event):
    video = make_video("cheating.mp4")
    make_event(video.id, kind="phone_visible", severity="high", score=0.92, timestamp_seconds=10.0)
    make_event(video.id, kind="close_contact", severity="medium", score=0.75, timestamp_seconds=45.0)
    make_event(video.id, kind="phone_visible", severity="high", score=0.88, timestamp_seconds=80.0,
               description="phone in hand")

    db = isolated_examye["SessionLocal"]()
    try:
        summary = summarization.generate_summary(db, db.get(Video, video.id))
    finally:
        db.close()

    assert summary.source == "stub"
    assert summary.severity == "high"
    assert "3" in summary.headline  # event count appears
    assert "phone_visible" in summary.body or "phone" in summary.body.lower()


def test_summary_uses_vllm_when_available(isolated_examye, make_video, make_event, monkeypatch):
    video = make_video("real.mp4")
    make_event(video.id)

    captured: dict = {}

    def fake_chat(system, user, *, temperature, max_tokens):
        captured["system"] = system
        captured["user"] = user
        return "Headline from Gemma\n- Bullet one\n- Bullet two"

    monkeypatch.setattr(summarization.llm, "chat", fake_chat)

    db = isolated_examye["SessionLocal"]()
    try:
        summary = summarization.generate_summary(db, db.get(Video, video.id))
    finally:
        db.close()

    assert summary.source == "vllm"
    assert summary.headline == "Headline from Gemma"
    assert "Bullet one" in summary.body
    assert "ExamEye" in captured["system"]
    assert "real.mp4" in captured["user"]


def test_summary_is_upserted_per_video(isolated_examye, make_video, make_event):
    video = make_video("repeat.mp4")
    make_event(video.id)

    db = isolated_examye["SessionLocal"]()
    try:
        s1 = summarization.generate_summary(db, db.get(Video, video.id))
        s2 = summarization.generate_summary(db, db.get(Video, video.id))
    finally:
        db.close()

    assert s1.id == s2.id
    db = isolated_examye["SessionLocal"]()
    try:
        assert db.query(Summary).filter(Summary.video_id == video.id).count() == 1
    finally:
        db.close()
