from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TESTNET_REST_BASE_URL = "https://testnet.binance.vision"
TESTNET_SYMBOL = "BTCUSDT"
DEFAULT_RECV_WINDOW_MS = 5_000
DEFAULT_MAX_VIRTUAL_NOTIONAL = Decimal("10")
_CLIENT_ORDER_ID = re.compile(r"^aurex-[a-z0-9-]{1,29}$")


class BinanceSpotTestnetError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True)
class BinanceTestnetCredentials:
    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)

    def __post_init__(self) -> None:
        for name, value in (("API key", self.api_key), ("secret key", self.secret_key)):
            if not value or value != value.strip():
                raise ValueError(f"Binance Testnet {name} is missing or malformed")
            if len(value) < 16:
                raise ValueError(f"Binance Testnet {name} is unexpectedly short")

    @classmethod
    def from_environment(cls) -> BinanceTestnetCredentials:
        api_key = os.environ.get("AUREX_BINANCE_TESTNET_API_KEY", "")
        secret_key = os.environ.get("AUREX_BINANCE_TESTNET_SECRET_KEY", "")
        if not api_key or not secret_key:
            raise BinanceSpotTestnetError(
                "Binance Spot Testnet credentials are not present in the process environment"
            )
        return cls(api_key=api_key, secret_key=secret_key)


@dataclass(frozen=True)
class BinanceHttpResponse:
    status_code: int
    payload: object
    headers: Mapping[str, str] = field(default_factory=dict)


class BinanceHttpTransport(Protocol):
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
        """Send one request to the fixed Binance Spot Testnet origin."""


class UrllibBinanceTestnetTransport:
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
        if not path.startswith("/api/"):
            raise BinanceSpotTestnetError("Only Binance Spot /api routes are allowed")
        url = f"{TESTNET_REST_BASE_URL}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, data=body, headers=dict(headers), method=method)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                raw_body = response.read()
                return BinanceHttpResponse(
                    status_code=response.status,
                    payload=_decode_json(raw_body),
                    headers=dict(response.headers.items()),
                )
        except HTTPError as exc:
            raw_body = exc.read()
            return BinanceHttpResponse(
                status_code=exc.code,
                payload=_decode_json(raw_body),
                headers=dict(exc.headers.items()) if exc.headers else {},
            )
        except (TimeoutError, URLError, OSError) as exc:
            raise BinanceSpotTestnetError(
                "Binance Spot Testnet request failed before a valid response was received"
            ) from exc


