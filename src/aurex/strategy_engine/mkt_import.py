from __future__ import annotations

import os
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from aurex.domain.enums import StrategyResearchObservationType, StrategyResearchStatus
from aurex.strategy_engine.schemas import (
    MktResearchCollectionHealthResponse,
    MktResearchImportPreflightResponse,
    MktResearchImportRequest,
    MktResearchImportResponse,
    MktResearchImportSourceQuality,
    MktResearchIntakeReadinessCheck,
    MktResearchIntakeReadinessResponse,
    MktResearchIntakeRunbookResponse,
    MktResearchIntakeRunbookStep,
    MktResearchIntakeThresholdResponse,
    StrategyResearchCandidateCreate,
    StrategyResearchObservationCreate,
)
from aurex.strategy_engine.service import StrategyPortfolioService

MKT_MIN_RESEARCH_RESOLVED_OBSERVATIONS = 100

SOURCE_DEFINITIONS = {
    "whale": {
        "candidate_key": "mkt_whale_research_candidate",
        "strategy": "mkt_whale_research_candidate",
        "display_name": "MKT Whale Research Candidate",
        "hypothesis": (
            "Large Kalshi trades may reveal followable prediction-market pressure, "
            "but only after Aurex fee-net evidence gates pass."
        ),
        "table": "whale_trades",
    },
    "momentum": {
        "candidate_key": "mkt_momentum_research_candidate",
        "strategy": "mkt_momentum_research_candidate",
        "display_name": "MKT Momentum Research Candidate",
        "hypothesis": (
            "Clustered Kalshi activity may reveal short-term prediction-market momentum, "
            "but MKT confidence scores are treated as research metadata only."
        ),
        "table": "alerts",
    },
    "crypto15m": {
        "candidate_key": "mkt_crypto15m_research_candidate",
        "strategy": "mkt_crypto15m_research_candidate",
        "display_name": "MKT Crypto 15m Research Candidate",
        "hypothesis": (
            "Kalshi 15-minute crypto market snapshots may expose repeatable event-window "
            "behavior, but only resolved observation evidence can advance it."
        ),
        "table": "crypto15m_signals",
    },
}


def import_mkt_research_database(
    session: Session,
    request: MktResearchImportRequest,
) -> MktResearchImportResponse:
    scan = scan_mkt_research_database(request)
    validate_mkt_research_import_acknowledgement(request, scan)
    service = StrategyPortfolioService(session)
    candidate_ids: dict[str, str] = {}

    observations_by_source = scan["observations_by_source"]
    assert isinstance(observations_by_source, dict)
    db_path = str(scan["db_path"])
    source_quality_by_source = mkt_source_quality_by_source(scan)
    for source in scan["sources"]:
        assert isinstance(source, str)
        payloads = observations_by_source.get(source, [])
        if not payloads:
            continue
        definition = SOURCE_DEFINITIONS[source]
        table = str(definition["table"])
        source_quality = source_quality_by_source.get(source)
        candidate = service.register_research_candidate(
            StrategyResearchCandidateCreate(
                candidate_key=str(definition["candidate_key"]),
                strategy=str(definition["strategy"]),
                display_name=str(definition["display_name"]),
                hypothesis=str(definition["hypothesis"]),
                status=StrategyResearchStatus.RESEARCH_ONLY,
                source_reference=f"{db_path}::{table}",
                raw_payload={
                    "source": "My-Krypt-Trader",
                    "table": table,
                    "db_path": db_path,
                    "import_quality": mkt_import_quality_payload(scan, source_quality),
                },
                normalized_payload={
                    "importer": "aurex_mkt_sqlite_v1",
                    "table": table,
                    "trade_eligible": False,
                    "trusted_profitable_strategy": False,
                    "research_only_import_acknowledged": (
                        request.acknowledge_research_only_import
                    ),
                    "import_quality_status": str(scan["quality_status"]),
                    "import_blockers": list(scan["blockers"]),
                    "source_quality_status": (
                        source_quality.status if source_quality is not None else None
                    ),
                    "source_processed_observations": (
                        source_quality.processed_observations
                        if source_quality is not None
                        else len(payloads)
                    ),
                    "source_resolved_observations": (
                        source_quality.resolved_observations
                        if source_quality is not None
                        else 0
                    ),
                    "source_target_resolved_observations": (
                        source_quality.target_resolved_observations
                        if source_quality is not None
                        else MKT_MIN_RESEARCH_RESOLVED_OBSERVATIONS
                    ),
                },
            )
        )
        candidate_ids[source] = candidate.id
        for payload in payloads:
            service.record_research_observation(payload)

    session.flush()
    return mkt_research_import_response(scan, list(candidate_ids.values()), request)


def preflight_mkt_research_database(
    request: MktResearchImportRequest,
) -> MktResearchImportPreflightResponse:
    scan = scan_mkt_research_database(request)
    return mkt_research_import_preflight_response(scan)


