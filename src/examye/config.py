"""Application settings, loaded from environment with EXAMYE_ prefix."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EXAMYE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./examye.db"
    upload_dir: Path = Path("./data/uploads")
    frame_dir: Path = Path("./data/frames")

    frame_interval_seconds: float = 1.0
    max_frames_per_video: int = 600

    yolo_model: str = "yolov8n.pt"
    yolo_conf: float = 0.35
    suspicion_threshold: float = 0.55

    vllm_base_url: str = "http://localhost:8001/v1"
    vllm_api_key: str = "EMPTY"
    vllm_model: str = "google/gemma-2-9b-it"
    vllm_timeout_seconds: float = 30.0

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.frame_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
