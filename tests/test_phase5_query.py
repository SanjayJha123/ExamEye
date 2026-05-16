"""Phase 5: natural-language query — retrieval + LLM/stub answer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from examye.models import Event, Video
from examye.services import query as query_service


@pytest.fixture
def seeded(isolated_examye):
    db = isolated_examye["SessionLocal"]()
    try:
        v1 = Video(filename="a.mp4", stored_path="/tmp/a", size_bytes=1, status="completed")
        v2 = Video(filename="b.mp4", stored_path="/tmp/b", size_bytes=1, status="completed")
        db.add_all([v1, v2])
        db.commit()
        db.refresh(v1)
        db.refresh(v2)

        events = [
            Event(
                video_id=v1.id,
                kind="phone_visible",
                severity="high",
                score=0.91,
                timestamp_seconds=12.5,
                description="cell phone visible in candidate's hand",
            ),
            Event(
                video_id=v1.id,
                kind="close_contact",
                severity="medium",
                score=0.71,
                timestamp_seconds=88.0,
                description="two candidates leaning close together",
            ),
            Event(
                video_id=v2.id,
                kind="candidate_absent",
                severity="low",
                score=0.55,
                timestamp_seconds=5.0,
                description="empty seat where candidate should be",
            ),
        ]
        db.add_all(events)
        db.commit()
        return {"v1": v1.id, "v2": v2.id}
    finally:
        db.close()


def test_retrieval_returns_relevant_events(isolated_examye, seeded, monkeypatch):
    monkeypatch.setattr(query_service.llm, "chat", lambda *a, **k: None)

    client = TestClient(isolated_examye["app"])
    r = client.post("/api/query", json={"question": "Were any phones used?", "top_k": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "stub"

    # Phone event should be the top hit (token match on "phone")
    assert data["evidence"]
    assert data["evidence"][0]["description"].lower().count("phone") >= 1


def test_query_scoped_to_one_video(isolated_examye, seeded, monkeypatch):
    monkeypatch.setattr(query_service.llm, "chat", lambda *a, **k: None)
    client = TestClient(isolated_examye["app"])
    r = client.post(
        "/api/query",
        json={"question": "What happened?", "video_id": seeded["v2"], "top_k": 5},
    )
    data = r.json()
    assert r.status_code == 200
    assert data["video_id"] == seeded["v2"]
    for e in data["evidence"]:
        assert e["video_id"] == seeded["v2"]


def test_query_uses_vllm_when_available(isolated_examye, seeded, monkeypatch):
    monkeypatch.setattr(
        query_service.llm,
        "chat",
        lambda system, user, *, temperature, max_tokens: "Yes, see [E1] — a phone was visible.",
    )
    client = TestClient(isolated_examye["app"])
    r = client.post("/api/query", json={"question": "Were any phones used?", "top_k": 3})
    data = r.json()
    assert data["source"] == "vllm"
    assert "phone" in data["answer"].lower()


def test_query_rejects_too_short(isolated_examye):
    client = TestClient(isolated_examye["app"])
    r = client.post("/api/query", json={"question": "hi"})
    assert r.status_code == 422


def test_query_with_no_events_says_so(isolated_examye, monkeypatch):
    monkeypatch.setattr(query_service.llm, "chat", lambda *a, **k: None)
    client = TestClient(isolated_examye["app"])
    r = client.post("/api/query", json={"question": "Anything suspicious?"})
    data = r.json()
    assert data["source"] == "stub"
    assert "No detection events" in data["answer"]
