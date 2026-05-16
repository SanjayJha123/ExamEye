"""Ollama management operations: pull, list, ping.

Talks to the daemon directly over HTTP so users don't need the `ollama` binary
in PATH — only a running Ollama service.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Iterator, Optional

import httpx

from ..config import get_settings


@dataclass
class PullProgress:
    status: str
    completed: Optional[int] = None
    total: Optional[int] = None
    digest: Optional[str] = None

    @property
    def percent(self) -> Optional[float]:
        if self.total and self.total > 0 and self.completed is not None:
            return 100.0 * self.completed / self.total
        return None


def _api(path: str) -> str:
    return f"{get_settings().ollama_host.rstrip('/')}{path}"


def stream_pull(model: str) -> Iterator[PullProgress]:
    """Stream pull progress events from /api/pull."""
    with httpx.Client(timeout=None) as client:
        with client.stream("POST", _api("/api/pull"), json={"name": model, "stream": True}) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield PullProgress(
                    status=str(data.get("status", "")),
                    completed=data.get("completed"),
                    total=data.get("total"),
                    digest=data.get("digest"),
                )


def list_models() -> list[dict]:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(_api("/api/tags"))
        r.raise_for_status()
        return r.json().get("models", [])


def is_running() -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(_api("/api/tags"))
            return r.status_code == 200
    except Exception:
        return False


def _fmt_bytes(n: Optional[int]) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


def pull_with_progress(model: str, *, out=None) -> int:
    """Stream pull progress to `out` and return an exit code (0 ok, 1 error)."""
    if out is None:
        out = sys.stderr
    if not is_running():
        host = get_settings().ollama_host
        print(
            f"❌ Ollama daemon not reachable at {host}.\n"
            f"   Install: https://ollama.com/download\n"
            f"   Then run: `ollama serve` (or start the macOS app).",
            file=out,
        )
        return 1

    print(f"📥 Pulling {model} via {get_settings().ollama_host}…", file=out)
    last_digest: Optional[str] = None
    try:
        for progress in stream_pull(model):
            if progress.digest and progress.digest != last_digest:
                # New layer started
                if last_digest is not None:
                    print("", file=out)
                last_digest = progress.digest

            pct = progress.percent
            tail = (
                f"{_fmt_bytes(progress.completed)}/{_fmt_bytes(progress.total)}"
                if progress.total
                else ""
            )
            bar = ""
            if pct is not None:
                filled = int(pct // 5)
                bar = "[" + "#" * filled + "-" * (20 - filled) + f"] {pct:5.1f}%"
            line = f"  {progress.status:<35} {bar} {tail}".rstrip()
            print(f"\r{line}", end="", file=out, flush=True)
    except httpx.HTTPStatusError as exc:
        print(f"\n❌ Ollama pull failed: {exc.response.status_code} {exc.response.text}", file=out)
        return 1
    except Exception as exc:
        print(f"\n❌ Ollama pull failed: {exc}", file=out)
        return 1

    print(f"\n✅ {model} ready.", file=out)
    return 0
