from __future__ import annotations

from decimal import Decimal

import pytest

from aurex.broker_engine.binance_spot_testnet import (
    BinanceAccountSnapshot,
    BinanceAssetBalance,
    BinanceOrderSnapshot,
    BinanceSpotSymbolRules,
    BinanceSpotTestnetError,
    BinanceTradeSnapshot,
)
from aurex.broker_engine.binance_testnet_fill_campaign import (
    build_fill_fee_contract,
    expected_balance_deltas,
    reconcile_balances,
    reconcile_order_trades,
    run_bounded_fill_campaign,
)


def rules() -> BinanceSpotSymbolRules:
    return BinanceSpotSymbolRules.from_exchange_info(
        {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                    "quoteOrderQtyMarketAllowed": True,
                    "permissions": ["SPOT"],
                    "orderTypes": ["LIMIT", "MARKET"],
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.01",
                            "maxPrice": "1000000",
                            "tickSize": "0.01",
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.00001",
                            "maxQty": "100",
                            "stepSize": "0.00001",
                        },
                        {
                            "filterType": "MARKET_LOT_SIZE",
                            "minQty": "0.00001",
                            "maxQty": "100",
                            "stepSize": "0.00001",
                        },
                        {
                            "filterType": "NOTIONAL",
                            "minNotional": "5",
                            "maxNotional": "1000000",
                            "applyMinToMarket": True,
                            "applyMaxToMarket": False,
                        },
                    ],
                }
            ]
        }
    )


def account(*, btc: str, usdt: str) -> BinanceAccountSnapshot:
    balances = (
        BinanceAssetBalance(asset="BTC", free=Decimal(btc), locked=Decimal("0")),
        BinanceAssetBalance(asset="USDT", free=Decimal(usdt), locked=Decimal("0")),
    )
    return BinanceAccountSnapshot(
        can_trade=True,
        account_type="SPOT",
        permissions=("SPOT",),
        nonzero_assets=tuple(balance.asset for balance in balances if balance.total),
        maker_commission=Decimal("0"),
        taker_commission=Decimal("0"),
        balances=balances,
    )


def order(
    *,
    order_id: int,
    client_order_id: str,
    side: str,
    quantity: str,
    quote_quantity: str,
    status: str = "FILLED",
) -> BinanceOrderSnapshot:
    return BinanceOrderSnapshot(
        symbol="BTCUSDT",
        order_id=order_id,
        client_order_id=client_order_id,
        status=status,
        side=side,
        order_type="MARKET",
        price=Decimal("0"),
        original_quantity=Decimal(quantity),
        executed_quantity=Decimal(quantity),
        cumulative_quote_quantity=Decimal(quote_quantity),
        original_quote_order_quantity=(
            Decimal("6.50") if side == "BUY" else Decimal("0")
        ),
        transact_time_ms=1_000,
        original_client_order_id=None,
    )


def trade(
    *,
    trade_id: int,
    order_id: int,
    side: str,
    quantity: str,
    quote_quantity: str,
    commission: str = "0",
    commission_asset: str = "USDT",
) -> BinanceTradeSnapshot:
    return BinanceTradeSnapshot(
        symbol="BTCUSDT",
        trade_id=trade_id,
        order_id=order_id,
        price=Decimal(quote_quantity) / Decimal(quantity),
        quantity=Decimal(quantity),
        quote_quantity=Decimal(quote_quantity),
        commission=Decimal(commission),
        commission_asset=commission_asset,
        time_ms=1_000 + trade_id,
        is_buyer=side == "BUY",
        is_maker=False,
        is_best_match=True,
    )


