import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_u1_primary_protocol import (
    U1PrimaryProtocol,
    audit_u1_primary_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_u1_primary_protocol import authoritative_protocol, load_inputs


class Args:
    evidence_root = Path("data/evidence")
    charter = evidence_root / "u1_mechanism_discovery_charter_v1.json"
    screen = evidence_root / "u1_mechanism_theory_screen_v1.json"
    contamination = evidence_root / "strategy_contamination_ledger_v1.json"
    universe = evidence_root / "market_universe_manifest_v1.json"
    development = evidence_root / "development_4h_dataset_bundle_v1.json"


@lru_cache(maxsize=1)
def protocol() -> U1PrimaryProtocol:
    inputs = load_inputs(Args())
    return authoritative_protocol(
        registered_at=datetime(2026, 7, 27, 16, tzinfo=UTC),
        charter=inputs[0],
        screen=inputs[1],
        contamination=inputs[2],
        universe=inputs[3],
        development=inputs[4],
    )


def rehash(payload: dict) -> dict:
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "protocol_evidence_hash"
        }
    )
    return payload


def test_u1_primary_protocol_is_one_fixed_unlevered_mechanism() -> None:
    frozen = protocol()

    assert len(frozen.decision_symbols) == 35
    assert len(frozen.folds) == 8
    assert frozen.signal.lookback_intervals == 168
    assert frozen.signal.target_annualized_variance_decimal == "0.36"
    assert frozen.portfolio.rebalance_bars == 168
    assert frozen.portfolio.no_leverage is True
    assert frozen.portfolio.no_shorting is True
    assert frozen.selection_control.selectable_parameter_sets == 1
    assert frozen.selection_control.rescue_variants_allowed is False
    assert frozen.gates.minimum_positive_temporal_folds == 6
    assert frozen.gates.minimum_primary_profit_factor == "1.15"
    assert frozen.permits_validation is False
    assert frozen.permits_holdout_or_forward is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert frozen.outcome_fields_inspected == []
    assert audit_u1_primary_protocol(frozen) is True


def test_u1_primary_protocol_refuses_changed_target_variance() -> None:
    payload = protocol().model_dump()
    payload["signal"]["target_annualized_variance_decimal"] = "0.25"

    with pytest.raises(ValidationError, match="Input should be '0.36'"):
        U1PrimaryProtocol.model_validate(rehash(payload))


def test_u1_primary_protocol_refuses_removed_benchmark_gate() -> None:
    payload = protocol().model_dump()
    payload["gates"]["primary_drawdown_not_above_benchmark"] = False

    with pytest.raises(ValidationError, match="Input should be True"):
        U1PrimaryProtocol.model_validate(rehash(payload))


def test_u1_primary_protocol_refuses_opening_validation() -> None:
    payload = protocol().model_dump()
    payload["permits_validation"] = True

    with pytest.raises(ValidationError, match="Input should be False"):
        U1PrimaryProtocol.model_validate(rehash(payload))


def test_u1_primary_protocol_refuses_a_rescue_variant() -> None:
    payload = protocol().model_dump()
    payload["selection_control"]["falsification_variants"] = 1

    with pytest.raises(ValidationError, match="Input should be 0"):
        U1PrimaryProtocol.model_validate(rehash(payload))


def test_u1_primary_protocol_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_u1_primary_protocol.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
