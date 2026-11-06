from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_FEASIBILITY_PASS = "PASS_S2_BIGQUERY_METADATA_AND_DRY_RUN_FEASIBILITY"
S2_FEASIBILITY_BLOCK_METADATA = "BLOCK_S2_BIGQUERY_PUBLIC_METADATA_UNAVAILABLE"
S2_FEASIBILITY_BLOCK_CLIENT = "BLOCK_S2_BIGQUERY_LOCAL_CLIENT_UNAVAILABLE"
S2_FEASIBILITY_BLOCK_PROJECT = "BLOCK_S2_BIGQUERY_PROJECT_OR_AUTH_UNAVAILABLE"
S2_FEASIBILITY_BLOCK_BILLING = "BLOCK_S2_BIGQUERY_ZERO_COST_BOUNDARY_UNVERIFIED"
S2_FEASIBILITY_BLOCK_DRY_RUN = "BLOCK_S2_BIGQUERY_DRY_RUN_FAILED"
S2_FEASIBILITY_RETRY = "NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_PASSES"
S2_FEASIBILITY_NEXT = "AUTHORIZE_S2_SOURCE_PAYLOAD_PROTOCOL_ONLY"


class S2FeasibilityBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S2MetadataEndpointSpec(BaseModel):
    target_id: Literal["DATASET", "BLOCKS_TABLE", "TRANSACTIONS_TABLE"]
    url: str
    expected_reference: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_endpoint(self) -> S2MetadataEndpointSpec:
        if not self.url.startswith(
            "https://bigquery.googleapis.com/bigquery/v2/projects/"
            "bigquery-public-data/datasets/crypto_bitcoin"
        ):
            raise ValueError("S2 metadata endpoint escaped the frozen public dataset")
        return self


class S2DryRunSpec(BaseModel):
    query_id: Literal["DEVELOPMENT_WEEKLY_AGGREGATE", "CAUSAL_SIX_CONFIRMATION"]
    google_sql: str = Field(min_length=100)
    query_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("query_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_query(self) -> S2DryRunSpec:
        normalized = " ".join(self.google_sql.upper().split())
        required = (
            "BIGQUERY-PUBLIC-DATA.CRYPTO_BITCOIN",
            "IS_COINBASE",
            "FEE",
            "BLOCK_TIMESTAMP",
        )
        forbidden = ("PRICE", "RETURN", "NFCI", "FUNDING", "SELECT *")
        if not all(token in normalized for token in required) or any(
            token in normalized for token in forbidden
        ):
            raise ValueError("S2 dry-run SQL escaped the chartered measurement family")
        if sha256(self.google_sql.encode("utf-8")).hexdigest() != self.query_sha256:
            raise ValueError("S2 dry-run query hash changed")
        return self


class S2BigQueryFeasibilityProtocol(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-protocol-v1"] = (
        "aurex-s2-bigquery-feasibility-protocol-v1"
    )
    protocol_id: Literal["s2-bigquery-feasibility-protocol-v1"] = (
        "s2-bigquery-feasibility-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_BIGQUERY_REQUESTS"] = (
        "FROZEN_BEFORE_BIGQUERY_REQUESTS"
    )
    builder_contract_hash: str
    charter_evidence_hash: str
    source_bindings: tuple[S2FeasibilityBinding, ...] = Field(min_length=2, max_length=2)
    metadata_endpoints: tuple[S2MetadataEndpointSpec, ...] = Field(
        min_length=3,
        max_length=3,
    )
    dry_run_specs: tuple[S2DryRunSpec, ...] = Field(min_length=2, max_length=2)
    source_project: Literal["bigquery-public-data"] = "bigquery-public-data"
    source_dataset: Literal["crypto_bitcoin"] = "crypto_bitcoin"
    processing_location: Literal["US"] = "US"
    maximum_metadata_requests: Literal[3] = 3
    maximum_metadata_response_bytes_each: Literal[2_000_000] = 2_000_000
    request_timeout_seconds: Literal[20] = 20
    required_local_commands: tuple[str, ...] = ("bq", "gcloud")
    required_billing_mode: Literal["BIGQUERY_SANDBOX_WITHOUT_BILLING_ACCOUNT"] = (
        "BIGQUERY_SANDBOX_WITHOUT_BILLING_ACCOUNT"
    )
    maximum_dry_run_requests: Literal[2] = 2
    dry_run_only: Literal[True] = True
    query_results_requested: Literal[False] = False
    query_result_rows_permitted: Literal[0] = 0
    metadata_values_permitted: Literal[True] = True
    blockchain_row_values_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    payload_acquisition_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    decision: Literal["FREEZE_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_ONLY"] = (
        "FREEZE_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_ONLY"
    )
    next_authorization: Literal["RUN_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_ONCE"] = (
        "RUN_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_ONCE"
    )
    limitations: tuple[str, ...] = Field(min_length=5)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "charter_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S2BigQueryFeasibilityProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        targets = tuple(item.target_id for item in self.metadata_endpoints)
        queries = tuple(item.query_id for item in self.dry_run_specs)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S2 feasibility source bindings must be unique and sorted")
        if targets != ("BLOCKS_TABLE", "DATASET", "TRANSACTIONS_TABLE"):
            raise ValueError("S2 feasibility metadata targets changed")
        if queries != ("CAUSAL_SIX_CONFIRMATION", "DEVELOPMENT_WEEKLY_AGGREGATE"):
            raise ValueError("S2 feasibility dry-run set changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S2 feasibility limitations must be unique and sorted")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S2 feasibility protocol hash changed")
        return self


class S2BigQueryFeasibilityProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-protocol-audit-v1"] = (
        "aurex-s2-bigquery-feasibility-protocol-audit-v1"
    )
    audit_id: Literal["s2-bigquery-feasibility-protocol-audit-v1"] = (
        "s2-bigquery-feasibility-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal[
        "data/evidence/s2_bigquery_feasibility_protocol_v1.json"
    ] = "data/evidence/s2_bigquery_feasibility_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    metadata_values_observed: Literal[0] = 0
    blockchain_row_values_observed: Literal[0] = 0
    query_results_observed: Literal[0] = 0
    orders_observed: Literal[0] = 0
    decision: Literal["PASS_S2_BIGQUERY_FEASIBILITY_PROTOCOL_AUDIT"] = (
        "PASS_S2_BIGQUERY_FEASIBILITY_PROTOCOL_AUDIT"
    )
    next_authorization: Literal["RUN_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_ONCE"] = (
        "RUN_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_ONCE"
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "charter_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2BigQueryFeasibilityProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 feasibility protocol audit hash changed")
        return self


