import json
import os
import sqlite3
import sys
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.db.base import Base
from aurex.db.models import PredictionEvidenceEvent, PredictionSettlement
from aurex.domain.enums import (
    PredictionMarketEvidenceKind,
    PredictionMarketOrderStatus,
    ReconciliationStatus,
)
from aurex.prediction_market.paper import hash_evidence_payload


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


def create_mkt_runtime_fixture(root) -> None:
    python_dir = root / "python"
    electron_dir = root / "electron" / "system"
    python_dir.mkdir(parents=True, exist_ok=True)
    electron_dir.mkdir(parents=True, exist_ok=True)
    (python_dir / "config.py").write_text(
        "\n".join(
            [
                "DEFAULT_CONFIG: dict[str, object] = {",
                '    "kalshi_env": "demo",',
                '    "enable_trading": False,',
                '    "crypto15m_live": False,',
                '    "gambling_mode": False,',
                "}",
                "",
            ],
        ),
        encoding="utf-8",
    )
    (electron_dir / "settings-store.ts").write_text(
        "\n".join(
            [
                "export const DEFAULT_CONFIG = {",
                "  kalshiEnv: 'demo',",
                "  enableTrading: false,",
                "  crypto15mLive: false,",
                "  gamblingMode: false,",
                "};",
                "",
            ],
        ),
        encoding="utf-8",
    )
    (root / "electron" / "main.ts").write_text(
        "\n".join(
            [
                "import { app } from 'electron';",
                "const scopedUserData = process.env.KRYPT_TRADER_USERDATA?.trim();",
                "if (scopedUserData) {",
                "  app.setPath('userData', scopedUserData);",
                "}",
                "",
            ],
        ),
        encoding="utf-8",
    )
    (electron_dir / "python-backend.ts").write_text(
        "\n".join(
            [
                "import { app } from 'electron';",
                "const userData = app.getPath('userData');",
                "const env = { ...process.env, KRYPT_TRADER_USERDATA: userData };",
                "void env;",
                "",
            ],
        ),
        encoding="utf-8",
    )
    for filename in [
        "db.py",
        "service.py",
        "scanner.py",
        "crypto15m_record.py",
        "backtest.py",
    ]:
        (python_dir / filename).write_text("# fixture\n", encoding="utf-8")
    (root / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "predev": "node scripts/setup-python.mjs",
                    "dev": "vite",
                    "py:setup": "node scripts/setup-python.mjs",
                },
            },
        )
        + "\n",
        encoding="utf-8",
    )


def write_mkt_settings(path, config: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"config": config}), encoding="utf-8")


def test_prediction_market_api_runs_paper_flow_without_live_execution(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    )
    assert contract.status_code == 200
    contract_id = contract.json()["id"]

    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract_id,
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "api-paper-flow",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        },
    )
    assert intent.status_code == 200
    intent_body = intent.json()
    assert intent_body["status"] == PredictionMarketOrderStatus.CREATED
    assert intent_body["intent_snapshot"]["paper_only"] is True
    assert intent_body["intent_snapshot"]["research_gate"]["approved"] is True
    assert intent_body["intent_snapshot"]["research_gate"]["live_execution"] == "blocked"

    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent_body['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 450,
            "execution_price": "0.60",
            "raw_payload": {"book_depth": "api-fixture"},
        },
    )
    assert submission.status_code == 200
    submission_body = submission.json()
    assert submission_body["order"]["status"] == PredictionMarketOrderStatus.FILLED
    assert Decimal(submission_body["fill"]["fees"]) == Decimal("0.16800000")
    position_id = submission_body["position"]["id"]

    settlement = client.post(
        f"/prediction-market/paper/positions/{position_id}/settle",
        json={"settlement_value": "1"},
    )
    assert settlement.status_code == 200
    assert Decimal(settlement.json()["realized_pl"]) == Decimal("3.83200000")

    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED

    readiness = client.get("/prediction-market/paper/demo-readiness")
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["status"] == "PAPER_DEMO_VERIFIED"
    assert readiness_body["ready_to_start"] is True
    assert readiness_body["demo_lifecycle_verified"] is True
    assert readiness_body["current_check"] is None
    assert readiness_body["completed_check_count"] == 8
    assert readiness_body["total_check_count"] == 8
    assert readiness_body["progress_pct"] == 100
    assert readiness_body["evidence"]["eligible_mkt_research_candidates"] == 1
    assert readiness_body["evidence"]["approved_research_intents"] == 1
    assert readiness_body["evidence"]["fills"] == 1
    assert readiness_body["evidence"]["settlements"] == 1
    assert readiness_body["evidence"]["countable_ledger_records"] == 1
    assert readiness_body["evidence"]["ledger_blocked_records"] == 0
    assert readiness_body["evidence"]["latest_reconciliation_status"] == (
        ReconciliationStatus.MATCHED
    )

    summary = client.get("/prediction-market/summary")
    assert summary.status_code == 200
    summary_body = summary.json()
    assert summary_body["contracts"] == 1
    assert summary_body["orders"] == 1
    assert summary_body["fills"] == 1
    assert summary_body["settled_positions"] == 1
    assert summary_body["live_execution_enabled"] is False

    evidence = client.get("/prediction-market/evidence")
    assert evidence.status_code == 200
    evidence_kinds = {event["kind"] for event in evidence.json()}
    assert PredictionMarketEvidenceKind.MARKET_SNAPSHOT in evidence_kinds
    assert PredictionMarketEvidenceKind.SETTLEMENT_RECORDED in evidence_kinds
    assert PredictionMarketEvidenceKind.POSITION_RECONCILED in evidence_kinds


def test_prediction_market_api_blocks_rejected_intent_submission(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()

    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_momentum_research_candidate",
            "side": "YES",
            "quantity": "100",
            "limit_price": "0.70",
            "idempotency_key": "api-risk-block",
            "risk_limits": {
                "max_order_cost": "10",
                "max_contract_exposure": "10",
                "max_open_positions": 25,
            },
        },
    )
    assert intent.status_code == 200
    intent_body = intent.json()
    assert intent_body["status"] == PredictionMarketOrderStatus.REJECTED
    assert "prediction_research_candidate_missing_for_mkt_strategy" in (
        intent_body["intent_snapshot"]["rejection_reasons"]
    )

    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent_body['id']}/submit",
        json={"available_quantity": "100", "latency_ms": 100, "execution_price": "0.70"},
    )
    assert submission.status_code == 400
    assert submission.json()["detail"] == "Rejected prediction order intents cannot be submitted"

    summary = client.get("/prediction-market/summary").json()
    assert summary["rejected_intents"] == 1
    assert summary["orders"] == 0


def test_prediction_market_api_manually_cancels_partial_paper_order(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "api-manual-cancel",
        },
    ).json()
    submitted = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "4",
            "latency_ms": 100,
            "execution_price": "0.60",
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["order"]["status"] == PredictionMarketOrderStatus.PARTIALLY_FILLED

    cancelled = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/cancel",
        json={"reason": "operator_manual_cancel"},
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == PredictionMarketOrderStatus.CANCELLED
    orders = client.get("/prediction-market/paper/orders").json()
    assert orders[0]["status"] == PredictionMarketOrderStatus.CANCELLED
    assert orders[0]["cancelled_at"] is not None
    assert orders[0]["filled_quantity"] == "4.000000000000"
    evidence = client.get("/prediction-market/evidence").json()
    cancel_events = [
        event
        for event in evidence
        if event["kind"] == PredictionMarketEvidenceKind.ORDER_CANCELLED
    ]
    assert cancel_events
    assert cancel_events[0]["payload"]["reason"] == "operator_manual_cancel"
    assert cancel_events[0]["payload"]["filled_quantity"] == "4.000000000000"


def test_prediction_market_api_accumulates_additional_partial_fills(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.61",
            "idempotency_key": "api-multi-partial-fill",
        },
    ).json()

    first = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "4",
            "latency_ms": 100,
            "execution_price": "0.60",
        },
    )
    second = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 120,
            "execution_price": "0.61",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["order"]["id"] == second_body["order"]["id"]
    assert second_body["order"]["status"] == PredictionMarketOrderStatus.FILLED
    assert Decimal(second_body["order"]["filled_quantity"]) == Decimal("10")
    assert Decimal(second_body["order"]["average_fill_price"]) == Decimal("0.606")
    assert Decimal(second_body["order"]["fees"]) == Decimal("0.167118")
    assert Decimal(second_body["fill"]["quantity"]) == Decimal("6")
    assert second_body["fill"]["external_fill_id"].endswith("-2")
    assert Decimal(second_body["position"]["quantity"]) == Decimal("10")
    assert Decimal(second_body["position"]["average_entry_price"]) == Decimal("0.606")
    assert Decimal(second_body["position"]["fees"]) == Decimal("0.167118")

    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED
    summary = client.get("/prediction-market/summary").json()
    assert summary["orders"] == 1
    assert summary["fills"] == 2
    assert summary["open_positions"] == 1


def test_prediction_market_api_sells_to_close_paper_position_without_live_execution(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    buy_intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "action": "BUY",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "api-buy-before-sell-close",
        },
    ).json()
    buy_submission = client.post(
        f"/prediction-market/paper/order-intents/{buy_intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 100,
            "execution_price": "0.60",
        },
    )
    assert buy_submission.status_code == 200

    sell_intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "action": "SELL",
            "quantity": "4",
            "limit_price": "0.58",
            "idempotency_key": "api-sell-to-close-partial",
        },
    )
    assert sell_intent.status_code == 200
    sell_intent_body = sell_intent.json()
    assert sell_intent_body["status"] == PredictionMarketOrderStatus.CREATED
    assert sell_intent_body["intent_snapshot"]["execution_boundary"] == (
        "paper_sell_to_close_only_no_short_selling_no_live_execution"
    )

    sell_submission = client.post(
        f"/prediction-market/paper/order-intents/{sell_intent_body['id']}/submit",
        json={
            "available_quantity": "4",
            "latency_ms": 100,
            "execution_price": "0.59",
        },
    )
    assert sell_submission.status_code == 200
    sell_body = sell_submission.json()
    assert sell_body["order"]["status"] == PredictionMarketOrderStatus.FILLED
    assert sell_body["order"]["action"] == "SELL"
    assert Decimal(sell_body["fill"]["fees"]) == Decimal("0.06773200")
    assert sell_body["position"]["status"] == "OPEN"
    assert Decimal(sell_body["position"]["quantity"]) == Decimal("6.000000000000")
    assert Decimal(sell_body["position"]["fees"]) == Decimal("0.10080000")
    assert Decimal(sell_body["position"]["realized_sell_to_close_fees"]) == Decimal(
        "0.13493200"
    )
    assert Decimal(sell_body["position"]["lifecycle_fees"]) == Decimal("0.23573200")
    assert Decimal(sell_body["position"]["realized_pl"]) == Decimal("-0.17493200")

    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED
    summary = client.get("/prediction-market/summary").json()
    assert summary["orders"] == 2
    assert summary["fills"] == 2
    assert summary["open_positions"] == 1
    assert summary["live_execution_enabled"] is False


def test_prediction_market_api_settlement_preserves_prior_sell_to_close_pl(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    buy_intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "action": "BUY",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "api-settle-after-partial-sell-buy",
        },
    ).json()
    buy_submission = client.post(
        f"/prediction-market/paper/order-intents/{buy_intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 100,
            "execution_price": "0.60",
        },
    ).json()
    position_id = buy_submission["position"]["id"]
    sell_intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "action": "SELL",
            "quantity": "4",
            "limit_price": "0.58",
            "idempotency_key": "api-settle-after-partial-sell-close",
        },
    ).json()
    client.post(
        f"/prediction-market/paper/order-intents/{sell_intent['id']}/submit",
        json={
            "available_quantity": "4",
            "latency_ms": 100,
            "execution_price": "0.59",
        },
    )

    settlement = client.post(
        f"/prediction-market/paper/positions/{position_id}/settle",
        json={"settlement_value": "1"},
    )

    assert settlement.status_code == 200
    settlement_body = settlement.json()
    assert Decimal(settlement_body["gross_payout"]) == Decimal("6")
    assert Decimal(settlement_body["fees"]) == Decimal("0.235732")
    assert Decimal(settlement_body["realized_pl"]) == Decimal("2.124268")
    assert settlement_body["raw_payload"]["prior_realized_pl"] == "-0.17493200"
    assert settlement_body["raw_payload"]["remaining_settlement_realized_pl"] == (
        "2.29920000"
    )
    assert settlement_body["raw_payload"]["prior_realized_fees"] == "0.13493200"
    assert settlement_body["raw_payload"]["remaining_settlement_fees"] == "0.10080000"
    assert settlement_body["raw_payload"]["total_lifecycle_fees"] == "0.23573200"
    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED
    positions = client.get("/prediction-market/paper/positions").json()
    assert Decimal(positions[0]["realized_pl"]) == Decimal("2.124268")
    assert Decimal(positions[0]["realized_sell_to_close_fees"]) == Decimal("0.134932")
    assert Decimal(positions[0]["lifecycle_fees"]) == Decimal("0.235732")
    assert positions[0]["raw_payload"]["total_lifecycle_fees"] == "0.23573200"
    evidence = client.get("/prediction-market/evidence").json()
    settlement_events = [
        event
        for event in evidence
        if event["kind"] == PredictionMarketEvidenceKind.SETTLEMENT_RECORDED
    ]
    assert settlement_events[-1]["payload"]["prior_realized_pl"] == "-0.17493200"
    assert settlement_events[-1]["payload"]["remaining_settlement_realized_pl"] == (
        "2.29920000"
    )
    assert settlement_events[-1]["payload"]["realized_pl"] == "2.12426800"
    assert settlement_events[-1]["payload"]["fees"] == "0.23573200"
    assert settlement_events[-1]["payload"]["prior_realized_fees"] == "0.13493200"
    assert settlement_events[-1]["payload"]["remaining_settlement_fees"] == (
        "0.10080000"
    )
    assert settlement_events[-1]["payload"]["total_lifecycle_fees"] == "0.23573200"


def test_prediction_market_api_rejects_stale_quote_snapshot_when_requested(
    client: TestClient,
) -> None:
    old_observed_at = datetime.now(UTC) - timedelta(hours=2)
    csv_text = "\n".join(
        [
            (
                "venue,event_ticker,market_title,contract_ticker,contract_title,category,"
                "status,yes_bid_price,yes_ask_price,no_bid_price,no_ask_price,closes_at,"
                "expiration_at,observed_at"
            ),
            (
                "KALSHI,KXSTALE-26JUN25,Stale quote test,"
                "KXSTALE-26JUN25-B1,Stale quote contract,crypto,OPEN,0.59,0.60,"
                f"0.40,0.41,2026-06-25T20:00:00Z,2026-06-25T20:00:00Z,"
                f"{old_observed_at.isoformat()}"
            ),
        ]
    )
    imported = client.post(
        "/prediction-market/contracts/import-csv",
        json={
            "source": "kalshi_export",
            "source_reference": "manual:stale-quote",
            "csv_text": csv_text,
            "csv_format": "aurex",
        },
    )
    assert imported.status_code == 200
    contract = client.get("/prediction-market/contracts").json()[0]

    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "quantity": "1",
            "limit_price": "0.60",
            "idempotency_key": "api-stale-quote-risk-block",
            "risk_limits": {
                "max_order_cost": "50",
                "max_contract_exposure": "50",
                "max_open_positions": 25,
                "max_quote_age_seconds": 900,
            },
        },
    )

    assert intent.status_code == 200
    body = intent.json()
    assert body["status"] == PredictionMarketOrderStatus.REJECTED
    assert body["intent_snapshot"]["rejection_reasons"] == [
        "prediction_quote_snapshot_stale"
    ]
    assert body["intent_snapshot"]["quote_freshness"]["age_seconds"] > 900
    assert body["intent_snapshot"]["quote_freshness"]["max_quote_age_seconds"] == 900
    assert body["intent_snapshot"]["quote_freshness"]["stale"] is True
    assert client.get("/prediction-market/summary").json()["orders"] == 0
    evidence = client.get("/prediction-market/evidence").json()
    risk_blocks = [
        event for event in evidence if event["kind"] == PredictionMarketEvidenceKind.RISK_BLOCK
    ]
    assert risk_blocks[-1]["payload"]["quote_freshness"]["rejection_reason"] == (
        "prediction_quote_snapshot_stale"
    )


