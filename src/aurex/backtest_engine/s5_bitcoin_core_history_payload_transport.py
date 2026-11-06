from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (
    S5_HISTORY_NEXT,
    S5_HISTORY_STOP,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryPayloadResultAudit,
    S5HistoryBinding,
    S5HistoryFileRecord,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_VERIFIER_FAILURE_ADJUDICATION = (
    "REJECT_TERMINAL_SOURCE_INTERPRETATION_BLOBLESS_CLONE_SUCCEEDED_VERIFIER_FAILED"
)
S5_VERIFIER_AMENDMENT_AUTHORIZATION = (
    "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_AMENDMENT_V2_ONLY"
)
S5_VERIFIER_RUN_AUTHORIZATION = "RUN_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_V2_ONCE"


class S5BitcoinCoreHistoryVerifierFailureAudit(S5BitcoinCoreHistoryPayloadResultAudit):
    schema_version: Literal["aurex-s5-bitcoin-core-history-verifier-failure-audit-v1"] = (
        "aurex-s5-bitcoin-core-history-verifier-failure-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-history-verifier-failure-audit-v1"] = (
        "s5-bitcoin-core-history-verifier-failure-audit-v1"
    )
    result_path: Literal["data/evidence/s5_bitcoin_core_history_payload_result_v1.json"] = (
        "data/evidence/s5_bitcoin_core_history_payload_result_v1.json"
    )
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=5, max_length=5)
    result_audit_evidence_hash: str
    transcript_file_sha256: str
    partial_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git.partial"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git.partial"
    partial_dataset_file_manifest: tuple[S5HistoryFileRecord, ...] = Field(min_length=1)
    partial_dataset_directory_sha256: str
    successful_clone_process_count: Literal[1] = 1
    additional_network_process_count: Literal[0] = 0
    clone_exit_code: Literal[0] = 0
    verifier_error_type: Literal["ValueError"] = "ValueError"
    verifier_error_message: str = Field(min_length=1)
    verifier_rejected_promised_missing_blob: Literal[True] = True
    repository_is_bare: Literal[True] = True
    repository_is_shallow: Literal[False] = False
    remote_origin_url: Literal["https://github.com/bitcoin/bitcoin.git"] = (
        "https://github.com/bitcoin/bitcoin.git"
    )
    remote_promisor: Literal[True] = True
    remote_partial_clone_filter: Literal["blob:none"] = "blob:none"
    source_cutoff_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    cutoff_commit_present: Literal[True] = True
    cutoff_commit_count: int = Field(gt=0)
    commit_messages_read: Literal[0] = 0
    author_identities_read: Literal[0] = 0
    author_timestamps_read: Literal[0] = 0
    pull_request_ids_parsed: Literal[0] = 0
    github_api_requests_executed: Literal[0] = 0
    original_decision: Literal["STOP_S5_BITCOIN_CORE_HISTORY_PAYLOAD_FAILED_RETIRE_S5"] = (
        S5_HISTORY_STOP
    )
    adjudication: Literal[
        "REJECT_TERMINAL_SOURCE_INTERPRETATION_BLOBLESS_CLONE_SUCCEEDED_VERIFIER_FAILED"
    ] = S5_VERIFIER_FAILURE_ADJUDICATION
    next_authorization: Literal[
        "AUTHORIZE_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_AMENDMENT_V2_ONLY"
    ] = S5_VERIFIER_AMENDMENT_AUTHORIZATION

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "result_audit_evidence_hash",
        "transcript_file_sha256",
        "partial_dataset_directory_sha256",
    )
    @classmethod
    def normalize_lineage_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_failure_audit(self) -> S5BitcoinCoreHistoryVerifierFailureAudit:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 verifier-failure bindings changed")
        manifest_paths = tuple(item.relative_path for item in self.partial_dataset_file_manifest)
        if manifest_paths != tuple(sorted(set(manifest_paths))):
            raise ValueError("S5 verifier-failure manifest changed")
        if not self.verifier_error_message.startswith(
            "Local Git integrity command failed: fatal: missing blob object '"
        ):
            raise ValueError("S5 verifier failure is not the expected promised-blob condition")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 verifier-failure audit hash changed")
        return self


