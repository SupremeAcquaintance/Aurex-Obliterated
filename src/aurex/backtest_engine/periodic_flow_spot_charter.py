from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

PERIODIC_FLOW_CHARTER_SCHEMA_VERSION = (
    "aurex-periodic-perpetual-flow-spot-charter-v1"
)
PERIODIC_FLOW_CHARTER_ID = "periodic-perpetual-flow-to-spot-charter-v1"
PERIODIC_FLOW_MECHANISM_ID = (
    "Q1-PERIODIC-PERPETUAL-ORDER-FLOW-SPOT-CONTINUATION"
)
PERIODIC_FLOW_DECISION = "FREEZE_Q1_FOR_METADATA_AND_SCHEMA_FEASIBILITY_ONLY"
PERIODIC_FLOW_NEXT_AUTHORIZATION = (
    "AUTHORIZE_Q1_METADATA_ONLY_BTCUSDT_ARCHIVE_CENSUS"
)
PERIODIC_FLOW_SOURCE_IDS = (
    "BINANCE-PUBLIC-DATA",
    "HANSEN-KIM-KIMBROUGH-2024",
    "KIM-HANSEN-2026",
    "WEN-BOURI-XU-ZHAO-2022",
)
PERIODIC_FLOW_BINDING_PATHS = (
    "data/evidence/aurex_strategy_factory_contract_v1.json",
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v3.json",
    "data/evidence/aurex_strategy_factory_readiness_current_result_v3.json",
    "data/evidence/binance_spot_testnet_sandbox_profile_v1.json",
    "data/evidence/jam_successor_development_outcome_result_v1.json",
    "data/evidence/strategy_contamination_ledger_v2.json",
    "data/evidence/v3_mechanism_discovery_charter_v1.json",
    "data/evidence/v3_mechanism_feasibility_screen_v1.json",
    "data/evidence/v3_mechanism_proposal_register_v1.json",
    "data/evidence/v3_p02_aggtrades_census_result_v1.json",
    "data/evidence/v3_p02_payload_pilot_stop_result_v1.json",
)
PERIODIC_FLOW_FEASIBILITY_GATES = (
    "FACTORY_CONTRACT_AND_READINESS_LINEAGE_VALID",
    "V3P02_TRANSPORT_STOP_PRESERVED_WITHOUT_RETRY_OR_OUTCOME_REUSE",
    "BTCUSDT_SPOT_AND_USDM_AGGTRADE_ARCHIVE_METADATA_CHECKSUMS_PRESENT",
    "SPOT_MICROSECOND_AND_FUTURES_MILLISECOND_TIMESTAMPS_NORMALIZED",
    "AGGRESSOR_SIDE_MAPPING_PROVEN_FROM_EXCHANGE_NATIVE_FIELDS",
    "QUARTER_HOUR_OBSERVATION_IS_CAUSAL_AND_CLOSES_BEFORE_DECISION",
    "SPOT_AND_PERPETUAL_CLOCK_ALIGNMENT_IS_DETERMINISTIC",
    "NO_GAP_FORWARD_FILL_INTERPOLATION_OR_SYNTHETIC_TRADE_ALLOWED",
    "FULL_TAKER_FEES_AND_ADVERSE_SLIPPAGE_REQUIRED",
    "TESTNET_ZERO_FEES_AND_FILLS_EXCLUDED_FROM_EDGE_EVIDENCE",
    "NO_DERIVATIVES_ORDER_MARGIN_FUNDING_OR_LIQUIDATION_AUTHORITY",
    "ONE_PARAMETER_SET_FROZEN_BEFORE_DEVELOPMENT_OUTCOMES",
    "VALIDATION_HOLDOUT_AND_FORWARD_PARTITIONS_REMAIN_SEALED",
    "UNIVERSAL_FACTORY_COST_INFERENCE_MULTIPLICITY_AND_HOLDOUT_GATES_BIND",
)


class PeriodicFlowEvidenceBinding(BaseModel):
    path: str
    file_sha256: str
    evidence_hash: str
    decision: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256", "evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class PeriodicFlowResearchSource(BaseModel):
    source_id: str
    source_type: Literal[
        "OFFICIAL_EXCHANGE_DOCUMENTATION",
        "PEER_REVIEWED_RESEARCH",
        "RESEARCH_PREPRINT",
    ]
    title: str
    reference: str
    bounded_claims: tuple[str, ...] = Field(min_length=1)
    does_not_prove_edge: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)


