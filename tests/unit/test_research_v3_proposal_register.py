import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposalRegister,
    audit_v3_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v3_proposal_register import (
    authoritative_register,
    load_charter,
)

CHARTER_PATH = Path(
    "data/evidence/v3_mechanism_discovery_charter_v1.json"
)


def register() -> V3MechanismProposalRegister:
    return authoritative_register(
        frozen_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        charter=load_charter(CHARTER_PATH),
    )


def rehash(payload: dict) -> dict:
    payload["register_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "register_evidence_hash"
        }
    )
    return payload


def test_v3_register_freezes_three_proposals_without_selection_or_outcomes() -> None:
    frozen = register()

    assert len(frozen.proposals) == 3
    assert frozen.proposal_budget_consumed == 3
    assert frozen.selected_primary_count == 0
    assert frozen.parameter_set_count == 0
    assert frozen.authorizes_timestamp_coverage_audit is True
    assert frozen.authorizes_market_numeric_value_inspection is False
    assert frozen.authorizes_return_testing is False
    assert frozen.selects_primary is False
    assert frozen.creates_candidate is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert audit_v3_mechanism_proposal_register(frozen)


def test_v3_proposal_coverage_contracts_are_frozen_before_feasibility() -> None:
    by_id = {proposal.proposal_id: proposal for proposal in register().proposals}
    cointegration = by_id[
        "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE"
    ]
    clock_phase = by_id["V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY"]
    maker = by_id["V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION"]

    assert cointegration.coverage_contract.minimum_qualified_symbols == 20
    assert cointegration.coverage_contract.maximum_single_gap_minutes == 1440
    assert clock_phase.coverage_contract.minimum_qualified_symbols == 10
    assert "usd_m_monthly_aggregate_trades" in (
        clock_phase.coverage_contract.supplemental_historical_sources
    )
    assert maker.coverage_contract.maximum_single_gap_minutes == 0
    assert maker.preliminary_execution_fit == (
        "BLOCKED_PENDING_L2_QUEUE_FILL_AND_LATENCY_HISTORY"
    )


def test_v3_proposal_sources_use_no_aurex_values_or_returns() -> None:
    frozen = register()

    for proposal in frozen.proposals:
        assert len(proposal.primary_sources) >= 3
        assert proposal.parameter_sets_defined == []
        assert proposal.market_numeric_fields_inspected == []
        assert proposal.strategy_outcome_fields_inspected == []
        assert proposal.return_metrics_calculated == []
        for source in proposal.primary_sources:
            assert source.url.startswith("https://")
            assert source.aurex_market_values_used == []
            assert source.aurex_return_metrics_used == []


def test_v3_register_refuses_selection_or_coverage_rescue() -> None:
    payload = register().model_dump()
    payload["selected_primary_count"] = 1
    with pytest.raises(ValidationError):
        V3MechanismProposalRegister.model_validate(rehash(payload))

    payload = register().model_dump()
    payload["proposals"][0]["coverage_contract"][
        "minimum_qualified_symbols"
    ] = 1
    with pytest.raises(ValidationError, match="hash does not match"):
        V3MechanismProposalRegister.model_validate(payload)


def test_v3_proposal_register_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v3_proposal_register.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
