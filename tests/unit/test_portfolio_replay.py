from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.portfolio_replay import (
    PortfolioLongSpotOpportunity,
    PortfolioPriceMark,
    PortfolioReplayConfig,
    PortfolioReplayRequest,
    audit_shared_capital_spot_portfolio,
    run_shared_capital_spot_portfolio,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


def config(**overrides: object) -> PortfolioReplayConfig:
    values: dict[str, object] = {
        "initial_capital": "1000",
        "commission_percent": "0",
        "slippage_ticks": 0,
        "risk_per_trade_percent": "50",
        "max_gross_exposure_percent": "100",
        "max_symbol_exposure_percent": "60",
        "max_open_positions": 2,
    }
    values.update(overrides)
    return PortfolioReplayConfig(**values)


def opportunity(
    opportunity_id: str,
    symbol: str,
    *,
    entry_at: datetime = START,
    exit_at: datetime | None = None,
    entry_price: str = "100",
    exit_price: str = "110",
    stop_loss: str = "90",
    minimum_contract: str = "1",
    tick_size: str = "0.01",
    priority: str = "0",
) -> PortfolioLongSpotOpportunity:
    return PortfolioLongSpotOpportunity(
        opportunity_id=opportunity_id,
        symbol=symbol,
        signal_at=entry_at,
        entry_at=entry_at,
        exit_at=exit_at or entry_at + timedelta(days=1),
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop_loss,
        tick_size=tick_size,
        point_value="1",
        minimum_contract=minimum_contract,
        priority=priority,
        exit_reason="CHANNEL_EXIT",
        market_regime="TRENDING_UP",
    )


def aligned_marks(
    opportunities: list[PortfolioLongSpotOpportunity],
    prices: dict[tuple[str, datetime], str] | None = None,
) -> list[PortfolioPriceMark]:
    prices = prices or {}
    times = sorted(
        {timestamp for item in opportunities for timestamp in (item.entry_at, item.exit_at)}
    )
    marks: list[PortfolioPriceMark] = []
    seen: set[tuple[str, datetime]] = set()
    for timestamp in times:
        for item in opportunities:
            if item.entry_at <= timestamp <= item.exit_at:
                key = (item.symbol, timestamp)
                if key in seen:
                    continue
                seen.add(key)
                default = item.entry_price if timestamp == item.entry_at else item.exit_price
                marks.append(
                    PortfolioPriceMark(
                        symbol=item.symbol,
                        timestamp=timestamp,
                        price=prices.get((item.symbol, timestamp), str(default)),
                    )
                )
    return marks


def request_for(
    opportunities: list[PortfolioLongSpotOpportunity],
    *,
    replay_config: PortfolioReplayConfig | None = None,
    marks: list[PortfolioPriceMark] | None = None,
) -> PortfolioReplayRequest:
    return PortfolioReplayRequest(
        config=replay_config or config(),
        opportunities=opportunities,
        marks=marks or aligned_marks(opportunities),
        source_evidence_hashes={"fixture": "a" * 64},
    )


def test_concurrent_entries_share_capital_proportionally() -> None:
    opportunities = [
        opportunity("eth-1", "ETHUSDT"),
        opportunity("sol-1", "SOLUSDT"),
    ]

    result = run_shared_capital_spot_portfolio(request_for(opportunities))

    assert [trade.quantity for trade in result.trades] == [Decimal("5"), Decimal("5")]
    assert result.final_equity == Decimal("1100")
    assert result.total_net_pl == Decimal("100")
    assert result.max_drawdown == Decimal("0")
    assert result.rejections == []


def test_replay_is_independent_of_input_order_and_hash_stable() -> None:
    eth = opportunity("eth-1", "ETHUSDT")
    sol = opportunity("sol-1", "SOLUSDT")
    forward = request_for([eth, sol])
    reverse = PortfolioReplayRequest(
        config=forward.config,
        opportunities=[sol, eth],
        marks=list(reversed(forward.marks)),
        source_evidence_hashes=forward.source_evidence_hashes,
    )

    first = run_shared_capital_spot_portfolio(forward)
    second = run_shared_capital_spot_portfolio(reverse)

    assert first.request_evidence_hash == second.request_evidence_hash
    assert first.result_evidence_hash == second.result_evidence_hash
    assert first.model_dump() == second.model_dump()
    assert audit_shared_capital_spot_portfolio(forward, first).status == "PASS"


def test_audit_blocks_tampered_portfolio_result() -> None:
    replay_request = request_for([opportunity("eth-1", "ETHUSDT")])
    result = run_shared_capital_spot_portfolio(replay_request)
    tampered = result.model_copy(update={"final_equity": Decimal("9999")})

    audit = audit_shared_capital_spot_portfolio(replay_request, tampered)

    assert audit.status == "BLOCKED"
    assert audit.request_evidence_hash_matches is True
    assert audit.stored_result_evidence_hash_matches is False
    assert audit.deterministic_replay_matches is False
    assert audit.reasons == [
        "stored_result_evidence_hash_mismatch",
        "deterministic_replay_mismatch",
    ]


def test_exit_is_processed_before_same_timestamp_entry() -> None:
    midpoint = START + timedelta(days=1)
    first = opportunity("eth-1", "ETHUSDT", exit_at=midpoint)
    second = opportunity(
        "sol-1",
        "SOLUSDT",
        entry_at=midpoint,
        exit_at=midpoint + timedelta(days=1),
    )
    replay_config = config(max_open_positions=1)

    result = run_shared_capital_spot_portfolio(
        request_for([first, second], replay_config=replay_config)
    )

    assert [trade.opportunity_id for trade in result.trades] == ["eth-1", "sol-1"]
    assert result.rejections == []
    midpoint_snapshot = next(
        snapshot for snapshot in result.equity_curve if snapshot.timestamp == midpoint
    )
    assert midpoint_snapshot.open_positions == 1


def test_priority_controls_capacity_without_input_order_bias() -> None:
    low = opportunity("eth-low", "ETHUSDT", priority="1")
    high = opportunity("sol-high", "SOLUSDT", priority="2")
    replay_config = config(max_open_positions=1)

    result = run_shared_capital_spot_portfolio(
        request_for([low, high], replay_config=replay_config)
    )

    assert [trade.opportunity_id for trade in result.trades] == ["sol-high"]
    assert result.rejections[0].opportunity_id == "eth-low"
    assert result.rejections[0].reason == "max_open_positions_priority_rejection"


def test_same_timestamp_symbol_collision_keeps_only_highest_priority() -> None:
    low = opportunity("eth-low", "ETHUSDT", priority="1")
    high = opportunity("eth-high", "ETHUSDT", priority="2")

    result = run_shared_capital_spot_portfolio(request_for([low, high]))

    assert [trade.opportunity_id for trade in result.trades] == ["eth-high"]
    assert result.rejections[0].opportunity_id == "eth-low"
    assert result.rejections[0].reason == "duplicate_symbol_entry_batch"


def test_mark_to_market_drawdown_captures_overlapping_open_risk() -> None:
    end = START + timedelta(days=2)
    midpoint = START + timedelta(days=1)
    eth = opportunity("eth-1", "ETHUSDT", exit_at=end, exit_price="110")
    sol = opportunity("sol-1", "SOLUSDT", exit_at=end, exit_price="110")
    marks = aligned_marks([eth, sol])
    marks.extend(
        [
            PortfolioPriceMark(symbol="ETHUSDT", timestamp=midpoint, price="80"),
            PortfolioPriceMark(symbol="SOLUSDT", timestamp=midpoint, price="80"),
        ]
    )

    result = run_shared_capital_spot_portfolio(
        request_for([eth, sol], marks=marks)
    )

    assert result.max_drawdown == Decimal("200")
    drawdown_snapshot = next(
        snapshot for snapshot in result.equity_curve if snapshot.timestamp == midpoint
    )
    assert drawdown_snapshot.equity == Decimal("800")
    assert drawdown_snapshot.open_positions == 2


def test_rejected_same_symbol_exit_cannot_remove_the_owned_position() -> None:
    first_exit = START + timedelta(days=2)
    rejected_entry = START + timedelta(hours=6)
    rejected_exit = START + timedelta(hours=12)
    owner = opportunity("eth-owner", "ETHUSDT", exit_at=first_exit)
    overlap = opportunity(
        "eth-overlap",
        "ETHUSDT",
        entry_at=rejected_entry,
        exit_at=rejected_exit,
    )

    result = run_shared_capital_spot_portfolio(request_for([owner, overlap]))

    assert [trade.opportunity_id for trade in result.trades] == ["eth-owner"]
    assert result.rejections[0].opportunity_id == "eth-overlap"
    assert result.rejections[0].reason == "symbol_position_already_open"


def test_costs_slippage_and_rounding_reconcile_to_final_cash() -> None:
    item = opportunity(
        "eth-1",
        "ETHUSDT",
        entry_price="100",
        exit_price="110",
        stop_loss="90",
        minimum_contract="0.1",
        tick_size="1",
    )
    replay_config = config(
        commission_percent="0.05",
        slippage_ticks=1,
        risk_per_trade_percent="1",
        max_symbol_exposure_percent="100",
    )

    result = run_shared_capital_spot_portfolio(
        request_for([item], replay_config=replay_config)
    )
    trade = result.trades[0]

    assert trade.entry_fill_price == Decimal("101")
    assert trade.exit_fill_price == Decimal("109")
    assert trade.quantity == Decimal("0.9")
    assert trade.slippage == Decimal("1.8")
    assert result.final_equity == replay_config.initial_capital + trade.realized_pl
    assert result.total_net_pl == trade.realized_pl


def test_rounding_to_zero_records_rejection_without_spending_cash() -> None:
    item = opportunity(
        "eth-1",
        "ETHUSDT",
        entry_price="100",
        stop_loss="1",
        minimum_contract="1",
    )
    replay_config = config(risk_per_trade_percent="0.01")

    result = run_shared_capital_spot_portfolio(
        request_for([item], replay_config=replay_config)
    )

    assert result.trades == []
    assert result.final_equity == Decimal("1000")
    assert result.rejections[0].reason == "shared_capital_or_rounding_rejection"


def test_missing_aligned_mark_is_rejected_before_replay() -> None:
    end = START + timedelta(days=2)
    midpoint = START + timedelta(days=1)
    eth = opportunity("eth-1", "ETHUSDT", exit_at=end)
    sol = opportunity("sol-1", "SOLUSDT", exit_at=end)
    marks = aligned_marks([eth, sol])
    marks.append(PortfolioPriceMark(symbol="ETHUSDT", timestamp=midpoint, price="90"))

    with pytest.raises(ValidationError, match="Aligned portfolio marks"):
        request_for([eth, sol], marks=marks)
