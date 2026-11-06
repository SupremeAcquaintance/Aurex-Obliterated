from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, getcontext
from enum import StrEnum

from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2DerivativesFoundationProtocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash

ZERO = Decimal("0")


class DerivativesFoundationError(ValueError):
    pass


class DuplicateEventError(DerivativesFoundationError):
    pass


class PairState(StrEnum):
    FLAT = "FLAT"
    OPENING = "OPENING"
    HEDGED = "HEDGED"
    CLOSING = "CLOSING"
    ROLLBACK = "ROLLBACK"
    LIQUIDATED = "LIQUIDATED"
    KILLED = "KILLED"


class Leg(StrEnum):
    SPOT = "SPOT"
    PERPETUAL = "PERPETUAL"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SyntheticOrderStatus(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(slots=True)
class SyntheticOrder:
    order_id: str
    leg: Leg
    side: Side
    quantity: Decimal
    reduce_only: bool
    created_at: datetime
    filled_quantity: Decimal = ZERO
    status: SyntheticOrderStatus = SyntheticOrderStatus.OPEN

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity


@dataclass(frozen=True, slots=True)
class FoundationLedgerEvent:
    event_id: str
    event_type: str
    occurred_at: datetime
    payload: dict[str, str]
    previous_hash: str
    event_hash: str


@dataclass(frozen=True, slots=True)
class FoundationSnapshot:
    cash: Decimal
    spot_quantity: Decimal
    perp_quantity: Decimal
    perp_average_entry: Decimal
    perp_realized_pl: Decimal
    cumulative_fees: Decimal
    cumulative_funding: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "cash": decimal_text(self.cash),
            "spot_quantity": decimal_text(self.spot_quantity),
            "perp_quantity": decimal_text(self.perp_quantity),
            "perp_average_entry": decimal_text(self.perp_average_entry),
            "perp_realized_pl": decimal_text(self.perp_realized_pl),
            "cumulative_fees": decimal_text(self.cumulative_fees),
            "cumulative_funding": decimal_text(self.cumulative_funding),
        }


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    status: str
    discrepancies: dict[str, dict[str, str]]


