import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_u1_execution_spec import (
    U1ExecutionSpecification,
    audit_u1_execution_specification,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_u1_execution_spec import (
    authoritative_specification,
    load_protocol,
)


@lru_cache(maxsize=1)
def specification() -> U1ExecutionSpecification:
    protocol = load_protocol(
        Path("data/evidence/u1_primary_mechanism_protocol_v1.json")
    )
    return authoritative_specification(
        registered_at=datetime(2026, 7, 27, 17, tzinfo=UTC),
        protocol=protocol,
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


def test_u1_execution_specification_freezes_arithmetic_and_ordering() -> None:
    frozen = specification()

    assert frozen.arithmetic.decimal_precision == 50
    assert frozen.arithmetic.realized_variance_formula.endswith("TIMES_2190")
    assert frozen.signals.signal_bar_index == "ENTRY_INDEX_MINUS_ONE"
    assert frozen.orders.rebalance_event_order[0] == "APPLY_TERMINAL_MARKET_EVENTS"
    assert frozen.orders.rebalance_event_order[1] == "EXIT_EXISTING_AT_OPEN"
    assert frozen.allocation.capacity_includes_entry_fees is True
    assert frozen.availability.writeoff_raw_exit_price == "0"
    assert frozen.folds.fold_rebalance_anchor == "EACH_FOLD_EVALUATION_START"
    assert (
        frozen.metrics.benchmark_comparison_scope
        == "OVERALL_BASE_COST_PRIMARY_VERSUS_OVERALL_BASE_COST_BENCHMARK"
    )
    assert frozen.outcome_fields_inspected == []
    assert frozen.preexisting_engine_or_result_artifacts == []
    assert audit_u1_execution_specification(frozen) is True


def test_u1_execution_specification_refuses_same_bar_signal() -> None:
    payload = specification().model_dump()
    payload["signals"]["signal_bar_index"] = "ENTRY_INDEX"

    with pytest.raises(ValidationError, match="ENTRY_INDEX_MINUS_ONE"):
        U1ExecutionSpecification.model_validate(rehash(payload))


def test_u1_execution_specification_refuses_unreserved_fees() -> None:
    payload = specification().model_dump()
    payload["allocation"]["capacity_includes_entry_fees"] = False

    with pytest.raises(ValidationError, match="Input should be True"):
        U1ExecutionSpecification.model_validate(rehash(payload))


def test_u1_execution_specification_refuses_invented_termination_price() -> None:
    payload = specification().model_dump()
    payload["availability"]["writeoff_raw_exit_price"] = "1"

    with pytest.raises(ValidationError, match="Input should be '0'"):
        U1ExecutionSpecification.model_validate(rehash(payload))


def test_u1_execution_specification_refuses_changed_event_order() -> None:
    payload = specification().model_dump()
    payload["orders"]["rebalance_event_order"][0:2] = reversed(
        payload["orders"]["rebalance_event_order"][0:2]
    )

    with pytest.raises(ValidationError, match="event order is fixed"):
        U1ExecutionSpecification.model_validate(rehash(payload))


def test_u1_execution_specification_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_u1_execution_spec.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
