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

V2_DERIVATIVES_FOUNDATION_PROTOCOL_SCHEMA_VERSION = (
    "aurex-v2-synthetic-derivatives-foundation-protocol-v1"
)
V2_FOUNDATION_SCENARIO_IDS = [
    "S01_FULL_OPEN_FUNDING_CLOSE_RECONCILE",
    "S02_FIRST_LEG_PARTIAL_SECOND_REJECT_ROLLBACK",
    "S03_DUPLICATE_FILL_IDEMPOTENCY",
    "S04_DUPLICATE_FUNDING_IDEMPOTENCY",
    "S05_OPEN_TIMEOUT_CANCEL_AND_ROLLBACK",
    "S06_INITIAL_MARGIN_PREFLIGHT_REJECTION",
    "S07_MAINTENANCE_BREACH_LIQUIDATION",
    "S08_ADL_REDUCTION_KILL_AND_FLATTEN",
    "S09_POSITION_RECONCILIATION_DRIFT",
    "S10_FEE_RECONCILIATION_DRIFT",
    "S11_KILL_SWITCH_REJECTS_OPEN_ALLOWS_REDUCE_ONLY",
    "S12_ASYMMETRIC_PARTIAL_FILLS_REACH_HEDGE",
    "S13_NEGATIVE_FUNDING_SHORT_PAYS",
    "S14_PARTIAL_CLOSE_COMPLETES_WITHOUT_RESIDUAL",
]


class V2DerivativesAccountingProtocol(BaseModel):
    decimal_precision_digits: Literal[28] = 28
    money_quantum: Literal["0.00000001"] = "0.00000001"
    quantity_quantum: Literal["0.00000001"] = "0.00000001"
    fee_formula: Literal["ABS_FILL_QUANTITY_TIMES_PRICE_TIMES_FEE_RATE"] = (
        "ABS_FILL_QUANTITY_TIMES_PRICE_TIMES_FEE_RATE"
    )
    spot_cash_formula: Literal[
        "NEGATIVE_SIGNED_SPOT_QUANTITY_TIMES_PRICE_MINUS_FEE"
    ] = "NEGATIVE_SIGNED_SPOT_QUANTITY_TIMES_PRICE_MINUS_FEE"
    perp_open_notional_cash_exchange: Literal[False] = False
    perp_unrealized_pl_formula: Literal[
        "SIGNED_PERP_QUANTITY_TIMES_MARK_MINUS_AVERAGE_ENTRY"
    ] = "SIGNED_PERP_QUANTITY_TIMES_MARK_MINUS_AVERAGE_ENTRY"
    perp_realized_pl_formula: Literal[
        "CLOSED_ABSOLUTE_QUANTITY_TIMES_EXIT_MINUS_ENTRY_TIMES_POSITION_SIGN"
    ] = "CLOSED_ABSOLUTE_QUANTITY_TIMES_EXIT_MINUS_ENTRY_TIMES_POSITION_SIGN"
    funding_cashflow_formula: Literal[
        "NEGATIVE_SIGNED_PERP_QUANTITY_TIMES_MARK_PRICE_TIMES_FUNDING_RATE"
    ] = "NEGATIVE_SIGNED_PERP_QUANTITY_TIMES_MARK_PRICE_TIMES_FUNDING_RATE"
    equity_formula: Literal[
        "CASH_PLUS_SPOT_QUANTITY_TIMES_SPOT_MARK_PLUS_PERP_UNREALIZED_PL"
    ] = "CASH_PLUS_SPOT_QUANTITY_TIMES_SPOT_MARK_PLUS_PERP_UNREALIZED_PL"
    collateral_formula: Literal[
        "CASH_PLUS_SPOT_VALUE_TIMES_HAIRCUT_PLUS_PERP_UNREALIZED_PL"
    ] = "CASH_PLUS_SPOT_VALUE_TIMES_HAIRCUT_PLUS_PERP_UNREALIZED_PL"
    every_fill_fee_and_funding_event_ledgered: Literal[True] = True
    event_hash_chain_required: Literal[True] = True
    duplicate_event_mutation_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V2PairedExecutionProtocol(BaseModel):
    pair_direction: Literal["LONG_SPOT_SHORT_USD_M_PERPETUAL"] = (
        "LONG_SPOT_SHORT_USD_M_PERPETUAL"
    )
    lifecycle: list[str]
    target_base_quantity: Decimal
    hedge_tolerance_base_quantity: Decimal
    maximum_open_seconds: Literal[5] = 5
    leg_submission_order: Literal["SPOT_THEN_PERPETUAL"] = (
        "SPOT_THEN_PERPETUAL"
    )
    both_legs_acknowledged_before_hedged: Literal[True] = True
    partial_fills_supported: Literal[True] = True
    outstanding_orders_cancelled_before_rollback: Literal[True] = True
    rollback_is_reduce_only: Literal[True] = True
    rollback_fills_include_fees: Literal[True] = True
    rollback_failure_enables_kill_switch: Literal[True] = True
    opening_while_killed_allowed: Literal[False] = False
    reduce_only_while_killed_allowed: Literal[True] = True
    pyramiding_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("lifecycle")
    @classmethod
    def validate_lifecycle(cls, value: list[str]) -> list[str]:
        expected = [
            "FLAT",
            "OPENING",
            "HEDGED",
            "CLOSING",
            "ROLLBACK",
            "LIQUIDATED",
            "KILLED",
        ]
        if value != expected:
            raise ValueError("V2 paired lifecycle changed")
        return value

    @model_validator(mode="after")
    def validate_quantities(self) -> V2PairedExecutionProtocol:
        if self.target_base_quantity != Decimal("1"):
            raise ValueError("V2 synthetic target quantity changed")
        if self.hedge_tolerance_base_quantity != Decimal("0.001"):
            raise ValueError("V2 hedge tolerance changed")
        return self


