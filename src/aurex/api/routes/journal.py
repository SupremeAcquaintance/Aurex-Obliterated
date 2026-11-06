from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.journal_engine.schemas import (
    TradeJournalEntryRequest,
    TradeJournalEntryResponse,
)
from aurex.journal_engine.service import TradeJournalService

router = APIRouter(prefix="/journal", tags=["trade-journal"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/trades", response_model=TradeJournalEntryResponse)
def create_trade_journal_entry(
    payload: TradeJournalEntryRequest,
    db: DbSession,
) -> object:
    try:
        entry = TradeJournalService(db).create_entry(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/trades", response_model=list[TradeJournalEntryResponse])
def list_trade_journal_entries(
    db: DbSession,
    paper_trade_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> object:
    return TradeJournalService(db).list_entries(
        paper_trade_id=paper_trade_id,
        limit=limit,
    )
