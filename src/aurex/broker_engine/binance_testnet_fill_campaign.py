from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from aurex.broker_engine.binance_spot_testnet import (
    TESTNET_REST_BASE_URL,
    TESTNET_SYMBOL,
    BinanceAccountSnapshot,
    BinanceOrderSnapshot,
    BinanceSpotSymbolRules,
    BinanceSpotTestnetError,
    BinanceTradeSnapshot,
)

DEFAULT_CONTRACT_PATH = Path(
    "data/evidence/binance_spot_testnet_fill_fee_contract_v1.json"
)
BUY_QUOTE_ORDER_QUANTITY = Decimal("6.50")
MAXIMUM_ORDER_NOTIONAL = Decimal("10.00")
MAXIMUM_ROUND_TRIP_LOSS = Decimal("0.50")
ACKNOWLEDGEMENT_PHRASE = (
    "I ACKNOWLEDGE ONE BOUNDED BINANCE SPOT TESTNET FILL CAMPAIGN"
)
TERMINAL_ORDER_STATUSES = {
    "FILLED",
    "CANCELED",
    "REJECTED",
    "EXPIRED",
    "EXPIRED_IN_MATCH",
}


class BinanceFillFeeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    contract_id: str
    frozen_at: datetime
    environment: str
    base_url: str
    symbol: str
    product: str
    base_asset: str
    quote_asset: str
    simulated_equity_usd: str
    buy_quote_order_quantity: str
    maximum_order_notional: str
    maximum_round_trip_loss: str
    order_timeout_seconds: int
    poll_interval_seconds: str
    maximum_cleanup_orders: int
    acknowledgement_phrase: str
    intended_fill_method: str
    partial_fill_policy: str
    ambiguous_outcome_policy: str
    idempotency_policy: str
    commission_policy: str
    balance_reconciliation_policy: str
    pass_gates: tuple[str, ...]
    limitations: tuple[str, ...]
    official_references: tuple[str, ...]
    production_authority: bool
    live_authority: bool
    real_capital_authority: bool
    sandbox_qualified: bool
    contract_sha256: str


def build_fill_fee_contract(*, frozen_at: datetime) -> BinanceFillFeeContract:
    draft = BinanceFillFeeContract(
        schema_version=1,
        contract_id="binance-spot-testnet-fill-fee-v1",
        frozen_at=frozen_at.astimezone(UTC),
        environment="BINANCE_SPOT_TESTNET",
        base_url=TESTNET_REST_BASE_URL,
        symbol=TESTNET_SYMBOL,
        product="SPOT",
        base_asset="BTC",
        quote_asset="USDT",
        simulated_equity_usd="100.00",
        buy_quote_order_quantity=format(BUY_QUOTE_ORDER_QUANTITY, "f"),
        maximum_order_notional=format(MAXIMUM_ORDER_NOTIONAL, "f"),
        maximum_round_trip_loss=format(MAXIMUM_ROUND_TRIP_LOSS, "f"),
        order_timeout_seconds=10,
        poll_interval_seconds="0.25",
        maximum_cleanup_orders=1,
        acknowledgement_phrase=ACKNOWLEDGEMENT_PHRASE,
        intended_fill_method=(
            "One MARKET BUY using quoteOrderQty, followed by one MARKET SELL using "
            "only campaign-acquired base quantity after base-fee deduction and "
            "market-step rounding."
        ),
        partial_fill_policy=(
            "Record partial execution, sell only proven acquired base, permit at most "
            "one deterministic cleanup sell, and fail the qualification gate."
        ),
        ambiguous_outcome_policy=(
            "Query the deterministic client order ID after a transport, timeout, "
            "HTTP 5xx, or -1007 outcome; never blindly resubmit and never submit a "
            "cleanup order while the prior order outcome remains ambiguous."
        ),
        idempotency_policy=(
            "Persist the run ID and all client order IDs before order entry; refuse "
            "to overwrite an existing campaign artifact."
        ),
        commission_policy=(
            "Read GET /api/v3/myTrades for every order and account for every "
            "commission in its actual commissionAsset, including zero commission."
        ),
        balance_reconciliation_policy=(
            "For every touched asset, final total balance minus initial total balance "
            "must exactly equal signed trade quantities and quote quantities minus "
            "commissions. Any unexplained asset delta fails."
        ),
        pass_gates=(
            "Testnet origin, Spot scope, BTCUSDT symbol, and no production/live authority",
            "authenticated account is trade-enabled",
            "MARKET and quoteOrderQty market BUY are supported by current filters",
            "signed MARKET test order passes without entering the matching engine",
            "BUY and SELL reach FILLED with deterministic identity",
            "each order exactly reconciles to its account trade records",
            "all commission assets and amounts are present and nonnegative",
            "all touched account balances satisfy exact delta equations",
            "final campaign BTC residual is nonnegative and below one market step",
            "each order notional is at most USD 10.00",
            "round-trip USDT loss is at most USD 0.50",
            "no cleanup or unresolved order outcome remains",
        ),
        limitations=(
            "Testnet assets are virtual and prove no real execution performance",
            "this campaign proves accounting mechanics, not strategy edge",
            "this campaign does not complete WebSocket, reconnect, reset, or soak gates",
            "sandbox_qualified remains false after Phase 2B",
            "production, live, and real-capital authority remain false",
        ),
        official_references=(
            "https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md",
            "https://github.com/binance/binance-spot-api-docs/blob/master/filters.md",
            "https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md",
        ),
        production_authority=False,
        live_authority=False,
        real_capital_authority=False,
        sandbox_qualified=False,
        contract_sha256="",
    )
    return draft.model_copy(update={"contract_sha256": contract_sha256(draft)})


