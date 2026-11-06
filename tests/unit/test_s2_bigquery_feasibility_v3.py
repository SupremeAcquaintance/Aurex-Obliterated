from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_bigquery_feasibility import audit_model
from aurex.backtest_engine.s2_bigquery_feasibility_v2 import (
    S2BigQueryFeasibilityAuditV2,
    S2BigQueryFeasibilityResultV2,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (
    S2_FEASIBILITY_V3_BLOCK_AUTH,
    S2_FEASIBILITY_V3_BLOCK_BILLING,
    S2_FEASIBILITY_V3_BLOCK_CLIENT,
    S2_FEASIBILITY_V3_BLOCK_DRY_RUN,
    S2_FEASIBILITY_V3_BLOCK_PROJECT,
    S2_FEASIBILITY_V3_BLOCK_TOKEN,
    S2_FEASIBILITY_V3_PASS,
    S2BigQueryFeasibilityProtocolAuditV3,
    S2BigQueryFeasibilityProtocolV3,
    S2RestDryRunAttemptV3,
)
from scripts.run_s2_bigquery_feasibility_v3 import (
    build_result,
    classify_rest_error,
    response_total_bytes,
)

PROTOCOL_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_v3.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v3.json")
PRIOR_RESULT_PATH = Path("data/evidence/s2_bigquery_feasibility_result_v2.json")
PRIOR_AUDIT_PATH = Path("data/evidence/s2_bigquery_feasibility_audit_v2.json")


def protocol() -> S2BigQueryFeasibilityProtocolV3:
    return S2BigQueryFeasibilityProtocolV3.model_validate_json(PROTOCOL_PATH.read_text())


def protocol_audit() -> S2BigQueryFeasibilityProtocolAuditV3:
    return S2BigQueryFeasibilityProtocolAuditV3.model_validate_json(PROTOCOL_AUDIT_PATH.read_text())


def prior_result() -> S2BigQueryFeasibilityResultV2:
    return S2BigQueryFeasibilityResultV2.model_validate_json(PRIOR_RESULT_PATH.read_text())


def prior_audit() -> S2BigQueryFeasibilityAuditV2:
    return S2BigQueryFeasibilityAuditV2.model_validate_json(PRIOR_AUDIT_PATH.read_text())


def successful_attempts() -> tuple[S2RestDryRunAttemptV3, ...]:
    return tuple(
        S2RestDryRunAttemptV3(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=datetime.now(UTC),
            http_status=200,
            response_bytes=100,
            succeeded=True,
            total_bytes_processed=1,
            error_class="NONE",
        )
        for spec in protocol().dry_run_specs
    )


def result_for(
    *,
    gcloud: bool = True,
    auth: bool = True,
    project: bool = True,
    billing_count: int = 1,
    no_billing: bool = True,
    token_count: int = 1,
    token_available: bool = True,
    attempts=(),
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
        active_auth_configured=auth,
        active_project_configured=project,
        billing_boundary_request_count=billing_count,
        sandbox_without_billing_verified=no_billing,
        access_token_request_count=token_count,
        access_token_available=token_available,
        attempts=attempts,
    )


def test_canonical_v3_protocol_and_audit_validate() -> None:
    assert audit_model(protocol(), "protocol_evidence_hash")
    assert audit_model(protocol_audit(), "audit_evidence_hash")
    assert len(protocol().source_bindings) == 8
    assert protocol().prior_result_evidence_hash == prior_result().result_evidence_hash
    assert protocol().prior_result_decision == "BLOCK_S2_BIGQUERY_V2_DRY_RUN_FAILED"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        (
            {
                "gcloud": False,
                "auth": False,
                "project": False,
                "billing_count": 0,
                "no_billing": False,
                "token_count": 0,
                "token_available": False,
            },
            S2_FEASIBILITY_V3_BLOCK_CLIENT,
        ),
        (
            {
                "auth": False,
                "project": False,
                "billing_count": 0,
                "no_billing": False,
                "token_count": 0,
                "token_available": False,
            },
            S2_FEASIBILITY_V3_BLOCK_AUTH,
        ),
        (
            {
                "project": False,
                "billing_count": 0,
                "no_billing": False,
                "token_count": 0,
                "token_available": False,
            },
            S2_FEASIBILITY_V3_BLOCK_PROJECT,
        ),
        (
            {"no_billing": False, "token_count": 0, "token_available": False},
            S2_FEASIBILITY_V3_BLOCK_BILLING,
        ),
        ({"token_available": False}, S2_FEASIBILITY_V3_BLOCK_TOKEN),
        ({}, S2_FEASIBILITY_V3_BLOCK_DRY_RUN),
    ),
)
def test_prerequisite_decision_order(overrides: dict, expected: str) -> None:
    assert result_for(**overrides).decision == expected


def test_complete_rest_dry_run_pass_only_authorizes_payload_protocol() -> None:
    result = result_for(attempts=successful_attempts())
    assert result.decision == S2_FEASIBILITY_V3_PASS
    assert result.next_authorization == "AUTHORIZE_S2_SOURCE_PAYLOAD_PROTOCOL_ONLY"
    assert result.response_bodies_persisted == 0
    assert result.query_execution_count == 0
    assert result.query_result_rows_returned == 0
    assert result.blockchain_row_values_read == 0
    assert result.parameters_defined == 0
    assert result.orders_submitted == 0
    assert result.authorizes_numeric_query is False
    assert result.authorizes_live is False


def test_attempt_after_failed_attempt_is_rejected() -> None:
    first, second = successful_attempts()
    failed = first.model_copy(
        update={
            "http_status": 403,
            "succeeded": False,
            "total_bytes_processed": None,
            "error_class": "PERMISSION_ERROR",
        }
    )
    with pytest.raises(ValidationError):
        result_for(attempts=(failed, second))


@pytest.mark.parametrize(
    ("status", "reason", "expected"),
    (
        (401, "invalidCredentials", "AUTH_ERROR"),
        (403, "accessNotConfigured", "API_DISABLED"),
        (403, "billingNotEnabled", "BILLING_ERROR"),
        (403, "quotaExceeded", "QUOTA_ERROR"),
        (403, "accessDenied", "PERMISSION_ERROR"),
        (400, "invalidQuery", "INVALID_QUERY"),
        (404, "notFound", "NOT_FOUND"),
        (500, "backendError", "API_ERROR"),
    ),
)
def test_rest_error_classification_is_sanitized(status: int, reason: str, expected: str) -> None:
    payload = {"error": {"errors": [{"reason": reason, "message": "not persisted"}]}}
    assert classify_rest_error(status, payload) == expected


def test_total_bytes_accepts_both_bigquery_statistics_shapes() -> None:
    assert response_total_bytes({"statistics": {"totalBytesProcessed": "12"}}) == 12
    assert response_total_bytes({"statistics": {"query": {"totalBytesProcessed": "13"}}}) == 13
