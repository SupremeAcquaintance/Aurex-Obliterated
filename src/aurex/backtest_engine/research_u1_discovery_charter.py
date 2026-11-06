from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

U1_DISCOVERY_CHARTER_SCHEMA_VERSION = "aurex-u1-mechanism-discovery-charter-v1"

U1_RETIRED_OR_QUARANTINED_LINEAGES = [
    "intraday_trend_pullback",
    "intraday_volatility_breakout",
    "jam_reversal",
    "path_quality_spot",
    "range_mean_reversion_existing_implementation",
    "slow_trend_breakout_spot",
]

U1_FORBIDDEN_DERIVATIONS = [
    "DO_NOT_CONDITION_ON_R4_EXIT_REASON_PROFITABILITY",
    "DO_NOT_CONDITION_ON_R4_HOLDING_DURATION_PROFITABILITY",
    "DO_NOT_CONDITION_ON_R4_MONTH_OR_QUARTER_PROFITABILITY",
    "DO_NOT_CONDITION_ON_R4_REBALANCE_COHORT_PROFITABILITY",
    "DO_NOT_CONDITION_ON_R4_SYMBOL_OR_OMISSION_PROFITABILITY",
    "DO_NOT_INVERT_NEGATE_FILTER_OR_REPARAMETERIZE_A_RETIRED_SIGNAL",
    "DO_NOT_RENAME_EXISTING_EXPLORATORY_CODE_AS_A_NEW_MECHANISM",
    "DO_NOT_USE_2025_2026_OR_FORWARD_RETURNS_TO_SELECT_THE_PRIMARY",
]

U1_REQUIRED_THEORY_EVIDENCE = [
    "AT_LEAST_TWO_PRIMARY_RESEARCH_SOURCES",
    "ECONOMIC_PREMISE_INDEPENDENT_OF_AUREX_BACKTEST_OUTCOMES",
    "EX_ANTE_DIRECTIONAL_PREDICTION",
    "POINT_IN_TIME_DATA_REQUIREMENTS",
    "REALISTIC_EXECUTION_AND_COST_PATH",
    "SPECIFIC_FALSIFICATION_CONDITION",
]

U1_THEORY_SOURCE_POLICY = [
    "ALLOW_OFFICIAL_EXCHANGE_MARKET_AND_DATA_DOCUMENTATION",
    "ALLOW_PEER_REVIEWED_RESEARCH",
    "ALLOW_REPUTABLE_INSTITUTIONAL_WORKING_PAPERS",
    "REJECT_ANONYMOUS_SIGNALS_SOCIAL_POSTS_AND_MARKETING_CLAIMS",
    "REJECT_SOURCES_SELECTED_BECAUSE_THEY_MATCH_AUREX_OUTCOMES",
]

U1_DISCOVERY_STAGES = [
    "01_THEORY_AND_DATA_FEASIBILITY_NO_RETURN_METRICS",
    "02_FREEZE_EXACTLY_ZERO_OR_ONE_PRIMARY_MECHANISM",
    "03_DEVELOPMENT_FALSIFICATION_2023_2024",
    "04_INTERNAL_VALIDATION_2025_IF_DEVELOPMENT_PASSES",
    "05_FINAL_HOLDOUT_2026_IF_INTERNAL_VALIDATION_PASSES",
    "06_FORWARD_PAPER_ONLY_IF_FINAL_HOLDOUT_PASSES",
]

U1_REQUIRED_CANDIDATE_BINDINGS = [
    "CANDIDATE_SOURCE_BYTES_AND_VERSION",
    "DATASET_AND_PARTITION_HASHES",
    "DECISION_GATES_AND_STOP_RULE",
    "EXACT_FEATURE_AND_SIGNAL_ARITHMETIC",
    "EXECUTION_ORDER_FILL_AND_COST_SEMANTICS",
    "HYPOTHESIS_AND_ECONOMIC_PREMISE",
    "MARKET_UNIVERSE_AND_AVAILABILITY_POLICY",
    "PARAMETERS_AND_REBALANCE_SCHEDULE",
    "RUN_MATRIX_AND_MULTIPLICITY_ACCOUNTING",
    "SHARED_CAPITAL_PORTFOLIO_AND_RISK_LIMITS",
]

