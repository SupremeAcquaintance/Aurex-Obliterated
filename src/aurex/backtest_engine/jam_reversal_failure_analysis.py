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

JAM_FAILURE_ANALYSIS_SCHEMA_VERSION = (
    "aurex-jam-reversal-spot-failure-analysis-v1"
)
JAM_FAILURE_ANALYSIS_ID = "jam-reversal-spot-v1.0.1-failure-analysis"
JAM_FAILURE_CLASSIFICATION = (
    "INSUFFICIENT_SAMPLE_AND_FEE_FRAGILE_NON_DURABLE_EDGE"
)
JAM_FAILURE_DECISION = (
    "STOP_CURRENT_VERSION_AND_RETURN_TO_PREREGISTERED_HYPOTHESIS_DESIGN"
)
JAM_FAILURE_FINDINGS = (
    "SAMPLE_TOO_SPARSE_FOR_RELIABILITY",
    "BASE_COSTS_EXCEED_GROSS_PRICE_EDGE",
    "OUT_OF_SAMPLE_EDGE_IS_NEGATIVE",
    "WALK_FORWARD_STABILITY_IS_ABSENT",
    "DRAWDOWN_GATE_PASS_DOES_NOT_OFFSET_EDGE_FAILURE",
    "CONSUMED_WINDOW_CANNOT_BE_USED_TO_RESCUE_THIS_VERSION",
)
JAM_SUCCESSOR_REQUIREMENTS = (
    "STATE_AN_ECONOMIC_MECHANISM_CHANGE_BEFORE_SELECTING_PARAMETERS",
    "DO_NOT_SWEEP_PARAMETERS_ON_THE_CONSUMED_2023_2025_JAM_WINDOW",
    "USE_A_NEW_STRATEGY_VERSION_AND_FREEZE_ITS_PROTOCOL_BEFORE_EVALUATION",
    "RESERVE_GENUINELY_UNOPENED_DATA_FOR_THE_SUCCESSOR_DECISION",
    "REQUIRE_POSITIVE_BASE_COST_AND_COST_STRESS_EVIDENCE",
    "REQUIRE_MINIMUM_SAMPLE_OOS_AND_WALK_FORWARD_GATES",
    "KEEP_PAPER_TESTNET_STRATEGY_AND_LIVE_AUTHORITY_FALSE_UNTIL_ACCEPTANCE",
)


class JamFailureFacts(BaseModel):
    total_trades: int = Field(ge=0)
    in_sample_trades: int = Field(ge=0)
    out_of_sample_trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    walk_forward_windows: int = Field(ge=0)
    walk_forward_passed_windows: int = Field(ge=0)
    gross_before_modeled_costs: Decimal
    base_modeled_costs: Decimal = Field(ge=0)
    base_net_pl: Decimal
    base_profit_factor: Decimal | None
    base_expectancy: Decimal
    out_of_sample_net_pl: Decimal
    out_of_sample_profit_factor: Decimal | None
    out_of_sample_expectancy: Decimal
    max_drawdown: Decimal = Field(ge=0)
    max_drawdown_gate: Decimal = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_reconciliations(self) -> JamFailureFacts:
        if self.wins + self.losses != self.total_trades:
            raise ValueError("Jam failure facts must reconcile wins and losses")
        if self.in_sample_trades + self.out_of_sample_trades != self.total_trades:
            raise ValueError("Jam failure facts must reconcile sample assignments")
        reconciliation_delta = (
            self.gross_before_modeled_costs
            - self.base_modeled_costs
            - self.base_net_pl
        )
        if abs(reconciliation_delta) > Decimal("1e-24"):
            raise ValueError("Jam gross edge minus modeled costs must equal net P/L")
        if self.walk_forward_passed_windows > self.walk_forward_windows:
            raise ValueError("Passed walk-forward windows cannot exceed all windows")
        return self


