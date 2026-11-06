from collections.abc import Generator
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    strategy_parameter_fingerprint,
)
from aurex.config.settings import get_settings
from aurex.db.base import Base
from aurex.db.models import (
    LiveDeploymentPlan,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
    Signal,
    SignalEvent,
    StrategyEvidenceReview,
    SystemEvent,
)
from aurex.domain.enums import (
    LiveDeploymentStatus,
    PositionStatus,
    SignalStatus,
    StrategyEvidenceDecision,
    TradeStatus,
)
from aurex.execution_engine.paper import (
    DETERMINISTIC_PAPER_FILL_MODEL,
    paper_execution_evidence_hash,
)
from tests.integration.backtest_helpers import post_accepted_backtest

pytestmark = pytest.mark.usefixtures("active_trend_pipeline")


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
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def valid_payload(timestamp: datetime | None = None) -> dict:
    signal_time = timestamp or datetime.now(UTC)
    return {
        "source": "tradingview",
        "strategy": "trend_pullback_v1",
        "strategy_version": "1.3.0",
        "settings_fingerprint": strategy_parameter_fingerprint(
            "trend_pullback_v1",
            TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
        ),
        "symbol": "btcusdt",
        "timeframe": "15m",
        "direction": "LONG",
        "entry_price": 68250.50,
        "stop_loss": 67800.00,
        "take_profit": 69200.00,
        "market_regime": "TRENDING_UP",
        "timestamp": signal_time.isoformat(),
    }


def auth_headers() -> dict[str, str]:
    return {"X-Aurex-Webhook-Secret": get_settings().webhook_secret}


def seed_do_not_trade_review(session: Session, now: datetime) -> StrategyEvidenceReview:
    plan = LiveDeploymentPlan(
        name=f"webhook-review-plan-{now.isoformat()}",
        strategy="trend_pullback_v1",
        symbols=["BTCUSDT"],
        status=LiveDeploymentStatus.BLOCKED,
        approval_snapshot={},
        rules_snapshot={},
    )
    session.add(plan)
    session.flush()
    review = StrategyEvidenceReview(
        live_deployment_plan=plan,
        decision=StrategyEvidenceDecision.DO_NOT_TRADE,
        strategy="trend_pullback_v1",
        symbols=["BTCUSDT"],
        summary="Mature paper evidence is negative.",
        reasons=["expectancy_not_positive"],
        next_actions=["Do not trade this strategy live under the current evidence record."],
        gate_snapshot={"fixture": True},
        evidence_snapshot={"fixture": True},
        reviewed_at=now,
    )
    session.add(review)
    session.flush()
    return review


