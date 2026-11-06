from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.db.base import Base
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


def test_tradingview_runbook_blocks_before_accepted_backtest(
    client: TestClient,
) -> None:
    response = client.get(
        "/signals/tradingview-runbook?strategy=trend_pullback_v1&symbol=btcusdt"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["ready_to_preflight"] is False
    assert body["ready_to_send_webhook"] is False
    assert body["live_trading_enabled"] is False
    assert body["mutates_ledger"] is False
    assert body["current_step"]["step_key"] == "accepted_backtest_contract"
    assert body["contract"]["reason"] == "accepted_backtest_missing_for_paper_trading"
    steps = {step["step_key"]: step for step in body["steps"]}
    assert steps["live_boundary"]["status"] == "PASS"
    assert steps["accepted_backtest_contract"]["status"] == "BLOCKED"
    assert steps["payload_preflight"]["status"] == "BLOCKED"
    assert body["required_header"] == "X-Aurex-Webhook-Secret"


def test_tradingview_runbook_ready_to_preflight_after_accepted_backtest(
    client: TestClient,
) -> None:
    accepted_backtest = post_accepted_backtest(client)

    response = client.get(
        "/signals/tradingview-runbook?strategy=trend_pullback_v1&symbol=BTCUSDT"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY_TO_PREFLIGHT"
    assert body["ready_to_preflight"] is True
    assert body["ready_to_send_webhook"] is False
    assert body["contract"]["accepted_backtest_run_id"] == accepted_backtest["id"]
    assert body["current_step"]["step_key"] == "payload_preflight"
    assert Decimal(body["progress_pct"]) == Decimal("40")
    steps = {step["step_key"]: step for step in body["steps"]}
    assert steps["live_boundary"]["status"] == "PASS"
    assert steps["accepted_backtest_contract"]["status"] == "PASS"
    assert steps["payload_preflight"]["status"] == "NOT_RUN"
    assert steps["webhook_rehearsal"]["status"] == "NOT_RUN"
    assert body["preflight_endpoint"] == "/signals/preflight/tradingview"
    assert body["webhook_endpoint"] == "/webhooks/tradingview"
    assert "Preflight alert" in body["next_action"]
