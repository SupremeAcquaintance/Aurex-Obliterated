from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
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
from aurex.db.models import Account, PaperTrade, RiskDecision, RiskProfile, Signal
from aurex.domain.enums import SignalStatus
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


def valid_payload() -> dict[str, object]:
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


def test_tradingview_signal_preflight_passes_without_mutating_ledger(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    before = ledger_counts(client)

    response = client.post("/signals/preflight/tradingview", json=valid_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PASS"
    assert body["would_execute_paper"] is True
    assert body["reason"] == "Risk approved"
    assert body["mutates_ledger"] is False
    assert body["duplicate_status"] == "CLEAR"
    assert body["duplicate_signal_id"] is None
    assert body["duplicate_cooldown_minutes"] == get_settings().duplicate_cooldown_minutes
    assert body["expected_webhook_status"] == SignalStatus.PAPER_EXECUTED
    assert body["expected_webhook_http_status"] == 202
    assert len(body["idempotency_key"]) == 64
    assert body["contract"]["status"] == "READY"
    assert body["rules_snapshot"]["signal_backtest_provenance_gate"]["blocked"] is False
    assert Decimal(body["position_size"]) == Decimal("1")
    assert ledger_counts(client) == before


def test_tradingview_signal_preflight_pass_matches_real_webhook(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = valid_payload()
    preflight = client.post("/signals/preflight/tradingview", json=payload).json()

    webhook = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )

    assert preflight["status"] == "PASS"
    assert webhook.status_code == preflight["expected_webhook_http_status"]
    assert webhook.json()["status"] == preflight["expected_webhook_status"]
    assert webhook.json()["status"] == SignalStatus.PAPER_EXECUTED


def test_tradingview_signal_preflight_blocks_missing_provenance_without_writes(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = valid_payload()
    payload.pop("strategy_version")
    payload.pop("settings_fingerprint")
    before = ledger_counts(client)

    response = client.post("/signals/preflight/tradingview", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["would_execute_paper"] is False
    assert body["reason"] == (
        "Paper trading requires signal provenance matching accepted backtest: "
        "signal_strategy_version_missing"
    )
    provenance_gate = body["rules_snapshot"]["signal_backtest_provenance_gate"]
    assert provenance_gate["blocked"] is True
    assert provenance_gate["reasons"] == [
        "signal_strategy_version_missing",
        "signal_settings_fingerprint_missing",
    ]
    assert body["mutates_ledger"] is False
    assert body["expected_webhook_status"] == SignalStatus.RISK_REJECTED
    assert body["expected_webhook_http_status"] == 202
    assert ledger_counts(client) == before


def test_tradingview_signal_preflight_block_matches_real_webhook(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = valid_payload()
    payload.pop("strategy_version")
    payload.pop("settings_fingerprint")
    preflight = client.post("/signals/preflight/tradingview", json=payload).json()

    webhook = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )

    assert preflight["status"] == "BLOCKED"
    assert webhook.status_code == preflight["expected_webhook_http_status"]
    assert webhook.json()["status"] == preflight["expected_webhook_status"]
    assert webhook.json()["rejection_reason"] == preflight["reason"]


def test_tradingview_signal_preflight_reports_duplicate_without_writes(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = valid_payload()
    webhook = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )
    assert webhook.status_code == 202
    before = ledger_counts(client)

    response = client.post("/signals/preflight/tradingview", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DUPLICATE_BLOCKED"
    assert body["would_execute_paper"] is False
    assert body["reason"] == "Duplicate signal within configured cooldown window"
    assert body["reasons"] == ["duplicate_signal_within_cooldown"]
    assert body["duplicate_status"] == "DUPLICATE"
    assert body["duplicate_signal_id"] == webhook.json()["id"]
    assert body["expected_webhook_status"] == SignalStatus.DUPLICATE_REJECTED
    assert body["expected_webhook_http_status"] == 409
    assert len(body["idempotency_key"]) == 64
    assert body["mutates_ledger"] is False
    assert ledger_counts(client) == before


def test_tradingview_signal_preflight_duplicate_matches_real_webhook(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = valid_payload()
    first_webhook = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )
    assert first_webhook.status_code == 202
    preflight = client.post("/signals/preflight/tradingview", json=payload).json()

    duplicate_webhook = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )

    assert preflight["status"] == "DUPLICATE_BLOCKED"
    assert duplicate_webhook.status_code == preflight["expected_webhook_http_status"]
    assert duplicate_webhook.json()["status"] == preflight["expected_webhook_status"]
    assert duplicate_webhook.json()["duplicate_of_signal_id"] == first_webhook.json()["id"]


def auth_headers() -> dict[str, str]:
    return {"X-Aurex-Webhook-Secret": get_settings().webhook_secret}


def ledger_counts(client: TestClient) -> dict[str, int]:
    with next(client.app.dependency_overrides[get_db]()) as session:
        return {
            "accounts": count_rows(session, Account),
            "risk_profiles": count_rows(session, RiskProfile),
            "signals": count_rows(session, Signal),
            "risk_decisions": count_rows(session, RiskDecision),
            "paper_trades": count_rows(session, PaperTrade),
        }


def count_rows(session: Session, model: type) -> int:
    return int(session.execute(select(func.count(model.id))).scalar_one())
