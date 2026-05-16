"""Thin client for an OpenAI-compatible vLLM endpoint (Gemma 4).

All callers should treat this as best-effort. If the endpoint is unreachable or
returns garbage, they should fall back to a deterministic stub.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    source: str  # "vllm" or "stub"


def _build_url() -> str:
    base = get_settings().vllm_base_url.rstrip("/")
    return f"{base}/chat/completions"


def chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> Optional[str]:
    """Call the vLLM chat completion endpoint. Returns text on success, None on failure."""
    settings = get_settings()
    payload = {
        "model": settings.vllm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {settings.vllm_api_key}"}

    try:
        with httpx.Client(timeout=settings.vllm_timeout_seconds) as client:
            r = client.post(_build_url(), json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.info("vLLM call failed (%s); will use stub fallback", exc)
        return None

    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("unexpected vLLM response shape: %s", exc)
        return None
