from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s2_bigquery_feasibility import (
    S2DryRunSpec,
    S2FeasibilityBinding,
    S2MetadataAttempt,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_FEASIBILITY_V2_PASS = "PASS_S2_BIGQUERY_AUTHENTICATED_METADATA_AND_DRY_RUN"
S2_FEASIBILITY_V2_BLOCK_CLIENT = "BLOCK_S2_BIGQUERY_V2_LOCAL_CLIENT_UNAVAILABLE"
S2_FEASIBILITY_V2_BLOCK_AUTH = "BLOCK_S2_BIGQUERY_V2_ACTIVE_AUTH_UNAVAILABLE"
S2_FEASIBILITY_V2_BLOCK_PROJECT = "BLOCK_S2_BIGQUERY_V2_ACTIVE_PROJECT_UNAVAILABLE"
S2_FEASIBILITY_V2_BLOCK_BILLING = "BLOCK_S2_BIGQUERY_V2_NO_BILLING_BOUNDARY_UNVERIFIED"
S2_FEASIBILITY_V2_BLOCK_METADATA = "BLOCK_S2_BIGQUERY_V2_AUTHENTICATED_METADATA_FAILED"
S2_FEASIBILITY_V2_BLOCK_DRY_RUN = "BLOCK_S2_BIGQUERY_V2_DRY_RUN_FAILED"
S2_FEASIBILITY_V2_RETRY = "NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_V2_PASSES"
S2_FEASIBILITY_V2_NEXT = "AUTHORIZE_S2_SOURCE_PAYLOAD_PROTOCOL_ONLY"


class S2AuthenticatedMetadataEndpointSpec(BaseModel):
    target_id: Literal["DATASET", "BLOCKS_TABLE", "TRANSACTIONS_TABLE"]
    url: str
    expected_reference: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_endpoint(self) -> S2AuthenticatedMetadataEndpointSpec:
        prefix = (
            "https://bigquery.googleapis.com/bigquery/v2/projects/"
            "bigquery-public-data/datasets/crypto_bitcoin"
        )
        if not self.url.startswith(prefix):
            raise ValueError("S2 v2 metadata endpoint escaped the public dataset")
        return self


class S2BigQueryFeasibilityProtocolV2(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-protocol-v2"] = (
        "aurex-s2-bigquery-feasibility-protocol-v2"
    )
    protocol_id: Literal["s2-bigquery-feasibility-protocol-v2"] = (
        "s2-bigquery-feasibility-protocol-v2"
    )
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_AUTHENTICATED_BIGQUERY_REQUESTS"] = (
        "FROZEN_BEFORE_AUTHENTICATED_BIGQUERY_REQUESTS"
    )
    builder_contract_hash: str
    charter_evidence_hash: str
    prior_protocol_evidence_hash: str
    prior_protocol_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    source_bindings: tuple[S2FeasibilityBinding, ...] = Field(
        min_length=6,
        max_length=6,
    )
    metadata_endpoints: tuple[S2AuthenticatedMetadataEndpointSpec, ...] = Field(
        min_length=3,
        max_length=3,
    )
    dry_run_specs: tuple[S2DryRunSpec, ...] = Field(min_length=2, max_length=2)
    source_project: Literal["bigquery-public-data"] = "bigquery-public-data"
    source_dataset: Literal["crypto_bitcoin"] = "crypto_bitcoin"
    processing_location: Literal["US"] = "US"
    required_local_commands: tuple[str, str] = ("bq", "gcloud")
    required_authentication: Literal["GCLOUD_ACTIVE_USER_OAUTH"] = "GCLOUD_ACTIVE_USER_OAUTH"
    required_billing_mode: Literal["BIGQUERY_SANDBOX_WITHOUT_BILLING_ACCOUNT"] = (
        "BIGQUERY_SANDBOX_WITHOUT_BILLING_ACCOUNT"
    )
    maximum_billing_boundary_requests: Literal[1] = 1
    maximum_access_token_requests: Literal[1] = 1
    maximum_metadata_requests: Literal[3] = 3
    maximum_metadata_response_bytes_each: Literal[2_000_000] = 2_000_000
    maximum_dry_run_requests: Literal[2] = 2
    request_timeout_seconds: Literal[20] = 20
    dry_run_only: Literal[True] = True
    query_results_requested: Literal[False] = False
    query_result_rows_permitted: Literal[0] = 0
    account_identifier_persistence_permitted: Literal[False] = False
    project_identifier_persistence_permitted: Literal[False] = False
    credential_or_token_persistence_permitted: Literal[False] = False
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
    decision: Literal["AMEND_V1_WITH_AUTHENTICATED_ZERO_COST_PREFLIGHT"] = (
        "AMEND_V1_WITH_AUTHENTICATED_ZERO_COST_PREFLIGHT"
    )
    next_authorization: Literal["RUN_S2_BIGQUERY_FEASIBILITY_V2_ONCE"] = (
        "RUN_S2_BIGQUERY_FEASIBILITY_V2_ONCE"
    )
    limitations: tuple[str, ...] = Field(min_length=6)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "charter_evidence_hash",
        "prior_protocol_evidence_hash",
        "prior_protocol_audit_evidence_hash",
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S2BigQueryFeasibilityProtocolV2:
        paths = tuple(item.path for item in self.source_bindings)
        targets = tuple(item.target_id for item in self.metadata_endpoints)
        queries = tuple(item.query_id for item in self.dry_run_specs)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S2 v2 source bindings must be unique and sorted")
        if targets != ("BLOCKS_TABLE", "DATASET", "TRANSACTIONS_TABLE"):
            raise ValueError("S2 v2 metadata targets changed")
        if queries != ("CAUSAL_SIX_CONFIRMATION", "DEVELOPMENT_WEEKLY_AGGREGATE"):
            raise ValueError("S2 v2 dry-run set changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S2 v2 limitations must be unique and sorted")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S2 v2 protocol hash changed")
        return self