class V2DerivativesRiskProtocol(BaseModel):
    synthetic_initial_cash: Decimal
    synthetic_reference_price: Decimal
    taker_fee_rate: Decimal
    spot_collateral_haircut: Decimal
    initial_margin_rate: Decimal
    maintenance_margin_rate: Decimal
    liquidation_fee_rate: Decimal
    minimum_initial_margin_buffer_ratio: Decimal
    liquidation_rule: Literal[
        "COLLATERAL_LESS_THAN_OR_EQUAL_TO_MAINTENANCE_PLUS_LIQUIDATION_FEE_BUFFER"
    ] = (
        "COLLATERAL_LESS_THAN_OR_EQUAL_TO_MAINTENANCE_PLUS_LIQUIDATION_FEE_BUFFER"
    )
    liquidation_closes_perpetual_and_spot: Literal[True] = True
    adl_reduction_is_external_perp_fill: Literal[True] = True
    adl_delta_breach_enables_kill_switch: Literal[True] = True
    stale_mark_blocks_risk_evaluation: Literal[True] = True
    negative_collateral_blocks_new_open: Literal[True] = True
    pretrade_margin_gate_required: Literal[True] = True
    kill_switch_cancels_open_orders: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_risk_constants(self) -> V2DerivativesRiskProtocol:
        expected = {
            "synthetic_initial_cash": Decimal("10000"),
            "synthetic_reference_price": Decimal("100"),
            "taker_fee_rate": Decimal("0.0005"),
            "spot_collateral_haircut": Decimal("0.95"),
            "initial_margin_rate": Decimal("0.10"),
            "maintenance_margin_rate": Decimal("0.05"),
            "liquidation_fee_rate": Decimal("0.005"),
            "minimum_initial_margin_buffer_ratio": Decimal("1.25"),
        }
        for field, value in expected.items():
            if getattr(self, field) != value:
                raise ValueError(f"V2 risk constant changed: {field}")
        if not (
            Decimal("0") < self.maintenance_margin_rate
            < self.initial_margin_rate
            < Decimal("1")
        ):
            raise ValueError("V2 margin-rate ordering is invalid")
        return self


class V2DerivativesReconciliationProtocol(BaseModel):
    quantity_tolerance: Literal["0.00000001"] = "0.00000001"
    money_tolerance: Literal["0.00000001"] = "0.00000001"
    required_fields: list[str]
    any_discrepancy_status: Literal["FAIL"] = "FAIL"
    discrepancy_enables_kill_switch: Literal[True] = True
    matched_snapshot_required_after_each_scenario: Literal[True] = True
    internal_ledger_is_not_exchange_truth: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("required_fields")
    @classmethod
    def validate_fields(cls, value: list[str]) -> list[str]:
        expected = [
            "cash",
            "cumulative_fees",
            "cumulative_funding",
            "perp_average_entry",
            "perp_quantity",
            "perp_realized_pl",
            "spot_quantity",
        ]
        normalized = sorted(set(value))
        if normalized != expected:
            raise ValueError("V2 reconciliation field set changed")
        return normalized