def test_prediction_market_api_rejects_wide_quote_spread_when_requested(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()

    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "quantity": "1",
            "limit_price": "0.60",
            "idempotency_key": "api-wide-spread-risk-block",
            "risk_limits": {
                "max_order_cost": "50",
                "max_contract_exposure": "50",
                "max_open_positions": 25,
                "max_spread": "0.005",
            },
        },
    )

    assert intent.status_code == 200
    body = intent.json()
    assert body["status"] == PredictionMarketOrderStatus.REJECTED
    assert body["intent_snapshot"]["rejection_reasons"] == [
        "prediction_quote_spread_exceeds_limit"
    ]
    assert body["intent_snapshot"]["risk_limits"]["max_spread"] == "0.005"
    quote_spread = body["intent_snapshot"]["quote_spread"]
    assert quote_spread["side"] == "YES"
    assert Decimal(quote_spread["bid"]) == Decimal("0.59")
    assert Decimal(quote_spread["ask"]) == Decimal("0.60")
    assert Decimal(quote_spread["spread"]) == Decimal("0.01")
    assert Decimal(quote_spread["max_spread"]) == Decimal("0.005")
    assert quote_spread["rejection_reason"] == "prediction_quote_spread_exceeds_limit"
    assert client.get("/prediction-market/summary").json()["orders"] == 0
    evidence = client.get("/prediction-market/evidence").json()
    risk_blocks = [
        event for event in evidence if event["kind"] == PredictionMarketEvidenceKind.RISK_BLOCK
    ]
    assert risk_blocks[-1]["payload"]["quote_spread"]["rejection_reason"] == (
        "prediction_quote_spread_exceeds_limit"
    )


def test_prediction_market_api_rejects_order_submission_when_latency_exceeds_limit(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "api-latency-risk-block",
            "risk_limits": {
                "max_order_cost": "50",
                "max_contract_exposure": "50",
                "max_open_positions": 25,
                "max_latency_ms": 250,
            },
        },
    )
    assert intent.status_code == 200
    assert intent.json()["status"] == PredictionMarketOrderStatus.CREATED

    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent.json()['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 300,
            "execution_price": "0.60",
        },
    )

    assert submission.status_code == 200
    body = submission.json()
    assert body["order"]["status"] == PredictionMarketOrderStatus.REJECTED
    assert body["order"]["raw_payload"]["execution_latency"] == {
        "latency_ms": 300,
        "max_latency_ms": 250,
        "exceeded": True,
        "rejection_reason": "prediction_execution_latency_exceeds_limit",
    }
    assert body["fill"] is None
    assert body["position"] is None
    summary = client.get("/prediction-market/summary").json()
    assert summary["orders"] == 1
    assert summary["fills"] == 0
    assert summary["open_positions"] == 0
    evidence = client.get("/prediction-market/evidence").json()
    risk_blocks = [
        event for event in evidence if event["kind"] == PredictionMarketEvidenceKind.RISK_BLOCK
    ]
    assert risk_blocks[-1]["payload"]["execution_latency"]["rejection_reason"] == (
        "prediction_execution_latency_exceeds_limit"
    )


def test_prediction_market_api_rejects_order_submission_when_slippage_exceeds_limit(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.65",
            "idempotency_key": "api-slippage-risk-block",
            "risk_limits": {
                "max_order_cost": "50",
                "max_contract_exposure": "50",
                "max_open_positions": 25,
                "max_slippage": "0.01",
            },
        },
    )
    assert intent.status_code == 200
    assert intent.json()["status"] == PredictionMarketOrderStatus.CREATED

    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent.json()['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 100,
            "execution_price": "0.62",
        },
    )

    assert submission.status_code == 200
    body = submission.json()
    assert body["order"]["status"] == PredictionMarketOrderStatus.REJECTED
    slippage = body["order"]["raw_payload"]["execution_slippage"]
    assert slippage["side"] == "YES"
    assert slippage["action"] == "BUY"
    assert Decimal(slippage["reference_price"]) == Decimal("0.60")
    assert Decimal(slippage["execution_price"]) == Decimal("0.62")
    assert Decimal(slippage["adverse_slippage"]) == Decimal("0.02")
    assert Decimal(slippage["max_slippage"]) == Decimal("0.01")
    assert slippage["exceeded"] is True
    assert slippage["rejection_reason"] == "prediction_execution_slippage_exceeds_limit"
    assert body["fill"] is None
    assert body["position"] is None
    summary = client.get("/prediction-market/summary").json()
    assert summary["orders"] == 1
    assert summary["fills"] == 0
    assert summary["open_positions"] == 0
    evidence = client.get("/prediction-market/evidence").json()
    risk_blocks = [
        event for event in evidence if event["kind"] == PredictionMarketEvidenceKind.RISK_BLOCK
    ]
    assert risk_blocks[-1]["payload"]["execution_slippage"]["rejection_reason"] == (
        "prediction_execution_slippage_exceeds_limit"
    )


def test_prediction_market_api_requires_mkt_research_gate_before_paper_intent(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()

    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "1",
            "limit_price": "0.60",
            "idempotency_key": "api-research-gate-block",
        },
    )

    assert intent.status_code == 200
    body = intent.json()
    assert body["status"] == PredictionMarketOrderStatus.REJECTED
    assert body["intent_snapshot"]["research_gate"]["required"] is True
    assert body["intent_snapshot"]["research_gate"]["approved"] is False
    assert body["intent_snapshot"]["research_gate"]["reason"] == (
        "prediction_research_candidate_missing_for_mkt_strategy"
    )
    assert body["intent_snapshot"]["rejection_reasons"] == [
        "prediction_research_candidate_missing_for_mkt_strategy"
    ]

    readiness = client.get("/prediction-market/paper/demo-readiness").json()
    assert readiness["status"] == "BLOCKED"
    assert readiness["ready_to_start"] is False
    assert readiness["demo_lifecycle_verified"] is False
    assert readiness["current_check"]["key"] == "eligible_mkt_research_candidate"
    assert readiness["completed_check_count"] == 2
    assert readiness["total_check_count"] == 8
    assert readiness["progress_pct"] == 25
    assert readiness["next_action"] == (
        "Pass an Aurex research gate for at least one MKT-derived candidate."
    )
    runbook = client.get("/prediction-market/paper/demo-runbook").json()
    assert runbook["status"] == "RUNBOOK_READINESS_BLOCKED"
    assert runbook["readiness_status"] == "BLOCKED"
    assert runbook["progress_status"] == "NO_PAPER_DEMO_RECORDS"
    assert runbook["current_step"]["key"] == "eligible_mkt_research_candidate"
    assert runbook["current_step"]["next_action"].startswith(
        "Resolve upstream MKT research runbook first:"
    )
    assert isinstance(runbook["upstream_research_runbook"], dict)
    assert runbook["upstream_research_runbook"]["live_execution_enabled"] is False
    assert "status" in runbook["upstream_research_runbook"]
    assert "next_action" in runbook["upstream_research_runbook"]
    assert "db_freshness_status" in runbook["upstream_research_runbook"]
    assert "collection_health" in runbook["upstream_research_runbook"]
    assert "processed_observations" in runbook["upstream_research_runbook"]
    assert "resolved_observations" in runbook["upstream_research_runbook"]
    assert "backtest_depth_progress_pct" in runbook["upstream_research_runbook"]
    assert "thresholds" in runbook["upstream_research_runbook"]
    assert {
        threshold["key"]
        for threshold in runbook["upstream_research_runbook"]["thresholds"]
    } == {
        "parseable_research_rows",
        "resolved_research_rows",
        "backtest_depth_resolved_rows",
    }
    assert runbook["completed_step_count"] == 2
    assert runbook["total_step_count"] == 10
    assert runbook["progress_pct"] == 20
    assert "eligible_mkt_research_candidate" in runbook["blockers"]
    assert runbook["live_execution_enabled"] is False


def test_prediction_market_contract_snapshot_csv_preflight_import_and_template(
    client: TestClient,
) -> None:
    csv_text = "\n".join(
        [
            (
                "venue,event_ticker,market_title,contract_ticker,contract_title,category,"
                "status,yes_bid_price,yes_ask_price,no_bid_price,no_ask_price,closes_at,"
                "expiration_at,observed_at"
            ),
            (
                "KALSHI,KXBTCD-26JUN25,Bitcoin above test level,"
                "KXBTCD-26JUN25-B62500,Bitcoin above 62500,crypto,OPEN,0.59,0.60,"
                "0.40,0.41,2026-06-25T20:00:00Z,2026-06-25T20:00:00Z,"
                "2026-06-25T19:30:00Z"
            ),
            (
                "KALSHI,,Missing event,KXBAD-26JUN25-B1,Bad contract,crypto,OPEN,"
                "0.10,0.20,0.80,0.90,2026-06-25T20:00:00Z,"
                "2026-06-25T20:00:00Z,2026-06-25T19:30:00Z"
            ),
        ]
    )

    template = client.get("/prediction-market/contracts/template.csv")
    assert template.status_code == 200
    assert "contract_ticker" in template.text

    preflight = client.post(
        "/prediction-market/contracts/preflight-csv",
        json={
            "source": "kalshi_export",
            "source_reference": "manual:btc-demo",
            "csv_text": csv_text,
            "csv_format": "aurex",
        },
    )
    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY_WITH_REJECTIONS"
    assert preflight_body["rows_received"] == 2
    assert preflight_body["importable_count"] == 1
    assert preflight_body["rejected_count"] == 1
    assert preflight_body["analysis_summary"]["unique_contracts"] == 1
    assert preflight_body["analysis_summary"]["actionable_yes_rows"] == 1

    imported = client.post(
        "/prediction-market/contracts/import-csv",
        json={
            "source": "kalshi_export",
            "source_reference": "manual:btc-demo",
            "csv_text": csv_text,
            "csv_format": "aurex",
        },
    )
    assert imported.status_code == 200
    imported_body = imported.json()
    assert imported_body["status"] == "IMPORTED_WITH_REJECTIONS"
    assert imported_body["imported_count"] == 1
    assert imported_body["rejected_count"] == 1
    assert len(imported_body["contract_ids"]) == 1

    contracts = client.get("/prediction-market/contracts").json()
    assert len(contracts) == 1
    assert contracts[0]["contract_ticker"] == "KXBTCD-26JUN25-B62500"

    readiness = client.get("/prediction-market/paper/demo-readiness").json()
    assert readiness["evidence"]["contract_snapshots"] == 1

    evidence = client.get("/prediction-market/evidence").json()
    assert {event["kind"] for event in evidence} == {PredictionMarketEvidenceKind.MARKET_SNAPSHOT}


def test_prediction_market_contract_snapshot_csv_import_accepts_mkt_markets_export(
    client: TestClient,
) -> None:
    csv_text = "\n".join(
        [
            (
                "ticker,event_ticker,title,yes_sub_title,category,status,close_time,"
                "yes_bid,yes_ask,last_updated"
            ),
            (
                "KXBTCD-26JUN25-B62500,KXBTCD-26JUN25,Bitcoin above test level,"
                "Bitcoin above 62500,crypto,open,2026-06-25T20:00:00Z,0.59,0.60,"
                "2026-06-25T19:30:00Z"
            ),
        ]
    )

    imported = client.post(
        "/prediction-market/contracts/import-csv",
        json={
            "source": "my-krypt-trader",
            "source_reference": "krypt-trader.db::markets",
            "csv_text": csv_text,
            "csv_format": "auto",
        },
    )

    assert imported.status_code == 200
    body = imported.json()
    assert body["csv_format"] == "mkt_markets"
    assert body["status"] == "IMPORTED"
    assert body["analysis_summary"]["actionable_yes_rows"] == 1
    assert body["analysis_summary"]["actionable_no_rows"] == 1

    contract = client.get("/prediction-market/contracts").json()[0]
    assert contract["status"] == "OPEN"
    assert Decimal(contract["yes_bid_price"]) == Decimal("0.59000000")
    assert Decimal(contract["yes_ask_price"]) == Decimal("0.60000000")
    assert Decimal(contract["no_bid_price"]) == Decimal("0.40000000")
    assert Decimal(contract["no_ask_price"]) == Decimal("0.41000000")


def test_prediction_market_contract_snapshot_mkt_db_preflight_and_import(
    client: TestClient,
    tmp_path,
) -> None:
    db_path = tmp_path / "krypt-trader.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table markets (
                ticker text primary key,
                event_ticker text default '',
                series_ticker text default '',
                title text default '',
                yes_sub_title text default '',
                category text default '',
                status text default 'open',
                close_time text default '',
                volume real default 0,
                volume_24h real default 0,
                open_interest real default 0,
                yes_bid real default 0,
                yes_ask real default 0,
                last_price real default 0,
                result text default '',
                settlement_value real default null,
                last_updated text
            );
            """
        )
        conn.executemany(
            """
            insert into markets (
                ticker, event_ticker, title, yes_sub_title, category, status,
                close_time, volume, volume_24h, open_interest, yes_bid, yes_ask,
                last_price, result, settlement_value, last_updated
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "KXBTCD-26JUN25-B62500",
                    "KXBTCD-26JUN25",
                    "Bitcoin above test level",
                    "Bitcoin above 62500",
                    "crypto",
                    "finalized",
                    "2026-06-25T20:00:00Z",
                    1200,
                    200,
                    900,
                    0.59,
                    0.60,
                    0.60,
                    "yes",
                    None,
                    "2026-06-25T21:00:00Z",
                ),
                (
                    "KXBAD-26JUN25-B1",
                    "",
                    "Missing event ticker",
                    "Missing event ticker",
                    "crypto",
                    "settled",
                    "2026-06-25T20:00:00Z",
                    500,
                    100,
                    100,
                    0.20,
                    0.30,
                    0.20,
                    "no",
                    None,
                    "2026-06-25T21:01:00Z",
                ),
                (
                    "KXOPEN-26JUN25-B1",
                    "KXOPEN-26JUN25",
                    "Open market should not import by default",
                    "Open market",
                    "crypto",
                    "open",
                    "2026-06-25T20:00:00Z",
                    999,
                    999,
                    100,
                    0.40,
                    0.41,
                    0.40,
                    "",
                    None,
                    "2026-06-25T19:00:00Z",
                ),
            ],
        )

    payload = {
        "db_path": str(db_path),
        "source": "my-krypt-trader",
        "source_reference": f"{db_path}::markets",
        "status_filter": "resolved",
        "limit": 10,
        "require_settlement_value": True,
    }

    readiness = client.post("/prediction-market/contracts/mkt-db-readiness", json=payload)
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["status"] == "READY_WITH_REJECTIONS"
    assert readiness_body["data_ready"] is True
    assert readiness_body["db_exists"] is True
    assert readiness_body["markets_table_available"] is True
    assert readiness_body["rows_received"] == 2
    assert readiness_body["importable_count"] == 1
    assert readiness_body["rejected_count"] == 1
    assert readiness_body["live_execution_enabled"] is False
    assert "campaign preflight" in readiness_body["next_action"]

    preflight = client.post("/prediction-market/contracts/preflight-mkt-db", json=payload)
    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY_WITH_REJECTIONS"
    assert preflight_body["rows_received"] == 2
    assert preflight_body["importable_count"] == 1
    assert preflight_body["rejected_count"] == 1
    assert preflight_body["csv_format"] == "mkt_markets"
    assert preflight_body["query_summary"]["status_filter"] == "resolved"
    assert preflight_body["query_summary"]["require_settlement_value"] is True
    assert preflight_body["analysis_summary"]["unique_contracts"] == 1
    assert preflight_body["analysis_summary"]["actionable_yes_rows"] == 1
    assert preflight_body["analysis_summary"]["actionable_no_rows"] == 1
    assert client.get("/prediction-market/summary").json()["contracts"] == 0

    imported = client.post("/prediction-market/contracts/import-mkt-db", json=payload)
    assert imported.status_code == 200
    imported_body = imported.json()
    assert imported_body["status"] == "IMPORTED_WITH_REJECTIONS"
    assert imported_body["rows_received"] == 2
    assert imported_body["imported_count"] == 1
    assert imported_body["rejected_count"] == 1
    assert len(imported_body["contract_ids"]) == 1

    contracts = client.get("/prediction-market/contracts").json()
    assert len(contracts) == 1
    assert contracts[0]["contract_ticker"] == "KXBTCD-26JUN25-B62500"
    assert contracts[0]["status"] == "SETTLED"
    assert Decimal(contracts[0]["settlement_value"]) == Decimal("1.00000000")

    evidence = client.get("/prediction-market/evidence").json()
    assert evidence[0]["payload"]["raw_payload"]["direct_db_import"] is True
    assert evidence[0]["payload"]["raw_payload"]["sqlite_table"] == "markets"
    assert evidence[0]["payload"]["raw_payload"]["source"] == "my-krypt-trader"
    assert evidence[0]["payload"]["raw_payload"]["csv_format"] == "mkt_markets"


