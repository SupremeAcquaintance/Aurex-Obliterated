import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from aurex.config.settings import Settings, get_settings
from aurex.db.base import utc_now
from aurex.db.models import (
    Account,
    EquityCurvePoint,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
    Signal,
    SignalEvent,
)
from aurex.domain.enums import (
    Direction,
    OrderStatus,
    PositionStatus,
    SignalStatus,
    TradeStatus,
)
from aurex.execution_engine.costs import modeled_execution_costs, quantized_money
from aurex.observability.system_events import SystemEventRecorder
from aurex.risk_engine.service import RiskEngine, ensure_utc

DETERMINISTIC_PAPER_FILL_MODEL = "deterministic_costed_market_v1"
IMPORTED_PAPER_FILL_MODEL = "paper_evidence_import"
EVIDENCE_GRADE_PAPER_FILL_MODELS = frozenset(
    {DETERMINISTIC_PAPER_FILL_MODEL, IMPORTED_PAPER_FILL_MODEL}
)
PAPER_EXECUTION_SCHEMA_VERSION = "paper_execution_v1"


@dataclass(frozen=True)
class PaperExecutionResult:
    order: PaperOrder
    trade: PaperTrade
    position: Position


def normalized_decimal_text(value: Decimal) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def normalized_datetime_text(value: datetime) -> str:
    return ensure_utc(value).isoformat()


def paper_execution_evidence_hash(snapshot: dict[str, object]) -> str:
    encoded = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def open_execution_assumptions_snapshot(
    *,
    requested_price: Decimal,
    quantity: Decimal,
    fees: Decimal,
    slippage: Decimal,
    filled_at: datetime,
    settings: Settings,
) -> dict[str, object]:
    return {
        "schema_version": PAPER_EXECUTION_SCHEMA_VERSION,
        "fill_model": DETERMINISTIC_PAPER_FILL_MODEL,
        "lifecycle_status": "OPEN",
        "price_semantics": "reference_prices_with_costs_recorded_separately",
        "cost_floor_enforced": True,
        "assumptions": {
            "commission_bps": normalized_decimal_text(settings.paper_commission_bps),
            "half_spread_bps": normalized_decimal_text(settings.paper_half_spread_bps),
            "market_impact_bps": normalized_decimal_text(
                settings.paper_market_impact_bps
            ),
            "latency_ms": settings.paper_latency_ms,
        },
        "entry": {
            "requested_price": normalized_decimal_text(requested_price),
            "filled_price": normalized_decimal_text(requested_price),
            "quantity": normalized_decimal_text(quantity),
            "fees": normalized_decimal_text(fees),
            "slippage": normalized_decimal_text(slippage),
            "filled_at": normalized_datetime_text(filled_at),
        },
        "exit": None,
        "total_fees": normalized_decimal_text(fees),
        "total_slippage": normalized_decimal_text(slippage),
    }


def imported_execution_assumptions_snapshot(
    *,
    source_reference: str,
    import_evidence_hash: str,
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
    opened_at: datetime,
    closed_at: datetime,
    fees: Decimal,
    slippage: Decimal,
) -> dict[str, object]:
    return {
        "schema_version": PAPER_EXECUTION_SCHEMA_VERSION,
        "fill_model": IMPORTED_PAPER_FILL_MODEL,
        "lifecycle_status": "CLOSED",
        "price_semantics": "external_fill_prices_with_reported_costs",
        "cost_floor_enforced": False,
        "source_verified_by_hash": True,
        "source_reference": source_reference,
        "import_evidence_hash": import_evidence_hash,
        "assumptions": {"source": "paper_evidence_import"},
        "entry": {
            "requested_price": normalized_decimal_text(entry_price),
            "filled_price": normalized_decimal_text(entry_price),
            "quantity": normalized_decimal_text(quantity),
            "fees": "0",
            "slippage": "0",
            "filled_at": normalized_datetime_text(opened_at),
        },
        "exit": {
            "reference_price": normalized_decimal_text(exit_price),
            "fees": normalized_decimal_text(fees),
            "slippage": normalized_decimal_text(slippage),
            "closed_at": normalized_datetime_text(closed_at),
            "cost_source": "external_evidence",
        },
        "total_fees": normalized_decimal_text(fees),
        "total_slippage": normalized_decimal_text(slippage),
    }


def execution_cost_assumptions(
    snapshot: object,
    fallback_settings: Settings,
) -> dict[str, Decimal | int]:
    assumptions = snapshot.get("assumptions") if isinstance(snapshot, dict) else None
    assumptions = assumptions if isinstance(assumptions, dict) else {}
    return {
        "commission_bps": Decimal(
            str(assumptions.get("commission_bps", fallback_settings.paper_commission_bps))
        ),
        "half_spread_bps": Decimal(
            str(assumptions.get("half_spread_bps", fallback_settings.paper_half_spread_bps))
        ),
        "market_impact_bps": Decimal(
            str(
                assumptions.get(
                    "market_impact_bps",
                    fallback_settings.paper_market_impact_bps,
                )
            )
        ),
        "latency_ms": int(
            assumptions.get("latency_ms", fallback_settings.paper_latency_ms)
        ),
    }


