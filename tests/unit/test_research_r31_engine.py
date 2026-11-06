from datetime import UTC, datetime, timedelta
from decimal import Decimal, getcontext, localcontext

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_engine import R3Candle, prepare_r3_market_data
from aurex.backtest_engine.research_r31_engine import (
    R31ResearchReplayConfig,
    audit_r31_research_replay,
    calculate_path_quality_signal,
    run_r31_research_replay,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
START = datetime(2023, 1, 1, tzinfo=UTC)


def trend_candles(*, rate: str, count: int = 510) -> list[R3Candle]:
    with localcontext() as context:
        context.prec = 50
        base = Decimal("100")
        slope = Decimal(rate)
        candles = []
        for index in range(count):
            close = base * (slope * Decimal(index)).exp()
            candles.append(
                R3Candle(
                    timestamp=START + timedelta(hours=4 * index),
                    open=close,
                    high=close * Decimal("1.001"),
                    low=close * Decimal("0.999"),
                    close=close,
                    volume="1000",
                )
            )
        return candles


def market_data():
    return prepare_r3_market_data(
        {
            "BETAUSDT": trend_candles(rate="0.002"),
            "ALPHAUSDT": trend_candles(rate="0.002"),
            "GAMMAUSDT": trend_candles(rate="0.001"),
        }
    )


def config_for(data, *, cost_multiplier: str = "1") -> R31ResearchReplayConfig:
    return R31ResearchReplayConfig(
        evaluation_start=data.timestamps[505],
        evaluation_end=data.timestamps[-1] + timedelta(hours=4),
        baseline_decision_symbols=list(data.symbols),
        cost_multiplier=cost_multiplier,
        universe_manifest_evidence_hash=HASH_A,
        development_dataset_bundle_evidence_hash=HASH_B,
        protocol_evidence_hash=HASH_C,
        execution_specification_evidence_hash=HASH_D,
        market_data_evidence_hash=data.market_data_evidence_hash,
    )


def test_path_quality_recovers_exponential_log_slope_and_fit() -> None:
    candles = tuple(trend_candles(rate="0.002", count=505))

    signal = calculate_path_quality_signal(candles, signal_index=504)

    assert signal.reference_at == candles[0].timestamp
    assert signal.signal_at == candles[504].timestamp
    assert signal.slope == pytest.approx(Decimal("0.002"), abs=Decimal("1E-48"))
    assert signal.r_squared == pytest.approx(Decimal("1"), abs=Decimal("1E-46"))
    assert signal.score == pytest.approx(Decimal("0.002"), abs=Decimal("1E-46"))
    assert signal.degenerate is False


def test_path_quality_rejects_constant_window_as_degenerate() -> None:
    candles = tuple(
        candle.model_copy(update={"close": Decimal("100")})
        for candle in trend_candles(rate="0", count=505)
    )

    signal = calculate_path_quality_signal(candles, signal_index=504)

    assert signal.slope == 0
    assert signal.r_squared == 0
    assert signal.score == 0
    assert signal.degenerate is True


def test_replay_ranks_ties_by_symbol_and_records_signal_evidence() -> None:
    data = market_data()

    result = run_r31_research_replay(config_for(data), data)

    first_rebalance = data.timestamps[505]
    records = [
        item for item in result.opportunities if item.rebalance_at == first_rebalance
    ]
    assert [(item.symbol, item.rank, item.reason) for item in records] == [
        ("ALPHAUSDT", 1, "ENTRY_ACCEPTED"),
        ("BETAUSDT", 2, "ENTRY_ACCEPTED"),
        ("GAMMAUSDT", 3, "ENTRY_ACCEPTED"),
    ]
    assert all(item.slope > 0 and item.r_squared > 0 for item in records)
    assert result.metrics.completed_trades == 3
    assert result.metrics.accepted_entries == 3
    assert R31ResearchReplayConfig.model_validate_json(
        result.config.model_dump_json()
    ) == result.config


def test_replay_holds_cash_when_all_windows_are_degenerate() -> None:
    flat = trend_candles(rate="0")
    data = prepare_r3_market_data(
        {"ALPHAUSDT": flat, "BETAUSDT": flat, "GAMMAUSDT": flat}
    )

    result = run_r31_research_replay(config_for(data), data)

    assert result.trades == []
    assert result.metrics.final_equity == Decimal("1000")
    assert {item.reason for item in result.opportunities} == {
        "DEGENERATE_TREND_WINDOW"
    }


def test_replay_is_hash_stable_auditable_and_context_independent() -> None:
    data = market_data()
    config = config_for(data)
    expected = run_r31_research_replay(config, data)
    original_precision = getcontext().prec
    try:
        getcontext().prec = 9
        actual = run_r31_research_replay(config, data)
    finally:
        getcontext().prec = original_precision

    assert actual == expected
    assert audit_r31_research_replay(config, data, expected).status == "PASS"
    tampered = expected.model_copy(update={"result_evidence_hash": "0" * 64})
    audit = audit_r31_research_replay(config, data, tampered)
    assert audit.status == "BLOCKED"
    assert audit.reasons == [
        "stored_result_evidence_hash_mismatch",
        "deterministic_replay_mismatch",
    ]


def test_double_cost_replays_fills_fees_and_capacity() -> None:
    data = market_data()
    base = run_r31_research_replay(config_for(data), data)
    stressed = run_r31_research_replay(
        config_for(data, cost_multiplier="2"),
        data,
    )

    assert stressed.metrics.net_pl < base.metrics.net_pl
    assert stressed.metrics.total_commission > base.metrics.total_commission
    assert stressed.metrics.total_slippage > base.metrics.total_slippage
    assert stressed.request_evidence_hash != base.request_evidence_hash


def test_config_refuses_any_unfrozen_signal_parameter() -> None:
    payload = config_for(market_data()).model_dump()
    payload["lookback_bars"] = 503

    with pytest.raises(ValidationError):
        R31ResearchReplayConfig.model_validate(payload)