class S5BitcoinCoreHistoryLocalVerifierAmendmentV2(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-local-verifier-amendment-v2"] = (
        "aurex-s5-bitcoin-core-history-local-verifier-amendment-v2"
    )
    amendment_id: Literal["s5-bitcoin-core-history-local-verifier-amendment-v2"] = (
        "s5-bitcoin-core-history-local-verifier-amendment-v2"
    )
    frozen_at: datetime
    status: Literal["FROZEN_AFTER_SUCCESSFUL_CLONE_AND_PROMISED_BLOB_VERIFIER_FAILURE"] = (
        "FROZEN_AFTER_SUCCESSFUL_CLONE_AND_PROMISED_BLOB_VERIFIER_FAILURE"
    )
    builder_contract_hash: str
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    failure_audit_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=5, max_length=5)
    preserved_partial_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git.partial"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git.partial"
    final_dataset_path: Literal["data/evidence/s5_bitcoin_core_history_payload_v1.git"] = (
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    )
    maximum_local_revalidation_count: Literal[1] = 1
    additional_network_process_count: Literal[0] = 0
    network_access_permitted: Literal[False] = False
    credential_access_permitted: Literal[False] = False
    original_object_enumeration: Literal["git rev-list --objects --no-object-names <cutoff>"] = (
        "git rev-list --objects --no-object-names <cutoff>"
    )
    corrected_object_enumeration: Literal[
        "git rev-list --objects --no-object-names --missing=print <cutoff>"
    ] = "git rev-list --objects --no-object-names --missing=print <cutoff>"
    corrected_stream_timeout_seconds: Literal[600] = 600
    corrected_stream_must_be_hashed_incrementally: Literal[True] = True
    missing_promised_blob_prefix: Literal["?"] = "?"
    protocol_source_cutoff_unchanged: Literal[True] = True
    protocol_gate_ids_unchanged: Literal[True] = True
    all_other_protocol_limits_unchanged: Literal[True] = True
    history_semantic_parsing_permitted: Literal[False] = False
    commit_message_access_permitted: Literal[False] = False
    author_identity_access_permitted: Literal[False] = False
    author_timestamp_access_permitted: Literal[False] = False
    pull_request_id_parsing_permitted: Literal[False] = False
    github_api_requests_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    decision: Literal["FREEZE_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_AMENDMENT_V2"] = (
        "FREEZE_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_AMENDMENT_V2"
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_V2_ONCE"] = (
        S5_VERIFIER_RUN_AUTHORIZATION
    )
    limitations: tuple[str, ...] = Field(min_length=8)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "failure_audit_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S5BitcoinCoreHistoryLocalVerifierAmendmentV2:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 verifier-amendment bindings changed")
        if any(
            (
                self.network_access_permitted,
                self.credential_access_permitted,
                self.history_semantic_parsing_permitted,
                self.commit_message_access_permitted,
                self.author_identity_access_permitted,
                self.author_timestamp_access_permitted,
                self.pull_request_id_parsing_permitted,
                self.github_api_requests_permitted,
                self.market_values_permitted,
                self.parameters_permitted,
                self.returns_permitted,
                self.paper_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("S5 verifier amendment cannot grant outcome or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S5 verifier amendment hash changed")
        return self


class S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-local-verifier-amendment-audit-v2"] = (
        "aurex-s5-bitcoin-core-history-local-verifier-amendment-audit-v2"
    )
    audit_id: Literal["s5-bitcoin-core-history-local-verifier-amendment-audit-v2"] = (
        "s5-bitcoin-core-history-local-verifier-amendment-audit-v2"
    )
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    additional_network_processes_observed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_AMENDMENT_V2_AUDIT"] = (
        "PASS_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_AMENDMENT_V2_AUDIT"
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_HISTORY_LOCAL_VERIFIER_V2_ONCE"] = (
        S5_VERIFIER_RUN_AUTHORIZATION
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "amendment_file_sha256",
        "amendment_evidence_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 verifier-amendment audit hash changed")
        return self


class S5BitcoinCoreHistoryPayloadResultV2(S5BitcoinCoreHistoryPayloadResult):
    schema_version: Literal["aurex-s5-bitcoin-core-history-payload-result-v2"] = (
        "aurex-s5-bitcoin-core-history-payload-result-v2"
    )
    result_id: Literal["s5-bitcoin-core-history-payload-result-v2"] = (
        "s5-bitcoin-core-history-payload-result-v2"
    )
    prior_result_file_sha256: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    failure_audit_evidence_hash: str
    verifier_amendment_file_sha256: str
    verifier_amendment_evidence_hash: str
    verifier_amendment_audit_evidence_hash: str
    additional_network_process_count: Literal[0] = 0
    missing_promised_object_count: int = Field(ge=0)
    object_stream_transport_order_preserved: Literal[True] = True

    @field_validator(
        "prior_result_file_sha256",
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "failure_audit_evidence_hash",
        "verifier_amendment_file_sha256",
        "verifier_amendment_evidence_hash",
        "verifier_amendment_audit_evidence_hash",
    )
    @classmethod
    def normalize_lineage_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S5BitcoinCoreHistoryPayloadResultAuditV2(S5BitcoinCoreHistoryPayloadResultAudit):
    schema_version: Literal["aurex-s5-bitcoin-core-history-payload-result-audit-v2"] = (
        "aurex-s5-bitcoin-core-history-payload-result-audit-v2"
    )
    audit_id: Literal["s5-bitcoin-core-history-payload-result-audit-v2"] = (
        "s5-bitcoin-core-history-payload-result-audit-v2"
    )
    result_path: Literal["data/evidence/s5_bitcoin_core_history_payload_result_v2.json"] = (
        "data/evidence/s5_bitcoin_core_history_payload_result_v2.json"
    )
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    verifier_amendment_evidence_hash: str
    verifier_amendment_audit_evidence_hash: str
    additional_network_process_count: Literal[0] = 0
    missing_promised_object_count: int = Field(ge=0)

    @field_validator(
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "verifier_amendment_evidence_hash",
        "verifier_amendment_audit_evidence_hash",
    )
    @classmethod
    def normalize_lineage_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


def audit_verifier_failure(audit: S5BitcoinCoreHistoryVerifierFailureAudit) -> bool:
    try:
        S5BitcoinCoreHistoryVerifierFailureAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_verifier_amendment(
    amendment: S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
) -> bool:
    try:
        S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate(
            amendment.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_verifier_amendment_audit(
    audit: S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
) -> bool:
    try:
        S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_s5_history_result_v2(result: S5BitcoinCoreHistoryPayloadResultV2) -> bool:
    try:
        S5BitcoinCoreHistoryPayloadResultV2.model_validate(result.model_dump(mode="json"))
    except ValueError:
        return False
    return result.next_authorization == S5_HISTORY_NEXT


def audit_s5_history_result_audit_v2(
    audit: S5BitcoinCoreHistoryPayloadResultAuditV2,
) -> bool:
    try:
        S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True
