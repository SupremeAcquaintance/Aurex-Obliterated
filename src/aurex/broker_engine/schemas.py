from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurex.domain.enums import (
    BrokerConnectionStatus,
    BrokerEnvironment,
    BrokerOrderStatus,
    Direction,
    OrderIntentStatus,
    ReadinessStatus,
    ReconciliationStatus,
)


class BrokerConnectionResponse(BaseModel):
    id: str
    broker_name: str
    environment: BrokerEnvironment
    account_label: str
    status: BrokerConnectionStatus
    live_trading_enabled: bool
    capabilities: dict
    last_heartbeat_at: datetime | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class OrderIntentCreateRequest(BaseModel):
    risk_decision_id: str = Field(min_length=1)
    broker_connection_id: str | None = Field(default=None, min_length=1)


class OrderIntentResponse(BaseModel):
    id: str
    signal_id: str | None
    risk_decision_id: str | None
    broker_connection_id: str
    strategy: str
    symbol: str
    direction: Direction
    order_type: str
    quantity: Decimal
    requested_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    time_in_force: str
    status: OrderIntentStatus
    idempotency_key: str
    intent_snapshot: dict
    created_intent_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrokerOrderResponse(BaseModel):
    id: str
    order_intent_id: str
    broker_connection_id: str
    external_order_id: str
    status: BrokerOrderStatus
    symbol: str
    direction: Direction
    quantity: Decimal
    requested_price: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    submitted_at: datetime | None
    external_updated_at: datetime | None
    raw_payload: dict

    model_config = ConfigDict(from_attributes=True)


class SandboxFillRequest(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    price: Decimal | None = Field(default=None, gt=0)
    fees: Decimal | None = Field(default=None, ge=0)


class BrokerFillResponse(BaseModel):
    id: str
    broker_order_id: str
    external_fill_id: str
    symbol: str
    direction: Direction
    quantity: Decimal
    price: Decimal
    fees: Decimal
    filled_at: datetime
    raw_payload: dict

    model_config = ConfigDict(from_attributes=True)


class BrokerReconciliationReportResponse(BaseModel):
    id: str
    broker_connection_id: str
    status: ReconciliationStatus
    summary: str
    discrepancies: list
    broker_snapshot: dict
    aurex_snapshot: dict
    reconciled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveReadinessCheckResponse(BaseModel):
    id: str
    check_key: str
    name: str
    status: ReadinessStatus
    required: bool
    evidence_snapshot: dict
    notes: str | None
    last_checked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class BrokerReadinessResponse(BaseModel):
    ready_for_live: bool
    live_trading_enabled: bool
    sandbox_connection: BrokerConnectionResponse
    checks: list[LiveReadinessCheckResponse]
    latest_reconciliation: BrokerReconciliationReportResponse | None
    summary: str


class EmergencyStopResponse(BaseModel):
    live_trading_enabled: bool
    affected_connections: int
    cancelled_orders: int
    cancelled_intents: int
    kill_switch_enabled: bool
    message: str
