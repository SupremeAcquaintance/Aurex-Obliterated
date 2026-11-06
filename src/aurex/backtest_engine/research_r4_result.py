from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_r4_engine import R4ReplayMetrics
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R4_RESULT_LEDGER_SCHEMA_VERSION = "aurex-r4-validation-result-ledger-v1"
R4_REQUIRED_GATE_IDS = [
    "base_cost_completed_trades",
    "base_cost_maximum_drawdown_percent",
    "base_cost_net_pl",
    "base_cost_profit_factor",
    "double_cost_net_pl",
    "leave_one_market_out_positive_fraction",
    "positive_quarterly_folds",
    "single_symbol_gross_profit_fraction",
    "top_five_gross_profit_fraction",
]
R4_MONTH_KEYS = [f"2025-{month:02d}" for month in range(1, 13)]


class R4ValidationReplayReceipt(BaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    category: Literal["OVERALL", "QUARTERLY_FOLD", "LEAVE_ONE_MARKET_OUT"]
    variant_id: Literal["path_quality_spot_v1"] = "path_quality_spot_v1"
    variant_version: Literal["1.0.0"] = "1.0.0"
    variant_role: Literal["PRIMARY"] = "PRIMARY"
    cost_multiplier: Decimal = Field(gt=0)
    fold_id: str | None = Field(default=None, max_length=128)
    omitted_symbols: list[str] = Field(default_factory=list)
    artifact_relative_path: str = Field(min_length=1, max_length=500)
    request_evidence_hash: str
    result_evidence_hash: str
    artifact_sha256: str
    metrics: R4ReplayMetrics

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_evidence_hash", "result_evidence_hash", "artifact_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("omitted_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})


class R4GateResult(BaseModel):
    gate_id: str = Field(min_length=1, max_length=128)
    passed: bool
    observed: str = Field(min_length=1, max_length=500)
    requirement: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")


class R4ValidationResultLedger(BaseModel):
    schema_version: Literal["aurex-r4-validation-result-ledger-v1"] = (
        R4_RESULT_LEDGER_SCHEMA_VERSION
    )
    study_id: Literal["r4-path-quality-spot-validation-v1"] = (
        "r4-path-quality-spot-validation-v1"
    )
    study_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE"] = "COMPLETE"
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    validation_dataset_bundle_evidence_hash: str
    candidate_protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    run_package_evidence_hash: str
    market_data_evidence_hash: str
    planned_replay_count: Literal[42] = 42
    completed_replay_count: Literal[42] = 42
    replay_receipts: list[R4ValidationReplayReceipt] = Field(
        min_length=42, max_length=42
    )
    primary_variant_id: Literal["path_quality_spot_v1"] = "path_quality_spot_v1"
    monthly_net_returns: dict[str, Decimal]
    positive_quarterly_folds: int = Field(ge=0, le=4)
    leave_one_market_out_positive_fraction: Decimal = Field(ge=0, le=1)
    base_cost_termination_writeoff_count: int = Field(ge=0)
    base_cost_termination_writeoff_net_pl: Decimal
    gates: list[R4GateResult] = Field(min_length=9, max_length=9)
    verdict: Literal[
        "PERMIT_PINE_PARITY_REVIEW_ONLY",
        "RETIRE_R4_CANDIDATE",
    ]
    creates_eligible_strategy: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    permits_pine_parity_review: bool
    ledger_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "validation_dataset_bundle_evidence_hash",
        "candidate_protocol_evidence_hash",
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
    def validate_ledger(self) -> R4ValidationResultLedger:
        run_ids = [receipt.run_id for receipt in self.replay_receipts]
        if run_ids != sorted(run_ids) or len(run_ids) != len(set(run_ids)):
            raise ValueError("R4 receipts must be uniquely sorted")
        gate_ids = [gate.gate_id for gate in self.gates]
        if gate_ids != R4_REQUIRED_GATE_IDS:
            raise ValueError("R4 ledger must preserve every required gate")
        if list(self.monthly_net_returns) != R4_MONTH_KEYS:
            raise ValueError("R4 ledger requires the exact 12 validation months")
        all_passed = all(gate.passed for gate in self.gates)
        expected_verdict = (
            "PERMIT_PINE_PARITY_REVIEW_ONLY"
            if all_passed
            else "RETIRE_R4_CANDIDATE"
        )
        if self.verdict != expected_verdict:
            raise ValueError("R4 verdict does not match the all-gates rule")
        if self.permits_pine_parity_review != all_passed:
            raise ValueError("R4 Pine permission does not match the gate verdict")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"ledger_evidence_hash"})
        )
        if self.ledger_evidence_hash != expected_hash:
            raise ValueError("R4 ledger hash does not match its evidence")
        return self


def build_r4_validation_result_ledger(**values) -> R4ValidationResultLedger:
    payload = {
        "schema_version": R4_RESULT_LEDGER_SCHEMA_VERSION,
        "study_id": "r4-path-quality-spot-validation-v1",
        "study_version": "1.0.0",
        "status": "COMPLETE",
        "planned_replay_count": 42,
        "primary_variant_id": "path_quality_spot_v1",
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
        "PERMIT_PINE_PARITY_REVIEW_ONLY"
        if all_passed
        else "RETIRE_R4_CANDIDATE"
    )
    payload["creates_eligible_strategy"] = False
    payload["creates_paper_eligibility"] = False
    payload["creates_live_eligibility"] = False
    payload["permits_pine_parity_review"] = all_passed
    return R4ValidationResultLedger(
        **payload,
        ledger_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r4_validation_result_ledger(
    ledger: R4ValidationResultLedger,
) -> bool:
    return ledger.ledger_evidence_hash == universe_evidence_hash(
        ledger.model_dump(exclude={"ledger_evidence_hash"})
    )
