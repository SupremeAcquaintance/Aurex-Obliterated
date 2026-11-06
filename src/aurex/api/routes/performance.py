from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aurex.analytics_engine.schemas import EquityCurveResponse, PerformanceSummaryResponse
from aurex.analytics_engine.service import AnalyticsEngine
from aurex.api.dependencies import get_db

router = APIRouter(prefix="/performance", tags=["performance"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=PerformanceSummaryResponse)
def performance_summary(db: DbSession) -> object:
    return AnalyticsEngine(db).performance_summary()


@router.get("/equity-curve", response_model=EquityCurveResponse)
def equity_curve(
    db: DbSession,
    limit: int = Query(default=250, ge=1, le=1000),
) -> EquityCurveResponse:
    return AnalyticsEngine(db).equity_curve(limit=limit)