@dataclass(frozen=True)
class BinanceSpotSymbolRules:
    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    tick_size: Decimal
    min_price: Decimal
    max_price: Decimal
    step_size: Decimal
    min_quantity: Decimal
    max_quantity: Decimal
    market_step_size: Decimal
    market_min_quantity: Decimal
    market_max_quantity: Decimal
    min_notional: Decimal
    max_notional: Decimal | None
    notional_applies_to_market: bool
    maximum_notional_applies_to_market: bool
    market_order_allowed: bool
    quote_order_quantity_market_allowed: bool
    bid_multiplier_up: Decimal | None
    bid_multiplier_down: Decimal | None
    ask_multiplier_up: Decimal | None
    ask_multiplier_down: Decimal | None
    percent_average_price_minutes: int | None

    @classmethod
    def from_exchange_info(cls, payload: Mapping[str, object]) -> BinanceSpotSymbolRules:
        symbols = payload.get("symbols")
        if not isinstance(symbols, list) or len(symbols) != 1:
            raise BinanceSpotTestnetError("BTCUSDT exchange information is missing or ambiguous")
        symbol = symbols[0]
        if not isinstance(symbol, dict) or symbol.get("symbol") != TESTNET_SYMBOL:
            raise BinanceSpotTestnetError("Exchange information did not resolve BTCUSDT")
        permissions = symbol.get("permissions", [])
        spot_allowed = symbol.get("isSpotTradingAllowed")
        if spot_allowed is False or (permissions and "SPOT" not in permissions):
            raise BinanceSpotTestnetError("BTCUSDT is not enabled for Spot trading")

        filters_raw = symbol.get("filters")
        if not isinstance(filters_raw, list):
            raise BinanceSpotTestnetError("BTCUSDT exchange filters are missing")
        filters = {
            item.get("filterType"): item
            for item in filters_raw
            if isinstance(item, dict) and isinstance(item.get("filterType"), str)
        }
        price_filter = _required_filter(filters, "PRICE_FILTER")
        lot_filter = _required_filter(filters, "LOT_SIZE")
        market_lot_filter = _required_filter(filters, "MARKET_LOT_SIZE")
        notional_filter = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
        if not isinstance(notional_filter, dict):
            raise BinanceSpotTestnetError("BTCUSDT notional filter is missing")
        percent_filter = filters.get("PERCENT_PRICE_BY_SIDE")

        return cls(
            symbol=TESTNET_SYMBOL,
            status=str(symbol.get("status", "")),
            base_asset=str(symbol.get("baseAsset", "")),
            quote_asset=str(symbol.get("quoteAsset", "")),
            tick_size=_decimal_field(price_filter, "tickSize"),
            min_price=_decimal_field(price_filter, "minPrice"),
            max_price=_decimal_field(price_filter, "maxPrice"),
            step_size=_decimal_field(lot_filter, "stepSize"),
            min_quantity=_decimal_field(lot_filter, "minQty"),
            max_quantity=_decimal_field(lot_filter, "maxQty"),
            market_step_size=_decimal_field(market_lot_filter, "stepSize"),
            market_min_quantity=_decimal_field(market_lot_filter, "minQty"),
            market_max_quantity=_decimal_field(market_lot_filter, "maxQty"),
            min_notional=_decimal_field(notional_filter, "minNotional"),
            max_notional=(
                _decimal_field(notional_filter, "maxNotional")
                if "maxNotional" in notional_filter
                and Decimal(str(notional_filter["maxNotional"])) > 0
                else None
            ),
            notional_applies_to_market=_boolean_field(
                notional_filter,
                "applyMinToMarket" if "applyMinToMarket" in notional_filter else "applyToMarket",
            ),
            maximum_notional_applies_to_market=_boolean_field(
                notional_filter,
                "applyMaxToMarket",
                default=False,
            ),
            market_order_allowed="MARKET" in symbol.get("orderTypes", []),
            quote_order_quantity_market_allowed=bool(
                symbol.get("quoteOrderQtyMarketAllowed", False)
            ),
            bid_multiplier_up=(
                _decimal_field(percent_filter, "bidMultiplierUp")
                if isinstance(percent_filter, dict)
                else None
            ),
            bid_multiplier_down=(
                _decimal_field(percent_filter, "bidMultiplierDown")
                if isinstance(percent_filter, dict)
                else None
            ),
            ask_multiplier_up=(
                _decimal_field(percent_filter, "askMultiplierUp")
                if isinstance(percent_filter, dict)
                else None
            ),
            ask_multiplier_down=(
                _decimal_field(percent_filter, "askMultiplierDown")
                if isinstance(percent_filter, dict)
                else None
            ),
            percent_average_price_minutes=(
                int(percent_filter["avgPriceMins"])
                if isinstance(percent_filter, dict)
                and percent_filter.get("avgPriceMins") is not None
                else None
            ),
        )

    @property
    def effective_market_step_size(self) -> Decimal:
        return self.market_step_size if self.market_step_size > 0 else self.step_size

    def validate_market_buy_quote(
        self,
        *,
        quote_order_quantity: Decimal,
        maximum_notional: Decimal = DEFAULT_MAX_VIRTUAL_NOTIONAL,
    ) -> None:
        self._validate_market_support()
        if not self.quote_order_quantity_market_allowed:
            raise BinanceSpotTestnetError(
                "BTCUSDT does not allow quoteOrderQty for MARKET orders"
            )
        if quote_order_quantity <= 0:
            raise BinanceSpotTestnetError("Market BUY quote quantity must be positive")
        if (
            self.notional_applies_to_market
            and quote_order_quantity < self.min_notional
        ):
            raise BinanceSpotTestnetError("Market BUY notional is below the BTCUSDT minimum")
        if (
            self.maximum_notional_applies_to_market
            and self.max_notional is not None
            and quote_order_quantity > self.max_notional
        ):
            raise BinanceSpotTestnetError(
                "Market BUY notional exceeds the BTCUSDT exchange maximum"
            )
        if quote_order_quantity > maximum_notional:
            raise BinanceSpotTestnetError(
                "Market BUY notional exceeds the Aurex virtual-order cap"
            )

    def validate_market_sell_quantity(
        self,
        *,
        quantity: Decimal,
        reference_price: Decimal,
        maximum_notional: Decimal = DEFAULT_MAX_VIRTUAL_NOTIONAL,
    ) -> None:
        self._validate_market_support()
        if reference_price <= 0:
            raise BinanceSpotTestnetError("Market SELL reference price must be positive")
        if quantity < self.market_min_quantity or quantity > self.market_max_quantity:
            raise BinanceSpotTestnetError(
                "Market SELL quantity is outside the BTCUSDT MARKET_LOT_SIZE range"
            )
        step_size = self.effective_market_step_size
        if not _is_step_aligned(quantity, step_size):
            raise BinanceSpotTestnetError(
                "Market SELL quantity is not aligned to the BTCUSDT market step size"
            )
        notional = quantity * reference_price
        if self.notional_applies_to_market and notional < self.min_notional:
            raise BinanceSpotTestnetError("Market SELL notional is below the BTCUSDT minimum")
        if (
            self.maximum_notional_applies_to_market
            and self.max_notional is not None
            and notional > self.max_notional
        ):
            raise BinanceSpotTestnetError(
                "Market SELL notional exceeds the BTCUSDT exchange maximum"
            )
        if notional > maximum_notional:
            raise BinanceSpotTestnetError(
                "Market SELL notional exceeds the Aurex virtual-order cap"
            )

    def round_market_quantity_down(self, quantity: Decimal) -> Decimal:
        return _round_to_step(quantity, self.effective_market_step_size, ROUND_FLOOR)

    def _validate_market_support(self) -> None:
        if self.status != "TRADING":
            raise BinanceSpotTestnetError("BTCUSDT is not currently in TRADING status")
        if not self.market_order_allowed:
            raise BinanceSpotTestnetError("BTCUSDT does not allow MARKET orders")

    def validate_limit_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        percent_reference_price: Decimal | None = None,
        maximum_notional: Decimal = DEFAULT_MAX_VIRTUAL_NOTIONAL,
    ) -> None:
        if self.status != "TRADING":
            raise BinanceSpotTestnetError("BTCUSDT is not currently in TRADING status")
        if side not in {"BUY", "SELL"}:
            raise BinanceSpotTestnetError("Only BUY or SELL sides are allowed")
        if quantity < self.min_quantity or quantity > self.max_quantity:
            raise BinanceSpotTestnetError("Order quantity is outside the BTCUSDT LOT_SIZE range")
        if not _is_step_aligned(quantity, self.step_size):
            raise BinanceSpotTestnetError("Order quantity is not aligned to BTCUSDT stepSize")
        if price < self.min_price or price > self.max_price:
            raise BinanceSpotTestnetError("Order price is outside the BTCUSDT PRICE_FILTER range")
        if not _is_step_aligned(price, self.tick_size):
            raise BinanceSpotTestnetError("Order price is not aligned to BTCUSDT tickSize")
        multiplier_down = self.bid_multiplier_down if side == "BUY" else self.ask_multiplier_down
        multiplier_up = self.bid_multiplier_up if side == "BUY" else self.ask_multiplier_up
        if multiplier_down is not None and multiplier_up is not None:
            if percent_reference_price is None or percent_reference_price <= 0:
                raise BinanceSpotTestnetError(
                    "BTCUSDT PERCENT_PRICE_BY_SIDE validation requires a reference price"
                )
            minimum_price = percent_reference_price * multiplier_down
            maximum_price = percent_reference_price * multiplier_up
            if price < minimum_price or price > maximum_price:
                raise BinanceSpotTestnetError(
                    f"Order price is outside the BTCUSDT PERCENT_PRICE_BY_SIDE {side} range"
                )
        notional = quantity * price
        if notional < self.min_notional:
            raise BinanceSpotTestnetError("Order notional is below the BTCUSDT minimum")
        if self.max_notional is not None and notional > self.max_notional:
            raise BinanceSpotTestnetError("Order notional exceeds the BTCUSDT exchange maximum")
        if notional > maximum_notional:
            raise BinanceSpotTestnetError("Order notional exceeds the Aurex virtual-order cap")

    def bounded_test_order(
        self,
        market_price: Decimal,
        percent_reference_price: Decimal,
        best_bid_price: Decimal,
        *,
        maximum_notional: Decimal = DEFAULT_MAX_VIRTUAL_NOTIONAL,
    ) -> tuple[Decimal, Decimal]:
        if market_price <= 0 or percent_reference_price <= 0 or best_bid_price <= 0:
            raise BinanceSpotTestnetError("BTCUSDT reference prices must be positive")
        if self.bid_multiplier_down is None or self.bid_multiplier_up is None:
            raise BinanceSpotTestnetError("BTCUSDT PERCENT_PRICE_BY_SIDE filter is required")
        lower_bound = percent_reference_price * self.bid_multiplier_down
        upper_bound = percent_reference_price * self.bid_multiplier_up
        candidate = max(
            best_bid_price * Decimal("0.90"),
            lower_bound * Decimal("1.02"),
        )
        candidate = min(candidate, upper_bound * Decimal("0.98"))
        price = _round_to_step(candidate, self.tick_size, ROUND_FLOOR)
        if price >= best_bid_price:
            raise BinanceSpotTestnetError(
                "No safely resting BTCUSDT BUY price exists inside the percent-price band"
            )
        minimum_quantity = max(
            self.min_quantity,
            _round_to_step(self.min_notional / price, self.step_size, ROUND_CEILING),
        )
        quantity = _round_to_step(minimum_quantity, self.step_size, ROUND_CEILING)
        self.validate_limit_order(
            side="BUY",
            quantity=quantity,
            price=price,
            percent_reference_price=percent_reference_price,
            maximum_notional=maximum_notional,
        )
        return quantity, price


