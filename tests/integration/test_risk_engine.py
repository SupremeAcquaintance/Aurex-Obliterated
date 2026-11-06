from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    strategy_parameter_fingerprint,
)
from aurex.db.base import Base
from aurex.db.models import (
    BacktestRun,
    LiveDeploymentPlan,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
    Signal,
    StrategyEvidenceReview,
)
from aurex.domain.enums import (
    Direction,
    LiveDeploymentStatus,
    MarketRegime,
    PositionStatus,
    SignalStatus,
    StrategyEvidenceDecision,
    TradeStatus,
)
from aurex.risk_engine.service import RiskEngine
from aurex.strategy_engine.service import StrategyPortfolioService
from tests.integration.backtest_helpers import seed_accepted_backtest

pytestmark = pytest.mark.usefixtures("active_trend_pipeline")


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db_session:
        strategy = StrategyPortfolioService(db_session).get_config("trend_pullback_v1")
        assert strategy is not None
        strategy.is_enabled = True
        db_session.flush()
        yield db_session

    Base.metadata.drop_all(engine)


def make_signal(
    now: datetime,
    *,
    direction: Direction = Direction.LONG,
    entry_price: Decimal = Decimal("100"),
    stop_loss: Decimal | None = Decimal("95"),
    take_profit: Decimal | None = Decimal("110"),
    status: SignalStatus = SignalStatus.VALIDATED,
    source_timestamp: datetime | None = None,
    include_provenance: bool = True,
    settings_fingerprint: str | None = None,
) -> Signal:
    normalized_payload = {}
    if include_provenance:
        normalized_payload = {
            "strategy_version": "1.3.0",
            "settings_fingerprint": settings_fingerprint
            or strategy_parameter_fingerprint(
                "trend_pullback_v1",
                TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
            ),
        }
    signal = Signal(
        source="tradingview",
        strategy="trend_pullback_v1",
        symbol="BTCUSDT",
        timeframe="15m",
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        market_regime=MarketRegime.TRENDING_UP,
        status=status,
        idempotency_key=f"risk-test:{now.isoformat()}:{entry_price}:{stop_loss}:{take_profit}",
        raw_payload=dict(normalized_payload),
        normalized_payload=normalized_payload,
        source_timestamp=source_timestamp or now,
        received_at=now,
    )
    return signal


def add_closed_trade(
    session: Session,
    engine: RiskEngine,
    now: datetime,
    realized_pl: Decimal,
    closed_at: datetime,
) -> None:
    account, _ = engine.get_or_create_default_profile()
    signal = make_signal(now)
    session.add(signal)
    session.flush()
    decision = RiskDecision(
        signal=signal,
        approved=True,
        reason="Fixture approved",
        rules_snapshot={},
    )
    session.add(decision)
    session.flush()
    order = PaperOrder(
        signal=signal,
        risk_decision_id=decision.id,
        symbol="BTCUSDT",
        direction=Direction.LONG,
        requested_price=Decimal("100"),
        quantity=Decimal("1"),
        created_order_at=now,
    )
    session.add(order)
    session.flush()
    trade = PaperTrade(
        account=account,
        paper_order=order,
        strategy="trend_pullback_v1",
        symbol="BTCUSDT",
        timeframe="15m",
        direction=Direction.LONG,
        status=TradeStatus.CLOSED,
        market_regime=MarketRegime.TRENDING_UP,
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        quantity=Decimal("1"),
        risk_amount=Decimal("5"),
        opened_at=now - timedelta(hours=1),
        exit_price=Decimal("90"),
        closed_at=closed_at,
        realized_pl=realized_pl,
    )
    session.add(trade)
    session.flush()


