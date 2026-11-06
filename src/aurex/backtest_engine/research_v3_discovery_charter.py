from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_DISCOVERY_CHARTER_SCHEMA_VERSION = (
    "aurex-v3-independent-mechanism-discovery-charter-v1"
)
V3_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE = [
    "AT_LEAST_TWO_PRIMARY_OR_PEER_REVIEWED_SOURCES",
    "ECONOMIC_PREMISE_INDEPENDENT_OF_AUREX_OUTCOMES",
    "EXACT_POINT_IN_TIME_FIELDS_AND_TEMPORAL_AVAILABILITY",
    "EXACT_PAYLOAD_LEVEL_TIMESTAMP_COVERAGE_AUDIT",
    "EXPLICIT_MISSING_ROW_SKIP_STOP_AND_NO_FILL_POLICY",
    "HISTORICAL_EXECUTION_FINANCING_AND_METADATA_DEPENDENCIES",
    "MECHANISM_SPECIFIC_COST_CAPACITY_AND_FAILURE_PATH",
    "SPECIFIC_PRE_RETURN_FALSIFICATION_CONDITION",
    "UNTOUCHED_VALIDATION_HOLDOUT_AND_FORWARD_PATH",
]
V3_THEORY_SOURCE_POLICY = [
    "ALLOW_OFFICIAL_EXCHANGE_DATA_AND_RISK_DOCUMENTATION",
    "ALLOW_PEER_REVIEWED_RESEARCH",
    "ALLOW_REPUTABLE_INSTITUTIONAL_WORKING_PAPERS",
    "REJECT_ANONYMOUS_SIGNALS_SOCIAL_POSTS_AND_MARKETING_CLAIMS",
    "REJECT_SOURCES_SELECTED_BECAUSE_THEY_MATCH_AUREX_OUTCOMES",
]
V3_PAYLOAD_FEASIBILITY_POLICY = [
    "AUDIT_ONLY_REQUIRED_TIMESTAMPS_SCHEMA_ROW_COUNTS_AND_SOURCE_IDENTITY",
    "CLASSIFY_COMMON_SOURCE_OUTAGE_LISTING_GAP_AND_SYMBOL_SPECIFIC_GAP",
    "DEFINE_SYNCHRONIZED_DECISION_EVENT_COVERAGE_PER_PROPOSAL",
    "FORBID_FORWARD_FILL_BACKFILL_INTERPOLATION_AND_SYNTHETIC_ROWS",
    "FREEZE_SKIP_EXCLUSION_AND_STOP_RULES_BEFORE_PRIMARY_SELECTION",
    "REQUIRE_MINIMUM_EVENT_AND_TEMPORAL_BREADTH_BEFORE_SELECTION",
    "REQUIRE_POINT_IN_TIME_EXECUTION_DEPENDENCIES_BEFORE_SELECTION",
]
V3_FORBIDDEN_DERIVATIONS = [
    "DO_NOT_RELAX_OR_REINTERPRET_P01_CONTINUITY_AFTER_FAILURE",
    "DO_NOT_PROMOTE_P02_PREMIUM_CONVERGENCE_AS_A_P01_RESCUE",
    "DO_NOT_PROMOTE_P03_WITHOUT_POINT_IN_TIME_BORROW_AND_EXECUTION",
    "DO_NOT_REEXPRESS_RETIRED_TREND_BREAKOUT_PATH_BETA_OR_CARRY_FAMILIES",
    "DO_NOT_USE_R3_R31_R4_U1_OR_P01_OUTCOME_BUCKETS_AS_RULES",
    "DO_NOT_DEFINE_PARAMETERS_DURING_THEORY_OR_FEASIBILITY_SCREEN",
    "DO_NOT_INSPECT_PRICE_VALUES_SIGNALS_TRADES_PNL_OR_RETURNS",
    "DO_NOT_SELECT_SYMBOLS_MONTHS_OR_PROPOSALS_BY_RETURN",
    "DO_NOT_OPEN_2025_2026_OR_FORWARD_DATA",
    "DO_NOT_CREATE_PINE_PAPER_SANDBOX_LIVE_OR_CAPITAL_PERMISSION",
]
V3_KNOWN_BLOCKED_OR_RETIRED_LINEAGES = [
    "JAM_REVERSAL_V1_QUARANTINED",
    "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY_RETIRED_PRE_RETURN",
    "P02_PREMIUM_CONVERGENCE_SPOT_PERP_BASIS_NONSELECTABLE_RELATED",
    "P03_NEGATIVE_FUNDING_REVERSE_CARRY_BORROW_BLOCKED",
    "R3_CROSS_SECTIONAL_MOMENTUM_NO_CANDIDATE",
    "R31_R4_PATH_QUALITY_RETIRED",
    "SLOW_BREAKOUT_SPOT_V1_RETIRED",
    "TREND_PULLBACK_V1_RETIRED",
    "U1_VOLATILITY_MANAGED_BROAD_SPOT_BETA_RETIRED",
    "VOLATILITY_BREAKOUT_V1_RETIRED",
]
V3_REQUIRED_SUCCESSOR_BINDINGS = [
    "CANDIDATE_SOURCE_BYTES_RUNTIME_AND_VERSION",
    "CONTAMINATION_AND_PROJECT_WIDE_MULTIPLICITY_ACCOUNTING",
    "DATA_PARTITIONS_TRANSFORMATIONS_AND_COVERAGE_HASHES",
    "DECISION_GATES_AND_AUTOMATIC_STOP_RULE",
    "EXACT_SIGNAL_POSITION_SIZING_AND_EXIT_ARITHMETIC",
    "EXECUTION_FEES_SLIPPAGE_CAPACITY_AND_FAILURE_SEMANTICS",
    "MECHANISM_SPECIFIC_POINT_IN_TIME_METADATA_POLICY",
    "ONE_SELECTABLE_PARAMETER_SET",
    "RUN_MATRIX_TEMPORAL_FOLDS_AND_CONCENTRATION_DIAGNOSTICS",
    "UNTOUCHED_VALIDATION_HOLDOUT_FORWARD_AND_PROMOTION_PATH",
]
V3_DISCOVERY_STAGES = [
    "01_FREEZE_CHARTER_AND_P01_STOP_LINEAGE",
    "02_PROPOSE_AT_MOST_THREE_INDEPENDENT_THEORIES_NO_OUTCOMES",
    "03_FREEZE_AND_RUN_PROPOSAL_SOURCE_EXECUTION_FEASIBILITY_NO_RETURNS",
    "04_SELECT_ZERO_OR_ONE_PRIMARY_WITHOUT_PARAMETERS",
    "05_FREEZE_SOURCE_ACQUISITION_AND_ONE_SHOT_DEVELOPMENT_PROTOCOL",
    "06_DEVELOPMENT_FALSIFICATION_2023_2024",
    "07_INTERNAL_VALIDATION_2025_ONLY_IF_DEVELOPMENT_PASSES",
    "08_FINAL_HOLDOUT_2026_H1_ONLY_IF_VALIDATION_PASSES",
    "09_FORWARD_PAPER_ONLY_IF_FINAL_HOLDOUT_PASSES",
]
V3_STOP_CONDITIONS = [
    "ANY_BOUND_PREDECESSOR_HASH_OR_AUDIT_FAILS",
    "PROPOSAL_IS_NOT_INDEPENDENT_OF_A_RETIRED_OR_BLOCKED_LINEAGE",
    "POINT_IN_TIME_SOURCE_EXECUTION_OR_FINANCING_IS_NOT_FEASIBLE",
    "PAYLOAD_COVERAGE_IS_BELOW_A_PREDECLARED_PROPOSAL_MINIMUM",
    "MISSING_ROW_POLICY_IS_DEFINED_AFTER_PRIMARY_SELECTION",
    "PRIMARY_OR_PARAMETER_IS_SELECTED_USING_MARKET_OUTCOMES",
    "PROPOSAL_OR_MULTIPLICITY_BUDGET_IS_BREACHED",
]
V3_ALLOWED_NEXT_DECISIONS = [
    "FREEZE_ONE_INDEPENDENT_PRIMARY_FOR_SOURCE_AND_PROTOCOL_DESIGN",
    "NO_FEASIBLE_INDEPENDENT_MECHANISM_STOP_RESEARCH",
]
V3_TIMESTAMP_COVERAGE_FIELDS = [
    "archive_identity_and_checksum",
    "boundary_completeness",
    "continuity_gap_count",
    "duplicate_timestamp_count",
    "first_timestamp",
    "last_timestamp",
    "missing_timestamp_count",
    "row_count",
    "schema_identity",
]


