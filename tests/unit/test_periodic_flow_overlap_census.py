from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_overlap_census import (
    Q1_OVERLAP_PASS_AUTHORIZATION,
    Q1_OVERLAP_PASS_DECISION,
    PeriodicFlowDailyChecksumRecord,
    PeriodicFlowOverlapCensusResult,
    PeriodicFlowOverlapEvent,
    audit_overlap_census_protocol,
    audit_overlap_census_result,
    build_overlap_census_protocol,
    build_overlap_census_result,
    daily_archive_url,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _protocol():
    return build_overlap_census_protocol(
        frozen_at=datetime(2026, 8, 7, tzinfo=UTC),
        parent_result_file_sha256="1" * 64,
        parent_result_evidence_hash="2" * 64,
        parent_audit_file_sha256="3" * 64,
        parent_audit_evidence_hash="4" * 64,
        target_archive_sha256="5" * 64,
        builder_contract_hash="6" * 64,
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )


def _event():
    return PeriodicFlowOverlapEvent(
        preceding_aggregate_trade_id=100,
        current_aggregate_trade_id=101,
        preceding_first_raw_trade_id=1_000,
        preceding_last_raw_trade_id=1_010,
        current_first_raw_trade_id=1_010,
        current_last_raw_trade_id=1_020,
        preceding_timestamp_ms=1_578_355_200_000,
        current_timestamp_ms=1_578_355_200_001,
        overlap_raw_trade_id_count=1,
        first_overlapped_raw_trade_id=1_010,
        last_overlapped_raw_trade_id=1_010,
        utc_day="2020-01-07",
    )


def _checksum(family: str):
    archive = daily_archive_url(family, "2020-01-07")
    digest = "a" * 64 if family == "aggTrades" else "b" * 64
    text = f"{digest}  {archive.rsplit('/', maxsplit=1)[-1]}"
    return PeriodicFlowDailyChecksumRecord(
        family=family,
        utc_day="2020-01-07",
        archive_url=archive,
        checksum_url=f"{archive}.CHECKSUM",
        checked_at=datetime(2026, 8, 7, 1, tzinfo=UTC),
        http_status=200,
        checksum_response_bytes=len(text.encode("utf-8")),
        checksum_text=text,
        checksum_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        archive_sha256=digest,
        availability="PRESENT",
        request_attempt_count=1,
    )


def _result():
    protocol = _protocol()
    return build_overlap_census_result(
        generated_at=datetime(2026, 8, 7, 2, tzinfo=UTC),
        protocol_file_sha256="7" * 64,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="8" * 64,
        overlap_event=_event(),
        checksum_records=(_checksum("aggTrades"), _checksum("trades")),
        checksum_get_attempt_count=2,
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )


def test_q1_overlap_protocol_freezes_checksum_only_scope() -> None:
    protocol = _protocol()
    assert audit_overlap_census_protocol(protocol)
    assert protocol.maximum_unique_checksum_urls == 2
    assert protocol.archive_payload_requests_permitted is False
    assert protocol.price_or_quantity_parsing_permitted is False
    assert protocol.return_calculation_permitted is False
    assert protocol.paper_operation_permitted is False
    assert protocol.live_permitted is False


def test_q1_overlap_event_refuses_bad_arithmetic() -> None:
    payload = _event().model_dump()
    payload["overlap_raw_trade_id_count"] = 2
    with pytest.raises(ValidationError):
        PeriodicFlowOverlapEvent.model_validate(payload)


def test_q1_overlap_result_authorizes_only_daily_payload_protocol() -> None:
    result = _result()
    assert audit_overlap_census_result(result)
    assert result.decision == Q1_OVERLAP_PASS_DECISION
    assert result.next_authorization == Q1_OVERLAP_PASS_AUTHORIZATION
    assert result.authorizes_daily_cross_source_payload_protocol
    assert result.archive_payload_requests_made == 0
    assert result.price_or_quantity_values_parsed == ()
    assert result.authorizes_testnet_strategy_orders is False
    assert result.authorizes_live is False


def test_q1_overlap_result_refuses_authority_tampering() -> None:
    payload = _result().model_dump()
    payload["authorizes_live"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowOverlapCensusResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_periodic_flow_overlap_census.py",
        "scripts/run_periodic_flow_overlap_census.py",
        "scripts/audit_periodic_flow_overlap_census.py",
    ],
)
def test_q1_overlap_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
