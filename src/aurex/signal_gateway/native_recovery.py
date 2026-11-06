"""Exit-only OHLC recovery simulation. Never an entry path or forward qualification."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.reference_replay import (
    ExitFill,
    OpenReplayPosition,
    resolve_bracket_exit,
)
from aurex.config.settings import Settings
from aurex.db.models import NativeBarOutcome, PaperOrder, PaperTrade, Position, RiskDecision
from aurex.domain.enums import Direction, OrderStatus, PositionStatus, TradeStatus
from aurex.execution_engine.costs import modeled_execution_costs, quantized_money
from aurex.execution_engine.paper import (
    DETERMINISTIC_PAPER_FILL_MODEL,
    PaperExecutionEngine,
    execution_cost_assumptions,
    open_execution_assumptions_snapshot,
    paper_execution_evidence_hash,
)
from aurex.risk_engine.native_spot import INITIAL_CAPITAL, MONEY_QUANTUM, as_utc, cost_parameters
from aurex.signal_gateway.native_bars import BASE_SECONDS, ClosedBar, NativeBarError, aware_utc

RECOVERY_FILL_MODEL = "native_ohlc_recovery_v1"
ONLINE_EXIT_FILL_MODEL = "native_ohlc_online_exit_v1"
ZERO = Decimal("0")


class RecoveryPosition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    trade_id: str
    order_id: str
    position_id: str
    account_id: str
    entry_receipt_id: str
    entry_receipt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    risk_amount: Decimal = Field(gt=0)
    opened_at: datetime
    opening_assumptions: dict

    @field_validator("opened_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return aware_utc(value)

    @model_validator(mode="after")
    def validate_geometry(self) -> "RecoveryPosition":
        if not self.stop_loss < self.entry_price < self.take_profit:
            raise ValueError("recovery_position_geometry_invalid")
        return self


class NativeRecoveryEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["native_exit_only_recovery_v1"] = "native_exit_only_recovery_v1"
    entry_authority: Literal[False] = False
    forward_qualifying: Literal[False] = False
    disposition: Literal["FLAT", "HELD", "CLOSED"]
    position: RecoveryPosition | None = None
    partial_entry_bar: bool = Field(default=False, strict=True)
    exit_price: Decimal | None = Field(default=None, gt=0)
    exit_reason: str | None = None
    recognized_at: datetime | None = None
    total_fees: Decimal | None = Field(default=None, ge=0)
    total_slippage: Decimal | None = Field(default=None, ge=0)
    realized_pl: Decimal | None = None
    execution_hash_after: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("recognized_at")
    @classmethod
    def validate_time(cls, value: datetime | None) -> datetime | None:
        return aware_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> "NativeRecoveryEvidence":
        exit_fields = (
            self.exit_price,
            self.exit_reason,
            self.recognized_at,
            self.total_fees,
            self.total_slippage,
            self.realized_pl,
        )
        if self.disposition == "FLAT":
            if self.position is not None or self.partial_entry_bar or self.execution_hash_after:
                raise ValueError("flat_recovery_has_position")
        elif self.position is None or self.execution_hash_after is None:
            raise ValueError("recovery_position_evidence_missing")
        if self.disposition == "CLOSED":
            if any(value is None for value in exit_fields):
                raise ValueError("recovery_close_evidence_missing")
        elif any(value is not None for value in exit_fields):
            raise ValueError("unclosed_recovery_has_exit")
        return self


def recovery_exit(bar: ClosedBar, position: RecoveryPosition) -> ExitFill | None:
    """OHLC has no event ordering; partial entry bars use explicit adverse bounds."""
    if position.opened_at >= bar.timestamp + timedelta(seconds=BASE_SECONDS):
        raise NativeBarError("recovery_bar_does_not_follow_entry")
    if position.opened_at > bar.timestamp:
        if bar.low <= position.stop_loss:
            return ExitFill(bar.low, "PARTIAL_ENTRY_STOP_BOUND", ZERO, True)
        if bar.close >= position.take_profit:
            return ExitFill(position.take_profit, "PARTIAL_ENTRY_TARGET_AT_CLOSE", ZERO)
        return None
    return resolve_bracket_exit(
        bar,
        OpenReplayPosition(
            direction=Direction.LONG,
            entry_at=position.opened_at,
            signal_price=position.entry_price,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            quantity=position.quantity,
            entry_fee=ZERO,
            entry_slippage=ZERO,
            initial_risk=position.risk_amount,
            point_value=Decimal("1"),
            market_regime="UNKNOWN",
        ),
        tick_size=Decimal("0.00000001"),
        slippage_ticks=0,
    )


def position_snapshot(
    session: Session, trade: PaperTrade, position: Position, scope: dict, settings: Settings
) -> RecoveryPosition:
    order = trade.paper_order
    if order is None or order.signal is None:
        raise NativeBarError("recovery_order_or_signal_missing")
    signal = order.signal
    owners = list(
        session.scalars(
            select(NativeBarOutcome)
            .where(
                NativeBarOutcome.signal_id == signal.id,
                NativeBarOutcome.outcome == "PAPER_EXECUTED",
            )
            .limit(2)
        )
    )
    decision = session.get(RiskDecision, order.risk_decision_id)
    if (
        len(owners) != 1
        or owners[0].evidence.get("scope") != scope
        or signal.source != "aurex_native"
        or any(
            getattr(signal, key) != scope[key]
            for key in ("strategy", "strategy_version", "settings_fingerprint")
        )
        or trade.strategy != signal.strategy
        or trade.symbol != "BTCUSDT"
        or trade.timeframe != "15m"
        or signal.symbol != trade.symbol
        or signal.timeframe != trade.timeframe
        or trade.direction != Direction.LONG
        or order.direction != Direction.LONG
        or position.direction != Direction.LONG
        or order.symbol != trade.symbol
        or position.symbol != trade.symbol
        or position.account_id != trade.account_id
        or trade.entry_price != signal.entry_price
        or trade.stop_loss != signal.stop_loss
        or trade.take_profit != signal.take_profit
        or order.requested_price != trade.entry_price
        or order.filled_price != trade.entry_price
        or position.average_entry_price != trade.entry_price
        or order.quantity != trade.quantity
        or position.quantity != trade.quantity
        or order.status != OrderStatus.FILLED
        or order.filled_at is None
        or as_utc(order.filled_at) != as_utc(trade.opened_at)
        or as_utc(position.opened_at) != as_utc(trade.opened_at)
        or as_utc(trade.opened_at) < as_utc(signal.source_timestamp)
        or decision is None
        or not decision.approved
        or decision.signal_id != signal.id
        or decision.position_size != trade.quantity
        or decision.risk_amount != trade.risk_amount
        or order.fill_model
        not in {DETERMINISTIC_PAPER_FILL_MODEL, RECOVERY_FILL_MODEL, ONLINE_EXIT_FILL_MODEL}
        or not isinstance(order.execution_assumptions, dict)
        or order.execution_assumptions_hash
        != paper_execution_evidence_hash(order.execution_assumptions)
    ):
        raise NativeBarError("recovery_position_binding_invalid")
    if trade.status == TradeStatus.OPEN and any(
        value is not None
        for value in (
            trade.exit_price,
            trade.closed_at,
            trade.realized_pl,
            trade.close_reason,
            position.closed_at,
        )
    ):
        raise NativeBarError("recovery_open_position_has_close_fields")
    assumptions = order.execution_assumptions.get("assumptions")
    if (
        not isinstance(assumptions, dict)
        or set(assumptions)
        != {"commission_bps", "half_spread_bps", "market_impact_bps", "latency_ms"}
        or type(assumptions["latency_ms"]) is not int
        or assumptions["latency_ms"] < 0
    ):
        raise NativeBarError("recovery_frozen_cost_assumptions_invalid")
    frozen_costs = execution_cost_assumptions(order.execution_assumptions, settings)
    frozen_settings = settings.model_copy(
        update={
            "paper_commission_bps": frozen_costs["commission_bps"],
            "paper_half_spread_bps": frozen_costs["half_spread_bps"],
            "paper_market_impact_bps": frozen_costs["market_impact_bps"],
            "paper_latency_ms": frozen_costs["latency_ms"],
        }
    )
    costs = cost_parameters(frozen_settings)
    fees, slippage = modeled_execution_costs(
        price=trade.entry_price, quantity=trade.quantity, **costs
    )
    opening = open_execution_assumptions_snapshot(
        requested_price=trade.entry_price,
        quantity=trade.quantity,
        fees=fees,
        slippage=slippage,
        filled_at=as_utc(trade.opened_at),
        settings=frozen_settings,
    )
    current = order.execution_assumptions
    if (
        order.fees != fees
        or order.slippage != slippage
        or current.get("entry") != opening["entry"]
        or current.get("assumptions") != opening["assumptions"]
        or current.get("fill_model") != order.fill_model
        or (
            trade.status == TradeStatus.OPEN
            and (
                trade.fees != fees
                or trade.slippage != slippage
                or current != {**opening, "fill_model": order.fill_model}
            )
        )
    ):
        raise NativeBarError("recovery_entry_cost_evidence_invalid")
    return RecoveryPosition(
        trade_id=trade.id,
        order_id=order.id,
        position_id=position.id,
        account_id=trade.account_id,
        entry_receipt_id=owners[0].id,
        entry_receipt_hash=owners[0].evidence_hash,
        entry_price=trade.entry_price,
        stop_loss=trade.stop_loss,
        take_profit=trade.take_profit,
        quantity=trade.quantity,
        risk_amount=trade.risk_amount,
        opened_at=as_utc(trade.opened_at),
        opening_assumptions=opening,
    )


def reconcile_account(session: Session, trade: PaperTrade, now: datetime | None) -> None:
    account = trade.account
    if (
        account.mode != "paper"
        or account.currency not in {"USD", "USDT"}
        or account.starting_equity != INITIAL_CAPITAL
    ):
        raise NativeBarError("recovery_account_scope_invalid")
    total = ZERO
    for closed in session.scalars(
        select(PaperTrade).where(
            PaperTrade.account_id == account.id, PaperTrade.status == TradeStatus.CLOSED
        )
    ).yield_per(128):
        if (
            closed.realized_pl is None
            or closed.closed_at is None
            or (now is not None and as_utc(closed.closed_at) > now)
        ):
            raise NativeBarError("recovery_closed_ledger_invalid")
        total += closed.realized_pl
    if abs(account.current_equity - (account.starting_equity + total)) > MONEY_QUANTUM:
        raise NativeBarError("recovery_account_equity_mismatch")


def manage_recovery(
    session: Session, settings: Settings, scope: dict, bar: ClosedBar, now: datetime
) -> NativeRecoveryEvidence:
    """Called only inside the processor's locked transaction, with entries prohibited."""
    return _manage_position_exit(session, settings, scope, bar, now, RECOVERY_FILL_MODEL)