@dataclass(slots=True)
class SyntheticDerivativesEngine:
    protocol: V2DerivativesFoundationProtocol
    cash: Decimal | None = None
    spot_quantity: Decimal = ZERO
    spot_average_entry: Decimal = ZERO
    perp_quantity: Decimal = ZERO
    perp_average_entry: Decimal = ZERO
    perp_realized_pl: Decimal = ZERO
    cumulative_fees: Decimal = ZERO
    cumulative_funding: Decimal = ZERO
    cumulative_liquidation_fees: Decimal = ZERO
    state: PairState = PairState.FLAT
    kill_switch_enabled: bool = False
    opening_started_at: datetime | None = None
    orders: dict[str, SyntheticOrder] = field(default_factory=dict)
    ledger: list[FoundationLedgerEvent] = field(default_factory=list)
    _processed_fill_ids: set[str] = field(default_factory=set)
    _processed_funding_ids: set[str] = field(default_factory=set)
    _processed_external_event_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        getcontext().prec = self.protocol.accounting.decimal_precision_digits
        if self.cash is None:
            self.cash = self.protocol.risk.synthetic_initial_cash
        self.cash = Decimal(self.cash)

    @property
    def tolerance(self) -> Decimal:
        return self.protocol.paired_execution.hedge_tolerance_base_quantity

    @property
    def ledger_head_hash(self) -> str:
        return self.ledger[-1].event_hash if self.ledger else "0" * 64

    @property
    def net_base_delta(self) -> Decimal:
        return self.spot_quantity + self.perp_quantity

    def snapshot(self) -> FoundationSnapshot:
        return FoundationSnapshot(
            cash=self.cash or ZERO,
            spot_quantity=self.spot_quantity,
            perp_quantity=self.perp_quantity,
            perp_average_entry=self.perp_average_entry,
            perp_realized_pl=self.perp_realized_pl,
            cumulative_fees=self.cumulative_fees,
            cumulative_funding=self.cumulative_funding,
        )

    def _append_event(
        self,
        *,
        event_id: str,
        event_type: str,
        occurred_at: datetime,
        payload: dict[str, object],
    ) -> FoundationLedgerEvent:
        normalized_at = ensure_utc(occurred_at)
        normalized_payload = {
            key: decimal_text(value) if isinstance(value, Decimal) else str(value)
            for key, value in sorted(payload.items())
        }
        previous_hash = self.ledger_head_hash
        event_hash = universe_evidence_hash(
            {
                "event_id": event_id,
                "event_type": event_type,
                "occurred_at": normalized_at,
                "payload": normalized_payload,
                "previous_hash": previous_hash,
            }
        )
        event = FoundationLedgerEvent(
            event_id=event_id,
            event_type=event_type,
            occurred_at=normalized_at,
            payload=normalized_payload,
            previous_hash=previous_hash,
            event_hash=event_hash,
        )
        self.ledger.append(event)
        return event

    def _new_order(
        self,
        *,
        order_id: str,
        leg: Leg,
        side: Side,
        quantity: Decimal,
        reduce_only: bool,
        created_at: datetime,
    ) -> SyntheticOrder:
        if order_id in self.orders:
            raise DerivativesFoundationError(f"Duplicate order id: {order_id}")
        normalized_quantity = Decimal(quantity)
        if normalized_quantity <= ZERO:
            raise DerivativesFoundationError("Order quantity must be positive")
        order = SyntheticOrder(
            order_id=order_id,
            leg=leg,
            side=side,
            quantity=normalized_quantity,
            reduce_only=reduce_only,
            created_at=ensure_utc(created_at),
        )
        self.orders[order_id] = order
        self._append_event(
            event_id=f"order:{order_id}",
            event_type="ORDER_CREATED",
            occurred_at=created_at,
            payload={
                "leg": leg.value,
                "side": side.value,
                "quantity": normalized_quantity,
                "reduce_only": reduce_only,
            },
        )
        return order

    def pretrade_required_cash(
        self,
        *,
        quantity: Decimal,
        spot_price: Decimal,
        perp_price: Decimal,
    ) -> Decimal:
        quantity = Decimal(quantity)
        spot_notional = quantity * Decimal(spot_price)
        perp_notional = quantity * Decimal(perp_price)
        fees = (
            spot_notional + perp_notional
        ) * self.protocol.risk.taker_fee_rate
        margin = (
            perp_notional
            * self.protocol.risk.initial_margin_rate
            * self.protocol.risk.minimum_initial_margin_buffer_ratio
        )
        return spot_notional + fees + margin

    def open_pair(
        self,
        *,
        spot_order_id: str,
        perp_order_id: str,
        quantity: Decimal,
        spot_price: Decimal,
        perp_price: Decimal,
        occurred_at: datetime,
    ) -> tuple[SyntheticOrder, SyntheticOrder]:
        if self.kill_switch_enabled:
            raise DerivativesFoundationError("Kill switch blocks new openings")
        if self.state != PairState.FLAT:
            raise DerivativesFoundationError("Pair must be flat before opening")
        quantity = Decimal(quantity)
        required = self.pretrade_required_cash(
            quantity=quantity,
            spot_price=spot_price,
            perp_price=perp_price,
        )
        if (self.cash or ZERO) < required:
            self._append_event(
                event_id=f"margin-reject:{spot_order_id}:{perp_order_id}",
                event_type="PRETRADE_MARGIN_REJECTED",
                occurred_at=occurred_at,
                payload={"available_cash": self.cash or ZERO, "required_cash": required},
            )
            raise DerivativesFoundationError("Pretrade margin requirement failed")
        self.state = PairState.OPENING
        self.opening_started_at = ensure_utc(occurred_at)
        spot_order = self._new_order(
            order_id=spot_order_id,
            leg=Leg.SPOT,
            side=Side.BUY,
            quantity=quantity,
            reduce_only=False,
            created_at=occurred_at,
        )
        perp_order = self._new_order(
            order_id=perp_order_id,
            leg=Leg.PERPETUAL,
            side=Side.SELL,
            quantity=quantity,
            reduce_only=False,
            created_at=occurred_at,
        )
        return spot_order, perp_order

    def _apply_spot_fill(
        self,
        *,
        order: SyntheticOrder,
        quantity: Decimal,
        price: Decimal,
    ) -> None:
        signed_quantity = quantity if order.side == Side.BUY else -quantity
        if order.reduce_only and signed_quantity > ZERO:
            raise DerivativesFoundationError("Reduce-only spot order cannot buy")
        if self.spot_quantity + signed_quantity < -self.tolerance:
            raise DerivativesFoundationError("Spot fill would cross below zero")
        if signed_quantity > ZERO:
            new_quantity = self.spot_quantity + signed_quantity
            self.spot_average_entry = (
                self.spot_quantity * self.spot_average_entry
                + signed_quantity * price
            ) / new_quantity
            self.spot_quantity = new_quantity
        else:
            self.spot_quantity += signed_quantity
            if abs(self.spot_quantity) <= self.tolerance:
                self.spot_quantity = ZERO
                self.spot_average_entry = ZERO
        self.cash = (self.cash or ZERO) - signed_quantity * price

    def _apply_perp_fill(
        self,
        *,
        order: SyntheticOrder,
        quantity: Decimal,
        price: Decimal,
    ) -> None:
        signed_fill = quantity if order.side == Side.BUY else -quantity
        existing = self.perp_quantity
        if order.reduce_only and (
            existing == ZERO or existing * signed_fill >= ZERO
        ):
            raise DerivativesFoundationError(
                "Reduce-only perpetual fill would increase exposure"
            )
        if order.reduce_only and quantity > abs(existing):
            raise DerivativesFoundationError(
                "Reduce-only perpetual fill would cross through zero"
            )
        if existing == ZERO or existing * signed_fill > ZERO:
            new_quantity = existing + signed_fill
            self.perp_average_entry = (
                abs(existing) * self.perp_average_entry
                + abs(signed_fill) * price
            ) / abs(new_quantity)
            self.perp_quantity = new_quantity
            return
        close_quantity = min(abs(existing), abs(signed_fill))
        realized = (
            close_quantity
            * (price - self.perp_average_entry)
            * Decimal(1 if existing > ZERO else -1)
        )
        self.perp_realized_pl += realized
        self.cash = (self.cash or ZERO) + realized
        new_quantity = existing + signed_fill
        if new_quantity == ZERO:
            self.perp_quantity = ZERO
            self.perp_average_entry = ZERO
        elif existing * new_quantity > ZERO:
            self.perp_quantity = new_quantity
        else:
            self.perp_quantity = new_quantity
            self.perp_average_entry = price

    def apply_fill(
        self,
        *,
        order_id: str,
        fill_id: str,
        quantity: Decimal,
        price: Decimal,
        fee_rate: Decimal,
        occurred_at: datetime,
    ) -> None:
        if fill_id in self._processed_fill_ids:
            raise DuplicateEventError(f"Duplicate fill id: {fill_id}")
        order = self.orders.get(order_id)
        if order is None:
            raise DerivativesFoundationError(f"Unknown order: {order_id}")
        if order.status not in {
            SyntheticOrderStatus.OPEN,
            SyntheticOrderStatus.PARTIALLY_FILLED,
        }:
            raise DerivativesFoundationError("Order cannot accept another fill")
        quantity = Decimal(quantity)
        price = Decimal(price)
        fee_rate = Decimal(fee_rate)
        if quantity <= ZERO or price <= ZERO or fee_rate < ZERO:
            raise DerivativesFoundationError("Fill values are invalid")
        if quantity > order.remaining_quantity:
            raise DerivativesFoundationError("Fill exceeds order remainder")
        if order.leg == Leg.SPOT:
            self._apply_spot_fill(order=order, quantity=quantity, price=price)
        else:
            self._apply_perp_fill(order=order, quantity=quantity, price=price)
        fee = quantity * price * fee_rate
        self.cash = (self.cash or ZERO) - fee
        self.cumulative_fees += fee
        order.filled_quantity += quantity
        order.status = (
            SyntheticOrderStatus.FILLED
            if order.remaining_quantity == ZERO
            else SyntheticOrderStatus.PARTIALLY_FILLED
        )
        self._processed_fill_ids.add(fill_id)
        self._append_event(
            event_id=f"fill:{fill_id}",
            event_type="FILL_APPLIED",
            occurred_at=occurred_at,
            payload={
                "order_id": order_id,
                "leg": order.leg.value,
                "side": order.side.value,
                "quantity": quantity,
                "price": price,
                "fee": fee,
            },
        )
        self._refresh_state_after_fill()

    def _refresh_state_after_fill(self) -> None:
        is_flat = (
            abs(self.spot_quantity) <= self.tolerance
            and abs(self.perp_quantity) <= self.tolerance
        )
        if is_flat:
            self.spot_quantity = ZERO
            self.perp_quantity = ZERO
            self.spot_average_entry = ZERO
            self.perp_average_entry = ZERO
            if self.state != PairState.LIQUIDATED:
                self.state = (
                    PairState.KILLED
                    if self.kill_switch_enabled
                    else PairState.FLAT
                )
            return
        target = self.protocol.paired_execution.target_base_quantity
        full_size = (
            self.spot_quantity >= target - self.tolerance
            and abs(self.perp_quantity) >= target - self.tolerance
        )
        if (
            self.state == PairState.OPENING
            and full_size
            and abs(self.net_base_delta) <= self.tolerance
        ):
            self.state = PairState.HEDGED

    def reject_order(
        self,
        *,
        order_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> None:
        order = self.orders.get(order_id)
        if order is None:
            raise DerivativesFoundationError(f"Unknown order: {order_id}")
        if order.status not in {
            SyntheticOrderStatus.OPEN,
            SyntheticOrderStatus.PARTIALLY_FILLED,
        }:
            raise DerivativesFoundationError("Order cannot be rejected")
        order.status = SyntheticOrderStatus.REJECTED
        self._append_event(
            event_id=f"reject:{order_id}",
            event_type="ORDER_REJECTED",
            occurred_at=occurred_at,
            payload={"order_id": order_id, "reason": reason},
        )

    def cancel_open_orders(self, *, occurred_at: datetime, reason: str) -> None:
        for order in sorted(self.orders.values(), key=lambda item: item.order_id):
            if order.status in {
                SyntheticOrderStatus.OPEN,
                SyntheticOrderStatus.PARTIALLY_FILLED,
            }:
                order.status = SyntheticOrderStatus.CANCELLED
                self._append_event(
                    event_id=f"cancel:{order.order_id}",
                    event_type="ORDER_CANCELLED",
                    occurred_at=occurred_at,
                    payload={"order_id": order.order_id, "reason": reason},
                )

    def begin_rollback(
        self,
        *,
        spot_order_id: str | None,
        perp_order_id: str | None,
        occurred_at: datetime,
        reason: str,
        enable_kill_switch: bool = False,
    ) -> list[SyntheticOrder]:
        self.cancel_open_orders(occurred_at=occurred_at, reason=reason)
        if enable_kill_switch:
            self.kill_switch_enabled = True
        self.state = PairState.ROLLBACK
        orders = []
        if self.spot_quantity > self.tolerance:
            if spot_order_id is None:
                raise DerivativesFoundationError("Spot rollback order id is required")
            orders.append(
                self._new_order(
                    order_id=spot_order_id,
                    leg=Leg.SPOT,
                    side=Side.SELL,
                    quantity=self.spot_quantity,
                    reduce_only=True,
                    created_at=occurred_at,
                )
            )
        if self.perp_quantity < -self.tolerance:
            if perp_order_id is None:
                raise DerivativesFoundationError("Perp rollback order id is required")
            orders.append(
                self._new_order(
                    order_id=perp_order_id,
                    leg=Leg.PERPETUAL,
                    side=Side.BUY,
                    quantity=abs(self.perp_quantity),
                    reduce_only=True,
                    created_at=occurred_at,
                )
            )
        if not orders:
            self._refresh_state_after_fill()
        return orders

    def expire_opening(
        self,
        *,
        now: datetime,
        spot_rollback_order_id: str | None,
        perp_rollback_order_id: str | None,
    ) -> list[SyntheticOrder]:
        if self.state != PairState.OPENING or self.opening_started_at is None:
            raise DerivativesFoundationError("No opening is active")
        elapsed = (ensure_utc(now) - self.opening_started_at).total_seconds()
        if elapsed <= self.protocol.paired_execution.maximum_open_seconds:
            raise DerivativesFoundationError("Opening has not timed out")
        return self.begin_rollback(
            spot_order_id=spot_rollback_order_id,
            perp_order_id=perp_rollback_order_id,
            occurred_at=now,
            reason="OPEN_TIMEOUT",
        )

    def begin_close(
        self,
        *,
        spot_order_id: str | None,
        perp_order_id: str | None,
        occurred_at: datetime,
    ) -> list[SyntheticOrder]:
        if self.state not in {
            PairState.HEDGED,
            PairState.KILLED,
            PairState.OPENING,
        }:
            raise DerivativesFoundationError("Pair cannot begin close in this state")
        self.cancel_open_orders(occurred_at=occurred_at, reason="BEGIN_CLOSE")
        self.state = PairState.CLOSING
        orders = []
        if self.spot_quantity > self.tolerance:
            if spot_order_id is None:
                raise DerivativesFoundationError("Spot close order id is required")
            orders.append(
                self._new_order(
                    order_id=spot_order_id,
                    leg=Leg.SPOT,
                    side=Side.SELL,
                    quantity=self.spot_quantity,
                    reduce_only=True,
                    created_at=occurred_at,
                )
            )
        if self.perp_quantity < -self.tolerance:
            if perp_order_id is None:
                raise DerivativesFoundationError("Perp close order id is required")
            orders.append(
                self._new_order(
                    order_id=perp_order_id,
                    leg=Leg.PERPETUAL,
                    side=Side.BUY,
                    quantity=abs(self.perp_quantity),
                    reduce_only=True,
                    created_at=occurred_at,
                )
            )
        if not orders:
            self._refresh_state_after_fill()
        return orders

    def settle_funding(
        self,
        *,
        funding_event_id: str,
        funding_rate: Decimal,
        mark_price: Decimal,
        occurred_at: datetime,
    ) -> Decimal:
        if funding_event_id in self._processed_funding_ids:
            raise DuplicateEventError(
                f"Duplicate funding event id: {funding_event_id}"
            )
        if self.perp_quantity == ZERO:
            raise DerivativesFoundationError(
                "Funding cannot settle without a perpetual position"
            )
        rate = Decimal(funding_rate)
        mark = Decimal(mark_price)
        cashflow = -self.perp_quantity * mark * rate
        self.cash = (self.cash or ZERO) + cashflow
        self.cumulative_funding += cashflow
        self._processed_funding_ids.add(funding_event_id)
        self._append_event(
            event_id=f"funding:{funding_event_id}",
            event_type="FUNDING_SETTLED",
            occurred_at=occurred_at,
            payload={
                "perp_quantity": self.perp_quantity,
                "mark_price": mark,
                "funding_rate": rate,
                "cashflow": cashflow,
            },
        )
        return cashflow

    def perp_unrealized_pl(self, *, mark_price: Decimal) -> Decimal:
        if self.perp_quantity == ZERO:
            return ZERO
        return self.perp_quantity * (
            Decimal(mark_price) - self.perp_average_entry
        )

    def equity(
        self,
        *,
        spot_mark_price: Decimal,
        perp_mark_price: Decimal,
    ) -> Decimal:
        return (
            (self.cash or ZERO)
            + self.spot_quantity * Decimal(spot_mark_price)
            + self.perp_unrealized_pl(mark_price=perp_mark_price)
        )

    def collateral(
        self,
        *,
        spot_mark_price: Decimal,
        perp_mark_price: Decimal,
    ) -> Decimal:
        return (
            (self.cash or ZERO)
            + self.spot_quantity
            * Decimal(spot_mark_price)
            * self.protocol.risk.spot_collateral_haircut
            + self.perp_unrealized_pl(mark_price=perp_mark_price)
        )

    def liquidation_threshold(
        self,
        *,
        perp_mark_price: Decimal,
    ) -> Decimal:
        notional = abs(self.perp_quantity) * Decimal(perp_mark_price)
        return notional * (
            self.protocol.risk.maintenance_margin_rate
            + self.protocol.risk.liquidation_fee_rate
        )

    def should_liquidate(
        self,
        *,
        spot_mark_price: Decimal,
        perp_mark_price: Decimal,
    ) -> bool:
        if self.perp_quantity == ZERO:
            return False
        return self.collateral(
            spot_mark_price=spot_mark_price,
            perp_mark_price=perp_mark_price,
        ) <= self.liquidation_threshold(perp_mark_price=perp_mark_price)

    def apply_liquidation(
        self,
        *,
        event_id: str,
        spot_price: Decimal,
        perp_price: Decimal,
        occurred_at: datetime,
    ) -> None:
        if event_id in self._processed_external_event_ids:
            raise DuplicateEventError(f"Duplicate liquidation id: {event_id}")
        if not self.should_liquidate(
            spot_mark_price=spot_price,
            perp_mark_price=perp_price,
        ):
            raise DerivativesFoundationError("Liquidation threshold is not breached")
        spot_price = Decimal(spot_price)
        perp_price = Decimal(perp_price)
        existing_perp = self.perp_quantity
        existing_spot = self.spot_quantity
        realized = (
            abs(existing_perp)
            * (perp_price - self.perp_average_entry)
            * Decimal(1 if existing_perp > ZERO else -1)
        )
        liquidation_fee = (
            abs(existing_perp)
            * perp_price
            * self.protocol.risk.liquidation_fee_rate
        )
        spot_fee = (
            existing_spot
            * spot_price
            * self.protocol.risk.taker_fee_rate
        )
        self.cash = (
            (self.cash or ZERO)
            + realized
            + existing_spot * spot_price
            - liquidation_fee
            - spot_fee
        )
        self.perp_realized_pl += realized
        self.cumulative_liquidation_fees += liquidation_fee
        self.cumulative_fees += liquidation_fee + spot_fee
        self.spot_quantity = ZERO
        self.spot_average_entry = ZERO
        self.perp_quantity = ZERO
        self.perp_average_entry = ZERO
        self.kill_switch_enabled = True
        self.state = PairState.LIQUIDATED
        self.cancel_open_orders(
            occurred_at=occurred_at,
            reason="LIQUIDATION",
        )
        self._processed_external_event_ids.add(event_id)
        self._append_event(
            event_id=f"liquidation:{event_id}",
            event_type="LIQUIDATION_APPLIED",
            occurred_at=occurred_at,
            payload={
                "spot_quantity_closed": existing_spot,
                "perp_quantity_closed": existing_perp,
                "spot_price": spot_price,
                "perp_price": perp_price,
                "perp_realized_pl": realized,
                "liquidation_fee": liquidation_fee,
                "spot_fee": spot_fee,
            },
        )

    def apply_adl_reduction(
        self,
        *,
        event_id: str,
        quantity: Decimal,
        price: Decimal,
        occurred_at: datetime,
    ) -> Decimal:
        if event_id in self._processed_external_event_ids:
            raise DuplicateEventError(f"Duplicate ADL id: {event_id}")
        quantity = Decimal(quantity)
        price = Decimal(price)
        if self.perp_quantity >= ZERO or quantity <= ZERO:
            raise DerivativesFoundationError("ADL requires a short position")
        if quantity > abs(self.perp_quantity):
            raise DerivativesFoundationError("ADL reduction exceeds short quantity")
        realized = (
            quantity
            * (price - self.perp_average_entry)
            * Decimal("-1")
        )
        self.cash = (self.cash or ZERO) + realized
        self.perp_realized_pl += realized
        self.perp_quantity += quantity
        if self.perp_quantity == ZERO:
            self.perp_average_entry = ZERO
        self._processed_external_event_ids.add(event_id)
        self._append_event(
            event_id=f"adl:{event_id}",
            event_type="ADL_REDUCTION_APPLIED",
            occurred_at=occurred_at,
            payload={
                "quantity": quantity,
                "price": price,
                "realized_pl": realized,
                "remaining_perp_quantity": self.perp_quantity,
            },
        )
        if abs(self.net_base_delta) > self.tolerance:
            self.set_kill_switch(
                enabled=True,
                occurred_at=occurred_at,
                reason="ADL_DELTA_BREACH",
            )
        return realized

    def set_kill_switch(
        self,
        *,
        enabled: bool,
        occurred_at: datetime,
        reason: str,
    ) -> None:
        if self.kill_switch_enabled == enabled:
            return
        self.kill_switch_enabled = enabled
        if enabled:
            self.cancel_open_orders(occurred_at=occurred_at, reason=reason)
            if self.state != PairState.LIQUIDATED:
                self.state = PairState.KILLED
        elif self.state == PairState.KILLED and (
            self.spot_quantity == ZERO and self.perp_quantity == ZERO
        ):
            self.state = PairState.FLAT
        self._append_event(
            event_id=f"kill-switch:{len(self.ledger)}",
            event_type="KILL_SWITCH_CHANGED",
            occurred_at=occurred_at,
            payload={"enabled": enabled, "reason": reason},
        )

    def reconcile(
        self,
        *,
        external: FoundationSnapshot,
        reconciliation_id: str,
        occurred_at: datetime,
    ) -> ReconciliationResult:
        internal = self.snapshot()
        quantity_tolerance = Decimal(
            self.protocol.reconciliation.quantity_tolerance
        )
        money_tolerance = Decimal(self.protocol.reconciliation.money_tolerance)
        quantity_fields = {"spot_quantity", "perp_quantity"}
        discrepancies: dict[str, dict[str, str]] = {}
        for field_name in self.protocol.reconciliation.required_fields:
            internal_value = getattr(internal, field_name)
            external_value = getattr(external, field_name)
            tolerance = (
                quantity_tolerance
                if field_name in quantity_fields
                else money_tolerance
            )
            delta = external_value - internal_value
            if abs(delta) > tolerance:
                discrepancies[field_name] = {
                    "internal": decimal_text(internal_value),
                    "external": decimal_text(external_value),
                    "delta": decimal_text(delta),
                }
        status = "MATCHED" if not discrepancies else "FAIL"
        self._append_event(
            event_id=f"reconciliation:{reconciliation_id}",
            event_type="RECONCILIATION_COMPLETED",
            occurred_at=occurred_at,
            payload={
                "status": status,
                "discrepancy_count": len(discrepancies),
            },
        )
        if discrepancies:
            self.set_kill_switch(
                enabled=True,
                occurred_at=occurred_at,
                reason="RECONCILIATION_DRIFT",
            )
        return ReconciliationResult(
            status=status,
            discrepancies=discrepancies,
        )


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def decimal_text(value: Decimal | object) -> str:
    if not isinstance(value, Decimal):
        return str(value)
    if value == ZERO:
        return "0"
    return format(value.normalize(), "f")