def test_prediction_market_mkt_db_readiness_reports_missing_local_data(
    client: TestClient,
    tmp_path,
) -> None:
    missing_db = tmp_path / "missing-krypt-trader.db"

    readiness = client.post(
        "/prediction-market/contracts/mkt-db-readiness",
        json={
            "db_path": str(missing_db),
            "source": "my-krypt-trader",
            "source_reference": f"{missing_db}::markets",
            "status_filter": "resolved",
            "limit": 10,
            "require_settlement_value": True,
        },
    )

    assert readiness.status_code == 200
    body = readiness.json()
    assert body["status"] == "MISSING_DB"
    assert body["data_ready"] is False
    assert body["db_exists"] is False
    assert body["markets_table_available"] is False
    assert body["rows_received"] == 0
    assert body["importable_count"] == 0
    assert body["rejected_count"] == 0
    assert "database not found" in body["error"]
    assert "before campaign preflight" in body["next_action"]
    assert body["live_execution_enabled"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_db_discovery_finds_ready_local_db(
    client: TestClient,
    tmp_path,
) -> None:
    nested_dir = tmp_path / "My-Krypt-Trader" / "python" / "data"
    nested_dir.mkdir(parents=True)
    ready_db = nested_dir / "krypt-trader.db"
    blocked_db = nested_dir / "notes.sqlite"
    create_mkt_markets_db(ready_db)
    with sqlite3.connect(blocked_db) as conn:
        conn.execute("create table unrelated (id integer primary key)")

    discovery = client.post(
        "/prediction-market/contracts/discover-mkt-dbs",
        json={
            "search_roots": [str(tmp_path / "My-Krypt-Trader"), str(tmp_path / "missing")],
            "limit": 10,
            "status_filter": "resolved",
            "require_settlement_value": True,
        },
    )

    assert discovery.status_code == 200
    body = discovery.json()
    assert body["candidate_count"] == 2
    assert body["ready_count"] == 1
    assert body["live_execution_enabled"] is False
    assert any("missing" in item for item in body["skipped_paths"])
    candidates = {candidate["db_path"]: candidate for candidate in body["candidates"]}
    assert candidates[str(ready_db)]["readiness"]["status"] == "READY"
    assert candidates[str(ready_db)]["readiness"]["data_ready"] is True
    assert candidates[str(ready_db)]["readiness"]["importable_count"] == 1
    assert candidates[str(blocked_db)]["readiness"]["status"] == "MISSING_MARKETS_TABLE"
    assert candidates[str(blocked_db)]["readiness"]["data_ready"] is False
    assert "Select a ready MKT DB path" in body["next_action"]
    assert client.get("/prediction-market/summary").json()["contracts"] == 0

    donor_readiness = client.post(
        "/prediction-market/contracts/mkt-donor-readiness",
        json={
            "mkt_root": str(tmp_path / "My-Krypt-Trader"),
            "search_roots": [str(tmp_path / "My-Krypt-Trader"), str(tmp_path / "missing")],
            "limit": 10,
            "status_filter": "resolved",
            "require_settlement_value": True,
        },
    )
    assert donor_readiness.status_code == 200
    donor_body = donor_readiness.json()
    assert donor_body["status"] == "DONOR_READY"
    assert donor_body["discovery"]["ready_count"] == 1
    assert donor_body["discovery"]["candidate_count"] == 2
    assert donor_body["live_execution_enabled"] is False
    assert any(item["key"] == "db_module" for item in donor_body["collector_files"])
    dev_command = "npm.cmd run dev" if os.name == "nt" else "npm run dev"
    assert any(dev_command in item["command"] for item in donor_body["command_hints"])
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_donor_readiness_reports_missing_local_data(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    python_dir = mkt_root / "python"
    create_mkt_runtime_fixture(mkt_root)

    donor_readiness = client.post(
        "/prediction-market/contracts/mkt-donor-readiness",
        json={
            "mkt_root": str(mkt_root),
            "search_roots": [str(mkt_root), str(python_dir), str(python_dir / "data")],
            "limit": 10,
            "status_filter": "resolved",
            "require_settlement_value": True,
        },
    )

    assert donor_readiness.status_code == 200
    body = donor_readiness.json()
    assert body["status"] == "DONOR_DATA_MISSING"
    assert body["root_exists"] is True
    assert body["python_dir_exists"] is True
    assert body["data_dir_exists"] is False
    assert body["db_module_exists"] is True
    assert body["discovery"]["candidate_count"] == 0
    assert body["discovery"]["ready_count"] == 0
    assert "mkt_data_dir_missing" in body["blockers"]
    assert "mkt_sqlite_db_missing" in body["blockers"]
    expected_db_path = str(python_dir / "data" / "krypt-trader.db")
    assert any(expected_db_path in item for item in body["expected_db_paths"])
    collector_files = {item["key"]: item for item in body["collector_files"]}
    assert collector_files["db_module"]["exists"] is True
    assert collector_files["service_loop"]["exists"] is True
    assert any("demo/dry-run" in item["live_execution"] for item in body["command_hints"])
    assert body["live_execution_enabled"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0

    runbook = client.post(
        "/prediction-market/contracts/mkt-donor-runbook",
        json={
            "mkt_root": str(mkt_root),
            "db_path": str(python_dir / "data" / "krypt-trader.db"),
            "search_roots": [str(mkt_root), str(python_dir), str(python_dir / "data")],
            "limit": 10,
            "status_filter": "resolved",
            "require_settlement_value": True,
        },
    )
    assert runbook.status_code == 200
    runbook_body = runbook.json()
    assert runbook_body["status"] == "RUNBOOK_COLLECT_DATA"
    assert runbook_body["live_execution_enabled"] is False
    assert runbook_body["donor_readiness"]["status"] == "DONOR_DATA_MISSING"
    assert runbook_body["db_inventory"]["status"] == "MISSING_DB"
    assert runbook_body["runtime_safety"]["status"] == "SAFETY_DEFAULTS_ONLY"
    assert any(step["title"] == "Verify MKT demo/dry-run safety" for step in runbook_body["steps"])
    dev_command = "npm.cmd run dev" if os.name == "nt" else "npm run dev"
    assert any(dev_command in (step["command"] or "") for step in runbook_body["steps"])
    assert "mkt_runtime_settings_requires_manual_confirmation" in runbook_body["blockers"]
    assert "mkt_sqlite_db_missing" in runbook_body["blockers"]
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_runtime_safety_confirms_safe_runtime_settings(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)
    settings_path = tmp_path / "userdata" / "settings.json"
    userdata_path = tmp_path / "userdata"
    credentials_dir = userdata_path / "credentials"
    credentials_dir.mkdir(parents=True)
    (credentials_dir / "apikey.demo.txt").write_text("demo-key", encoding="utf-8")
    (credentials_dir / "rsakey.demo.pem").write_text("demo-rsa", encoding="utf-8")
    write_mkt_settings(
        settings_path,
        {
            "kalshiEnv": "demo",
            "enableTrading": False,
            "crypto15mLive": False,
            "gamblingMode": False,
        },
    )

    response = client.post(
        "/prediction-market/contracts/mkt-runtime-safety",
        json={
            "mkt_root": str(mkt_root),
            "settings_path": str(settings_path),
            "userdata_path": str(userdata_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SAFETY_CONFIRMED"
    assert body["settings_loaded"] is True
    assert body["settings_exists"] is True
    assert body["settings_auto_discovered"] is False
    assert body["userdata_auto_discovered"] is False
    assert body["failed_checks"] == 0
    assert body["blockers"] == []
    assert body["live_execution_enabled"] is False
    runtime_checks = {check["key"]: check for check in body["checks"]}
    assert runtime_checks["runtime_kalshi_env"]["status"] == "PASS"
    assert runtime_checks["runtime_enable_trading"]["observed"] == "false"
    credentials = {item["env"]: item for item in body["credentials"]}
    assert credentials["demo"]["credential_pair_present"] is True
    assert credentials["demo"]["contents_read"] is False
    assert credentials["production"]["credential_pair_present"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_runtime_safety_discovers_userdata_settings_path(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)
    userdata_path = tmp_path / "userdata"
    settings_path = userdata_path / "settings.json"
    write_mkt_settings(
        settings_path,
        {
            "kalshiEnv": "demo",
            "enableTrading": False,
            "crypto15mLive": False,
            "gamblingMode": False,
        },
    )
    monkeypatch.setenv("KRYPT_TRADER_USERDATA", str(userdata_path))

    response = client.post(
        "/prediction-market/contracts/mkt-runtime-safety",
        json={"mkt_root": str(mkt_root)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SAFETY_CONFIRMED"
    assert body["settings_path"] == str(settings_path)
    assert body["userdata_path"] == str(userdata_path)
    assert body["settings_auto_discovered"] is True
    assert body["userdata_auto_discovered"] is True
    assert body["settings_loaded"] is True
    selected_settings = [item for item in body["settings_candidates"] if item["selected"]]
    selected_userdata = [item for item in body["userdata_candidates"] if item["selected"]]
    assert selected_settings[0]["key"] == "krypt_trader_userdata_env_settings"
    assert selected_userdata[0]["key"] in {
        "settings_parent",
        "krypt_trader_userdata_env_userdata",
    }
    assert body["blockers"] == []
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_runtime_safety_blocks_unsafe_runtime_settings(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)
    settings_path = tmp_path / "userdata" / "settings.json"
    write_mkt_settings(
        settings_path,
        {
            "kalshiEnv": "production",
            "enableTrading": True,
            "crypto15mLive": True,
            "gamblingMode": True,
        },
    )

    response = client.post(
        "/prediction-market/contracts/mkt-runtime-safety",
        json={
            "mkt_root": str(mkt_root),
            "settings_path": str(settings_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SAFETY_BLOCKED"
    assert body["settings_loaded"] is True
    assert body["failed_checks"] >= 4
    assert "mkt_runtime_kalshi_env_not_demo" in body["blockers"]
    assert "mkt_runtime_enable_trading_enabled" in body["blockers"]
    assert "mkt_runtime_crypto15m_live_enabled" in body["blockers"]
    assert "mkt_runtime_gambling_mode_enabled" in body["blockers"]

    runbook = client.post(
        "/prediction-market/contracts/mkt-donor-runbook",
        json={
            "mkt_root": str(mkt_root),
            "db_path": str(mkt_root / "python" / "data" / "krypt-trader.db"),
            "settings_path": str(settings_path),
            "search_roots": [str(mkt_root)],
            "limit": 10,
            "status_filter": "resolved",
            "require_settlement_value": True,
        },
    )
    assert runbook.status_code == 200
    runbook_body = runbook.json()
    assert runbook_body["status"] == "RUNBOOK_BLOCKED"
    assert runbook_body["runtime_safety"]["status"] == "SAFETY_BLOCKED"
    steps = {step["title"]: step for step in runbook_body["steps"]}
    assert steps["Verify MKT demo/dry-run safety"]["status"] == "BLOCKED"
    assert "mkt_runtime_enable_trading_enabled" in runbook_body["blockers"]
    assert runbook_body["live_execution_enabled"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_donor_bootstrap_creates_demo_safe_userdata(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)

    response = client.post(
        "/prediction-market/contracts/mkt-donor-bootstrap",
        json={"mkt_root": str(mkt_root)},
    )

    assert response.status_code == 200
    body = response.json()
    userdata_path = mkt_root / ".aurex-demo-userdata"
    settings_path = userdata_path / "settings.json"
    assert body["status"] == "BOOTSTRAP_READY"
    assert body["userdata_path"] == str(userdata_path)
    assert body["settings_path"] == str(settings_path)
    assert body["settings_written"] is True
    assert body["live_execution_enabled"] is False
    assert body["runtime_safety"]["status"] == "SAFETY_CONFIRMED"
    assert body["runtime_safety"]["userdata_path"] == str(userdata_path)
    assert (userdata_path / "logs").is_dir()
    assert (userdata_path / "data").is_dir()
    assert (userdata_path / "credentials").is_dir()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["config"]["kalshiEnv"] == "demo"
    assert settings["config"]["enableTrading"] is False
    assert settings["config"]["crypto15mLive"] is False
    assert settings["config"]["gamblingMode"] is False
    assert any("KRYPT_TRADER_USERDATA" in hint["command"] for hint in body["command_hints"])
    assert client.get("/prediction-market/summary").json()["contracts"] == 0

    rediscovered_safety = client.post(
        "/prediction-market/contracts/mkt-runtime-safety",
        json={"mkt_root": str(mkt_root)},
    ).json()
    assert rediscovered_safety["status"] == "SAFETY_CONFIRMED"
    assert rediscovered_safety["settings_auto_discovered"] is True
    assert rediscovered_safety["settings_path"] == str(settings_path)

    runbook = client.post(
        "/prediction-market/contracts/mkt-donor-runbook",
        json={"mkt_root": str(mkt_root), "limit": 10},
    )
    assert runbook.status_code == 200
    runbook_body = runbook.json()
    assert runbook_body["collection_status"]["status"] == "COLLECTION_WAITING_FOR_DB"
    assert runbook_body["collection_status"]["db_path"] == (
        str(userdata_path / "data" / "krypt-trader.db")
    )
    assert runbook_body["db_inventory"]["status"] == "MISSING_DB"
    assert runbook_body["runtime_safety"]["status"] == "SAFETY_CONFIRMED"
    assert runbook_body["db_path"] == str(userdata_path / "data" / "krypt-trader.db")
    runbook_steps = {step["title"]: step for step in runbook_body["steps"]}
    assert runbook_steps["Collect local MKT donor data"]["status"] == "NEEDS_ACTION"
    assert "KRYPT_TRADER_USERDATA" in runbook_steps["Collect local MKT donor data"]["command"]


def test_prediction_market_mkt_donor_bootstrap_refuses_unsafe_existing_settings(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)
    userdata_path = tmp_path / "mkt-userdata"
    settings_path = userdata_path / "settings.json"
    write_mkt_settings(
        settings_path,
        {
            "kalshiEnv": "production",
            "enableTrading": True,
            "crypto15mLive": True,
            "gamblingMode": True,
        },
    )

    response = client.post(
        "/prediction-market/contracts/mkt-donor-bootstrap",
        json={"mkt_root": str(mkt_root), "userdata_path": str(userdata_path)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BOOTSTRAP_BLOCKED"
    assert body["settings_written"] is False
    assert "mkt_demo_settings_existing_unsafe" in body["blockers"]
    assert "mkt_runtime_enable_trading_enabled" in body["blockers"]
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))
    assert persisted["config"]["kalshiEnv"] == "production"
    assert persisted["config"]["enableTrading"] is True
    assert body["live_execution_enabled"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_donor_collection_status_tracks_bootstrap_db_readiness(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)
    bootstrap = client.post(
        "/prediction-market/contracts/mkt-donor-bootstrap",
        json={"mkt_root": str(mkt_root)},
    ).json()
    userdata_path = tmp_path / "My-Krypt-Trader" / ".aurex-demo-userdata"
    log_file = userdata_path / "logs" / "service.log"
    log_file.write_text("demo collector started\n", encoding="utf-8")

    waiting = client.post(
        "/prediction-market/contracts/mkt-donor-collection-status",
        json={"mkt_root": str(mkt_root), "limit": 10},
    )

    assert waiting.status_code == 200
    waiting_body = waiting.json()
    assert bootstrap["status"] == "BOOTSTRAP_READY"
    assert waiting_body["status"] == "COLLECTION_WAITING_FOR_DB"
    assert waiting_body["runtime_safety"]["status"] == "SAFETY_CONFIRMED"
    assert waiting_body["settings_path"] == str(userdata_path / "settings.json")
    assert waiting_body["userdata_path"] == str(userdata_path)
    assert waiting_body["db_path"] == str(userdata_path / "data" / "krypt-trader.db")
    assert waiting_body["db_inventory"]["status"] == "MISSING_DB"
    assert waiting_body["db_file_size_bytes"] is None
    assert waiting_body["db_modified_at"] is None
    assert waiting_body["db_age_seconds"] is None
    assert waiting_body["latest_log_modified_at"] is not None
    assert waiting_body["latest_log_age_seconds"] is not None
    assert waiting_body["latest_log_age_seconds"] <= waiting_body["freshness_window_seconds"]
    assert waiting_body["freshness_window_seconds"] == 900
    assert waiting_body["recommended_recheck_after_seconds"] == 60
    assert waiting_body["recommended_recheck_at"] is not None
    assert waiting_body["collection_freshness_status"] == "FRESHNESS_WAITING_FOR_DB"
    assert waiting_body["collection_quality"]["status"] == "QUALITY_EMPTY"
    assert waiting_body["collection_quality"]["evidence_tier"] == "DONOR_EMPTY"
    assert waiting_body["collection_quality"]["aurex_use_scope"] == "COLLECT_ONLY"
    assert waiting_body["collection_quality"]["total_rows"] == 0
    assert waiting_body["collection_quality"]["backtest_depth_progress_pct"] == 0
    assert "donor_rows_present" in waiting_body["collection_quality"]["blockers"]
    assert waiting_body["launch_health"]["status"] == "LAUNCH_HEALTH_STARTING"
    waiting_health_checks = {
        check["key"]: check for check in waiting_body["launch_health"]["checks"]
    }
    assert waiting_health_checks["recent_db_or_log_activity"]["status"] == "PASS"
    assert waiting_health_checks["donor_rows_present"]["status"] == "BLOCKED"
    assert "donor_rows_present" in waiting_body["launch_health"]["blockers"]
    waiting_targets = {
        target["key"]: target for target in waiting_body["collection_quality"]["targets"]
    }
    assert waiting_targets["resolved_replay_candidates"]["remaining_count"] == 100
    assert waiting_targets["resolved_research_observations"]["remaining_count"] == 100
    assert waiting_body["data_dir_exists"] is True
    assert waiting_body["logs_dir_exists"] is True
    assert waiting_body["log_files"][0]["name"] == "service.log"
    assert any(
        "KRYPT_TRADER_USERDATA" in hint["command"]
        and "run dev" in hint["command"]
        for hint in waiting_body["command_hints"]
    )
    assert any(
        hint["command"] == str(userdata_path / "data" / "krypt-trader.db")
        for hint in waiting_body["command_hints"]
    )
    assert "mkt_sqlite_db_missing" in waiting_body["blockers"]
    assert waiting_body["live_execution_enabled"] is False

    empty_db_path = userdata_path / "data" / "krypt-trader.db"
    create_mkt_empty_markets_schema(empty_db_path)
    old_timestamp = (datetime.now(UTC) - timedelta(hours=1)).timestamp()
    os.utime(empty_db_path, (old_timestamp, old_timestamp))
    os.utime(log_file, (old_timestamp, old_timestamp))
    inactive = client.post(
        "/prediction-market/contracts/mkt-donor-collection-status",
        json={"mkt_root": str(mkt_root), "limit": 10},
    )
    assert inactive.status_code == 200
    inactive_body = inactive.json()
    assert inactive_body["status"] == "COLLECTION_INACTIVE"
    assert inactive_body["collection_freshness_status"] == "FRESHNESS_NO_RECENT_WRITES"
    assert inactive_body["collection_quality"]["evidence_tier"] == "DONOR_EMPTY"
    assert inactive_body["collection_quality"]["aurex_use_scope"] == "COLLECT_ONLY"
    assert inactive_body["db_age_seconds"] >= 3500
    assert inactive_body["latest_log_age_seconds"] >= 3500
    assert inactive_body["freshness_window_seconds"] == 900
    assert inactive_body["recommended_recheck_after_seconds"] == 60
    assert inactive_body["recommended_recheck_at"] is not None
    assert inactive_body["launch_health"]["status"] == "LAUNCH_HEALTH_INACTIVE"
    assert "recent_db_or_log_activity" in inactive_body["launch_health"]["blockers"]
    assert "mkt_collection_no_recent_writes" in inactive_body["blockers"]
    assert "mkt_sqlite_db_empty" in inactive_body["blockers"]
    assert any(
        "KRYPT_TRADER_USERDATA" in hint["command"]
        for hint in inactive_body["command_hints"]
    )

    insert_mkt_market_row(empty_db_path)
    add_mkt_research_inventory_rows(empty_db_path)
    ready = client.post(
        "/prediction-market/contracts/mkt-donor-collection-status",
        json={"mkt_root": str(mkt_root), "limit": 10},
    )
    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["status"] == "COLLECTION_REPLAY_READY"
    assert ready_body["db_file_size_bytes"] > 0
    assert ready_body["db_modified_at"] is not None
    assert ready_body["db_age_seconds"] <= ready_body["freshness_window_seconds"]
    assert ready_body["latest_log_age_seconds"] >= 3500
    assert ready_body["recommended_recheck_after_seconds"] == 300
    assert ready_body["recommended_recheck_at"] is not None
    assert ready_body["collection_freshness_status"] == "FRESHNESS_DB_RECENT"
    assert ready_body["db_inventory"]["replay_table_ready"] is True
    assert ready_body["db_inventory"]["research_tables_ready"] is True
    assert ready_body["collection_quality"]["status"] == "QUALITY_REPLAY_AND_RESEARCH_SAMPLE"
    assert ready_body["collection_quality"]["evidence_tier"] == (
        "DONOR_SPARSE_REPLAY_AND_RESEARCH_SAMPLE"
    )
    assert ready_body["collection_quality"]["aurex_use_scope"] == (
        "GUARDED_REPLAY_AND_RESEARCH_ONLY"
    )
    assert ready_body["collection_quality"]["replay_candidate_count"] == 1
    assert ready_body["collection_quality"]["research_candidate_count"] == 3
    assert ready_body["collection_quality"]["backtest_depth_progress_pct"] == 2
    assert ready_body["launch_health"]["status"] == "LAUNCH_HEALTH_SAMPLE_READY"
    ready_health_checks = {
        check["key"]: check for check in ready_body["launch_health"]["checks"]
    }
    assert ready_health_checks["donor_rows_present"]["status"] == "PASS"
    assert ready_health_checks["evidence_sample_present"]["status"] == "PASS"
    assert ready_health_checks["backtest_depth_target"]["status"] == "BLOCKED"
    assert ready_body["launch_health"]["blockers"] == ["backtest_depth_target"]
    ready_targets = {
        target["key"]: target for target in ready_body["collection_quality"]["targets"]
    }
    assert ready_targets["resolved_replay_candidates"]["remaining_count"] == 99
    assert ready_targets["resolved_research_observations"]["remaining_count"] == 97
    assert "backtest_replay_depth" in ready_body["collection_quality"]["blockers"]
    assert "backtest_research_depth" in ready_body["collection_quality"]["blockers"]
    assert ready_body["runtime_safety"]["status"] == "SAFETY_CONFIRMED"
    assert any(
        "KRYPT_TRADER_USERDATA" in hint["command"]
        for hint in ready_body["command_hints"]
    )
    assert ready_body["live_execution_enabled"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_donor_launch_preflight_checks_scoped_runtime(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)
    bootstrap = client.post(
        "/prediction-market/contracts/mkt-donor-bootstrap",
        json={"mkt_root": str(mkt_root)},
    ).json()

    needs_setup = client.post(
        "/prediction-market/contracts/mkt-donor-launch-preflight",
        json={"mkt_root": str(mkt_root)},
    )
    assert needs_setup.status_code == 200
    needs_setup_body = needs_setup.json()
    assert bootstrap["status"] == "BOOTSTRAP_READY"
    assert needs_setup_body["status"] == "LAUNCH_NEEDS_SETUP"
    assert needs_setup_body["launch_scope"] == "DONOR_COLLECTION_ONLY"
    assert needs_setup_body["evidence_tier"] == "DONOR_EMPTY"
    assert needs_setup_body["aurex_use_scope"] == "COLLECT_ONLY"
    assert needs_setup_body["backtest_depth_ready"] is False
    assert "Launch readiness only" in needs_setup_body["evidence_boundary"]
    assert needs_setup_body["runtime_safety"]["status"] == "SAFETY_CONFIRMED"
    assert needs_setup_body["collection_status"]["status"] == "COLLECTION_WAITING_FOR_DB"
    assert "KRYPT_TRADER_USERDATA" in needs_setup_body["launch_command"]
    repair_command = next(
        command
        for command in needs_setup_body["setup_commands"]
        if command["label"] == "Repair MKT Python backend"
    )["command"]
    assert "KRYPT_TRADER_PYTHON" in repair_command
    if os.name == "nt":
        assert "npm.cmd run py:setup -- --strict --force" in repair_command
    else:
        assert "npm run py:setup -- --strict --force" in repair_command
    warning_checks = {
        check["key"]: check for check in needs_setup_body["checks"] if check["status"] == "WARN"
    }
    assert warning_checks["node_modules_available"]["observed"] == "missing"
    assert warning_checks["mkt_python_venv_available"]["observed"] == "missing"
    assert needs_setup_body["blockers"] == []
    assert needs_setup_body["live_execution_enabled"] is False

    (mkt_root / "node_modules").mkdir()
    venv_scripts = mkt_root / "python" / ".venv" / "Scripts"
    venv_scripts.mkdir(parents=True)
    (venv_scripts / "python.exe").write_text("", encoding="utf-8")
    (mkt_root / "python" / ".venv" / "pyvenv.cfg").write_text(
        "\n".join(
            [
                "home = C:\\missing-python312",
                "executable = C:\\missing-python312\\python.exe",
                "",
            ],
        ),
        encoding="utf-8",
    )
    broken_venv = client.post(
        "/prediction-market/contracts/mkt-donor-launch-preflight",
        json={"mkt_root": str(mkt_root)},
    )
    assert broken_venv.status_code == 200
    broken_venv_body = broken_venv.json()
    assert broken_venv_body["status"] == "LAUNCH_NEEDS_SETUP"
    broken_checks = {check["key"]: check for check in broken_venv_body["checks"]}
    assert broken_checks["mkt_python_venv_available"]["status"] == "WARN"
    assert "broken: base executable missing" in broken_checks[
        "mkt_python_venv_available"
    ]["observed"]

    (mkt_root / "python" / ".venv" / "pyvenv.cfg").write_text(
        "\n".join(
            [
                f"home = {Path(sys.executable).parent}",
                f"executable = {sys.executable}",
                "",
            ],
        ),
        encoding="utf-8",
    )
    donor_db = mkt_root / ".aurex-demo-userdata" / "data" / "krypt-trader.db"
    create_mkt_empty_markets_schema(donor_db)
    old_timestamp = (datetime.now(UTC) - timedelta(hours=1)).timestamp()
    os.utime(donor_db, (old_timestamp, old_timestamp))
    ready = client.post(
        "/prediction-market/contracts/mkt-donor-launch-preflight",
        json={"mkt_root": str(mkt_root)},
    )
    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["status"] == "LAUNCH_READY"
    assert ready_body["launch_scope"] == "DONOR_COLLECTION_ONLY"
    assert ready_body["evidence_tier"] == "DONOR_EMPTY"
    assert ready_body["aurex_use_scope"] == "COLLECT_ONLY"
    assert ready_body["backtest_depth_ready"] is False
    assert "real trading remain blocked" in ready_body["evidence_boundary"]
    checks = {check["key"]: check for check in ready_body["checks"]}
    assert checks["node_modules_available"]["status"] == "PASS"
    assert checks["mkt_python_venv_available"]["status"] == "PASS"
    assert checks["runtime_safety_confirmed"]["status"] == "PASS"
    assert checks["launch_command_scoped_to_userdata"]["status"] == "PASS"
    assert checks["electron_userdata_env_override_available"]["status"] == "PASS"
    assert checks["donor_db_not_yet_ready"]["status"] == "PASS"
    assert ready_body["collection_status"]["status"] == "COLLECTION_INACTIVE"
    assert ready_body["blockers"] == []
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_donor_launch_preflight_blocks_unscoped_electron_userdata(
    client: TestClient,
    tmp_path,
) -> None:
    mkt_root = tmp_path / "My-Krypt-Trader"
    create_mkt_runtime_fixture(mkt_root)
    client.post(
        "/prediction-market/contracts/mkt-donor-bootstrap",
        json={"mkt_root": str(mkt_root)},
    )
    (mkt_root / "node_modules").mkdir()
    venv_scripts = mkt_root / "python" / ".venv" / "Scripts"
    venv_scripts.mkdir(parents=True)
    (venv_scripts / "python.exe").write_text("", encoding="utf-8")
    (mkt_root / "python" / ".venv" / "pyvenv.cfg").write_text(
        "\n".join(
            [
                f"home = {Path(sys.executable).parent}",
                f"executable = {sys.executable}",
                "",
            ],
        ),
        encoding="utf-8",
    )
    (mkt_root / "electron" / "main.ts").write_text(
        "import { app } from 'electron';\nvoid app;\n",
        encoding="utf-8",
    )

    response = client.post(
        "/prediction-market/contracts/mkt-donor-launch-preflight",
        json={"mkt_root": str(mkt_root)},
    )

    assert response.status_code == 200
    body = response.json()
    checks = {check["key"]: check for check in body["checks"]}
    assert body["status"] == "LAUNCH_BLOCKED"
    assert checks["electron_userdata_env_override_available"]["status"] == "FAIL"
    assert checks["electron_userdata_env_override_available"]["observed"] == (
        "electron main does not map KRYPT_TRADER_USERDATA"
    )
    assert "electron_userdata_env_override_available" in body["blockers"]
    assert body["live_execution_enabled"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0


def test_prediction_market_mkt_db_inventory_reports_replay_and_research_rows(
    client: TestClient,
    tmp_path,
) -> None:
    missing_db = tmp_path / "missing-krypt-trader.db"
    missing_inventory = client.post(
        "/prediction-market/contracts/mkt-db-inventory",
        json={
            "db_path": str(missing_db),
            "source": "my-krypt-trader",
            "source_reference": f"{missing_db}::markets",
            "status_filter": "resolved",
            "limit": 10,
            "require_settlement_value": True,
        },
    )
    assert missing_inventory.status_code == 200
    missing_body = missing_inventory.json()
    assert missing_body["status"] == "MISSING_DB"
    assert missing_body["db_exists"] is False
    assert missing_body["markets_readiness"]["status"] == "MISSING_DB"
    assert "mkt_sqlite_db_missing" in missing_body["blockers"]
    assert all(table["exists"] is False for table in missing_body["tables"])

    db_path = tmp_path / "krypt-trader.db"
    create_mkt_markets_db(db_path)
    add_mkt_research_inventory_rows(db_path)

    inventory = client.post(
        "/prediction-market/contracts/mkt-db-inventory",
        json={
            "db_path": str(db_path),
            "source": "my-krypt-trader",
            "source_reference": f"{db_path}::markets",
            "status_filter": "resolved",
            "limit": 10,
            "require_settlement_value": True,
        },
    )

    assert inventory.status_code == 200
    body = inventory.json()
    assert body["status"] == "INVENTORY_REPLAY_READY"
    assert body["db_exists"] is True
    assert body["replay_table_ready"] is True
    assert body["research_tables_ready"] is True
    assert body["execution_history_ready"] is True
    assert body["replay_candidate_count"] == 1
    assert body["research_candidate_count"] == 3
    assert body["markets_readiness"]["status"] == "READY"
    assert body["live_execution_enabled"] is False
    tables = {table["table"]: table for table in body["tables"]}
    assert tables["markets"]["row_count"] == 1
    assert tables["markets"]["resolved_count"] == 1
    assert tables["alerts"]["resolved_count"] == 1
    assert tables["whale_trades"]["resolved_count"] == 1
    assert tables["crypto15m_signals"]["resolved_count"] == 1
    assert tables["bot_positions"]["row_count"] == 1
    assert "market_snapshots" in body["missing_tables"]
    assert client.get("/prediction-market/summary").json()["contracts"] == 0

    mkt_root = tmp_path / "My-Krypt-Trader"
    python_dir = mkt_root / "python"
    data_dir = python_dir / "data"
    data_dir.mkdir(parents=True)
    create_mkt_runtime_fixture(mkt_root)
    rooted_db = data_dir / "krypt-trader.db"
    create_mkt_markets_db(rooted_db)
    add_mkt_research_inventory_rows(rooted_db)
    runbook = client.post(
        "/prediction-market/contracts/mkt-donor-runbook",
        json={
            "mkt_root": str(mkt_root),
            "db_path": str(rooted_db),
            "search_roots": [str(mkt_root)],
            "limit": 10,
            "status_filter": "resolved",
            "require_settlement_value": True,
        },
    )
    assert runbook.status_code == 200
    runbook_body = runbook.json()
    assert runbook_body["status"] == "RUNBOOK_REPLAY_READY"
    assert runbook_body["db_inventory"]["replay_table_ready"] is True
    assert runbook_body["donor_readiness"]["discovery"]["ready_count"] == 1
    steps = {step["title"]: step for step in runbook_body["steps"]}
    assert steps["Confirm MKT donor checkout"]["status"] == "PASSED"
    assert steps["Use donor data inside Aurex gates"]["status"] == "READY"
    assert any(step["safety_gate"].startswith("No live trading") for step in runbook_body["steps"])
    assert runbook_body["live_execution_enabled"] is False


def test_prediction_market_campaign_readiness_blocks_missing_mkt_db(
    client: TestClient,
    tmp_path,
) -> None:
    missing_db = tmp_path / "missing-krypt-trader.db"

    readiness = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-readiness",
        json={
            "db_import": {
                "db_path": str(missing_db),
                "source": "my-krypt-trader",
                "source_reference": f"{missing_db}::markets:campaign",
                "status_filter": "resolved",
                "limit": 10,
                "require_settlement_value": True,
            },
            "batch": {
                "strategy": "mkt_whale_research_candidate",
                "side": "YES",
                "quantity": "10",
                "max_records": 2,
                "idempotency_prefix": "mkt-db-missing-campaign",
            },
        },
    )

    assert readiness.status_code == 200
    body = readiness.json()
    assert body["status"] == "MKT_DB_NOT_READY"
    assert body["ready_for_campaign_preflight"] is False
    assert body["ready_for_campaign_replay"] is False
    assert body["campaign_preflight"] is None
    assert body["data_readiness"]["status"] == "MISSING_DB"
    assert body["data_quality_status"] == "QUALITY_EMPTY"
    assert body["data_evidence_tier"] == "DONOR_EMPTY"
    assert body["data_use_scope"] == "COLLECT_ONLY"
    assert body["data_backtest_depth_ready"] is False
    assert body["strategy_gate"]["approved"] is False
    checks = {check["key"]: check["passed"] for check in body["checks"]}
    assert checks["live_execution_disabled"] is True
    assert checks["mkt_db_data_ready"] is False
    assert checks["mkt_db_evidence_tier"] is False
    assert checks["mkt_research_gate_accepted"] is False
    assert "before campaign preflight" in body["next_action"]
    assert body["live_execution_enabled"] is False


def test_prediction_market_mkt_db_campaign_preflight_and_run_replays_rows(
    client: TestClient,
    tmp_path,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    db_path = tmp_path / "krypt-trader-campaign.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table markets (
                ticker text primary key,
                event_ticker text default '',
                series_ticker text default '',
                title text default '',
                yes_sub_title text default '',
                category text default '',
                status text default 'open',
                close_time text default '',
                volume real default 0,
                volume_24h real default 0,
                open_interest real default 0,
                yes_bid real default 0,
                yes_ask real default 0,
                last_price real default 0,
                result text default '',
                settlement_value real default null,
                last_updated text
            );
            """
        )
        conn.executemany(
            """
            insert into markets (
                ticker, event_ticker, title, yes_sub_title, category, status,
                close_time, volume, volume_24h, open_interest, yes_bid, yes_ask,
                last_price, result, settlement_value, last_updated
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "KXBTCD-26JUN25-B62500",
                    "KXBTCD-26JUN25",
                    "Bitcoin above test level",
                    "Bitcoin above 62500",
                    "crypto",
                    "finalized",
                    "2026-06-25T20:00:00Z",
                    1200,
                    200,
                    900,
                    0.59,
                    0.60,
                    0.60,
                    "yes",
                    None,
                    "2026-06-25T21:00:00Z",
                ),
                (
                    "KXETHD-26JUN25-B2500",
                    "KXETHD-26JUN25",
                    "Ether above test level",
                    "Ether above 2500",
                    "crypto",
                    "finalized",
                    "2026-06-25T20:05:00Z",
                    1300,
                    240,
                    850,
                    0.54,
                    0.55,
                    0.55,
                    "no",
                    None,
                    "2026-06-26T21:00:00Z",
                ),
                (
                    "KXOPEN-26JUN25-B1",
                    "KXOPEN-26JUN25",
                    "Open market excluded from campaign default",
                    "Open market",
                    "crypto",
                    "open",
                    "2026-06-25T20:00:00Z",
                    999,
                    999,
                    100,
                    0.40,
                    0.41,
                    0.40,
                    "",
                    None,
                    "2026-06-25T19:00:00Z",
                ),
            ],
        )

    payload = {
        "db_import": {
            "db_path": str(db_path),
            "source": "my-krypt-trader",
            "source_reference": f"{db_path}::markets:campaign",
            "status_filter": "resolved",
            "limit": 10,
            "require_settlement_value": True,
        },
        "batch": {
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "idempotency_prefix": "mkt-db-campaign-fixture",
        },
    }

    readiness = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-readiness",
        json=payload,
    )
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["status"] == "SIDE_RATIONALE_REQUIRED"
    assert readiness_body["ready_for_campaign_preflight"] is True
    assert readiness_body["ready_for_campaign_replay"] is False
    assert readiness_body["data_readiness"]["data_ready"] is True
    assert readiness_body["data_quality_status"] == "QUALITY_REPLAY_SAMPLE"
    assert readiness_body["data_evidence_tier"] == "DONOR_SPARSE_REPLAY_SAMPLE"
    assert readiness_body["data_use_scope"] == "GUARDED_REPLAY_SAMPLE_ONLY"
    assert readiness_body["data_backtest_depth_ready"] is False
    assert readiness_body["strategy_gate"]["approved"] is True
    assert readiness_body["strategy_gate"]["live_execution"] == "blocked"
    assert readiness_body["campaign_preflight"]["status"] == "READY"
    assert readiness_body["campaign_preflight"]["mutated_ledger"] is False
    assert readiness_body["campaign_preflight"]["side_sensitivity_warning"]
    checks = {check["key"]: check["passed"] for check in readiness_body["checks"]}
    assert checks["mkt_db_evidence_tier"] is True
    assert checks["campaign_preflight_ready"] is True
    assert checks["side_sensitivity_acknowledged"] is False
    assert client.get("/prediction-market/summary").json()["contracts"] == 0

    acknowledged_readiness = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-readiness",
        json={
            **payload,
            "acknowledge_side_sensitivity": True,
            "side_selection_rationale": (
                "Pre-declared whale-following test for YES side before reviewing "
                "the opposite-side projection."
            ),
        },
    )
    assert acknowledged_readiness.status_code == 200
    acknowledged_body = acknowledged_readiness.json()
    assert acknowledged_body["status"] == "READY_FOR_CAMPAIGN_REPLAY"
    assert acknowledged_body["ready_for_campaign_replay"] is True
    assert acknowledged_body["live_execution_enabled"] is False

    blocked_manifest = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-manifest",
        json=payload,
    )
    assert blocked_manifest.status_code == 200
    blocked_manifest_body = blocked_manifest.json()
    assert blocked_manifest_body["status"] == "MANIFEST_PREFLIGHT_READY"
    assert blocked_manifest_body["replay_ready"] is False
    assert blocked_manifest_body["mutated_ledger"] is False
    assert blocked_manifest_body["live_execution_enabled"] is False
    assert blocked_manifest_body["readiness"]["status"] == "SIDE_RATIONALE_REQUIRED"
    assert blocked_manifest_body["manifest"]["paper_only"] is True
    assert blocked_manifest_body["manifest"]["live_execution"] == "blocked"
    assert blocked_manifest_body["manifest"]["controls"]["mutates_ledger"] is False
    assert "side_sensitivity_acknowledged" in " ".join(blocked_manifest_body["blockers"])
    summary_after_blocked_manifest = client.get("/prediction-market/summary").json()
    assert summary_after_blocked_manifest["contracts"] == 0
    assert summary_after_blocked_manifest["order_intents"] == 0

    ready_manifest = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-manifest",
        json={
            **payload,
            "acknowledge_side_sensitivity": True,
            "side_selection_rationale": (
                "Pre-declared whale-following test for YES side before reviewing "
                "the opposite-side projection."
            ),
        },
    )
    noisy_batch_payload = {
        **payload["batch"],
        "idempotency_prefix": "campaign-fixture-noisy-prefix",
        "reviewed_preflight_hash": "a" * 64,
    }
    repeated_ready_manifest = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-manifest",
        json={
            **payload,
            "batch": noisy_batch_payload,
            "acknowledge_side_sensitivity": True,
            "side_selection_rationale": (
                "Pre-declared whale-following test for YES side before reviewing "
                "the opposite-side projection."
            ),
        },
    )
    assert ready_manifest.status_code == 200
    assert repeated_ready_manifest.status_code == 200
    ready_manifest_body = ready_manifest.json()
    assert ready_manifest_body["status"] == "MANIFEST_READY"
    assert ready_manifest_body["replay_ready"] is True
    assert ready_manifest_body["manifest_hash"] == repeated_ready_manifest.json()["manifest_hash"]
    assert "idempotency_prefix" not in ready_manifest_body["manifest"]["batch"]
    assert "reviewed_preflight_hash" not in ready_manifest_body["manifest"]["batch"]
    assert ready_manifest_body["manifest"]["campaign_preflight_status"] == "READY"
    assert ready_manifest_body["manifest"]["side_sensitivity_acknowledged"] is True
    assert ready_manifest_body["manifest"]["controls"]["live_execution_enabled"] is False
    assert ready_manifest_body["manifest"]["projected_replay"]["completed_records"] == 2
    assert ready_manifest_body["manifest"]["opposite_side_projection"]["side"] == "NO"
    summary_after_ready_manifest = client.get("/prediction-market/summary").json()
    assert summary_after_ready_manifest["contracts"] == 0
    assert summary_after_ready_manifest["order_intents"] == 0

    preflight = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-preflight",
        json=payload,
    )
    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY"
    assert preflight_body["mutated_ledger"] is False
    assert preflight_body["live_execution_enabled"] is False
    assert preflight_body["import_preflight"]["importable_count"] == 2
    assert preflight_body["import_preflight"]["rows_received"] == 2
    assert preflight_body["batch_preflight"]["eligible_records"] == 2
    assert preflight_body["batch_preflight"]["available_contracts"] == 2
    assert preflight_body["projected_replay"]["status"] == "BATCH_COMPLETED"
    assert preflight_body["projected_replay"]["attempted_records"] == 2
    assert preflight_body["projected_replay"]["completed_records"] == 2
    assert preflight_body["projected_replay"]["target_closed_records"] == 100
    assert preflight_body["projected_replay"]["target_calendar_days"] == 30
    assert preflight_body["projected_replay"]["target_active_days"] == 15
    assert preflight_body["projected_replay"]["target_unique_contracts"] == 25
    assert preflight_body["projected_replay"]["projected_raw_closed_records"] == 2
    assert preflight_body["projected_replay"]["projected_closed_records"] == 2
    assert preflight_body["projected_replay"]["projected_calendar_days"] >= 1
    assert preflight_body["projected_replay"]["projected_active_days"] >= 1
    assert preflight_body["projected_replay"]["projected_unique_contracts"] == 2
    assert preflight_body["projected_replay"]["projected_countable_records"] == 2
    assert preflight_body["projected_replay"]["projected_blocked_records"] == 0
    assert preflight_body["projected_replay"]["remaining_closed_records"] == 98
    assert preflight_body["projected_replay"]["remaining_calendar_days"] < 30
    assert preflight_body["projected_replay"]["remaining_active_days"] < 15
    assert preflight_body["projected_replay"]["remaining_unique_contracts"] == 23
    assert 0 < preflight_body["projected_replay"]["projected_progress_pct"] < 100
    assert preflight_body["projected_replay"]["ready_for_live_review"] is False
    assert preflight_body["projected_replay"]["first_failed_check"]
    assert preflight_body["projected_replay"]["live_execution_enabled"] is False
    assert preflight_body["projected_replay"]["side"] == "YES"
    assert preflight_body["opposite_side_projection"]["side"] == "NO"
    assert preflight_body["opposite_side_projection"]["completed_records"] == 2
    assert Decimal(
        preflight_body["opposite_side_projection"]["projected_fee_net_realized_pl"]
    ) > Decimal(preflight_body["projected_replay"]["projected_fee_net_realized_pl"])
    assert preflight_body["side_sensitivity_warning"] in {
        "opposite_side_projects_better_fee_net_pl",
        "selected_side_negative_opposite_side_positive",
        "projection_is_side_sensitive_selected_positive_opposite_negative",
        "projection_requires_side_hypothesis_before_replay",
    }
    summary_after_preflight = client.get("/prediction-market/summary").json()
    assert summary_after_preflight["contracts"] == 0
    assert summary_after_preflight["order_intents"] == 0
    assert summary_after_preflight["orders"] == 0
    assert summary_after_preflight["fills"] == 0
    assert summary_after_preflight["settled_positions"] == 0

    rejected_run = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-run",
        json=payload,
    )
    assert rejected_run.status_code == 400
    assert "side_selection_rationale" in rejected_run.json()["detail"]
    summary_after_rejection = client.get("/prediction-market/summary").json()
    assert summary_after_rejection["contracts"] == 0
    assert summary_after_rejection["order_intents"] == 0

    acknowledged_payload = {
        **payload,
        "acknowledge_side_sensitivity": True,
        "side_selection_rationale": (
            "Pre-declared whale-following test for YES side before reviewing "
            "the opposite-side projection."
        ),
    }
    unreviewed_run = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-run",
        json=acknowledged_payload,
    )
    assert unreviewed_run.status_code == 400
    assert "reviewed_manifest_hash_required_before_campaign_replay" in unreviewed_run.json()[
        "detail"
    ]

    reviewed_payload = {
        **acknowledged_payload,
        "batch": {
            **acknowledged_payload["batch"],
            "idempotency_prefix": "campaign-fixture-run-prefix",
            "reviewed_preflight_hash": "b" * 64,
        },
        "reviewed_manifest_hash": ready_manifest_body["manifest_hash"],
    }
    run = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-run",
        json=reviewed_payload,
    )
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "CAMPAIGN_REPLAY_COMPLETED"
    assert body["live_execution_enabled"] is False
    assert body["manifest_hash"] == ready_manifest_body["manifest_hash"]
    assert body["reviewed_manifest_hash"] == ready_manifest_body["manifest_hash"]
    assert body["side_sensitivity_acknowledged"] is True
    assert body["side_sensitivity_warning"] == preflight_body["side_sensitivity_warning"]
    assert body["side_selection_rationale"].startswith("Pre-declared whale-following")
    assert body["campaign_evidence"]["kind"] == PredictionMarketEvidenceKind.PAPER_DEMO_CAMPAIGN
    assert body["campaign_evidence"]["strategy"] == "mkt_whale_research_candidate"
    assert body["campaign_evidence"]["evidence_hash"]
    assert body["campaign_evidence"]["payload"]["side_sensitivity_acknowledged"] is True
    assert body["campaign_evidence"]["payload"]["side_sensitivity_warning"] == body[
        "side_sensitivity_warning"
    ]
    assert body["campaign_evidence"]["payload"]["side_selection_rationale"].startswith(
        "Pre-declared whale-following"
    )
    evidence_payload = body["campaign_evidence"]["payload"]
    assert evidence_payload["manifest_hash"] == ready_manifest_body["manifest_hash"]
    assert evidence_payload["reviewed_manifest_hash"] == ready_manifest_body["manifest_hash"]
    assert evidence_payload["donor_quality"]["status"] == "QUALITY_REPLAY_SAMPLE"
    assert evidence_payload["donor_quality"]["evidence_tier"] == "DONOR_SPARSE_REPLAY_SAMPLE"
    assert evidence_payload["donor_quality"]["aurex_use_scope"] == "GUARDED_REPLAY_SAMPLE_ONLY"
    assert evidence_payload["donor_quality"]["backtest_depth_ready"] is False
    assert evidence_payload["donor_quality"]["replay_candidate_count"] == 2
    assert evidence_payload["donor_quality"]["research_candidate_count"] == 0
    assert evidence_payload["preflight"]["status"] == "READY"
    assert evidence_payload["preflight"]["mutated_ledger"] is False
    assert evidence_payload["preflight"]["projected_replay"]["target_closed_records"] == 100
    assert evidence_payload["preflight"]["projected_replay"]["projected_raw_closed_records"] == 2
    assert evidence_payload["preflight"]["projected_replay"]["projected_countable_records"] == 2
    assert evidence_payload["preflight"]["projected_replay"]["remaining_closed_records"] == 98
    assert evidence_payload["preflight"]["projected_replay"]["remaining_unique_contracts"] == 23
    assert evidence_payload["preflight"]["projected_replay"]["projected_progress_pct"] < 100
    assert evidence_payload["preflight"]["opposite_side_projection"]["side"] == "NO"
    assert evidence_payload["progress"]["target_closed_records"] == 100
    assert evidence_payload["progress"]["raw_closed_records"] == 2
    assert evidence_payload["progress"]["remaining_records"] == 98
    assert evidence_payload["progress"]["remaining_unique_contracts"] == 23
    assert evidence_payload["progress"]["progress_pct"] < 100
    assert evidence_payload["progress"]["current_check"]["key"] == "minimum_closed_records"
    assert body["import_result"]["imported_count"] == 2
    assert body["batch"]["completed_records"] == 2
    assert body["batch"]["attempted_records"] == 2
    assert body["progress"]["closed_records"] == 2
    assert body["progress"]["unique_contracts"] == 2
    assert body["ledger"]["countable_records"] == 2
    assert body["ledger"]["blocked_records"] == 0
    assert {
        result["source_reference"] for result in body["batch"]["results"]
    } == {f"{db_path}::markets:campaign"}
    latest_evidence = client.get("/prediction-market/evidence?limit=1").json()[0]
    assert latest_evidence["kind"] == PredictionMarketEvidenceKind.PAPER_DEMO_CAMPAIGN
    assert latest_evidence["evidence_hash"] == body["campaign_evidence"]["evidence_hash"]
    assert latest_evidence["payload"]["batch"]["completed_records"] == 2
    assert latest_evidence["payload"]["preflight"]["projected_replay"][
        "remaining_closed_records"
    ] == 98
    assert latest_evidence["payload"]["progress"]["ready_for_live_review"] is False
    campaign_audit = client.get("/prediction-market/paper/demo-campaigns").json()
    assert campaign_audit["record_count"] == 1
    assert campaign_audit["acknowledged_records"] == 1
    assert campaign_audit["side_sensitive_records"] == 1
    assert campaign_audit["current_result_clean_records"] == 1
    assert campaign_audit["current_result_drifted_records"] == 0
    assert campaign_audit["latest_evidence_hash"] == body["campaign_evidence"]["evidence_hash"]
    audit_record = campaign_audit["records"][0]
    assert audit_record["evidence_hash"] == body["campaign_evidence"]["evidence_hash"]
    assert audit_record["status"] == "CAMPAIGN_REPLAY_COMPLETED"
    assert audit_record["source_reference"] == f"{db_path}::markets:campaign"
    assert audit_record["donor_quality_status"] == "QUALITY_REPLAY_SAMPLE"
    assert audit_record["donor_evidence_tier"] == "DONOR_SPARSE_REPLAY_SAMPLE"
    assert audit_record["donor_use_scope"] == "GUARDED_REPLAY_SAMPLE_ONLY"
    assert audit_record["donor_backtest_depth_ready"] is False
    assert audit_record["side"] == "YES"
    assert audit_record["completed_records"] == 2
    assert audit_record["countable_records"] == 2
    assert audit_record["current_result_records"] == 2
    assert audit_record["current_result_countable_records"] == 2
    assert audit_record["current_result_blocked_records"] == 0
    assert audit_record["current_result_ledger_status"] == "CURRENT_RESULT_LEDGER_CLEAN"
    assert audit_record["current_result_ledger_blockers"] == []
    assert audit_record["target_closed_records"] == 100
    assert audit_record["raw_closed_records"] == 2
    assert audit_record["remaining_records"] == 98
    assert audit_record["remaining_unique_contracts"] == 23
    assert 0 < audit_record["progress_pct"] < 100
    assert audit_record["current_check_key"] == "minimum_closed_records"
    assert audit_record["ready_for_live_review"] is False
    assert audit_record["payload"]["preflight"]["projected_replay"][
        "remaining_closed_records"
    ] == 98
    assert audit_record["payload"]["progress"]["remaining_records"] == 98
    assert audit_record["side_selection_rationale"].startswith(
        "Pre-declared whale-following"
    )

    with next(client.app.dependency_overrides[get_db]()) as db:
        event = (
            db.query(PredictionEvidenceEvent)
            .filter(
                PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.FILL_RECEIVED
            )
            .first()
        )
        assert event is not None
        event.payload = {**event.payload, "quantity": "999"}
        event.evidence_hash = hash_evidence_payload(
            event.kind,
            event.entity_type,
            event.entity_id,
            event.payload,
        )
        db.commit()

    drifted_campaign_audit = client.get("/prediction-market/paper/demo-campaigns").json()
    assert drifted_campaign_audit["current_result_clean_records"] == 0
    assert drifted_campaign_audit["current_result_drifted_records"] == 1
    assert "current-result ledger drift" in drifted_campaign_audit["next_action"]
    drifted_record = drifted_campaign_audit["records"][0]
    assert drifted_record["countable_records"] == 2
    assert drifted_record["current_result_records"] == 2
    assert drifted_record["current_result_countable_records"] == 1
    assert drifted_record["current_result_blocked_records"] == 1
    assert drifted_record["current_result_ledger_status"] == "CURRENT_RESULT_LEDGER_DRIFTED"
    assert "paper_demo_result_records_blocked" in drifted_record[
        "current_result_ledger_blockers"
    ]
    assert "fill_evidence_payload_mismatch" in drifted_record[
        "current_result_ledger_blockers"
    ]

    duplicate = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-preflight",
        json=reviewed_payload,
    )
    assert duplicate.status_code == 200
    duplicate_body = duplicate.json()
    assert duplicate_body["status"] == "NO_NEW_CONTRACTS"
    assert duplicate_body["batch_preflight"]["eligible_records"] == 0
    assert duplicate_body["batch_preflight"]["skipped_records"] == 2
    assert duplicate_body["projected_replay"] is None


def test_prediction_market_guided_demo_uses_imported_settlement_outcome(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    csv_text = "\n".join(
        [
            (
                "ticker,event_ticker,title,yes_sub_title,category,status,close_time,"
                "yes_bid,yes_ask,result,last_updated"
            ),
            (
                "KXBTCD-26JUN25-B62500,KXBTCD-26JUN25,Bitcoin above test level,"
                "Bitcoin above 62500,crypto,finalized,2026-06-25T20:00:00Z,0.59,"
                "0.60,yes,2026-06-25T21:00:00Z"
            ),
        ]
    )

    imported = client.post(
        "/prediction-market/contracts/import-csv",
        json={
            "source": "my-krypt-trader",
            "source_reference": "krypt-trader.db::markets:resolved",
            "csv_text": csv_text,
            "csv_format": "mkt_markets",
        },
    )

    assert imported.status_code == 200
    contract = client.get("/prediction-market/contracts").json()[0]
    assert contract["status"] == "SETTLED"
    assert Decimal(contract["settlement_value"]) == Decimal("1.00000000")

    run = client.post(
        "/prediction-market/paper/demo-run",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "available_quantity": "10",
            "idempotency_key": "guided-demo-imported-outcome",
        },
    )

    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "PAPER_DEMO_VERIFIED"
    assert body["completed_lifecycle"] is True
    assert body["run_snapshot"]["settlement_source"] == "contract_snapshot"
    assert Decimal(body["settlement"]["settlement_value"]) == Decimal("1.00000000")
    assert Decimal(body["settlement"]["realized_pl"]) == Decimal("3.83200000")

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 1
    assert ledger["countable_records"] == 1
    assert ledger["blocked_records"] == 0
    assert ledger["latest_reconciliation_status"] == ReconciliationStatus.MATCHED
    assert ledger["live_execution_enabled"] is False
    record = ledger["records"][0]
    assert record["counts_toward_target"] is True
    assert record["blockers"] == []
    assert record["primary_strategy"] == "mkt_whale_research_candidate"
    assert record["strategies"] == ["mkt_whale_research_candidate"]
    assert record["source"] == "my-krypt-trader"
    assert record["source_reference"] == "krypt-trader.db::markets:resolved"
    assert record["csv_format"] == "mkt_markets"
    assert record["imported_from_mkt"] is True
    assert record["evidence_hash"]
    assert record["evidence_event_id"]
    assert record["reconciliation_status"] == ReconciliationStatus.MATCHED
    assert Decimal(record["realized_pl"]) == Decimal("3.83200000")
    assert record["recorded_evidence_kinds"] == [
        PredictionMarketEvidenceKind.MARKET_SNAPSHOT,
        PredictionMarketEvidenceKind.ORDER_INTENT,
        PredictionMarketEvidenceKind.ORDER_SUBMITTED,
        PredictionMarketEvidenceKind.FILL_RECEIVED,
        PredictionMarketEvidenceKind.SETTLEMENT_RECORDED,
        PredictionMarketEvidenceKind.POSITION_RECONCILED,
    ]
    assert record["missing_evidence_kinds"] == []


def test_prediction_market_guided_demo_honors_execution_risk_limits(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()

    run = client.post(
        "/prediction-market/paper/demo-run",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.65",
            "available_quantity": "10",
            "execution_price": "0.62",
            "latency_ms": 100,
            "idempotency_key": "guided-demo-slippage-risk-block",
            "risk_limits": {
                "max_order_cost": "50",
                "max_contract_exposure": "50",
                "max_open_positions": 25,
                "max_slippage": "0.01",
            },
        },
    )

    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "ORDER_SUBMITTED_NO_FILL"
    assert body["completed_lifecycle"] is False
    assert body["order"]["status"] == PredictionMarketOrderStatus.REJECTED
    assert body["fill"] is None
    assert body["position"] is None
    assert body["intent"]["intent_snapshot"]["risk_limits"]["max_slippage"] == "0.01"
    assert body["order"]["raw_payload"]["execution_slippage"]["rejection_reason"] == (
        "prediction_execution_slippage_exceeds_limit"
    )
    summary = client.get("/prediction-market/summary").json()
    assert summary["orders"] == 1
    assert summary["fills"] == 0
    assert summary["open_positions"] == 0
    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 0


def test_prediction_market_demo_ledger_blocks_missing_lifecycle_evidence(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-missing-fill-evidence",
        },
    ).json()
    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 450,
            "execution_price": "0.60",
        },
    ).json()

    settlement = client.post(
        f"/prediction-market/paper/positions/{submission['position']['id']}/settle",
        json={"settlement_value": "1"},
    )
    assert settlement.status_code == 200
    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED

    with next(client.app.dependency_overrides[get_db]()) as db:
        db.execute(
            delete(PredictionEvidenceEvent).where(
                PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.FILL_RECEIVED
            )
        )
        db.commit()

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 1
    assert ledger["countable_records"] == 0
    assert ledger["blocked_records"] == 1
    record = ledger["records"][0]
    assert record["counts_toward_target"] is False
    assert record["missing_evidence_kinds"] == [
        PredictionMarketEvidenceKind.FILL_RECEIVED
    ]
    assert "paper_demo_lifecycle_evidence_missing" in record["blockers"]
    assert PredictionMarketEvidenceKind.SETTLEMENT_RECORDED in (
        record["recorded_evidence_kinds"]
    )

    readiness = client.get("/prediction-market/paper/demo-readiness").json()
    assert readiness["status"] == "PAPER_DEMO_LIFECYCLE_BLOCKED"
    assert readiness["ready_to_start"] is True
    assert readiness["demo_lifecycle_verified"] is False
    assert readiness["current_check"]["key"] == "paper_demo_lifecycle_evidence_complete"
    assert readiness["evidence"]["countable_ledger_records"] == 0
    assert readiness["evidence"]["ledger_blocked_records"] == 1

    runbook = client.get("/prediction-market/paper/demo-runbook").json()
    assert runbook["status"] == "RUNBOOK_RUN_PAPER_LIFECYCLE"
    assert runbook["readiness_status"] == "PAPER_DEMO_LIFECYCLE_BLOCKED"
    assert runbook["current_step"]["key"] == "paper_demo_lifecycle_evidence_complete"
    assert "paper_demo_lifecycle_evidence_complete" in runbook["blockers"]

    progress = client.get("/prediction-market/paper/demo-progress").json()
    assert progress["status"] == "PAPER_DEMO_LEDGER_BLOCKED"
    assert progress["raw_closed_records"] == 1
    assert progress["closed_records"] == 0
    assert progress["calendar_days"] == 0
    assert progress["active_days"] == 0
    assert progress["unique_contracts"] == 0
    assert Decimal(progress["fee_net_realized_pl"]) == Decimal("0")
    assert Decimal(progress["expectancy"]) == Decimal("0")
    assert progress["countable_ledger_records"] == 0
    assert progress["ledger_blocked_records"] == 1
    assert progress["next_action"] == (
        "Resolve demo-ledger blockers before counting paper/demo evidence."
    )


