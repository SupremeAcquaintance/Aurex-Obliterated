from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from aurex.backtest_engine.s2_btc_source_execution import S2BtcPriceRow
from aurex.backtest_engine.s2_development_measurement_execution import (
    S2DevelopmentMeasurementRow,
    growth_ppm,
)
from aurex.backtest_engine.s2_strategy_preregistration import S2StrategyPreregistration
from scripts.freeze_s2_development_backtest_protocol import build_protocol
from scripts.run_s2_development_backtest import (
    apply_interval,
    build_hashed,
    calmar_ratio,
    compare_metric,
    compound_annual_growth_rate,
    desired_position,
    evaluate_gates,
    maximum_drawdown,
    profit_factor,
    simulate_candidate,
    stationary_bootstrap_lower_mean,
    weekly_sharpe,
)


def measurement_rows(*, agreements: tuple[str, ...]) -> tuple[S2DevelopmentMeasurementRow, ...]:
    rows = []
    first_week = date(2017, 10, 7)
    for index, agreement in enumerate(agreements):
        if agreement == "BOTH_BROADENING":
            tx_current, fee_current = 110, 110
        elif agreement == "BOTH_CONTRACTING":
            tx_current, fee_current = 90, 90
        else:
            tx_current, fee_current = 110, 90
        week = first_week + timedelta(days=7 * index)
        rows.append(
            S2DevelopmentMeasurementRow(
                sequence=index + 8,
                week_start=week,
                decision_cutoff_at=week + timedelta(days=7),
                earliest_execution_at=week + timedelta(days=9),
                source_payload_evidence_hash="1" * 64,
                confirmed_tx_current_4w=tx_current,
                confirmed_tx_prior_4w=100,
                confirmed_fee_sats_current_4w=fee_current,
                confirmed_fee_sats_prior_4w=100,
                confirmed_tx_growth_ppm=growth_ppm(tx_current, 100),
                confirmed_fee_growth_ppm=growth_ppm(fee_current, 100),
                settlement_demand_agreement=agreement,
            )
        )
    return tuple(rows)


def price_rows(values: tuple[str, ...]) -> tuple[S2BtcPriceRow, ...]:
    rows = []
    first = date(2017, 10, 16)
    for index, value in enumerate(values):
        day = first + timedelta(days=7 * index)
        rows.append(
            build_hashed(
                S2BtcPriceRow,
                "price_evidence_hash",
                sequence=index + 1,
                measurement_sequence=index + 8,
                activation_date=day,
                activation_open_time_ms=(1_508_112_000_000 + index * 604_800_000),
                open_price=value,
                archive_file_sha256="2" * 64,
                published_archive_sha256="2" * 64,
                checksum_file_sha256="3" * 64,
                source_target_id=f"{index + 1:03d}-btcusdt-1h-{day.isoformat()}",
            )
        )
    return tuple(rows)


def test_desired_position_uses_only_frozen_agreement() -> None:
    rows = measurement_rows(
        agreements=("BOTH_BROADENING", "BOTH_CONTRACTING", "FLAT_OR_MIXED")
    )

    assert tuple(desired_position(row) for row in rows) == (1, 0, 0)


def test_apply_interval_charges_entry_before_return_and_terminal_exit() -> None:
    equity, interval_return, entry, terminal = apply_interval(
        equity=Decimal("100"),
        current_position=0,
        desired=1,
        current_price=Decimal("100"),
        next_price=Decimal("110"),
        cost_bps=Decimal("15"),
        terminal=True,
    )

    expected = Decimal("100") * Decimal("0.9985") * Decimal("1.1") * Decimal("0.9985")
    assert equity == expected
    assert interval_return == expected / Decimal("100") - 1
    assert entry is True
    assert terminal is True


def test_cash_interval_has_no_cost_or_market_return() -> None:
    observed = apply_interval(
        equity=Decimal("100"),
        current_position=0,
        desired=0,
        current_price=Decimal("100"),
        next_price=Decimal("200"),
        cost_bps=Decimal("15"),
        terminal=False,
    )

    assert observed == (Decimal("100"), Decimal("0"), False, False)


def test_maximum_drawdown_uses_peak_to_trough_equity() -> None:
    assert maximum_drawdown(
        (Decimal("100"), Decimal("120"), Decimal("90"), Decimal("110"))
    ) == Decimal("0.25")


def test_profit_factor_uses_interval_dollar_pnl() -> None:
    assert profit_factor((Decimal("2"), Decimal("-1"), Decimal("3"))) == "5"
    assert profit_factor((Decimal("1"), Decimal("2"))) == "Infinity"
    assert profit_factor((Decimal("0"),)) == "0"


def test_weekly_sharpe_uses_sample_standard_deviation_and_sqrt_52() -> None:
    returns = (Decimal("0.01"), Decimal("0.02"), Decimal("-0.01"))
    mean = sum(returns) / Decimal(3)
    sample_variance = sum((value - mean) ** 2 for value in returns) / Decimal(2)
    expected = mean / sample_variance.sqrt() * Decimal(52).sqrt()

    assert weekly_sharpe(returns) == str(expected)
    assert weekly_sharpe((Decimal("0.01"), Decimal("0.01"))) == "Infinity"
    assert weekly_sharpe((Decimal("0"), Decimal("0"))) == "0"


