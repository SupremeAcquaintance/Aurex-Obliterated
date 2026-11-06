from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from aurex.backtest_engine.s2_bigquery_feasibility import S2FeasibilityBinding
from aurex.backtest_engine.s2_bigquery_payload import (
    S2BigQueryPayloadAudit,
    S2BigQueryPayloadProtocol,
    S2BigQueryPayloadProtocolAudit,
    S2BigQueryPayloadResult,
)
from aurex.backtest_engine.universe import normalize_sha256


class S2BigQueryPayloadFailureAuditV1(S2BigQueryPayloadProtocolAudit):
    schema_version: Literal["aurex-s2-bigquery-payload-failure-audit-v1"] = (
        "aurex-s2-bigquery-payload-failure-audit-v1"
    )
    audit_id: Literal["s2-bigquery-payload-failure-audit-v1"] = (
        "s2-bigquery-payload-failure-audit-v1"
    )
    protocol_path: Literal["data/evidence/s2_bigquery_payload_protocol_v1.json"] = (
        "data/evidence/s2_bigquery_payload_protocol_v1.json"
    )
    result_path: Literal["data/evidence/s2_bigquery_payload_result_v1.json"] = (
        "data/evidence/s2_bigquery_payload_result_v1.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    runner_contract_hash: str
    result_reconstructed_exactly: Literal[True] = True
    query_submission_count: Literal[1] = 1
    query_completed: Literal[True] = True
    query_result_rows_accepted: Literal[0] = 0
    payload_bytes_persisted: Literal[0] = 0
    blocker: Literal["payload_schema_mismatch"] = "payload_schema_mismatch"
    decision: Literal["BLOCK_S2_PAYLOAD_VALIDATION_FAILED"] = "BLOCK_S2_PAYLOAD_VALIDATION_FAILED"
    next_authorization: Literal["AUTHORIZE_SEPARATELY_FROZEN_S2_PAYLOAD_SCHEMA_AMENDMENT_ONLY"] = (
        "AUTHORIZE_SEPARATELY_FROZEN_S2_PAYLOAD_SCHEMA_AMENDMENT_ONLY"
    )

    @field_validator("result_file_sha256", "result_evidence_hash", "runner_contract_hash")
    @classmethod
    def normalize_result_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S2BigQueryPayloadProtocolV2(S2BigQueryPayloadProtocol):
    schema_version: Literal["aurex-s2-bigquery-payload-protocol-v2"] = (
        "aurex-s2-bigquery-payload-protocol-v2"
    )
    protocol_id: Literal["s2-bigquery-payload-protocol-v2"] = "s2-bigquery-payload-protocol-v2"
    status: Literal["FROZEN_BEFORE_S2_PAYLOAD_SCHEMA_RETRY"] = (
        "FROZEN_BEFORE_S2_PAYLOAD_SCHEMA_RETRY"
    )
    prior_payload_protocol_evidence_hash: str
    prior_payload_protocol_audit_evidence_hash: str
    prior_payload_result_evidence_hash: str
    prior_payload_failure_audit_evidence_hash: str
    prior_payload_result_decision: Literal["BLOCK_S2_PAYLOAD_VALIDATION_FAILED"]
    observed_schema_mismatch: Literal["confirmed_fee_satoshis:NUMERIC_NOT_INTEGER"] = (
        "confirmed_fee_satoshis:NUMERIC_NOT_INTEGER"
    )
    amendment: Literal["CAST_CONFIRMED_FEE_SATOSHIS_SUM_TO_INT64"] = (
        "CAST_CONFIRMED_FEE_SATOSHIS_SUM_TO_INT64"
    )
    source_bindings: tuple[S2FeasibilityBinding, ...] = Field(min_length=6, max_length=6)
    decision: Literal["AMEND_S2_PAYLOAD_SCHEMA_CAST_ONLY"] = "AMEND_S2_PAYLOAD_SCHEMA_CAST_ONLY"
    next_authorization: Literal["RUN_S2_DEVELOPMENT_PAYLOAD_V2_ONCE"] = (
        "RUN_S2_DEVELOPMENT_PAYLOAD_V2_ONCE"
    )

    @field_validator(
        "prior_payload_protocol_evidence_hash",
        "prior_payload_protocol_audit_evidence_hash",
        "prior_payload_result_evidence_hash",
        "prior_payload_failure_audit_evidence_hash",
    )
    @classmethod
    def normalize_prior_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S2BigQueryPayloadProtocolAuditV2(S2BigQueryPayloadProtocolAudit):
    schema_version: Literal["aurex-s2-bigquery-payload-protocol-audit-v2"] = (
        "aurex-s2-bigquery-payload-protocol-audit-v2"
    )
    audit_id: Literal["s2-bigquery-payload-protocol-audit-v2"] = (
        "s2-bigquery-payload-protocol-audit-v2"
    )
    protocol_path: Literal["data/evidence/s2_bigquery_payload_protocol_v2.json"] = (
        "data/evidence/s2_bigquery_payload_protocol_v2.json"
    )
    prior_payload_result_evidence_hash: str
    prior_payload_failure_audit_evidence_hash: str
    decision: Literal["PASS_S2_BIGQUERY_PAYLOAD_PROTOCOL_V2_AUDIT"] = (
        "PASS_S2_BIGQUERY_PAYLOAD_PROTOCOL_V2_AUDIT"
    )
    next_authorization: Literal["RUN_S2_DEVELOPMENT_PAYLOAD_V2_ONCE"] = (
        "RUN_S2_DEVELOPMENT_PAYLOAD_V2_ONCE"
    )

    @field_validator(
        "prior_payload_result_evidence_hash",
        "prior_payload_failure_audit_evidence_hash",
    )
    @classmethod
    def normalize_prior_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S2BigQueryPayloadResultV2(S2BigQueryPayloadResult):
    schema_version: Literal["aurex-s2-bigquery-payload-result-v2"] = (
        "aurex-s2-bigquery-payload-result-v2"
    )
    result_id: Literal["s2-bigquery-payload-result-v2"] = "s2-bigquery-payload-result-v2"
    prior_payload_result_evidence_hash: str
    prior_payload_failure_audit_evidence_hash: str

    @field_validator(
        "prior_payload_result_evidence_hash",
        "prior_payload_failure_audit_evidence_hash",
    )
    @classmethod
    def normalize_prior_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S2BigQueryPayloadAuditV2(S2BigQueryPayloadAudit):
    schema_version: Literal["aurex-s2-bigquery-payload-audit-v2"] = (
        "aurex-s2-bigquery-payload-audit-v2"
    )
    audit_id: Literal["s2-bigquery-payload-audit-v2"] = "s2-bigquery-payload-audit-v2"
    prior_payload_result_evidence_hash: str
    prior_payload_failure_audit_evidence_hash: str

    @field_validator(
        "prior_payload_result_evidence_hash",
        "prior_payload_failure_audit_evidence_hash",
    )
    @classmethod
    def normalize_prior_hashes(cls, value: str) -> str:
        return normalize_sha256(value)