def test_prediction_market_demo_ledger_blocks_tampered_settlement_evidence(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-tampered-settlement-evidence",
        },
    ).json()
    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 450,
            "execution_price": "0.60",
        },
    ).json()
    settlement = client.post(
        f"/prediction-market/paper/positions/{submission['position']['id']}/settle",
        json={"settlement_value": "1"},
    )
    assert settlement.status_code == 200
    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED

    with next(client.app.dependency_overrides[get_db]()) as db:
        event = (
            db.query(PredictionEvidenceEvent)
            .filter(
                PredictionEvidenceEvent.kind
                == PredictionMarketEvidenceKind.SETTLEMENT_RECORDED
            )
            .one()
        )
        event.payload = {**event.payload, "fees": "0.00"}
        db.commit()

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 1
    assert ledger["countable_records"] == 0
    assert ledger["blocked_records"] == 1
    record = ledger["records"][0]
    assert record["counts_toward_target"] is False
    assert "settlement_evidence_hash_mismatch" in record["blockers"]
    assert "settlement_evidence_payload_mismatch" in record["blockers"]

    progress = client.get("/prediction-market/paper/demo-progress").json()
    assert progress["status"] == "PAPER_DEMO_LEDGER_BLOCKED"
    assert progress["raw_closed_records"] == 1
    assert progress["closed_records"] == 0
    assert progress["countable_ledger_records"] == 0
    assert progress["ledger_blocked_records"] == 1


