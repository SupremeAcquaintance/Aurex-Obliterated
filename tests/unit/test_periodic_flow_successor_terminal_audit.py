from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_successor_terminal_audit import (
    PeriodicFlowSuccessorTransportAttemptAudit,
    audit_successor_terminal_audit,
    build_successor_terminal_audit,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _attempt(
    attempt: int, *, status: int | None, content_length: int | None, received: int
) -> PeriodicFlowSuccessorTransportAttemptAudit:
    started = datetime(2026, 8, 10, 21, attempt, tzinfo=UTC)
    completed = started + timedelta(seconds=attempt)
    return PeriodicFlowSuccessorTransportAttemptAudit(
        attempt=attempt,
        request_file_sha256=_hash(f"request-{attempt}"),
        response_file_sha256=_hash(f"response-{attempt}"),
        requested_at=started,
        completed_at=completed,
        duration_seconds=Decimal(attempt),
        status=status,
        content_length=content_length,
        bytes_received=received,
    )


def _values() -> dict:
    attempts = (
        _attempt(1, status=200, content_length=370_923_781, received=3_597_961),
        _attempt(2, status=None, content_length=None, received=0),
        _attempt(3, status=200, content_length=370_923_781, received=12_734_069),
    )
    return {
        "audited_at": datetime(2026, 8, 10, 22, tzinfo=UTC),
        "result_file_sha256": _hash("result-file"),
        "result_evidence_hash": _hash("result-evidence"),
        "checkpoint_file_sha256": _hash("checkpoint-file"),
        "checkpoint_evidence_hash": _hash("checkpoint-evidence"),
        "protocol_file_sha256": _hash("protocol-file"),
        "protocol_evidence_hash": _hash("protocol-evidence"),
        "protocol_audit_file_sha256": _hash("protocol-audit-file"),
        "protocol_audit_evidence_hash": _hash("protocol-audit-evidence"),
        "execution_contract_file_sha256": _hash("contract-file"),
        "execution_contract_evidence_hash": _hash("contract-evidence"),
        "execution_contract_audit_file_sha256": _hash("contract-audit-file"),
        "execution_contract_audit_evidence_hash": _hash("contract-audit-evidence"),
        "runner_source_hash": _hash("runner"),
        "auditor_contract_hash": _hash("auditor"),
        "attempts": attempts,
        "request_marker_manifest_hash": _hash("markers"),
        "findings": tuple(f"finding-{index}" for index in range(7)),
    }


def test_terminal_audit_is_hash_bound_and_grants_no_authority() -> None:
    audit = build_successor_terminal_audit(**_values())

    assert audit_successor_terminal_audit(audit)
    assert audit.cumulative_payload_bytes_received == 16_332_030
    assert audit.precise_transport_exception_reconstructable is False
    assert audit.orders_submitted == 0
    assert audit.authorizes_live is False


def test_attempt_rejects_impossible_body_accounting() -> None:
    with pytest.raises(ValidationError):
        _attempt(1, status=200, content_length=10, received=11)


def test_terminal_audit_rejects_changed_attempt_bytes() -> None:
    values = _values()
    values["attempts"] = (
        _attempt(1, status=200, content_length=370_923_781, received=3_597_962),
        values["attempts"][1],
        values["attempts"][2],
    )

    with pytest.raises(ValidationError):
        build_successor_terminal_audit(**values)