def mkt_research_intake_runbook(
    request: MktResearchImportRequest,
) -> MktResearchIntakeRunbookResponse:
    readiness = mkt_research_intake_readiness(request)
    start_command = next(
        (
            str(hint.get("command"))
            for hint in readiness.command_hints
            if "start mkt" in str(hint.get("label", "")).lower()
        ),
        None,
    )
    preflight = readiness.preflight
    processed = (
        int(preflight.processed_observations)
        if preflight is not None
        else readiness.collection_health.processed_observations
    )
    resolved = (
        int(preflight.resolved_observations)
        if preflight is not None
        else readiness.collection_health.resolved_observations
    )
    quality = preflight.quality_status if preflight is not None else None
    steps = [
        mkt_research_runbook_step(
            rank=1,
            key="scoped_launch_command",
            label="Use scoped MKT demo runtime",
            status="PASSED" if start_command else "BLOCKED",
            evidence=(
                "Scoped KRYPT_TRADER_USERDATA command is available."
                if start_command
                else "No scoped MKT launch command was generated."
            ),
            command=start_command,
            writes_research_ledger=False,
            next_action=(
                "Run this command in a terminal only when you want MKT demo collection to start."
                if start_command
                else "Fix the selected donor DB path so Aurex can derive scoped userData."
            ),
        ),
        mkt_research_runbook_step(
            rank=2,
            key="collector_activity",
            label="Confirm donor collector activity",
            status=mkt_research_runbook_activity_status(
                readiness.collection_activity_status
            ),
            evidence=(
                f"{readiness.collection_activity_status}; DB {readiness.db_freshness_status}; "
                f"latest log {readiness.latest_log_modified_at or 'none'}."
            ),
            command=start_command,
            writes_research_ledger=False,
            next_action=readiness.collection_health.next_action,
        ),
        mkt_research_runbook_step(
            rank=3,
            key="research_rows_present",
            label="Wait for parseable MKT research rows",
            status="PASSED" if processed > 0 else "BLOCKED",
            evidence=f"{processed} processed research observation(s).",
            writes_research_ledger=False,
            next_action=(
                "Proceed to resolution/depth checks."
                if processed > 0
                else "Keep MKT collecting until whale, momentum, or crypto15m rows appear."
            ),
        ),
        mkt_research_runbook_step(
            rank=4,
            key="resolved_observations_present",
            label="Wait for resolved outcomes",
            status="PASSED" if resolved > 0 else "BLOCKED",
            evidence=f"{resolved} resolved research observation(s).",
            writes_research_ledger=False,
            next_action=(
                "Resolved rows can be inspected as research evidence."
                if resolved > 0
                else "Do not import for research decisions until rows have settlement outcomes."
            ),
        ),
        mkt_research_runbook_step(
            rank=5,
            key="preflight_quality",
            label="Run non-mutating import preflight",
            status=mkt_research_runbook_preflight_status(readiness),
            evidence=quality or "Preflight not run because the donor DB is missing.",
            writes_research_ledger=False,
            next_action=(
                preflight.next_action
                if preflight is not None
                else "Launch MKT until the donor DB exists, then rerun runbook/preflight."
            ),
        ),
        mkt_research_runbook_step(
            rank=6,
            key="research_only_import_boundary",
            label="Import only as disabled research candidates",
            status=(
                "READY"
                if readiness.safe_to_import_research
                else "BLOCKED"
            ),
            evidence=(
                "Import path writes disabled research candidates only; live remains blocked."
                if readiness.safe_to_import_research
                else "No resolved MKT research rows are ready for research-only import."
            ),
            writes_research_ledger=True,
            next_action=(
                "Use acknowledge_research_only_import=true for sparse imports; never treat this "
                "as paper/live eligibility."
                if readiness.safe_to_import_research
                else "Collect resolved observations before importing into the research ledger."
            ),
        ),
        mkt_research_runbook_step(
            rank=7,
            key="research_backtest_gate",
            label="Run Aurex research backtest gates",
            status=(
                "READY"
                if readiness.ready_for_research_backtest
                else "BLOCKED"
            ),
            evidence=(
                f"{readiness.collection_health.backtest_depth_progress_pct}% of one-source "
                "resolved-depth target."
            ),
            writes_research_ledger=False,
            next_action=(
                "Run the research candidate backtest gate and review IS/OOS, walk-forward, "
                "drawdown, regime, concentration, and significance blockers."
                if readiness.ready_for_research_backtest
                else "Collect 100 resolved observations for at least one MKT source first."
            ),
        ),
        mkt_research_runbook_step(
            rank=8,
            key="live_execution_boundary",
            label="Keep live execution disabled",
            status="PASSED",
            evidence="MKT research intake live_execution_enabled=false.",
            writes_research_ledger=False,
            next_action="Do not enable live execution from MKT research intake.",
        ),
    ]
    status_text, next_action = mkt_research_runbook_status(readiness)
    current_step = mkt_research_runbook_current_step(steps)
    completed_step_count = sum(1 for step in steps if step.status == "PASSED")
    total_step_count = len(steps)
    progress_pct = round(
        (completed_step_count / total_step_count) * 100 if total_step_count else 0,
        2,
    )
    blockers = [
        step.key
        for step in steps
        if step.status == "BLOCKED"
    ]
    return MktResearchIntakeRunbookResponse(
        status=status_text,
        db_path=readiness.db_path,
        readiness_status=readiness.status,
        db_freshness_status=readiness.db_freshness_status,
        db_file_size_bytes=readiness.db_file_size_bytes,
        db_modified_at=readiness.db_modified_at,
        latest_log_modified_at=readiness.latest_log_modified_at,
        collection_activity_status=readiness.collection_activity_status,
        collection_health_status=readiness.collection_health.status,
        collection_health=readiness.collection_health,
        processed_observations=readiness.collection_health.processed_observations,
        resolved_observations=readiness.collection_health.resolved_observations,
        unresolved_observations=readiness.collection_health.unresolved_observations,
        backtest_depth_progress_pct=readiness.collection_health.backtest_depth_progress_pct,
        preflight_quality_status=quality,
        current_step=current_step,
        current_command=current_step.command if current_step is not None else None,
        completed_step_count=completed_step_count,
        total_step_count=total_step_count,
        progress_pct=progress_pct,
        thresholds=mkt_research_intake_thresholds(
            processed=processed,
            resolved=resolved,
        ),
        steps=steps,
        blockers=blockers,
        next_action=next_action,
        checked_at=datetime.now(UTC),
        live_execution_enabled=False,
    )


