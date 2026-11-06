from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v6 import (
    PeriodicFlowSuccessorTransportAttemptAuditV6,
    audit_successor_terminal_audit_v6,
    build_successor_terminal_audit_v6,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def test_v6_terminal_audit_is_hash_bound_and_grants_no_authority() -> None:
    hashes = {
        name: _hash(name)
        for name in (
            "result_file_sha256",
            "result_evidence_hash",
            "checkpoint_file_sha256",
            "checkpoint_evidence_hash",
            "protocol_file_sha256",
            "protocol_evidence_hash",
            "validator_amendment_file_sha256",
            "validator_amendment_evidence_hash",
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
        PeriodicFlowSuccessorTransportAttemptAuditV6(
            attempt=number,
            request_file_sha256=_hash(f"request-{number}"),
            response_file_sha256=_hash(f"response-{number}"),
            range_start=0 if number <= 14 else 184_135_287,
            status=200 if number == 14 else None,
            bytes_received=184_135_287 if number == 14 else 0,
            partial_bytes_after_attempt=0 if number < 14 else 184_135_287,
            failure_class="INCOMPLETE_BODY" if number == 14 else "URL_ERROR",
            exception_type=(
                "IncompleteBodyError" if number == 14 else "URLError"
            ),
            exception_message=(
                "response ended early"
                if number == 14
                else "urlopen error getaddrinfo failed"
            ),
        )
        for number in range(1, 25)
    )
    audit = build_successor_terminal_audit_v6(
        **hashes,
        audited_at=datetime(2026, 8, 14, tzinfo=UTC),
        frozen_failure_reason="transport failed: getaddrinfo failed",
        attempts=attempts,
        findings=tuple(f"finding-{number}" for number in range(8)),
    )

    assert audit_successor_terminal_audit_v6(audit)
    assert audit.failed_target_payload_bytes_received == 184_135_287
    assert audit.authorizes_live is False
    assert audit.orders_submitted == 0
