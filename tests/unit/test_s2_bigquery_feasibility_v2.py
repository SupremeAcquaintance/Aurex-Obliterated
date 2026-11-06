from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_bigquery_feasibility import (
    S2BigQueryFeasibilityAudit,
    S2BigQueryFeasibilityResult,
    S2MetadataAttempt,
    audit_model,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v2 import (
    S2_FEASIBILITY_V2_BLOCK_AUTH,
    S2_FEASIBILITY_V2_BLOCK_BILLING,
    S2_FEASIBILITY_V2_BLOCK_CLIENT,
    S2_FEASIBILITY_V2_BLOCK_DRY_RUN,
    S2_FEASIBILITY_V2_BLOCK_METADATA,
    S2_FEASIBILITY_V2_BLOCK_PROJECT,
    S2_FEASIBILITY_V2_PASS,
    S2BigQueryFeasibilityProtocolAuditV2,
    S2BigQueryFeasibilityProtocolV2,
    S2DryRunAttemptV2,
)
from scripts.run_s2_bigquery_feasibility_v2 import build_result

PROTOCOL_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_v2.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v2.json")
PRIOR_RESULT_PATH = Path("data/evidence/s2_bigquery_feasibility_result_v1.json")
PRIOR_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_audit_v1.json")


def protocol() -> S2BigQueryFeasibilityProtocolV2:
    return S2BigQueryFeasibilityProtocolV2.model_validate_json(PROTOCOL_PATH.read_text())


def protocol_audit() -> S2BigQueryFeasibilityProtocolAuditV2:
    return S2BigQueryFeasibilityProtocolAuditV2.model_validate_json(PROTOCOL_AUDIT_PATH.read_text())


def prior_result() -> S2BigQueryFeasibilityResult:
    return S2BigQueryFeasibilityResult.model_validate_json(PRIOR_RESULT_PATH.read_text())


def prior_audit() -> S2BigQueryFeasibilityAudit:
    return S2BigQueryFeasibilityAudit.model_validate_json(PRIOR_AUDIT_PATH.read_text())


def successful_metadata() -> tuple[S2MetadataAttempt, ...]:
    digest = sha256(b"{}").hexdigest()
    return tuple(
        S2MetadataAttempt(
            target_id=target,
            requested_at=datetime.now(UTC),
            http_status=200,
            response_bytes=2,
            response_sha256=digest,
            response_path=f"data/evidence/s2_bigquery_metadata_v2/{target}.json",
            expected_reference_matched=True,
            error_class="NONE",
        )
        for target in ("BLOCKS_TABLE", "DATASET", "TRANSACTIONS_TABLE")
    )


def successful_dry_runs() -> tuple[S2DryRunAttemptV2, ...]:
    return tuple(
        S2DryRunAttemptV2(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=datetime.now(UTC),
            succeeded=True,
            total_bytes_processed=1,
            error_class="NONE",
        )
        for spec in protocol().dry_run_specs
    )


def result_for(
    *,
    gcloud: bool = True,
    bq: bool = True,
    auth: bool = True,
    project: bool = True,
    billing_count: int = 1,
    no_billing: bool = True,
    token_count: int = 1,
    metadata=(),
    dry_runs=(),
):
    return build_result(
        generated_at=datetime.now(UTC),
        protocol=protocol(),
        protocol_path=PROTOCOL_PATH,
        protocol_audit=protocol_audit(),
        protocol_audit_path=PROTOCOL_AUDIT_PATH,
        prior_result=prior_result(),
        prior_audit=prior_audit(),
        gcloud_available=gcloud,
        bq_available=bq,
        active_auth_configured=auth,
        active_project_configured=project,
        billing_boundary_request_count=billing_count,
        sandbox_without_billing_verified=no_billing,
        access_token_request_count=token_count,
        metadata_attempts=metadata,
        dry_run_attempts=dry_runs,
    )


def test_canonical_v2_protocol_and_audit_validate() -> None:
    assert audit_model(protocol(), "protocol_evidence_hash")
    assert audit_model(protocol_audit(), "audit_evidence_hash")
    assert len(protocol().source_bindings) == 6
    assert len(protocol().metadata_endpoints) == 3
    assert len(protocol().dry_run_specs) == 2
    assert protocol().prior_result_evidence_hash == prior_result().result_evidence_hash


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        (
            {
                "gcloud": False,
                "bq": False,
                "auth": False,
                "project": False,
                "billing_count": 0,
                "no_billing": False,
                "token_count": 0,
            },
            S2_FEASIBILITY_V2_BLOCK_CLIENT,
        ),
        (
            {
                "auth": False,
                "project": False,
                "billing_count": 0,
                "no_billing": False,
                "token_count": 0,
            },
            S2_FEASIBILITY_V2_BLOCK_AUTH,
        ),
        (
            {"project": False, "billing_count": 0, "no_billing": False, "token_count": 0},
            S2_FEASIBILITY_V2_BLOCK_PROJECT,
        ),
        ({"no_billing": False, "token_count": 0}, S2_FEASIBILITY_V2_BLOCK_BILLING),
        ({}, S2_FEASIBILITY_V2_BLOCK_METADATA),
    ),
)
def test_prerequisite_decision_order(overrides: dict, expected: str) -> None:
    assert result_for(**overrides).decision == expected


def test_metadata_pass_without_dry_runs_remains_blocked() -> None:
    result = result_for(metadata=successful_metadata())
    assert result.decision == S2_FEASIBILITY_V2_BLOCK_DRY_RUN


def test_complete_feasibility_pass_only_authorizes_payload_protocol() -> None:
    result = result_for(
        metadata=successful_metadata(),
        dry_runs=successful_dry_runs(),
    )
    assert result.decision == S2_FEASIBILITY_V2_PASS
    assert result.next_authorization == "AUTHORIZE_S2_SOURCE_PAYLOAD_PROTOCOL_ONLY"
    assert result.account_identifier_persisted is False
    assert result.project_identifier_persisted is False
    assert result.credentials_or_tokens_persisted is False
    assert result.query_execution_count == 0
    assert result.query_result_rows_returned == 0
    assert result.blockchain_row_values_read == 0
    assert result.returns_calculated == 0
    assert result.orders_submitted == 0
    assert result.authorizes_numeric_query is False
    assert result.authorizes_live is False


def test_metadata_cannot_exist_without_token_request() -> None:
    with pytest.raises(ValidationError):
        result_for(metadata=successful_metadata(), token_count=0)


def test_successful_dry_run_requires_no_error_and_processed_bytes() -> None:
    spec = protocol().dry_run_specs[0]
    with pytest.raises(ValidationError):
        S2DryRunAttemptV2(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=datetime.now(UTC),
            succeeded=True,
            total_bytes_processed=1,
            error_class="API_ERROR",
        )
