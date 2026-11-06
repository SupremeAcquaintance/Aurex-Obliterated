from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S4_FEASIBILITY_PROTOCOL_DECISION = (
    "FREEZE_S4_ETP_METADATA_AND_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL"
)
S4_FEASIBILITY_RUN_AUTHORIZATION = "RUN_S4_ETP_SOURCE_FEASIBILITY_ONCE"
S4_FEASIBILITY_PASS = "PASS_S4_ETP_POINT_IN_TIME_SOURCE_FEASIBILITY"
S4_FEASIBILITY_STOP = "STOP_S4_ETP_SOURCE_FEASIBILITY_FAILED_RETIRE_S4"
S4_FEASIBILITY_NEXT = "AUTHORIZE_S4_ETP_NUMERIC_PAYLOAD_PROTOCOL_ONLY"
S4_FEASIBILITY_NONE = "NONE_S4_ETP_SOURCE_FEASIBILITY_FAILED_RETIRE_S4"

S4_STATIC_ENDPOINT_IDS = (
    "SEC_API_DOCUMENTATION",
    "SEC_EDGAR_ACCESS_DOCUMENTATION",
    "SEC_FUND_TICKER_CATALOG",
    "SEC_PUBLIC_REUSE_POLICY",
    "SEC_TICKER_EXCHANGE_CATALOG",
)

S4_FEASIBILITY_GATE_IDS = (
    "ALL_REQUEST_ATTEMPTS_DURABLY_RECORDED",
    "OFFICIAL_SEC_AUTHORITY_ONLY",
    "COMPLETE_SPOT_BITCOIN_ETP_UNIVERSE_RECONSTRUCTABLE",
    "FUND_LIFECYCLE_AND_TICKER_HISTORY_RECONSTRUCTABLE",
    "OFFICIAL_ISSUER_DATA_ENDPOINT_CATALOG_COMPLETE",
    "DAILY_SHARES_OUTSTANDING_HISTORY_DESCRIPTOR_COMPLETE",
    "DAILY_BITCOIN_HOLDINGS_HISTORY_DESCRIPTOR_COMPLETE",
    "ACTUAL_PUBLICATION_TIMING_RECONSTRUCTABLE",
    "PER_FUND_CASH_IN_KIND_REGIME_DATES_RECONSTRUCTABLE",
    "FEES_SPLITS_MERGERS_AND_NON_CREATION_CHANGES_RECONSTRUCTABLE",
    "ZERO_DOLLAR_PUBLIC_ACCESS",
    "REUSE_RIGHTS_EXPLICIT",
    "ZERO_ETP_NUMERIC_VALUES_ACCESSED",
    "ZERO_BTC_MARKET_VALUES_OR_OUTCOMES_ACCESSED",
    "ZERO_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
)


class S4FeasibilityBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S4MetadataEndpointSpec(BaseModel):
    endpoint_id: Literal[
        "SEC_API_DOCUMENTATION",
        "SEC_EDGAR_ACCESS_DOCUMENTATION",
        "SEC_FUND_TICKER_CATALOG",
        "SEC_PUBLIC_REUSE_POLICY",
        "SEC_TICKER_EXCHANGE_CATALOG",
    ]
    url: str = Field(min_length=20)
    response_kind: Literal["TEXT_DOCUMENTATION", "JSON_IDENTITY_CATALOG"]
    required_markers: tuple[str, ...] = Field(min_length=2)
    permitted_json_keys: tuple[str, ...] = ()
    maximum_response_bytes: int = Field(ge=250_000, le=25_000_000)
    permits_identity_metadata: Literal[True] = True
    permits_cik_ticker_exchange_values: bool
    permits_etp_numeric_values: Literal[False] = False
    permits_btc_market_values: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_endpoint(self) -> S4MetadataEndpointSpec:
        if not self.url.startswith("https://www.sec.gov/"):
            raise ValueError("S4 static metadata endpoint escaped SEC authority")
        if self.endpoint_id in {
            "SEC_FUND_TICKER_CATALOG",
            "SEC_TICKER_EXCHANGE_CATALOG",
        }:
            if self.response_kind != "JSON_IDENTITY_CATALOG":
                raise ValueError("S4 SEC identity catalogs must remain JSON")
            if not self.permits_cik_ticker_exchange_values:
                raise ValueError("S4 SEC identity catalogs require identity fields")
        elif self.permits_cik_ticker_exchange_values:
            raise ValueError("S4 documentation endpoints cannot expose identity rows")
        if self.required_markers != tuple(sorted(set(self.required_markers))):
            raise ValueError("S4 endpoint markers must be unique and sorted")
        if self.permitted_json_keys != tuple(sorted(set(self.permitted_json_keys))):
            raise ValueError("S4 endpoint JSON keys must be unique and sorted")
        return self