def mkt_research_intake_readiness(
    request: MktResearchImportRequest,
) -> MktResearchIntakeReadinessResponse:
    db_path = Path(request.db_path).expanduser()
    db_stat = mkt_research_db_file_stat(db_path)
    db_freshness_status = mkt_research_db_freshness_status(db_stat)
    logs_dir = mkt_research_logs_dir_for_db(db_path)
    log_files = mkt_research_log_files(logs_dir)
    latest_log_modified_at = mkt_research_latest_log_modified_at(log_files)
    collection_activity_status = mkt_research_collection_activity_status(
        db_freshness_status,
        latest_log_modified_at,
    )
    command_hints = mkt_research_collection_command_hints(db_path)
    if not db_stat["exists"]:
        collection_health = mkt_research_collection_health(
            db_freshness_status=db_freshness_status,
            collection_activity_status=collection_activity_status,
            processed=0,
            resolved=0,
            unresolved=0,
            quality="IMPORT_EMPTY",
            ready_for_backtest=False,
        )
        checks = [
            mkt_research_intake_check(
                "donor_db_exists",
                False,
                "missing",
                "scoped MKT SQLite DB exists",
                "Launch MKT with scoped demo userData until the donor DB exists.",
            ),
            mkt_research_intake_check(
                "preflight_read_only",
                True,
                "not run because DB is missing",
                "read-only preflight must not mutate Aurex research ledger",
                "Requirement satisfied.",
            ),
        ]
        return MktResearchIntakeReadinessResponse(
            status="RESEARCH_INTAKE_DB_MISSING",
            db_path=str(db_path),
            db_exists=False,
            db_file_size_bytes=None,
            db_modified_at=None,
            db_age_seconds=None,
            db_freshness_status=db_freshness_status,
            logs_dir=str(logs_dir),
            logs_dir_exists=logs_dir.is_dir(),
            latest_log_modified_at=latest_log_modified_at,
            log_files=log_files,
            collection_activity_status=collection_activity_status,
            preflight=None,
            checks=checks,
            blockers=["mkt_research_db_missing"],
            safe_to_import_research=False,
            ready_for_research_backtest=False,
            command_hints=command_hints,
            collection_health=collection_health,
            next_action="Launch MKT in scoped demo mode, then rerun research intake readiness.",
            live_execution_enabled=False,
        )

    preflight = preflight_mkt_research_database(request)
    processed = preflight.processed_observations
    resolved = preflight.resolved_observations
    unresolved = preflight.unresolved_observations
    quality = preflight.quality_status
    safe_to_import = resolved > 0
    ready_for_backtest = quality == "IMPORT_BACKTEST_CANDIDATE"
    collection_health = mkt_research_collection_health(
        db_freshness_status=db_freshness_status,
        collection_activity_status=collection_activity_status,
        processed=processed,
        resolved=resolved,
        unresolved=unresolved,
        quality=quality,
        ready_for_backtest=ready_for_backtest,
    )
    checks = [
        mkt_research_intake_check(
            "donor_db_exists",
            True,
            "present",
            "scoped MKT SQLite DB exists",
            "Requirement satisfied.",
        ),
        mkt_research_intake_check(
            "preflight_read_only",
            not preflight.mutates_research_ledger,
            "read-only" if not preflight.mutates_research_ledger else "mutating",
            "read-only preflight must not mutate Aurex research ledger",
            "Use the preflight endpoint before import.",
        ),
        mkt_research_intake_check(
            "donor_db_recent_or_rows_present",
            processed > 0
            or collection_activity_status
            in {
                "RESEARCH_COLLECTION_DB_RECENT",
                "RESEARCH_COLLECTION_LOG_RECENT",
            },
            collection_activity_status,
            "recent donor DB/log writes or parseable research rows",
            "Launch or restart MKT in scoped demo mode, then rerun intake readiness.",
        ),
        mkt_research_intake_check(
            "research_rows_present",
            processed > 0,
            f"{processed} parsed MKT research row(s)",
            "at least one parseable MKT research row",
            "Keep MKT collecting until whale, momentum, or crypto15m rows appear.",
        ),
        mkt_research_intake_check(
            "resolved_observations_present",
            resolved > 0,
            f"{resolved} resolved MKT research observation(s)",
            "at least one resolved observation before research import is worthwhile",
            "Wait for MKT rows to settle before importing into Aurex research.",
        ),
        mkt_research_intake_check(
            "backtest_depth_available",
            ready_for_backtest,
            quality,
            "IMPORT_BACKTEST_CANDIDATE",
            "Collect 100 resolved observations for at least one MKT source.",
        ),
    ]
    blockers = [check.key for check in checks if not check.passed]
    if ready_for_backtest:
        status = "RESEARCH_INTAKE_READY_FOR_BACKTEST_IMPORT"
        next_action = "Import MKT research rows, then run Aurex research backtest gates."
    elif safe_to_import:
        status = "RESEARCH_INTAKE_READY_FOR_RESEARCH_IMPORT"
        next_action = (
            "Import only if you want research inspection; keep collecting before trusting "
            "backtest behavior."
        )
    elif processed > 0:
        status = "RESEARCH_INTAKE_WAITING_FOR_RESOLUTION"
        next_action = "Keep MKT collecting until parsed rows have settlement outcomes."
    elif collection_activity_status == "RESEARCH_COLLECTION_INACTIVE":
        status = "RESEARCH_INTAKE_COLLECTION_INACTIVE"
        next_action = "Launch or restart MKT in scoped demo mode until donor DB timestamps update."
    else:
        status = "RESEARCH_INTAKE_WAITING_FOR_ROWS"
        next_action = "Keep MKT collecting until whale, momentum, or crypto15m rows appear."

    return MktResearchIntakeReadinessResponse(
        status=status,
        db_path=str(db_path),
        db_exists=True,
        db_file_size_bytes=db_stat["size_bytes"],
        db_modified_at=db_stat["modified_at"],
        db_age_seconds=db_stat["age_seconds"],
        db_freshness_status=db_freshness_status,
        logs_dir=str(logs_dir),
        logs_dir_exists=logs_dir.is_dir(),
        latest_log_modified_at=latest_log_modified_at,
        log_files=log_files,
        collection_activity_status=collection_activity_status,
        preflight=preflight,
        checks=checks,
        blockers=blockers,
        safe_to_import_research=safe_to_import,
        ready_for_research_backtest=ready_for_backtest,
        command_hints=command_hints,
        collection_health=collection_health,
        next_action=next_action,
        live_execution_enabled=False,
    )


def scan_mkt_research_database(request: MktResearchImportRequest) -> dict[str, object]:
    db_path = Path(request.db_path).expanduser()
    if not db_path.exists():
        raise ValueError(f"My-Krypt-Trader database not found: {db_path}")
    sources = normalize_mkt_sources(request.sources)
    source_counts: Counter[str] = Counter()
    resolved_counts: Counter[str] = Counter()
    unresolved_counts: Counter[str] = Counter()
    skip_reasons: Counter[str] = Counter()
    table_exists_by_source: dict[str, bool | None] = {source: None for source in sources}
    observations_by_source: dict[str, list[StrategyResearchObservationCreate]] = {
        source: [] for source in sources
    }

    if not request.include_resolved and not request.include_unresolved:
        skip_reasons["all_rows_excluded_by_request"] += 1
        return mkt_research_import_scan_result(
            db_path=db_path,
            sources=sources,
            source_counts=source_counts,
            resolved_counts=resolved_counts,
            unresolved_counts=unresolved_counts,
            skip_reasons=skip_reasons,
            table_exists_by_source=table_exists_by_source,
            observations_by_source=observations_by_source,
        )

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for source in sources:
            definition = SOURCE_DEFINITIONS[source]
            table = str(definition["table"])
            if not sqlite_table_exists(conn, table):
                table_exists_by_source[source] = False
                skip_reasons[f"{source}_table_missing"] += 1
                continue
            table_exists_by_source[source] = True
            rows = fetch_mkt_rows(conn, table, request)
            if not rows:
                source_counts[source] += 0
                continue
            for row in rows:
                payload, reason = mkt_row_to_observation(source, dict(row), str(db_path))
                if payload is None:
                    skip_reasons[reason] += 1
                    continue
                observations_by_source[source].append(payload)
                source_counts[source] += 1
                if mkt_observation_is_resolved(payload):
                    resolved_counts[source] += 1
                else:
                    unresolved_counts[source] += 1

    return mkt_research_import_scan_result(
        db_path=db_path,
        sources=sources,
        source_counts=source_counts,
        resolved_counts=resolved_counts,
        unresolved_counts=unresolved_counts,
        skip_reasons=skip_reasons,
        table_exists_by_source=table_exists_by_source,
        observations_by_source=observations_by_source,
    )