def test_prediction_market_demo_ledger_blocks_tampered_fill_evidence(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-tampered-fill-evidence",
        },
    ).json()
    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 450,
            "execution_price": "0.60",
        },
    ).json()
    settlement = client.post(
        f"/prediction-market/paper/positions/{submission['position']['id']}/settle",
        json={"settlement_value": "1"},
    )
    assert settlement.status_code == 200
    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED

    with next(client.app.dependency_overrides[get_db]()) as db:
        event = (
            db.query(PredictionEvidenceEvent)
            .filter(
                PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.FILL_RECEIVED
            )
            .one()
        )
        event.payload = {**event.payload, "quantity": "999"}
        event.evidence_hash = hash_evidence_payload(
            event.kind,
            event.entity_type,
            event.entity_id,
            event.payload,
        )
        db.commit()

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 1
    assert ledger["countable_records"] == 0
    assert ledger["blocked_records"] == 1
    record = ledger["records"][0]
    assert record["counts_toward_target"] is False
    assert PredictionMarketEvidenceKind.FILL_RECEIVED in record["missing_evidence_kinds"]
    assert "paper_demo_lifecycle_evidence_missing" in record["blockers"]
    assert "fill_evidence_payload_mismatch" in record["blockers"]
    assert "fill_evidence_hash_mismatch" not in record["blockers"]
    assert "settlement_evidence_hash_mismatch" not in record["blockers"]

    progress = client.get("/prediction-market/paper/demo-progress").json()
    assert progress["status"] == "PAPER_DEMO_LEDGER_BLOCKED"
    assert progress["raw_closed_records"] == 1
    assert progress["closed_records"] == 0
    assert progress["countable_ledger_records"] == 0
    assert progress["ledger_blocked_records"] == 1


