from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.s2_bigquery_feasibility import audit_model, build_hashed
from aurex.backtest_engine.s2_bigquery_payload import (
    S2_PAYLOAD_NEXT,
    S2_PAYLOAD_PASS,
    S2BigQueryPayloadProtocol,
)
from aurex.backtest_engine.s2_bigquery_payload_v2 import (
    S2BigQueryPayloadFailureAuditV1,
    S2BigQueryPayloadProtocolAuditV2,
    S2BigQueryPayloadProtocolV2,
    S2BigQueryPayloadResultV2,
)
from scripts.freeze_s2_bigquery_payload_protocol_v2 import build_protocol
from scripts.run_s2_bigquery_payload import query_request

V1_PROTOCOL_PATH = Path("data/evidence/s2_bigquery_payload_protocol_v1.json")
V1_FAILURE_AUDIT_PATH = Path("data/evidence/s2_bigquery_payload_failure_audit_v1.json")
V2_PROTOCOL_PATH = Path("data/evidence/s2_bigquery_payload_protocol_v2.json")
V2_PROTOCOL_AUDIT_PATH = Path("data/evidence/s2_bigquery_payload_protocol_audit_v2.json")


def v1_protocol() -> S2BigQueryPayloadProtocol:
    return S2BigQueryPayloadProtocol.model_validate_json(V1_PROTOCOL_PATH.read_text())


def failure_audit() -> S2BigQueryPayloadFailureAuditV1:
    return S2BigQueryPayloadFailureAuditV1.model_validate_json(V1_FAILURE_AUDIT_PATH.read_text())


def test_failed_v1_result_audit_is_hash_valid() -> None:
    audit = failure_audit()
    assert audit_model(audit, "audit_evidence_hash")
    assert audit.query_completed is True
    assert audit.query_result_rows_accepted == 0
    assert audit.payload_bytes_persisted == 0
    assert audit.blocker == "payload_schema_mismatch"


def test_v2_protocol_changes_only_declared_fee_output_cast() -> None:
    before = v1_protocol()
    after = build_protocol(frozen_at=datetime.now(UTC))
    assert isinstance(after, S2BigQueryPayloadProtocolV2)
    old = "SUM(IF(NOT t.is_coinbase, t.fee, 0)) AS confirmed_fee_satoshis,"
    new = "CAST(SUM(IF(NOT t.is_coinbase, t.fee, 0)) AS INT64) AS confirmed_fee_satoshis,"
    assert before.query_spec.google_sql.count(old) == 1
    assert after.query_spec.google_sql == before.query_spec.google_sql.replace(old, new)
    assert after.query_spec.first_week_start == before.query_spec.first_week_start
    assert after.query_spec.last_week_start == before.query_spec.last_week_start
    assert after.query_spec.maximum_bytes_billed == before.query_spec.maximum_bytes_billed
    assert after.observed_schema_mismatch == "confirmed_fee_satoshis:NUMERIC_NOT_INTEGER"
    assert len(after.source_bindings) == 6


def test_frozen_v2_protocol_and_audit_are_hash_valid() -> None:
    protocol = S2BigQueryPayloadProtocolV2.model_validate_json(V2_PROTOCOL_PATH.read_text())
    audit = S2BigQueryPayloadProtocolAuditV2.model_validate_json(V2_PROTOCOL_AUDIT_PATH.read_text())
    assert audit_model(protocol, "protocol_evidence_hash")
    assert audit_model(audit, "audit_evidence_hash")
    assert protocol.protocol_evidence_hash == audit.protocol_evidence_hash
    body = json.loads(query_request(protocol, token="in-memory", project="in-memory").data)
    assert "CAST(SUM(IF(NOT t.is_coinbase, t.fee, 0)) AS INT64)" in body["query"]
    assert body["maximumBytesBilled"] == "60000000000"


def test_v2_success_result_preserves_authority_boundary() -> None:
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    result = build_hashed(
        S2BigQueryPayloadResultV2,
        "result_evidence_hash",
        {
            "generated_at": datetime.now(UTC),
            "protocol_file_sha256": "0" * 64,
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_file_sha256": "1" * 64,
            "protocol_audit_evidence_hash": "2" * 64,
            "feasibility_result_evidence_hash": (protocol.feasibility_result_evidence_hash),
            "feasibility_result_audit_evidence_hash": (
                protocol.feasibility_result_audit_evidence_hash
            ),
            "runner_contract_hash": "3" * 64,
            "prior_payload_result_evidence_hash": (protocol.prior_payload_result_evidence_hash),
            "prior_payload_failure_audit_evidence_hash": (
                protocol.prior_payload_failure_audit_evidence_hash
            ),
            "gcloud_available": True,
            "active_auth_configured": True,
            "active_project_configured": True,
            "billing_boundary_request_count": 1,
            "sandbox_without_billing_verified": True,
            "access_token_request_count": 1,
            "access_token_available": True,
            "query_submission_count": 1,
            "query_result_poll_count": 0,
            "query_result_page_count": 1,
            "query_completed": True,
            "total_bytes_processed": 1,
            "query_result_rows_returned": 280,
            "blockchain_row_values_read": 280,
            "payload_path": protocol.payload_path,
            "payload_file_sha256": "4" * 64,
            "payload_evidence_hash": "5" * 64,
            "payload_byte_count": 1,
            "blockers": (),
            "decision": S2_PAYLOAD_PASS,
            "next_authorization": S2_PAYLOAD_NEXT,
            "authorizes_measurement_protocol": True,
            "limitations": protocol.limitations,
        },
    )
    assert result.authorizes_measurement_protocol is True
    assert result.authorizes_parameters is False
    assert result.authorizes_returns is False
    assert result.authorizes_paper is False
    assert result.authorizes_live is False
