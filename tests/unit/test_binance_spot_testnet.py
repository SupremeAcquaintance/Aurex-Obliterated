from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from urllib.parse import parse_qs

import pytest

from aurex.broker_engine.binance_spot_testnet import (
    TESTNET_REST_BASE_URL,
    BinanceHttpResponse,
    BinanceSpotSymbolRules,
    BinanceSpotTestnetClient,
    BinanceSpotTestnetError,
    BinanceTestnetCredentials,
    deterministic_client_order_id,
)


def exchange_info_payload() -> dict:
    return {
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


class RecordingTransport:
    def __init__(self, responses: list[BinanceHttpResponse]) -> None:
        self.responses = responses
        self.requests: list[dict] = []

    def send(
        self,
        *,
        method: str,
        path: str,
        query: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> BinanceHttpResponse:
        self.requests.append(
            {
                "method": method,
                "path": path,
                "query": query,
                "body": body,
                "headers": dict(headers),
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.responses.pop(0)


def response(payload: object, status_code: int = 200) -> BinanceHttpResponse:
    return BinanceHttpResponse(status_code=status_code, payload=payload)


def credentials() -> BinanceTestnetCredentials:
    return BinanceTestnetCredentials(
        api_key="testnet-api-key-value",
        secret_key="testnet-secret-key-value",
    )


def test_client_is_permanently_bound_to_testnet() -> None:
    client = BinanceSpotTestnetClient(transport=RecordingTransport([]))

    assert client.base_url == TESTNET_REST_BASE_URL
    assert client.environment == "BINANCE_SPOT_TESTNET"
    assert client.virtual_order_entry_enabled is False
    assert client.virtual_fill_entry_enabled is False


def test_credentials_are_redacted_from_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUREX_BINANCE_TESTNET_API_KEY", "testnet-api-key-value")
    monkeypatch.setenv("AUREX_BINANCE_TESTNET_SECRET_KEY", "testnet-secret-key-value")

    loaded = BinanceTestnetCredentials.from_environment()

    assert "testnet-api-key-value" not in repr(loaded)
    assert "testnet-secret-key-value" not in repr(loaded)


def test_public_connectivity_and_symbol_rules() -> None:
    transport = RecordingTransport(
        [
            response({}),
            response({"serverTime": 1_000}),
            response(exchange_info_payload()),
            response({"symbol": "BTCUSDT", "price": "100000.00"}),
            response({"mins": 5, "price": "100000.00"}),
            response(
                {
                    "symbol": "BTCUSDT",
                    "bidPrice": "99999.99",
                    "bidQty": "1",
                    "askPrice": "100000.00",
                    "askQty": "1",
                }
            ),
        ]
    )
    ticks = iter([900, 900])
    client = BinanceSpotTestnetClient(
        transport=transport,
        clock_ms=lambda: next(ticks),
    )

    client.ping()

    assert client.synchronize_time() == 100
    rules = client.symbol_rules()
    assert rules.symbol == "BTCUSDT"
    assert rules.min_notional == Decimal("5")
    assert client.ticker_price() == Decimal("100000.00")
    assert client.average_price(expected_minutes=5) == Decimal("100000.00")
    assert client.best_bid_price() == Decimal("99999.99")
    assert all(request["path"].startswith("/api/") for request in transport.requests)


def test_rules_reject_misaligned_or_oversized_orders() -> None:
    rules = BinanceSpotSymbolRules.from_exchange_info(exchange_info_payload())

    with pytest.raises(BinanceSpotTestnetError, match="stepSize"):
        rules.validate_limit_order(
            side="BUY",
            quantity=Decimal("0.000101"),
            price=Decimal("50000.00"),
            percent_reference_price=Decimal("50000"),
        )
    with pytest.raises(BinanceSpotTestnetError, match="virtual-order cap"):
        rules.validate_limit_order(
            side="BUY",
            quantity=Decimal("0.00021"),
            price=Decimal("50000.00"),
            percent_reference_price=Decimal("50000"),
        )


def test_bounded_test_order_obeys_exchange_and_aurex_limits() -> None:
    rules = BinanceSpotSymbolRules.from_exchange_info(exchange_info_payload())

    quantity, price = rules.bounded_test_order(
        Decimal("100000"),
        Decimal("100000"),
        Decimal("99999.99"),
    )

    assert price == Decimal("89999.99")
    assert quantity == Decimal("0.00006")
    assert quantity * price == Decimal("5.3999994")


def test_bounded_order_stays_away_from_moving_percent_price_boundary() -> None:
    rules = BinanceSpotSymbolRules.from_exchange_info(exchange_info_payload())

    with pytest.raises(BinanceSpotTestnetError, match="PERCENT_PRICE_BY_SIDE"):
        rules.validate_limit_order(
            side="BUY",
            quantity=Decimal("0.00010"),
            price=Decimal("50000.00"),
            percent_reference_price=Decimal("100100"),
        )

    quantity, price = rules.bounded_test_order(
        Decimal("100000"),
        Decimal("100100"),
        Decimal("99999.99"),
    )

    assert price == Decimal("89999.99")
    assert quantity == Decimal("0.00006")
    rules.validate_limit_order(
        side="BUY",
        quantity=quantity,
        price=price,
        percent_reference_price=Decimal("100100"),
    )


def test_signed_account_read_is_sanitized_and_signature_is_not_in_body() -> None:
    transport = RecordingTransport(
        [
            response({"serverTime": 1_000}),
            response(
                {
                    "canTrade": True,
                    "accountType": "SPOT",
                    "permissions": ["SPOT"],
                    "uid": 999,
                    "commissionRates": {"maker": "0.001", "taker": "0.001"},
                    "balances": [
                        {"asset": "BTC", "free": "1", "locked": "0"},
                        {"asset": "USDT", "free": "0", "locked": "0"},
                    ],
                }
            ),
        ]
    )
    ticks = iter([900, 900, 900])
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=transport,
        clock_ms=lambda: next(ticks),
    )

    account = client.account_snapshot()

    assert account.can_trade is True
    assert account.permissions == ("SPOT",)
    assert account.nonzero_assets == ("BTC",)
    assert not hasattr(account, "uid")
    signed = transport.requests[1]
    query = parse_qs(signed["query"])
    assert query["timestamp"] == ["1000"]
    assert query["recvWindow"] == ["5000"]
    assert len(query["signature"][0]) == 64
    assert signed["body"] is None
    assert signed["headers"]["X-MBX-APIKEY"] == "testnet-api-key-value"


def test_test_order_uses_signed_form_body_and_never_enters_matching_engine() -> None:
    transport = RecordingTransport(
        [
            response(exchange_info_payload()),
            response({"mins": 5, "price": "100000.00"}),
            response({"serverTime": 1_000}),
            response({}),
        ]
    )
    ticks = iter([900, 900, 900])
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=transport,
        clock_ms=lambda: next(ticks),
    )
    client_order_id = deterministic_client_order_id("validation", "evidence")

    client.test_limit_order(
        side="BUY",
        quantity=Decimal("0.00010"),
        price=Decimal("50000.00"),
        client_order_id=client_order_id,
    )

    request = transport.requests[-1]
    assert request["path"] == "/api/v3/order/test"
    assert request["query"] == ""
    body = parse_qs(request["body"].decode("ascii"))
    assert body["symbol"] == ["BTCUSDT"]
    assert body["newClientOrderId"] == [client_order_id]
    assert len(body["signature"][0]) == 64


def test_virtual_order_entry_fails_closed_by_default() -> None:
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=RecordingTransport([]),
    )

    with pytest.raises(BinanceSpotTestnetError, match="disabled"):
        client.place_limit_order(
            side="BUY",
            quantity=Decimal("0.00010"),
            price=Decimal("50000.00"),
            client_order_id=deterministic_client_order_id("cancel", "evidence"),
        )


def test_market_fill_entry_is_separately_disabled_by_default() -> None:
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=RecordingTransport([]),
    )

    with pytest.raises(BinanceSpotTestnetError, match="fill entry is disabled"):
        client.place_market_buy(
            quote_order_quantity=Decimal("6.50"),
            client_order_id=deterministic_client_order_id("fill-buy", "evidence"),
        )


