from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_daily_cross_source import (
    Q1_DAILY_CROSS_PASS_AUTHORIZATION,
    Q1_DAILY_CROSS_PASS_DECISION,
    PeriodicFlowDailyArchiveEvidence,
    PeriodicFlowDailyCrossSourceResult,
    PeriodicFlowDailyPayloadTarget,
    audit_daily_cross_protocol,
    audit_daily_cross_result,
    build_daily_cross_protocol,
    build_daily_cross_result,
)
from aurex.backtest_engine.periodic_flow_overlap_census import (
    PeriodicFlowOverlapEvent,
    daily_archive_url,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _event():
    return PeriodicFlowOverlapEvent(
        preceding_aggregate_trade_id=100,
        current_aggregate_trade_id=101,
        preceding_first_raw_trade_id=1_000,
        preceding_last_raw_trade_id=1_000,
        current_first_raw_trade_id=1_000,
        current_last_raw_trade_id=1_000,
        preceding_timestamp_ms=1_579_046_400_000,
        current_timestamp_ms=1_579_046_400_000,
        overlap_raw_trade_id_count=1,
        first_overlapped_raw_trade_id=1_000,
        last_overlapped_raw_trade_id=1_000,
        utc_day="2020-01-15",
    )


def _protocol():
    targets = tuple(
        PeriodicFlowDailyPayloadTarget(
            family=family,
            archive_url=daily_archive_url(family, "2020-01-15"),
            published_archive_sha256=("a" if family == "aggTrades" else "b")
            * 64,
            expected_column_count=7 if family == "aggTrades" else 6,
            expected_member_name=f"BTCUSDT-{family}-2020-01-15.csv",
        )
        for family in ("aggTrades", "trades")
    )
    return build_daily_cross_protocol(
        frozen_at=datetime(2026, 8, 7, tzinfo=UTC),
        census_result_file_sha256="1" * 64,
        census_result_evidence_hash="2" * 64,
        census_audit_file_sha256="3" * 64,
        census_audit_evidence_hash="4" * 64,
        builder_contract_hash="5" * 64,
        parent_overlap_event=_event(),
        targets=targets,
        target_manifest_hash=universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets]}
        ),
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )


def _evidence():
    return (
        PeriodicFlowDailyArchiveEvidence(
            family="aggTrades",
            local_path=(
                "source_snapshots/q1_periodic_flow_daily_cross_source_v1/"
                "aggTrades/BTCUSDT-aggTrades-2020-01-15.zip"
            ),
            archive_sha256="a" * 64,
            published_archive_sha256="a" * 64,
            archive_bytes=1_000,
            member_name="BTCUSDT-aggTrades-2020-01-15.csv",
            member_compressed_bytes=900,
            member_uncompressed_bytes=5_000,
            row_count=100,
            first_id=1,
            last_id=100,
            id_non_increasing_count=0,
            id_gap_count=0,
            timestamp_regression_count=0,
            monthly_overlap_event_match_count=1,
            target_raw_trade_id_occurrence_count=0,
            target_raw_trade_timestamp_ms=None,
            payload_get_attempt_count=1,
            archive_pass=True,
            reason_codes=(),
            parsed_numeric_fields=(
                "aggregate_trade_id",
                "first_trade_id",
                "last_trade_id",
                "timestamp",
            ),
            excluded_numeric_fields=("price", "quantity"),
        ),
        PeriodicFlowDailyArchiveEvidence(
            family="trades",
            local_path=(
                "source_snapshots/q1_periodic_flow_daily_cross_source_v1/"
                "trades/BTCUSDT-trades-2020-01-15.zip"
            ),
            archive_sha256="b" * 64,
            published_archive_sha256="b" * 64,
            archive_bytes=2_000,
            member_name="BTCUSDT-trades-2020-01-15.csv",
            member_compressed_bytes=1_800,
            member_uncompressed_bytes=8_000,
            row_count=200,
            first_id=900,
            last_id=1_100,
            id_non_increasing_count=0,
            id_gap_count=1,
            timestamp_regression_count=0,
            monthly_overlap_event_match_count=0,
            target_raw_trade_id_occurrence_count=1,
            target_raw_trade_timestamp_ms=1_579_046_400_000,
            payload_get_attempt_count=1,
            archive_pass=True,
            reason_codes=(),
            parsed_numeric_fields=("trade_id", "timestamp"),
            excluded_numeric_fields=("price", "quantity", "quote_quantity"),
        ),
    )


def _result():
    protocol = _protocol()
    return build_daily_cross_result(
        generated_at=datetime(2026, 8, 7, 1, tzinfo=UTC),
        protocol_file_sha256="6" * 64,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="7" * 64,
        parent_overlap_event=_event(),
        archive_evidence=_evidence(),
        payload_get_attempt_count=2,
        total_archive_bytes=3_000,
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )


def test_q1_daily_cross_protocol_freezes_two_no_value_payloads() -> None:
    protocol = _protocol()
    assert audit_daily_cross_protocol(protocol)
    assert len(protocol.targets) == 2
    assert protocol.price_or_quantity_parsing_permitted is False
    assert protocol.return_calculation_permitted is False
    assert protocol.paper_operation_permitted is False
    assert protocol.live_permitted is False


def test_q1_daily_cross_result_authorizes_raw_source_census_only() -> None:
    result = _result()
    assert audit_daily_cross_result(result)
    assert result.decision == Q1_DAILY_CROSS_PASS_DECISION
    assert result.next_authorization == Q1_DAILY_CROSS_PASS_AUTHORIZATION
    assert result.authorizes_usdm_raw_trades_metadata_census_protocol
    assert result.raw_trade_timestamp_matches_aggregate_timestamp
    assert result.price_or_quantity_values_parsed == ()
    assert result.authorizes_testnet_strategy_orders is False
    assert result.authorizes_live is False


def test_q1_daily_cross_result_refuses_authority_tampering() -> None:
    payload = _result().model_dump()
    payload["authorizes_live"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowDailyCrossSourceResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_periodic_flow_daily_cross_source.py",
        "scripts/run_periodic_flow_daily_cross_source.py",
        "scripts/audit_periodic_flow_daily_cross_source.py",
    ],
)
def test_q1_daily_cross_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
