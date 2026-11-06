from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from aurex.db.models import PaperOrder, PaperTrade, RiskDecision, Signal
from aurex.domain.enums import Direction, MarketRegime, SignalStatus
from aurex.execution_engine.paper import PaperExecutionEngine
from aurex.risk_engine.service import RiskEngine
from aurex.signal_gateway.service import SignalIntakeService
from aurex.strategy_engine.service import StrategyPortfolioService
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import eligible_fixture as eligible_fixture
from tests.integration.test_native_signal_intake import session as session
from tests.integration.test_native_signal_intake import settings as settings
from tests.integration.test_risk_engine import add_closed_trade


def add_history(session, pl, *, days_ago=15, strategy="trend_pullback_v1"):
    engine = RiskEngine(session)
    account, _ = engine.get_or_create_default_profile()
    add_closed_trade(
        session, engine, NOW - timedelta(days=days_ago), Decimal(pl), NOW - timedelta(days=days_ago)
    )
    trade = session.scalars(select(PaperTrade).order_by(PaperTrade.created_at.desc())).first()
    trade.strategy = strategy
    account.current_equity += Decimal(pl)
    session.flush()


def pending_approval(session, settings):
    payload = native_payload()
    fields = payload.model_dump(exclude={"timestamp", "strategy_version", "settings_fingerprint"})
    signal = Signal(
        **fields,
        source_timestamp=NOW,
        received_at=NOW,
        status=SignalStatus.VALIDATED,
        idempotency_key="native-pending",
        raw_payload=payload.model_dump(mode="json"),
        normalized_payload=payload.model_dump(mode="json"),
    )
    session.add(signal)
    session.flush()
    decision = RiskEngine(session, settings).evaluate_signal(signal, now=NOW).decision
    assert decision.approved, decision.reason
    return signal, decision


@pytest.mark.parametrize(
    "pl,reason", [("-10", "strategy_remaining"), ("-11", "strategy_remaining")]
)
def test_total_strategy_loss_stops_native_entries(session, settings, eligible_fixture, pl, reason):
    add_history(session, pl)
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert reason in result.signal.rejection_reason


def test_other_strategy_loss_also_exhausts_account_budget(session, settings, eligible_fixture):
    add_history(session, "-10", strategy="other-strategy")
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "account_remaining" in result.signal.rejection_reason


def test_remaining_total_budget_reduces_size(session, settings, eligible_fixture):
    add_history(session, "-9.9")
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.PAPER_EXECUTED
    decision = session.scalars(
        select(RiskDecision).where(RiskDecision.signal_id == result.signal.id)
    ).one()
    assert Decimal("0") < decision.risk_amount <= Decimal("0.1")
    assert Decimal(
        decision.rules_snapshot["native_spot_budget"]["loss_budgets"]["strategy_remaining"]
    ) == Decimal("0.1")


def test_remaining_daily_budget_reserves_costs_before_entry(session, settings, eligible_fixture):
    add_history(session, "-0.9", days_ago=0)
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.PAPER_EXECUTED
    decision = session.scalars(
        select(RiskDecision).where(RiskDecision.signal_id == result.signal.id)
    ).one()
    assert decision.risk_amount <= Decimal("0.091")


def test_profile_overrides_cannot_raise_native_risk_caps(session, settings, eligible_fixture):
    _, profile = RiskEngine(session).get_or_create_default_profile()
    profile.risk_per_trade = Decimal("0.03")
    strategy = StrategyPortfolioService(session).get_config("trend_pullback_v1")
    strategy.risk_per_trade = Decimal("0.05")
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.PAPER_EXECUTED
    decision = session.scalars(select(RiskDecision)).one()
    assert decision.risk_amount <= Decimal("0.5")
    assert Decimal(decision.rules_snapshot["effective_risk_per_trade"]) == Decimal("0.005")


@pytest.mark.parametrize(
    "starting,equity,reason",
    [
        ("1000", "1000", "100-unit"),
        ("100", "99", "reconcile"),
    ],
)
def test_account_must_match_explicit_capital_and_ledger(
    session, settings, eligible_fixture, starting, equity, reason
):
    account, _ = RiskEngine(session).get_or_create_default_profile()
    account.starting_equity, account.current_equity = Decimal(starting), Decimal(equity)
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert reason in result.signal.rejection_reason
    assert session.scalars(select(PaperOrder)).all() == []


def test_policy_blocks_second_entry_even_if_profile_allows_more(
    session, settings, eligible_fixture
):
    _, profile = RiskEngine(session).get_or_create_default_profile()
    profile.max_open_positions = 5
    StrategyPortfolioService(session).get_config("trend_pullback_v1").max_open_positions = 5
    service = SignalIntakeService(
        session, settings.model_copy(update={"duplicate_cooldown_minutes": 0})
    )
    assert service.ingest_native(native_payload()).signal.status == SignalStatus.PAPER_EXECUTED
    result = service.ingest_native(native_payload(timestamp=NOW - timedelta(seconds=1)))
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "one open paper position" in result.signal.rejection_reason
    assert len(session.scalars(select(PaperOrder)).all()) == 1


def test_stop_exit_net_loss_stays_inside_recorded_modeled_budget(
    session, settings, eligible_fixture
):
    SignalIntakeService(session, settings).ingest_native(native_payload())
    trade = session.scalars(select(PaperTrade)).one()
    closed = PaperExecutionEngine(session, settings).close_trade(
        trade.id, Decimal("95"), "modeled stop fixture", now=NOW
    )
    assert -closed.realized_pl <= closed.risk_amount <= Decimal("0.5")
    assert closed.account.current_equity >= Decimal("99.5")


