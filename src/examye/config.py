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

    # LLM backend selection:
    #   "ollama"  — local Ollama daemon (default; ~5GB RAM with gemma4:e2b)
    #   "openai"  — any OpenAI-compatible /v1/chat/completions endpoint
    #               (vLLM, LiteLLM, OpenAI itself, LM Studio, …)
    #   "stub"    — skip the network entirely; always use the deterministic fallback
    llm_backend: str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores this; OpenAI-style servers use Bearer auth.
    llm_model: str = "gemma4:e2b"
    llm_timeout_seconds: float = 120.0

    # Where to reach the Ollama daemon for management ops (pull / list / ping).
    # Distinct from llm_base_url because Ollama's native API isn't /v1-prefixed.
    ollama_host: str = "http://localhost:11434"

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.frame_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