class JamReversalFailureAnalysis(BaseModel):
    schema_version: Literal[
        "aurex-jam-reversal-spot-failure-analysis-v1"
    ] = JAM_FAILURE_ANALYSIS_SCHEMA_VERSION
    analysis_id: Literal[
        "jam-reversal-spot-v1.0.1-failure-analysis"
    ] = JAM_FAILURE_ANALYSIS_ID
    analyzed_at: datetime
    strategy: Literal["jam_reversal_spot_v1"] = "jam_reversal_spot_v1"
    strategy_version: Literal["1.0.1"] = "1.0.1"
    status: Literal["COMPLETE_VERSION_RETIRED"] = "COMPLETE_VERSION_RETIRED"
    analysis_boundary: Literal[
        "STORED_DECISION_EVIDENCE_ONLY_NO_NEW_RETURN_INSPECTION"
    ] = "STORED_DECISION_EVIDENCE_ONLY_NO_NEW_RETURN_INSPECTION"
    historical_decision_path: Literal[
        "data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json"
    ] = "data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json"
    historical_decision_evidence_hash: str
    protocol_evidence_hash: str
    replay_record_evidence_hash: str
    validation_evidence_hash: str
    contamination_ledger_path: Literal[
        "data/evidence/strategy_contamination_ledger_v2.json"
    ] = "data/evidence/strategy_contamination_ledger_v2.json"
    contamination_ledger_evidence_hash: str
    source_audits_passed: bool
    failed_acceptance_gates: list[str] = Field(min_length=1)
    facts: JamFailureFacts
    failure_classification: Literal[
        "INSUFFICIENT_SAMPLE_AND_FEE_FRAGILE_NON_DURABLE_EDGE"
    ] = JAM_FAILURE_CLASSIFICATION
    findings: tuple[str, ...]
    next_research_decision: Literal[
        "STOP_CURRENT_VERSION_AND_RETURN_TO_PREREGISTERED_HYPOTHESIS_DESIGN"
    ] = JAM_FAILURE_DECISION
    successor_requirements: tuple[str, ...]
    authorizes_parameter_retuning: bool = False
    authorizes_new_candidate: bool = False
    authorizes_forward_paper: bool = False
    authorizes_testnet_strategy_orders: bool = False
    authorizes_production: bool = False
    authorizes_live: bool = False
    analysis_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("analyzed_at")
    @classmethod
    def normalize_analyzed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "historical_decision_evidence_hash",
        "protocol_evidence_hash",
        "replay_record_evidence_hash",
        "validation_evidence_hash",
        "contamination_ledger_evidence_hash",
        "analysis_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_analysis(self) -> JamReversalFailureAnalysis:
        if not self.source_audits_passed:
            raise ValueError("Jam failure analysis requires audited source evidence")
        if self.findings != JAM_FAILURE_FINDINGS:
            raise ValueError("Jam failure-analysis findings are fixed")
        if self.successor_requirements != JAM_SUCCESSOR_REQUIREMENTS:
            raise ValueError("Jam successor requirements are fixed")
        if any(
            (
                self.authorizes_parameter_retuning,
                self.authorizes_new_candidate,
                self.authorizes_forward_paper,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("Jam failure analysis cannot grant trading authority")
        if self.facts.total_trades >= 60:
            raise ValueError("Jam sample-size classification no longer applies")
        if self.facts.base_net_pl >= 0 or self.facts.base_expectancy >= 0:
            raise ValueError("Jam fee-net failure classification no longer applies")
        if self.facts.out_of_sample_expectancy >= 0:
            raise ValueError("Jam OOS failure classification no longer applies")
        if self.facts.walk_forward_passed_windows != 0:
            raise ValueError("Jam walk-forward failure classification no longer applies")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"analysis_evidence_hash"})
        )
        if self.analysis_evidence_hash != expected_hash:
            raise ValueError("Jam failure-analysis hash does not match its evidence")
        return self


def audit_jam_reversal_failure_analysis(
    analysis: JamReversalFailureAnalysis,
) -> bool:
    expected_hash = universe_evidence_hash(
        analysis.model_dump(exclude={"analysis_evidence_hash"})
    )
    return analysis.analysis_evidence_hash == expected_hash
