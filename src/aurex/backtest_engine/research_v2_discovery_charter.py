from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
    V2_EXCLUDED_INCOMPLETE_SYMBOLS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_DISCOVERY_CHARTER_SCHEMA_VERSION = (
    "aurex-v2-lower-directional-risk-discovery-charter-v1"
)
V2_REQUIRED_THEORY_EVIDENCE = [
    "AT_LEAST_TWO_PRIMARY_OR_PEER_REVIEWED_SOURCES",
    "ECONOMIC_PREMISE_INDEPENDENT_OF_AUREX_RETURN_OUTCOMES",
    "EX_ANTE_CARRY_OR_CONVERGENCE_DIRECTION",
    "EXACT_POINT_IN_TIME_DATA_REQUIREMENTS",
    "HISTORICAL_FEE_CONTRACT_AND_COLLATERAL_REQUIREMENTS",
    "REALISTIC_PAIRED_EXECUTION_AND_FAILURE_PATH",
    "SPECIFIC_FALSIFICATION_CONDITION",
]
V2_THEORY_SOURCE_POLICY = [
    "ALLOW_OFFICIAL_EXCHANGE_MARKET_DATA_AND_RISK_DOCUMENTATION",
    "ALLOW_PEER_REVIEWED_RESEARCH",
    "ALLOW_REPUTABLE_INSTITUTIONAL_WORKING_PAPERS",
    "REJECT_ANONYMOUS_SIGNALS_SOCIAL_POSTS_AND_MARKETING_CLAIMS",
    "REJECT_SOURCES_SELECTED_BECAUSE_THEY_MATCH_AUREX_OUTCOMES",
]
V2_FORBIDDEN_DERIVATIONS = [
    "DO_NOT_RESCUE_TUNE_OR_REINTERPRET_U1",
    "DO_NOT_REUSE_R3_R31_R4_OUTCOME_BUCKETS_AS_RULES",
    "DO_NOT_USE_PILOT_NUMERIC_VALUES_BEYOND_SCHEMA_AND_RESOURCE_QUALIFICATION",
    "DO_NOT_CALCULATE_RETURNS_DURING_THEORY_SCREEN",
    "DO_NOT_SELECT_SYMBOLS_MONTHS_OR_PARAMETERS_BY_RETURN",
    "DO_NOT_ASSUME_FUTURE_FUNDING_FEES_LIQUIDITY_OR_MARGIN_FROM_ARCHIVE_COVERAGE",
    "DO_NOT_BEGIN_FULL_ACQUISITION_BEFORE_A_SEPARATE_FROZEN_PROTOCOL",
    "DO_NOT_OPEN_2025_2026_OR_FORWARD_DATA",
]
V2_REQUIRED_NEXT_PROTOCOL_BINDINGS = [
    "CANDIDATE_SOURCE_BYTES_AND_VERSION",
    "CONTRACT_AND_FEE_METADATA_POLICY",
    "DATASET_PARTITION_AND_TRANSFORMATION_HASHES",
    "DECISION_GATES_AND_MECHANICAL_STOP_RULE",
    "EXACT_FUNDING_BASIS_AND_SIGNAL_ARITHMETIC",
    "FULL_ACQUISITION_RESOURCE_AND_INTEGRITY_PROTOCOL",
    "PAIRED_ORDER_FILL_ROLLBACK_AND_COST_SEMANTICS",
    "PORTFOLIO_COLLATERAL_MARGIN_LIQUIDATION_AND_ADL_SEMANTICS",
    "RECONCILIATION_AND_EVIDENCE_REQUIREMENTS",
    "RUN_MATRIX_AND_MULTIPLICITY_ACCOUNTING",
]
V2_DISCOVERY_STAGES = [
    "01_THEORY_AND_POINT_IN_TIME_FEASIBILITY_NO_RETURNS",
    "02_FREEZE_ZERO_OR_ONE_PRIMARY_DATA_ACQUISITION_DESIGN",
    "03_FULL_DATA_ACQUISITION_AND_QUALITY_AUDIT",
    "04_FREEZE_ZERO_OR_ONE_PRIMARY_DEVELOPMENT_PROTOCOL",
    "05_DEVELOPMENT_FALSIFICATION_2023_2024",
    "06_INTERNAL_VALIDATION_2025_ONLY_IF_DEVELOPMENT_PASSES",
    "07_FINAL_HOLDOUT_2026_ONLY_IF_INTERNAL_VALIDATION_PASSES",
    "08_FORWARD_PAPER_ONLY_IF_FINAL_HOLDOUT_PASSES",
]
V2_STOP_CONDITIONS = [
    "ANY_PREDECESSOR_EVIDENCE_HASH_FAILS",
    "FULL_POINT_IN_TIME_DATA_OR_METADATA_IS_NOT_FEASIBLE",
    "MECHANISM_REQUIRES_UNMODELED_BORROW_MARGIN_OR_EXECUTION",
    "PRIMARY_IS_SELECTED_USING_RETURN_OUTCOMES",
    "PROPOSAL_BUDGET_OR_MULTIPLICITY_BOUNDARY_IS_BREACHED",
    "SYNTHETIC_OR_DATA_INTEGRITY_AUDIT_FAILS",
]
V2_ALLOWED_NEXT_DECISIONS = [
    "FREEZE_ONE_PRIMARY_FOR_FULL_DATA_AND_PROTOCOL_DESIGN",
    "NO_FEASIBLE_LOWER_DIRECTIONAL_RISK_MECHANISM_STOP_RESEARCH",
]


