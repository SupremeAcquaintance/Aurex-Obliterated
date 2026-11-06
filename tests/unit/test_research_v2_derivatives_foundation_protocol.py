import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2_FOUNDATION_SCENARIO_IDS,
    V2DerivativesFoundationProtocol,
    audit_v2_derivatives_foundation_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_derivatives_foundation_protocol import (
    authoritative_protocol,
    load_inputs,
)


class Args:
    acquisition_protocol = Path(
        "data/evidence/v2_derivatives_acquisition_protocol_v1.json"
    )
    pilot_result = Path(
        "data/evidence/v2_derivatives_pilot_acquisition_result_v1.json"
    )
    evidence_root = Path("data/evidence")


def protocol() -> V2DerivativesFoundationProtocol:
    acquisition, pilot = load_inputs(Args())
    return authoritative_protocol(
        frozen_at=datetime(2026, 7, 28, 3, tzinfo=UTC),
        acquisition=acquisition,
        pilot=pilot,
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


def test_v2_foundation_protocol_is_synthetic_and_exact() -> None:
    frozen = protocol()

    assert frozen.synthetic_only is True
    assert [item.scenario_id for item in frozen.scenarios] == (
        V2_FOUNDATION_SCENARIO_IDS
    )
    assert frozen.accounting.event_hash_chain_required is True
    assert frozen.paired_execution.partial_fills_supported is True
    assert frozen.risk.pretrade_margin_gate_required is True
    assert frozen.reconciliation.discrepancy_enables_kill_switch is True
    assert frozen.authorizes_real_market_data_import is False
    assert frozen.authorizes_strategy_return_calculation is False
    assert frozen.pass_creates_strategy_candidate is False
    assert audit_v2_derivatives_foundation_protocol(frozen)
    assert V2DerivativesFoundationProtocol.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_v2_foundation_protocol_fixes_signed_funding_formula() -> None:
    frozen = protocol()

    assert frozen.accounting.funding_cashflow_formula == (
        "NEGATIVE_SIGNED_PERP_QUANTITY_TIMES_MARK_PRICE_TIMES_FUNDING_RATE"
    )
    assert frozen.accounting.perp_unrealized_pl_formula == (
        "SIGNED_PERP_QUANTITY_TIMES_MARK_MINUS_AVERAGE_ENTRY"
    )
    assert frozen.accounting.equity_formula == (
        "CASH_PLUS_SPOT_QUANTITY_TIMES_SPOT_MARK_PLUS_PERP_UNREALIZED_PL"
    )


def test_v2_foundation_protocol_refuses_scenario_or_permission_changes() -> None:
    payload = protocol().model_dump()
    payload["scenarios"] = payload["scenarios"][:-1]
    with pytest.raises(ValidationError):
        V2DerivativesFoundationProtocol.model_validate(rehash(payload))

    payload = protocol().model_dump()
    payload["authorizes_strategy_return_calculation"] = True
    with pytest.raises(ValidationError):
        V2DerivativesFoundationProtocol.model_validate(rehash(payload))

    payload = protocol().model_dump()
    payload["paired_execution"]["hedge_tolerance_base_quantity"] = "0.01"
    with pytest.raises(ValidationError, match="hedge tolerance changed"):
        V2DerivativesFoundationProtocol.model_validate(rehash(payload))


def test_v2_foundation_protocol_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_derivatives_foundation_protocol.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
