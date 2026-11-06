from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_u1_engine import U1ReplayMetrics
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

U1_RESULT_LEDGER_SCHEMA_VERSION = (
    "aurex-u1-volatility-managed-broad-spot-beta-result-ledger-v1"
)
U1_REQUIRED_GATE_IDS = [
    "benchmark_maximum_drawdown_not_worse",
    "benchmark_realized_volatility_reduction",
    "benchmark_return_to_drawdown_not_worse",
    "deterministic_replay_audit",
    "double_cost_net_pl",
    "leave_one_market_out_positive_fraction",
    "primary_completed_trades",
    "primary_maximum_drawdown_percent",
    "primary_net_pl",
    "primary_positive_temporal_folds",
    "primary_profit_factor",
    "single_symbol_gross_profit_fraction",
    "top_five_gross_profit_fraction",
]
U1_MONTH_KEYS = [
    f"{year}-{month:02d}"
    for year, start_month, end_month in ((2023, 2, 12), (2024, 1, 12))
    for month in range(start_month, end_month + 1)
]


class U1ReplayReceipt(BaseModel):
    run_id: str = Field(min_length=1, max_length=240)
    category: Literal[
        "OVERALL",
        "BENCHMARK",
        "TEMPORAL_FOLD",
        "LEAVE_ONE_MARKET_OUT",
    ]
    variant_role: Literal["PRIMARY", "BENCHMARK"]
    cost_multiplier: Decimal = Field(gt=0)
    fold_id: str | None = Field(default=None, max_length=128)
    omitted_symbols: list[str] = Field(default_factory=list)
    artifact_relative_path: str = Field(min_length=1, max_length=500)
    request_evidence_hash: str
    result_evidence_hash: str
    artifact_sha256: str
    deterministic_replay_audit_passed: Literal[True] = True
    metrics: U1ReplayMetrics

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_evidence_hash", "result_evidence_hash", "artifact_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("omitted_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})


class U1GateResult(BaseModel):
    gate_id: str = Field(min_length=1, max_length=128)
    passed: bool
    observed: str = Field(min_length=1, max_length=500)
    requirement: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")


class U1ResultLedger(BaseModel):
    schema_version: Literal[
        "aurex-u1-volatility-managed-broad-spot-beta-result-ledger-v1"
    ] = U1_RESULT_LEDGER_SCHEMA_VERSION
    study_id: Literal["u1-volatility-managed-broad-spot-beta-development-v1"] = (
        "u1-volatility-managed-broad-spot-beta-development-v1"
    )
    study_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE"] = "COMPLETE"
    discovery_charter_evidence_hash: str
    theory_screen_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    contamination_ledger_evidence_hash: str
    primary_protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    run_package_evidence_hash: str
    market_data_evidence_hash: str
    planned_replay_count: Literal[47] = 47
    completed_replay_count: Literal[47] = 47
    replay_receipts: list[U1ReplayReceipt] = Field(min_length=47, max_length=47)
    primary_variant_id: Literal["volatility_managed_broad_spot_beta_v1"] = (
        "volatility_managed_broad_spot_beta_v1"
    )
    benchmark_id: Literal["static_broad_spot_equal_weight_v1"] = (
        "static_broad_spot_equal_weight_v1"
    )
    monthly_net_returns: dict[str, Decimal]
    positive_temporal_folds: int = Field(ge=0, le=8)
    leave_one_market_out_positive_fraction: Decimal = Field(ge=0, le=1)
    all_replay_audits_passed: Literal[True] = True
    base_cost_termination_writeoff_count: int = Field(ge=0)
    base_cost_termination_writeoff_net_pl: Decimal
    primary_base_metrics: U1ReplayMetrics
    benchmark_base_metrics: U1ReplayMetrics
    gates: list[U1GateResult] = Field(min_length=13, max_length=13)
    verdict: Literal[
        "PERMIT_FREEZE_2025_INTERNAL_VALIDATION_CANDIDATE",
        "STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA",
    ]
    development_passes_all_gates: bool
    creates_eligible_strategy: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    permits_validation_data_access: Literal[False] = False
    permits_holdout_or_forward_access: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    permits_freeze_2025_internal_validation_candidate: bool
    ledger_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "theory_screen_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "contamination_ledger_evidence_hash",
        "primary_protocol_evidence_hash",
        "execution_specification_evidence_hash",
        "run_package_evidence_hash",
        "market_data_evidence_hash",
        "ledger_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("monthly_net_returns")
    @classmethod
    def normalize_months(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def validate_ledger(self) -> U1ResultLedger:
        run_ids = [receipt.run_id for receipt in self.replay_receipts]
        if run_ids != sorted(run_ids) or len(run_ids) != len(set(run_ids)):
            raise ValueError("U1 receipts must be uniquely sorted")
        gate_ids = [gate.gate_id for gate in self.gates]
        if gate_ids != U1_REQUIRED_GATE_IDS:
            raise ValueError("U1 ledger must preserve every required gate")
        if list(self.monthly_net_returns) != U1_MONTH_KEYS:
            raise ValueError("U1 ledger requires the exact 23 development months")
        all_passed = all(gate.passed for gate in self.gates)
        expected_verdict = (
            "PERMIT_FREEZE_2025_INTERNAL_VALIDATION_CANDIDATE"
            if all_passed
            else "STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
        )
        if (
            self.verdict != expected_verdict
            or self.development_passes_all_gates != all_passed
            or self.permits_freeze_2025_internal_validation_candidate != all_passed
        ):
            raise ValueError("U1 verdict does not match the all-gates rule")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"ledger_evidence_hash"})
        )
        if self.ledger_evidence_hash != expected_hash:
            raise ValueError("U1 ledger hash does not match its evidence")
        return self