def _manage_position_exit(
    session: Session,
    settings: Settings,
    scope: dict,
    bar: ClosedBar,
    now: datetime,
    fill_model: str,
) -> NativeRecoveryEvidence:
    """Shared nonqualifying OHLC mechanics; callers supply their own admission evidence."""
    if fill_model not in {RECOVERY_FILL_MODEL, ONLINE_EXIT_FILL_MODEL}:
        raise NativeBarError("native_exit_fill_model_invalid")
    if settings.live_trading_enabled or settings.live_execution_adapter != "disabled":
        raise NativeBarError("recovery_requires_live_disabled")
    if not session.in_transaction():
        raise NativeBarError("recovery_requires_database_transaction")
    connection = session.connection()
    if (
        connection.dialect.name != "sqlite"
        or not connection.connection.driver_connection.in_transaction
    ):
        raise NativeBarError("recovery_requires_database_transaction")
    orphan = session.scalar(
        select(PaperOrder.id)
        .outerjoin(PaperTrade, PaperTrade.paper_order_id == PaperOrder.id)
        .where(PaperTrade.id.is_(None))
        .limit(1)
    )
    trades = list(
        session.scalars(select(PaperTrade).where(PaperTrade.status == TradeStatus.OPEN).limit(2))
    )
    positions = list(
        session.scalars(select(Position).where(Position.status == PositionStatus.OPEN).limit(2))
    )
    if orphan is not None or len(trades) != len(positions) or len(trades) > 1:
        raise NativeBarError("recovery_open_ledger_unreconciled")
    if not trades:
        return NativeRecoveryEvidence(disposition="FLAT")
    trade, position = trades[0], positions[0]
    snapshot = position_snapshot(session, trade, position, scope, settings)
    reconcile_account(session, trade, now)
    fill = recovery_exit(bar, snapshot)
    order = trade.paper_order
    if fill is not None:
        # close_trade applies the frozen entry cost assumptions; no second price slippage.
        PaperExecutionEngine(session, settings).close_trade(
            trade.id, fill.price, fill.reason, now=now
        )
    # Recovery quarantine is permanent for this position, even after timely observation resumes.
    if order.fill_model == RECOVERY_FILL_MODEL:
        fill_model = RECOVERY_FILL_MODEL
    order.fill_model = fill_model
    order.execution_assumptions = {
        **order.execution_assumptions,
        "fill_model": fill_model,
        "cost_floor_enforced": True,
    }
    order.execution_assumptions_hash = paper_execution_evidence_hash(order.execution_assumptions)
    session.flush()
    return NativeRecoveryEvidence(
        disposition="CLOSED" if fill else "HELD",
        position=snapshot,
        partial_entry_bar=snapshot.opened_at > bar.timestamp,
        exit_price=fill.price if fill else None,
        exit_reason=fill.reason if fill else None,
        recognized_at=now if fill else None,
        total_fees=trade.fees if fill else None,
        total_slippage=trade.slippage if fill else None,
        realized_pl=trade.realized_pl if fill else None,
        execution_hash_after=order.execution_assumptions_hash,
    )


