from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_development_charter import S5GitRefRecord
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_SOURCE_PROTOCOL_DECISION = "FREEZE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_PROTOCOL"
S5_SOURCE_RUN_AUTHORIZATION = "RUN_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_ONCE"
S5_SOURCE_PASS = "PASS_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY"
S5_SOURCE_STOP = "STOP_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_FAILED_RETIRE_S5"
S5_SOURCE_NEXT = "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_ONLY"
S5_SOURCE_NONE = "NONE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_FAILED_RETIRE_S5"

S5_SOURCE_GATE_IDS = (
    "ALL_TWELVE_PREDECESSOR_FAMILIES_BOUND_AND_NONREUSABLE",
    "CANONICAL_REPOSITORY_IDENTITY_AND_MASTER_BRANCH_DOCUMENTED",
    "PUBLIC_GIT_SMART_HTTP_REF_DISCOVERY_REACHABLE_WITHOUT_CREDENTIALS",
    "MIT_REUSE_RIGHTS_DOCUMENTED",
    "AUTHOR_DATE_OVERRIDE_RISK_DOCUMENTED",
    "BITCOIN_CORE_PULL_REQUEST_REBASE_AND_SIGNED_MERGE_WORKFLOW_DOCUMENTED",
    "PUBLIC_GITHUB_COMMIT_METADATA_ENDPOINT_DOCUMENTED",
    "PUBLIC_GITHUB_PULL_REQUEST_MERGED_AT_ENDPOINT_DOCUMENTED",
    "ZERO_DOLLAR_GITHUB_RATE_LIMIT_AND_REQUEST_BUDGET_PATH_DOCUMENTED",
    "EXACT_REF_HASH_PERSISTENCE_AND_RECHECK_IS_IMPLEMENTABLE",
    "POINT_IN_TIME_AVAILABILITY_FIELDS_EXIST_WITHOUT_HISTORY_PAYLOAD_ACCESS",
    "METADATA_PROTOCOL_PASS_CONDITION_IS_REACHABLE_BY_ALLOWED_SOURCES",
    "ONE_SELECTABLE_MECHANISM_AND_ZERO_CHARTER_STAGE_PARAMETERS",
    "FAILURE_OF_ANY_GATE_STOPS_S5_BEFORE_REPOSITORY_HISTORY_OR_BTC_VALUES",
)


