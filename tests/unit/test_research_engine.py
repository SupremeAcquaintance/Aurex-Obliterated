from datetime import UTC, datetime, timedelta
from decimal import Decimal, getcontext

import pytest

from aurex.backtest_engine.research_engine import (
    R3Candle,
    R3ResearchReplayConfig,
    audit_r3_research_replay,
    prepare_r3_market_data,
    run_r3_research_replay,
    sample_log_return_stddev,
    wilder_atr,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
START = datetime(2024, 1, 1, tzinfo=UTC)


def candles_from_closes(closes: list[str]) -> list[R3Candle]:
    candles: list[R3Candle] = []
    for index, raw_close in enumerate(closes):
        close = Decimal(raw_close)
        candles.append(
            R3Candle(
                timestamp=START + timedelta(hours=4 * index),
                open=close,
                high=close + Decimal("1"),
                low=close - Decimal("1"),
                close=close,
                volume="1000",
            )
        )
    return candles


def basic_market_data():
    return prepare_r3_market_data(
        {
            "BETAUSDT": candles_from_closes(
                ["100", "101", "102", "103", "104", "105", "106"]
            ),
            "ALPHAUSDT": candles_from_closes(
                ["100", "101", "102", "103", "104", "105", "106"]
            ),
            "GAMMAUSDT": candles_from_closes(
                ["100", "100.5", "100.75", "101", "101.25", "101.5", "101.75"]
            ),
        }
    )


def config_for(
    market_data,
    *,
    fixed_selected_count: int = 2,
    minimum_ranked_positions: int = 2,
    evaluation_start_index: int = 3,
    evaluation_end_index: int = 7,
    rebalance_bars: int = 2,
) -> R3ResearchReplayConfig:
    return R3ResearchReplayConfig(
        variant_id="synthetic-primary",
        variant_role="PRIMARY",
        lookback_bars=1,
        rebalance_bars=rebalance_bars,
        volatility_lookback_bars=2,
        atr_lookback_bars=2,
        catastrophe_stop_atr_multiple="3",
        selected_fraction="0.67",
        fixed_selected_count=fixed_selected_count,
        evaluation_start=market_data.timestamps[evaluation_start_index],
        evaluation_end=(
            market_data.timestamps[evaluation_end_index]
            if evaluation_end_index < len(market_data.timestamps)
            else market_data.timestamps[-1] + timedelta(hours=4)
        ),
        baseline_decision_symbols=list(market_data.symbols),
        initial_capital="1000",
        risk_per_position_percent="1",
        max_symbol_exposure_percent="40",
        max_gross_exposure_percent="100",
        max_open_positions=fixed_selected_count,
        minimum_ranked_positions=minimum_ranked_positions,
        quantity_increment="0.0001",
        price_increment="0.01",
        commission_percent_per_side="0.10",
        adverse_slippage_percent_per_side="0.05",
        cost_multiplier="1",
        universe_manifest_evidence_hash=HASH_A,
        development_dataset_bundle_evidence_hash=HASH_B,
        protocol_evidence_hash=HASH_C,
        execution_specification_evidence_hash=HASH_D,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )


def test_wilder_atr_uses_sma_seed_then_recursive_rma() -> None:
    candles = [
        R3Candle(
            timestamp=START,
            open="10",
            high="11",
            low="9",
            close="10",
            volume="1",
        ),
        R3Candle(
            timestamp=START + timedelta(hours=4),
            open="10",
            high="12",
            low="8",
            close="10",
            volume="1",
        ),
        R3Candle(
            timestamp=START + timedelta(hours=8),
            open="10",
            high="13",
            low="7",
            close="10",
            volume="1",
        ),
    ]

    assert wilder_atr(tuple(candles), 2) == (
        None,
        Decimal("3"),
        Decimal("4.5"),
    )


def test_volatility_uses_sample_stddev_of_exact_log_return_window() -> None:
    candles = tuple(candles_from_closes(["100", "100", "100", "100"]))

    assert sample_log_return_stddev(candles, signal_index=3, lookback_returns=2) == 0


def test_rebalance_ties_use_symbol_order_and_exit_before_reentry() -> None:
    market_data = basic_market_data()
    result = run_r3_research_replay(config_for(market_data), market_data)

    first_rebalance = market_data.timestamps[3]
    first_records = [
        item for item in result.opportunities if item.rebalance_at == first_rebalance
    ]
    assert [(item.symbol, item.rank, item.reason) for item in first_records] == [
        ("ALPHAUSDT", 1, "ENTRY_ACCEPTED"),
        ("BETAUSDT", 2, "ENTRY_ACCEPTED"),
        ("GAMMAUSDT", 3, "RANK_BELOW_SELECTION"),
    ]
    assert [trade.exit_reason for trade in result.trades] == [
        "REBALANCE",
        "REBALANCE",
        "END_OF_WINDOW",
        "END_OF_WINDOW",
    ]
    assert result.trades[0].exit_at == market_data.timestamps[5]
    assert result.trades[2].entry_at == market_data.timestamps[5]
    assert result.metrics.completed_trades == 4
    assert result.metrics.accepted_entries == 4
    assert sum((trade.net_pl for trade in result.trades), Decimal("0")) == (
        result.metrics.net_pl
    )


def test_entry_bar_stop_is_disabled_and_next_bar_gap_uses_open() -> None:
    alpha = [
        R3Candle(
            timestamp=START,
            open="100",
            high="101",
            low="99",
            close="100",
            volume="1",
        ),
        R3Candle(
            timestamp=START + timedelta(hours=4),
            open="100",
            high="101",
            low="99",
            close="100",
            volume="1",
        ),
        R3Candle(
            timestamp=START + timedelta(hours=8),
            open="100",
            high="111",
            low="99",
            close="110",
            volume="1",
        ),
        R3Candle(
            timestamp=START + timedelta(hours=12),
            open="100",
            high="101",
            low="50",
            close="100",
            volume="1",
        ),
        R3Candle(
            timestamp=START + timedelta(hours=16),
            open="70",
            high="75",
            low="65",
            close="72",
            volume="1",
        ),
        R3Candle(
            timestamp=START + timedelta(hours=20),
            open="72",
            high="73",
            low="71",
            close="72",
            volume="1",
        ),
    ]
    flat = candles_from_closes(["100", "99", "98", "97", "96", "95"])
    market_data = prepare_r3_market_data(
        {"ALPHAUSDT": alpha, "BETAUSDT": flat, "GAMMAUSDT": flat}
    )
    config = config_for(
        market_data,
        fixed_selected_count=1,
        minimum_ranked_positions=1,
        evaluation_start_index=3,
        evaluation_end_index=6,
        rebalance_bars=10,
    )

    result = run_r3_research_replay(config, market_data)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_bar_timestamp == market_data.timestamps[3]
    assert trade.exit_bar_timestamp == market_data.timestamps[4]
    assert trade.exit_reason == "FIXED_STOP"
    assert trade.stop_price == Decimal("79")
    assert trade.raw_exit_price == Decimal("70")


def test_insufficient_positive_markets_holds_cash() -> None:
    down = candles_from_closes(["100", "99", "98", "97", "96", "95", "94"])
    up = candles_from_closes(["100", "101", "102", "103", "104", "105", "106"])
    market_data = prepare_r3_market_data(
        {"ALPHAUSDT": up, "BETAUSDT": down, "GAMMAUSDT": down}
    )
    result = run_r3_research_replay(config_for(market_data), market_data)

    assert result.trades == []
    assert result.metrics.final_equity == Decimal("1000")
    assert result.metrics.profit_factor is None
    assert {
        record.reason for record in result.opportunities if record.score > 0
    } == {"INSUFFICIENT_POSITIVE_MARKETS"}


def test_market_data_requires_exact_alignment_and_continuity() -> None:
    aligned = candles_from_closes(["100", "101", "102"])
    shifted = candles_from_closes(["100", "101", "102"])
    shifted[1] = shifted[1].model_copy(
        update={"timestamp": shifted[1].timestamp + timedelta(hours=1)}
    )

    with pytest.raises(ValueError, match="continuity failed"):
        prepare_r3_market_data({"ALPHAUSDT": aligned, "BETAUSDT": shifted})


def test_replay_is_input_order_independent_hash_stable_and_auditable() -> None:
    first = basic_market_data()
    second = prepare_r3_market_data(
        {
            "GAMMAUSDT": list(first.candles_by_symbol["GAMMAUSDT"]),
            "ALPHAUSDT": list(first.candles_by_symbol["ALPHAUSDT"]),
            "BETAUSDT": list(first.candles_by_symbol["BETAUSDT"]),
        }
    )
    first_result = run_r3_research_replay(config_for(first), first)
    second_result = run_r3_research_replay(config_for(second), second)

    assert first.market_data_evidence_hash == second.market_data_evidence_hash
    assert first_result == second_result
    assert audit_r3_research_replay(
        config_for(first), first, first_result
    ).status == "PASS"

    tampered = first_result.model_copy(update={"result_evidence_hash": "0" * 64})
    audit = audit_r3_research_replay(config_for(first), first, tampered)
    assert audit.status == "BLOCKED"
    assert audit.reasons == [
        "stored_result_evidence_hash_mismatch",
        "deterministic_replay_mismatch",
    ]


def test_replay_pins_decimal_context_against_ambient_precision() -> None:
    market_data = basic_market_data()
    expected = run_r3_research_replay(config_for(market_data), market_data)
    original_precision = getcontext().prec
    try:
        getcontext().prec = 9
        actual = run_r3_research_replay(config_for(market_data), market_data)
    finally:
        getcontext().prec = original_precision

    assert actual == expected


def test_simultaneous_allocation_respects_cash_gross_and_symbol_caps() -> None:
    market_data = basic_market_data()
    result = run_r3_research_replay(config_for(market_data), market_data)
    first_entries = [
        trade for trade in result.trades if trade.entry_at == market_data.timestamps[3]
    ]

    assert len(first_entries) == 2
    assert sum(trade.entry_notional + trade.entry_fee for trade in first_entries) <= (
        Decimal("1000")
    )
    assert all(trade.entry_notional <= Decimal("400") for trade in first_entries)
    assert result.equity_curve[0].gross_exposure_percent <= Decimal("100")


def test_cost_stress_replays_fills_fees_sizing_and_capacity() -> None:
    market_data = basic_market_data()
    base_config = config_for(market_data)
    stressed_config = base_config.model_copy(update={"cost_multiplier": Decimal("2")})

    base = run_r3_research_replay(base_config, market_data)
    stressed = run_r3_research_replay(stressed_config, market_data)

    assert stressed.metrics.net_pl < base.metrics.net_pl
    assert stressed.metrics.total_commission > base.metrics.total_commission
    assert stressed.metrics.total_slippage > base.metrics.total_slippage
    assert stressed.trades[0].entry_fill_price > base.trades[0].entry_fill_price
    assert stressed.request_evidence_hash != base.request_evidence_hash
