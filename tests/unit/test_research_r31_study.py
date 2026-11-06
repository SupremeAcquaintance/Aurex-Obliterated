import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r31_study import (
    R31MechanismStudyProtocol,
    audit_r31_mechanism_study_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r31_mechanism_study import (
    authoritative_protocol,
    builder_contract_hash,
    find_r31_result_artifacts,
    load_parent_evidence,
)


class Args:
    evidence_root = Path("data/evidence")
    universe = evidence_root / "market_universe_manifest_v1.json"
    bundle = evidence_root / "development_4h_dataset_bundle_v1.json"
    r3_protocol = evidence_root / "r3_cross_sectional_momentum_study_v1.json"
    r3_execution = evidence_root / "r3_cross_sectional_momentum_execution_spec_v1.json"
    r3_result = evidence_root / "r3_cross_sectional_momentum_result_v1.json"
    failure_protocol = evidence_root / "r3_failure_analysis_protocol_v1.json"
    failure_package = evidence_root / "r3_failure_analysis_package_v1.json"
    failure_result = evidence_root / "r3_failure_analysis_result_v1.json"


def protocol() -> R31MechanismStudyProtocol:
    inputs = load_parent_evidence(Args())
    return authoritative_protocol(
        registered_at=datetime(2026, 7, 23, 12, tzinfo=UTC),
        universe=inputs[0],
        bundle=inputs[1],
        r3_protocol=inputs[2],
        r3_execution=inputs[3],
        r3_result=inputs[4],
        failure_protocol=inputs[5],
        failure_package=inputs[6],
        failure_result=inputs[7],
    )


def rehash(payload: dict) -> dict:
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        {key: value for key, value in payload.items() if key != "protocol_evidence_hash"}
    )
    return payload


def test_r31_protocol_has_one_fixed_path_quality_primary() -> None:
    frozen = protocol()

    assert frozen.signal.signal_id == "xsmom_path_quality_84d_14d_primary"
    assert frozen.signal.score_formula == "OLS_SLOPE_TIMES_R_SQUARED"
    assert frozen.signal.lookback_intervals == 504
    assert frozen.signal.close_observations == 505
    assert frozen.signal.rebalance_bars == 84
    assert frozen.selection_control.selectable_primary_count == 1
    assert frozen.selection_control.selectable_parameter_sets == 1
    assert frozen.selection_control.falsification_variants == 0
    assert frozen.selection_control.development_pass_creates_eligible_strategy is False
    assert frozen.known_outcome_boundary.parent_r3_verdict == "NO_CANDIDATE"
    assert frozen.known_outcome_boundary.failure_analysis_decision == (
        "PROPOSE_BOUNDED_R3_1"
    )
    assert frozen.r31_outcome_fields_inspected == []
    assert frozen.preexisting_r31_result_artifacts == []
    assert audit_r31_mechanism_study_protocol(frozen) is True
    assert R31MechanismStudyProtocol.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_r31_protocol_keeps_all_unopened_partitions_sealed() -> None:
    frozen = protocol()

    assert frozen.forbidden_partitions == ["FORWARD", "HOLDOUT", "VALIDATION"]
    assert len(frozen.decision_symbols) == 35
    assert frozen.diagnostic_only_symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert len(frozen.folds) == 6
    assert frozen.evaluation_end.isoformat() == "2025-01-01T00:00:00+00:00"


def test_r31_protocol_refuses_a_second_selectable_parameter_set() -> None:
    payload = protocol().model_dump()
    payload["selection_control"]["selectable_parameter_sets"] = 2

    with pytest.raises(ValidationError):
        R31MechanismStudyProtocol.model_validate(rehash(payload))


def test_r31_protocol_refuses_outcome_inspection() -> None:
    payload = protocol().model_dump()
    payload["r31_outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="predate every R3.1 outcome"):
        R31MechanismStudyProtocol.model_validate(rehash(payload))


def test_r31_protocol_refuses_changed_score_formula() -> None:
    payload = protocol().model_dump()
    payload["signal"]["score_formula"] = "LOOKBACK_TOTAL_RETURN"

    with pytest.raises(ValidationError):
        R31MechanismStudyProtocol.model_validate(rehash(payload))


def test_r31_protocol_refuses_changed_gate() -> None:
    payload = protocol().model_dump()
    payload["gates"]["minimum_positive_quarterly_folds"] = 3

    with pytest.raises(ValidationError):
        R31MechanismStudyProtocol.model_validate(rehash(payload))


def test_r31_builder_is_bound_to_the_authorized_result_path() -> None:
    assert len(builder_contract_hash()) == 64
    assert find_r31_result_artifacts(Path("data/evidence")) == [
        "r31_path_quality_result_v1.json"
    ]


def test_stored_r31_protocol_matches_authoritative_rebuild() -> None:
    stored = R31MechanismStudyProtocol.model_validate_json(
        Path("data/evidence/r31_path_quality_study_v1.json").read_text(
            encoding="utf-8"
        )
    )
    inputs = load_parent_evidence(Args())
    rebuilt = authoritative_protocol(
        registered_at=stored.registered_at,
        universe=inputs[0],
        bundle=inputs[1],
        r3_protocol=inputs[2],
        r3_execution=inputs[3],
        r3_result=inputs[4],
        failure_protocol=inputs[5],
        failure_package=inputs[6],
        failure_result=inputs[7],
    )

    assert stored == rebuilt
    assert stored.protocol_evidence_hash == (
        "dba4e1282533d5a93825eb1b6bd8b8e854f4146218bd70d5633f9a489b7030b5"
    )


def test_r31_freeze_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_r31_mechanism_study.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
