import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r31_execution_spec import (
    R31ExecutionSpecification,
    audit_r31_execution_specification,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r31_execution_spec import (
    authoritative_specification,
    builder_contract_hash,
    find_result_artifacts,
    load_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    protocol = evidence_root / "r31_path_quality_study_v1.json"
    parent_execution = (
        evidence_root / "r3_cross_sectional_momentum_execution_spec_v1.json"
    )


def specification() -> R31ExecutionSpecification:
    protocol, parent = load_inputs(Args())
    return authoritative_specification(
        registered_at=datetime(2026, 7, 23, 13, tzinfo=UTC),
        protocol=protocol,
        parent=parent,
    )


def rehash(payload: dict) -> dict:
    payload["specification_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "specification_evidence_hash"
        }
    )
    return payload


def test_r31_execution_freezes_exact_ols_arithmetic() -> None:
    frozen = specification()

    assert frozen.arithmetic.decimal_precision == 50
    assert frozen.signals.close_observation_count == 505
    assert frozen.signals.lookback_interval_count == 504
    assert frozen.signals.regression_x_mean == "252"
    assert frozen.signals.regression_sxx == "10732260"
    assert frozen.signals.score_formula == "SLOPE_TIMES_R_SQUARED"
    assert frozen.signals.recorded_signal_fields == [
        "INTERCEPT",
        "R_SQUARED",
        "SCORE",
        "SLOPE",
    ]
    assert audit_r31_execution_specification(frozen) is True
    assert R31ExecutionSpecification.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_r31_execution_inherits_every_non_signal_parent_section() -> None:
    frozen = specification()
    _, parent = load_inputs(Args())

    assert frozen.inputs == parent.inputs
    assert frozen.indicators == parent.indicators
    assert frozen.orders == parent.orders
    assert frozen.allocation == parent.allocation
    assert frozen.folds == parent.folds
    assert frozen.metrics == parent.metrics


def test_r31_execution_refuses_changed_sxx() -> None:
    payload = specification().model_dump()
    payload["signals"]["regression_sxx"] = "1"

    with pytest.raises(ValidationError):
        R31ExecutionSpecification.model_validate(rehash(payload))


def test_r31_execution_refuses_outcome_inspection() -> None:
    payload = specification().model_dump()
    payload["outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="predate every outcome"):
        R31ExecutionSpecification.model_validate(rehash(payload))


def test_r31_execution_builder_is_bound_to_the_authorized_result_path() -> None:
    assert len(builder_contract_hash()) == 64
    assert find_result_artifacts(Path("data/evidence")) == [
        "r31_path_quality_result_v1.json"
    ]


def test_stored_r31_execution_matches_authoritative_rebuild() -> None:
    stored = R31ExecutionSpecification.model_validate_json(
        Path("data/evidence/r31_path_quality_execution_spec_v1.json").read_text(
            encoding="utf-8"
        )
    )
    protocol, parent = load_inputs(Args())
    rebuilt = authoritative_specification(
        registered_at=stored.registered_at,
        protocol=protocol,
        parent=parent,
    )

    assert stored == rebuilt
    assert stored.specification_evidence_hash == (
        "76a0403f61f7d684761a05765c9d48d3310e56c8433779abb164d14e209773f1"
    )


def test_r31_execution_freeze_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_r31_execution_spec.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