class S2MetadataAttempt(BaseModel):
    target_id: Literal["DATASET", "BLOCKS_TABLE", "TRANSACTIONS_TABLE"]
    requested_at: datetime
    http_status: int = Field(ge=0, le=599)
    response_bytes: int = Field(ge=0, le=2_000_000)
    response_sha256: str | None
    response_path: str | None
    expected_reference_matched: bool
    required_schema_fields_present: tuple[str, ...] = ()
    error_class: Literal["NONE", "HTTP_ERROR", "NETWORK_ERROR", "INVALID_JSON"]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("response_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S2MetadataAttempt:
        successful = self.error_class == "NONE"
        if successful != (
            self.http_status == 200
            and self.response_bytes > 0
            and self.response_sha256 is not None
            and self.response_path is not None
            and self.expected_reference_matched
        ):
            raise ValueError("S2 metadata attempt success state is inconsistent")
        return self


class S2DryRunEvidence(BaseModel):
    query_id: Literal["DEVELOPMENT_WEEKLY_AGGREGATE", "CAUSAL_SIX_CONFIRMATION"]
    query_sha256: str
    total_bytes_processed: int = Field(ge=0)
    query_valid: Literal[True] = True
    result_rows_returned: Literal[0] = 0

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("query_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S2BigQueryFeasibilityResult(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-result-v1"] = (
        "aurex-s2-bigquery-feasibility-result-v1"
    )
    result_id: Literal["s2-bigquery-feasibility-result-v1"] = (
        "s2-bigquery-feasibility-result-v1"
    )
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    metadata_attempts: tuple[S2MetadataAttempt, ...] = Field(max_length=3)
    gcloud_available: bool
    bq_available: bool
    active_project_configured: bool
    sandbox_without_billing_verified: bool
    dry_run_evidence: tuple[S2DryRunEvidence, ...] = Field(max_length=2)
    metadata_request_count: int = Field(ge=0, le=3)
    dry_run_request_count: int = Field(ge=0, le=2)
    query_execution_count: Literal[0] = 0
    query_result_rows_returned: Literal[0] = 0
    blockchain_row_values_read: Literal[0] = 0
    market_values_read: Literal[0] = 0
    payload_bytes_acquired: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    blockers: tuple[str, ...]
    decision: Literal[
        "PASS_S2_BIGQUERY_METADATA_AND_DRY_RUN_FEASIBILITY",
        "BLOCK_S2_BIGQUERY_PUBLIC_METADATA_UNAVAILABLE",
        "BLOCK_S2_BIGQUERY_LOCAL_CLIENT_UNAVAILABLE",
        "BLOCK_S2_BIGQUERY_PROJECT_OR_AUTH_UNAVAILABLE",
        "BLOCK_S2_BIGQUERY_ZERO_COST_BOUNDARY_UNVERIFIED",
        "BLOCK_S2_BIGQUERY_DRY_RUN_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S2_SOURCE_PAYLOAD_PROTOCOL_ONLY",
        "NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_PASSES",
    ]
    authorizes_numeric_query: Literal[False] = False
    authorizes_payload_acquisition: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=5)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S2BigQueryFeasibilityResult:
        targets = tuple(item.target_id for item in self.metadata_attempts)
        query_ids = tuple(item.query_id for item in self.dry_run_evidence)
        metadata_passed = targets == (
            "BLOCKS_TABLE",
            "DATASET",
            "TRANSACTIONS_TABLE",
        ) and all(item.error_class == "NONE" for item in self.metadata_attempts)
        client_passed = self.gcloud_available and self.bq_available
        dry_run_passed = query_ids == (
            "CAUSAL_SIX_CONFIRMATION",
            "DEVELOPMENT_WEEKLY_AGGREGATE",
        )
        if not metadata_passed:
            expected_decision = S2_FEASIBILITY_BLOCK_METADATA
        elif not client_passed:
            expected_decision = S2_FEASIBILITY_BLOCK_CLIENT
        elif not self.active_project_configured:
            expected_decision = S2_FEASIBILITY_BLOCK_PROJECT
        elif not self.sandbox_without_billing_verified:
            expected_decision = S2_FEASIBILITY_BLOCK_BILLING
        elif not dry_run_passed:
            expected_decision = S2_FEASIBILITY_BLOCK_DRY_RUN
        else:
            expected_decision = S2_FEASIBILITY_PASS
        expected_next = (
            S2_FEASIBILITY_NEXT
            if expected_decision == S2_FEASIBILITY_PASS
            else S2_FEASIBILITY_RETRY
        )
        if (
            targets != tuple(sorted(set(targets)))
            or query_ids != tuple(sorted(set(query_ids)))
            or self.metadata_request_count != len(self.metadata_attempts)
            or self.dry_run_request_count != len(self.dry_run_evidence)
            or self.blockers != tuple(sorted(set(self.blockers)))
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.decision != expected_decision
            or self.next_authorization != expected_next
        ):
            raise ValueError("S2 BigQuery feasibility result changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S2 BigQuery feasibility result hash changed")
        return self


class S2BigQueryFeasibilityAudit(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-audit-v1"] = (
        "aurex-s2-bigquery-feasibility-audit-v1"
    )
    audit_id: Literal["s2-bigquery-feasibility-audit-v1"] = (
        "s2-bigquery-feasibility-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    response_artifact_count: int = Field(ge=0, le=3)
    response_artifacts_verified: Literal[True] = True
    result_reconstructed_exactly: Literal[True] = True
    query_execution_count: Literal[0] = 0
    query_result_rows_returned: Literal[0] = 0
    blockchain_row_values_read: Literal[0] = 0
    market_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: str
    next_authorization: str
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2BigQueryFeasibilityAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 BigQuery feasibility audit hash changed")
        return self


def build_hashed(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump(mode="json")
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def audit_model(instance, hash_field: str) -> bool:
    return getattr(instance, hash_field) == universe_evidence_hash(
        instance.model_dump(mode="json", exclude={hash_field})
    )