def conservative_cost_floor(
    provided: Decimal | None,
    modeled: Decimal,
) -> Decimal:
    if provided is None:
        return modeled
    return quantized_money(max(provided, modeled))


def close_execution_assumptions_snapshot(
    *,
    order: PaperOrder,
    exit_price: Decimal,
    closed_at: datetime,
    modeled_fees: Decimal,
    modeled_slippage: Decimal,
    provided_fees: Decimal | None,
    provided_slippage: Decimal | None,
    effective_fees: Decimal,
    effective_slippage: Decimal,
    total_fees: Decimal,
    total_slippage: Decimal,
    fallback_settings: Settings,
) -> dict[str, object]:
    current = order.execution_assumptions
    snapshot = json.loads(json.dumps(current)) if isinstance(current, dict) else {}
    assumptions = execution_cost_assumptions(snapshot, fallback_settings)
    snapshot.update(
        {
            "schema_version": PAPER_EXECUTION_SCHEMA_VERSION,
            "fill_model": order.fill_model,
            "lifecycle_status": "CLOSED",
            "price_semantics": "reference_prices_with_costs_recorded_separately",
            "cost_floor_enforced": order.fill_model == DETERMINISTIC_PAPER_FILL_MODEL,
            "assumptions": {
                "commission_bps": normalized_decimal_text(
                    Decimal(str(assumptions["commission_bps"]))
                ),
                "half_spread_bps": normalized_decimal_text(
                    Decimal(str(assumptions["half_spread_bps"]))
                ),
                "market_impact_bps": normalized_decimal_text(
                    Decimal(str(assumptions["market_impact_bps"]))
                ),
                "latency_ms": int(assumptions["latency_ms"]),
            },
            "exit": {
                "reference_price": normalized_decimal_text(exit_price),
                "modeled_fees": normalized_decimal_text(modeled_fees),
                "modeled_slippage": normalized_decimal_text(modeled_slippage),
                "provided_fees": (
                    normalized_decimal_text(provided_fees)
                    if provided_fees is not None
                    else None
                ),
                "provided_slippage": (
                    normalized_decimal_text(provided_slippage)
                    if provided_slippage is not None
                    else None
                ),
                "fees": normalized_decimal_text(effective_fees),
                "slippage": normalized_decimal_text(effective_slippage),
                "closed_at": normalized_datetime_text(closed_at),
                "cost_source": "modeled_floor",
            },
            "total_fees": normalized_decimal_text(total_fees),
            "total_slippage": normalized_decimal_text(total_slippage),
        }
    )
    if not isinstance(snapshot.get("entry"), dict):
        snapshot["entry"] = {
            "requested_price": normalized_decimal_text(order.requested_price),
            "filled_price": (
                normalized_decimal_text(order.filled_price)
                if order.filled_price is not None
                else None
            ),
            "quantity": normalized_decimal_text(order.quantity),
            "fees": normalized_decimal_text(order.fees),
            "slippage": normalized_decimal_text(order.slippage),
            "filled_at": (
                normalized_datetime_text(order.filled_at)
                if order.filled_at is not None
                else None
            ),
        }
    return snapshot