U1_MINIMUM_ADVANCEMENT_GATES = [
    "AUDIT_AND_REPLAY_DETERMINISM_PASS",
    "BASE_COST_NET_PROFIT_POSITIVE",
    "BASE_COST_PROFIT_FACTOR_AT_LEAST_1_15",
    "COMPLETED_TRADES_AT_LEAST_100",
    "DOUBLE_COST_NET_PROFIT_POSITIVE",
    "LEAVE_ONE_MARKET_OUT_POSITIVE_FRACTION_AT_LEAST_0_80",
    "MAXIMUM_DRAWDOWN_PERCENT_AT_MOST_20",
    "POSITIVE_IN_AT_LEAST_TWO_THIRDS_OF_PREDECLARED_TEMPORAL_FOLDS",
    "SINGLE_MARKET_GROSS_PROFIT_FRACTION_AT_MOST_0_25",
    "TOP_FIVE_MARKET_GROSS_PROFIT_FRACTION_AT_MOST_0_70",
]

U1_STOP_CONDITIONS = [
    "ANY_REQUIRED_BINDING_IS_MISSING_OR_CHANGED",
    "ANY_REQUIRED_DATASET_OR_SOURCE_HASH_FAILS",
    "ANY_PREDECLARED_ADVANCEMENT_GATE_FAILS",
    "PRIMARY_MECHANISM_IS_SELECTED_USING_RETURN_OUTCOMES",
    "PRIMARY_MECHANISM_REQUIRES_UNAVAILABLE_POINT_IN_TIME_DATA",
    "RESULT_OR_REPLAY_AUDIT_FAILS",
]

U1_ALLOWED_NEXT_DECISIONS = [
    "FREEZE_ONE_PRIMARY_MECHANISM_FOR_DEVELOPMENT",
    "NO_FEASIBLE_UNRELATED_MECHANISM_STOP_RESEARCH",
]


