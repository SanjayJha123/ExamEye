"""Natural-language query over stored events with LLM-backed answer + evidence."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from sqlalchemy.orm import Session

from ..models import Event, QueryRecord, Summary, Video
from ..schemas import QueryIn
from . import llm

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
    "and", "or", "but", "if", "then", "this", "that", "those", "these",
    "do", "does", "did", "have", "has", "had", "i", "you", "we", "they",
    "what", "when", "where", "why", "how", "which", "who",
}

_SYSTEM_PROMPT = (
    "You are ExamEye, an investigation assistant. Answer the user's question using "
    "only the supplied evidence events. If the evidence is insufficient, say so. "
    "Cite evidence by their numeric IDs in square brackets, e.g. [E12]. Keep the "
    "answer concise (under 180 words)."
)


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _score_event(query_tokens: set[str], event: Event) -> float:
    haystack = f"{event.kind} {event.description}".lower()
    if not query_tokens:
        return event.score
    text_tokens = set(_tokenize(haystack))
    overlap = len(query_tokens & text_tokens)
    base = overlap / max(len(query_tokens), 1)
    severity_boost = {"high": 0.3, "medium": 0.15, "low": 0.05, "info": 0.0}.get(event.severity, 0.0)
    return base + severity_boost + 0.2 * event.score


def _retrieve(db: Session, payload: QueryIn) -> list[Event]:
    q = db.query(Event)
    if payload.video_id is not None:
        q = q.filter(Event.video_id == payload.video_id)
    events: list[Event] = q.all()
    if not events:
        return []
    tokens = set(_tokenize(payload.question))
    scored: list[tuple[float, Event]] = [(_score_event(tokens, e), e) for e in events]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [e for score, e in scored[: payload.top_k] if score > 0]


def _format_evidence(events: Iterable[Event]) -> str:
    lines = []
    for e in events:
        lines.append(
            f"[E{e.id}] video={e.video_id} t={e.timestamp_seconds:.1f}s "
            f"{e.kind} severity={e.severity} score={e.score:.2f}: {e.description}"
        )
    return "\n".join(lines) if lines else "(no relevant events found)"


def _stub_answer(payload: QueryIn, events: list[Event]) -> str:
    if not events:
        scope = f" in video {payload.video_id}" if payload.video_id else ""
        return (
            f"No detection events relevant to your question were found{scope}. "
            "Either the footage didn't contain matching activity, or the pipeline "
            "has not finished processing yet."
        )
    parts = [f"Found {len(events)} relevant detection event(s):"]
    for e in events:
        parts.append(
            f"- [E{e.id}] at t={e.timestamp_seconds:.1f}s ({e.severity}): {e.description}"
        )
    parts.append(
        "Review the cited frames before drawing conclusions; this is an automated retrieval."
    )
    return "\n".join(parts)


def answer_query(db: Session, payload: QueryIn) -> QueryRecord:
    events = _retrieve(db, payload)

    context_blocks = [_format_evidence(events)]
    if payload.video_id is not None:
        summary = db.query(Summary).filter(Summary.video_id == payload.video_id).one_or_none()
        if summary is not None:
            context_blocks.append(
                f"Existing video summary:\nHeadline: {summary.headline}\nBody: {summary.body}"
            )
        video = db.get(Video, payload.video_id)
        if video is not None:
            context_blocks.append(
                f"Video metadata: filename={video.filename}, "
                f"duration={video.duration_seconds or 0:.1f}s, status={video.status}"
            )

    user_prompt = (
        f"Question: {payload.question}\n\n"
        f"Evidence:\n{chr(10).join(context_blocks)}\n\n"
        f"Answer the question using the evidence above."
    )

    text = llm.chat(_SYSTEM_PROMPT, user_prompt, temperature=0.1, max_tokens=400)
    if text:
        answer = text
        source = "vllm"
    else:
        answer = _stub_answer(payload, events)
        source = "stub"

    evidence_payload = [
        {
            "event_id": e.id,
            "video_id": e.video_id,
            "frame_id": e.frame_id,
            "timestamp_seconds": e.timestamp_seconds,
            "description": e.description,
            "score": e.score,
        }
        for e in events
    ]

    record = QueryRecord(
        video_id=payload.video_id,
        question=payload.question,
        answer=answer,
        evidence=evidence_payload,
        source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
