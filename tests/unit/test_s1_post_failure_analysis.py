from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.s1_development_outcome_execution import S11IntervalOutcome
from aurex.backtest_engine.s1_post_failure_analysis import S1PostFailureAnalysisProtocol
from scripts.run_s1_post_failure_analysis import (
    diagnostic_position_analysis,
    drawdown_chronology,
    exposure_episode_summary,
    gross_equity,
    stress_tail_concentration,
)

PROTOCOL_PATH = Path("data/evidence/s1_post_failure_analysis_protocol_v1.json")


def row(
    sequence: int,
    *,
    candidate: str = "PRIMARY",
    desired: int = 1,
    gross: str = "0",
    base_equity: str = "100",
    stress_equity: str | None = None,
    stress_pnl: str = "0",
) -> S11IntervalOutcome:
    return S11IntervalOutcome.model_construct(
        candidate_id=candidate,
        interval_sequence=sequence,
        feature_sequence=sequence + 4,
        target_date=date(2020, 1, sequence),
        next_target_date=date(2020, 1, sequence + 1),
        selected_open_time_ms=sequence,
        next_selected_open_time_ms=sequence + 1,
        open_price="100",
        next_open_price="100",
        desired_position=desired,
        prior_position=desired,
        entry_fill=False,
        terminal_liquidation_fill=False,
        fill_count=0,
        gross_interval_return=gross,
        base_equity_before="100",
        base_equity_after=base_equity,
        base_interval_return="0",
        base_interval_pnl_usd="0",
        stress_equity_before="100",
        stress_equity_after=stress_equity or base_equity,
        stress_interval_return="0",
        stress_interval_pnl_usd=stress_pnl,
        feature_row_evidence_hash="1" * 64,
        current_price_row_evidence_hash="2" * 64,
        next_price_row_evidence_hash="3" * 64,
        interval_evidence_hash="4" * 64,
    )


def test_protocol_forbids_rescue_variants_and_execution_authority() -> None:
    protocol = S1PostFailureAnalysisProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    assert protocol.parameter_variants_permitted == 0
    assert protocol.diagnostic_rescue_permitted is False
    assert protocol.authorizes_analysis_execution_now is False
    assert protocol.authorizes_validation_access is False
    assert protocol.authorizes_holdout_access is False
    assert protocol.authorizes_testnet_strategy_orders is False
    assert protocol.authorizes_live is False


def test_gross_equity_compounds_existing_primary_intervals() -> None:
    rows = (row(1, gross="0.10"), row(2, gross="-0.10"))
    assert gross_equity(rows) == Decimal("99.00")


def test_drawdown_uses_earliest_peak_and_trough_and_finds_recovery() -> None:
    rows = (
        row(1, base_equity="120"),
        row(2, base_equity="90"),
        row(3, base_equity="120"),
    )
    observed = drawdown_chronology(rows, basis="BASE")
    assert observed.maximum_drawdown == "0.25"
    assert observed.peak_date == date(2020, 1, 2)
    assert observed.trough_date == date(2020, 1, 3)
    assert observed.recovery_date == date(2020, 1, 4)


def test_drawdown_marks_unrecovered_episode() -> None:
    rows = (row(1, base_equity="120"), row(2, base_equity="80"))
    observed = drawdown_chronology(rows, basis="BASE")
    assert observed.recovered_before_development_end is False
    assert observed.recovery_date is None


def test_exposure_episodes_use_maximal_contiguous_long_runs() -> None:
    rows = (
        row(1, desired=1, gross="0.1"),
        row(2, desired=1, gross="-0.1"),
        row(3, desired=0),
        row(4, desired=1, gross="0"),
    )
    observed = exposure_episode_summary(rows)
    assert observed.long_episode_count == 2
    assert observed.long_interval_count == 3
    assert observed.shortest_episode_intervals == 1
    assert observed.longest_episode_intervals == 2
    assert observed.nonzero_long_interval_hit_rate == "0.5"


def test_tail_concentration_uses_pnl_magnitude_and_sequence_ties() -> None:
    rows = tuple(
        row(index, stress_pnl=str(value))
        for index, value in enumerate((10, 9, 8, 7, 6, 1, -10, -9, -8, -7, -6, -1), start=1)
    )
    observed = stress_tail_concentration(rows)
    assert observed.top_interval_sequences == (1, 2, 3, 4, 5)
    assert observed.bottom_interval_sequences == (7, 8, 9, 10, 11)
    assert observed.top_five_positive_pnl_share == str(Decimal(40) / Decimal(41))
    assert observed.bottom_five_negative_pnl_share == str(Decimal(40) / Decimal(41))


def test_diagnostic_analysis_detects_duplicate_vectors() -> None:
    grouped = {
        "PRIMARY": (row(1, candidate="PRIMARY", desired=1), row(2, candidate="PRIMARY", desired=0)),
        "D1": (row(1, candidate="D1", desired=1), row(2, candidate="D1", desired=1)),
        "D2": (row(1, candidate="D2", desired=0), row(2, candidate="D2", desired=1)),
        "D3": (row(1, candidate="D3", desired=0), row(2, candidate="D3", desired=1)),
    }
    unique, duplicates, agreement = diagnostic_position_analysis(grouped, primary_id="PRIMARY")
    assert unique == 2
    assert duplicates == ("D2==D3",)
    assert agreement == {"D1": "0.5", "D2": "0", "D3": "0"}


def test_actual_failed_outcome_lineage_is_development_only() -> None:
    protocol = S1PostFailureAnalysisProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    assert protocol.outcome_ledger_row_count == 1104
    assert protocol.primary_interval_count == 276
    assert protocol.new_market_data_values_read == 0
    assert protocol.new_candidate_definitions_created == 0
