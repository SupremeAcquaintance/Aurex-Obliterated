from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v3 import (
    PeriodicFlowSuccessorTransportAttemptAuditV3,
    audit_successor_terminal_audit_v3,
    build_successor_terminal_audit_v3,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _attempt(number: int) -> PeriodicFlowSuccessorTransportAttemptAuditV3:
    return PeriodicFlowSuccessorTransportAttemptAuditV3(
        attempt=number,
        request_file_sha256=_hash(f"request-{number}"),
        response_file_sha256=_hash(f"response-{number}"),
        range_start=0 if number == 1 else 86_150_831,
        status=200 if number == 1 else None,
        expected_total_bytes=228_784_150,
        bytes_received=86_150_831 if number == 1 else 0,
        partial_bytes_after_attempt=86_150_831,
        failure_class="INCOMPLETE_BODY" if number == 1 else "URL_ERROR",
        exception_type="IncompleteBodyError" if number == 1 else "URLError",
        exception_message=(
            "response incomplete"
            if number == 1
            else "urlopen error getaddrinfo failed"
        ),
    )


def _values() -> dict:
    hash_fields = {
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
            "partial_archive_file_sha256",
        )
    }
    return {
        **hash_fields,
        "audited_at": datetime(2026, 8, 12, tzinfo=UTC),
        "frozen_failure_reason": "transport stopped: getaddrinfo failed",
        "attempts": tuple(_attempt(number) for number in range(1, 13)),
        "partial_archive_path": "data/evidence/archive.zip.part",
        "findings": tuple(f"finding-{number}" for number in range(1, 8)),
    }


def test_v3_terminal_audit_is_hash_bound_and_grants_no_authority() -> None:
    audit = build_successor_terminal_audit_v3(**_values())

    assert audit_successor_terminal_audit_v3(audit)
    assert audit.partial_archive_bytes == 86_150_831
    assert audit.orders_submitted == 0
    assert audit.authorizes_live is False


def test_v3_terminal_attempt_rejects_changed_resume_offset() -> None:
    values = _attempt(2).model_dump()
    values["range_start"] = 1

    with pytest.raises(ValidationError):
        PeriodicFlowSuccessorTransportAttemptAuditV3.model_validate(values)
