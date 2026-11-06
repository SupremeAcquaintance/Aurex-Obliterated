"""Conservative admission policy for the initial native BTCUSDT paper account.

This is modeled stop risk, not protection against gaps or an exchange execution
filter. Historical replay and imported evidence retain their original semantics.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.config.settings import Settings
from aurex.db.models import (
    Account,
    PaperOrder,
    PaperTrade,
    Position,
    RiskProfile,
    Signal,
    StrategyConfig,
)
from aurex.domain.enums import Direction, PositionStatus, TradeStatus
from aurex.execution_engine.costs import MONEY_QUANTUM, modeled_execution_costs

POLICY_VERSION = "native_btcusdt_spot_paper_v1"
INITIAL_CAPITAL = Decimal("100")
MAX_TRADE_RISK = Decimal("0.005")
MAX_DAILY_LOSS = Decimal("0.01")
MAX_WEEKLY_LOSS = Decimal("0.03")
MAX_TOTAL_LOSS = Decimal("0.10")
QUANTITY_QUANTUM = Decimal("0.000000000001")
ROUNDING_RESERVE = MONEY_QUANTUM * 5


@dataclass(frozen=True)
class NativeSpotSizing:
    quantity: Decimal
    modeled_stop_loss: Decimal
    net_reward_risk: Decimal
    snapshot: dict[str, object]


def cost_parameters(settings: Settings) -> dict[str, Decimal]:
    costs = {
        "commission_bps": settings.paper_commission_bps,
        "half_spread_bps": settings.paper_half_spread_bps,
        "market_impact_bps": settings.paper_market_impact_bps,
    }
    floors = (Decimal("10"), Decimal("2.5"), Decimal("2.5"))
    if any(
        not value.is_finite() or value < floor
        for value, floor in zip(costs.values(), floors, strict=True)
    ):
        raise ValueError("Native spot costs cannot fall below the paper cost floors")
    return costs


def size_native_spot(
    *,
    entry: Decimal,
    stop: Decimal,
    target: Decimal,
    available_quote: Decimal,
    risk_budget: Decimal,
    minimum_reward_risk: Decimal,
    settings: Settings,
) -> NativeSpotSizing:
    values = (entry, stop, target, available_quote, risk_budget, minimum_reward_risk)
    if any(not value.is_finite() or value <= 0 for value in values):
        raise ValueError("Native spot prices, quote balance and risk budget must be positive")
    if any(
        price >= Decimal("1000000000000") or price != price.quantize(MONEY_QUANTUM)
        for price in (entry, stop, target)
    ):
        raise ValueError("Native spot prices exceed the ledger's 8-decimal precision or range")
    if not stop < entry < target:
        raise ValueError("Native spot requires long-only price geometry")
    costs = cost_parameters(settings)
    rate = sum(costs.values()) / Decimal("10000")
    # Reserve all four rounded entry/exit cost components plus final P&L rounding.
    unit_loss = entry - stop + (entry + stop) * rate
    risk_quantity = (risk_budget - ROUNDING_RESERVE) / unit_loss
    cash_quantity = (available_quote - ROUNDING_RESERVE) / (entry * (1 + rate))
    quantity = min(risk_quantity, cash_quantity).quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
    if quantity <= 0:
        raise ValueError("Native spot budget is below internal quantity precision")
    entry_fees, entry_slippage = modeled_execution_costs(price=entry, quantity=quantity, **costs)
    stop_fees, stop_slippage = modeled_execution_costs(price=stop, quantity=quantity, **costs)
    target_fees, target_slippage = modeled_execution_costs(price=target, quantity=quantity, **costs)
    loss = (
        (entry - stop) * quantity + entry_fees + entry_slippage + stop_fees + stop_slippage
    ).quantize(MONEY_QUANTUM, rounding=ROUND_UP)
    cash_required = entry * quantity + entry_fees + entry_slippage
    net_reward = (
        (target - entry) * quantity - entry_fees - entry_slippage - target_fees - target_slippage
    ).quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)
    if loss <= 0 or loss > risk_budget or cash_required > available_quote:
        raise ValueError("Native spot rounded size exceeds a risk or cash budget")
    net_reward_risk = net_reward / loss
    if net_reward_risk < minimum_reward_risk:
        raise ValueError("Native spot net reward:risk is below minimum after costs")
    return NativeSpotSizing(
        quantity=quantity,
        modeled_stop_loss=loss,
        net_reward_risk=net_reward_risk,
        snapshot={
            "policy_version": POLICY_VERSION,
            "risk_semantics": "modeled_loss_at_stop_including_entry_and_exit_costs",
            "gap_loss_guaranteed": False,
            "venue_filters_verified": False,
            "account_unit_assumption": "USD_USDT_PAR_PAPER_ONLY",
            "max_leverage": "1",
            "entry_price": str(entry),
            "stop_price": str(stop),
            "target_price": str(target),
            "quantity": str(quantity),
            "available_quote": str(available_quote),
            "cash_required": str(cash_required),
            "risk_budget": str(risk_budget),
            "modeled_stop_loss": str(loss),
            "net_reward_risk": str(net_reward_risk),
            "entry_fees": str(entry_fees),
            "entry_slippage": str(entry_slippage),
            "stop_exit_fees": str(stop_fees),
            "stop_exit_slippage": str(stop_slippage),
            "costs": {key: str(value) for key, value in costs.items()},
            "latency_ms": settings.paper_latency_ms,
        },
    )


def evaluate_native_spot(
    session: Session,
    settings: Settings,
    signal: Signal,
    account: Account,
    profile: RiskProfile,
    strategy: StrategyConfig,
    now: datetime,
) -> NativeSpotSizing:
    if settings.live_trading_enabled or settings.live_execution_adapter != "disabled":
        raise ValueError("Native spot paper policy requires live execution disabled")
    if signal.symbol != "BTCUSDT" or signal.direction != Direction.LONG:
        raise ValueError("Native spot is restricted to BTCUSDT LONG; no borrowing or shorts")
    # SQLite intake holds a write lock; row-locking databases serialize on account.
    session.execute(select(Account.id).where(Account.id == account.id).with_for_update())
    session.refresh(account)
    if account.mode != "paper" or account.currency not in {"USD", "USDT"}:
        raise ValueError("Native spot requires a USD/USDT paper account")
    if account.starting_equity != INITIAL_CAPITAL:
        raise ValueError("Native spot requires an explicitly configured 100-unit starting account")

    orphan_order = session.scalar(
        select(PaperOrder.id)
        .outerjoin(PaperTrade, PaperTrade.paper_order_id == PaperOrder.id)
        .where(PaperTrade.id.is_(None))
        .limit(1)
    )
    if orphan_order is not None:
        # Orders without trades have no reliable account ownership or exposure.
        raise ValueError("Native spot ledger contains an orphan paper order")

    trades = list(session.scalars(select(PaperTrade).where(PaperTrade.account_id == account.id)))
    positions = list(
        session.scalars(
            select(Position).where(
                Position.account_id == account.id, Position.status == PositionStatus.OPEN
            )
        )
    )
    opened = [trade for trade in trades if trade.status == TradeStatus.OPEN]
    if opened or positions:
        raise ValueError("Native spot permits only one open paper position per account")
    closed = [trade for trade in trades if trade.status == TradeStatus.CLOSED]
    for trade in closed:
        if trade.realized_pl is None or trade.closed_at is None:
            raise ValueError("Native spot closed-trade ledger is incomplete")
        if as_utc(trade.closed_at) > now:
            raise ValueError("Native spot closed-trade ledger contains a future timestamp")
    total_pl = sum((trade.realized_pl for trade in closed), Decimal("0"))
    if abs(account.current_equity - (account.starting_equity + total_pl)) > MONEY_QUANTUM:
        raise ValueError("Native spot equity does not reconcile with the closed-trade ledger")
    equity = min(account.current_equity, account.starting_equity)
    if not equity.is_finite() or equity <= 0:
        raise ValueError("Native spot account equity must be positive")
    start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    week = start - timedelta(days=start.weekday())
    daily_pl = sum(
        (trade.realized_pl for trade in closed if as_utc(trade.closed_at) >= start), Decimal("0")
    )
    weekly_pl = sum(
        (trade.realized_pl for trade in closed if as_utc(trade.closed_at) >= week), Decimal("0")
    )
    strategy_pl = sum(
        (trade.realized_pl for trade in closed if trade.strategy == signal.strategy), Decimal("0")
    )
    risk_fraction = min(
        MAX_TRADE_RISK,
        profile.risk_per_trade,
        strategy.risk_per_trade if strategy.risk_per_trade is not None else profile.risk_per_trade,
    )
    budgets = {
        "per_trade": equity * risk_fraction,
        "daily_remaining": equity * min(profile.max_daily_loss, MAX_DAILY_LOSS)
        + min(Decimal("0"), daily_pl),
        "weekly_remaining": equity * min(profile.max_weekly_loss, MAX_WEEKLY_LOSS)
        + min(Decimal("0"), weekly_pl),
        "strategy_remaining": INITIAL_CAPITAL * MAX_TOTAL_LOSS + min(Decimal("0"), strategy_pl),
        "account_remaining": INITIAL_CAPITAL * MAX_TOTAL_LOSS + min(Decimal("0"), total_pl),
    }
    for name, value in budgets.items():
        if not value.is_finite() or value <= ROUNDING_RESERVE:
            raise ValueError(f"Native spot {name} loss budget exhausted")
    result = size_native_spot(
        entry=signal.entry_price,
        stop=signal.stop_loss,
        target=signal.take_profit,
        available_quote=account.current_equity,
        risk_budget=min(budgets.values()),
        minimum_reward_risk=max(
            profile.minimum_reward_risk,
            strategy.minimum_reward_risk or profile.minimum_reward_risk,
        ),
        settings=settings,
    )
    result.snapshot.update(
        {
            "loss_budgets": {key: str(value) for key, value in budgets.items()},
            "current_equity": str(account.current_equity),
            "starting_equity": str(account.starting_equity),
            "max_open_positions": 1,
            "closed_trade_count": len(closed),
            "realized_pl": {
                "daily": str(daily_pl),
                "weekly": str(weekly_pl),
                "strategy": str(strategy_pl),
                "account": str(total_pl),
            },
        }
    )
    return result


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