def mkt_research_import_scan_result(
    *,
    db_path: Path,
    sources: list[str],
    source_counts: Counter[str],
    resolved_counts: Counter[str],
    unresolved_counts: Counter[str],
    skip_reasons: Counter[str],
    table_exists_by_source: dict[str, bool | None],
    observations_by_source: dict[str, list[StrategyResearchObservationCreate]],
) -> dict[str, object]:
    quality_status, source_quality, blockers, next_action = mkt_research_import_quality(
        sources,
        source_counts,
        resolved_counts,
        unresolved_counts,
        table_exists_by_source,
    )
    if "all_rows_excluded_by_request" in skip_reasons:
        blockers = [*blockers, "all_rows_excluded_by_request"]
    processed = sum(source_counts.values())
    candidate_count = sum(1 for payloads in observations_by_source.values() if payloads)
    return {
        "db_path": str(db_path),
        "sources": sources,
        "candidate_count": candidate_count,
        "processed_observations": processed,
        "resolved_observations": sum(resolved_counts.values()),
        "unresolved_observations": sum(unresolved_counts.values()),
        "skipped_rows": sum(skip_reasons.values()),
        "source_counts": dict(source_counts),
        "skip_reasons": dict(skip_reasons),
        "quality_status": quality_status,
        "source_quality": source_quality,
        "blockers": blockers,
        "next_action": next_action,
        "observations_by_source": observations_by_source,
    }


def mkt_research_import_response(
    scan: dict[str, object],
    candidate_ids: list[str],
    request: MktResearchImportRequest,
) -> MktResearchImportResponse:
    return MktResearchImportResponse(
        db_path=str(scan["db_path"]),
        candidate_count=int(scan["candidate_count"]),
        processed_observations=int(scan["processed_observations"]),
        resolved_observations=int(scan["resolved_observations"]),
        unresolved_observations=int(scan["unresolved_observations"]),
        skipped_rows=int(scan["skipped_rows"]),
        source_counts=dict(scan["source_counts"]),
        candidate_ids=candidate_ids,
        skip_reasons=dict(scan["skip_reasons"]),
        quality_status=str(scan["quality_status"]),
        source_quality=list(scan["source_quality"]),
        blockers=list(scan["blockers"]),
        next_action=str(scan["next_action"]),
        research_only_import_acknowledged=request.acknowledge_research_only_import,
        live_execution_enabled=False,
        preflight_only=False,
        mutates_research_ledger=True,
    )


def mkt_research_import_preflight_response(
    scan: dict[str, object],
) -> MktResearchImportPreflightResponse:
    return MktResearchImportPreflightResponse(
        db_path=str(scan["db_path"]),
        candidate_count=int(scan["candidate_count"]),
        processed_observations=int(scan["processed_observations"]),
        resolved_observations=int(scan["resolved_observations"]),
        unresolved_observations=int(scan["unresolved_observations"]),
        skipped_rows=int(scan["skipped_rows"]),
        source_counts=dict(scan["source_counts"]),
        candidate_ids=[],
        skip_reasons=dict(scan["skip_reasons"]),
        quality_status=str(scan["quality_status"]),
        source_quality=list(scan["source_quality"]),
        blockers=list(scan["blockers"]),
        next_action=str(scan["next_action"]),
        research_only_import_acknowledged=False,
        live_execution_enabled=False,
        preflight_only=True,
        mutates_research_ledger=False,
    )


def validate_mkt_research_import_acknowledgement(
    request: MktResearchImportRequest,
    scan: dict[str, object],
) -> None:
    if int(scan["candidate_count"]) == 0:
        return
    if str(scan["quality_status"]) == "IMPORT_BACKTEST_CANDIDATE":
        return
    if request.acknowledge_research_only_import:
        return
    raise ValueError(
        "MKT research import is not backtest-depth evidence. Run readiness/preflight, then "
        "set acknowledge_research_only_import=true to import these rows as research-only."
    )


def mkt_source_quality_by_source(
    scan: dict[str, object],
) -> dict[str, MktResearchImportSourceQuality]:
    return {
        item.source: item
        for item in scan.get("source_quality", [])
        if isinstance(item, MktResearchImportSourceQuality)
    }


def mkt_import_quality_payload(
    scan: dict[str, object],
    source_quality: MktResearchImportSourceQuality | None,
) -> dict[str, object]:
    return {
        "quality_status": str(scan["quality_status"]),
        "blockers": list(scan["blockers"]),
        "processed_observations": int(scan["processed_observations"]),
        "resolved_observations": int(scan["resolved_observations"]),
        "unresolved_observations": int(scan["unresolved_observations"]),
        "source_quality": (
            source_quality.model_dump(mode="json") if source_quality is not None else None
        ),
    }


def mkt_research_db_file_stat(path: Path) -> dict[str, object]:
    try:
        stat = path.stat()
    except OSError:
        return {
            "exists": False,
            "size_bytes": None,
            "modified_at": None,
            "age_seconds": None,
        }
    modified_at = datetime.fromtimestamp(stat.st_mtime, UTC)
    age_seconds = max((datetime.now(UTC) - modified_at).total_seconds(), 0.0)
    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_at": modified_at,
        "age_seconds": round(age_seconds, 3),
    }


def mkt_research_db_freshness_status(
    db_stat: dict[str, object],
    max_age_seconds: int = 15 * 60,
) -> str:
    if not db_stat.get("exists"):
        return "RESEARCH_DB_MISSING"
    age_seconds = db_stat.get("age_seconds")
    if not isinstance(age_seconds, int | float):
        return "RESEARCH_DB_UNKNOWN"
    if age_seconds <= max_age_seconds:
        return "RESEARCH_DB_RECENT"
    return "RESEARCH_DB_STALE"


