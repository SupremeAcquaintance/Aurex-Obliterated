from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_full_development_runner import (
    PeriodicFlowArchiveEvidence,
)
from aurex.backtest_engine.periodic_flow_successor_runner import (
    PeriodicFlowSuccessorAcquisitionResult,
    PeriodicFlowSuccessorCheckpoint,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorValidatorAmendmentV6(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-validator-amendment-v6"
    ] = "aurex-q1-periodic-flow-successor-validator-amendment-v6"
    amendment_id: Literal["q1-periodic-flow-successor-validator-amendment-v6"] = (
        "q1-periodic-flow-successor-validator-amendment-v6"
    )
    frozen_at: datetime
    status: Literal["FROZEN_POST_V5_TERMINAL_PRE_V6_NETWORK"] = (
        "FROZEN_POST_V5_TERMINAL_PRE_V6_NETWORK"
    )
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    parent_v5_amendment_file_sha256: str
    parent_v5_amendment_evidence_hash: str
    parent_v5_contract_file_sha256: str
    parent_v5_contract_evidence_hash: str
    parent_v5_contract_audit_file_sha256: str
    parent_v5_contract_audit_evidence_hash: str
    terminal_v5_result_file_sha256: str
    terminal_v5_result_evidence_hash: str
    terminal_v5_checkpoint_file_sha256: str
    terminal_v5_checkpoint_evidence_hash: str
    terminal_v5_audit_file_sha256: str
    terminal_v5_audit_evidence_hash: str
    inherited_source_manifest_unchanged: Literal[True] = True
    inherited_transport_rules_unchanged: Literal[True] = True
    inherited_structural_gates_unchanged_except_validator_domain: Literal[True] = True
    inherited_sufficiency_gates_unchanged: Literal[True] = True
    checkpoint_only_seed: Literal[True] = True
    terminal_archive_reuse_requires_exact_published_sha256: Literal[True] = True
    terminal_archive_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_v5/BTCUSDT/"
        "2023-01/trades/BTCUSDT-trades-2023-01.zip"
    ] = (
        "data/evidence/q1_periodic_flow_successor_acquisition_v5/BTCUSDT/"
        "2023-01/trades/BTCUSDT-trades-2023-01.zip"
    )
    terminal_archive_sha256: Literal[
        "d5c30a110f8f40c375cfef5b4fff922a1f21eeac58e53899d05166baaff2ca2d"
    ] = "d5c30a110f8f40c375cfef5b4fff922a1f21eeac58e53899d05166baaff2ca2d"
    terminal_archive_bytes: Literal[797_254_027] = 797_254_027
    unordered_domain: Literal[
        "USD_M_PERPETUAL_WITH_PRIMARY_ID_NON_INCREASING_COUNT_ABOVE_ZERO"
    ] = "USD_M_PERPETUAL_WITH_PRIMARY_ID_NON_INCREASING_COUNT_ABOVE_ZERO"
    unordered_gap_metric_policy: Literal[
        "NOT_APPLICABLE_ENCODE_FORWARD_GAP_SKIP_COUNT_SKIP_FRACTION_MAX_SKIP_AS_ZERO"
    ] = (
        "NOT_APPLICABLE_ENCODE_FORWARD_GAP_SKIP_COUNT_SKIP_FRACTION_MAX_SKIP_AS_ZERO"
    )
    unordered_archive_decision: Literal[
        "EXCLUDE_WHOLE_MONTH_PRIMARY_ID_NOT_STRICTLY_INCREASING"
    ] = "EXCLUDE_WHOLE_MONTH_PRIMARY_ID_NOT_STRICTLY_INCREASING"
    source_row_reordering_permitted: Literal[False] = False
    source_row_sorting_permitted: Literal[False] = False
    source_row_dropping_permitted: Literal[False] = False
    source_row_synthesis_permitted: Literal[False] = False
    ordered_archive_gap_rules_unchanged: Literal[True] = True
    spot_archive_rules_unchanged: Literal[True] = True
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    strategy_or_order_authority: Literal[False] = False
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_V6_EXECUTION_CONTRACT_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_V6_EXECUTION_CONTRACT_ONLY"
    limitations: tuple[str, ...] = Field(min_length=12)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_protocol_file_sha256",
        "parent_protocol_evidence_hash",
        "parent_v5_amendment_file_sha256",
        "parent_v5_amendment_evidence_hash",
        "parent_v5_contract_file_sha256",
        "parent_v5_contract_evidence_hash",
        "parent_v5_contract_audit_file_sha256",
        "parent_v5_contract_audit_evidence_hash",
        "terminal_v5_result_file_sha256",
        "terminal_v5_result_evidence_hash",
        "terminal_v5_checkpoint_file_sha256",
        "terminal_v5_checkpoint_evidence_hash",
        "terminal_v5_audit_file_sha256",
        "terminal_v5_audit_evidence_hash",
        "terminal_archive_sha256",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> PeriodicFlowSuccessorValidatorAmendmentV6:
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("Q1 successor v6 validator amendment changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("Q1 successor v6 validator amendment hash changed")
        return self


class PeriodicFlowSuccessorValidatorAmendmentAuditV6(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-validator-amendment-audit-v6"
    ] = "aurex-q1-periodic-flow-successor-validator-amendment-audit-v6"
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    terminal_v5_audit_evidence_hash: str
    auditor_contract_hash: str
    validator_domain_narrowing_verified: Literal[True] = True
    no_source_mutation_verified: Literal[True] = True
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
        "terminal_v5_audit_evidence_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorValidatorAmendmentAuditV6:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v6 amendment audit hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractV6(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-v6"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-v6"
    contract_id: Literal["q1-periodic-flow-successor-execution-contract-v6"] = (
        "q1-periodic-flow-successor-execution-contract-v6"
    )
    frozen_at: datetime
    status: Literal["FROZEN_SOURCE_BOUND_PRE_V6_NETWORK"] = (
        "FROZEN_SOURCE_BOUND_PRE_V6_NETWORK"
    )
    amendment_file_sha256: str
    amendment_evidence_hash: str
    amendment_audit_file_sha256: str
    amendment_audit_evidence_hash: str
    runner_source_hash: str
    seed_v5_checkpoint_file_sha256: str
    seed_v5_checkpoint_evidence_hash: str
    seed_v5_result_file_sha256: str
    seed_v5_result_evidence_hash: str
    seed_v5_terminal_audit_file_sha256: str
    seed_v5_terminal_audit_evidence_hash: str
    seed_archive_count: Literal[51] = 51
    seed_paired_month_count: Literal[17] = 17
    seed_excluded_month_count: Literal[8] = 8
    acquisition_root: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_v6"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_v6"
    checkpoint_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v6.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v6.json"
    result_path: Literal[
        "data/evidence/q1_periodic_flow_successor_acquisition_result_v6.json"
    ] = "data/evidence/q1_periodic_flow_successor_acquisition_result_v6.json"
    processing_order: Literal[
        "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    ] = "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    seed_checkpoint_revalidation: Literal[
        "EXACT_FILE_SIZE_SHA256_PLUS_V5_EVIDENCE_AND_TERMINAL_AUDIT_HASHES"
    ] = "EXACT_FILE_SIZE_SHA256_PLUS_V5_EVIDENCE_AND_TERMINAL_AUDIT_HASHES"
    terminal_archive_adoption: Literal[
        "EXACT_PUBLISHED_SHA256_THEN_V6_STRUCTURAL_REINSPECTION"
    ] = "EXACT_PUBLISHED_SHA256_THEN_V6_STRUCTURAL_REINSPECTION"
    terminal_result_immutable: Literal[True] = True
    required_free_disk_bytes_before_acquisition: Literal[120_000_000_000] = (
        120_000_000_000
    )
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
        "seed_v5_checkpoint_file_sha256",
        "seed_v5_checkpoint_evidence_hash",
        "seed_v5_result_file_sha256",
        "seed_v5_result_evidence_hash",
        "seed_v5_terminal_audit_file_sha256",
        "seed_v5_terminal_audit_evidence_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> PeriodicFlowSuccessorExecutionContractV6:
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("Q1 successor v6 execution contract changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("Q1 successor v6 execution contract hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractAuditV6(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-audit-v6"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-audit-v6"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    seed_checkpoint_verified: Literal[True] = True
    terminal_archive_verified: Literal[True] = True
    validator_scope_verified: Literal[True] = True
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
    def validate_audit(self) -> PeriodicFlowSuccessorExecutionContractAuditV6:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v6 contract audit hash changed")
        return self


class PeriodicFlowArchiveEvidenceV6(PeriodicFlowArchiveEvidence):
    payload_get_attempt_count: int = Field(ge=0, le=24)


class PeriodicFlowSuccessorCheckpointV6(PeriodicFlowSuccessorCheckpoint):
    schema_version: Literal["aurex-q1-periodic-flow-successor-checkpoint-v6"] = (
        "aurex-q1-periodic-flow-successor-checkpoint-v6"
    )
    checkpoint_id: Literal["q1-periodic-flow-successor-checkpoint-v6"] = (
        "q1-periodic-flow-successor-checkpoint-v6"
    )
    archive_evidence: tuple[PeriodicFlowArchiveEvidenceV6, ...]
    request_marker_count: int = Field(ge=0, le=1152)
    response_marker_count: int = Field(ge=0, le=1152)


class PeriodicFlowSuccessorAcquisitionResultV6(
    PeriodicFlowSuccessorAcquisitionResult
):
    schema_version: Literal["aurex-q1-periodic-flow-successor-result-v6"] = (
        "aurex-q1-periodic-flow-successor-result-v6"
    )
    result_id: Literal["q1-periodic-flow-successor-result-v6"] = (
        "q1-periodic-flow-successor-result-v6"
    )
    request_marker_count: int = Field(ge=0, le=1152)


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    data = provisional.model_dump()
    data[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(data)


def build_validator_amendment_v6(**values):
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorValidatorAmendmentV6,
        "amendment_evidence_hash",
        payload,
    )


def build_validator_amendment_audit_v6(**values):
    return _build(
        PeriodicFlowSuccessorValidatorAmendmentAuditV6,
        "audit_evidence_hash",
        values,
    )


def build_execution_contract_v6(**values):
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorExecutionContractV6,
        "contract_evidence_hash",
        payload,
    )


def build_execution_contract_audit_v6(**values):
    return _build(
        PeriodicFlowSuccessorExecutionContractAuditV6,
        "audit_evidence_hash",
        values,
    )


def build_checkpoint_v6(**values):
    payload = dict(values)
    for field, key in (
        ("archive_evidence", "key"),
        ("paired_month_evidence", "month"),
        ("excluded_month_evidence", "month"),
    ):
        payload[field] = tuple(sorted(payload[field], key=lambda item: getattr(item, key)))
    return _build(
        PeriodicFlowSuccessorCheckpointV6,
        "checkpoint_evidence_hash",
        payload,
    )


def build_acquisition_result_v6(**values):
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
        PeriodicFlowSuccessorAcquisitionResultV6,
        "result_evidence_hash",
        payload,
    )


def audit_hash(model: BaseModel, hash_field: str) -> bool:
    return getattr(model, hash_field) == universe_evidence_hash(
        model.model_dump(exclude={hash_field})
    )
