from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_payload_gap_remediation import (
    Q1_GAP_PASS_AUTHORIZATION,
    Q1_GAP_PASS_DECISION,
    PeriodicFlowGapRecord,
    PeriodicFlowGapRemediationResult,
    audit_gap_remediation_protocol,
    audit_gap_remediation_result,
    build_gap_remediation_protocol,
    build_gap_remediation_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _protocol():
    return build_gap_remediation_protocol(
        frozen_at=datetime(2026, 8, 7, tzinfo=UTC),
        parent_protocol_file_sha256="1" * 64,
        parent_protocol_evidence_hash="2" * 64,
        parent_result_file_sha256="3" * 64,
        parent_result_evidence_hash="4" * 64,
        parent_audit_file_sha256="5" * 64,
        parent_audit_evidence_hash="6" * 64,
        builder_contract_hash="7" * 64,
        target_archive_sha256="8" * 64,
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )


def _result():
    protocol = _protocol()
    gaps = (
        PeriodicFlowGapRecord(
            preceding_aggregate_trade_id=10,
            current_aggregate_trade_id=11,
            preceding_last_raw_trade_id=100,
            current_first_raw_trade_id=102,
            skipped_raw_trade_id_count=1,
            current_timestamp_ms=1_577_836_860_000,
        ),
        PeriodicFlowGapRecord(
            preceding_aggregate_trade_id=20,
            current_aggregate_trade_id=21,
            preceding_last_raw_trade_id=200,
            current_first_raw_trade_id=203,
            skipped_raw_trade_id_count=2,
            current_timestamp_ms=1_577_836_920_000,
        ),
    )
    return build_gap_remediation_result(
        generated_at=datetime(2026, 8, 7, 1, tzinfo=UTC),
        protocol_file_sha256="9" * 64,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="a" * 64,
        archive_sha256="8" * 64,
        row_count=100_000,
        first_aggregate_trade_id=1,
        last_aggregate_trade_id=100_000,
        aggregate_trade_id_gap_count=0,
        aggregate_trade_id_non_increasing_count=0,
        first_raw_trade_id=1,
        last_raw_trade_id=10_000,
        raw_trade_span_invalid_count=0,
        raw_trade_range_overlap_count=0,
        gap_records=gaps,
        gap_manifest_hash=universe_evidence_hash(
            {"gaps": [item.model_dump() for item in gaps]}
        ),
        gap_event_count=2,
        total_skipped_raw_trade_ids=3,
        maximum_single_gap_skipped_raw_ids=2,
        raw_trade_id_span=10_000,
        skipped_raw_trade_id_fraction=Decimal("3") / Decimal("10000"),
        gap_size_buckets={
            "1": 1,
            "2_TO_10": 1,
            "11_TO_100": 0,
            "101_TO_1000": 0,
            "OVER_1000": 0,
        },
        first_timestamp_ms=1_577_836_800_000,
        last_timestamp_ms=1_580_515_199_999,
        timestamp_regression_count=0,
        unique_minute_count=44_640,
        minute_coverage_fraction=Decimal("1"),
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )


def test_q1_gap_protocol_is_local_structural_only() -> None:
    protocol = _protocol()
    assert audit_gap_remediation_protocol(protocol)
    assert protocol.network_access_permitted is False
    assert protocol.price_or_quantity_parsing_permitted is False
    assert protocol.return_calculation_permitted is False
    assert protocol.maximum_gap_event_count == 10_000
    assert protocol.maximum_skipped_raw_id_fraction == "0.01"
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.live_permitted is False


def test_q1_gap_result_authorizes_only_full_acquisition_protocol() -> None:
    result = _result()
    assert audit_gap_remediation_result(result)
    assert result.decision == Q1_GAP_PASS_DECISION
    assert result.next_authorization == Q1_GAP_PASS_AUTHORIZATION
    assert result.authorizes_separate_full_development_acquisition_protocol
    assert result.interpretation_is_inference_not_trade_classification
    assert result.price_or_quantity_values_parsed == ()
    assert result.return_metrics_calculated == ()
    assert result.authorizes_paper_operation is False
    assert result.authorizes_testnet_strategy_orders is False
    assert result.authorizes_live is False
    assert result.real_net_profit_usd == "0"


def test_q1_gap_result_refuses_authority_tampering() -> None:
    payload = _result().model_dump()
    payload["authorizes_paper_operation"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowGapRemediationResult.model_validate(payload)


def test_q1_gap_record_refuses_overlap() -> None:
    with pytest.raises(ValidationError):
        PeriodicFlowGapRecord(
            preceding_aggregate_trade_id=10,
            current_aggregate_trade_id=11,
            preceding_last_raw_trade_id=100,
            current_first_raw_trade_id=100,
            skipped_raw_trade_id_count=1,
            current_timestamp_ms=1_577_836_860_000,
        )


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_periodic_flow_payload_gap_remediation.py",
        "scripts/run_periodic_flow_payload_gap_remediation.py",
        "scripts/audit_periodic_flow_payload_gap_remediation.py",
    ],
)
def test_q1_gap_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