def contract_sha256(contract: BinanceFillFeeContract) -> str:
    payload = contract.model_dump(mode="json")
    payload["contract_sha256"] = ""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def audit_fill_fee_contract(contract: BinanceFillFeeContract) -> bool:
    expected = build_fill_fee_contract(frozen_at=contract.frozen_at)
    return contract == expected and contract.contract_sha256 == contract_sha256(contract)


@dataclass(frozen=True)
class OrderTradeReconciliation:
    order_identity_matches: bool
    side_matches: bool
    quantities_match: bool
    quote_quantities_match: bool
    trade_records_present: bool
    commissions_valid: bool
    commission_by_asset: Mapping[str, Decimal]

    @property
    def passed(self) -> bool:
        return all(
            (
                self.order_identity_matches,
                self.side_matches,
                self.quantities_match,
                self.quote_quantities_match,
                self.trade_records_present,
                self.commissions_valid,
            )
        )


@dataclass(frozen=True)
class BalanceReconciliation:
    expected_deltas: Mapping[str, Decimal]
    observed_deltas: Mapping[str, Decimal]
    mismatches: Mapping[str, Mapping[str, Decimal]]

    @property
    def passed(self) -> bool:
        return not self.mismatches


@dataclass(frozen=True)
class CampaignOrder:
    order: BinanceOrderSnapshot
    trades: tuple[BinanceTradeSnapshot, ...]
    reconciliation: OrderTradeReconciliation
    purpose: str


@dataclass(frozen=True)
class FillCampaignResult:
    initial_account: BinanceAccountSnapshot
    final_account: BinanceAccountSnapshot
    buy: CampaignOrder
    sells: tuple[CampaignOrder, ...]
    balance_reconciliation: BalanceReconciliation
    sold_base_quantity: Decimal
    expected_base_residual: Decimal
    round_trip_quote_delta: Decimal
    cleanup_order_used: bool
    cleanup_blocker: str | None
    passed: bool
    failed_gates: tuple[str, ...]


class FillCampaignClient(Protocol):
    def account_snapshot(self) -> BinanceAccountSnapshot: ...

    def symbol_rules(self) -> BinanceSpotSymbolRules: ...

    def test_market_buy(
        self,
        *,
        quote_order_quantity: Decimal,
        client_order_id: str,
    ) -> None: ...

    def place_market_buy(
        self,
        *,
        quote_order_quantity: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot: ...

    def test_market_sell(
        self,
        *,
        quantity: Decimal,
        client_order_id: str,
    ) -> None: ...

    def place_market_sell(
        self,
        *,
        quantity: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot: ...

    def query_order(
        self,
        *,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> BinanceOrderSnapshot: ...

    def account_trades(self, *, order_id: int) -> tuple[BinanceTradeSnapshot, ...]: ...


def reconcile_order_trades(
    *,
    order: BinanceOrderSnapshot,
    trades: Sequence[BinanceTradeSnapshot],
    expected_side: str,
    expected_client_order_id: str,
) -> OrderTradeReconciliation:
    quantity = sum((trade.quantity for trade in trades), Decimal("0"))
    quote_quantity = sum((trade.quote_quantity for trade in trades), Decimal("0"))
    commission_by_asset: dict[str, Decimal] = defaultdict(Decimal)
    for trade in trades:
        commission_by_asset[trade.commission_asset] += trade.commission
    return OrderTradeReconciliation(
        order_identity_matches=(
            order.client_order_id == expected_client_order_id
            and order.symbol == TESTNET_SYMBOL
            and all(
                trade.symbol == order.symbol and trade.order_id == order.order_id
                for trade in trades
            )
        ),
        side_matches=(
            order.side == expected_side
            and all(trade.is_buyer == (expected_side == "BUY") for trade in trades)
        ),
        quantities_match=quantity == order.executed_quantity,
        quote_quantities_match=quote_quantity == order.cumulative_quote_quantity,
        trade_records_present=bool(trades) if order.executed_quantity > 0 else not trades,
        commissions_valid=all(
            trade.commission >= 0 and bool(trade.commission_asset) for trade in trades
        ),
        commission_by_asset=dict(sorted(commission_by_asset.items())),
    )


def expected_balance_deltas(
    *,
    buy_trades: Sequence[BinanceTradeSnapshot],
    sell_trades: Sequence[BinanceTradeSnapshot],
    base_asset: str = "BTC",
    quote_asset: str = "USDT",
) -> dict[str, Decimal]:
    deltas: dict[str, Decimal] = defaultdict(Decimal)
    for trade in buy_trades:
        deltas[base_asset] += trade.quantity
        deltas[quote_asset] -= trade.quote_quantity
        deltas[trade.commission_asset] -= trade.commission
    for trade in sell_trades:
        deltas[base_asset] -= trade.quantity
        deltas[quote_asset] += trade.quote_quantity
        deltas[trade.commission_asset] -= trade.commission
    return dict(sorted(deltas.items()))


def reconcile_balances(
    *,
    initial: BinanceAccountSnapshot,
    final: BinanceAccountSnapshot,
    expected_deltas: Mapping[str, Decimal],
) -> BalanceReconciliation:
    initial_by_asset = {balance.asset: balance.total for balance in initial.balances}
    final_by_asset = {balance.asset: balance.total for balance in final.balances}
    assets = set(initial_by_asset) | set(final_by_asset) | set(expected_deltas)
    observed = {
        asset: final_by_asset.get(asset, Decimal("0"))
        - initial_by_asset.get(asset, Decimal("0"))
        for asset in sorted(assets)
    }
    mismatches = {
        asset: {
            "expected": expected_deltas.get(asset, Decimal("0")),
            "observed": observed[asset],
        }
        for asset in sorted(assets)
        if observed[asset] != expected_deltas.get(asset, Decimal("0"))
    }
    return BalanceReconciliation(
        expected_deltas=dict(sorted(expected_deltas.items())),
        observed_deltas=observed,
        mismatches=mismatches,
    )


def run_bounded_fill_campaign(
    client: FillCampaignClient,
    *,
    buy_client_order_id: str,
    sell_client_order_id: str,
    cleanup_client_order_id: str,
    contract: BinanceFillFeeContract,
    on_checkpoint: Callable[[str, object], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> FillCampaignResult:
    if not audit_fill_fee_contract(contract):
        raise BinanceSpotTestnetError("Fill-and-fee campaign contract is not reproducible")
    if contract.production_authority or contract.live_authority or contract.sandbox_qualified:
        raise BinanceSpotTestnetError("Fill-and-fee campaign contract crossed its safety boundary")

    def checkpoint(stage: str, value: object) -> None:
        if on_checkpoint is not None:
            on_checkpoint(stage, value)

    initial = client.account_snapshot()
    checkpoint("initial_account", initial)
    if not initial.can_trade or "SPOT" not in initial.permissions:
        raise BinanceSpotTestnetError("Binance Spot Testnet account is not trade-enabled")
    if initial.balance("USDT").free < BUY_QUOTE_ORDER_QUANTITY:
        raise BinanceSpotTestnetError("Insufficient free Testnet USDT for bounded campaign")

    rules = client.symbol_rules()
    rules.validate_market_buy_quote(
        quote_order_quantity=BUY_QUOTE_ORDER_QUANTITY,
        maximum_notional=MAXIMUM_ORDER_NOTIONAL,
    )
    client.test_market_buy(
        quote_order_quantity=BUY_QUOTE_ORDER_QUANTITY,
        client_order_id=buy_client_order_id,
    )
    checkpoint("market_buy_test_order", {"status": "PASS"})

    buy_order = _submit_and_resolve(
        submit=lambda: client.place_market_buy(
            quote_order_quantity=BUY_QUOTE_ORDER_QUANTITY,
            client_order_id=buy_client_order_id,
        ),
        client=client,
        client_order_id=buy_client_order_id,
        contract=contract,
        sleep=sleep,
        monotonic=monotonic,
    )
    checkpoint("buy_order", buy_order)
    buy_trades = client.account_trades(order_id=buy_order.order_id)
    checkpoint("buy_trades", buy_trades)
    buy_reconciliation = reconcile_order_trades(
        order=buy_order,
        trades=buy_trades,
        expected_side="BUY",
        expected_client_order_id=buy_client_order_id,
    )
    buy = CampaignOrder(
        order=buy_order,
        trades=buy_trades,
        reconciliation=buy_reconciliation,
        purpose="BUY",
    )

    base_commission = buy_reconciliation.commission_by_asset.get("BTC", Decimal("0"))
    acquired_base = buy_order.executed_quantity - base_commission
    sell_quantity = rules.round_market_quantity_down(acquired_base)
    sells: list[CampaignOrder] = []
    cleanup_order_used = False
    cleanup_blocker: str | None = None

    if sell_quantity > 0:
        rules.validate_market_sell_quantity(
            quantity=sell_quantity,
            reference_price=(
                buy_order.cumulative_quote_quantity / buy_order.executed_quantity
                if buy_order.executed_quantity > 0
                else Decimal("0")
            ),
            maximum_notional=MAXIMUM_ORDER_NOTIONAL,
        )
        client.test_market_sell(
            quantity=sell_quantity,
            client_order_id=sell_client_order_id,
        )
        checkpoint("market_sell_test_order", {"status": "PASS"})
        sell = _execute_sell(
            client=client,
            quantity=sell_quantity,
            client_order_id=sell_client_order_id,
            purpose="SELL",
            contract=contract,
            checkpoint=checkpoint,
            sleep=sleep,
            monotonic=monotonic,
        )
        sells.append(sell)

        sold = sum(
            (trade.quantity for campaign_order in sells for trade in campaign_order.trades),
            Decimal("0"),
        )
        sell_base_commission = sum(
            (
                campaign_order.reconciliation.commission_by_asset.get(
                    "BTC", Decimal("0")
                )
                for campaign_order in sells
            ),
            Decimal("0"),
        )
        remaining = rules.round_market_quantity_down(
            acquired_base - sold - sell_base_commission
        )
        if sell.order.status != "FILLED" and remaining > 0:
            try:
                rules.validate_market_sell_quantity(
                    quantity=remaining,
                    reference_price=(
                        buy_order.cumulative_quote_quantity
                        / buy_order.executed_quantity
                    ),
                    maximum_notional=MAXIMUM_ORDER_NOTIONAL,
                )
            except BinanceSpotTestnetError as exc:
                cleanup_blocker = str(exc)
                checkpoint("cleanup_blocked", {"reason": cleanup_blocker})
            else:
                cleanup_order_used = True
                client.test_market_sell(
                    quantity=remaining,
                    client_order_id=cleanup_client_order_id,
                )
                cleanup = _execute_sell(
                    client=client,
                    quantity=remaining,
                    client_order_id=cleanup_client_order_id,
                    purpose="CLEANUP_SELL",
                    contract=contract,
                    checkpoint=checkpoint,
                    sleep=sleep,
                    monotonic=monotonic,
                )
                sells.append(cleanup)

    final = client.account_snapshot()
    checkpoint("final_account", final)
    all_sell_trades = tuple(
        trade for campaign_order in sells for trade in campaign_order.trades
    )
    expected_deltas = expected_balance_deltas(
        buy_trades=buy_trades,
        sell_trades=all_sell_trades,
    )
    balance_reconciliation = reconcile_balances(
        initial=initial,
        final=final,
        expected_deltas=expected_deltas,
    )
    sold_base = sum((trade.quantity for trade in all_sell_trades), Decimal("0"))
    expected_base_residual = expected_deltas.get("BTC", Decimal("0"))
    round_trip_quote_delta = expected_deltas.get("USDT", Decimal("0"))

    failed_gates: list[str] = []
    if buy.order.status != "FILLED":
        failed_gates.append("buy_not_filled")
    if not buy.reconciliation.passed:
        failed_gates.append("buy_trade_reconciliation")
    if len(sells) != 1 or sells[0].order.status != "FILLED":
        failed_gates.append("sell_not_single_filled_order")
    if any(not sell.reconciliation.passed for sell in sells):
        failed_gates.append("sell_trade_reconciliation")
    if not balance_reconciliation.passed:
        failed_gates.append("balance_reconciliation")
    if expected_base_residual < 0 or expected_base_residual >= rules.effective_market_step_size:
        failed_gates.append("base_residual")
    if round_trip_quote_delta < -MAXIMUM_ROUND_TRIP_LOSS:
        failed_gates.append("round_trip_loss")
    if cleanup_order_used:
        failed_gates.append("cleanup_used")
    if cleanup_blocker is not None:
        failed_gates.append("cleanup_incomplete")
    if (
        buy.order.original_quote_order_quantity != BUY_QUOTE_ORDER_QUANTITY
        or buy.order.cumulative_quote_quantity > MAXIMUM_ORDER_NOTIONAL
        or any(
            sell.order.cumulative_quote_quantity > MAXIMUM_ORDER_NOTIONAL
            for sell in sells
        )
    ):
        failed_gates.append("order_notional_cap")

    return FillCampaignResult(
        initial_account=initial,
        final_account=final,
        buy=buy,
        sells=tuple(sells),
        balance_reconciliation=balance_reconciliation,
        sold_base_quantity=sold_base,
        expected_base_residual=expected_base_residual,
        round_trip_quote_delta=round_trip_quote_delta,
        cleanup_order_used=cleanup_order_used,
        cleanup_blocker=cleanup_blocker,
        passed=not failed_gates,
        failed_gates=tuple(failed_gates),
    )


def _execute_sell(
    *,
    client: FillCampaignClient,
    quantity: Decimal,
    client_order_id: str,
    purpose: str,
    contract: BinanceFillFeeContract,
    checkpoint: Callable[[str, object], None],
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> CampaignOrder:
    order = _submit_and_resolve(
        submit=lambda: client.place_market_sell(
            quantity=quantity,
            client_order_id=client_order_id,
        ),
        client=client,
        client_order_id=client_order_id,
        contract=contract,
        sleep=sleep,
        monotonic=monotonic,
    )
    checkpoint(f"{purpose.lower()}_order", order)
    trades = client.account_trades(order_id=order.order_id)
    checkpoint(f"{purpose.lower()}_trades", trades)
    reconciliation = reconcile_order_trades(
        order=order,
        trades=trades,
        expected_side="SELL",
        expected_client_order_id=client_order_id,
    )
    return CampaignOrder(
        order=order,
        trades=trades,
        reconciliation=reconciliation,
        purpose=purpose,
    )


def _submit_and_resolve(
    *,
    submit: Callable[[], BinanceOrderSnapshot],
    client: FillCampaignClient,
    client_order_id: str,
    contract: BinanceFillFeeContract,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> BinanceOrderSnapshot:
    try:
        order = submit()
    except BinanceSpotTestnetError as exc:
        uncertain = (
            exc.status_code is None
            or exc.status_code >= 500
            or exc.error_code == -1007
        )
        if not uncertain:
            raise
        try:
            order = client.query_order(client_order_id=client_order_id)
        except BinanceSpotTestnetError:
            raise BinanceSpotTestnetError(
                "Testnet order outcome remains ambiguous; no resubmission or cleanup is allowed"
            ) from exc
    deadline = monotonic() + contract.order_timeout_seconds
    while order.status not in TERMINAL_ORDER_STATUSES and monotonic() < deadline:
        sleep(Decimal(contract.poll_interval_seconds).__float__())
        order = client.query_order(order_id=order.order_id)
    return order


def account_evidence(
    account: BinanceAccountSnapshot,
    *,
    assets: Sequence[str],
) -> dict[str, object]:
    return {
        "can_trade": account.can_trade,
        "account_type": account.account_type,
        "permissions": list(account.permissions),
        "maker_commission": (
            str(account.maker_commission) if account.maker_commission is not None else None
        ),
        "taker_commission": (
            str(account.taker_commission) if account.taker_commission is not None else None
        ),
        "balances": {
            asset: {
                "free": str(account.balance(asset).free),
                "locked": str(account.balance(asset).locked),
                "total": str(account.balance(asset).total),
            }
            for asset in sorted(set(assets))
        },
    }


def order_evidence(order: BinanceOrderSnapshot) -> dict[str, object]:
    return {
        "symbol": order.symbol,
        "external_order_id": order.order_id,
        "client_order_id": order.client_order_id,
        "status": order.status,
        "side": order.side,
        "type": order.order_type,
        "price": str(order.price),
        "original_quantity": str(order.original_quantity),
        "original_quote_order_quantity": str(order.original_quote_order_quantity),
        "executed_quantity": str(order.executed_quantity),
        "cumulative_quote_quantity": str(order.cumulative_quote_quantity),
        "transact_time_ms": order.transact_time_ms,
    }


def trades_evidence(trades: Sequence[BinanceTradeSnapshot]) -> list[dict[str, object]]:
    return [
        {
            "symbol": trade.symbol,
            "trade_id": trade.trade_id,
            "external_order_id": trade.order_id,
            "price": str(trade.price),
            "quantity": str(trade.quantity),
            "quote_quantity": str(trade.quote_quantity),
            "commission": str(trade.commission),
            "commission_asset": trade.commission_asset,
            "time_ms": trade.time_ms,
            "is_buyer": trade.is_buyer,
            "is_maker": trade.is_maker,
            "is_best_match": trade.is_best_match,
        }
        for trade in trades
    ]