def mkt_research_logs_dir_for_db(db_path: Path) -> Path:
    return mkt_research_userdata_path_for_db(db_path) / "logs"


def mkt_research_log_files(logs_dir: Path, limit: int = 10) -> list[dict[str, object]]:
    if not logs_dir.is_dir():
        return []
    files: list[dict[str, object]] = []
    for path in sorted(
        (item for item in logs_dir.iterdir() if item.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )[:limit]:
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC),
            }
        )
    return files


def mkt_research_latest_log_modified_at(log_files: list[dict[str, object]]) -> datetime | None:
    values = [
        item["modified_at"]
        for item in log_files
        if isinstance(item.get("modified_at"), datetime)
    ]
    return max(values) if values else None


def mkt_research_collection_activity_status(
    db_freshness_status: str,
    latest_log_modified_at: datetime | None,
    max_age_seconds: int = 15 * 60,
) -> str:
    recent_log = False
    if latest_log_modified_at is not None:
        recent_log = (
            max((datetime.now(UTC) - latest_log_modified_at).total_seconds(), 0.0)
            <= max_age_seconds
        )
    if db_freshness_status == "RESEARCH_DB_RECENT":
        return "RESEARCH_COLLECTION_DB_RECENT"
    if recent_log:
        if db_freshness_status == "RESEARCH_DB_MISSING":
            return "RESEARCH_COLLECTION_STARTING"
        return "RESEARCH_COLLECTION_LOG_RECENT"
    if db_freshness_status == "RESEARCH_DB_MISSING":
        return "RESEARCH_COLLECTION_WAITING_FOR_DB"
    if db_freshness_status == "RESEARCH_DB_STALE":
        return "RESEARCH_COLLECTION_INACTIVE"
        return "RESEARCH_COLLECTION_UNKNOWN"


def mkt_research_runbook_activity_status(collection_activity_status: str) -> str:
    if collection_activity_status in {
        "RESEARCH_COLLECTION_DB_RECENT",
        "RESEARCH_COLLECTION_LOG_RECENT",
        "RESEARCH_COLLECTION_STARTING",
    }:
        return "RUNNING"
    return "BLOCKED"


def mkt_research_runbook_preflight_status(
    readiness: MktResearchIntakeReadinessResponse,
) -> str:
    if readiness.ready_for_research_backtest:
        return "PASSED"
    if readiness.safe_to_import_research:
        return "RESEARCH_ONLY"
    if readiness.preflight is not None:
        return "BLOCKED"
    return "BLOCKED"


def mkt_research_runbook_status(
    readiness: MktResearchIntakeReadinessResponse,
) -> tuple[str, str]:
    activity = readiness.collection_activity_status
    if readiness.ready_for_research_backtest:
        return (
            "RUNBOOK_READY_FOR_BACKTEST_GATE",
            "Import MKT rows as research evidence, then run Aurex research backtest gates.",
        )
    if readiness.safe_to_import_research:
        return (
            "RUNBOOK_READY_FOR_RESEARCH_IMPORT",
            "Optionally import as research-only evidence, but keep collecting for depth.",
        )
    if activity in {
        "RESEARCH_COLLECTION_DB_RECENT",
        "RESEARCH_COLLECTION_LOG_RECENT",
        "RESEARCH_COLLECTION_STARTING",
    }:
        return (
            "RUNBOOK_COLLECTION_ACTIVE",
            "Keep MKT running until parseable and resolved research rows appear.",
        )
    if activity == "RESEARCH_COLLECTION_INACTIVE":
        return (
            "RUNBOOK_COLLECTION_INACTIVE",
            "Run the scoped MKT demo collection command, then rerun this runbook.",
        )
    return (
        "RUNBOOK_WAITING_FOR_COLLECTION",
        "Prepare and start scoped MKT demo collection before importing research rows.",
    )


def mkt_research_runbook_current_step(
    steps: list[MktResearchIntakeRunbookStep],
) -> MktResearchIntakeRunbookStep | None:
    ready_step = next((step for step in steps if step.status == "READY"), None)
    if ready_step is not None:
        return ready_step
    blocked_step = next((step for step in steps if step.status == "BLOCKED"), None)
    if blocked_step is not None:
        return blocked_step
    running_step = next((step for step in steps if step.status == "RUNNING"), None)
    if running_step is not None:
        return running_step
    return next((step for step in steps if step.status != "PASSED"), None)


def mkt_research_runbook_step(
    *,
    rank: int,
    key: str,
    label: str,
    status: str,
    evidence: str,
    next_action: str,
    command: str | None = None,
    writes_research_ledger: bool = False,
) -> MktResearchIntakeRunbookStep:
    return MktResearchIntakeRunbookStep(
        rank=rank,
        key=key,
        label=label,
        status=status,
        evidence=evidence,
        command=command,
        writes_research_ledger=writes_research_ledger,
        next_action=next_action,
    )


def mkt_research_collection_health(
    *,
    db_freshness_status: str,
    collection_activity_status: str,
    processed: int,
    resolved: int,
    unresolved: int,
    quality: str,
    ready_for_backtest: bool,
) -> MktResearchCollectionHealthResponse:
    progress = round(
        min(resolved / MKT_MIN_RESEARCH_RESOLVED_OBSERVATIONS, 1.0) * 100,
        2,
    )
    blockers: list[str] = []
    if collection_activity_status == "RESEARCH_COLLECTION_WAITING_FOR_DB":
        blockers.append("mkt_research_db_missing")
    elif collection_activity_status == "RESEARCH_COLLECTION_INACTIVE":
        blockers.append("recent_research_db_activity")
    elif collection_activity_status == "RESEARCH_COLLECTION_UNKNOWN":
        blockers.append("research_db_freshness_unknown")

    if processed == 0:
        blockers.append("research_rows_present")
    if resolved == 0:
        blockers.append("resolved_observations_present")
    if not ready_for_backtest:
        blockers.append("backtest_depth_target")

    if ready_for_backtest:
        status = "COLLECTION_HEALTH_BACKTEST_DEPTH_READY"
        next_action = "Run Aurex research backtest gates for the backtest-depth MKT source."
    elif resolved > 0:
        status = "COLLECTION_HEALTH_SAMPLE_READY"
        next_action = (
            "Research sample exists; keep collecting before treating MKT as backtest-depth "
            "evidence."
        )
    elif processed > 0:
        status = "COLLECTION_HEALTH_UNRESOLVED_ONLY"
        next_action = "Keep MKT collecting until parsed research rows have settlement outcomes."
    elif collection_activity_status == "RESEARCH_COLLECTION_STARTING":
        status = "COLLECTION_HEALTH_STARTING"
        next_action = "MKT logs look recent; wait for the donor DB and research rows to appear."
    elif collection_activity_status in {
        "RESEARCH_COLLECTION_DB_RECENT",
        "RESEARCH_COLLECTION_LOG_RECENT",
    }:
        status = "COLLECTION_HEALTH_COLLECTING"
        next_action = "MKT appears recently active; keep it running until research rows appear."
    elif collection_activity_status == "RESEARCH_COLLECTION_INACTIVE":
        status = "COLLECTION_HEALTH_INACTIVE"
        next_action = "Launch or restart MKT in scoped demo mode until DB timestamps update."
    else:
        status = "COLLECTION_HEALTH_WAITING_FOR_DB"
        next_action = "Launch MKT in scoped demo mode until the donor research DB exists."

    return MktResearchCollectionHealthResponse(
        status=status,
        processed_observations=processed,
        resolved_observations=resolved,
        unresolved_observations=unresolved,
        backtest_depth_progress_pct=progress,
        blockers=sorted(set(blockers)),
        next_action=next_action,
    )