class V2DiscoveryPartitionBoundary(BaseModel):
    partition: Literal["DEVELOPMENT", "VALIDATION", "HOLDOUT", "FORWARD"]
    start: datetime
    end: datetime | None
    role: Literal[
        "FUTURE_DEVELOPMENT_FALSIFICATION",
        "FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
        "FINAL_ELIGIBILITY_HOLDOUT",
        "LOCKED_FORWARD_EVIDENCE",
    ]
    access: Literal[
        "CLOSED_PENDING_FULL_ACQUISITION_PROTOCOL",
        "SEALED_FOR_UNRELATED_MECHANISM",
        "SEALED_AND_NOT_IMPORTED",
        "LOCKED",
    ]

    model_config = ConfigDict(extra="forbid")

    @field_validator("start", "end")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None

    @model_validator(mode="after")
    def validate_boundary(self) -> V2DiscoveryPartitionBoundary:
        expected = {
            "DEVELOPMENT": (
                "2023-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
                "FUTURE_DEVELOPMENT_FALSIFICATION",
                "CLOSED_PENDING_FULL_ACQUISITION_PROTOCOL",
            ),
            "VALIDATION": (
                "2025-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
                "SEALED_FOR_UNRELATED_MECHANISM",
            ),
            "HOLDOUT": (
                "2026-01-01T00:00:00+00:00",
                "2026-07-01T00:00:00+00:00",
                "FINAL_ELIGIBILITY_HOLDOUT",
                "SEALED_AND_NOT_IMPORTED",
            ),
            "FORWARD": (
                "2026-07-01T00:00:00+00:00",
                None,
                "LOCKED_FORWARD_EVIDENCE",
                "LOCKED",
            ),
        }[self.partition]
        actual = (
            self.start.isoformat(),
            self.end.isoformat() if self.end is not None else None,
            self.role,
            self.access,
        )
        if actual != expected:
            raise ValueError(f"V2 {self.partition} boundary changed")
        return self