class U1PartitionBoundary(BaseModel):
    partition: Literal["DEVELOPMENT", "VALIDATION", "HOLDOUT", "FORWARD"]
    start: datetime
    end: datetime | None
    research_role: Literal[
        "DEVELOPMENT_FALSIFICATION",
        "INTERNAL_VALIDATION_NOT_ELIGIBILITY",
        "FINAL_ELIGIBILITY_HOLDOUT",
        "LOCKED_FORWARD_EVIDENCE",
    ]
    access: Literal[
        "OPEN",
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
    def validate_boundary(self) -> U1PartitionBoundary:
        expected = {
            "DEVELOPMENT": (
                "2023-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
                "DEVELOPMENT_FALSIFICATION",
                "OPEN",
            ),
            "VALIDATION": (
                "2025-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "INTERNAL_VALIDATION_NOT_ELIGIBILITY",
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
            self.research_role,
            self.access,
        )
        if actual != expected:
            raise ValueError(f"{self.partition} discovery boundary is fixed")
        return self


class U1MechanismDiscoveryCharter(BaseModel):
    schema_version: Literal["aurex-u1-mechanism-discovery-charter-v1"] = (
        U1_DISCOVERY_CHARTER_SCHEMA_VERSION
    )
    charter_id: Literal["u1-unrelated-mechanism-discovery-v1"] = (
        "u1-unrelated-mechanism-discovery-v1"
    )
    charter_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_DISCOVERY_OUTCOME"] = "FROZEN_PRE_DISCOVERY_OUTCOME"
    r4_failure_analysis_result_evidence_hash: str
    contamination_ledger_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    validation_dataset_bundle_evidence_hash: str
    partition_boundaries: list[U1PartitionBoundary] = Field(min_length=4, max_length=4)
    retired_or_quarantined_lineages: list[str]
    forbidden_derivations: list[str]
    required_theory_evidence: list[str]
    theory_source_policy: list[str]
    discovery_stages: list[str]
    required_candidate_bindings: list[str]
    minimum_advancement_gates: list[str]
    stop_conditions: list[str]
    allowed_next_decisions: list[str]
    maximum_theory_proposals: Literal[3] = 3
    maximum_return_tested_mechanisms: Literal[1] = 1
    maximum_selectable_parameter_sets: Literal[1] = 1
    maximum_selectable_candidates: Literal[1] = 1
    theory_screen_may_read_market_returns: Literal[False] = False
    theory_screen_may_calculate_strategy_outcomes: Literal[False] = False
    validation_is_final_eligibility_evidence: Literal[False] = False
    holdout_is_required_for_eligibility: Literal[True] = True
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    opens_2026_or_forward_partition: Literal[False] = False
    preexisting_discovery_artifacts: list[str] = Field(default_factory=list)
    builder_contract_hash: str
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "r4_failure_analysis_result_evidence_hash",
        "contamination_ledger_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "validation_dataset_bundle_evidence_hash",
        "builder_contract_hash",
        "charter_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "retired_or_quarantined_lineages",
        "forbidden_derivations",
        "required_theory_evidence",
        "theory_source_policy",
        "discovery_stages",
        "required_candidate_bindings",
        "minimum_advancement_gates",
        "stop_conditions",
        "allowed_next_decisions",
        "preexisting_discovery_artifacts",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_charter(self) -> U1MechanismDiscoveryCharter:
        expected_lists = {
            "retired_or_quarantined_lineages": U1_RETIRED_OR_QUARANTINED_LINEAGES,
            "forbidden_derivations": U1_FORBIDDEN_DERIVATIONS,
            "required_theory_evidence": U1_REQUIRED_THEORY_EVIDENCE,
            "theory_source_policy": U1_THEORY_SOURCE_POLICY,
            "discovery_stages": U1_DISCOVERY_STAGES,
            "required_candidate_bindings": U1_REQUIRED_CANDIDATE_BINDINGS,
            "minimum_advancement_gates": U1_MINIMUM_ADVANCEMENT_GATES,
            "stop_conditions": U1_STOP_CONDITIONS,
            "allowed_next_decisions": U1_ALLOWED_NEXT_DECISIONS,
        }
        for field, expected in expected_lists.items():
            if getattr(self, field) != sorted(expected):
                raise ValueError(f"U1 charter {field} is fixed")
        if [item.partition for item in self.partition_boundaries] != [
            "DEVELOPMENT",
            "VALIDATION",
            "HOLDOUT",
            "FORWARD",
        ]:
            raise ValueError("U1 charter partition order is fixed")
        if self.preexisting_discovery_artifacts:
            raise ValueError("U1 charter must predate every discovery artifact")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected_hash:
            raise ValueError("U1 charter hash does not match its evidence")
        return self


def build_u1_mechanism_discovery_charter(
    **values,
) -> U1MechanismDiscoveryCharter:
    payload = {
        "schema_version": U1_DISCOVERY_CHARTER_SCHEMA_VERSION,
        "charter_id": "u1-unrelated-mechanism-discovery-v1",
        "charter_version": "1.0.0",
        "status": "FROZEN_PRE_DISCOVERY_OUTCOME",
        "maximum_theory_proposals": 3,
        "maximum_return_tested_mechanisms": 1,
        "maximum_selectable_parameter_sets": 1,
        "maximum_selectable_candidates": 1,
        "theory_screen_may_read_market_returns": False,
        "theory_screen_may_calculate_strategy_outcomes": False,
        "validation_is_final_eligibility_evidence": False,
        "holdout_is_required_for_eligibility": True,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "opens_2026_or_forward_partition": False,
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    for field in (
        "retired_or_quarantined_lineages",
        "forbidden_derivations",
        "required_theory_evidence",
        "theory_source_policy",
        "discovery_stages",
        "required_candidate_bindings",
        "minimum_advancement_gates",
        "stop_conditions",
        "allowed_next_decisions",
        "preexisting_discovery_artifacts",
    ):
        payload[field] = sorted(set(payload[field]))
    return U1MechanismDiscoveryCharter(
        **payload,
        charter_evidence_hash=universe_evidence_hash(payload),
    )


def audit_u1_mechanism_discovery_charter(
    charter: U1MechanismDiscoveryCharter,
) -> bool:
    return charter.charter_evidence_hash == universe_evidence_hash(
        charter.model_dump(exclude={"charter_evidence_hash"})
    )