def mkt_research_intake_thresholds(
    *,
    processed: int,
    resolved: int,
) -> list[MktResearchIntakeThresholdResponse]:
    return [
        mkt_research_intake_threshold(
            key="parseable_research_rows",
            label="Parseable research rows",
            current_count=processed,
            target_count=1,
            next_action="Keep MKT collecting until whale, momentum, or crypto15m rows appear.",
        ),
        mkt_research_intake_threshold(
            key="resolved_research_rows",
            label="Resolved research rows",
            current_count=resolved,
            target_count=1,
            next_action="Wait for MKT rows to settle before research-only import is useful.",
        ),
        mkt_research_intake_threshold(
            key="backtest_depth_resolved_rows",
            label="Backtest-depth resolved rows",
            current_count=resolved,
            target_count=MKT_MIN_RESEARCH_RESOLVED_OBSERVATIONS,
            next_action=(
                "Collect 100 resolved observations for at least one MKT source before "
                "running Aurex research backtest gates."
            ),
        ),
    ]


def mkt_research_intake_threshold(
    *,
    key: str,
    label: str,
    current_count: int,
    target_count: int,
    next_action: str,
) -> MktResearchIntakeThresholdResponse:
    remaining = max(target_count - current_count, 0)
    progress = round(
        min(current_count / target_count, 1.0) * 100 if target_count else 100,
        2,
    )
    return MktResearchIntakeThresholdResponse(
        key=key,
        label=label,
        current_count=current_count,
        target_count=target_count,
        remaining_count=remaining,
        progress_pct=progress,
        status="PASSED" if remaining == 0 else "BLOCKED",
        next_action="Requirement satisfied." if remaining == 0 else next_action,
    )


def mkt_research_collection_command_hints(db_path: Path) -> list[dict[str, str]]:
    userdata_path = mkt_research_userdata_path_for_db(db_path)
    root = mkt_research_root_for_userdata(userdata_path)
    return [
        {
            "label": "Start MKT scoped demo collection",
            "command": (
                f"$env:KRYPT_TRADER_USERDATA='{userdata_path}'; "
                f"Set-Location '{root}'; {mkt_research_npm_command('run dev')}"
            ),
            "purpose": (
                "Launch MKT so research donor tables can write into the scoped Aurex demo DB."
            ),
            "live_execution": "demo/dry-run only; does not enable Aurex live execution.",
        },
        {
            "label": "Expected MKT research donor DB",
            "command": str(db_path),
            "purpose": "Rerun MKT research intake readiness against this SQLite DB.",
            "live_execution": "none",
        },
    ]


def mkt_research_userdata_path_for_db(db_path: Path) -> Path:
    if db_path.name == "krypt-trader.db" and db_path.parent.name == "data":
        return db_path.parent.parent
    return db_path.parent


def mkt_research_root_for_userdata(userdata_path: Path) -> Path:
    if userdata_path.name == ".aurex-demo-userdata":
        return userdata_path.parent
    for candidate in (userdata_path, *userdata_path.parents):
        if candidate.name == "My-Krypt-Trader":
            return candidate
    return Path("My-Krypt-Trader")


def mkt_research_npm_command(args: str) -> str:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    return f"{executable} {args}"


def normalize_mkt_sources(sources: list[str]) -> list[str]:
    normalized = [source.strip().lower() for source in sources if source.strip()]
    unknown = sorted(set(normalized) - set(SOURCE_DEFINITIONS))
    if unknown:
        raise ValueError(f"Unknown My-Krypt-Trader import source(s): {', '.join(unknown)}")
    return normalized or list(SOURCE_DEFINITIONS)


def mkt_research_import_quality(
    sources: list[str],
    source_counts: Counter[str],
    resolved_counts: Counter[str],
    unresolved_counts: Counter[str],
    table_exists_by_source: dict[str, bool | None],
) -> tuple[str, list[MktResearchImportSourceQuality], list[str], str]:
    source_quality = [
        mkt_research_import_source_quality(
            source,
            processed=int(source_counts.get(source, 0)),
            resolved=int(resolved_counts.get(source, 0)),
            unresolved=int(unresolved_counts.get(source, 0)),
            table_exists=table_exists_by_source.get(source),
        )
        for source in sources
    ]
    resolved_total = sum(item.resolved_observations for item in source_quality)
    processed_total = sum(item.processed_observations for item in source_quality)
    backtest_candidate_sources = [
        item.source for item in source_quality if item.status == "SOURCE_BACKTEST_CANDIDATE"
    ]
    blockers: list[str] = []
    if processed_total == 0:
        blockers.append("mkt_research_import_empty")
    if resolved_total == 0:
        blockers.append("mkt_research_resolved_observations_missing")
    if not backtest_candidate_sources:
        blockers.append("mkt_research_backtest_depth_missing")

    if backtest_candidate_sources:
        status = "IMPORT_BACKTEST_CANDIDATE"
        next_action = (
            "Run Aurex research backtest gates for the candidate source(s) with resolved depth."
        )
    elif resolved_total > 0:
        status = "IMPORT_SPARSE_RESOLVED_SAMPLE"
        next_action = (
            "Treat imported MKT rows as research only; collect more resolved observations before "
            "trusting any backtest result."
        )
    elif processed_total > 0:
        status = "IMPORT_UNRESOLVED_ONLY"
        next_action = (
            "Keep collecting until imported MKT observations have settlement outcomes."
        )
    else:
        status = "IMPORT_EMPTY"
        next_action = "Verify the selected MKT DB path and keep MKT collecting before import."

    return status, source_quality, blockers, next_action


