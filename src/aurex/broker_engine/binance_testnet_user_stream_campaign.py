from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from aurex.broker_engine.binance_spot_testnet import (
    TESTNET_SYMBOL,
    BinanceAccountSnapshot,
    BinanceOrderSnapshot,
    BinanceSpotSymbolRules,
    BinanceSpotTestnetError,
    BinanceTradeSnapshot,
)
from aurex.broker_engine.binance_testnet_user_stream import (
    BinanceEventDeduplicator,
    BinanceExecutionReport,
    BinanceExecutionReportReconciliation,
    BinanceUserDataEvent,
    BinanceUserStreamContract,
    account_position_matches_snapshot,
    reconcile_execution_report,
)


class UserStreamRestClient(Protocol):
    def account_snapshot(self) -> BinanceAccountSnapshot: ...

    def symbol_rules(self) -> BinanceSpotSymbolRules: ...

    def ticker_price(self) -> Decimal: ...

    def average_price(self, *, expected_minutes: int | None = None) -> Decimal: ...

    def best_bid_price(self) -> Decimal: ...

    def place_limit_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot: ...

    def query_order(
        self,
        *,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> BinanceOrderSnapshot: ...

    def cancel_order(
        self,
        *,
        client_order_id: str,
        new_client_order_id: str | None = None,
    ) -> BinanceOrderSnapshot: ...

    def account_trades(self, *, order_id: int) -> tuple[BinanceTradeSnapshot, ...]: ...


class UserStreamSession(Protocol):
    @property
    def subscription_id(self) -> int | None: ...

    def connect(self) -> None: ...

    def subscribe(self) -> int: ...

    def next_event(self, *, timeout_seconds: float | None = None) -> BinanceUserDataEvent: ...

    def unsubscribe(self) -> None: ...

    def disconnect(self) -> None: ...


@dataclass(frozen=True)
class StreamObservedOrder:
    placed: BinanceOrderSnapshot
    cancelled: BinanceOrderSnapshot
    final: BinanceOrderSnapshot
    trades: tuple[BinanceTradeSnapshot, ...]


@dataclass(frozen=True)
class BinanceUserStreamCampaignResult:
    initial_account: BinanceAccountSnapshot
    recovery_account: BinanceAccountSnapshot
    final_account: BinanceAccountSnapshot
    first_order: StreamObservedOrder
    second_order: StreamObservedOrder
    first_subscription_id: int
    second_subscription_id: int
    first_new_report: BinanceExecutionReport
    second_new_report: BinanceExecutionReport
    second_cancel_report: BinanceExecutionReport
    first_new_reconciliation: BinanceExecutionReportReconciliation
    second_new_reconciliation: BinanceExecutionReportReconciliation
    second_cancel_reconciliation: BinanceExecutionReportReconciliation
    events: tuple[BinanceUserDataEvent, ...]
    account_position_match_found: bool
    duplicate_event_count: int
    forced_disconnect_verified: bool
    rest_gap_recovery_verified: bool
    graceful_unsubscribe_verified: bool
    balance_reconciliation_verified: bool
    failed_gates: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failed_gates


def run_user_stream_campaign(
    rest: UserStreamRestClient,
    *,
    stream_factory: Callable[[], UserStreamSession],
    contract: BinanceUserStreamContract,
    first_client_order_id: str,
    first_cancel_client_order_id: str,
    second_client_order_id: str,
    second_cancel_client_order_id: str,
    on_checkpoint: Callable[[str, object], None] | None = None,
    monotonic: Callable[[], float],
) -> BinanceUserStreamCampaignResult:
    def checkpoint(stage: str, value: object) -> None:
        if on_checkpoint is not None:
            on_checkpoint(stage, value)

    initial_account = rest.account_snapshot()
    checkpoint("initial_account", initial_account)
    if not initial_account.can_trade:
        raise BinanceSpotTestnetError("Binance Spot Testnet account is not trade-enabled")

    rules = rest.symbol_rules()
    market_price = rest.ticker_price()
    average_price = rest.average_price(
        expected_minutes=rules.percent_average_price_minutes
    )
    best_bid = rest.best_bid_price()
    quantity, price = rules.bounded_test_order(
        market_price,
        average_price,
        best_bid,
        maximum_notional=Decimal(contract.maximum_order_notional),
    )
    checkpoint(
        "resting_order_preview",
        {
            "symbol": TESTNET_SYMBOL,
            "side": "BUY",
            "quantity": str(quantity),
            "price": str(price),
            "notional": str(quantity * price),
            "below_best_bid": price < best_bid,
        },
    )

    deduplicator = BinanceEventDeduplicator()
    events: list[BinanceUserDataEvent] = []

    first_stream = stream_factory()
    first_stream.connect()
    first_subscription_id = first_stream.subscribe()
    checkpoint(
        "first_subscription",
        {"subscription_id": first_subscription_id, "method": contract.subscription_method},
    )
    first_placed = _place_and_resolve(
        rest,
        quantity=quantity,
        price=price,
        client_order_id=first_client_order_id,
    )
    checkpoint("first_order_placed", first_placed)
    first_new_event = _wait_for_execution(
        first_stream,
        order_id=first_placed.order_id,
        status="NEW",
        deduplicator=deduplicator,
        events=events,
        timeout_seconds=contract.event_timeout_seconds,
        monotonic=monotonic,
        checkpoint=checkpoint,
    )
    first_stream.disconnect()
    forced_disconnect_verified = first_stream.subscription_id is None
    checkpoint(
        "forced_disconnect",
        {"verified": forced_disconnect_verified, "gap_expected": True},
    )

    first_cancelled = rest.cancel_order(
        client_order_id=first_client_order_id,
        new_client_order_id=first_cancel_client_order_id,
    )
    checkpoint("first_order_cancelled_during_gap", first_cancelled)

    second_stream = stream_factory()
    second_stream.connect()
    second_subscription_id = second_stream.subscribe()
    checkpoint(
        "second_subscription",
        {"subscription_id": second_subscription_id, "method": contract.subscription_method},
    )
    first_final = rest.query_order(order_id=first_placed.order_id)
    recovery_account = rest.account_snapshot()
    first_trades = rest.account_trades(order_id=first_placed.order_id)
    checkpoint("first_order_rest_recovery", first_final)
    checkpoint("recovery_account", recovery_account)
    checkpoint("first_order_trades", first_trades)
    rest_gap_recovery_verified = (
        first_final.order_id == first_placed.order_id
        and first_final.client_order_id == first_client_order_id
        and first_final.status == "CANCELED"
        and first_final.executed_quantity == 0
        and not first_trades
    )

    second_placed = _place_and_resolve(
        rest,
        quantity=quantity,
        price=price,
        client_order_id=second_client_order_id,
    )
    checkpoint("second_order_placed", second_placed)
    second_new_event = _wait_for_execution(
        second_stream,
        order_id=second_placed.order_id,
        status="NEW",
        deduplicator=deduplicator,
        events=events,
        timeout_seconds=contract.event_timeout_seconds,
        monotonic=monotonic,
        checkpoint=checkpoint,
    )
    second_cancelled = rest.cancel_order(
        client_order_id=second_client_order_id,
        new_client_order_id=second_cancel_client_order_id,
    )
    checkpoint("second_order_cancelled", second_cancelled)
    second_cancel_event = _wait_for_execution(
        second_stream,
        order_id=second_placed.order_id,
        status="CANCELED",
        deduplicator=deduplicator,
        events=events,
        timeout_seconds=contract.event_timeout_seconds,
        monotonic=monotonic,
        checkpoint=checkpoint,
    )
    second_final = rest.query_order(order_id=second_placed.order_id)
    second_trades = rest.account_trades(order_id=second_placed.order_id)
    final_account = rest.account_snapshot()
    checkpoint("second_order_final", second_final)
    checkpoint("second_order_trades", second_trades)
    checkpoint("final_account", final_account)
    account_position_match_found = any(
        event.account_position is not None
        and account_position_matches_snapshot(event.account_position, final_account)
        for event in events
    )
    if not account_position_match_found:
        account_position_match_found = _wait_for_account_match(
            second_stream,
            final_account=final_account,
            deduplicator=deduplicator,
            events=events,
            timeout_seconds=contract.event_timeout_seconds,
            monotonic=monotonic,
            checkpoint=checkpoint,
        )

    second_stream.unsubscribe()
    graceful_unsubscribe_verified = second_stream.subscription_id is None
    second_stream.disconnect()
    checkpoint(
        "graceful_unsubscribe",
        {"verified": graceful_unsubscribe_verified},
    )

    first_report = _required_report(first_new_event)
    second_new_report = _required_report(second_new_event)
    second_cancel_report = _required_report(second_cancel_event)
    first_new_reconciliation = reconcile_execution_report(
        first_report,
        first_placed,
        subscription_id=first_subscription_id,
    )
    second_new_reconciliation = reconcile_execution_report(
        second_new_report,
        second_placed,
        subscription_id=second_subscription_id,
    )
    second_cancel_reconciliation = reconcile_execution_report(
        second_cancel_report,
        second_final,
        subscription_id=second_subscription_id,
    )
    balances_match = _account_assets_match(
        initial_account,
        final_account,
        assets=("BTC", "USDT"),
    )

    failed_gates: list[str] = []
    _require(
        first_placed.status == "NEW" and first_placed.executed_quantity == 0,
        "first order did not remain NEW and unfilled",
        failed_gates,
    )
    _require(
        first_new_reconciliation.passed,
        "first NEW execution report did not reconcile with REST",
        failed_gates,
    )
    _require(
        forced_disconnect_verified,
        "forced disconnect did not close the first subscription",
        failed_gates,
    )
    _require(
        rest_gap_recovery_verified,
        "REST did not recover the first CANCELED order across the stream gap",
        failed_gates,
    )
    _require(
        second_placed.status == "NEW" and second_placed.executed_quantity == 0,
        "second order did not remain NEW and unfilled",
        failed_gates,
    )
    _require(
        second_new_reconciliation.passed,
        "second NEW execution report did not reconcile with REST",
        failed_gates,
    )
    _require(
        second_final.status == "CANCELED"
        and second_final.executed_quantity == 0
        and second_cancel_reconciliation.passed,
        "second CANCELED execution report did not reconcile with REST",
        failed_gates,
    )
    _require(
        not first_trades and not second_trades,
        "one or more Testnet trades occurred during the no-fill stream campaign",
        failed_gates,
    )
    _require(
        account_position_match_found,
        "no USDT account-position event matched the final REST account",
        failed_gates,
    )
    _require(
        balances_match,
        "final BTC or USDT balance differs from the initial account",
        failed_gates,
    )
    _require(
        graceful_unsubscribe_verified,
        "the second user-data subscription did not unsubscribe cleanly",
        failed_gates,
    )

    return BinanceUserStreamCampaignResult(
        initial_account=initial_account,
        recovery_account=recovery_account,
        final_account=final_account,
        first_order=StreamObservedOrder(
            placed=first_placed,
            cancelled=first_cancelled,
            final=first_final,
            trades=first_trades,
        ),
        second_order=StreamObservedOrder(
            placed=second_placed,
            cancelled=second_cancelled,
            final=second_final,
            trades=second_trades,
        ),
        first_subscription_id=first_subscription_id,
        second_subscription_id=second_subscription_id,
        first_new_report=first_report,
        second_new_report=second_new_report,
        second_cancel_report=second_cancel_report,
        first_new_reconciliation=first_new_reconciliation,
        second_new_reconciliation=second_new_reconciliation,
        second_cancel_reconciliation=second_cancel_reconciliation,
        events=tuple(events),
        account_position_match_found=account_position_match_found,
        duplicate_event_count=deduplicator.duplicate_count,
        forced_disconnect_verified=forced_disconnect_verified,
        rest_gap_recovery_verified=rest_gap_recovery_verified,
        graceful_unsubscribe_verified=graceful_unsubscribe_verified,
        balance_reconciliation_verified=balances_match,
        failed_gates=tuple(failed_gates),
    )


def _place_and_resolve(
    rest: UserStreamRestClient,
    *,
    quantity: Decimal,
    price: Decimal,
    client_order_id: str,
) -> BinanceOrderSnapshot:
    try:
        return rest.place_limit_order(
            side="BUY",
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )
    except BinanceSpotTestnetError as exc:
        uncertain = (
            exc.status_code is None
            or exc.status_code >= 500
            or exc.error_code == -1007
        )
        if not uncertain:
            raise
        try:
            return rest.query_order(client_order_id=client_order_id)
        except BinanceSpotTestnetError:
            raise BinanceSpotTestnetError(
                "Testnet stream-campaign order outcome is ambiguous; no resubmission allowed"
            ) from exc


def _wait_for_execution(
    stream: UserStreamSession,
    *,
    order_id: int,
    status: str,
    deduplicator: BinanceEventDeduplicator,
    events: list[BinanceUserDataEvent],
    timeout_seconds: float,
    monotonic: Callable[[], float],
    checkpoint: Callable[[str, object], None],
) -> BinanceUserDataEvent:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        event = stream.next_event(
            timeout_seconds=max(0.001, deadline - monotonic())
        )
        if not deduplicator.accept(event):
            checkpoint(
                "duplicate_event_suppressed",
                {"event_key": event.event_key},
            )
            continue
        events.append(event)
        checkpoint("user_data_event", event)
        report = event.execution_report
        if (
            report is not None
            and report.order_id == order_id
            and report.order_status == status
        ):
            return event
    raise BinanceSpotTestnetError(
        f"Timed out waiting for order {order_id} user-data status {status}"
    )


def _wait_for_account_match(
    stream: UserStreamSession,
    *,
    final_account: BinanceAccountSnapshot,
    deduplicator: BinanceEventDeduplicator,
    events: list[BinanceUserDataEvent],
    timeout_seconds: float,
    monotonic: Callable[[], float],
    checkpoint: Callable[[str, object], None],
) -> bool:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        try:
            event = stream.next_event(
                timeout_seconds=max(0.001, deadline - monotonic())
            )
        except TimeoutError:
            return False
        if not deduplicator.accept(event):
            checkpoint(
                "duplicate_event_suppressed",
                {"event_key": event.event_key},
            )
            continue
        events.append(event)
        checkpoint("user_data_event", event)
        if (
            event.account_position is not None
            and account_position_matches_snapshot(
                event.account_position,
                final_account,
            )
        ):
            return True
    return False


def _required_report(event: BinanceUserDataEvent) -> BinanceExecutionReport:
    if event.execution_report is None:
        raise BinanceSpotTestnetError("Required execution report is missing")
    return event.execution_report


def _account_assets_match(
    left: BinanceAccountSnapshot,
    right: BinanceAccountSnapshot,
    *,
    assets: Sequence[str],
) -> bool:
    return all(
        left.balance(asset).free == right.balance(asset).free
        and left.balance(asset).locked == right.balance(asset).locked
        for asset in assets
    )


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)
