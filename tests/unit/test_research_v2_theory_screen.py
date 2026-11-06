import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_theory_screen import (
    V2MechanismTheoryScreen,
    audit_v2_mechanism_theory_screen,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_theory_screen import authoritative_screen, load_charter


class Args:
    foundation_protocol = Path(
        "data/evidence/v2_derivatives_foundation_protocol_v1.json"
    )
    foundation_result = Path(
        "data/evidence/v2_derivatives_foundation_result_v1.json"
    )
    charter = Path("data/evidence/v2_mechanism_discovery_charter_v1.json")


def screen() -> V2MechanismTheoryScreen:
    return authoritative_screen(
        frozen_at=datetime(2026, 7, 28, 9, tzinfo=UTC),
        charter=load_charter(Args()),
    )


def rehash(payload: dict) -> dict:
    payload["screen_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "screen_evidence_hash"
        }
    )
    return payload


def test_v2_theory_screen_selects_one_without_outcomes_or_authority() -> None:
    frozen = screen()

    assert len(frozen.proposals) == 3
    assert frozen.selected_proposal_id == (
        "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    )
    assert (
        sum(
            proposal.disposition
            == "SELECT_FOR_FULL_DATA_AND_PROTOCOL_DESIGN"
            for proposal in frozen.proposals
        )
        == 1
    )
    assert frozen.return_tested_mechanism_count == 0
    assert frozen.parameter_set_count == 0
    assert frozen.market_data_numeric_fields_inspected == []
    assert frozen.strategy_outcome_fields_inspected == []
    assert frozen.return_metrics_calculated == []
    assert frozen.authorizes_full_acquisition is False
    assert frozen.authorizes_return_testing is False
    assert frozen.creates_candidate is False
    assert frozen.opens_development is False
    assert frozen.opens_validation is False
    assert frozen.opens_holdout is False
    assert frozen.opens_forward is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert audit_v2_mechanism_theory_screen(frozen)


def test_v2_theory_screen_refuses_outcomes_and_parameters() -> None:
    payload = screen().model_dump()
    payload["return_metrics_calculated"] = ["net_pl"]
    with pytest.raises(ValidationError, match="cannot contain data outcomes"):
        V2MechanismTheoryScreen.model_validate(rehash(payload))

    payload = screen().model_dump()
    payload["proposals"][0]["parameter_sets_defined"] = ["lookback=1"]
    with pytest.raises(ValidationError, match="cannot contain data outcomes"):
        V2MechanismTheoryScreen.model_validate(rehash(payload))


def test_v2_theory_screen_refuses_second_selected_primary() -> None:
    payload = screen().model_dump()
    payload["proposals"][1]["disposition"] = (
        "SELECT_FOR_FULL_DATA_AND_PROTOCOL_DESIGN"
    )
    payload["proposals"][1]["nonselection_reasons"] = []

    with pytest.raises(ValidationError):
        V2MechanismTheoryScreen.model_validate(rehash(payload))


def test_v2_theory_screen_keeps_reverse_carry_borrow_blocked() -> None:
    payload = screen().model_dump()
    payload["proposals"][2]["feasibility"]["requires_spot_borrowing"] = False

    with pytest.raises(ValidationError, match="Reverse carry must remain"):
        V2MechanismTheoryScreen.model_validate(rehash(payload))


def test_v2_theory_screen_refuses_selection_rule_drift() -> None:
    payload = screen().model_dump()
    payload["selection_rules"].pop()

    with pytest.raises(ValidationError, match="selection rules changed"):
        V2MechanismTheoryScreen.model_validate(rehash(payload))


def test_v2_theory_screen_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_theory_screen.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
