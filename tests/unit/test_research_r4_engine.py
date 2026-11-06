from datetime import UTC, datetime, timedelta
from decimal import Decimal, getcontext, localcontext

import pytest

from aurex.backtest_engine.research_engine import (
    R3Candle,
    R3ReplayMetrics,
    prepare_r3_market_data,
)
from aurex.backtest_engine.research_r4_engine import (
    R4ResearchReplayConfig,
    audit_r4_research_replay,
    prepare_r4_market_data,
    run_r4_research_replay,
)
from aurex.backtest_engine.research_r31_engine import (
    R31ResearchReplayConfig,
    run_r31_research_replay,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
VALIDATION_START = datetime(2025, 1, 1, tzinfo=UTC)
VALIDATION_BARS = 20
VALIDATION_END = VALIDATION_START + timedelta(hours=4 * VALIDATION_BARS)
DEVELOPMENT_BARS = 510
DEVELOPMENT_START = VALIDATION_START - timedelta(hours=4 * DEVELOPMENT_BARS)


def trend_candles(
    *,
    rate: str,
    start: datetime,
    count: int,
    offset: int = 0,
) -> list[R3Candle]:
    with localcontext() as context:
        context.prec = 50
        base = Decimal("100")
        slope = Decimal(rate)
        candles = []
        for local_index in range(count):
            index = offset + local_index
            close = base * (slope * Decimal(index)).exp()
            candles.append(
                R3Candle(
                    timestamp=start + timedelta(hours=4 * local_index),
                    open=close,
                    high=close * Decimal("1.001"),
                    low=close * Decimal("0.999"),
                    close=close,
                    volume="1000",
                )
            )
        return candles


def split_market(
    rates: dict[str, str],
    *,
    terminal_rows: dict[str, int] | None = None,
):
    terminal_rows = terminal_rows or {}
    development = {
        symbol: trend_candles(
            rate=rate,
            start=DEVELOPMENT_START,
            count=DEVELOPMENT_BARS,
        )
        for symbol, rate in rates.items()
    }
    validation = {
        symbol: trend_candles(
            rate=rate,
            start=VALIDATION_START,
            count=terminal_rows.get(symbol, VALIDATION_BARS),
            offset=DEVELOPMENT_BARS,
        )
        for symbol, rate in rates.items()
    }
    return development, validation


def r4_data(
    rates: dict[str, str] | None = None,
    *,
    terminal_rows: dict[str, int] | None = None,
):
    development, validation = split_market(
        rates
        or {
            "ALPHAUSDT": "0.002",
            "BETAUSDT": "0.0015",
            "GAMMAUSDT": "0.001",
        },
        terminal_rows=terminal_rows,
    )
    return prepare_r4_market_data(
        development_by_symbol=development,
        validation_by_symbol=validation,
        validation_start=VALIDATION_START,
        validation_end=VALIDATION_END,
    )


def r4_config(data, *, omitted_symbols=None, cost_multiplier="1"):
    return R4ResearchReplayConfig(
        evaluation_start=VALIDATION_START,
        evaluation_end=VALIDATION_END,
        baseline_decision_symbols=list(data.symbols),
        omitted_symbols=omitted_symbols or [],
        cost_multiplier=cost_multiplier,
        universe_manifest_evidence_hash=HASH_A,
        development_dataset_bundle_evidence_hash=HASH_B,
        candidate_protocol_evidence_hash=HASH_C,
        validation_dataset_bundle_evidence_hash=HASH_D,
        execution_specification_evidence_hash=HASH_E,
        market_data_evidence_hash=data.market_data_evidence_hash,
    )


def test_continuous_r4_replay_is_exactly_equivalent_to_r31_core() -> None:
    development, validation = split_market(
        {
            "ALPHAUSDT": "0.002",
            "BETAUSDT": "0.0015",
            "GAMMAUSDT": "0.001",
        }
    )
    r4_market = prepare_r4_market_data(
        development_by_symbol=development,
        validation_by_symbol=validation,
        validation_start=VALIDATION_START,
        validation_end=VALIDATION_END,
    )
    combined = prepare_r3_market_data(
        {
            symbol: development[symbol] + validation[symbol]
            for symbol in development
        }
    )
    r31_config = R31ResearchReplayConfig(
        evaluation_start=VALIDATION_START,
        evaluation_end=VALIDATION_END,
        baseline_decision_symbols=list(combined.symbols),
        cost_multiplier="1",
        universe_manifest_evidence_hash=HASH_A,
        development_dataset_bundle_evidence_hash=HASH_B,
        protocol_evidence_hash=HASH_C,
        execution_specification_evidence_hash=HASH_E,
        market_data_evidence_hash=combined.market_data_evidence_hash,
    )

    expected = run_r31_research_replay(r31_config, combined)
    actual = run_r4_research_replay(r4_config(r4_market), r4_market)

    assert [item.model_dump() for item in actual.trades] == [
        item.model_dump() for item in expected.trades
    ]
    assert [item.model_dump() for item in actual.opportunities] == [
        item.model_dump() for item in expected.opportunities
    ]
    assert actual.equity_curve == expected.equity_curve
    for field in R3ReplayMetrics.model_fields:
        assert getattr(actual.metrics, field) == getattr(expected.metrics, field)
    assert actual.availability_events == []
    assert actual.metrics.termination_writeoff_count == 0


def test_held_terminal_market_is_written_off_at_zero_once() -> None:
    data = r4_data(terminal_rows={"ALPHAUSDT": 3})

    result = run_r4_research_replay(r4_config(data), data)

    writeoffs = [
        trade
        for trade in result.trades
        if trade.exit_reason == "MARKET_TERMINATION_WRITE_OFF"
    ]
    assert len(writeoffs) == 1
    writeoff = writeoffs[0]
    assert writeoff.symbol == "ALPHAUSDT"
    assert writeoff.raw_exit_price == 0
    assert writeoff.exit_fill_price == 0
    assert writeoff.exit_notional == 0
    assert writeoff.exit_fee == 0
    assert writeoff.exit_slippage_cost == 0
    assert result.metrics.termination_writeoff_count == 1
    assert result.metrics.termination_writeoff_net_pl == writeoff.net_pl
    assert result.availability_events[0].held_position_written_off is True


def test_unheld_terminal_market_is_permanently_removed_without_trade() -> None:
    data = r4_data(
        rates={
            "ALPHAUSDT": "0",
            "BETAUSDT": "0",
            "GAMMAUSDT": "0",
        },
        terminal_rows={"ALPHAUSDT": 3},
    )

    result = run_r4_research_replay(r4_config(data), data)

    assert result.trades == []
    assert result.metrics.termination_writeoff_count == 0
    assert result.availability_events[0].symbol == "ALPHAUSDT"
    assert result.availability_events[0].held_position_written_off is False


def test_prepare_blocks_internal_gap_or_resumed_series() -> None:
    development, validation = split_market(
        {
            "ALPHAUSDT": "0.002",
            "BETAUSDT": "0.0015",
            "GAMMAUSDT": "0.001",
        }
    )
    validation["ALPHAUSDT"] = [
        validation["ALPHAUSDT"][0],
        validation["ALPHAUSDT"][2],
    ]

    with pytest.raises(ValueError, match="internal, duplicate, or resumed gap"):
        prepare_r4_market_data(
            development_by_symbol=development,
            validation_by_symbol=validation,
            validation_start=VALIDATION_START,
            validation_end=VALIDATION_END,
        )


def test_replay_is_hash_stable_auditable_and_context_independent() -> None:
    data = r4_data(terminal_rows={"ALPHAUSDT": 3})
    config = r4_config(data)
    expected = run_r4_research_replay(config, data)
    original_precision = getcontext().prec
    try:
        getcontext().prec = 9
        actual = run_r4_research_replay(config, data)
    finally:
        getcontext().prec = original_precision

    assert actual == expected
    assert audit_r4_research_replay(config, data, expected).status == "PASS"
    tampered = expected.model_copy(update={"result_evidence_hash": "0" * 64})
    audit = audit_r4_research_replay(config, data, tampered)
    assert audit.status == "BLOCKED"
    assert audit.reasons == [
        "stored_result_evidence_hash_mismatch",
        "deterministic_replay_mismatch",
    ]


def test_leave_one_out_keeps_fixed_selection_count_and_baseline() -> None:
    rates = {
        f"SYMBOL{index:02d}USDT": str(Decimal("0.0005") + Decimal(index) / 10000)
        for index in range(8)
    }
    data = r4_data(rates=rates)

    result = run_r4_research_replay(
        r4_config(data, omitted_symbols=["SYMBOL07USDT"]),
        data,
    )

    assert result.rebalance_breadth[0].active_symbol_count == 7
    assert result.rebalance_breadth[0].selected_market_count == 7
    assert {trade.symbol for trade in result.trades} == {
        f"SYMBOL{index:02d}USDT" for index in range(7)
    }
