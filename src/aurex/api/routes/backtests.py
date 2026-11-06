from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.backtest_engine.datasets import (
    OhlcvDatasetLab,
    dataset_response,
    preflight_ohlcv_dataset,
)
from aurex.backtest_engine.eligibility import paper_backtest_eligibility
from aurex.backtest_engine.parity import (
    BacktestParityLab,
    parity_record_response,
    preflight_tradingview_export_manifest,
)
from aurex.backtest_engine.reference_replay import (
    ReferenceReplayEvidenceLab,
    reference_replay_record_response,
    reference_replay_summary_response,
    run_reference_replay,
)
from aurex.backtest_engine.reference_validation import (
    ReferenceReplayValidationLab,
    reference_validation_record_response,
)
from aurex.backtest_engine.schemas import (
    BacktestPaperEligibilityResponse,
    BacktestParityAuditResponse,
    BacktestParityExportManifestRequest,
    BacktestParityExportManifestResponse,
    BacktestParityRequest,
    BacktestParityResponse,
    BacktestProtocolCreate,
    BacktestProtocolResponse,
    BacktestReportCreate,
    BacktestReportCsvPreflightResponse,
    BacktestReportCsvRequest,
    BacktestRunManifestResponse,
    BacktestRunResponse,
    BacktestStrategySetupResponse,
    BacktestTradeResponse,
    BacktestTradingViewRunPackageResponse,
    CsvImportRequest,
    OhlcvDatasetAuditResponse,
    OhlcvDatasetCsvRequest,
    OhlcvDatasetPreflightResponse,
    OhlcvDatasetResponse,
    ReferenceReplayAuditResponse,
    ReferenceReplayRequest,
    ReferenceReplayResponse,
    ReferenceReplaySummaryResponse,
    ReferenceReplayValidationAuditResponse,
    ReferenceReplayValidationRequest,
    ReferenceReplayValidationResponse,
    TradeCsvImportResponse,
    WalkForwardPlanRequest,
    WalkForwardPlanResponse,
)
from aurex.backtest_engine.service import (
    BacktestLab,
    backtest_protocol_response,
    load_trade_csv,
    plan_walk_forward_windows,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/protocols",
    response_model=BacktestProtocolResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_backtest_protocol(
    payload: BacktestProtocolCreate,
    db: DbSession,
) -> BacktestProtocolResponse:
    try:
        protocol = BacktestLab(db).register_protocol(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(protocol)
    return BacktestProtocolResponse.model_validate(backtest_protocol_response(protocol))


@router.get("/protocols", response_model=list[BacktestProtocolResponse])
def list_backtest_protocols(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BacktestProtocolResponse]:
    return [
        BacktestProtocolResponse.model_validate(backtest_protocol_response(protocol))
        for protocol in BacktestLab(db).list_protocols(limit=limit)
    ]


@router.get("/protocols/{protocol_id}", response_model=BacktestProtocolResponse)
def get_backtest_protocol(
    protocol_id: str,
    db: DbSession,
) -> BacktestProtocolResponse:
    protocol = BacktestLab(db).get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest protocol not found",
        )
    return BacktestProtocolResponse.model_validate(backtest_protocol_response(protocol))


@router.get(
    "/protocols/{protocol_id}/run-manifest",
    response_model=BacktestRunManifestResponse,
)
def get_backtest_run_manifest(
    protocol_id: str,
    db: DbSession,
) -> BacktestRunManifestResponse:
    lab = BacktestLab(db)
    protocol = lab.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest protocol not found",
        )
    return BacktestRunManifestResponse.model_validate(lab.run_manifest(protocol))


@router.get(
    "/protocols/{protocol_id}/tradingview-run-package",
    response_model=BacktestTradingViewRunPackageResponse,
)
def get_backtest_tradingview_run_package(
    protocol_id: str,
    db: DbSession,
) -> BacktestTradingViewRunPackageResponse:
    lab = BacktestLab(db)
    protocol = lab.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest protocol not found",
        )
    return BacktestTradingViewRunPackageResponse.model_validate(
        lab.tradingview_run_package(protocol)
    )


