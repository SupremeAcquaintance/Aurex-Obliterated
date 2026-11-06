from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_u1_engine import U1_RESEARCH_ENGINE_VERSION
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

U1_RUN_PACKAGE_SCHEMA_VERSION = (
    "aurex-u1-volatility-managed-broad-spot-beta-run-package-v1"
)
U1_SOURCE_FILES = (
    "scripts/freeze_u1_run_package.py",
    "scripts/run_u1_primary_mechanism.py",
    "src/aurex/backtest_engine/binance_vision.py",
    "src/aurex/backtest_engine/development_bundle.py",
    "src/aurex/backtest_engine/research_engine.py",
    "src/aurex/backtest_engine/research_study_runner.py",
    "src/aurex/backtest_engine/research_u1_engine.py",
    "src/aurex/backtest_engine/research_u1_execution_spec.py",
    "src/aurex/backtest_engine/research_u1_primary_protocol.py",
    "src/aurex/backtest_engine/research_u1_result.py",
    "src/aurex/backtest_engine/research_u1_run_package.py",
    "src/aurex/backtest_engine/research_u1_study_runner.py",
    "src/aurex/backtest_engine/universe.py",
)


class U1PlannedReplay(BaseModel):
    run_id: str = Field(min_length=1, max_length=240)
    category: Literal[
        "OVERALL",
        "BENCHMARK",
        "TEMPORAL_FOLD",
        "LEAVE_ONE_MARKET_OUT",
    ]
    variant_id: Literal["volatility_managed_broad_spot_beta_v1"] = (
        "volatility_managed_broad_spot_beta_v1"
    )
    variant_version: Literal["1.0.0"] = "1.0.0"
    variant_role: Literal["PRIMARY", "BENCHMARK"]
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
    def validate_plan(self) -> U1PlannedReplay:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("U1 planned replay end must follow its start")
        if self.cost_multiplier not in {
            Decimal("1"),
            Decimal("1.5"),
            Decimal("2"),
        }:
            raise ValueError("U1 planned cost is outside the frozen grid")
        if self.category == "OVERALL":
            if (
                self.variant_role != "PRIMARY"
                or self.fold_id is not None
                or self.omitted_symbols
            ):
                raise ValueError("U1 overall plans require an unmodified primary")
        elif self.category == "BENCHMARK":
            if (
                self.variant_role != "BENCHMARK"
                or self.cost_multiplier != Decimal("1")
                or self.fold_id is not None
                or self.omitted_symbols
            ):
                raise ValueError("U1 benchmark plan is fixed at base costs")
        elif self.category == "TEMPORAL_FOLD":
            if (
                self.variant_role != "PRIMARY"
                or self.cost_multiplier != Decimal("1")
                or not self.fold_id
                or self.omitted_symbols
            ):
                raise ValueError("U1 fold plans require one base-cost primary fold")
        elif (
            self.variant_role != "PRIMARY"
            or self.cost_multiplier != Decimal("1")
            or self.fold_id is not None
            or len(self.omitted_symbols) != 1
        ):
            raise ValueError("U1 LOMO plans require one base-cost primary omission")
        return self


