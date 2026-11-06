import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_successor_charter import (
    JAM_SELECTED_PROPOSAL_ID,
    JamSuccessorHypothesisCharter,
    audit_jam_successor_hypothesis_charter,
)
from scripts.freeze_jam_successor_hypothesis_charter import (
    build_charter,
    load_inputs,
)

CHARTER_PATH = Path("data/evidence/jam_successor_hypothesis_charter_v1.json")


def stored_charter() -> JamSuccessorHypothesisCharter:
    return JamSuccessorHypothesisCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )


def rebuilt_charter() -> JamSuccessorHypothesisCharter:
    stored = stored_charter()
    failure, ledger, profile = load_inputs()
    return build_charter(
        frozen_at=stored.frozen_at,
        failure=failure,
        ledger=ledger,
        profile=profile,
    )


def test_stored_jam_successor_charter_matches_rebuild() -> None:
    stored = stored_charter()

    assert stored == rebuilt_charter()
    assert audit_jam_successor_hypothesis_charter(stored) is True
    assert stored.status == "FROZEN_DESIGN_ONLY_NOT_AUTHORIZED_TO_RUN"
    assert stored.new_outcome_fields_inspected == ()


def test_charter_selects_one_flow_hypothesis_for_capability_review() -> None:
    charter = stored_charter()
    selected = [
        proposal
        for proposal in charter.proposals
        if proposal.decision == "SELECT_FOR_FUTURE_CAPABILITY_REVIEW_ONLY"
    ]

    assert len(selected) == 1
    assert selected[0].proposal_id == JAM_SELECTED_PROPOSAL_ID
    assert selected[0].exact_pine_compatible is False
    assert selected[0].btcusdt_spot_scope_compatible is True
    assert selected[0].historical_fill_identifiable is True
    assert charter.next_required_authorization == (
        "AUTHORIZE_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS"
    )


def test_charter_rejects_parameter_rescue_and_unidentifiable_maker_fills() -> None:
    decisions = {
        proposal.proposal_id: proposal.decision
        for proposal in stored_charter().proposals
    }

    assert decisions["J2-P02-CANDLE-PARAMETER-RESCUE"] == "REJECT"
    assert decisions["J2-P03-PASSIVE-MAKER-RETEST"] == "REJECT"
    assert decisions["J2-P04-LOW-ACTIVITY-CROSS-ASSET-REVERSAL"] == "DEFER"


def test_charter_maps_consumed_provisional_and_forward_evidence() -> None:
    partitions = {
        partition.partition_id: partition
        for partition in stored_charter().evidence_partitions
    }

    assert partitions["JAM-V1-CONSUMED-2023-2025"].state == "CONSUMED"
    assert partitions["JAM-V1-EXPLORATORY-2026"].state == (
        "EXPLORATORY_CONTAMINATED"
    )
    assert partitions["JAM-PROVISIONAL-HISTORICAL-POOL-2019-2022"].state == (
        "PROVISIONAL_UNOPENED_UNVERIFIED"
    )
    assert partitions["JAM-LOCKED-FORWARD-2026-08-01"].state == "LOCKED_FORWARD"
    assert all(
        partition.outcome_access_permitted is False
        for partition in partitions.values()
    )


def test_charter_grants_no_research_or_trading_authority() -> None:
    charter = stored_charter()

    assert charter.creates_strategy_version is False
    assert charter.authorizes_market_data_import is False
    assert charter.authorizes_parameter_definition is False
    assert charter.authorizes_return_testing is False
    assert charter.authorizes_candidate is False
    assert charter.authorizes_forward_paper is False
    assert charter.authorizes_testnet_strategy_orders is False
    assert charter.authorizes_production is False
    assert charter.authorizes_live is False


def test_charter_refuses_authority_tampering() -> None:
    payload = json.loads(stored_charter().model_dump_json())
    payload["authorizes_market_data_import"] = True

    with pytest.raises(ValidationError, match="cannot grant authority"):
        JamSuccessorHypothesisCharter.model_validate(payload)


def test_charter_refuses_false_pine_compatibility() -> None:
    payload = json.loads(stored_charter().model_dump_json())
    payload["exact_pine_signal_supported"] = True

    with pytest.raises(ValidationError, match="not exactly available in Pine"):
        JamSuccessorHypothesisCharter.model_validate(payload)

