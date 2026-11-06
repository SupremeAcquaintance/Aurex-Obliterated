import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r4_run_package import (
    R4_SOURCE_FILES,
    R4RunPackage,
    audit_r4_run_package,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r4_run_package import (
    authoritative_run_package,
    load_package_inputs,
    source_file_hashes,
    verify_regression_receipt,
)


class Args:
    evidence_root = Path("data/evidence")
    universe = evidence_root / "market_universe_manifest_v1.json"
    development_bundle = (
        evidence_root / "development_4h_dataset_bundle_v1.json"
    )
    validation_bundle = evidence_root / "validation_2025_4h_bundle_v1.json"
    protocol = evidence_root / "r4_path_quality_candidate_v1.json"
    execution = evidence_root / "r4_path_quality_execution_spec_v1.json"
    r31_regression_result = (
        evidence_root
        / "r31_path_quality_results_v1"
        / "overall--xsmom_path_quality_84d_14d_primary--cost-1.json"
    )


@lru_cache(maxsize=1)
def package() -> R4RunPackage:
    inputs = load_package_inputs(Args())
    regression = verify_regression_receipt(Args.r31_regression_result)
    return authoritative_run_package(
        frozen_at=datetime(2026, 7, 23, 15, tzinfo=UTC),
        universe=inputs[0],
        development_bundle=inputs[1],
        protocol=inputs[2],
        validation_bundle=inputs[3],
        specification=inputs[4],
        market_data_evidence_hash=inputs[5].market_data_evidence_hash,
        regression_result=regression,
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


def test_r4_package_freezes_exact_42_replay_matrix() -> None:
    frozen = package()
    categories = [plan.category for plan in frozen.planned_replays]

    assert frozen.expected_replay_count == 42
    assert categories.count("OVERALL") == 3
    assert categories.count("QUARTERLY_FOLD") == 4
    assert categories.count("LEAVE_ONE_MARKET_OUT") == 35
    assert {
        plan.cost_multiplier
        for plan in frozen.planned_replays
        if plan.category == "OVERALL"
    } == {1, 1.5, 2}
    assert frozen.known_data_regression_status == "PASS"
    assert frozen.known_data_regression_trade_count == 230
    assert frozen.preexisting_result_artifacts == []
    assert frozen.outcome_fields_inspected == []
    assert audit_r4_run_package(frozen) is True
    assert R4RunPackage.model_validate_json(frozen.model_dump_json()) == frozen


def test_r4_package_refuses_preexisting_outcomes() -> None:
    payload = package().model_dump()
    payload["outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="predate every validation outcome"):
        R4RunPackage.model_validate(rehash(payload))


def test_r4_package_refuses_duplicate_fold_with_recomputed_hash() -> None:
    payload = package().model_dump()
    folds = [
        plan
        for plan in payload["planned_replays"]
        if plan["category"] == "QUARTERLY_FOLD"
    ]
    folds[1]["fold_id"] = folds[0]["fold_id"]

    with pytest.raises(ValidationError, match="all four quarterly folds"):
        R4RunPackage.model_validate(rehash(payload))


def test_r4_package_hashes_every_outcome_source_file() -> None:
    hashes = source_file_hashes(Path.cwd())

    assert tuple(hashes) == R4_SOURCE_FILES
    assert all(len(evidence_hash) == 64 for evidence_hash in hashes.values())


def test_r4_package_scripts_support_direct_invocation() -> None:
    for script in [
        "scripts/freeze_r4_run_package.py",
        "scripts/run_r4_validation.py",
    ]:
        completed = subprocess.run(
            [sys.executable, script, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

