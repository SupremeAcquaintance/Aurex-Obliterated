import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from aurex.api.dependencies import get_db
from aurex.api.webhook_ingress import MAX_BODY_BYTES, DirectWebhookBoundary, create_webhook_ingress
from aurex.config.settings import Settings
from aurex.db.base import Base
from aurex.db.models import BrokerFill, BrokerOrder, PaperOrder, PaperTrade, Position, Signal
from aurex.signal_gateway.service import tradingview_signal_verification
from aurex.signal_gateway.tradingview_external_proof import EXPECTED_SETTINGS_FINGERPRINT

SECRET = "ingress-integration-fixture-only-" + "x" * 32
SENDER = ("52.89.214.238", 50123)


@pytest.fixture()
def ingress():
    settings = Settings(_env_file=None, webhook_secret=SECRET)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    app = create_webhook_ingress(settings)

    def database():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = database
    yield app, sessions, settings
    engine.dispose()


def payload():
    return {
        "source": "tradingview",
        "strategy": "trend_pullback_v1",
        "strategy_version": "1.3.0",
        "settings_fingerprint": EXPECTED_SETTINGS_FINGERPRINT,
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": "LONG",
        "entry_price": "64000",
        "stop_loss": "63000",
        "take_profit": "66000",
        "market_regime": "TRENDING_UP",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_synthetic_direct_receipt_rejects_retired_candidate_without_orders(ingress):
    app, sessions, settings = ingress
    raw = json.dumps(payload(), indent=2).encode()
    with TestClient(app, base_url="https://testserver", client=SENDER) as client:
        response = client.post(
            "/webhooks/tradingview", params={"secret": SECRET},
            content=raw, headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "RISK_REJECTED"
        with sessions() as session:
            verification = tradingview_signal_verification(
                session, settings, strategy="trend_pullback_v1", symbol="BTCUSDT"
            )
            assert verification.status == "DELIVERY_VERIFIED_PIPELINE_BLOCKED"
            assert verification.delivery_verified is True
            assert verification.pipeline_verified is False
            assert verification.signal_event_statuses == ["RECEIVED", "VALIDATED", "RISK_REJECTED"]
        duplicate = client.post(
            "/webhooks/tradingview", content=raw,
            headers={"Content-Type": "application/json", "X-Aurex-Webhook-Secret": SECRET},
        )
        assert duplicate.status_code == 409
    with sessions() as session:
        verification = tradingview_signal_verification(
            session, settings, strategy="trend_pullback_v1", symbol="BTCUSDT"
        )
        assert verification.delivery_body_sha256 == sha256(raw).hexdigest()
        assert SECRET not in verification.model_dump_json()
        for model in (PaperOrder, PaperTrade, BrokerOrder, BrokerFill, Position):
            assert count(session, model) == 0
        assert count(session, Signal) == 2


@pytest.mark.parametrize("path", ["/dashboard", "/docs", "/openapi.json", "/risk", "/live"])
def test_management_surface_is_not_exposed(ingress, path):
    app, sessions, _ = ingress
    with TestClient(app, base_url="https://testserver", client=SENDER) as client:
        assert client.get(path).status_code == 404
        assert client.post(path, json=payload()).status_code == 404
    with sessions() as session:
        assert count(session, Signal) == 0


@pytest.mark.parametrize(
    ("base_url", "peer", "headers", "expected"),
    [
        ("http://testserver", SENDER, {}, 400),
        ("https://testserver", ("127.0.0.1", 1234), {}, 403),
        ("https://testserver", SENDER, {"X-Forwarded-For": SENDER[0]}, 400),
        ("https://testserver", SENDER, {"Forwarded": f"for={SENDER[0]}"}, 400),
        ("https://testserver", SENDER, {"X-Real-IP": SENDER[0]}, 400),
        ("https://testserver", SENDER, {"Content-Type": "text/plain"}, 415),
        ("https://testserver", SENDER, {"X-Aurex-Webhook-Secret": "bad"}, 401),
    ],
)
def test_bad_transport_source_or_authentication_never_writes(
    ingress, base_url, peer, headers, expected
):
    app, sessions, _ = ingress
    auth = {"X-Aurex-Webhook-Secret": SECRET} | headers
    with TestClient(app, base_url=base_url, client=peer) as client:
        response = client.post("/webhooks/tradingview", json=payload(), headers=auth)
        assert response.status_code == expected
        assert SECRET not in response.text
    with sessions() as session:
        assert count(session, Signal) == 0


def test_uvicorn_proxy_rewriting_cannot_forge_a_receipt(ingress):
    app, sessions, _ = ingress
    wrapped = ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1")
    with TestClient(wrapped, client=("127.0.0.1", 1234)) as client:
        response = client.post(
            "/webhooks/tradingview", json=payload(),
            headers={"X-Forwarded-For": SENDER[0], "X-Forwarded-Proto": "https",
                     "X-Aurex-Webhook-Secret": SECRET},
        )
    assert response.status_code == 400
    with sessions() as session:
        assert count(session, Signal) == 0


@pytest.mark.parametrize("field,value", [
    ("strategy", "jam_reversal_v1"), ("symbol", "ETHUSDT"),
    ("timeframe", "30m"), ("strategy_version", "1.2.0"),
    ("settings_fingerprint", "wrong-settings"),
])
def test_campaign_scope_cannot_expand(ingress, field, value):
    app, sessions, _ = ingress
    with TestClient(app, base_url="https://testserver", client=SENDER) as client:
        response = client.post(
            "/webhooks/tradingview", json=payload() | {field: value},
            headers={"X-Aurex-Webhook-Secret": SECRET},
        )
    assert response.status_code == 422
    with sessions() as session:
        assert count(session, Signal) == 0


def test_ambiguous_secret_and_oversized_body_are_rejected(ingress):
    app, sessions, _ = ingress
    with TestClient(app, base_url="https://testserver", client=SENDER) as client:
        assert client.post(
            "/webhooks/tradingview", params=[("secret", SECRET), ("secret", SECRET)],
            json=payload(),
        ).status_code == 401
        assert client.post(
            "/webhooks/tradingview", params={"secret": "invalid-\u00e9-secret"}, json=payload(),
        ).status_code == 401
        assert client.post(
            "/webhooks/tradingview", content=b" " * (MAX_BODY_BYTES + 1),
            headers={"Content-Type": "application/json", "X-Aurex-Webhook-Secret": SECRET},
        ).status_code == 413
    with sessions() as session:
        assert count(session, Signal) == 0


def test_runtime_safety_configuration_change_fails_closed(ingress):
    app, sessions, settings = ingress
    with TestClient(app, base_url="https://testserver", client=SENDER) as client:
        settings.live_trading_enabled = True
        assert client.post(
            "/webhooks/tradingview", json=payload(),
            headers={"X-Aurex-Webhook-Secret": SECRET},
        ).status_code == 503
    with sessions() as session:
        assert count(session, Signal) == 0


@pytest.mark.parametrize("case", ["oversized_chunks", "slow_body", "disconnect"])
def test_streaming_body_limits_before_application_or_database(case, monkeypatch):
    async def scenario():
        async def forbidden_app(*args):
            pytest.fail("Rejected body reached the application")

        boundary = DirectWebhookBoundary(
            forbidden_app, Settings(_env_file=None, webhook_secret=SECRET)
        )
        scope = {
            "type": "http", "method": "POST", "path": "/webhooks/tradingview",
            "scheme": "https", "client": SENDER, "query_string": b"",
            "headers": [(b"content-type", b"application/json"),
                        (b"x-aurex-webhook-secret", SECRET.encode()), (b"content-length", b"1")],
        }
        messages = []

        async def send(message):
            messages.append(message)

        async def receive():
            if case == "slow_body":
                await asyncio.sleep(1)
            if case == "disconnect":
                return {"type": "http.disconnect"}
            return {"type": "http.request", "body": b"x" * 9000, "more_body": True}

        await boundary(scope, receive, send)
        if case == "disconnect":
            assert messages == []
        else:
            assert messages[0]["status"] == (408 if case == "slow_body" else 413)

    monkeypatch.setattr("aurex.api.webhook_ingress.BODY_TIMEOUT_SECONDS", 0.01)
    asyncio.run(scenario())
