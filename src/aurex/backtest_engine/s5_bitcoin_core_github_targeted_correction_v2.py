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

S5_TARGETED_V2_RUN = "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_V2"


class S5TargetedCorrectionV2Protocol(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v2-remediation-protocol-v1"
    ] = "aurex-s5-targeted-correction-v2-remediation-protocol-v1"
    protocol_id: Literal["s5-targeted-correction-v2-remediation-protocol-v1"] = (
        "s5-targeted-correction-v2-remediation-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_REMEDIATION_ONLY_ZERO_V2_REQUESTS"] = (
        "FROZEN_REMEDIATION_ONLY_ZERO_V2_REQUESTS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=8, max_length=8)
    source_binding_manifest_evidence_hash: str
    v1_protocol_evidence_hash: str
    v1_protocol_audit_evidence_hash: str
    v1_execution_contract_evidence_hash: str
    v1_execution_contract_audit_evidence_hash: str
    v1_result_evidence_hash: str
    v1_failure_audit_evidence_hash: str
    target_manifest_evidence_hash: str
    target_count: Literal[194] = 194
    v1_uncertain_attempt_target: Literal[10] = 10
    v1_uncertain_attempt_count: Literal[1] = 1
    v1_accepted_response_count: Literal[0] = 0
    v1_underlying_error_type: Literal["TypeError"] = "TypeError"
    v1_context_manager_defect_verified: Literal[True] = True
    v1_attempt_retry_authority_superseded_only_for_pull_10: Literal[True] = True
    untouched_first_request_target_count: Literal[193] = 193
    v2_remedial_request_target_count: Literal[1] = 1
    maximum_v2_request_count: Literal[194] = 194
    maximum_cumulative_possible_request_count: Literal[195] = 195
    transport_response_lifecycle: Literal[
        "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    ] = "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    direct_pull_endpoint_template: Literal[
        "https://api.github.com/repos/bitcoin/bitcoin/pulls/{pull_number}"
    ] = "https://api.github.com/repos/bitcoin/bitcoin/pulls/{pull_number}"
    acceptable_http_statuses: tuple[Literal[200, 404], ...] = (200, 404)
    raw_response_directory: Literal[
        "data/evidence/s5_github_targeted_pull_responses_v2"
    ] = "data/evidence/s5_github_targeted_pull_responses_v2"
    response_file_pattern: Literal["pull_{pull_number:06d}.json"] = (
        "pull_{pull_number:06d}.json"
    )
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v2.json"
    ] = "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v2.json"
    crash_marker_required_before_request: Literal[True] = True
    incomplete_v2_attempt_retry_forbidden: Literal[True] = True
    completed_v2_response_resume_permitted: Literal[True] = True
    credentials_permitted: Literal[False] = False
    authorization_header_permitted: Literal[False] = False
    environment_proxy_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    concurrency_permitted: Literal[False] = False
    mapping_rule_change_permitted: Literal[False] = False
    accepted_event_creation_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    maximum_local_git_process_count: Literal[2] = 2
    maximum_response_bytes_per_target: Literal[2097152] = 2_097_152
    maximum_total_response_bytes: Literal[268435456] = 268_435_456
    maximum_elapsed_seconds: Literal[21600] = 21_600
    v2_requests_executed_during_freeze: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S5_TARGETED_CORRECTION_V2_REMEDIATION_PROTOCOL"] = (
        "FREEZE_S5_TARGETED_CORRECTION_V2_REMEDIATION_PROTOCOL"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_V2"
    ] = S5_TARGETED_V2_RUN
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
        "v1_protocol_evidence_hash",
        "v1_protocol_audit_evidence_hash",
        "v1_execution_contract_evidence_hash",
        "v1_execution_contract_audit_evidence_hash",
        "v1_result_evidence_hash",
        "v1_failure_audit_evidence_hash",
        "target_manifest_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5TargetedCorrectionV2Protocol:
        paths = tuple(binding.path for binding in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 targeted v2 source bindings changed")
        forbidden = (
            self.credentials_permitted,
            self.authorization_header_permitted,
            self.environment_proxy_permitted,
            self.redirects_permitted,
            self.concurrency_permitted,
            self.mapping_rule_change_permitted,
            self.accepted_event_creation_permitted,
            self.market_values_permitted,
            self.parameters_permitted,
            self.returns_permitted,
            self.candidates_permitted,
            self.orders_permitted,
        )
        if any(forbidden):
            raise ValueError("S5 targeted v2 grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 targeted v2 protocol hash changed")
        return self


class S5TargetedCorrectionV2ProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v2-remediation-protocol-audit-v1"
    ] = "aurex-s5-targeted-correction-v2-remediation-protocol-audit-v1"
    audit_id: Literal[
        "s5-targeted-correction-v2-remediation-protocol-audit-v1"
    ] = "s5-targeted-correction-v2-remediation-protocol-audit-v1"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    source_binding_manifest_evidence_hash: str
    target_manifest_evidence_hash: str
    source_binding_count: Literal[8] = 8
    auditor_source_sha256: str
    v2_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S5_TARGETED_CORRECTION_V2_PROTOCOL_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_V2_PROTOCOL_AUDIT"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_V2"
    ] = S5_TARGETED_V2_RUN
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
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCorrectionV2ProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted v2 protocol audit hash changed")
        return self
