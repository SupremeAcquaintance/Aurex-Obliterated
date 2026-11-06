from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurex.broker_engine.binance_spot_testnet import (
    BinanceAccountSnapshot,
    BinanceAssetBalance,
    BinanceOrderSnapshot,
    BinanceSpotSymbolRules,
)
from aurex.broker_engine.binance_testnet_user_stream import (
    BinanceUserDataEvent,
    build_user_stream_contract,
    parse_user_data_event,
)
from aurex.broker_engine.binance_testnet_user_stream_campaign import (
    run_user_stream_campaign,
)
from scripts.check_binance_spot_testnet_user_stream import (
    campaign_client_order_ids,
)

FIRST_ID = "aurex-stream-one-1234567890ab"
FIRST_CANCEL_ID = "aurex-stream-one-x-1234567890"
SECOND_ID = "aurex-stream-two-1234567890ab"
SECOND_CANCEL_ID = "aurex-stream-two-x-1234567890"


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
                        {
                            "filterType": "PERCENT_PRICE_BY_SIDE",
                            "bidMultiplierUp": "2",
                            "bidMultiplierDown": "0.5",
                            "askMultiplierUp": "2",
                            "askMultiplierDown": "0.5",
                            "avgPriceMins": 5,
                        },
                    ],
                }
            ]
        }
    )


def account(*, usdt_free: str = "100", usdt_locked: str = "0") -> BinanceAccountSnapshot:
    balances = (
        BinanceAssetBalance(
            asset="BTC",
            free=Decimal("1"),
            locked=Decimal("0"),
        ),
        BinanceAssetBalance(
            asset="USDT",
            free=Decimal(usdt_free),
            locked=Decimal(usdt_locked),
        ),
    )
    return BinanceAccountSnapshot(
        can_trade=True,
        account_type="SPOT",
        permissions=("SPOT",),
        nonzero_assets=("BTC", "USDT"),
        maker_commission=Decimal("0"),
        taker_commission=Decimal("0"),
        balances=balances,
    )


def order(
    *,
    order_id: int,
    client_order_id: str,
    quantity: Decimal,
    price: Decimal,
    status: str,
    original_client_order_id: str | None = None,
) -> BinanceOrderSnapshot:
    return BinanceOrderSnapshot(
        symbol="BTCUSDT",
        order_id=order_id,
        client_order_id=client_order_id,
        status=status,
        side="BUY",
        order_type="LIMIT",
        price=price,
        original_quantity=quantity,
        executed_quantity=Decimal("0"),
        cumulative_quote_quantity=Decimal("0"),
        original_quote_order_quantity=Decimal("0"),
        transact_time_ms=1_000 + order_id,
        original_client_order_id=original_client_order_id,
    )


def execution_event(
    *,
    subscription_id: int,
    order_id: int,
    client_order_id: str,
    status: str,
    execution_id: int,
    quantity: Decimal,
    price: Decimal,
    original_client_order_id: str | None = None,
) -> BinanceUserDataEvent:
    return parse_user_data_event(
        {
            "subscriptionId": subscription_id,
            "event": {
                "e": "executionReport",
                "E": 10_000 + execution_id,
                "T": 9_000 + execution_id,
                "s": "BTCUSDT",
                "c": client_order_id,
                "C": original_client_order_id or "",
                "S": "BUY",
                "o": "LIMIT",
                "x": status,
                "X": status,
                "p": str(price),
                "q": str(quantity),
                "z": "0",
                "Z": "0",
                "l": "0",
                "L": "0",
                "n": "0",
                "N": None,
                "i": order_id,
                "t": -1,
                "I": execution_id,
            },
        }
    )


def final_account_event(*, subscription_id: int) -> BinanceUserDataEvent:
    return parse_user_data_event(
        {
            "subscriptionId": subscription_id,
            "event": {
                "e": "outboundAccountPosition",
                "E": 20_000,
                "u": 19_999,
                "B": [{"a": "USDT", "f": "100", "l": "0"}],
            },
        }
    )