def test_enabled_market_buy_uses_bounded_quote_quantity() -> None:
    client_order_id = deterministic_client_order_id("fill-buy", "evidence")
    transport = RecordingTransport(
        [
            response(exchange_info_payload()),
            response({"serverTime": 1_000}),
            response(
                {
                    "symbol": "BTCUSDT",
                    "orderId": 43,
                    "clientOrderId": client_order_id,
                    "price": "0",
                    "origQty": "0.00010",
                    "executedQty": "0.00010",
                    "origQuoteOrderQty": "6.50",
                    "cummulativeQuoteQty": "6.49",
                    "status": "FILLED",
                    "type": "MARKET",
                    "side": "BUY",
                    "transactTime": 1_000,
                }
            ),
        ]
    )
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=transport,
        clock_ms=lambda: 900,
        virtual_fill_entry_enabled=True,
    )

    placed = client.place_market_buy(
        quote_order_quantity=Decimal("6.50"),
        client_order_id=client_order_id,
    )

    assert placed.status == "FILLED"
    assert placed.original_quote_order_quantity == Decimal("6.50")
    body = parse_qs(transport.requests[-1]["body"].decode("ascii"))
    assert body["type"] == ["MARKET"]
    assert body["side"] == ["BUY"]
    assert body["quoteOrderQty"] == ["6.50"]
    assert "quantity" not in body


def test_account_trades_are_sanitized_and_bound_to_order() -> None:
    transport = RecordingTransport(
        [
            response({"serverTime": 1_000}),
            response(
                [
                    {
                        "symbol": "BTCUSDT",
                        "id": 7,
                        "orderId": 43,
                        "price": "64900",
                        "qty": "0.00010",
                        "quoteQty": "6.49",
                        "commission": "0.000001",
                        "commissionAsset": "BTC",
                        "time": 1_001,
                        "isBuyer": True,
                        "isMaker": False,
                        "isBestMatch": True,
                    }
                ]
            ),
        ]
    )
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=transport,
        clock_ms=lambda: 900,
    )

    trades = client.account_trades(order_id=43)

    assert len(trades) == 1
    assert trades[0].commission == Decimal("0.000001")
    assert trades[0].commission_asset == "BTC"
    query = parse_qs(transport.requests[-1]["query"])
    assert query["orderId"] == ["43"]
    assert query["limit"] == ["1000"]