def test_prediction_market_demo_ledger_blocks_fill_evidence_wrong_position(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-fill-evidence-wrong-position",
        },
    ).json()
    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 450,
            "execution_price": "0.60",
        },
    ).json()
    settlement = client.post(
        f"/prediction-market/paper/positions/{submission['position']['id']}/settle",
        json={"settlement_value": "1"},
    )
    assert settlement.status_code == 200
    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED

    with next(client.app.dependency_overrides[get_db]()) as db:
        event = (
            db.query(PredictionEvidenceEvent)
            .filter(
                PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.FILL_RECEIVED
            )
            .one()
        )
        event.payload = {**event.payload, "position_id": "not-the-filled-position"}
        event.evidence_hash = hash_evidence_payload(
            event.kind,
            event.entity_type,
            event.entity_id,
            event.payload,
        )
        db.commit()

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 1
    assert ledger["countable_records"] == 0
    assert ledger["blocked_records"] == 1
    record = ledger["records"][0]
    assert record["counts_toward_target"] is False
    assert PredictionMarketEvidenceKind.FILL_RECEIVED in record["missing_evidence_kinds"]
    assert "fill_evidence_payload_mismatch" in record["blockers"]
    assert "fill_evidence_hash_mismatch" not in record["blockers"]


def test_prediction_market_demo_ledger_blocks_stale_matched_reconciliation(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-stale-reconciliation",
        },
    ).json()
    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 450,
            "execution_price": "0.60",
        },
    ).json()
    settlement = client.post(
        f"/prediction-market/paper/positions/{submission['position']['id']}/settle",
        json={"settlement_value": "1"},
    )
    assert settlement.status_code == 200
    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED

    with next(client.app.dependency_overrides[get_db]()) as db:
        settlement_row = db.get(PredictionSettlement, settlement.json()["id"])
        assert settlement_row is not None
        settlement_row.raw_payload = {
            **settlement_row.raw_payload,
            "cumulative_realized_pl": "999",
        }
        db.commit()

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 1
    assert ledger["countable_records"] == 0
    assert ledger["blocked_records"] == 1
    record = ledger["records"][0]
    assert record["counts_toward_target"] is False
    assert "current_reconciliation_drift_detected" in record["blockers"]
    assert "matched_reconciliation_after_settlement_missing" not in record["blockers"]
    assert record["missing_evidence_kinds"] == []

    progress = client.get("/prediction-market/paper/demo-progress").json()
    assert progress["status"] == "PAPER_DEMO_LEDGER_BLOCKED"
    assert progress["raw_closed_records"] == 1
    assert progress["closed_records"] == 0
    assert progress["countable_ledger_records"] == 0
    assert progress["ledger_blocked_records"] == 1


