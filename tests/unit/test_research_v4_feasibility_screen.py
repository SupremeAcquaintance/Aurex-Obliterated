from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v4_feasibility_screen import (
    V4_FEASIBILITY_DECISION,
    V4_FEASIBILITY_NEXT_DECISION,
    V4_FEASIBILITY_PROPOSAL_IDS,
    V4MechanismFeasibilityScreen,
    audit_v4_mechanism_feasibility_screen,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREEN_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "v4_mechanism_feasibility_screen_v1.json"
)


def frozen_screen() -> V4MechanismFeasibilityScreen:
    return V4MechanismFeasibilityScreen.model_validate_json(
        SCREEN_PATH.read_text(encoding="utf-8")
    )


def test_v4_screen_closes_round_with_zero_selection() -> None:
    screen = frozen_screen()

    assert [item.proposal_id for item in screen.dispositions] == (
        V4_FEASIBILITY_PROPOSAL_IDS
    )
    assert [item.formal_status for item in screen.dispositions] == [
        "REJECTED_SOURCE_AND_EXECUTION_FEASIBILITY",
        "STOPPED_METADATA_TRANSPORT_BUDGET",
    ]
    assert all(
        item.qualified_for_primary_selection is False
        for item in screen.dispositions
    )
    assert screen.selected_primary_proposal_id is None
    assert screen.selected_primary_count == 0
    assert screen.decision == V4_FEASIBILITY_DECISION
    assert screen.next_decision == V4_FEASIBILITY_NEXT_DECISION
    assert screen.v4_closed is True
    assert screen.authorizes_v4_retry_continuation_or_amendment is False
    assert screen.authorizes_network_requests is False
    assert screen.authorizes_return_testing is False
    assert screen.creates_candidate is False
    assert screen.creates_live_eligibility is False
    assert screen.return_metrics_calculated == []
    assert audit_v4_mechanism_feasibility_screen(screen)


def test_v4p02_transport_manifest_is_exact() -> None:
    screen = frozen_screen()
    p02 = screen.dispositions[1]

    assert p02.transport_observation_manifest == {
        "accepted_response_body_bytes": 0,
        "attempts_used": 1,
        "dataset_head_attempts_used": 0,
        "declared_metadata_content_length_bytes": 203_310_405,
        "http_hops_used": 1,
        "metadata_body_budget_bytes": 8_388_608,
    }
    assert "NO_RETRY_OR_BUDGET_EXPANSION_PERMITTED" in p02.reason_codes
    assert "NO_DATASET_HEAD_ATTEMPT_CONSUMED" in p02.reason_codes


def test_v4_screen_contains_no_outcome_or_permission_leakage() -> None:
    screen = frozen_screen()

    assert screen.market_numeric_values_inspected == []
    assert screen.strategy_outcome_fields_inspected == []
    assert screen.return_metrics_calculated == []
    for disposition in screen.dispositions:
        assert disposition.parameter_sets_defined == []
        assert disposition.market_numeric_values_inspected == []
        assert disposition.strategy_outcomes_inspected == []
        assert disposition.return_metrics_calculated == []


def test_v4_screen_refuses_selection_tampering() -> None:
    payload = frozen_screen().model_dump()
    payload["selected_primary_proposal_id"] = (
        "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM"
    )
    payload["selected_primary_count"] = 1

    with pytest.raises(ValidationError):
        V4MechanismFeasibilityScreen.model_validate(payload)


def test_v4_screen_refuses_terminal_hash_tampering() -> None:
    payload = frozen_screen().model_dump()
    payload["dispositions"][1]["terminal_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4MechanismFeasibilityScreen.model_validate(payload)


def test_v4_screen_refuses_transport_fact_tampering() -> None:
    payload = frozen_screen().model_dump()
    payload["dispositions"][1]["transport_observation_manifest"][
        "accepted_response_body_bytes"
    ] = 1

    with pytest.raises(ValidationError):
        V4MechanismFeasibilityScreen.model_validate(payload)


def test_v4_screen_script_checks_all_frozen_lineage() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v4_feasibility_screen.py",
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
