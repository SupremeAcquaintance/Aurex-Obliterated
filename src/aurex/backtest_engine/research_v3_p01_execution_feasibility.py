from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P01_EXECUTION_PROTOCOL_SCHEMA_VERSION = (
    "aurex-v3-p01-cross-asset-execution-metadata-feasibility-protocol-v1"
)
V3_P01_EXECUTION_RESULT_SCHEMA_VERSION = (
    "aurex-v3-p01-cross-asset-execution-metadata-feasibility-result-v1"
)
V3_P01_EXECUTION_REQUIREMENT_IDS = [
    "CROSS_ASSET_IDENTITY_HEDGE_AND_RESIDUAL_RISK_FOUNDATION",
    "HISTORICAL_ACCOUNT_FEE_TIER",
    "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES",
    "HISTORICAL_FUTURES_CONTRACT_LIFECYCLE",
    "HISTORICAL_FUTURES_ORDER_FILTERS",
    "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS",
    "HISTORICAL_SETTLED_FUNDING_AND_INTERVALS",
    "HISTORICAL_SPOT_ORDER_FILTERS",
    "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES",
    "SYNCHRONIZED_SOURCE_COVERAGE_25_SYMBOLS",
    "SYNTHETIC_PARTIAL_FILL_ROLLBACK_IDEMPOTENCY_RECONCILIATION",
]
V3_P01_EXECUTION_FAIL_DECISION = (
    "REJECT_V3P01_EXECUTION_AND_METADATA_FEASIBILITY"
)


