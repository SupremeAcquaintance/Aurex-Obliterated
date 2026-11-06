import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_u1_run_package import (
    U1_SOURCE_FILES,
    U1RunPackage,
    audit_u1_run_package,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_u1_run_package import (
    authoritative_u1_run_package,
    load_package_inputs,
    source_file_hashes,
)


class Args:
    evidence_root = Path("data/evidence")
    charter = evidence_root / "u1_mechanism_discovery_charter_v1.json"
    screen = evidence_root / "u1_mechanism_theory_screen_v1.json"
    contamination = evidence_root / "strategy_contamination_ledger_v1.json"
    universe = evidence_root / "market_universe_manifest_v1.json"
    development = evidence_root / "development_4h_dataset_bundle_v1.json"
    protocol = evidence_root / "u1_primary_mechanism_protocol_v1.json"
    execution = evidence_root / "u1_primary_execution_spec_v1.json"


@lru_cache(maxsize=1)
def package() -> U1RunPackage:
    inputs = load_package_inputs(Args())
    return authoritative_u1_run_package(
        frozen_at=datetime(2026, 7, 27, 14, tzinfo=UTC),
        charter=inputs[0],
        screen=inputs[1],
        contamination=inputs[2],
        universe=inputs[3],
        development=inputs[4],
        protocol=inputs[5],
        specification=inputs[6],
        market_data=inputs[7],
    )


def rehash(payload: dict) -> dict:
    payload["package_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "package_evidence_hash"
        }
    )
    return payload


def test_u1_package_freezes_exact_47_replay_matrix() -> None:
    frozen = package()
    categories = [plan.category for plan in frozen.planned_replays]

    assert frozen.expected_replay_count == 47
    assert categories.count("OVERALL") == 3
    assert categories.count("BENCHMARK") == 1
    assert categories.count("TEMPORAL_FOLD") == 8
    assert categories.count("LEAVE_ONE_MARKET_OUT") == 35
    assert {
        plan.cost_multiplier
        for plan in frozen.planned_replays
        if plan.category == "OVERALL"
    } == {1, 1.5, 2}
    assert frozen.validation_data_loaded is False
    assert frozen.holdout_data_loaded is False
    assert frozen.forward_data_loaded is False
    assert frozen.preexisting_result_artifacts == []
    assert frozen.outcome_fields_inspected == []
    assert audit_u1_run_package(frozen) is True
    assert U1RunPackage.model_validate_json(frozen.model_dump_json()) == frozen


def test_u1_package_refuses_preexisting_outcomes() -> None:
    payload = package().model_dump()
    payload["outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="predate every development outcome"):
        U1RunPackage.model_validate(rehash(payload))


def test_u1_package_refuses_benchmark_cost_mutation() -> None:
    payload = package().model_dump()
    benchmark = next(
        plan
        for plan in payload["planned_replays"]
        if plan["category"] == "BENCHMARK"
    )
    benchmark["cost_multiplier"] = "1.5"

    with pytest.raises(ValidationError, match="benchmark plan is fixed"):
        U1RunPackage.model_validate(rehash(payload))


def test_u1_package_refuses_duplicate_fold() -> None:
    payload = package().model_dump()
    folds = [
        plan
        for plan in payload["planned_replays"]
        if plan["category"] == "TEMPORAL_FOLD"
    ]
    folds[1]["fold_id"] = folds[0]["fold_id"]

    with pytest.raises(ValidationError, match="all eight temporal folds"):
        U1RunPackage.model_validate(rehash(payload))


def test_u1_package_hashes_every_outcome_source_file() -> None:
    hashes = source_file_hashes(Path.cwd())

    assert tuple(hashes) == U1_SOURCE_FILES
    assert all(len(evidence_hash) == 64 for evidence_hash in hashes.values())


def test_u1_package_scripts_support_direct_invocation() -> None:
    for script in [
        "scripts/freeze_u1_run_package.py",
        "scripts/run_u1_primary_mechanism.py",
    ]:
        completed = subprocess.run(
            [sys.executable, script, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
