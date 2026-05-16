"""Natural-language investigation query endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import QueryIn, QueryOut
from ..services.query import answer_query

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", response_model=QueryOut)
def ask(payload: QueryIn, db: Session = Depends(get_db)) -> QueryOut:
    record = answer_query(db, payload)
    return QueryOut.model_validate(
        {
            "id": record.id,
            "video_id": record.video_id,
            "question": record.question,
            "answer": record.answer,
            "evidence": record.evidence or [],
            "source": record.source,
            "created_at": record.created_at,
        }
    )
