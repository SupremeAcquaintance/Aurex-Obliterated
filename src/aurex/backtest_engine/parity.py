import json
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.datasets import OhlcvDatasetLab
from aurex.backtest_engine.reference_replay import ENGINE_VERSION, run_reference_replay
from aurex.backtest_engine.schemas import (
    BacktestParityAuditResponse,
    BacktestParityExportManifestRequest,
    BacktestParityExportManifestResponse,
    BacktestParityRequest,
    BacktestParityResponse,
    BacktestTradeInput,
    ReferenceReplayRequest,
    ReferenceReplayTrade,
)
from aurex.backtest_engine.service import (
    build_backtest_protocol_hash,
    build_backtest_run_manifest,
    build_trade_evidence_hash,
    build_tradingview_run_package,
    ensure_utc,
)
from aurex.db.base import utc_now
from aurex.db.models import (
    BacktestDataset,
    BacktestDatasetCandle,
    BacktestParityRun,
    BacktestProtocol,
    BacktestRun,
    BacktestTrade,
)
from aurex.observability.system_events import SystemEventRecorder

PARITY_ENGINE_VERSION = "tradingview-trade-parity-v1.2.0"
PARITY_SCHEMA_VERSION = "aurex-backtest-parity-v3"
PAIRED_EXPORT_SCHEMA_VERSION = "aurex-tradingview-paired-export-v1"
TRADINGVIEW_CHART_SOURCE = "tradingview-chart-export"
REQUIRED_TRADINGVIEW_FIELDS = (
    "direction",
    "entry_at",
    "closed_at",
    "entry_price",
    "exit_price",
    "quantity",
    "fees",
)


