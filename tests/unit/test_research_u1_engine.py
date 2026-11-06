from datetime import UTC, datetime, timedelta
from decimal import Decimal, getcontext, localcontext

import pytest

from aurex.backtest_engine.research_engine import R3Candle
from aurex.backtest_engine.research_u1_engine import (
    U1ResearchReplayConfig,
    audit_u1_research_replay,
    calculate_u1_exposure,
    prepare_u1_market_data,
    run_u1_research_replay,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64
DATA_START = datetime(2023, 1, 1, tzinfo=UTC)
TOTAL_BARS = 400
DATA_END = DATA_START + timedelta(hours=4 * TOTAL_BARS)
EVALUATION_START = DATA_START + timedelta(hours=4 * 200)
EVALUATION_END = DATA_START + timedelta(hours=4 * 380)


def symbol_name(index: int) -> str:
    return f"SYMBOL{index:02d}USDT"


def candles(
    *,
    rate: str = "0.02",
    count: int = TOTAL_BARS,
    entry_bar_close_multiplier: str | None = None,
) -> list[R3Candle]:
    with localcontext() as context:
        context.prec = 50
        slope = Decimal(rate)
        output = []
        for index in range(count):
            close = Decimal("100") * (slope * Decimal(index)).exp()
            if (
                entry_bar_close_multiplier is not None
                and index == 200
            ):
                close *= Decimal(entry_bar_close_multiplier)
            output.append(
                R3Candle(
                    timestamp=DATA_START + timedelta(hours=4 * index),
                    open=Decimal("100") * (slope * Decimal(index)).exp(),
                    high=max(close, Decimal("100")),
                    low=min(close, Decimal("100")),
                    close=close,
                    volume="1000",
                )
            )
        return output


def market_data(
    *,
    count: int = 21,
    rate: str = "0.02",
    terminal_rows: dict[str, int] | None = None,
    entry_bar_close_multiplier: str | None = None,
):
    terminal_rows = terminal_rows or {}
    return prepare_u1_market_data(
        {
            symbol_name(index): candles(
                rate=rate,
                count=terminal_rows.get(symbol_name(index), TOTAL_BARS),
                entry_bar_close_multiplier=entry_bar_close_multiplier,
            )
            for index in range(count)
        },
        data_start=DATA_START,
        data_end=DATA_END,
    )


def config(
    data,
    *,
    role: str = "PRIMARY",
    omitted_symbols: list[str] | None = None,
    evaluation_end: datetime = EVALUATION_END,
):
    return U1ResearchReplayConfig(
        variant_role=role,
        evaluation_start=EVALUATION_START,
        evaluation_end=evaluation_end,
        baseline_decision_symbols=list(data.symbols),
        omitted_symbols=omitted_symbols or [],
        cost_multiplier="1",
        discovery_charter_evidence_hash=HASH_A,
        theory_screen_evidence_hash=HASH_B,
        primary_protocol_evidence_hash=HASH_C,
        execution_specification_evidence_hash=HASH_D,
        universe_manifest_evidence_hash=HASH_E,
        development_dataset_bundle_evidence_hash=HASH_F,
        market_data_evidence_hash=data.market_data_evidence_hash,
    )


def test_u1_exposure_uses_exact_inverse_variance_arithmetic() -> None:
    data = market_data(rate="0.02")

    variance, exposure = calculate_u1_exposure(
        data,
        signal_index=199,
        active_symbols=list(data.symbols),
    )

    with localcontext() as context:
        context.prec = 50
        assert abs(variance - Decimal("0.8760")) < Decimal("1E-24")
        assert exposure == Decimal("0.36") / variance


def test_primary_retains_cash_and_equal_weights_below_benchmark() -> None:
    data = market_data(rate="0.02")

    primary = run_u1_research_replay(config(data), data)
    benchmark = run_u1_research_replay(config(data, role="BENCHMARK"), data)

    assert primary.signals[0].target_exposure < 1
    assert benchmark.signals[0].target_exposure == 1
    primary_entries = [
        item for item in primary.opportunities if item.rebalance_at == EVALUATION_START
    ]
    assert len(primary_entries) == 21
    assert len({item.target_fill_notional for item in primary_entries}) == 1
    assert primary.equity_curve[0].cash > benchmark.equity_curve[0].cash
    assert (
        primary.equity_curve[0].gross_exposure_percent
        < benchmark.equity_curve[0].gross_exposure_percent
    )
    assert primary.equity_curve[-1].open_positions == 0
    assert primary.equity_curve[-1].equity == primary.metrics.final_equity
    with localcontext() as context:
        context.prec = 50
        assert sum(
            (trade.net_pl for trade in primary.trades), Decimal("0")
        ) == primary.metrics.net_pl


def test_signal_uses_prior_close_not_entry_bar_close() -> None:
    baseline = market_data(rate="0.02")
    changed = market_data(rate="0.02", entry_bar_close_multiplier="9")
    one_bar_end = EVALUATION_START + timedelta(hours=4)

    expected = run_u1_research_replay(
        config(baseline, evaluation_end=one_bar_end), baseline
    )
    actual = run_u1_research_replay(
        config(changed, evaluation_end=one_bar_end), changed
    )

    assert actual.signals == expected.signals
    assert [
        (item.symbol, item.accepted_quantity) for item in actual.opportunities
    ] == [
        (item.symbol, item.accepted_quantity) for item in expected.opportunities
    ]


def test_terminal_held_market_is_written_off_at_zero() -> None:
    terminal_at = 205
    symbol = symbol_name(0)
    data = market_data(terminal_rows={symbol: terminal_at})

    result = run_u1_research_replay(config(data), data)

    writeoffs = [
        trade
        for trade in result.trades
        if trade.exit_reason == "MARKET_TERMINATION_WRITE_OFF"
    ]
    assert len(writeoffs) == 1
    assert writeoffs[0].symbol == symbol
    assert writeoffs[0].raw_exit_price == 0
    assert writeoffs[0].exit_fill_price == 0
    assert writeoffs[0].exit_fee == 0
    assert writeoffs[0].exit_slippage_cost == 0
    assert result.availability_events[0].held_position_written_off is True
    assert result.metrics.termination_writeoff_count == 1


def test_leave_one_out_removes_symbol_and_preserves_breadth() -> None:
    data = market_data()
    omitted = symbol_name(20)

    result = run_u1_research_replay(
        config(data, omitted_symbols=[omitted]), data
    )

    assert result.rebalance_breadth[0].active_symbol_count == 20
    assert omitted not in {trade.symbol for trade in result.trades}
    assert omitted not in {item.symbol for item in result.opportunities}


def test_replay_is_hash_stable_auditable_and_context_independent() -> None:
    data = market_data()
    replay_config = config(data)
    expected = run_u1_research_replay(replay_config, data)
    original_precision = getcontext().prec
    try:
        getcontext().prec = 9
        actual = run_u1_research_replay(replay_config, data)
    finally:
        getcontext().prec = original_precision

    assert actual == expected
    assert audit_u1_research_replay(
        replay_config, data, expected
    ).status == "PASS"
    tampered = expected.model_copy(update={"result_evidence_hash": "0" * 64})
    audit = audit_u1_research_replay(replay_config, data, tampered)
    assert audit.status == "BLOCKED"
    assert audit.reasons == [
        "stored_result_evidence_hash_mismatch",
        "deterministic_replay_mismatch",
    ]


def test_prepare_blocks_internal_or_resumed_gap() -> None:
    broken = candles()
    broken = broken[:10] + broken[11:]
    series = {
        symbol_name(index): (broken if index == 0 else candles())
        for index in range(21)
    }

    with pytest.raises(ValueError, match="internal, duplicate, or resumed gap"):
        prepare_u1_market_data(
            series,
            data_start=DATA_START,
            data_end=DATA_END,
        )


def test_fee_reserved_allocation_never_exceeds_cash() -> None:
    data = market_data(rate="0")

    result = run_u1_research_replay(
        config(
            data,
            role="BENCHMARK",
            evaluation_end=EVALUATION_START + timedelta(hours=4),
        ),
        data,
    )

    assert result.equity_curve[0].cash >= 0
    assert result.metrics.total_commission > 0
    assert result.metrics.total_slippage > 0
    assert result.metrics.maximum_gross_exposure_percent <= 100
