from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.strategy_engine.mkt_import import (
    import_mkt_research_database,
    mkt_research_intake_readiness,
    mkt_research_intake_runbook,
    preflight_mkt_research_database,
)
from aurex.strategy_engine.schemas import (
    MktResearchImportPreflightResponse,
    MktResearchImportRequest,
    MktResearchImportResponse,
    MktResearchIntakeReadinessResponse,
    MktResearchIntakeRunbookResponse,
    StrategyComparisonResponse,
    StrategyConfigResponse,
    StrategyConfigUpdate,
    StrategyResearchBacktestRequest,
    StrategyResearchBacktestResponse,
    StrategyResearchCandidateCreate,
    StrategyResearchCandidateResponse,
    StrategyResearchEvidenceResponse,
    StrategyResearchObservationCreate,
    StrategyResearchObservationResponse,
    StrategyResearchReadinessQueueResponse,
)
from aurex.strategy_engine.service import (
    StrategyPortfolioService,
    research_candidate_response,
    strategy_config_response,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[StrategyConfigResponse])
def list_strategies(db: DbSession) -> object:
    return [
        strategy_config_response(config)
        for config in StrategyPortfolioService(db).list_configs()
    ]


@router.get("/comparison", response_model=StrategyComparisonResponse)
def strategy_comparison(db: DbSession) -> StrategyComparisonResponse:
    return StrategyPortfolioService(db).strategy_comparison()


@router.get("/research-candidates", response_model=list[StrategyResearchCandidateResponse])
def list_research_candidates(db: DbSession) -> object:
    return StrategyPortfolioService(db).list_research_candidates()


@router.get(
    "/research-candidates/readiness-queue",
    response_model=StrategyResearchReadinessQueueResponse,
)
def research_candidate_readiness_queue(
    db: DbSession,
    limit: int = 25,
) -> object:
    return StrategyPortfolioService(db).research_readiness_queue(limit=limit)


@router.post("/research-candidates", response_model=StrategyResearchCandidateResponse)
def register_research_candidate(
    payload: StrategyResearchCandidateCreate,
    db: DbSession,
) -> object:
    try:
        candidate = StrategyPortfolioService(db).register_research_candidate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(candidate)
    return research_candidate_response(candidate, len(candidate.observations or []))


@router.post(
    "/research-candidates/{candidate_id}/backtest",
    response_model=StrategyResearchBacktestResponse,
)
def run_research_candidate_backtest(
    candidate_id: str,
    payload: StrategyResearchBacktestRequest,
    db: DbSession,
) -> StrategyResearchBacktestResponse:
    try:
        result = StrategyPortfolioService(db).run_research_backtest(candidate_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return result


@router.get(
    "/research-candidates/{candidate_id}/evidence",
    response_model=StrategyResearchEvidenceResponse,
)
def get_research_candidate_evidence(
    candidate_id: str,
    db: DbSession,
    observation_limit: int = 50,
    backtest_limit: int = 10,
) -> object:
    try:
        return StrategyPortfolioService(db).research_evidence_for_candidate(
            candidate_id,
            observation_limit=observation_limit,
            backtest_limit=backtest_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/research-candidates/mkt-intake-readiness",
    response_model=MktResearchIntakeReadinessResponse,
)
def check_mkt_research_intake_readiness(
    payload: MktResearchImportRequest,
) -> MktResearchIntakeReadinessResponse:
    try:
        return mkt_research_intake_readiness(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/research-candidates/mkt-intake-runbook",
    response_model=MktResearchIntakeRunbookResponse,
)
def build_mkt_research_intake_runbook(
    payload: MktResearchImportRequest,
) -> MktResearchIntakeRunbookResponse:
    try:
        return mkt_research_intake_runbook(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/research-candidates/preflight-mkt",
    response_model=MktResearchImportPreflightResponse,
)
def preflight_mkt_research_candidates(
    payload: MktResearchImportRequest,
) -> MktResearchImportPreflightResponse:
    try:
        return preflight_mkt_research_database(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/research-candidates/import-mkt", response_model=MktResearchImportResponse)
def import_mkt_research_candidates(
    payload: MktResearchImportRequest,
    db: DbSession,
) -> MktResearchImportResponse:
    try:
        result = import_mkt_research_database(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return result


@router.get(
    "/research-candidates/observations",
    response_model=list[StrategyResearchObservationResponse],
)
def list_research_observations(
    db: DbSession,
    candidate_id: str | None = None,
    limit: int = 50,
) -> object:
    return StrategyPortfolioService(db).list_research_observations(
        candidate_id=candidate_id,
        limit=limit,
    )


@router.post(
    "/research-candidates/observations",
    response_model=StrategyResearchObservationResponse,
)
def record_research_observation(
    payload: StrategyResearchObservationCreate,
    db: DbSession,
) -> object:
    try:
        observation = StrategyPortfolioService(db).record_research_observation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(observation)
    return observation


@router.patch("/{strategy}", response_model=StrategyConfigResponse)
def update_strategy(
    strategy: str,
    payload: StrategyConfigUpdate,
    db: DbSession,
) -> object:
    try:
        config = StrategyPortfolioService(db).update_config(strategy, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(config)
    return strategy_config_response(config)