@dataclass(frozen=True)
class BinanceAssetBalance:
    asset: str
    free: Decimal
    locked: Decimal

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass(frozen=True)
class BinanceAccountSnapshot:
    can_trade: bool
    account_type: str
    permissions: tuple[str, ...]
    nonzero_assets: tuple[str, ...]
    maker_commission: Decimal | None
    taker_commission: Decimal | None
    balances: tuple[BinanceAssetBalance, ...]

    def balance(self, asset: str) -> BinanceAssetBalance:
        for balance in self.balances:
            if balance.asset == asset:
                return balance
        return BinanceAssetBalance(asset=asset, free=Decimal("0"), locked=Decimal("0"))


@dataclass(frozen=True)
class BinanceOrderSnapshot:
    symbol: str
    order_id: int
    client_order_id: str
    status: str
    side: str
    order_type: str
    price: Decimal
    original_quantity: Decimal
    executed_quantity: Decimal
    cumulative_quote_quantity: Decimal
    original_quote_order_quantity: Decimal
    transact_time_ms: int | None
    original_client_order_id: str | None

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> BinanceOrderSnapshot:
        return cls(
            symbol=str(payload.get("symbol", "")),
            order_id=int(payload.get("orderId", 0)),
            client_order_id=str(
                payload.get("clientOrderId") or payload.get("origClientOrderId") or ""
            ),
            status=str(payload.get("status", "")),
            side=str(payload.get("side", "")),
            order_type=str(payload.get("type", "")),
            price=Decimal(str(payload.get("price", "0"))),
            original_quantity=Decimal(str(payload.get("origQty", "0"))),
            executed_quantity=Decimal(str(payload.get("executedQty", "0"))),
            cumulative_quote_quantity=Decimal(str(payload.get("cummulativeQuoteQty", "0"))),
            original_quote_order_quantity=Decimal(
                str(payload.get("origQuoteOrderQty", "0"))
            ),
            transact_time_ms=(
                int(payload["transactTime"]) if payload.get("transactTime") is not None else None
            ),
            original_client_order_id=(
                str(payload["origClientOrderId"])
                if payload.get("origClientOrderId") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class BinanceTradeSnapshot:
    symbol: str
    trade_id: int
    order_id: int
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal
    commission: Decimal
    commission_asset: str
    time_ms: int
    is_buyer: bool
    is_maker: bool
    is_best_match: bool

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> BinanceTradeSnapshot:
        return cls(
            symbol=str(payload.get("symbol", "")),
            trade_id=int(payload.get("id", 0)),
            order_id=int(payload.get("orderId", 0)),
            price=Decimal(str(payload.get("price", "0"))),
            quantity=Decimal(str(payload.get("qty", "0"))),
            quote_quantity=Decimal(str(payload.get("quoteQty", "0"))),
            commission=Decimal(str(payload.get("commission", "0"))),
            commission_asset=str(payload.get("commissionAsset", "")),
            time_ms=int(payload.get("time", 0)),
            is_buyer=bool(payload.get("isBuyer")),
            is_maker=bool(payload.get("isMaker")),
            is_best_match=bool(payload.get("isBestMatch")),
        )


@dataclass(frozen=True)
class BinanceVirtualCancelReconciliation:
    external_order_identity_matches: bool
    placement_identity_matches: bool
    cancellation_identity_matches: bool
    quantity_matches: bool
    no_fill_occurred: bool
    lifecycle_status_matches: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.external_order_identity_matches,
                self.placement_identity_matches,
                self.cancellation_identity_matches,
                self.quantity_matches,
                self.no_fill_occurred,
                self.lifecycle_status_matches,
            )
        )