@router.post("/window-plan", response_model=WalkForwardPlanResponse)
def create_walk_forward_window_plan(
    payload: WalkForwardPlanRequest,
) -> WalkForwardPlanResponse:
    try:
        return plan_walk_forward_windows(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/ohlcv/preflight-csv",
    response_model=OhlcvDatasetPreflightResponse,
)
def preflight_ohlcv_csv(
    payload: OhlcvDatasetCsvRequest,
) -> OhlcvDatasetPreflightResponse:
    try:
        return preflight_ohlcv_dataset(payload).response
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/ohlcv/import-csv",
    response_model=OhlcvDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_ohlcv_csv(
    payload: OhlcvDatasetCsvRequest,
    db: DbSession,
) -> OhlcvDatasetResponse:
    try:
        dataset, reused_existing = OhlcvDatasetLab(db).import_csv(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(dataset)
    return dataset_response(dataset, reused_existing=reused_existing)


@router.get("/ohlcv/datasets", response_model=list[OhlcvDatasetResponse])
def list_ohlcv_datasets(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[OhlcvDatasetResponse]:
    return [
        dataset_response(dataset)
        for dataset in OhlcvDatasetLab(db).list_datasets(limit=limit)
    ]


@router.get(
    "/ohlcv/datasets/{dataset_id}/audit",
    response_model=OhlcvDatasetAuditResponse,
)
def audit_ohlcv_dataset(
    dataset_id: str,
    db: DbSession,
) -> OhlcvDatasetAuditResponse:
    lab = OhlcvDatasetLab(db)
    dataset = lab.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OHLCV dataset not found",
        )
    return lab.audit(dataset)


@router.get("/ohlcv/datasets/{dataset_id}", response_model=OhlcvDatasetResponse)
def get_ohlcv_dataset(
    dataset_id: str,
    db: DbSession,
) -> OhlcvDatasetResponse:
    dataset = OhlcvDatasetLab(db).get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OHLCV dataset not found",
        )
    return dataset_response(dataset)


