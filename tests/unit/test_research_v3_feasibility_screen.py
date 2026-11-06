from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v3_feasibility_screen import (
    V3_FEASIBILITY_DECISION,
    V3_FEASIBILITY_NEXT_DECISION,
    V3_FEASIBILITY_PROPOSAL_IDS,
    V3MechanismFeasibilityScreen,
    audit_v3_mechanism_feasibility_screen,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREEN_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "v3_mechanism_feasibility_screen_v1.json"
)


def frozen_screen() -> V3MechanismFeasibilityScreen:
    return V3MechanismFeasibilityScreen.model_validate_json(
        SCREEN_PATH.read_text(encoding="utf-8")
    )


def test_v3_screen_closes_round_with_zero_selection() -> None:
    screen = frozen_screen()

    assert [item.proposal_id for item in screen.dispositions] == (
        V3_FEASIBILITY_PROPOSAL_IDS
    )
    assert [item.formal_status for item in screen.dispositions] == [
        "REJECTED_EXECUTION_AND_METADATA_FEASIBILITY",
        "STOPPED_TRANSPORT_UNRESOLVED",
        "REJECTED_HISTORICAL_EVIDENCE_UNAVAILABLE",
    ]
    assert all(
        item.qualified_for_primary_selection is False
        for item in screen.dispositions
    )
    assert screen.selected_primary_proposal_id is None
    assert screen.selected_primary_count == 0
    assert screen.decision == V3_FEASIBILITY_DECISION
    assert screen.next_decision == V3_FEASIBILITY_NEXT_DECISION
    assert screen.v3_closed is True
    assert screen.authorizes_v3_retry_or_amendment is False
    assert screen.authorizes_return_testing is False
    assert screen.creates_candidate is False
    assert screen.creates_live_eligibility is False
    assert screen.return_metrics_calculated == []
    assert audit_v3_mechanism_feasibility_screen(screen)


def test_v3_screen_refuses_selection_tampering() -> None:
    screen = frozen_screen()
    payload = screen.model_dump()
    payload["selected_primary_proposal_id"] = (
        "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY"
    )
    payload["selected_primary_count"] = 1

    with pytest.raises(ValidationError):
        V3MechanismFeasibilityScreen.model_validate(payload)


def test_v3_screen_refuses_terminal_hash_tampering() -> None:
    screen = frozen_screen()
    payload = screen.model_dump()
    payload["dispositions"][1]["terminal_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V3MechanismFeasibilityScreen.model_validate(payload)


def test_v3_screen_script_checks_frozen_artifact() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v3_feasibility_screen.py",
            "--check",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "selected=0" in completed.stdout
    assert "returns=[]" in completed.stdout
