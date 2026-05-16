"""Investigation summary generation via Gemma 4 (vLLM) with stub fallback."""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Event, Summary, Video
from . import llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are ExamEye, an AI investigation assistant for academic exam proctoring. "
    "You analyze automated detection events from CCTV footage and produce a "
    "succinct, professional incident report. Be factual; do not invent details "
    "the events don't support. Output two sections: a short headline (one line) "
    "and a body of 3-6 bullet points covering the key observations and "
    "recommended next steps for a human investigator."
)


def _format_events_for_prompt(events: list[Event]) -> str:
    if not events:
        return "(no detection events were recorded)"
    lines: list[str] = []
    for e in events[:120]:
        lines.append(
            f"- t={e.timestamp_seconds:.1f}s [{e.severity}] {e.kind} "
            f"(score={e.score:.2f}): {e.description}"
        )
    if len(events) > 120:
        lines.append(f"... ({len(events) - 120} additional events truncated)")
    return "\n".join(lines)


def _severity_of(events: list[Event]) -> str:
    counts = Counter(e.severity for e in events)
    if counts.get("high", 0) > 0:
        return "high"
    if counts.get("medium", 0) >= 2:
        return "medium"
    if counts.get("medium", 0) == 1 or counts.get("low", 0) >= 3:
        return "low"
    return "info"


def _stub_summary(video: Video, events: list[Event]) -> tuple[str, str]:
    if not events:
        headline = f"No suspicious activity detected in {video.filename}."
        body = (
            "- The automated pipeline processed the footage end-to-end.\n"
            "- No events crossed the suspicion threshold.\n"
            "- Recommend routine review only."
        )
        return headline, body

    kinds = Counter(e.kind for e in events)
    high = [e for e in events if e.severity == "high"]
    medium = [e for e in events if e.severity == "medium"]

    top_kinds = ", ".join(f"{k} ({n}×)" for k, n in kinds.most_common(3))
    headline = (
        f"{len(events)} suspicious events flagged in {video.filename} "
        f"({len(high)} high, {len(medium)} medium severity)."
    )
    bullets = [f"- Predominant patterns: {top_kinds}."]
    if high:
        first = high[0]
        last = high[-1]
        bullets.append(
            f"- High-severity activity spans t={first.timestamp_seconds:.1f}s to "
            f"t={last.timestamp_seconds:.1f}s; first observation: {first.description}."
        )
    if medium:
        bullets.append(
            f"- {len(medium)} medium-severity event(s); review frames near "
            f"t={medium[0].timestamp_seconds:.1f}s for context."
        )
    bullets.append(
        "- Recommend a human investigator review the high-severity evidence frames "
        "before any disciplinary action."
    )
    return headline, "\n".join(bullets)


def _parse_llm_output(text: str) -> tuple[str, str]:
    """Split LLM output into (headline, body)."""
    stripped = text.strip()
    if not stripped:
        return ("ExamEye summary", "(empty LLM response)")
    parts = stripped.split("\n", 1)
    headline = parts[0].strip().lstrip("# ").strip()
    body = parts[1].strip() if len(parts) > 1 else ""
    if not body:
        body = headline
        headline = headline[:160]
    return headline[:480], body


def generate_summary(db: Session, video: Video) -> Summary:
    events = (
        db.query(Event)
        .filter(Event.video_id == video.id)
        .order_by(Event.timestamp_seconds.asc())
        .all()
    )
    severity = _severity_of(events)

    user_prompt = (
        f"Video: {video.filename}\n"
        f"Duration: {video.duration_seconds or 0:.1f}s\n"
        f"Total detection events: {len(events)}\n"
        f"Overall severity tag: {severity}\n\n"
        f"Events (chronological):\n{_format_events_for_prompt(events)}\n\n"
        f"Write the headline on the first line, then the bullets."
    )

    text = llm.chat(_SYSTEM_PROMPT, user_prompt, temperature=0.2, max_tokens=512)
    if text:
        headline, body = _parse_llm_output(text)
        source = "vllm"
    else:
        headline, body = _stub_summary(video, events)
        source = "stub"

    existing = db.query(Summary).filter(Summary.video_id == video.id).one_or_none()
    if existing is None:
        existing = Summary(video_id=video.id)
        db.add(existing)

    existing.headline = headline
    existing.body = body
    existing.severity = severity
    existing.source = source
    db.commit()
    db.refresh(existing)
    return existing


# Settings is imported lazily where needed
get_settings = get_settings  # re-export for tests