def verify_recovery(
    session: Session,
    settings: Settings,
    scope: dict,
    bar: ClosedBar,
    evidence: NativeRecoveryEvidence,
    processed_at: datetime,
) -> None:
    _verify_position_exit(
        session, settings, scope, bar, evidence, processed_at, RECOVERY_FILL_MODEL
    )


def _verify_position_exit(
    session: Session,
    settings: Settings,
    scope: dict,
    bar: ClosedBar,
    evidence: NativeRecoveryEvidence,
    processed_at: datetime,
    fill_model: str,
) -> None:
    if evidence.position is None:
        return
    snapshot = evidence.position
    trade = session.get(PaperTrade, snapshot.trade_id)
    position = session.get(Position, snapshot.position_id)
    if (
        trade is None
        or position is None
        or position_snapshot(session, trade, position, scope, settings) != snapshot
    ):
        raise NativeBarError("recovery_saved_position_mismatch")
    reconcile_account(session, trade, None)
    fill = recovery_exit(bar, snapshot)
    if (
        evidence.disposition != ("CLOSED" if fill else "HELD")
        or evidence.partial_entry_bar != (snapshot.opened_at > bar.timestamp)
        or (
            trade.paper_order.fill_model != fill_model
            and not (
                fill_model == ONLINE_EXIT_FILL_MODEL
                and evidence.disposition == "HELD"
                and trade.paper_order.fill_model == RECOVERY_FILL_MODEL
            )
        )
    ):
        raise NativeBarError("recovery_saved_outcome_mismatch")
    if fill is None:
        held = {**snapshot.opening_assumptions, "fill_model": fill_model}
        if evidence.execution_hash_after != paper_execution_evidence_hash(held):
            raise NativeBarError("recovery_held_evidence_mismatch")
        return
    assumptions = execution_cost_assumptions(snapshot.opening_assumptions, settings)
    fees, slippage = modeled_execution_costs(
        price=fill.price,
        quantity=snapshot.quantity,
        **{
            key: assumptions[key]
            for key in ("commission_bps", "half_spread_bps", "market_impact_bps")
        },
    )
    entry = snapshot.opening_assumptions["entry"]
    fees = quantized_money(fees + Decimal(entry["fees"]))
    slippage = quantized_money(slippage + Decimal(entry["slippage"]))
    pl = quantized_money((fill.price - snapshot.entry_price) * snapshot.quantity - fees - slippage)
    if (
        trade.status != TradeStatus.CLOSED
        or position.status != PositionStatus.CLOSED
        or trade.exit_price != fill.price
        or evidence.exit_price != fill.price
        or trade.close_reason != fill.reason
        or evidence.exit_reason != fill.reason
        or trade.closed_at is None
        or position.closed_at is None
        or as_utc(trade.closed_at) != evidence.recognized_at
        or as_utc(position.closed_at) != evidence.recognized_at
        or not bar.timestamp + timedelta(seconds=BASE_SECONDS)
        <= evidence.recognized_at
        <= processed_at
        or trade.fees != fees
        or evidence.total_fees != fees
        or trade.slippage != slippage
        or evidence.total_slippage != slippage
        or trade.realized_pl != pl
        or evidence.realized_pl != pl
        or trade.paper_order.execution_assumptions_hash != evidence.execution_hash_after
    ):
        raise NativeBarError("recovery_close_ledger_mismatch")
