from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

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
    BrokerFill,
    BrokerOrder,
    BrokerPositionSnapshot,
    OrderIntent,
    PaperOrder,
)
from aurex.domain.enums import (
    BrokerConnectionStatus,
    BrokerEnvironment,
    BrokerOrderStatus,
    OrderIntentStatus,
    ReadinessStatus,
    ReconciliationStatus,
    SignalStatus,
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
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def auth_headers() -> dict[str, str]:
    return {"X-Aurex-Webhook-Secret": get_settings().webhook_secret}


def webhook_payload() -> dict:
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
        "entry_price": 100,
        "stop_loss": 95,
        "take_profit": 110,
        "market_regime": "TRENDING_UP",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def approved_risk_decision_id(client: TestClient) -> str:
    post_accepted_backtest(client)
    response = client.post(
        "/webhooks/tradingview",
        json=webhook_payload(),
        headers=auth_headers(),
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == SignalStatus.PAPER_EXECUTED
    return body["latest_risk_decision"]["id"]


def test_broker_readiness_defaults_are_sandbox_and_not_live(client: TestClient) -> None:
    response = client.get("/broker/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["ready_for_live"] is False
    assert body["live_trading_enabled"] is False
    assert body["sandbox_connection"]["environment"] == BrokerEnvironment.SANDBOX
    assert body["sandbox_connection"]["live_trading_enabled"] is False
    checks = {item["check_key"]: item for item in body["checks"]}
    assert checks["live_trading_disabled"]["status"] == ReadinessStatus.PASS
    assert checks["paper_trading_gate"]["status"] == ReadinessStatus.BLOCKED


def test_sandbox_order_intent_fill_and_reconciliation_flow(client: TestClient) -> None:
    risk_decision_id = approved_risk_decision_id(client)

    intent_response = client.post(
        "/broker/sandbox/order-intents",
        json={"risk_decision_id": risk_decision_id},
    )
    assert intent_response.status_code == 200
    intent = intent_response.json()
    assert intent["status"] == OrderIntentStatus.CREATED
    assert intent["intent_snapshot"]["sandbox_only"] is True

    order_response = client.post(f"/broker/sandbox/order-intents/{intent['id']}/submit")
    assert order_response.status_code == 200
    order = order_response.json()
    assert order["status"] == BrokerOrderStatus.SUBMITTED
    assert order["external_order_id"].startswith("sandbox-order-")

    fill_response = client.post(
        f"/broker/sandbox/orders/{order['id']}/simulate-fill",
        json={},
    )
    assert fill_response.status_code == 200
    fill = fill_response.json()
    assert fill["external_fill_id"].startswith("sandbox-fill-")

    reconciliation_response = client.post("/broker/reconciliation/run")
    assert reconciliation_response.status_code == 200
    report = reconciliation_response.json()
    assert report["status"] == ReconciliationStatus.MATCHED
    assert report["discrepancies"] == []
    assert len(report["broker_snapshot"]["positions"]) == 1
    assert len(report["aurex_snapshot"]["positions"]) == 1
    assert report["broker_snapshot"]["positions"][0]["quantity"] == (
        report["aurex_snapshot"]["positions"][0]["quantity"]
    )
    assert Decimal(report["broker_snapshot"]["costs"][0]["total_fill_fees"]) == Decimal(
        "0.10"
    )
    assert Decimal(report["aurex_snapshot"]["costs"][0]["fees"]) == Decimal("0.10")
    assert Decimal(report["broker_snapshot"]["cost_summary"]["total_fill_fees"]) == Decimal(
        "0.10"
    )
    assert Decimal(report["aurex_snapshot"]["cost_summary"]["total_order_fees"]) == Decimal(
        "0.10"
    )

    readiness = client.get("/broker/readiness").json()
    checks = {item["check_key"]: item for item in readiness["checks"]}
    assert checks["sandbox_order_intent_test"]["status"] == ReadinessStatus.PASS
    assert checks["position_reconciliation"]["status"] == ReadinessStatus.PASS
    assert readiness["ready_for_live"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        intent_status = session.execute(select(OrderIntent)).scalar_one().status
        assert intent_status == OrderIntentStatus.RECONCILED
        assert session.execute(select(BrokerOrder)).scalar_one().status == BrokerOrderStatus.FILLED
        assert session.execute(select(BrokerFill)).scalar_one().price == 100


def test_reconciliation_detects_broker_fee_mismatch(client: TestClient) -> None:
    risk_decision_id = approved_risk_decision_id(client)
    intent = client.post(
        "/broker/sandbox/order-intents",
        json={"risk_decision_id": risk_decision_id},
    ).json()
    order = client.post(f"/broker/sandbox/order-intents/{intent['id']}/submit").json()
    fill_response = client.post(
        f"/broker/sandbox/orders/{order['id']}/simulate-fill",
        json={"fees": "1.25"},
    )
    assert fill_response.status_code == 200
    assert Decimal(fill_response.json()["fees"]) == Decimal("1.25")

    reconciliation_response = client.post("/broker/reconciliation/run")

    assert reconciliation_response.status_code == 200
    report = reconciliation_response.json()
    assert report["status"] == ReconciliationStatus.DISCREPANCY
    mismatch = next(
        item for item in report["discrepancies"] if item["reason"] == "broker_fee_mismatch"
    )
    assert Decimal(mismatch["broker_fees"]) == Decimal("1.25")
    assert Decimal(mismatch["aurex_order_fees"]) == Decimal("0.10")
    assert Decimal(report["broker_snapshot"]["costs"][0]["total_fill_fees"]) == Decimal("1.25")
    assert Decimal(report["aurex_snapshot"]["costs"][0]["fees"]) == Decimal("0.10")

    readiness = client.get("/broker/readiness").json()
    checks = {item["check_key"]: item for item in readiness["checks"]}
    assert checks["position_reconciliation"]["status"] == ReadinessStatus.FAIL
    assert readiness["ready_for_live"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(PaperOrder)).scalar_one().fees == Decimal("0.10")


def test_reconciliation_detects_position_snapshot_mismatch(client: TestClient) -> None:
    risk_decision_id = approved_risk_decision_id(client)
    intent = client.post(
        "/broker/sandbox/order-intents",
        json={"risk_decision_id": risk_decision_id},
    ).json()
    order = client.post(f"/broker/sandbox/order-intents/{intent['id']}/submit").json()
    client.post(f"/broker/sandbox/orders/{order['id']}/simulate-fill", json={})

    with next(client.app.dependency_overrides[get_db]()) as session:
        snapshot = session.execute(select(BrokerPositionSnapshot)).scalar_one()
        snapshot.quantity = snapshot.quantity * 2
        session.commit()

    reconciliation_response = client.post("/broker/reconciliation/run")

    assert reconciliation_response.status_code == 200
    report = reconciliation_response.json()
    assert report["status"] == ReconciliationStatus.DISCREPANCY
    assert any(
        item["reason"] == "position_quantity_mismatch"
        for item in report["discrepancies"]
    )

    readiness = client.get("/broker/readiness").json()
    checks = {item["check_key"]: item for item in readiness["checks"]}
    assert checks["position_reconciliation"]["status"] == ReadinessStatus.FAIL
    assert readiness["ready_for_live"] is False


def test_broker_emergency_stop_cancels_open_sandbox_orders_and_sets_kill_switch(
    client: TestClient,
) -> None:
    risk_decision_id = approved_risk_decision_id(client)
    intent = client.post(
        "/broker/sandbox/order-intents",
        json={"risk_decision_id": risk_decision_id},
    ).json()
    client.post(f"/broker/sandbox/order-intents/{intent['id']}/submit")

    response = client.post("/broker/emergency-stop")

    assert response.status_code == 200
    body = response.json()
    assert body["live_trading_enabled"] is False
    assert body["cancelled_orders"] == 1
    assert body["cancelled_intents"] == 1
    assert body["kill_switch_enabled"] is True

    risk_status = client.get("/risk/status").json()
    readiness = client.get("/broker/readiness").json()
    assert risk_status["kill_switch_enabled"] is True
    assert readiness["sandbox_connection"]["status"] == BrokerConnectionStatus.EMERGENCY_STOPPED
    checks = {item["check_key"]: item for item in readiness["checks"]}
    assert checks["emergency_stop_tested"]["status"] == ReadinessStatus.PASS
