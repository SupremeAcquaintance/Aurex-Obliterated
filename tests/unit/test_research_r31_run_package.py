import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r31_execution_spec import (
    R31ExecutionSpecification,
)
from aurex.backtest_engine.research_r31_run_package import (
    R31_SOURCE_FILES,
    R31RunPackage,
    audit_r31_run_package,
)
from aurex.backtest_engine.research_r31_study import R31MechanismStudyProtocol
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r31_mechanism_study import load_verified_inputs
from scripts.freeze_r31_run_package import (
    authoritative_run_package,
    load_package_inputs,
    source_file_hashes,
)


@lru_cache(maxsize=1)
def package() -> R31RunPackage:
    evidence_root = Path("data/evidence")
    universe, bundle = load_verified_inputs(
        evidence_root=evidence_root,
        universe_path=evidence_root / "market_universe_manifest_v1.json",
        bundle_path=evidence_root / "development_4h_dataset_bundle_v1.json",
    )
    protocol = R31MechanismStudyProtocol.model_validate_json(
        (evidence_root / "r31_path_quality_study_v1.json").read_text(
            encoding="utf-8"
        )
    )
    specification = R31ExecutionSpecification.model_validate_json(
        (evidence_root / "r31_path_quality_execution_spec_v1.json").read_text(
            encoding="utf-8"
        )
    )
    return authoritative_run_package(
        frozen_at=datetime(2026, 7, 23, 12, tzinfo=UTC),
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        specification=specification,
        market_data_evidence_hash="e" * 64,
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


def test_r31_package_freezes_exact_44_replay_matrix() -> None:
    frozen = package()
    categories = [plan.category for plan in frozen.planned_replays]

    assert frozen.expected_replay_count == 44
    assert categories.count("OVERALL") == 3
    assert categories.count("QUARTERLY_FOLD") == 6
    assert categories.count("LEAVE_ONE_MARKET_OUT") == 35
    assert {
        plan.cost_multiplier
        for plan in frozen.planned_replays
        if plan.category == "OVERALL"
    } == {1, 1.5, 2}
    assert len(
        {
            plan.fold_id
            for plan in frozen.planned_replays
            if plan.category == "QUARTERLY_FOLD"
        }
    ) == 6
    assert len(
        {
            plan.omitted_symbols[0]
            for plan in frozen.planned_replays
            if plan.category == "LEAVE_ONE_MARKET_OUT"
        }
    ) == 35
    assert frozen.preexisting_result_artifacts == []
    assert frozen.outcome_fields_inspected == []
    assert audit_r31_run_package(frozen) is True
    assert R31RunPackage.model_validate_json(frozen.model_dump_json()) == frozen


def test_r31_package_refuses_preexisting_outcomes() -> None:
    payload = package().model_dump()
    payload["outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="predate every outcome"):
        R31RunPackage.model_validate(rehash(payload))


def test_r31_package_refuses_duplicate_fold_even_with_recomputed_hash() -> None:
    payload = package().model_dump()
    folds = [
        plan
        for plan in payload["planned_replays"]
        if plan["category"] == "QUARTERLY_FOLD"
    ]
    folds[1]["fold_id"] = folds[0]["fold_id"]

    with pytest.raises(ValidationError, match="all six quarterly folds"):
        R31RunPackage.model_validate(rehash(payload))


def test_r31_package_hashes_every_outcome_source_file() -> None:
    hashes = source_file_hashes(Path.cwd())

    assert tuple(hashes) == R31_SOURCE_FILES
    assert all(len(evidence_hash) == 64 for evidence_hash in hashes.values())


def test_r31_package_scripts_support_direct_invocation() -> None:
    for script in [
        "scripts/freeze_r31_run_package.py",
        "scripts/run_r31_mechanism_study.py",
    ]:
        completed = subprocess.run(
            [sys.executable, script, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_stored_r31_package_matches_authoritative_rebuild(monkeypatch) -> None:
    from scripts import freeze_r31_run_package as builder

    class Args:
        evidence_root = Path("data/evidence")
        universe = evidence_root / "market_universe_manifest_v1.json"
        bundle = evidence_root / "development_4h_dataset_bundle_v1.json"
        protocol = evidence_root / "r31_path_quality_study_v1.json"
        execution = evidence_root / "r31_path_quality_execution_spec_v1.json"

    stored = R31RunPackage.model_validate_json(
        Path("data/evidence/r31_path_quality_run_package_v1.json").read_text(
            encoding="utf-8"
        )
    )
    universe, bundle, protocol, specification, market_data = load_package_inputs(
        Args()
    )
    # Historical reconstruction uses recorded runtime metadata, without authorizing a replay.
    monkeypatch.setattr(builder.platform, "python_version", lambda: stored.python_version)
    monkeypatch.setattr(builder.pydantic, "__version__", stored.pydantic_version)
    rebuilt = authoritative_run_package(
        frozen_at=stored.frozen_at,
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        specification=specification,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )

    assert stored == rebuilt
    assert stored.package_evidence_hash == (
        "13c1e6cc657b055f3cf957fd6e841e9bdbe8ed59ce6eee89c6f7d9b39c78d722"
    )
    assert stored.market_data_evidence_hash == (
        "ec5e60c129d941b0f72ea39fde63a99df992efbca2c9348c7abc9d313c3c50c2"
    )