def mkt_research_import_source_quality(
    source: str,
    *,
    processed: int,
    resolved: int,
    unresolved: int,
    table_exists: bool | None,
) -> MktResearchImportSourceQuality:
    table = str(SOURCE_DEFINITIONS[source]["table"])
    remaining = max(MKT_MIN_RESEARCH_RESOLVED_OBSERVATIONS - resolved, 0)
    if table_exists is None:
        status = "SOURCE_NOT_SCANNED"
        next_action = "Import request excluded this source before scanning the SQLite table."
    elif not table_exists:
        status = "SOURCE_TABLE_MISSING"
        next_action = f"Collect or migrate MKT data until the {table} table exists."
    elif processed == 0:
        status = "SOURCE_EMPTY"
        next_action = f"No importable {source} rows were found in {table}."
    elif resolved == 0:
        status = "SOURCE_UNRESOLVED_ONLY"
        next_action = f"Wait for {source} rows to settle before using them in a research gate."
    elif resolved < MKT_MIN_RESEARCH_RESOLVED_OBSERVATIONS:
        status = "SOURCE_SPARSE_RESOLVED_SAMPLE"
        next_action = (
            f"Collect {remaining} more resolved {source} observation(s) before treating this "
            "source as backtest-depth evidence."
        )
    else:
        status = "SOURCE_BACKTEST_CANDIDATE"
        next_action = "Source has enough resolved observations for Aurex research backtest gates."

    return MktResearchImportSourceQuality(
        source=source,
        table=table,
        table_exists=table_exists,
        processed_observations=processed,
        resolved_observations=resolved,
        unresolved_observations=unresolved,
        target_resolved_observations=MKT_MIN_RESEARCH_RESOLVED_OBSERVATIONS,
        remaining_resolved_observations=remaining,
        status=status,
        next_action=next_action,
    )


def mkt_observation_is_resolved(payload: StrategyResearchObservationCreate) -> bool:
    return payload.resolved_at is not None and bool(payload.outcome_snapshot)


def mkt_research_intake_check(
    key: str,
    passed: bool,
    observed: str,
    expected: str,
    next_action: str,
) -> MktResearchIntakeReadinessCheck:
    return MktResearchIntakeReadinessCheck(
        key=key,
        status="PASS" if passed else "BLOCKED",
        passed=passed,
        observed=observed,
        expected=expected,
        next_action="Requirement satisfied." if passed else next_action,
    )


def sqlite_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def fetch_mkt_rows(
    conn: sqlite3.Connection,
    table: str,
    request: MktResearchImportRequest,
) -> list[sqlite3.Row]:
    filters: list[str] = []
    if request.include_resolved != request.include_unresolved:
        filters.append("resolved = 1" if request.include_resolved else "resolved = 0")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    order_column = "observed_at" if table == "crypto15m_signals" else "created_at"
    return list(
        conn.execute(
            f"SELECT * FROM {table} {where} ORDER BY {order_column} ASC LIMIT ?",
            (request.limit_per_source,),
        ).fetchall()
    )


def mkt_row_to_observation(
    source: str,
    row: dict[str, Any],
    db_path: str,
) -> tuple[StrategyResearchObservationCreate | None, str]:
    if source == "whale":
        return whale_row_to_observation(row, db_path)
    if source == "momentum":
        return momentum_row_to_observation(row, db_path)
    if source == "crypto15m":
        return crypto15m_row_to_observation(row, db_path)
    return None, "unknown_source"


def whale_row_to_observation(
    row: dict[str, Any],
    db_path: str,
) -> tuple[StrategyResearchObservationCreate | None, str]:
    side = normalize_side(row.get("taker_side"))
    entry_price = normalize_probability(row.get("price"))
    if side is None:
        return None, "whale_invalid_side"
    if entry_price is None:
        return None, "whale_invalid_price"
    outcome = outcome_snapshot_from_correct(side, row)
    observed_at = parse_mkt_datetime(row.get("created_at"))
    return (
        StrategyResearchObservationCreate(
            candidate_key="mkt_whale_research_candidate",
            strategy="mkt_whale_research_candidate",
            display_name="MKT Whale Research Candidate",
            hypothesis=str(SOURCE_DEFINITIONS["whale"]["hypothesis"]),
            observation_type=StrategyResearchObservationType.WHALE_TRADE,
            source_event_id=f"mkt:whale:{row.get('trade_id') or row.get('id')}",
            symbol=bounded_text(row.get("event_ticker"), 64),
            contract_ticker=bounded_text(row.get("ticker"), 160),
            side=side,
            confidence=normalize_confidence(row.get("confidence")),
            implied_probability=entry_price,
            observation_snapshot={
                "importer": "aurex_mkt_sqlite_v1",
                "mkt_table": "whale_trades",
                "mkt_row_id": row.get("id"),
                "mkt_trade_id": row.get("trade_id"),
                "mkt_confidence_percent": row.get("confidence"),
                "dollar_value": row.get("dollar_value"),
                "count_fp": row.get("count_fp"),
                "market_volume": row.get("market_volume"),
                "open_interest": row.get("open_interest"),
                "category": row.get("category"),
                "trusted_edge": False,
            },
            raw_payload=mkt_raw_payload("whale_trades", row, db_path),
            observed_at=observed_at,
            resolved_at=parse_resolved_at(row, observed_at, outcome),
            outcome_snapshot=outcome,
        ),
        "ok",
    )