class SuccessfulClient:
    def __init__(self, *, final_usdt: str = "99.95") -> None:
        self.accounts = [
            account(btc="1.0", usdt="100"),
            account(btc="1.000009", usdt=final_usdt),
        ]
        self.buy_id = "aurex-fill-buy-1234567890abcdef"
        self.sell_id = "aurex-fill-sell-1234567890abcdef"
        self.buy = order(
            order_id=1,
            client_order_id=self.buy_id,
            side="BUY",
            quantity="0.00010",
            quote_quantity="6.50",
        )
        self.sell = order(
            order_id=2,
            client_order_id=self.sell_id,
            side="SELL",
            quantity="0.00009",
            quote_quantity="6.45",
        )
        self.trades = {
            1: (
                trade(
                    trade_id=11,
                    order_id=1,
                    side="BUY",
                    quantity="0.00010",
                    quote_quantity="6.50",
                    commission="0.000001",
                    commission_asset="BTC",
                ),
            ),
            2: (
                trade(
                    trade_id=12,
                    order_id=2,
                    side="SELL",
                    quantity="0.00009",
                    quote_quantity="6.45",
                ),
            ),
        }
        self.buy_submissions = 0
        self.sell_submissions = 0

    def account_snapshot(self) -> BinanceAccountSnapshot:
        return self.accounts.pop(0)

    def symbol_rules(self) -> BinanceSpotSymbolRules:
        return rules()

    def test_market_buy(self, **_: object) -> None:
        return None

    def place_market_buy(self, **_: object) -> BinanceOrderSnapshot:
        self.buy_submissions += 1
        return self.buy

    def test_market_sell(self, **_: object) -> None:
        return None

    def place_market_sell(self, **_: object) -> BinanceOrderSnapshot:
        self.sell_submissions += 1
        return self.sell

    def query_order(self, **_: object) -> BinanceOrderSnapshot:
        raise AssertionError("terminal orders do not require polling")

    def account_trades(self, *, order_id: int) -> tuple[BinanceTradeSnapshot, ...]:
        return self.trades[order_id]


def contract():
    from datetime import UTC, datetime

    return build_fill_fee_contract(frozen_at=datetime(2026, 7, 31, tzinfo=UTC))


def test_order_and_balance_reconciliation_include_actual_commission_asset() -> None:
    buy = order(
        order_id=1,
        client_order_id="aurex-fill-buy-1234567890abcdef",
        side="BUY",
        quantity="0.00010",
        quote_quantity="6.50",
    )
    buy_trades = (
        trade(
            trade_id=11,
            order_id=1,
            side="BUY",
            quantity="0.00010",
            quote_quantity="6.50",
            commission="0.000001",
            commission_asset="BTC",
        ),
    )

    reconciliation = reconcile_order_trades(
        order=buy,
        trades=buy_trades,
        expected_side="BUY",
        expected_client_order_id=buy.client_order_id,
    )
    deltas = expected_balance_deltas(buy_trades=buy_trades, sell_trades=())
    balances = reconcile_balances(
        initial=account(btc="1", usdt="100"),
        final=account(btc="1.000099", usdt="93.50"),
        expected_deltas=deltas,
    )

    assert reconciliation.passed is True
    assert reconciliation.commission_by_asset == {"BTC": Decimal("0.000001")}
    assert deltas == {"BTC": Decimal("0.000099"), "USDT": Decimal("-6.50")}
    assert balances.passed is True


def test_bounded_campaign_reconciles_round_trip_and_dust() -> None:
    client = SuccessfulClient()

    result = run_bounded_fill_campaign(
        client,
        buy_client_order_id=client.buy_id,
        sell_client_order_id=client.sell_id,
        cleanup_client_order_id="aurex-cleanup-1234567890abcdef",
        contract=contract(),
        sleep=lambda _: None,
        monotonic=lambda: 0,
    )

    assert result.passed is True
    assert result.failed_gates == ()
    assert result.expected_base_residual == Decimal("0.000009")
    assert result.round_trip_quote_delta == Decimal("-0.05")
    assert client.buy_submissions == 1
    assert client.sell_submissions == 1


def test_unexplained_balance_delta_fails_campaign() -> None:
    client = SuccessfulClient(final_usdt="100")

    result = run_bounded_fill_campaign(
        client,
        buy_client_order_id=client.buy_id,
        sell_client_order_id=client.sell_id,
        cleanup_client_order_id="aurex-cleanup-1234567890abcdef",
        contract=contract(),
        sleep=lambda _: None,
        monotonic=lambda: 0,
    )

    assert result.passed is False
    assert "balance_reconciliation" in result.failed_gates


class PartialSellClient(SuccessfulClient):
    def __init__(self) -> None:
        super().__init__()
        self.cleanup_id = "aurex-cleanup-1234567890abcdef"
        self.sell = BinanceOrderSnapshot(
            symbol="BTCUSDT",
            order_id=2,
            client_order_id=self.sell_id,
            status="CANCELED",
            side="SELL",
            order_type="MARKET",
            price=Decimal("0"),
            original_quantity=Decimal("0.00009"),
            executed_quantity=Decimal("0.00001"),
            cumulative_quote_quantity=Decimal("0.65"),
            original_quote_order_quantity=Decimal("0"),
            transact_time_ms=1_000,
            original_client_order_id=None,
        )
        self.cleanup = order(
            order_id=3,
            client_order_id=self.cleanup_id,
            side="SELL",
            quantity="0.00008",
            quote_quantity="5.80",
        )
        self.trades[2] = (
            trade(
                trade_id=12,
                order_id=2,
                side="SELL",
                quantity="0.00001",
                quote_quantity="0.65",
            ),
        )
        self.trades[3] = (
            trade(
                trade_id=13,
                order_id=3,
                side="SELL",
                quantity="0.00008",
                quote_quantity="5.80",
            ),
        )

    def place_market_sell(self, **_: object) -> BinanceOrderSnapshot:
        self.sell_submissions += 1
        return self.sell if self.sell_submissions == 1 else self.cleanup


