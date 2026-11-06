from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_bigquery_feasibility import (
    S2_FEASIBILITY_BLOCK_BILLING,
    S2_FEASIBILITY_BLOCK_CLIENT,
    S2_FEASIBILITY_BLOCK_METADATA,
    S2_FEASIBILITY_BLOCK_PROJECT,
    S2BigQueryFeasibilityProtocol,
    S2BigQueryFeasibilityProtocolAudit,
    S2DryRunSpec,
    S2MetadataAttempt,
    audit_model,
)
from scripts.run_s2_bigquery_feasibility import build_result

PROTOCOL_PATH = "data/evidence/s2_bigquery_feasibility_protocol_v1.json"
PROTOCOL_AUDIT_PATH = (
    "data/evidence/s2_bigquery_feasibility_protocol_audit_v1.json"
)


def protocol() -> S2BigQueryFeasibilityProtocol:
    return S2BigQueryFeasibilityProtocol.model_validate_json(
        open(PROTOCOL_PATH, encoding="utf-8").read()
    )


def protocol_audit() -> S2BigQueryFeasibilityProtocolAudit:
    return S2BigQueryFeasibilityProtocolAudit.model_validate_json(
        open(PROTOCOL_AUDIT_PATH, encoding="utf-8").read()
    )


def failed_attempts() -> tuple[S2MetadataAttempt, ...]:
    return tuple(
        S2MetadataAttempt(
            target_id=target,
            requested_at=datetime.now(UTC),
            http_status=403,
            response_bytes=0,
            response_sha256=None,
            response_path=None,
            expected_reference_matched=False,
            error_class="HTTP_ERROR",
        )
        for target in ("BLOCKS_TABLE", "DATASET", "TRANSACTIONS_TABLE")
    )


def successful_attempts() -> tuple[S2MetadataAttempt, ...]:
    body_hash = sha256(b"{}").hexdigest()
    return tuple(
        S2MetadataAttempt(
            target_id=target,
            requested_at=datetime.now(UTC),
            http_status=200,
            response_bytes=2,
            response_sha256=body_hash,
            response_path=f"data/evidence/{target.lower()}.json",
            expected_reference_matched=True,
            required_schema_fields_present=(),
            error_class="NONE",
        )
        for target in ("BLOCKS_TABLE", "DATASET", "TRANSACTIONS_TABLE")
    )


def result_for(*, attempts, gcloud: bool, bq: bool, project: bool):
    return build_result(
        generated_at=datetime.now(UTC),
        protocol=protocol(),
        protocol_path=Path(PROTOCOL_PATH),
        protocol_audit=protocol_audit(),
        protocol_audit_path=Path(PROTOCOL_AUDIT_PATH),
        attempts=attempts,
        gcloud_available=gcloud,
        bq_available=bq,
        active_project_configured=project,
    )


def test_canonical_protocol_and_audit_validate() -> None:
    assert audit_model(protocol(), "protocol_evidence_hash")
    assert audit_model(protocol_audit(), "audit_evidence_hash")
    assert len(protocol().metadata_endpoints) == 3
    assert len(protocol().dry_run_specs) == 2


def test_query_hash_tampering_is_rejected() -> None:
    query = protocol().dry_run_specs[0]
    payload = query.model_dump()
    payload["google_sql"] += "\n-- changed"
    with pytest.raises(ValidationError):
        S2DryRunSpec.model_validate(payload)


def test_metadata_failure_has_priority() -> None:
    result = result_for(
        attempts=failed_attempts(),
        gcloud=False,
        bq=False,
        project=False,
    )
    assert result.decision == S2_FEASIBILITY_BLOCK_METADATA
    assert result.metadata_request_count == 3


def test_missing_clients_block_after_metadata_passes() -> None:
    result = result_for(
        attempts=successful_attempts(),
        gcloud=False,
        bq=False,
        project=False,
    )
    assert result.decision == S2_FEASIBILITY_BLOCK_CLIENT


def test_missing_project_blocks_after_clients_pass() -> None:
    result = result_for(
        attempts=successful_attempts(),
        gcloud=True,
        bq=True,
        project=False,
    )
    assert result.decision == S2_FEASIBILITY_BLOCK_PROJECT


def test_zero_cost_boundary_blocks_before_dry_run() -> None:
    result = result_for(
        attempts=successful_attempts(),
        gcloud=True,
        bq=True,
        project=True,
    )
    assert result.decision == S2_FEASIBILITY_BLOCK_BILLING
    assert result.dry_run_request_count == 0


def test_result_never_grants_numeric_or_trading_authority() -> None:
    result = result_for(
        attempts=failed_attempts(),
        gcloud=False,
        bq=False,
        project=False,
    )
    assert result.query_execution_count == 0
    assert result.blockchain_row_values_read == 0
    assert result.market_values_read == 0
    assert result.payload_bytes_acquired == 0
    assert result.returns_calculated == 0
    assert result.orders_submitted == 0
    assert result.authorizes_numeric_query is False
    assert result.authorizes_live is False


def test_inconsistent_metadata_success_is_rejected() -> None:
    with pytest.raises(ValidationError):
        S2MetadataAttempt(
            target_id="DATASET",
            requested_at=datetime.now(UTC),
            http_status=200,
            response_bytes=2,
            response_sha256=None,
            response_path=None,
            expected_reference_matched=True,
            error_class="NONE",
        )
