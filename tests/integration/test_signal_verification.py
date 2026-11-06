from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    strategy_parameter_fingerprint,
)
from aurex.config.settings import get_settings
from aurex.db.base import Base
from aurex.db.models import PaperOrder, PaperTrade, RiskDecision, Signal, SignalEvent
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


def test_tradingview_verification_reports_no_signal_without_writes(
    client: TestClient,
) -> None:
    before = ledger_counts(client)

    response = client.get(
        "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=btcusdt"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NO_SIGNAL"
    assert body["verified"] is False
    assert body["delivery_verified"] is False
    assert body["pipeline_verified"] is False
    assert body["latest_signal_id"] is None
    assert body["provenance_status"] == "UNKNOWN"
    assert body["checks"][0]["check_key"] == "latest_signal_received"
    assert body["mutates_ledger"] is False
    assert ledger_counts(client) == before


def test_tradingview_verification_separates_pipeline_from_external_origin(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    webhook = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers=auth_headers(),
    )
    assert webhook.status_code == 202
    assert webhook.json()["status"] == SignalStatus.PAPER_EXECUTED
    before = ledger_counts(client)

    response = client.get(
        "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=BTCUSDT"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PIPELINE_VERIFIED_ORIGIN_UNPROVEN"
    assert body["verified"] is False
    assert body["delivery_verified"] is False
    assert body["pipeline_verified"] is True
    assert body["latest_signal_id"] == webhook.json()["id"]
    assert body["latest_signal_status"] == SignalStatus.PAPER_EXECUTED
    assert body["risk_approved"] is True
    assert body["paper_order_id"] is not None
    assert body["paper_trade_id"] is not None
    assert body["provenance_status"] == "MATCHED"
    assert body["delivery_auth_status"] == "SHARED_SECRET_VALIDATED"
    assert body["delivery_auth_transport"] == "header"
    assert body["delivery_origin_status"] == "REMOTE_IP_INVALID"
    assert body["delivery_remote_ip"] == "testclient"
    assert len(body["delivery_evidence_hash"]) == 64
    assert body["signal_event_statuses"] == [
        SignalStatus.RECEIVED,
        SignalStatus.VALIDATED,
        SignalStatus.RISK_APPROVED,
        SignalStatus.PAPER_ORDER_CREATED,
        SignalStatus.PAPER_EXECUTED,
    ]
    assert body["missing_event_statuses"] == []
    checks = {check["check_key"]: check for check in body["checks"]}
    assert checks["webhook_shared_secret_authenticated"]["status"] == "PASS"
    assert checks["webhook_payload_integrity_recorded"]["status"] == "PASS"
    assert checks["tradingview_source_ip_matched"]["status"] == "BLOCKED"
    assert {
        check["status"]
        for key, check in checks.items()
        if key != "tradingview_source_ip_matched"
    } == {"PASS"}
    assert ledger_counts(client) == before


def test_tradingview_verification_requires_authenticated_published_source_ip(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)

    with TestClient(client.app, client=("52.89.214.238", 50000)) as tradingview_client:
        webhook = tradingview_client.post(
            f"/webhooks/tradingview?secret={get_settings().webhook_secret}",
            json=valid_payload(),
        )
        assert webhook.status_code == 202
        response = tradingview_client.get(
            "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=BTCUSDT"
        )

    body = response.json()
    assert body["status"] == "VERIFIED"
    assert body["verified"] is True
    assert body["delivery_verified"] is True
    assert body["pipeline_verified"] is True
    assert body["delivery_auth_status"] == "SHARED_SECRET_VALIDATED"
    assert body["delivery_auth_transport"] == "query"
    assert body["delivery_origin_status"] == "TRADINGVIEW_SOURCE_IP_MATCHED"
    assert body["delivery_remote_ip"] == "52.89.214.238"
    assert (
        body["delivery_source_network_configuration_status"]
        == "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS"
    )
    assert body["delivery_source_networks"] == [
        "34.212.75.30/32",
        "52.32.178.7/32",
        "52.89.214.238/32",
        "54.218.53.128/32",
    ]
    assert len(body["delivery_source_networks_sha256"]) == 64
    assert {check["status"] for check in body["checks"]} == {"PASS"}


def test_authentic_delivery_can_be_proven_while_eligibility_blocks_pipeline(
    client: TestClient,
) -> None:
    with TestClient(client.app, client=("34.212.75.30", 50000)) as tradingview_client:
        webhook = tradingview_client.post(
            f"/webhooks/tradingview?secret={get_settings().webhook_secret}",
            json=valid_payload(),
        )
        assert webhook.status_code == 202
        assert webhook.json()["status"] == SignalStatus.RISK_REJECTED
        response = tradingview_client.get(
            "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=BTCUSDT"
        )

    body = response.json()
    assert body["status"] == "DELIVERY_VERIFIED_PIPELINE_BLOCKED"
    assert body["verified"] is False
    assert body["delivery_verified"] is True
    assert body["pipeline_verified"] is False
    assert body["delivery_origin_status"] == "TRADINGVIEW_SOURCE_IP_MATCHED"
    checks = {check["check_key"]: check for check in body["checks"]}
    assert checks["webhook_shared_secret_authenticated"]["status"] == "PASS"
    assert checks["webhook_payload_integrity_recorded"]["status"] == "PASS"
    assert checks["tradingview_source_ip_matched"]["status"] == "PASS"
    assert checks["risk_decision_approved"]["status"] == "BLOCKED"


def test_tradingview_verification_blocks_broad_source_network_configuration(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "tradingview_webhook_source_networks",
        "52.89.214.0/24",
    )

    with TestClient(client.app, client=("52.89.214.238", 50000)) as tradingview_client:
        webhook = tradingview_client.post(
            f"/webhooks/tradingview?secret={get_settings().webhook_secret}",
            json=valid_payload(),
        )
        assert webhook.status_code == 202
        response = tradingview_client.get(
            "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=BTCUSDT"
        )

    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["delivery_verified"] is False
    assert body["pipeline_verified"] is False
    assert body["delivery_origin_status"] == "TRADINGVIEW_SOURCE_IP_MATCHED"
    assert (
        body["delivery_source_network_configuration_status"]
        == "SOURCE_NETWORK_CONFIGURATION_UNSAFE_SCOPE"
    )
    checks = {check["check_key"]: check for check in body["checks"]}
    assert checks["tradingview_source_network_configuration_safe"]["status"] == (
        "BLOCKED"
    )
    assert checks["tradingview_source_ip_matched"]["status"] == "PASS"


def test_tradingview_verification_detects_delivery_receipt_tampering(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    webhook = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers=auth_headers(),
    )
    assert webhook.status_code == 202

    with next(client.app.dependency_overrides[get_db]()) as session:
        received_event = session.execute(
            select(SignalEvent).where(
                SignalEvent.signal_id == webhook.json()["id"],
                SignalEvent.status == SignalStatus.RECEIVED,
            )
        ).scalar_one()
        metadata = dict(received_event.metadata_json)
        delivery = dict(metadata["webhook_delivery"])
        delivery["body_size_bytes"] += 1
        metadata["webhook_delivery"] = delivery
        received_event.metadata_json = metadata
        session.commit()

    body = client.get(
        "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=BTCUSDT"
    ).json()
    checks = {check["check_key"]: check for check in body["checks"]}
    assert body["delivery_verified"] is False
    assert checks["webhook_payload_integrity_recorded"]["status"] == "BLOCKED"


def test_tradingview_verification_blocks_missing_signal_event_timeline(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    webhook = client.post(
        "/webhooks/tradingview",
        json=valid_payload(),
        headers=auth_headers(),
    )
    assert webhook.status_code == 202
    with next(client.app.dependency_overrides[get_db]()) as session:
        session.execute(
            delete(SignalEvent).where(
                SignalEvent.signal_id == webhook.json()["id"],
                SignalEvent.status == SignalStatus.PAPER_EXECUTED,
            )
        )
        session.commit()

    response = client.get(
        "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=BTCUSDT"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["verified"] is False
    assert body["missing_event_statuses"] == [SignalStatus.PAPER_EXECUTED]
    checks = {check["check_key"]: check for check in body["checks"]}
    assert checks["signal_event_timeline_complete"]["status"] == "BLOCKED"
    assert "Missing: PAPER_EXECUTED" in checks["signal_event_timeline_complete"]["evidence"]


def test_tradingview_verification_reports_rejected_latest_signal(
    client: TestClient,
) -> None:
    post_accepted_backtest(client)
    payload = valid_payload()
    payload.pop("strategy_version")
    payload.pop("settings_fingerprint")
    webhook = client.post(
        "/webhooks/tradingview",
        json=payload,
        headers=auth_headers(),
    )
    assert webhook.status_code == 202
    assert webhook.json()["status"] == SignalStatus.RISK_REJECTED
    before = ledger_counts(client)

    response = client.get(
        "/signals/tradingview-verification?strategy=trend_pullback_v1&symbol=BTCUSDT"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["verified"] is False
    assert body["latest_signal_id"] == webhook.json()["id"]
    assert body["latest_signal_status"] == SignalStatus.RISK_REJECTED
    assert body["risk_approved"] is False
    assert body["paper_order_id"] is None
    assert body["paper_trade_id"] is None
    assert body["provenance_status"] == "BLOCKED"
    assert body["signal_event_statuses"] == [
        SignalStatus.RECEIVED,
        SignalStatus.VALIDATED,
        SignalStatus.RISK_REJECTED,
    ]
    assert body["missing_event_statuses"] == []
    checks = {check["check_key"]: check for check in body["checks"]}
    assert checks["signal_event_timeline_complete"]["status"] == "PASS"
    assert checks["risk_decision_approved"]["status"] == "BLOCKED"
    assert checks["signal_provenance_matched"]["status"] == "BLOCKED"
    assert checks["paper_order_created"]["status"] == "BLOCKED"
    assert ledger_counts(client) == before


def auth_headers() -> dict[str, str]:
    return {"X-Aurex-Webhook-Secret": get_settings().webhook_secret}


def test_forwarded_sender_cannot_forge_main_app_delivery(client: TestClient) -> None:
    before = ledger_counts(client)
    wrapped = ProxyHeadersMiddleware(client.app, trusted_hosts="127.0.0.1")
    with TestClient(wrapped, client=("127.0.0.1", 1234)) as proxy_client:
        response = proxy_client.post(
            "/webhooks/tradingview",
            json=valid_payload(),
            headers=auth_headers() | {"X-Forwarded-For": "52.89.214.238"},
        )
    assert response.status_code == 400
    assert ledger_counts(client) == before


def ledger_counts(client: TestClient) -> dict[str, int]:
    with next(client.app.dependency_overrides[get_db]()) as session:
        return {
            "signals": count_rows(session, Signal),
            "risk_decisions": count_rows(session, RiskDecision),
            "paper_orders": count_rows(session, PaperOrder),
            "paper_trades": count_rows(session, PaperTrade),
        }


def count_rows(session: Session, model: type) -> int:
    return int(session.execute(select(func.count(model.id))).scalar_one())