class S5FeasibilityBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S5RepositoryEndpointSpec(BaseModel):
    endpoint_id: Literal["GITHUB_CANONICAL_REPOSITORY_METADATA"] = (
        "GITHUB_CANONICAL_REPOSITORY_METADATA"
    )
    method: Literal["GET"] = "GET"
    url: Literal["https://api.github.com/repos/bitcoin/bitcoin"] = (
        "https://api.github.com/repos/bitcoin/bitcoin"
    )
    permitted_response_keys: tuple[str, ...] = (
        "archived",
        "clone_url",
        "default_branch",
        "disabled",
        "full_name",
        "license.spdx_id",
        "private",
        "visibility",
    )
    response_headers_to_preserve: tuple[str, ...] = (
        "content-type",
        "etag",
        "last-modified",
        "x-github-api-version-selected",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "x-ratelimit-resource",
    )
    public_resource_only: Literal[True] = True
    authentication_permitted: Literal[False] = False
    maximum_response_bytes: Literal[1048576] = 1048576

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5GitProbeSpec(BaseModel):
    probe_id: Literal["BITCOIN_CORE_CANONICAL_REF_DISCOVERY"] = (
        "BITCOIN_CORE_CANONICAL_REF_DISCOVERY"
    )
    remote_url: Literal["https://github.com/bitcoin/bitcoin.git"] = (
        "https://github.com/bitcoin/bitcoin.git"
    )
    refs: tuple[str, ...] = (
        "HEAD",
        "refs/heads/master",
        "refs/tags/v30.0",
    )
    credentials_permitted: Literal[False] = False
    history_fetch_permitted: Literal[False] = False
    clone_permitted: Literal[False] = False
    maximum_stdout_bytes: Literal[4096] = 4096

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5BitcoinCoreSourceFeasibilityProtocol(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-source-feasibility-protocol-v1"] = (
        "aurex-s5-bitcoin-core-source-feasibility-protocol-v1"
    )
    protocol_id: Literal["s5-bitcoin-core-source-feasibility-protocol-v1"] = (
        "s5-bitcoin-core-source-feasibility-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PROTOCOL_ONLY_ZERO_NETWORK_REQUESTS"] = (
        "FROZEN_PROTOCOL_ONLY_ZERO_NETWORK_REQUESTS"
    )
    builder_contract_hash: str
    charter_evidence_hash: str
    source_bindings: tuple[S5FeasibilityBinding, ...] = Field(min_length=4, max_length=4)
    repository_endpoint: S5RepositoryEndpointSpec
    git_probe: S5GitProbeSpec
    required_gate_ids: tuple[str, ...] = Field(min_length=14, max_length=14)
    maximum_http_requests: Literal[1] = 1
    maximum_git_transport_requests: Literal[1] = 1
    maximum_total_attempts: Literal[2] = 2
    request_timeout_seconds: Literal[20] = 20
    maximum_run_count: Literal[1] = 1
    github_user_agent: Literal["Aurex-S5-Source-Feasibility/1.0"] = (
        "Aurex-S5-Source-Feasibility/1.0"
    )
    github_accept_header: Literal["application/vnd.github+json"] = "application/vnd.github+json"
    github_api_version: Literal["2022-11-28"] = "2022-11-28"
    result_artifact_required_on_every_exit: Literal[True] = True
    attempt_record_required_for_every_planned_attempt: Literal[True] = True
    raw_response_artifact_required_for_every_completed_attempt: Literal[True] = True
    partial_response_artifacts_must_be_preserved: Literal[True] = True
    all_or_nothing_response_persistence_forbidden: Literal[True] = True
    unknown_attempt_or_success_counts_forbidden: Literal[True] = True
    rerun_after_result_forbidden: Literal[True] = True
    protocol_pass_condition_reachable_by_allowed_sources: Literal[True] = True
    public_repository_metadata_permitted: Literal[True] = True
    public_git_ref_discovery_permitted: Literal[True] = True
    authentication_permitted: Literal[False] = False
    repository_clone_permitted: Literal[False] = False
    repository_history_permitted: Literal[False] = False
    github_commit_history_permitted: Literal[False] = False
    github_pull_request_history_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
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
    repository_endpoint_may_return_incidental_aggregate_numeric_context: Literal[True] = True
    incidental_context_is_outcome_aware_nonqualifying: Literal[True] = True
    network_requests_executed: Literal[0] = 0
    repository_history_records_parsed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_PROTOCOL"] = (
        S5_SOURCE_PROTOCOL_DECISION
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_ONCE"] = (
        S5_SOURCE_RUN_AUTHORIZATION
    )
    limitations: tuple[str, ...] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("builder_contract_hash", "charter_evidence_hash", "protocol_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5BitcoinCoreSourceFeasibilityProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 feasibility bindings must be unique and sorted")
        if self.required_gate_ids != S5_SOURCE_GATE_IDS:
            raise ValueError("S5 source-feasibility gates changed")
        if any(
            (
                self.authentication_permitted,
                self.repository_clone_permitted,
                self.repository_history_permitted,
                self.github_commit_history_permitted,
                self.github_pull_request_history_permitted,
                self.market_values_permitted,
                self.parameters_permitted,
                self.returns_permitted,
                self.historical_screen_permitted,
                self.validation_permitted,
                self.holdout_permitted,
                self.pine_permitted,
                self.paper_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("S5 metadata protocol cannot grant history or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 source-feasibility protocol hash changed")
        return self


class S5BitcoinCoreSourceFeasibilityProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-source-feasibility-protocol-audit-v1"] = (
        "aurex-s5-bitcoin-core-source-feasibility-protocol-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-source-feasibility-protocol-audit-v1"] = (
        "s5-bitcoin-core-source-feasibility-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal["data/evidence/s5_bitcoin_core_source_feasibility_protocol_v1.json"] = (
        "data/evidence/s5_bitcoin_core_source_feasibility_protocol_v1.json"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    source_binding_count: Literal[4] = 4
    gate_count: Literal[14] = 14
    planned_attempt_count: Literal[2] = 2
    network_requests_observed: Literal[0] = 0
    repository_history_records_parsed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_BITCOIN_CORE_SOURCE_FEASIBILITY_PROTOCOL_AUDIT"] = (
        "PASS_S5_BITCOIN_CORE_SOURCE_FEASIBILITY_PROTOCOL_AUDIT"
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_ONCE"] = (
        S5_SOURCE_RUN_AUTHORIZATION
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
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5BitcoinCoreSourceFeasibilityProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 source-feasibility protocol audit hash changed")
        return self


class S5RawArtifactRecord(BaseModel):
    attempt_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    file_sha256: str
    byte_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S5MetadataAttempt(BaseModel):
    attempt_id: Literal["01_GITHUB_REPOSITORY_METADATA", "02_GIT_REF_DISCOVERY"]
    attempt_kind: Literal["HTTP_GET", "GIT_LS_REMOTE"]
    attempted: bool
    succeeded: bool
    started_at: datetime | None
    completed_at: datetime | None
    status_code_or_exit_code: int | None
    response_bytes: int = Field(ge=0)
    raw_artifact_path: str | None
    raw_artifact_sha256: str | None
    error_type: str | None
    error_message: str | None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator("raw_artifact_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S5MetadataAttempt:
        if not self.attempted and any(
            value is not None
            for value in (
                self.started_at,
                self.completed_at,
                self.status_code_or_exit_code,
                self.raw_artifact_path,
                self.raw_artifact_sha256,
                self.error_type,
                self.error_message,
            )
        ):
            raise ValueError("Unattempted S5 metadata attempt cannot contain outcome data")
        if self.succeeded and (
            not self.attempted or self.raw_artifact_path is None or self.raw_artifact_sha256 is None
        ):
            raise ValueError("Successful S5 metadata attempt requires a raw artifact")
        return self


class S5SourceGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5BitcoinCoreSourceFeasibilityResult(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-source-feasibility-result-v1"] = (
        "aurex-s5-bitcoin-core-source-feasibility-result-v1"
    )
    result_id: Literal["s5-bitcoin-core-source-feasibility-result-v1"] = (
        "s5-bitcoin-core-source-feasibility-result-v1"
    )
    executed_at: datetime
    protocol_evidence_hash: str
    runner_contract_hash: str
    attempts: tuple[S5MetadataAttempt, ...] = Field(min_length=2, max_length=2)
    raw_artifacts: tuple[S5RawArtifactRecord, ...] = Field(max_length=2)
    attempted_count: int = Field(ge=0, le=2)
    succeeded_count: int = Field(ge=0, le=2)
    repository_full_name: str | None
    repository_private: bool | None
    repository_archived: bool | None
    repository_disabled: bool | None
    repository_visibility: str | None
    repository_default_branch: str | None
    repository_clone_url: str | None
    repository_license_spdx_id: str | None
    github_rate_limit: int | None = Field(default=None, ge=0)
    github_rate_remaining: int | None = Field(default=None, ge=0)
    git_ref_records: tuple[S5GitRefRecord, ...] = Field(max_length=3)
    head_matches_master: bool
    gate_results: tuple[S5SourceGateResult, ...] = Field(min_length=14, max_length=14)
    passed_gate_count: int = Field(ge=0, le=14)
    failed_gate_count: int = Field(ge=0, le=14)
    credentials_used: Literal[False] = False
    repository_aggregate_numeric_context_received: bool
    repository_aggregate_context_is_nonqualifying: Literal[True] = True
    repository_history_records_parsed: Literal[0] = 0
    github_commit_history_records_parsed: Literal[0] = 0
    github_pull_request_history_records_parsed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    source_feasibility_conclusion: Literal[
        "TECHNICALLY_FEASIBLE_METADATA_PATH_ONLY",
        "NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL",
    ]
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal[
        "PASS_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY",
        "STOP_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_FAILED_RETIRE_S5",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_ONLY",
        "NONE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_FAILED_RETIRE_S5",
    ]
    authorizes_history_payload_protocol: bool
    authorizes_repository_history_access: Literal[False] = False
    authorizes_market_values: Literal[False] = False
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

    @field_validator("executed_at")
    @classmethod
    def normalize_executed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("protocol_evidence_hash", "runner_contract_hash", "result_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5BitcoinCoreSourceFeasibilityResult:
        attempt_ids = tuple(item.attempt_id for item in self.attempts)
        if attempt_ids != (
            "01_GITHUB_REPOSITORY_METADATA",
            "02_GIT_REF_DISCOVERY",
        ):
            raise ValueError("S5 metadata attempt sequence changed")
        if self.attempted_count != sum(item.attempted for item in self.attempts):
            raise ValueError("S5 metadata attempted count changed")
        if self.succeeded_count != sum(item.succeeded for item in self.attempts):
            raise ValueError("S5 metadata success count changed")
        artifact_ids = tuple(item.attempt_id for item in self.raw_artifacts)
        if artifact_ids != tuple(sorted(set(artifact_ids))):
            raise ValueError("S5 raw artifact records must be unique and sorted")
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        if gate_ids != S5_SOURCE_GATE_IDS:
            raise ValueError("S5 source-feasibility result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        failed = sum(item.status == "FAIL" for item in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (passed, failed):
            raise ValueError("S5 gate counts changed")
        passed_result = failed == 0
        if passed_result != (
            self.decision == S5_SOURCE_PASS
            and self.next_authorization == S5_SOURCE_NEXT
            and self.authorizes_history_payload_protocol
            and self.source_feasibility_conclusion == "TECHNICALLY_FEASIBLE_METADATA_PATH_ONLY"
        ):
            raise ValueError("S5 source-feasibility decision is inconsistent")
        if not passed_result and (
            self.decision != S5_SOURCE_STOP
            or self.next_authorization != S5_SOURCE_NONE
            or self.authorizes_history_payload_protocol
            or self.source_feasibility_conclusion != "NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL"
        ):
            raise ValueError("S5 source-feasibility stop decision is inconsistent")
        if passed_result and (
            self.succeeded_count != 2
            or self.repository_full_name != "bitcoin/bitcoin"
            or self.repository_private is not False
            or self.repository_archived is not False
            or self.repository_disabled is not False
            or self.repository_default_branch != "master"
            or self.repository_license_spdx_id != "MIT"
            or len(self.git_ref_records) != 3
            or not self.head_matches_master
        ):
            raise ValueError("S5 PASS lacks canonical repository proof")
        if any(
            (
                self.authorizes_repository_history_access,
                self.authorizes_market_values,
                self.authorizes_parameters,
                self.authorizes_returns,
                self.authorizes_paper,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("S5 metadata result cannot grant history or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 source-feasibility result hash changed")
        return self


class S5BitcoinCoreSourceFeasibilityResultAudit(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-source-feasibility-result-audit-v1"] = (
        "aurex-s5-bitcoin-core-source-feasibility-result-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-source-feasibility-result-audit-v1"] = (
        "s5-bitcoin-core-source-feasibility-result-audit-v1"
    )
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json"] = (
        "data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    raw_artifacts_verified: Literal[True] = True
    attempted_count: int = Field(ge=0, le=2)
    succeeded_count: int = Field(ge=0, le=2)
    passed_gate_count: int = Field(ge=0, le=14)
    failed_gate_count: int = Field(ge=0, le=14)
    repository_history_records_parsed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_SOURCE_RESULT_RECONSTRUCTED_NO_HISTORY_OR_MARKET_OUTCOMES"] = (
        "PASS_S5_SOURCE_RESULT_RECONSTRUCTED_NO_HISTORY_OR_MARKET_OUTCOMES"
    )
    next_authorization: Literal[
        "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_ONLY",
        "NONE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_FAILED_RETIRE_S5",
    ]
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
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5BitcoinCoreSourceFeasibilityResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 source result audit hash changed")
        return self


def audit_s5_source_protocol(protocol: S5BitcoinCoreSourceFeasibilityProtocol) -> bool:
    try:
        S5BitcoinCoreSourceFeasibilityProtocol.model_validate(protocol.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s5_source_protocol_audit(
    audit: S5BitcoinCoreSourceFeasibilityProtocolAudit,
) -> bool:
    try:
        S5BitcoinCoreSourceFeasibilityProtocolAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s5_source_result(result: S5BitcoinCoreSourceFeasibilityResult) -> bool:
    try:
        S5BitcoinCoreSourceFeasibilityResult.model_validate(result.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s5_source_result_audit(
    audit: S5BitcoinCoreSourceFeasibilityResultAudit,
) -> bool:
    try:
        S5BitcoinCoreSourceFeasibilityResultAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True