class U1RunPackage(BaseModel):
    schema_version: Literal[
        "aurex-u1-volatility-managed-broad-spot-beta-run-package-v1"
    ] = U1_RUN_PACKAGE_SCHEMA_VERSION
    package_id: Literal["u1-primary-mechanism-run-package-v1"] = (
        "u1-primary-mechanism-run-package-v1"
    )
    package_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_DEVELOPMENT_OUTCOME"] = (
        "FROZEN_PRE_DEVELOPMENT_OUTCOME"
    )
    engine_version: Literal[
        "u1-volatility-managed-broad-spot-engine-v1.0.0"
    ] = U1_RESEARCH_ENGINE_VERSION
    python_version: str = Field(min_length=1, max_length=64)
    pydantic_version: str = Field(min_length=1, max_length=64)
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    discovery_charter_evidence_hash: str
    theory_screen_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    contamination_ledger_evidence_hash: str
    primary_protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    market_data_evidence_hash: str
    source_file_sha256: dict[str, str] = Field(min_length=1)
    planned_replays: list[U1PlannedReplay] = Field(min_length=47, max_length=47)
    expected_replay_count: Literal[47] = 47
    result_ledger_relative_path: Literal[
        "u1_primary_mechanism_result_v1.json"
    ] = "u1_primary_mechanism_result_v1.json"
    replay_artifact_directory_relative_path: Literal[
        "u1_primary_mechanism_results_v1"
    ] = "u1_primary_mechanism_results_v1"
    deterministic_replay_required: Literal[True] = True
    validation_data_loaded: Literal[False] = False
    holdout_data_loaded: Literal[False] = False
    forward_data_loaded: Literal[False] = False
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
        "discovery_charter_evidence_hash",
        "theory_screen_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "contamination_ledger_evidence_hash",
        "primary_protocol_evidence_hash",
        "execution_specification_evidence_hash",
        "market_data_evidence_hash",
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
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_package(self) -> U1RunPackage:
        if self.preexisting_result_artifacts or self.outcome_fields_inspected:
            raise ValueError("U1 run package must predate every development outcome")
        if tuple(self.source_file_sha256) != U1_SOURCE_FILES:
            raise ValueError("U1 run-package source files are fixed")
        run_ids = [plan.run_id for plan in self.planned_replays]
        if run_ids != sorted(run_ids) or len(run_ids) != len(set(run_ids)):
            raise ValueError("U1 replay IDs must be uniquely sorted")
        category_counts = {
            category: sum(plan.category == category for plan in self.planned_replays)
            for category in (
                "OVERALL",
                "BENCHMARK",
                "TEMPORAL_FOLD",
                "LEAVE_ONE_MARKET_OUT",
            )
        }
        if category_counts != {
            "OVERALL": 3,
            "BENCHMARK": 1,
            "TEMPORAL_FOLD": 8,
            "LEAVE_ONE_MARKET_OUT": 35,
        }:
            raise ValueError("U1 must preserve the exact 47-replay matrix")
        overall_costs = {
            plan.cost_multiplier
            for plan in self.planned_replays
            if plan.category == "OVERALL"
        }
        if overall_costs != {Decimal("1"), Decimal("1.5"), Decimal("2")}:
            raise ValueError("U1 overall runs require all three cost levels")
        fold_ids = {
            plan.fold_id
            for plan in self.planned_replays
            if plan.category == "TEMPORAL_FOLD"
        }
        if len(fold_ids) != 8:
            raise ValueError("U1 requires all eight temporal folds")
        lomo_symbols = [
            plan.omitted_symbols[0]
            for plan in self.planned_replays
            if plan.category == "LEAVE_ONE_MARKET_OUT"
        ]
        if len(set(lomo_symbols)) != 35:
            raise ValueError("U1 must omit every decision market exactly once")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"package_evidence_hash"})
        )
        if self.package_evidence_hash != expected_hash:
            raise ValueError("U1 run-package hash does not match its evidence")
        return self


def build_u1_run_package(**values) -> U1RunPackage:
    payload = {
        "schema_version": U1_RUN_PACKAGE_SCHEMA_VERSION,
        "package_id": "u1-primary-mechanism-run-package-v1",
        "package_version": "1.0.0",
        "status": "FROZEN_PRE_DEVELOPMENT_OUTCOME",
        "engine_version": U1_RESEARCH_ENGINE_VERSION,
        "decimal_precision": 50,
        "decimal_rounding": "ROUND_HALF_EVEN",
        "expected_replay_count": 47,
        "result_ledger_relative_path": "u1_primary_mechanism_result_v1.json",
        "replay_artifact_directory_relative_path": (
            "u1_primary_mechanism_results_v1"
        ),
        "deterministic_replay_required": True,
        "validation_data_loaded": False,
        "holdout_data_loaded": False,
        "forward_data_loaded": False,
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    payload["source_file_sha256"] = dict(
        sorted(payload["source_file_sha256"].items())
    )
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
    return U1RunPackage(
        **payload,
        package_evidence_hash=universe_evidence_hash(payload),
    )


def audit_u1_run_package(package: U1RunPackage) -> bool:
    return package.package_evidence_hash == universe_evidence_hash(
        package.model_dump(exclude={"package_evidence_hash"})
    )
