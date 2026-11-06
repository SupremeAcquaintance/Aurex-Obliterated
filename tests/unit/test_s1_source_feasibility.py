from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s1_source_feasibility import (
    S1_SOURCE_PASS_DECISION,
    S1SourceMetadataAudit,
    S1SourceMetadataProtocol,
    S1SourceMetadataResult,
)
from scripts.audit_s1_source_metadata_feasibility import build_audit
from scripts.freeze_s1_source_metadata_feasibility import build_protocol
from scripts.run_s1_source_metadata_feasibility import build_result, response_record

PROTOCOL_PATH = Path(
    "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
)
RESULT_PATH = Path("data/evidence/s1_source_metadata_feasibility_result_v1.json")
AUDIT_PATH = Path("data/evidence/s1_source_metadata_feasibility_audit_v1.json")


def test_frozen_s1_source_protocol_is_exact_and_head_only() -> None:
    stored = S1SourceMetadataProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )

    assert stored == build_protocol(frozen_at=stored.frozen_at)
    assert len(stored.requests) == 4
    assert all(request.method == "HEAD" for request in stored.requests)
    assert stored.response_body_byte_budget == 0
    assert stored.authorizes_response_body_read is False
    assert stored.authorizes_return_testing is False


def test_synthetic_pass_requires_both_vintage_endpoints() -> None:
    protocol = S1SourceMetadataProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    now = datetime(2026, 8, 26, tzinfo=UTC)
    responses = []
    for request in protocol.requests:
        status = 400 if request.request_id == "04-structured-api-no-key" else 200
        content_type = (
            "text/csv"
            if request.role == "NO_KEY_VINTAGE_CSV"
            else "text/html"
        )
        responses.append(
            response_record(
                request_id=request.request_id,
                attempted_at=now,
                status_code=status,
                final_url=request.url,
                content_type=content_type,
                content_length=100,
                etag=None,
                last_modified=None,
                outcome="HTTP_RESPONSE",
            )
        )
    result = build_result(
        protocol_path=PROTOCOL_PATH,
        protocol=protocol,
        responses=tuple(responses),
        completed_at=now,
    )

    assert result.decision == S1_SOURCE_PASS_DECISION
    assert result.response_body_bytes_read == 0
    assert all(gate.status == "PASS" for gate in result.gates)


def test_result_rejects_outcome_authority_tampering() -> None:
    result = S1SourceMetadataResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    payload = json.loads(result.model_dump_json())
    payload["authorizes_return_testing"] = True

    with pytest.raises(ValidationError):
        S1SourceMetadataResult.model_validate(payload)


def test_stored_s1_source_result_and_audit_reconstruct() -> None:
    result = S1SourceMetadataResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1SourceMetadataAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )
    protocol = S1SourceMetadataProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )

    assert result == build_result(
        protocol_path=PROTOCOL_PATH,
        protocol=protocol,
        responses=result.responses,
        completed_at=result.completed_at,
    )
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        result_path=RESULT_PATH,
        audited_at=audit.audited_at,
    )
