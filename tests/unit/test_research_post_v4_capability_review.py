from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_post_v4_capability_review import (
    POST_V4_ALLOWED_NEXT_TRACKS,
    POST_V4_CAPABILITY_IDS,
    POST_V4_DECISION,
    POST_V4_REQUIRED_OPERATOR_DECISION_IDS,
    PostV4CapabilityGapReview,
    audit_post_v4_capability_gap_review,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "post_v4_capability_gap_review_v1.json"
)


def frozen_review() -> PostV4CapabilityGapReview:
    return PostV4CapabilityGapReview.model_validate_json(
        REVIEW_PATH.read_text(encoding="utf-8")
    )


def test_post_v4_review_binds_complete_capability_set() -> None:
    review = frozen_review()

    assert [
        item.capability_id for item in review.capability_assessments
    ] == POST_V4_CAPABILITY_IDS
    statuses = {
        item.capability_id: item.status
        for item in review.capability_assessments
    }
    assert statuses["EVIDENCE_GRADE_BAR_REPLAY"] == "PROVEN"
    assert statuses["PROVEN_POSITIVE_NET_STRATEGY_EDGE"] == "ABSENT"
    assert statuses["EXECUTION_GRADE_HISTORICAL_TICK_OR_L2"] == "ABSENT"
    assert statuses["DETERMINISTIC_PRODUCTION_EXCHANGE_ADAPTER"] == "ABSENT"
    assert statuses["OPERATOR_CAPITAL_AND_LOSS_BUDGET"] == (
        "OPERATOR_INPUT_REQUIRED"
    )
    assert audit_post_v4_capability_gap_review(review)


def test_post_v4_review_requires_six_operator_decisions() -> None:
    review = frozen_review()

    assert [
        item.decision_id for item in review.required_operator_decisions
    ] == POST_V4_REQUIRED_OPERATOR_DECISION_IDS
    assert all(
        item.status == "REQUIRED_UNRESOLVED"
        for item in review.required_operator_decisions
    )


def test_post_v4_review_allows_only_non_alpha_next_tracks() -> None:
    review = frozen_review()

    assert review.allowed_next_tracks == POST_V4_ALLOWED_NEXT_TRACKS
    assert review.decision == POST_V4_DECISION
    assert review.successor_discovery_authorized is False
    assert review.network_requests_authorized is False
    assert review.market_data_import_authorized is False
    assert review.parameter_definition_authorized is False
    assert review.return_testing_authorized is False
    assert review.creates_candidate is False
    assert review.creates_paper_eligibility is False
    assert review.creates_sandbox_eligibility is False
    assert review.creates_live_eligibility is False


def test_post_v4_review_contains_no_outcomes() -> None:
    review = frozen_review()

    assert review.market_numeric_values_inspected == []
    assert review.strategy_outcome_fields_inspected == []
    assert review.return_metrics_calculated == []


def test_post_v4_review_refuses_successor_authorization_tampering() -> None:
    payload = frozen_review().model_dump()
    payload["successor_discovery_authorized"] = True

    with pytest.raises(ValidationError):
        PostV4CapabilityGapReview.model_validate(payload)


def test_post_v4_review_script_checks_all_lineage() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_post_v4_capability_review.py",
            "--check",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "operator_decisions=6" in completed.stdout
    assert "returns=[]" in completed.stdout