@pytest.mark.parametrize("change", ["costs", "kill", "quantity", "snapshot", "price", "equity"])
def test_execution_rechecks_approval_before_any_order(session, settings, eligible_fixture, change):
    signal, decision = pending_approval(session, settings)
    if change == "costs":
        settings = settings.model_copy(update={"paper_commission_bps": Decimal("15")})
    elif change == "kill":
        RiskEngine(session).set_kill_switch(True)
    elif change == "quantity":
        decision.position_size *= 2
    elif change == "snapshot":
        decision.rules_snapshot = {}
    elif change == "price":
        signal.entry_price = Decimal("100.1")
    else:
        RiskEngine(session).get_or_create_default_profile()[0].current_equity = Decimal("99")
    with pytest.raises(ValueError, match="Native paper approval"):
        PaperExecutionEngine(session, settings).execute_approved_signal(signal, decision, now=NOW)
    assert session.scalars(select(PaperOrder)).all() == []


def test_native_risk_refuses_borrowed_short_scope(session, settings, eligible_fixture):
    signal, _ = pending_approval(session, settings)
    signal.direction = Direction.SHORT
    signal.market_regime = MarketRegime.TRENDING_DOWN
    signal.stop_loss, signal.take_profit = Decimal("105"), Decimal("88")
    result = RiskEngine(session, settings).evaluate_signal(signal, now=NOW)
    assert result.decision.approved is False
    assert "BTCUSDT LONG" in result.decision.reason


def test_daily_cap_cannot_be_raised_by_profile(session, settings, eligible_fixture):
    _, profile = RiskEngine(session).get_or_create_default_profile()
    profile.max_daily_loss = Decimal("0.2")
    profile.max_weekly_loss = Decimal("0.2")
    add_history(session, "-1", days_ago=0)
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "daily_remaining" in result.signal.rejection_reason


def test_weekly_cap_cannot_be_raised_by_profile(session, settings, eligible_fixture):
    _, profile = RiskEngine(session).get_or_create_default_profile()
    profile.max_weekly_loss = Decimal("0.2")
    add_history(session, "-3", days_ago=1)
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "weekly_remaining" in result.signal.rejection_reason


def test_incomplete_closed_trade_cannot_hide_loss(session, settings, eligible_fixture):
    add_history(session, "-1")
    session.scalars(select(PaperTrade)).one().realized_pl = None
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "incomplete" in result.signal.rejection_reason


def test_future_closed_profit_cannot_fund_native_trade(session, settings, eligible_fixture):
    add_history(session, "1", days_ago=-1)
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "future timestamp" in result.signal.rejection_reason


def test_pending_approval_cannot_execute_after_another_fill(session, settings, eligible_fixture):
    signal, decision = pending_approval(session, settings)
    result = SignalIntakeService(session, settings).ingest_native(
        native_payload(timestamp=NOW - timedelta(seconds=1))
    )
    assert result.signal.status == SignalStatus.PAPER_EXECUTED
    with pytest.raises(ValueError, match="Native paper approval"):
        PaperExecutionEngine(session, settings).execute_approved_signal(signal, decision, now=NOW)
    assert len(session.scalars(select(PaperOrder)).all()) == 1


def test_missing_native_budget_is_not_a_legacy_approval(session, settings, eligible_fixture):
    signal, decision = pending_approval(session, settings)
    session.flush()
    session.expire_all()
    decision.rules_snapshot = {}
    with pytest.raises(ValueError, match="sizing evidence"):
        PaperExecutionEngine(session, settings).execute_approved_signal(signal, decision, now=NOW)
    assert session.scalars(select(PaperOrder)).all() == []


def test_profitable_history_does_not_increase_initial_trade_risk(
    session, settings, eligible_fixture
):
    add_history(session, "10")
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.PAPER_EXECUTED
    decision = session.scalars(
        select(RiskDecision).where(RiskDecision.signal_id == result.signal.id)
    ).one()
    assert decision.risk_amount <= Decimal("0.5")


def test_gap_loss_is_recorded_not_clipped_to_modeled_stop_budget(
    session, settings, eligible_fixture
):
    SignalIntakeService(session, settings).ingest_native(native_payload())
    trade = session.scalars(select(PaperTrade)).one()
    closed = PaperExecutionEngine(session, settings).close_trade(
        trade.id, Decimal("80"), "synthetic gap beyond stop", now=NOW
    )
    assert -closed.realized_pl > closed.risk_amount
    assert closed.account.current_equity == Decimal("100") + closed.realized_pl
    result = SignalIntakeService(session, settings).ingest_native(
        native_payload(timestamp=NOW - timedelta(seconds=1))
    )
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "Daily loss limit" in result.signal.rejection_reason


def test_risk_decision_cannot_be_used_for_another_signal(session, settings, eligible_fixture):
    signal, decision = pending_approval(session, settings)
    decision.signal_id = "not-the-approved-signal"
    with pytest.raises(ValueError, match="belong to the executing signal"):
        PaperExecutionEngine(session, settings).execute_approved_signal(signal, decision, now=NOW)
    assert session.scalars(select(PaperOrder)).all() == []


def test_orphan_order_is_not_treated_as_free_quote_balance(session, settings, eligible_fixture):
    signal, decision = pending_approval(session, settings)
    session.add(
        PaperOrder(
            signal=signal,
            risk_decision_id=decision.id,
            symbol="BTCUSDT",
            direction=Direction.LONG,
            requested_price=signal.entry_price,
            quantity=decision.position_size,
            created_order_at=NOW,
        )
    )
    session.flush()
    result = SignalIntakeService(session, settings).ingest_native(
        native_payload(timestamp=NOW - timedelta(seconds=1))
    )
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "orphan paper order" in result.signal.rejection_reason
    assert len(session.scalars(select(PaperOrder)).all()) == 1
    assert session.scalars(select(PaperTrade)).all() == []
