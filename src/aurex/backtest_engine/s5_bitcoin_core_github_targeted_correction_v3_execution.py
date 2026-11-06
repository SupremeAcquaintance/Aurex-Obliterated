from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_execution import (
    S5TargetedCompletenessCorrectionResultV2,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S5TargetedCorrectionV3ExecutionContract(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v3-execution-contract-v1"
    ] = "aurex-s5-targeted-correction-v3-execution-contract-v1"
    contract_id: Literal["s5-targeted-correction-v3-execution-contract-v1"] = (
        "s5-targeted-correction-v3-execution-contract-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_V3_EXECUTION_CONTRACT_ZERO_REQUESTS"] = (
        "FROZEN_V3_EXECUTION_CONTRACT_ZERO_REQUESTS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=4, max_length=4)
    source_binding_manifest_evidence_hash: str
    implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=4, max_length=4
    )
    implementation_binding_manifest_evidence_hash: str
    target_protocol_evidence_hash: str
    v3_protocol_file_sha256: str
    v3_protocol_evidence_hash: str
    v3_protocol_audit_file_sha256: str
    v3_protocol_audit_evidence_hash: str
    adopted_response_file_sha256: str
    adopted_response_body_sha256: str
    target_manifest_evidence_hash: str
    runner_contract_hash: str
    adopted_response_count: Literal[1] = 1
    pull_10_v3_request_permitted: Literal[False] = False
    maximum_v3_request_count: Literal[193] = 193
    maximum_cumulative_possible_request_count: Literal[195] = 195
    empty_merge_commit_sha_preserved_as_missing: Literal[True] = True
    credentials_permitted: Literal[False] = False
    mapping_rule_change_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v3.json"
    ] = "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v3.json"
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
        "target_protocol_evidence_hash",
        "v3_protocol_file_sha256",
        "v3_protocol_evidence_hash",
        "v3_protocol_audit_file_sha256",
        "v3_protocol_audit_evidence_hash",
        "adopted_response_file_sha256",
        "adopted_response_body_sha256",
        "target_manifest_evidence_hash",
        "runner_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S5TargetedCorrectionV3ExecutionContract:
        for rows in (self.source_bindings, self.implementation_bindings):
            paths = tuple(row.path for row in rows)
            if paths != tuple(sorted(set(paths))):
                raise ValueError("S5 targeted v3 execution bindings changed")
        if self.source_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in self.source_bindings)
        ):
            raise ValueError("S5 targeted v3 source binding hash changed")
        if self.implementation_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in self.implementation_bindings)
        ):
            raise ValueError("S5 targeted v3 implementation binding hash changed")
        if any(
            (
                self.pull_10_v3_request_permitted,
                self.credentials_permitted,
                self.mapping_rule_change_permitted,
                self.market_values_permitted,
                self.orders_permitted,
            )
        ):
            raise ValueError("S5 targeted v3 execution grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S5 targeted v3 execution contract hash changed")
        return self


class S5TargetedCorrectionV3ExecutionContractAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v3-execution-contract-audit-v1"
    ] = "aurex-s5-targeted-correction-v3-execution-contract-audit-v1"
    audit_id: Literal[
        "s5-targeted-correction-v3-execution-contract-audit-v1"
    ] = "s5-targeted-correction-v3-execution-contract-audit-v1"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    builder_contract_hash: str
    runner_contract_hash: str
    source_binding_manifest_evidence_hash: str
    implementation_binding_manifest_evidence_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    v3_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_TARGETED_CORRECTION_V3_EXECUTION_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_V3_EXECUTION_AUDIT"
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
    def validate_audit(self) -> S5TargetedCorrectionV3ExecutionContractAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted v3 execution audit hash changed")
        return self


class S5TargetedCompletenessCorrectionResultV3(
    S5TargetedCompletenessCorrectionResultV2
):
    schema_version: Literal[
        "aurex-s5-targeted-completeness-correction-result-v3"
    ] = "aurex-s5-targeted-completeness-correction-result-v3"
    result_id: Literal["s5-targeted-completeness-correction-result-v3"] = (
        "s5-targeted-completeness-correction-result-v3"
    )
    v3_schema_protocol_evidence_hash: str
    v2_failure_audit_evidence_hash: str
    adopted_response_file_sha256: str
    adopted_response_body_sha256: str
    adopted_response_count: Literal[1] = 1
    pull_10_v3_request_count: Literal[0] = 0
    v3_new_request_count: int = Field(ge=0, le=193)
    empty_merge_commit_sha_response_count: int = Field(ge=1, le=194)

    @field_validator(
        "v3_schema_protocol_evidence_hash",
        "v2_failure_audit_evidence_hash",
        "adopted_response_file_sha256",
        "adopted_response_body_sha256",
    )
    @classmethod
    def normalize_v3_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_v3_result(self) -> S5TargetedCompletenessCorrectionResultV3:
        if not self.response_bindings or (
            self.response_bindings[0].sequence,
            self.response_bindings[0].pull_number,
        ) != (1, 10):
            raise ValueError("S5 targeted v3 adopted response identity changed")
        resumed_v3_count = self.resumed_response_count - self.adopted_response_count
        if (
            resumed_v3_count < 0
            or self.request_attempt_marker_count < self.adopted_response_count
            or self.v3_new_request_count != self.new_request_attempt_count
            or self.v3_new_request_count + resumed_v3_count > 193
            or self.empty_merge_commit_sha_response_count
            > len(self.response_bindings)
        ):
            raise ValueError("S5 targeted v3 request accounting changed")
        if self.decision == "PASS_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION" and (
            self.v3_new_request_count + resumed_v3_count != 193
        ):
            raise ValueError("S5 targeted v3 pass lacks all untouched responses")
        return self
