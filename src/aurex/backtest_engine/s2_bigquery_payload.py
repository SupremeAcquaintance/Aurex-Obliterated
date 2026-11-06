from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s2_bigquery_feasibility import S2FeasibilityBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_PAYLOAD_PASS = "PASS_S2_DEVELOPMENT_PAYLOAD_ACQUIRED"
S2_PAYLOAD_BLOCK_CLIENT = "BLOCK_S2_PAYLOAD_LOCAL_CLIENT_UNAVAILABLE"
S2_PAYLOAD_BLOCK_AUTH = "BLOCK_S2_PAYLOAD_ACTIVE_AUTH_UNAVAILABLE"
S2_PAYLOAD_BLOCK_PROJECT = "BLOCK_S2_PAYLOAD_ACTIVE_PROJECT_UNAVAILABLE"
S2_PAYLOAD_BLOCK_BILLING = "BLOCK_S2_PAYLOAD_NO_BILLING_BOUNDARY_UNVERIFIED"
S2_PAYLOAD_BLOCK_TOKEN = "BLOCK_S2_PAYLOAD_ACCESS_TOKEN_UNAVAILABLE"
S2_PAYLOAD_BLOCK_QUERY = "BLOCK_S2_PAYLOAD_QUERY_FAILED"
S2_PAYLOAD_BLOCK_VALIDATION = "BLOCK_S2_PAYLOAD_VALIDATION_FAILED"
S2_PAYLOAD_RETRY = "NONE_UNTIL_SEPARATELY_FROZEN_S2_PAYLOAD_AMENDMENT"
S2_PAYLOAD_NEXT = "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"


