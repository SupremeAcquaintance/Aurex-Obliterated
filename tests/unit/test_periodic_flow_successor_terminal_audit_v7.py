from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v7 import (
    EXPECTED_EXCLUSION_REASON_COUNTS,
    EXPECTED_QUALIFIED_MONTHS_BY_YEAR,
    audit_successor_terminal_audit_v7,
    build_successor_terminal_audit_v7,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def test_v7_terminal_audit_confirms_stop_and_grants_no_authority() -> None:
    hashes = {
        name: _hash(name)
        for name in (
            "result_file_sha256",
            "result_evidence_hash",
            "checkpoint_file_sha256",
            "checkpoint_evidence_hash",
            "protocol_file_sha256",
            "protocol_evidence_hash",
            "transport_amendment_file_sha256",
            "transport_amendment_evidence_hash",
            "execution_contract_file_sha256",
            "execution_contract_evidence_hash",
            "execution_contract_audit_file_sha256",
            "execution_contract_audit_evidence_hash",
            "runner_source_hash",
            "auditor_contract_hash",
            "request_marker_manifest_hash",
        )
    }
    audit = build_successor_terminal_audit_v7(
        **hashes,
        audited_at=datetime(2026, 8, 14, tzinfo=UTC),
        qualified_months_by_year=EXPECTED_QUALIFIED_MONTHS_BY_YEAR,
        exclusion_reason_counts=EXPECTED_EXCLUSION_REASON_COUNTS,
        findings=tuple(f"finding-{number}" for number in range(10)),
    )

    assert audit_successor_terminal_audit_v7(audit)
    assert audit.authorizes_measurement_protocol is False
    assert audit.authorizes_live is False
    assert audit.orders_submitted == 0
    assert audit.next_authorization == "NONE_SOURCE_SUFFICIENCY_FAILED"