class BacktestParityLab:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preflight(self, request: BacktestParityRequest) -> BacktestParityResponse:
        return compare_backtest_parity(self.session, request)

    def record(
        self,
        request: BacktestParityRequest,
    ) -> tuple[BacktestParityRun, bool]:
        response = self.preflight(request)
        if response.status == "BLOCKED" or response.parity_evidence_hash is None:
            reasons = ", ".join(response.reasons) or "parity preflight blocked"
            raise ValueError(f"Parity evidence cannot be recorded: {reasons}")

        existing = self.session.execute(
            select(BacktestParityRun).where(
                BacktestParityRun.evidence_hash == response.parity_evidence_hash
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, True

        recorded_at = utc_now()
        record = BacktestParityRun(
            dataset_id=response.dataset_id,
            tradingview_run_id=response.tradingview_run_id,
            strategy=response.strategy,
            strategy_version=response.strategy_version,
            engine_version=response.engine_version,
            status=response.status,
            dataset_evidence_hash=response.dataset_evidence_hash,
            tradingview_evidence_hash=response.tradingview_evidence_hash,
            replay_evidence_hash=str(response.replay_evidence_hash),
            evidence_hash=response.parity_evidence_hash,
            request_snapshot=response.request_snapshot,
            summary_snapshot=response.summary,
            mismatch_snapshot=response.mismatches,
            reason_snapshot=response.reasons,
            warning_snapshot=response.warnings,
            recorded_at=recorded_at,
        )
        self.session.add(record)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "backtest_parity",
            "Immutable TradingView parity evidence recorded",
            {
                "parity_run_id": record.id,
                "status": record.status,
                "strategy": record.strategy,
                "strategy_version": record.strategy_version,
                "dataset_id": record.dataset_id,
                "tradingview_run_id": record.tradingview_run_id,
                "evidence_hash": record.evidence_hash,
                "comparison_only": True,
                "acceptance_eligible": False,
            },
            occurred_at=recorded_at,
        )
        self.session.flush()
        return record, False

    def list_runs(self, limit: int = 100) -> list[BacktestParityRun]:
        return list(
            self.session.execute(
                select(BacktestParityRun)
                .order_by(BacktestParityRun.recorded_at.desc())
                .limit(limit)
            ).scalars()
        )

    def get_run(self, parity_run_id: str) -> BacktestParityRun | None:
        return self.session.get(BacktestParityRun, parity_run_id)

    def audit(self, record: BacktestParityRun) -> BacktestParityAuditResponse:
        current_hash = build_parity_evidence_hash(parity_record_payload(record))
        reasons: list[str] = []
        if current_hash != record.evidence_hash:
            reasons.append("parity_record_evidence_hash_mismatch")

        replayed_hash: str | None = None
        try:
            request = BacktestParityRequest.model_validate(
                record.request_snapshot.get("request")
            )
            replayed = self.preflight(request)
            replayed_hash = replayed.parity_evidence_hash
            if replayed.status == "BLOCKED":
                reasons.append("parity_source_recheck_blocked")
                reasons.extend(
                    f"parity_source_{reason}" for reason in replayed.reasons
                )
            elif replayed_hash != record.evidence_hash:
                reasons.append("parity_source_or_replay_drift")
        except (LookupError, ValueError, TypeError) as exc:
            reasons.append(f"parity_source_recheck_failed:{exc}")

        return BacktestParityAuditResponse(
            parity_run_id=record.id,
            status="PASS" if not reasons else "BLOCKED",
            stored_evidence_hash=record.evidence_hash,
            current_evidence_hash=current_hash,
            replayed_evidence_hash=replayed_hash,
            evidence_hash_matches=current_hash == record.evidence_hash,
            replay_matches=replayed_hash == record.evidence_hash,
            reasons=reasons,
            checked_at=utc_now(),
        )


def preflight_tradingview_export_manifest(
    session: Session,
    request: BacktestParityExportManifestRequest,
) -> BacktestParityExportManifestResponse:
    dataset = OhlcvDatasetLab(session).get_dataset(request.dataset_id)
    if dataset is None:
        raise LookupError("OHLCV dataset not found")
    chart_dataset = OhlcvDatasetLab(session).get_dataset(
        request.tradingview_chart_dataset_id
    )
    if chart_dataset is None:
        raise LookupError("TradingView chart dataset not found")
    run = session.get(BacktestRun, request.tradingview_run_id)
    if run is None:
        raise LookupError("TradingView backtest run not found")

    reasons: list[str] = []
    dataset_audit = OhlcvDatasetLab(session).audit(dataset)
    chart_audit = OhlcvDatasetLab(session).audit(chart_dataset)
    if dataset_audit.status != "PASS":
        reasons.extend(f"reference_dataset_{reason}" for reason in dataset_audit.reasons)
    if chart_audit.status != "PASS":
        reasons.extend(f"chart_dataset_{reason}" for reason in chart_audit.reasons)
    if dataset.source.strip().lower() != "binance-vision":
        reasons.append("reference_dataset_source_invalid")
    if not bool(dataset.quality_snapshot.get("source_artifacts_verified")):
        reasons.append("reference_dataset_source_artifacts_not_verified")
    if chart_dataset.source.strip().lower() != TRADINGVIEW_CHART_SOURCE:
        reasons.append("chart_dataset_source_invalid")

    expected_ticker_id = f"BINANCE:{dataset.symbol}"
    expected_chart_reference = (
        f"tradingview://chart/{expected_ticker_id}/{dataset.timeframe}"
    )
    expected_report_reference = (
        f"tradingview://strategy-tester/{expected_ticker_id}/{dataset.timeframe}"
    )
    if chart_dataset.source_reference != expected_chart_reference:
        reasons.append("chart_source_reference_mismatch")
    if run.source_reference != expected_report_reference:
        reasons.append("report_source_reference_mismatch")
    if run.source_format != "tradingview":
        reasons.append("report_source_format_invalid")
    if run.data_source != "tradingview-export":
        reasons.append("report_data_source_invalid")
    if chart_dataset.symbol != dataset.symbol:
        reasons.append("chart_symbol_mismatch")
    if chart_dataset.timeframe != dataset.timeframe:
        reasons.append("chart_timeframe_mismatch")
    if dataset.symbol not in {str(symbol).upper() for symbol in run.symbols or []}:
        reasons.append("report_symbol_mismatch")
    if run.timeframe != dataset.timeframe:
        reasons.append("report_timeframe_mismatch")

    reference_start = ensure_utc(dataset.data_start)
    reference_end = ensure_utc(dataset.data_end)
    if (
        ensure_utc(chart_dataset.data_start) != reference_start
        or ensure_utc(chart_dataset.data_end) != reference_end
    ):
        reasons.append("chart_coverage_mismatch")
    report_start = ensure_utc(run.data_start)
    report_end = ensure_utc(run.data_end)
    if (
        report_start < reference_start
        or report_end > reference_end
        or report_start >= report_end
    ):
        reasons.append("report_coverage_outside_market_data")

    chart_csv_sha256 = chart_dataset.quality_snapshot.get("canonical_csv_sha256")
    if not valid_sha256(chart_csv_sha256):
        reasons.append("chart_canonical_csv_hash_invalid")
    if not valid_sha256(run.source_artifact_hash):
        reasons.append("report_source_artifact_hash_invalid")

    protocol: BacktestProtocol | None = None
    run_manifest: dict[str, Any] = {}
    run_package: dict[str, Any] = {}
    if not run.protocol_id:
        reasons.append("report_frozen_protocol_missing")
    else:
        protocol = session.get(BacktestProtocol, run.protocol_id)
        if protocol is None:
            reasons.append("report_frozen_protocol_not_found")
        else:
            if run.protocol_evidence_hash != protocol.protocol_hash:
                reasons.append("report_protocol_evidence_hash_mismatch")
            if build_backtest_protocol_hash(protocol.protocol_snapshot) != protocol.protocol_hash:
                reasons.append("frozen_protocol_integrity_mismatch")
            consumed_run_id = (
                protocol.backtest_run.id if protocol.backtest_run is not None else None
            )
            if consumed_run_id != run.id:
                reasons.append("frozen_protocol_not_consumed_by_report")
            run_manifest = build_backtest_run_manifest(protocol)
            run_package = build_tradingview_run_package(protocol)
            configuration_reasons = [
                str(reason)
                for reason in run_package.get("reasons") or []
                if reason != "protocol_unconsumed"
            ]
            reasons.extend(
                f"frozen_run_package_{reason}" for reason in configuration_reasons
            )
            if run_package.get("ticker_id") != expected_ticker_id:
                reasons.append("frozen_run_ticker_mismatch")
            if run_package.get("timeframe") != dataset.timeframe:
                reasons.append("frozen_run_timeframe_mismatch")
            if run_package.get("strategy") != run.strategy:
                reasons.append("frozen_run_strategy_mismatch")
            if run_package.get("strategy_version") != run.strategy_version:
                reasons.append("frozen_run_strategy_version_mismatch")

    attested_at = ensure_utc(request.export_attestation.attested_at)
    latest_import = max(
        ensure_utc(chart_dataset.imported_at),
        ensure_utc(run.created_at),
    )
    checked_at = utc_now()
    if attested_at < latest_import:
        reasons.append("paired_export_attestation_precedes_imported_evidence")
    if attested_at > checked_at + timedelta(minutes=5):
        reasons.append("paired_export_attestation_is_in_the_future")

    manifest = {
        "schema_version": PAIRED_EXPORT_SCHEMA_VERSION,
        "attestation": request.export_attestation.model_dump(mode="json"),
        "frozen_run": {
            "protocol_id": run.protocol_id,
            "protocol_hash": run.protocol_evidence_hash,
            "manifest_hash": run_manifest.get("manifest_hash"),
            "package_hash": run_package.get("package_hash"),
            "pine_source_sha256": run_package.get("pine_source_sha256"),
            "settings_fingerprint": run_manifest.get("settings_fingerprint"),
            "strategy": run.strategy,
            "strategy_version": run.strategy_version,
            "ticker_id": expected_ticker_id,
            "timeframe": dataset.timeframe,
        },
        "reference_dataset": {
            "dataset_id": dataset.id,
            "evidence_hash": dataset.evidence_hash,
            "source": dataset.source,
            "source_reference": dataset.source_reference,
            "data_start": reference_start.isoformat(),
            "data_end": reference_end.isoformat(),
        },
        "tradingview_chart_export": {
            "dataset_id": chart_dataset.id,
            "dataset_evidence_hash": chart_dataset.evidence_hash,
            "canonical_csv_sha256": chart_csv_sha256,
            "source": chart_dataset.source,
            "source_reference": chart_dataset.source_reference,
            "data_start": ensure_utc(chart_dataset.data_start).isoformat(),
            "data_end": ensure_utc(chart_dataset.data_end).isoformat(),
            "imported_at": ensure_utc(chart_dataset.imported_at).isoformat(),
        },
        "tradingview_report_export": {
            "run_id": run.id,
            "trade_evidence_hash": run.evidence_hash,
            "source_artifact_hash": run.source_artifact_hash,
            "data_source": run.data_source,
            "source_format": run.source_format,
            "source_reference": run.source_reference,
            "data_start": report_start.isoformat(),
            "data_end": report_end.isoformat(),
            "imported_at": ensure_utc(run.created_at).isoformat(),
        },
    }
    reasons = unique(reasons)
    return BacktestParityExportManifestResponse(
        status="READY" if not reasons else "BLOCKED",
        manifest_hash=build_parity_evidence_hash(manifest) if not reasons else None,
        manifest=manifest,
        reasons=reasons,
        warnings=[
            (
                "This lineage is operator-attested and hash-bound; TradingView does not "
                "sign or independently prove that both exports came from one unchanged run."
            ),
            (
                "The chart hash binds Aurex's canonical candle CSV; the report hash binds "
                "the original Strategy Tester CSV bytes submitted to Aurex."
            ),
        ],
        checked_at=checked_at,
        mutates_ledger=False,
    )


def compare_backtest_parity(
    session: Session,
    request: BacktestParityRequest,
) -> BacktestParityResponse:
    dataset = OhlcvDatasetLab(session).get_dataset(request.dataset_id)
    if dataset is None:
        raise LookupError("OHLCV dataset not found")
    run = session.get(BacktestRun, request.tradingview_run_id)
    if run is None:
        raise LookupError("TradingView backtest run not found")
    tradingview_chart_dataset = (
        OhlcvDatasetLab(session).get_dataset(request.tradingview_chart_dataset_id)
        if request.tradingview_chart_dataset_id is not None
        else None
    )

    reasons: list[str] = []
    warnings = [
        "Parity evidence is comparison-only and cannot satisfy backtest acceptance.",
        (
            "A pass applies only to the two bound datasets, report, engine version, "
            "and tolerances."
        ),
        "TradingView remains authoritative until a real exported report produces a pass.",
    ]
    dataset_audit = OhlcvDatasetLab(session).audit(dataset)
    if dataset_audit.status != "PASS":
        reasons.extend(f"dataset_{reason}" for reason in dataset_audit.reasons)
    if dataset.source.strip().lower() != "binance-vision":
        reasons.append("reference_dataset_source_is_not_binance_vision")
    if not bool(dataset.quality_snapshot.get("source_artifacts_verified")):
        reasons.append("reference_dataset_source_artifacts_not_verified")

    market_data_summary = market_data_summary_template(
        reference_count=dataset.row_count,
        tradingview_count=(
            tradingview_chart_dataset.row_count
            if tradingview_chart_dataset is not None
            else 0
        ),
    )
    market_data_mismatches: list[dict] = []
    tradingview_chart_hash: str | None = None
    if request.tradingview_chart_dataset_id is None:
        reasons.append("tradingview_chart_dataset_required")
    elif tradingview_chart_dataset is None:
        reasons.append("tradingview_chart_dataset_not_found")
    else:
        tradingview_chart_hash = tradingview_chart_dataset.evidence_hash
        chart_audit = OhlcvDatasetLab(session).audit(tradingview_chart_dataset)
        if chart_audit.status != "PASS":
            reasons.extend(
                f"tradingview_chart_dataset_{reason}"
                for reason in chart_audit.reasons
            )
        expected_chart_reference = (
            f"tradingview://chart/BINANCE:{dataset.symbol}/{dataset.timeframe}"
        )
        if (
            tradingview_chart_dataset.source.strip().lower()
            != TRADINGVIEW_CHART_SOURCE
        ):
            reasons.append("tradingview_chart_dataset_source_invalid")
        if tradingview_chart_dataset.source_reference != expected_chart_reference:
            reasons.append("tradingview_chart_source_reference_mismatch")
        if tradingview_chart_dataset.symbol != dataset.symbol:
            reasons.append("tradingview_chart_symbol_mismatch")
        if tradingview_chart_dataset.timeframe != dataset.timeframe:
            reasons.append("tradingview_chart_timeframe_mismatch")
        if (
            ensure_utc(tradingview_chart_dataset.data_start)
            != ensure_utc(dataset.data_start)
            or ensure_utc(tradingview_chart_dataset.data_end)
            != ensure_utc(dataset.data_end)
        ):
            reasons.append("tradingview_chart_coverage_mismatch")
        if chart_audit.status == "PASS":
            market_data_summary, market_data_mismatches = (
                compare_market_data_datasets(
                    dataset,
                    tradingview_chart_dataset,
                )
            )

    export_manifest_snapshot: dict[str, Any] | None = None
    if request.export_attestation is None:
        reasons.append("tradingview_export_attestation_required")
    if request.reviewed_export_manifest_hash is None:
        reasons.append("reviewed_tradingview_export_manifest_hash_required")
    if (
        request.tradingview_chart_dataset_id is not None
        and request.export_attestation is not None
    ):
        export_manifest = preflight_tradingview_export_manifest(
            session,
            BacktestParityExportManifestRequest(
                dataset_id=request.dataset_id,
                tradingview_chart_dataset_id=request.tradingview_chart_dataset_id,
                tradingview_run_id=request.tradingview_run_id,
                export_attestation=request.export_attestation,
            ),
        )
        export_manifest_snapshot = export_manifest.model_dump(
            mode="json",
            exclude={"checked_at"},
        )
        warnings.extend(export_manifest.warnings)
        if export_manifest.status != "READY":
            reasons.extend(
                f"tradingview_export_manifest_{reason}"
                for reason in export_manifest.reasons
            )
        elif (
            request.reviewed_export_manifest_hash
            != export_manifest.manifest_hash
        ):
            reasons.append("reviewed_tradingview_export_manifest_hash_mismatch")

    tradingview_trades = sorted(run.trades or [], key=lambda trade: trade.sequence)
    current_tradingview_hash = build_trade_evidence_hash(
        [persisted_trade_input(trade) for trade in tradingview_trades]
    )
    if not run.evidence_hash:
        reasons.append("tradingview_evidence_hash_missing")
    elif current_tradingview_hash != run.evidence_hash:
        reasons.append("tradingview_trade_evidence_hash_mismatch")
    if run.source_format != "tradingview":
        reasons.append("source_run_is_not_tradingview")
    if run.data_source != "tradingview-export":
        reasons.append("tradingview_run_data_source_invalid")
    expected_run_reference = (
        f"tradingview://strategy-tester/BINANCE:{dataset.symbol}/"
        f"{dataset.timeframe}"
    )
    if run.source_reference != expected_run_reference:
        reasons.append("tradingview_run_source_reference_mismatch")
    if not valid_sha256(run.source_artifact_hash):
        reasons.append("tradingview_run_source_artifact_hash_invalid")
    if not tradingview_trades:
        reasons.append("tradingview_completed_trades_missing")
    if run.strategy != "trend_pullback_v1" or run.strategy_version != "1.3.0":
        reasons.append("parity_engine_strategy_not_supported")
    if dataset.symbol not in {str(symbol).upper() for symbol in run.symbols or []}:
        reasons.append("dataset_symbol_does_not_match_tradingview_run")
    if dataset.timeframe != run.timeframe:
        reasons.append("dataset_timeframe_does_not_match_tradingview_run")

    missing_fields = missing_tradingview_fields(tradingview_trades)
    if missing_fields:
        reasons.append("tradingview_comparison_fields_missing")

    commission_percent = mapping_decimal(
        run.cost_model,
        "commission_percent",
        reasons,
        "tradingview_commission_percent_invalid",
    )
    slippage_ticks = mapping_integer(
        run.slippage_model,
        "ticks",
        reasons,
        "tradingview_slippage_ticks_invalid",
    )
    if (run.slippage_model or {}).get("type") != "fixed_ticks":
        reasons.append("tradingview_slippage_model_must_be_fixed_ticks")
    if commission_percent is not None and commission_percent < 0:
        reasons.append("tradingview_commission_percent_invalid")
    if slippage_ticks is not None and slippage_ticks < 0:
        reasons.append("tradingview_slippage_ticks_invalid")

    request_snapshot = {
        "request": request.model_dump(mode="json"),
        "tradingview_config_hash": run.config_hash,
        "tradingview_report_source": {
            "data_source": run.data_source,
            "source_format": run.source_format,
            "source_reference": run.source_reference,
            "source_artifact_hash": run.source_artifact_hash,
        },
        "market_data_evidence": {
            "reference_dataset_id": dataset.id,
            "reference_dataset_evidence_hash": dataset.evidence_hash,
            "tradingview_chart_dataset_id": (
                tradingview_chart_dataset.id
                if tradingview_chart_dataset is not None
                else None
            ),
            "tradingview_chart_dataset_evidence_hash": tradingview_chart_hash,
            "summary": market_data_summary,
            "mismatches": market_data_mismatches,
        },
        "tradingview_export_lineage": export_manifest_snapshot,
        "execution_assumptions": {
            "commission_percent_per_side": decimal_text(commission_percent),
            "slippage_ticks": slippage_ticks,
            "intrabar_policy": "stop_first",
        },
        "required_tradingview_fields": list(REQUIRED_TRADINGVIEW_FIELDS),
    }
    empty_summary = parity_summary_template(
        reference_count=len(tradingview_trades),
        replay_count=0,
        missing_fields=missing_fields,
    )
    tradingview_hash = run.evidence_hash or current_tradingview_hash
    if reasons:
        return parity_response(
            request=request,
            run=run,
            dataset_hash=dataset.evidence_hash,
            tradingview_chart_dataset_hash=tradingview_chart_hash,
            tradingview_hash=tradingview_hash,
            replay_hash=None,
            parity_hash=None,
            request_snapshot=request_snapshot,
            status="BLOCKED",
            summary=empty_summary,
            mismatches=[],
            market_data_summary=market_data_summary,
            market_data_mismatches=market_data_mismatches,
            reasons=unique(reasons),
            warnings=warnings,
        )

    replay = run_reference_replay(
        session,
        ReferenceReplayRequest(
            dataset_id=dataset.id,
            strategy=run.strategy,
            strategy_version=run.strategy_version,
            parameters=run.parameters or {},
            tick_size=request.tick_size,
            point_value=request.point_value,
            minimum_contract=request.minimum_contract,
            commission_percent=commission_percent or Decimal("0"),
            slippage_ticks=slippage_ticks or 0,
            intrabar_policy="stop_first",
        ),
    )
    if replay.status != "READY" or replay.engine_evidence_hash is None:
        reasons.extend(f"replay_{reason}" for reason in replay.reasons)
        return parity_response(
            request=request,
            run=run,
            dataset_hash=dataset.evidence_hash,
            tradingview_chart_dataset_hash=tradingview_chart_hash,
            tradingview_hash=tradingview_hash,
            replay_hash=None,
            parity_hash=None,
            request_snapshot=request_snapshot,
            status="BLOCKED",
            summary=empty_summary,
            mismatches=[],
            market_data_summary=market_data_summary,
            market_data_mismatches=market_data_mismatches,
            reasons=unique(reasons),
            warnings=warnings + replay.warnings,
        )

    if market_data_mismatches:
        reasons = [
            "market_data_parity_mismatches",
            "trade_level_comparison_not_run_due_to_market_data_mismatch",
        ]
        evidence_payload = parity_evidence_payload(
            status="FAILED",
            strategy=run.strategy,
            strategy_version=run.strategy_version,
            dataset_id=dataset.id,
            dataset_hash=dataset.evidence_hash,
            tradingview_chart_dataset_id=(
                tradingview_chart_dataset.id
                if tradingview_chart_dataset is not None
                else None
            ),
            tradingview_chart_dataset_hash=tradingview_chart_hash,
            tradingview_run_id=run.id,
            tradingview_hash=tradingview_hash,
            replay_hash=replay.engine_evidence_hash,
            request_snapshot=request_snapshot,
            summary=empty_summary,
            mismatches=[],
            market_data_summary=market_data_summary,
            market_data_mismatches=market_data_mismatches,
            reasons=reasons,
            warnings=warnings,
        )
        return parity_response(
            request=request,
            run=run,
            dataset_hash=dataset.evidence_hash,
            tradingview_chart_dataset_hash=tradingview_chart_hash,
            tradingview_hash=tradingview_hash,
            replay_hash=replay.engine_evidence_hash,
            parity_hash=build_parity_evidence_hash(evidence_payload),
            request_snapshot=request_snapshot,
            status="FAILED",
            summary=empty_summary,
            mismatches=[],
            market_data_summary=market_data_summary,
            market_data_mismatches=market_data_mismatches,
            reasons=reasons,
            warnings=warnings,
        )

    summary, mismatches = compare_trade_sequences(
        tradingview_trades,
        replay.trades,
        request=request,
        missing_fields=missing_fields,
    )
    status = "PASSED" if not mismatches else "FAILED"
    reasons = [] if status == "PASSED" else ["trade_level_parity_mismatches"]
    evidence_payload = parity_evidence_payload(
        status=status,
        strategy=run.strategy,
        strategy_version=run.strategy_version,
        dataset_id=dataset.id,
        dataset_hash=dataset.evidence_hash,
        tradingview_chart_dataset_id=(
            tradingview_chart_dataset.id
            if tradingview_chart_dataset is not None
            else None
        ),
        tradingview_chart_dataset_hash=tradingview_chart_hash,
        tradingview_run_id=run.id,
        tradingview_hash=tradingview_hash,
        replay_hash=replay.engine_evidence_hash,
        request_snapshot=request_snapshot,
        summary=summary,
        mismatches=mismatches,
        market_data_summary=market_data_summary,
        market_data_mismatches=market_data_mismatches,
        reasons=reasons,
        warnings=warnings,
    )
    return parity_response(
        request=request,
        run=run,
        dataset_hash=dataset.evidence_hash,
        tradingview_chart_dataset_hash=tradingview_chart_hash,
        tradingview_hash=tradingview_hash,
        replay_hash=replay.engine_evidence_hash,
        parity_hash=build_parity_evidence_hash(evidence_payload),
        request_snapshot=request_snapshot,
        status=status,
        summary=summary,
        mismatches=mismatches,
        market_data_summary=market_data_summary,
        market_data_mismatches=market_data_mismatches,
        reasons=reasons,
        warnings=warnings,
    )


def market_data_summary_template(
    *,
    reference_count: int,
    tradingview_count: int,
) -> dict:
    return {
        "reference_candle_count": reference_count,
        "tradingview_candle_count": tradingview_count,
        "aligned_candle_count": 0,
        "matched_candle_count": 0,
        "mismatched_candle_count": 0,
        "reference_only_count": 0,
        "tradingview_only_count": 0,
        "match_rate": "0",
        "field_mismatch_counts": {},
        "maximum_observed_deltas": {},
        "exact_ohlcv_match": False,
    }


def compare_market_data_datasets(
    reference: BacktestDataset,
    tradingview: BacktestDataset,
) -> tuple[dict, list[dict]]:
    reference_by_timestamp = {
        ensure_utc(candle.timestamp): candle for candle in reference.candles
    }
    tradingview_by_timestamp = {
        ensure_utc(candle.timestamp): candle for candle in tradingview.candles
    }
    timestamps = sorted(reference_by_timestamp.keys() | tradingview_by_timestamp.keys())
    field_counts: Counter[str] = Counter()
    maximum_deltas = {
        field: Decimal("0")
        for field in ("open", "high", "low", "close", "volume")
    }
    mismatches: list[dict] = []
    matched = 0
    aligned = 0
    reference_only = 0
    tradingview_only = 0

    for timestamp in timestamps:
        reference_candle = reference_by_timestamp.get(timestamp)
        tradingview_candle = tradingview_by_timestamp.get(timestamp)
        if reference_candle is None:
            tradingview_only += 1
            mismatches.append(
                {
                    "status": "TRADINGVIEW_ONLY",
                    "timestamp": iso_text(timestamp),
                    "reference": None,
                    "tradingview": candle_snapshot(tradingview_candle),
                    "reasons": ["timestamp_missing_from_reference_dataset"],
                }
            )
            continue
        if tradingview_candle is None:
            reference_only += 1
            mismatches.append(
                {
                    "status": "REFERENCE_ONLY",
                    "timestamp": iso_text(timestamp),
                    "reference": candle_snapshot(reference_candle),
                    "tradingview": None,
                    "reasons": ["timestamp_missing_from_tradingview_chart_dataset"],
                }
            )
            continue

        aligned += 1
        reference_values = candle_decimal_values(reference_candle)
        tradingview_values = candle_decimal_values(tradingview_candle)
        reasons: list[str] = []
        for field in ("open", "high", "low", "close", "volume"):
            delta = abs(reference_values[field] - tradingview_values[field])
            maximum_deltas[field] = max(maximum_deltas[field], delta)
            if delta != 0:
                reason = f"{field}_mismatch"
                reasons.append(reason)
                field_counts[reason] += 1

        if not reasons:
            matched += 1
            continue
        mismatches.append(
            {
                "status": "VALUE_MISMATCH",
                "timestamp": iso_text(timestamp),
                "reference": candle_snapshot(reference_candle),
                "tradingview": candle_snapshot(tradingview_candle),
                "reasons": reasons,
            }
        )

    reference_count = len(reference_by_timestamp)
    tradingview_count = len(tradingview_by_timestamp)
    denominator = max(reference_count, tradingview_count)
    summary = {
        "reference_candle_count": reference_count,
        "tradingview_candle_count": tradingview_count,
        "aligned_candle_count": aligned,
        "matched_candle_count": matched,
        "mismatched_candle_count": len(mismatches),
        "reference_only_count": reference_only,
        "tradingview_only_count": tradingview_only,
        "match_rate": decimal_text(
            Decimal(matched) / Decimal(denominator)
            if denominator
            else Decimal("0")
        ),
        "field_mismatch_counts": dict(sorted(field_counts.items())),
        "maximum_observed_deltas": {
            field: decimal_text(delta)
            for field, delta in maximum_deltas.items()
        },
        "exact_ohlcv_match": not mismatches and reference_count == tradingview_count,
    }
    return summary, mismatches


def candle_decimal_values(
    candle: BacktestDatasetCandle,
) -> dict[str, Decimal]:
    return {
        "open": Decimal(candle.open),
        "high": Decimal(candle.high),
        "low": Decimal(candle.low),
        "close": Decimal(candle.close),
        "volume": Decimal(candle.volume),
    }


def candle_snapshot(candle: BacktestDatasetCandle | None) -> dict | None:
    if candle is None:
        return None
    return {
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def compare_trade_sequences(
    reference: list[BacktestTrade],
    replay: list[ReferenceReplayTrade],
    *,
    request: BacktestParityRequest,
    missing_fields: list[dict],
) -> tuple[dict, list[dict]]:
    reference_sorted = sorted(
        reference,
        key=lambda trade: (ensure_utc(trade.entry_at), trade.sequence),
    )
    replay_sorted = sorted(replay, key=lambda trade: (ensure_utc(trade.entry_at), trade.sequence))
    entry_tolerance = request.tolerances.entry_time_seconds
    index_reference = 0
    index_replay = 0
    aligned = 0
    exact = 0
    reference_only = 0
    replay_only = 0
    mismatches: list[dict] = []
    field_counts: Counter[str] = Counter()
    max_deltas = {
        "entry_time_seconds": Decimal("0"),
        "exit_time_seconds": Decimal("0"),
        "entry_price": Decimal("0"),
        "exit_price": Decimal("0"),
        "quantity_relative": Decimal("0"),
        "fees": Decimal("0"),
        "realized_pl": Decimal("0"),
    }

    while index_reference < len(reference_sorted) and index_replay < len(replay_sorted):
        reference_trade = reference_sorted[index_reference]
        replay_trade = replay_sorted[index_replay]
        time_delta = int(
            abs(
                (
                    ensure_utc(reference_trade.entry_at)
                    - ensure_utc(replay_trade.entry_at)
                ).total_seconds()
            )
        )
        if time_delta <= entry_tolerance:
            aligned += 1
            mismatch, deltas = compare_aligned_trade(
                reference_trade,
                replay_trade,
                request=request,
            )
            for field, delta in deltas.items():
                max_deltas[field] = max(max_deltas[field], delta)
            if mismatch is None:
                exact += 1
            else:
                mismatches.append(mismatch)
                field_counts.update(mismatch["reasons"])
            index_reference += 1
            index_replay += 1
            continue

        if ensure_utc(reference_trade.entry_at) < ensure_utc(replay_trade.entry_at):
            reference_only += 1
            field_counts["reference_trade_missing_from_replay"] += 1
            mismatches.append(unmatched_trade("REFERENCE_ONLY", reference_trade, None))
            index_reference += 1
        else:
            replay_only += 1
            field_counts["replay_trade_missing_from_reference"] += 1
            mismatches.append(unmatched_trade("REPLAY_ONLY", None, replay_trade))
            index_replay += 1

    for reference_trade in reference_sorted[index_reference:]:
        reference_only += 1
        field_counts["reference_trade_missing_from_replay"] += 1
        mismatches.append(unmatched_trade("REFERENCE_ONLY", reference_trade, None))
    for replay_trade in replay_sorted[index_replay:]:
        replay_only += 1
        field_counts["replay_trade_missing_from_reference"] += 1
        mismatches.append(unmatched_trade("REPLAY_ONLY", None, replay_trade))

    denominator = max(len(reference), len(replay), 1)
    summary = parity_summary_template(
        reference_count=len(reference),
        replay_count=len(replay),
        missing_fields=missing_fields,
    )
    summary.update(
        {
            "aligned_trade_count": aligned,
            "matched_trade_count": exact,
            "mismatched_trade_count": aligned - exact,
            "reference_only_count": reference_only,
            "replay_only_count": replay_only,
            "match_rate": decimal_text(Decimal(exact) / Decimal(denominator)),
            "field_mismatch_counts": dict(sorted(field_counts.items())),
            "maximum_observed_deltas": {
                key: decimal_text(value) for key, value in max_deltas.items()
            },
        }
    )
    return summary, mismatches


def compare_aligned_trade(
    reference: BacktestTrade,
    replay: ReferenceReplayTrade,
    *,
    request: BacktestParityRequest,
) -> tuple[dict | None, dict[str, Decimal]]:
    price_tolerance = request.tick_size * request.tolerances.price_ticks
    money_tolerance = request.tolerances.money_absolute
    entry_seconds = Decimal(
        str(abs((ensure_utc(reference.entry_at) - ensure_utc(replay.entry_at)).total_seconds()))
    )
    exit_seconds = Decimal(
        str(abs((ensure_utc(reference.closed_at) - ensure_utc(replay.closed_at)).total_seconds()))
    )
    entry_price_delta = abs(Decimal(reference.entry_price) - replay.entry_price)
    exit_price_delta = abs(Decimal(reference.exit_price) - replay.exit_price)
    quantity_delta = relative_delta(Decimal(reference.quantity), replay.quantity)
    fee_delta = abs(Decimal(reference.fees) - replay.fees)
    net_delta = abs(Decimal(reference.realized_pl) - replay.realized_pl)
    deltas = {
        "entry_time_seconds": entry_seconds,
        "exit_time_seconds": exit_seconds,
        "entry_price": entry_price_delta,
        "exit_price": exit_price_delta,
        "quantity_relative": quantity_delta,
        "fees": fee_delta,
        "realized_pl": net_delta,
    }
    checks = [
        field_check(
            "direction",
            reference.direction,
            replay.direction,
            reference.direction == replay.direction,
        ),
        field_check(
            "entry_at",
            reference.entry_at,
            replay.entry_at,
            entry_seconds <= request.tolerances.entry_time_seconds,
            delta=entry_seconds,
            tolerance=Decimal(request.tolerances.entry_time_seconds),
        ),
        field_check(
            "closed_at",
            reference.closed_at,
            replay.closed_at,
            exit_seconds <= request.tolerances.exit_time_seconds,
            delta=exit_seconds,
            tolerance=Decimal(request.tolerances.exit_time_seconds),
        ),
        field_check(
            "entry_price",
            reference.entry_price,
            replay.entry_price,
            entry_price_delta <= price_tolerance,
            delta=entry_price_delta,
            tolerance=price_tolerance,
        ),
        field_check(
            "exit_price",
            reference.exit_price,
            replay.exit_price,
            exit_price_delta <= price_tolerance,
            delta=exit_price_delta,
            tolerance=price_tolerance,
        ),
        field_check(
            "quantity",
            reference.quantity,
            replay.quantity,
            quantity_delta <= request.tolerances.quantity_relative,
            delta=quantity_delta,
            tolerance=request.tolerances.quantity_relative,
        ),
        field_check(
            "fees",
            reference.fees,
            replay.fees,
            fee_delta <= money_tolerance,
            delta=fee_delta,
            tolerance=money_tolerance,
        ),
        field_check(
            "realized_pl",
            reference.realized_pl,
            replay.realized_pl,
            net_delta <= money_tolerance,
            delta=net_delta,
            tolerance=money_tolerance,
        ),
    ]
    reference_exit_reason = infer_reference_exit_reason(
        reference,
        replay,
        price_tolerance=price_tolerance,
    )
    replay_exit_reason = canonical_exit_reason(replay.exit_reason)
    checks.append(
        field_check(
            "exit_reason",
            reference_exit_reason,
            replay_exit_reason,
            reference_exit_reason == replay_exit_reason,
        )
    )
    failed = [check for check in checks if not check["passed"]]
    if not failed:
        return None, deltas
    return {
        "status": "MISMATCH",
        "reference_sequence": reference.sequence,
        "replay_sequence": replay.sequence,
        "reference_entry_at": iso_text(reference.entry_at),
        "replay_entry_at": iso_text(replay.entry_at),
        "reasons": [f"{check['field']}_mismatch" for check in failed],
        "field_results": failed,
    }, deltas


def unmatched_trade(
    status: str,
    reference: BacktestTrade | None,
    replay: ReferenceReplayTrade | None,
) -> dict:
    return {
        "status": status,
        "reference_sequence": reference.sequence if reference else None,
        "replay_sequence": replay.sequence if replay else None,
        "reference_entry_at": iso_text(reference.entry_at) if reference else None,
        "replay_entry_at": iso_text(replay.entry_at) if replay else None,
        "reasons": [
            "reference_trade_missing_from_replay"
            if reference
            else "replay_trade_missing_from_reference"
        ],
        "field_results": [],
    }


def field_check(
    field: str,
    reference: object,
    replay: object,
    passed: bool,
    *,
    delta: Decimal | None = None,
    tolerance: Decimal | None = None,
) -> dict:
    return {
        "field": field,
        "passed": passed,
        "reference": scalar_text(reference),
        "replay": scalar_text(replay),
        "delta": decimal_text(delta),
        "tolerance": decimal_text(tolerance),
    }


def infer_reference_exit_reason(
    reference: BacktestTrade,
    replay: ReferenceReplayTrade,
    *,
    price_tolerance: Decimal,
) -> str:
    exit_price = Decimal(reference.exit_price)
    replay_reason = canonical_exit_reason(replay.exit_reason)
    if (
        replay_reason == "TAKE_PROFIT"
        and replay.take_profit is not None
        and abs(exit_price - replay.take_profit) <= price_tolerance
    ):
        return "TAKE_PROFIT"
    if replay_reason == "STOP_LOSS" and abs(exit_price - replay.exit_price) <= price_tolerance:
        return "STOP_LOSS"
    if (
        replay_reason == "BACKTEST_WINDOW_END"
        and abs(exit_price - replay.exit_price) <= price_tolerance
    ):
        return "BACKTEST_WINDOW_END"
    return "UNKNOWN"


def canonical_exit_reason(value: str) -> str:
    if value in {"STOP_LOSS", "STOP_AND_TARGET_AMBIGUOUS"}:
        return "STOP_LOSS"
    return value


def missing_tradingview_fields(trades: list[BacktestTrade]) -> list[dict]:
    missing: list[dict] = []
    for trade in trades:
        fields = [field for field in REQUIRED_TRADINGVIEW_FIELDS if getattr(trade, field) is None]
        if fields:
            missing.append({"sequence": trade.sequence, "fields": fields})
    return missing


def persisted_trade_input(trade: BacktestTrade) -> BacktestTradeInput:
    return BacktestTradeInput(
        sequence=trade.sequence,
        external_trade_id=trade.external_trade_id,
        source_format=trade.source_format,
        strategy=trade.strategy,
        symbol=trade.symbol,
        direction=trade.direction,
        entry_at=trade.entry_at,
        closed_at=trade.closed_at,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        gross_pl=trade.gross_pl,
        fees=trade.fees,
        slippage=trade.slippage,
        realized_pl=trade.realized_pl,
        equity=trade.equity,
        r_multiple=trade.r_multiple,
        market_regime=trade.market_regime,
    )


def mapping_decimal(
    mapping: dict | None,
    key: str,
    reasons: list[str],
    reason: str,
) -> Decimal | None:
    try:
        value = Decimal(str((mapping or {}).get(key)))
    except (InvalidOperation, TypeError, ValueError):
        reasons.append(reason)
        return None
    if not value.is_finite():
        reasons.append(reason)
        return None
    return value


def mapping_integer(
    mapping: dict | None,
    key: str,
    reasons: list[str],
    reason: str,
) -> int | None:
    try:
        raw = Decimal(str((mapping or {}).get(key)))
        value = int(raw)
    except (InvalidOperation, TypeError, ValueError):
        reasons.append(reason)
        return None
    if raw != value:
        reasons.append(reason)
        return None
    return value


def valid_sha256(value: str | None) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def parity_summary_template(
    *,
    reference_count: int,
    replay_count: int,
    missing_fields: list[dict],
) -> dict:
    return {
        "reference_trade_count": reference_count,
        "replay_trade_count": replay_count,
        "aligned_trade_count": 0,
        "matched_trade_count": 0,
        "mismatched_trade_count": 0,
        "reference_only_count": 0,
        "replay_only_count": 0,
        "match_rate": "0",
        "missing_required_fields": missing_fields,
        "field_mismatch_counts": {},
        "maximum_observed_deltas": {},
    }


def parity_response(
    *,
    request: BacktestParityRequest,
    run: BacktestRun,
    dataset_hash: str,
    tradingview_chart_dataset_hash: str | None,
    tradingview_hash: str,
    replay_hash: str | None,
    parity_hash: str | None,
    request_snapshot: dict,
    status: str,
    summary: dict,
    mismatches: list[dict],
    market_data_summary: dict,
    market_data_mismatches: list[dict],
    reasons: list[str],
    warnings: list[str],
) -> BacktestParityResponse:
    return BacktestParityResponse(
        status=status,
        engine_version=PARITY_ENGINE_VERSION,
        strategy=run.strategy,
        strategy_version=run.strategy_version,
        dataset_id=request.dataset_id,
        dataset_evidence_hash=dataset_hash,
        tradingview_chart_dataset_id=request.tradingview_chart_dataset_id,
        tradingview_chart_dataset_evidence_hash=(
            tradingview_chart_dataset_hash
        ),
        tradingview_run_id=run.id,
        tradingview_evidence_hash=tradingview_hash,
        replay_evidence_hash=replay_hash,
        parity_evidence_hash=parity_hash,
        request_snapshot=request_snapshot,
        summary=summary,
        mismatches=mismatches,
        market_data_summary=market_data_summary,
        market_data_mismatches=market_data_mismatches,
        reasons=reasons,
        warnings=unique(warnings),
        checked_at=utc_now(),
        mutates_ledger=False,
    )


def parity_record_response(
    record: BacktestParityRun,
    *,
    reused_existing: bool = False,
) -> BacktestParityResponse:
    market_data_evidence = record.request_snapshot.get("market_data_evidence") or {}
    return BacktestParityResponse(
        id=record.id,
        status=record.status,
        engine_version=record.engine_version,
        strategy=record.strategy,
        strategy_version=record.strategy_version,
        dataset_id=record.dataset_id,
        dataset_evidence_hash=record.dataset_evidence_hash,
        tradingview_chart_dataset_id=market_data_evidence.get(
            "tradingview_chart_dataset_id"
        ),
        tradingview_chart_dataset_evidence_hash=market_data_evidence.get(
            "tradingview_chart_dataset_evidence_hash"
        ),
        tradingview_run_id=record.tradingview_run_id,
        tradingview_evidence_hash=record.tradingview_evidence_hash,
        replay_evidence_hash=record.replay_evidence_hash,
        parity_evidence_hash=record.evidence_hash,
        request_snapshot=record.request_snapshot,
        summary=record.summary_snapshot,
        mismatches=record.mismatch_snapshot,
        market_data_summary=market_data_evidence.get("summary") or {},
        market_data_mismatches=market_data_evidence.get("mismatches") or [],
        reasons=record.reason_snapshot,
        warnings=record.warning_snapshot,
        comparison_only=True,
        acceptance_eligible=False,
        immutable=True,
        reused_existing=reused_existing,
        recorded_at=record.recorded_at,
        checked_at=record.recorded_at,
        mutates_ledger=True,
    )


def parity_record_payload(record: BacktestParityRun) -> dict:
    market_data_evidence = record.request_snapshot.get("market_data_evidence") or {}
    return parity_evidence_payload(
        status=record.status,
        strategy=record.strategy,
        strategy_version=record.strategy_version,
        dataset_id=record.dataset_id,
        dataset_hash=record.dataset_evidence_hash,
        tradingview_chart_dataset_id=market_data_evidence.get(
            "tradingview_chart_dataset_id"
        ),
        tradingview_chart_dataset_hash=market_data_evidence.get(
            "tradingview_chart_dataset_evidence_hash"
        ),
        tradingview_run_id=record.tradingview_run_id,
        tradingview_hash=record.tradingview_evidence_hash,
        replay_hash=record.replay_evidence_hash,
        request_snapshot=record.request_snapshot,
        summary=record.summary_snapshot,
        mismatches=record.mismatch_snapshot,
        market_data_summary=market_data_evidence.get("summary") or {},
        market_data_mismatches=market_data_evidence.get("mismatches") or [],
        reasons=record.reason_snapshot,
        warnings=record.warning_snapshot,
    )


def parity_evidence_payload(
    *,
    status: str,
    strategy: str,
    strategy_version: str,
    dataset_id: str,
    dataset_hash: str,
    tradingview_chart_dataset_id: str | None,
    tradingview_chart_dataset_hash: str | None,
    tradingview_run_id: str,
    tradingview_hash: str,
    replay_hash: str,
    request_snapshot: dict,
    summary: dict,
    mismatches: list[dict],
    market_data_summary: dict,
    market_data_mismatches: list[dict],
    reasons: list[str],
    warnings: list[str],
) -> dict:
    return {
        "schema_version": PARITY_SCHEMA_VERSION,
        "engine_version": PARITY_ENGINE_VERSION,
        "reference_replay_engine_version": ENGINE_VERSION,
        "status": status,
        "strategy": strategy,
        "strategy_version": strategy_version,
        "dataset_id": dataset_id,
        "dataset_evidence_hash": dataset_hash,
        "tradingview_chart_dataset_id": tradingview_chart_dataset_id,
        "tradingview_chart_dataset_evidence_hash": (
            tradingview_chart_dataset_hash
        ),
        "tradingview_run_id": tradingview_run_id,
        "tradingview_evidence_hash": tradingview_hash,
        "replay_evidence_hash": replay_hash,
        "request_snapshot": request_snapshot,
        "summary": summary,
        "mismatches": mismatches,
        "market_data_summary": market_data_summary,
        "market_data_mismatches": market_data_mismatches,
        "reasons": reasons,
        "warnings": warnings,
        "comparison_only": True,
        "acceptance_eligible": False,
    }


def build_parity_evidence_hash(payload: dict) -> str:
    canonical = json.dumps(canonical_value(payload), sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if isinstance(value, datetime):
        return iso_text(value)
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, Enum):
        return value.value
    return value


def relative_delta(left: Decimal, right: Decimal) -> Decimal:
    denominator = max(abs(left), abs(right), Decimal("0.000000000001"))
    return abs(left - right) / denominator


def scalar_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return iso_text(value)
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def iso_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