def test_tradingview_webhook_accepts_and_stores_valid_signal(client: TestClient) -> None:
    accepted_backtest = post_accepted_backtest(client)
    response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == SignalStatus.PAPER_EXECUTED
    assert body["symbol"] == "BTCUSDT"
    assert body["rejection_reason"] is None
    assert body["latest_risk_decision"]["approved"] is True
    assert body["latest_risk_decision"]["position_size"] is not None
    assert body["processing_latency_ms"] is not None
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-aurex-signal-id"] == body["id"]
    assert response.headers["x-aurex-idempotency-key"] == body["idempotency_key"]
    assert float(response.headers["x-aurex-processing-ms"]) >= 0
    assert response.headers["x-aurex-processing-budget-ms"] == "2500"
    assert response.headers["x-aurex-processing-budget-status"] == "within"
    backtest_gate = body["latest_risk_decision"]["rules_snapshot"]["paper_backtest_gate"]
    assert backtest_gate["approved"] is True
    assert backtest_gate["backtest_run_id"] == accepted_backtest["id"]
    provenance_gate = body["latest_risk_decision"]["rules_snapshot"][
        "signal_backtest_provenance_gate"
    ]
    assert provenance_gate["blocked"] is False
    assert provenance_gate["signal_strategy_version"] == "1.3.0"

    signals_response = client.get("/signals")
    assert signals_response.status_code == 200
    assert len(signals_response.json()) == 1
    assert signals_response.json()[0]["latest_risk_decision"]["reason"] == "Risk approved"

    trades_response = client.get("/trades")
    assert trades_response.status_code == 200
    assert len(trades_response.json()) == 1
    assert trades_response.json()[0]["status"] == TradeStatus.OPEN

    with next(client.app.dependency_overrides[get_db]()) as session:
        saved_signal = session.execute(select(Signal)).scalar_one()
        events = session.execute(select(SignalEvent)).scalars().all()
        risk_decision = session.execute(select(RiskDecision)).scalar_one()
        paper_trade = session.execute(select(PaperTrade)).scalar_one()
        position = session.execute(select(Position)).scalar_one()
        system_events = session.execute(select(SystemEvent)).scalars().all()

    assert saved_signal.normalized_payload["symbol"] == "BTCUSDT"
    assert saved_signal.normalized_payload["strategy_version"] == "1.3.0"
    assert saved_signal.normalized_payload["settings_fingerprint"]
    received_event = next(event for event in events if event.status == SignalStatus.RECEIVED)
    delivery = received_event.metadata_json["webhook_delivery"]
    assert delivery["authentication_status"] == "SHARED_SECRET_VALIDATED"
    assert delivery["authentication_transport"] == "header"
    assert delivery["request_method"] == "POST"
    assert delivery["request_path"] == "/webhooks/tradingview"
    assert delivery["content_type"].startswith("application/json")
    assert len(delivery["body_sha256"]) == 64
    assert len(delivery["evidence_hash"]) == 64
    assert delivery["body_size_bytes"] > 0
    assert delivery["remote_ip"] == "testclient"
    assert delivery["origin_status"] == "REMOTE_IP_INVALID"
    assert (
        delivery["source_network_configuration_status"]
        == "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS"
    )
    assert delivery["source_networks"] == [
        "34.212.75.30/32",
        "52.32.178.7/32",
        "52.89.214.238/32",
        "54.218.53.128/32",
    ]
    assert len(delivery["source_networks_sha256"]) == 64
    assert delivery["source_networks_authority_url"].startswith(
        "https://www.tradingview.com/support/"
    )
    assert {event.status for event in events} == {
        SignalStatus.RECEIVED,
        SignalStatus.VALIDATED,
        SignalStatus.RISK_APPROVED,
        SignalStatus.PAPER_ORDER_CREATED,
        SignalStatus.PAPER_EXECUTED,
    }
    assert risk_decision.approved is True
    assert risk_decision.position_size is not None
    assert (
        risk_decision.rules_snapshot["paper_backtest_gate"]["backtest_run_id"]
        == accepted_backtest["id"]
    )
    assert paper_trade.status == TradeStatus.OPEN
    assert position.status == PositionStatus.OPEN
    assert {event.category for event in system_events} == {
        "backtest_lab",
        "signal_gateway",
        "risk_engine",
        "paper_execution",
        "strategy_portfolio",
    }

    events_response = client.get("/system/events")
    assert events_response.status_code == 200
    assert len(events_response.json()) == 6
    assert any(
        event["message"] == "Backtest protocol registered"
        for event in events_response.json()
    )


def test_tradingview_webhook_accepts_query_secret_for_tradingview_alerts(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    response = client.post(
        f"/webhooks/tradingview?secret={get_settings().webhook_secret}",
        json=valid_payload(),
    )

    assert response.status_code == 202
    assert response.json()["status"] == SignalStatus.PAPER_EXECUTED
    assert response.json()["latest_risk_decision"]["approved"] is True


def test_tradingview_webhook_blocks_paper_execution_after_do_not_trade_review(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    now = datetime.now(UTC)
    with next(client.app.dependency_overrides[get_db]()) as session:
        review = seed_do_not_trade_review(session, now)
        review_id = review.id
        session.commit()

    response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(now),
        headers=auth_headers(),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == SignalStatus.RISK_REJECTED
    assert body["rejection_reason"] == (
        "Paper trading blocked by latest strategy evidence review: "
        "strategy_evidence_review_do_not_trade"
    )
    review_gate = body["latest_risk_decision"]["rules_snapshot"][
        "strategy_evidence_review_gate"
    ]
    assert review_gate["blocked"] is True
    assert review_gate["review_id"] == review_id
    assert review_gate["decision"] == StrategyEvidenceDecision.DO_NOT_TRADE
    assert review_gate["reasons"] == ["expectancy_not_positive"]
    assert client.get("/trades").json() == []


def test_tradingview_webhook_rejects_malformed_payload(client: TestClient) -> None:
    payload = valid_payload()
    payload.pop("direction")

    response = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )

    assert response.status_code == 422


def test_tradingview_webhook_blocks_missing_signal_provenance(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = valid_payload()
    payload.pop("strategy_version")
    payload.pop("settings_fingerprint")

    response = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == SignalStatus.RISK_REJECTED
    assert body["rejection_reason"] == (
        "Paper trading requires signal provenance matching accepted backtest: "
        "signal_strategy_version_missing"
    )
    provenance_gate = body["latest_risk_decision"]["rules_snapshot"][
        "signal_backtest_provenance_gate"
    ]
    assert provenance_gate["blocked"] is True
    assert provenance_gate["reasons"] == [
        "signal_strategy_version_missing",
        "signal_settings_fingerprint_missing",
    ]
    assert client.get("/trades").json() == []


def test_tradingview_webhook_rejects_invalid_secret(client: TestClient) -> None:
    response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers={"X-Aurex-Webhook-Secret": "wrong"},
    )

    assert response.status_code == 401


def test_tradingview_webhook_rejects_conflicting_auth_transports(
    client: TestClient,
) -> None:
    response = client.post(
        f"/webhooks/tradingview?secret={get_settings().webhook_secret}",
        json=valid_payload(),
        headers={"X-Aurex-Webhook-Secret": "wrong"},
    )

    assert response.status_code == 401


def test_tradingview_webhook_rejects_missing_secret(client: TestClient) -> None:
    response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
    )

    assert response.status_code == 401


