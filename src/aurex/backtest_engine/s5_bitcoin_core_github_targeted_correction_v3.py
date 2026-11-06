from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_TARGETED_V3_RUN = "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_V3"


class S5TargetedCorrectionV3Protocol(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v3-schema-remediation-protocol-v1"
    ] = "aurex-s5-targeted-correction-v3-schema-remediation-protocol-v1"
    protocol_id: Literal[
        "s5-targeted-correction-v3-schema-remediation-protocol-v1"
    ] = "s5-targeted-correction-v3-schema-remediation-protocol-v1"
    frozen_at: datetime
    status: Literal["FROZEN_SCHEMA_REMEDIATION_ZERO_V3_REQUESTS"] = (
        "FROZEN_SCHEMA_REMEDIATION_ZERO_V3_REQUESTS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=8, max_length=8)
    source_binding_manifest_evidence_hash: str
    target_protocol_evidence_hash: str
    v2_protocol_evidence_hash: str
    v2_execution_contract_evidence_hash: str
    v2_result_evidence_hash: str
    v2_failure_audit_evidence_hash: str
    target_manifest_evidence_hash: str
    target_count: Literal[194] = 194
    adopted_response_pull_number: Literal[10] = 10
    adopted_response_http_status: Literal[200] = 200
    adopted_response_file_sha256: str
    adopted_response_body_sha256: str
    adopted_response_merge_commit_sha_value: Literal[""] = ""
    pull_10_v3_request_permitted: Literal[False] = False
    untouched_v3_request_target_count: Literal[193] = 193
    maximum_v3_request_count: Literal[193] = 193
    maximum_cumulative_possible_request_count: Literal[195] = 195
    merge_commit_sha_accepted_source_shapes: tuple[
        Literal["NULL", "EMPTY_STRING", "SHA1_40_LOWER_HEX"], ...
    ] = ("NULL", "EMPTY_STRING", "SHA1_40_LOWER_HEX")
    merge_commit_sha_source_value_normalization_permitted: Literal[False] = False
    transport_response_lifecycle: Literal[
        "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    ] = "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    raw_response_directory: Literal[
        "data/evidence/s5_github_targeted_pull_responses_v3"
    ] = "data/evidence/s5_github_targeted_pull_responses_v3"
    response_file_pattern: Literal["pull_{pull_number:06d}.json"] = (
        "pull_{pull_number:06d}.json"
    )
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v3.json"
    ] = "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v3.json"
    crash_marker_required_before_request: Literal[True] = True
    incomplete_v3_attempt_retry_forbidden: Literal[True] = True
    completed_v3_response_resume_permitted: Literal[True] = True
    credentials_permitted: Literal[False] = False
    authorization_header_permitted: Literal[False] = False
    environment_proxy_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    concurrency_permitted: Literal[False] = False
    mapping_rule_change_permitted: Literal[False] = False
    accepted_event_creation_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    maximum_local_git_process_count: Literal[2] = 2
    maximum_response_bytes_per_target: Literal[2097152] = 2_097_152
    maximum_total_response_bytes: Literal[268435456] = 268_435_456
    maximum_elapsed_seconds: Literal[21600] = 21_600
    v3_requests_executed_during_freeze: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S5_TARGETED_CORRECTION_V3_SCHEMA_REMEDIATION"] = (
        "FREEZE_S5_TARGETED_CORRECTION_V3_SCHEMA_REMEDIATION"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_V3"
    ] = S5_TARGETED_V3_RUN
    limitations: tuple[str, ...] = Field(min_length=12)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "target_protocol_evidence_hash",
        "v2_protocol_evidence_hash",
        "v2_execution_contract_evidence_hash",
        "v2_result_evidence_hash",
        "v2_failure_audit_evidence_hash",
        "target_manifest_evidence_hash",
        "adopted_response_file_sha256",
        "adopted_response_body_sha256",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5TargetedCorrectionV3Protocol:
        paths = tuple(row.path for row in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 targeted v3 source bindings changed")
        if self.merge_commit_sha_accepted_source_shapes != (
            "NULL",
            "EMPTY_STRING",
            "SHA1_40_LOWER_HEX",
        ):
            raise ValueError("S5 targeted v3 merge SHA source shapes changed")
        if any(
            (
                self.pull_10_v3_request_permitted,
                self.merge_commit_sha_source_value_normalization_permitted,
                self.credentials_permitted,
                self.authorization_header_permitted,
                self.environment_proxy_permitted,
                self.redirects_permitted,
                self.concurrency_permitted,
                self.mapping_rule_change_permitted,
                self.accepted_event_creation_permitted,
                self.market_values_permitted,
                self.returns_permitted,
                self.orders_permitted,
            )
        ):
            raise ValueError("S5 targeted v3 grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 targeted v3 protocol hash changed")
        return self


class S5TargetedCorrectionV3ProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v3-protocol-audit-v1"
    ] = "aurex-s5-targeted-correction-v3-protocol-audit-v1"
    audit_id: Literal["s5-targeted-correction-v3-protocol-audit-v1"] = (
        "s5-targeted-correction-v3-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    source_binding_manifest_evidence_hash: str
    target_manifest_evidence_hash: str
    adopted_response_file_sha256: str
    adopted_response_body_sha256: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    v3_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_TARGETED_CORRECTION_V3_PROTOCOL_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_V3_PROTOCOL_AUDIT"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_V3"
    ] = S5_TARGETED_V3_RUN
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "target_manifest_evidence_hash",
        "adopted_response_file_sha256",
        "adopted_response_body_sha256",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCorrectionV3ProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted v3 protocol audit hash changed")
        return self