def test_cagr_and_calmar_follow_frozen_formulas() -> None:
    cagr = compound_annual_growth_rate(Decimal("200"), Decimal("100"), 272)

    assert cagr == Decimal("2") ** (Decimal(52) / Decimal(272)) - 1
    assert calmar_ratio(cagr, Decimal("0.2")) == str(cagr / Decimal("0.2"))
    assert calmar_ratio(Decimal("0.1"), Decimal("0")) == "Infinity"
    assert calmar_ratio(Decimal("0"), Decimal("0")) == "0"


def test_stationary_bootstrap_constant_series_is_exact() -> None:
    observed = stationary_bootstrap_lower_mean(
        (Decimal("0.01"),) * 20,
        resamples=100,
        restart_probability=Decimal("0.125"),
        seed=2718,
        order_index=4,
    )

    assert observed == Decimal("0.01")


def test_stationary_bootstrap_is_seed_reproducible() -> None:
    values = tuple(Decimal(index) / Decimal("100") for index in range(-5, 6))
    kwargs = {
        "resamples": 100,
        "restart_probability": Decimal("0.125"),
        "seed": 2718,
        "order_index": 4,
    }

    assert stationary_bootstrap_lower_mean(values, **kwargs) == (
        stationary_bootstrap_lower_mean(values, **kwargs)
    )


def test_all_cash_simulation_produces_272_zero_strategy_intervals() -> None:
    protocol = build_protocol(frozen_at=protocol_time())
    measurements = measurement_rows(agreements=("FLAT_OR_MIXED",) * 273)
    prices = price_rows(values=("100",) * 273)

    outcome, ledger = simulate_candidate(
        measurements=measurements, prices=prices, protocol=protocol
    )

    assert len(ledger) == 272
    assert outcome.position_transition_count == 0
    assert outcome.long_interval_count == 0
    assert outcome.long_exposure_fraction == "0"
    assert outcome.base_final_equity_usd == "100"
    assert outcome.base_net_total_return == "0"
    assert outcome.base_profit_factor == "0"
    assert outcome.base_maximum_drawdown == "0"
    assert outcome.stress_bootstrap_lower_mean_weekly_return == "0"
    assert outcome.buy_hold_base_final_equity_usd == str(
        Decimal("100") * Decimal("0.9985") * Decimal("0.9985")
    )


def test_all_long_simulation_charges_exactly_entry_and_terminal_fills() -> None:
    protocol = build_protocol(frozen_at=protocol_time())
    measurements = measurement_rows(agreements=("BOTH_BROADENING",) * 273)
    prices = price_rows(values=("100",) * 273)

    outcome, ledger = simulate_candidate(
        measurements=measurements, prices=prices, protocol=protocol
    )

    assert outcome.position_transition_count == 2
    assert outcome.long_interval_count == 272
    assert sum(row.fill_count for row in ledger) == 2
    assert ledger[0].entry_fill is True
    assert ledger[-1].terminal_liquidation_fill is True


def test_simulation_rejects_measurement_price_misalignment() -> None:
    protocol = build_protocol(frozen_at=protocol_time())
    measurements = list(measurement_rows(agreements=("FLAT_OR_MIXED",) * 273))
    prices = price_rows(values=("100",) * 273)
    first = measurements[0].model_copy(
        update={"earliest_execution_at": date(2017, 10, 17)}
    )
    measurements[0] = first

    with pytest.raises(ValueError, match="not aligned"):
        simulate_candidate(
            measurements=tuple(measurements), prices=prices, protocol=protocol
        )


def test_all_fifteen_gates_are_mapped_once() -> None:
    protocol = build_protocol(frozen_at=protocol_time())
    preregistration = S2StrategyPreregistration.model_validate_json(
        (Path("data/evidence/s2_strategy_preregistration_v1.json")).read_text()
    )
    outcome, _ = simulate_candidate(
        measurements=measurement_rows(agreements=("FLAT_OR_MIXED",) * 273),
        prices=price_rows(values=("100",) * 273),
        protocol=protocol,
    )

    gates = evaluate_gates(outcome, preregistration)

    assert len(gates) == 15
    assert tuple(gate.gate_id for gate in gates) == tuple(
        gate.gate_id for gate in preregistration.development_gates
    )
    assert sum(gate.status == "FAIL" for gate in gates) > 0


@pytest.mark.parametrize(
    ("observed", "operator", "threshold", "expected"),
    (
        ("Infinity", "GE", "1", True),
        ("-Infinity", "LT", "0", True),
        ("1", "EQ", "1", True),
        ("0.9", "GE", "1", False),
    ),
)
def test_metric_comparison_handles_finite_and_infinite_values(
    observed, operator, threshold, expected
) -> None:
    assert compare_metric(observed, operator, threshold) is expected


def protocol_time():
    return datetime(2026, 8, 30, 22, 0, tzinfo=UTC)
