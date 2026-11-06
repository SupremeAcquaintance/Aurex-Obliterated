from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V4_DISCOVERY_CHARTER_SCHEMA_VERSION = (
    "aurex-v4-independent-mechanism-discovery-charter-v1"
)
V4_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE = [
    "AT_LEAST_THREE_INDEPENDENT_PRIMARY_OR_PEER_REVIEWED_SOURCES",
    "AT_LEAST_ONE_OFFICIAL_POINT_IN_TIME_DATA_OR_EXECUTION_SOURCE",
    "AT_LEAST_ONE_PEER_REVIEWED_ECONOMIC_OR_MARKET_STRUCTURE_SOURCE",
    "ECONOMIC_PREMISE_INDEPENDENT_OF_ALL_AUREX_OUTCOMES",
    "EXACT_POINT_IN_TIME_FIELDS_SCHEMA_AND_TEMPORAL_AVAILABILITY",
    "EXACT_SOURCE_TRANSPORT_PERSISTENCE_AND_RECOVERY_CONTRACT",
    "EXACT_PAYLOAD_LEVEL_TIMESTAMP_AND_COVERAGE_CONTRACT",
    "EXPLICIT_MISSING_ROW_SKIP_STOP_AND_NO_FILL_POLICY",
    "HISTORICAL_EXECUTION_FINANCING_METADATA_AND_CAPACITY_DEPENDENCIES",
    "MECHANISM_SPECIFIC_COST_RISK_AND_FAILURE_PATH",
    "PROJECT_WIDE_CONTAMINATION_AND_MULTIPLICITY_ACCOUNTING",
    "SPECIFIC_PRE_RETURN_FALSIFICATION_CONDITION",
    "UNTOUCHED_VALIDATION_HOLDOUT_AND_FORWARD_PATH",
]
V4_THEORY_SOURCE_POLICY = [
    "ALLOW_OFFICIAL_EXCHANGE_DATA_EXECUTION_AND_RISK_DOCUMENTATION",
    "ALLOW_PEER_REVIEWED_RESEARCH",
    "ALLOW_REPUTABLE_INSTITUTIONAL_WORKING_PAPERS",
    "REQUIRE_CLAIM_TO_SOURCE_MAPPING_AND_ACCESS_TIMESTAMPS",
    "REJECT_ANONYMOUS_SIGNALS_SOCIAL_POSTS_AND_MARKETING_CLAIMS",
    "REJECT_SOURCES_SELECTED_BECAUSE_THEY_MATCH_AUREX_OUTCOMES",
    "REJECT_UNDATED_CURRENT_DOCUMENTATION_AS_HISTORICAL_TRUTH",
]
V4_SOURCE_DATA_POLICY = [
    "AUDIT_ONLY_SOURCE_IDENTITY_SCHEMA_TIMESTAMPS_COUNTS_GAPS_AND_CHECKSUMS",
    "CLASSIFY_COMMON_SOURCE_OUTAGE_LISTING_GAP_AND_SYMBOL_SPECIFIC_GAP",
    "DEFINE_MECHANISM_SPECIFIC_SYNCHRONIZED_DECISION_EVENT_COVERAGE",
    "FREEZE_SOURCE_REVISION_AND_CHECKSUM_CHANGE_POLICY",
    "FORBID_FORWARD_FILL_BACKFILL_INTERPOLATION_AND_SYNTHETIC_ROWS",
    "FREEZE_SKIP_EXCLUSION_AND_STOP_RULES_BEFORE_PRIMARY_SELECTION",
    "REQUIRE_MINIMUM_EVENT_TEMPORAL_AND_CROSS_MARKET_BREADTH",
    "REQUIRE_FINAL_PAYLOAD_CHECKSUM_BEFORE_SCHEMA_OR_COVERAGE_CLAIMS",
]
V4_SOURCE_TRANSPORT_POLICY = [
    "APPEND_REQUEST_INTENT_BEFORE_EVERY_NETWORK_ATTEMPT",
    "APPEND_RESPONSE_STATUS_HEADERS_BYTES_HASH_AND_TIMESTAMPS_AFTER_EVERY_ATTEMPT",
    "COUNT_CUMULATIVE_ATTEMPTS_ACROSS_PROCESS_RESTARTS",
    "FREEZE_CONNECTION_READ_INACTIVITY_AND_TOTAL_WALL_CLOCK_TIMEOUTS",
    "FREEZE_UNIQUE_URL_ATTEMPT_RETRY_CONCURRENCY_BYTE_AND_STORAGE_BUDGETS",
    "PERSIST_EACH_COMPLETED_OBSERVATION_BEFORE_DEPENDENT_PAYLOAD_ACCESS",
    "PRESERVE_PARTIAL_BYTE_COUNT_AND_HASH_BEFORE_TRANSACTIONAL_CLEANUP",
    "PERMIT_RANGE_OR_RESUME_ONLY_IF_PREDECLARED_AND_FINAL_CHECKSUM_VERIFIES",
    "REQUIRE_METADATA_CENSUS_ARTIFACT_BEFORE_ANY_PAYLOAD_REQUEST",
    "REQUIRE_PREDECLARED_COMPLETE_REJECT_AND_TRANSPORT_STOP_ARTIFACT_SCHEMAS",
    "STOP_WITHOUT_AFTER_THE_FACT_RETRY_AMENDMENT_OR_BUDGET_EXPANSION",
    "FORBID_INFERENCE_OF_ANY_UNPRESERVED_OBSERVATION",
]
V4_EXECUTION_FEASIBILITY_POLICY = [
    "AUDIT_POINT_IN_TIME_FEES_FILTERS_AND_VENUE_STATE_BEFORE_SELECTION",
    "AUDIT_BORROW_MARGIN_FUNDING_LIQUIDATION_AND_COLLATERAL_IF_REQUIRED",
    "AUDIT_MULTI_LEG_ATOMICITY_ROLLBACK_IDEMPOTENCY_AND_RECONCILIATION_IF_REQUIRED",
    "FORBID_CANDLE_TOUCH_OR_BAR_RANGE_AS_FILL_OR_QUEUE_EVIDENCE",
    "REQUIRE_DETERMINISTIC_ORDER_ACK_FILL_POSITION_AND_BALANCE_RECONCILIATION_PATH",
    "REQUIRE_MECHANISM_SPECIFIC_LIQUIDITY_CAPACITY_AND_STALE_DATA_FAILURE_PATH",
    "REQUIRE_KILL_SWITCH_AND_MAXIMUM_LOSS_BOUND_BEFORE_ANY_PAPER_OR_LIVE_PATH",
    "USE_NO_CREDENTIALS_PRIVATE_ENDPOINTS_OR_REAL_ORDERS_DURING_DISCOVERY",
]
V4_FORBIDDEN_DERIVATIONS = [
    "DO_NOT_RETRY_REBRAND_OR_AMEND_ANY_V3_PROPOSAL",
    "DO_NOT_START_V3P02_FULL_AGGREGATE_TRADE_ACQUISITION",
    "DO_NOT_REUSE_V3_CLOCK_PHASE_AS_A_V4_PRIMARY",
    "DO_NOT_REUSE_V3_CROSS_ASSET_COINTEGRATION_AS_A_V4_PRIMARY",
    "DO_NOT_REUSE_V3_PASSIVE_LIQUIDITY_PROVISION_AS_A_V4_PRIMARY",
    "DO_NOT_REEXPRESS_RETIRED_TREND_BREAKOUT_PATH_BETA_CARRY_OR_REVERSAL_FAMILIES",
    "DO_NOT_USE_ANY_PRIOR_OUTCOME_BUCKET_AS_A_NEW_RULE",
    "DO_NOT_DEFINE_PARAMETERS_DURING_CHARTER_THEORY_OR_FEASIBILITY",
    "DO_NOT_INSPECT_PRICE_VALUES_SIGNALS_TRADES_PNL_OR_RETURNS",
    "DO_NOT_SELECT_SYMBOLS_MONTHS_SOURCES_OR_PROPOSALS_BY_RETURN",
    "DO_NOT_OPEN_2025_2026_OR_FORWARD_OUTCOMES",
    "DO_NOT_CREATE_PINE_PAPER_SANDBOX_LIVE_OR_CAPITAL_PERMISSION",
    "DO_NOT_CLAIM_EDGE_RELIABILITY_PROFITABILITY_OR_READINESS_WITHOUT_EVIDENCE",
]
V4_KNOWN_BLOCKED_OR_RETIRED_LINEAGES = [
    "JAM_REVERSAL_V1_QUARANTINED",
    "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY_RETIRED_PRE_RETURN",
    "P02_PREMIUM_CONVERGENCE_SPOT_PERP_BASIS_NONSELECTABLE_RELATED",
    "P03_NEGATIVE_FUNDING_REVERSE_CARRY_BORROW_BLOCKED",
    "R3_CROSS_SECTIONAL_MOMENTUM_NO_CANDIDATE",
    "R31_R4_PATH_QUALITY_RETIRED",
    "SLOW_BREAKOUT_SPOT_V1_RETIRED",
    "TREND_PULLBACK_V1_RETIRED",
    "U1_VOLATILITY_MANAGED_BROAD_SPOT_BETA_RETIRED",
    "V3P01_CROSS_ASSET_COINTEGRATION_EXECUTION_METADATA_REJECTED",
    "V3P02_CLOCK_PHASE_TRANSPORT_STOPPED_NO_SELECTION",
    "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_SOURCE_REJECTED",
    "VOLATILITY_BREAKOUT_V1_RETIRED",
]
V4_REQUIRED_SUCCESSOR_BINDINGS = [
    "APPEND_ONLY_TRANSPORT_JOURNAL_AND_INCREMENTAL_OBSERVATION_LEDGER",
    "CANDIDATE_SOURCE_BYTES_RUNTIME_AND_VERSION",
    "CONTAMINATION_AND_PROJECT_WIDE_MULTIPLICITY_ACCOUNTING",
    "DATA_PARTITIONS_TRANSFORMATIONS_AND_COVERAGE_HASHES",
    "DECISION_GATES_AND_AUTOMATIC_STOP_RULE",
    "EXACT_SIGNAL_POSITION_SIZING_AND_EXIT_ARITHMETIC",
    "EXECUTION_FEES_SLIPPAGE_CAPACITY_AND_FAILURE_SEMANTICS",
    "MECHANISM_SPECIFIC_POINT_IN_TIME_METADATA_POLICY",
    "ONE_SELECTABLE_PARAMETER_SET",
    "PREDECLARED_COMPLETE_REJECT_AND_TRANSPORT_STOP_RESULT_SCHEMAS",
    "RUN_MATRIX_TEMPORAL_FOLDS_AND_CONCENTRATION_DIAGNOSTICS",
    "SOURCE_REQUEST_RETRY_TIMEOUT_RESUME_BYTE_AND_STORAGE_BUDGETS",
    "UNTOUCHED_VALIDATION_HOLDOUT_FORWARD_AND_PROMOTION_PATH",
]
V4_DISCOVERY_STAGES = [
    "01_FREEZE_CHARTER_AND_V3_TERMINAL_LINEAGE",
    "02_PROPOSE_AT_MOST_THREE_INDEPENDENT_THEORIES_NO_OUTCOMES",
    "03_FREEZE_PROPOSAL_SOURCE_EXECUTION_AND_TRANSPORT_CONTRACTS",
    "04_RUN_PROPOSAL_FEASIBILITY_AND_PERSIST_ALL_TERMINAL_OUTCOMES_NO_RETURNS",
    "05_SELECT_ZERO_OR_ONE_PRIMARY_WITHOUT_PARAMETERS",
    "06_FREEZE_SOURCE_ACQUISITION_AND_ONE_SHOT_DEVELOPMENT_PROTOCOL",
    "07_DEVELOPMENT_FALSIFICATION_2023_2024",
    "08_INTERNAL_VALIDATION_2025_ONLY_IF_DEVELOPMENT_PASSES",
    "09_FINAL_HOLDOUT_2026_H1_ONLY_IF_VALIDATION_PASSES",
    "10_FORWARD_PAPER_ONLY_IF_FINAL_HOLDOUT_PASSES",
]
V4_STOP_CONDITIONS = [
    "ANY_BOUND_PREDECESSOR_HASH_OR_AUDIT_FAILS",
    "ANY_NETWORK_ATTEMPT_LACKS_A_DURABLE_REQUEST_INTENT_OR_RESPONSE_RECORD",
    "CUMULATIVE_REQUEST_OR_RESOURCE_BUDGET_CANNOT_BE_RECONSTRUCTED",
    "POINT_IN_TIME_SOURCE_EXECUTION_FINANCING_OR_CAPACITY_IS_NOT_FEASIBLE",
    "PROPOSAL_IS_A_DIRECT_RETRY_REBRAND_OR_DERIVATION_OF_A_BLOCKED_LINEAGE",
    "PAYLOAD_COVERAGE_IS_BELOW_A_PREDECLARED_PROPOSAL_MINIMUM",
    "PARTIAL_OR_FAILED_TRANSPORT_EVIDENCE_CANNOT_BE_PRESERVED",
    "PRIMARY_PARAMETER_SOURCE_OR_MARKET_IS_SELECTED_USING_OUTCOMES",
    "PROPOSAL_OR_PROJECT_WIDE_MULTIPLICITY_BUDGET_IS_BREACHED",
    "RETRY_TIMEOUT_RESUME_SKIP_OR_MISSING_ROW_POLICY_CHANGES_AFTER_OBSERVATION",
]
V4_ALLOWED_NEXT_DECISIONS = [
    "FREEZE_ONE_INDEPENDENT_PRIMARY_FOR_SOURCE_AND_PROTOCOL_DESIGN",
    "SELECT_ZERO_V4_PRIMARY_MECHANISMS_AND_CLOSE_V4",
]
V4_PERMITTED_FEASIBILITY_FIELDS = [
    "archive_or_endpoint_identity",
    "boundary_completeness",
    "checksum_and_revision_identity",
    "content_length_and_storage_projection",
    "continuity_gap_count",
    "duplicate_timestamp_count",
    "first_and_last_timestamp",
    "http_status_and_selected_headers",
    "missing_timestamp_count",
    "request_attempt_and_elapsed_time",
    "row_count",
    "schema_identity",
    "transport_journal_identity_and_hash",
]


