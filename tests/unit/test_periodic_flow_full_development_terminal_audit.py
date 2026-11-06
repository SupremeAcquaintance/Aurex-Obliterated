from __future__ import annotations

import hashlib
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.periodic_flow_full_development_terminal_audit import (
    PeriodicFlowObservedGap,
    audit_terminal_acquisition_audit,
    build_terminal_acquisition_audit,
)
from scripts.audit_periodic_flow_full_development_terminal import scan_spot_archive


def test_independent_spot_scan_does_not_parse_price_or_quantity(tmp_path: Path) -> None:
    path = tmp_path / "BTCUSDT-aggTrades-2020-02.zip"
    rows = (
        "1,NOT_A_PRICE,NOT_A_QUANTITY,10,10,1580515200000,true,IGNORED\n"
        "2,STILL_NOT_A_PRICE,STILL_NOT_A_QUANTITY,11,11,1580515260000,false,IGNORED\n"
        "3,NO_PRICE,NO_QUANTITY,12,12,1580515380000,true,IGNORED\n"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-aggTrades-2020-02.csv", rows)

    scan = scan_spot_archive(
        path=path,
        month="2020-02",
        expected_member="BTCUSDT-aggTrades-2020-02.csv",
    )

    assert scan.row_count == 3
    assert scan.unique_minute_count == 3
    assert scan.maximum_event_gap_minutes == 2
    assert scan.maximum_missing_minute_run == 1
    assert scan.gaps[0].missing_start_minute_ms == 1580515320000


def test_terminal_audit_is_hash_bound_and_no_outcome() -> None:
    gap = PeriodicFlowObservedGap(
        preceding_observed_minute_ms=60_000,
        missing_start_minute_ms=120_000,
        missing_end_minute_ms=21_300_000,
        following_observed_minute_ms=21_360_000,
        observed_minute_distance=355,
        missing_minute_count=354,
    )
    values = {
        "audited_at": datetime(2026, 8, 10, 18, tzinfo=UTC),
        "result_file_sha256": "1" * 64,
        "result_evidence_hash": "2" * 64,
        "checkpoint_file_sha256": "3" * 64,
        "checkpoint_evidence_hash": "4" * 64,
        "protocol_file_sha256": "5" * 64,
        "protocol_evidence_hash": "6" * 64,
        "execution_contract_file_sha256": "7" * 64,
        "execution_contract_evidence_hash": "8" * 64,
        "runner_source_hash": "9" * 64,
        "auditor_contract_hash": "a" * 64,
        "prior_remediation_result_file_sha256": "b" * 64,
        "prior_remediation_result_evidence_hash": "c" * 64,
        "prior_remediation_audit_file_sha256": "d" * 64,
        "prior_remediation_audit_evidence_hash": "e" * 64,
        "failed_archive_local_path": "archive.zip",
        "failed_archive_sha256": hashlib.sha256(b"archive").hexdigest(),
        "failed_archive_bytes": 7,
        "failed_archive_member_name": "archive.csv",
        "failed_archive_row_count": 100_000,
        "expected_minute_count": 100,
        "unique_minute_count": 99,
        "minute_coverage_fraction": Decimal("0.99"),
        "maximum_event_gap_minutes": 355,
        "maximum_missing_minute_run": 354,
        "observed_gaps": (gap,),
        "reconstructed_reason_codes": ("EVENT_GAP_EXCEEDS_15_MINUTES",),
        "frozen_failure_reason": (
            "Archive structural gates failed: ('EVENT_GAP_EXCEEDS_15_MINUTES',)"
        ),
        "prior_matching_gap_count": 1,
        "findings": (
            "a",
            "b",
            "c",
            "d",
            "e",
        ),
    }

    audit = build_terminal_acquisition_audit(**values)

    assert audit_terminal_acquisition_audit(audit)
    assert audit.returns_calculated == ()
    assert audit.orders_submitted == 0
    assert audit.authorizes_live is False