@router.post(
    "/reference-replay/preflight",
    response_model=ReferenceReplayResponse,
)
def preflight_reference_replay(
    payload: ReferenceReplayRequest,
    db: DbSession,
) -> ReferenceReplayResponse:
    try:
        return run_reference_replay(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/reference-replay/runs",
    response_model=ReferenceReplayResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_reference_replay(
    payload: ReferenceReplayRequest,
    db: DbSession,
) -> ReferenceReplayResponse:
    try:
        record, reused_existing = ReferenceReplayEvidenceLab(db).record(payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(record)
    return reference_replay_record_response(
        record,
        reused_existing=reused_existing,
    )


@router.get(
    "/reference-replay/runs",
    response_model=list[ReferenceReplaySummaryResponse],
)
def list_reference_replay_runs(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ReferenceReplaySummaryResponse]:
    return [
        reference_replay_summary_response(record)
        for record in ReferenceReplayEvidenceLab(db).list_runs(limit=limit)
    ]


@router.get(
    "/reference-replay/runs/{reference_replay_run_id}/audit",
    response_model=ReferenceReplayAuditResponse,
)
def audit_reference_replay_run(
    reference_replay_run_id: str,
    db: DbSession,
) -> ReferenceReplayAuditResponse:
    lab = ReferenceReplayEvidenceLab(db)
    record = lab.get_run(reference_replay_run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference replay run not found",
        )
    return lab.audit(record)


@router.get(
    "/reference-replay/runs/{reference_replay_run_id}",
    response_model=ReferenceReplayResponse,
)
def get_reference_replay_run(
    reference_replay_run_id: str,
    db: DbSession,
) -> ReferenceReplayResponse:
    record = ReferenceReplayEvidenceLab(db).get_run(reference_replay_run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference replay run not found",
        )
    return reference_replay_record_response(record)


@router.post(
    "/reference-replay/validations/preflight",
    response_model=ReferenceReplayValidationResponse,
)
def preflight_reference_replay_validation(
    payload: ReferenceReplayValidationRequest,
    db: DbSession,
) -> ReferenceReplayValidationResponse:
    try:
        return ReferenceReplayValidationLab(db).preflight(payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/reference-replay/validations",
    response_model=ReferenceReplayValidationResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_reference_replay_validation(
    payload: ReferenceReplayValidationRequest,
    db: DbSession,
) -> ReferenceReplayValidationResponse:
    try:
        record, reused_existing = ReferenceReplayValidationLab(db).record(payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(record)
    return reference_validation_record_response(
        record,
        reused_existing=reused_existing,
        mutates_ledger=True,
    )


@router.get(
    "/reference-replay/validations",
    response_model=list[ReferenceReplayValidationResponse],
)
def list_reference_replay_validations(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ReferenceReplayValidationResponse]:
    return [
        reference_validation_record_response(record)
        for record in ReferenceReplayValidationLab(db).list_runs(limit=limit)
    ]


@router.get(
    "/reference-replay/validations/{validation_id}/audit",
    response_model=ReferenceReplayValidationAuditResponse,
)
def audit_reference_replay_validation(
    validation_id: str,
    db: DbSession,
) -> ReferenceReplayValidationAuditResponse:
    lab = ReferenceReplayValidationLab(db)
    record = lab.get_run(validation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference replay validation not found",
        )
    return lab.audit(record)


@router.get(
    "/reference-replay/validations/{validation_id}",
    response_model=ReferenceReplayValidationResponse,
)
def get_reference_replay_validation(
    validation_id: str,
    db: DbSession,
) -> ReferenceReplayValidationResponse:
    record = ReferenceReplayValidationLab(db).get_run(validation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference replay validation not found",
        )
    return reference_validation_record_response(record)


@router.post(
    "/parity/export-manifest/preflight",
    response_model=BacktestParityExportManifestResponse,
)
def preflight_backtest_parity_export_manifest(
    payload: BacktestParityExportManifestRequest,
    db: DbSession,
) -> BacktestParityExportManifestResponse:
    try:
        return preflight_tradingview_export_manifest(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/parity/preflight",
    response_model=BacktestParityResponse,
)
def preflight_backtest_parity(
    payload: BacktestParityRequest,
    db: DbSession,
) -> BacktestParityResponse:
    try:
        return BacktestParityLab(db).preflight(payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/parity/runs",
    response_model=BacktestParityResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_backtest_parity(
    payload: BacktestParityRequest,
    db: DbSession,
) -> BacktestParityResponse:
    try:
        record, reused_existing = BacktestParityLab(db).record(payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(record)
    return parity_record_response(record, reused_existing=reused_existing)


@router.get(
    "/parity/runs",
    response_model=list[BacktestParityResponse],
)
def list_backtest_parity_runs(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BacktestParityResponse]:
    return [
        parity_record_response(record)
        for record in BacktestParityLab(db).list_runs(limit=limit)
    ]


@router.get(
    "/parity/runs/{parity_run_id}/audit",
    response_model=BacktestParityAuditResponse,
)
def audit_backtest_parity_run(
    parity_run_id: str,
    db: DbSession,
) -> BacktestParityAuditResponse:
    lab = BacktestParityLab(db)
    record = lab.get_run(parity_run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest parity run not found",
        )
    return lab.audit(record)


@router.get(
    "/parity/runs/{parity_run_id}",
    response_model=BacktestParityResponse,
)
def get_backtest_parity_run(
    parity_run_id: str,
    db: DbSession,
) -> BacktestParityResponse:
    record = BacktestParityLab(db).get_run(parity_run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest parity run not found",
        )
    return parity_record_response(record)


@router.post("/reports", response_model=BacktestRunResponse, status_code=status.HTTP_201_CREATED)
def create_backtest_report(payload: BacktestReportCreate, db: DbSession) -> object:
    if payload.source_format == "tradingview":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "TradingView evidence must use /backtests/reports/import-csv so "
                "Aurex parses the original completed-trades export"
            ),
        )
    try:
        run = BacktestLab(db).create_report(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(run)
    return run


@router.get("/reports", response_model=list[BacktestRunResponse])
def list_backtest_reports(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[object]:
    return BacktestLab(db).list_runs(limit=limit)


@router.get("/strategy-setup", response_model=BacktestStrategySetupResponse)
def get_backtest_strategy_setup(
    db: DbSession,
    strategy: str = Query(default="trend_pullback_v1", min_length=1, max_length=100),
    symbol: str = Query(default="BTCUSDT", min_length=1, max_length=64),
    timeframe: str = Query(default="15m", min_length=1, max_length=32),
    venue: str = Query(default="BINANCE", min_length=1, max_length=32),
) -> BacktestStrategySetupResponse:
    try:
        return BacktestStrategySetupResponse.model_validate(
            BacktestLab(db).strategy_setup(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                venue=venue,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/paper-eligibility",
    response_model=BacktestPaperEligibilityResponse,
)
def get_backtest_paper_eligibility(
    db: DbSession,
    strategy: str = Query(default="trend_pullback_v1", min_length=1, max_length=100),
    symbol: str = Query(default="BTCUSDT", min_length=1, max_length=64),
) -> BacktestPaperEligibilityResponse:
    eligibility = paper_backtest_eligibility(
        db,
        strategy=strategy,
        symbol=symbol,
    )
    return BacktestPaperEligibilityResponse(
        approved=eligibility.approved,
        reason=eligibility.reason,
        backtest_run_id=eligibility.backtest_run_id,
        evidence_snapshot=eligibility.evidence_snapshot,
    )


@router.get("/reports/{run_id}", response_model=BacktestRunResponse)
def get_backtest_report(run_id: str, db: DbSession) -> object:
    run = BacktestLab(db).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return run


@router.get(
    "/reports/{run_id}/trades",
    response_model=list[BacktestTradeResponse],
)
def list_backtest_report_trades(
    run_id: str,
    db: DbSession,
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[object]:
    lab = BacktestLab(db)
    if lab.get_run(run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return lab.list_run_trades(run_id, limit=limit, offset=offset)


@router.get("/reports/{run_id}/csv")
def export_backtest_report_csv(run_id: str, db: DbSession) -> Response:
    run = BacktestLab(db).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    try:
        csv_text = BacktestLab(db).export_report_csv(run)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(content=csv_text, media_type="text/csv")


@router.post(
    "/reports/preflight-csv",
    response_model=BacktestReportCsvPreflightResponse,
)
def preflight_backtest_report_csv(
    payload: BacktestReportCsvRequest,
    db: DbSession,
) -> BacktestReportCsvPreflightResponse:
    try:
        return BacktestLab(db).preflight_report_csv(payload).response
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/reports/import-csv",
    response_model=BacktestRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_backtest_report_csv(payload: BacktestReportCsvRequest, db: DbSession) -> object:
    try:
        run = BacktestLab(db).create_report_from_csv(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(run)
    return run


@router.get("/report-template.csv")
def backtest_report_template_csv() -> Response:
    csv_text = (
        "realized_pl,closed_at,market_regime,strategy,symbol,equity,r_multiple\n"
        "12.50,2026-01-02T14:30:00Z,TRENDING_UP,trend_pullback_v1,BTCUSDT,"
        "1012.50,2.5\n"
    )
    return Response(content=csv_text, media_type="text/csv")


@router.post("/trades/import-csv", response_model=TradeCsvImportResponse)
def import_trade_csv(payload: CsvImportRequest) -> TradeCsvImportResponse:
    try:
        trades = load_trade_csv(payload.csv_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TradeCsvImportResponse(trades=len(trades), parsed_trades=trades)