def add_strategy_evidence_review(
    session: Session,
    now: datetime,
    *,
    decision: StrategyEvidenceDecision,
    strategy: str = "trend_pullback_v1",
    symbols: list[str] | None = None,
) -> StrategyEvidenceReview:
    plan = LiveDeploymentPlan(
        name=f"review-plan-{now.isoformat()}-{decision.value}",
        strategy=strategy,
        symbols=symbols or ["BTCUSDT"],
        status=LiveDeploymentStatus.BLOCKED,
        approval_snapshot={},
        rules_snapshot={},
    )
    session.add(plan)
    session.flush()
    review = StrategyEvidenceReview(
        live_deployment_plan=plan,
        decision=decision,
        strategy=strategy,
        symbols=symbols or ["BTCUSDT"],
        summary=f"{decision.value} fixture",
        reasons=(
            ["expectancy_not_positive"]
            if decision == StrategyEvidenceDecision.DO_NOT_TRADE
            else []
        ),
        next_actions=["Do not trade this strategy live under the current evidence record."]
        if decision == StrategyEvidenceDecision.DO_NOT_TRADE
        else ["Continue evidence review."],
        gate_snapshot={"fixture": True},
        evidence_snapshot={"fixture": True},
        reviewed_at=now,
    )
    session.add(review)
    session.flush()
    return review


