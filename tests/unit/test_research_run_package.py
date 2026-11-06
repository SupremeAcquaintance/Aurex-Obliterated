import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_run_package import (
    R3RunPackage,
    audit_r3_run_package,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r3_execution_spec import load_verified_protocol
from scripts.freeze_r3_mechanism_study import load_verified_inputs
from scripts.freeze_r3_run_package import (
    authoritative_run_package,
    load_package_inputs,
    load_verified_execution_specification,
    source_file_hashes,
)


@lru_cache(maxsize=1)
def package():
    universe, bundle = load_verified_inputs(
        evidence_root=Path("data/evidence"),
        universe_path=Path("data/evidence/market_universe_manifest_v1.json"),
        bundle_path=Path("data/evidence/development_4h_dataset_bundle_v1.json"),
    )
    protocol = load_verified_protocol(
        Path("data/evidence/r3_cross_sectional_momentum_study_v1.json"),
        universe=universe,
        bundle=bundle,
    )
    specification = load_verified_execution_specification(
        Path("data/evidence/r3_cross_sectional_momentum_execution_spec_v1.json"),
        protocol_hash=protocol.protocol_evidence_hash,
        universe_hash=universe.manifest_evidence_hash,
        bundle_hash=bundle.bundle_evidence_hash,
    )
    return authoritative_run_package(
        frozen_at=datetime(2026, 7, 22, 20, tzinfo=UTC),
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        execution_specification=specification,
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


def test_run_package_freezes_complete_62_replay_matrix() -> None:
    frozen = package()
    categories = [plan.category for plan in frozen.planned_replays]

    assert frozen.expected_replay_count == 62
    assert categories.count("OVERALL") == 9
    assert categories.count("QUARTERLY_FOLD") == 18
    assert categories.count("LEAVE_ONE_MARKET_OUT") == 35
    assert {
        plan.cost_multiplier
        for plan in frozen.planned_replays
        if plan.category == "OVERALL"
    } == {1, 1.5, 2}
    assert all(
        plan.variant_role == "PRIMARY" and len(plan.omitted_symbols) == 1
        for plan in frozen.planned_replays
        if plan.category == "LEAVE_ONE_MARKET_OUT"
    )
    assert frozen.preexisting_result_artifacts == []
    assert frozen.outcome_fields_inspected == []
    assert audit_r3_run_package(frozen) is True
    assert R3RunPackage.model_validate_json(frozen.model_dump_json()) == frozen


def test_run_package_refuses_preexisting_outcomes() -> None:
    payload = package().model_dump()
    payload["outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="before every outcome"):
        R3RunPackage.model_validate(rehash(payload))


def test_run_package_refuses_missing_replay_even_with_recomputed_hash() -> None:
    payload = package().model_dump()
    payload["planned_replays"].pop()

    with pytest.raises(ValidationError, match="expected replay count"):
        R3RunPackage.model_validate(rehash(payload))


def test_run_package_hashes_every_outcome_source_file() -> None:
    hashes = source_file_hashes(Path.cwd())

    assert sorted(hashes) == [
        "scripts/run_r3_mechanism_study.py",
        "src/aurex/backtest_engine/research_engine.py",
        "src/aurex/backtest_engine/research_result.py",
        "src/aurex/backtest_engine/research_run_package.py",
        "src/aurex/backtest_engine/research_study_runner.py",
    ]
    assert all(len(evidence_hash) == 64 for evidence_hash in hashes.values())


def test_run_package_scripts_support_direct_invocation() -> None:
    for script in [
        "scripts/freeze_r3_run_package.py",
        "scripts/run_r3_mechanism_study.py",
    ]:
        completed = subprocess.run(
            [sys.executable, script, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_authoritative_frozen_run_package_matches_offline_rebuild(monkeypatch) -> None:
    from scripts import freeze_r3_run_package as builder

    class Args:
        evidence_root = Path("data/evidence")
        universe_manifest = evidence_root / "market_universe_manifest_v1.json"
        dataset_bundle = evidence_root / "development_4h_dataset_bundle_v1.json"
        protocol = evidence_root / "r3_cross_sectional_momentum_study_v1.json"
        execution_specification = (
            evidence_root / "r3_cross_sectional_momentum_execution_spec_v1.json"
        )

    stored = R3RunPackage.model_validate_json(
        Path(
            "data/evidence/r3_cross_sectional_momentum_run_package_v1.json"
        ).read_text(encoding="utf-8")
    )
    universe, bundle, protocol, specification, market_data = load_package_inputs(Args())
    # Reconstruct historical metadata; actual execution validates the current runtime separately.
    monkeypatch.setattr(builder.platform, "python_version", lambda: stored.python_version)
    monkeypatch.setattr(builder.pydantic, "__version__", stored.pydantic_version)
    rebuilt = authoritative_run_package(
        frozen_at=stored.frozen_at,
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        execution_specification=specification,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )

    assert stored == rebuilt
    assert stored.package_evidence_hash == (
        "2ca29f9328306c91f8281051731592da5e3d8b00db47573f5f4b08b9d9bb2756"
    )
    assert stored.market_data_evidence_hash == (
        "ec5e60c129d941b0f72ea39fde63a99df992efbca2c9348c7abc9d313c3c50c2"
    )


def test_frozen_r3_execution_rejects_wrong_python_runtime(monkeypatch) -> None:
    from scripts import run_r3_mechanism_study as runner

    monkeypatch.setattr(runner.platform, "python_version", lambda: "0.0.0")
    with pytest.raises(ValueError, match="frozen Python version"):
        runner.load_verified_run_package(
            Path("data/evidence/r3_cross_sectional_momentum_run_package_v1.json")
        )