def test_risk_status_and_kill_switch_endpoints_control_webhook_risk(
    client: TestClient,
) -> None:
    status_response = client.get("/risk/status")
    assert status_response.status_code == 200
    assert status_response.json()["kill_switch_enabled"] is False

    enable_response = client.post("/risk/kill-switch")
    assert enable_response.status_code == 200
    assert enable_response.json()["kill_switch_enabled"] is True

    webhook_response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers=auth_headers(),
    )

    assert webhook_response.status_code == 202
    assert webhook_response.json()["status"] == SignalStatus.RISK_REJECTED
    assert webhook_response.json()["rejection_reason"] == "Kill switch is enabled"
    assert client.get("/trades").json() == []

    reset_response = client.post("/risk/kill-switch/reset")
    assert reset_response.status_code == 200
    assert reset_response.json()["kill_switch_enabled"] is False


def test_tradingview_webhook_rejects_and_journals_duplicate_signal(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    first_response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers=auth_headers(),
    )
    second_response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers=auth_headers(),
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 409

    first_body = first_response.json()
    duplicate_body = second_response.json()
    assert duplicate_body["status"] == SignalStatus.DUPLICATE_REJECTED
    assert duplicate_body["duplicate_of_signal_id"] == first_body["id"]
    assert duplicate_body["rejection_reason"] == (
        "Duplicate signal within configured cooldown window"
    )

    signals_response = client.get("/signals")
    assert signals_response.status_code == 200
    assert len(signals_response.json()) == 2

    with next(client.app.dependency_overrides[get_db]()) as session:
        statuses = session.execute(select(Signal.status)).scalars().all()
        event_statuses = session.execute(select(SignalEvent.status)).scalars().all()

    assert statuses.count(SignalStatus.PAPER_EXECUTED) == 1
    assert statuses.count(SignalStatus.DUPLICATE_REJECTED) == 1
    assert event_statuses.count(SignalStatus.DUPLICATE_REJECTED) == 1