def reconcile_virtual_cancel_snapshots(
    *,
    placed: BinanceOrderSnapshot,
    queried: BinanceOrderSnapshot,
    cancelled: BinanceOrderSnapshot,
    final: BinanceOrderSnapshot,
    placement_client_order_id: str,
    cancellation_client_order_id: str,
    expected_quantity: Decimal,
) -> BinanceVirtualCancelReconciliation:
    snapshots = (placed, queried, cancelled, final)
    return BinanceVirtualCancelReconciliation(
        external_order_identity_matches=len({snapshot.order_id for snapshot in snapshots}) == 1,
        placement_identity_matches=(
            placed.client_order_id
            == queried.client_order_id
            == final.client_order_id
            == placement_client_order_id
        ),
        cancellation_identity_matches=(
            cancelled.original_client_order_id == placement_client_order_id
            and cancelled.client_order_id == cancellation_client_order_id
        ),
        quantity_matches=all(
            snapshot.original_quantity == expected_quantity for snapshot in snapshots
        ),
        no_fill_occurred=all(snapshot.executed_quantity == 0 for snapshot in snapshots),
        lifecycle_status_matches=(
            placed.status == "NEW"
            and queried.status == "NEW"
            and cancelled.status == "CANCELED"
            and final.status == "CANCELED"
        ),
    )


