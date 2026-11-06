from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

KNOWN_SOURCE_MONTHS = tuple(
    f"{year}-{month:02d}" for year in range(2020, 2023) for month in range(1, 13)
)
UNKNOWN_SOURCE_MONTHS = tuple(f"2023-{month:02d}" for month in range(1, 13))


class PeriodicFlowSuccessorSourceQualityProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-source-quality-protocol-v1"
    ] = "aurex-q1-periodic-flow-successor-source-quality-protocol-v1"
    protocol_id: Literal[
        "q1-periodic-flow-successor-source-quality-protocol-v1"
    ] = "q1-periodic-flow-successor-source-quality-protocol-v1"
    frozen_at: datetime
    status: Literal["FROZEN_POST_V1_STOP_PRE_SUCCESSOR_ACQUISITION"] = (
        "FROZEN_POST_V1_STOP_PRE_SUCCESSOR_ACQUISITION"
    )
    authorization_record: Literal[
        "TERMINAL_AUDIT_AUTHORIZED_SOURCE_QUALITY_CENSUS_PROTOCOL_ONLY"
    ] = "TERMINAL_AUDIT_AUTHORIZED_SOURCE_QUALITY_CENSUS_PROTOCOL_ONLY"
    parent_terminal_audit_file_sha256: str
    parent_terminal_audit_evidence_hash: str
    parent_v1_protocol_file_sha256: str
    parent_v1_protocol_evidence_hash: str
    jam_full_result_file_sha256: str
    jam_full_result_evidence_hash: str
    jam_full_audit_file_sha256: str
    jam_full_audit_evidence_hash: str
    jam_remediation_result_file_sha256: str
    jam_remediation_result_evidence_hash: str
    jam_remediation_audit_file_sha256: str
    jam_remediation_audit_evidence_hash: str
    development_start_month: Literal["2020-01"] = "2020-01"
    development_end_month: Literal["2023-12"] = "2023-12"
    known_source_months: tuple[str, ...] = Field(min_length=36, max_length=36)
    unknown_source_months: tuple[str, ...] = Field(min_length=12, max_length=12)
    minimum_minute_coverage_fraction: Decimal = Field(
        default=Decimal("0.99"), ge=Decimal("0.99"), le=Decimal("0.99")
    )
    maximum_event_gap_minutes: Literal[15] = 15
    minimum_qualifying_paired_months: Literal[30] = 30
    minimum_qualifying_months_per_year: Literal[6] = 6
    minimum_qualifying_months_per_quarter: Literal[1] = 1
    known_source_policy: Literal[
        "APPLY_V1_GATES_TO_PRIOR_INDEPENDENTLY_AUDITED_SPOT_EVIDENCE"
    ] = "APPLY_V1_GATES_TO_PRIOR_INDEPENDENTLY_AUDITED_SPOT_EVIDENCE"
    known_failed_month_policy: Literal["EXCLUDE_MONTH_NO_USDM_REQUEST"] = (
        "EXCLUDE_MONTH_NO_USDM_REQUEST"
    )
    unknown_month_policy: Literal[
        "ACQUIRE_AND_QUALIFY_SPOT_BEFORE_ANY_MATCHING_USDM_REQUEST"
    ] = "ACQUIRE_AND_QUALIFY_SPOT_BEFORE_ANY_MATCHING_USDM_REQUEST"
    failed_target_policy: Literal["EXCLUDE_MONTH_RECORD_FAILURE_CONTINUE"] = (
        "EXCLUDE_MONTH_RECORD_FAILURE_CONTINUE"
    )
    missing_minute_policy: Literal["NO_SYNTHESIS_EXCLUDE_FAILED_MONTH"] = (
        "NO_SYNTHESIS_EXCLUDE_FAILED_MONTH"
    )
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
        "AUTHORIZE_Q1_SUCCESSOR_SOURCE_QUALITY_CENSUS_NO_NETWORK"
    ] = "AUTHORIZE_Q1_SUCCESSOR_SOURCE_QUALITY_CENSUS_NO_NETWORK"
    limitations: tuple[str, ...] = Field(min_length=8)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_terminal_audit_file_sha256",
        "parent_terminal_audit_evidence_hash",
        "parent_v1_protocol_file_sha256",
        "parent_v1_protocol_evidence_hash",
        "jam_full_result_file_sha256",
        "jam_full_result_evidence_hash",
        "jam_full_audit_file_sha256",
        "jam_full_audit_evidence_hash",
        "jam_remediation_result_file_sha256",
        "jam_remediation_result_evidence_hash",
        "jam_remediation_audit_file_sha256",
        "jam_remediation_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> PeriodicFlowSuccessorSourceQualityProtocol:
        if (
            self.known_source_months != KNOWN_SOURCE_MONTHS
            or self.unknown_source_months != UNKNOWN_SOURCE_MONTHS
            or self.minimum_minute_coverage_fraction != Decimal("0.99")
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor source-quality protocol changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 successor source-quality protocol hash changed")
        return self


class PeriodicFlowSuccessorSourceQualityProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-source-quality-protocol-audit-v1"
    ] = "aurex-q1-periodic-flow-successor-source-quality-protocol-audit-v1"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    parent_terminal_audit_evidence_hash: str
    auditor_contract_hash: str
    lineage_reconstructed: Literal[True] = True
    source_sufficiency_gates_frozen: Literal[True] = True
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
        "parent_terminal_audit_evidence_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorSourceQualityProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor protocol audit hash changed")
        return self