class FakeRestClient:
    def __init__(self, *, final_usdt: str = "100") -> None:
        self.accounts = [account(), account(), account(usdt_free=final_usdt)]
        self.orders: dict[str, BinanceOrderSnapshot] = {}
        self.next_order_id = 1

    def account_snapshot(self) -> BinanceAccountSnapshot:
        return self.accounts.pop(0)

    def symbol_rules(self) -> BinanceSpotSymbolRules:
        return rules()

    def ticker_price(self) -> Decimal:
        return Decimal("100000")

    def average_price(self, *, expected_minutes: int | None = None) -> Decimal:
        assert expected_minutes == 5
        return Decimal("100000")

    def best_bid_price(self) -> Decimal:
        return Decimal("99999.99")

    def place_limit_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot:
        assert side == "BUY"
        placed = order(
            order_id=self.next_order_id,
            client_order_id=client_order_id,
            quantity=quantity,
            price=price,
            status="NEW",
        )
        self.next_order_id += 1
        self.orders[client_order_id] = placed
        return placed

    def query_order(
        self,
        *,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> BinanceOrderSnapshot:
        if client_order_id is not None:
            return self.orders[client_order_id]
        return next(item for item in self.orders.values() if item.order_id == order_id)

    def cancel_order(
        self,
        *,
        client_order_id: str,
        new_client_order_id: str | None = None,
    ) -> BinanceOrderSnapshot:
        placed = self.orders[client_order_id]
        cancelled = order(
            order_id=placed.order_id,
            client_order_id=new_client_order_id or client_order_id,
            quantity=placed.original_quantity,
            price=placed.price,
            status="CANCELED",
            original_client_order_id=client_order_id,
        )
        self.orders[client_order_id] = order(
            order_id=placed.order_id,
            client_order_id=client_order_id,
            quantity=placed.original_quantity,
            price=placed.price,
            status="CANCELED",
        )
        return cancelled

    def account_trades(self, *, order_id: int) -> tuple:
        del order_id
        return ()


class FakeStream:
    def __init__(self, *, subscription_id: int, events: list[BinanceUserDataEvent]) -> None:
        self._subscription_id: int | None = None
        self.expected_subscription_id = subscription_id
        self.events = events
        self.connected = False

    @property
    def subscription_id(self) -> int | None:
        return self._subscription_id

    def connect(self) -> None:
        self.connected = True

    def subscribe(self) -> int:
        assert self.connected
        self._subscription_id = self.expected_subscription_id
        return self.expected_subscription_id

    def next_event(self, *, timeout_seconds: float | None = None) -> BinanceUserDataEvent:
        del timeout_seconds
        if not self.events:
            raise TimeoutError
        return self.events.pop(0)

    def unsubscribe(self) -> None:
        self._subscription_id = None

    def disconnect(self) -> None:
        self.connected = False
        self._subscription_id = None


def campaign_streams() -> list[FakeStream]:
    quantity = Decimal("0.00006")
    price = Decimal("89999.99")
    return [
        FakeStream(
            subscription_id=10,
            events=[
                execution_event(
                    subscription_id=10,
                    order_id=1,
                    client_order_id=FIRST_ID,
                    status="NEW",
                    execution_id=101,
                    quantity=quantity,
                    price=price,
                )
            ],
        ),
        FakeStream(
            subscription_id=11,
            events=[
                execution_event(
                    subscription_id=11,
                    order_id=2,
                    client_order_id=SECOND_ID,
                    status="NEW",
                    execution_id=102,
                    quantity=quantity,
                    price=price,
                ),
                execution_event(
                    subscription_id=11,
                    order_id=2,
                    client_order_id=SECOND_CANCEL_ID,
                    original_client_order_id=SECOND_ID,
                    status="CANCELED",
                    execution_id=103,
                    quantity=quantity,
                    price=price,
                ),
                final_account_event(subscription_id=11),
            ],
        ),
    ]


def run_campaign(*, final_usdt: str = "100"):
    streams = campaign_streams()
    return run_user_stream_campaign(
        FakeRestClient(final_usdt=final_usdt),
        stream_factory=lambda: streams.pop(0),
        contract=build_user_stream_contract(
            frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
        ),
        first_client_order_id=FIRST_ID,
        first_cancel_client_order_id=FIRST_CANCEL_ID,
        second_client_order_id=SECOND_ID,
        second_cancel_client_order_id=SECOND_CANCEL_ID,
        monotonic=time.monotonic,
    )


def test_campaign_proves_reconnect_gap_recovery_and_event_parity() -> None:
    result = run_campaign()

    assert result.passed is True
    assert result.forced_disconnect_verified is True
    assert result.rest_gap_recovery_verified is True
    assert result.first_new_reconciliation.passed is True
    assert result.second_new_reconciliation.passed is True
    assert result.second_cancel_reconciliation.passed is True
    assert result.account_position_match_found is True
    assert result.balance_reconciliation_verified is True
    assert result.first_order.trades == ()
    assert result.second_order.trades == ()


def test_campaign_rejects_unexplained_final_balance_drift() -> None:
    result = run_campaign(final_usdt="99.99")

    assert result.passed is False
    assert result.balance_reconciliation_verified is False
    assert any("balance differs" in gate for gate in result.failed_gates)


def test_campaign_order_and_cancel_identities_are_all_distinct() -> None:
    contract = build_user_stream_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )

    identities = campaign_client_order_ids(
        contract,
        checked_at=datetime(2026, 7, 31, 12, tzinfo=UTC),
        output=Path("data/evidence/stream.json"),
    )

    assert len(identities) == 4
    assert len(set(identities.values())) == 4
