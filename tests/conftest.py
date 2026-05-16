"""Pytest fixtures. Test env vars are set BEFORE examye is imported."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Set environment BEFORE importing examye so settings pick it up.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="examye-test-"))
_TEST_DB = _TEST_ROOT / "test.db"
os.environ.setdefault("EXAMYE_DATABASE_URL", f"sqlite:///{_TEST_DB}")
os.environ.setdefault("EXAMYE_UPLOAD_DIR", str(_TEST_ROOT / "uploads"))
os.environ.setdefault("EXAMYE_FRAME_DIR", str(_TEST_ROOT / "frames"))
# Unreachable on purpose so LLM calls fall back to stubs.
os.environ.setdefault("EXAMYE_LLM_BACKEND", "openai")
os.environ.setdefault("EXAMYE_LLM_BASE_URL", "http://127.0.0.1:1/v1")
os.environ.setdefault("EXAMYE_LLM_TIMEOUT_SECONDS", "1")
os.environ.setdefault("EXAMYE_OLLAMA_HOST", "http://127.0.0.1:1")

from examye.config import get_settings  # noqa: E402
from examye.database import Base, SessionLocal, engine  # noqa: E402
from examye.main import app  # noqa: E402
import examye.models  # noqa: E402,F401  ensure models registered


@pytest.fixture
def isolated_examye() -> Iterator[dict]:
    # Clear the settings cache so per-test env tweaks (via monkeypatch.setenv)
    # are observed even after a previous test mutated them.
    get_settings.cache_clear()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    settings = get_settings()
    settings.ensure_dirs()

    # Wipe upload/frame dirs between tests.
    for d in (settings.upload_dir, settings.frame_dir):
        for child in d.iterdir():
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                import shutil

                shutil.rmtree(child, ignore_errors=True)

    yield {
        "app": app,
        "SessionLocal": SessionLocal,
        "settings": settings,
        "tmp_path": _TEST_ROOT,
    }
