from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    strategy_parameter_fingerprint,
)
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


def test_signal_contract_blocks_without_accepted_backtest(client: TestClient) -> None:
    response = client.get("/signals/contract?strategy=trend_pullback_v1&symbol=btcusdt")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["ready_for_paper"] is False
    assert body["reason"] == "accepted_backtest_missing_for_paper_trading"
    assert body["accepted_backtest_run_id"] is None
    assert body["known_strategy"] is True
    assert body["requires_provenance"] is True
    assert body["settings_fingerprint"] is None
    assert "strategy_version" in body["required_payload_fields"]
    assert "settings_fingerprint" in body["required_payload_fields"]
    assert "initial_capital" in body["missing_parameters"]
    assert "Import an accepted backtest" in body["next_actions"][0]


def test_tradingview_alert_setup_blocks_without_accepted_backtest(
    client: TestClient,
) -> None:
    response = client.get(
        "/signals/tradingview-alert-setup?strategy=trend_pullback_v1&symbol=btcusdt"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["ready_for_alert_preflight"] is False
    assert body["webhook_method"] == "POST"
    assert body["webhook_endpoint"] == "/webhooks/tradingview"
    assert body["webhook_url_template"].endswith("?secret=<AUREX_WEBHOOK_SECRET>")
    assert body["query_secret_supported"] is True
    assert body["header_auth_supported"] is True
    assert body["required_header"] == "X-Aurex-Webhook-Secret"
    assert body["alert_message"]["strategy"] == "trend_pullback_v1"
    assert body["mutates_ledger"] is False
    assert "Do not enable" in body["next_actions"][1]


def test_signal_contract_reports_expected_pine_provenance(
    client: TestClient,
) -> None:
    accepted_backtest = post_accepted_backtest(client)
    expected_fingerprint = strategy_parameter_fingerprint(
        "trend_pullback_v1",
        TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    )

    response = client.get("/signals/contract?strategy=trend_pullback_v1&symbol=BTCUSDT")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["ready_for_paper"] is True
    assert body["reason"] == "accepted_backtest_ready_for_paper_trading"
    assert body["accepted_backtest_run_id"] == accepted_backtest["id"]
    assert body["strategy_version"] == "1.3.0"
    assert body["settings_fingerprint"] == expected_fingerprint
    assert body["settings_fingerprint_preview"] == expected_fingerprint[:24]
    assert body["missing_parameters"] == []
    assert body["example_payload"]["strategy_version"] == "1.3.0"
    assert body["example_payload"]["settings_fingerprint"] == expected_fingerprint
    assert body["example_payload"]["entry_price"] == "100"
    assert body["example_payload"]["stop_loss"] == "95"
    assert body["example_payload"]["take_profit"] == "110"
    assert body["evidence_snapshot"]["strategy_parameter_fingerprint"] == expected_fingerprint

    preflight = client.post("/signals/preflight/tradingview", json=body["example_payload"])

    assert preflight.status_code == 200
    assert preflight.json()["status"] == "PASS"
    assert preflight.json()["mutates_ledger"] is False


def test_tradingview_alert_setup_reports_ready_payload_after_accepted_backtest(
    client: TestClient,
) -> None:
    accepted_backtest = post_accepted_backtest(client)
    expected_fingerprint = strategy_parameter_fingerprint(
        "trend_pullback_v1",
        TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    )

    response = client.get(
        "/signals/tradingview-alert-setup?strategy=trend_pullback_v1&symbol=BTCUSDT"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY_TO_PREFLIGHT"
    assert body["ready_for_alert_preflight"] is True
    assert body["accepted_backtest_run_id"] == accepted_backtest["id"]
    assert body["strategy_version"] == "1.3.0"
    assert body["settings_fingerprint"] == expected_fingerprint
    assert body["settings_fingerprint_preview"] == expected_fingerprint[:24]
    assert body["preflight_endpoint"] == "/signals/preflight/tradingview"
    assert body["verification_endpoint"] == "/signals/tradingview-verification"
    assert body["alert_condition"] == (
        "Aurex trend_pullback_v1 / any alert() function call"
    )
    assert body["alert_message"]["strategy_version"] == "1.3.0"
    assert body["alert_message"]["settings_fingerprint"] == expected_fingerprint
    assert "source" in body["required_payload_fields"]
    assert "strategy_version" in body["required_payload_fields"]
    assert "Copy the alert message" in body["next_actions"][0]
    assert "TradingView sends the alert message as the POST body." in body[
        "delivery_constraints"
    ]
    assert body["contract"]["status"] == "READY"