def test_tradingview_webhook_canonicalizes_timeframe_and_equivalent_utc_timestamp(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    signal_time = datetime(2026, 6, 5, 10, 15, tzinfo=UTC)
    first_payload = {
        **valid_payload(signal_time),
        "timeframe": "15",
    }
    equivalent_payload = {
        **valid_payload(signal_time.astimezone(timezone(timedelta(hours=2)))),
        "timeframe": "15m",
    }

    first_response = client.post(
        "/webhooks/tradingview",
        json=first_payload,
        headers=auth_headers(),
    )
    duplicate_response = client.post(
        "/webhooks/tradingview",
        json=equivalent_payload,
        headers=auth_headers(),
    )

    assert first_response.status_code == 202
    assert first_response.json()["timeframe"] == "15m"
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["duplicate_of_signal_id"] == first_response.json()["id"]
    assert (
        duplicate_response.json()["idempotency_key"]
        == first_response.json()["idempotency_key"]
    )


def test_tradingview_webhook_isolates_idempotency_by_strategy_provenance(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    signal_time = datetime.now(UTC)
    first_response = client.post(
        "/webhooks/tradingview",
        json=valid_payload(signal_time),
        headers=auth_headers(),
    )
    changed_provenance = {
        **valid_payload(signal_time),
        "strategy_version": "1.4.0",
        "settings_fingerprint": "different-reviewed-settings",
    }
    second_response = client.post(
        "/webhooks/tradingview",
        json=changed_provenance,
        headers=auth_headers(),
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["status"] == SignalStatus.RISK_REJECTED
    assert second_response.json()["idempotency_key"] != first_response.json()["idempotency_key"]
    assert second_response.json()["duplicate_of_signal_id"] is None


def test_tradingview_webhook_rejects_cooldown_duplicate_with_new_timestamp(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    first_time = datetime.now(UTC)
    first_payload = valid_payload(first_time)
    cooldown_payload = {
        **valid_payload(first_time + timedelta(minutes=15)),
        "entry_price": 68275.50,
        "stop_loss": 67850.00,
        "take_profit": 69250.00,
    }

    first_response = client.post(
        "/webhooks/tradingview",
        json=first_payload,
        headers=auth_headers(),
    )
    cooldown_response = client.post(
        "/webhooks/tradingview",
        json=cooldown_payload,
        headers=auth_headers(),
    )

    assert first_response.status_code == 202
    assert cooldown_response.status_code == 409
    assert cooldown_response.json()["status"] == SignalStatus.DUPLICATE_REJECTED
    assert cooldown_response.json()["duplicate_of_signal_id"] == first_response.json()["id"]


def test_paper_close_trade_and_reset_endpoints(client: TestClient) -> None:
    post_accepted_backtest(client)
    payload = {
        **valid_payload(),
        "entry_price": 100,
        "stop_loss": 95,
        "take_profit": 110,
    }
    webhook_response = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )
    assert webhook_response.status_code == 202
    assert webhook_response.json()["status"] == SignalStatus.PAPER_EXECUTED

    trade = client.get("/trades").json()[0]
    close_response = client.post(
        "/paper/close-trade",
        json={
            "trade_id": trade["id"],
            "exit_price": 110,
            "close_reason": "target hit",
        },
    )

    assert close_response.status_code == 200
    closed_trade = close_response.json()
    assert closed_trade["status"] == TradeStatus.CLOSED
    assert closed_trade["realized_pl"] == "9.68500000"
    assert closed_trade["r_multiple"] == "1.937000"
    assert closed_trade["fees"] == "0.21000000"
    assert closed_trade["slippage"] == "0.10500000"

    with next(client.app.dependency_overrides[get_db]()) as session:
        order = session.execute(select(PaperOrder)).scalar_one()
        assert order.fill_model == DETERMINISTIC_PAPER_FILL_MODEL
        assert order.execution_assumptions["lifecycle_status"] == "CLOSED"
        assert order.execution_assumptions["cost_floor_enforced"] is True
        assert order.execution_assumptions_hash == paper_execution_evidence_hash(
            order.execution_assumptions
        )

    summary_response = client.get("/performance/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total_trades"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["total_net_pl"] == "9.68500000"
    assert summary["best_strategy"]["strategy"] == "trend_pullback_v1"

    curve_response = client.get("/performance/equity-curve")
    assert curve_response.status_code == 200
    curve = curve_response.json()
    assert curve["point_count"] >= 2
    assert curve["latest_equity"] == "1009.68500000"
    assert curve["max_drawdown"] == "0"
    assert curve["total_realized_pl"] == "9.68500000"

    reset_response = client.post("/paper/reset")
    assert reset_response.status_code == 200
    assert reset_response.json()["deleted_trades"] == 1
    assert client.get("/trades").json() == []

    empty_summary = client.get("/performance/summary").json()
    assert empty_summary["total_trades"] == 0
    assert empty_summary["best_strategy"] is None
    assert client.get("/performance/equity-curve").json()["point_count"] == 0


def test_paper_short_trade_close_calculates_profit_and_r_multiple(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = {
        **valid_payload(),
        "direction": "SHORT",
        "entry_price": 100,
        "stop_loss": 105,
        "take_profit": 90,
        "market_regime": "TRENDING_DOWN",
    }
    webhook_response = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )
    assert webhook_response.status_code == 202
    assert webhook_response.json()["status"] == SignalStatus.PAPER_EXECUTED

    trade = client.get("/trades").json()[0]
    close_response = client.post(
        "/paper/close-trade",
        json={
            "trade_id": trade["id"],
            "exit_price": 90,
            "close_reason": "target hit",
        },
    )

    assert close_response.status_code == 200
    closed_trade = close_response.json()
    assert closed_trade["status"] == TradeStatus.CLOSED
    assert closed_trade["realized_pl"] == "9.71500000"
    assert closed_trade["r_multiple"] == "1.943000"
