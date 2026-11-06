from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v4 import (
    PeriodicFlowSuccessorDnsAttemptAuditV4,
    audit_successor_terminal_audit_v4,
    build_successor_terminal_audit_v4,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def test_v4_terminal_audit_is_hash_bound_and_grants_no_authority() -> None:
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
    attempts = tuple(
        PeriodicFlowSuccessorDnsAttemptAuditV4(
            attempt=number,
            request_file_sha256=_hash(f"request-{number}"),
            response_file_sha256=_hash(f"response-{number}"),
            exception_message="urlopen error getaddrinfo failed",
        )
        for number in range(1, 13)
    )
    audit = build_successor_terminal_audit_v4(
        **hashes,
        audited_at=datetime(2026, 8, 13, tzinfo=UTC),
        frozen_failure_reason="transport failed: getaddrinfo failed",
        attempts=attempts,
        findings=tuple(f"finding-{number}" for number in range(7)),
    )

    assert audit_successor_terminal_audit_v4(audit)
    assert audit.failed_target_payload_bytes_received == 0
    assert audit.authorizes_live is False
    assert audit.orders_submitted == 0