class S2PayloadQuerySpec(BaseModel):
    query_id: Literal["S2_DEVELOPMENT_CONFIRMED_WEEKLY_PAYLOAD"] = (
        "S2_DEVELOPMENT_CONFIRMED_WEEKLY_PAYLOAD"
    )
    google_sql: str
    query_sha256: str
    expected_field_names: tuple[
        Literal["week_start"],
        Literal["decision_cutoff_at"],
        Literal["earliest_execution_at"],
        Literal["confirmed_block_count"],
        Literal["confirmed_non_coinbase_transaction_count"],
        Literal["confirmed_fee_satoshis"],
        Literal["latest_sixth_confirmation_at"],
    ] = (
        "week_start",
        "decision_cutoff_at",
        "earliest_execution_at",
        "confirmed_block_count",
        "confirmed_non_coinbase_transaction_count",
        "confirmed_fee_satoshis",
        "latest_sixth_confirmation_at",
    )
    expected_field_types: tuple[
        Literal["STRING"],
        Literal["STRING"],
        Literal["STRING"],
        Literal["INTEGER"],
        Literal["INTEGER"],
        Literal["INTEGER"],
        Literal["STRING"],
    ] = (
        "STRING",
        "STRING",
        "STRING",
        "INTEGER",
        "INTEGER",
        "INTEGER",
        "STRING",
    )
    first_week_start: date = date(2017, 8, 19)
    last_week_start: date = date(2022, 12, 24)
    expected_row_count: Literal[280] = 280
    maximum_bytes_billed: Literal[60_000_000_000] = 60_000_000_000

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("query_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_query(self) -> S2PayloadQuerySpec:
        if self.query_sha256 != universe_evidence_hash(self.google_sql):
            raise ValueError("S2 payload query hash changed")
        if (
            self.first_week_start != date(2017, 8, 19)
            or self.last_week_start != date(2022, 12, 24)
            or (self.last_week_start - self.first_week_start).days // 7 + 1 != 280
        ):
            raise ValueError("S2 payload weekly window changed")
        return self


class S2BigQueryPayloadProtocol(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-payload-protocol-v1"] = (
        "aurex-s2-bigquery-payload-protocol-v1"
    )
    protocol_id: Literal["s2-bigquery-payload-protocol-v1"] = "s2-bigquery-payload-protocol-v1"
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_S2_NUMERIC_QUERY"] = "FROZEN_BEFORE_S2_NUMERIC_QUERY"
    builder_contract_hash: str
    charter_evidence_hash: str
    feasibility_protocol_evidence_hash: str
    feasibility_protocol_audit_evidence_hash: str
    feasibility_result_evidence_hash: str
    feasibility_result_audit_evidence_hash: str
    source_bindings: tuple[S2FeasibilityBinding, ...] = Field(min_length=8, max_length=8)
    query_spec: S2PayloadQuerySpec
    query_endpoint_template: Literal[
        "https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries"
    ] = "https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries"
    query_results_endpoint_template: Literal[
        "https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries/{job_id}"
    ] = "https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries/{job_id}"
    source_project: Literal["bigquery-public-data"] = "bigquery-public-data"
    source_dataset: Literal["crypto_bitcoin"] = "crypto_bitcoin"
    processing_location: Literal["US"] = "US"
    required_local_commands: tuple[Literal["gcloud"]] = ("gcloud",)
    required_authentication: Literal["GCLOUD_ACTIVE_USER_OAUTH"] = "GCLOUD_ACTIVE_USER_OAUTH"
    required_billing_mode: Literal["BIGQUERY_SANDBOX_WITHOUT_BILLING_ACCOUNT"] = (
        "BIGQUERY_SANDBOX_WITHOUT_BILLING_ACCOUNT"
    )
    one_time_market_data_budget_usd: Literal["0"] = "0"
    maximum_billing_boundary_requests: Literal[1] = 1
    maximum_access_token_requests: Literal[1] = 1
    maximum_query_submissions: Literal[1] = 1
    maximum_query_result_polls: Literal[30] = 30
    maximum_query_result_pages: Literal[1] = 1
    maximum_response_bytes_each: Literal[2_000_000] = 2_000_000
    request_timeout_seconds: Literal[30] = 30
    query_timeout_milliseconds: Literal[20_000] = 20_000
    poll_interval_seconds: Literal[2] = 2
    page_size: Literal[1000] = 1000
    use_legacy_sql: Literal[False] = False
    use_query_cache: Literal[False] = False
    raw_response_persistence_permitted: Literal[False] = False
    account_identifier_persistence_permitted: Literal[False] = False
    project_identifier_persistence_permitted: Literal[False] = False
    credential_or_token_persistence_permitted: Literal[False] = False
    development_blockchain_payload_permitted: Literal[True] = True
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    signals_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    payload_path: Literal["data/evidence/s2_development_weekly_payload_v1.json"] = (
        "data/evidence/s2_development_weekly_payload_v1.json"
    )
    decision: Literal["FREEZE_S2_DEVELOPMENT_PAYLOAD_ACQUISITION"] = (
        "FREEZE_S2_DEVELOPMENT_PAYLOAD_ACQUISITION"
    )
    next_authorization: Literal["RUN_S2_DEVELOPMENT_PAYLOAD_ONCE"] = (
        "RUN_S2_DEVELOPMENT_PAYLOAD_ONCE"
    )
    limitations: tuple[str, ...] = Field(min_length=8)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "charter_evidence_hash",
        "feasibility_protocol_evidence_hash",
        "feasibility_protocol_audit_evidence_hash",
        "feasibility_result_evidence_hash",
        "feasibility_result_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S2BigQueryPayloadProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S2 payload source bindings must be unique and sorted")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S2 payload limitations must be unique and sorted")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S2 payload protocol hash changed")
        return self


