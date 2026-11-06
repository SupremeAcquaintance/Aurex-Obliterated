import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r4_protocol import (
    R4CandidateProtocol,
    audit_r4_candidate_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r4_candidate import (
    authoritative_protocol,
    builder_contract_hash,
    load_parent_evidence,
)


class Args:
    evidence_root = Path("data/evidence")
    universe = evidence_root / "market_universe_manifest_v1.json"
    development_bundle = evidence_root / "development_4h_dataset_bundle_v1.json"
    r31_protocol = evidence_root / "r31_path_quality_study_v1.json"
    r31_execution = evidence_root / "r31_path_quality_execution_spec_v1.json"
    r31_package = evidence_root / "r31_path_quality_run_package_v1.json"
    r31_result = evidence_root / "r31_path_quality_result_v1.json"


@lru_cache(maxsize=1)
def protocol() -> R4CandidateProtocol:
    return authoritative_protocol(
        registered_at=datetime(2026, 7, 23, 14, tzinfo=UTC),
        parents=load_parent_evidence(Args()),
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


def test_r4_candidate_preserves_the_accepted_r31_strategy() -> None:
    frozen = protocol()

    assert frozen.candidate_id == "path_quality_spot_v1"
    assert frozen.signal.signal_id == "xsmom_path_quality_84d_14d_primary"
    assert frozen.signal.lookback_intervals == 504
    assert frozen.signal.rebalance_bars == 84
    assert frozen.selection_control.signal_changes_from_r31 == []
    assert frozen.selection_control.portfolio_changes_from_r31 == []
    assert frozen.selection_control.cost_changes_from_r31 == []
    assert len(frozen.decision_symbols) == 35
    assert frozen.replay_matrix.expected_total_runs == 42
    assert audit_r4_candidate_protocol(frozen) is True
    assert R4CandidateProtocol.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_r4_candidate_freezes_validation_without_opening_it() -> None:
    frozen = protocol()

    assert frozen.validation_data.partition_start.isoformat() == (
        "2025-01-01T00:00:00+00:00"
    )
    assert frozen.validation_data.partition_end.isoformat() == (
        "2026-01-01T00:00:00+00:00"
    )
    assert frozen.validation_data_acquired_at_registration is False
    assert frozen.preexisting_validation_data_artifacts == []
    assert frozen.preexisting_r4_result_artifacts == []
    assert frozen.validation_outcome_fields_inspected == []
    assert frozen.known_outcome_boundary.r4_validation_outcome_known is False
    assert frozen.selection_control.validation_pass_creates_paper_eligibility is False
    assert frozen.selection_control.validation_pass_creates_live_eligibility is False


def test_r4_candidate_has_prospective_terminal_market_semantics() -> None:
    data = protocol().validation_data

    assert data.accepted_availability_shapes == [
        "CONTIGUOUS_TERMINAL_SUFFIX_MISSING",
        "FULL_CONTINUOUS",
    ]
    assert data.leading_missing_candle_policy == "BLOCK_DATASET"
    assert data.internal_missing_candle_policy == "BLOCK_DATASET"
    assert data.resumed_after_missing_policy == "BLOCK_DATASET"
    assert data.terminated_held_symbol_policy == (
        "WRITE_OFF_TO_ZERO_AT_FIRST_MISSING_BAR"
    )
    assert data.replacement_symbols_allowed is False
    assert data.synthetic_candles_allowed is False


def test_r4_candidate_scales_sample_gate_and_requires_three_of_four_quarters() -> None:
    gates = protocol().gates

    assert gates.minimum_base_cost_completed_trades == 67
    assert "12_MONTHS_DIVIDED_BY_18_MONTHS" in gates.minimum_trade_count_basis
    assert gates.minimum_positive_quarterly_folds == 3
    assert gates.total_quarterly_folds == 4
    assert "4_FOLDS_DIVIDED_BY_6_FOLDS" in gates.positive_fold_basis
    assert gates.minimum_base_cost_profit_factor == Decimal("1.10")
    assert gates.maximum_base_cost_drawdown_percent == Decimal("20")


def test_r4_candidate_refuses_a_signal_change_even_with_recomputed_hash() -> None:
    payload = protocol().model_dump()
    payload["signal"]["lookback_intervals"] = 503

    with pytest.raises(ValidationError):
        R4CandidateProtocol.model_validate(rehash(payload))


def test_r4_candidate_refuses_a_replacement_symbol() -> None:
    payload = protocol().model_dump()
    payload["decision_symbols"][-1] = "BTCUSDT"

    with pytest.raises(ValidationError, match="exact R3.1 universe"):
        R4CandidateProtocol.model_validate(rehash(payload))


def test_r4_candidate_refuses_relaxed_gate() -> None:
    payload = protocol().model_dump()
    payload["gates"]["minimum_positive_quarterly_folds"] = 2

    with pytest.raises(ValidationError):
        R4CandidateProtocol.model_validate(rehash(payload))


def test_r4_candidate_refuses_preexisting_outcome() -> None:
    payload = protocol().model_dump()
    payload["validation_outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="predate validation data and outcomes"):
        R4CandidateProtocol.model_validate(rehash(payload))


def test_r4_builder_is_hash_bound_and_script_is_directly_invocable() -> None:
    assert len(builder_contract_hash()) == 64
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_r4_candidate.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
