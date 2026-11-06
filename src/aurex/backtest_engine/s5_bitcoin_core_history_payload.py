from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_HISTORY_PROTOCOL_DECISION = "FREEZE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL"
S5_HISTORY_RUN_AUTHORIZATION = "RUN_S5_BITCOIN_CORE_HISTORY_PAYLOAD_ONCE"
S5_HISTORY_PASS = "PASS_S5_BITCOIN_CORE_HISTORY_PAYLOAD"
S5_HISTORY_STOP = "STOP_S5_BITCOIN_CORE_HISTORY_PAYLOAD_FAILED_RETIRE_S5"
S5_HISTORY_NEXT = "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL_ONLY"
S5_HISTORY_NONE = "NONE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_FAILED_RETIRE_S5"

S5_HISTORY_GATE_IDS = (
    "PREDECESSOR_LINEAGE_AND_READINESS_V28_BOUND",
    "CANONICAL_BITCOIN_CORE_REMOTE_AND_MASTER_BRANCH_FIXED",
    "SOURCE_CUTOFF_AND_V30_TAG_IDENTITIES_FIXED_BEFORE_HISTORY_ACCESS",
    "ONE_PUBLIC_CREDENTIAL_FREE_GIT_CLONE_PROCESS_ONLY",
    "BARE_SINGLE_BRANCH_TAGLESS_BLOBLESS_CLONE_ENFORCED",
    "FREE_DISK_AND_DATASET_BYTE_LIMITS_ENFORCED",
    "CLONE_COMPLETED_AND_FINAL_DATASET_PATH_EXISTS",
    "FETCHED_MASTER_CONTAINS_FROZEN_SOURCE_CUTOFF",
    "REPOSITORY_IS_COMPLETE_NOT_SHALLOW",
    "PROMISOR_REMOTE_AND_BLOB_NONE_FILTER_VERIFIED",
    "COMPLETE_DATASET_FILE_MANIFEST_HASHED",
    "CUTOFF_REACHABLE_OBJECT_ID_STREAM_HASHED_WITHOUT_SEMANTIC_PARSING",
    "ZERO_MARKET_OUTCOMES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
    "PASS_AUTHORIZES_COMPLETENESS_CENSUS_PROTOCOL_ONLY",
)


class S5HistoryBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S5HistoryFileRecord(BaseModel):
    relative_path: str = Field(min_length=1)
    file_sha256: str
    byte_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_path(self) -> S5HistoryFileRecord:
        path = self.relative_path.replace("\\", "/")
        if path != self.relative_path or path.startswith("/") or ".." in path.split("/"):
            raise ValueError("S5 history manifest path must be canonical and relative")
        return self


