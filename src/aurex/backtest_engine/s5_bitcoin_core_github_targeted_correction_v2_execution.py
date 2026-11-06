from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (
    S5TargetedCompletenessCorrectionResult,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S5TargetedCorrectionV2ExecutionContract(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v2-execution-contract-v1"
    ] = "aurex-s5-targeted-correction-v2-execution-contract-v1"
    contract_id: Literal["s5-targeted-correction-v2-execution-contract-v1"] = (
        "s5-targeted-correction-v2-execution-contract-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_V2_EXECUTION_CONTRACT_ZERO_REQUESTS"] = (
        "FROZEN_V2_EXECUTION_CONTRACT_ZERO_REQUESTS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=3, max_length=3)
    source_binding_manifest_evidence_hash: str
    implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=3, max_length=3
    )
    implementation_binding_manifest_evidence_hash: str
    v1_target_protocol_evidence_hash: str
    v2_protocol_file_sha256: str
    v2_protocol_evidence_hash: str
    v2_protocol_audit_file_sha256: str
    v2_protocol_audit_evidence_hash: str
    target_manifest_evidence_hash: str
    runner_contract_hash: str
    corrected_response_lifecycle: Literal[
        "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    ] = "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    maximum_v2_request_count: Literal[194] = 194
    maximum_cumulative_possible_request_count: Literal[195] = 195
    credentials_permitted: Literal[False] = False
    mapping_rule_change_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v2.json"
    ] = "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v2.json"
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "implementation_binding_manifest_evidence_hash",
        "v1_target_protocol_evidence_hash",
        "v2_protocol_file_sha256",
        "v2_protocol_evidence_hash",
        "v2_protocol_audit_file_sha256",
        "v2_protocol_audit_evidence_hash",
        "target_manifest_evidence_hash",
        "runner_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S5TargetedCorrectionV2ExecutionContract:
        for rows in (self.source_bindings, self.implementation_bindings):
            paths = tuple(row.path for row in rows)
            if paths != tuple(sorted(set(paths))):
                raise ValueError("S5 targeted v2 execution bindings changed")
        source_hash = universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in self.source_bindings)
        )
        implementation_hash = universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in self.implementation_bindings)
        )
        if (
            source_hash != self.source_binding_manifest_evidence_hash
            or implementation_hash
            != self.implementation_binding_manifest_evidence_hash
        ):
            raise ValueError("S5 targeted v2 execution binding hash changed")
        if any(
            (
                self.credentials_permitted,
                self.mapping_rule_change_permitted,
                self.market_values_permitted,
                self.orders_permitted,
            )
        ):
            raise ValueError("S5 targeted v2 execution grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S5 targeted v2 execution contract hash changed")
        return self


class S5TargetedCorrectionV2ExecutionContractAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v2-execution-contract-audit-v1"
    ] = "aurex-s5-targeted-correction-v2-execution-contract-audit-v1"
    audit_id: Literal[
        "s5-targeted-correction-v2-execution-contract-audit-v1"
    ] = "s5-targeted-correction-v2-execution-contract-audit-v1"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    builder_contract_hash: str
    runner_contract_hash: str
    source_binding_manifest_evidence_hash: str
    implementation_binding_manifest_evidence_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    v2_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_TARGETED_CORRECTION_V2_EXECUTION_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_V2_EXECUTION_AUDIT"
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "builder_contract_hash",
        "runner_contract_hash",
        "source_binding_manifest_evidence_hash",
        "implementation_binding_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCorrectionV2ExecutionContractAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted v2 execution audit hash changed")
        return self


class S5TargetedCompletenessCorrectionResultV2(
    S5TargetedCompletenessCorrectionResult
):
    schema_version: Literal[
        "aurex-s5-targeted-completeness-correction-result-v2"
    ] = "aurex-s5-targeted-completeness-correction-result-v2"
    result_id: Literal["s5-targeted-completeness-correction-result-v2"] = (
        "s5-targeted-completeness-correction-result-v2"
    )
    v1_target_protocol_evidence_hash: str
    v2_remediation_protocol_evidence_hash: str
    v1_failure_result_evidence_hash: str
    v1_failure_audit_evidence_hash: str
    v1_uncertain_request_count: Literal[1] = 1
    v2_remedial_retry_count: Literal[1] = 1
    cumulative_possible_request_count: Literal[195] = 195
    corrected_response_lifecycle_used: Literal[True] = True

    @field_validator(
        "v1_target_protocol_evidence_hash",
        "v2_remediation_protocol_evidence_hash",
        "v1_failure_result_evidence_hash",
        "v1_failure_audit_evidence_hash",
    )
    @classmethod
    def normalize_v2_hashes(cls, value: str) -> str:
        return normalize_sha256(value)
