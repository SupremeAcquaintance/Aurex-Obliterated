import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r4_execution_spec import (
    R4ExecutionSpecification,
    audit_r4_execution_specification,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r4_execution_spec import (
    authoritative_specification,
    builder_contract_hash,
    find_result_artifacts,
    load_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    r4_protocol = evidence_root / "r4_path_quality_candidate_v1.json"
    r31_execution = evidence_root / "r31_path_quality_execution_spec_v1.json"
    validation_bundle = evidence_root / "validation_2025_4h_bundle_v1.json"


@lru_cache(maxsize=1)
def specification() -> R4ExecutionSpecification:
    protocol, parent, validation = load_inputs(Args())
    return authoritative_specification(
        registered_at=datetime(2026, 7, 23, 15, tzinfo=UTC),
        protocol=protocol,
        parent=parent,
        validation=validation,
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


def test_r4_execution_inherits_every_parent_strategy_semantic() -> None:
    frozen = specification()
    _, parent, _ = load_inputs(Args())

    assert frozen.arithmetic == parent.arithmetic
    assert frozen.signals == parent.signals
    assert frozen.indicators == parent.indicators
    assert frozen.orders == parent.orders
    assert frozen.allocation == parent.allocation
    assert frozen.folds.parent_fold_semantics == parent.folds
    assert frozen.metrics.parent_metrics == parent.metrics
    assert audit_r4_execution_specification(frozen) is True
    assert R4ExecutionSpecification.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_r4_execution_freezes_terminal_symbols_and_zero_writeoff() -> None:
    frozen = specification()

    assert [item.symbol for item in frozen.inputs.terminal_symbols] == [
        "FTMUSDT",
        "MKRUSDT",
    ]
    assert frozen.lifecycle.terminated_held_symbol == (
        "CLOSE_AT_ZERO_ON_FIRST_MISSING_BAR"
    )
    assert frozen.lifecycle.termination_raw_exit_price == "0"
    assert frozen.lifecycle.termination_event_order[0] == (
        "WRITE_OFF_TERMINATED_OPEN_POSITIONS"
    )
    assert frozen.lifecycle.terminated_symbol_reactivation is False


def test_r4_execution_refuses_a_less_conservative_delisting_fill() -> None:
    payload = specification().model_dump()
    payload["lifecycle"]["termination_raw_exit_price"] = "LAST_CLOSE"

    with pytest.raises(ValidationError):
        R4ExecutionSpecification.model_validate(rehash(payload))


def test_r4_execution_refuses_parent_signal_drift() -> None:
    payload = specification().model_dump()
    payload["signals"]["regression_sxx"] = "1"

    with pytest.raises(ValidationError):
        R4ExecutionSpecification.model_validate(rehash(payload))


def test_r4_execution_predates_results_and_builder_is_bound() -> None:
    assert specification().preexisting_result_artifacts == []
    assert specification().outcome_fields_inspected == []
    assert find_result_artifacts(Path("data/evidence")) == []
    assert len(builder_contract_hash()) == 64


def test_r4_execution_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_r4_execution_spec.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