class S2BigQueryFeasibilityProtocolAuditV2(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-protocol-audit-v2"] = (
        "aurex-s2-bigquery-feasibility-protocol-audit-v2"
    )
    audit_id: Literal["s2-bigquery-feasibility-protocol-audit-v2"] = (
        "s2-bigquery-feasibility-protocol-audit-v2"
    )
    audited_at: datetime
    protocol_path: Literal["data/evidence/s2_bigquery_feasibility_protocol_v2.json"] = (
        "data/evidence/s2_bigquery_feasibility_protocol_v2.json"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    charter_evidence_hash: str
    prior_result_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    identifiers_observed: Literal[0] = 0
    blockchain_row_values_observed: Literal[0] = 0
    query_results_observed: Literal[0] = 0
    orders_observed: Literal[0] = 0
    decision: Literal["PASS_S2_BIGQUERY_FEASIBILITY_PROTOCOL_V2_AUDIT"] = (
        "PASS_S2_BIGQUERY_FEASIBILITY_PROTOCOL_V2_AUDIT"
    )
    next_authorization: Literal["RUN_S2_BIGQUERY_FEASIBILITY_V2_ONCE"] = (
        "RUN_S2_BIGQUERY_FEASIBILITY_V2_ONCE"
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
        "prior_result_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2BigQueryFeasibilityProtocolAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 v2 protocol audit hash changed")
        return self


class S2DryRunAttemptV2(BaseModel):
    query_id: Literal["DEVELOPMENT_WEEKLY_AGGREGATE", "CAUSAL_SIX_CONFIRMATION"]
    query_sha256: str
    requested_at: datetime
    succeeded: bool
    total_bytes_processed: int | None = Field(default=None, ge=0)
    result_rows_returned: Literal[0] = 0
    query_executed: Literal[False] = False
    error_class: Literal[
        "NONE",
        "CLIENT_ERROR",
        "AUTH_ERROR",
        "API_ERROR",
        "INVALID_RESPONSE",
        "TIMEOUT",
    ]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("query_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S2DryRunAttemptV2:
        if self.succeeded != (
            self.error_class == "NONE" and self.total_bytes_processed is not None
        ):
            raise ValueError("S2 v2 dry-run state is inconsistent")
        return self


class S2BigQueryFeasibilityResultV2(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-result-v2"] = (
        "aurex-s2-bigquery-feasibility-result-v2"
    )
    result_id: Literal["s2-bigquery-feasibility-result-v2"] = "s2-bigquery-feasibility-result-v2"
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    runner_contract_hash: str
    gcloud_available: bool
    bq_available: bool
    active_auth_configured: bool
    active_project_configured: bool
    billing_boundary_request_count: int = Field(ge=0, le=1)
    sandbox_without_billing_verified: bool
    access_token_request_count: int = Field(ge=0, le=1)
    metadata_attempts: tuple[S2MetadataAttempt, ...] = Field(max_length=3)
    dry_run_attempts: tuple[S2DryRunAttemptV2, ...] = Field(max_length=2)
    metadata_request_count: int = Field(ge=0, le=3)
    dry_run_request_count: int = Field(ge=0, le=2)
    account_identifier_persisted: Literal[False] = False
    project_identifier_persisted: Literal[False] = False
    credentials_or_tokens_persisted: Literal[False] = False
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
        "PASS_S2_BIGQUERY_AUTHENTICATED_METADATA_AND_DRY_RUN",
        "BLOCK_S2_BIGQUERY_V2_LOCAL_CLIENT_UNAVAILABLE",
        "BLOCK_S2_BIGQUERY_V2_ACTIVE_AUTH_UNAVAILABLE",
        "BLOCK_S2_BIGQUERY_V2_ACTIVE_PROJECT_UNAVAILABLE",
        "BLOCK_S2_BIGQUERY_V2_NO_BILLING_BOUNDARY_UNVERIFIED",
        "BLOCK_S2_BIGQUERY_V2_AUTHENTICATED_METADATA_FAILED",
        "BLOCK_S2_BIGQUERY_V2_DRY_RUN_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S2_SOURCE_PAYLOAD_PROTOCOL_ONLY",
        "NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_V2_PASSES",
    ]
    authorizes_numeric_query: Literal[False] = False
    authorizes_payload_acquisition: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=6)
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
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S2BigQueryFeasibilityResultV2:
        targets = tuple(item.target_id for item in self.metadata_attempts)
        query_ids = tuple(item.query_id for item in self.dry_run_attempts)
        metadata_passed = targets == (
            "BLOCKS_TABLE",
            "DATASET",
            "TRANSACTIONS_TABLE",
        ) and all(item.error_class == "NONE" for item in self.metadata_attempts)
        dry_runs_passed = query_ids == (
            "CAUSAL_SIX_CONFIRMATION",
            "DEVELOPMENT_WEEKLY_AGGREGATE",
        ) and all(item.succeeded for item in self.dry_run_attempts)
        clients_passed = self.gcloud_available and self.bq_available
        if not clients_passed:
            expected_decision = S2_FEASIBILITY_V2_BLOCK_CLIENT
        elif not self.active_auth_configured:
            expected_decision = S2_FEASIBILITY_V2_BLOCK_AUTH
        elif not self.active_project_configured:
            expected_decision = S2_FEASIBILITY_V2_BLOCK_PROJECT
        elif not self.sandbox_without_billing_verified:
            expected_decision = S2_FEASIBILITY_V2_BLOCK_BILLING
        elif not metadata_passed:
            expected_decision = S2_FEASIBILITY_V2_BLOCK_METADATA
        elif not dry_runs_passed:
            expected_decision = S2_FEASIBILITY_V2_BLOCK_DRY_RUN
        else:
            expected_decision = S2_FEASIBILITY_V2_PASS
        expected_next = (
            S2_FEASIBILITY_V2_NEXT
            if expected_decision == S2_FEASIBILITY_V2_PASS
            else S2_FEASIBILITY_V2_RETRY
        )
        prerequisite_order_valid = (
            (not self.active_auth_configured or self.gcloud_available)
            and (not self.active_project_configured or self.active_auth_configured)
            and (self.billing_boundary_request_count == 0 or self.active_project_configured)
            and (
                not self.sandbox_without_billing_verified
                or self.billing_boundary_request_count == 1
            )
            and (self.access_token_request_count == 0 or self.sandbox_without_billing_verified)
            and (not self.metadata_attempts or self.access_token_request_count == 1)
            and (not self.dry_run_attempts or metadata_passed)
        )
        if (
            not prerequisite_order_valid
            or targets != tuple(sorted(set(targets)))
            or query_ids != tuple(sorted(set(query_ids)))
            or self.metadata_request_count != len(self.metadata_attempts)
            or self.dry_run_request_count != len(self.dry_run_attempts)
            or self.blockers != tuple(sorted(set(self.blockers)))
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.decision != expected_decision
            or self.next_authorization != expected_next
        ):
            raise ValueError("S2 BigQuery feasibility v2 result changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S2 BigQuery feasibility v2 result hash changed")
        return self


class S2BigQueryFeasibilityAuditV2(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-feasibility-audit-v2"] = (
        "aurex-s2-bigquery-feasibility-audit-v2"
    )
    audit_id: Literal["s2-bigquery-feasibility-audit-v2"] = "s2-bigquery-feasibility-audit-v2"
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    response_artifact_count: int = Field(ge=0, le=3)
    response_artifacts_verified: Literal[True] = True
    result_reconstructed_exactly: Literal[True] = True
    identifiers_observed_in_artifacts: Literal[0] = 0
    credentials_or_tokens_observed_in_artifacts: Literal[0] = 0
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
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2BigQueryFeasibilityAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 v2 feasibility audit hash changed")
        return self
