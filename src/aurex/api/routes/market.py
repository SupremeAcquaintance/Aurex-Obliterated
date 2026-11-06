from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.market_state.schemas import (
    CandleImportRequest,
    CandleImportResponse,
    MarketStateComputeRequest,
    MarketStateResponse,
)
from aurex.market_state.service import MarketStateEngine, normalize_symbol

router = APIRouter(prefix="/market", tags=["market"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/candles/import", response_model=CandleImportResponse)
def import_market_candles(payload: CandleImportRequest, db: DbSession) -> CandleImportResponse:
    imported, updated = MarketStateEngine(db).import_candles(payload)
    db.commit()
    return CandleImportResponse(
        imported=imported,
        updated=updated,
        symbol=normalize_symbol(payload.symbol),
        timeframe=payload.timeframe,
    )


@router.post("/state/compute", response_model=MarketStateResponse)
def compute_market_state(payload: MarketStateComputeRequest, db: DbSession) -> object:
    state = MarketStateEngine(db).compute_state(
        payload.symbol,
        payload.timeframe,
        higher_timeframe=payload.higher_timeframe,
        limit=payload.limit,
    )
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough candles to compute market state",
        )
    db.commit()
    db.refresh(state)
    return state

