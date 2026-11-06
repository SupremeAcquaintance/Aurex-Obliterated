from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.config.settings import get_settings
from aurex.execution_engine.evidence_collection import PaperEvidenceCollectionStatusService
from aurex.execution_engine.evidence_import import (
    PaperEvidenceCsvImporter,
    paper_evidence_template_csv,
)
from aurex.execution_engine.paper import PaperExecutionEngine
from aurex.execution_engine.schemas import (
    CloseTradeRequest,
    PaperEvidenceCollectionStatusResponse,
    PaperEvidenceCsvImportRequest,
    PaperEvidenceCsvPreflightResponse,
    PaperEvidenceImportBatchResponse,
    PaperResetResponse,
    TradeResponse,
)
from aurex.live_deployment.service import LiveMicroDeploymentService

router = APIRouter(prefix="/paper", tags=["paper"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/close-trade", response_model=TradeResponse)
def close_trade(payload: CloseTradeRequest, db: DbSession) -> object:
    try:
        trade = PaperExecutionEngine(db, get_settings()).close_trade(
            trade_id=payload.trade_id,
            exit_price=payload.exit_price,
            close_reason=payload.close_reason,
            fees=payload.fees,
            slippage=payload.slippage,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.commit()
    db.refresh(trade)
    return trade


@router.post("/evidence/preflight-csv", response_model=PaperEvidenceCsvPreflightResponse)
def preflight_paper_evidence_csv(
    payload: PaperEvidenceCsvImportRequest,
    db: DbSession,
) -> dict[str, object]:
    try:
        plan = LiveMicroDeploymentService(db, get_settings()).get_or_create_default_plan()
        return PaperEvidenceCsvImporter(db).preflight_csv(
            payload,
            strategy_scope=plan.strategy,
            symbol_scope=list(plan.symbols or []),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/evidence/import-csv", response_model=PaperEvidenceImportBatchResponse)
def import_paper_evidence_csv(payload: PaperEvidenceCsvImportRequest, db: DbSession) -> object:
    try:
        batch = PaperEvidenceCsvImporter(db).import_csv(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.commit()
    db.refresh(batch)
    return batch


@router.get("/evidence/imports", response_model=list[PaperEvidenceImportBatchResponse])
def list_paper_evidence_imports(
    db: DbSession,
    limit: int = Query(default=25, ge=1, le=500),
) -> list[object]:
    return PaperEvidenceCsvImporter(db).list_batches(limit=limit)


@router.get("/evidence/imports/{batch_id}", response_model=PaperEvidenceImportBatchResponse)
def get_paper_evidence_import(batch_id: str, db: DbSession) -> object:
    batch = PaperEvidenceCsvImporter(db).get_batch(batch_id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper evidence import batch not found",
        )
    return batch


@router.get(
    "/evidence/collection-status",
    response_model=PaperEvidenceCollectionStatusResponse,
)
def paper_evidence_collection_status(db: DbSession) -> dict[str, object]:
    status_payload = PaperEvidenceCollectionStatusService(db, get_settings()).status()
    db.commit()
    return status_payload


@router.get("/evidence/template.csv")
def paper_evidence_import_template() -> Response:
    return Response(
        content=paper_evidence_template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="aurex-paper-evidence-template.csv"'},
    )


@router.post("/reset", response_model=PaperResetResponse)
def reset_paper(db: DbSession) -> dict[str, object]:
    result = PaperExecutionEngine(db, get_settings()).reset_paper()
    db.commit()
    return result
