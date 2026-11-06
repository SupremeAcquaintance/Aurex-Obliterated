from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.db.models import PaperTrade
from aurex.execution_engine.schemas import TradeResponse

router = APIRouter(prefix="/trades", tags=["trades"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[TradeResponse])
def list_trades(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PaperTrade]:
    return list(
        db.execute(select(PaperTrade).order_by(PaperTrade.opened_at.desc()).limit(limit)).scalars()
    )


@router.get("/{trade_id}", response_model=TradeResponse)
def get_trade(trade_id: str, db: DbSession) -> PaperTrade:
    trade = db.get(PaperTrade, trade_id)
    if trade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found",
        )
    return trade