class PeriodicFlowOperatorScope(BaseModel):
    environment: Literal["BINANCE_SPOT_TESTNET"] = "BINANCE_SPOT_TESTNET"
    execution_product: Literal["SPOT_ONLY"] = "SPOT_ONLY"
    execution_symbol: Literal["BTCUSDT"] = "BTCUSDT"
    signal_market: Literal["BINANCE_USDM_PERPETUAL_BTCUSDT"] = (
        "BINANCE_USDM_PERPETUAL_BTCUSDT"
    )
    direction: Literal["LONG_OR_CASH_NO_SHORT"] = "LONG_OR_CASH_NO_SHORT"
    maximum_effective_leverage: Literal["1"] = "1"
    simulated_equity_usd: Literal["100"] = "100"
    maximum_per_trade_loss_usd: Literal["0.50"] = "0.50"
    maximum_daily_loss_usd: Literal["1.00"] = "1.00"
    maximum_total_loss_usd: Literal["10.00"] = "10.00"
    paid_data_budget_usd: Literal["0"] = "0"
    production_account_verified: Literal[False] = False
    real_capital_authorized: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class PeriodicFlowMechanism(BaseModel):
    mechanism_id: Literal[
        "Q1-PERIODIC-PERPETUAL-ORDER-FLOW-SPOT-CONTINUATION"
    ] = PERIODIC_FLOW_MECHANISM_ID
    name: Literal["Periodic perpetual order-flow continuation into BTC spot"] = (
        "Periodic perpetual order-flow continuation into BTC spot"
    )
    causal_actor: str
    economic_premise: str
    ex_ante_direction: str
    who_pays: str
    persistence_case: str
    decay_and_failure_risks: tuple[str, ...] = Field(min_length=1)
    falsifiable_predictions: tuple[str, ...] = Field(min_length=1)
    required_input_families: tuple[str, ...] = Field(min_length=1)
    observation_boundary: str
    execution_expression: str
    exact_parameters_defined: tuple[str, ...] = ()
    exact_pine_compatible: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_mechanism(self) -> PeriodicFlowMechanism:
        if self.exact_parameters_defined:
            raise ValueError("Q1 charter cannot define signal parameters")
        return self


class PeriodicFlowPartition(BaseModel):
    partition_id: str
    start: datetime
    end: datetime | None
    role: Literal[
        "DEVELOPMENT",
        "VALIDATION",
        "EXCLUDED_WASHOUT",
        "HOLDOUT",
        "FORWARD",
    ]
    state: Literal[
        "CLOSED_PENDING_SEPARATE_PROTOCOL",
        "SEALED",
        "EXCLUDED_FROM_ALL_SELECTION_AND_SCORING",
        "SEALED_FUTURE",
        "LOCKED_FORWARD",
    ]
    outcome_access_permitted: Literal[False] = False
    purpose: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("start", "end")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_partition(self) -> PeriodicFlowPartition:
        if self.end is not None and self.end <= self.start:
            raise ValueError("Q1 partition end must follow its start")
        if self.role == "FORWARD" and self.end is not None:
            raise ValueError("Q1 forward partition must be open-ended")
        return self