def test_open_orders_are_sanitized_and_bound_to_btcusdt() -> None:
    client_order_id = deterministic_client_order_id("restart", "evidence")
    transport = RecordingTransport(
        [
            response({"serverTime": 1_000}),
            response(
                [
                    {
                        "symbol": "BTCUSDT",
                        "orderId": 44,
                        "clientOrderId": client_order_id,
                        "price": "50000.00",
                        "origQty": "0.00010",
                        "executedQty": "0",
                        "cummulativeQuoteQty": "0",
                        "status": "NEW",
                        "timeInForce": "GTC",
                        "type": "LIMIT",
                        "side": "BUY",
                        "time": 1_000,
                    }
                ]
            ),
        ]
    )
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=transport,
        clock_ms=lambda: 900,
    )

    orders = client.open_orders()

    assert len(orders) == 1
    assert orders[0].order_id == 44
    assert orders[0].client_order_id == client_order_id
    request = transport.requests[-1]
    assert request["path"] == "/api/v3/openOrders"
    query = parse_qs(request["query"])
    assert query["symbol"] == ["BTCUSDT"]


def test_enabled_virtual_order_can_be_placed_queried_and_cancelled() -> None:
    client_order_id = deterministic_client_order_id("cancel", "lifecycle-evidence")

    cancel_client_order_id = deterministic_client_order_id("cancel-op", "lifecycle-evidence")

    def order_payload(
        status: str,
        *,
        client_id: str = client_order_id,
        original_client_id: str | None = None,
    ) -> dict:
        payload = {
            "symbol": "BTCUSDT",
            "orderId": 42,
            "clientOrderId": client_id,
            "price": "50000.00",
            "origQty": "0.00010",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "status": status,
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
            "transactTime": 1_000,
        }
        if original_client_id is not None:
            payload["origClientOrderId"] = original_client_id
        return payload

    transport = RecordingTransport(
        [
            response(exchange_info_payload()),
            response({"mins": 5, "price": "100000.00"}),
            response(
                {
                    "symbol": "BTCUSDT",
                    "bidPrice": "99999.99",
                    "bidQty": "1",
                    "askPrice": "100000.00",
                    "askQty": "1",
                }
            ),
            response({"serverTime": 1_000}),
            response(order_payload("NEW")),
            response(order_payload("NEW")),
            response(
                order_payload(
                    "CANCELED",
                    client_id=cancel_client_order_id,
                    original_client_id=client_order_id,
                )
            ),
            response(order_payload("CANCELED", client_id=client_order_id)),
        ]
    )
    client = BinanceSpotTestnetClient(
        credentials=credentials(),
        transport=transport,
        clock_ms=lambda: 900,
        virtual_order_entry_enabled=True,
    )

    placed = client.place_limit_order(
        side="BUY",
        quantity=Decimal("0.00010"),
        price=Decimal("50000.00"),
        client_order_id=client_order_id,
    )
    queried = client.query_order(client_order_id=client_order_id)
    cancelled = client.cancel_order(
        client_order_id=client_order_id,
        new_client_order_id=cancel_client_order_id,
    )
    final = client.query_order(order_id=cancelled.order_id)

    assert placed.status == "NEW"
    assert queried.order_id == placed.order_id
    assert cancelled.status == "CANCELED"
    assert cancelled.original_client_order_id == client_order_id
    assert cancelled.client_order_id == cancel_client_order_id
    assert final.status == "CANCELED"
    assert final.client_order_id == client_order_id
    assert final.executed_quantity == 0
    final_query = parse_qs(transport.requests[-1]["query"])
    assert final_query["orderId"] == ["42"]
    assert "origClientOrderId" not in final_query
    assert [request["path"] for request in transport.requests] == [
        "/api/v3/exchangeInfo",
        "/api/v3/avgPrice",
        "/api/v3/ticker/bookTicker",
        "/api/v3/time",
        "/api/v3/order",
        "/api/v3/order",
        "/api/v3/order",
        "/api/v3/order",
    ]


def test_safe_error_does_not_include_credentials_or_signature() -> None:
    transport = RecordingTransport(
        [
            response(
                {"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."},
                status_code=401,
            )
        ]
    )
    client = BinanceSpotTestnetClient(transport=transport)

    with pytest.raises(BinanceSpotTestnetError) as captured:
        client.ping()

    rendered = str(captured.value)
    assert "Invalid API-key" in rendered
    assert "testnet-api-key-value" not in rendered
    assert "signature" not in rendered


def test_client_order_id_is_stable_and_bounded() -> None:
    first = deterministic_client_order_id("validation", "same-evidence")
    second = deterministic_client_order_id("validation", "same-evidence")

    assert first == second
    assert first.startswith("aurex-validation-")
    assert len(first) <= 35
