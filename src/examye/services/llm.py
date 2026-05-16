"""Backend-agnostic LLM client.

Supports any OpenAI-compatible chat-completion endpoint, so the same code path
works for Ollama (default), vLLM, LiteLLM, LM Studio, or OpenAI itself. The
caller treats every call as best-effort — on any failure we return None and let
the higher layer fall back to a deterministic stub.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


def _chat_url() -> str:
    base = get_settings().llm_base_url.rstrip("/")
    return f"{base}/chat/completions"


def chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> Optional[str]:
    """Run a chat completion. Returns the model's text on success, None on failure."""
    settings = get_settings()
    if settings.llm_backend == "stub":
        return None

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            r = client.post(_chat_url(), json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.ConnectError as exc:
        logger.info(
            "LLM backend %s unreachable at %s (%s); using stub fallback. "
            "Run `uv run examye pull-model` and start the backend.",
            settings.llm_backend,
            settings.llm_base_url,
            exc,
        )
        return None
    except Exception as exc:
        logger.info("LLM call failed (%s); using stub fallback", exc)
        return None

    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("unexpected LLM response shape: %s", exc)
        return None


def ping() -> tuple[bool, str]:
    """Quickly check whether the configured backend is reachable.

    Returns (reachable, message). Used by the CLI to give a clear health signal.
    """
    settings = get_settings()
    if settings.llm_backend == "stub":
        return True, "backend=stub (deterministic, no network)"

    # For Ollama, hit /api/tags. For OpenAI-compatible, hit /models.
    if settings.llm_backend == "ollama":
        url = f"{settings.ollama_host.rstrip('/')}/api/tags"
    else:
        url = f"{settings.llm_base_url.rstrip('/')}/models"

    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(url, headers={"Authorization": f"Bearer {settings.llm_api_key}"})
            r.raise_for_status()
            return True, f"ok ({url})"
    except Exception as exc:
        return False, f"unreachable: {exc}"