def test_prediction_market_demo_ledger_blocks_unreconciled_settlement(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-unreconciled",
        },
    ).json()
    submission = client.post(
        f"/prediction-market/paper/order-intents/{intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 450,
            "execution_price": "0.60",
        },
    ).json()

    settlement = client.post(
        f"/prediction-market/paper/positions/{submission['position']['id']}/settle",
        json={"settlement_value": "1"},
    )
    assert settlement.status_code == 200

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 1
    assert ledger["countable_records"] == 0
    assert ledger["blocked_records"] == 1
    assert ledger["latest_reconciliation_status"] is None
    record = ledger["records"][0]
    assert record["counts_toward_target"] is False
    assert "matched_reconciliation_after_settlement_missing" in record["blockers"]
    assert record["primary_strategy"] == "mkt_whale_research_candidate"
    assert record["evidence_hash"]
    assert record["live_execution_enabled"] is False
    assert PredictionMarketEvidenceKind.POSITION_RECONCILED in (
        record["missing_evidence_kinds"]
    )


def test_prediction_market_demo_ledger_scopes_fills_to_position_lifecycle(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    first_intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_prediction_strategy",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-first-position-cycle",
        },
    ).json()
    first_submission = client.post(
        f"/prediction-market/paper/order-intents/{first_intent['id']}/submit",
        json={
            "available_quantity": "10",
            "latency_ms": 100,
            "execution_price": "0.60",
        },
    ).json()
    first_settlement = client.post(
        f"/prediction-market/paper/positions/{first_submission['position']['id']}/settle",
        json={"settlement_value": "1"},
    )
    assert first_settlement.status_code == 200

    reopened_contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()
    assert reopened_contract["id"] == contract["id"]
    second_intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": "fixture_reopened_prediction_strategy",
            "side": "YES",
            "quantity": "5",
            "limit_price": "0.60",
            "idempotency_key": "demo-ledger-second-position-cycle",
        },
    ).json()
    second_submission = client.post(
        f"/prediction-market/paper/order-intents/{second_intent['id']}/submit",
        json={
            "available_quantity": "5",
            "latency_ms": 100,
            "execution_price": "0.60",
        },
    ).json()
    second_settlement = client.post(
        f"/prediction-market/paper/positions/{second_submission['position']['id']}/settle",
        json={"settlement_value": "0"},
    )
    assert second_settlement.status_code == 200
    reconciliation = client.post("/prediction-market/paper/reconciliation/run")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["status"] == ReconciliationStatus.MATCHED

    ledger = client.get("/prediction-market/paper/demo-ledger").json()
    assert ledger["record_count"] == 2
    assert ledger["countable_records"] == 2
    assert ledger["blocked_records"] == 0

    records = {record["settlement_id"]: record for record in ledger["records"]}
    first_record = records[first_settlement.json()["id"]]
    second_record = records[second_settlement.json()["id"]]
    assert first_record["strategies"] == ["fixture_prediction_strategy"]
    assert first_record["primary_strategy"] == "fixture_prediction_strategy"
    assert first_record["quantity"] == "10.000000000000"
    assert second_record["strategies"] == ["fixture_reopened_prediction_strategy"]
    assert second_record["primary_strategy"] == "fixture_reopened_prediction_strategy"
    assert second_record["quantity"] == "5.000000000000"
    assert second_record["counts_toward_target"] is True