def test_partial_sell_uses_one_cleanup_and_still_fails_qualification() -> None:
    client = PartialSellClient()

    result = run_bounded_fill_campaign(
        client,
        buy_client_order_id=client.buy_id,
        sell_client_order_id=client.sell_id,
        cleanup_client_order_id=client.cleanup_id,
        contract=contract(),
        sleep=lambda _: None,
        monotonic=lambda: 0,
    )

    assert result.balance_reconciliation.passed is True
    assert result.cleanup_order_used is True
    assert client.sell_submissions == 2
    assert result.passed is False
    assert "cleanup_used" in result.failed_gates


class BelowMinimumCleanupClient(PartialSellClient):
    def __init__(self) -> None:
        super().__init__()
        self.accounts = [
            account(btc="1.0", usdt="100"),
            account(btc="1.000059", usdt="96.38"),
        ]
        self.sell = BinanceOrderSnapshot(
            symbol="BTCUSDT",
            order_id=2,
            client_order_id=self.sell_id,
            status="CANCELED",
            side="SELL",
            order_type="MARKET",
            price=Decimal("0"),
            original_quantity=Decimal("0.00009"),
            executed_quantity=Decimal("0.00004"),
            cumulative_quote_quantity=Decimal("2.88"),
            original_quote_order_quantity=Decimal("0"),
            transact_time_ms=1_000,
            original_client_order_id=None,
        )
        self.trades[2] = (
            trade(
                trade_id=12,
                order_id=2,
                side="SELL",
                quantity="0.00004",
                quote_quantity="2.88",
            ),
        )


def test_below_minimum_cleanup_is_recorded_instead_of_forced() -> None:
    client = BelowMinimumCleanupClient()

    result = run_bounded_fill_campaign(
        client,
        buy_client_order_id=client.buy_id,
        sell_client_order_id=client.sell_id,
        cleanup_client_order_id=client.cleanup_id,
        contract=contract(),
        sleep=lambda _: None,
        monotonic=lambda: 0,
    )

    assert result.balance_reconciliation.passed is True
    assert result.cleanup_order_used is False
    assert result.cleanup_blocker is not None
    assert "below the BTCUSDT minimum" in result.cleanup_blocker
    assert client.sell_submissions == 1
    assert "cleanup_incomplete" in result.failed_gates


class AmbiguousBuyClient(SuccessfulClient):
    def place_market_buy(self, **_: object) -> BinanceOrderSnapshot:
        self.buy_submissions += 1
        raise BinanceSpotTestnetError("gateway timeout", status_code=504)

    def query_order(self, **kwargs: object) -> BinanceOrderSnapshot:
        if kwargs.get("client_order_id") == self.buy_id:
            return self.buy
        raise AssertionError("unexpected order query")


def test_ambiguous_submit_is_queried_once_without_resubmission() -> None:
    client = AmbiguousBuyClient()

    result = run_bounded_fill_campaign(
        client,
        buy_client_order_id=client.buy_id,
        sell_client_order_id=client.sell_id,
        cleanup_client_order_id="aurex-cleanup-1234567890abcdef",
        contract=contract(),
        sleep=lambda _: None,
        monotonic=lambda: 0,
    )

    assert result.passed is True
    assert client.buy_submissions == 1


class UnresolvedBuyClient(AmbiguousBuyClient):
    def query_order(self, **_: object) -> BinanceOrderSnapshot:
        raise BinanceSpotTestnetError("order query unavailable", status_code=503)


def test_unresolved_submit_blocks_resubmission_and_cleanup() -> None:
    client = UnresolvedBuyClient()

    with pytest.raises(BinanceSpotTestnetError, match="remains ambiguous"):
        run_bounded_fill_campaign(
            client,
            buy_client_order_id=client.buy_id,
            sell_client_order_id=client.sell_id,
            cleanup_client_order_id="aurex-cleanup-1234567890abcdef",
            contract=contract(),
            sleep=lambda _: None,
            monotonic=lambda: 0,
        )

    assert client.buy_submissions == 1
    assert client.sell_submissions == 0