class S5HistoryCloneSpec(BaseModel):
    remote_url: Literal["https://github.com/bitcoin/bitcoin.git"] = (
        "https://github.com/bitcoin/bitcoin.git"
    )
    branch: Literal["master"] = "master"
    final_dataset_path: Literal["data/evidence/s5_bitcoin_core_history_payload_v1.git"] = (
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    )
    partial_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git.partial"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git.partial"
    raw_transcript_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_responses_v1/01_git_clone.json"
    ] = "data/evidence/s5_bitcoin_core_history_payload_responses_v1/01_git_clone.json"
    git_arguments: tuple[str, ...] = (
        "clone",
        "--bare",
        "--filter=blob:none",
        "--single-branch",
        "--no-tags",
        "--branch",
        "master",
        "--quiet",
    )
    maximum_git_process_count: Literal[1] = 1
    maximum_elapsed_seconds: Literal[1800] = 1800
    minimum_free_disk_bytes: Literal[5000000000] = 5_000_000_000
    maximum_dataset_bytes: Literal[2000000000] = 2_000_000_000
    maximum_transcript_bytes: Literal[4194304] = 4_194_304
    credentials_permitted: Literal[False] = False
    interactive_prompt_permitted: Literal[False] = False
    bare_clone_required: Literal[True] = True
    single_branch_required: Literal[True] = True
    tags_permitted: Literal[False] = False
    blob_payloads_requested: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5BitcoinCoreHistoryPayloadProtocol(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-payload-protocol-v1"] = (
        "aurex-s5-bitcoin-core-history-payload-protocol-v1"
    )
    protocol_id: Literal["s5-bitcoin-core-history-payload-protocol-v1"] = (
        "s5-bitcoin-core-history-payload-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PROTOCOL_ONLY_ZERO_HISTORY_ACCESS"] = (
        "FROZEN_PROTOCOL_ONLY_ZERO_HISTORY_ACCESS"
    )
    builder_contract_hash: str
    charter_evidence_hash: str
    source_feasibility_result_evidence_hash: str
    readiness_v28_result_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=8, max_length=8)
    clone_spec: S5HistoryCloneSpec
    source_cutoff_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_v30_tag_object: str = Field(pattern=r"^[0-9a-f]{40}$")
    required_gate_ids: tuple[str, ...] = Field(min_length=14, max_length=14)
    maximum_run_count: Literal[1] = 1
    result_artifact_required_on_every_normal_exit: Literal[True] = True
    partial_dataset_must_be_preserved_on_failure: Literal[True] = True
    rerun_after_result_forbidden: Literal[True] = True
    repository_history_payload_permitted: Literal[True] = True
    history_semantic_parsing_permitted: Literal[False] = False
    commit_message_access_permitted: Literal[False] = False
    author_identity_access_permitted: Literal[False] = False
    author_timestamp_access_permitted: Literal[False] = False
    pull_request_id_parsing_permitted: Literal[False] = False
    github_api_requests_permitted: Literal[False] = False
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
    network_processes_executed: Literal[0] = 0
    repository_history_records_acquired: Literal[0] = 0
    repository_history_records_semantically_parsed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL"] = (
        S5_HISTORY_PROTOCOL_DECISION
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_HISTORY_PAYLOAD_ONCE"] = (
        S5_HISTORY_RUN_AUTHORIZATION
    )
    limitations: tuple[str, ...] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "charter_evidence_hash",
        "source_feasibility_result_evidence_hash",
        "readiness_v28_result_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5BitcoinCoreHistoryPayloadProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 history bindings must be unique and sorted")
        if self.required_gate_ids != S5_HISTORY_GATE_IDS:
            raise ValueError("S5 history payload gates changed")
        if any(
            (
                self.history_semantic_parsing_permitted,
                self.commit_message_access_permitted,
                self.author_identity_access_permitted,
                self.author_timestamp_access_permitted,
                self.pull_request_id_parsing_permitted,
                self.github_api_requests_permitted,
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
            raise ValueError(
                "S5 history payload protocol cannot grant research or trading authority"
            )
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 history payload protocol hash changed")
        return self


class S5BitcoinCoreHistoryPayloadProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-payload-protocol-audit-v1"] = (
        "aurex-s5-bitcoin-core-history-payload-protocol-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-history-payload-protocol-audit-v1"] = (
        "s5-bitcoin-core-history-payload-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal["data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json"] = (
        "data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    source_binding_count: Literal[8] = 8
    gate_count: Literal[14] = 14
    planned_network_process_count: Literal[1] = 1
    history_access_observed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_AUDIT"] = (
        "PASS_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_AUDIT"
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_HISTORY_PAYLOAD_ONCE"] = (
        S5_HISTORY_RUN_AUTHORIZATION
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
    def validate_audit(self) -> S5BitcoinCoreHistoryPayloadProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 history protocol audit hash changed")
        return self


class S5HistoryCloneAttempt(BaseModel):
    attempt_id: Literal["01_GIT_BLOBLESS_BARE_CLONE"] = "01_GIT_BLOBLESS_BARE_CLONE"
    attempted: bool
    succeeded: bool
    started_at: datetime | None
    completed_at: datetime | None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    exit_code: int | None
    transcript_path: str | None
    transcript_file_sha256: str | None
    transcript_byte_count: int = Field(ge=0)
    error_type: str | None
    error_message: str | None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator("transcript_file_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S5HistoryCloneAttempt:
        if not self.attempted and any(
            value is not None
            for value in (
                self.started_at,
                self.completed_at,
                self.elapsed_seconds,
                self.exit_code,
                self.transcript_path,
                self.transcript_file_sha256,
                self.error_type,
                self.error_message,
            )
        ):
            raise ValueError("Unattempted S5 history clone cannot contain outcome data")
        if self.succeeded and (
            not self.attempted
            or self.exit_code != 0
            or self.transcript_path is None
            or self.transcript_file_sha256 is None
        ):
            raise ValueError("Successful S5 history clone requires a zero-exit transcript")
        return self


class S5HistoryGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5BitcoinCoreHistoryPayloadResult(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-payload-result-v1"] = (
        "aurex-s5-bitcoin-core-history-payload-result-v1"
    )
    result_id: Literal["s5-bitcoin-core-history-payload-result-v1"] = (
        "s5-bitcoin-core-history-payload-result-v1"
    )
    executed_at: datetime
    protocol_evidence_hash: str
    runner_contract_hash: str
    attempt: S5HistoryCloneAttempt
    dataset_path: str | None
    partial_dataset_path: str | None
    dataset_file_manifest: tuple[S5HistoryFileRecord, ...]
    dataset_file_count: int = Field(ge=0)
    dataset_byte_count: int = Field(ge=0)
    dataset_directory_sha256: str | None
    free_disk_bytes_before: int = Field(ge=0)
    fetched_master_head: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    source_cutoff_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    cutoff_commit_present: bool
    cutoff_is_ancestor_of_fetched_master: bool
    repository_is_bare: bool
    repository_is_shallow: bool | None
    remote_origin_url: str | None
    remote_promisor: bool
    remote_partial_clone_filter: str | None
    local_branch_refs: tuple[str, ...]
    local_tag_ref_count: int = Field(ge=0)
    reachable_object_id_count: int = Field(ge=0)
    reachable_object_id_stream_sha256: str | None
    cutoff_commit_count: int = Field(ge=0)
    newer_remote_state_incidentally_acquired: bool
    gate_results: tuple[S5HistoryGateResult, ...] = Field(min_length=14, max_length=14)
    passed_gate_count: int = Field(ge=0, le=14)
    failed_gate_count: int = Field(ge=0, le=14)
    network_process_count: int = Field(ge=0, le=1)
    credentials_used: Literal[False] = False
    repository_history_records_acquired: int = Field(ge=0)
    repository_history_records_semantically_parsed: Literal[0] = 0
    commit_messages_read: Literal[0] = 0
    author_identities_read: Literal[0] = 0
    author_timestamps_read: Literal[0] = 0
    pull_request_ids_parsed: Literal[0] = 0
    github_api_requests_executed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    payload_conclusion: Literal[
        "CANONICAL_HISTORY_PAYLOAD_ACQUIRED_FOR_INTEGRITY_CENSUS_ONLY",
        "PAYLOAD_NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL",
    ]
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal[
        "PASS_S5_BITCOIN_CORE_HISTORY_PAYLOAD",
        "STOP_S5_BITCOIN_CORE_HISTORY_PAYLOAD_FAILED_RETIRE_S5",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL_ONLY",
        "NONE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_FAILED_RETIRE_S5",
    ]
    authorizes_history_completeness_census_protocol: bool
    authorizes_history_semantic_parsing: Literal[False] = False
    authorizes_github_api_requests: Literal[False] = False
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=10)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("executed_at")
    @classmethod
    def normalize_executed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "dataset_directory_sha256",
        "reachable_object_id_stream_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5BitcoinCoreHistoryPayloadResult:
        paths = tuple(item.relative_path for item in self.dataset_file_manifest)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 history dataset manifest must be unique and sorted")
        if self.dataset_file_count != len(self.dataset_file_manifest):
            raise ValueError("S5 history dataset file count changed")
        if self.dataset_byte_count != sum(item.byte_count for item in self.dataset_file_manifest):
            raise ValueError("S5 history dataset byte count changed")
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        if gate_ids != S5_HISTORY_GATE_IDS:
            raise ValueError("S5 history result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        failed = sum(item.status == "FAIL" for item in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (passed, failed):
            raise ValueError("S5 history gate counts changed")
        passed_result = failed == 0
        if passed_result != (
            self.decision == S5_HISTORY_PASS
            and self.next_authorization == S5_HISTORY_NEXT
            and self.authorizes_history_completeness_census_protocol
            and self.payload_conclusion
            == "CANONICAL_HISTORY_PAYLOAD_ACQUIRED_FOR_INTEGRITY_CENSUS_ONLY"
        ):
            raise ValueError("S5 history payload decision is inconsistent")
        if not passed_result and (
            self.decision != S5_HISTORY_STOP
            or self.next_authorization != S5_HISTORY_NONE
            or self.authorizes_history_completeness_census_protocol
        ):
            raise ValueError("Failed S5 history payload cannot authorize another stage")
        if self.repository_history_records_acquired != self.cutoff_commit_count:
            raise ValueError("S5 acquired history count must equal the cutoff commit count")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 history payload result hash changed")
        return self


class S5BitcoinCoreHistoryPayloadResultAudit(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-payload-result-audit-v1"] = (
        "aurex-s5-bitcoin-core-history-payload-result-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-history-payload-result-audit-v1"] = (
        "s5-bitcoin-core-history-payload-result-audit-v1"
    )
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_history_payload_result_v1.json"] = (
        "data/evidence/s5_bitcoin_core_history_payload_result_v1.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    transcript_reverified: bool
    dataset_manifest_reverified: bool
    local_git_integrity_reverified: bool
    passed_gate_count: int = Field(ge=0, le=14)
    failed_gate_count: int = Field(ge=0, le=14)
    dataset_file_count: int = Field(ge=0)
    dataset_byte_count: int = Field(ge=0)
    cutoff_commit_count: int = Field(ge=0)
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal[
        "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL_ONLY",
        "NONE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_FAILED_RETIRE_S5",
    ]
    decision: Literal["PASS_S5_BITCOIN_CORE_HISTORY_PAYLOAD_RESULT_AUDIT"] = (
        "PASS_S5_BITCOIN_CORE_HISTORY_PAYLOAD_RESULT_AUDIT"
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
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5BitcoinCoreHistoryPayloadResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 history result audit hash changed")
        return self


def audit_s5_history_protocol(protocol: S5BitcoinCoreHistoryPayloadProtocol) -> bool:
    expected = universe_evidence_hash(
        protocol.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return protocol.protocol_evidence_hash == expected


def audit_s5_history_protocol_audit(
    audit: S5BitcoinCoreHistoryPayloadProtocolAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected


def audit_s5_history_result(result: S5BitcoinCoreHistoryPayloadResult) -> bool:
    expected = universe_evidence_hash(
        result.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return result.result_evidence_hash == expected


def audit_s5_history_result_audit(
    audit: S5BitcoinCoreHistoryPayloadResultAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected
