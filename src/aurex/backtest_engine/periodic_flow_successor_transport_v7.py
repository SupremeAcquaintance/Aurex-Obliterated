from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_successor_runner import (
    PeriodicFlowSuccessorAcquisitionResult,
    PeriodicFlowSuccessorCheckpoint,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (
    PeriodicFlowSuccessorTransportAmendmentV5,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (
    PeriodicFlowArchiveEvidenceV6,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorTransportAmendmentV7(
    PeriodicFlowSuccessorTransportAmendmentV5
):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-transport-amendment-v7"
    ] = "aurex-q1-periodic-flow-successor-transport-amendment-v7"
    amendment_id: Literal["q1-periodic-flow-successor-transport-amendment-v7"] = (
        "q1-periodic-flow-successor-transport-amendment-v7"
    )
    status: Literal["FROZEN_POST_V6_TERMINAL_PRE_V7_NETWORK"] = (
        "FROZEN_POST_V6_TERMINAL_PRE_V7_NETWORK"
    )
    parent_v6_validator_amendment_file_sha256: str
    parent_v6_validator_amendment_evidence_hash: str
    parent_v6_contract_file_sha256: str
    parent_v6_contract_evidence_hash: str
    parent_v6_contract_audit_file_sha256: str
    parent_v6_contract_audit_evidence_hash: str
    terminal_v6_result_file_sha256: str
    terminal_v6_result_evidence_hash: str
    terminal_v6_checkpoint_file_sha256: str
    terminal_v6_checkpoint_evidence_hash: str
    terminal_v6_audit_file_sha256: str
    terminal_v6_audit_evidence_hash: str
    seed_total_new_archive_bytes: Literal[30_282_986_798] = 30_282_986_798
    inherited_maximum_new_archive_bytes_total: Literal[100_000_000_000] = (
        100_000_000_000
    )
    maximum_remaining_payload_bytes: Literal[69_717_013_202] = 69_717_013_202
    inherited_minimum_free_disk_bytes_after_acquisition: Literal[20_000_000_000] = (
        20_000_000_000
    )
    failed_partial_adoption_permitted: Literal[False] = False
    failed_partial_retained_as_immutable_v6_evidence: Literal[True] = True
    fresh_v7_target_request_required: Literal[True] = True
    request_marker_schema: Literal[
        "aurex-q1-periodic-flow-successor-http-request-v7"
    ] = "aurex-q1-periodic-flow-successor-http-request-v7"
    response_marker_schema: Literal[
        "aurex-q1-periodic-flow-successor-http-response-v7"
    ] = "aurex-q1-periodic-flow-successor-http-response-v7"
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_V7_EXECUTION_CONTRACT_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_V7_EXECUTION_CONTRACT_ONLY"

    @field_validator(
        "parent_v6_validator_amendment_file_sha256",
        "parent_v6_validator_amendment_evidence_hash",
        "parent_v6_contract_file_sha256",
        "parent_v6_contract_evidence_hash",
        "parent_v6_contract_audit_file_sha256",
        "parent_v6_contract_audit_evidence_hash",
        "terminal_v6_result_file_sha256",
        "terminal_v6_result_evidence_hash",
        "terminal_v6_checkpoint_file_sha256",
        "terminal_v6_checkpoint_evidence_hash",
        "terminal_v6_audit_file_sha256",
        "terminal_v6_audit_evidence_hash",
    )
    @classmethod
    def normalize_v6_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_v7_amendment(self) -> PeriodicFlowSuccessorTransportAmendmentV7:
        if (
            self.seed_total_new_archive_bytes + self.maximum_remaining_payload_bytes
            != self.inherited_maximum_new_archive_bytes_total
        ):
            raise ValueError("Q1 successor v7 remaining payload cap changed")
        return self


class PeriodicFlowSuccessorTransportAmendmentAuditV7(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-transport-amendment-audit-v7"
    ] = "aurex-q1-periodic-flow-successor-transport-amendment-audit-v7"
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    terminal_v6_audit_evidence_hash: str
    auditor_contract_hash: str
    exact_v6_checkpoint_seed_verified: Literal[True] = True
    failed_partial_non_adoption_verified: Literal[True] = True
    inherited_total_payload_cap_verified: Literal[True] = True
    inherited_validator_gates_verified: Literal[True] = True
    no_outcome_boundary_verified: Literal[True] = True
    network_requests_made: Literal[0] = 0
    outcomes_accessed: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "amendment_file_sha256",
        "amendment_evidence_hash",
        "terminal_v6_audit_evidence_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTransportAmendmentAuditV7:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v7 amendment audit hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractV7(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-v7"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-v7"
    contract_id: Literal["q1-periodic-flow-successor-execution-contract-v7"] = (
        "q1-periodic-flow-successor-execution-contract-v7"
    )
    frozen_at: datetime
    status: Literal["FROZEN_SOURCE_BOUND_PRE_V7_NETWORK"] = (
        "FROZEN_SOURCE_BOUND_PRE_V7_NETWORK"
    )
    amendment_file_sha256: str
    amendment_evidence_hash: str
    amendment_audit_file_sha256: str
    amendment_audit_evidence_hash: str
    runner_source_hash: str
    seed_v6_checkpoint_file_sha256: str
    seed_v6_checkpoint_evidence_hash: str
    seed_v6_result_file_sha256: str
    seed_v6_result_evidence_hash: str
    seed_v6_terminal_audit_file_sha256: str
    seed_v6_terminal_audit_evidence_hash: str
    seed_archive_count: Literal[56] = 56
    seed_paired_month_count: Literal[17] = 17
    seed_excluded_month_count: Literal[11] = 11
    seed_total_new_archive_bytes: Literal[30_282_986_798] = 30_282_986_798
    acquisition_root: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_v7"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_v7"
    checkpoint_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v7.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v7.json"
    result_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_result_v7.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_result_v7.json"
    processing_order: Literal[
        "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    ] = "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    seed_checkpoint_revalidation: Literal[
        "EXACT_FILE_SIZE_SHA256_EVIDENCE_HASH_AND_ALL_ARCHIVE_HASHES"
    ] = "EXACT_FILE_SIZE_SHA256_EVIDENCE_HASH_AND_ALL_ARCHIVE_HASHES"
    failed_v6_partial_adoption: Literal["FORBIDDEN"] = "FORBIDDEN"
    required_free_disk_bytes_before_acquisition: Literal[89_717_013_202] = (
        89_717_013_202
    )
    maximum_remaining_payload_bytes: Literal[69_717_013_202] = 69_717_013_202
    minimum_free_disk_bytes_after_acquisition: Literal[20_000_000_000] = (
        20_000_000_000
    )
    terminal_result_immutable: Literal[True] = True
    strategy_or_order_authority: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=12)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "amendment_file_sha256",
        "amendment_evidence_hash",
        "amendment_audit_file_sha256",
        "amendment_audit_evidence_hash",
        "runner_source_hash",
        "seed_v6_checkpoint_file_sha256",
        "seed_v6_checkpoint_evidence_hash",
        "seed_v6_result_file_sha256",
        "seed_v6_result_evidence_hash",
        "seed_v6_terminal_audit_file_sha256",
        "seed_v6_terminal_audit_evidence_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> PeriodicFlowSuccessorExecutionContractV7:
        if (
            self.required_free_disk_bytes_before_acquisition
            != self.maximum_remaining_payload_bytes
            + self.minimum_free_disk_bytes_after_acquisition
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor v7 execution contract changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("Q1 successor v7 execution contract hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractAuditV7(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-audit-v7"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-audit-v7"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    seed_checkpoint_verified: Literal[True] = True
    disk_and_payload_budget_verified: Literal[True] = True
    failed_partial_non_adoption_verified: Literal[True] = True
    no_outcome_boundary_verified: Literal[True] = True
    network_requests_made: Literal[0] = 0
    outcomes_accessed: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorExecutionContractAuditV7:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v7 contract audit hash changed")
        return self


class PeriodicFlowSuccessorCheckpointV7(PeriodicFlowSuccessorCheckpoint):
    schema_version: Literal["aurex-q1-periodic-flow-successor-checkpoint-v7"] = (
        "aurex-q1-periodic-flow-successor-checkpoint-v7"
    )
    checkpoint_id: Literal["q1-periodic-flow-successor-checkpoint-v7"] = (
        "q1-periodic-flow-successor-checkpoint-v7"
    )
    archive_evidence: tuple[PeriodicFlowArchiveEvidenceV6, ...]
    request_marker_count: int = Field(ge=0, le=1152)
    response_marker_count: int = Field(ge=0, le=1152)


class PeriodicFlowSuccessorAcquisitionResultV7(
    PeriodicFlowSuccessorAcquisitionResult
):
    schema_version: Literal["aurex-q1-periodic-flow-successor-result-v7"] = (
        "aurex-q1-periodic-flow-successor-result-v7"
    )
    result_id: Literal["q1-periodic-flow-successor-result-v7"] = (
        "q1-periodic-flow-successor-result-v7"
    )
    request_marker_count: int = Field(ge=0, le=1152)


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    data = provisional.model_dump()
    data[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(data)


def build_transport_amendment_v7(**values):
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorTransportAmendmentV7,
        "amendment_evidence_hash",
        payload,
    )


def build_transport_amendment_audit_v7(**values):
    return _build(
        PeriodicFlowSuccessorTransportAmendmentAuditV7,
        "audit_evidence_hash",
        values,
    )


def build_execution_contract_v7(**values):
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorExecutionContractV7,
        "contract_evidence_hash",
        payload,
    )


def build_execution_contract_audit_v7(**values):
    return _build(
        PeriodicFlowSuccessorExecutionContractAuditV7,
        "audit_evidence_hash",
        values,
    )


def build_checkpoint_v7(**values):
    payload = dict(values)
    for field, key in (
        ("archive_evidence", "key"),
        ("paired_month_evidence", "month"),
        ("excluded_month_evidence", "month"),
    ):
        payload[field] = tuple(sorted(payload[field], key=lambda item: getattr(item, key)))
    return _build(
        PeriodicFlowSuccessorCheckpointV7,
        "checkpoint_evidence_hash",
        payload,
    )


def build_acquisition_result_v7(**values):
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    hard_failed = payload.get("hard_failure_target_key") is not None
    sufficient = (
        not hard_failed
        and payload["completed_month_count"] == 37
        and payload["qualified_paired_month_count"] >= 30
        and all(
            payload["qualified_months_by_year"].get(str(year), 0) >= 6
            for year in range(2020, 2024)
        )
        and payload["qualified_quarter_count"] == 16
    )
    payload["decision"] = (
        "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        if hard_failed
        else (
            "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
            if sufficient
            else "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED"
        )
    )
    payload["next_authorization"] = {
        "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED": (
            "NONE_ACQUISITION_INTEGRITY_FAILED"
        ),
        "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL": (
            "AUTHORIZE_Q1_SUCCESSOR_PAIRED_MEASUREMENT_PROTOCOL_ONLY"
        ),
        "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED": (
            "NONE_SOURCE_SUFFICIENCY_FAILED"
        ),
    }[payload["decision"]]
    return _build(
        PeriodicFlowSuccessorAcquisitionResultV7,
        "result_evidence_hash",
        payload,
    )


def audit_hash(model: BaseModel, hash_field: str) -> bool:
    return getattr(model, hash_field) == universe_evidence_hash(
        model.model_dump(exclude={hash_field})
    )
