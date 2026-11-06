from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_successor_runner import (
    PeriodicFlowSuccessorAcquisitionResult,
    PeriodicFlowSuccessorCheckpoint,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorTransportAmendmentV5(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-transport-amendment-v5"
    ] = "aurex-q1-periodic-flow-successor-transport-amendment-v5"
    amendment_id: Literal["q1-periodic-flow-successor-transport-amendment-v5"] = (
        "q1-periodic-flow-successor-transport-amendment-v5"
    )
    frozen_at: datetime
    status: Literal["FROZEN_POST_V4_TERMINAL_PRE_NETWORK"] = (
        "FROZEN_POST_V4_TERMINAL_PRE_NETWORK"
    )
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    parent_v4_amendment_file_sha256: str
    parent_v4_amendment_evidence_hash: str
    parent_v4_contract_file_sha256: str
    parent_v4_contract_evidence_hash: str
    parent_v4_contract_audit_file_sha256: str
    parent_v4_contract_audit_evidence_hash: str
    terminal_v4_result_file_sha256: str
    terminal_v4_result_evidence_hash: str
    terminal_v4_checkpoint_file_sha256: str
    terminal_v4_checkpoint_evidence_hash: str
    terminal_v4_audit_file_sha256: str
    terminal_v4_audit_evidence_hash: str
    inherited_source_manifest_unchanged: Literal[True] = True
    inherited_structural_gates_unchanged: Literal[True] = True
    inherited_sufficiency_gates_unchanged: Literal[True] = True
    inherited_byte_and_disk_caps_unchanged: Literal[True] = True
    checkpoint_only_seed: Literal[True] = True
    bootstrap_partial_permitted: Literal[False] = False
    range_requests_permitted: Literal[True] = True
    partial_resume_permitted: Literal[True] = True
    head_requests_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    dns_resolution_before_each_network_target: Literal[True] = True
    maximum_dns_checks_per_network_target: Literal[12] = 12
    dns_retry_delays_seconds: tuple[int, ...] = (
        5,
        20,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
    )
    maximum_get_attempts_per_target: Literal[24] = 24
    maximum_payload_get_attempts: Literal[1152] = 1152
    retry_delays_seconds: tuple[int, ...] = (
        5,
        20,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
        60,
    )
    connect_timeout_seconds: Literal[300] = 300
    idle_read_timeout_seconds: Literal[300] = 300
    total_attempt_deadline_seconds: Literal[21_600] = 21_600
    stream_chunk_bytes: Literal[65_536] = 65_536
    request_marker_schema: Literal[
        "aurex-q1-periodic-flow-successor-http-request-v5"
    ] = "aurex-q1-periodic-flow-successor-http-request-v5"
    response_marker_schema: Literal[
        "aurex-q1-periodic-flow-successor-http-response-v5"
    ] = "aurex-q1-periodic-flow-successor-http-response-v5"
    partial_preserved_after_transient_failure: Literal[True] = True
    completed_archive_requires_published_sha256: Literal[True] = True
    prior_evidence_generations_immutable: Literal[True] = True
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    strategy_or_order_authority: Literal[False] = False
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_V5_EXECUTION_CONTRACT_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_V5_EXECUTION_CONTRACT_ONLY"
    limitations: tuple[str, ...] = Field(min_length=10)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_protocol_file_sha256",
        "parent_protocol_evidence_hash",
        "parent_v4_amendment_file_sha256",
        "parent_v4_amendment_evidence_hash",
        "parent_v4_contract_file_sha256",
        "parent_v4_contract_evidence_hash",
        "parent_v4_contract_audit_file_sha256",
        "parent_v4_contract_audit_evidence_hash",
        "terminal_v4_result_file_sha256",
        "terminal_v4_result_evidence_hash",
        "terminal_v4_checkpoint_file_sha256",
        "terminal_v4_checkpoint_evidence_hash",
        "terminal_v4_audit_file_sha256",
        "terminal_v4_audit_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> PeriodicFlowSuccessorTransportAmendmentV5:
        if (
            len(self.dns_retry_delays_seconds)
            != self.maximum_dns_checks_per_network_target - 1
            or len(self.retry_delays_seconds)
            != self.maximum_get_attempts_per_target - 1
            or self.maximum_payload_get_attempts
            != self.maximum_get_attempts_per_target * 48
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor v5 transport amendment changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("Q1 successor v5 transport amendment hash changed")
        return self


class PeriodicFlowSuccessorTransportAmendmentAuditV5(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-transport-amendment-audit-v5"
    ] = "aurex-q1-periodic-flow-successor-transport-amendment-audit-v5"
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    terminal_v4_audit_evidence_hash: str
    auditor_contract_hash: str
    checkpoint_only_scope_verified: Literal[True] = True
    dns_resilience_scope_verified: Literal[True] = True
    inherited_gates_verified: Literal[True] = True
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
        "terminal_v4_audit_evidence_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTransportAmendmentAuditV5:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v5 amendment audit hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractV5(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-v5"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-v5"
    contract_id: Literal["q1-periodic-flow-successor-execution-contract-v5"] = (
        "q1-periodic-flow-successor-execution-contract-v5"
    )
    frozen_at: datetime
    status: Literal["FROZEN_SOURCE_BOUND_PRE_V5_NETWORK"] = (
        "FROZEN_SOURCE_BOUND_PRE_V5_NETWORK"
    )
    amendment_file_sha256: str
    amendment_evidence_hash: str
    amendment_audit_file_sha256: str
    amendment_audit_evidence_hash: str
    runner_source_hash: str
    seed_v4_checkpoint_file_sha256: str
    seed_v4_checkpoint_evidence_hash: str
    seed_v4_result_file_sha256: str
    seed_v4_result_evidence_hash: str
    seed_v4_terminal_audit_file_sha256: str
    seed_v4_terminal_audit_evidence_hash: str
    seed_archive_count: Literal[45] = 45
    seed_paired_month_count: Literal[16] = 16
    seed_excluded_month_count: Literal[6] = 6
    acquisition_root: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_v5"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_v5"
    checkpoint_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v5.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v5.json"
    result_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_result_v5.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_result_v5.json"
    processing_order: Literal[
        "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    ] = "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    seed_checkpoint_revalidation: Literal[
        "EXACT_FILE_SIZE_AND_SHA256_BEFORE_USE"
    ] = "EXACT_FILE_SIZE_AND_SHA256_BEFORE_USE"
    interrupted_request_reconciliation: Literal[
        "WRITE_RESUMABLE_RESPONSE_FROM_PARTIAL_DELTA"
    ] = "WRITE_RESUMABLE_RESPONSE_FROM_PARTIAL_DELTA"
    terminal_result_immutable: Literal[True] = True
    required_free_disk_bytes_before_acquisition: Literal[120_000_000_000] = (
        120_000_000_000
    )
    strategy_or_order_authority: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=10)
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
        "seed_v4_checkpoint_file_sha256",
        "seed_v4_checkpoint_evidence_hash",
        "seed_v4_result_file_sha256",
        "seed_v4_result_evidence_hash",
        "seed_v4_terminal_audit_file_sha256",
        "seed_v4_terminal_audit_evidence_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> PeriodicFlowSuccessorExecutionContractV5:
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("Q1 successor v5 execution contract changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("Q1 successor v5 execution contract hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractAuditV5(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-audit-v5"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-audit-v5"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    seed_checkpoint_verified: Literal[True] = True
    dns_resilience_verified: Literal[True] = True
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
    def validate_audit(self) -> PeriodicFlowSuccessorExecutionContractAuditV5:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v5 contract audit hash changed")
        return self


class PeriodicFlowSuccessorCheckpointV5(PeriodicFlowSuccessorCheckpoint):
    schema_version: Literal["aurex-q1-periodic-flow-successor-checkpoint-v5"] = (
        "aurex-q1-periodic-flow-successor-checkpoint-v5"
    )
    checkpoint_id: Literal["q1-periodic-flow-successor-checkpoint-v5"] = (
        "q1-periodic-flow-successor-checkpoint-v5"
    )
    request_marker_count: int = Field(ge=0, le=1152)
    response_marker_count: int = Field(ge=0, le=1152)


class PeriodicFlowSuccessorAcquisitionResultV5(
    PeriodicFlowSuccessorAcquisitionResult
):
    schema_version: Literal["aurex-q1-periodic-flow-successor-result-v5"] = (
        "aurex-q1-periodic-flow-successor-result-v5"
    )
    result_id: Literal["q1-periodic-flow-successor-result-v5"] = (
        "q1-periodic-flow-successor-result-v5"
    )
    request_marker_count: int = Field(ge=0, le=1152)


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    data = provisional.model_dump()
    data[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(data)


def build_transport_amendment_v5(**values):
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorTransportAmendmentV5,
        "amendment_evidence_hash",
        payload,
    )


def build_transport_amendment_audit_v5(**values):
    return _build(
        PeriodicFlowSuccessorTransportAmendmentAuditV5,
        "audit_evidence_hash",
        values,
    )


def build_execution_contract_v5(**values):
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorExecutionContractV5,
        "contract_evidence_hash",
        payload,
    )


def build_execution_contract_audit_v5(**values):
    return _build(
        PeriodicFlowSuccessorExecutionContractAuditV5,
        "audit_evidence_hash",
        values,
    )


def build_checkpoint_v5(**values):
    payload = dict(values)
    for field, key in (
        ("archive_evidence", "key"),
        ("paired_month_evidence", "month"),
        ("excluded_month_evidence", "month"),
    ):
        payload[field] = tuple(sorted(payload[field], key=lambda item: getattr(item, key)))
    return _build(
        PeriodicFlowSuccessorCheckpointV5,
        "checkpoint_evidence_hash",
        payload,
    )


def build_acquisition_result_v5(**values):
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
        PeriodicFlowSuccessorAcquisitionResultV5,
        "result_evidence_hash",
        payload,
    )


def audit_hash(model: BaseModel, hash_field: str) -> bool:
    return getattr(model, hash_field) == universe_evidence_hash(
        model.model_dump(exclude={hash_field})
    )
