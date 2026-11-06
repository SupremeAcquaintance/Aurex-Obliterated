from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from aurex.db.base import utc_now
from aurex.db.models import BrokerOrder, OrderIntent
from aurex.domain.enums import BrokerOrderStatus


@dataclass(frozen=True)
class BrokerSubmitResult:
    external_order_id: str
    status: BrokerOrderStatus
    submitted_at: datetime
    raw_payload: dict


@dataclass(frozen=True)
class BrokerFillResult:
    external_fill_id: str
    quantity: Decimal
    price: Decimal
    fees: Decimal
    filled_at: datetime
    raw_payload: dict


class BrokerAdapter(Protocol):
    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult:
        """Submit an order intent to a broker-like surface."""

    def simulate_fill(
        self,
        order: BrokerOrder,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal,
    ) -> BrokerFillResult:
        """Simulate a fill for a submitted order."""


class SandboxBrokerAdapter:
    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult:
        now = utc_now()
        external_order_id = f"sandbox-order-{intent.id}"
        return BrokerSubmitResult(
            external_order_id=external_order_id,
            status=BrokerOrderStatus.SUBMITTED,
            submitted_at=now,
            raw_payload={
                "adapter": "sandbox",
                "order_intent_id": intent.id,
                "external_order_id": external_order_id,
                "submitted_at": now.isoformat(),
            },
        )

    def simulate_fill(
        self,
        order: BrokerOrder,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal,
    ) -> BrokerFillResult:
        now = utc_now()
        external_fill_id = f"sandbox-fill-{order.id}-{len(order.id)}"
        return BrokerFillResult(
            external_fill_id=external_fill_id,
            quantity=quantity,
            price=price,
            fees=fees,
            filled_at=now,
            raw_payload={
                "adapter": "sandbox",
                "broker_order_id": order.id,
                "external_order_id": order.external_order_id,
                "external_fill_id": external_fill_id,
                "filled_at": now.isoformat(),
            },
        )
