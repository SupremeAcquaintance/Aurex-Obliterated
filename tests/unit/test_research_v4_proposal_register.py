from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v4_proposal_register import (
    V4MechanismProposalRegister,
    audit_v4_mechanism_proposal_register,
)
from scripts.freeze_v4_proposal_register import (
    authoritative_register,
    load_charter,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FROZEN_AT = datetime(2026, 7, 29, 6, 0, tzinfo=UTC)
CHARTER_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "v4_mechanism_discovery_charter_v1.json"
)


def frozen_register() -> V4MechanismProposalRegister:
    return authoritative_register(
        frozen_at=FROZEN_AT,
        charter=load_charter(CHARTER_PATH),
    )


def test_v4_register_uses_two_proposals_and_leaves_one_slot_unused() -> None:
    register = frozen_register()

    assert [proposal.proposal_id for proposal in register.proposals] == [
        "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE",
        "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM",
    ]
    assert register.maximum_proposal_budget == 3
    assert register.proposal_budget_consumed == 2
    assert register.proposal_budget_unused == 1
    assert register.selected_primary_count == 0
    assert register.parameter_set_count == 0
    assert register.decision == (
        "FREEZE_TWO_PROPOSALS_LEAVE_ONE_SLOT_UNUSED_FOR_NO_RETURN_FEASIBILITY"
    )
    assert audit_v4_mechanism_proposal_register(register)


def test_v4_register_preserves_no_network_and_no_outcome_boundary() -> None:
    register = frozen_register()

    assert register.authorizes_network_requests is False
    assert register.requires_separate_transport_contract_before_network is True
    assert register.authorizes_market_numeric_value_inspection is False
    assert register.authorizes_return_testing is False
    assert register.selects_primary is False
    assert register.creates_candidate is False
    assert register.opens_development_outcomes is False
    assert register.opens_validation is False
    assert register.opens_holdout is False
    assert register.opens_forward is False
    assert register.permits_pine_parity is False
    assert register.creates_paper_eligibility is False
    assert register.creates_sandbox_eligibility is False
    assert register.creates_live_eligibility is False
    assert register.strategy_outcome_fields_inspected == []
    assert register.return_metrics_calculated == []

    for proposal in register.proposals:
        assert proposal.parameter_sets_defined == []
        assert proposal.market_numeric_fields_inspected == []
        assert proposal.strategy_outcome_fields_inspected == []
        assert proposal.return_metrics_calculated == []
        assert proposal.source_feasibility_contract.market_numeric_values_permitted is False
        assert proposal.source_feasibility_contract.return_metrics_permitted is False


def test_v4_proposals_have_independent_research_and_execution_sources() -> None:
    register = frozen_register()

    for proposal in register.proposals:
        source_kinds = {source.source_kind for source in proposal.primary_sources}
        source_hosts = {
            source.url.split("/", maxsplit=3)[2]
            for source in proposal.primary_sources
        }
        assert "PEER_REVIEWED_ARTICLE" in source_kinds
        assert "OFFICIAL_EXCHANGE_DOCUMENTATION" in source_kinds or (
            "OFFICIAL_EXCHANGE_DATA_ARCHIVE" in source_kinds
        )
        assert len(source_hosts) >= 3
        assert all(source.explicit_limitations for source in proposal.primary_sources)
        assert all(
            source.aurex_market_values_used == []
            for source in proposal.primary_sources
        )
        assert all(
            source.aurex_return_metrics_used == []
            for source in proposal.primary_sources
        )


def test_v4_proposals_freeze_mechanism_specific_hard_stops() -> None:
    cross_venue, options = frozen_register().proposals

    assert "same-asset law-of-one-price" in (
        " ".join(cross_venue.independence_from_blocked_lineages).lower()
    )
    assert (
        "last_trades_for_simultaneous_bbo"
        in cross_venue.source_feasibility_contract.prohibited_substitutions
    )
    assert (
        "no_assumed_cross_venue_atomicity"
        in cross_venue.execution_feasibility_contract.multi_leg_failure_requirements
    )
    assert "negatively convex" in options.ex_ante_payoff_direction.lower()
    assert (
        "mark_midpoint_or_model_value_for_executable_option_fill"
        in options.source_feasibility_contract.prohibited_substitutions
    )
    assert (
        "maximum_tail_loss_margin_usage_and_daily_loss_bound"
        in options.execution_feasibility_contract.mandatory_risk_controls
    )


def test_v4_register_records_why_no_third_proposal_was_padded() -> None:
    screened = {
        item.theory_id: item.disposition
        for item in frozen_register().screened_out_theories
    }

    assert screened == {
        "LIQUIDATION_EVENT_DIRECTIONAL_REACTION": (
            "NOT_REGISTERED_RETIRED_LINEAGE_OVERLAP"
        ),
        "OPTION_PUT_CALL_PARITY_ARBITRAGE": (
            "NOT_REGISTERED_RELATED_TO_REGISTERED_PROPOSAL"
        ),
        "STABLECOIN_MINT_REDEMPTION_ARBITRAGE": (
            "NOT_REGISTERED_EXECUTION_ACCESS_NOT_CREDIBLE"
        ),
        "TRIANGULAR_WITHIN_VENUE_ARBITRAGE": (
            "NOT_REGISTERED_RELATED_TO_REGISTERED_PROPOSAL"
        ),
    }


def test_v4_register_refuses_permission_or_outcome_tampering() -> None:
    payload = frozen_register().model_dump()
    payload["authorizes_network_requests"] = True
    payload["return_metrics_calculated"] = ["net_profit"]

    with pytest.raises(ValidationError):
        V4MechanismProposalRegister.model_validate(payload)


def test_v4_register_refuses_source_support_weakening() -> None:
    payload = frozen_register().model_dump()
    payload["proposals"][0]["primary_sources"] = [
        source
        for source in payload["proposals"][0]["primary_sources"]
        if source["source_kind"] != "PEER_REVIEWED_ARTICLE"
    ]
    payload["register_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4MechanismProposalRegister.model_validate(payload)


def test_v4_register_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v4_proposal_register.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "V4" in completed.stdout