class S4EtpSourceFeasibilityProtocol(BaseModel):
    schema_version: Literal[
        "aurex-s4-etp-source-feasibility-protocol-v1"
    ] = "aurex-s4-etp-source-feasibility-protocol-v1"
    protocol_id: Literal["s4-etp-source-feasibility-protocol-v1"] = (
        "s4-etp-source-feasibility-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_S4_METADATA_REQUESTS"] = (
        "FROZEN_BEFORE_S4_METADATA_REQUESTS"
    )
    builder_contract_hash: str
    charter_evidence_hash: str
    source_bindings: tuple[S4FeasibilityBinding, ...] = Field(
        min_length=4, max_length=4
    )
    static_metadata_endpoints: tuple[S4MetadataEndpointSpec, ...] = Field(
        min_length=5, max_length=5
    )
    sec_submissions_url_template: Literal[
        "https://data.sec.gov/submissions/CIK{cik_10_digit}.json"
    ] = "https://data.sec.gov/submissions/CIK{cik_10_digit}.json"
    sec_submissions_permitted_keys: tuple[str, ...] = (
        "acceptanceDateTime",
        "accessionNumber",
        "cik",
        "exchanges",
        "files",
        "filingDate",
        "form",
        "formerNames",
        "name",
        "primaryDocDescription",
        "primaryDocument",
        "reportDate",
        "tickers",
        "website",
    )
    maximum_static_requests: Literal[5] = 5
    maximum_dynamic_submission_requests: Literal[32] = 32
    maximum_total_requests: Literal[37] = 37
    maximum_response_bytes_each: Literal[25_000_000] = 25_000_000
    request_timeout_seconds: Literal[45] = 45
    maximum_run_count: Literal[1] = 1
    sec_user_agent_environment_variable: Literal["AUREX_SEC_USER_AGENT"] = (
        "AUREX_SEC_USER_AGENT"
    )
    sec_user_agent_must_identify_operator_and_contact: Literal[True] = True
    run_blocked_without_sec_user_agent: Literal[True] = True
    required_gate_ids: tuple[str, ...] = S4_FEASIBILITY_GATE_IDS
    result_artifact_required_on_every_exit: Literal[True] = True
    attempt_record_required_for_every_planned_request: Literal[True] = True
    partial_response_artifacts_must_be_preserved: Literal[True] = True
    all_or_nothing_response_persistence_forbidden: Literal[True] = True
    unknown_attempt_or_success_counts_forbidden: Literal[True] = True
    rerun_after_result_forbidden: Literal[True] = True
    raw_sec_documentation_permitted: Literal[True] = True
    raw_sec_identity_catalogs_permitted: Literal[True] = True
    raw_sec_submission_metadata_permitted: Literal[True] = True
    issuer_page_response_bodies_permitted: Literal[False] = False
    issuer_head_requests_permitted: Literal[False] = False
    sec_filing_document_bodies_permitted: Literal[False] = False
    xbrl_fact_endpoints_permitted: Literal[False] = False
    etp_numeric_values_permitted: Literal[False] = False
    btc_market_values_permitted: Literal[False] = False
    payload_acquisition_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    historical_screen_permitted: Literal[False] = False
    validation_permitted: Literal[False] = False
    holdout_permitted: Literal[False] = False
    pine_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    pre_freeze_incidental_current_numeric_context_observed: Literal[True] = True
    incidental_context_categories: tuple[str, ...] = (
        "CURRENT_AS_OF_DATE",
        "CURRENT_BENCHMARK_LEVEL",
        "CURRENT_BITCOIN_QUANTITY",
        "CURRENT_HOLDING_COUNT",
        "CURRENT_MARKET_VALUE",
        "CURRENT_PORTFOLIO_WEIGHT",
    )
    incidental_exact_numeric_values_persisted_by_aurex: Literal[False] = False
    incidental_context_is_outcome_aware_nonqualifying: Literal[True] = True
    decision: Literal[
        "FREEZE_S4_ETP_METADATA_AND_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL"
    ] = S4_FEASIBILITY_PROTOCOL_DECISION
    next_authorization: Literal["RUN_S4_ETP_SOURCE_FEASIBILITY_ONCE"] = (
        S4_FEASIBILITY_RUN_AUTHORIZATION
    )
    limitations: tuple[str, ...] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
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
    def validate_protocol(self) -> S4EtpSourceFeasibilityProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        endpoint_ids = tuple(item.endpoint_id for item in self.static_metadata_endpoints)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S4 feasibility bindings must be unique and sorted")
        if endpoint_ids != S4_STATIC_ENDPOINT_IDS:
            raise ValueError("S4 feasibility endpoint set changed")
        if self.required_gate_ids != S4_FEASIBILITY_GATE_IDS:
            raise ValueError("S4 feasibility gates changed")
        if self.sec_submissions_permitted_keys != tuple(
            sorted(set(self.sec_submissions_permitted_keys))
        ):
            raise ValueError("S4 SEC submissions keys changed")
        if self.incidental_context_categories != tuple(
            sorted(set(self.incidental_context_categories))
        ):
            raise ValueError("S4 incidental context disclosure changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S4 feasibility limitations must be unique and sorted")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S4 feasibility protocol hash changed")
        return self


class S4EtpSourceFeasibilityProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-s4-etp-source-feasibility-protocol-audit-v1"
    ] = "aurex-s4-etp-source-feasibility-protocol-audit-v1"
    audit_id: Literal["s4-etp-source-feasibility-protocol-audit-v1"] = (
        "s4-etp-source-feasibility-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal[
        "data/evidence/s4_etp_source_feasibility_protocol_v1.json"
    ] = "data/evidence/s4_etp_source_feasibility_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    etp_numeric_values_observed_by_protocol: Literal[0] = 0
    btc_market_values_observed_by_protocol: Literal[0] = 0
    parameters_observed: Literal[0] = 0
    returns_observed: Literal[0] = 0
    orders_observed: Literal[0] = 0
    durable_every_exit_result_contract_verified: Literal[True] = True
    exact_attempt_count_contract_verified: Literal[True] = True
    incidental_context_disclosure_verified: Literal[True] = True
    decision: Literal["PASS_S4_ETP_SOURCE_FEASIBILITY_PROTOCOL_AUDIT"] = (
        "PASS_S4_ETP_SOURCE_FEASIBILITY_PROTOCOL_AUDIT"
    )
    next_authorization: Literal["RUN_S4_ETP_SOURCE_FEASIBILITY_ONCE"] = (
        S4_FEASIBILITY_RUN_AUTHORIZATION
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
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
    def validate_audit(self) -> S4EtpSourceFeasibilityProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S4 feasibility protocol audit hash changed")
        return self


class S4MetadataAttempt(BaseModel):
    sequence: int = Field(ge=1, le=37)
    request_id: str = Field(min_length=1)
    endpoint_id: str = Field(min_length=1)
    requested_at: datetime
    completed_at: datetime
    http_status: int = Field(ge=0, le=599)
    response_bytes: int = Field(ge=0, le=25_000_000)
    response_sha256: str | None
    response_path: str | None
    error_class: Literal[
        "NONE",
        "HTTP_ERROR",
        "NETWORK_ERROR",
        "RESPONSE_TOO_LARGE",
        "INVALID_METADATA",
        "PROTOCOL_BLOCKED",
    ]
    request_succeeded: bool
    etp_identity_rows_parsed: int = Field(ge=0)
    etp_numeric_values_read: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("requested_at", "completed_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("response_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S4MetadataAttempt:
        complete = (
            self.http_status == 200
            and self.response_bytes > 0
            and self.response_sha256 is not None
            and self.response_path is not None
            and self.error_class == "NONE"
        )
        if self.request_succeeded != complete:
            raise ValueError("S4 metadata attempt success state changed")
        if self.completed_at < self.requested_at:
            raise ValueError("S4 metadata attempt completed before request")
        return self


class S4FeasibilityGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    detail: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S4EtpSourceFeasibilityResult(BaseModel):
    schema_version: Literal[
        "aurex-s4-etp-source-feasibility-result-v1"
    ] = "aurex-s4-etp-source-feasibility-result-v1"
    result_id: Literal["s4-etp-source-feasibility-result-v1"] = (
        "s4-etp-source-feasibility-result-v1"
    )
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    metadata_attempts: tuple[S4MetadataAttempt, ...] = Field(
        min_length=5, max_length=37
    )
    gate_results: tuple[S4FeasibilityGateResult, ...] = Field(
        min_length=15, max_length=15
    )
    planned_request_count: int = Field(ge=5, le=37)
    attempted_request_count: int = Field(ge=5, le=37)
    successful_request_count: int = Field(ge=0, le=37)
    failed_request_count: int = Field(ge=0, le=37)
    persisted_response_artifact_count: int = Field(ge=0, le=37)
    passed_gate_count: int = Field(ge=0, le=15)
    failed_gate_count: int = Field(ge=0, le=15)
    static_endpoint_ids_attempted: tuple[str, ...] = Field(min_length=5, max_length=5)
    dynamic_submission_request_count: int = Field(ge=0, le=32)
    universe_candidate_count: int = Field(ge=0)
    classified_spot_bitcoin_etp_count: int = Field(ge=0)
    complete_universe_reconstructable: bool
    lifecycle_history_reconstructable: bool
    issuer_data_endpoint_catalog_complete: bool
    daily_shares_history_descriptor_complete: bool
    daily_bitcoin_history_descriptor_complete: bool
    actual_publication_timing_reconstructable: bool
    per_fund_regime_dates_reconstructable: bool
    non_creation_change_reconciliation_reconstructable: bool
    zero_dollar_public_access_observed: bool
    reuse_rights_explicit: bool
    etp_identity_rows_parsed: int = Field(ge=0)
    etp_time_series_rows_parsed: Literal[0] = 0
    etp_numeric_values_read: Literal[0] = 0
    etp_numeric_payloads_acquired: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    blockers: tuple[str, ...]
    decision: Literal[
        "PASS_S4_ETP_POINT_IN_TIME_SOURCE_FEASIBILITY",
        "STOP_S4_ETP_SOURCE_FEASIBILITY_FAILED_RETIRE_S4",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S4_ETP_NUMERIC_PAYLOAD_PROTOCOL_ONLY",
        "NONE_S4_ETP_SOURCE_FEASIBILITY_FAILED_RETIRE_S4",
    ]
    authorizes_etp_numeric_payload: Literal[False] = False
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_pine: Literal[False] = False
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
    def normalize_time(cls, value: datetime) -> datetime:
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
    def validate_result(self) -> S4EtpSourceFeasibilityResult:
        attempts = self.metadata_attempts
        sequences = tuple(item.sequence for item in attempts)
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        gate_statuses = tuple(item.status for item in self.gate_results)
        successes = sum(item.request_succeeded for item in attempts)
        artifacts = sum(item.response_path is not None for item in attempts)
        if sequences != tuple(range(1, len(attempts) + 1)):
            raise ValueError("S4 attempt sequence must be complete and contiguous")
        if self.static_endpoint_ids_attempted != S4_STATIC_ENDPOINT_IDS:
            raise ValueError("S4 static endpoint attempt set changed")
        if tuple(item.endpoint_id for item in attempts[:5]) != S4_STATIC_ENDPOINT_IDS:
            raise ValueError("S4 static attempts must be recorded first and in order")
        if any(
            item.endpoint_id != "SEC_SUBMISSIONS_CIK" for item in attempts[5:]
        ):
            raise ValueError("S4 dynamic attempts escaped SEC submissions metadata")
        if gate_ids != S4_FEASIBILITY_GATE_IDS:
            raise ValueError("S4 result gate set changed")
        if (
            self.planned_request_count != len(attempts)
            or self.attempted_request_count != len(attempts)
            or self.successful_request_count != successes
            or self.failed_request_count != len(attempts) - successes
            or self.persisted_response_artifact_count != artifacts
            or self.dynamic_submission_request_count != len(attempts) - 5
            or self.dynamic_submission_request_count
            != min(self.universe_candidate_count, 32)
            or self.passed_gate_count != gate_statuses.count("PASS")
            or self.failed_gate_count != gate_statuses.count("FAIL")
            or self.etp_identity_rows_parsed
            != sum(item.etp_identity_rows_parsed for item in attempts)
        ):
            raise ValueError("S4 result exact attempt or gate counts changed")
        if self.classified_spot_bitcoin_etp_count > self.universe_candidate_count:
            raise ValueError("S4 classified universe exceeds candidate universe")
        state_gates = {
            "COMPLETE_SPOT_BITCOIN_ETP_UNIVERSE_RECONSTRUCTABLE": (
                self.complete_universe_reconstructable
            ),
            "FUND_LIFECYCLE_AND_TICKER_HISTORY_RECONSTRUCTABLE": (
                self.lifecycle_history_reconstructable
            ),
            "OFFICIAL_ISSUER_DATA_ENDPOINT_CATALOG_COMPLETE": (
                self.issuer_data_endpoint_catalog_complete
            ),
            "DAILY_SHARES_OUTSTANDING_HISTORY_DESCRIPTOR_COMPLETE": (
                self.daily_shares_history_descriptor_complete
            ),
            "DAILY_BITCOIN_HOLDINGS_HISTORY_DESCRIPTOR_COMPLETE": (
                self.daily_bitcoin_history_descriptor_complete
            ),
            "ACTUAL_PUBLICATION_TIMING_RECONSTRUCTABLE": (
                self.actual_publication_timing_reconstructable
            ),
            "PER_FUND_CASH_IN_KIND_REGIME_DATES_RECONSTRUCTABLE": (
                self.per_fund_regime_dates_reconstructable
            ),
            "FEES_SPLITS_MERGERS_AND_NON_CREATION_CHANGES_RECONSTRUCTABLE": (
                self.non_creation_change_reconciliation_reconstructable
            ),
            "ZERO_DOLLAR_PUBLIC_ACCESS": self.zero_dollar_public_access_observed,
            "REUSE_RIGHTS_EXPLICIT": self.reuse_rights_explicit,
        }
        actual = {item.gate_id: item.status for item in self.gate_results}
        always_pass = (
            "ALL_REQUEST_ATTEMPTS_DURABLY_RECORDED",
            "OFFICIAL_SEC_AUTHORITY_ONLY",
            "ZERO_ETP_NUMERIC_VALUES_ACCESSED",
            "ZERO_BTC_MARKET_VALUES_OR_OUTCOMES_ACCESSED",
            "ZERO_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
        )
        if any(actual[gate_id] != "PASS" for gate_id in always_pass):
            raise ValueError("S4 durable-record or zero-access gate changed")
        if any(
            (actual[gate_id] == "PASS") != passed
            for gate_id, passed in state_gates.items()
        ):
            raise ValueError("S4 source state and gate decisions diverged")
        expected_decision = (
            S4_FEASIBILITY_PASS if self.failed_gate_count == 0 else S4_FEASIBILITY_STOP
        )
        expected_next = (
            S4_FEASIBILITY_NEXT
            if expected_decision == S4_FEASIBILITY_PASS
            else S4_FEASIBILITY_NONE
        )
        if self.decision != expected_decision or self.next_authorization != expected_next:
            raise ValueError("S4 source feasibility authority changed")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise ValueError("S4 source feasibility blockers changed")
        if (self.failed_gate_count == 0) == bool(self.blockers):
            raise ValueError("S4 blocker presence does not match gate outcome")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S4 source feasibility limitations changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S4 source feasibility result hash changed")
        return self


def build_hashed(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump(mode="json")
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def audit_s4_feasibility_protocol(protocol: S4EtpSourceFeasibilityProtocol) -> bool:
    try:
        S4EtpSourceFeasibilityProtocol.model_validate(
            protocol.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_s4_feasibility_protocol_audit(
    audit: S4EtpSourceFeasibilityProtocolAudit,
) -> bool:
    try:
        S4EtpSourceFeasibilityProtocolAudit.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_s4_feasibility_result(result: S4EtpSourceFeasibilityResult) -> bool:
    try:
        S4EtpSourceFeasibilityResult.model_validate(result.model_dump(mode="json"))
    except ValueError:
        return False
    return True
