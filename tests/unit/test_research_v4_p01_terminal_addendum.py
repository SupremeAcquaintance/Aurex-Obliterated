from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v4_p01_terminal_addendum import (
    V4P01TerminalAuditAddendum,
    audit_v4_p01_terminal_audit_addendum,
)
from scripts.freeze_v4_p01_terminal_addendum import (
    authoritative_addendum,
    load_evidence,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDITED_AT = datetime(2026, 7, 29, 11, 0, tzinfo=UTC)


def frozen_addendum() -> V4P01TerminalAuditAddendum:
    evidence = load_evidence()
    return authoritative_addendum(
        audited_at=AUDITED_AT,
        continuation=evidence[0],
        original=evidence[1],
        original_terminal=evidence[2],
        corrected_gate=evidence[3],
        terminal=evidence[4],
        payload_observations=evidence[5],
    )


def test_addendum_reconciles_query_and_wire_product_identity() -> None:
    addendum = frozen_addendum()
    identities = addendum.identity_observations_by_request

    binance = [
        values
        for request_id, values in identities.items()
        if "BINANCE" in request_id
    ]
    coinbase = [
        values
        for request_id, values in identities.items()
        if "COINBASE" in request_id
    ]
    assert binance == [["ETHBTC"], ["ETHBTC"], ["ETHBTC"]]
    assert coinbase == [["ETH-BTC"], ["ETH-BTC"], ["ETH-BTC"]]
    assert audit_v4_p01_terminal_audit_addendum(addendum)


def test_addendum_corrects_explanation_but_preserves_rejection() -> None:
    addendum = frozen_addendum()
    statuses = {
        item.gate_id: item.status
        for item in addendum.corrected_execution_gate_results
    }

    assert addendum.invariant_decision == (
        "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
    )
    assert statuses["COMMON_ETH_BTC_PRODUCT_IDENTITY"] == "PASS"
    assert statuses["RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES"] == "FAIL"
    assert statuses["SOURCE_REVISION_AND_BYTE_INTEGRITY"] == "FAIL"
    assert statuses["POINT_IN_TIME_FEES_AND_FEE_CURRENCY"] == "FAIL"
    assert statuses["POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE"] == "FAIL"
    assert len(addendum.defect_assessments) == 2
    assert all(
        item.corrected_decision_changes is False
        for item in addendum.defect_assessments
    )


def test_addendum_authorizes_no_network_outcome_or_trading_action() -> None:
    addendum = frozen_addendum()

    assert addendum.authorizes_network_requests is False
    assert addendum.authorizes_retries_or_new_samples is False
    assert addendum.inspects_market_numeric_values is False
    assert addendum.calculates_signals_trades_pnl_or_returns is False
    assert addendum.rewrites_prior_artifacts is False
    assert addendum.selects_primary is False
    assert addendum.creates_candidate is False
    assert addendum.creates_paper_eligibility is False
    assert addendum.creates_sandbox_eligibility is False
    assert addendum.creates_live_eligibility is False


def test_addendum_refuses_decision_or_gate_tampering() -> None:
    payload = frozen_addendum().model_dump()
    payload["invariant_decision"] = "SELECT_V4P01"
    payload["authorizes_network_requests"] = True
    payload["corrected_execution_gate_results"][11]["status"] = "PASS"
    payload["addendum_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4P01TerminalAuditAddendum.model_validate(payload)


def test_addendum_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v4_p01_terminal_addendum.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "terminal explanation correction" in completed.stdout