def test_risk_engine_rejects_future_signal(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    signal = make_signal(now, source_timestamp=now + timedelta(seconds=1))
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Signal timestamp is in the future"
    assert session.scalars(select(PaperOrder)).all() == []


def test_risk_engine_approves_valid_signal_with_position_size(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    seed_accepted_backtest(session)
    signal = make_signal(now)
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    backtest_run = session.execute(select(BacktestRun)).scalar_one()
    backtest_gate = result.decision.rules_snapshot["paper_backtest_gate"]
    assert result.decision.approved is True
    assert result.decision.reason == "Risk approved"
    assert result.decision.reward_risk == Decimal("2")
    assert result.decision.risk_amount == Decimal("5.00000000")
    assert result.decision.position_size == Decimal("1.000000000000")
    assert backtest_gate["approved"] is True
    assert backtest_gate["reason"] == "accepted_backtest_ready_for_paper_trading"
    assert backtest_gate["backtest_run_id"] == backtest_run.id
    assert backtest_gate["evidence_snapshot"]["backtest_run_id"] == backtest_run.id
    assert backtest_gate["evidence_snapshot"]["reasons"] == []
    assert result.decision.rules_snapshot["strategy_evidence_review_gate"] == {
        "blocked": False,
        "reason": "strategy_evidence_review_not_recorded",
        "review_id": None,
        "decision": None,
        "strategy": "trend_pullback_v1",
        "symbols": ["BTCUSDT"],
        "summary": None,
        "reasons": [],
        "next_actions": [],
        "reviewed_at": None,
    }
    assert result.decision.rules_snapshot["signal_backtest_provenance_gate"][
        "blocked"
    ] is False
    assert signal.status == SignalStatus.RISK_APPROVED


def test_risk_engine_blocks_signal_without_matching_backtest_provenance(
    session: Session,
) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    seed_accepted_backtest(session)
    signal = make_signal(now, include_provenance=False)
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    provenance_gate = result.decision.rules_snapshot["signal_backtest_provenance_gate"]
    assert result.decision.approved is False
    assert result.decision.reason == (
        "Paper trading requires signal provenance matching accepted backtest: "
        "signal_strategy_version_missing"
    )
    assert provenance_gate["blocked"] is True
    assert provenance_gate["reasons"] == [
        "signal_strategy_version_missing",
        "signal_settings_fingerprint_missing",
    ]
    assert signal.status == SignalStatus.RISK_REJECTED


def test_risk_engine_blocks_paper_trading_after_do_not_trade_review(
    session: Session,
) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    seed_accepted_backtest(session)
    review = add_strategy_evidence_review(
        session,
        now,
        decision=StrategyEvidenceDecision.DO_NOT_TRADE,
    )
    signal = make_signal(now)
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    review_gate = result.decision.rules_snapshot["strategy_evidence_review_gate"]
    assert result.decision.approved is False
    assert result.decision.reason == (
        "Paper trading blocked by latest strategy evidence review: "
        "strategy_evidence_review_do_not_trade"
    )
    assert result.decision.rules_snapshot["paper_backtest_gate"]["approved"] is True
    assert review_gate["blocked"] is True
    assert review_gate["review_id"] == review.id
    assert review_gate["decision"] == StrategyEvidenceDecision.DO_NOT_TRADE
    assert review_gate["reasons"] == ["expectancy_not_positive"]
    assert signal.status == SignalStatus.RISK_REJECTED


def test_risk_engine_blocks_paper_trading_without_accepted_backtest(
    session: Session,
) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    signal = make_signal(now)
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == (
        "Paper trading requires accepted backtest evidence: "
        "accepted_backtest_missing_for_paper_trading"
    )
    backtest_gate = result.decision.rules_snapshot["paper_backtest_gate"]
    assert backtest_gate["approved"] is False
    assert backtest_gate["reason"] == "accepted_backtest_missing_for_paper_trading"
    assert backtest_gate["backtest_run_id"] is None
    assert backtest_gate["evidence_snapshot"]["strategy"] == "trend_pullback_v1"
    assert backtest_gate["evidence_snapshot"]["symbol"] == "BTCUSDT"
    assert backtest_gate["evidence_snapshot"]["reasons"] == [
        "accepted_backtest_missing_for_paper_trading"
    ]
    assert signal.status == SignalStatus.RISK_REJECTED


def test_risk_engine_rejects_missing_stop_loss(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    signal = make_signal(now, stop_loss=None)
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Missing stop loss"
    assert signal.status == SignalStatus.RISK_REJECTED
    assert signal.rejection_reason == "Missing stop loss"


def test_risk_engine_rejects_missing_take_profit(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    signal = make_signal(now, take_profit=None)
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Missing take profit"
    assert signal.status == SignalStatus.RISK_REJECTED
    assert signal.rejection_reason == "Missing take profit"


def test_risk_engine_rejects_bad_reward_risk(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    signal = make_signal(now, take_profit=Decimal("101"))
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Reward:risk is below minimum"
    assert result.decision.reward_risk == Decimal("0.2")


def test_risk_engine_rejects_stale_signal(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    signal = make_signal(now, source_timestamp=now - timedelta(minutes=4))
    session.add(signal)
    session.flush()

    result = RiskEngine(session).evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Signal is stale"


def test_risk_engine_rejects_daily_loss_limit(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    engine = RiskEngine(session)
    add_closed_trade(session, engine, now, Decimal("-10"), now - timedelta(hours=1))
    signal = make_signal(now, entry_price=Decimal("101"))
    session.add(signal)
    session.flush()

    result = engine.evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Daily loss limit reached"


def test_risk_engine_rejects_weekly_loss_limit(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    engine = RiskEngine(session)
    add_closed_trade(session, engine, now, Decimal("-30"), now - timedelta(days=2))
    signal = make_signal(now, entry_price=Decimal("102"), take_profit=Decimal("116"))
    session.add(signal)
    session.flush()

    result = engine.evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Weekly loss limit reached"


def test_risk_engine_rejects_max_open_positions(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    engine = RiskEngine(session)
    account, risk_profile = engine.get_or_create_default_profile()
    risk_profile.max_open_positions = 1
    session.add(
        Position(
            account=account,
            symbol="BTCUSDT",
            direction=Direction.LONG,
            status=PositionStatus.OPEN,
            quantity=Decimal("1"),
            average_entry_price=Decimal("100"),
            opened_at=now,
        )
    )
    signal = make_signal(now)
    session.add(signal)
    session.flush()

    result = engine.evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Max open positions reached"


def test_risk_engine_rejects_when_kill_switch_enabled(session: Session) -> None:
    now = datetime(2026, 6, 5, 12, tzinfo=UTC)
    engine = RiskEngine(session)
    engine.set_kill_switch(True)
    signal = make_signal(now)
    session.add(signal)
    session.flush()

    result = engine.evaluate_signal(signal, now=now)

    assert result.decision.approved is False
    assert result.decision.reason == "Kill switch is enabled"


def test_risk_status_reports_default_profile(session: Session) -> None:
    status = RiskEngine(session).risk_status()

    assert status["account_name"] == "paper-main"
    assert status["risk_profile_name"] == "default"
    assert status["kill_switch_enabled"] is False
    assert status["open_positions"] == 0

    decisions = session.execute(select(RiskDecision)).scalars().all()
    assert decisions == []
