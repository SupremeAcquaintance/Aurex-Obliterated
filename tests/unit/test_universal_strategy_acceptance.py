from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurex.backtest_engine.schemas import (
    AcceptanceCriteria,
    BacktestReportCreate,
    BacktestTradeInput,
)
from aurex.backtest_engine.service import (
    calculate_backtest_segments,
    moving_block_bootstrap_mean_lower_bound,
    sample_window_reasons,
    strict_strategy_factory_acceptance_criteria,
    universal_acceptance_configuration_reasons,
    universal_robustness_snapshot,
)


def strict_payload(*, include_costs: bool = True, variants: int = 1) -> BacktestReportCreate:
    holdout_start = datetime(2026, 3, 1, tzinfo=UTC)
    trades = [
        BacktestTradeInput(
            realized_pl=Decimal("2") if index % 5 else Decimal("-0.5"),
            fees=Decimal("0.10") if include_costs else None,
            slippage=Decimal("0.05") if include_costs else None,
            market_regime="TRENDING_UP",
            closed_at=holdout_start + timedelta(days=index),
        )
        for index in range(20)
    ]
    return BacktestReportCreate(
        strategy="factory_test_v1",
        strategy_version="1.0.0",
        symbols=["BTCUSDT"],
        timeframe="15m",
        data_source="synthetic-test-evidence",
        data_start=datetime(2026, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 4, 1, tzinfo=UTC),
        in_sample_start=datetime(2026, 1, 1, tzinfo=UTC),
        in_sample_end=datetime(2026, 1, 31, tzinfo=UTC),
        out_of_sample_start=datetime(2026, 2, 1, tzinfo=UTC),
        out_of_sample_end=datetime(2026, 2, 28, tzinfo=UTC),
        holdout_start=holdout_start,
        holdout_end=datetime(2026, 3, 31, tzinfo=UTC),
        tested_variant_count=variants,
        variant_registry_hash="a" * 64,
        cost_model={"commission_percent": "0.10"},
        slippage_model={"type": "fixed_ticks", "ticks": "2"},
        risk_snapshot={"risk_per_trade": "0.005"},
        trades=trades,
        acceptance_criteria=strict_strategy_factory_acceptance_criteria(
            min_holdout_trades=10,
            uncertainty_bootstrap_samples=1000,
        ),
    )


def test_strict_factory_helper_enables_all_universal_controls() -> None:
    criteria = strict_strategy_factory_acceptance_criteria()

    assert criteria.require_cost_stress is True
    assert criteria.require_uncertainty_bound is True
    assert criteria.require_multiple_testing_control is True
    assert criteria.require_holdout_decision is True


def test_complete_universal_evidence_passes_deterministically() -> None:
    payload = strict_payload()
    snapshot = universal_robustness_snapshot(
        payload,
        payload.acceptance_criteria,
        calculate_backtest_segments(payload),
    )

    assert snapshot["status"] == "PASS"
    assert snapshot["reasons"] == []
    assert snapshot["cost_stress"]["status"] == "PASS"
    assert snapshot["uncertainty"]["status"] == "PASS"
    assert snapshot["multiple_testing"]["status"] == "PASS"


def test_partial_universal_control_activation_fails_closed() -> None:
    payload = strict_payload()
    criteria = AcceptanceCriteria(require_cost_stress=True)

    reasons = universal_acceptance_configuration_reasons(criteria, payload)

    assert reasons[0].startswith("Universal robustness controls must be enabled together")


def test_missing_trade_level_costs_fail_cost_stress() -> None:
    payload = strict_payload(include_costs=False)
    snapshot = universal_robustness_snapshot(
        payload,
        payload.acceptance_criteria,
        calculate_backtest_segments(payload),
    )

    assert snapshot["status"] == "FAIL"
    assert snapshot["cost_stress"]["status"] == "FAIL"
    assert any("trade-level fees and slippage" in reason for reason in snapshot["reasons"])


def test_variant_pressure_raises_holdout_profit_factor_threshold() -> None:
    payload = strict_payload(variants=6)
    snapshot = universal_robustness_snapshot(
        payload,
        payload.acceptance_criteria,
        calculate_backtest_segments(payload),
    )

    assert snapshot["multiple_testing"]["profit_factor_penalty"] == "0.10"
    assert snapshot["multiple_testing"]["adjusted_profit_factor_threshold"] == "1.25"


def test_holdout_must_be_separate_from_validation_window() -> None:
    payload = strict_payload().model_copy(
        update={"holdout_start": datetime(2026, 2, 28, tzinfo=UTC)}
    )

    assert "Holdout window must start after the out-of-sample window ends" in (
        sample_window_reasons(payload)
    )


def test_bootstrap_lower_bound_is_reproducible() -> None:
    values = [Decimal("2"), Decimal("1"), Decimal("-0.25")] * 10

    first = moving_block_bootstrap_mean_lower_bound(
        values,
        samples=1000,
        confidence=Decimal("0.95"),
    )
    second = moving_block_bootstrap_mean_lower_bound(
        values,
        samples=1000,
        confidence=Decimal("0.95"),
    )

    assert first == second