class V2DerivativesSyntheticScenario(BaseModel):
    scenario_id: str
    purpose: str = Field(min_length=20, max_length=500)
    required_assertions: list[str] = Field(min_length=2)
    uses_real_market_data: Literal[False] = False
    calculates_strategy_return: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("required_assertions")
    @classmethod
    def normalize_assertions(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class V2DerivativesFoundationProtocol(BaseModel):
    schema_version: Literal[
        "aurex-v2-synthetic-derivatives-foundation-protocol-v1"
    ] = V2_DERIVATIVES_FOUNDATION_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["v2-synthetic-derivatives-foundation-v1"] = (
        "v2-synthetic-derivatives-foundation-v1"
    )
    protocol_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_SYNTHETIC_EXECUTION"] = (
        "FROZEN_PRE_SYNTHETIC_EXECUTION"
    )
    capability_audit_evidence_hash: str
    source_census_result_evidence_hash: str
    acquisition_protocol_evidence_hash: str
    pilot_result_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    synthetic_only: Literal[True] = True
    accounting: V2DerivativesAccountingProtocol
    paired_execution: V2PairedExecutionProtocol
    risk: V2DerivativesRiskProtocol
    reconciliation: V2DerivativesReconciliationProtocol
    scenarios: list[V2DerivativesSyntheticScenario] = Field(
        min_length=14, max_length=14
    )
    all_scenarios_must_pass: Literal[True] = True
    failure_decision: Literal[
        "STOP_V2_DERIVATIVES_FOUNDATION_AND_REPAIR_WITHOUT_STRATEGY_TEST"
    ] = "STOP_V2_DERIVATIVES_FOUNDATION_AND_REPAIR_WITHOUT_STRATEGY_TEST"
    pass_decision: Literal[
        "PERMIT_SEPARATE_V2_NO_RETURN_DISCOVERY_CHARTER"
    ] = "PERMIT_SEPARATE_V2_NO_RETURN_DISCOVERY_CHARTER"
    pass_creates_strategy_candidate: Literal[False] = False
    authorizes_real_market_data_import: Literal[False] = False
    authorizes_strategy_return_calculation: Literal[False] = False
    authorizes_mechanism_selection: Literal[False] = False
    creates_strategy_eligibility: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    validation_data_loaded: Literal[False] = False
    holdout_data_loaded: Literal[False] = False
    forward_data_loaded: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=5)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "capability_audit_evidence_hash",
        "source_census_result_evidence_hash",
        "acquisition_protocol_evidence_hash",
        "pilot_result_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("strategy_outcome_fields_inspected", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> V2DerivativesFoundationProtocol:
        scenario_ids = [scenario.scenario_id for scenario in self.scenarios]
        if scenario_ids != V2_FOUNDATION_SCENARIO_IDS:
            raise ValueError("V2 synthetic scenario matrix changed")
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("V2 synthetic scenarios contain duplicates")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("V2 synthetic protocol must predate outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("V2 synthetic protocol hash does not match")
        return self


def build_v2_derivatives_foundation_protocol(
    **values,
) -> V2DerivativesFoundationProtocol:
    payload = {
        "schema_version": V2_DERIVATIVES_FOUNDATION_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "v2-synthetic-derivatives-foundation-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_PRE_SYNTHETIC_EXECUTION",
        "synthetic_only": True,
        "all_scenarios_must_pass": True,
        "failure_decision": (
            "STOP_V2_DERIVATIVES_FOUNDATION_AND_REPAIR_WITHOUT_STRATEGY_TEST"
        ),
        "pass_decision": "PERMIT_SEPARATE_V2_NO_RETURN_DISCOVERY_CHARTER",
        "pass_creates_strategy_candidate": False,
        "authorizes_real_market_data_import": False,
        "authorizes_strategy_return_calculation": False,
        "authorizes_mechanism_selection": False,
        "creates_strategy_eligibility": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "validation_data_loaded": False,
        "holdout_data_loaded": False,
        "forward_data_loaded": False,
        "strategy_outcome_fields_inspected": [],
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    for field in ("strategy_outcome_fields_inspected", "limitations"):
        payload[field] = sorted(set(payload[field]))
    payload["scenarios"] = sorted(
        payload["scenarios"], key=lambda item: item.scenario_id
    )
    return V2DerivativesFoundationProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_derivatives_foundation_protocol(
    protocol: V2DerivativesFoundationProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