class V3P01ExecutionFeasibilityProtocol(BaseModel):
    schema_version: Literal[
        "aurex-v3-p01-cross-asset-execution-metadata-feasibility-protocol-v1"
    ] = V3_P01_EXECUTION_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal[
        "v3-p01-cross-asset-execution-metadata-feasibility-v1"
    ] = "v3-p01-cross-asset-execution-metadata-feasibility-v1"
    protocol_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FORMAL_FEASIBILITY_RESULT"] = (
        "FROZEN_PRE_FORMAL_FEASIBILITY_RESULT"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    v3p01_coverage_result_evidence_hash: str
    v2_metadata_audit_result_evidence_hash: str
    v2_foundation_result_evidence_hash: str
    builder_contract_hash: str
    proposal_id: Literal[
        "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE"
    ] = "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE"
    requirement_ids: list[str] = Field(min_length=11, max_length=11)
    qualification_rule: Literal[
        "ALL_ELEVEN_REQUIREMENTS_MUST_PASS_WITHOUT_HISTORICAL_OVERRIDE"
    ] = "ALL_ELEVEN_REQUIREMENTS_MUST_PASS_WITHOUT_HISTORICAL_OVERRIDE"
    conservative_historical_overrides_permitted: Literal[False] = False
    same_asset_base_quantity_netting_qualifies_cross_asset_risk: Literal[
        False
    ] = False
    requirement_failure_action: Literal[
        "REJECT_V3P01_BEFORE_PRIMARY_SELECTION"
    ] = "REJECT_V3P01_BEFORE_PRIMARY_SELECTION"
    market_numeric_value_inspection_permitted: Literal[False] = False
    strategy_outcome_inspection_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    selection_permitted: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "v3p01_coverage_result_evidence_hash",
        "v2_metadata_audit_result_evidence_hash",
        "v2_foundation_result_evidence_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("requirement_ids", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> V3P01ExecutionFeasibilityProtocol:
        if self.requirement_ids != V3_P01_EXECUTION_REQUIREMENT_IDS:
            raise ValueError("V3P01 execution requirement matrix changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("V3P01 execution protocol hash does not match")
        return self


class V3P01ExecutionRequirementAssessment(BaseModel):
    requirement_id: str
    status: Literal["PASS", "FAIL"]
    evidence_hashes: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=40, max_length=1500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_hashes")
    @classmethod
    def normalize_hashes(cls, value: list[str]) -> list[str]:
        return sorted({normalize_sha256(item) for item in value})


class V3P01ExecutionFeasibilityResult(BaseModel):
    schema_version: Literal[
        "aurex-v3-p01-cross-asset-execution-metadata-feasibility-result-v1"
    ] = V3_P01_EXECUTION_RESULT_SCHEMA_VERSION
    result_id: Literal[
        "v3-p01-cross-asset-execution-metadata-feasibility-v1"
    ] = "v3-p01-cross-asset-execution-metadata-feasibility-v1"
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE_NO_RETURN_FEASIBILITY_REJECTION"] = (
        "COMPLETE_NO_RETURN_FEASIBILITY_REJECTION"
    )
    protocol_evidence_hash: str
    runner_contract_hash: str
    cross_asset_foundation_source_hash: str
    assessments: list[V3P01ExecutionRequirementAssessment] = Field(
        min_length=11,
        max_length=11,
    )
    passed_requirement_count: int = Field(ge=0, le=11)
    failed_requirement_count: int = Field(ge=0, le=11)
    passed_requirement_ids: list[str]
    failed_requirement_ids: list[str]
    decision: Literal[
        "REJECT_V3P01_EXECUTION_AND_METADATA_FEASIBILITY"
    ] = V3_P01_EXECUTION_FAIL_DECISION
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "cross_asset_foundation_source_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "passed_requirement_ids",
        "failed_requirement_ids",
        "market_numeric_values_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V3P01ExecutionFeasibilityResult:
        if self.assessments != sorted(
            self.assessments,
            key=lambda item: item.requirement_id,
        ):
            raise ValueError("V3P01 execution assessments are not canonical")
        if (
            len({item.requirement_id for item in self.assessments}) != 11
            or {item.requirement_id for item in self.assessments}
            != set(V3_P01_EXECUTION_REQUIREMENT_IDS)
        ):
            raise ValueError("V3P01 execution assessment matrix changed")
        passed = sorted(
            item.requirement_id
            for item in self.assessments
            if item.status == "PASS"
        )
        failed = sorted(set(V3_P01_EXECUTION_REQUIREMENT_IDS) - set(passed))
        if (
            self.passed_requirement_ids != passed
            or self.failed_requirement_ids != failed
            or self.passed_requirement_count != len(passed)
            or self.failed_requirement_count != len(failed)
            or not failed
        ):
            raise ValueError("V3P01 execution assessment counts changed")
        if (
            self.market_numeric_values_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3P01 feasibility result may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V3P01 execution result hash does not match")
        return self


def build_v3_p01_execution_feasibility_protocol(
    **values,
) -> V3P01ExecutionFeasibilityProtocol:
    payload = {
        "schema_version": V3_P01_EXECUTION_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "v3-p01-cross-asset-execution-metadata-feasibility-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_PRE_FORMAL_FEASIBILITY_RESULT",
        "proposal_id": "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
        "requirement_ids": V3_P01_EXECUTION_REQUIREMENT_IDS,
        "qualification_rule": (
            "ALL_ELEVEN_REQUIREMENTS_MUST_PASS_WITHOUT_HISTORICAL_OVERRIDE"
        ),
        "conservative_historical_overrides_permitted": False,
        "same_asset_base_quantity_netting_qualifies_cross_asset_risk": False,
        "requirement_failure_action": (
            "REJECT_V3P01_BEFORE_PRIMARY_SELECTION"
        ),
        "market_numeric_value_inspection_permitted": False,
        "strategy_outcome_inspection_permitted": False,
        "return_calculation_permitted": False,
        "selection_permitted": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P01ExecutionFeasibilityProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_v3_p01_execution_feasibility_result(
    **values,
) -> V3P01ExecutionFeasibilityResult:
    assessments = sorted(
        values.pop("assessments"),
        key=lambda item: item.requirement_id,
    )
    passed = sorted(
        item.requirement_id
        for item in assessments
        if item.status == "PASS"
    )
    failed = sorted(set(V3_P01_EXECUTION_REQUIREMENT_IDS) - set(passed))
    payload = {
        "schema_version": V3_P01_EXECUTION_RESULT_SCHEMA_VERSION,
        "result_id": "v3-p01-cross-asset-execution-metadata-feasibility-v1",
        "result_version": "1.0.0",
        "status": "COMPLETE_NO_RETURN_FEASIBILITY_REJECTION",
        "assessments": assessments,
        "passed_requirement_count": len(passed),
        "failed_requirement_count": len(failed),
        "passed_requirement_ids": passed,
        "failed_requirement_ids": failed,
        "decision": V3_P01_EXECUTION_FAIL_DECISION,
        "selects_primary": False,
        "creates_candidate": False,
        "opens_development": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "market_numeric_values_inspected": [],
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P01ExecutionFeasibilityResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p01_execution_feasibility_protocol(
    protocol: V3P01ExecutionFeasibilityProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_v3_p01_execution_feasibility_result(
    result: V3P01ExecutionFeasibilityResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
