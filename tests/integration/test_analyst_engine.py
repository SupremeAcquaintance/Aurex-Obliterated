from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.db.base import Base
from aurex.db.models import Account, AnalystNote, PaperOrder, PaperTrade, RiskDecision, Signal
from aurex.domain.enums import (
    AnalystNoteType,
    Direction,
    MarketRegime,
    OrderStatus,
    SignalStatus,
    SystemEventSeverity,
    TradeStatus,
)


@pytest.fixture()
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_analyst_summary_is_advisory_with_no_trade_data(client: TestClient) -> None:
    response = client.get("/analyst/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["advisory_only"] is True
    assert body["closed_trades"] == 0
    assert body["note_count"] == 0
    assert "No closed paper trades" in body["headline"]
    assert body["evidence_snapshot"]["execution_authority"] == "none"


def test_trade_review_creates_advisory_note(client: TestClient) -> None:
    now = datetime(2026, 6, 6, 9, tzinfo=UTC)
    with next(client.app.dependency_overrides[get_db]()) as session:
        account = add_account(session)
        trade = add_closed_trade(
            session,
            account,
            now,
            realized_pl=Decimal("-6"),
            r_multiple=Decimal("-1.2"),
        )
        session.commit()
        trade_id = trade.id

    response = client.post(f"/analyst/trades/{trade_id}/review")

    assert response.status_code == 200
    body = response.json()
    assert body["advisory_only"] is True
    assert body["note_type"] == AnalystNoteType.TRADE_REVIEW
    assert body["trade_id"] == trade_id
    assert body["strategy"] == "trend_pullback_v1"
    assert "realized P/L" in body["summary"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        note = session.execute(select(AnalystNote)).scalar_one()
        assert note.advisory_only is True
        assert note.evidence_snapshot["trade_id"] == trade_id


def test_pattern_similarity_returns_matches_and_stores_note(client: TestClient) -> None:
    now = datetime(2026, 6, 6, 10, tzinfo=UTC)
    with next(client.app.dependency_overrides[get_db]()) as session:
        account = add_account(session)
        source = add_closed_trade(
            session,
            account,
            now,
            realized_pl=Decimal("10"),
            r_multiple=Decimal("2"),
        )
        add_closed_trade(
            session,
            account,
            now + timedelta(minutes=15),
            realized_pl=Decimal("8"),
            r_multiple=Decimal("1.6"),
        )
        add_closed_trade(
            session,
            account,
            now + timedelta(minutes=30),
            realized_pl=Decimal("-4"),
            r_multiple=Decimal("-0.8"),
            symbol="ETHUSDT",
        )
        session.commit()
        source_id = source.id

    response = client.post(f"/analyst/trades/{source_id}/similarity?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["advisory_only"] is True
    assert body["source_trade_id"] == source_id
    assert len(body["similar_trades"]) == 2
    assert body["note"]["note_type"] == AnalystNoteType.PATTERN_SIMILARITY
    assert body["note"]["evidence_snapshot"]["similar_trade_ids"]


def test_risk_anomaly_scan_flags_oversized_loss(client: TestClient) -> None:
    now = datetime(2026, 6, 6, 11, tzinfo=UTC)
    with next(client.app.dependency_overrides[get_db]()) as session:
        account = add_account(session)
        add_closed_trade(
            session,
            account,
            now,
            realized_pl=Decimal("-8"),
            r_multiple=Decimal("-1.6"),
            fees=Decimal("0.25"),
            slippage=Decimal("0.25"),
        )
        session.commit()

    response = client.post("/analyst/risk-anomalies/scan", json={"limit": 50})

    assert response.status_code == 200
    body = response.json()
    assert body["advisory_only"] is True
    assert body["scanned_trades"] == 1
    assert len(body["created_notes"]) == 1
    note = body["created_notes"][0]
    assert note["note_type"] == AnalystNoteType.RISK_ANOMALY
    assert note["severity"] == SystemEventSeverity.WARNING
    assert "loss exceeded planned risk" in note["summary"]


def test_strategy_degradation_scan_flags_recent_decay(client: TestClient) -> None:
    now = datetime(2026, 6, 6, 12, tzinfo=UTC)
    with next(client.app.dependency_overrides[get_db]()) as session:
        account = add_account(session)
        for index in range(5):
            add_closed_trade(
                session,
                account,
                now + timedelta(minutes=index),
                realized_pl=Decimal("5"),
                r_multiple=Decimal("1"),
            )
        for index in range(5, 10):
            add_closed_trade(
                session,
                account,
                now + timedelta(minutes=index),
                realized_pl=Decimal("-6"),
                r_multiple=Decimal("-1.2"),
            )
        session.commit()

    response = client.post("/analyst/strategy-degradation/scan", json={"limit": 50})

    assert response.status_code == 200
    body = response.json()
    assert body["advisory_only"] is True
    assert body["scanned_trades"] == 10
    assert len(body["created_notes"]) == 1
    note = body["created_notes"][0]
    assert note["note_type"] == AnalystNoteType.STRATEGY_DEGRADATION
    assert "recent expectancy fell" in note["summary"]


def add_account(session: Session) -> Account:
    account = Account(
        name="paper-main",
        mode="paper",
        currency="USD",
        starting_equity=Decimal("1000"),
        current_equity=Decimal("1000"),
    )
    session.add(account)
    session.flush()
    return account


def add_closed_trade(
    session: Session,
    account: Account,
    timestamp: datetime,
    *,
    realized_pl: Decimal,
    r_multiple: Decimal,
    strategy: str = "trend_pullback_v1",
    symbol: str = "BTCUSDT",
    market_regime: MarketRegime = MarketRegime.TRENDING_UP,
    fees: Decimal = Decimal("0"),
    slippage: Decimal = Decimal("0"),
) -> PaperTrade:
    signal = Signal(
        source="tradingview",
        strategy=strategy,
        symbol=symbol,
        timeframe="15m",
        direction=Direction.LONG,
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        market_regime=market_regime,
        status=SignalStatus.PAPER_EXECUTED,
        idempotency_key=f"{strategy}:{symbol}:{timestamp.isoformat()}",
        raw_payload={},
        normalized_payload={},
        source_timestamp=timestamp,
        received_at=timestamp,
        processed_at=timestamp,
    )
    session.add(signal)
    session.flush()

    decision = RiskDecision(
        signal=signal,
        approved=True,
        reason="Fixture approved",
        reward_risk=Decimal("2"),
        risk_amount=Decimal("5"),
        position_size=Decimal("1"),
        account_equity=Decimal("1000"),
        rules_snapshot={},
    )
    session.add(decision)
    session.flush()

    order = PaperOrder(
        signal=signal,
        risk_decision_id=decision.id,
        symbol=symbol,
        direction=Direction.LONG,
        order_type="market",
        status=OrderStatus.FILLED,
        requested_price=Decimal("100"),
        filled_price=Decimal("100"),
        quantity=Decimal("1"),
        created_order_at=timestamp,
        filled_at=timestamp,
    )
    session.add(order)
    session.flush()

    trade = PaperTrade(
        account=account,
        paper_order=order,
        strategy=strategy,
        symbol=symbol,
        timeframe="15m",
        direction=Direction.LONG,
        status=TradeStatus.CLOSED,
        market_regime=market_regime,
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        quantity=Decimal("1"),
        risk_amount=Decimal("5"),
        opened_at=timestamp,
        exit_price=Decimal("100") + realized_pl,
        closed_at=timestamp + timedelta(minutes=1),
        realized_pl=realized_pl,
        r_multiple=r_multiple,
        fees=fees,
        slippage=slippage,
        close_reason="fixture",
    )
    session.add(trade)
    session.flush()
    return trade