def test_prediction_market_demo_batch_replays_imported_resolved_contracts_once(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    csv_text = "\n".join(
        [
            (
                "ticker,event_ticker,title,yes_sub_title,category,status,close_time,"
                "yes_bid,yes_ask,result,last_updated"
            ),
            (
                "KXBTCD-26JUN25-B62500,KXBTCD-26JUN25,Bitcoin above test level,"
                "Bitcoin above 62500,crypto,finalized,2026-06-25T20:00:00Z,0.59,"
                "0.60,yes,2026-06-25T21:00:00Z"
            ),
            (
                "KXETHD-26JUN25-B2500,KXETHD-26JUN25,Ether above test level,"
                "Ether above 2500,crypto,finalized,2026-06-25T20:05:00Z,0.54,"
                "0.55,no,2026-06-26T21:00:00Z"
            ),
        ]
    )
    imported = client.post(
        "/prediction-market/contracts/import-csv",
        json={
            "source": "my-krypt-trader",
            "source_reference": "krypt-trader.db::markets:batch-resolved",
            "csv_text": csv_text,
            "csv_format": "mkt_markets",
        },
    )
    assert imported.status_code == 200

    preflight = client.post(
        "/prediction-market/paper/demo-batch-preflight",
        json={
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "source": "my-krypt-trader",
            "idempotency_prefix": "batch-fixture-preflight",
        },
    )

    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY"
    assert preflight_body["eligible_records"] == 2
    assert preflight_body["skipped_records"] == 0
    assert preflight_body["available_contracts"] == 2
    assert preflight_body["max_records"] == 2
    assert preflight_body["preflight_hash"]
    assert preflight_body["live_execution_enabled"] is False
    assert {result["status"] for result in preflight_body["results"]} == {"READY"}
    assert all(result["settlement_value"] for result in preflight_body["results"])
    assert all(result["source"] == "my-krypt-trader" for result in preflight_body["results"])
    summary_after_preflight = client.get("/prediction-market/summary").json()
    assert summary_after_preflight["order_intents"] == 0
    assert summary_after_preflight["orders"] == 0
    assert summary_after_preflight["fills"] == 0

    unreviewed_batch = client.post(
        "/prediction-market/paper/demo-batch-run",
        json={
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "source": "my-krypt-trader",
            "idempotency_prefix": "batch-fixture",
        },
    )
    assert unreviewed_batch.status_code == 400
    assert "reviewed_batch_preflight_hash_required_before_replay" in (
        unreviewed_batch.json()["detail"]
    )

    batch = client.post(
        "/prediction-market/paper/demo-batch-run",
        json={
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "source": "my-krypt-trader",
            "idempotency_prefix": "batch-fixture",
            "reviewed_preflight_hash": preflight_body["preflight_hash"],
        },
    )

    assert batch.status_code == 200
    body = batch.json()
    assert body["status"] == "BATCH_COMPLETED"
    assert body["preflight_hash"] == preflight_body["preflight_hash"]
    assert body["reviewed_preflight_hash"] == preflight_body["preflight_hash"]
    assert body["batch_evidence"]["kind"] == PredictionMarketEvidenceKind.PAPER_DEMO_BATCH
    assert body["batch_evidence"]["strategy"] == "mkt_whale_research_candidate"
    assert body["batch_evidence"]["payload"]["preflight_hash"] == preflight_body[
        "preflight_hash"
    ]
    assert body["batch_evidence"]["payload"]["reviewed_preflight_hash"] == (
        preflight_body["preflight_hash"]
    )
    assert body["batch_evidence"]["payload"]["batch"]["completed_records"] == 2
    assert body["attempted_records"] == 2
    assert body["completed_records"] == 2
    assert body["skipped_records"] == 0
    assert body["rejected_records"] == 0
    assert body["available_contracts"] == 2
    assert body["live_execution_enabled"] is False
    assert {result["status"] for result in body["results"]} == {"PAPER_DEMO_VERIFIED"}
    assert all(result["evidence_hash"] for result in body["results"])
    assert body["progress"]["raw_closed_records"] == 2
    assert body["progress"]["closed_records"] == 2
    assert body["progress"]["unique_contracts"] == 2
    assert body["progress"]["target_unique_contracts"] == 25
    assert body["progress"]["remaining_unique_contracts"] == 23
    assert body["progress"]["provenance_complete_records"] == 2
    assert body["progress"]["provenance_missing_records"] == 0
    assert body["progress"]["countable_ledger_records"] == 2
    assert body["progress"]["ledger_blocked_records"] == 0
    checks = {check["key"]: check["passed"] for check in body["progress"]["checks"]}
    assert checks["minimum_unique_contracts"] is False
    assert checks["single_contract_concentration"] is False
    assert checks["snapshot_provenance"] is True
    assert checks["countable_ledger_records"] is True
    assert body["ledger"]["record_count"] == 2
    assert body["ledger"]["countable_records"] == 2
    assert body["ledger"]["blocked_records"] == 0
    assert body["ledger"]["live_execution_enabled"] is False
    latest_evidence = client.get("/prediction-market/evidence?limit=1").json()[0]
    assert latest_evidence["kind"] == PredictionMarketEvidenceKind.PAPER_DEMO_BATCH
    assert latest_evidence["evidence_hash"] == body["batch_evidence"]["evidence_hash"]
    batch_audit = client.get("/prediction-market/paper/demo-batches").json()
    assert batch_audit["record_count"] == 1
    assert batch_audit["current_result_clean_records"] == 1
    assert batch_audit["current_result_drifted_records"] == 0
    assert batch_audit["latest_evidence_hash"] == body["batch_evidence"]["evidence_hash"]
    audit_record = batch_audit["records"][0]
    assert audit_record["evidence_hash"] == body["batch_evidence"]["evidence_hash"]
    assert audit_record["status"] == "BATCH_COMPLETED"
    assert audit_record["preflight_hash"] == preflight_body["preflight_hash"]
    assert audit_record["reviewed_preflight_hash"] == preflight_body["preflight_hash"]
    assert audit_record["completed_records"] == 2
    assert audit_record["countable_records"] == 2
    assert audit_record["current_result_records"] == 2
    assert audit_record["current_result_countable_records"] == 2
    assert audit_record["current_result_blocked_records"] == 0
    assert audit_record["current_result_ledger_status"] == "CURRENT_RESULT_LEDGER_CLEAN"
    assert audit_record["current_result_ledger_blockers"] == []
    assert audit_record["raw_closed_records"] == 2
    assert audit_record["remaining_records"] == 98
    assert audit_record["remaining_unique_contracts"] == 23
    assert audit_record["ready_for_live_review"] is False

    with next(client.app.dependency_overrides[get_db]()) as db:
        event = (
            db.query(PredictionEvidenceEvent)
            .filter(
                PredictionEvidenceEvent.kind == PredictionMarketEvidenceKind.FILL_RECEIVED
            )
            .first()
        )
        assert event is not None
        event.payload = {**event.payload, "fees": "99"}
        event.evidence_hash = hash_evidence_payload(
            event.kind,
            event.entity_type,
            event.entity_id,
            event.payload,
        )
        db.commit()

    drifted_batch_audit = client.get("/prediction-market/paper/demo-batches").json()
    assert drifted_batch_audit["current_result_clean_records"] == 0
    assert drifted_batch_audit["current_result_drifted_records"] == 1
    assert "current-result ledger drift" in drifted_batch_audit["next_action"]
    drifted_record = drifted_batch_audit["records"][0]
    assert drifted_record["countable_records"] == 2
    assert drifted_record["current_result_records"] == 2
    assert drifted_record["current_result_countable_records"] == 1
    assert drifted_record["current_result_blocked_records"] == 1
    assert drifted_record["current_result_ledger_status"] == "CURRENT_RESULT_LEDGER_DRIFTED"
    assert "paper_demo_result_records_blocked" in drifted_record[
        "current_result_ledger_blockers"
    ]
    assert "fill_evidence_payload_mismatch" in drifted_record[
        "current_result_ledger_blockers"
    ]

    duplicate_preflight = client.post(
        "/prediction-market/paper/demo-batch-preflight",
        json={
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "source": "my-krypt-trader",
            "idempotency_prefix": "batch-fixture-repeat-preflight",
        },
    ).json()
    assert duplicate_preflight["status"] == "NO_NEW_CONTRACTS"
    assert duplicate_preflight["eligible_records"] == 0
    assert duplicate_preflight["skipped_records"] == 2
    assert duplicate_preflight["preflight_hash"]
    assert {result["skip_reason"] for result in duplicate_preflight["results"]} == {
        "contract_already_has_settled_record_for_strategy"
    }
    duplicate = client.post(
        "/prediction-market/paper/demo-batch-run",
        json={
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "source": "my-krypt-trader",
            "idempotency_prefix": "batch-fixture-repeat",
            "reviewed_preflight_hash": duplicate_preflight["preflight_hash"],
        },
    )
    assert duplicate.status_code == 400
    assert "reviewed_batch_preflight_not_replay_ready" in duplicate.json()["detail"]


def test_prediction_market_guided_demo_run_tracks_progress(
    client: TestClient,
) -> None:
    seed_accepted_research_gate(client, strategy="mkt_whale_research_candidate")
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()

    run = client.post(
        "/prediction-market/paper/demo-run",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "available_quantity": "10",
            "execution_price": "0.60",
            "latency_ms": 450,
            "settlement_value": "1",
            "idempotency_key": "guided-demo-run",
        },
    )

    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "PAPER_DEMO_VERIFIED"
    assert body["completed_lifecycle"] is True
    assert body["run_snapshot"]["paper_only"] is True
    assert body["run_snapshot"]["live_execution"] == "blocked"
    assert body["intent"]["status"] == PredictionMarketOrderStatus.FILLED
    assert body["order"]["status"] == PredictionMarketOrderStatus.FILLED
    assert Decimal(body["fill"]["fees"]) == Decimal("0.16800000")
    assert Decimal(body["settlement"]["realized_pl"]) == Decimal("3.83200000")
    assert body["reconciliation"]["status"] == ReconciliationStatus.MATCHED

    progress = client.get("/prediction-market/paper/demo-progress")
    assert progress.status_code == 200
    progress_body = progress.json()
    assert progress_body["status"] == "COLLECTING_PAPER_DEMO_EVIDENCE"
    assert progress_body["ready_for_live_review"] is False
    assert progress_body["current_check"]["key"] == "minimum_closed_records"
    assert progress_body["completed_check_count"] == 4
    assert progress_body["total_check_count"] == 11
    assert progress_body["progress_pct"] == 36.36
    assert progress_body["target_closed_records"] == 100
    assert progress_body["target_calendar_days"] == 30
    assert progress_body["target_active_days"] == 15
    assert progress_body["target_unique_contracts"] == 25
    assert progress_body["raw_closed_records"] == 1
    assert progress_body["closed_records"] == 1
    assert progress_body["calendar_days"] == 1
    assert progress_body["active_days"] == 1
    assert progress_body["unique_contracts"] == 1
    assert progress_body["remaining_records"] == 99
    assert progress_body["remaining_calendar_days"] == 29
    assert progress_body["remaining_active_days"] == 14
    assert progress_body["remaining_unique_contracts"] == 24
    assert Decimal(progress_body["fee_net_realized_pl"]) == Decimal("3.83200000")
    assert Decimal(progress_body["expectancy"]) == Decimal("3.83200000")
    assert progress_body["profit_factor"] is None
    assert Decimal(progress_body["max_drawdown"]) == Decimal("0")
    assert progress_body["winning_records"] == 1
    assert progress_body["losing_records"] == 0
    assert progress_body["unique_contracts"] == 1
    assert progress_body["max_single_day_records"] == 1
    assert Decimal(progress_body["max_single_day_record_share"]) == Decimal("1")
    assert progress_body["max_single_contract_records"] == 1
    assert Decimal(progress_body["max_single_contract_record_share"]) == Decimal("1")
    assert progress_body["provenance_complete_records"] == 0
    assert progress_body["provenance_missing_records"] == 1
    assert progress_body["countable_ledger_records"] == 1
    assert progress_body["ledger_blocked_records"] == 0
    assert progress_body["latest_reconciliation_status"] == ReconciliationStatus.MATCHED
    checks = {check["key"]: check["passed"] for check in progress_body["checks"]}
    assert checks["minimum_closed_records"] is False
    assert checks["minimum_calendar_days"] is False
    assert checks["minimum_active_days"] is False
    assert checks["single_day_concentration"] is False
    assert checks["minimum_unique_contracts"] is False
    assert checks["single_contract_concentration"] is False
    assert checks["snapshot_provenance"] is False
    assert checks["countable_ledger_records"] is True
    assert checks["positive_expectancy"] is True
    assert checks["profit_factor"] is True
    assert checks["matched_reconciliation"] is True
    assert progress_body["distribution"]["daily_counts"]
    assert progress_body["live_execution_enabled"] is False
    runbook = client.get("/prediction-market/paper/demo-runbook").json()
    assert runbook["status"] == "RUNBOOK_COLLECT_EVIDENCE"
    assert runbook["readiness_status"] == "PAPER_DEMO_VERIFIED"
    assert runbook["progress_status"] == "COLLECTING_PAPER_DEMO_EVIDENCE"
    assert runbook["upstream_research_runbook"] is None
    assert runbook["current_step"]["key"] == "paper_demo_evidence_target"
    assert runbook["completed_step_count"] == 8
    assert runbook["total_step_count"] == 10
    assert runbook["progress_pct"] == 80
    assert "paper_demo_evidence_target" in runbook["blockers"]
    assert runbook["live_execution_enabled"] is False


def test_prediction_market_guided_demo_run_respects_research_gate(
    client: TestClient,
) -> None:
    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=contract_snapshot_payload(),
    ).json()

    run = client.post(
        "/prediction-market/paper/demo-run",
        json={
            "contract_id": contract["id"],
            "strategy": "mkt_whale_research_candidate",
            "side": "YES",
            "quantity": "1",
            "settlement_value": "1",
            "idempotency_key": "guided-demo-run-blocked",
        },
    )

    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "INTENT_REJECTED"
    assert body["completed_lifecycle"] is False
    assert body["intent"]["status"] == PredictionMarketOrderStatus.REJECTED
    assert body["order"] is None
    assert body["settlement"] is None

    progress = client.get("/prediction-market/paper/demo-progress").json()
    assert progress["status"] == "NO_PAPER_DEMO_RECORDS"
    assert progress["closed_records"] == 0
    assert progress["active_days"] == 0
    assert progress["current_check"]["key"] == "minimum_closed_records"
    assert progress["completed_check_count"] == 2
    assert progress["total_check_count"] == 11
    assert progress["progress_pct"] == 18.18
    assert progress["checks"][0]["passed"] is False
    assert progress["live_execution_enabled"] is False


def create_mkt_markets_db(db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table markets (
                ticker text primary key,
                event_ticker text default '',
                series_ticker text default '',
                title text default '',
                yes_sub_title text default '',
                category text default '',
                status text default 'open',
                close_time text default '',
                volume real default 0,
                volume_24h real default 0,
                open_interest real default 0,
                yes_bid real default 0,
                yes_ask real default 0,
                last_price real default 0,
                result text default '',
                settlement_value real default null,
                last_updated text
            );
            """
        )
        conn.execute(
            """
            insert into markets (
                ticker, event_ticker, title, yes_sub_title, category, status,
                close_time, volume, volume_24h, open_interest, yes_bid, yes_ask,
                last_price, result, settlement_value, last_updated
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "KXBTCD-26JUN25-B62500",
                "KXBTCD-26JUN25",
                "Bitcoin above test level",
                "Bitcoin above 62500",
                "crypto",
                "finalized",
                "2026-06-25T20:00:00Z",
                1200,
                200,
                900,
                0.59,
                0.60,
                0.60,
                "yes",
                None,
                "2026-06-25T21:00:00Z",
            ),
        )


def create_mkt_empty_markets_schema(db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table markets (
                ticker text primary key,
                event_ticker text default '',
                series_ticker text default '',
                title text default '',
                yes_sub_title text default '',
                category text default '',
                status text default 'open',
                close_time text default '',
                volume real default 0,
                volume_24h real default 0,
                open_interest real default 0,
                yes_bid real default 0,
                yes_ask real default 0,
                last_price real default 0,
                result text default '',
                settlement_value real default null,
                last_updated text
            );
            """
        )


def insert_mkt_market_row(db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            insert into markets (
                ticker, event_ticker, title, yes_sub_title, category, status,
                close_time, volume, volume_24h, open_interest, yes_bid, yes_ask,
                last_price, result, settlement_value, last_updated
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "KXBTCD-26JUN25-B62500",
                "KXBTCD-26JUN25",
                "Bitcoin above test level",
                "Bitcoin above 62500",
                "crypto",
                "finalized",
                "2026-06-25T20:00:00Z",
                1200,
                200,
                900,
                0.59,
                0.60,
                0.60,
                "yes",
                None,
                "2026-06-25T21:00:00Z",
            ),
        )


def add_mkt_research_inventory_rows(db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table alerts (
                id integer primary key autoincrement,
                ticker text not null,
                resolved integer default 0,
                resolved_at text default null,
                created_at text default (datetime('now'))
            );
            create table whale_trades (
                id integer primary key autoincrement,
                trade_id text unique,
                ticker text not null,
                resolved integer default 0,
                resolved_at text default null,
                created_at text default (datetime('now'))
            );
            create table crypto15m_signals (
                id integer primary key autoincrement,
                ticker text not null,
                observed_at text default (datetime('now')),
                close_time text default '',
                resolved integer default 0,
                settled_at text default null
            );
            create table bot_positions (
                id integer primary key autoincrement,
                ticker text not null,
                resolved integer default 0,
                created_at text default (datetime('now')),
                last_updated text default (datetime('now')),
                resolved_at text default null
            );
            create table trades (
                trade_id text primary key,
                ticker text not null,
                created_time text default ''
            );
            """
        )
        conn.execute(
            "insert into alerts (ticker, resolved, resolved_at, created_at) values (?, ?, ?, ?)",
            ("KXBTCD-26JUN25-B62500", 1, "2026-06-25T21:05:00Z", "2026-06-25T19:00:00Z"),
        )
        conn.execute(
            """
            insert into whale_trades (trade_id, ticker, resolved, resolved_at, created_at)
            values (?, ?, ?, ?, ?)
            """,
            (
                "trade-1",
                "KXBTCD-26JUN25-B62500",
                1,
                "2026-06-25T21:06:00Z",
                "2026-06-25T19:01:00Z",
            ),
        )
        conn.execute(
            """
            insert into crypto15m_signals (ticker, observed_at, close_time, resolved, settled_at)
            values (?, ?, ?, ?, ?)
            """,
            (
                "KXBTCD-26JUN25-B62500",
                "2026-06-25T19:02:00Z",
                "2026-06-25T20:00:00Z",
                1,
                "2026-06-25T21:07:00Z",
            ),
        )
        conn.execute(
            """
            insert into bot_positions (ticker, resolved, created_at, last_updated, resolved_at)
            values (?, ?, ?, ?, ?)
            """,
            (
                "KXBTCD-26JUN25-B62500",
                1,
                "2026-06-25T19:03:00Z",
                "2026-06-25T21:08:00Z",
                "2026-06-25T21:08:00Z",
            ),
        )
        conn.execute(
            "insert into trades (trade_id, ticker, created_time) values (?, ?, ?)",
            ("feed-trade-1", "KXBTCD-26JUN25-B62500", "2026-06-25T19:04:00Z"),
        )


def contract_snapshot_payload() -> dict:
    now = datetime.now(UTC)
    return {
        "venue": "KALSHI",
        "event_ticker": "KXBTCD-26JUN25",
        "market_title": "Bitcoin above test level on Jun 25",
        "contract_ticker": "KXBTCD-26JUN25-B62500",
        "contract_title": "Bitcoin above 62500",
        "category": "crypto",
        "status": "OPEN",
        "yes_bid_price": "0.59",
        "yes_ask_price": "0.60",
        "no_bid_price": "0.40",
        "no_ask_price": "0.41",
        "closes_at": (now + timedelta(hours=1)).isoformat(),
        "expiration_at": (now + timedelta(hours=1)).isoformat(),
        "raw_payload": {"source": "api-fixture"},
    }


def seed_accepted_research_gate(client: TestClient, *, strategy: str) -> None:
    candidate = client.post(
        "/strategies/research-candidates",
        json={
            "source": "MY_KRYPT_TRADER",
            "candidate_key": strategy,
            "strategy": strategy,
            "display_name": strategy.replace("_", " ").title(),
            "hypothesis": "Fixture research gate for prediction-market paper intent tests.",
            "status": "RESEARCH_ONLY",
        },
    ).json()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(24):
        observed_at = start + timedelta(days=index)
        response = client.post(
            "/strategies/research-candidates/observations",
            json={
                "candidate_key": strategy,
                "source": "MY_KRYPT_TRADER",
                "strategy": strategy,
                "display_name": strategy.replace("_", " ").title(),
                "hypothesis": "Fixture research gate for prediction-market paper intent tests.",
                "observation_type": "WHALE_TRADE",
                "source_event_id": f"{strategy}-{index}",
                "symbol": "BTCUSDT",
                "contract_ticker": f"KXTEST-{index}",
                "side": "YES",
                "confidence": "0.80",
                "implied_probability": "0.40",
                "observation_snapshot": {
                    "category": "CRYPTO",
                    "variant_key": "base",
                },
                "observed_at": observed_at.isoformat(),
                "resolved_at": (observed_at + timedelta(hours=1)).isoformat(),
                "outcome_snapshot": {"settlement_value": "1"},
            },
        )
        assert response.status_code == 200

    gate = client.post(
        f"/strategies/research-candidates/{candidate['id']}/backtest",
        json={
            "minimum_trades": 20,
            "minimum_oos_trades": 6,
            "minimum_active_days": 12,
            "maximum_single_day_share": "0.10",
            "minimum_walk_forward_windows": 2,
            "minimum_walk_forward_pass_rate": "1",
            "minimum_regime_trades": 10,
            "minimum_statistical_oos_trades": 6,
        },
    )
    assert gate.status_code == 200
    assert gate.json()["accepted"] is True