class V4DiscoveryPartitionBoundary(BaseModel):
    partition: Literal["DEVELOPMENT", "VALIDATION", "HOLDOUT", "FORWARD"]
    start: datetime
    end: datetime | None
    role: Literal[
        "SOURCE_FEASIBILITY_ONLY_NO_MARKET_VALUES_OR_OUTCOMES",
        "FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
        "FINAL_ELIGIBILITY_HOLDOUT",
        "LOCKED_FORWARD_EVIDENCE",
    ]
    access: Literal[
        "SOURCE_METADATA_TIMESTAMP_SCHEMA_ONLY",
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
    def validate_boundary(self) -> V4DiscoveryPartitionBoundary:
        expected = {
            "DEVELOPMENT": (
                "2023-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
                "SOURCE_FEASIBILITY_ONLY_NO_MARKET_VALUES_OR_OUTCOMES",
                "SOURCE_METADATA_TIMESTAMP_SCHEMA_ONLY",
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
            raise ValueError(f"V4 {self.partition} boundary changed")
        return self


class V4MechanismDiscoveryCharter(BaseModel):
    schema_version: Literal[
        "aurex-v4-independent-mechanism-discovery-charter-v1"
    ] = V4_DISCOVERY_CHARTER_SCHEMA_VERSION
    charter_id: Literal["v4-independent-mechanism-discovery-v1"] = (
        "v4-independent-mechanism-discovery-v1"
    )
    charter_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_V4_PROPOSAL_SCREEN"] = (
        "FROZEN_PRE_V4_PROPOSAL_SCREEN"
    )
    v3_discovery_charter_evidence_hash: str
    v3_proposal_register_evidence_hash: str
    v3_feasibility_screen_evidence_hash: str
    v3p01_terminal_evidence_hash: str
    v3p02_terminal_evidence_hash: str
    v3p03_terminal_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    v3_final_decision: Literal["SELECT_ZERO_V3_PRIMARY_MECHANISMS"]
    v3_selected_primary_count: Literal[0] = 0
    v3_return_metrics_calculated: list[str] = Field(default_factory=list)
    research_scope: Literal[
        "INDEPENDENT_CRASH_SAFE_DATA_FEASIBLE_MECHANISM_DISCOVERY"
    ] = "INDEPENDENT_CRASH_SAFE_DATA_FEASIBLE_MECHANISM_DISCOVERY"
    partition_boundaries: list[V4DiscoveryPartitionBoundary] = Field(
        min_length=4,
        max_length=4,
    )
    required_theory_and_feasibility_evidence: list[str]
    theory_source_policy: list[str]
    source_data_policy: list[str]
    source_transport_policy: list[str]
    execution_feasibility_policy: list[str]
    forbidden_derivations: list[str]
    known_blocked_or_retired_lineages: list[str]
    required_successor_bindings: list[str]
    discovery_stages: list[str]
    stop_conditions: list[str]
    allowed_next_decisions: list[str]
    permitted_feasibility_fields: list[str]
    maximum_theory_proposals: Literal[3] = 3
    maximum_selected_primary_mechanisms: Literal[1] = 1
    maximum_return_tested_mechanisms_under_charter: Literal[0] = 0
    maximum_parameter_sets_under_charter: Literal[0] = 0
    successor_maximum_selectable_parameter_sets: Literal[1] = 1
    may_reuse_verified_v3_source_artifacts_for_feasibility_only: Literal[
        True
    ] = True
    charter_authorizes_network_requests: Literal[False] = False
    successor_transport_contract_required_before_network: Literal[True] = True
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
    preexisting_v4_successor_artifacts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=8)
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "v3_discovery_charter_evidence_hash",
        "v3_proposal_register_evidence_hash",
        "v3_feasibility_screen_evidence_hash",
        "v3p01_terminal_evidence_hash",
        "v3p02_terminal_evidence_hash",
        "v3p03_terminal_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "charter_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "v3_return_metrics_calculated",
        "required_theory_and_feasibility_evidence",
        "theory_source_policy",
        "source_data_policy",
        "source_transport_policy",
        "execution_feasibility_policy",
        "forbidden_derivations",
        "known_blocked_or_retired_lineages",
        "required_successor_bindings",
        "discovery_stages",
        "stop_conditions",
        "allowed_next_decisions",
        "permitted_feasibility_fields",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_v4_successor_artifacts",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_charter(self) -> V4MechanismDiscoveryCharter:
        expected_lists = {
            "required_theory_and_feasibility_evidence": (
                V4_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE
            ),
            "theory_source_policy": V4_THEORY_SOURCE_POLICY,
            "source_data_policy": V4_SOURCE_DATA_POLICY,
            "source_transport_policy": V4_SOURCE_TRANSPORT_POLICY,
            "execution_feasibility_policy": V4_EXECUTION_FEASIBILITY_POLICY,
            "forbidden_derivations": V4_FORBIDDEN_DERIVATIONS,
            "known_blocked_or_retired_lineages": (
                V4_KNOWN_BLOCKED_OR_RETIRED_LINEAGES
            ),
            "required_successor_bindings": V4_REQUIRED_SUCCESSOR_BINDINGS,
            "discovery_stages": V4_DISCOVERY_STAGES,
            "stop_conditions": V4_STOP_CONDITIONS,
            "allowed_next_decisions": V4_ALLOWED_NEXT_DECISIONS,
            "permitted_feasibility_fields": V4_PERMITTED_FEASIBILITY_FIELDS,
        }
        for field_name, expected in expected_lists.items():
            if getattr(self, field_name) != sorted(expected):
                raise ValueError(f"V4 charter {field_name} changed")
        if [item.partition for item in self.partition_boundaries] != [
            "DEVELOPMENT",
            "VALIDATION",
            "HOLDOUT",
            "FORWARD",
        ]:
            raise ValueError("V4 charter partition order changed")
        if (
            self.v3_return_metrics_calculated
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
            or self.preexisting_v4_successor_artifacts
        ):
            raise ValueError("V4 charter must predate V4 proposal outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected_hash:
            raise ValueError("V4 charter hash does not match")
        return self


def build_v4_mechanism_discovery_charter(
    **values,
) -> V4MechanismDiscoveryCharter:
    payload = {
        "schema_version": V4_DISCOVERY_CHARTER_SCHEMA_VERSION,
        "charter_id": "v4-independent-mechanism-discovery-v1",
        "charter_version": "1.0.0",
        "status": "FROZEN_PRE_V4_PROPOSAL_SCREEN",
        "research_scope": (
            "INDEPENDENT_CRASH_SAFE_DATA_FEASIBLE_MECHANISM_DISCOVERY"
        ),
        "v3_selected_primary_count": 0,
        "v3_return_metrics_calculated": [],
        "maximum_theory_proposals": 3,
        "maximum_selected_primary_mechanisms": 1,
        "maximum_return_tested_mechanisms_under_charter": 0,
        "maximum_parameter_sets_under_charter": 0,
        "successor_maximum_selectable_parameter_sets": 1,
        "may_reuse_verified_v3_source_artifacts_for_feasibility_only": True,
        "charter_authorizes_network_requests": False,
        "successor_transport_contract_required_before_network": True,
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
        "preexisting_v4_successor_artifacts": [],
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    for field_name in (
        "v3_return_metrics_calculated",
        "required_theory_and_feasibility_evidence",
        "theory_source_policy",
        "source_data_policy",
        "source_transport_policy",
        "execution_feasibility_policy",
        "forbidden_derivations",
        "known_blocked_or_retired_lineages",
        "required_successor_bindings",
        "discovery_stages",
        "stop_conditions",
        "allowed_next_decisions",
        "permitted_feasibility_fields",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_v4_successor_artifacts",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V4MechanismDiscoveryCharter(
        **payload,
        charter_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_mechanism_discovery_charter(
    charter: V4MechanismDiscoveryCharter,
) -> bool:
    return charter.charter_evidence_hash == universe_evidence_hash(
        charter.model_dump(exclude={"charter_evidence_hash"})
    )