class S2BigQueryPayloadProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-payload-protocol-audit-v1"] = (
        "aurex-s2-bigquery-payload-protocol-audit-v1"
    )
    audit_id: Literal["s2-bigquery-payload-protocol-audit-v1"] = (
        "s2-bigquery-payload-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal["data/evidence/s2_bigquery_payload_protocol_v1.json"] = (
        "data/evidence/s2_bigquery_payload_protocol_v1.json"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    feasibility_result_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    identifiers_observed: Literal[0] = 0
    blockchain_row_values_observed: Literal[0] = 0
    query_results_observed: Literal[0] = 0
    orders_observed: Literal[0] = 0
    decision: Literal["PASS_S2_BIGQUERY_PAYLOAD_PROTOCOL_AUDIT"] = (
        "PASS_S2_BIGQUERY_PAYLOAD_PROTOCOL_AUDIT"
    )
    next_authorization: Literal["RUN_S2_DEVELOPMENT_PAYLOAD_ONCE"] = (
        "RUN_S2_DEVELOPMENT_PAYLOAD_ONCE"
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
        "feasibility_result_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2BigQueryPayloadProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 payload protocol audit hash changed")
        return self


class S2DevelopmentWeeklyRow(BaseModel):
    week_start: date
    decision_cutoff_at: date
    earliest_execution_at: date
    confirmed_block_count: int = Field(gt=0)
    confirmed_non_coinbase_transaction_count: int = Field(gt=0)
    confirmed_fee_satoshis: int = Field(ge=0)
    latest_sixth_confirmation_at: datetime

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("latest_sixth_confirmation_at")
    @classmethod
    def normalize_confirmation_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_row(self) -> S2DevelopmentWeeklyRow:
        if (
            self.week_start.weekday() != 5
            or self.decision_cutoff_at != self.week_start + timedelta(days=7)
            or self.earliest_execution_at != self.week_start + timedelta(days=9)
            or self.latest_sixth_confirmation_at.date() >= self.decision_cutoff_at
        ):
            raise ValueError("S2 development weekly row timing changed")
        return self


class S2DevelopmentWeeklyPayload(BaseModel):
    schema_version: Literal["aurex-s2-development-weekly-payload-v1"] = (
        "aurex-s2-development-weekly-payload-v1"
    )
    payload_id: Literal["s2-development-weekly-payload-v1"] = "s2-development-weekly-payload-v1"
    acquired_at: datetime
    protocol_evidence_hash: str
    query_sha256: str
    row_count: Literal[280] = 280
    rows: tuple[S2DevelopmentWeeklyRow, ...] = Field(min_length=280, max_length=280)
    account_identifier_persisted: Literal[False] = False
    project_identifier_persisted: Literal[False] = False
    credential_or_token_persisted: Literal[False] = False
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    payload_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("acquired_at")
    @classmethod
    def normalize_acquired_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("protocol_evidence_hash", "query_sha256", "payload_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_payload(self) -> S2DevelopmentWeeklyPayload:
        starts = tuple(row.week_start for row in self.rows)
        expected_starts = tuple(date(2017, 8, 19) + timedelta(days=7 * i) for i in range(280))
        if starts != expected_starts or self.row_count != len(self.rows):
            raise ValueError("S2 development payload weekly coverage changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"payload_evidence_hash"})
        )
        if self.payload_evidence_hash != expected_hash:
            raise ValueError("S2 development payload hash changed")
        return self


class S2BigQueryPayloadResult(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-payload-result-v1"] = (
        "aurex-s2-bigquery-payload-result-v1"
    )
    result_id: Literal["s2-bigquery-payload-result-v1"] = "s2-bigquery-payload-result-v1"
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    feasibility_result_evidence_hash: str
    feasibility_result_audit_evidence_hash: str
    runner_contract_hash: str
    gcloud_available: bool
    active_auth_configured: bool
    active_project_configured: bool
    billing_boundary_request_count: int = Field(ge=0, le=1)
    sandbox_without_billing_verified: bool
    access_token_request_count: int = Field(ge=0, le=1)
    access_token_available: bool
    query_submission_count: int = Field(ge=0, le=1)
    query_result_poll_count: int = Field(ge=0, le=30)
    query_result_page_count: int = Field(ge=0, le=1)
    query_completed: bool
    total_bytes_processed: int | None = Field(default=None, ge=0, le=60_000_000_000)
    query_result_rows_returned: int = Field(ge=0, le=280)
    blockchain_row_values_read: int = Field(ge=0, le=280)
    raw_response_bodies_persisted: Literal[0] = 0
    account_identifier_persisted: Literal[False] = False
    project_identifier_persisted: Literal[False] = False
    credentials_or_tokens_persisted: Literal[False] = False
    payload_path: str | None = None
    payload_file_sha256: str | None = None
    payload_evidence_hash: str | None = None
    payload_byte_count: int = Field(ge=0)
    market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_generated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    blockers: tuple[str, ...]
    decision: Literal[
        "PASS_S2_DEVELOPMENT_PAYLOAD_ACQUIRED",
        "BLOCK_S2_PAYLOAD_LOCAL_CLIENT_UNAVAILABLE",
        "BLOCK_S2_PAYLOAD_ACTIVE_AUTH_UNAVAILABLE",
        "BLOCK_S2_PAYLOAD_ACTIVE_PROJECT_UNAVAILABLE",
        "BLOCK_S2_PAYLOAD_NO_BILLING_BOUNDARY_UNVERIFIED",
        "BLOCK_S2_PAYLOAD_ACCESS_TOKEN_UNAVAILABLE",
        "BLOCK_S2_PAYLOAD_QUERY_FAILED",
        "BLOCK_S2_PAYLOAD_VALIDATION_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY",
        "NONE_UNTIL_SEPARATELY_FROZEN_S2_PAYLOAD_AMENDMENT",
    ]
    authorizes_measurement_protocol: bool
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=8)
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
        "feasibility_result_evidence_hash",
        "feasibility_result_audit_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("payload_file_sha256", "payload_evidence_hash")
    @classmethod
    def normalize_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S2BigQueryPayloadResult:
        payload_present = (
            self.payload_path == "data/evidence/s2_development_weekly_payload_v1.json"
            and self.payload_file_sha256 is not None
            and self.payload_evidence_hash is not None
            and self.payload_byte_count > 0
        )
        passed = (
            self.query_completed
            and self.total_bytes_processed is not None
            and self.query_submission_count == 1
            and self.query_result_page_count == 1
            and self.query_result_rows_returned == 280
            and self.blockchain_row_values_read == 280
            and payload_present
        )
        if not self.gcloud_available:
            expected_decision = S2_PAYLOAD_BLOCK_CLIENT
        elif not self.active_auth_configured:
            expected_decision = S2_PAYLOAD_BLOCK_AUTH
        elif not self.active_project_configured:
            expected_decision = S2_PAYLOAD_BLOCK_PROJECT
        elif not self.sandbox_without_billing_verified:
            expected_decision = S2_PAYLOAD_BLOCK_BILLING
        elif self.access_token_request_count != 1 or not self.access_token_available:
            expected_decision = S2_PAYLOAD_BLOCK_TOKEN
        elif self.query_submission_count != 1 or not self.query_completed:
            expected_decision = S2_PAYLOAD_BLOCK_QUERY
        elif not passed:
            expected_decision = S2_PAYLOAD_BLOCK_VALIDATION
        else:
            expected_decision = S2_PAYLOAD_PASS
        expected_next = (
            S2_PAYLOAD_NEXT if expected_decision == S2_PAYLOAD_PASS else S2_PAYLOAD_RETRY
        )
        prerequisites_valid = (
            (not self.active_auth_configured or self.gcloud_available)
            and (not self.active_project_configured or self.active_auth_configured)
            and (self.billing_boundary_request_count == 0 or self.active_project_configured)
            and (
                not self.sandbox_without_billing_verified
                or self.billing_boundary_request_count == 1
            )
            and (self.access_token_request_count == 0 or self.sandbox_without_billing_verified)
            and (not self.access_token_available or self.access_token_request_count == 1)
            and (self.query_submission_count == 0 or self.access_token_available)
        )
        if (
            not prerequisites_valid
            or self.blockers != tuple(sorted(set(self.blockers)))
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.decision != expected_decision
            or self.next_authorization != expected_next
            or self.authorizes_measurement_protocol != passed
        ):
            raise ValueError("S2 BigQuery payload result changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("S2 BigQuery payload result hash changed")
        return self


class S2BigQueryPayloadAudit(BaseModel):
    schema_version: Literal["aurex-s2-bigquery-payload-audit-v1"] = (
        "aurex-s2-bigquery-payload-audit-v1"
    )
    audit_id: Literal["s2-bigquery-payload-audit-v1"] = "s2-bigquery-payload-audit-v1"
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    feasibility_result_evidence_hash: str
    feasibility_result_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    payload_file_sha256: str
    payload_evidence_hash: str
    payload_byte_count: int = Field(gt=0)
    payload_row_count: Literal[280] = 280
    source_artifacts_verified: Literal[True] = True
    payload_reconstructed_exactly: Literal[True] = True
    result_reconstructed_exactly: Literal[True] = True
    identifiers_observed_in_artifacts: Literal[0] = 0
    credentials_or_tokens_observed_in_artifacts: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S2_DEVELOPMENT_PAYLOAD_ACQUIRED"] = S2_PAYLOAD_PASS
    next_authorization: Literal["AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"] = (
        S2_PAYLOAD_NEXT
    )
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
        "feasibility_result_evidence_hash",
        "feasibility_result_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "payload_file_sha256",
        "payload_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2BigQueryPayloadAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 payload audit hash changed")
        return self
