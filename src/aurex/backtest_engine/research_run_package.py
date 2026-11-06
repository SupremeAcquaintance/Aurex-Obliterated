from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_engine import R3_RESEARCH_ENGINE_VERSION
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_RUN_PACKAGE_SCHEMA_VERSION = "aurex-r3-run-package-v1"


class R3PlannedReplay(BaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    category: Literal["OVERALL", "QUARTERLY_FOLD", "LEAVE_ONE_MARKET_OUT"]
    variant_id: str = Field(min_length=1, max_length=128)
    variant_role: Literal["PRIMARY", "FALSIFICATION"]
    cost_multiplier: Decimal = Field(gt=0)
    evaluation_start: datetime
    evaluation_end: datetime
    fold_id: str | None = Field(default=None, max_length=128)
    omitted_symbols: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("omitted_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})

    @model_validator(mode="after")
    def validate_plan(self) -> "R3PlannedReplay":
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("R3 planned replay end must follow its start")
        if self.category == "QUARTERLY_FOLD":
            if not self.fold_id or self.omitted_symbols:
                raise ValueError("R3 fold plans require a fold and no omitted market")
        elif self.fold_id is not None:
            raise ValueError("Only R3 fold plans may name a fold")
        if self.category == "LEAVE_ONE_MARKET_OUT":
            if self.variant_role != "PRIMARY" or len(self.omitted_symbols) != 1:
                raise ValueError("R3 LOMO plans require primary and one omitted market")
            if self.cost_multiplier != Decimal("1"):
                raise ValueError("R3 LOMO plans use base costs only")
        elif self.omitted_symbols:
            raise ValueError("Only R3 LOMO plans may omit markets")
        if self.category == "QUARTERLY_FOLD" and self.cost_multiplier != Decimal("1"):
            raise ValueError("R3 fold plans use base costs only")
        return self


class R3RunPackage(BaseModel):
    schema_version: Literal["aurex-r3-run-package-v1"] = R3_RUN_PACKAGE_SCHEMA_VERSION
    package_id: str = Field(min_length=1, max_length=128)
    package_version: str = Field(min_length=1, max_length=64)
    frozen_at: datetime
    status: Literal["FROZEN_PRE_OUTCOME"] = "FROZEN_PRE_OUTCOME"
    engine_version: Literal["r3-cross-sectional-momentum-engine-v1.0.0"] = (
        R3_RESEARCH_ENGINE_VERSION
    )
    python_version: str = Field(min_length=1, max_length=64)
    pydantic_version: str = Field(min_length=1, max_length=64)
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    market_data_evidence_hash: str
    protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    source_file_sha256: dict[str, str] = Field(min_length=1)
    planned_replays: list[R3PlannedReplay] = Field(min_length=1)
    expected_replay_count: int = Field(gt=0)
    result_ledger_relative_path: str = Field(min_length=1, max_length=500)
    replay_artifact_directory_relative_path: str = Field(min_length=1, max_length=500)
    preexisting_result_artifacts: list[str] = Field(default_factory=list)
    outcome_fields_inspected: list[str] = Field(default_factory=list)
    builder_contract_hash: str
    package_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "market_data_evidence_hash",
        "protocol_evidence_hash",
        "execution_specification_evidence_hash",
        "builder_contract_hash",
        "package_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("source_file_sha256")
    @classmethod
    def normalize_source_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            path.strip().replace("\\", "/"): normalize_sha256(evidence_hash)
            for path, evidence_hash in sorted(value.items())
            if path.strip()
        }

    @field_validator("preexisting_result_artifacts", "outcome_fields_inspected")
    @classmethod
    def normalize_empty_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_package(self) -> "R3RunPackage":
        if self.preexisting_result_artifacts or self.outcome_fields_inspected:
            raise ValueError("R3 run package must be frozen before every outcome")
        run_ids = [plan.run_id for plan in self.planned_replays]
        if run_ids != sorted(run_ids) or len(run_ids) != len(set(run_ids)):
            raise ValueError("R3 planned replay IDs must be uniquely sorted")
        if self.expected_replay_count != len(self.planned_replays):
            raise ValueError("R3 expected replay count does not match its plan")
        category_counts = {
            category: sum(plan.category == category for plan in self.planned_replays)
            for category in ("OVERALL", "QUARTERLY_FOLD", "LEAVE_ONE_MARKET_OUT")
        }
        if category_counts != {
            "OVERALL": 9,
            "QUARTERLY_FOLD": 18,
            "LEAVE_ONE_MARKET_OUT": 35,
        }:
            raise ValueError("R3 run package must preserve the exact 62-replay matrix")
        variant_ids = {plan.variant_id for plan in self.planned_replays}
        if len(variant_ids) != 3:
            raise ValueError("R3 run package must preserve exactly three variants")
        for variant_id in variant_ids:
            overall_costs = {
                plan.cost_multiplier
                for plan in self.planned_replays
                if plan.category == "OVERALL" and plan.variant_id == variant_id
            }
            fold_ids = {
                plan.fold_id
                for plan in self.planned_replays
                if plan.category == "QUARTERLY_FOLD"
                and plan.variant_id == variant_id
            }
            if overall_costs != {Decimal("1"), Decimal("1.5"), Decimal("2")}:
                raise ValueError("R3 variants require all three cost levels")
            if len(fold_ids) != 6:
                raise ValueError("R3 variants require all six quarterly folds")
        lomo_symbols = [
            plan.omitted_symbols[0]
            for plan in self.planned_replays
            if plan.category == "LEAVE_ONE_MARKET_OUT"
        ]
        if len(set(lomo_symbols)) != 35:
            raise ValueError("R3 LOMO plan must omit every market exactly once")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"package_evidence_hash"})
        )
        if self.package_evidence_hash != expected_hash:
            raise ValueError("R3 run-package hash does not match its evidence")
        return self


def build_r3_run_package(**values) -> R3RunPackage:
    payload = {
        "schema_version": R3_RUN_PACKAGE_SCHEMA_VERSION,
        "engine_version": R3_RESEARCH_ENGINE_VERSION,
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    payload["source_file_sha256"] = dict(sorted(payload["source_file_sha256"].items()))
    payload["planned_replays"] = sorted(
        payload["planned_replays"], key=lambda plan: plan.run_id
    )
    payload["expected_replay_count"] = len(payload["planned_replays"])
    payload["preexisting_result_artifacts"] = sorted(
        set(payload["preexisting_result_artifacts"])
    )
    payload["outcome_fields_inspected"] = sorted(
        set(payload["outcome_fields_inspected"])
    )
    return R3RunPackage(
        **payload,
        package_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r3_run_package(package: R3RunPackage) -> bool:
    return package.package_evidence_hash == universe_evidence_hash(
        package.model_dump(exclude={"package_evidence_hash"})
    )