class V3DiscoveryPartitionBoundary(BaseModel):
    partition: Literal["DEVELOPMENT", "VALIDATION", "HOLDOUT", "FORWARD"]
    start: datetime
    end: datetime | None
    role: Literal[
        "SOURCE_FEASIBILITY_ONLY_NO_STRATEGY_OUTCOMES",
        "FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
        "FINAL_ELIGIBILITY_HOLDOUT",
        "LOCKED_FORWARD_EVIDENCE",
    ]
    access: Literal[
        "TIMESTAMP_SCHEMA_COVERAGE_ONLY",
        "SEALED_FOR_INDEPENDENT_MECHANISM",
        "SEALED_AND_NOT_IMPORTED",
        "LOCKED",
    ]

    model_config = ConfigDict(extra="forbid")

    @field_validator("start", "end")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None

    @model_validator(mode="after")
    def validate_boundary(self) -> V3DiscoveryPartitionBoundary:
        expected = {
            "DEVELOPMENT": (
                "2023-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
                "SOURCE_FEASIBILITY_ONLY_NO_STRATEGY_OUTCOMES",
                "TIMESTAMP_SCHEMA_COVERAGE_ONLY",
            ),
            "VALIDATION": (
                "2025-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
                "SEALED_FOR_INDEPENDENT_MECHANISM",
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
            raise ValueError(f"V3 {self.partition} boundary changed")
        return self


class V3MechanismDiscoveryCharter(BaseModel):
    schema_version: Literal[
        "aurex-v3-independent-mechanism-discovery-charter-v1"
    ] = V3_DISCOVERY_CHARTER_SCHEMA_VERSION
    charter_id: Literal["v3-independent-mechanism-discovery-v1"] = (
        "v3-independent-mechanism-discovery-v1"
    )
    charter_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_V3_PROPOSAL_SCREEN"] = (
        "FROZEN_PRE_V3_PROPOSAL_SCREEN"
    )
    v2_discovery_charter_evidence_hash: str
    v2_theory_screen_evidence_hash: str
    p01_protocol_evidence_hash: str
    p01_acquisition_result_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    p01_final_decision: Literal[
        "STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA"
    ]
    p01_qualified_symbol_count: Literal[0] = 0
    p01_return_metrics_calculated: list[str] = Field(default_factory=list)
    research_scope: Literal[
        "INDEPENDENT_DATA_FEASIBLE_MECHANISM_DISCOVERY"
    ] = "INDEPENDENT_DATA_FEASIBLE_MECHANISM_DISCOVERY"
    partition_boundaries: list[V3DiscoveryPartitionBoundary] = Field(
        min_length=4,
        max_length=4,
    )
    required_theory_and_feasibility_evidence: list[str]
    theory_source_policy: list[str]
    payload_feasibility_policy: list[str]
    forbidden_derivations: list[str]
    known_blocked_or_retired_lineages: list[str]
    required_successor_bindings: list[str]
    discovery_stages: list[str]
    stop_conditions: list[str]
    allowed_next_decisions: list[str]
    permitted_timestamp_coverage_fields: list[str]
    maximum_theory_proposals: Literal[3] = 3
    maximum_selected_primary_mechanisms: Literal[1] = 1
    maximum_return_tested_mechanisms_under_charter: Literal[0] = 0
    maximum_parameter_sets_under_charter: Literal[0] = 0
    successor_maximum_selectable_parameter_sets: Literal[1] = 1
    may_reuse_p01_payload_for_coverage_only: Literal[True] = True
    may_inspect_market_numeric_values: Literal[False] = False
    may_calculate_signals_trades_or_returns: Literal[False] = False
    selection_creates_candidate: Literal[False] = False
    development_outcomes_open: Literal[False] = False
    validation_data_open: Literal[False] = False
    holdout_data_open: Literal[False] = False
    forward_data_open: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    preexisting_v3_successor_artifacts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=6)
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "v2_discovery_charter_evidence_hash",
        "v2_theory_screen_evidence_hash",
        "p01_protocol_evidence_hash",
        "p01_acquisition_result_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "charter_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "p01_return_metrics_calculated",
        "required_theory_and_feasibility_evidence",
        "theory_source_policy",
        "payload_feasibility_policy",
        "forbidden_derivations",
        "known_blocked_or_retired_lineages",
        "required_successor_bindings",
        "discovery_stages",
        "stop_conditions",
        "allowed_next_decisions",
        "permitted_timestamp_coverage_fields",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_v3_successor_artifacts",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_charter(self) -> V3MechanismDiscoveryCharter:
        expected_lists = {
            "required_theory_and_feasibility_evidence": (
                V3_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE
            ),
            "theory_source_policy": V3_THEORY_SOURCE_POLICY,
            "payload_feasibility_policy": V3_PAYLOAD_FEASIBILITY_POLICY,
            "forbidden_derivations": V3_FORBIDDEN_DERIVATIONS,
            "known_blocked_or_retired_lineages": (
                V3_KNOWN_BLOCKED_OR_RETIRED_LINEAGES
            ),
            "required_successor_bindings": V3_REQUIRED_SUCCESSOR_BINDINGS,
            "discovery_stages": V3_DISCOVERY_STAGES,
            "stop_conditions": V3_STOP_CONDITIONS,
            "allowed_next_decisions": V3_ALLOWED_NEXT_DECISIONS,
            "permitted_timestamp_coverage_fields": V3_TIMESTAMP_COVERAGE_FIELDS,
        }
        for field_name, expected in expected_lists.items():
            if getattr(self, field_name) != sorted(expected):
                raise ValueError(f"V3 charter {field_name} changed")
        if [item.partition for item in self.partition_boundaries] != [
            "DEVELOPMENT",
            "VALIDATION",
            "HOLDOUT",
            "FORWARD",
        ]:
            raise ValueError("V3 charter partition order changed")
        if (
            self.p01_return_metrics_calculated
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
            or self.preexisting_v3_successor_artifacts
        ):
            raise ValueError("V3 charter must predate proposal outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected_hash:
            raise ValueError("V3 charter hash does not match")
        return self


def build_v3_mechanism_discovery_charter(
    **values,
) -> V3MechanismDiscoveryCharter:
    payload = {
        "schema_version": V3_DISCOVERY_CHARTER_SCHEMA_VERSION,
        "charter_id": "v3-independent-mechanism-discovery-v1",
        "charter_version": "1.0.0",
        "status": "FROZEN_PRE_V3_PROPOSAL_SCREEN",
        "research_scope": "INDEPENDENT_DATA_FEASIBLE_MECHANISM_DISCOVERY",
        "p01_qualified_symbol_count": 0,
        "p01_return_metrics_calculated": [],
        "maximum_theory_proposals": 3,
        "maximum_selected_primary_mechanisms": 1,
        "maximum_return_tested_mechanisms_under_charter": 0,
        "maximum_parameter_sets_under_charter": 0,
        "successor_maximum_selectable_parameter_sets": 1,
        "may_reuse_p01_payload_for_coverage_only": True,
        "may_inspect_market_numeric_values": False,
        "may_calculate_signals_trades_or_returns": False,
        "selection_creates_candidate": False,
        "development_outcomes_open": False,
        "validation_data_open": False,
        "holdout_data_open": False,
        "forward_data_open": False,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        "preexisting_v3_successor_artifacts": [],
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    for field_name in (
        "p01_return_metrics_calculated",
        "required_theory_and_feasibility_evidence",
        "theory_source_policy",
        "payload_feasibility_policy",
        "forbidden_derivations",
        "known_blocked_or_retired_lineages",
        "required_successor_bindings",
        "discovery_stages",
        "stop_conditions",
        "allowed_next_decisions",
        "permitted_timestamp_coverage_fields",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_v3_successor_artifacts",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V3MechanismDiscoveryCharter(
        **payload,
        charter_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_mechanism_discovery_charter(
    charter: V3MechanismDiscoveryCharter,
) -> bool:
    return charter.charter_evidence_hash == universe_evidence_hash(
        charter.model_dump(exclude={"charter_evidence_hash"})
    )