class V2MechanismDiscoveryCharter(BaseModel):
    schema_version: Literal[
        "aurex-v2-lower-directional-risk-discovery-charter-v1"
    ] = V2_DISCOVERY_CHARTER_SCHEMA_VERSION
    charter_id: Literal["v2-lower-directional-risk-discovery-v1"] = (
        "v2-lower-directional-risk-discovery-v1"
    )
    charter_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_DISCOVERY_OUTCOME"] = "FROZEN_PRE_DISCOVERY_OUTCOME"
    capability_audit_evidence_hash: str
    source_census_result_evidence_hash: str
    acquisition_protocol_evidence_hash: str
    pilot_result_evidence_hash: str
    derivatives_foundation_protocol_evidence_hash: str
    derivatives_foundation_result_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    research_scope: Literal[
        "LOWER_DIRECTIONAL_RISK_SPOT_PERPETUAL_MECHANISMS"
    ] = "LOWER_DIRECTIONAL_RISK_SPOT_PERPETUAL_MECHANISMS"
    complete_source_symbols: list[str] = Field(min_length=31, max_length=31)
    excluded_incomplete_symbols: list[str] = Field(min_length=4, max_length=4)
    partition_boundaries: list[V2DiscoveryPartitionBoundary] = Field(
        min_length=4, max_length=4
    )
    required_theory_evidence: list[str]
    theory_source_policy: list[str]
    forbidden_derivations: list[str]
    required_next_protocol_bindings: list[str]
    discovery_stages: list[str]
    stop_conditions: list[str]
    allowed_next_decisions: list[str]
    maximum_theory_proposals: Literal[3] = 3
    maximum_selected_primary_mechanisms: Literal[1] = 1
    maximum_return_tested_mechanisms_under_charter: Literal[0] = 0
    maximum_selectable_parameter_sets_under_charter: Literal[0] = 0
    theory_screen_may_read_market_returns: Literal[False] = False
    theory_screen_may_calculate_strategy_outcomes: Literal[False] = False
    theory_screen_may_download_full_dataset: Literal[False] = False
    selection_creates_candidate: Literal[False] = False
    development_data_open: Literal[False] = False
    validation_data_open: Literal[False] = False
    holdout_data_open: Literal[False] = False
    forward_data_open: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    preexisting_discovery_artifacts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=5)
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "capability_audit_evidence_hash",
        "source_census_result_evidence_hash",
        "acquisition_protocol_evidence_hash",
        "pilot_result_evidence_hash",
        "derivatives_foundation_protocol_evidence_hash",
        "derivatives_foundation_result_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "charter_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "complete_source_symbols",
        "excluded_incomplete_symbols",
        "required_theory_evidence",
        "theory_source_policy",
        "forbidden_derivations",
        "required_next_protocol_bindings",
        "discovery_stages",
        "stop_conditions",
        "allowed_next_decisions",
        "strategy_outcome_fields_inspected",
        "preexisting_discovery_artifacts",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_charter(self) -> V2MechanismDiscoveryCharter:
        expected_lists = {
            "complete_source_symbols": V2_COMPLETE_SYMBOLS,
            "excluded_incomplete_symbols": V2_EXCLUDED_INCOMPLETE_SYMBOLS,
            "required_theory_evidence": V2_REQUIRED_THEORY_EVIDENCE,
            "theory_source_policy": V2_THEORY_SOURCE_POLICY,
            "forbidden_derivations": V2_FORBIDDEN_DERIVATIONS,
            "required_next_protocol_bindings": (
                V2_REQUIRED_NEXT_PROTOCOL_BINDINGS
            ),
            "discovery_stages": V2_DISCOVERY_STAGES,
            "stop_conditions": V2_STOP_CONDITIONS,
            "allowed_next_decisions": V2_ALLOWED_NEXT_DECISIONS,
        }
        for field_name, expected in expected_lists.items():
            if getattr(self, field_name) != sorted(expected):
                raise ValueError(f"V2 charter {field_name} changed")
        if [item.partition for item in self.partition_boundaries] != [
            "DEVELOPMENT",
            "VALIDATION",
            "HOLDOUT",
            "FORWARD",
        ]:
            raise ValueError("V2 charter partition order changed")
        if (
            self.strategy_outcome_fields_inspected
            or self.preexisting_discovery_artifacts
        ):
            raise ValueError("V2 charter must predate discovery and outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected_hash:
            raise ValueError("V2 charter hash does not match")
        return self


def build_v2_mechanism_discovery_charter(
    **values,
) -> V2MechanismDiscoveryCharter:
    payload = {
        "schema_version": V2_DISCOVERY_CHARTER_SCHEMA_VERSION,
        "charter_id": "v2-lower-directional-risk-discovery-v1",
        "charter_version": "1.0.0",
        "status": "FROZEN_PRE_DISCOVERY_OUTCOME",
        "research_scope": "LOWER_DIRECTIONAL_RISK_SPOT_PERPETUAL_MECHANISMS",
        "maximum_theory_proposals": 3,
        "maximum_selected_primary_mechanisms": 1,
        "maximum_return_tested_mechanisms_under_charter": 0,
        "maximum_selectable_parameter_sets_under_charter": 0,
        "theory_screen_may_read_market_returns": False,
        "theory_screen_may_calculate_strategy_outcomes": False,
        "theory_screen_may_download_full_dataset": False,
        "selection_creates_candidate": False,
        "development_data_open": False,
        "validation_data_open": False,
        "holdout_data_open": False,
        "forward_data_open": False,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "strategy_outcome_fields_inspected": [],
        "preexisting_discovery_artifacts": [],
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    for field_name in (
        "complete_source_symbols",
        "excluded_incomplete_symbols",
        "required_theory_evidence",
        "theory_source_policy",
        "forbidden_derivations",
        "required_next_protocol_bindings",
        "discovery_stages",
        "stop_conditions",
        "allowed_next_decisions",
        "strategy_outcome_fields_inspected",
        "preexisting_discovery_artifacts",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V2MechanismDiscoveryCharter(
        **payload,
        charter_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_mechanism_discovery_charter(
    charter: V2MechanismDiscoveryCharter,
) -> bool:
    return charter.charter_evidence_hash == universe_evidence_hash(
        charter.model_dump(exclude={"charter_evidence_hash"})
    )
