import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_u1_theory_screen import (
    U1MechanismTheoryScreen,
    audit_u1_mechanism_theory_screen,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_u1_mechanism_theory_screen import (
    authoritative_screen,
    load_charter,
)


@lru_cache(maxsize=1)
def screen() -> U1MechanismTheoryScreen:
    charter = load_charter(
        Path("data/evidence/u1_mechanism_discovery_charter_v1.json")
    )
    return authoritative_screen(
        frozen_at=datetime(2026, 7, 27, 15, tzinfo=UTC),
        charter=charter,
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


def test_u1_theory_screen_selects_one_without_reading_returns() -> None:
    frozen = screen()

    assert len(frozen.proposals) == 3
    assert frozen.selected_proposal_id == "P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
    assert sum(
        proposal.disposition == "SELECT_FOR_PRIMARY_PROTOCOL_DESIGN"
        for proposal in frozen.proposals
    ) == 1
    assert frozen.return_tested_mechanisms == 0
    assert frozen.strategy_outcome_fields_inspected == []
    assert frozen.return_metrics_calculated == []
    assert frozen.creates_candidate is False
    assert frozen.opens_validation is False
    assert frozen.opens_holdout_or_forward is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert audit_u1_mechanism_theory_screen(frozen) is True


def test_u1_theory_screen_refuses_outcome_metrics() -> None:
    payload = screen().model_dump()
    payload["return_metrics_calculated"] = ["net_pl"]

    with pytest.raises(ValidationError, match="cannot contain strategy outcomes"):
        U1MechanismTheoryScreen.model_validate(rehash(payload))


def test_u1_theory_screen_refuses_selecting_data_blocked_jump_proposal() -> None:
    payload = screen().model_dump()
    payload["proposals"][0]["disposition"] = "DEFER_UNTIL_DATA_FOUNDATION_EXISTS"
    payload["proposals"][0]["blocking_reasons"] = ["SYNTHETIC"]
    payload["proposals"][1]["disposition"] = "SELECT_FOR_PRIMARY_PROTOCOL_DESIGN"
    payload["proposals"][1]["blocking_reasons"] = []

    with pytest.raises(ValidationError, match="currently executable"):
        U1MechanismTheoryScreen.model_validate(rehash(payload))


def test_u1_theory_screen_refuses_a_second_selected_proposal() -> None:
    payload = screen().model_dump()
    payload["proposals"][2]["disposition"] = "SELECT_FOR_PRIMARY_PROTOCOL_DESIGN"
    payload["proposals"][2]["blocking_reasons"] = []

    with pytest.raises(ValidationError, match="currently executable"):
        U1MechanismTheoryScreen.model_validate(rehash(payload))


def test_u1_theory_screen_refuses_removed_selection_rule() -> None:
    payload = screen().model_dump()
    payload["selection_rules"].pop()

    with pytest.raises(ValidationError, match="selection rules are fixed"):
        U1MechanismTheoryScreen.model_validate(rehash(payload))


def test_u1_theory_screen_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_u1_mechanism_theory_screen.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
