from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_engine import R3ReplayMetrics
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_RESULT_LEDGER_SCHEMA_VERSION = "aurex-r3-study-result-ledger-v1"
R3_REQUIRED_GATE_IDS = [
    "double_cost_net_pl",
    "leave_one_market_out_positive_fraction",
    "primary_completed_trades",
    "primary_maximum_drawdown_percent",
    "primary_net_pl",
    "primary_positive_quarterly_folds",
    "primary_profit_factor",
    "single_symbol_gross_profit_fraction",
    "supportive_falsification_variants",
    "top_five_gross_profit_fraction",
]


class R3StudyReplayReceipt(BaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    category: Literal["OVERALL", "QUARTERLY_FOLD", "LEAVE_ONE_MARKET_OUT"]
    variant_id: str = Field(min_length=1, max_length=128)
    variant_role: Literal["PRIMARY", "FALSIFICATION"]
    cost_multiplier: Decimal = Field(gt=0)
    fold_id: str | None = Field(default=None, max_length=128)
    omitted_symbols: list[str] = Field(default_factory=list)
    artifact_relative_path: str = Field(min_length=1, max_length=500)
    request_evidence_hash: str
    result_evidence_hash: str
    artifact_sha256: str
    metrics: R3ReplayMetrics

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_evidence_hash", "result_evidence_hash", "artifact_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("omitted_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})


class R3GateResult(BaseModel):
    gate_id: str = Field(min_length=1, max_length=128)
    passed: bool
    observed: str = Field(min_length=1, max_length=500)
    requirement: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")


class R3StudyResultLedger(BaseModel):
    schema_version: Literal["aurex-r3-study-result-ledger-v1"] = (
        R3_RESULT_LEDGER_SCHEMA_VERSION
    )
    study_id: str = Field(min_length=1, max_length=128)
    study_version: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    status: Literal["COMPLETE"] = "COMPLETE"
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    run_package_evidence_hash: str
    market_data_evidence_hash: str
    planned_replay_count: int = Field(gt=0)
    completed_replay_count: int = Field(gt=0)
    replay_receipts: list[R3StudyReplayReceipt] = Field(min_length=1)
    primary_variant_id: str = Field(min_length=1, max_length=128)
    monthly_net_returns: dict[str, Decimal]
    positive_fold_counts: dict[str, int]
    leave_one_market_out_positive_fraction: Decimal
    supportive_falsification_variants: list[str]
    gates: list[R3GateResult] = Field(min_length=1)
    verdict: Literal["ADVANCE_PRIMARY_TO_R4", "NO_CANDIDATE"]
    ledger_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "protocol_evidence_hash",
        "execution_specification_evidence_hash",
        "run_package_evidence_hash",
        "market_data_evidence_hash",
        "ledger_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("supportive_falsification_variants")
    @classmethod
    def normalize_variants(cls, value: list[str]) -> list[str]:
        return sorted({variant.strip() for variant in value if variant.strip()})

    @model_validator(mode="after")
    def validate_ledger(self) -> "R3StudyResultLedger":
        run_ids = [receipt.run_id for receipt in self.replay_receipts]
        if run_ids != sorted(run_ids) or len(run_ids) != len(set(run_ids)):
            raise ValueError("R3 result receipts must be uniquely sorted by run ID")
        if self.planned_replay_count != self.completed_replay_count:
            raise ValueError("R3 study did not complete every planned replay")
        if self.completed_replay_count != len(self.replay_receipts):
            raise ValueError("R3 result receipt count does not match completion count")
        gate_ids = [gate.gate_id for gate in self.gates]
        if gate_ids != sorted(gate_ids) or len(gate_ids) != len(set(gate_ids)):
            raise ValueError("R3 gates must be uniquely sorted by gate ID")
        if gate_ids != R3_REQUIRED_GATE_IDS:
            raise ValueError("R3 result ledger must preserve every required gate")
        expected_verdict = (
            "ADVANCE_PRIMARY_TO_R4"
            if all(gate.passed for gate in self.gates)
            else "NO_CANDIDATE"
        )
        if self.verdict != expected_verdict:
            raise ValueError("R3 verdict does not match the all-gates-required rule")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"ledger_evidence_hash"})
        )
        if self.ledger_evidence_hash != expected_hash:
            raise ValueError("R3 result-ledger hash does not match its evidence")
        return self


def build_r3_study_result_ledger(**values) -> R3StudyResultLedger:
    payload = {
        "schema_version": R3_RESULT_LEDGER_SCHEMA_VERSION,
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
    payload["positive_fold_counts"] = dict(
        sorted(payload["positive_fold_counts"].items())
    )
    payload["supportive_falsification_variants"] = sorted(
        set(payload["supportive_falsification_variants"])
    )
    payload["completed_replay_count"] = len(payload["replay_receipts"])
    payload["verdict"] = (
        "ADVANCE_PRIMARY_TO_R4"
        if all(gate.passed for gate in payload["gates"])
        else "NO_CANDIDATE"
    )
    return R3StudyResultLedger(
        **payload,
        ledger_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r3_study_result_ledger(ledger: R3StudyResultLedger) -> bool:
    return ledger.ledger_evidence_hash == universe_evidence_hash(
        ledger.model_dump(exclude={"ledger_evidence_hash"})
    )
