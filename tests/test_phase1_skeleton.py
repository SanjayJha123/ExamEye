"""Phase 1: skeleton is wired up — app boots, health works, upload stores file."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_health(isolated_examye):
    client = TestClient(isolated_examye["app"])
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_index_renders(isolated_examye):
    client = TestClient(isolated_examye["app"])
    r = client.get("/")
    assert r.status_code == 200
    assert "ExamEye" in r.text
    assert "Upload CCTV footage" in r.text


def test_list_videos_empty(isolated_examye):
    client = TestClient(isolated_examye["app"])
    r = client.get("/api/videos")
    assert r.status_code == 200
    assert r.json() == []


def test_upload_rejects_bad_extension(isolated_examye):
    client = TestClient(isolated_examye["app"])
    r = client.post(
        "/api/videos",
        files={"file": ("not_a_video.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_stores_file_and_creates_row(isolated_examye, monkeypatch):
    # Block the background pipeline so the test stays isolated to Phase 1.
    import examye.routes.videos as videos_routes

    monkeypatch.setattr(videos_routes, "run_pipeline_sync", lambda video_id: None)

    client = TestClient(isolated_examye["app"])
    fake_mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64
    r = client.post(
        "/api/videos",
        files={"file": ("clip.mp4", fake_mp4, "video/mp4")},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["filename"] == "clip.mp4"
    assert data["size_bytes"] == len(fake_mp4)
    assert data["status"] == "uploaded"

    stored = list(Path(isolated_examye["settings"].upload_dir).glob("*.mp4"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == fake_mp4

    # Detail page renders too
    detail = client.get(f"/videos/{data['id']}")
    assert detail.status_code == 200
    assert "clip.mp4" in detail.text


def test_video_404(isolated_examye):
    client = TestClient(isolated_examye["app"])
    assert client.get("/api/videos/999").status_code == 404
    assert client.get("/videos/999").status_code == 404
