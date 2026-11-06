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


class PeriodicFlowSuccessorTransportAmendmentV4(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-transport-amendment-v4"
    ] = "aurex-q1-periodic-flow-successor-transport-amendment-v4"
    amendment_id: Literal["q1-periodic-flow-successor-transport-amendment-v4"] = (
        "q1-periodic-flow-successor-transport-amendment-v4"
    )
    frozen_at: datetime
    status: Literal["FROZEN_POST_V3_TERMINAL_PRE_NETWORK"] = (
        "FROZEN_POST_V3_TERMINAL_PRE_NETWORK"
    )
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    parent_v3_amendment_file_sha256: str
    parent_v3_amendment_evidence_hash: str
    parent_v3_contract_file_sha256: str
    parent_v3_contract_evidence_hash: str
    parent_v3_contract_audit_file_sha256: str
    parent_v3_contract_audit_evidence_hash: str
    terminal_v3_result_file_sha256: str
    terminal_v3_result_evidence_hash: str
    terminal_v3_checkpoint_file_sha256: str
    terminal_v3_checkpoint_evidence_hash: str
    terminal_v3_audit_file_sha256: str
    terminal_v3_audit_evidence_hash: str
    bootstrap_partial_path: str
    bootstrap_partial_file_sha256: str
    bootstrap_partial_bytes: Literal[86_150_831] = 86_150_831
    bootstrap_target_key: Literal["2020-08|USD_M_PERPETUAL"] = (
        "2020-08|USD_M_PERPETUAL"
    )
    bootstrap_expected_total_bytes: Literal[228_784_150] = 228_784_150
    inherited_source_manifest_unchanged: Literal[True] = True
    inherited_structural_gates_unchanged: Literal[True] = True
    inherited_sufficiency_gates_unchanged: Literal[True] = True
    inherited_byte_and_disk_caps_unchanged: Literal[True] = True
    exact_bootstrap_partial_copy_permitted: Literal[True] = True
    range_requests_permitted: Literal[True] = True
    partial_resume_permitted: Literal[True] = True
    head_requests_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    dns_resolution_preflight_required: Literal[True] = True
    maximum_get_attempts_per_target: Literal[12] = 12
    maximum_payload_get_attempts: Literal[576] = 576
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
    )
    connect_timeout_seconds: Literal[300] = 300
    idle_read_timeout_seconds: Literal[300] = 300
    total_attempt_deadline_seconds: Literal[21_600] = 21_600
    stream_chunk_bytes: Literal[65_536] = 65_536
    request_marker_schema: Literal[
        "aurex-q1-periodic-flow-successor-http-request-v4"
    ] = "aurex-q1-periodic-flow-successor-http-request-v4"
    response_marker_schema: Literal[
        "aurex-q1-periodic-flow-successor-http-response-v4"
    ] = "aurex-q1-periodic-flow-successor-http-response-v4"
    partial_preserved_after_transient_failure: Literal[True] = True
    completed_archive_requires_published_sha256: Literal[True] = True
    v1_v2_and_v3_evidence_immutable: Literal[True] = True
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    strategy_or_order_authority: Literal[False] = False
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_V4_EXECUTION_CONTRACT_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_V4_EXECUTION_CONTRACT_ONLY"
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
        "parent_v3_amendment_file_sha256",
        "parent_v3_amendment_evidence_hash",
        "parent_v3_contract_file_sha256",
        "parent_v3_contract_evidence_hash",
        "parent_v3_contract_audit_file_sha256",
        "parent_v3_contract_audit_evidence_hash",
        "terminal_v3_result_file_sha256",
        "terminal_v3_result_evidence_hash",
        "terminal_v3_checkpoint_file_sha256",
        "terminal_v3_checkpoint_evidence_hash",
        "terminal_v3_audit_file_sha256",
        "terminal_v3_audit_evidence_hash",
        "bootstrap_partial_file_sha256",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> PeriodicFlowSuccessorTransportAmendmentV4:
        if (
            len(self.retry_delays_seconds)
            != self.maximum_get_attempts_per_target - 1
            or self.maximum_payload_get_attempts
            != self.maximum_get_attempts_per_target * 48
            or self.bootstrap_partial_bytes >= self.bootstrap_expected_total_bytes
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor v4 transport amendment changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("Q1 successor v4 transport amendment hash changed")
        return self


class PeriodicFlowSuccessorTransportAmendmentAuditV4(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-transport-amendment-audit-v4"
    ] = "aurex-q1-periodic-flow-successor-transport-amendment-audit-v4"
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    parent_protocol_evidence_hash: str
    terminal_v3_audit_evidence_hash: str
    bootstrap_partial_file_sha256: str
    bootstrap_partial_bytes: Literal[86_150_831] = 86_150_831
    auditor_contract_hash: str
    exact_override_scope_verified: Literal[True] = True
    terminal_lineage_verified: Literal[True] = True
    bootstrap_partial_verified: Literal[True] = True
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
        "parent_protocol_evidence_hash",
        "terminal_v3_audit_evidence_hash",
        "bootstrap_partial_file_sha256",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTransportAmendmentAuditV4:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v4 transport amendment audit changed")
        return self


class PeriodicFlowSuccessorExecutionContractV4(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-v4"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-v4"
    contract_id: Literal["q1-periodic-flow-successor-execution-contract-v4"] = (
        "q1-periodic-flow-successor-execution-contract-v4"
    )
    frozen_at: datetime
    status: Literal["FROZEN_SOURCE_BOUND_PRE_V4_NETWORK"] = (
        "FROZEN_SOURCE_BOUND_PRE_V4_NETWORK"
    )
    amendment_file_sha256: str
    amendment_evidence_hash: str
    amendment_audit_file_sha256: str
    amendment_audit_evidence_hash: str
    runner_source_hash: str
    seed_v3_checkpoint_file_sha256: str
    seed_v3_checkpoint_evidence_hash: str
    seed_v3_result_file_sha256: str
    seed_v3_result_evidence_hash: str
    seed_v3_terminal_audit_file_sha256: str
    seed_v3_terminal_audit_evidence_hash: str
    seed_archive_count: Literal[7] = 7
    seed_paired_month_count: Literal[2] = 2
    seed_excluded_month_count: Literal[1] = 1
    acquisition_root: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_v4"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_v4"
    checkpoint_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v4.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v4.json"
    result_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_result_v4.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_result_v4.json"
    processing_order: Literal[
        "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    ] = "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    seed_checkpoint_revalidation: Literal[
        "EXACT_FILE_SIZE_AND_SHA256_BEFORE_USE"
    ] = "EXACT_FILE_SIZE_AND_SHA256_BEFORE_USE"
    bootstrap_partial_policy: Literal[
        "ATOMIC_COPY_EXACT_V3_PARTIAL_THEN_STRICT_RANGE_RESUME"
    ] = "ATOMIC_COPY_EXACT_V3_PARTIAL_THEN_STRICT_RANGE_RESUME"
    interrupted_request_reconciliation: Literal[
        "WRITE_RESUMABLE_RESPONSE_FROM_PARTIAL_DELTA"
    ] = "WRITE_RESUMABLE_RESPONSE_FROM_PARTIAL_DELTA"
    range_response_policy: Literal[
        "OFFSET_ZERO_REQUIRES_200_OFFSET_POSITIVE_REQUIRES_EXACT_206_CONTENT_RANGE"
    ] = "OFFSET_ZERO_REQUIRES_200_OFFSET_POSITIVE_REQUIRES_EXACT_206_CONTENT_RANGE"
    checkpoint_write_policy: Literal[
        "ATOMIC_AFTER_EACH_INSPECTION_EXCLUSION_AND_PAIRED_MONTH"
    ] = "ATOMIC_AFTER_EACH_INSPECTION_EXCLUSION_AND_PAIRED_MONTH"
    terminal_result_immutable: Literal[True] = True
    required_free_disk_bytes_before_acquisition: Literal[120_000_000_000] = (
        120_000_000_000
    )
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
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
        "seed_v3_checkpoint_file_sha256",
        "seed_v3_checkpoint_evidence_hash",
        "seed_v3_result_file_sha256",
        "seed_v3_result_evidence_hash",
        "seed_v3_terminal_audit_file_sha256",
        "seed_v3_terminal_audit_evidence_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> PeriodicFlowSuccessorExecutionContractV4:
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("Q1 successor v4 execution contract changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("Q1 successor v4 execution contract hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractAuditV4(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-audit-v4"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-audit-v4"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    amendment_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    seed_checkpoint_verified: Literal[True] = True
    bootstrap_partial_verified: Literal[True] = True
    resumable_transport_verified: Literal[True] = True
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
        "amendment_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorExecutionContractAuditV4:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v4 execution contract audit changed")
        return self


class PeriodicFlowSuccessorCheckpointV4(PeriodicFlowSuccessorCheckpoint):
    schema_version: Literal["aurex-q1-periodic-flow-successor-checkpoint-v4"] = (
        "aurex-q1-periodic-flow-successor-checkpoint-v4"
    )
    checkpoint_id: Literal["q1-periodic-flow-successor-checkpoint-v4"] = (
        "q1-periodic-flow-successor-checkpoint-v4"
    )
    request_marker_count: int = Field(ge=0, le=576)
    response_marker_count: int = Field(ge=0, le=576)


class PeriodicFlowSuccessorAcquisitionResultV4(
    PeriodicFlowSuccessorAcquisitionResult
):
    schema_version: Literal["aurex-q1-periodic-flow-successor-result-v4"] = (
        "aurex-q1-periodic-flow-successor-result-v4"
    )
    result_id: Literal["q1-periodic-flow-successor-result-v4"] = (
        "q1-periodic-flow-successor-result-v4"
    )
    request_marker_count: int = Field(ge=0, le=576)


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    data = provisional.model_dump()
    data[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(data)


def build_transport_amendment_v4(
    **values,
) -> PeriodicFlowSuccessorTransportAmendmentV4:
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorTransportAmendmentV4,
        "amendment_evidence_hash",
        payload,
    )


def build_transport_amendment_audit_v4(
    **values,
) -> PeriodicFlowSuccessorTransportAmendmentAuditV4:
    return _build(
        PeriodicFlowSuccessorTransportAmendmentAuditV4,
        "audit_evidence_hash",
        values,
    )


def build_execution_contract_v4(
    **values,
) -> PeriodicFlowSuccessorExecutionContractV4:
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorExecutionContractV4,
        "contract_evidence_hash",
        payload,
    )


def build_execution_contract_audit_v4(
    **values,
) -> PeriodicFlowSuccessorExecutionContractAuditV4:
    return _build(
        PeriodicFlowSuccessorExecutionContractAuditV4,
        "audit_evidence_hash",
        values,
    )


def build_checkpoint_v4(**values) -> PeriodicFlowSuccessorCheckpointV4:
    payload = dict(values)
    payload["archive_evidence"] = tuple(
        sorted(payload["archive_evidence"], key=lambda item: item.key)
    )
    payload["paired_month_evidence"] = tuple(
        sorted(payload["paired_month_evidence"], key=lambda item: item.month)
    )
    payload["excluded_month_evidence"] = tuple(
        sorted(payload["excluded_month_evidence"], key=lambda item: item.month)
    )
    return _build(
        PeriodicFlowSuccessorCheckpointV4,
        "checkpoint_evidence_hash",
        payload,
    )


def build_acquisition_result_v4(
    **values,
) -> PeriodicFlowSuccessorAcquisitionResultV4:
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
        PeriodicFlowSuccessorAcquisitionResultV4,
        "result_evidence_hash",
        payload,
    )


def audit_hash(model: BaseModel, hash_field: str) -> bool:
    return getattr(model, hash_field) == universe_evidence_hash(
        model.model_dump(exclude={hash_field})
    )
