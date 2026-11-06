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

R31_RESULT_LEDGER_SCHEMA_VERSION = "aurex-r3.1-study-result-ledger-v1"
R31_REQUIRED_GATE_IDS = [
    "double_cost_net_pl",
    "leave_one_market_out_positive_fraction",
    "primary_completed_trades",
    "primary_maximum_drawdown_percent",
    "primary_net_pl",
    "primary_positive_quarterly_folds",
    "primary_profit_factor",
    "single_symbol_gross_profit_fraction",
    "top_five_gross_profit_fraction",
]
R31_MONTH_KEYS = [
    f"{year:04d}-{month:02d}"
    for year, first_month, last_month in ((2023, 7, 12), (2024, 1, 12))
    for month in range(first_month, last_month + 1)
]


class R31StudyReplayReceipt(BaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    category: Literal["OVERALL", "QUARTERLY_FOLD", "LEAVE_ONE_MARKET_OUT"]
    variant_id: Literal["xsmom_path_quality_84d_14d_primary"] = (
        "xsmom_path_quality_84d_14d_primary"
    )
    variant_role: Literal["PRIMARY"] = "PRIMARY"
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


class R31GateResult(BaseModel):
    gate_id: str = Field(min_length=1, max_length=128)
    passed: bool
    observed: str = Field(min_length=1, max_length=500)
    requirement: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")


class R31StudyResultLedger(BaseModel):
    schema_version: Literal["aurex-r3.1-study-result-ledger-v1"] = (
        R31_RESULT_LEDGER_SCHEMA_VERSION
    )
    study_id: Literal["r3.1-cross-sectional-path-quality-spot-v1"] = (
        "r3.1-cross-sectional-path-quality-spot-v1"
    )
    study_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE"] = "COMPLETE"
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    run_package_evidence_hash: str
    market_data_evidence_hash: str
    planned_replay_count: Literal[44] = 44
    completed_replay_count: Literal[44] = 44
    replay_receipts: list[R31StudyReplayReceipt] = Field(min_length=44, max_length=44)
    primary_variant_id: Literal["xsmom_path_quality_84d_14d_primary"] = (
        "xsmom_path_quality_84d_14d_primary"
    )
    monthly_net_returns: dict[str, Decimal]
    positive_quarterly_folds: int = Field(ge=0, le=6)
    leave_one_market_out_positive_fraction: Decimal = Field(ge=0, le=1)
    gates: list[R31GateResult] = Field(min_length=9, max_length=9)
    verdict: Literal["PERMIT_R4_PREREGISTRATION", "STOP_FAMILY"]
    creates_eligible_strategy: Literal[False] = False
    opens_validation_partition: Literal[False] = False
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

    @field_validator("monthly_net_returns")
    @classmethod
    def normalize_months(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def validate_ledger(self) -> "R31StudyResultLedger":
        run_ids = [receipt.run_id for receipt in self.replay_receipts]
        if run_ids != sorted(run_ids) or len(run_ids) != len(set(run_ids)):
            raise ValueError("R3.1 receipts must be uniquely sorted")
        gate_ids = [gate.gate_id for gate in self.gates]
        if gate_ids != R31_REQUIRED_GATE_IDS:
            raise ValueError("R3.1 ledger must preserve every required gate")
        if list(self.monthly_net_returns) != R31_MONTH_KEYS:
            raise ValueError("R3.1 ledger requires the exact 18 development months")
        expected_verdict = (
            "PERMIT_R4_PREREGISTRATION"
            if all(gate.passed for gate in self.gates)
            else "STOP_FAMILY"
        )
        if self.verdict != expected_verdict:
            raise ValueError("R3.1 verdict does not match the all-gates rule")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"ledger_evidence_hash"})
        )
        if self.ledger_evidence_hash != expected_hash:
            raise ValueError("R3.1 ledger hash does not match its evidence")
        return self


def build_r31_study_result_ledger(**values) -> R31StudyResultLedger:
    payload = {
        "schema_version": R31_RESULT_LEDGER_SCHEMA_VERSION,
        "study_id": "r3.1-cross-sectional-path-quality-spot-v1",
        "study_version": "1.0.0",
        "status": "COMPLETE",
        "planned_replay_count": 44,
        "primary_variant_id": "xsmom_path_quality_84d_14d_primary",
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
    payload["verdict"] = (
        "PERMIT_R4_PREREGISTRATION"
        if all(gate.passed for gate in payload["gates"])
        else "STOP_FAMILY"
    )
    payload["creates_eligible_strategy"] = False
    payload["opens_validation_partition"] = False
    return R31StudyResultLedger(
        **payload,
        ledger_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r31_study_result_ledger(ledger: R31StudyResultLedger) -> bool:
    return ledger.ledger_evidence_hash == universe_evidence_hash(
        ledger.model_dump(exclude={"ledger_evidence_hash"})
    )
