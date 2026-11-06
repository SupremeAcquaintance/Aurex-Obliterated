from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    PeriodicFlowDevelopmentTarget,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorAcquisitionProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-acquisition-protocol-v1"
    ] = "aurex-q1-periodic-flow-successor-acquisition-protocol-v1"
    protocol_id: Literal["q1-periodic-flow-successor-acquisition-protocol-v1"] = (
        "q1-periodic-flow-successor-acquisition-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_SUCCESSOR_ACQUISITION"] = (
        "FROZEN_PRE_SUCCESSOR_ACQUISITION"
    )
    authorization_record: Literal[
        "SOURCE_QUALITY_CENSUS_AUTHORIZED_SUCCESSOR_ACQUISITION_PROTOCOL_ONLY"
    ] = "SOURCE_QUALITY_CENSUS_AUTHORIZED_SUCCESSOR_ACQUISITION_PROTOCOL_ONLY"
    parent_census_result_file_sha256: str
    parent_census_result_evidence_hash: str
    parent_census_audit_file_sha256: str
    parent_census_audit_evidence_hash: str
    parent_v1_protocol_file_sha256: str
    parent_v1_protocol_evidence_hash: str
    terminal_audit_file_sha256: str
    terminal_audit_evidence_hash: str
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    development_start_month: Literal["2020-01"] = "2020-01"
    development_end_month: Literal["2023-12"] = "2023-12"
    known_eligible_months: tuple[str, ...] = Field(min_length=25, max_length=25)
    known_excluded_months: tuple[str, ...] = Field(min_length=11, max_length=11)
    unknown_spot_first_months: tuple[str, ...] = Field(min_length=12, max_length=12)
    targets: tuple[PeriodicFlowDevelopmentTarget, ...] = Field(
        min_length=74, max_length=74
    )
    target_count: Literal[74] = 74
    reuse_candidate_count: Literal[26] = 26
    maximum_network_target_count: Literal[48] = 48
    processing_order: Literal[
        "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    ] = "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    known_failed_month_policy: Literal["ABSENT_FROM_TARGET_MANIFEST"] = (
        "ABSENT_FROM_TARGET_MANIFEST"
    )
    structural_failure_policy: Literal[
        "EXCLUDE_MONTH_RECORD_EVIDENCE_CONTINUE_WITH_NEXT_MONTH"
    ] = "EXCLUDE_MONTH_RECORD_EVIDENCE_CONTINUE_WITH_NEXT_MONTH"
    transport_or_integrity_failure_policy: Literal[
        "HARD_STOP_PRESERVE_CHECKPOINT_NO_SILENT_SKIP"
    ] = "HARD_STOP_PRESERVE_CHECKPOINT_NO_SILENT_SKIP"
    minimum_minute_coverage_fraction: Decimal = Field(
        default=Decimal("0.99"), ge=Decimal("0.99"), le=Decimal("0.99")
    )
    maximum_event_gap_minutes: Literal[15] = 15
    minimum_paired_minute_coverage_fraction: Decimal = Field(
        default=Decimal("0.99"), ge=Decimal("0.99"), le=Decimal("0.99")
    )
    minimum_qualifying_paired_months: Literal[30] = 30
    minimum_qualifying_months_per_year: Literal[6] = 6
    minimum_qualifying_months_per_quarter: Literal[1] = 1
    maximum_archive_bytes: Literal[5_000_000_000] = 5_000_000_000
    maximum_new_archive_bytes_total: Literal[100_000_000_000] = 100_000_000_000
    maximum_member_uncompressed_bytes: Literal[30_000_000_000] = 30_000_000_000
    maximum_total_member_uncompressed_bytes: Literal[1_000_000_000_000] = (
        1_000_000_000_000
    )
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_free_disk_bytes_after_acquisition: Literal[20_000_000_000] = (
        20_000_000_000
    )
    one_archive_at_a_time: Literal[True] = True
    stream_to_partial_then_atomic_rename: Literal[True] = True
    request_and_response_markers_required: Literal[True] = True
    checkpoint_after_each_archive_and_month: Literal[True] = True
    partial_file_reuse_permitted: Literal[False] = False
    head_requests_permitted: Literal[False] = False
    range_requests_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    pine_deployment_permitted: Literal[False] = False
    paper_operation_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_ACQUISITION_EXECUTION_CONTRACT_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_ACQUISITION_EXECUTION_CONTRACT_ONLY"
    limitations: tuple[str, ...] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_census_result_file_sha256",
        "parent_census_result_evidence_hash",
        "parent_census_audit_file_sha256",
        "parent_census_audit_evidence_hash",
        "parent_v1_protocol_file_sha256",
        "parent_v1_protocol_evidence_hash",
        "terminal_audit_file_sha256",
        "terminal_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> PeriodicFlowSuccessorAcquisitionProtocol:
        keys = [item.key for item in self.targets]
        target_months = tuple(sorted({item.month for item in self.targets}))
        expected_months = self.known_eligible_months + self.unknown_spot_first_months
        if (
            self.known_eligible_months != tuple(sorted(set(self.known_eligible_months)))
            or self.known_excluded_months != tuple(sorted(set(self.known_excluded_months)))
            or self.unknown_spot_first_months
            != tuple(sorted(set(self.unknown_spot_first_months)))
            or set(self.known_eligible_months) & set(self.known_excluded_months)
            or keys != sorted(keys)
            or len(keys) != len(set(keys))
            or target_months != expected_months
            or any(
                sum(item.month == month for item in self.targets) != 2
                for month in expected_months
            )
            or sum(item.reuse_candidate_path is not None for item in self.targets)
            != self.reuse_candidate_count
            or sum(item.reuse_candidate_path is None for item in self.targets)
            != self.maximum_network_target_count
            or self.minimum_minute_coverage_fraction != Decimal("0.99")
            or self.minimum_paired_minute_coverage_fraction != Decimal("0.99")
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor acquisition protocol changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 successor acquisition protocol hash changed")
        return self


class PeriodicFlowSuccessorAcquisitionProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-acquisition-protocol-audit-v1"
    ] = "aurex-q1-periodic-flow-successor-acquisition-protocol-audit-v1"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    parent_census_result_evidence_hash: str
    auditor_contract_hash: str
    target_manifest_hash: str
    target_count: Literal[74] = 74
    reuse_candidate_count: Literal[26] = 26
    maximum_network_target_count: Literal[48] = 48
    excluded_month_count: Literal[11] = 11
    lineage_and_manifest_reconstructed: Literal[True] = True
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
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "parent_census_result_evidence_hash",
        "auditor_contract_hash",
        "target_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorAcquisitionProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor acquisition protocol audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    data = provisional.model_dump()
    data[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(data)


def build_successor_acquisition_protocol(
    **values,
) -> PeriodicFlowSuccessorAcquisitionProtocol:
    payload = dict(values)
    payload["known_eligible_months"] = tuple(sorted(payload["known_eligible_months"]))
    payload["known_excluded_months"] = tuple(sorted(payload["known_excluded_months"]))
    payload["unknown_spot_first_months"] = tuple(
        sorted(payload["unknown_spot_first_months"])
    )
    payload["targets"] = tuple(sorted(payload["targets"], key=lambda item: item.key))
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorAcquisitionProtocol,
        "protocol_evidence_hash",
        payload,
    )


def build_successor_acquisition_protocol_audit(
    **values,
) -> PeriodicFlowSuccessorAcquisitionProtocolAudit:
    return _build(
        PeriodicFlowSuccessorAcquisitionProtocolAudit,
        "audit_evidence_hash",
        values,
    )


def audit_hash(model: BaseModel, hash_field: str) -> bool:
    return getattr(model, hash_field) == universe_evidence_hash(
        model.model_dump(exclude={hash_field})
    )