class BinanceSpotTestnetClient:
    def __init__(
        self,
        *,
        credentials: BinanceTestnetCredentials | None = None,
        transport: BinanceHttpTransport | None = None,
        timeout_seconds: float = 10,
        recv_window_ms: int = DEFAULT_RECV_WINDOW_MS,
        maximum_virtual_notional: Decimal = DEFAULT_MAX_VIRTUAL_NOTIONAL,
        virtual_order_entry_enabled: bool = False,
        virtual_fill_entry_enabled: bool = False,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if recv_window_ms <= 0 or recv_window_ms > 60_000:
            raise ValueError("recv_window_ms must be between 1 and 60000")
        if maximum_virtual_notional <= 0 or maximum_virtual_notional > Decimal("10"):
            raise ValueError("Aurex Testnet virtual-order notional cannot exceed USD 10")
        self._credentials = credentials
        self._transport = transport or UrllibBinanceTestnetTransport()
        self._timeout_seconds = timeout_seconds
        self._recv_window_ms = recv_window_ms
        self._maximum_virtual_notional = maximum_virtual_notional
        self._virtual_order_entry_enabled = virtual_order_entry_enabled
        self._virtual_fill_entry_enabled = virtual_fill_entry_enabled
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._server_offset_ms: int | None = None

    @property
    def environment(self) -> str:
        return "BINANCE_SPOT_TESTNET"

    @property
    def base_url(self) -> str:
        return TESTNET_REST_BASE_URL

    @property
    def virtual_order_entry_enabled(self) -> bool:
        return self._virtual_order_entry_enabled

    @property
    def virtual_fill_entry_enabled(self) -> bool:
        return self._virtual_fill_entry_enabled

    def ping(self) -> None:
        self._request("GET", "/api/v3/ping")

    def synchronize_time(self) -> int:
        local_before = self._clock_ms()
        payload = self._request("GET", "/api/v3/time")
        local_after = self._clock_ms()
        if not isinstance(payload, dict) or not isinstance(payload.get("serverTime"), int):
            raise BinanceSpotTestnetError("Binance Testnet server-time response is invalid")
        local_midpoint = local_before + ((local_after - local_before) // 2)
        self._server_offset_ms = payload["serverTime"] - local_midpoint
        return self._server_offset_ms

    def symbol_rules(self) -> BinanceSpotSymbolRules:
        payload = self._request(
            "GET",
            "/api/v3/exchangeInfo",
            parameters={"symbol": TESTNET_SYMBOL},
        )
        if not isinstance(payload, dict):
            raise BinanceSpotTestnetError("Binance Testnet exchange-info response is invalid")
        return BinanceSpotSymbolRules.from_exchange_info(payload)

    def ticker_price(self) -> Decimal:
        payload = self._request(
            "GET",
            "/api/v3/ticker/price",
            parameters={"symbol": TESTNET_SYMBOL},
        )
        if not isinstance(payload, dict) or payload.get("symbol") != TESTNET_SYMBOL:
            raise BinanceSpotTestnetError("Binance Testnet ticker response is invalid")
        price = Decimal(str(payload.get("price", "0")))
        if price <= 0:
            raise BinanceSpotTestnetError("Binance Testnet ticker price is invalid")
        return price

    def average_price(self, *, expected_minutes: int | None = None) -> Decimal:
        payload = self._request(
            "GET",
            "/api/v3/avgPrice",
            parameters={"symbol": TESTNET_SYMBOL},
        )
        if not isinstance(payload, dict):
            raise BinanceSpotTestnetError("Binance Testnet average-price response is invalid")
        price = Decimal(str(payload.get("price", "0")))
        if price <= 0:
            raise BinanceSpotTestnetError("Binance Testnet average price is invalid")
        if expected_minutes is not None and payload.get("mins") != expected_minutes:
            raise BinanceSpotTestnetError(
                "Binance Testnet average-price window does not match the symbol filter"
            )
        return price

    def best_bid_price(self) -> Decimal:
        payload = self._request(
            "GET",
            "/api/v3/ticker/bookTicker",
            parameters={"symbol": TESTNET_SYMBOL},
        )
        if not isinstance(payload, dict) or payload.get("symbol") != TESTNET_SYMBOL:
            raise BinanceSpotTestnetError("Binance Testnet book-ticker response is invalid")
        best_bid = Decimal(str(payload.get("bidPrice", "0")))
        if best_bid <= 0:
            raise BinanceSpotTestnetError("Binance Testnet best bid is invalid")
        return best_bid

    def account_snapshot(self) -> BinanceAccountSnapshot:
        payload = self._signed_request(
            "GET",
            "/api/v3/account",
            parameters={"omitZeroBalances": "true"},
        )
        if not isinstance(payload, dict):
            raise BinanceSpotTestnetError("Binance Testnet account response is invalid")
        commission_rates = payload.get("commissionRates")
        rates = commission_rates if isinstance(commission_rates, dict) else {}
        balances = payload.get("balances")
        sanitized_balances = (
            tuple(
                BinanceAssetBalance(
                    asset=str(item.get("asset", "")),
                    free=Decimal(str(item.get("free", "0"))),
                    locked=Decimal(str(item.get("locked", "0"))),
                )
                for item in balances
                if isinstance(item, dict) and item.get("asset")
            )
            if isinstance(balances, list)
            else ()
        )
        nonzero_assets = (
            tuple(
                sorted(
                    balance.asset
                    for balance in sanitized_balances
                    if balance.total != 0
                )
            )
        )
        return BinanceAccountSnapshot(
            can_trade=bool(payload.get("canTrade")),
            account_type=str(payload.get("accountType", "")),
            permissions=tuple(str(item) for item in payload.get("permissions", [])),
            nonzero_assets=nonzero_assets,
            maker_commission=_optional_decimal(rates.get("maker")),
            taker_commission=_optional_decimal(rates.get("taker")),
            balances=sanitized_balances,
        )

    def test_limit_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str,
    ) -> None:
        self._validate_order(side, quantity, price, client_order_id)
        payload = self._signed_request(
            "POST",
            "/api/v3/order/test",
            parameters=_limit_order_parameters(side, quantity, price, client_order_id),
        )
        if not isinstance(payload, dict):
            raise BinanceSpotTestnetError("Binance Testnet test-order response is invalid")

    def place_limit_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot:
        if not self._virtual_order_entry_enabled:
            raise BinanceSpotTestnetError(
                "Virtual order entry is disabled; enable it explicitly for Testnet qualification"
            )
        self._validate_order(side, quantity, price, client_order_id)
        payload = self._signed_request(
            "POST",
            "/api/v3/order",
            parameters=_limit_order_parameters(side, quantity, price, client_order_id),
        )
        return self._order_snapshot(payload)

    def test_market_buy(
        self,
        *,
        quote_order_quantity: Decimal,
        client_order_id: str,
    ) -> None:
        self._validate_market_buy(quote_order_quantity, client_order_id)
        payload = self._signed_request(
            "POST",
            "/api/v3/order/test",
            parameters=_market_buy_parameters(quote_order_quantity, client_order_id),
        )
        if not isinstance(payload, dict):
            raise BinanceSpotTestnetError("Binance Testnet market test-order response is invalid")

    def place_market_buy(
        self,
        *,
        quote_order_quantity: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot:
        if not self._virtual_fill_entry_enabled:
            raise BinanceSpotTestnetError(
                "Virtual fill entry is disabled; enable it explicitly for Testnet qualification"
            )
        self._validate_market_buy(quote_order_quantity, client_order_id)
        payload = self._signed_request(
            "POST",
            "/api/v3/order",
            parameters=_market_buy_parameters(quote_order_quantity, client_order_id),
        )
        return self._order_snapshot(payload)

    def test_market_sell(
        self,
        *,
        quantity: Decimal,
        client_order_id: str,
    ) -> None:
        self._validate_market_sell(quantity, client_order_id)
        payload = self._signed_request(
            "POST",
            "/api/v3/order/test",
            parameters=_market_sell_parameters(quantity, client_order_id),
        )
        if not isinstance(payload, dict):
            raise BinanceSpotTestnetError("Binance Testnet market test-order response is invalid")

    def place_market_sell(
        self,
        *,
        quantity: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot:
        if not self._virtual_fill_entry_enabled:
            raise BinanceSpotTestnetError(
                "Virtual fill entry is disabled; enable it explicitly for Testnet qualification"
            )
        self._validate_market_sell(quantity, client_order_id)
        payload = self._signed_request(
            "POST",
            "/api/v3/order",
            parameters=_market_sell_parameters(quantity, client_order_id),
        )
        return self._order_snapshot(payload)

    def query_order(
        self,
        *,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> BinanceOrderSnapshot:
        if client_order_id is None and order_id is None:
            raise BinanceSpotTestnetError(
                "Order query requires a client order ID or external order ID"
            )
        if client_order_id is not None:
            _validate_client_order_id(client_order_id)
        if order_id is not None and order_id <= 0:
            raise BinanceSpotTestnetError("External order ID must be positive")
        parameters: dict[str, object] = {"symbol": TESTNET_SYMBOL}
        if client_order_id is not None:
            parameters["origClientOrderId"] = client_order_id
        if order_id is not None:
            parameters["orderId"] = order_id
        payload = self._signed_request(
            "GET",
            "/api/v3/order",
            parameters=parameters,
        )
        return self._order_snapshot(payload)

    def open_orders(self) -> tuple[BinanceOrderSnapshot, ...]:
        payload = self._signed_request(
            "GET",
            "/api/v3/openOrders",
            parameters={"symbol": TESTNET_SYMBOL},
        )
        if not isinstance(payload, list):
            raise BinanceSpotTestnetError(
                "Binance Testnet open-orders response is invalid"
            )
        orders = tuple(
            BinanceOrderSnapshot.from_payload(item)
            for item in payload
            if isinstance(item, dict)
        )
        if len(orders) != len(payload):
            raise BinanceSpotTestnetError(
                "Binance Testnet open-orders response contains an invalid item"
            )
        if any(
            order.symbol != TESTNET_SYMBOL
            or order.order_id <= 0
            or not order.client_order_id
            or order.status not in {"NEW", "PARTIALLY_FILLED", "PENDING_CANCEL"}
            or order.original_quantity <= 0
            or order.executed_quantity < 0
            or order.executed_quantity > order.original_quantity
            for order in orders
        ):
            raise BinanceSpotTestnetError(
                "Binance Testnet open-orders response failed validation"
            )
        return orders

    def cancel_order(
        self,
        *,
        client_order_id: str,
        new_client_order_id: str | None = None,
    ) -> BinanceOrderSnapshot:
        if not self._virtual_order_entry_enabled:
            raise BinanceSpotTestnetError(
                "Virtual order entry is disabled; cancellation is unavailable"
            )
        _validate_client_order_id(client_order_id)
        if new_client_order_id is not None:
            _validate_client_order_id(new_client_order_id)
        parameters = {
            "symbol": TESTNET_SYMBOL,
            "origClientOrderId": client_order_id,
        }
        if new_client_order_id is not None:
            parameters["newClientOrderId"] = new_client_order_id
        payload = self._signed_request(
            "DELETE",
            "/api/v3/order",
            parameters=parameters,
        )
        return self._order_snapshot(payload)

    def account_trades(self, *, order_id: int) -> tuple[BinanceTradeSnapshot, ...]:
        if order_id <= 0:
            raise BinanceSpotTestnetError("External order ID must be positive")
        payload = self._signed_request(
            "GET",
            "/api/v3/myTrades",
            parameters={
                "symbol": TESTNET_SYMBOL,
                "orderId": order_id,
                "limit": 1000,
            },
        )
        if not isinstance(payload, list):
            raise BinanceSpotTestnetError("Binance Testnet account-trades response is invalid")
        trades = tuple(
            BinanceTradeSnapshot.from_payload(item)
            for item in payload
            if isinstance(item, dict)
        )
        if len(trades) != len(payload):
            raise BinanceSpotTestnetError(
                "Binance Testnet account-trades response contains an invalid item"
            )
        if any(
            trade.symbol != TESTNET_SYMBOL
            or trade.order_id != order_id
            or trade.trade_id <= 0
            or trade.price <= 0
            or trade.quantity <= 0
            or trade.quote_quantity <= 0
            or trade.commission < 0
            or not trade.commission_asset
            for trade in trades
        ):
            raise BinanceSpotTestnetError(
                "Binance Testnet account-trades response failed validation"
            )
        return trades

    def _validate_order(
        self,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str,
    ) -> None:
        _validate_client_order_id(client_order_id)
        rules = self.symbol_rules()
        percent_reference_price = self.average_price(
            expected_minutes=rules.percent_average_price_minutes
        )
        rules.validate_limit_order(
            side=side,
            quantity=quantity,
            price=price,
            percent_reference_price=percent_reference_price,
            maximum_notional=self._maximum_virtual_notional,
        )
        if self._virtual_order_entry_enabled and side == "BUY":
            best_bid_price = self.best_bid_price()
            if price >= best_bid_price:
                raise BinanceSpotTestnetError(
                    "Virtual cancel BUY price must remain below the current best bid"
                )

    def _validate_market_buy(
        self,
        quote_order_quantity: Decimal,
        client_order_id: str,
    ) -> None:
        _validate_client_order_id(client_order_id)
        self.symbol_rules().validate_market_buy_quote(
            quote_order_quantity=quote_order_quantity,
            maximum_notional=self._maximum_virtual_notional,
        )

    def _validate_market_sell(
        self,
        quantity: Decimal,
        client_order_id: str,
    ) -> None:
        _validate_client_order_id(client_order_id)
        rules = self.symbol_rules()
        rules.validate_market_sell_quantity(
            quantity=quantity,
            reference_price=self.average_price(),
            maximum_notional=self._maximum_virtual_notional,
        )

    def _order_snapshot(self, payload: object) -> BinanceOrderSnapshot:
        if not isinstance(payload, dict) or payload.get("symbol") != TESTNET_SYMBOL:
            raise BinanceSpotTestnetError("Binance Testnet order response is invalid")
        return BinanceOrderSnapshot.from_payload(payload)

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        parameters: Mapping[str, object] | None = None,
    ) -> object:
        if self._credentials is None:
            raise BinanceSpotTestnetError("Binance Spot Testnet credentials are required")
        if self._server_offset_ms is None:
            self.synchronize_time()
        signed_parameters = dict(parameters or {})
        signed_parameters["recvWindow"] = self._recv_window_ms
        signed_parameters["timestamp"] = self._clock_ms() + (self._server_offset_ms or 0)
        unsigned_query = _encode_parameters(signed_parameters)
        signature = hmac.new(
            self._credentials.secret_key.encode("utf-8"),
            unsigned_query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signed_query = f"{unsigned_query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._credentials.api_key}
        if method == "GET":
            return self._request(method, path, encoded_query=signed_query, headers=headers)
        return self._request(
            method,
            path,
            encoded_body=signed_query.encode("ascii"),
            headers={
                **headers,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        parameters: Mapping[str, object] | None = None,
        encoded_query: str = "",
        encoded_body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> object:
        if not path.startswith("/api/"):
            raise BinanceSpotTestnetError("Only Binance Spot /api routes are allowed")
        query = encoded_query or _encode_parameters(parameters or {})
        response = self._transport.send(
            method=method,
            path=path,
            query=query,
            body=encoded_body,
            headers={"Accept": "application/json", **dict(headers or {})},
            timeout_seconds=self._timeout_seconds,
        )
        if response.status_code < 200 or response.status_code >= 300:
            code, message = _safe_error(response.payload)
            raise BinanceSpotTestnetError(
                f"Binance Spot Testnet rejected the request: {message}",
                status_code=response.status_code,
                error_code=code,
            )
        return response.payload


def deterministic_client_order_id(purpose: str, evidence_key: str) -> str:
    normalized_purpose = re.sub(r"[^a-z0-9]+", "-", purpose.lower()).strip("-")[:10] or "order"
    digest = hashlib.sha256(evidence_key.encode("utf-8")).hexdigest()[:16]
    return f"aurex-{normalized_purpose}-{digest}"


def _required_filter(
    filters: Mapping[str, Mapping[str, object]],
    name: str,
) -> Mapping[str, object]:
    value = filters.get(name)
    if value is None:
        raise BinanceSpotTestnetError(f"BTCUSDT {name} filter is missing")
    return value


def _decimal_field(payload: Mapping[str, object], name: str) -> Decimal:
    try:
        return Decimal(str(payload[name]))
    except (KeyError, ValueError) as exc:
        raise BinanceSpotTestnetError(f"BTCUSDT filter field {name} is invalid") from exc


def _boolean_field(
    payload: Mapping[str, object],
    name: str,
    *,
    default: bool | None = None,
) -> bool:
    value = payload.get(name)
    if isinstance(value, bool):
        return value
    if value is None and default is not None:
        return default
    raise BinanceSpotTestnetError(f"BTCUSDT filter field {name} is invalid")


def _optional_decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _is_step_aligned(value: Decimal, step: Decimal) -> bool:
    return step == 0 or value % step == 0


def _round_to_step(value: Decimal, step: Decimal, rounding: str) -> Decimal:
    if step == 0:
        return value
    units = (value / step).to_integral_value(rounding=rounding)
    return units * step


def _validate_client_order_id(value: str) -> None:
    if not _CLIENT_ORDER_ID.fullmatch(value):
        raise BinanceSpotTestnetError(
            "Client order ID must be deterministic, Aurex-prefixed, and at most 35 characters"
        )


def _limit_order_parameters(
    side: str,
    quantity: Decimal,
    price: Decimal,
    client_order_id: str,
) -> dict[str, object]:
    return {
        "symbol": TESTNET_SYMBOL,
        "side": side,
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": format(quantity, "f"),
        "price": format(price, "f"),
        "newClientOrderId": client_order_id,
        "newOrderRespType": "FULL",
    }


def _market_buy_parameters(
    quote_order_quantity: Decimal,
    client_order_id: str,
) -> dict[str, object]:
    return {
        "symbol": TESTNET_SYMBOL,
        "side": "BUY",
        "type": "MARKET",
        "quoteOrderQty": format(quote_order_quantity, "f"),
        "newClientOrderId": client_order_id,
        "newOrderRespType": "FULL",
    }


def _market_sell_parameters(
    quantity: Decimal,
    client_order_id: str,
) -> dict[str, object]:
    return {
        "symbol": TESTNET_SYMBOL,
        "side": "SELL",
        "type": "MARKET",
        "quantity": format(quantity, "f"),
        "newClientOrderId": client_order_id,
        "newOrderRespType": "FULL",
    }


def _encode_parameters(parameters: Mapping[str, object]) -> str:
    return urlencode([(key, str(value)) for key, value in parameters.items()])


def _decode_json(raw_body: bytes) -> object:
    if not raw_body:
        return {}
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"msg": "The endpoint returned a non-JSON response"}


def _safe_error(payload: object) -> tuple[int | None, str]:
    if not isinstance(payload, dict):
        return None, "unrecognized error response"
    raw_code = payload.get("code")
    code = (
        int(raw_code)
        if isinstance(raw_code, int | str) and str(raw_code).lstrip("-").isdigit()
        else None
    )
    message = str(payload.get("msg", "unrecognized error response"))
    return code, message[:300]
