from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aurex.analyst_engine.schemas import (
    AnalystNoteResponse,
    AnalystScanRequest,
    AnalystScanResponse,
    AnalystSummaryResponse,
    PatternSimilarityResponse,
)
from aurex.analyst_engine.service import AnalystEngine
from aurex.api.dependencies import get_db

router = APIRouter(prefix="/analyst", tags=["analyst"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=AnalystSummaryResponse)
def analyst_summary(
    db: DbSession,
    limit: int = Query(default=5, ge=1, le=25),
) -> AnalystSummaryResponse:
    return AnalystEngine(db).summary(limit=limit)


@router.get("/notes", response_model=list[AnalystNoteResponse])
def list_analyst_notes(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> object:
    return AnalystEngine(db).list_notes(limit=limit)


@router.post("/trades/{trade_id}/review", response_model=AnalystNoteResponse)
def review_trade(trade_id: str, db: DbSession) -> object:
    try:
        note = AnalystEngine(db).review_trade(trade_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    db.refresh(note)
    return note


@router.post("/trades/{trade_id}/similarity", response_model=PatternSimilarityResponse)
def pattern_similarity(
    trade_id: str,
    db: DbSession,
    limit: int = Query(default=5, ge=1, le=25),
) -> PatternSimilarityResponse:
    try:
        result = AnalystEngine(db).pattern_similarity(trade_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/risk-anomalies/scan", response_model=AnalystScanResponse)
def scan_risk_anomalies(
    payload: AnalystScanRequest,
    db: DbSession,
) -> AnalystScanResponse:
    result = AnalystEngine(db).scan_risk_anomalies(
        strategy=payload.strategy,
        limit=payload.limit,
    )
    db.commit()
    return result


@router.post("/strategy-degradation/scan", response_model=AnalystScanResponse)
def scan_strategy_degradation(
    payload: AnalystScanRequest,
    db: DbSession,
) -> AnalystScanResponse:
    result = AnalystEngine(db).scan_strategy_degradation(
        strategy=payload.strategy,
        limit=payload.limit,
    )
    db.commit()
    return result