class PeriodicFlowSpotCharter(BaseModel):
    schema_version: Literal[
        "aurex-periodic-perpetual-flow-spot-charter-v1"
    ] = PERIODIC_FLOW_CHARTER_SCHEMA_VERSION
    charter_id: Literal[
        "periodic-perpetual-flow-to-spot-charter-v1"
    ] = PERIODIC_FLOW_CHARTER_ID
    frozen_at: datetime
    status: Literal["FROZEN_CHARTER_ONLY_NO_OUTCOMES"] = (
        "FROZEN_CHARTER_ONLY_NO_OUTCOMES"
    )
    authorization_record: Literal[
        "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY"
    ] = "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY"
    builder_contract_hash: str
    predecessor_bindings: tuple[PeriodicFlowEvidenceBinding, ...]
    research_sources: tuple[PeriodicFlowResearchSource, ...]
    operator_scope: PeriodicFlowOperatorScope
    mechanism: PeriodicFlowMechanism
    partitions: tuple[PeriodicFlowPartition, ...]
    feasibility_gates: tuple[str, ...]
    decision: Literal[
        "FREEZE_Q1_FOR_METADATA_AND_SCHEMA_FEASIBILITY_ONLY"
    ] = PERIODIC_FLOW_DECISION
    next_authorization: Literal[
        "AUTHORIZE_Q1_METADATA_ONLY_BTCUSDT_ARCHIVE_CENSUS"
    ] = PERIODIC_FLOW_NEXT_AUTHORIZATION
    family_predecessor_variant_count: Literal[1] = 1
    new_parameter_set_budget: Literal[1] = 1
    project_wide_variant_registry_required: Literal[True] = True
    market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    exact_parameters_defined: tuple[str, ...] = ()
    real_market_values_opened: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    qualified_strategy_count: Literal[0] = 0
    authorizes_archive_payload_download: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_pine_deployment: Literal[False] = False
    authorizes_paper_operation: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=1)
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("builder_contract_hash", "charter_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_charter(self) -> PeriodicFlowSpotCharter:
        if tuple(item.path for item in self.predecessor_bindings) != (
            PERIODIC_FLOW_BINDING_PATHS
        ):
            raise ValueError("Q1 predecessor evidence lineage changed")
        if tuple(item.source_id for item in self.research_sources) != (
            PERIODIC_FLOW_SOURCE_IDS
        ):
            raise ValueError("Q1 research source register changed")
        if self.feasibility_gates != PERIODIC_FLOW_FEASIBILITY_GATES:
            raise ValueError("Q1 feasibility gates changed")
        roles = tuple(item.role for item in self.partitions)
        if roles != (
            "DEVELOPMENT",
            "VALIDATION",
            "EXCLUDED_WASHOUT",
            "HOLDOUT",
            "FORWARD",
        ):
            raise ValueError("Q1 chronological partition plan changed")
        for previous, current in zip(
            self.partitions,
            self.partitions[1:],
            strict=False,
        ):
            if previous.end != current.start:
                raise ValueError("Q1 partitions must be contiguous")
        if any(
            (
                self.market_numeric_fields_inspected,
                self.return_metrics_calculated,
                self.exact_parameters_defined,
            )
        ):
            raise ValueError("Q1 charter cannot inspect outcomes or define parameters")
        if any(
            (
                self.authorizes_archive_payload_download,
                self.authorizes_parameter_definition,
                self.authorizes_return_testing,
                self.authorizes_validation_access,
                self.authorizes_holdout_access,
                self.authorizes_pine_deployment,
                self.authorizes_paper_operation,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("Q1 charter cannot grant execution or outcome authority")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected_hash:
            raise ValueError("Q1 charter evidence hash changed")
        return self


class PeriodicFlowSpotCharterAudit(BaseModel):
    schema_version: Literal[
        "aurex-periodic-perpetual-flow-spot-charter-audit-v1"
    ] = "aurex-periodic-perpetual-flow-spot-charter-audit-v1"
    audit_id: Literal["periodic-perpetual-flow-to-spot-charter-audit-v1"] = (
        "periodic-perpetual-flow-to-spot-charter-audit-v1"
    )
    audited_at: datetime
    charter_path: Literal[
        "data/evidence/periodic_flow_spot_charter_v1.json"
    ] = "data/evidence/periodic_flow_spot_charter_v1.json"
    charter_file_sha256: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    predecessor_binding_count: Literal[11] = 11
    research_source_count: Literal[4] = 4
    partition_count: Literal[5] = 5
    market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_Q1_CHARTER_RECONSTRUCTED_NO_AUTHORITY"] = (
        "PASS_Q1_CHARTER_RECONSTRUCTED_NO_AUTHORITY"
    )
    next_authorization: Literal[
        "AUTHORIZE_Q1_METADATA_ONLY_BTCUSDT_ARCHIVE_CENSUS"
    ] = PERIODIC_FLOW_NEXT_AUTHORIZATION
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "charter_file_sha256",
        "charter_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_audit_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSpotCharterAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 charter audit evidence hash changed")
        return self


def audit_periodic_flow_spot_charter(charter: PeriodicFlowSpotCharter) -> bool:
    expected = universe_evidence_hash(
        charter.model_dump(exclude={"charter_evidence_hash"})
    )
    return charter.charter_evidence_hash == expected


def audit_periodic_flow_spot_charter_audit(
    audit: PeriodicFlowSpotCharterAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected
