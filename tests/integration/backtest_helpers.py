from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aurex.backtest_engine.schemas import (
    AcceptanceCriteria,
    BacktestProtocolCreate,
    BacktestReportCreate,
    BacktestReportCsvRequest,
    BacktestTradeInput,
    WalkForwardWindowInput,
)
from aurex.backtest_engine.service import TREND_PULLBACK_V1_PARAMETER_TEMPLATE, BacktestLab


def accepted_backtest_payload(
    *,
    strategy: str = "trend_pullback_v1",
    symbols: list[str] | None = None,
) -> BacktestReportCreate:
    in_sample_start = datetime(2026, 1, 1, tzinfo=UTC)
    out_of_sample_start = datetime(2026, 2, 16, tzinfo=UTC)
    parameters = dict(TREND_PULLBACK_V1_PARAMETER_TEMPLATE)
    selected_symbols = symbols or ["BTCUSDT"]
    trades: list[BacktestTradeInput] = []
    for index in range(100):
        realized_pl = Decimal("2") if index < 70 else Decimal("-1")
        closed_at = (
            in_sample_start + timedelta(days=index % 45)
            if index < 50
            else out_of_sample_start + timedelta(days=(index - 50) % 44)
        )
        trades.append(
            BacktestTradeInput(
                sequence=index + 1,
                external_trade_id=str(index + 1),
                source_format="tradingview",
                strategy=strategy,
                symbol=selected_symbols[0],
                direction="LONG",
                entry_at=closed_at - timedelta(minutes=15),
                entry_price=Decimal("100"),
                exit_price=(
                    Decimal("102") if realized_pl > 0 else Decimal("99")
                ),
                quantity=Decimal("1"),
                gross_pl=realized_pl + Decimal("0.1"),
                fees=Decimal("0.1"),
                slippage=Decimal("0.02"),
                realized_pl=realized_pl,
                market_regime="TRENDING_UP",
                closed_at=closed_at,
                raw_row={"entry": {"Trade #": str(index + 1)}, "exit": {}},
            )
        )
    return BacktestReportCreate(
        strategy=strategy,
        strategy_version="1.3.0",
        symbols=selected_symbols,
        timeframe="15m",
        data_source="tradingview-export",
        source_format="tradingview",
        csv_timezone="UTC",
        source_reference=(
            f"tradingview://strategy-tester/BINANCE:{selected_symbols[0]}/15m"
        ),
        data_start=datetime(2026, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 3, 31, tzinfo=UTC),
        in_sample_start=in_sample_start,
        in_sample_end=datetime(2026, 2, 15, tzinfo=UTC),
        out_of_sample_start=out_of_sample_start,
        out_of_sample_end=datetime(2026, 3, 31, tzinfo=UTC),
        parameters=parameters,
        cost_model={"commission_percent": "0.05"},
        slippage_model={"type": "fixed_ticks", "ticks": "2"},
        risk_snapshot={"risk_per_trade": "0.005"},
        walk_forward_windows=[
            WalkForwardWindowInput(
                window_id="wf-1",
                train_start=in_sample_start,
                train_end=datetime(2026, 1, 15, tzinfo=UTC),
                test_start=datetime(2026, 1, 16, tzinfo=UTC),
                test_end=datetime(2026, 1, 25, tzinfo=UTC),
                configuration_reference="fixture://walk-forward/wf-1",
                parameters=parameters,
            ),
            WalkForwardWindowInput(
                window_id="wf-2",
                train_start=in_sample_start,
                train_end=datetime(2026, 1, 25, tzinfo=UTC),
                test_start=datetime(2026, 1, 26, tzinfo=UTC),
                test_end=datetime(2026, 2, 4, tzinfo=UTC),
                configuration_reference="fixture://walk-forward/wf-2",
                parameters=parameters,
            ),
            WalkForwardWindowInput(
                window_id="wf-3",
                train_start=in_sample_start,
                train_end=datetime(2026, 2, 4, tzinfo=UTC),
                test_start=datetime(2026, 2, 5, tzinfo=UTC),
                test_end=datetime(2026, 2, 15, tzinfo=UTC),
                configuration_reference="fixture://walk-forward/wf-3",
                parameters=parameters,
            ),
        ],
        trades=trades,
        acceptance_criteria=AcceptanceCriteria(
            min_trades=100,
            min_profit_factor=Decimal("1.15"),
            max_drawdown=Decimal("50"),
            min_out_of_sample_trades=30,
            min_out_of_sample_profit_factor=Decimal("1.15"),
            min_active_trading_days=15,
            max_single_day_trade_share=Decimal("0.25"),
        ),
    )


def seed_accepted_backtest(session: Session, **kwargs: object) -> None:
    payload = accepted_backtest_payload(**kwargs)
    protocol_payload = payload.model_dump(
        mode="json",
        exclude={"protocol_id", "source_format", "trades"},
    )
    protocol = BacktestLab(session).register_protocol(
        BacktestProtocolCreate.model_validate(protocol_payload)
    )
    payload.protocol_id = protocol.id
    request = payload.model_dump(
        mode="json",
        exclude={"source_artifact_hash", "source_format", "trades"},
    )
    request["csv_format"] = "tradingview"
    request["csv_text"] = tradingview_csv(payload)
    BacktestLab(session).create_report_from_csv(
        BacktestReportCsvRequest.model_validate(request)
    )
    session.flush()


def post_accepted_backtest(client: TestClient, **kwargs: object) -> dict:
    payload = accepted_backtest_payload(**kwargs)
    protocol_payload = payload.model_dump(
        mode="json",
        exclude={"protocol_id", "source_format", "trades"},
    )
    protocol = client.post("/backtests/protocols", json=protocol_payload)
    assert protocol.status_code == 201
    payload.protocol_id = protocol.json()["id"]
    request = payload.model_dump(
        mode="json",
        exclude={"source_format", "trades"},
    )
    request["csv_format"] = "tradingview"
    request["csv_text"] = tradingview_csv(payload)
    response = client.post("/backtests/reports/import-csv", json=request)
    assert response.status_code == 201
    body = response.json()
    assert body["result"]["acceptance_passed"] is True
    enabled = client.patch(
        f"/strategies/{payload.strategy}",
        json={"is_enabled": True},
    )
    assert enabled.status_code == 200
    return body


def tradingview_csv(payload: BacktestReportCreate) -> str:
    rows = [
        "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Net P&L USD,"
        "Commission USD,Symbol"
    ]
    for trade in payload.trades:
        trade_id = trade.external_trade_id or str(trade.sequence)
        entry_at = trade.entry_at.isoformat().replace("+00:00", "Z")
        closed_at = trade.closed_at.isoformat().replace("+00:00", "Z")
        symbol = trade.symbol or payload.symbols[0]
        rows.append(
            f"{trade_id},Entry long,AUREX-LONG-TRENDING_UP,{entry_at},"
            f"{trade.entry_price},{trade.quantity},,,{symbol}"
        )
        rows.append(
            f"{trade_id},Exit long,AUREX-LONG-EXIT,{closed_at},"
            f"{trade.exit_price},{trade.quantity},{trade.realized_pl},{trade.fees},{symbol}"
        )
    return "\n".join(rows)
