import ast
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.db.base import utc_now
from aurex.db.models import (
    PredictionContract,
    PredictionEvidenceEvent,
    PredictionFill,
    PredictionOrder,
    PredictionOrderIntent,
    PredictionPosition,
    PredictionReconciliationReport,
    PredictionSettlement,
    StrategyResearchBacktestRun,
    StrategyResearchCandidate,
)
from aurex.domain.enums import (
    PredictionMarketEvidenceKind,
    PredictionMarketOrderStatus,
    PredictionMarketPositionStatus,
    PredictionMarketSide,
    PredictionMarketStatus,
    ReconciliationStatus,
    StrategyResearchSource,
    StrategyResearchStatus,
)
from aurex.prediction_market.calculations import (
    calculate_binary_entry_cost,
    estimate_binary_contract_fee,
)
from aurex.prediction_market.contract_csv import (
    PredictionContractSnapshotCsvImporter,
    prediction_contract_snapshot_template_csv,
)
from aurex.prediction_market.mkt_db import PredictionContractSnapshotMktDbImporter
from aurex.prediction_market.paper import (
    PredictionContractSnapshot,
    PredictionFillModel,
    PredictionMarketPaperEngine,
    PredictionOrderRequest,
    PredictionRiskLimits,
    ensure_utc,
    hash_evidence_payload,
    quote_freshness_snapshot,
    quote_spread_snapshot,
)
from aurex.prediction_market.schemas import (
    PredictionContractResponse,
    PredictionContractSnapshotCsvImportResponse,
    PredictionContractSnapshotCsvPreflightResponse,
    PredictionContractSnapshotCsvRequest,
    PredictionContractSnapshotMktDbDiscoveryCandidateResponse,
    PredictionContractSnapshotMktDbDiscoveryRequest,
    PredictionContractSnapshotMktDbDiscoveryResponse,
    PredictionContractSnapshotMktDbImportResponse,
    PredictionContractSnapshotMktDbInventoryResponse,
    PredictionContractSnapshotMktDbInventoryTableResponse,
    PredictionContractSnapshotMktDbPreflightResponse,
    PredictionContractSnapshotMktDbReadinessResponse,
    PredictionContractSnapshotMktDbRequest,
    PredictionContractSnapshotMktDonorBootstrapRequest,
    PredictionContractSnapshotMktDonorBootstrapResponse,
    PredictionContractSnapshotMktDonorCollectionQualityCheckResponse,
    PredictionContractSnapshotMktDonorCollectionQualityResponse,
    PredictionContractSnapshotMktDonorCollectionStatusRequest,
    PredictionContractSnapshotMktDonorCollectionStatusResponse,
    PredictionContractSnapshotMktDonorCollectionTargetResponse,
    PredictionContractSnapshotMktDonorLaunchHealthCheckResponse,
    PredictionContractSnapshotMktDonorLaunchHealthResponse,
    PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse,
    PredictionContractSnapshotMktDonorLaunchPreflightRequest,
    PredictionContractSnapshotMktDonorLaunchPreflightResponse,
    PredictionContractSnapshotMktDonorReadinessRequest,
    PredictionContractSnapshotMktDonorReadinessResponse,
    PredictionContractSnapshotMktDonorRunbookRequest,
    PredictionContractSnapshotMktDonorRunbookResponse,
    PredictionContractSnapshotMktDonorRunbookStepResponse,
    PredictionContractSnapshotMktRuntimePathCandidateResponse,
    PredictionContractSnapshotMktRuntimeSafetyCheckResponse,
    PredictionContractSnapshotMktRuntimeSafetyCredentialResponse,
    PredictionContractSnapshotMktRuntimeSafetyRequest,
    PredictionContractSnapshotMktRuntimeSafetyResponse,
    PredictionContractSnapshotRequest,
    PredictionEvidenceEventResponse,
    PredictionFillModelRequest,
    PredictionMarketSummaryResponse,
    PredictionOrderCancelRequest,
    PredictionOrderIntentCreateRequest,
    PredictionOrderIntentResponse,
    PredictionOrderResponse,
    PredictionOrderSubmissionResponse,
    PredictionPaperDemoBatchAuditRecordResponse,
    PredictionPaperDemoBatchAuditResponse,
    PredictionPaperDemoBatchPreflightRequest,
    PredictionPaperDemoBatchPreflightResponse,
    PredictionPaperDemoBatchRunRequest,
    PredictionPaperDemoBatchRunResponse,
    PredictionPaperDemoCampaignAuditRecordResponse,
    PredictionPaperDemoCampaignAuditResponse,
    PredictionPaperDemoEvidenceLedgerResponse,
    PredictionPaperDemoEvidenceRecordResponse,
    PredictionPaperDemoMktDbCampaignManifestResponse,
    PredictionPaperDemoMktDbCampaignPreflightRequest,
    PredictionPaperDemoMktDbCampaignPreflightResponse,
    PredictionPaperDemoMktDbCampaignProjectionResponse,
    PredictionPaperDemoMktDbCampaignReadinessResponse,
    PredictionPaperDemoMktDbCampaignRunRequest,
    PredictionPaperDemoMktDbCampaignRunResponse,
    PredictionPaperDemoProgressResponse,
    PredictionPaperDemoReadinessResponse,
    PredictionPaperDemoRunbookResponse,
    PredictionPaperDemoRunbookStepResponse,
    PredictionPaperDemoRunRequest,
    PredictionPaperDemoRunResponse,
    PredictionPositionResponse,
    PredictionReconciliationReportResponse,
    PredictionSettlementRequest,
    PredictionSettlementResponse,
)
from aurex.strategy_engine.mkt_import import mkt_research_intake_runbook
from aurex.strategy_engine.schemas import MktResearchImportRequest

router = APIRouter(prefix="/prediction-market", tags=["prediction-market"])
DbSession = Annotated[Session, Depends(get_db)]


def engine(db: Session) -> PredictionMarketPaperEngine:
    return PredictionMarketPaperEngine(db)