def momentum_row_to_observation(
    row: dict[str, Any],
    db_path: str,
) -> tuple[StrategyResearchObservationCreate | None, str]:
    side = normalize_side(row.get("direction"))
    yes_price = normalize_probability(row.get("price"))
    if side is None:
        return None, "momentum_invalid_side"
    if yes_price is None:
        return None, "momentum_invalid_price"
    entry_price = yes_price if side == "YES" else Decimal("1") - yes_price
    outcome = outcome_snapshot_from_correct(side, row)
    observed_at = parse_mkt_datetime(row.get("created_at"))
    return (
        StrategyResearchObservationCreate(
            candidate_key="mkt_momentum_research_candidate",
            strategy="mkt_momentum_research_candidate",
            display_name="MKT Momentum Research Candidate",
            hypothesis=str(SOURCE_DEFINITIONS["momentum"]["hypothesis"]),
            observation_type=StrategyResearchObservationType.MOMENTUM_CLUSTER,
            source_event_id=f"mkt:momentum:{row.get('id')}",
            symbol=bounded_text(row.get("event_ticker"), 64),
            contract_ticker=bounded_text(row.get("ticker"), 160),
            side=side,
            confidence=normalize_confidence(row.get("confidence")),
            implied_probability=entry_price,
            observation_snapshot={
                "importer": "aurex_mkt_sqlite_v1",
                "mkt_table": "alerts",
                "mkt_row_id": row.get("id"),
                "signal_type": row.get("signal_type"),
                "mkt_confidence_percent": row.get("confidence"),
                "mkt_yes_price": str(yes_price),
                "mkt_entry_cost": str(entry_price),
                "price_change": row.get("price_change"),
                "volume_24h": row.get("volume_24h"),
                "category": row.get("category"),
                "trusted_edge": False,
            },
            raw_payload=mkt_raw_payload("alerts", row, db_path),
            observed_at=observed_at,
            resolved_at=parse_resolved_at(row, observed_at, outcome),
            outcome_snapshot=outcome,
        ),
        "ok",
    )


def crypto15m_row_to_observation(
    row: dict[str, Any],
    db_path: str,
) -> tuple[StrategyResearchObservationCreate | None, str]:
    favorite = str(row.get("favorite") or "").strip().lower()
    if favorite not in {"up", "down"}:
        return None, "crypto15m_invalid_favorite"
    side = "YES" if favorite == "up" else "NO"
    entry_price = normalize_probability(row.get("entry_cost") or row.get("favorite_price"))
    if entry_price is None:
        return None, "crypto15m_invalid_entry_price"
    outcome = crypto15m_outcome_snapshot(row)
    observed_at = parse_mkt_datetime(row.get("observed_at"))
    return (
        StrategyResearchObservationCreate(
            candidate_key="mkt_crypto15m_research_candidate",
            strategy="mkt_crypto15m_research_candidate",
            display_name="MKT Crypto 15m Research Candidate",
            hypothesis=str(SOURCE_DEFINITIONS["crypto15m"]["hypothesis"]),
            observation_type=StrategyResearchObservationType.CRYPTO_15M,
            source_event_id=f"mkt:crypto15m:{row.get('id') or row.get('ticker')}",
            symbol=bounded_text(row.get("asset"), 64),
            contract_ticker=bounded_text(row.get("ticker"), 160),
            side=side,
            confidence=normalize_probability(row.get("favorite_price")),
            implied_probability=entry_price,
            observation_snapshot={
                "importer": "aurex_mkt_sqlite_v1",
                "mkt_table": "crypto15m_signals",
                "mkt_row_id": row.get("id"),
                "category": "crypto",
                "favorite": favorite,
                "favorite_price": row.get("favorite_price"),
                "entry_cost": row.get("entry_cost"),
                "up_prob": row.get("up_prob"),
                "delta_pct": row.get("delta_pct"),
                "open_spot": row.get("open_spot"),
                "obs_spot": row.get("obs_spot"),
                "mins_left": row.get("mins_left"),
                "trusted_edge": False,
            },
            raw_payload=mkt_raw_payload("crypto15m_signals", row, db_path),
            observed_at=observed_at,
            resolved_at=parse_crypto15m_resolved_at(row, observed_at, outcome),
            outcome_snapshot=outcome,
        ),
        "ok",
    )


def normalize_side(value: object) -> str | None:
    side = str(value or "").strip().upper()
    if side in {"YES", "Y", "UP"}:
        return "YES"
    if side in {"NO", "N", "DOWN"}:
        return "NO"
    return None


def normalize_probability(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        probability = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if probability > Decimal("1") and probability <= Decimal("100"):
        probability = probability / Decimal("100")
    if probability < Decimal("0") or probability > Decimal("1"):
        return None
    return probability


def normalize_confidence(value: object) -> Decimal | None:
    return normalize_probability(value)


def outcome_snapshot_from_correct(side: str, row: dict[str, Any]) -> dict[str, object]:
    if not bool_from_mkt_flag(row.get("resolved")):
        return {}
    correct = bool_from_mkt_flag(row.get("outcome_correct"))
    if correct is None:
        return {}
    settlement_value = settlement_value_for_side_correct(side, correct)
    return {
        "settlement_value": str(settlement_value),
        "outcome_correct": correct,
        "resolved_price": row.get("resolved_price"),
        "pnl_estimate": row.get("pnl_estimate"),
        "source": "My-Krypt-Trader",
    }


def crypto15m_outcome_snapshot(row: dict[str, Any]) -> dict[str, object]:
    if not bool_from_mkt_flag(row.get("resolved")):
        return {}
    up_won = bool_from_mkt_flag(row.get("up_won"))
    if up_won is None:
        return {}
    return {
        "settlement_value": "1" if up_won else "0",
        "up_won": up_won,
        "source": "My-Krypt-Trader",
    }


def bool_from_mkt_flag(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "win", "won"}:
        return True
    if normalized in {"0", "false", "no", "n", "loss", "lost"}:
        return False
    return None


def settlement_value_for_side_correct(side: str, correct: bool) -> Decimal:
    if side == "YES":
        return Decimal("1") if correct else Decimal("0")
    return Decimal("0") if correct else Decimal("1")


def parse_resolved_at(
    row: dict[str, Any],
    observed_at: datetime | None,
    outcome: dict[str, object],
) -> datetime | None:
    if not outcome:
        return None
    return parse_mkt_datetime(row.get("resolved_at")) or observed_at


def parse_crypto15m_resolved_at(
    row: dict[str, Any],
    observed_at: datetime | None,
    outcome: dict[str, object],
) -> datetime | None:
    if not outcome:
        return None
    return (
        parse_mkt_datetime(row.get("settled_at"))
        or parse_mkt_datetime(row.get("close_time"))
        or observed_at
    )


def parse_mkt_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    candidates = [text, text.replace("Z", "+00:00")]
    if " " in text and "T" not in text:
        candidates.append(text.replace(" ", "T"))
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def bounded_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def mkt_raw_payload(table: str, row: dict[str, Any], db_path: str) -> dict[str, object]:
    return {
        "source": "My-Krypt-Trader",
        "source_table": table,
        "db_path": db_path,
        "row": {key: serializable_value(value) for key, value in row.items()},
    }


def serializable_value(value: object) -> object:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
