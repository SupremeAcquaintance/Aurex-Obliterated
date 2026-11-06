from decimal import Decimal
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.broker_engine.adapters import SandboxBrokerAdapter
from aurex.broker_engine.schemas import BrokerReadinessResponse, EmergencyStopResponse
from aurex.config.settings import Settings
from aurex.db.base import utc_now
from aurex.db.models import (
    BrokerConnection,
    BrokerFill,
    BrokerOrder,
    BrokerPositionSnapshot,
    BrokerReconciliationReport,
    LiveReadinessCheck,
    OrderIntent,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
)
from aurex.domain.enums import (
    BrokerConnectionStatus,
    BrokerEnvironment,
    BrokerOrderStatus,
    OrderIntentStatus,
    PositionStatus,
    ReadinessStatus,
    ReconciliationStatus,
    TradeStatus,
)
from aurex.observability.system_events import SystemEventRecorder
from aurex.risk_engine.service import RiskEngine

SANDBOX_BROKER_NAME = "Aurex Sandbox Broker"
SANDBOX_ACCOUNT_LABEL = "paper-sandbox"


class BrokerReadinessService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.adapter = SandboxBrokerAdapter()

    def readiness_status(self) -> BrokerReadinessResponse:
        connection = self.ensure_sandbox_connection()
        checks = self.run_readiness_checks()
        latest_report = self.latest_reconciliation_report(connection.id)
        ready_for_live = (
            not self.settings.live_trading_enabled
            and all(check.status == ReadinessStatus.PASS for check in checks if check.required)
        )
        summary = (
            "Live readiness gates are satisfied, but live trading remains disabled."
            if ready_for_live
            else "Live trading is blocked until every required readiness gate passes."
        )
        return BrokerReadinessResponse(
            ready_for_live=ready_for_live,
            live_trading_enabled=self.settings.live_trading_enabled,
            sandbox_connection=connection,
            checks=checks,
            latest_reconciliation=latest_report,
            summary=summary,
        )

    def ensure_sandbox_connection(self) -> BrokerConnection:
        connection = self.session.execute(
            select(BrokerConnection).where(
                BrokerConnection.broker_name == SANDBOX_BROKER_NAME,
                BrokerConnection.environment == BrokerEnvironment.SANDBOX,
                BrokerConnection.account_label == SANDBOX_ACCOUNT_LABEL,
            )
        ).scalar_one_or_none()
        if connection is not None:
            return connection

        connection = BrokerConnection(
            broker_name=SANDBOX_BROKER_NAME,
            environment=BrokerEnvironment.SANDBOX,
            account_label=SANDBOX_ACCOUNT_LABEL,
            status=BrokerConnectionStatus.CONNECTED,
            live_trading_enabled=False,
            capabilities={
                "sandbox_only": True,
                "supports_order_intents": True,
                "supports_simulated_fills": True,
                "supports_position_snapshots": True,
            },
            last_heartbeat_at=utc_now(),
            is_active=True,
        )
        self.session.add(connection)
        self.session.flush()
        return connection

    def list_connections(self) -> list[BrokerConnection]:
        self.ensure_sandbox_connection()
        return list(
            self.session.execute(
                select(BrokerConnection).order_by(BrokerConnection.created_at.asc())
            ).scalars()
        )

    def create_order_intent(
        self,
        risk_decision_id: str,
        broker_connection_id: str | None = None,
    ) -> OrderIntent:
        connection = (
            self.session.get(BrokerConnection, broker_connection_id)
            if broker_connection_id
            else self.ensure_sandbox_connection()
        )
        if connection is None:
            raise ValueError("Broker connection not found")
        self._assert_sandbox_connection(connection)

        decision = self.session.get(RiskDecision, risk_decision_id)
        if decision is None:
            raise ValueError("Risk decision not found")
        if not decision.approved:
            raise ValueError("Order intent requires an approved risk decision")
        if decision.position_size is None or decision.risk_amount is None:
            raise ValueError("Risk decision must include position size and risk amount")
        signal = decision.signal
        if signal is None:
            raise ValueError("Risk decision is missing its signal")

        key = order_intent_key(connection.id, decision.id)
        existing = self.session.execute(
            select(OrderIntent).where(OrderIntent.idempotency_key == key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        intent = OrderIntent(
            signal=signal,
            risk_decision=decision,
            broker_connection=connection,
            strategy=signal.strategy,
            symbol=signal.symbol,
            direction=signal.direction,
            order_type="market",
            quantity=decision.position_size,
            requested_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            time_in_force="GTC",
            status=OrderIntentStatus.CREATED,
            idempotency_key=key,
            intent_snapshot={
                "sandbox_only": True,
                "signal_id": signal.id,
                "risk_decision_id": decision.id,
                "risk_amount": str(decision.risk_amount),
                "reward_risk": str(decision.reward_risk),
                "live_trading_enabled": self.settings.live_trading_enabled,
            },
            created_intent_at=utc_now(),
        )
        self.session.add(intent)
        self.session.flush()
        self._record_event(
            "Sandbox order intent created",
            {"order_intent_id": intent.id, "risk_decision_id": decision.id},
        )
        return intent

    def submit_sandbox_order(self, order_intent_id: str) -> BrokerOrder:
        intent = self.session.get(OrderIntent, order_intent_id)
        if intent is None:
            raise ValueError("Order intent not found")
        self._assert_sandbox_connection(intent.broker_connection)

        existing = self.session.execute(
            select(BrokerOrder).where(BrokerOrder.order_intent_id == intent.id)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        result = self.adapter.submit_order(intent)
        order = BrokerOrder(
            order_intent=intent,
            broker_connection=intent.broker_connection,
            external_order_id=result.external_order_id,
            status=result.status,
            symbol=intent.symbol,
            direction=intent.direction,
            quantity=intent.quantity,
            requested_price=intent.requested_price,
            filled_quantity=Decimal("0"),
            average_fill_price=None,
            submitted_at=result.submitted_at,
            external_updated_at=result.submitted_at,
            raw_payload=result.raw_payload,
        )
        intent.status = OrderIntentStatus.SUBMITTED
        self.session.add(order)
        self.session.flush()
        self._record_event(
            "Sandbox broker order submitted",
            {"broker_order_id": order.id, "order_intent_id": intent.id},
        )
        return order

    def simulate_fill(
        self,
        broker_order_id: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
        fees: Decimal | None = None,
    ) -> BrokerFill:
        order = self.session.get(BrokerOrder, broker_order_id)
        if order is None:
            raise ValueError("Broker order not found")
        self._assert_sandbox_connection(order.broker_connection)
        if order.status == BrokerOrderStatus.CANCELLED:
            raise ValueError("Cannot fill a cancelled broker order")

        existing = self.session.execute(
            select(BrokerFill).where(BrokerFill.broker_order_id == order.id)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        fill_quantity = quantity or order.quantity
        fill_price = price or order.requested_price
        fill_fees = fees
        if fill_fees is None:
            paper_order = self._paper_order_for_intent(order.order_intent)
            fill_fees = (
                (paper_order.fees * fill_quantity / order.quantity)
                if paper_order is not None and order.quantity > 0
                else Decimal("0")
            )
        result = self.adapter.simulate_fill(order, fill_quantity, fill_price, fill_fees)
        fill = BrokerFill(
            broker_order=order,
            external_fill_id=result.external_fill_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=result.quantity,
            price=result.price,
            fees=result.fees,
            filled_at=result.filled_at,
            raw_payload=result.raw_payload,
        )
        order.status = BrokerOrderStatus.FILLED
        order.filled_quantity = result.quantity
        order.average_fill_price = result.price
        order.external_updated_at = result.filled_at
        order.order_intent.status = OrderIntentStatus.FILLED
        self.session.add(fill)
        self.session.add(
            BrokerPositionSnapshot(
                broker_connection=order.broker_connection,
                symbol=order.symbol,
                direction=order.direction,
                quantity=result.quantity,
                average_entry_price=result.price,
                captured_at=result.filled_at,
                raw_payload={"source": "sandbox_fill", "broker_order_id": order.id},
            )
        )
        self.session.flush()
        self._record_event(
            "Sandbox broker order filled",
            {"broker_order_id": order.id, "external_fill_id": result.external_fill_id},
        )
        return fill

    def reconcile(self, broker_connection_id: str | None = None) -> BrokerReconciliationReport:
        connection = (
            self.session.get(BrokerConnection, broker_connection_id)
            if broker_connection_id
            else self.ensure_sandbox_connection()
        )
        if connection is None:
            raise ValueError("Broker connection not found")
        self._assert_sandbox_connection(connection)

        orders = list(
            self.session.execute(
                select(BrokerOrder).where(BrokerOrder.broker_connection_id == connection.id)
            ).scalars()
        )
        discrepancies: list[dict] = []
        latest_positions = self._latest_broker_position_snapshots(connection.id)
        open_positions = self._open_aurex_positions()
        broker_snapshot = {"orders": [], "fills": [], "positions": [], "costs": []}
        aurex_snapshot = {
            "order_intents": [],
            "paper_trades": [],
            "positions": [],
            "costs": [],
        }
        broker_fee_total = Decimal("0")
        aurex_order_fee_total = Decimal("0")

        for order in orders:
            intent = order.order_intent
            fills = list(
                self.session.execute(
                    select(BrokerFill).where(BrokerFill.broker_order_id == order.id)
                ).scalars()
            )
            fill_fees = broker_fill_fee_total(fills)
            broker_fee_total += fill_fees
            broker_snapshot["orders"].append(broker_order_snapshot(order))
            broker_snapshot["fills"].extend(broker_fill_snapshot(fill) for fill in fills)
            broker_snapshot["costs"].append(broker_cost_snapshot(order, fills))
            aurex_snapshot["order_intents"].append(order_intent_snapshot(intent))
            paper_order = self._paper_order_for_intent(intent)
            if paper_order is not None:
                paper_order_fees = paper_order.fees or Decimal("0")
                aurex_order_fee_total += paper_order_fees
                aurex_snapshot["costs"].append(paper_order_cost_snapshot(paper_order))

            if order.status != BrokerOrderStatus.FILLED:
                discrepancies.append({"order_id": order.id, "reason": "broker order not filled"})
                continue
            if paper_order is None:
                discrepancies.append({"order_id": order.id, "reason": "paper order missing"})
            elif fill_fees != (paper_order.fees or Decimal("0")):
                discrepancies.append(
                    {
                        "order_id": order.id,
                        "reason": "broker_fee_mismatch",
                        "broker_fees": str(fill_fees),
                        "aurex_order_fees": str(paper_order.fees or Decimal("0")),
                    }
                )
            if order.filled_quantity != intent.quantity:
                discrepancies.append({"order_id": order.id, "reason": "quantity mismatch"})
            if order.average_fill_price != intent.requested_price:
                discrepancies.append({"order_id": order.id, "reason": "fill price mismatch"})

            paper_trade = self._paper_trade_for_intent(intent)
            if paper_trade is None:
                discrepancies.append({"order_id": order.id, "reason": "paper trade missing"})
            else:
                aurex_snapshot["paper_trades"].append(paper_trade_snapshot(paper_trade))
                if paper_trade.quantity != order.filled_quantity:
                    discrepancies.append(
                        {"order_id": order.id, "reason": "paper trade quantity mismatch"}
                    )
                if paper_trade.entry_price != order.average_fill_price:
                    discrepancies.append(
                        {"order_id": order.id, "reason": "paper trade entry mismatch"}
                    )

        broker_snapshot["cost_summary"] = {"total_fill_fees": str(broker_fee_total)}
        aurex_snapshot["cost_summary"] = {"total_order_fees": str(aurex_order_fee_total)}
        broker_snapshot["positions"].extend(
            broker_position_snapshot(snapshot) for snapshot in latest_positions
        )
        aurex_snapshot["positions"].extend(
            aurex_position_snapshot(position) for position in open_positions
        )
        discrepancies.extend(position_sync_discrepancies(latest_positions, open_positions))

        if not orders:
            status = ReconciliationStatus.NOT_READY
            summary = "No sandbox broker orders are available to reconcile."
        elif discrepancies:
            status = ReconciliationStatus.DISCREPANCY
            summary = f"Found {len(discrepancies)} broker reconciliation discrepancies."
        else:
            status = ReconciliationStatus.MATCHED
            summary = "Sandbox broker orders, fills, and paper trades reconcile."

        report = BrokerReconciliationReport(
            broker_connection=connection,
            status=status,
            summary=summary,
            discrepancies=discrepancies,
            broker_snapshot=broker_snapshot,
            aurex_snapshot=aurex_snapshot,
            reconciled_at=utc_now(),
        )
        self.session.add(report)
        self.session.flush()
        self._upsert_check(
            "position_reconciliation",
            "Broker and Aurex position reconciliation",
            (
                ReadinessStatus.PASS
                if status == ReconciliationStatus.MATCHED
                else ReadinessStatus.FAIL
            ),
            {
                "report_id": report.id,
                "status": status.value,
                "discrepancies": discrepancies,
            },
            "Latest reconciliation must match before live readiness.",
        )
        if status == ReconciliationStatus.MATCHED:
            for order in orders:
                order.order_intent.status = OrderIntentStatus.RECONCILED
        self._record_event(
            "Broker reconciliation completed",
            {"status": status.value, "report_id": report.id},
        )
        self.session.flush()
        return report

    def latest_reconciliation_report(
        self,
        broker_connection_id: str,
    ) -> BrokerReconciliationReport | None:
        return self.session.execute(
            select(BrokerReconciliationReport)
            .where(BrokerReconciliationReport.broker_connection_id == broker_connection_id)
            .order_by(BrokerReconciliationReport.reconciled_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _latest_broker_position_snapshots(
        self,
        broker_connection_id: str,
    ) -> list[BrokerPositionSnapshot]:
        snapshots = list(
            self.session.execute(
                select(BrokerPositionSnapshot)
                .where(BrokerPositionSnapshot.broker_connection_id == broker_connection_id)
                .order_by(BrokerPositionSnapshot.captured_at.asc())
            ).scalars()
        )
        latest_by_key: dict[tuple[str, object], BrokerPositionSnapshot] = {}
        for snapshot in snapshots:
            latest_by_key[(snapshot.symbol, snapshot.direction)] = snapshot
        return list(latest_by_key.values())

    def _open_aurex_positions(self) -> list[Position]:
        return list(
            self.session.execute(
                select(Position).where(Position.status == PositionStatus.OPEN)
            ).scalars()
        )

    def run_readiness_checks(self) -> list[LiveReadinessCheck]:
        connection = self.ensure_sandbox_connection()
        now = utc_now()
        latest_report = self.latest_reconciliation_report(connection.id)
        has_fill = (
            self.session.execute(select(BrokerFill).limit(1)).scalar_one_or_none() is not None
        )
        emergency_tested = (
            self.session.execute(
                select(LiveReadinessCheck).where(
                    LiveReadinessCheck.check_key == "emergency_stop_tested",
                    LiveReadinessCheck.status == ReadinessStatus.PASS,
                )
            ).scalar_one_or_none()
            is not None
            or connection.status == BrokerConnectionStatus.EMERGENCY_STOPPED
        )

        checks = [
            (
                "live_trading_disabled",
                "Live trading disabled",
                (
                    ReadinessStatus.PASS
                    if not self.settings.live_trading_enabled
                    else ReadinessStatus.FAIL
                ),
                {"live_trading_enabled": self.settings.live_trading_enabled},
                "Live trading must remain disabled during readiness.",
            ),
            (
                "sandbox_connection_configured",
                "Sandbox broker connection configured",
                ReadinessStatus.PASS,
                {
                    "broker_connection_id": connection.id,
                    "environment": connection.environment.value,
                },
                "Sandbox broker is available for non-live validation.",
            ),
            (
                "sandbox_order_intent_test",
                "Sandbox order intent and fill test",
                ReadinessStatus.PASS if has_fill else ReadinessStatus.NOT_RUN,
                {"has_sandbox_fill": has_fill},
                "Create and fill at least one sandbox order intent.",
            ),
            (
                "position_reconciliation",
                "Broker and Aurex reconciliation",
                readiness_from_reconciliation(latest_report),
                {
                    "latest_report_id": latest_report.id if latest_report else None,
                    "latest_status": latest_report.status.value if latest_report else None,
                },
                "Latest reconciliation must match.",
            ),
            (
                "emergency_stop_tested",
                "Emergency stop path tested",
                ReadinessStatus.PASS if emergency_tested else ReadinessStatus.NOT_RUN,
                {"emergency_stop_tested": emergency_tested},
                "Emergency stop must be tested before live readiness.",
            ),
            (
                "paper_trading_gate",
                "Paper trading gate completed",
                ReadinessStatus.BLOCKED,
                {
                    "minimum_paper_trades_required": 100,
                    "live_mode_allowed": False,
                },
                "Paper-trading gate is intentionally blocked until evidence is complete.",
            ),
        ]
        for key, name, status, evidence, notes in checks:
            self._upsert_check(
                key,
                name,
                status,
                {**evidence, "checked_at": now.isoformat()},
                notes,
            )
        self.session.flush()
        return list(
            self.session.execute(
                select(LiveReadinessCheck).order_by(LiveReadinessCheck.check_key.asc())
            ).scalars()
        )

    def emergency_stop(self) -> EmergencyStopResponse:
        connections = list(self.session.execute(select(BrokerConnection)).scalars())
        cancelled_orders = 0
        cancelled_intents = 0
        for connection in connections:
            connection.status = BrokerConnectionStatus.EMERGENCY_STOPPED
            connection.live_trading_enabled = False

        for order in self.session.execute(select(BrokerOrder)).scalars():
            if order.status in {BrokerOrderStatus.CREATED, BrokerOrderStatus.SUBMITTED}:
                order.status = BrokerOrderStatus.CANCELLED
                cancelled_orders += 1

        for intent in self.session.execute(select(OrderIntent)).scalars():
            if intent.status in {OrderIntentStatus.CREATED, OrderIntentStatus.SUBMITTED}:
                intent.status = OrderIntentStatus.CANCELLED
                cancelled_intents += 1

        _, risk_profile = RiskEngine(self.session).get_or_create_default_profile()
        risk_profile.kill_switch_enabled = True
        self._upsert_check(
            "emergency_stop_tested",
            "Emergency stop path tested",
            ReadinessStatus.PASS,
            {
                "affected_connections": len(connections),
                "cancelled_orders": cancelled_orders,
                "cancelled_intents": cancelled_intents,
            },
            "Emergency stop was executed in sandbox readiness mode.",
        )
        self._record_event(
            "Broker emergency stop executed",
            {
                "affected_connections": len(connections),
                "cancelled_orders": cancelled_orders,
                "cancelled_intents": cancelled_intents,
            },
        )
        self.session.flush()
        return EmergencyStopResponse(
            live_trading_enabled=self.settings.live_trading_enabled,
            affected_connections=len(connections),
            cancelled_orders=cancelled_orders,
            cancelled_intents=cancelled_intents,
            kill_switch_enabled=risk_profile.kill_switch_enabled,
            message="Sandbox broker emergency stop executed; risk kill switch is enabled.",
        )

    def list_order_intents(self) -> list[OrderIntent]:
        return list(
            self.session.execute(
                select(OrderIntent).order_by(OrderIntent.created_intent_at.desc())
            ).scalars()
        )

    def list_broker_orders(self) -> list[BrokerOrder]:
        return list(
            self.session.execute(select(BrokerOrder).order_by(BrokerOrder.created_at.desc())).scalars()
        )

    def list_reconciliation_reports(self) -> list[BrokerReconciliationReport]:
        return list(
            self.session.execute(
                select(BrokerReconciliationReport).order_by(
                    BrokerReconciliationReport.reconciled_at.desc()
                )
            ).scalars()
        )

    def _paper_trade_for_intent(self, intent: OrderIntent) -> PaperTrade | None:
        if intent.signal_id is None:
            return None
        return self.session.execute(
            select(PaperTrade)
            .join(PaperOrder, PaperTrade.paper_order_id == PaperOrder.id)
            .where(
                PaperOrder.signal_id == intent.signal_id,
                PaperTrade.status.in_([TradeStatus.OPEN, TradeStatus.CLOSED]),
            )
            .limit(1)
        ).scalar_one_or_none()

    def _paper_order_for_intent(self, intent: OrderIntent) -> PaperOrder | None:
        if intent.signal_id is None:
            return None
        return self.session.execute(
            select(PaperOrder)
            .where(
                PaperOrder.signal_id == intent.signal_id,
                PaperOrder.risk_decision_id == intent.risk_decision_id,
            )
            .limit(1)
        ).scalar_one_or_none()

    def _assert_sandbox_connection(self, connection: BrokerConnection) -> None:
        if connection.environment != BrokerEnvironment.SANDBOX:
            raise ValueError("Only sandbox broker connections are allowed in Stage 13")
        if connection.live_trading_enabled:
            raise ValueError("Broker connection has live trading enabled")

    def _upsert_check(
        self,
        check_key: str,
        name: str,
        status: ReadinessStatus,
        evidence_snapshot: dict,
        notes: str,
        required: bool = True,
    ) -> LiveReadinessCheck:
        check = self.session.execute(
            select(LiveReadinessCheck).where(LiveReadinessCheck.check_key == check_key)
        ).scalar_one_or_none()
        if check is None:
            check = LiveReadinessCheck(check_key=check_key, name=name)
            self.session.add(check)
        check.name = name
        check.status = status
        check.required = required
        check.evidence_snapshot = evidence_snapshot
        check.notes = notes
        check.last_checked_at = utc_now()
        return check

    def _record_event(self, message: str, metadata: dict) -> None:
        SystemEventRecorder(self.session).info("broker_readiness", message, metadata)


def order_intent_key(broker_connection_id: str, risk_decision_id: str) -> str:
    raw = f"{broker_connection_id}|{risk_decision_id}|sandbox"
    return sha256(raw.encode("utf-8")).hexdigest()


def readiness_from_reconciliation(
    report: BrokerReconciliationReport | None,
) -> ReadinessStatus:
    if report is None:
        return ReadinessStatus.NOT_RUN
    if report.status == ReconciliationStatus.MATCHED:
        return ReadinessStatus.PASS
    return ReadinessStatus.FAIL


def order_intent_snapshot(intent: OrderIntent) -> dict[str, object]:
    return {
        "id": intent.id,
        "signal_id": intent.signal_id,
        "risk_decision_id": intent.risk_decision_id,
        "symbol": intent.symbol,
        "direction": intent.direction.value,
        "quantity": str(intent.quantity),
        "requested_price": str(intent.requested_price),
        "status": intent.status.value,
    }


def broker_order_snapshot(order: BrokerOrder) -> dict[str, object]:
    return {
        "id": order.id,
        "external_order_id": order.external_order_id,
        "symbol": order.symbol,
        "direction": order.direction.value,
        "quantity": str(order.quantity),
        "filled_quantity": str(order.filled_quantity),
        "requested_price": str(order.requested_price),
        "average_fill_price": str(order.average_fill_price),
        "status": order.status.value,
    }


def broker_fill_snapshot(fill: BrokerFill) -> dict[str, object]:
    return {
        "id": fill.id,
        "external_fill_id": fill.external_fill_id,
        "broker_order_id": fill.broker_order_id,
        "symbol": fill.symbol,
        "quantity": str(fill.quantity),
        "price": str(fill.price),
        "fees": str(fill.fees),
        "filled_at": fill.filled_at.isoformat(),
    }


def broker_fill_fee_total(fills: list[BrokerFill]) -> Decimal:
    return sum((fill.fees or Decimal("0") for fill in fills), Decimal("0"))


def broker_implied_slippage(order: BrokerOrder) -> Decimal:
    if order.average_fill_price is None:
        return Decimal("0")
    return order.average_fill_price - order.requested_price


def broker_cost_snapshot(order: BrokerOrder, fills: list[BrokerFill]) -> dict[str, object]:
    return {
        "order_id": order.id,
        "external_order_id": order.external_order_id,
        "fill_count": len(fills),
        "total_fill_fees": str(broker_fill_fee_total(fills)),
        "implied_slippage": str(broker_implied_slippage(order)),
    }


def paper_order_cost_snapshot(order: PaperOrder) -> dict[str, object]:
    return {
        "paper_order_id": order.id,
        "signal_id": order.signal_id,
        "risk_decision_id": order.risk_decision_id,
        "fees": str(order.fees),
        "slippage": str(order.slippage),
    }


def paper_trade_snapshot(trade: PaperTrade) -> dict[str, object]:
    return {
        "id": trade.id,
        "paper_order_id": trade.paper_order_id,
        "symbol": trade.symbol,
        "quantity": str(trade.quantity),
        "entry_price": str(trade.entry_price),
        "fees": str(trade.fees),
        "slippage": str(trade.slippage),
        "status": trade.status.value,
    }


def broker_position_snapshot(snapshot: BrokerPositionSnapshot) -> dict[str, object]:
    return {
        "id": snapshot.id,
        "symbol": snapshot.symbol,
        "direction": snapshot.direction.value,
        "quantity": str(snapshot.quantity),
        "average_entry_price": str(snapshot.average_entry_price),
        "captured_at": snapshot.captured_at.isoformat(),
    }


def aurex_position_snapshot(position: Position) -> dict[str, object]:
    return {
        "id": position.id,
        "symbol": position.symbol,
        "direction": position.direction.value,
        "quantity": str(position.quantity),
        "average_entry_price": str(position.average_entry_price),
        "status": position.status.value,
    }


def position_sync_discrepancies(
    broker_positions: list[BrokerPositionSnapshot],
    aurex_positions: list[Position],
) -> list[dict[str, str]]:
    discrepancies: list[dict[str, str]] = []
    aurex_by_key = {
        (position.symbol, position.direction): position for position in aurex_positions
    }
    broker_by_key = {
        (snapshot.symbol, snapshot.direction): snapshot for snapshot in broker_positions
    }

    for key, snapshot in broker_by_key.items():
        position = aurex_by_key.get(key)
        if position is None:
            discrepancies.append(
                {
                    "symbol": snapshot.symbol,
                    "direction": snapshot.direction.value,
                    "reason": "aurex_position_missing",
                }
            )
            continue
        if snapshot.quantity != position.quantity:
            discrepancies.append(
                {
                    "symbol": snapshot.symbol,
                    "direction": snapshot.direction.value,
                    "reason": "position_quantity_mismatch",
                }
            )
        if snapshot.average_entry_price != position.average_entry_price:
            discrepancies.append(
                {
                    "symbol": snapshot.symbol,
                    "direction": snapshot.direction.value,
                    "reason": "position_entry_price_mismatch",
                }
            )

    for key, position in aurex_by_key.items():
        if key not in broker_by_key:
            discrepancies.append(
                {
                    "symbol": position.symbol,
                    "direction": position.direction.value,
                    "reason": "broker_position_missing",
                }
            )

    return discrepancies