class PaperExecutionEngine:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def execute_approved_signal(
        self,
        signal: Signal,
        decision: RiskDecision,
        now: datetime | None = None,
    ) -> PaperExecutionResult:
        executed_at = ensure_utc(now or utc_now())
        if not decision.approved:
            raise ValueError("Paper execution requires risk approval")
        if decision.signal_id != signal.id:
            raise ValueError("Risk approval must belong to the executing signal")
        if decision.position_size is None or decision.risk_amount is None:
            raise ValueError("Risk approval must include position size and risk amount")
        if signal.stop_loss is None or signal.take_profit is None:
            raise ValueError("Paper execution requires stop loss and take profit")

        existing_order = self.session.execute(
            select(PaperOrder).where(PaperOrder.signal_id == signal.id).limit(1)
        ).scalar_one_or_none()
        if existing_order is not None:
            existing_trade = self.session.execute(
                select(PaperTrade).where(PaperTrade.paper_order_id == existing_order.id).limit(1)
            ).scalar_one()
            existing_position = self.session.execute(
                select(Position)
                .where(
                    Position.account_id == existing_trade.account_id,
                    Position.symbol == existing_trade.symbol,
                    Position.direction == existing_trade.direction,
                    Position.status == PositionStatus.OPEN,
                )
                .limit(1)
            ).scalar_one()
            return PaperExecutionResult(
                order=existing_order,
                trade=existing_trade,
                position=existing_position,
            )

        account, _ = RiskEngine(self.session).get_or_create_default_profile()
        if signal.source == "aurex_native":
            RiskEngine(self.session, self.settings).validate_native_paper_decision(
                signal, decision, now=executed_at
            )
        entry_fees, entry_slippage = modeled_execution_costs(
            price=signal.entry_price,
            quantity=decision.position_size,
            commission_bps=self.settings.paper_commission_bps,
            half_spread_bps=self.settings.paper_half_spread_bps,
            market_impact_bps=self.settings.paper_market_impact_bps,
        )
        execution_assumptions = open_execution_assumptions_snapshot(
            requested_price=signal.entry_price,
            quantity=decision.position_size,
            fees=entry_fees,
            slippage=entry_slippage,
            filled_at=executed_at,
            settings=self.settings,
        )
        order = PaperOrder(
            signal=signal,
            risk_decision_id=decision.id,
            symbol_id=signal.symbol_id,
            symbol=signal.symbol,
            direction=signal.direction,
            order_type="market",
            status=OrderStatus.FILLED,
            requested_price=signal.entry_price,
            filled_price=signal.entry_price,
            quantity=decision.position_size,
            fees=entry_fees,
            slippage=entry_slippage,
            fill_model=DETERMINISTIC_PAPER_FILL_MODEL,
            execution_assumptions=execution_assumptions,
            execution_assumptions_hash=paper_execution_evidence_hash(
                execution_assumptions
            ),
            created_order_at=executed_at,
            filled_at=executed_at,
        )
        self.session.add(order)
        self.session.flush()

        trade = PaperTrade(
            account=account,
            paper_order=order,
            strategy=signal.strategy,
            symbol_id=signal.symbol_id,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction,
            status=TradeStatus.OPEN,
            market_regime=signal.market_regime,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            quantity=decision.position_size,
            risk_amount=decision.risk_amount,
            opened_at=executed_at,
            fees=entry_fees,
            slippage=entry_slippage,
        )
        self.session.add(trade)

        position = Position(
            account=account,
            symbol_id=signal.symbol_id,
            symbol=signal.symbol,
            direction=signal.direction,
            status=PositionStatus.OPEN,
            quantity=decision.position_size,
            average_entry_price=signal.entry_price,
            opened_at=executed_at,
        )
        self.session.add(position)
        self.session.flush()

        self._record_equity_point(account, executed_at, Decimal("0"))
        self._add_signal_event(signal, SignalStatus.PAPER_ORDER_CREATED, "Paper order created")
        self._add_signal_event(signal, SignalStatus.PAPER_EXECUTED, "Paper trade opened")
        SystemEventRecorder(self.session).info(
            "paper_execution",
            "Paper trade opened",
            {
                "signal_id": signal.id,
                "paper_order_id": order.id,
                "paper_trade_id": trade.id,
                "position_id": position.id,
                "symbol": signal.symbol,
                "strategy": signal.strategy,
                "quantity": str(decision.position_size),
                "fill_model": order.fill_model,
                "entry_fees": str(entry_fees),
                "entry_slippage": str(entry_slippage),
                "execution_assumptions_hash": order.execution_assumptions_hash,
            },
            occurred_at=executed_at,
        )
        signal.status = SignalStatus.PAPER_EXECUTED
        signal.processed_at = executed_at
        self.session.flush()

        return PaperExecutionResult(order=order, trade=trade, position=position)

    def close_trade(
        self,
        trade_id: str,
        exit_price: Decimal,
        close_reason: str,
        fees: Decimal | None = None,
        slippage: Decimal | None = None,
        now: datetime | None = None,
    ) -> PaperTrade:
        closed_at = ensure_utc(now or utc_now())
        trade = self.session.get(PaperTrade, trade_id)
        if trade is None:
            raise ValueError("Paper trade not found")
        if trade.status == TradeStatus.CLOSED:
            raise ValueError("Paper trade is already closed")
        if exit_price <= 0:
            raise ValueError("Exit price must be positive")
        if fees is not None and fees < 0:
            raise ValueError("Fees and slippage cannot be negative")
        if slippage is not None and slippage < 0:
            raise ValueError("Fees and slippage cannot be negative")

        order = trade.paper_order
        assumptions = execution_cost_assumptions(order.execution_assumptions, self.settings)
        modeled_exit_fees, modeled_exit_slippage = modeled_execution_costs(
            price=exit_price,
            quantity=trade.quantity,
            commission_bps=assumptions["commission_bps"],
            half_spread_bps=assumptions["half_spread_bps"],
            market_impact_bps=assumptions["market_impact_bps"],
        )
        exit_fees = conservative_cost_floor(fees, modeled_exit_fees)
        exit_slippage = conservative_cost_floor(slippage, modeled_exit_slippage)
        total_fees = quantized_money((trade.fees or Decimal("0")) + exit_fees)
        total_slippage = quantized_money(
            (trade.slippage or Decimal("0")) + exit_slippage
        )

        gross_pl = calculate_trade_pl(
            trade.direction,
            trade.entry_price,
            exit_price,
            trade.quantity,
        )
        realized_pl = quantized_money(gross_pl - total_fees - total_slippage)
        trade.status = TradeStatus.CLOSED
        trade.exit_price = exit_price
        trade.closed_at = closed_at
        trade.realized_pl = realized_pl
        trade.r_multiple = realized_pl / trade.risk_amount if trade.risk_amount else None
        trade.fees = total_fees
        trade.slippage = total_slippage
        trade.close_reason = close_reason
        execution_assumptions = close_execution_assumptions_snapshot(
            order=order,
            exit_price=exit_price,
            closed_at=closed_at,
            modeled_fees=modeled_exit_fees,
            modeled_slippage=modeled_exit_slippage,
            provided_fees=fees,
            provided_slippage=slippage,
            effective_fees=exit_fees,
            effective_slippage=exit_slippage,
            total_fees=total_fees,
            total_slippage=total_slippage,
            fallback_settings=self.settings,
        )
        order.execution_assumptions = execution_assumptions
        order.execution_assumptions_hash = paper_execution_evidence_hash(
            execution_assumptions
        )

        account = trade.account
        account.current_equity = account.current_equity + realized_pl
        self._close_matching_position(trade, closed_at)
        self._record_equity_point(account, closed_at, realized_pl)
        SystemEventRecorder(self.session).info(
            "paper_execution",
            "Paper trade closed",
            {
                "paper_trade_id": trade.id,
                "symbol": trade.symbol,
                "strategy": trade.strategy,
                "realized_pl": str(realized_pl),
                "r_multiple": str(trade.r_multiple),
                "close_reason": close_reason,
                "total_fees": str(total_fees),
                "total_slippage": str(total_slippage),
                "execution_assumptions_hash": order.execution_assumptions_hash,
            },
            occurred_at=closed_at,
        )
        self.session.flush()
        return trade

    def reset_paper(self) -> dict[str, Decimal | int]:
        account, _ = RiskEngine(self.session).get_or_create_default_profile()

        deleted_trades = self.session.execute(delete(PaperTrade)).rowcount or 0
        deleted_orders = self.session.execute(delete(PaperOrder)).rowcount or 0
        deleted_positions = self.session.execute(delete(Position)).rowcount or 0
        deleted_equity_points = self.session.execute(delete(EquityCurvePoint)).rowcount or 0
        account.current_equity = account.starting_equity
        SystemEventRecorder(self.session).warning(
            "paper_execution",
            "Paper trading state reset",
            {
                "deleted_trades": deleted_trades,
                "deleted_orders": deleted_orders,
                "deleted_positions": deleted_positions,
                "deleted_equity_points": deleted_equity_points,
            },
        )
        self.session.flush()

        return {
            "account_equity": account.current_equity,
            "deleted_trades": deleted_trades,
            "deleted_orders": deleted_orders,
            "deleted_positions": deleted_positions,
            "deleted_equity_points": deleted_equity_points,
        }

    def _close_matching_position(self, trade: PaperTrade, closed_at: datetime) -> None:
        position = self.session.execute(
            select(Position)
            .where(
                Position.account_id == trade.account_id,
                Position.symbol == trade.symbol,
                Position.direction == trade.direction,
                Position.status == PositionStatus.OPEN,
            )
            .order_by(Position.opened_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if position is None:
            return

        position.status = PositionStatus.CLOSED
        position.closed_at = closed_at

    def _record_equity_point(
        self,
        account: Account,
        recorded_at: datetime,
        realized_pl: Decimal,
    ) -> None:
        previous_high = self.session.execute(
            select(func.max(EquityCurvePoint.equity)).where(
                EquityCurvePoint.account_id == account.id
            )
        ).scalar_one()
        high_water = max(previous_high or account.current_equity, account.current_equity)
        drawdown = max(Decimal("0"), high_water - account.current_equity)
        self.session.add(
            EquityCurvePoint(
                account_id=account.id,
                equity=account.current_equity,
                realized_pl=realized_pl,
                drawdown=drawdown,
                recorded_at=recorded_at,
            )
        )

    def _add_signal_event(self, signal: Signal, status: SignalStatus, message: str) -> None:
        self.session.add(
            SignalEvent(
                signal=signal,
                status=status,
                message=message,
                metadata_json={},
            )
        )


def calculate_trade_pl(
    direction: Direction,
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
) -> Decimal:
    if direction == Direction.LONG:
        return (exit_price - entry_price) * quantity
    return (entry_price - exit_price) * quantity