class PeriodicFlowKnownSpotDisposition(BaseModel):
    month: str
    archive_sha256: str
    archive_bytes: int = Field(gt=0)
    unique_minute_count: int = Field(gt=0)
    expected_minute_count: int = Field(gt=0)
    minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    maximum_event_gap_minutes: int = Field(ge=0)
    duplicate_member_exception_applied: bool
    eligible_for_successor_pairing: bool
    reason_codes: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_disposition(self) -> PeriodicFlowKnownSpotDisposition:
        if (
            self.minute_coverage_fraction
            != Decimal(self.unique_minute_count) / Decimal(self.expected_minute_count)
            or self.duplicate_member_exception_applied != (self.month == "2021-12")
            or self.eligible_for_successor_pairing != (not self.reason_codes)
            or self.reason_codes != tuple(sorted(set(self.reason_codes)))
        ):
            raise ValueError("Q1 known Spot disposition changed")
        return self

    @property
    def year(self) -> int:
        return int(self.month[:4])


class PeriodicFlowSuccessorSourceQualityResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-source-quality-result-v1"
    ] = "aurex-q1-periodic-flow-successor-source-quality-result-v1"
    result_id: Literal["q1-periodic-flow-successor-source-quality-result-v1"] = (
        "q1-periodic-flow-successor-source-quality-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_PRIOR_EVIDENCE_CENSUS_NO_NETWORK_NO_OUTCOMES"] = (
        "COMPLETE_PRIOR_EVIDENCE_CENSUS_NO_NETWORK_NO_OUTCOMES"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    known_spot_dispositions: tuple[PeriodicFlowKnownSpotDisposition, ...] = Field(
        min_length=36, max_length=36
    )
    known_eligible_month_count: int = Field(ge=0, le=36)
    known_ineligible_month_count: int = Field(ge=0, le=36)
    known_eligible_months: tuple[str, ...]
    known_ineligible_months: tuple[str, ...]
    unknown_spot_first_months: tuple[str, ...] = Field(min_length=12, max_length=12)
    maximum_possible_qualifying_month_count: int = Field(ge=0, le=48)
    maximum_successor_network_spot_archives: Literal[12] = 12
    maximum_successor_network_usdm_archives: int = Field(ge=0, le=47)
    maximum_successor_network_archives: int = Field(ge=0, le=59)
    network_requests_made: Literal[0] = 0
    payload_bytes_received: Literal[0] = 0
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    features_calculated: tuple[str, ...] = ()
    parameters_defined: tuple[str, ...] = ()
    returns_calculated: tuple[str, ...] = ()
    validation_accessed: Literal[False] = False
    holdout_accessed: Literal[False] = False
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    decision: Literal["PERMIT_Q1_SUCCESSOR_ACQUISITION_PROTOCOL_DESIGN"] = (
        "PERMIT_Q1_SUCCESSOR_ACQUISITION_PROTOCOL_DESIGN"
    )
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_ACQUISITION_PROTOCOL_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_ACQUISITION_PROTOCOL_ONLY"
    limitations: tuple[str, ...] = Field(min_length=8)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> PeriodicFlowSuccessorSourceQualityResult:
        months = tuple(item.month for item in self.known_spot_dispositions)
        eligible = tuple(
            item.month
            for item in self.known_spot_dispositions
            if item.eligible_for_successor_pairing
        )
        ineligible = tuple(
            item.month
            for item in self.known_spot_dispositions
            if not item.eligible_for_successor_pairing
        )
        expected_usdm = len(eligible) - 1 + len(self.unknown_spot_first_months)
        if (
            months != KNOWN_SOURCE_MONTHS
            or self.known_eligible_month_count != len(eligible)
            or self.known_ineligible_month_count != len(ineligible)
            or self.known_eligible_months != eligible
            or self.known_ineligible_months != ineligible
            or self.unknown_spot_first_months != UNKNOWN_SOURCE_MONTHS
            or self.maximum_possible_qualifying_month_count
            != len(eligible) + len(self.unknown_spot_first_months)
            or self.maximum_successor_network_usdm_archives != expected_usdm
            or self.maximum_successor_network_archives
            != self.maximum_successor_network_spot_archives + expected_usdm
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor source-quality result changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 successor source-quality result hash changed")
        return self


class PeriodicFlowSuccessorSourceQualityResultAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-source-quality-result-audit-v1"
    ] = "aurex-q1-periodic-flow-successor-source-quality-result-audit-v1"
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    auditor_contract_hash: str
    disposition_count_reconstructed: Literal[36] = 36
    known_eligible_month_count: int = Field(ge=0, le=36)
    known_ineligible_month_count: int = Field(ge=0, le=36)
    network_requests_made: Literal[0] = 0
    outcomes_accessed: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PERMIT_Q1_SUCCESSOR_ACQUISITION_PROTOCOL_DESIGN"] = (
        "PERMIT_Q1_SUCCESSOR_ACQUISITION_PROTOCOL_DESIGN"
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "protocol_evidence_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorSourceQualityResultAudit:
        if self.known_eligible_month_count + self.known_ineligible_month_count != 36:
            raise ValueError("Q1 successor result audit counts changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor result audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    data = provisional.model_dump()
    data[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(data)


def build_successor_source_quality_protocol(
    **values,
) -> PeriodicFlowSuccessorSourceQualityProtocol:
    payload = dict(values)
    payload["known_source_months"] = KNOWN_SOURCE_MONTHS
    payload["unknown_source_months"] = UNKNOWN_SOURCE_MONTHS
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorSourceQualityProtocol,
        "protocol_evidence_hash",
        payload,
    )


def build_successor_source_quality_protocol_audit(
    **values,
) -> PeriodicFlowSuccessorSourceQualityProtocolAudit:
    return _build(
        PeriodicFlowSuccessorSourceQualityProtocolAudit,
        "audit_evidence_hash",
        values,
    )


def build_successor_source_quality_result(
    **values,
) -> PeriodicFlowSuccessorSourceQualityResult:
    payload = dict(values)
    payload["known_spot_dispositions"] = tuple(
        sorted(payload["known_spot_dispositions"], key=lambda item: item.month)
    )
    payload["known_eligible_months"] = tuple(
        item.month
        for item in payload["known_spot_dispositions"]
        if item.eligible_for_successor_pairing
    )
    payload["known_ineligible_months"] = tuple(
        item.month
        for item in payload["known_spot_dispositions"]
        if not item.eligible_for_successor_pairing
    )
    payload["known_eligible_month_count"] = len(payload["known_eligible_months"])
    payload["known_ineligible_month_count"] = len(payload["known_ineligible_months"])
    payload["unknown_spot_first_months"] = UNKNOWN_SOURCE_MONTHS
    payload["maximum_possible_qualifying_month_count"] = (
        payload["known_eligible_month_count"] + len(UNKNOWN_SOURCE_MONTHS)
    )
    payload["maximum_successor_network_spot_archives"] = len(UNKNOWN_SOURCE_MONTHS)
    payload["maximum_successor_network_usdm_archives"] = (
        payload["known_eligible_month_count"] - 1 + len(UNKNOWN_SOURCE_MONTHS)
    )
    payload["maximum_successor_network_archives"] = (
        payload["maximum_successor_network_spot_archives"]
        + payload["maximum_successor_network_usdm_archives"]
    )
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorSourceQualityResult,
        "result_evidence_hash",
        payload,
    )


def build_successor_source_quality_result_audit(
    **values,
) -> PeriodicFlowSuccessorSourceQualityResultAudit:
    return _build(
        PeriodicFlowSuccessorSourceQualityResultAudit,
        "audit_evidence_hash",
        values,
    )


def audit_hash(model: BaseModel, hash_field: str) -> bool:
    return getattr(model, hash_field) == universe_evidence_hash(
        model.model_dump(exclude={hash_field})
    )