@router.get("/summary", response_model=PredictionMarketSummaryResponse)
def prediction_market_summary(db: DbSession) -> PredictionMarketSummaryResponse:
    latest_reconciliation = db.execute(
        select(PredictionReconciliationReport)
        .order_by(PredictionReconciliationReport.reconciled_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return PredictionMarketSummaryResponse(
        contracts=count_rows(db, PredictionContract),
        order_intents=count_rows(db, PredictionOrderIntent),
        orders=count_rows(db, PredictionOrder),
        fills=count_rows(db, PredictionFill),
        open_positions=count_positions(db, PredictionMarketPositionStatus.OPEN),
        settled_positions=count_positions(db, PredictionMarketPositionStatus.SETTLED),
        rejected_intents=count_intents(db, PredictionMarketOrderStatus.REJECTED),
        latest_reconciliation=latest_reconciliation,
        live_execution_enabled=False,
    )


@router.get("/paper/demo-readiness", response_model=PredictionPaperDemoReadinessResponse)
def prediction_paper_demo_readiness(db: DbSession) -> PredictionPaperDemoReadinessResponse:
    return build_prediction_paper_demo_readiness(db)


@router.get("/paper/demo-progress", response_model=PredictionPaperDemoProgressResponse)
def prediction_paper_demo_progress(db: DbSession) -> PredictionPaperDemoProgressResponse:
    return build_prediction_paper_demo_progress(db)


@router.get("/paper/demo-runbook", response_model=PredictionPaperDemoRunbookResponse)
def prediction_paper_demo_runbook(db: DbSession) -> PredictionPaperDemoRunbookResponse:
    return build_prediction_paper_demo_runbook(db)


@router.get("/paper/demo-ledger", response_model=PredictionPaperDemoEvidenceLedgerResponse)
def prediction_paper_demo_ledger(
    db: DbSession,
    limit: int = 50,
) -> PredictionPaperDemoEvidenceLedgerResponse:
    return build_prediction_paper_demo_ledger(db, limit=limit)


@router.get("/paper/demo-campaigns", response_model=PredictionPaperDemoCampaignAuditResponse)
def prediction_paper_demo_campaigns(
    db: DbSession,
    limit: int = 20,
) -> PredictionPaperDemoCampaignAuditResponse:
    return build_prediction_paper_demo_campaign_audit(db, limit=limit)


@router.get("/paper/demo-batches", response_model=PredictionPaperDemoBatchAuditResponse)
def prediction_paper_demo_batches(
    db: DbSession,
    limit: int = 20,
) -> PredictionPaperDemoBatchAuditResponse:
    return build_prediction_paper_demo_batch_audit(db, limit=limit)


@router.post("/paper/demo-run", response_model=PredictionPaperDemoRunResponse)
def run_prediction_paper_demo(
    payload: PredictionPaperDemoRunRequest,
    db: DbSession,
) -> object:
    try:
        result = execute_prediction_paper_demo(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    for key in ("intent", "order", "fill", "position", "settlement", "reconciliation"):
        if result.get(key) is not None:
            db.refresh(result[key])
    return result


@router.post(
    "/paper/demo-batch-preflight",
    response_model=PredictionPaperDemoBatchPreflightResponse,
)
def preflight_prediction_paper_demo_batch(
    payload: PredictionPaperDemoBatchPreflightRequest,
    db: DbSession,
) -> object:
    return build_prediction_paper_demo_batch_preflight(db, payload)


@router.post("/paper/demo-batch-run", response_model=PredictionPaperDemoBatchRunResponse)
def run_prediction_paper_demo_batch(
    payload: PredictionPaperDemoBatchRunRequest,
    db: DbSession,
) -> object:
    try:
        preflight_hash = validate_prediction_paper_demo_batch_preflight_review(
            db,
            payload,
        )
        result = execute_prediction_paper_demo_batch(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    result["preflight_hash"] = preflight_hash
    result["reviewed_preflight_hash"] = payload.reviewed_preflight_hash
    result["batch_evidence"] = record_prediction_paper_demo_batch_evidence(
        db,
        payload=payload,
        batch=result,
        preflight_hash=preflight_hash,
    )
    db.commit()
    return result


@router.post(
    "/paper/demo-mkt-db-campaign-readiness",
    response_model=PredictionPaperDemoMktDbCampaignReadinessResponse,
)
def prediction_paper_demo_mkt_db_campaign_readiness(
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
    db: DbSession,
) -> PredictionPaperDemoMktDbCampaignReadinessResponse:
    return build_prediction_paper_demo_mkt_db_campaign_readiness(db, payload)


@router.post(
    "/paper/demo-mkt-db-campaign-manifest",
    response_model=PredictionPaperDemoMktDbCampaignManifestResponse,
)
def prediction_paper_demo_mkt_db_campaign_manifest(
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
    db: DbSession,
) -> PredictionPaperDemoMktDbCampaignManifestResponse:
    return build_prediction_paper_demo_mkt_db_campaign_manifest(db, payload)


@router.post(
    "/paper/demo-mkt-db-campaign-preflight",
    response_model=PredictionPaperDemoMktDbCampaignPreflightResponse,
)
def preflight_prediction_paper_demo_mkt_db_campaign(
    payload: PredictionPaperDemoMktDbCampaignPreflightRequest,
    db: DbSession,
) -> object:
    try:
        return build_prediction_paper_demo_mkt_db_campaign_preflight(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/paper/demo-mkt-db-campaign-run",
    response_model=PredictionPaperDemoMktDbCampaignRunResponse,
)
def run_prediction_paper_demo_mkt_db_campaign(
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
    db: DbSession,
) -> object:
    try:
        result = execute_prediction_paper_demo_mkt_db_campaign(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/contracts/snapshot", response_model=PredictionContractResponse)
def upsert_contract_snapshot(
    payload: PredictionContractSnapshotRequest,
    db: DbSession,
) -> object:
    try:
        contract = engine(db).upsert_contract_snapshot(
            PredictionContractSnapshot(**payload.model_dump())
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(contract)
    return contract


@router.post(
    "/contracts/preflight-csv",
    response_model=PredictionContractSnapshotCsvPreflightResponse,
)
def preflight_contract_snapshots_csv(
    payload: PredictionContractSnapshotCsvRequest,
    db: DbSession,
) -> object:
    try:
        return PredictionContractSnapshotCsvImporter(db).preflight_csv(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/contracts/import-csv",
    response_model=PredictionContractSnapshotCsvImportResponse,
)
def import_contract_snapshots_csv(
    payload: PredictionContractSnapshotCsvRequest,
    db: DbSession,
) -> object:
    try:
        result = PredictionContractSnapshotCsvImporter(db).import_csv(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return result


def build_prediction_contract_mkt_db_readiness(
    db: Session,
    payload: PredictionContractSnapshotMktDbRequest,
) -> PredictionContractSnapshotMktDbReadinessResponse:
    db_path = Path(payload.db_path).expanduser()
    db_exists = db_path.exists()
    base = {
        "db_path": str(db_path),
        "source": payload.source.strip(),
        "source_reference": payload.source_reference.strip(),
        "query_summary": {
            "table": "markets",
            "status_filter": payload.status_filter,
            "limit": payload.limit,
            "min_volume": str(payload.min_volume) if payload.min_volume is not None else None,
            "require_settlement_value": payload.require_settlement_value,
        },
        "checked_at": utc_now(),
        "live_execution_enabled": False,
    }
    try:
        preflight = PredictionContractSnapshotMktDbImporter(db).preflight_db(payload)
    except ValueError as exc:
        error = str(exc)
        if not db_exists:
            readiness_status = "MISSING_DB"
            next_action = (
                "Create or export the My-Krypt-Trader SQLite database before campaign preflight."
            )
            markets_table_available = False
        elif "markets table" in error.lower():
            readiness_status = "MISSING_MARKETS_TABLE"
            next_action = (
                "Run My-Krypt-Trader market collection until the markets table exists."
            )
            markets_table_available = False
        else:
            readiness_status = "UNREADABLE_DB"
            next_action = "Fix the My-Krypt-Trader SQLite file before importing market rows."
            markets_table_available = None
        return PredictionContractSnapshotMktDbReadinessResponse(
            **base,
            status=readiness_status,
            data_ready=False,
            db_exists=db_exists,
            markets_table_available=markets_table_available,
            rows_received=0,
            importable_count=0,
            rejected_count=0,
            import_hash=None,
            analysis_summary={},
            error=error,
            next_action=next_action,
        )

    rows_received = int(preflight.get("rows_received") or 0)
    importable_count = int(preflight.get("importable_count") or 0)
    rejected_count = int(preflight.get("rejected_count") or 0)
    if importable_count > 0 and rejected_count > 0:
        readiness_status = "READY_WITH_REJECTIONS"
        next_action = "Review rejected rows, then run MKT DB campaign preflight."
    elif importable_count > 0:
        readiness_status = "READY"
        next_action = "Run MKT DB campaign preflight before any replay."
    elif rows_received > 0:
        readiness_status = "NO_IMPORTABLE_ROWS"
        next_action = (
            "Collect resolved MKT markets with settlement outcomes before campaign replay."
        )
    else:
        readiness_status = "NO_MARKET_ROWS"
        next_action = "Populate the My-Krypt-Trader markets table before campaign replay."

    return PredictionContractSnapshotMktDbReadinessResponse(
        **base,
        status=readiness_status,
        data_ready=importable_count > 0,
        db_exists=True,
        markets_table_available=True,
        rows_received=rows_received,
        importable_count=importable_count,
        rejected_count=rejected_count,
        import_hash=str(preflight.get("import_hash") or ""),
        analysis_summary=dict(preflight.get("analysis_summary") or {}),
        error=None,
        next_action=next_action,
    )


MKT_DB_INVENTORY_TABLES = [
    {
        "key": "markets",
        "table": "markets",
        "usable_for": "paper_replay",
        "resolved_where": (
            "settlement_value is not null "
            "or lower(coalesce(result, '')) in "
            "('yes', 'no', 'y', 'n', 'true', 'false', '1', '0')"
        ),
        "latest_columns": ["last_updated", "close_time"],
        "empty_action": "Run MKT market collection until markets rows are recorded.",
        "ready_action": "Use readiness/preflight before replaying resolved market rows.",
    },
    {
        "key": "alerts",
        "table": "alerts",
        "usable_for": "research_observations",
        "resolved_where": "coalesce(resolved, 0) = 1",
        "latest_columns": ["resolved_at", "created_at"],
        "empty_action": "Run MKT momentum scanning longer before importing research observations.",
        "ready_action": "Import alerts as research observations, not trusted strategy evidence.",
    },
    {
        "key": "whale_trades",
        "table": "whale_trades",
        "usable_for": "research_observations",
        "resolved_where": "coalesce(resolved, 0) = 1",
        "latest_columns": ["resolved_at", "created_at"],
        "empty_action": "Run MKT whale scanning longer before importing research observations.",
        "ready_action": (
            "Import whale rows as research observations, not trusted strategy evidence."
        ),
    },
    {
        "key": "crypto15m_signals",
        "table": "crypto15m_signals",
        "usable_for": "research_observations",
        "resolved_where": "coalesce(resolved, 0) = 1",
        "latest_columns": ["settled_at", "observed_at", "close_time"],
        "empty_action": "Run MKT 15-minute crypto signal recording before importing observations.",
        "ready_action": "Import resolved crypto15m rows as research observations.",
    },
    {
        "key": "bot_positions",
        "table": "bot_positions",
        "usable_for": "execution_history",
        "resolved_where": "coalesce(resolved, 0) = 1",
        "latest_columns": ["resolved_at", "last_updated", "created_at"],
        "empty_action": "No MKT execution history exists in this DB.",
        "ready_action": "Use only for reconciliation/audit context; Aurex live remains disabled.",
    },
    {
        "key": "trades",
        "table": "trades",
        "usable_for": "market_trade_feed",
        "resolved_where": None,
        "latest_columns": ["created_time"],
        "empty_action": "Run MKT trade-feed collection longer before using market context.",
        "ready_action": "Use as market-context evidence only.",
    },
    {
        "key": "market_snapshots",
        "table": "market_snapshots",
        "usable_for": "market_context",
        "resolved_where": None,
        "latest_columns": ["snapshot_at"],
        "empty_action": "Run MKT market collection longer before using market snapshots.",
        "ready_action": "Use as market-context evidence only.",
    },
    {
        "key": "crypto15m_ticks",
        "table": "crypto15m_ticks",
        "usable_for": "market_context",
        "resolved_where": None,
        "latest_columns": ["observed_at"],
        "empty_action": "Run MKT 15-minute crypto tick recording before using tick context.",
        "ready_action": "Use as market-context evidence only.",
    },
]

MKT_MIN_BACKTEST_REPLAY_ROWS = 100
MKT_MIN_BACKTEST_RESEARCH_ROWS = 100
MKT_COLLECTION_RECENT_WINDOW_SECONDS = 15 * 60


def build_prediction_contract_mkt_db_inventory(
    db: Session,
    payload: PredictionContractSnapshotMktDbRequest,
) -> PredictionContractSnapshotMktDbInventoryResponse:
    db_path = Path(payload.db_path).expanduser()
    checked_at = utc_now()
    markets_readiness = build_prediction_contract_mkt_db_readiness(db, payload)
    if not db_path.exists():
        return PredictionContractSnapshotMktDbInventoryResponse(
            db_path=str(db_path),
            status="MISSING_DB",
            db_exists=False,
            tables_available=0,
            total_rows=0,
            replay_table_ready=False,
            research_tables_ready=False,
            execution_history_ready=False,
            replay_candidate_count=0,
            research_candidate_count=0,
            markets_readiness=markets_readiness,
            tables=mkt_db_missing_inventory_tables(),
            missing_tables=[str(spec["table"]) for spec in MKT_DB_INVENTORY_TABLES],
            blockers=["mkt_sqlite_db_missing"],
            error=markets_readiness.error,
            next_action="Run My-Krypt-Trader until krypt-trader.db exists, then rerun inventory.",
            checked_at=checked_at,
            live_execution_enabled=False,
        )

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                mkt_db_inventory_table(conn, spec)
                for spec in MKT_DB_INVENTORY_TABLES
            ]
    except sqlite3.Error as exc:
        return PredictionContractSnapshotMktDbInventoryResponse(
            db_path=str(db_path),
            status="UNREADABLE_DB",
            db_exists=True,
            tables_available=0,
            total_rows=0,
            replay_table_ready=False,
            research_tables_ready=False,
            execution_history_ready=False,
            replay_candidate_count=0,
            research_candidate_count=0,
            markets_readiness=markets_readiness,
            tables=mkt_db_missing_inventory_tables(),
            missing_tables=[],
            blockers=["mkt_sqlite_db_unreadable"],
            error=str(exc),
            next_action="Fix or replace the MKT SQLite DB before import, manifest, or replay.",
            checked_at=checked_at,
            live_execution_enabled=False,
        )

    replay_candidate_count = int(markets_readiness.importable_count or 0)
    research_candidate_count = sum(
        int(table.resolved_count or 0)
        for table in tables
        if table.usable_for == "research_observations"
    )
    execution_history_ready = any(
        table.table in {"bot_positions"} and table.row_count > 0 for table in tables
    )
    total_rows = sum(table.row_count for table in tables)
    missing_tables = [table.table for table in tables if not table.exists]
    blockers: list[str] = []
    if not markets_readiness.markets_table_available:
        blockers.append("mkt_markets_table_missing")
    elif not markets_readiness.data_ready:
        blockers.append("mkt_no_resolved_replay_rows")
    if research_candidate_count == 0:
        blockers.append("mkt_research_tables_empty")

    replay_table_ready = markets_readiness.data_ready
    research_tables_ready = research_candidate_count > 0
    if replay_table_ready:
        inventory_status = "INVENTORY_REPLAY_READY"
        next_action = "Build a campaign manifest before replaying resolved MKT market rows."
    elif research_tables_ready:
        inventory_status = "INVENTORY_RESEARCH_ONLY"
        next_action = (
            "Import resolved MKT observations into the strategy lab while collecting replay rows."
        )
    elif total_rows > 0:
        inventory_status = "INVENTORY_COLLECTING"
        next_action = "Keep MKT collecting until resolved market or research rows are available."
    elif any(table.exists for table in tables):
        inventory_status = "INVENTORY_EMPTY_SCHEMA"
        next_action = "Run MKT longer in demo/dry-run mode so the schema receives rows."
    else:
        inventory_status = "INVENTORY_NO_SCHEMA"
        next_action = "Run MKT setup/startup so it initializes krypt-trader.db tables."

    return PredictionContractSnapshotMktDbInventoryResponse(
        db_path=str(db_path),
        status=inventory_status,
        db_exists=True,
        tables_available=sum(1 for table in tables if table.exists),
        total_rows=total_rows,
        replay_table_ready=replay_table_ready,
        research_tables_ready=research_tables_ready,
        execution_history_ready=execution_history_ready,
        replay_candidate_count=replay_candidate_count,
        research_candidate_count=research_candidate_count,
        markets_readiness=markets_readiness,
        tables=tables,
        missing_tables=missing_tables,
        blockers=blockers,
        error=None,
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


def mkt_db_missing_inventory_tables() -> (
    list[PredictionContractSnapshotMktDbInventoryTableResponse]
):
    return [
        PredictionContractSnapshotMktDbInventoryTableResponse(
            key=str(spec["key"]),
            table=str(spec["table"]),
            exists=False,
            row_count=0,
            resolved_count=None,
            latest_at=None,
            usable_for=str(spec["usable_for"]),
            next_action="Create/populate the MKT SQLite DB before this table can be inspected.",
        )
        for spec in MKT_DB_INVENTORY_TABLES
    ]


def mkt_db_inventory_table(
    conn: sqlite3.Connection,
    spec: dict[str, object],
) -> PredictionContractSnapshotMktDbInventoryTableResponse:
    table = str(spec["table"])
    if not sqlite_inventory_table_exists(conn, table):
        return PredictionContractSnapshotMktDbInventoryTableResponse(
            key=str(spec["key"]),
            table=table,
            exists=False,
            row_count=0,
            resolved_count=None,
            latest_at=None,
            usable_for=str(spec["usable_for"]),
            next_action="Run MKT until this table is created.",
        )

    row_count = sqlite_inventory_count(conn, table)
    resolved_where = spec.get("resolved_where")
    resolved_count = (
        sqlite_inventory_count(conn, table, str(resolved_where))
        if resolved_where
        else None
    )
    latest_at = sqlite_inventory_latest_at(
        conn,
        table,
        [str(column) for column in spec.get("latest_columns", [])],
    )
    next_action = (
        str(spec["ready_action"])
        if row_count > 0 and (resolved_count is None or resolved_count > 0)
        else str(spec["empty_action"])
    )
    return PredictionContractSnapshotMktDbInventoryTableResponse(
        key=str(spec["key"]),
        table=table,
        exists=True,
        row_count=row_count,
        resolved_count=resolved_count,
        latest_at=latest_at,
        usable_for=str(spec["usable_for"]),
        next_action=next_action,
    )


def sqlite_inventory_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select name from sqlite_master where type = 'table' and name = ?",
        (table,),
    ).fetchone()
    return row is not None


def sqlite_inventory_count(
    conn: sqlite3.Connection,
    table: str,
    where: str | None = None,
) -> int:
    sql = f"select count(*) from {table}"
    if where:
        sql = f"{sql} where {where}"
    return int(conn.execute(sql).fetchone()[0] or 0)


def sqlite_inventory_latest_at(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
) -> str | None:
    available_columns = sqlite_inventory_columns(conn, table)
    values: list[str] = []
    for column in columns:
        if column not in available_columns:
            continue
        value = conn.execute(f"select max(nullif({column}, '')) from {table}").fetchone()[0]
        if value:
            values.append(str(value))
    return max(values) if values else None


def sqlite_inventory_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info({table})").fetchall()}


def build_prediction_contract_mkt_db_discovery(
    db: Session,
    payload: PredictionContractSnapshotMktDbDiscoveryRequest,
) -> PredictionContractSnapshotMktDbDiscoveryResponse:
    checked_at = utc_now()
    candidate_paths, skipped_paths = discover_mkt_db_candidate_paths(payload)
    candidates: list[PredictionContractSnapshotMktDbDiscoveryCandidateResponse] = []
    for path in candidate_paths:
        stat = path.stat()
        readiness = build_prediction_contract_mkt_db_readiness(
            db,
            PredictionContractSnapshotMktDbRequest(
                db_path=str(path),
                source="my-krypt-trader",
                source_reference=f"{path}::markets",
                status_filter=payload.status_filter,
                limit=100,
                min_volume=payload.min_volume,
                require_settlement_value=payload.require_settlement_value,
            ),
        )
        candidates.append(
            PredictionContractSnapshotMktDbDiscoveryCandidateResponse(
                db_path=str(path),
                file_size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                readiness=readiness,
            )
        )

    ready_count = sum(1 for candidate in candidates if candidate.readiness.data_ready)
    if ready_count:
        next_action = "Select a ready MKT DB path, then run campaign readiness."
    elif candidates:
        next_action = "Inspect discovered DB blockers before campaign preflight."
    else:
        next_action = (
            "Run or export My-Krypt-Trader market collection so Aurex can find a SQLite DB."
        )
    return PredictionContractSnapshotMktDbDiscoveryResponse(
        search_roots=[str(Path(root).expanduser()) for root in payload.search_roots],
        candidate_count=len(candidates),
        ready_count=ready_count,
        candidates=candidates,
        skipped_paths=skipped_paths[:50],
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


def discover_mkt_db_candidate_paths(
    payload: PredictionContractSnapshotMktDbDiscoveryRequest,
) -> tuple[list[Path], list[str]]:
    suffixes = {".db", ".sqlite", ".sqlite3"}
    ignored_parts = {
        ".git",
        ".tmp",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
    }
    discovered: list[Path] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for raw_root in payload.search_roots:
        root = Path(raw_root).expanduser()
        if not root.exists():
            skipped.append(f"{root}:missing")
            continue
        for path in iter_mkt_db_candidate_scan_paths(root, ignored_parts, skipped):
            if len(discovered) >= payload.limit:
                break
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            discovered.append(path)
        if len(discovered) >= payload.limit:
            break
    return discovered, skipped


def iter_mkt_db_candidate_scan_paths(
    root: Path,
    ignored_parts: set[str],
    skipped: list[str],
):
    if root.is_file():
        yield root
        return

    def onerror(error: OSError) -> None:
        skipped.append(f"{error.filename}:{type(error).__name__}")

    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror):
        current = Path(dirpath)
        if current.name in ignored_parts:
            dirnames[:] = []
            continue
        dirnames[:] = sorted(dirname for dirname in dirnames if dirname not in ignored_parts)
        for filename in sorted(filenames):
            yield current / filename


def build_prediction_contract_mkt_donor_readiness(
    db: Session,
    payload: PredictionContractSnapshotMktDonorReadinessRequest,
) -> PredictionContractSnapshotMktDonorReadinessResponse:
    checked_at = utc_now()
    root = Path(payload.mkt_root).expanduser()
    python_dir = root / "python"
    data_dir = python_dir / "data"
    db_module = python_dir / "db.py"
    discovery = build_prediction_contract_mkt_db_discovery(
        db,
        PredictionContractSnapshotMktDbDiscoveryRequest(
            search_roots=payload.search_roots,
            limit=payload.limit,
            status_filter=payload.status_filter,
            min_volume=payload.min_volume,
            require_settlement_value=payload.require_settlement_value,
        ),
    )
    root_exists = root.exists()
    python_dir_exists = python_dir.is_dir()
    data_dir_exists = data_dir.is_dir()
    db_module_exists = db_module.is_file()
    code_ready = root_exists and python_dir_exists and db_module_exists
    blockers: list[str] = []
    if not root_exists:
        blockers.append("mkt_root_missing")
    if root_exists and not python_dir_exists:
        blockers.append("mkt_python_dir_missing")
    if python_dir_exists and not db_module_exists:
        blockers.append("mkt_db_module_missing")
    if code_ready and not data_dir_exists:
        blockers.append("mkt_data_dir_missing")
    if discovery.candidate_count == 0:
        blockers.append("mkt_sqlite_db_missing")
    elif discovery.ready_count == 0:
        blockers.append("mkt_sqlite_db_not_ready")

    if discovery.ready_count > 0:
        readiness_status = "DONOR_READY"
        next_action = "Select a ready donor DB, build a campaign manifest, then preflight replay."
    elif not code_ready:
        readiness_status = "DONOR_CODE_MISSING"
        next_action = "Restore or point Aurex at the My-Krypt-Trader checkout before DB discovery."
    elif discovery.candidate_count > 0:
        readiness_status = "DONOR_DB_BLOCKED"
        next_action = "Inspect candidate readiness blockers before importing or replaying MKT data."
    else:
        readiness_status = "DONOR_DATA_MISSING"
        next_action = (
            "Run My-Krypt-Trader market collection in demo/dry-run mode until a local "
            "krypt-trader.db exists, then rerun donor readiness."
        )

    return PredictionContractSnapshotMktDonorReadinessResponse(
        status=readiness_status,
        mkt_root=str(root),
        root_exists=root_exists,
        python_dir_exists=python_dir_exists,
        data_dir_exists=data_dir_exists,
        db_module_exists=db_module_exists,
        expected_db_paths=expected_mkt_donor_db_paths(root),
        collector_files=mkt_donor_collector_files(root),
        command_hints=mkt_donor_command_hints(root),
        discovery=discovery,
        blockers=blockers,
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


MKT_RUNTIME_SAFETY_REQUIREMENTS: tuple[dict[str, object], ...] = (
    {
        "snake": "kalshi_env",
        "camel": "kalshiEnv",
        "expected": "demo",
        "blocker": "mkt_runtime_kalshi_env_not_demo",
        "label": "Kalshi environment",
    },
    {
        "snake": "enable_trading",
        "camel": "enableTrading",
        "expected": False,
        "blocker": "mkt_runtime_enable_trading_enabled",
        "label": "Master trading switch",
    },
    {
        "snake": "crypto15m_live",
        "camel": "crypto15mLive",
        "expected": False,
        "blocker": "mkt_runtime_crypto15m_live_enabled",
        "label": "15-minute crypto live trading",
    },
    {
        "snake": "gambling_mode",
        "camel": "gamblingMode",
        "expected": False,
        "blocker": "mkt_runtime_gambling_mode_enabled",
        "label": "Gambling mode",
    },
)


def build_prediction_contract_mkt_runtime_safety(
    payload: PredictionContractSnapshotMktRuntimeSafetyRequest,
) -> PredictionContractSnapshotMktRuntimeSafetyResponse:
    checked_at = utc_now()
    root = Path(payload.mkt_root).expanduser()
    explicit_settings_path = (
        Path(payload.settings_path).expanduser() if payload.settings_path else None
    )
    explicit_userdata_path = (
        Path(payload.userdata_path).expanduser() if payload.userdata_path else None
    )
    settings_path, settings_auto_discovered, settings_candidates = (
        resolve_mkt_runtime_settings_path(root, explicit_settings_path)
    )
    userdata_path, userdata_auto_discovered, userdata_candidates = (
        resolve_mkt_runtime_userdata_path(root, explicit_userdata_path, settings_path)
    )
    checks: list[PredictionContractSnapshotMktRuntimeSafetyCheckResponse] = []
    blockers: list[str] = []

    root_exists = root.exists()
    checks.append(
        mkt_runtime_safety_check(
            key="mkt_root_exists",
            passed=root_exists,
            observed="present" if root_exists else "missing",
            expected="present",
            source=str(root),
            next_action=(
                "Inspect runtime configuration."
                if root_exists
                else "Restore My-Krypt-Trader under Aurex or update mkt_root."
            ),
        ),
    )
    if not root_exists:
        blockers.append("mkt_root_missing")

    python_config, python_source, python_error = mkt_python_default_runtime_config(root)
    if python_error:
        checks.append(
            mkt_runtime_safety_check(
                key="python_default_config_loaded",
                passed=False,
                observed=python_error,
                expected="python DEFAULT_CONFIG readable",
                source=python_source,
                next_action="Restore My-Krypt-Trader/python/config.py before donor collection.",
            ),
        )
        blockers.append("mkt_python_default_config_missing")
    else:
        checks.extend(
            mkt_runtime_safety_requirement_checks(
                config=python_config,
                source=python_source,
                key_prefix="python_default",
                blocker_prefix="mkt_python_default",
                next_action="Keep MKT default config demo-safe before donor collection.",
                blockers=blockers,
            ),
        )

    electron_config, electron_source, electron_error = mkt_electron_default_runtime_config(root)
    if electron_error:
        checks.append(
            mkt_runtime_safety_check(
                key="electron_default_config_loaded",
                passed=False,
                observed=electron_error,
                expected="Electron DEFAULT_CONFIG readable",
                source=electron_source,
                next_action=(
                    "Restore My-Krypt-Trader/electron/system/settings-store.ts before "
                    "donor collection."
                ),
            ),
        )
        blockers.append("mkt_electron_default_config_missing")
    else:
        checks.extend(
            mkt_runtime_safety_requirement_checks(
                config=electron_config,
                source=electron_source,
                key_prefix="electron_default",
                blocker_prefix="mkt_electron_default",
                next_action="Keep the MKT desktop default config demo-safe.",
                blockers=blockers,
            ),
        )

    settings_config, settings_exists, settings_loaded, settings_error = (
        mkt_runtime_settings_config(settings_path)
    )
    if settings_loaded:
        checks.extend(
            mkt_runtime_safety_requirement_checks(
                config=settings_config,
                source=str(settings_path),
                key_prefix="runtime",
                blocker_prefix="mkt_runtime",
                next_action="Set the MKT runtime settings back to demo/dry-run.",
                blockers=blockers,
            ),
        )
    else:
        checks.append(
            PredictionContractSnapshotMktRuntimeSafetyCheckResponse(
                key="runtime_settings_loaded",
                status="WARN",
                passed=False,
                observed=settings_error or "settings_path not supplied",
                expected="load settings.json or verify MKT settings manually",
                source=str(settings_path) if settings_path else "not supplied",
                next_action=(
                    "Open MKT Settings and confirm demo/dry-run, or provide settings_path "
                    "for Aurex to verify."
                ),
            ),
        )
        blockers.append("mkt_runtime_settings_requires_manual_confirmation")

    credentials = mkt_runtime_credential_status(root, userdata_path)
    demo_credentials = next((item for item in credentials if item.env == "demo"), None)
    production_credentials = next(
        (item for item in credentials if item.env == "production"),
        None,
    )
    if demo_credentials:
        checks.append(
            PredictionContractSnapshotMktRuntimeSafetyCheckResponse(
                key="demo_credentials_visibility",
                status="PASS" if demo_credentials.credential_pair_present else "WARN",
                passed=True,
                observed=(
                    "demo credential pair present"
                    if demo_credentials.credential_pair_present
                    else "demo credential pair absent"
                ),
                expected="demo credentials only if authenticated collection is needed",
                source=demo_credentials.credentials_dir,
                next_action=(
                    "Use demo credentials only for donor data collection."
                    if demo_credentials.credential_pair_present
                    else (
                        "Add demo credentials only if MKT cannot collect required data "
                        "without them."
                    )
                ),
            ),
        )
    if production_credentials:
        checks.append(
            PredictionContractSnapshotMktRuntimeSafetyCheckResponse(
                key="production_credentials_visibility",
                status="WARN" if production_credentials.credential_pair_present else "PASS",
                passed=True,
                observed=(
                    "production credential pair present"
                    if production_credentials.credential_pair_present
                    else "production credential pair absent"
                ),
                expected="production credentials absent or locked behind demo-safe settings",
                source=production_credentials.credentials_dir,
                next_action=(
                    "Do not switch MKT to production while collecting donor data."
                    if production_credentials.credential_pair_present
                    else "Keep production credentials absent during donor-data work."
                ),
            ),
        )

    failed_checks = sum(1 for check in checks if check.status == "FAIL")
    warning_checks = sum(1 for check in checks if check.status == "WARN")
    passed_checks = sum(1 for check in checks if check.status == "PASS")
    unique_blockers = sorted(set(blockers))
    if failed_checks:
        safety_status = "SAFETY_BLOCKED"
        next_action = "Fix failed MKT runtime safety checks before starting donor collection."
    elif settings_loaded:
        safety_status = "SAFETY_CONFIRMED"
        next_action = (
            "Proceed with MKT donor collection only while these settings remain unchanged."
        )
    else:
        safety_status = "SAFETY_DEFAULTS_ONLY"
        next_action = (
            "MKT code defaults are safe, but runtime settings still need manual confirmation "
            "or settings_path verification."
        )

    return PredictionContractSnapshotMktRuntimeSafetyResponse(
        status=safety_status,
        mkt_root=str(root),
        root_exists=root_exists,
        settings_path=str(settings_path) if settings_path else None,
        settings_exists=settings_exists,
        settings_loaded=settings_loaded,
        settings_error=settings_error,
        settings_auto_discovered=settings_auto_discovered,
        settings_candidates=settings_candidates,
        userdata_path=str(userdata_path) if userdata_path else None,
        userdata_auto_discovered=userdata_auto_discovered,
        userdata_candidates=userdata_candidates,
        credentials=credentials,
        checks=checks,
        passed_checks=passed_checks,
        warning_checks=warning_checks,
        failed_checks=failed_checks,
        blockers=unique_blockers,
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


def resolve_mkt_runtime_settings_path(
    root: Path,
    explicit_path: Path | None,
) -> tuple[Path | None, bool, list[PredictionContractSnapshotMktRuntimePathCandidateResponse]]:
    raw_candidates: list[tuple[str, Path, str, str]] = []
    if explicit_path is not None:
        raw_candidates.append(
            (
                "explicit_settings_path",
                explicit_path,
                "request",
                "Operator-supplied MKT settings.json path.",
            ),
        )
    raw_candidates.extend(mkt_runtime_settings_path_candidates(root))
    selected_path = explicit_path
    auto_discovered = False
    if selected_path is None:
        selected_path = first_existing_path(
            path
            for key, path, _, _ in raw_candidates
            if mkt_runtime_candidate_can_auto_select(root, key)
        )
        auto_discovered = selected_path is not None
    candidates = [
        mkt_runtime_path_candidate(
            key=key,
            path=path,
            source=source,
            purpose=purpose,
            selected=selected_path is not None and paths_equal(path, selected_path),
        )
        for key, path, source, purpose in raw_candidates
    ]
    return selected_path, auto_discovered, candidates


def resolve_mkt_runtime_userdata_path(
    root: Path,
    explicit_path: Path | None,
    settings_path: Path | None,
) -> tuple[Path | None, bool, list[PredictionContractSnapshotMktRuntimePathCandidateResponse]]:
    raw_candidates: list[tuple[str, Path, str, str]] = []
    if explicit_path is not None:
        raw_candidates.append(
            (
                "explicit_userdata_path",
                explicit_path,
                "request",
                "Operator-supplied MKT userData directory.",
            ),
        )
    if settings_path is not None:
        raw_candidates.append(
            (
                "settings_parent",
                settings_path.parent,
                "settings_path",
                "Use the loaded settings.json parent as the MKT userData directory.",
            ),
        )
    raw_candidates.extend(mkt_runtime_userdata_path_candidates(root))
    selected_path = explicit_path
    auto_discovered = False
    if selected_path is None:
        selected_path = first_existing_path(
            path
            for key, path, _, _ in raw_candidates
            if mkt_runtime_candidate_can_auto_select(root, key)
        )
        auto_discovered = selected_path is not None
    candidates = [
        mkt_runtime_path_candidate(
            key=key,
            path=path,
            source=source,
            purpose=purpose,
            selected=selected_path is not None and paths_equal(path, selected_path),
        )
        for key, path, source, purpose in raw_candidates
    ]
    return selected_path, auto_discovered, candidates


def mkt_runtime_settings_path_candidates(root: Path) -> list[tuple[str, Path, str, str]]:
    return [
        (
            f"{key}_settings",
            user_data_path / "settings.json",
            source,
            "Candidate MKT settings.json path.",
        )
        for key, user_data_path, source in mkt_runtime_userdata_base_candidates(root)
    ]


def mkt_runtime_userdata_path_candidates(root: Path) -> list[tuple[str, Path, str, str]]:
    return [
        (
            f"{key}_userdata",
            user_data_path,
            source,
            "Candidate MKT userData directory for credentials, logs, and data.",
        )
        for key, user_data_path, source in mkt_runtime_userdata_base_candidates(root)
    ]


def mkt_runtime_userdata_base_candidates(root: Path) -> list[tuple[str, Path, str]]:
    candidates: list[tuple[str, Path, str]] = []
    env_userdata = os.environ.get("KRYPT_TRADER_USERDATA")
    if env_userdata:
        candidates.append(
            (
                "krypt_trader_userdata_env",
                Path(env_userdata).expanduser(),
                "KRYPT_TRADER_USERDATA",
            ),
        )
    candidates.extend(
        [
            (
                "aurex_demo_userdata",
                root / ".aurex-demo-userdata",
                "Aurex demo bootstrap",
            ),
            (
                "workspace_tmp_product_name",
                root / ".tmp" / "Krypt Trader",
                "workspace fallback",
            ),
            (
                "workspace_userdata",
                root / "userData",
                "workspace fallback",
            ),
        ],
    )
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(
            (
                "appdata_product_name",
                Path(appdata).expanduser() / "Krypt Trader",
                "APPDATA/productName",
            ),
        )
        candidates.append(
            (
                "appdata_package_name",
                Path(appdata).expanduser() / "krypt-trader",
                "APPDATA/packageName",
            ),
        )
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(
            (
                "localappdata_product_name",
                Path(local_appdata).expanduser() / "Krypt Trader",
                "LOCALAPPDATA/productName",
            ),
        )
    return candidates


def mkt_runtime_candidate_can_auto_select(root: Path, key: str) -> bool:
    global_profile = key.startswith(("appdata_", "localappdata_"))
    if not global_profile:
        return True
    return paths_equal(root, Path("My-Krypt-Trader"))


def first_existing_path(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if safe_path_exists(path):
            return path
    return None


def mkt_runtime_path_candidate(
    key: str,
    path: Path,
    source: str,
    purpose: str,
    selected: bool,
) -> PredictionContractSnapshotMktRuntimePathCandidateResponse:
    return PredictionContractSnapshotMktRuntimePathCandidateResponse(
        key=key,
        path=str(path),
        exists=safe_path_exists(path),
        selected=selected,
        source=source,
        purpose=purpose,
    )


def safe_path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def safe_path_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return str(left) == str(right)


def mkt_runtime_safety_requirement_checks(
    config: dict[str, object],
    source: str,
    key_prefix: str,
    blocker_prefix: str,
    next_action: str,
    blockers: list[str],
) -> list[PredictionContractSnapshotMktRuntimeSafetyCheckResponse]:
    checks: list[PredictionContractSnapshotMktRuntimeSafetyCheckResponse] = []
    for requirement in MKT_RUNTIME_SAFETY_REQUIREMENTS:
        snake_key = str(requirement["snake"])
        camel_key = str(requirement["camel"])
        expected = requirement["expected"]
        observed = mkt_runtime_config_value(config, snake_key, camel_key)
        passed = mkt_runtime_expected_value_matches(observed, expected)
        if not passed:
            blocker = str(requirement["blocker"])
            if blocker_prefix != "mkt_runtime":
                blocker = f"{blocker_prefix}_{snake_key}_unsafe"
            blockers.append(blocker)
        checks.append(
            mkt_runtime_safety_check(
                key=f"{key_prefix}_{snake_key}",
                passed=passed,
                observed=mkt_runtime_display_value(observed),
                expected=mkt_runtime_display_value(expected),
                source=source,
                next_action=next_action if not passed else "Requirement satisfied.",
            ),
        )
    return checks


def mkt_runtime_safety_check(
    key: str,
    passed: bool,
    observed: str,
    expected: str,
    source: str,
    next_action: str,
) -> PredictionContractSnapshotMktRuntimeSafetyCheckResponse:
    return PredictionContractSnapshotMktRuntimeSafetyCheckResponse(
        key=key,
        status="PASS" if passed else "FAIL",
        passed=passed,
        observed=observed,
        expected=expected,
        source=source,
        next_action=next_action,
    )


def mkt_python_default_runtime_config(root: Path) -> tuple[dict[str, object], str, str | None]:
    source = root / "python" / "config.py"
    if not source.is_file():
        return {}, str(source), "missing"
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                has_default_config_target = any(
                    isinstance(target, ast.Name) and target.id == "DEFAULT_CONFIG"
                    for target in node.targets
                )
                value_node = node.value if has_default_config_target else None
            elif isinstance(node, ast.AnnAssign):
                has_default_config_target = (
                    isinstance(node.target, ast.Name) and node.target.id == "DEFAULT_CONFIG"
                )
                value_node = node.value if has_default_config_target else None
            else:
                value_node = None
            if value_node is None:
                continue
            value = ast.literal_eval(value_node)
            if isinstance(value, dict):
                return value, str(source), None
            return {}, str(source), "DEFAULT_CONFIG is not a dict"
    except (OSError, SyntaxError, ValueError) as exc:
        return {}, str(source), f"unreadable: {exc}"
    return {}, str(source), "DEFAULT_CONFIG missing"


def mkt_electron_default_runtime_config(
    root: Path,
) -> tuple[dict[str, object], str, str | None]:
    source = root / "electron" / "system" / "settings-store.ts"
    if not source.is_file():
        return {}, str(source), "missing"
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, str(source), f"unreadable: {exc}"
    config: dict[str, object] = {}
    for key in ["kalshiEnv", "enableTrading", "crypto15mLive", "gamblingMode"]:
        value = mkt_electron_config_literal(text, key)
        if value is not None:
            config[key] = value
    return config, str(source), None


def mkt_electron_config_literal(text: str, key: str) -> object | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*([^,\n]+)", text)
    if not match:
        return None
    raw_value = match.group(1).strip().strip(";")
    if raw_value in {"true", "false"}:
        return raw_value == "true"
    if (raw_value.startswith("'") and raw_value.endswith("'")) or (
        raw_value.startswith('"') and raw_value.endswith('"')
    ):
        return raw_value[1:-1]
    return raw_value


def mkt_runtime_settings_config(
    settings_path: Path | None,
) -> tuple[dict[str, object], bool, bool, str | None]:
    if settings_path is None:
        return {}, False, False, None
    if not safe_path_exists(settings_path):
        return {}, False, False, "settings file missing"
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, True, False, f"settings unreadable: {exc}"
    if not isinstance(raw, dict):
        return {}, True, False, "settings JSON is not an object"
    config = raw.get("config", raw)
    if not isinstance(config, dict):
        return {}, True, False, "settings config is not an object"
    return config, True, True, None


def mkt_runtime_credential_status(
    root: Path,
    userdata_path: Path | None,
) -> list[PredictionContractSnapshotMktRuntimeSafetyCredentialResponse]:
    credentials_dir = (
        userdata_path / "credentials" if userdata_path else root / "python" / "credentials"
    )
    statuses: list[PredictionContractSnapshotMktRuntimeSafetyCredentialResponse] = []
    for env in ["demo", "production"]:
        api_key = credentials_dir / f"apikey.{env}.txt"
        rsa_key = credentials_dir / f"rsakey.{env}.pem"
        api_key_exists = api_key.is_file()
        rsa_key_exists = rsa_key.is_file()
        statuses.append(
            PredictionContractSnapshotMktRuntimeSafetyCredentialResponse(
                env=env,
                credentials_dir=str(credentials_dir),
                api_key_file_exists=api_key_exists,
                rsa_key_file_exists=rsa_key_exists,
                credential_pair_present=api_key_exists and rsa_key_exists,
                contents_read=False,
            ),
        )
    return statuses


def mkt_runtime_config_value(
    config: dict[str, object],
    snake_key: str,
    camel_key: str,
) -> object | None:
    if snake_key in config:
        return config[snake_key]
    if camel_key in config:
        return config[camel_key]
    return None


def mkt_runtime_expected_value_matches(observed: object | None, expected: object) -> bool:
    if isinstance(expected, bool):
        if isinstance(observed, bool):
            return observed is expected
        if isinstance(observed, str):
            normalized = observed.strip().lower()
            if normalized in {"true", "false"}:
                return (normalized == "true") is expected
        return False
    if observed is None:
        return False
    return str(observed).strip().lower() == str(expected).strip().lower()


def mkt_runtime_display_value(value: object | None) -> str:
    if value is None:
        return "missing"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_prediction_contract_mkt_donor_bootstrap(
    payload: PredictionContractSnapshotMktDonorBootstrapRequest,
) -> PredictionContractSnapshotMktDonorBootstrapResponse:
    checked_at = utc_now()
    root = Path(payload.mkt_root).expanduser()
    userdata_path = (
        Path(payload.userdata_path).expanduser()
        if payload.userdata_path
        else root / ".aurex-demo-userdata"
    )
    settings_path = userdata_path / "settings.json"
    directories = [
        userdata_path,
        userdata_path / "logs",
        userdata_path / "data",
        userdata_path / "credentials",
    ]
    directories_created: list[str] = []
    blockers: list[str] = []
    settings_written = False

    if not root.exists():
        blockers.append("mkt_root_missing")
    if not (root / "package.json").is_file():
        blockers.append("mkt_package_json_missing")
    if not (root / "python" / "config.py").is_file():
        blockers.append("mkt_python_config_missing")
    if not (root / "electron" / "system" / "settings-store.ts").is_file():
        blockers.append("mkt_electron_settings_store_missing")

    existing_config, settings_exists, settings_loaded, settings_error = (
        mkt_runtime_settings_config(settings_path)
    )
    existing_settings_safe = settings_loaded and all(
        mkt_runtime_expected_value_matches(
            mkt_runtime_config_value(
                existing_config,
                str(requirement["snake"]),
                str(requirement["camel"]),
            ),
            requirement["expected"],
        )
        for requirement in MKT_RUNTIME_SAFETY_REQUIREMENTS
    )
    if settings_exists and not existing_settings_safe and not payload.overwrite_existing_settings:
        blockers.append("mkt_demo_settings_existing_unsafe")
    if settings_exists and settings_error and not payload.overwrite_existing_settings:
        blockers.append("mkt_demo_settings_existing_unreadable")

    if not blockers:
        for directory in directories:
            if not safe_path_exists(directory):
                directory.mkdir(parents=True, exist_ok=True)
                directories_created.append(str(directory))
        if not settings_exists or payload.overwrite_existing_settings:
            settings_path.write_text(
                json.dumps(mkt_demo_settings_state(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            settings_written = True

    runtime_safety = build_prediction_contract_mkt_runtime_safety(
        PredictionContractSnapshotMktRuntimeSafetyRequest(
            mkt_root=str(root),
            settings_path=str(settings_path),
            userdata_path=str(userdata_path),
        ),
    )
    blockers = sorted(set([*blockers, *runtime_safety.blockers]))
    if blockers:
        status_text = "BOOTSTRAP_BLOCKED"
        next_action = "Fix bootstrap and runtime safety blockers before starting MKT."
    else:
        status_text = "BOOTSTRAP_READY"
        next_action = (
            "Run MKT with the provided KRYPT_TRADER_USERDATA command, then rerun donor "
            "readiness and DB inventory after data appears."
        )

    return PredictionContractSnapshotMktDonorBootstrapResponse(
        status=status_text,
        mkt_root=str(root),
        userdata_path=str(userdata_path),
        settings_path=str(settings_path),
        settings_written=settings_written,
        directories_created=directories_created,
        runtime_safety=runtime_safety,
        command_hints=mkt_donor_bootstrap_command_hints(root, userdata_path),
        blockers=blockers,
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


def mkt_demo_settings_state() -> dict[str, object]:
    return {
        "config": {
            "kalshiEnv": "demo",
            "enableTrading": False,
            "crypto15mLive": False,
            "gamblingMode": False,
            "crypto15mEnabled": False,
        },
        "activeProfileId": None,
        "customProfiles": [],
        "startMinimized": False,
        "startWithWindows": False,
        "enableDiscordRpc": False,
        "acceptedDisclaimer": False,
        "windowBounds": None,
    }


def mkt_donor_bootstrap_command_hints(root: Path, userdata_path: Path) -> list[dict]:
    root_text = str(root)
    userdata_text = str(userdata_path)
    return [
        {
            "label": "Start MKT with Aurex demo userData",
            "command": (
                f"$env:KRYPT_TRADER_USERDATA='{userdata_text}'; "
                f"Set-Location '{root_text}'; {mkt_npm_command('run dev')}"
            ),
            "purpose": (
                "Launch MKT using the Aurex-prepared demo/dry-run runtime folder so "
                "settings, data, logs, and credentials stay local and inspectable."
            ),
            "live_execution": "demo/dry-run only; do not switch to production or enable trading.",
        },
        {
            "label": "Expected donor DB",
            "command": str(userdata_path / "data" / "krypt-trader.db"),
            "purpose": (
                "After MKT runs, Aurex DB discovery/inventory should inspect this SQLite DB."
            ),
            "live_execution": "none",
        },
    ]


def build_prediction_contract_mkt_donor_collection_status(
    db: Session,
    payload: PredictionContractSnapshotMktDonorCollectionStatusRequest,
) -> PredictionContractSnapshotMktDonorCollectionStatusResponse:
    checked_at = utc_now()
    root = Path(payload.mkt_root).expanduser()
    runtime_safety = build_prediction_contract_mkt_runtime_safety(
        PredictionContractSnapshotMktRuntimeSafetyRequest(
            mkt_root=str(root),
            settings_path=payload.settings_path,
            userdata_path=payload.userdata_path,
        ),
    )
    userdata_path = (
        Path(runtime_safety.userdata_path).expanduser()
        if runtime_safety.userdata_path
        else None
    )
    db_path = (
        Path(payload.db_path).expanduser()
        if payload.db_path
        else mkt_donor_collection_db_path(root, userdata_path)
    )
    db_inventory = build_prediction_contract_mkt_db_inventory(
        db,
        PredictionContractSnapshotMktDbRequest(
            db_path=str(db_path),
            source="my-krypt-trader",
            source_reference=f"{db_path}::markets",
            status_filter=payload.status_filter,
            limit=payload.limit,
            min_volume=payload.min_volume,
            require_settlement_value=payload.require_settlement_value,
        ),
    )
    logs_dir = (userdata_path / "logs") if userdata_path else root / "logs"
    log_files = mkt_donor_collection_log_files(logs_dir)
    db_stat = mkt_donor_file_stat(db_path)
    latest_log_modified_at = mkt_donor_latest_log_modified_at(log_files)
    db_age_seconds = mkt_donor_file_age_seconds(checked_at, db_stat["modified_at"])
    latest_log_age_seconds = mkt_donor_file_age_seconds(
        checked_at,
        latest_log_modified_at,
    )
    collection_freshness_status = mkt_donor_collection_freshness_status(
        checked_at,
        db_inventory,
        db_stat,
        latest_log_modified_at,
    )
    blockers = mkt_donor_collection_blockers(
        runtime_safety,
        db_inventory,
        collection_freshness_status,
    )
    collection_quality = mkt_donor_collection_quality(db_inventory)
    launch_health = mkt_donor_launch_health(
        checked_at,
        runtime_safety,
        db_inventory,
        db_stat,
        latest_log_modified_at,
        collection_freshness_status,
        collection_quality,
    )
    status_text, next_action = mkt_donor_collection_status_text(
        runtime_safety,
        db_inventory,
        collection_freshness_status,
        blockers,
    )
    recommended_recheck_after_seconds = mkt_donor_recheck_after_seconds(
        runtime_safety,
        status_text,
        collection_freshness_status,
        launch_health.status,
    )
    recommended_recheck_at = (
        checked_at + timedelta(seconds=recommended_recheck_after_seconds)
        if recommended_recheck_after_seconds is not None
        else None
    )
    data_dir = db_path.parent
    command_hints = (
        mkt_donor_bootstrap_command_hints(root, userdata_path)
        if userdata_path
        else []
    )

    return PredictionContractSnapshotMktDonorCollectionStatusResponse(
        status=status_text,
        mkt_root=str(root),
        settings_path=runtime_safety.settings_path,
        userdata_path=runtime_safety.userdata_path,
        db_path=str(db_path),
        data_dir_exists=data_dir.is_dir(),
        logs_dir_exists=logs_dir.is_dir(),
        db_file_size_bytes=db_stat["size_bytes"],
        db_modified_at=db_stat["modified_at"],
        db_age_seconds=db_age_seconds,
        latest_log_modified_at=latest_log_modified_at,
        latest_log_age_seconds=latest_log_age_seconds,
        freshness_window_seconds=MKT_COLLECTION_RECENT_WINDOW_SECONDS,
        recommended_recheck_after_seconds=recommended_recheck_after_seconds,
        recommended_recheck_at=recommended_recheck_at,
        collection_freshness_status=collection_freshness_status,
        log_files=log_files,
        command_hints=command_hints,
        runtime_safety=runtime_safety,
        db_inventory=db_inventory,
        collection_quality=collection_quality,
        launch_health=launch_health,
        blockers=blockers,
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


def mkt_donor_collection_db_path(root: Path, userdata_path: Path | None) -> Path:
    if userdata_path:
        return userdata_path / "data" / "krypt-trader.db"
    return root / "python" / "data" / "krypt-trader.db"


def mkt_donor_file_stat(path: Path) -> dict[str, object]:
    try:
        stat = path.stat()
    except OSError:
        return {"size_bytes": None, "modified_at": None}
    return {
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC),
    }


def mkt_donor_file_age_seconds(
    checked_at: datetime,
    modified_at: object,
) -> int | None:
    if not isinstance(modified_at, datetime):
        return None
    age_seconds = int((checked_at - modified_at).total_seconds())
    return max(age_seconds, 0)


def mkt_donor_latest_log_modified_at(log_files: list[dict]) -> datetime | None:
    values: list[datetime] = []
    for log_file in log_files:
        modified_at = log_file.get("modified_at")
        if not isinstance(modified_at, str):
            continue
        try:
            values.append(datetime.fromisoformat(modified_at))
        except ValueError:
            continue
    return max(values) if values else None


def mkt_donor_collection_freshness_status(
    checked_at: datetime,
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse,
    db_stat: dict[str, object],
    latest_log_modified_at: datetime | None,
) -> str:
    db_modified_at = db_stat.get("modified_at")
    if not db_inventory.db_exists:
        return "FRESHNESS_WAITING_FOR_DB"
    if not isinstance(db_modified_at, datetime):
        return "FRESHNESS_UNKNOWN"

    db_age_seconds = (checked_at - db_modified_at).total_seconds()
    log_age_seconds = (
        (checked_at - latest_log_modified_at).total_seconds()
        if latest_log_modified_at is not None
        else None
    )
    if db_age_seconds <= MKT_COLLECTION_RECENT_WINDOW_SECONDS:
        return "FRESHNESS_DB_RECENT"
    if (
        log_age_seconds is not None
        and log_age_seconds <= MKT_COLLECTION_RECENT_WINDOW_SECONDS
    ):
        return "FRESHNESS_LOG_RECENT"
    if db_inventory.total_rows > 0:
        return "FRESHNESS_STALE_ROWS_PRESENT"
    return "FRESHNESS_NO_RECENT_WRITES"


def mkt_donor_collection_blockers(
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse,
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse,
    collection_freshness_status: str,
) -> list[str]:
    blockers = list(runtime_safety.blockers)
    if runtime_safety.status == "SAFETY_BLOCKED":
        blockers.append("mkt_runtime_safety_blocked")
    if collection_freshness_status == "FRESHNESS_NO_RECENT_WRITES":
        blockers.append("mkt_collection_no_recent_writes")
    elif collection_freshness_status == "FRESHNESS_STALE_ROWS_PRESENT":
        blockers.append("mkt_collection_stale_rows_present")
    elif collection_freshness_status == "FRESHNESS_UNKNOWN":
        blockers.append("mkt_collection_freshness_unknown")
    if not db_inventory.db_exists:
        blockers.append("mkt_sqlite_db_missing")
    elif db_inventory.total_rows == 0:
        blockers.append("mkt_sqlite_db_empty")
    elif not db_inventory.replay_table_ready and not db_inventory.research_tables_ready:
        blockers.extend(db_inventory.blockers)
    return sorted(set(blockers))


def mkt_donor_collection_quality(
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse,
) -> PredictionContractSnapshotMktDonorCollectionQualityResponse:
    replay_count = int(db_inventory.replay_candidate_count or 0)
    research_count = int(db_inventory.research_candidate_count or 0)
    context_count = sum(
        int(table.row_count or 0)
        for table in db_inventory.tables
        if table.usable_for in {"market_context", "market_trade_feed"}
    )
    latest_values = [table.latest_at for table in db_inventory.tables if table.latest_at]
    latest_row_at = max(latest_values) if latest_values else None
    targets = [
        mkt_donor_collection_target(
            key="market_context_rows",
            label="Market context rows",
            current_count=context_count,
            target_count=1,
            next_action="Collect at least one market/trade/tick context row.",
        ),
        mkt_donor_collection_target(
            key="resolved_replay_candidates",
            label="Resolved replay candidates",
            current_count=replay_count,
            target_count=MKT_MIN_BACKTEST_REPLAY_ROWS,
            next_action="Collect more resolved market rows before treating replay as evidence.",
        ),
        mkt_donor_collection_target(
            key="resolved_research_observations",
            label="Resolved research observations",
            current_count=research_count,
            target_count=MKT_MIN_BACKTEST_RESEARCH_ROWS,
            next_action="Collect more resolved alerts/whales/crypto observations.",
        ),
    ]
    backtest_depth_progress_pct = round(
        (
            min(replay_count / MKT_MIN_BACKTEST_REPLAY_ROWS, 1.0)
            + min(research_count / MKT_MIN_BACKTEST_RESEARCH_ROWS, 1.0)
        )
        / 2
        * 100,
        2,
    )

    checks = [
        mkt_donor_collection_quality_check(
            key="donor_rows_present",
            passed=db_inventory.total_rows > 0,
            observed=f"{db_inventory.total_rows} total donor row(s)",
            expected="at least 1 row after demo collection starts",
            next_action="Keep MKT running in scoped demo/dry-run mode until rows appear.",
        ),
        mkt_donor_collection_quality_check(
            key="context_rows_present",
            passed=context_count > 0,
            observed=f"{context_count} market-context row(s)",
            expected="at least 1 market context row",
            next_action="Keep collecting markets/trades/ticks for context before analysis.",
        ),
        mkt_donor_collection_quality_check(
            key="replay_sample_present",
            passed=replay_count > 0,
            observed=f"{replay_count} resolved replay candidate(s)",
            expected="at least 1 resolved market row with outcome",
            next_action="Collect resolved markets before campaign manifest or replay.",
        ),
        mkt_donor_collection_quality_check(
            key="research_sample_present",
            passed=research_count > 0,
            observed=f"{research_count} resolved research observation(s)",
            expected="at least 1 resolved alert/whale/crypto observation",
            next_action="Collect resolved signal observations before strategy-lab import.",
        ),
        mkt_donor_collection_quality_check(
            key="backtest_replay_depth",
            passed=replay_count >= MKT_MIN_BACKTEST_REPLAY_ROWS,
            observed=f"{replay_count}/{MKT_MIN_BACKTEST_REPLAY_ROWS} replay candidate(s)",
            expected=f"{MKT_MIN_BACKTEST_REPLAY_ROWS}+ replay candidates",
            next_action="Keep collecting; do not treat sparse replay rows as backtest proof.",
        ),
        mkt_donor_collection_quality_check(
            key="backtest_research_depth",
            passed=research_count >= MKT_MIN_BACKTEST_RESEARCH_ROWS,
            observed=f"{research_count}/{MKT_MIN_BACKTEST_RESEARCH_ROWS} research observation(s)",
            expected=f"{MKT_MIN_BACKTEST_RESEARCH_ROWS}+ resolved observations",
            next_action="Keep collecting before claiming strategy reliability.",
        ),
    ]
    failed = [check.key for check in checks if not check.passed]

    if (
        replay_count >= MKT_MIN_BACKTEST_REPLAY_ROWS
        and research_count >= MKT_MIN_BACKTEST_RESEARCH_ROWS
    ):
        quality_status = "QUALITY_BACKTEST_CANDIDATE"
        next_action = (
            "Build campaign/research manifests and run Aurex backtest gates before paper replay."
        )
    elif replay_count > 0 and research_count > 0:
        quality_status = "QUALITY_REPLAY_AND_RESEARCH_SAMPLE"
        next_action = (
            "Small donor sample exists; use only through Aurex replay/research gates while "
            "continuing collection toward backtest depth."
        )
    elif replay_count > 0:
        quality_status = "QUALITY_REPLAY_SAMPLE"
        next_action = (
            "Replay sample exists; collect research observations and more resolved rows before "
            "trusting strategy behavior."
        )
    elif research_count > 0:
        quality_status = "QUALITY_RESEARCH_SAMPLE"
        next_action = (
            "Research sample exists; import only as candidate observations while collecting "
            "resolved markets for replay."
        )
    elif context_count > 0:
        quality_status = "QUALITY_CONTEXT_ONLY"
        next_action = "Context rows exist, but resolved replay/research rows are still missing."
    elif db_inventory.total_rows > 0:
        quality_status = "QUALITY_COLLECTING"
        next_action = "Rows exist, but no replay/research/context quality target is met yet."
    else:
        quality_status = "QUALITY_EMPTY"
        next_action = "Run MKT in scoped demo/dry-run mode until the donor DB receives rows."
    evidence_tier, aurex_use_scope = mkt_donor_collection_evidence_tier(quality_status)

    return PredictionContractSnapshotMktDonorCollectionQualityResponse(
        status=quality_status,
        evidence_tier=evidence_tier,
        aurex_use_scope=aurex_use_scope,
        replay_candidate_count=replay_count,
        research_candidate_count=research_count,
        context_row_count=context_count,
        total_rows=db_inventory.total_rows,
        latest_row_at=latest_row_at,
        minimum_backtest_replay_rows=MKT_MIN_BACKTEST_REPLAY_ROWS,
        minimum_backtest_research_rows=MKT_MIN_BACKTEST_RESEARCH_ROWS,
        backtest_depth_progress_pct=backtest_depth_progress_pct,
        targets=targets,
        checks=checks,
        blockers=failed,
        next_action=next_action,
        live_execution_enabled=False,
    )


def mkt_donor_collection_evidence_tier(quality_status: str) -> tuple[str, str]:
    if quality_status == "QUALITY_BACKTEST_CANDIDATE":
        return "DONOR_BACKTEST_DEPTH_CANDIDATE", "CAN_ENTER_AUREX_BACKTEST_GATES"
    if quality_status == "QUALITY_REPLAY_AND_RESEARCH_SAMPLE":
        return "DONOR_SPARSE_REPLAY_AND_RESEARCH_SAMPLE", "GUARDED_REPLAY_AND_RESEARCH_ONLY"
    if quality_status == "QUALITY_REPLAY_SAMPLE":
        return "DONOR_SPARSE_REPLAY_SAMPLE", "GUARDED_REPLAY_SAMPLE_ONLY"
    if quality_status == "QUALITY_RESEARCH_SAMPLE":
        return "DONOR_SPARSE_RESEARCH_SAMPLE", "RESEARCH_CANDIDATE_ONLY"
    if quality_status == "QUALITY_CONTEXT_ONLY":
        return "DONOR_CONTEXT_ONLY", "MARKET_CONTEXT_ONLY"
    if quality_status == "QUALITY_COLLECTING":
        return "DONOR_ROWS_UNCLASSIFIED", "COLLECT_MORE"
    return "DONOR_EMPTY", "COLLECT_ONLY"


def mkt_donor_collection_target(
    key: str,
    label: str,
    current_count: int,
    target_count: int,
    next_action: str,
) -> PredictionContractSnapshotMktDonorCollectionTargetResponse:
    remaining = max(target_count - current_count, 0)
    progress_pct = (
        round(min(current_count / target_count, 1.0) * 100, 2)
        if target_count > 0
        else 100.0
    )
    return PredictionContractSnapshotMktDonorCollectionTargetResponse(
        key=key,
        label=label,
        current_count=current_count,
        target_count=target_count,
        remaining_count=remaining,
        progress_pct=progress_pct,
        status="TARGET_MET" if remaining == 0 else "TARGET_OPEN",
        next_action="Target satisfied." if remaining == 0 else next_action,
    )


def mkt_donor_collection_quality_check(
    key: str,
    passed: bool,
    observed: str,
    expected: str,
    next_action: str,
) -> PredictionContractSnapshotMktDonorCollectionQualityCheckResponse:
    return PredictionContractSnapshotMktDonorCollectionQualityCheckResponse(
        key=key,
        status="PASS" if passed else "BLOCKED",
        passed=passed,
        observed=observed,
        expected=expected,
        next_action="Requirement satisfied." if passed else next_action,
    )


def mkt_donor_launch_health(
    checked_at: datetime,
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse,
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse,
    db_stat: dict[str, object],
    latest_log_modified_at: datetime | None,
    collection_freshness_status: str,
    collection_quality: PredictionContractSnapshotMktDonorCollectionQualityResponse,
) -> PredictionContractSnapshotMktDonorLaunchHealthResponse:
    recent_db_seen = mkt_donor_recent_file_seen(checked_at, db_stat.get("modified_at"))
    recent_log_seen = mkt_donor_recent_file_seen(checked_at, latest_log_modified_at)
    donor_rows_present = db_inventory.total_rows > 0
    evidence_sample_present = (
        collection_quality.replay_candidate_count > 0
        or collection_quality.research_candidate_count > 0
    )
    backtest_candidate = collection_quality.status == "QUALITY_BACKTEST_CANDIDATE"

    checks = [
        mkt_donor_launch_health_check(
            key="runtime_safety_confirmed",
            passed=runtime_safety.status != "SAFETY_BLOCKED",
            observed=runtime_safety.status,
            expected="SAFETY_CONFIRMED or warning-only dry-run safety state",
            next_action="Fix MKT runtime safety blockers before launching or trusting donor data.",
        ),
        mkt_donor_launch_health_check(
            key="recent_db_or_log_activity",
            passed=recent_db_seen or recent_log_seen,
            observed=(
                f"db_recent={str(recent_db_seen).lower()}, "
                f"log_recent={str(recent_log_seen).lower()}"
            ),
            expected="DB or log modified within the last 15 minutes",
            next_action=(
                "Start or restart MKT with the scoped KRYPT_TRADER_USERDATA command, then "
                "rerun collection status."
            ),
        ),
        mkt_donor_launch_health_check(
            key="donor_rows_present",
            passed=donor_rows_present,
            observed=f"{db_inventory.total_rows} donor row(s)",
            expected="at least 1 row in the scoped MKT SQLite donor DB",
            next_action="Keep MKT running in demo/dry-run mode until the donor DB receives rows.",
        ),
        mkt_donor_launch_health_check(
            key="evidence_sample_present",
            passed=evidence_sample_present,
            observed=(
                f"replay={collection_quality.replay_candidate_count}, "
                f"research={collection_quality.research_candidate_count}"
            ),
            expected="at least one resolved replay or research observation",
            next_action=(
                "Collect resolved donor observations before importing or replaying in Aurex."
            ),
        ),
        mkt_donor_launch_health_check(
            key="backtest_depth_target",
            passed=backtest_candidate,
            observed=f"{collection_quality.backtest_depth_progress_pct}% depth",
            expected=(
                f"{MKT_MIN_BACKTEST_REPLAY_ROWS}+ replay candidates and "
                f"{MKT_MIN_BACKTEST_RESEARCH_ROWS}+ research observations"
            ),
            next_action=(
                "Continue collecting before treating MKT-derived behavior as backtest evidence."
            ),
        ),
    ]
    blockers = [check.key for check in checks if not check.passed]

    if runtime_safety.status == "SAFETY_BLOCKED":
        status_text = "LAUNCH_HEALTH_BLOCKED"
        next_action = "Fix runtime safety blockers before starting MKT or importing donor data."
    elif collection_quality.status == "QUALITY_BACKTEST_CANDIDATE":
        status_text = "LAUNCH_HEALTH_BACKTEST_CANDIDATE"
        next_action = "Build campaign manifests and run Aurex backtest/replay gates."
    elif evidence_sample_present:
        status_text = "LAUNCH_HEALTH_SAMPLE_READY"
        next_action = (
            "Use the sparse donor sample only through Aurex research/replay gates while "
            "continuing collection toward backtest depth."
        )
    elif donor_rows_present:
        status_text = "LAUNCH_HEALTH_COLLECTING"
        next_action = "Keep collecting until resolved replay or research observations appear."
    elif recent_db_seen or recent_log_seen:
        status_text = "LAUNCH_HEALTH_STARTING"
        next_action = "MKT appears recently launched; keep it running until donor rows appear."
    elif collection_freshness_status == "FRESHNESS_STALE_ROWS_PRESENT":
        status_text = "LAUNCH_HEALTH_STALE"
        next_action = "Restart or inspect MKT collection before trusting stale donor rows."
    elif collection_freshness_status == "FRESHNESS_NO_RECENT_WRITES":
        status_text = "LAUNCH_HEALTH_INACTIVE"
        next_action = "Launch MKT with scoped demo userData, then verify DB/log timestamps update."
    else:
        status_text = "LAUNCH_HEALTH_WAITING_FOR_DB"
        next_action = "Launch MKT in scoped demo/dry-run mode until the expected DB appears."

    return PredictionContractSnapshotMktDonorLaunchHealthResponse(
        status=status_text,
        checks=checks,
        blockers=blockers,
        next_action=next_action,
        live_execution_enabled=False,
    )


def mkt_donor_recent_file_seen(
    checked_at: datetime,
    modified_at: object,
    max_age_seconds: int = MKT_COLLECTION_RECENT_WINDOW_SECONDS,
) -> bool:
    if not isinstance(modified_at, datetime):
        return False
    age_seconds = (checked_at - modified_at).total_seconds()
    return 0 <= age_seconds <= max_age_seconds


def mkt_donor_launch_health_check(
    key: str,
    passed: bool,
    observed: str,
    expected: str,
    next_action: str,
) -> PredictionContractSnapshotMktDonorLaunchHealthCheckResponse:
    return PredictionContractSnapshotMktDonorLaunchHealthCheckResponse(
        key=key,
        status="PASS" if passed else "BLOCKED",
        passed=passed,
        observed=observed,
        expected=expected,
        next_action="Requirement satisfied." if passed else next_action,
    )


def mkt_donor_collection_status_text(
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse,
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse,
    collection_freshness_status: str,
    blockers: list[str],
) -> tuple[str, str]:
    if runtime_safety.status == "SAFETY_BLOCKED":
        return (
            "COLLECTION_BLOCKED",
            "Fix runtime safety blockers before starting or trusting MKT donor collection.",
        )
    if not db_inventory.db_exists:
        return (
            "COLLECTION_WAITING_FOR_DB",
            "Start MKT in demo/dry-run mode until the expected krypt-trader.db exists.",
        )
    if collection_freshness_status == "FRESHNESS_NO_RECENT_WRITES":
        return (
            "COLLECTION_INACTIVE",
            (
                "Launch or restart MKT with the scoped demo userData command, then rerun "
                "collection status until DB or log timestamps update."
            ),
        )
    if collection_freshness_status == "FRESHNESS_STALE_ROWS_PRESENT":
        return (
            "COLLECTION_STALE",
            (
                "Rows exist, but collection is not writing recently. Verify MKT is still running "
                "before treating the donor feed as active."
            ),
        )
    if db_inventory.total_rows == 0:
        return (
            "COLLECTION_DB_EMPTY",
            "Keep MKT running in demo/dry-run mode until its SQLite tables receive rows.",
        )
    if db_inventory.replay_table_ready:
        return (
            "COLLECTION_REPLAY_READY",
            "Build a campaign manifest and campaign preflight before any replay.",
        )
    if db_inventory.research_tables_ready:
        return (
            "COLLECTION_RESEARCH_READY",
            "Import MKT research observations while continuing to collect replay-ready rows.",
        )
    if blockers:
        return (
            "COLLECTION_BLOCKED",
            "Resolve collection blockers before import, replay, or paper/demo campaign use.",
        )
    return (
        "COLLECTION_COLLECTING",
        "Keep MKT collecting until replay-ready or research-ready rows are available.",
    )


def mkt_donor_recheck_after_seconds(
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse,
    collection_status: str,
    collection_freshness_status: str,
    launch_health_status: str,
) -> int | None:
    if runtime_safety.status == "SAFETY_BLOCKED" or collection_status == "COLLECTION_BLOCKED":
        return None
    if collection_status in {"COLLECTION_REPLAY_READY", "COLLECTION_RESEARCH_READY"}:
        return 5 * 60
    if collection_freshness_status in {"FRESHNESS_DB_RECENT", "FRESHNESS_LOG_RECENT"}:
        return 60
    if launch_health_status in {
        "LAUNCH_HEALTH_STARTING",
        "LAUNCH_HEALTH_WAITING_FOR_DB",
        "LAUNCH_HEALTH_INACTIVE",
    }:
        return 60
    if collection_status in {"COLLECTION_DB_EMPTY", "COLLECTION_WAITING_FOR_DB"}:
        return 60
    return 5 * 60


def mkt_donor_collection_log_files(logs_dir: Path, limit: int = 10) -> list[dict]:
    if not logs_dir.is_dir():
        return []
    files: list[dict] = []
    try:
        candidates = sorted(
            (path for path in logs_dir.iterdir() if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return []
    for path in candidates[:limit]:
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            },
        )
    return files


def build_prediction_contract_mkt_donor_launch_preflight(
    db: Session,
    payload: PredictionContractSnapshotMktDonorLaunchPreflightRequest,
) -> PredictionContractSnapshotMktDonorLaunchPreflightResponse:
    checked_at = utc_now()
    root = Path(payload.mkt_root).expanduser()
    collection_status = build_prediction_contract_mkt_donor_collection_status(
        db,
        PredictionContractSnapshotMktDonorCollectionStatusRequest(
            mkt_root=str(root),
            settings_path=payload.settings_path,
            userdata_path=payload.userdata_path,
            db_path=payload.db_path,
        ),
    )
    runtime_safety = collection_status.runtime_safety
    userdata_path = (
        Path(collection_status.userdata_path).expanduser()
        if collection_status.userdata_path
        else None
    )
    package_json = root / "package.json"
    package_scripts, package_error = mkt_package_scripts(package_json)
    launch_command = (
        str(mkt_donor_bootstrap_command_hints(root, userdata_path)[0]["command"])
        if userdata_path
        else None
    )
    checks = mkt_donor_launch_preflight_checks(
        root=root,
        package_json=package_json,
        package_scripts=package_scripts,
        package_error=package_error,
        runtime_safety=runtime_safety,
        userdata_path=userdata_path,
        collection_status=collection_status,
        launch_command=launch_command,
    )
    blockers = [
        check.key
        for check in checks
        if check.status == "FAIL"
    ]
    needs_setup = any(check.status == "WARN" for check in checks)
    if blockers:
        status_text = "LAUNCH_BLOCKED"
        next_action = "Fix failed launch preflight checks before running MKT."
    elif needs_setup:
        status_text = "LAUNCH_NEEDS_SETUP"
        next_action = "Complete setup warnings, then rerun launch preflight."
    else:
        status_text = "LAUNCH_READY"
        next_action = (
            "Run the launch command, keep MKT in demo/dry-run, then check collection status."
        )

    return PredictionContractSnapshotMktDonorLaunchPreflightResponse(
        status=status_text,
        mkt_root=str(root),
        userdata_path=collection_status.userdata_path,
        settings_path=collection_status.settings_path,
        db_path=collection_status.db_path,
        launch_command=launch_command,
        launch_scope="DONOR_COLLECTION_ONLY",
        evidence_tier=collection_status.collection_quality.evidence_tier,
        aurex_use_scope=collection_status.collection_quality.aurex_use_scope,
        backtest_depth_ready=(
            collection_status.collection_quality.evidence_tier
            == "DONOR_BACKTEST_DEPTH_CANDIDATE"
        ),
        evidence_boundary=(
            "Launch readiness only means the scoped MKT donor collector can be started. "
            "Import, replay, backtest, paper/demo progress, live review, and real trading "
            "remain blocked until their separate Aurex evidence gates pass."
        ),
        setup_commands=mkt_donor_launch_setup_commands(root, userdata_path),
        checks=checks,
        runtime_safety=runtime_safety,
        collection_status=collection_status,
        blockers=sorted(set(blockers)),
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


def mkt_package_scripts(package_json: Path) -> tuple[dict[str, object], str | None]:
    if not package_json.is_file():
        return {}, "package.json missing"
    try:
        raw = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"package.json unreadable: {exc}"
    scripts = raw.get("scripts", {})
    if not isinstance(scripts, dict):
        return {}, "package.json scripts is not an object"
    return scripts, None


def mkt_donor_launch_preflight_checks(
    root: Path,
    package_json: Path,
    package_scripts: dict[str, object],
    package_error: str | None,
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse,
    userdata_path: Path | None,
    collection_status: PredictionContractSnapshotMktDonorCollectionStatusResponse,
    launch_command: str | None,
) -> list[PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse]:
    checks: list[PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse] = []
    venv_ok, venv_observed, venv_source = mkt_python_venv_status(root)
    (
        user_data_override_ok,
        user_data_override_observed,
        user_data_override_source,
    ) = mkt_electron_userdata_override_status(root)
    checks.append(
        mkt_donor_launch_preflight_check(
            key="mkt_root_exists",
            passed=root.is_dir(),
            observed="present" if root.is_dir() else "missing",
            expected="present",
            source=str(root),
            next_action="Restore or update the MKT root path.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_check(
            key="package_json_readable",
            passed=package_error is None,
            observed="readable" if package_error is None else str(package_error),
            expected="readable package.json",
            source=str(package_json),
            next_action="Restore MKT package.json before launch.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_check(
            key="npm_dev_script_available",
            passed="dev" in package_scripts,
            observed=str(package_scripts.get("dev", "missing")),
            expected="scripts.dev present",
            source=str(package_json),
            next_action="Restore the MKT npm dev script before launch.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_warning(
            key="npm_predev_setup_available",
            passed="predev" in package_scripts or "py:setup" in package_scripts,
            observed=(
                str(package_scripts.get("predev") or package_scripts.get("py:setup") or "missing")
            ),
            expected="predev or py:setup script present",
            source=str(package_json),
            next_action="Run npm install or restore setup scripts if MKT dependencies are missing.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_warning(
            key="node_modules_available",
            passed=(root / "node_modules").is_dir(),
            observed="present" if (root / "node_modules").is_dir() else "missing",
            expected="node_modules present for npm run dev",
            source=str(root / "node_modules"),
            next_action="Run npm install inside My-Krypt-Trader if npm run dev fails.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_warning(
            key="mkt_python_venv_available",
            passed=venv_ok,
            observed=venv_observed,
            expected="python/.venv interpreter present with reachable base Python",
            source=venv_source,
            next_action="Run the strict MKT Python backend repair command, then rerun preflight.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_check(
            key="runtime_safety_confirmed",
            passed=runtime_safety.status == "SAFETY_CONFIRMED",
            observed=runtime_safety.status,
            expected="SAFETY_CONFIRMED",
            source=runtime_safety.settings_path or "settings_path missing",
            next_action=runtime_safety.next_action,
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_check(
            key="userdata_path_selected",
            passed=userdata_path is not None and userdata_path.is_dir(),
            observed=str(userdata_path) if userdata_path else "missing",
            expected="existing MKT userData directory",
            source=str(userdata_path) if userdata_path else "not selected",
            next_action="Run MKT donor bootstrap before launch preflight.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_check(
            key="launch_command_scoped_to_userdata",
            passed=bool(launch_command and "KRYPT_TRADER_USERDATA" in launch_command),
            observed=launch_command or "missing",
            expected="PowerShell command sets KRYPT_TRADER_USERDATA",
            source=str(root),
            next_action="Run donor bootstrap so Aurex can generate a scoped launch command.",
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_check(
            key="electron_userdata_env_override_available",
            passed=user_data_override_ok,
            observed=user_data_override_observed,
            expected="electron/main.ts maps KRYPT_TRADER_USERDATA to app userData",
            source=user_data_override_source,
            next_action=(
                "Patch MKT Electron main startup so app.setPath('userData', "
                "KRYPT_TRADER_USERDATA) runs before settings/backend startup."
            ),
        ),
    )
    checks.append(
        mkt_donor_launch_preflight_warning(
            key="donor_db_not_yet_ready",
            passed=collection_status.status in {
                "COLLECTION_WAITING_FOR_DB",
                "COLLECTION_DB_EMPTY",
                "COLLECTION_INACTIVE",
                "COLLECTION_STALE",
                "COLLECTION_COLLECTING",
                "COLLECTION_RESEARCH_READY",
                "COLLECTION_REPLAY_READY",
            },
            observed=collection_status.status,
            expected="collection monitor reachable",
            source=collection_status.db_path,
            next_action=collection_status.next_action,
        ),
    )
    return checks


def mkt_donor_launch_preflight_check(
    key: str,
    passed: bool,
    observed: str,
    expected: str,
    source: str,
    next_action: str,
) -> PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse:
    return PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse(
        key=key,
        status="PASS" if passed else "FAIL",
        passed=passed,
        observed=observed,
        expected=expected,
        source=source,
        next_action="Requirement satisfied." if passed else next_action,
    )


def mkt_donor_launch_preflight_warning(
    key: str,
    passed: bool,
    observed: str,
    expected: str,
    source: str,
    next_action: str,
) -> PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse:
    return PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse(
        key=key,
        status="PASS" if passed else "WARN",
        passed=passed,
        observed=observed,
        expected=expected,
        source=source,
        next_action="Requirement satisfied." if passed else next_action,
    )


def mkt_donor_launch_setup_commands(root: Path, userdata_path: Path | None) -> list[dict]:
    root_text = str(root)
    commands = [
        {
            "label": "Install MKT npm dependencies",
            "command": f"Set-Location '{root_text}'; {mkt_npm_command('install')}",
            "purpose": "Only needed if node_modules is missing or npm run dev cannot start.",
            "live_execution": "none",
        },
        {
            "label": "Repair MKT Python backend",
            "command": mkt_strict_python_setup_command(root),
            "purpose": (
                "Recreates the MKT Python venv with an explicit Aurex Python interpreter and "
                "fails loudly if backend dependencies cannot install."
            ),
            "live_execution": "none",
        },
    ]
    if userdata_path:
        commands.append(mkt_donor_bootstrap_command_hints(root, userdata_path)[0])
    return commands


def mkt_electron_userdata_override_status(root: Path) -> tuple[bool, str, str]:
    main_path = root / "electron" / "main.ts"
    backend_path = root / "electron" / "system" / "python-backend.ts"
    if not safe_path_is_file(main_path):
        return False, "missing electron/main.ts", str(main_path)
    try:
        main_source = main_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"unreadable electron/main.ts: {exc}", str(main_path)

    main_maps_env = (
        "KRYPT_TRADER_USERDATA" in main_source
        and "app.setPath" in main_source
        and "userData" in main_source
    )

    if not safe_path_is_file(backend_path):
        return False, "missing electron/system/python-backend.ts", str(backend_path)
    try:
        backend_source = backend_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"unreadable electron/system/python-backend.ts: {exc}", str(backend_path)

    backend_passes_userdata = (
        "KRYPT_TRADER_USERDATA" in backend_source
        and "app.getPath('userData')" in backend_source
    )
    if main_maps_env and backend_passes_userdata:
        return True, "present", f"{main_path}; {backend_path}"
    if not main_maps_env:
        return False, "electron main does not map KRYPT_TRADER_USERDATA", str(main_path)
    return False, "python backend does not pass app userData to service", str(backend_path)


def mkt_strict_python_setup_command(root: Path) -> str:
    root_text = str(root)
    python_text = str(Path(sys.executable))
    return (
        f"$env:KRYPT_TRADER_PYTHON='{python_text}'; "
        f"Set-Location '{root_text}'; "
        f"{mkt_npm_command('run py:setup -- --strict --force')}"
    )


def mkt_npm_command(args: str) -> str:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    return f"{executable} {args}"


def build_prediction_contract_mkt_donor_runbook(
    db: Session,
    payload: PredictionContractSnapshotMktDonorRunbookRequest,
) -> PredictionContractSnapshotMktDonorRunbookResponse:
    checked_at = utc_now()
    root = Path(payload.mkt_root).expanduser()
    donor_readiness = build_prediction_contract_mkt_donor_readiness(
        db,
        PredictionContractSnapshotMktDonorReadinessRequest(
            mkt_root=str(root),
            search_roots=payload.search_roots,
            limit=payload.limit,
            status_filter=payload.status_filter,
            min_volume=payload.min_volume,
            require_settlement_value=payload.require_settlement_value,
        ),
    )
    collection_status = build_prediction_contract_mkt_donor_collection_status(
        db,
        PredictionContractSnapshotMktDonorCollectionStatusRequest(
            mkt_root=str(root),
            settings_path=payload.settings_path,
            userdata_path=payload.userdata_path,
            db_path=payload.db_path,
            status_filter=payload.status_filter,
            limit=payload.limit,
            min_volume=payload.min_volume,
            require_settlement_value=payload.require_settlement_value,
        ),
    )
    db_path = Path(collection_status.db_path).expanduser()
    db_inventory = collection_status.db_inventory
    runtime_safety = collection_status.runtime_safety
    steps = mkt_donor_runbook_steps(
        root,
        db_path,
        donor_readiness,
        db_inventory,
        runtime_safety,
        collection_status,
    )
    blockers = [
        blocker
        for step in steps
        for blocker in step.blockers
        if step.status != "PASSED"
    ]
    if runtime_safety.status == "SAFETY_BLOCKED":
        runbook_status = "RUNBOOK_BLOCKED"
        next_action = "Fix MKT runtime safety blockers before donor collection or replay."
    elif db_inventory.replay_table_ready:
        runbook_status = "RUNBOOK_REPLAY_READY"
        next_action = "Use DB readiness, campaign manifest, and campaign preflight before replay."
    elif db_inventory.research_tables_ready:
        runbook_status = "RUNBOOK_RESEARCH_READY"
        next_action = "Import MKT observations into the strategy lab while collecting replay rows."
    elif donor_readiness.root_exists and donor_readiness.python_dir_exists:
        runbook_status = "RUNBOOK_COLLECT_DATA"
        next_action = "Run MKT in demo/dry-run mode until krypt-trader.db has usable rows."
    else:
        runbook_status = "RUNBOOK_BLOCKED"
        next_action = "Restore or point Aurex at the My-Krypt-Trader checkout first."

    return PredictionContractSnapshotMktDonorRunbookResponse(
        status=runbook_status,
        mkt_root=str(root),
        db_path=str(db_path),
        donor_readiness=donor_readiness,
        db_inventory=db_inventory,
        collection_status=collection_status,
        runtime_safety=runtime_safety,
        steps=steps,
        blockers=sorted(set(blockers)),
        next_action=next_action,
        checked_at=checked_at,
        live_execution_enabled=False,
    )


def mkt_donor_runbook_steps(
    root: Path,
    db_path: Path,
    donor_readiness: PredictionContractSnapshotMktDonorReadinessResponse,
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse,
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse,
    collection_status: PredictionContractSnapshotMktDonorCollectionStatusResponse,
) -> list[PredictionContractSnapshotMktDonorRunbookStepResponse]:
    venv_exists = mkt_python_venv_exists(root)
    code_blockers = [
        blocker
        for blocker in [
            "mkt_root_missing" if not donor_readiness.root_exists else None,
            "mkt_python_dir_missing" if not donor_readiness.python_dir_exists else None,
            "mkt_db_module_missing" if not donor_readiness.db_module_exists else None,
        ]
        if blocker is not None
    ]
    data_blockers = list(db_inventory.blockers)
    safety_step_status = (
        "PASSED"
        if runtime_safety.status == "SAFETY_CONFIRMED"
        else "BLOCKED"
        if runtime_safety.status == "SAFETY_BLOCKED"
        else "VERIFY_MANUALLY"
    )
    safety_step_blockers = (
        []
        if runtime_safety.status == "SAFETY_CONFIRMED"
        else list(runtime_safety.blockers)
    )
    collection_step_status = (
        "PASSED"
        if collection_status.status in {"COLLECTION_REPLAY_READY", "COLLECTION_RESEARCH_READY"}
        else "BLOCKED"
        if collection_status.status == "COLLECTION_BLOCKED"
        else "NEEDS_ACTION"
    )
    collection_command = (
        str(
            mkt_donor_bootstrap_command_hints(
                root,
                Path(collection_status.userdata_path),
            )[0]["command"],
        )
        if collection_status.userdata_path
        else f"cd {root}; {mkt_npm_command('run dev')}"
    )
    return [
        PredictionContractSnapshotMktDonorRunbookStepResponse(
            step=1,
            title="Confirm MKT donor checkout",
            status="BLOCKED" if code_blockers else "PASSED",
            command=None,
            purpose="Ensure Aurex can inspect the local My-Krypt-Trader donor code and schema.",
            verification="MKT root, python directory, and python/db.py must exist.",
            safety_gate="No commands execute and no trading state changes in this step.",
            blockers=code_blockers,
            next_action=(
                "Restore My-Krypt-Trader under the Aurex workspace or update mkt_root."
                if code_blockers
                else "Proceed to Python dependency setup check."
            ),
        ),
        PredictionContractSnapshotMktDonorRunbookStepResponse(
            step=2,
            title="Prepare MKT Python backend",
            status="PASSED" if venv_exists else "NEEDS_ACTION",
            command=mkt_strict_python_setup_command(root),
            purpose="Create the MKT Python virtual environment and install backend dependencies.",
            verification=(
                "My-Krypt-Trader/python/.venv contains a usable interpreter whose pyvenv.cfg "
                "base Python is reachable."
            ),
            safety_gate=(
                "Dependency setup must not save credentials, import data into Aurex, or trade."
            ),
            blockers=[] if venv_exists else ["mkt_python_venv_missing"],
            next_action=(
                "Proceed to demo/dry-run safety check."
                if venv_exists
                else "Run setup only if network/package installation is acceptable."
            ),
        ),
        PredictionContractSnapshotMktDonorRunbookStepResponse(
            step=3,
            title="Verify MKT demo/dry-run safety",
            status=safety_step_status,
            command=None,
            purpose="Protect capital before using MKT as a donor data collector.",
            verification=(
                "Aurex runtime safety checks must confirm or manually verify "
                "kalshiEnv=demo, enableTrading=false, crypto15mLive=false, "
                "and gamblingMode=false."
            ),
            safety_gate=(
                f"Safety preflight status: {runtime_safety.status}. Do not enable "
                "production or live 15-minute crypto while collecting donor data."
            ),
            blockers=safety_step_blockers,
            next_action=runtime_safety.next_action,
        ),
        PredictionContractSnapshotMktDonorRunbookStepResponse(
            step=4,
            title="Collect local MKT donor data",
            status=collection_step_status,
            command=collection_command,
            purpose="Run MKT long enough to create/populate krypt-trader.db from public/demo data.",
            verification=f"Expected DB exists and has rows: {db_path}",
            safety_gate=(
                f"Collection status: {collection_status.status}. MKT must remain "
                "demo/dry-run; Aurex live execution remains disabled."
            ),
            blockers=collection_status.blockers if collection_step_status != "PASSED" else [],
            next_action=collection_status.next_action,
        ),
        PredictionContractSnapshotMktDonorRunbookStepResponse(
            step=5,
            title="Review MKT DB inventory",
            status=(
                "PASSED"
                if db_inventory.replay_table_ready or db_inventory.research_tables_ready
                else "BLOCKED"
            ),
            command=None,
            purpose="Classify the donor DB as replay-ready, research-only, collecting, or missing.",
            verification="Run Aurex DB inventory and inspect table counts/resolved rows.",
            safety_gate="Inventory is read-only and must not import, replay, or write evidence.",
            blockers=data_blockers,
            next_action=db_inventory.next_action,
        ),
        PredictionContractSnapshotMktDonorRunbookStepResponse(
            step=6,
            title="Use donor data inside Aurex gates",
            status="READY" if db_inventory.replay_table_ready else "BLOCKED",
            command=None,
            purpose="Move only usable data through Aurex readiness, manifest, and preflight gates.",
            verification=(
                "Replay requires markets readiness, campaign manifest, side-rationale checks, "
                "and campaign preflight. Research rows remain research-only."
            ),
            safety_gate="No live trading. No replay without manifest and preflight review.",
            blockers=[] if db_inventory.replay_table_ready else ["mkt_replay_rows_not_ready"],
            next_action=(
                "Build campaign manifest, then run campaign preflight."
                if db_inventory.replay_table_ready
                else "Keep collecting resolved markets or import research observations only."
            ),
        ),
    ]


def mkt_python_venv_exists(root: Path) -> bool:
    return mkt_python_venv_status(root)[0]


def mkt_python_venv_status(root: Path) -> tuple[bool, str, str]:
    venv_root = root / "python" / ".venv"
    candidates = [
        venv_root / "Scripts" / "python.exe",
        venv_root / "bin" / "python",
    ]
    interpreter = next((path for path in candidates if safe_path_is_file(path)), None)
    if interpreter is None:
        return False, "missing", str(venv_root)

    pyvenv_cfg = venv_root / "pyvenv.cfg"
    if not safe_path_is_file(pyvenv_cfg):
        return False, "incomplete: pyvenv.cfg missing", str(pyvenv_cfg)

    try:
        raw_lines = pyvenv_cfg.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return False, f"unreadable: {exc}", str(pyvenv_cfg)

    config: dict[str, str] = {}
    for line in raw_lines:
        key, separator, value = line.partition("=")
        if separator:
            config[key.strip().lower()] = value.strip()

    executable = config.get("executable")
    if executable and not safe_path_is_file(Path(executable)):
        return False, f"broken: base executable missing ({executable})", str(pyvenv_cfg)

    home = config.get("home")
    if home and not safe_path_exists(Path(home)):
        return False, f"broken: base home missing ({home})", str(pyvenv_cfg)

    return True, "present", str(interpreter)


def expected_mkt_donor_db_paths(root: Path) -> list[str]:
    paths = [root / "python" / "data" / "krypt-trader.db"]
    userdata = os.environ.get("KRYPT_TRADER_USERDATA")
    if userdata:
        paths.append(Path(userdata) / "data" / "krypt-trader.db")
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "Krypt Trader" / "data" / "krypt-trader.db")
    return [str(path) for path in paths]


def mkt_donor_collector_files(root: Path) -> list[dict]:
    files = [
        ("db_module", root / "python" / "db.py", "Defines krypt-trader.db and markets schema."),
        ("service_loop", root / "python" / "service.py", "Runs MKT scanner/trader loops."),
        (
            "market_scanner",
            root / "python" / "scanner.py",
            "Collects Kalshi markets and whale/momentum rows.",
        ),
        (
            "crypto15m_recorder",
            root / "python" / "crypto15m_record.py",
            "Records and resolves 15-minute crypto market signals.",
        ),
        (
            "fee_backtest",
            root / "python" / "backtest.py",
            "Runs MKT fee-aware backtests after data exists.",
        ),
        ("package_scripts", root / "package.json", "Defines setup, dev, and backtest commands."),
    ]
    return [
        {
            "key": key,
            "path": str(path),
            "exists": path.is_file(),
            "purpose": purpose,
        }
        for key, path, purpose in files
    ]


def mkt_donor_command_hints(root: Path) -> list[dict]:
    root_text = str(root)
    db_path = str(root / "python" / "data" / "krypt-trader.db")
    return [
        {
            "label": "Set up MKT Python dependencies",
            "command": mkt_strict_python_setup_command(root),
            "purpose": "Create the MKT Python environment used by its scanner/backend.",
            "live_execution": "none",
        },
        {
            "label": "Start MKT in demo/dry-run",
            "command": f"cd {root_text}; {mkt_npm_command('run dev')}",
            "purpose": "Run MKT long enough to create/populate krypt-trader.db with market rows.",
            "live_execution": "must remain demo/dry-run; do not enable production trading.",
        },
        {
            "label": "Check MKT fee-aware backtest",
            "command": f"cd {root_text}; {mkt_npm_command(f'run py:backtest -- --db {db_path}')}",
            "purpose": (
                "Only useful after resolved MKT signals exist; Aurex still treats results as "
                "research."
            ),
            "live_execution": "none",
        },
    ]


@router.post(
    "/contracts/mkt-donor-readiness",
    response_model=PredictionContractSnapshotMktDonorReadinessResponse,
)
def prediction_contract_snapshots_mkt_donor_readiness(
    payload: PredictionContractSnapshotMktDonorReadinessRequest,
    db: DbSession,
) -> PredictionContractSnapshotMktDonorReadinessResponse:
    return build_prediction_contract_mkt_donor_readiness(db, payload)


@router.post(
    "/contracts/mkt-runtime-safety",
    response_model=PredictionContractSnapshotMktRuntimeSafetyResponse,
)
def prediction_contract_snapshots_mkt_runtime_safety(
    payload: PredictionContractSnapshotMktRuntimeSafetyRequest,
) -> PredictionContractSnapshotMktRuntimeSafetyResponse:
    return build_prediction_contract_mkt_runtime_safety(payload)


@router.post(
    "/contracts/mkt-donor-bootstrap",
    response_model=PredictionContractSnapshotMktDonorBootstrapResponse,
)
def prediction_contract_snapshots_mkt_donor_bootstrap(
    payload: PredictionContractSnapshotMktDonorBootstrapRequest,
) -> PredictionContractSnapshotMktDonorBootstrapResponse:
    return build_prediction_contract_mkt_donor_bootstrap(payload)


@router.post(
    "/contracts/mkt-donor-collection-status",
    response_model=PredictionContractSnapshotMktDonorCollectionStatusResponse,
)
def prediction_contract_snapshots_mkt_donor_collection_status(
    payload: PredictionContractSnapshotMktDonorCollectionStatusRequest,
    db: DbSession,
) -> PredictionContractSnapshotMktDonorCollectionStatusResponse:
    return build_prediction_contract_mkt_donor_collection_status(db, payload)


@router.post(
    "/contracts/mkt-donor-launch-preflight",
    response_model=PredictionContractSnapshotMktDonorLaunchPreflightResponse,
)
def prediction_contract_snapshots_mkt_donor_launch_preflight(
    payload: PredictionContractSnapshotMktDonorLaunchPreflightRequest,
    db: DbSession,
) -> PredictionContractSnapshotMktDonorLaunchPreflightResponse:
    return build_prediction_contract_mkt_donor_launch_preflight(db, payload)


@router.post(
    "/contracts/mkt-donor-runbook",
    response_model=PredictionContractSnapshotMktDonorRunbookResponse,
)
def prediction_contract_snapshots_mkt_donor_runbook(
    payload: PredictionContractSnapshotMktDonorRunbookRequest,
    db: DbSession,
) -> PredictionContractSnapshotMktDonorRunbookResponse:
    return build_prediction_contract_mkt_donor_runbook(db, payload)


@router.post(
    "/contracts/discover-mkt-dbs",
    response_model=PredictionContractSnapshotMktDbDiscoveryResponse,
)
def discover_prediction_contract_mkt_dbs(
    payload: PredictionContractSnapshotMktDbDiscoveryRequest,
    db: DbSession,
) -> PredictionContractSnapshotMktDbDiscoveryResponse:
    return build_prediction_contract_mkt_db_discovery(db, payload)


@router.post(
    "/contracts/mkt-db-readiness",
    response_model=PredictionContractSnapshotMktDbReadinessResponse,
)
def prediction_contract_snapshots_mkt_db_readiness(
    payload: PredictionContractSnapshotMktDbRequest,
    db: DbSession,
) -> PredictionContractSnapshotMktDbReadinessResponse:
    return build_prediction_contract_mkt_db_readiness(db, payload)


@router.post(
    "/contracts/mkt-db-inventory",
    response_model=PredictionContractSnapshotMktDbInventoryResponse,
)
def prediction_contract_snapshots_mkt_db_inventory(
    payload: PredictionContractSnapshotMktDbRequest,
    db: DbSession,
) -> PredictionContractSnapshotMktDbInventoryResponse:
    return build_prediction_contract_mkt_db_inventory(db, payload)


@router.post(
    "/contracts/preflight-mkt-db",
    response_model=PredictionContractSnapshotMktDbPreflightResponse,
)
def preflight_contract_snapshots_mkt_db(
    payload: PredictionContractSnapshotMktDbRequest,
    db: DbSession,
) -> object:
    try:
        return PredictionContractSnapshotMktDbImporter(db).preflight_db(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/contracts/import-mkt-db",
    response_model=PredictionContractSnapshotMktDbImportResponse,
)
def import_contract_snapshots_mkt_db(
    payload: PredictionContractSnapshotMktDbRequest,
    db: DbSession,
) -> object:
    try:
        result = PredictionContractSnapshotMktDbImporter(db).import_db(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/contracts/template.csv")
def prediction_contract_snapshot_template() -> Response:
    return Response(
        content=prediction_contract_snapshot_template_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="aurex-prediction-contract-snapshots-template.csv"'
            )
        },
    )


@router.get("/contracts", response_model=list[PredictionContractResponse])
def list_contracts(db: DbSession) -> object:
    return list(
        db.execute(
            select(PredictionContract).order_by(PredictionContract.last_seen_at.desc())
        ).scalars()
    )


@router.post("/paper/order-intents", response_model=PredictionOrderIntentResponse)
def create_prediction_order_intent(
    payload: PredictionOrderIntentCreateRequest,
    db: DbSession,
) -> object:
    request = PredictionOrderRequest(
        contract_id=payload.contract_id,
        strategy=payload.strategy,
        side=payload.side,
        quantity=payload.quantity,
        limit_price=payload.limit_price,
        idempotency_key=payload.idempotency_key,
        action=payload.action,
        order_type=payload.order_type,
        expected_edge=payload.expected_edge,
        confidence=payload.confidence,
        account_id=payload.account_id,
        signal_id=payload.signal_id,
        risk_decision_id=payload.risk_decision_id,
        broker_connection_id=payload.broker_connection_id,
        expires_at=payload.expires_at,
        risk_limits=PredictionRiskLimits(
            max_order_cost=payload.risk_limits.max_order_cost,
            max_contract_exposure=payload.risk_limits.max_contract_exposure,
            max_open_positions=payload.risk_limits.max_open_positions,
            max_quote_age_seconds=payload.risk_limits.max_quote_age_seconds,
            max_spread=payload.risk_limits.max_spread,
            max_latency_ms=payload.risk_limits.max_latency_ms,
            max_slippage=payload.risk_limits.max_slippage,
        ),
    )
    try:
        intent = engine(db).create_order_intent(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(intent)
    return intent


@router.get("/paper/order-intents", response_model=list[PredictionOrderIntentResponse])
def list_prediction_order_intents(db: DbSession) -> object:
    return list(
        db.execute(
            select(PredictionOrderIntent).order_by(PredictionOrderIntent.created_intent_at.desc())
        ).scalars()
    )


@router.post(
    "/paper/order-intents/{order_intent_id}/submit",
    response_model=PredictionOrderSubmissionResponse,
)
def submit_prediction_order(
    order_intent_id: str,
    payload: PredictionFillModelRequest,
    db: DbSession,
) -> PredictionOrderSubmissionResponse:
    try:
        result = engine(db).submit_order(
            order_intent_id,
            PredictionFillModel(
                available_quantity=payload.available_quantity,
                latency_ms=payload.latency_ms,
                execution_price=payload.execution_price,
                raw_payload=payload.raw_payload,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(result.order)
    if result.fill is not None:
        db.refresh(result.fill)
    if result.position is not None:
        db.refresh(result.position)
    return PredictionOrderSubmissionResponse(
        order=result.order,
        fill=result.fill,
        position=result.position,
    )


@router.post(
    "/paper/order-intents/{order_intent_id}/cancel",
    response_model=PredictionOrderIntentResponse,
)
def cancel_prediction_order_intent(
    order_intent_id: str,
    payload: PredictionOrderCancelRequest,
    db: DbSession,
) -> object:
    try:
        intent = engine(db).cancel_order_intent(order_intent_id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(intent)
    return intent


@router.get("/paper/orders", response_model=list[PredictionOrderResponse])
def list_prediction_orders(db: DbSession) -> object:
    return list(
        db.execute(select(PredictionOrder).order_by(PredictionOrder.created_at.desc())).scalars()
    )


@router.post("/paper/stale-orders/cancel")
def cancel_stale_prediction_orders(db: DbSession) -> dict[str, int]:
    cancelled = engine(db).cancel_stale_orders()
    db.commit()
    return {"cancelled": cancelled}


@router.get("/paper/positions", response_model=list[PredictionPositionResponse])
def list_prediction_positions(db: DbSession) -> object:
    return list(
        db.execute(select(PredictionPosition).order_by(PredictionPosition.created_at.desc())).scalars()
    )


@router.post(
    "/paper/positions/{position_id}/settle",
    response_model=PredictionSettlementResponse,
)
def settle_prediction_position(
    position_id: str,
    payload: PredictionSettlementRequest,
    db: DbSession,
) -> object:
    try:
        settlement = engine(db).settle_position(position_id, payload.settlement_value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(settlement)
    return settlement


@router.post("/paper/reconciliation/run", response_model=PredictionReconciliationReportResponse)
def run_prediction_reconciliation(db: DbSession) -> object:
    report = engine(db).reconcile_paper_ledger()
    db.commit()
    db.refresh(report)
    return report


@router.get("/paper/reconciliation", response_model=list[PredictionReconciliationReportResponse])
def list_prediction_reconciliation_reports(db: DbSession) -> object:
    return list(
        db.execute(
            select(PredictionReconciliationReport).order_by(
                PredictionReconciliationReport.reconciled_at.desc()
            )
        ).scalars()
    )


@router.get("/evidence", response_model=list[PredictionEvidenceEventResponse])
def list_prediction_evidence(db: DbSession, limit: int = 50) -> object:
    bounded_limit = min(max(limit, 1), 200)
    return list(
        db.execute(
            select(PredictionEvidenceEvent)
            .order_by(PredictionEvidenceEvent.occurred_at.desc())
            .limit(bounded_limit)
        ).scalars()
    )


def count_rows(db: Session, model: type) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


def count_positions(db: Session, status: PredictionMarketPositionStatus) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(PredictionPosition)
            .where(PredictionPosition.status == status)
        ).scalar_one()
    )


def count_intents(db: Session, status: PredictionMarketOrderStatus) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(PredictionOrderIntent)
            .where(PredictionOrderIntent.status == status)
        ).scalar_one()
    )


def execute_prediction_paper_demo(
    db: Session,
    payload: PredictionPaperDemoRunRequest,
) -> dict[str, object]:
    paper = engine(db)
    contract, selected_by = demo_contract_for_payload(db, payload)
    execution_price = payload.execution_price or executable_contract_price(contract, payload.side)
    limit_price = payload.limit_price or execution_price
    if limit_price is None:
        raise ValueError("Selected prediction contract has no executable ask price for this side")

    intent = paper.create_order_intent(
        PredictionOrderRequest(
            contract_id=contract.id,
            strategy=payload.strategy,
            side=payload.side,
            quantity=payload.quantity,
            limit_price=limit_price,
            idempotency_key=payload.idempotency_key or f"paper-demo-{uuid4()}",
            expires_at=None,
            risk_limits=PredictionRiskLimits(
                max_order_cost=payload.risk_limits.max_order_cost,
                max_contract_exposure=payload.risk_limits.max_contract_exposure,
                max_open_positions=payload.risk_limits.max_open_positions,
                max_quote_age_seconds=payload.risk_limits.max_quote_age_seconds,
                max_spread=payload.risk_limits.max_spread,
                max_latency_ms=payload.risk_limits.max_latency_ms,
                max_slippage=payload.risk_limits.max_slippage,
            ),
        )
    )
    run_snapshot = {
        "paper_only": True,
        "live_execution": "blocked",
        "selected_contract_by": selected_by,
        "contract_ticker": contract.contract_ticker,
        "strategy": payload.strategy,
        "side": payload.side.value,
        "quantity": str(payload.quantity),
        "limit_price": str(limit_price),
        "execution_price": str(execution_price) if execution_price is not None else None,
        "settlement_requested": (
            payload.settlement_value is not None or contract.settlement_value is not None
        ),
        "settlement_source": (
            "request"
            if payload.settlement_value is not None
            else "contract_snapshot"
            if contract.settlement_value is not None
            else None
        ),
    }
    if intent.status == PredictionMarketOrderStatus.REJECTED:
        return demo_run_response(
            status="INTENT_REJECTED",
            next_action="Fix the paper-intent research/risk blockers before demo execution.",
            intent=intent,
            run_snapshot=run_snapshot,
        )

    submission = paper.submit_order(
        intent.id,
        PredictionFillModel(
            available_quantity=payload.available_quantity or payload.quantity,
            latency_ms=payload.latency_ms,
            execution_price=execution_price,
            raw_payload={
                "source": "aurex_guided_paper_demo",
                "contract_ticker": contract.contract_ticker,
            },
        ),
    )
    if submission.fill is None or submission.position is None:
        return demo_run_response(
            status="ORDER_SUBMITTED_NO_FILL",
            next_action="Adjust limit price, available quantity, or imported market snapshot.",
            intent=intent,
            order=submission.order,
            run_snapshot=run_snapshot,
        )

    settlement = None
    reconciliation = None
    settlement_value = payload.settlement_value
    if settlement_value is None:
        settlement_value = contract.settlement_value
    if settlement_value is not None:
        settlement = paper.settle_position(submission.position.id, settlement_value)
        reconciliation = paper.reconcile_paper_ledger()

    if settlement is None:
        return demo_run_response(
            status="FILLED_OPEN_POSITION",
            next_action="Settle the paper prediction-market position and run reconciliation.",
            intent=intent,
            order=submission.order,
            fill=submission.fill,
            position=submission.position,
            run_snapshot=run_snapshot,
        )

    matched = reconciliation is not None and reconciliation.status == ReconciliationStatus.MATCHED
    return demo_run_response(
        status="PAPER_DEMO_VERIFIED" if matched else "PAPER_DEMO_RECONCILIATION_REQUIRED",
        next_action=(
            "Paper demo lifecycle verified; continue collecting forward demo evidence."
            if matched
            else "Resolve prediction-market reconciliation discrepancies before counting evidence."
        ),
        intent=intent,
        order=submission.order,
        fill=submission.fill,
        position=submission.position,
        settlement=settlement,
        reconciliation=reconciliation,
        completed_lifecycle=matched,
        run_snapshot=run_snapshot,
    )


def build_prediction_paper_demo_batch_preflight(
    db: Session,
    payload: PredictionPaperDemoBatchPreflightRequest,
) -> dict[str, object]:
    candidates = prediction_demo_batch_candidates(db, payload)
    results: list[dict[str, object]] = []
    eligible_records = 0
    skipped_records = 0
    strategy_gate_passes = prediction_demo_batch_strategy_gate_passes(
        db,
        payload.strategy,
    )
    checked_at = utc_now()

    for contract in candidates:
        executable_price = executable_contract_price(contract, payload.side)
        limit_price = payload.limit_price or executable_price
        quote_freshness = quote_freshness_snapshot(
            contract,
            checked_at,
            payload.risk_limits.max_quote_age_seconds,
        )
        quote_spread = quote_spread_snapshot(
            contract,
            payload.side,
            payload.risk_limits.max_spread,
        )
        skipped = False
        skip_reason = None
        next_action = "Ready for guarded paper/demo replay."
        status = "READY"

        if payload.skip_existing and prediction_contract_has_strategy_settlement(
            db,
            contract.id,
            payload.strategy,
            payload.side,
        ):
            skipped = True
            skip_reason = "contract_already_has_settled_record_for_strategy"
            next_action = "Use a new imported/resolved contract snapshot for more evidence."
        elif not strategy_gate_passes:
            skipped = True
            skip_reason = "prediction_research_gate_not_accepted_for_strategy"
            next_action = "Pass the Aurex research gate before batch replay."
        elif limit_price is None:
            skipped = True
            skip_reason = "executable_price_missing"
            next_action = "Import a snapshot with an executable ask price for the selected side."
        elif quote_freshness["stale"]:
            skipped = True
            skip_reason = "prediction_quote_snapshot_stale"
            next_action = (
                "Refresh the prediction-market quote snapshot or clear the quote-age limit "
                "for intentional historical replay."
            )
        elif quote_spread["rejection_reason"] is not None:
            skipped = True
            skip_reason = str(quote_spread["rejection_reason"])
            next_action = (
                "Use tighter prediction-market quotes, lower size, or clear the spread limit "
                "for intentional historical replay."
            )
        elif (
            payload.risk_limits.max_latency_ms is not None
            and payload.latency_ms > payload.risk_limits.max_latency_ms
        ):
            skipped = True
            skip_reason = "prediction_execution_latency_exceeds_limit"
            next_action = "Reduce modeled latency or raise the reviewed latency cap."
        elif prediction_demo_estimated_order_cost(payload.quantity, limit_price) > (
            payload.risk_limits.max_order_cost
        ):
            skipped = True
            skip_reason = "prediction_order_cost_exceeds_limit"
            next_action = "Reduce quantity or raise the paper-demo max order cost."
        elif eligible_records >= payload.max_records:
            skipped = True
            skip_reason = "batch_limit_reached"
            next_action = "Increase batch max after reviewing the preview."

        if skipped:
            status = "SKIPPED"
            skipped_records += 1
        else:
            eligible_records += 1

        results.append(
            prediction_demo_batch_item(
                contract,
                status=status,
                skipped=skipped,
                skip_reason=skip_reason,
                executable_price=executable_price,
                limit_price=limit_price,
                next_action=next_action,
            )
        )

    if not candidates:
        preflight_status = "NO_ELIGIBLE_CONTRACTS"
        next_action = "Import resolved prediction-market snapshots before batch paper/demo replay."
    elif eligible_records == 0 and all(
        result.get("skip_reason") == "contract_already_has_settled_record_for_strategy"
        for result in results
    ):
        preflight_status = "NO_NEW_CONTRACTS"
        next_action = "Import new resolved contract snapshots before replaying more evidence."
    elif eligible_records == 0:
        preflight_status = "BLOCKED"
        next_action = "Resolve batch preflight blockers before replay."
    elif skipped_records:
        preflight_status = "READY_WITH_SKIPS"
        next_action = "Review skipped records, then run batch replay for ready records."
    else:
        preflight_status = "READY"
        next_action = "Run guarded batch replay if the preview matches the intended evidence set."

    preflight = {
        "status": preflight_status,
        "eligible_records": eligible_records,
        "skipped_records": skipped_records,
        "available_contracts": len(candidates),
        "max_records": payload.max_records,
        "results": results,
        "next_action": next_action,
        "live_execution_enabled": False,
    }
    preflight["preflight_hash"] = prediction_demo_batch_preflight_hash(
        payload,
        preflight,
    )
    return preflight


def validate_prediction_paper_demo_batch_preflight_review(
    db: Session,
    payload: PredictionPaperDemoBatchRunRequest,
) -> str:
    reviewed_hash = (payload.reviewed_preflight_hash or "").strip()
    if not reviewed_hash:
        raise ValueError(
            "reviewed_batch_preflight_hash_required_before_replay; run and review "
            "batch preflight before replaying paper/demo evidence."
        )
    preflight_payload = PredictionPaperDemoBatchPreflightRequest(
        **payload.model_dump(exclude={"reviewed_preflight_hash"}),
    )
    preflight = build_prediction_paper_demo_batch_preflight(db, preflight_payload)
    current_hash = str(preflight.get("preflight_hash") or "")
    if reviewed_hash != current_hash:
        raise ValueError(
            "reviewed_batch_preflight_hash_mismatch; rerun batch preflight and use "
            "the current preflight hash before replaying paper/demo evidence."
        )
    if preflight.get("status") not in {"READY", "READY_WITH_SKIPS"}:
        raise ValueError(
            "reviewed_batch_preflight_not_replay_ready; resolve batch preflight "
            "blockers before replaying paper/demo evidence."
        )
    return current_hash


def prediction_demo_batch_preflight_hash(
    payload: PredictionPaperDemoBatchRunRequest,
    preflight: dict[str, object],
) -> str:
    review_payload = payload.model_dump(
        mode="json",
        exclude={"idempotency_prefix", "reviewed_preflight_hash"},
    )
    review_preflight = {
        "status": preflight.get("status"),
        "eligible_records": preflight.get("eligible_records"),
        "skipped_records": preflight.get("skipped_records"),
        "available_contracts": preflight.get("available_contracts"),
        "max_records": preflight.get("max_records"),
        "results": preflight.get("results"),
        "live_execution_enabled": preflight.get("live_execution_enabled"),
    }
    serialized = json.dumps(
        {
            "review_version": "prediction-paper-demo-batch-v1",
            "request": review_payload,
            "preflight": review_preflight,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def execute_prediction_paper_demo_batch(
    db: Session,
    payload: PredictionPaperDemoBatchRunRequest,
) -> dict[str, object]:
    candidates = prediction_demo_batch_candidates(db, payload)
    results: list[dict[str, object]] = []
    attempted_records = 0
    completed_records = 0
    skipped_records = 0
    rejected_records = 0

    for contract in candidates:
        if payload.skip_existing and prediction_contract_has_strategy_settlement(
            db,
            contract.id,
            payload.strategy,
            payload.side,
        ):
            skipped_records += 1
            results.append(
                prediction_demo_batch_item(
                    contract,
                    status="SKIPPED_DUPLICATE",
                    skipped=True,
                    skip_reason="contract_already_has_settled_record_for_strategy",
                    next_action="Use a new imported/resolved contract snapshot for more evidence.",
                )
            )
            continue
        if attempted_records >= payload.max_records:
            break

        attempted_records += 1
        run_payload = PredictionPaperDemoRunRequest(
            contract_id=contract.id,
            strategy=payload.strategy,
            side=payload.side,
            quantity=payload.quantity,
            limit_price=payload.limit_price,
            available_quantity=payload.available_quantity or payload.quantity,
            latency_ms=payload.latency_ms,
            idempotency_key=(
                f"{payload.idempotency_prefix}-{contract.contract_ticker}-{uuid4().hex[:8]}"
            )[:128],
            risk_limits=payload.risk_limits,
        )
        demo_result = execute_prediction_paper_demo(db, run_payload)
        if demo_result["status"] == "INTENT_REJECTED":
            rejected_records += 1
        if bool(demo_result["completed_lifecycle"]):
            completed_records += 1
        results.append(prediction_demo_batch_result_item(contract, demo_result, db))

    if not candidates:
        batch_status = "NO_ELIGIBLE_CONTRACTS"
        next_action = "Import resolved prediction-market snapshots before batch paper/demo replay."
    elif attempted_records == 0 and skipped_records > 0:
        batch_status = "NO_NEW_CONTRACTS"
        next_action = "Import new resolved contract snapshots before replaying more evidence."
    elif completed_records == attempted_records and attempted_records > 0:
        batch_status = "BATCH_COMPLETED"
        next_action = "Review the demo ledger and continue collecting across more days."
    elif completed_records > 0:
        batch_status = "BATCH_PARTIAL"
        next_action = "Inspect blocked batch records before counting them as evidence."
    else:
        batch_status = "BATCH_BLOCKED"
        next_action = "Fix paper-demo blockers before running more batch records."

    return {
        "status": batch_status,
        "attempted_records": attempted_records,
        "completed_records": completed_records,
        "skipped_records": skipped_records,
        "rejected_records": rejected_records,
        "available_contracts": len(candidates),
        "results": results,
        "progress": build_prediction_paper_demo_progress(db),
        "ledger": build_prediction_paper_demo_ledger(db, limit=50),
        "next_action": next_action,
        "live_execution_enabled": False,
    }


def record_prediction_paper_demo_batch_evidence(
    db: Session,
    *,
    payload: PredictionPaperDemoBatchRunRequest,
    batch: dict[str, object],
    preflight_hash: str,
) -> PredictionEvidenceEvent:
    progress = batch["progress"]
    ledger = batch["ledger"]
    result_ids = [
        {
            "contract_id": item.get("contract_id"),
            "intent_id": item.get("intent_id"),
            "order_id": item.get("order_id"),
            "fill_id": item.get("fill_id"),
            "position_id": item.get("position_id"),
            "settlement_id": item.get("settlement_id"),
            "evidence_hash": item.get("evidence_hash"),
            "status": item.get("status"),
        }
        for item in batch.get("results", [])
    ]
    event_payload = {
        "paper_only": True,
        "live_execution": "blocked",
        "status": batch.get("status"),
        "strategy": payload.strategy,
        "side": payload.side.value,
        "quantity": str(payload.quantity),
        "max_records": payload.max_records,
        "source": payload.source,
        "source_reference": payload.source_reference,
        "preflight_hash": preflight_hash,
        "reviewed_preflight_hash": payload.reviewed_preflight_hash,
        "request": payload.model_dump(
            mode="json",
            exclude={"reviewed_preflight_hash"},
        ),
        "batch": {
            "attempted_records": batch.get("attempted_records"),
            "completed_records": batch.get("completed_records"),
            "skipped_records": batch.get("skipped_records"),
            "rejected_records": batch.get("rejected_records"),
            "available_contracts": batch.get("available_contracts"),
            "result_ids": result_ids,
        },
        "progress": {
            "status": progress.status,
            "target_closed_records": progress.target_closed_records,
            "raw_closed_records": progress.raw_closed_records,
            "closed_records": progress.closed_records,
            "unique_contracts": progress.unique_contracts,
            "remaining_records": progress.remaining_records,
            "remaining_unique_contracts": progress.remaining_unique_contracts,
            "progress_pct": progress.progress_pct,
            "current_check": evidence_json_snapshot(progress.current_check),
            "countable_ledger_records": progress.countable_ledger_records,
            "ledger_blocked_records": progress.ledger_blocked_records,
            "fee_net_realized_pl": str(progress.fee_net_realized_pl),
            "ready_for_live_review": progress.ready_for_live_review,
        },
        "ledger": {
            "record_count": ledger.record_count,
            "countable_records": ledger.countable_records,
            "blocked_records": ledger.blocked_records,
            "latest_reconciliation_status": (
                ledger.latest_reconciliation_status.value
                if ledger.latest_reconciliation_status
                else None
            ),
        },
    }
    return engine(db).record_evidence_event(
        PredictionMarketEvidenceKind.PAPER_DEMO_BATCH,
        "prediction_paper_demo_batch",
        None,
        event_payload,
        strategy=payload.strategy,
    )


def build_prediction_paper_demo_mkt_db_campaign_preflight(
    db: Session,
    payload: PredictionPaperDemoMktDbCampaignPreflightRequest,
) -> dict[str, object]:
    importer = PredictionContractSnapshotMktDbImporter(db)
    import_preflight = importer.preflight_db(payload.db_import)
    projected_replay = None
    opposite_side_projection = None
    try:
        importer.import_db(payload.db_import)
        batch_payload = campaign_batch_payload(payload.db_import, payload.batch)
        batch_preflight = build_prediction_paper_demo_batch_preflight(db, batch_payload)
        if int(batch_preflight.get("eligible_records") or 0) > 0:
            projected_batch = execute_prediction_paper_demo_batch(db, batch_payload)
            projected_replay = mkt_db_campaign_projection(projected_batch, batch_payload.side)
    finally:
        db.rollback()

    if projected_replay is not None:
        opposite_side_projection = project_mkt_db_campaign_side(
            db,
            payload.db_import,
            payload.batch,
            opposite_prediction_side(payload.batch.side),
        )
    side_sensitivity_warning = mkt_db_campaign_side_sensitivity_warning(
        projected_replay,
        opposite_side_projection,
    )
    status, next_action = mkt_db_campaign_preflight_status(
        import_preflight,
        batch_preflight,
    )
    return {
        "status": status,
        "import_preflight": import_preflight,
        "batch_preflight": batch_preflight,
        "projected_replay": projected_replay,
        "opposite_side_projection": opposite_side_projection,
        "side_sensitivity_warning": side_sensitivity_warning,
        "mutated_ledger": False,
        "next_action": next_action,
        "live_execution_enabled": False,
    }


def execute_prediction_paper_demo_mkt_db_campaign(
    db: Session,
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
) -> dict[str, object]:
    preflight = build_prediction_paper_demo_mkt_db_campaign_preflight(
        db,
        PredictionPaperDemoMktDbCampaignPreflightRequest(
            db_import=payload.db_import,
            batch=PredictionPaperDemoBatchPreflightRequest(
                **payload.batch.model_dump()
            ),
        ),
    )
    validate_mkt_db_campaign_side_sensitivity_acknowledgement(payload, preflight)
    manifest = validate_mkt_db_campaign_manifest_review(db, payload)
    importer = PredictionContractSnapshotMktDbImporter(db)
    import_result = importer.import_db(payload.db_import)
    batch_payload = campaign_batch_payload(payload.db_import, payload.batch)
    batch = execute_prediction_paper_demo_batch(db, batch_payload)
    status, next_action = mkt_db_campaign_run_status(import_result, batch)
    side_rationale = normalized_side_selection_rationale(payload)
    campaign_evidence = record_mkt_db_campaign_evidence(
        db,
        payload=payload,
        preflight=preflight,
        import_result=import_result,
        batch=batch,
        status=status,
        side_sensitivity_warning=preflight.get("side_sensitivity_warning"),
        side_selection_rationale=side_rationale,
        manifest_hash=manifest.manifest_hash,
    )
    return {
        "status": status,
        "import_result": import_result,
        "batch": batch,
        "progress": batch["progress"],
        "ledger": batch["ledger"],
        "campaign_evidence": campaign_evidence,
        "manifest_hash": manifest.manifest_hash,
        "reviewed_manifest_hash": payload.reviewed_manifest_hash,
        "side_sensitivity_warning": preflight.get("side_sensitivity_warning"),
        "side_sensitivity_acknowledged": payload.acknowledge_side_sensitivity,
        "side_selection_rationale": side_rationale,
        "next_action": next_action,
        "live_execution_enabled": False,
    }


def campaign_batch_payload(
    db_import_payload: PredictionContractSnapshotMktDbRequest,
    batch_payload: PredictionPaperDemoBatchRunRequest,
) -> PredictionPaperDemoBatchRunRequest:
    return batch_payload.model_copy(
        update={
            "source": batch_payload.source or db_import_payload.source,
            "source_reference": (
                batch_payload.source_reference or db_import_payload.source_reference
            ),
            "require_imported_snapshot": True,
            "require_settlement_value": True,
            "skip_existing": True,
        },
    )


def campaign_manifest_batch_snapshot(
    batch_payload: PredictionPaperDemoBatchRunRequest,
) -> dict[str, object]:
    return batch_payload.model_dump(
        mode="json",
        exclude={
            "idempotency_prefix",
            "reviewed_preflight_hash",
        },
    )


def validate_mkt_db_campaign_side_sensitivity_acknowledgement(
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
    preflight: dict[str, object],
) -> None:
    warning = preflight.get("side_sensitivity_warning")
    if warning is None:
        return
    rationale = normalized_side_selection_rationale(payload)
    if payload.acknowledge_side_sensitivity and rationale is not None:
        return
    raise ValueError(
        "MKT DB campaign projection is side-sensitive; acknowledge the warning and "
        "provide a side_selection_rationale before replaying evidence."
    )


def normalized_side_selection_rationale(
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
) -> str | None:
    rationale = (payload.side_selection_rationale or "").strip()
    if len(rationale) < 20:
        return None
    return rationale


def validate_mkt_db_campaign_manifest_review(
    db: Session,
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
) -> PredictionPaperDemoMktDbCampaignManifestResponse:
    manifest = build_prediction_paper_demo_mkt_db_campaign_manifest(db, payload)
    reviewed_hash = (payload.reviewed_manifest_hash or "").strip()
    if not reviewed_hash:
        raise ValueError(
            "reviewed_manifest_hash_required_before_campaign_replay; build and review "
            "the MKT DB campaign manifest before replaying evidence."
        )
    if reviewed_hash != manifest.manifest_hash:
        raise ValueError(
            "reviewed_manifest_hash_mismatch; rebuild the campaign manifest and use the "
            "current manifest hash before replaying evidence."
        )
    if not manifest.replay_ready:
        raise ValueError(
            "reviewed_manifest_not_replay_ready; resolve manifest blockers before replaying "
            "evidence."
        )
    return manifest


def record_mkt_db_campaign_evidence(
    db: Session,
    *,
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
    preflight: dict[str, object],
    import_result: dict[str, object],
    batch: dict[str, object],
    status: str,
    side_sensitivity_warning: object,
    side_selection_rationale: str | None,
    manifest_hash: str,
) -> PredictionEvidenceEvent:
    progress = batch["progress"]
    ledger = batch["ledger"]
    donor_inventory = build_prediction_contract_mkt_db_inventory(db, payload.db_import)
    donor_quality = mkt_donor_collection_quality(donor_inventory)
    result_ids = [
        {
            "contract_id": item.get("contract_id"),
            "intent_id": item.get("intent_id"),
            "order_id": item.get("order_id"),
            "fill_id": item.get("fill_id"),
            "position_id": item.get("position_id"),
            "settlement_id": item.get("settlement_id"),
            "evidence_hash": item.get("evidence_hash"),
            "status": item.get("status"),
        }
        for item in batch.get("results", [])
    ]
    event_payload = {
        "paper_only": True,
        "live_execution": "blocked",
        "status": status,
        "strategy": payload.batch.strategy,
        "side": payload.batch.side.value,
        "quantity": str(payload.batch.quantity),
        "max_records": payload.batch.max_records,
        "manifest_hash": manifest_hash,
        "reviewed_manifest_hash": payload.reviewed_manifest_hash,
        "db_import": {
            "db_path": import_result.get("db_path"),
            "source": import_result.get("source"),
            "source_reference": import_result.get("source_reference"),
            "csv_format": import_result.get("csv_format"),
            "import_hash": import_result.get("import_hash"),
            "rows_received": import_result.get("rows_received"),
            "imported_count": import_result.get("imported_count"),
            "rejected_count": import_result.get("rejected_count"),
            "query_summary": import_result.get("query_summary"),
        },
        "donor_quality": {
            "status": donor_quality.status,
            "evidence_tier": donor_quality.evidence_tier,
            "aurex_use_scope": donor_quality.aurex_use_scope,
            "backtest_depth_ready": (
                donor_quality.evidence_tier == "DONOR_BACKTEST_DEPTH_CANDIDATE"
            ),
            "replay_candidate_count": donor_quality.replay_candidate_count,
            "research_candidate_count": donor_quality.research_candidate_count,
            "context_row_count": donor_quality.context_row_count,
            "total_rows": donor_quality.total_rows,
            "backtest_depth_progress_pct": donor_quality.backtest_depth_progress_pct,
            "latest_row_at": donor_quality.latest_row_at,
            "minimum_backtest_replay_rows": donor_quality.minimum_backtest_replay_rows,
            "minimum_backtest_research_rows": donor_quality.minimum_backtest_research_rows,
        },
        "preflight": {
            "status": preflight.get("status"),
            "next_action": preflight.get("next_action"),
            "mutated_ledger": preflight.get("mutated_ledger"),
            "import_preflight": evidence_json_snapshot(
                preflight.get("import_preflight")
            ),
            "batch_preflight": evidence_json_snapshot(
                preflight.get("batch_preflight")
            ),
            "projected_replay": evidence_json_snapshot(
                preflight.get("projected_replay")
            ),
            "opposite_side_projection": evidence_json_snapshot(
                preflight.get("opposite_side_projection")
            ),
            "side_sensitivity_warning": (
                str(side_sensitivity_warning) if side_sensitivity_warning else None
            ),
        },
        "batch": {
            "status": batch.get("status"),
            "attempted_records": batch.get("attempted_records"),
            "completed_records": batch.get("completed_records"),
            "skipped_records": batch.get("skipped_records"),
            "rejected_records": batch.get("rejected_records"),
            "available_contracts": batch.get("available_contracts"),
            "result_ids": result_ids,
        },
        "progress": {
            "status": progress.status,
            "target_closed_records": progress.target_closed_records,
            "target_calendar_days": progress.target_calendar_days,
            "target_active_days": progress.target_active_days,
            "target_unique_contracts": progress.target_unique_contracts,
            "raw_closed_records": progress.raw_closed_records,
            "closed_records": progress.closed_records,
            "calendar_days": progress.calendar_days,
            "active_days": progress.active_days,
            "unique_contracts": progress.unique_contracts,
            "remaining_records": progress.remaining_records,
            "remaining_calendar_days": progress.remaining_calendar_days,
            "remaining_active_days": progress.remaining_active_days,
            "remaining_unique_contracts": progress.remaining_unique_contracts,
            "progress_pct": progress.progress_pct,
            "current_check": evidence_json_snapshot(progress.current_check),
            "countable_ledger_records": progress.countable_ledger_records,
            "ledger_blocked_records": progress.ledger_blocked_records,
            "provenance_complete_records": progress.provenance_complete_records,
            "provenance_missing_records": progress.provenance_missing_records,
            "max_single_day_record_share": str(progress.max_single_day_record_share),
            "max_single_contract_record_share": str(
                progress.max_single_contract_record_share
            ),
            "fee_net_realized_pl": str(progress.fee_net_realized_pl),
            "expectancy": str(progress.expectancy),
            "profit_factor": (
                str(progress.profit_factor) if progress.profit_factor is not None else None
            ),
            "max_drawdown": str(progress.max_drawdown),
            "ready_for_live_review": progress.ready_for_live_review,
        },
        "ledger": {
            "record_count": ledger.record_count,
            "countable_records": ledger.countable_records,
            "blocked_records": ledger.blocked_records,
            "latest_reconciliation_status": (
                ledger.latest_reconciliation_status.value
                if ledger.latest_reconciliation_status
                else None
            ),
        },
        "side_sensitivity_warning": (
            str(side_sensitivity_warning) if side_sensitivity_warning else None
        ),
        "side_sensitivity_acknowledged": payload.acknowledge_side_sensitivity,
        "side_selection_rationale": side_selection_rationale,
    }
    return engine(db).record_evidence_event(
        PredictionMarketEvidenceKind.PAPER_DEMO_CAMPAIGN,
        "prediction_paper_demo_campaign",
        None,
        event_payload,
        strategy=payload.batch.strategy,
    )


def evidence_json_snapshot(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[attr-defined]
    return json.loads(json.dumps(value, default=str))


def project_mkt_db_campaign_side(
    db: Session,
    db_import_payload: PredictionContractSnapshotMktDbRequest,
    batch_payload: PredictionPaperDemoBatchRunRequest,
    side: PredictionMarketSide,
) -> PredictionPaperDemoMktDbCampaignProjectionResponse | None:
    importer = PredictionContractSnapshotMktDbImporter(db)
    side_batch_payload = campaign_batch_payload(
        db_import_payload,
        batch_payload.model_copy(update={"side": side}),
    )
    try:
        importer.import_db(db_import_payload)
        preflight = build_prediction_paper_demo_batch_preflight(db, side_batch_payload)
        if int(preflight.get("eligible_records") or 0) == 0:
            return None
        projected_batch = execute_prediction_paper_demo_batch(db, side_batch_payload)
        return mkt_db_campaign_projection(projected_batch, side)
    finally:
        db.rollback()


def opposite_prediction_side(side: PredictionMarketSide) -> PredictionMarketSide:
    return PredictionMarketSide.NO if side == PredictionMarketSide.YES else PredictionMarketSide.YES


def mkt_db_campaign_side_sensitivity_warning(
    selected: PredictionPaperDemoMktDbCampaignProjectionResponse | None,
    opposite: PredictionPaperDemoMktDbCampaignProjectionResponse | None,
) -> str | None:
    if selected is None or opposite is None:
        return None
    if selected.completed_records == 0 or opposite.completed_records == 0:
        return None
    if selected.projected_fee_net_realized_pl < opposite.projected_fee_net_realized_pl:
        return "opposite_side_projects_better_fee_net_pl"
    if selected.projected_fee_net_realized_pl <= 0 < opposite.projected_fee_net_realized_pl:
        return "selected_side_negative_opposite_side_positive"
    if selected.projected_fee_net_realized_pl > 0 > opposite.projected_fee_net_realized_pl:
        return "projection_is_side_sensitive_selected_positive_opposite_negative"
    return "projection_requires_side_hypothesis_before_replay"


def build_prediction_paper_demo_mkt_db_campaign_readiness(
    db: Session,
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
) -> PredictionPaperDemoMktDbCampaignReadinessResponse:
    data_readiness = build_prediction_contract_mkt_db_readiness(db, payload.db_import)
    db_inventory = build_prediction_contract_mkt_db_inventory(db, payload.db_import)
    data_quality = mkt_donor_collection_quality(db_inventory)
    strategy_gate = prediction_campaign_strategy_gate(db, payload.batch.strategy)
    campaign_preflight: dict[str, object] | None = None
    preflight_error: str | None = None
    if data_readiness.data_ready and bool(strategy_gate["approved"]):
        try:
            campaign_preflight = build_prediction_paper_demo_mkt_db_campaign_preflight(
                db,
                PredictionPaperDemoMktDbCampaignPreflightRequest(
                    db_import=payload.db_import,
                    batch=PredictionPaperDemoBatchPreflightRequest(
                        **payload.batch.model_dump()
                    ),
                ),
            )
        except ValueError as exc:
            preflight_error = str(exc)

    preflight_status = (
        str(campaign_preflight.get("status")) if campaign_preflight is not None else None
    )
    preflight_ready = preflight_status in {"READY", "READY_WITH_WARNINGS"}
    side_sensitivity_warning = (
        campaign_preflight.get("side_sensitivity_warning")
        if campaign_preflight is not None
        else None
    )
    side_rationale = normalized_side_selection_rationale(payload)
    side_rationale_ready = (
        side_sensitivity_warning is None
        or (payload.acknowledge_side_sensitivity and side_rationale is not None)
    )
    ready_for_campaign_preflight = data_readiness.data_ready and bool(strategy_gate["approved"])
    ready_for_campaign_replay = (
        ready_for_campaign_preflight and preflight_ready and side_rationale_ready
    )

    checks = [
        readiness_check(
            "live_execution_disabled",
            True,
            "Live execution is disabled for MKT campaign readiness.",
            "Live execution must remain disabled.",
        ),
        readiness_check(
            "mkt_db_data_ready",
            data_readiness.data_ready,
            (
                f"{data_readiness.importable_count} usable MKT DB row(s) found."
                if data_readiness.data_ready
                else data_readiness.status
            ),
            data_readiness.next_action,
        ),
        readiness_check(
            "mkt_db_evidence_tier",
            data_readiness.data_ready,
            (
                f"{data_quality.evidence_tier} / {data_quality.aurex_use_scope} / "
                f"{data_quality.backtest_depth_progress_pct}% donor depth."
            ),
            (
                "Classified donor maturity; sparse tiers remain guarded replay/research only."
                if data_readiness.data_ready
                else data_quality.next_action
            ),
        ),
        readiness_check(
            "mkt_research_gate_accepted",
            bool(strategy_gate["approved"]),
            str(strategy_gate["reason"]),
            str(strategy_gate["next_action"]),
        ),
        readiness_check(
            "campaign_preflight_ready",
            preflight_ready,
            (
                f"Campaign preflight status: {preflight_status}."
                if preflight_status
                else preflight_error
                or "Campaign preflight has not run because prerequisites are blocked."
            ),
            (
                str(campaign_preflight.get("next_action"))
                if campaign_preflight is not None
                else preflight_error
                or "Resolve data and research-gate blockers before campaign preflight."
            ),
        ),
        readiness_check(
            "side_sensitivity_acknowledged",
            side_rationale_ready,
            (
                "No side-sensitivity acknowledgement required."
                if side_sensitivity_warning is None
                else f"Side sensitivity warning: {side_sensitivity_warning}."
            ),
            (
                "Acknowledge side sensitivity and provide a pre-declared side rationale."
                if side_sensitivity_warning is not None
                else "OK"
            ),
        ),
    ]
    status = campaign_readiness_status(
        data_ready=data_readiness.data_ready,
        strategy_gate_approved=bool(strategy_gate["approved"]),
        preflight_ready=preflight_ready,
        side_rationale_ready=side_rationale_ready,
        ready_for_campaign_replay=ready_for_campaign_replay,
    )
    next_action = next(
        (str(check["next_action"]) for check in checks if not bool(check["passed"])),
        "Ready for guarded MKT DB campaign replay; live execution remains disabled.",
    )
    return PredictionPaperDemoMktDbCampaignReadinessResponse(
        status=status,
        ready_for_campaign_preflight=ready_for_campaign_preflight,
        ready_for_campaign_replay=ready_for_campaign_replay,
        data_readiness=data_readiness,
        data_quality_status=data_quality.status,
        data_evidence_tier=data_quality.evidence_tier,
        data_use_scope=data_quality.aurex_use_scope,
        data_backtest_depth_ready=(
            data_quality.evidence_tier == "DONOR_BACKTEST_DEPTH_CANDIDATE"
        ),
        strategy_gate=strategy_gate,
        campaign_preflight=campaign_preflight,
        checks=checks,
        next_action=next_action,
        live_execution_enabled=False,
    )


def build_prediction_paper_demo_mkt_db_campaign_manifest(
    db: Session,
    payload: PredictionPaperDemoMktDbCampaignRunRequest,
) -> PredictionPaperDemoMktDbCampaignManifestResponse:
    generated_at = utc_now()
    readiness = build_prediction_paper_demo_mkt_db_campaign_readiness(db, payload)
    blockers = [
        f"{check.get('key')}: {check.get('next_action')}"
        for check in readiness.checks
        if not bool(check.get("passed"))
    ]
    replay_ready = readiness.ready_for_campaign_replay
    status_label = (
        "MANIFEST_READY"
        if replay_ready
        else "MANIFEST_PREFLIGHT_READY"
        if readiness.ready_for_campaign_preflight
        else "MANIFEST_BLOCKED"
    )
    side_rationale = normalized_side_selection_rationale(payload)
    campaign_preflight = readiness.campaign_preflight
    side_sensitivity_warning = (
        campaign_preflight.side_sensitivity_warning if campaign_preflight is not None else None
    )
    manifest = {
        "manifest_version": "mkt-db-campaign-v1",
        "paper_only": True,
        "live_execution": "blocked",
        "db_import": payload.db_import.model_dump(mode="json"),
        "batch": campaign_manifest_batch_snapshot(payload.batch),
        "readiness_status": readiness.status,
        "data_status": readiness.data_readiness.status,
        "strategy_gate": readiness.strategy_gate,
        "campaign_preflight_status": (
            campaign_preflight.status if campaign_preflight is not None else None
        ),
        "projected_replay": (
            campaign_preflight.projected_replay.model_dump(mode="json")
            if campaign_preflight is not None and campaign_preflight.projected_replay is not None
            else None
        ),
        "opposite_side_projection": (
            campaign_preflight.opposite_side_projection.model_dump(mode="json")
            if (
                campaign_preflight is not None
                and campaign_preflight.opposite_side_projection is not None
            )
            else None
        ),
        "side_sensitivity_warning": side_sensitivity_warning,
        "side_sensitivity_acknowledged": payload.acknowledge_side_sensitivity,
        "side_selection_rationale": side_rationale,
        "blockers": blockers,
        "controls": {
            "requires_campaign_preflight": True,
            "requires_research_gate": True,
            "requires_side_sensitivity_acknowledgement": (
                side_sensitivity_warning is not None
            ),
            "mutates_ledger": False,
            "live_execution_enabled": False,
        },
    }
    manifest_hash = prediction_campaign_manifest_hash(manifest)
    next_action = (
        "Review manifest, then run guarded paper replay only if the plan matches intent."
        if replay_ready
        else readiness.next_action
    )
    return PredictionPaperDemoMktDbCampaignManifestResponse(
        status=status_label,
        replay_ready=replay_ready,
        manifest_hash=manifest_hash,
        manifest=manifest,
        readiness=readiness,
        blockers=blockers,
        generated_at=generated_at,
        mutated_ledger=False,
        next_action=next_action,
        live_execution_enabled=False,
    )


def prediction_campaign_manifest_hash(manifest: dict) -> str:
    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def campaign_readiness_status(
    *,
    data_ready: bool,
    strategy_gate_approved: bool,
    preflight_ready: bool,
    side_rationale_ready: bool,
    ready_for_campaign_replay: bool,
) -> str:
    if ready_for_campaign_replay:
        return "READY_FOR_CAMPAIGN_REPLAY"
    if data_ready and strategy_gate_approved and preflight_ready and not side_rationale_ready:
        return "SIDE_RATIONALE_REQUIRED"
    if data_ready and strategy_gate_approved and not preflight_ready:
        return "CAMPAIGN_PREFLIGHT_BLOCKED"
    if data_ready and not strategy_gate_approved:
        return "RESEARCH_GATE_NOT_READY"
    if not data_ready:
        return "MKT_DB_NOT_READY"
    return "BLOCKED"


def prediction_campaign_strategy_gate(db: Session, strategy: str) -> dict[str, object]:
    if not strategy.lower().startswith("mkt_"):
        return {
            "strategy": strategy,
            "required": False,
            "approved": True,
            "candidate_id": None,
            "backtest_run_id": None,
            "evidence_hash": None,
            "reason": "non_mkt_strategy_research_gate_not_required",
            "next_action": "Use MKT strategies for MKT DB campaign evidence.",
            "live_execution": "blocked",
        }
    candidates = eligible_mkt_research_candidates(db)
    candidate = next((item for item in candidates if item.strategy == strategy), None)
    if candidate is not None:
        return {
            "strategy": strategy,
            "required": True,
            "approved": True,
            "candidate_id": candidate.id,
            "backtest_run_id": (candidate.normalized_payload or {}).get(
                "latest_research_backtest_run_id"
            ),
            "evidence_hash": (candidate.normalized_payload or {}).get(
                "latest_research_backtest_hash"
            ),
            "reason": "mkt_research_gate_accepted_for_paper_demo",
            "next_action": "Run campaign preflight before replay.",
            "live_execution": "blocked",
        }
    return {
        "strategy": strategy,
        "required": True,
        "approved": False,
        "candidate_id": None,
        "backtest_run_id": None,
        "evidence_hash": None,
        "reason": "prediction_research_gate_not_accepted_for_strategy",
        "next_action": "Pass the Aurex research gate for this MKT strategy before replay.",
        "live_execution": "blocked",
    }


def mkt_db_campaign_preflight_status(
    import_preflight: dict[str, object],
    batch_preflight: dict[str, object],
) -> tuple[str, str]:
    if int(import_preflight.get("importable_count") or 0) == 0:
        return (
            "NO_IMPORTABLE_MARKET_ROWS",
            "Fix or collect resolved MKT markets rows before paper/demo campaign replay.",
        )
    if batch_preflight.get("status") == "NO_NEW_CONTRACTS":
        return (
            "NO_NEW_CONTRACTS",
            "Import new resolved contract snapshots before replaying more evidence.",
        )
    if int(batch_preflight.get("eligible_records") or 0) == 0:
        return (
            "CAMPAIGN_PREFLIGHT_BLOCKED",
            str(batch_preflight.get("next_action") or "Resolve campaign blockers."),
        )
    if int(import_preflight.get("rejected_count") or 0) > 0 or int(
        batch_preflight.get("skipped_records") or 0
    ) > 0:
        return (
            "READY_WITH_WARNINGS",
            "Review rejected/skipped rows, then run the guarded MKT DB paper/demo campaign.",
        )
    return (
        "READY",
        "Run the guarded MKT DB paper/demo campaign if this preview matches the intended set.",
    )


def mkt_db_campaign_run_status(
    import_result: dict[str, object],
    batch: dict[str, object],
) -> tuple[str, str]:
    if int(import_result.get("imported_count") or 0) == 0:
        return (
            "NO_IMPORTABLE_MARKET_ROWS",
            "Import resolved MKT markets rows before campaign replay.",
        )
    if batch.get("status") == "NO_NEW_CONTRACTS":
        return (
            "NO_NEW_CONTRACTS",
            "Import new resolved contract snapshots before replaying more evidence.",
        )
    completed = int(batch.get("completed_records") or 0)
    attempted = int(batch.get("attempted_records") or 0)
    if completed > 0 and completed == attempted:
        return (
            "CAMPAIGN_REPLAY_COMPLETED",
            "Review the demo ledger and continue collecting across more contracts and days.",
        )
    if completed > 0:
        return (
            "CAMPAIGN_REPLAY_PARTIAL",
            "Inspect blocked campaign records before counting them as evidence.",
        )
    return (
        "CAMPAIGN_REPLAY_BLOCKED",
        str(batch.get("next_action") or "Fix campaign blockers before replaying more records."),
    )


def mkt_db_campaign_projection(
    projected_batch: dict[str, object],
    side: PredictionMarketSide,
) -> PredictionPaperDemoMktDbCampaignProjectionResponse:
    progress = projected_batch["progress"]
    ledger = projected_batch["ledger"]
    first_failed_check = next(
        (
            str(check["key"])
            for check in progress.checks
            if not bool(check.get("passed"))
        ),
        None,
    )
    return PredictionPaperDemoMktDbCampaignProjectionResponse(
        side=side,
        status=str(projected_batch.get("status") or "UNKNOWN"),
        attempted_records=int(projected_batch.get("attempted_records") or 0),
        completed_records=int(projected_batch.get("completed_records") or 0),
        rejected_records=int(projected_batch.get("rejected_records") or 0),
        target_closed_records=progress.target_closed_records,
        target_calendar_days=progress.target_calendar_days,
        target_active_days=progress.target_active_days,
        target_unique_contracts=progress.target_unique_contracts,
        projected_raw_closed_records=progress.raw_closed_records,
        projected_closed_records=progress.closed_records,
        projected_calendar_days=progress.calendar_days,
        projected_active_days=progress.active_days,
        projected_unique_contracts=progress.unique_contracts,
        projected_countable_records=progress.countable_ledger_records,
        projected_blocked_records=progress.ledger_blocked_records,
        remaining_closed_records=progress.remaining_records,
        remaining_calendar_days=progress.remaining_calendar_days,
        remaining_active_days=progress.remaining_active_days,
        remaining_unique_contracts=progress.remaining_unique_contracts,
        projected_progress_pct=progress.progress_pct,
        projected_fee_net_realized_pl=progress.fee_net_realized_pl,
        projected_expectancy=progress.expectancy,
        projected_profit_factor=progress.profit_factor,
        projected_max_drawdown=progress.max_drawdown,
        ready_for_live_review=progress.ready_for_live_review,
        first_failed_check=first_failed_check,
        next_action=(
            "Projection still fails campaign gates; inspect first_failed_check."
            if first_failed_check
            else str(projected_batch.get("next_action") or "Projection passed checks.")
        ),
        live_execution_enabled=ledger.live_execution_enabled,
    )


def prediction_demo_batch_candidates(
    db: Session,
    payload: PredictionPaperDemoBatchRunRequest,
) -> list[PredictionContract]:
    price_column = (
        PredictionContract.yes_ask_price
        if payload.side.value == "YES"
        else PredictionContract.no_ask_price
    )
    statement = select(PredictionContract).where(price_column.is_not(None))
    if payload.require_settlement_value:
        statement = statement.where(PredictionContract.settlement_value.is_not(None))
    contracts = list(
        db.execute(
            statement.order_by(PredictionContract.last_seen_at.asc()).limit(250)
        ).scalars()
    )
    candidates: list[PredictionContract] = []
    for contract in contracts:
        raw_payload = contract.raw_payload or {}
        if payload.require_imported_snapshot and not raw_payload.get("csv_format"):
            continue
        if payload.source and raw_payload.get("source") != payload.source:
            continue
        if (
            payload.source_reference
            and raw_payload.get("source_reference") != payload.source_reference
        ):
            continue
        candidates.append(contract)
    return candidates


def prediction_contract_has_strategy_settlement(
    db: Session,
    contract_id: str,
    strategy: str,
    side: object,
) -> bool:
    settlements = list(
        db.execute(
            select(PredictionSettlement).where(PredictionSettlement.contract_id == contract_id)
        ).scalars()
    )
    for settlement in settlements:
        position = settlement.position
        if position is None or position.side != side:
            continue
        if strategy in prediction_record_strategies(db, settlement, position):
            return True
    return False


def prediction_demo_batch_strategy_gate_passes(db: Session, strategy: str) -> bool:
    if not strategy.lower().startswith("mkt_"):
        return True
    return any(candidate.strategy == strategy for candidate in eligible_mkt_research_candidates(db))


def prediction_demo_estimated_order_cost(quantity: Decimal, limit_price: Decimal) -> Decimal:
    estimated_fee = estimate_binary_contract_fee(quantity, limit_price)
    return calculate_binary_entry_cost(quantity, limit_price, estimated_fee)


def prediction_demo_batch_result_item(
    contract: PredictionContract,
    demo_result: dict[str, object],
    db: Session,
) -> dict[str, object]:
    settlement = demo_result.get("settlement")
    evidence_hash = (
        settlement_evidence_hash(db, settlement.id)
        if isinstance(settlement, PredictionSettlement)
        else None
    )
    return prediction_demo_batch_item(
        contract,
        status=str(demo_result["status"]),
        completed_lifecycle=bool(demo_result["completed_lifecycle"]),
        intent_id=entity_id(demo_result.get("intent")),
        order_id=entity_id(demo_result.get("order")),
        fill_id=entity_id(demo_result.get("fill")),
        position_id=entity_id(demo_result.get("position")),
        settlement_id=entity_id(settlement),
        reconciliation_status=getattr(demo_result.get("reconciliation"), "status", None),
        realized_pl=(
            settlement.realized_pl if isinstance(settlement, PredictionSettlement) else None
        ),
        evidence_hash=evidence_hash,
        next_action=str(demo_result["next_action"]),
    )


def prediction_demo_batch_item(
    contract: PredictionContract,
    *,
    status: str,
    next_action: str,
    source: str | None = None,
    source_reference: str | None = None,
    csv_format: str | None = None,
    settlement_value: Decimal | None = None,
    executable_price: Decimal | None = None,
    limit_price: Decimal | None = None,
    completed_lifecycle: bool = False,
    skipped: bool = False,
    skip_reason: str | None = None,
    intent_id: str | None = None,
    order_id: str | None = None,
    fill_id: str | None = None,
    position_id: str | None = None,
    settlement_id: str | None = None,
    reconciliation_status: ReconciliationStatus | None = None,
    realized_pl: Decimal | None = None,
    evidence_hash: str | None = None,
) -> dict[str, object]:
    raw_payload = contract.raw_payload or {}
    return {
        "contract_id": contract.id,
        "contract_ticker": contract.contract_ticker,
        "status": status,
        "source": source or raw_payload.get("source"),
        "source_reference": source_reference or raw_payload.get("source_reference"),
        "csv_format": csv_format or raw_payload.get("csv_format"),
        "settlement_value": settlement_value or contract.settlement_value,
        "executable_price": executable_price,
        "limit_price": limit_price,
        "completed_lifecycle": completed_lifecycle,
        "skipped": skipped,
        "skip_reason": skip_reason,
        "intent_id": intent_id,
        "order_id": order_id,
        "fill_id": fill_id,
        "position_id": position_id,
        "settlement_id": settlement_id,
        "reconciliation_status": reconciliation_status,
        "realized_pl": realized_pl,
        "evidence_hash": evidence_hash,
        "next_action": next_action,
    }


def entity_id(entity: object) -> str | None:
    return str(getattr(entity, "id", "")) or None


def settlement_evidence_hash(db: Session, settlement_id: str) -> str | None:
    event = db.execute(
        select(PredictionEvidenceEvent)
        .where(
            PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.SETTLEMENT_RECORDED,
            PredictionEvidenceEvent.entity_id == settlement_id,
        )
        .order_by(PredictionEvidenceEvent.occurred_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return event.evidence_hash if event is not None else None


def demo_run_response(
    *,
    status: str,
    next_action: str,
    intent: PredictionOrderIntent,
    run_snapshot: dict[str, object],
    order: PredictionOrder | None = None,
    fill: PredictionFill | None = None,
    position: PredictionPosition | None = None,
    settlement: PredictionSettlement | None = None,
    reconciliation: PredictionReconciliationReport | None = None,
    completed_lifecycle: bool = False,
) -> dict[str, object]:
    return {
        "status": status,
        "completed_lifecycle": completed_lifecycle,
        "next_action": next_action,
        "intent": intent,
        "order": order,
        "fill": fill,
        "position": position,
        "settlement": settlement,
        "reconciliation": reconciliation,
        "run_snapshot": run_snapshot,
    }


def demo_contract_for_payload(
    db: Session,
    payload: PredictionPaperDemoRunRequest,
) -> tuple[PredictionContract, str]:
    if payload.contract_id:
        contract = db.get(PredictionContract, payload.contract_id)
        if contract is None:
            raise ValueError("Prediction contract not found")
        return contract, "contract_id"

    price_column = (
        PredictionContract.yes_ask_price
        if payload.side.value == "YES"
        else PredictionContract.no_ask_price
    )
    contract = db.execute(
        select(PredictionContract)
        .where(
            PredictionContract.status == PredictionMarketStatus.OPEN,
            price_column.is_not(None),
        )
        .order_by(PredictionContract.last_seen_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if contract is None:
        raise ValueError("No open actionable prediction contract snapshot is available")
    return contract, "latest_open_actionable"


def executable_contract_price(
    contract: PredictionContract,
    side: object,
) -> Decimal | None:
    if str(getattr(side, "value", side)) == "YES":
        return contract.yes_ask_price
    return contract.no_ask_price


def build_prediction_paper_demo_progress(
    db: Session,
    *,
    strategy: str | None = None,
) -> PredictionPaperDemoProgressResponse:
    target_closed_records = 100
    target_calendar_days = 30
    target_active_days = 15
    target_unique_contracts = 25
    max_single_day_share_limit = Decimal("0.25")
    max_single_contract_share_limit = Decimal("0.10")
    minimum_profit_factor = Decimal("1.20")
    settlements = list(
        db.execute(
            select(PredictionSettlement).order_by(PredictionSettlement.settled_at.asc())
        ).scalars()
    )
    latest_reconciliation = db.execute(
        select(PredictionReconciliationReport)
        .order_by(PredictionReconciliationReport.reconciled_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    current_reconciliation_discrepancies = (
        PredictionMarketPaperEngine(db).paper_reconciliation_discrepancies()
    )
    ledger_records = prediction_paper_demo_records_for_settlements(
        db,
        settlements,
        latest_reconciliation,
        current_reconciliation_discrepancies,
    )
    if strategy is not None:
        ledger_records = [
            record for record in ledger_records if strategy in record.strategies
        ]
        strategy_settlement_ids = {record.settlement_id for record in ledger_records}
        settlements = [
            settlement
            for settlement in settlements
            if settlement.id in strategy_settlement_ids
        ]
    raw_closed_records = len(settlements)
    raw_latest_closed_at = settlements[-1].settled_at if settlements else None
    matched_reconciliation = (
        latest_reconciliation is not None
        and latest_reconciliation.status == ReconciliationStatus.MATCHED
        and (
            raw_latest_closed_at is None
            or ensure_utc(latest_reconciliation.reconciled_at)
            >= ensure_utc(raw_latest_closed_at)
        )
    )
    countable_settlement_ids = {
        record.settlement_id for record in ledger_records if record.counts_toward_target
    }
    evidence_settlements = [
        settlement for settlement in settlements if settlement.id in countable_settlement_ids
    ]
    closed_records = len(evidence_settlements)
    first_closed_at = evidence_settlements[0].settled_at if evidence_settlements else None
    latest_closed_at = evidence_settlements[-1].settled_at if evidence_settlements else None
    calendar_days = (
        (latest_closed_at.date() - first_closed_at.date()).days + 1
        if first_closed_at is not None and latest_closed_at is not None
        else 0
    )
    daily_counts = Counter(
        settlement.settled_at.date().isoformat() for settlement in evidence_settlements
    )
    contract_counts = Counter(
        settlement.contract.contract_ticker for settlement in evidence_settlements
    )
    active_days = len(daily_counts)
    max_single_day_records = max(daily_counts.values(), default=0)
    max_single_day_record_share = (
        Decimal(max_single_day_records) / Decimal(closed_records)
        if closed_records
        else Decimal("0")
    )
    max_single_contract_records = max(contract_counts.values(), default=0)
    max_single_contract_record_share = (
        Decimal(max_single_contract_records) / Decimal(closed_records)
        if closed_records
        else Decimal("0")
    )
    fee_net_realized_pl = sum(
        (settlement.realized_pl for settlement in evidence_settlements),
        Decimal("0"),
    )
    total_fees = sum((settlement.fees for settlement in evidence_settlements), Decimal("0"))
    expectancy = (
        fee_net_realized_pl / Decimal(closed_records) if closed_records else Decimal("0")
    )
    winning_records = sum(
        1 for settlement in evidence_settlements if settlement.realized_pl > 0
    )
    losing_records = sum(
        1 for settlement in evidence_settlements if settlement.realized_pl < 0
    )
    breakeven_records = closed_records - winning_records - losing_records
    gross_profit = sum(
        (
            settlement.realized_pl
            for settlement in evidence_settlements
            if settlement.realized_pl > 0
        ),
        Decimal("0"),
    )
    gross_loss = abs(
        sum(
            (
                settlement.realized_pl
                for settlement in evidence_settlements
                if settlement.realized_pl < 0
            ),
            Decimal("0"),
        )
    )
    profit_factor = (
        None
        if gross_loss == 0
        else gross_profit / gross_loss
    )
    max_drawdown = prediction_demo_max_drawdown(
        [settlement.realized_pl for settlement in evidence_settlements]
    )
    unique_contracts = len(contract_counts)
    countable_ledger_records = sum(
        1 for record in ledger_records if record.counts_toward_target
    )
    ledger_blocked_records = len(ledger_records) - countable_ledger_records
    provenance_complete_records = sum(
        1
        for record in ledger_records
        if record.counts_toward_target
        and record.source
        and record.source_reference
        and record.csv_format
    )
    provenance_missing_records = closed_records - provenance_complete_records
    remaining_records = max(target_closed_records - closed_records, 0)
    remaining_calendar_days = max(target_calendar_days - calendar_days, 0)
    remaining_active_days = max(target_active_days - active_days, 0)
    remaining_unique_contracts = max(target_unique_contracts - unique_contracts, 0)
    profit_factor_passes = (
        gross_profit > 0 if profit_factor is None else profit_factor >= minimum_profit_factor
    )
    checks = [
        progress_check(
            "minimum_closed_records",
            closed_records >= target_closed_records,
            f"{closed_records}/{target_closed_records} closed paper/demo records.",
            f"Collect {remaining_records} more closed paper/demo record(s).",
        ),
        progress_check(
            "minimum_calendar_days",
            calendar_days >= target_calendar_days,
            f"{calendar_days}/{target_calendar_days} calendar day(s) observed.",
            f"Extend the evidence window by {remaining_calendar_days} calendar day(s).",
        ),
        progress_check(
            "minimum_active_days",
            active_days >= target_active_days,
            f"{active_days}/{target_active_days} active paper/demo day(s).",
            f"Collect paper/demo records on {remaining_active_days} more active day(s).",
        ),
        progress_check(
            "single_day_concentration",
            closed_records == 0 or max_single_day_record_share <= max_single_day_share_limit,
            (
                f"Max single-day share is {max_single_day_record_share:.2%} "
                f"across {max_single_day_records} record(s)."
            ),
            "Spread paper/demo evidence across more days before live review.",
        ),
        progress_check(
            "minimum_unique_contracts",
            unique_contracts >= target_unique_contracts,
            f"{unique_contracts}/{target_unique_contracts} unique contract(s).",
            f"Collect paper/demo records across {remaining_unique_contracts} more contract(s).",
        ),
        progress_check(
            "single_contract_concentration",
            closed_records == 0
            or max_single_contract_record_share <= max_single_contract_share_limit,
            (
                f"Max single-contract share is {max_single_contract_record_share:.2%} "
                f"across {max_single_contract_records} record(s)."
            ),
            "Spread paper/demo evidence across more contracts before live review.",
        ),
        progress_check(
            "snapshot_provenance",
            closed_records > 0 and provenance_missing_records == 0,
            (
                f"{provenance_complete_records}/{closed_records} record(s) include imported "
                "snapshot provenance."
            ),
            (
                "Use imported market snapshots with source reference and CSV format before "
                "live review."
            ),
        ),
        progress_check(
            "countable_ledger_records",
            raw_closed_records > 0
            and countable_ledger_records == raw_closed_records
            and ledger_blocked_records == 0,
            (
                f"{countable_ledger_records}/{raw_closed_records} closed record(s) are "
                "clean in the demo ledger."
            ),
            "Resolve demo-ledger blockers before counting evidence.",
        ),
        progress_check(
            "positive_expectancy",
            closed_records > 0 and expectancy > 0,
            f"Fee-net expectancy is {expectancy}.",
            "Paper/demo expectancy must be positive after fees.",
        ),
        progress_check(
            "profit_factor",
            profit_factor_passes,
            (
                "No losses recorded; gross profit is positive."
                if profit_factor is None and gross_profit > 0
                else f"Profit factor is {profit_factor or Decimal('0')}."
            ),
            f"Paper/demo profit factor must be at least {minimum_profit_factor}.",
        ),
        progress_check(
            "matched_reconciliation",
            matched_reconciliation,
            (
                "Latest prediction-market reconciliation matched."
                if matched_reconciliation
                else "No matched prediction-market reconciliation after the latest settlement yet."
            ),
            "Run prediction-market paper reconciliation before live review.",
        ),
    ]
    ready_for_live_review = all(bool(check["passed"]) for check in checks)
    current_check = next((check for check in checks if not bool(check["passed"])), None)
    completed_check_count = sum(1 for check in checks if bool(check["passed"]))
    total_check_count = len(checks)
    progress_pct = round(
        (completed_check_count / total_check_count) * 100 if total_check_count else 0,
        2,
    )

    if raw_closed_records == 0:
        progress_status = "NO_PAPER_DEMO_RECORDS"
        next_action = "Run guided paper/demo trades from recorded prediction-market snapshots."
    elif not matched_reconciliation:
        progress_status = "RECONCILIATION_REQUIRED"
        next_action = "Run prediction-market paper reconciliation before counting demo evidence."
    elif ledger_blocked_records > 0:
        progress_status = "PAPER_DEMO_LEDGER_BLOCKED"
        next_action = "Resolve demo-ledger blockers before counting paper/demo evidence."
    elif ready_for_live_review:
        progress_status = "PAPER_DEMO_EVIDENCE_TARGET_MET"
        next_action = "Run independent live-readiness review; live execution remains disabled."
    else:
        progress_status = "COLLECTING_PAPER_DEMO_EVIDENCE"
        next_action = next(
            (str(check["next_action"]) for check in checks if not bool(check["passed"])),
            "Continue collecting diversified paper/demo evidence.",
        )

    return PredictionPaperDemoProgressResponse(
        generated_at=utc_now(),
        status=progress_status,
        ready_for_live_review=ready_for_live_review,
        current_check=current_check,
        completed_check_count=completed_check_count,
        total_check_count=total_check_count,
        progress_pct=progress_pct,
        target_closed_records=target_closed_records,
        target_calendar_days=target_calendar_days,
        target_active_days=target_active_days,
        target_unique_contracts=target_unique_contracts,
        raw_closed_records=raw_closed_records,
        closed_records=closed_records,
        calendar_days=calendar_days,
        active_days=active_days,
        unique_contracts=unique_contracts,
        remaining_records=remaining_records,
        remaining_calendar_days=remaining_calendar_days,
        remaining_active_days=remaining_active_days,
        remaining_unique_contracts=remaining_unique_contracts,
        fee_net_realized_pl=fee_net_realized_pl,
        total_fees=total_fees,
        expectancy=expectancy,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        winning_records=winning_records,
        losing_records=losing_records,
        breakeven_records=breakeven_records,
        max_single_day_records=max_single_day_records,
        max_single_day_record_share=max_single_day_record_share,
        max_single_contract_records=max_single_contract_records,
        max_single_contract_record_share=max_single_contract_record_share,
        provenance_complete_records=provenance_complete_records,
        provenance_missing_records=provenance_missing_records,
        countable_ledger_records=countable_ledger_records,
        ledger_blocked_records=ledger_blocked_records,
        first_closed_at=first_closed_at,
        latest_closed_at=latest_closed_at,
        latest_reconciliation_status=(
            latest_reconciliation.status if latest_reconciliation is not None else None
        ),
        checks=checks,
        distribution={
            "daily_counts": dict(sorted(daily_counts.items())),
            "contract_counts": dict(sorted(contract_counts.items())),
            "max_single_day_share_limit": str(max_single_day_share_limit),
            "max_single_contract_share_limit": str(max_single_contract_share_limit),
            "minimum_profit_factor": str(minimum_profit_factor),
        },
        next_action=next_action,
        live_execution_enabled=False,
    )


def build_prediction_paper_demo_runbook(
    db: Session,
) -> PredictionPaperDemoRunbookResponse:
    readiness = build_prediction_paper_demo_readiness(db)
    progress = build_prediction_paper_demo_progress(db)
    evidence = readiness.evidence
    eligible_research_candidates = int(
        evidence.get("eligible_mkt_research_candidates") or 0
    )
    upstream_research_runbook = (
        prediction_paper_demo_upstream_research_runbook()
        if eligible_research_candidates == 0
        else None
    )
    latest_reconciliation_status = evidence.get("latest_reconciliation_status")
    evidence_step_status = (
        "PASSED"
        if progress.ready_for_live_review
        else "BLOCKED"
    )
    live_review_status = "READY" if progress.ready_for_live_review else "BLOCKED"
    steps = [
        prediction_paper_demo_runbook_step(
            rank=1,
            key="live_execution_disabled",
            label="Keep live execution disabled",
            status="PASSED",
            evidence="Prediction paper/demo runbook live_execution_enabled=false.",
            next_action="Keep live execution disabled while collecting paper/demo evidence.",
        ),
        prediction_paper_demo_runbook_step(
            rank=2,
            key="eligible_mkt_research_candidate",
            label="Pass an MKT research gate",
            status="PASSED" if eligible_research_candidates > 0 else "BLOCKED",
            evidence=(
                f"{eligible_research_candidates} eligible MKT research candidate(s)."
                + prediction_paper_demo_upstream_evidence(upstream_research_runbook)
            ),
            next_action=prediction_paper_demo_upstream_next_action(
                upstream_research_runbook,
            ),
        ),
        prediction_paper_demo_runbook_step(
            rank=3,
            key="prediction_contract_snapshot_recorded",
            label="Record or import a contract snapshot",
            status=(
                "PASSED"
                if int(evidence.get("contract_snapshots") or 0) > 0
                else "BLOCKED"
            ),
            evidence=(
                f"{evidence.get('contract_snapshots') or 0} contract snapshot(s); "
                f"{evidence.get('open_contracts') or 0} open."
            ),
            next_action="Record or import a prediction-market contract snapshot.",
        ),
        prediction_paper_demo_runbook_step(
            rank=4,
            key="approved_paper_intent_gate",
            label="Create an approved paper intent",
            status=(
                "PASSED"
                if int(evidence.get("approved_research_intents") or 0) > 0
                else "BLOCKED"
            ),
            evidence=(
                f"{evidence.get('approved_research_intents') or 0} approved paper "
                "intent(s)."
            ),
            writes_ledger=True,
            next_action=(
                "Create a paper intent for an MKT strategy with accepted research evidence."
            ),
        ),
        prediction_paper_demo_runbook_step(
            rank=5,
            key="paper_fill_recorded",
            label="Submit paper order and record fill",
            status="PASSED" if int(evidence.get("fills") or 0) > 0 else "BLOCKED",
            evidence=f"{evidence.get('fills') or 0} paper fill(s).",
            writes_ledger=True,
            next_action="Submit the paper intent and record a fill or partial fill.",
        ),
        prediction_paper_demo_runbook_step(
            rank=6,
            key="paper_settlement_recorded",
            label="Settle the paper position",
            status=(
                "PASSED"
                if int(evidence.get("settlements") or 0) > 0
                else "BLOCKED"
            ),
            evidence=f"{evidence.get('settlements') or 0} settlement(s).",
            writes_ledger=True,
            next_action="Settle the paper prediction-market position.",
        ),
        prediction_paper_demo_runbook_step(
            rank=7,
            key="paper_reconciliation_matched",
            label="Run matched paper reconciliation",
            status=(
                "PASSED"
                if latest_reconciliation_status == ReconciliationStatus.MATCHED.value
                else "BLOCKED"
            ),
            evidence=f"Latest reconciliation: {latest_reconciliation_status or 'none'}.",
            writes_ledger=True,
            next_action="Run prediction-market paper reconciliation and resolve discrepancies.",
        ),
        prediction_paper_demo_runbook_step(
            rank=8,
            key="paper_demo_lifecycle_evidence_complete",
            label="Verify lifecycle evidence trail",
            status=(
                "PASSED"
                if int(evidence.get("settlements") or 0) > 0
                and int(evidence.get("ledger_blocked_records") or 0) == 0
                and int(evidence.get("countable_ledger_records") or 0)
                == int(evidence.get("settlements") or 0)
                else "BLOCKED"
            ),
            evidence=(
                f"{evidence.get('countable_ledger_records') or 0}/"
                f"{evidence.get('settlements') or 0} settled record(s) lifecycle-clean; "
                f"{evidence.get('ledger_blocked_records') or 0} blocked."
            ),
            writes_ledger=True,
            next_action=(
                "Resolve paper-demo ledger lifecycle blockers before collecting evidence."
            ),
        ),
        prediction_paper_demo_runbook_step(
            rank=9,
            key="paper_demo_evidence_target",
            label="Collect diversified paper/demo evidence",
            status=evidence_step_status,
            evidence=(
                f"{progress.closed_records}/{progress.target_closed_records} closed, "
                f"{progress.calendar_days}/{progress.target_calendar_days} calendar day(s), "
                f"{progress.active_days}/{progress.target_active_days} active day(s), "
                f"{progress.unique_contracts}/{progress.target_unique_contracts} unique "
                "contract(s)."
            ),
            writes_ledger=True,
            next_action=progress.next_action,
        ),
        prediction_paper_demo_runbook_step(
            rank=10,
            key="independent_live_review_boundary",
            label="Run independent live-readiness review",
            status=live_review_status,
            evidence=(
                "Paper/demo evidence target met."
                if progress.ready_for_live_review
                else "Paper/demo evidence target is not met."
            ),
            next_action=(
                "Run independent live-readiness review; live execution remains disabled."
                if progress.ready_for_live_review
                else "Meet paper/demo evidence targets before any live-readiness review."
            ),
        ),
    ]
    current_step = next((step for step in steps if step.status == "BLOCKED"), None)
    if current_step is None:
        current_step = next((step for step in steps if step.status == "READY"), None)
    completed_step_count = sum(1 for step in steps if step.status == "PASSED")
    total_step_count = len(steps)
    progress_pct = round(
        (completed_step_count / total_step_count) * 100 if total_step_count else 0,
        2,
    )
    if progress.ready_for_live_review:
        status_text = "RUNBOOK_READY_FOR_LIVE_REVIEW"
    elif readiness.demo_lifecycle_verified:
        status_text = "RUNBOOK_COLLECT_EVIDENCE"
    elif readiness.ready_to_start:
        status_text = "RUNBOOK_RUN_PAPER_LIFECYCLE"
    else:
        status_text = "RUNBOOK_READINESS_BLOCKED"

    return PredictionPaperDemoRunbookResponse(
        generated_at=utc_now(),
        status=status_text,
        readiness_status=readiness.status,
        progress_status=progress.status,
        upstream_research_runbook=upstream_research_runbook,
        current_step=current_step,
        completed_step_count=completed_step_count,
        total_step_count=total_step_count,
        progress_pct=progress_pct,
        steps=steps,
        blockers=[step.key for step in steps if step.status == "BLOCKED"],
        next_action=(
            current_step.next_action
            if current_step is not None
            else "Paper/demo path is ready for independent live-readiness review."
        ),
        readiness=readiness,
        progress=progress,
        live_execution_enabled=False,
    )


def build_prediction_paper_demo_ledger(
    db: Session,
    *,
    limit: int = 50,
) -> PredictionPaperDemoEvidenceLedgerResponse:
    bounded_limit = max(1, min(limit, 200))
    settlements = list(
        db.execute(
            select(PredictionSettlement)
            .order_by(PredictionSettlement.settled_at.desc())
            .limit(bounded_limit)
        ).scalars()
    )
    latest_reconciliation = db.execute(
        select(PredictionReconciliationReport)
        .order_by(PredictionReconciliationReport.reconciled_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    current_reconciliation_discrepancies = (
        PredictionMarketPaperEngine(db).paper_reconciliation_discrepancies()
    )

    records = prediction_paper_demo_records_for_settlements(
        db,
        settlements,
        latest_reconciliation,
        current_reconciliation_discrepancies,
    )
    countable_records = sum(1 for record in records if record.counts_toward_target)
    blocked_records = len(records) - countable_records
    if not records:
        next_action = "Run guided paper/demo trades from recorded prediction-market snapshots."
    elif blocked_records:
        next_action = "Inspect paper-demo ledger blockers before counting these records."
    else:
        next_action = (
            "Paper-demo ledger records are evidence-clean; continue collecting until progress "
            "targets are met."
        )

    return PredictionPaperDemoEvidenceLedgerResponse(
        generated_at=utc_now(),
        records=records,
        record_count=len(records),
        countable_records=countable_records,
        blocked_records=blocked_records,
        latest_reconciliation_status=(
            latest_reconciliation.status if latest_reconciliation is not None else None
        ),
        next_action=next_action,
        live_execution_enabled=False,
    )


def build_prediction_paper_demo_campaign_audit(
    db: Session,
    *,
    limit: int = 20,
) -> PredictionPaperDemoCampaignAuditResponse:
    bounded_limit = max(1, min(limit, 100))
    events = list(
        db.execute(
            select(PredictionEvidenceEvent)
            .where(PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.PAPER_DEMO_CAMPAIGN)
            .order_by(PredictionEvidenceEvent.occurred_at.desc())
            .limit(bounded_limit)
        ).scalars()
    )
    records = [prediction_campaign_audit_record(db, event) for event in events]
    side_sensitive_records = sum(
        1 for record in records if record.side_sensitivity_warning is not None
    )
    acknowledged_records = sum(
        1 for record in records if record.side_sensitivity_acknowledged
    )
    current_result_clean_records = current_result_clean_count(records)
    current_result_drifted_records = current_result_drifted_count(records)
    if not records:
        next_action = "Run a guarded MKT DB campaign replay to create campaign audit evidence."
    elif current_result_drifted_records:
        next_action = (
            "Resolve campaign current-result ledger drift before relying on campaign "
            "evidence."
        )
    elif side_sensitive_records > acknowledged_records:
        next_action = "Review campaign side-sensitivity acknowledgements before trusting evidence."
    else:
        next_action = "Campaign audit evidence is available for review."

    return PredictionPaperDemoCampaignAuditResponse(
        generated_at=utc_now(),
        records=records,
        record_count=len(records),
        acknowledged_records=acknowledged_records,
        side_sensitive_records=side_sensitive_records,
        current_result_clean_records=current_result_clean_records,
        current_result_drifted_records=current_result_drifted_records,
        latest_evidence_hash=records[0].evidence_hash if records else None,
        next_action=next_action,
        live_execution_enabled=False,
    )


def build_prediction_paper_demo_batch_audit(
    db: Session,
    *,
    limit: int = 20,
) -> PredictionPaperDemoBatchAuditResponse:
    bounded_limit = max(1, min(limit, 100))
    events = list(
        db.execute(
            select(PredictionEvidenceEvent)
            .where(PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.PAPER_DEMO_BATCH)
            .order_by(PredictionEvidenceEvent.occurred_at.desc())
            .limit(bounded_limit)
        ).scalars()
    )
    records = [prediction_batch_audit_record(db, event) for event in events]
    current_result_clean_records = current_result_clean_count(records)
    current_result_drifted_records = current_result_drifted_count(records)
    if not records:
        next_action = (
            "Run reviewed prediction paper/demo batch replay to create batch audit evidence."
        )
    elif current_result_drifted_records:
        next_action = (
            "Resolve batch current-result ledger drift before relying on batch "
            "evidence."
        )
    else:
        next_action = "Batch replay audit evidence is available for review."
    return PredictionPaperDemoBatchAuditResponse(
        generated_at=utc_now(),
        records=records,
        record_count=len(records),
        current_result_clean_records=current_result_clean_records,
        current_result_drifted_records=current_result_drifted_records,
        latest_evidence_hash=records[0].evidence_hash if records else None,
        next_action=next_action,
        live_execution_enabled=False,
    )


def prediction_batch_audit_record(
    db: Session,
    event: PredictionEvidenceEvent,
) -> PredictionPaperDemoBatchAuditRecordResponse:
    payload = event.payload or {}
    batch = payload.get("batch") if isinstance(payload.get("batch"), dict) else {}
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    ledger = payload.get("ledger") if isinstance(payload.get("ledger"), dict) else {}
    current_check = (
        progress.get("current_check") if isinstance(progress.get("current_check"), dict) else {}
    )
    current_result_ledger = paper_demo_current_result_ledger(db, payload)
    return PredictionPaperDemoBatchAuditRecordResponse(
        evidence_event_id=event.id,
        evidence_hash=event.evidence_hash,
        occurred_at=event.occurred_at,
        strategy=event.strategy,
        status=str(payload.get("status")) if payload.get("status") is not None else None,
        source=str(payload.get("source")) if payload.get("source") is not None else None,
        source_reference=(
            str(payload.get("source_reference"))
            if payload.get("source_reference") is not None
            else None
        ),
        side=prediction_side_or_none(payload.get("side")),
        preflight_hash=(
            str(payload.get("preflight_hash"))
            if payload.get("preflight_hash") is not None
            else None
        ),
        reviewed_preflight_hash=(
            str(payload.get("reviewed_preflight_hash"))
            if payload.get("reviewed_preflight_hash") is not None
            else None
        ),
        attempted_records=int(batch.get("attempted_records") or 0),
        completed_records=int(batch.get("completed_records") or 0),
        skipped_records=int(batch.get("skipped_records") or 0),
        rejected_records=int(batch.get("rejected_records") or 0),
        countable_records=int(
            progress.get("countable_ledger_records")
            or ledger.get("countable_records")
            or 0
        ),
        blocked_records=int(
            progress.get("ledger_blocked_records") or ledger.get("blocked_records") or 0
        ),
        target_closed_records=int(progress.get("target_closed_records") or 100),
        raw_closed_records=int(
            progress.get("raw_closed_records")
            or progress.get("closed_records")
            or ledger.get("record_count")
            or 0
        ),
        remaining_records=int(progress.get("remaining_records") or 0),
        remaining_unique_contracts=int(progress.get("remaining_unique_contracts") or 0),
        progress_pct=float(progress.get("progress_pct") or 0),
        current_check_key=(
            str(current_check.get("key")) if current_check.get("key") is not None else None
        ),
        fee_net_realized_pl=Decimal(str(progress.get("fee_net_realized_pl") or "0")),
        ready_for_live_review=bool(progress.get("ready_for_live_review")),
        current_result_records=current_result_ledger["record_count"],
        current_result_countable_records=current_result_ledger["countable_records"],
        current_result_blocked_records=current_result_ledger["blocked_records"],
        current_result_fee_net_realized_pl=current_result_ledger["fee_net_realized_pl"],
        current_result_ledger_status=str(current_result_ledger["status"]),
        current_result_ledger_blockers=list(current_result_ledger["blockers"]),
        payload=payload,
        live_execution_enabled=False,
    )


def current_result_clean_count(records: Iterable[object]) -> int:
    return sum(
        1
        for record in records
        if getattr(record, "current_result_ledger_status", None)
        == "CURRENT_RESULT_LEDGER_CLEAN"
    )


def current_result_drifted_count(records: Iterable[object]) -> int:
    return sum(
        1
        for record in records
        if getattr(record, "current_result_ledger_status", None)
        in {"CURRENT_RESULT_LEDGER_DRIFTED", "CURRENT_RESULT_LEDGER_MISSING"}
    )


def prediction_campaign_audit_record(
    db: Session,
    event: PredictionEvidenceEvent,
) -> PredictionPaperDemoCampaignAuditRecordResponse:
    payload = event.payload or {}
    db_import = payload.get("db_import") if isinstance(payload.get("db_import"), dict) else {}
    donor_quality = (
        payload.get("donor_quality")
        if isinstance(payload.get("donor_quality"), dict)
        else {}
    )
    batch = payload.get("batch") if isinstance(payload.get("batch"), dict) else {}
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    ledger = payload.get("ledger") if isinstance(payload.get("ledger"), dict) else {}
    current_check = (
        progress.get("current_check") if isinstance(progress.get("current_check"), dict) else {}
    )
    current_result_ledger = paper_demo_current_result_ledger(db, payload)
    side = prediction_side_or_none(payload.get("side"))
    return PredictionPaperDemoCampaignAuditRecordResponse(
        evidence_event_id=event.id,
        evidence_hash=event.evidence_hash,
        occurred_at=event.occurred_at,
        strategy=event.strategy,
        status=str(payload.get("status")) if payload.get("status") is not None else None,
        source=str(db_import.get("source")) if db_import.get("source") is not None else None,
        source_reference=(
            str(db_import.get("source_reference"))
            if db_import.get("source_reference") is not None
            else None
        ),
        import_hash=(
            str(db_import.get("import_hash")) if db_import.get("import_hash") is not None else None
        ),
        donor_quality_status=(
            str(donor_quality.get("status"))
            if donor_quality.get("status") is not None
            else None
        ),
        donor_evidence_tier=(
            str(donor_quality.get("evidence_tier"))
            if donor_quality.get("evidence_tier") is not None
            else None
        ),
        donor_use_scope=(
            str(donor_quality.get("aurex_use_scope"))
            if donor_quality.get("aurex_use_scope") is not None
            else None
        ),
        donor_backtest_depth_ready=bool(donor_quality.get("backtest_depth_ready")),
        side=side,
        side_sensitivity_warning=(
            str(payload.get("side_sensitivity_warning"))
            if payload.get("side_sensitivity_warning") is not None
            else None
        ),
        side_sensitivity_acknowledged=bool(
            payload.get("side_sensitivity_acknowledged")
        ),
        side_selection_rationale=(
            str(payload.get("side_selection_rationale"))
            if payload.get("side_selection_rationale") is not None
            else None
        ),
        attempted_records=int(batch.get("attempted_records") or 0),
        completed_records=int(batch.get("completed_records") or 0),
        skipped_records=int(batch.get("skipped_records") or 0),
        rejected_records=int(batch.get("rejected_records") or 0),
        countable_records=int(
            progress.get("countable_ledger_records")
            or ledger.get("countable_records")
            or 0
        ),
        blocked_records=int(
            progress.get("ledger_blocked_records") or ledger.get("blocked_records") or 0
        ),
        target_closed_records=int(progress.get("target_closed_records") or 100),
        raw_closed_records=int(
            progress.get("raw_closed_records")
            or progress.get("closed_records")
            or ledger.get("record_count")
            or 0
        ),
        remaining_records=int(progress.get("remaining_records") or 0),
        remaining_calendar_days=int(progress.get("remaining_calendar_days") or 0),
        remaining_active_days=int(progress.get("remaining_active_days") or 0),
        remaining_unique_contracts=int(progress.get("remaining_unique_contracts") or 0),
        progress_pct=float(progress.get("progress_pct") or 0),
        current_check_key=(
            str(current_check.get("key")) if current_check.get("key") is not None else None
        ),
        fee_net_realized_pl=Decimal(str(progress.get("fee_net_realized_pl") or "0")),
        ready_for_live_review=bool(progress.get("ready_for_live_review")),
        current_result_records=current_result_ledger["record_count"],
        current_result_countable_records=current_result_ledger["countable_records"],
        current_result_blocked_records=current_result_ledger["blocked_records"],
        current_result_fee_net_realized_pl=current_result_ledger["fee_net_realized_pl"],
        current_result_ledger_status=str(current_result_ledger["status"]),
        current_result_ledger_blockers=list(current_result_ledger["blockers"]),
        payload=payload,
        live_execution_enabled=False,
    )


def paper_demo_current_result_ledger(
    db: Session,
    payload: dict,
) -> dict[str, object]:
    batch = payload.get("batch") if isinstance(payload.get("batch"), dict) else {}
    result_ids = batch.get("result_ids") if isinstance(batch.get("result_ids"), list) else []
    settlement_ids = unique_strings(
        [
            str(item.get("settlement_id"))
            for item in result_ids
            if isinstance(item, dict) and item.get("settlement_id") is not None
        ]
    )
    expected_completed_records = int(batch.get("completed_records") or 0)
    blockers: list[str] = []
    if not settlement_ids:
        if expected_completed_records:
            blockers.append("paper_demo_result_settlement_ids_missing")
        return {
            "status": (
                "CURRENT_RESULT_LEDGER_MISSING"
                if blockers
                else "CURRENT_RESULT_LEDGER_EMPTY"
            ),
            "record_count": 0,
            "countable_records": 0,
            "blocked_records": 0,
            "fee_net_realized_pl": Decimal("0"),
            "blockers": blockers,
        }

    settlements = list(
        db.execute(
            select(PredictionSettlement)
            .where(PredictionSettlement.id.in_(settlement_ids))
            .order_by(PredictionSettlement.settled_at.desc())
    ).scalars()
    )
    found_ids = {settlement.id for settlement in settlements}
    missing_ids = [
        settlement_id
        for settlement_id in settlement_ids
        if settlement_id not in found_ids
    ]
    if missing_ids:
        blockers.append("paper_demo_result_settlements_missing")

    latest_reconciliation = db.execute(
        select(PredictionReconciliationReport)
        .order_by(PredictionReconciliationReport.reconciled_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    current_reconciliation_discrepancies = (
        PredictionMarketPaperEngine(db).paper_reconciliation_discrepancies()
    )
    records = prediction_paper_demo_records_for_settlements(
        db,
        settlements,
        latest_reconciliation,
        current_reconciliation_discrepancies,
    )
    countable_records = sum(1 for record in records if record.counts_toward_target)
    blocked_records = len(records) - countable_records
    if blocked_records:
        blockers.append("paper_demo_result_records_blocked")
    if expected_completed_records and countable_records != expected_completed_records:
        blockers.append("paper_demo_result_countable_records_drifted")

    record_blockers = [
        blocker
        for record in records
        for blocker in record.blockers
    ]
    blockers.extend(record_blockers)
    fee_net_realized_pl = sum(
        (record.realized_pl for record in records if record.counts_toward_target),
        Decimal("0"),
    )
    clean = not blockers
    return {
        "status": (
            "CURRENT_RESULT_LEDGER_CLEAN"
            if clean
            else "CURRENT_RESULT_LEDGER_DRIFTED"
        ),
        "record_count": len(records),
        "countable_records": countable_records,
        "blocked_records": blocked_records,
        "fee_net_realized_pl": fee_net_realized_pl,
        "blockers": unique_strings(blockers),
    }


def prediction_side_or_none(value: object) -> PredictionMarketSide | None:
    if value is None:
        return None
    try:
        return PredictionMarketSide(str(value))
    except ValueError:
        return None


def prediction_paper_demo_records_for_settlements(
    db: Session,
    settlements: list[PredictionSettlement],
    latest_reconciliation: PredictionReconciliationReport | None,
    current_reconciliation_discrepancies: list[dict[str, str]],
) -> list[PredictionPaperDemoEvidenceRecordResponse]:
    settlement_ids = [settlement.id for settlement in settlements]
    settlement_events: dict[str, PredictionEvidenceEvent] = {}
    if settlement_ids:
        events = list(
            db.execute(
                select(PredictionEvidenceEvent)
                .where(
                    PredictionEvidenceEvent.kind
                    == PredictionMarketEvidenceKind.SETTLEMENT_RECORDED,
                    PredictionEvidenceEvent.entity_id.in_(settlement_ids),
                )
                .order_by(PredictionEvidenceEvent.occurred_at.desc())
            ).scalars()
        )
        for event in events:
            if event.entity_id and event.entity_id not in settlement_events:
                settlement_events[event.entity_id] = event

    return [
        prediction_paper_demo_record(
            db,
            settlement,
            settlement_events.get(settlement.id),
            latest_reconciliation,
            current_reconciliation_discrepancies,
        )
        for settlement in settlements
    ]


def prediction_paper_demo_record(
    db: Session,
    settlement: PredictionSettlement,
    evidence_event: PredictionEvidenceEvent | None,
    latest_reconciliation: PredictionReconciliationReport | None,
    current_reconciliation_discrepancies: list[dict[str, str]],
) -> PredictionPaperDemoEvidenceRecordResponse:
    position = settlement.position
    contract = settlement.contract
    strategies = prediction_record_strategies(db, settlement, position)
    blockers: list[str] = []

    if evidence_event is None or not evidence_event.evidence_hash:
        blockers.append("settlement_evidence_missing")
    if position is None:
        blockers.append("position_missing")
    if not strategies:
        blockers.append("strategy_attribution_missing")
    if not bool((settlement.raw_payload or {}).get("paper_only")):
        blockers.append("paper_only_settlement_marker_missing")
    blockers.extend(settlement_evidence_integrity_blockers(settlement, evidence_event))

    reconciled_after_settlement = (
        latest_reconciliation is not None
        and ensure_utc(latest_reconciliation.reconciled_at) >= ensure_utc(settlement.settled_at)
    )
    if (
        latest_reconciliation is None
        or latest_reconciliation.status != ReconciliationStatus.MATCHED
        or not reconciled_after_settlement
    ):
        blockers.append("matched_reconciliation_after_settlement_missing")
    elif current_reconciliation_discrepancies:
        blockers.append("current_reconciliation_drift_detected")

    (
        recorded_evidence_kinds,
        missing_evidence_kinds,
        invalid_evidence_blockers,
    ) = prediction_demo_lifecycle_evidence_status(
        db,
        settlement,
        position,
        latest_reconciliation if reconciled_after_settlement else None,
    )
    if missing_evidence_kinds:
        blockers.append("paper_demo_lifecycle_evidence_missing")
    blockers.extend(invalid_evidence_blockers)

    raw_payload = contract.raw_payload or {}
    source = str(raw_payload.get("source") or "manual_snapshot")
    csv_format = raw_payload.get("csv_format")
    source_reference = raw_payload.get("source_reference")
    primary_strategy = (
        strategies[0]
        if len(strategies) == 1
        else "MIXED"
        if strategies
        else None
    )

    return PredictionPaperDemoEvidenceRecordResponse(
        settlement_id=settlement.id,
        position_id=settlement.position_id,
        contract_id=settlement.contract_id,
        contract_ticker=contract.contract_ticker,
        venue=contract.venue,
        side=position.side if position is not None else None,
        strategies=strategies,
        primary_strategy=primary_strategy,
        quantity=position.quantity if position is not None else None,
        average_entry_price=position.average_entry_price if position is not None else None,
        settlement_value=settlement.settlement_value,
        gross_payout=settlement.gross_payout,
        fees=settlement.fees,
        realized_pl=settlement.realized_pl,
        settled_at=settlement.settled_at,
        evidence_event_id=evidence_event.id if evidence_event is not None else None,
        evidence_hash=evidence_event.evidence_hash if evidence_event is not None else None,
        source=source,
        source_reference=str(source_reference) if source_reference is not None else None,
        csv_format=str(csv_format) if csv_format is not None else None,
        imported_from_mkt=(
            str(csv_format or "").lower() == "mkt_markets"
            or "krypt" in source.lower()
            or source.lower() in {"mkt", "my-krypt-trader", "my_krypt_trader"}
        ),
        reconciliation_report_id=(
            latest_reconciliation.id if reconciled_after_settlement else None
        ),
        reconciliation_status=(
            latest_reconciliation.status if reconciled_after_settlement else None
        ),
        recorded_evidence_kinds=recorded_evidence_kinds,
        missing_evidence_kinds=missing_evidence_kinds,
        counts_toward_target=not blockers,
        blockers=blockers,
        live_execution_enabled=False,
    )


def settlement_evidence_integrity_blockers(
    settlement: PredictionSettlement,
    evidence_event: PredictionEvidenceEvent | None,
) -> list[str]:
    if evidence_event is None:
        return []

    blockers: list[str] = []
    if not prediction_evidence_event_hash_is_valid(evidence_event):
        blockers.append("settlement_evidence_hash_mismatch")

    if evidence_event.entity_type != "prediction_settlement" or (
        evidence_event.entity_id != settlement.id
    ):
        blockers.append("settlement_evidence_entity_mismatch")

    payload = evidence_event.payload if isinstance(evidence_event.payload, dict) else {}
    if payload.get("position_id") != settlement.position_id:
        blockers.append("settlement_evidence_payload_mismatch")
        return blockers

    money_fields = {
        "settlement_value": settlement.settlement_value,
        "gross_payout": settlement.gross_payout,
        "realized_pl": settlement.realized_pl,
        "fees": settlement.fees,
    }
    for key, expected in money_fields.items():
        try:
            observed = Decimal(str(payload[key]))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            blockers.append("settlement_evidence_payload_mismatch")
            break
        if observed != expected:
            blockers.append("settlement_evidence_payload_mismatch")
            break

    return blockers


def prediction_record_strategies(
    db: Session,
    settlement: PredictionSettlement,
    position: PredictionPosition | None,
) -> list[str]:
    if position is None:
        return []
    fills = prediction_record_fills(db, settlement, position)
    return sorted(
        {
            fill.order.order_intent.strategy
            for fill in fills
            if fill.order is not None and fill.order.order_intent is not None
        }
    )


def prediction_demo_lifecycle_evidence_status(
    db: Session,
    settlement: PredictionSettlement,
    position: PredictionPosition | None,
    reconciliation: PredictionReconciliationReport | None,
) -> tuple[
    list[PredictionMarketEvidenceKind],
    list[PredictionMarketEvidenceKind],
    list[str],
]:
    requirements = prediction_demo_lifecycle_evidence_requirements(
        db,
        settlement,
        position,
        reconciliation,
    )
    recorded: list[PredictionMarketEvidenceKind] = []
    missing: list[PredictionMarketEvidenceKind] = []
    invalid_blockers: list[str] = []
    for kind, entity_type, entity_id in requirements:
        exists, invalid_reasons = prediction_evidence_event_exists(
            db,
            kind,
            entity_type,
            entity_id,
        )
        if exists:
            if kind not in recorded:
                recorded.append(kind)
        elif kind not in missing:
            missing.append(kind)
        invalid_blockers.extend(invalid_reasons)
    return recorded, missing, unique_strings(invalid_blockers)


def prediction_demo_lifecycle_evidence_requirements(
    db: Session,
    settlement: PredictionSettlement,
    position: PredictionPosition | None,
    reconciliation: PredictionReconciliationReport | None,
) -> list[tuple[PredictionMarketEvidenceKind, str, str | None]]:
    requirements: list[tuple[PredictionMarketEvidenceKind, str, str | None]] = [
        (
            PredictionMarketEvidenceKind.MARKET_SNAPSHOT,
            "prediction_contract",
            settlement.contract_id,
        ),
    ]
    if position is not None:
        fills = prediction_record_fills(db, settlement, position)
        for fill in fills:
            order = fill.order
            intent = order.order_intent if order is not None else None
            if intent is not None:
                requirements.append(
                    (
                        PredictionMarketEvidenceKind.ORDER_INTENT,
                        "prediction_order_intent",
                        intent.id,
                    )
                )
            requirements.append(
                (
                    PredictionMarketEvidenceKind.ORDER_SUBMITTED,
                    "prediction_order",
                    order.id if order is not None else None,
                )
            )
            requirements.append(
                (
                    PredictionMarketEvidenceKind.FILL_RECEIVED,
                    "prediction_fill",
                    fill.id,
                )
            )
    requirements.extend(
        [
            (
                PredictionMarketEvidenceKind.SETTLEMENT_RECORDED,
                "prediction_settlement",
                settlement.id,
            ),
            (
                PredictionMarketEvidenceKind.POSITION_RECONCILED,
                "prediction_reconciliation_report",
                reconciliation.id if reconciliation is not None else None,
            ),
        ]
    )
    return requirements


def prediction_record_fills(
    db: Session,
    settlement: PredictionSettlement,
    position: PredictionPosition,
) -> list[PredictionFill]:
    return list(
        db.execute(
            select(PredictionFill)
            .join(PredictionOrder)
            .join(PredictionOrderIntent)
            .where(
                PredictionOrderIntent.contract_id == settlement.contract_id,
                PredictionFill.side == position.side,
                PredictionFill.filled_at >= position.opened_at,
                PredictionFill.filled_at <= settlement.settled_at,
            )
            .order_by(PredictionFill.filled_at.asc())
        ).scalars()
    )


def prediction_evidence_event_exists(
    db: Session,
    kind: PredictionMarketEvidenceKind,
    entity_type: str,
    entity_id: str | None,
) -> tuple[bool, list[str]]:
    if entity_id is None:
        return False, []
    events = list(
        db.execute(
            select(PredictionEvidenceEvent).where(
                PredictionEvidenceEvent.kind == kind,
                PredictionEvidenceEvent.entity_type == entity_type,
                PredictionEvidenceEvent.entity_id == entity_id,
            )
        ).scalars()
    )
    invalid_reasons: list[str] = []
    for event in events:
        reasons = prediction_evidence_event_validity_reasons(db, event)
        if not reasons:
            return True, []
        invalid_reasons.extend(reasons)
    return False, unique_strings(invalid_reasons)


def prediction_evidence_event_hash_is_valid(event: PredictionEvidenceEvent) -> bool:
    expected_hash = hash_evidence_payload(
        event.kind,
        event.entity_type,
        event.entity_id,
        event.payload,
    )
    return event.evidence_hash == expected_hash


def prediction_evidence_event_validity_reasons(
    db: Session,
    event: PredictionEvidenceEvent,
) -> list[str]:
    prefix = evidence_reason_prefix(event.kind)
    reasons: list[str] = []
    if not prediction_evidence_event_hash_is_valid(event):
        reasons.append(f"{prefix}_evidence_hash_mismatch")

    expected_entity_type = evidence_entity_type_for(event.kind)
    if expected_entity_type is not None and event.entity_type != expected_entity_type:
        reasons.append(f"{prefix}_evidence_entity_mismatch")
        return unique_strings(reasons)

    if event.kind == PredictionMarketEvidenceKind.MARKET_SNAPSHOT:
        return unique_strings(reasons)

    payload = event.payload if isinstance(event.payload, dict) else None
    if payload is None:
        reasons.append(f"{prefix}_evidence_payload_mismatch")
        return unique_strings(reasons)

    if event.kind == PredictionMarketEvidenceKind.ORDER_INTENT:
        intent = db.get(PredictionOrderIntent, event.entity_id)
        if intent is None:
            reasons.append(f"{prefix}_evidence_row_missing")
        else:
            reasons.extend(order_intent_evidence_mismatches(intent, payload, prefix))
    elif event.kind == PredictionMarketEvidenceKind.ORDER_SUBMITTED:
        order = db.get(PredictionOrder, event.entity_id)
        if order is None:
            reasons.append(f"{prefix}_evidence_row_missing")
        else:
            reasons.extend(order_evidence_mismatches(order, payload, prefix))
    elif event.kind == PredictionMarketEvidenceKind.FILL_RECEIVED:
        fill = db.get(PredictionFill, event.entity_id)
        if fill is None:
            reasons.append(f"{prefix}_evidence_row_missing")
        else:
            reasons.extend(fill_evidence_mismatches(db, fill, payload, prefix))
    elif event.kind == PredictionMarketEvidenceKind.SETTLEMENT_RECORDED:
        settlement = db.get(PredictionSettlement, event.entity_id)
        if settlement is None:
            reasons.append(f"{prefix}_evidence_row_missing")
        else:
            reasons.extend(settlement_evidence_mismatches(settlement, payload, prefix))
    elif event.kind == PredictionMarketEvidenceKind.POSITION_RECONCILED:
        reconciliation = db.get(PredictionReconciliationReport, event.entity_id)
        if reconciliation is None:
            reasons.append(f"{prefix}_evidence_row_missing")
        else:
            reasons.extend(reconciliation_evidence_mismatches(reconciliation, payload, prefix))

    return unique_strings(reasons)


def order_intent_evidence_mismatches(
    intent: PredictionOrderIntent,
    payload: dict,
    prefix: str,
) -> list[str]:
    if (
        payload.get("strategy") == intent.strategy
        and payload.get("contract_ticker") == intent.contract.contract_ticker
        and payload.get("side") == intent.side.value
        and payload.get("action") == intent.action.value
        and payload_decimal_matches(payload, "quantity", intent.quantity)
        and payload_decimal_matches(payload, "limit_price", intent.limit_price)
        and payload_decimal_matches(payload, "max_cost", intent.max_cost)
    ):
        return []
    return [f"{prefix}_evidence_payload_mismatch"]


def order_evidence_mismatches(
    order: PredictionOrder,
    payload: dict,
    prefix: str,
) -> list[str]:
    if (
        payload.get("status") == order.status.value
        and payload.get("side") == order.side.value
        and payload.get("action") == order.action.value
        and payload_decimal_matches(payload, "limit_price", order.limit_price)
        and payload_decimal_matches(
            payload,
            "cumulative_filled_quantity",
            order.filled_quantity,
        )
    ):
        return []
    return [f"{prefix}_evidence_payload_mismatch"]


def fill_evidence_mismatches(
    db: Session,
    fill: PredictionFill,
    payload: dict,
    prefix: str,
) -> list[str]:
    position = None
    position_id = payload.get("position_id")
    if position_id is not None:
        position = db.get(PredictionPosition, str(position_id))
    position_matches = (
        position is not None
        and fill.order is not None
        and fill.order.order_intent is not None
        and position.contract_id == fill.order.order_intent.contract_id
        and position.side == fill.side
        and ensure_utc(position.opened_at) <= ensure_utc(fill.filled_at)
        and (
            position.closed_at is None
            or ensure_utc(fill.filled_at) <= ensure_utc(position.closed_at)
        )
    )
    if (
        payload.get("order_id") == fill.order_id
        and payload.get("side") == fill.side.value
        and payload.get("action") == fill.action.value
        and position_matches
        and payload_decimal_matches(payload, "quantity", fill.quantity)
        and payload_decimal_matches(payload, "price", fill.price)
        and payload_decimal_matches(payload, "fees", fill.fees)
    ):
        return []
    return [f"{prefix}_evidence_payload_mismatch"]


def settlement_evidence_mismatches(
    settlement: PredictionSettlement,
    payload: dict,
    prefix: str,
) -> list[str]:
    if (
        payload.get("position_id") == settlement.position_id
        and payload_decimal_matches(payload, "settlement_value", settlement.settlement_value)
        and payload_decimal_matches(payload, "gross_payout", settlement.gross_payout)
        and payload_decimal_matches(payload, "realized_pl", settlement.realized_pl)
        and payload_decimal_matches(payload, "fees", settlement.fees)
    ):
        return []
    return [f"{prefix}_evidence_payload_mismatch"]


def reconciliation_evidence_mismatches(
    reconciliation: PredictionReconciliationReport,
    payload: dict,
    prefix: str,
) -> list[str]:
    if (
        payload.get("status") == reconciliation.status.value
        and payload.get("summary") == reconciliation.summary
        and payload.get("discrepancies") == reconciliation.discrepancies
    ):
        return []
    return [f"{prefix}_evidence_payload_mismatch"]


def payload_decimal_matches(payload: dict, key: str, expected: Decimal) -> bool:
    try:
        return Decimal(str(payload[key])) == expected
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return False


def evidence_reason_prefix(kind: PredictionMarketEvidenceKind) -> str:
    return {
        PredictionMarketEvidenceKind.MARKET_SNAPSHOT: "market_snapshot",
        PredictionMarketEvidenceKind.ORDER_INTENT: "order_intent",
        PredictionMarketEvidenceKind.ORDER_SUBMITTED: "order",
        PredictionMarketEvidenceKind.FILL_RECEIVED: "fill",
        PredictionMarketEvidenceKind.SETTLEMENT_RECORDED: "settlement",
        PredictionMarketEvidenceKind.POSITION_RECONCILED: "reconciliation",
    }.get(kind, kind.value.lower())


def evidence_entity_type_for(kind: PredictionMarketEvidenceKind) -> str | None:
    return {
        PredictionMarketEvidenceKind.MARKET_SNAPSHOT: "prediction_contract",
        PredictionMarketEvidenceKind.ORDER_INTENT: "prediction_order_intent",
        PredictionMarketEvidenceKind.ORDER_SUBMITTED: "prediction_order",
        PredictionMarketEvidenceKind.FILL_RECEIVED: "prediction_fill",
        PredictionMarketEvidenceKind.SETTLEMENT_RECORDED: "prediction_settlement",
        PredictionMarketEvidenceKind.POSITION_RECONCILED: "prediction_reconciliation_report",
    }.get(kind)


def unique_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def build_prediction_paper_demo_readiness(
    db: Session,
) -> PredictionPaperDemoReadinessResponse:
    eligible_candidates = eligible_mkt_research_candidates(db)
    contract_snapshots = count_rows(db, PredictionContract)
    open_contracts = int(
        db.execute(
            select(func.count())
            .select_from(PredictionContract)
            .where(PredictionContract.status == PredictionMarketStatus.OPEN)
        ).scalar_one()
    )
    approved_research_intents = int(
        db.execute(
            select(func.count())
            .select_from(PredictionOrderIntent)
            .where(
                PredictionOrderIntent.intent_snapshot["research_gate"]["approved"].as_boolean()
                .is_(True)
            )
        ).scalar_one()
    )
    fills = count_rows(db, PredictionFill)
    settlements = count_rows(db, PredictionSettlement)
    latest_reconciliation = db.execute(
        select(PredictionReconciliationReport)
        .order_by(PredictionReconciliationReport.reconciled_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    current_reconciliation_discrepancies = (
        PredictionMarketPaperEngine(db).paper_reconciliation_discrepancies()
    )
    matched_reconciliation = (
        latest_reconciliation is not None
        and latest_reconciliation.status == ReconciliationStatus.MATCHED
    )
    settlement_rows = list(
        db.execute(
            select(PredictionSettlement).order_by(PredictionSettlement.settled_at.asc())
        ).scalars()
    )
    ledger_records = prediction_paper_demo_records_for_settlements(
        db,
        settlement_rows,
        latest_reconciliation,
        current_reconciliation_discrepancies,
    )
    countable_ledger_records = sum(
        1 for record in ledger_records if record.counts_toward_target
    )
    ledger_blocked_records = len(ledger_records) - countable_ledger_records

    checks = [
        readiness_check(
            "live_execution_disabled",
            True,
            "Live execution is disabled.",
            "Live execution must remain disabled for paper/demo readiness.",
        ),
        readiness_check(
            "eligible_mkt_research_candidate",
            bool(eligible_candidates),
            f"{len(eligible_candidates)} MKT research candidate(s) are paper-eligible.",
            "Pass an Aurex research gate for at least one MKT-derived candidate.",
        ),
        readiness_check(
            "prediction_contract_snapshot_recorded",
            contract_snapshots > 0,
            (
                f"{contract_snapshots} prediction contract snapshot(s) recorded; "
                f"{open_contracts} currently open."
            ),
            "Record a prediction-market contract snapshot.",
        ),
        readiness_check(
            "approved_paper_intent_gate",
            approved_research_intents > 0,
            f"{approved_research_intents} paper intent(s) have approved research-gate evidence.",
            "Create a paper intent for an eligible MKT strategy.",
        ),
        readiness_check(
            "paper_fill_recorded",
            fills > 0,
            f"{fills} paper fill(s) recorded.",
            "Submit the paper intent and record a fill or partial fill.",
        ),
        readiness_check(
            "paper_settlement_recorded",
            settlements > 0,
            f"{settlements} settlement(s) recorded.",
            "Settle the paper prediction-market position.",
        ),
        readiness_check(
            "paper_reconciliation_matched",
            matched_reconciliation,
            (
                "Latest prediction-market reconciliation matched."
                if matched_reconciliation
                else "No matched prediction-market reconciliation yet."
            ),
            "Run prediction-market paper reconciliation and resolve discrepancies.",
        ),
        readiness_check(
            "paper_demo_lifecycle_evidence_complete",
            settlements > 0
            and countable_ledger_records == settlements
            and ledger_blocked_records == 0,
            (
                f"{countable_ledger_records}/{settlements} settled paper/demo record(s) "
                "have complete lifecycle evidence."
            ),
            "Resolve paper-demo ledger blockers before treating the lifecycle as verified.",
        ),
    ]
    start_checks = checks[:3]
    lifecycle_checks = checks[3:]
    ready_to_start = all(bool(check["passed"]) for check in start_checks)
    demo_lifecycle_verified = ready_to_start and all(
        bool(check["passed"]) for check in lifecycle_checks
    )
    lifecycle_started = (
        approved_research_intents > 0
        or fills > 0
        or settlements > 0
        or latest_reconciliation is not None
    )
    if demo_lifecycle_verified:
        readiness_status = "PAPER_DEMO_VERIFIED"
    elif ready_to_start and lifecycle_started:
        readiness_status = "PAPER_DEMO_LIFECYCLE_BLOCKED"
    elif ready_to_start:
        readiness_status = "READY_TO_RUN_PAPER_DEMO"
    else:
        readiness_status = "BLOCKED"
    next_action = next(
        (str(check["next_action"]) for check in checks if not bool(check["passed"])),
        (
            "Paper demo lifecycle verified; keep live disabled and continue forward "
            "evidence collection."
        ),
    )
    current_check = next((check for check in checks if not bool(check["passed"])), None)
    completed_check_count = sum(1 for check in checks if bool(check["passed"]))
    total_check_count = len(checks)
    progress_pct = round(
        (completed_check_count / total_check_count) * 100 if total_check_count else 0,
        2,
    )
    return PredictionPaperDemoReadinessResponse(
        generated_at=utc_now(),
        status=readiness_status,
        ready_to_start=ready_to_start,
        demo_lifecycle_verified=demo_lifecycle_verified,
        current_check=current_check,
        completed_check_count=completed_check_count,
        total_check_count=total_check_count,
        progress_pct=progress_pct,
        next_action=next_action,
        checks=checks,
        evidence={
            "eligible_mkt_research_candidates": len(eligible_candidates),
            "contract_snapshots": contract_snapshots,
            "open_contracts": open_contracts,
            "approved_research_intents": approved_research_intents,
            "fills": fills,
            "settlements": settlements,
            "latest_reconciliation_status": (
                latest_reconciliation.status.value
                if latest_reconciliation is not None
                else None
            ),
            "countable_ledger_records": countable_ledger_records,
            "ledger_blocked_records": ledger_blocked_records,
            "live_execution_enabled": False,
        },
    )


def readiness_check(
    key: str,
    passed: bool,
    summary: str,
    next_action: str,
) -> dict[str, object]:
    return {
        "key": key,
        "passed": passed,
        "summary": summary,
        "next_action": "OK" if passed else next_action,
    }


def progress_check(
    key: str,
    passed: bool,
    summary: str,
    next_action: str,
) -> dict[str, object]:
    return {
        "key": key,
        "passed": passed,
        "summary": summary,
        "next_action": "OK" if passed else next_action,
    }


def prediction_paper_demo_upstream_research_runbook() -> dict[str, object]:
    try:
        runbook = mkt_research_intake_runbook(MktResearchImportRequest())
    except ValueError as exc:
        return {
            "status": "UPSTREAM_RESEARCH_RUNBOOK_ERROR",
            "db_path": MktResearchImportRequest().db_path,
            "current_step_key": None,
            "current_step_status": None,
            "current_command": None,
            "progress_pct": 0,
            "next_action": str(exc),
            "live_execution_enabled": False,
        }
    current_step = runbook.current_step
    return {
        "status": runbook.status,
        "db_path": runbook.db_path,
        "readiness_status": runbook.readiness_status,
        "db_freshness_status": runbook.db_freshness_status,
        "db_file_size_bytes": runbook.db_file_size_bytes,
        "db_modified_at": runbook.db_modified_at.isoformat()
        if runbook.db_modified_at
        else None,
        "latest_log_modified_at": runbook.latest_log_modified_at.isoformat()
        if runbook.latest_log_modified_at
        else None,
        "collection_activity_status": runbook.collection_activity_status,
        "collection_health_status": runbook.collection_health_status,
        "collection_health": runbook.collection_health.model_dump(mode="json"),
        "processed_observations": runbook.processed_observations,
        "resolved_observations": runbook.resolved_observations,
        "unresolved_observations": runbook.unresolved_observations,
        "backtest_depth_progress_pct": runbook.backtest_depth_progress_pct,
        "thresholds": [threshold.model_dump(mode="json") for threshold in runbook.thresholds],
        "current_step_key": current_step.key if current_step is not None else None,
        "current_step_status": current_step.status if current_step is not None else None,
        "current_command": runbook.current_command,
        "completed_step_count": runbook.completed_step_count,
        "total_step_count": runbook.total_step_count,
        "progress_pct": runbook.progress_pct,
        "next_action": runbook.next_action,
        "blockers": runbook.blockers,
        "live_execution_enabled": runbook.live_execution_enabled,
    }


def prediction_paper_demo_upstream_evidence(
    upstream_research_runbook: dict[str, object] | None,
) -> str:
    if upstream_research_runbook is None:
        return ""
    current_step_key = upstream_research_runbook.get("current_step_key") or "none"
    current_step_status = upstream_research_runbook.get("current_step_status") or "unknown"
    return (
        f" Upstream research runbook {upstream_research_runbook.get('status')}; "
        f"current step {current_step_key}/{current_step_status}."
    )


def prediction_paper_demo_upstream_next_action(
    upstream_research_runbook: dict[str, object] | None,
) -> str:
    if upstream_research_runbook is None:
        return "Pass an Aurex research gate for at least one MKT-derived candidate."
    return (
        "Resolve upstream MKT research runbook first: "
        f"{upstream_research_runbook.get('next_action')}"
    )


def prediction_paper_demo_runbook_step(
    *,
    rank: int,
    key: str,
    label: str,
    status: str,
    evidence: str,
    next_action: str,
    writes_ledger: bool = False,
) -> PredictionPaperDemoRunbookStepResponse:
    return PredictionPaperDemoRunbookStepResponse(
        rank=rank,
        key=key,
        label=label,
        status=status,
        evidence=evidence,
        writes_ledger=writes_ledger,
        next_action="OK" if status == "PASSED" else next_action,
    )


def prediction_demo_max_drawdown(values: list[Decimal]) -> Decimal:
    equity = Decimal("0")
    high_water = Decimal("0")
    max_drawdown = Decimal("0")
    for value in values:
        equity += value
        high_water = max(high_water, equity)
        max_drawdown = max(max_drawdown, high_water - equity)
    return max_drawdown


def eligible_mkt_research_candidates(db: Session) -> list[StrategyResearchCandidate]:
    candidates = list(
        db.execute(
            select(StrategyResearchCandidate).where(
                StrategyResearchCandidate.source == StrategyResearchSource.MY_KRYPT_TRADER,
                StrategyResearchCandidate.status == StrategyResearchStatus.PAPER_ELIGIBLE,
                StrategyResearchCandidate.trade_eligible.is_(True),
            )
        ).scalars()
    )
    eligible: list[StrategyResearchCandidate] = []
    for candidate in candidates:
        latest_run = db.execute(
            select(StrategyResearchBacktestRun)
            .where(StrategyResearchBacktestRun.candidate_id == candidate.id)
            .order_by(StrategyResearchBacktestRun.reviewed_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_run is not None and latest_run.accepted:
            eligible.append(candidate)
    return eligible