def build_u1_result_ledger(**values) -> U1ResultLedger:
    payload = {
        "schema_version": U1_RESULT_LEDGER_SCHEMA_VERSION,
        "study_id": "u1-volatility-managed-broad-spot-beta-development-v1",
        "study_version": "1.0.0",
        "status": "COMPLETE",
        "planned_replay_count": 47,
        "primary_variant_id": "volatility_managed_broad_spot_beta_v1",
        "benchmark_id": "static_broad_spot_equal_weight_v1",
        **values,
    }
    payload["generated_at"] = normalize_timestamp(payload["generated_at"])
    payload["replay_receipts"] = sorted(
        payload["replay_receipts"], key=lambda receipt: receipt.run_id
    )
    payload["gates"] = sorted(payload["gates"], key=lambda gate: gate.gate_id)
    payload["monthly_net_returns"] = dict(
        sorted(payload["monthly_net_returns"].items())
    )
    payload["completed_replay_count"] = len(payload["replay_receipts"])
    all_passed = all(gate.passed for gate in payload["gates"])
    payload["verdict"] = (
        "PERMIT_FREEZE_2025_INTERNAL_VALIDATION_CANDIDATE"
        if all_passed
        else "STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
    )
    payload["development_passes_all_gates"] = all_passed
    payload["creates_eligible_strategy"] = False
    payload["creates_paper_eligibility"] = False
    payload["creates_live_eligibility"] = False
    payload["permits_validation_data_access"] = False
    payload["permits_holdout_or_forward_access"] = False
    payload["permits_pine_parity"] = False
    payload["permits_freeze_2025_internal_validation_candidate"] = all_passed
    return U1ResultLedger(
        **payload,
        ledger_evidence_hash=universe_evidence_hash(payload),
    )


def audit_u1_result_ledger(ledger: U1ResultLedger) -> bool:
    return ledger.ledger_evidence_hash == universe_evidence_hash(
        ledger.model_dump(exclude={"ledger_evidence_hash"})
    )
