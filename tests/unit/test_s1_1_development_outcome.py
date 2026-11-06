from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aurex.backtest_engine.s1_development_outcome import (
    S11DevelopmentOutcomeProtocol,
)
from aurex.backtest_engine.s1_nfci_feature_execution import S1NfciFeatureRow
from aurex.backtest_engine.s1_strategy_preregistration import S1StrategyCandidate
from scripts.run_s1_1_development_outcome import (
    apply_interval,
    compare_metric,
    desired_position,
    feature_evidence_hash,
    maximum_drawdown,
    profit_factor,
    stationary_bootstrap_lower_mean,
)

PROTOCOL_PATH = Path("data/evidence/s1_1_development_outcome_protocol_v1.json")


def feature(*, level: str = "0", change_1v: str = "0", change_4v: str = "0"):
    return S1NfciFeatureRow(
        sequence=5,
        target_id="005-nfci-vintage-2017-09-14",
        source_vintage_date=date(2017, 9, 14),
        selected_observation_date=date(2017, 9, 8),
        release_lag_days=6,
        source_normalized_row_sha256="1" * 64,
        nfci_level=level,
        nfci_change_1v=change_1v,
        nfci_change_4v=change_4v,
    )


def primary() -> S1StrategyCandidate:
    return S1StrategyCandidate(
        candidate_id="S1-C1-CONSISTENT-EASING-PRIMARY",
        role="PRIMARY_ELIGIBILITY",
        long_rule="NFCI_CHANGE_1V_LT_0_AND_NFCI_CHANGE_4V_LT_0",
        may_be_promoted=True,
    )


def test_protocol_freezes_zero_value_reads_and_exact_cost_semantics() -> None:
    protocol = S11DevelopmentOutcomeProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    assert protocol.feature_values_parsed_during_protocol_freeze == 0
    assert protocol.price_values_parsed_during_protocol_freeze == 0
    assert protocol.returns_calculated_during_protocol_freeze == 0
    assert protocol.base_cost_bps_per_fill == "15"
    assert protocol.stress_cost_bps_per_fill == "22.5"
    assert "FORCE_CASH" in protocol.terminal_liquidation_policy


def test_primary_equality_is_cash() -> None:
    assert desired_position(feature(), primary()) == 0
    assert desired_position(feature(change_1v="-0.1", change_4v="0"), primary()) == 0
    assert desired_position(feature(change_1v="0", change_4v="-0.1"), primary()) == 0


def test_primary_requires_both_changes_strictly_negative() -> None:
    assert (
        desired_position(feature(change_1v="-0.1", change_4v="-0.2"), primary())
        == 1
    )


def test_cash_interval_has_zero_return_and_no_fill() -> None:
    equity, result, entry, terminal = apply_interval(
        equity=Decimal("100"),
        current_position=0,
        desired=0,
        current_price=Decimal("100"),
        next_price=Decimal("110"),
        cost_bps=Decimal("15"),
        terminal=False,
    )
    assert equity == Decimal("100")
    assert result == 0
    assert (entry, terminal) == (False, False)


def test_initial_long_entry_charges_one_fill_before_market_return() -> None:
    equity, result, entry, terminal = apply_interval(
        equity=Decimal("100"),
        current_position=0,
        desired=1,
        current_price=Decimal("100"),
        next_price=Decimal("110"),
        cost_bps=Decimal("15"),
        terminal=False,
    )
    assert equity == Decimal("109.83500")
    assert result == Decimal("0.09835")
    assert (entry, terminal) == (True, False)


def test_long_to_cash_transition_charges_cost_without_market_return() -> None:
    equity, result, entry, terminal = apply_interval(
        equity=Decimal("100"),
        current_position=1,
        desired=0,
        current_price=Decimal("100"),
        next_price=Decimal("110"),
        cost_bps=Decimal("15"),
        terminal=False,
    )
    assert equity == Decimal("99.8500")
    assert result == Decimal("-0.0015")
    assert (entry, terminal) == (True, False)


def test_terminal_long_interval_charges_forced_liquidation_fill() -> None:
    equity, result, entry, terminal = apply_interval(
        equity=Decimal("100"),
        current_position=1,
        desired=1,
        current_price=Decimal("100"),
        next_price=Decimal("110"),
        cost_bps=Decimal("15"),
        terminal=True,
    )
    assert equity == Decimal("109.8350")
    assert result == Decimal("0.09835")
    assert (entry, terminal) == (False, True)


def test_terminal_entry_from_cash_charges_two_fills() -> None:
    equity, _, entry, terminal = apply_interval(
        equity=Decimal("100"),
        current_position=0,
        desired=1,
        current_price=Decimal("100"),
        next_price=Decimal("110"),
        cost_bps=Decimal("15"),
        terminal=True,
    )
    assert equity == Decimal("109.670247500")
    assert (entry, terminal) == (True, True)


def test_maximum_drawdown_uses_running_equity_peak() -> None:
    assert maximum_drawdown(
        (Decimal("100"), Decimal("120"), Decimal("90"), Decimal("110"))
    ) == Decimal("0.25")


def test_profit_factor_uses_interval_dollar_pnl() -> None:
    assert profit_factor(
        (Decimal("10"), Decimal("-5"), Decimal("5"), Decimal("-5"))
    ) == "1.5"
    assert profit_factor((Decimal("1"), Decimal("2"))) == "Infinity"
    assert profit_factor((Decimal("0"),)) == "0"


def test_stationary_bootstrap_constant_series_is_exact() -> None:
    observed = stationary_bootstrap_lower_mean(
        (Decimal("0.01"),) * 16,
        resamples=100,
        restart_probability=Decimal("0.125"),
        seed=1729,
        order_index=4,
    )
    assert observed == Decimal("0.01")


def test_stationary_bootstrap_is_seed_reproducible() -> None:
    values = tuple(Decimal(value) for value in ("0.1", "-0.2", "0.05", "0.03"))
    first = stationary_bootstrap_lower_mean(
        values,
        resamples=200,
        restart_probability=Decimal("0.125"),
        seed=1729,
        order_index=9,
    )
    second = stationary_bootstrap_lower_mean(
        values,
        resamples=200,
        restart_probability=Decimal("0.125"),
        seed=1729,
        order_index=9,
    )
    assert first == second


def test_gate_comparison_handles_finite_and_infinite_metrics() -> None:
    assert compare_metric("276", "EQ", "276") is True
    assert compare_metric("0.2", "GE", "0.20") is True
    assert compare_metric("Infinity", "GE", "1.10") is True
    assert compare_metric("0", "GT", "0") is False


def test_feature_evidence_hash_is_deterministic() -> None:
    row = feature(level="-0.4", change_1v="-0.1", change_4v="-0.2")
    assert feature_evidence_hash(row) == feature_evidence_hash(row)
    assert len(feature_evidence_hash(row)) == 64


def test_interval_rejects_nonpositive_inputs() -> None:
    with pytest.raises(ValueError, match="positive"):
        apply_interval(
            equity=Decimal("100"),
            current_position=0,
            desired=1,
            current_price=Decimal("0"),
            next_price=Decimal("110"),
            cost_bps=Decimal("15"),
            terminal=False,
        )
