import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.service import TREND_PULLBACK_V1_PARAMETER_TEMPLATE
from aurex.config.settings import get_settings
from aurex.db.base import Base
from aurex.db.models import (
    Account,
    BacktestRun,
    EquityCurvePoint,
    LiveApprovalPacket,
    LiveDailyReviewReport,
    LiveDeploymentPlan,
    PaperOrder,
    PaperTrade,
    PredictionEvidenceEvent,
    RiskDecision,
    RiskProfile,
    Signal,
    StrategyEvidenceReview,
    TradeJournalEntry,
)
from aurex.domain.enums import (
    BrokerEnvironment,
    Direction,
    LiveApprovalPacketStatus,
    LiveApprovalStatus,
    LiveApprovalType,
    LiveDailyReviewStatus,
    LiveDeploymentStatus,
    MarketRegime,
    OrderStatus,
    PredictionMarketEvidenceKind,
    ReadinessStatus,
    ReconciliationStatus,
    SignalStatus,
    StrategyEvidenceDecision,
    TradeStatus,
)
from aurex.execution_engine.paper import (
    DETERMINISTIC_PAPER_FILL_MODEL,
    PAPER_EXECUTION_SCHEMA_VERSION,
    paper_execution_evidence_hash,
)
from aurex.live_deployment.service import daily_review_context_snapshot
from aurex.prediction_market.paper import hash_evidence_payload

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


def gate_map(body: dict) -> dict[str, dict]:
    return {item["gate_key"]: item for item in body["gates"]}


def prediction_contract_snapshot_payload() -> dict:
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
        "raw_payload": {
            "source": "my-krypt-trader",
            "source_reference": "fixture:mkt-live-gate",
            "csv_format": "mkt_markets",
        },
    }


def create_live_mkt_campaign_db(db_path) -> None:
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
                    "KXLIVEGATE-26JUN25-B62500",
                    "KXLIVEGATE-26JUN25",
                    "Bitcoin above live gate test level",
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
                    "KXLIVEGATE-26JUN26-B2500",
                    "KXLIVEGATE-26JUN26",
                    "Ether above live gate test level",
                    "Ether above 2500",
                    "crypto",
                    "finalized",
                    "2026-06-26T20:05:00Z",
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
            ],
        )


def seed_accepted_mkt_research_gate(client: TestClient, *, strategy: str) -> None:
    candidate = client.post(
        "/strategies/research-candidates",
        json={
            "source": "MY_KRYPT_TRADER",
            "candidate_key": strategy,
            "strategy": strategy,
            "display_name": strategy.replace("_", " ").title(),
            "hypothesis": "Fixture research gate for MKT live deployment tests.",
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
                "hypothesis": "Fixture research gate for MKT live deployment tests.",
                "observation_type": "WHALE_TRADE",
                "source_event_id": f"{strategy}-live-gate-{index}",
                "symbol": "BTCUSDT",
                "contract_ticker": f"KXLIVE-{index}",
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


def test_live_micro_deployment_defaults_are_blocked_and_non_live(client: TestClient) -> None:
    response = client.get("/live/deployment")

    assert response.status_code == 200
    body = response.json()
    assert body["activation_allowed"] is False
    assert body["live_trading_enabled"] is False
    assert body["status"] == LiveDeploymentStatus.BLOCKED
    assert body["plan"]["live_trading_enabled"] is False
    assert body["plan"]["target_net_profit"] == "100"

    gates = gate_map(body)
    assert gates["live_trading_disabled"]["status"] == ReadinessStatus.PASS
    assert gates["one_strategy_selected"]["status"] == ReadinessStatus.BLOCKED
    assert gates["accepted_backtest_complete"]["status"] == ReadinessStatus.BLOCKED
    assert gates["symbol_scope_limited"]["status"] == ReadinessStatus.PASS
    assert gates["tiny_risk_limits"]["status"] == ReadinessStatus.PASS
    assert gates["broker_account_selected"]["status"] == ReadinessStatus.BLOCKED
    assert gates["paper_evidence_complete"]["status"] == ReadinessStatus.NOT_RUN
    assert gates["mkt_donor_credential_boundary"]["status"] == ReadinessStatus.PASS
    assert gates["mkt_donor_credential_boundary"]["evidence_snapshot"][
        "required_for_strategy"
    ] is False
    assert gates["prediction_demo_campaign_quality"]["status"] == ReadinessStatus.PASS
    assert gates["prediction_demo_campaign_quality"]["evidence_snapshot"][
        "required_for_strategy"
    ] is False
    assert gates["broker_statement_reconciliation"]["status"] == ReadinessStatus.NOT_RUN
    assert gates["strategy_evidence_review_clear"]["status"] == ReadinessStatus.NOT_RUN
    assert gates["live_execution_adapter_ready"]["status"] == ReadinessStatus.BLOCKED
    assert "live_execution_adapter_not_implemented" in gates[
        "live_execution_adapter_ready"
    ]["evidence_snapshot"]["reasons"]
    assert gates["explicit_user_approval"]["status"] == ReadinessStatus.BLOCKED
    assert body["approvals"] == []
    assert body["latest_paper_evidence"] is None
    assert body["latest_broker_statement"] is None
    assert body["latest_profit_milestone"] is None
    assert body["latest_approval_packet"] is None


def test_live_micro_deployment_requires_prediction_demo_campaign_for_mkt_strategy(
    client: TestClient,
) -> None:
    response = client.patch(
        "/live/deployment/plan",
        json={"strategy": "mkt_whale_research_candidate", "symbols": ["KALSHI"]},
    )
    assert response.status_code == 200

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    gate = gates["prediction_demo_campaign_quality"]
    credential_gate = gates["mkt_donor_credential_boundary"]

    assert gate["status"] == ReadinessStatus.NOT_RUN
    assert gate["evidence_snapshot"]["required_for_strategy"] is True
    assert gate["evidence_snapshot"]["closed_records"] == 0
    assert gate["evidence_snapshot"]["target_closed_records"] == 100
    assert "minimum_closed_records" in gate["evidence_snapshot"]["reasons"]
    assert credential_gate["status"] == ReadinessStatus.PASS
    assert credential_gate["evidence_snapshot"]["required_for_strategy"] is True
    assert credential_gate["evidence_snapshot"]["contents_read"] is False
    assert credential_gate["evidence_snapshot"][
        "production_credential_material_present"
    ] is False
    assert status["activation_allowed"] is False


def test_mkt_live_prediction_demo_gate_blocks_dirty_lifecycle_evidence(
    client: TestClient,
) -> None:
    strategy = "mkt_whale_research_candidate"
    seed_accepted_mkt_research_gate(client, strategy=strategy)
    response = client.patch(
        "/live/deployment/plan",
        json={"strategy": strategy, "symbols": ["KALSHI"]},
    )
    assert response.status_code == 200

    contract = client.post(
        "/prediction-market/contracts/snapshot",
        json=prediction_contract_snapshot_payload(),
    ).json()
    intent = client.post(
        "/prediction-market/paper/order-intents",
        json={
            "contract_id": contract["id"],
            "strategy": strategy,
            "side": "YES",
            "quantity": "10",
            "limit_price": "0.60",
            "idempotency_key": "live-gate-dirty-demo-lifecycle",
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

    status = client.get("/live/deployment").json()
    gate = gate_map(status)["prediction_demo_campaign_quality"]
    evidence = gate["evidence_snapshot"]

    assert gate["status"] == ReadinessStatus.BLOCKED
    assert evidence["required_for_strategy"] is True
    assert evidence["progress_status"] == "PAPER_DEMO_LEDGER_BLOCKED"
    assert evidence["raw_closed_records"] == 1
    assert evidence["closed_records"] == 0
    assert evidence["countable_ledger_records"] == 0
    assert evidence["ledger_blocked_records"] == 1
    assert evidence["provenance_missing_records"] == 0
    assert evidence["progress_pct"] < 100
    assert evidence["live_execution_enabled"] is False
    assert "countable_ledger_records" in evidence["reasons"]
    assert status["activation_allowed"] is False


def test_mkt_live_prediction_demo_gate_blocks_campaign_current_result_drift(
    client: TestClient,
    tmp_path,
) -> None:
    strategy = "mkt_whale_research_candidate"
    seed_accepted_mkt_research_gate(client, strategy=strategy)
    response = client.patch(
        "/live/deployment/plan",
        json={"strategy": strategy, "symbols": ["KALSHI"]},
    )
    assert response.status_code == 200

    db_path = tmp_path / "krypt-trader-live-campaign.db"
    create_live_mkt_campaign_db(db_path)
    payload = {
        "db_import": {
            "db_path": str(db_path),
            "source": "my-krypt-trader",
            "source_reference": f"{db_path}::markets:live-gate-campaign",
            "status_filter": "resolved",
            "limit": 10,
            "require_settlement_value": True,
        },
        "batch": {
            "strategy": strategy,
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "idempotency_prefix": "live-gate-campaign-drift",
        },
        "acknowledge_side_sensitivity": True,
        "side_selection_rationale": (
            "Pre-declared live gate campaign drift fixture before replay."
        ),
    }

    manifest = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-manifest",
        json=payload,
    )
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    assert manifest_body["replay_ready"] is True

    run = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-run",
        json={
            **payload,
            "batch": {
                **payload["batch"],
                "reviewed_preflight_hash": "c" * 64,
            },
            "reviewed_manifest_hash": manifest_body["manifest_hash"],
        },
    )
    assert run.status_code == 200
    assert run.json()["status"] == "CAMPAIGN_REPLAY_COMPLETED"

    clean_status = client.get("/live/deployment").json()
    clean_gate = gate_map(clean_status)["prediction_demo_campaign_quality"]
    clean_evidence = clean_gate["evidence_snapshot"]
    assert clean_gate["status"] == ReadinessStatus.BLOCKED
    assert clean_evidence["campaign_audit_records"] == 1
    assert clean_evidence["strategy_campaign_audit_records"] == 1
    assert clean_evidence["campaign_current_result_drifted_records"] == 0
    assert clean_evidence["strategy_campaign_current_result_drifted_records"] == 0
    assert clean_evidence["batch_current_result_drifted_records"] == 0
    assert "prediction_demo_campaign_current_result_drifted" not in clean_evidence[
        "reasons"
    ]
    assert "minimum_closed_records" in clean_evidence["reasons"]

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

    drifted_status = client.get("/live/deployment").json()
    drifted_gate = gate_map(drifted_status)["prediction_demo_campaign_quality"]
    drifted_evidence = drifted_gate["evidence_snapshot"]

    assert drifted_gate["status"] == ReadinessStatus.BLOCKED
    assert drifted_evidence["required_for_strategy"] is True
    assert drifted_evidence["ready_for_live_review"] is False
    assert drifted_evidence["progress_ready_for_live_review"] is False
    assert drifted_evidence["campaign_current_result_drifted_records"] == 1
    assert drifted_evidence["strategy_campaign_current_result_drifted_records"] == 1
    assert drifted_evidence["batch_current_result_drifted_records"] == 0
    assert drifted_evidence["latest_campaign_record"][
        "current_result_ledger_status"
    ] == "CURRENT_RESULT_LEDGER_DRIFTED"
    assert drifted_evidence["latest_strategy_campaign_record"][
        "current_result_ledger_status"
    ] == "CURRENT_RESULT_LEDGER_DRIFTED"
    assert drifted_evidence["latest_batch_record"] is None
    assert "prediction_demo_campaign_current_result_drifted" in drifted_evidence[
        "reasons"
    ]
    assert "prediction_demo_campaign_strategy_current_result_drifted" in drifted_evidence[
        "reasons"
    ]
    assert "prediction_demo_batch_current_result_drifted" not in drifted_evidence[
        "reasons"
    ]
    assert "fill_evidence_payload_mismatch" in drifted_evidence[
        "latest_campaign_record"
    ]["current_result_ledger_blockers"]
    assert "current-result ledger drift" in drifted_evidence["next_action"]
    assert drifted_status["activation_allowed"] is False

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    review_body = review.json()
    assert review_body["decision"] == StrategyEvidenceDecision.BLOCKED
    assert "prediction_demo_campaign_quality_not_passed" in review_body["reasons"]
    assert any(
        "current-result ledger drift" in action
        for action in review_body["next_actions"]
    )


def test_mkt_live_prediction_demo_gate_rejects_other_strategy_campaign_evidence(
    client: TestClient,
    tmp_path,
) -> None:
    selected_strategy = "mkt_whale_research_candidate"
    donor_strategy = "mkt_momentum_research_candidate"
    seed_accepted_mkt_research_gate(client, strategy=selected_strategy)
    seed_accepted_mkt_research_gate(client, strategy=donor_strategy)

    db_path = tmp_path / "krypt-trader-other-strategy-campaign.db"
    create_live_mkt_campaign_db(db_path)
    payload = {
        "db_import": {
            "db_path": str(db_path),
            "source": "my-krypt-trader",
            "source_reference": f"{db_path}::markets:other-strategy-campaign",
            "status_filter": "resolved",
            "limit": 10,
            "require_settlement_value": True,
        },
        "batch": {
            "strategy": donor_strategy,
            "side": "YES",
            "quantity": "10",
            "max_records": 2,
            "idempotency_prefix": "live-gate-foreign-campaign",
        },
        "acknowledge_side_sensitivity": True,
        "side_selection_rationale": (
            "Pre-declared foreign strategy fixture; it must not qualify another strategy."
        ),
    }
    manifest = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-manifest",
        json=payload,
    )
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    assert manifest_body["replay_ready"] is True

    run = client.post(
        "/prediction-market/paper/demo-mkt-db-campaign-run",
        json={
            **payload,
            "batch": {
                **payload["batch"],
                "reviewed_preflight_hash": "d" * 64,
            },
            "reviewed_manifest_hash": manifest_body["manifest_hash"],
        },
    )
    assert run.status_code == 200
    assert run.json()["campaign_evidence"]["strategy"] == donor_strategy

    response = client.patch(
        "/live/deployment/plan",
        json={"strategy": selected_strategy, "symbols": ["KALSHI"]},
    )
    assert response.status_code == 200

    status = client.get("/live/deployment").json()
    gate = gate_map(status)["prediction_demo_campaign_quality"]
    evidence = gate["evidence_snapshot"]

    assert gate["status"] == ReadinessStatus.BLOCKED
    assert evidence["strategy"] == selected_strategy
    assert evidence["raw_closed_records"] == 0
    assert evidence["closed_records"] == 0
    assert evidence["campaign_audit_records"] == 1
    assert evidence["campaign_current_result_clean_records"] == 1
    assert evidence["strategy_campaign_audit_records"] == 0
    assert evidence["strategy_campaign_current_result_clean_records"] == 0
    assert evidence["latest_campaign_record"]["strategy"] == donor_strategy
    assert evidence["latest_strategy_campaign_record"] is None
    assert "prediction_demo_campaign_strategy_evidence_missing" in evidence[
        "reasons"
    ]
    assert "minimum_closed_records" in evidence["reasons"]
    assert "selected strategy" in evidence["next_action"]
    assert status["activation_allowed"] is False


def test_mkt_live_readiness_fails_when_donor_production_credentials_are_present(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    userdata = tmp_path / "mkt-userdata"
    credentials_dir = userdata / "credentials"
    credentials_dir.mkdir(parents=True)
    (credentials_dir / "apikey.production.txt").write_text(
        "production-api-key-that-must-not-be-read",
        encoding="utf-8",
    )
    monkeypatch.setenv("KRYPT_TRADER_USERDATA", str(userdata))

    response = client.patch(
        "/live/deployment/plan",
        json={"strategy": "mkt_whale_research_candidate", "symbols": ["KALSHI"]},
    )
    assert response.status_code == 200

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    gate = gates["mkt_donor_credential_boundary"]

    assert gate["status"] == ReadinessStatus.FAIL
    assert gate["evidence_snapshot"]["required_for_strategy"] is True
    assert gate["evidence_snapshot"]["contents_read"] is False
    assert gate["evidence_snapshot"]["production_credential_material_present"] is True
    assert gate["evidence_snapshot"]["production_credential_material_count"] == 1
    assert "mkt_production_credential_material_present" in gate["evidence_snapshot"][
        "reasons"
    ]
    assert status["activation_allowed"] is False

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    review_body = review.json()
    assert review_body["decision"] == StrategyEvidenceDecision.BLOCKED
    assert "mkt_donor_credential_boundary_not_passed" in review_body["reasons"]
    assert any(
        "production MKT credential files" in action
        for action in review_body["next_actions"]
    )


def test_accepted_backtest_gate_requires_matching_strategy_and_symbols(
    client: TestClient,
) -> None:
    wrong_strategy = post_backtest_with_protocol(
        client,
        accepted_backtest_payload(strategy="breakout_v1"),
    )
    assert wrong_strategy.status_code == 201
    assert wrong_strategy.json()["result"]["acceptance_passed"] is True

    blocked_status = client.get("/live/deployment").json()
    blocked_gates = gate_map(blocked_status)
    assert blocked_gates["accepted_backtest_complete"]["status"] == ReadinessStatus.BLOCKED
    assert blocked_status["activation_allowed"] is False

    weak_matching = post_backtest_with_protocol(
        client,
        weak_self_accepted_backtest_payload(),
    )
    assert weak_matching.status_code == 201
    assert weak_matching.json()["result"]["acceptance_passed"] is True

    weak_status = client.get("/live/deployment").json()
    weak_gates = gate_map(weak_status)
    weak_evidence = weak_gates["accepted_backtest_complete"]["evidence_snapshot"]
    assert weak_gates["accepted_backtest_complete"]["status"] == ReadinessStatus.BLOCKED
    assert weak_evidence["total_trades"] == 2
    assert "accepted_backtest_minimum_trades_not_met" in weak_evidence[
        "live_readiness_reasons"
    ]
    assert weak_status["activation_allowed"] is False

    concentrated_matching = post_backtest_with_protocol(
        client,
        concentrated_self_accepted_backtest_payload(),
    )
    assert concentrated_matching.status_code == 201
    assert concentrated_matching.json()["result"]["acceptance_passed"] is True

    concentrated_status = client.get("/live/deployment").json()
    concentrated_gates = gate_map(concentrated_status)
    concentrated_evidence = concentrated_gates["accepted_backtest_complete"][
        "evidence_snapshot"
    ]
    assert concentrated_gates["accepted_backtest_complete"]["status"] == (
        ReadinessStatus.BLOCKED
    )
    assert concentrated_evidence["trade_distribution"]["active_trading_days"] == 1
    assert "accepted_backtest_active_trading_days_not_met" in concentrated_evidence[
        "live_readiness_reasons"
    ]
    assert "accepted_backtest_trade_concentration_too_high" in concentrated_evidence[
        "live_readiness_reasons"
    ]
    assert concentrated_status["activation_allowed"] is False

    matching = post_backtest_with_protocol(
        client,
        accepted_backtest_payload(),
    )
    assert matching.status_code == 201
    matching_body = matching.json()
    assert matching_body["result"]["acceptance_passed"] is True

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    evidence = gates["accepted_backtest_complete"]["evidence_snapshot"]
    assert gates["accepted_backtest_complete"]["status"] == ReadinessStatus.PASS
    assert evidence["backtest_run_id"] == matching_body["id"]
    assert evidence["strategy"] == "trend_pullback_v1"
    assert evidence["symbols"] == ["BTCUSDT"]
    assert evidence["total_trades"] == 100
    assert evidence["acceptance_passed"] is True
    assert evidence["out_of_sample"]["total_trades"] == 50
    assert evidence["walk_forward"]["window_count"] == 3
    assert Decimal(evidence["walk_forward"]["pass_rate"]) >= Decimal("0.66")
    assert evidence["trade_distribution"]["active_trading_days"] >= 15
    assert evidence["market_regime_breakdown"]["missing_market_regime_count"] == 0
    assert evidence["live_readiness_reasons"] == []
    assert status["activation_allowed"] is False


def test_live_micro_deployment_plan_updates_stay_non_live(client: TestClient) -> None:
    response = client.patch(
        "/live/deployment/plan",
        json={
            "symbols": ["ethusdt", "btcusdt"],
            "risk_per_trade": "0.0100",
            "max_open_positions": 2,
        },
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["symbols"] == ["ETHUSDT", "BTCUSDT"]
    assert plan["live_trading_enabled"] is False
    assert plan["status"] == LiveDeploymentStatus.BLOCKED

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["symbol_scope_limited"]["status"] == ReadinessStatus.PASS
    assert gates["tiny_risk_limits"]["status"] == ReadinessStatus.FAIL
    assert status["activation_allowed"] is False


def test_imported_backtest_csv_can_satisfy_accepted_backtest_gate(
    client: TestClient,
) -> None:
    payload = accepted_backtest_payload()
    register_backtest_protocol(client, payload)
    csv_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"source_format", "trades"}
    }
    csv_payload["csv_format"] = "tradingview"
    csv_payload["csv_text"] = tradingview_csv_from_payload(payload)

    preflight = client.post("/backtests/reports/preflight-csv", json=csv_payload)
    imported = client.post("/backtests/reports/import-csv", json=csv_payload)
    status = client.get("/live/deployment").json()
    gates = gate_map(status)

    assert preflight.status_code == 200
    assert preflight.json()["status"] == "READY"
    assert preflight.json()["analysis_summary"]["acceptance_passed"] is True
    assert imported.status_code == 201
    assert imported.json()["result"]["total_trades"] == 100
    assert gates["accepted_backtest_complete"]["status"] == ReadinessStatus.PASS
    assert gates["accepted_backtest_complete"]["evidence_snapshot"]["backtest_run_id"] == (
        imported.json()["id"]
    )
    assert status["activation_allowed"] is False


def test_daily_review_and_activation_attempt_do_not_enable_live(client: TestClient) -> None:
    review_response = client.post(
        "/live/deployment/daily-review",
        json={"notes": "Stage 14 dry run"},
    )

    assert review_response.status_code == 200
    review = review_response.json()
    assert review["status"] == LiveDailyReviewStatus.BLOCKED
    assert review["reconciliation_status"] == "NOT_READY"
    assert review["rule_violations"] == ["broker_reconciliation_not_matched"]

    activation_response = client.post("/live/deployment/activation-attempt")

    assert activation_response.status_code == 200
    body = activation_response.json()
    assert body["activation_allowed"] is False
    assert body["live_trading_enabled"] is False
    assert body["status"] == LiveDeploymentStatus.BLOCKED
    assert "explicit_user_approval" in body["blocking_gate_keys"]
    assert body["blocking_gates"]
    approval_blocker = next(
        item for item in body["blocking_gates"] if item["gate_key"] == "explicit_user_approval"
    )
    assert approval_blocker["status"] == ReadinessStatus.BLOCKED
    assert "approvals" in approval_blocker["next_action"]
    assert any("approvals" in action for action in body["next_actions"])
    assert "no live broker execution was attempted" in body["message"]


def test_clean_daily_review_blocks_after_plan_context_changes(
    client: TestClient,
) -> None:
    client.get("/live/deployment")

    with next(client.app.dependency_overrides[get_db]()) as session:
        plan = session.execute(select(LiveDeploymentPlan)).scalar_one()
        report = LiveDailyReviewReport(
            live_deployment_plan=plan,
            review_date=datetime.now(UTC).date(),
            status=LiveDailyReviewStatus.CLEAN,
            realized_pl=Decimal("0"),
            trade_count=0,
            rule_violations=[],
            reconciliation_status=ReconciliationStatus.MATCHED,
            review_snapshot={
                "review_context": daily_review_context_snapshot(
                    plan,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            },
            notes="Fixture clean daily review.",
            reviewed_at=datetime.now(UTC),
        )
        session.add(report)
        session.commit()

    fresh_status = client.get("/live/deployment").json()
    fresh_gate = gate_map(fresh_status)["daily_review_ready"]
    assert fresh_gate["status"] == ReadinessStatus.PASS
    assert fresh_gate["evidence_snapshot"]["freshness_reasons"] == []

    plan_update = client.patch(
        "/live/deployment/plan",
        json={"risk_per_trade": "0.0030"},
    )
    assert plan_update.status_code == 200

    stale_status = client.get("/live/deployment").json()
    stale_gate = gate_map(stale_status)["daily_review_ready"]
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert Decimal(
        stale_gate["evidence_snapshot"]["reviewed_context"]["deployment_plan"][
            "risk_per_trade"
        ],
    ) == Decimal("0.0025")
    assert Decimal(
        stale_gate["evidence_snapshot"]["current_context"]["deployment_plan"][
            "risk_per_trade"
        ],
    ) == Decimal("0.0030")
    assert "daily_review_deployment_plan_risk_per_trade_changed_since_review" in (
        stale_gate["evidence_snapshot"]["freshness_reasons"]
    )
    assert stale_status["activation_allowed"] is False


def test_live_flag_cannot_bypass_missing_live_execution_adapter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUREX_LIVE_TRADING_ENABLED", "true")
    get_settings.cache_clear()
    try:
        status = client.get("/live/deployment").json()
        gates = gate_map(status)
        adapter_gate = gates["live_execution_adapter_ready"]

        assert status["live_trading_enabled"] is True
        assert status["activation_allowed"] is False
        assert gates["live_trading_disabled"]["status"] == ReadinessStatus.FAIL
        assert adapter_gate["status"] == ReadinessStatus.BLOCKED
        assert adapter_gate["evidence_snapshot"]["adapter"] == "disabled"
        assert adapter_gate["evidence_snapshot"]["implemented"] is False
        assert adapter_gate["evidence_snapshot"]["supports_live_order_submission"] is False
        assert "live_execution_adapter_not_implemented" in adapter_gate[
            "evidence_snapshot"
        ]["reasons"]

        activation_response = client.post("/live/deployment/activation-attempt")
        assert activation_response.status_code == 200
        activation = activation_response.json()
        assert activation["activation_allowed"] is False
        assert "live_execution_adapter_ready" in activation["blocking_gate_keys"]
        assert activation["blocking_gates"]
        adapter_blocker = next(
            item
            for item in activation["blocking_gates"]
            if item["gate_key"] == "live_execution_adapter_ready"
        )
        assert adapter_blocker["reason"] == "live_execution_adapter_not_implemented"
        assert "live execution adapter" in adapter_blocker["next_action"]
        assert any("live execution adapter" in action for action in activation["next_actions"])
        assert "no live broker execution was attempted" in activation["message"]
    finally:
        get_settings.cache_clear()


def test_daily_review_flags_first_live_failure_conditions(client: TestClient) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=3,
            calendar_days=1,
            prefix="daily-review-failure",
            create_journals=True,
            profitable_trade_count=0,
            loss_amount=Decimal("-12"),
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        trades[0].journal_entries[0].emotional_override = True
        session.delete(trades[1].journal_entries[0])
        session.commit()

    response = client.post(
        "/live/deployment/daily-review",
        json={"notes": "Failure protocol dry run"},
    )

    assert response.status_code == 200
    review = response.json()
    assert review["status"] == LiveDailyReviewStatus.VIOLATION
    assert set(review["rule_violations"]) == {
        "broker_reconciliation_not_matched",
        "daily_loss_limit_breached",
        "weekly_loss_limit_breached",
        "three_consecutive_losses",
        "unjournaled_trades_present",
        "journal_rule_violations_present",
    }
    assert review["realized_pl"] == "-36.00000000"
    assert review["trade_count"] == 3
    assert review["review_snapshot"]["daily_realized_pl"] == "-36.00000000"
    assert review["review_snapshot"]["weekly_realized_pl"] == "-36.00000000"
    assert Decimal(review["review_snapshot"]["daily_loss_limit"]) == Decimal("-10")
    assert Decimal(review["review_snapshot"]["weekly_loss_limit"]) == Decimal("-30")
    assert review["review_snapshot"]["consecutive_losses"] == 3
    assert review["review_snapshot"]["journal_audit"]["unjournaled_trade_count"] == 1
    assert review["review_snapshot"]["journal_audit"]["journal_rule_violation_count"] == 1

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["daily_review_ready"]["status"] == ReadinessStatus.NOT_RUN
    assert status["activation_allowed"] is False
    assert status["live_trading_enabled"] is False


def test_explicit_approvals_are_auditable_but_do_not_enable_live(
    client: TestClient,
) -> None:
    for approval_type in LiveApprovalType:
        response = client.post(
            "/live/deployment/approvals",
            json={
                "approval_type": approval_type,
                "approved": True,
                "approver": "Adonis",
                "evidence_reference": f"manual-check:{approval_type.value.lower()}",
                "notes": "Recorded for Stage 14 evidence hardening.",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == LiveApprovalStatus.APPROVED

    status = client.get("/live/deployment").json()
    gates = gate_map(status)

    assert gates["explicit_user_approval"]["status"] == ReadinessStatus.PASS
    assert len(status["approvals"]) == 4
    assert status["activation_allowed"] is False
    assert status["live_trading_enabled"] is False


def test_explicit_approvals_become_stale_after_plan_risk_change(
    client: TestClient,
) -> None:
    for approval_type in LiveApprovalType:
        response = client.post(
            "/live/deployment/approvals",
            json={
                "approval_type": approval_type,
                "approved": True,
                "approver": "Adonis",
                "evidence_reference": f"manual-check:{approval_type.value.lower()}",
                "notes": "Approval before risk change.",
            },
        )
        assert response.status_code == 200

    initial_status = client.get("/live/deployment").json()
    initial_gates = gate_map(initial_status)
    assert initial_gates["explicit_user_approval"]["status"] == ReadinessStatus.PASS
    assert initial_status["plan"]["approval_snapshot"]["broker_approved"] is True

    plan_update = client.patch(
        "/live/deployment/plan",
        json={"risk_per_trade": "0.0030"},
    )
    assert plan_update.status_code == 200

    stale_status = client.get("/live/deployment").json()
    stale_gates = gate_map(stale_status)
    approval_gate = stale_gates["explicit_user_approval"]
    assert approval_gate["status"] == ReadinessStatus.BLOCKED
    assert stale_status["plan"]["approval_snapshot"]["broker_approved"] is False
    assert "broker_deployment_plan_risk_per_trade_changed_since_approval" in (
        approval_gate["evidence_snapshot"]["stale_reasons"]
    )
    assert "live_execution_deployment_plan_risk_per_trade_changed_since_approval" in (
        approval_gate["evidence_snapshot"]["stale_reasons"]
    )
    assert Decimal(
        approval_gate["evidence_snapshot"]["current_context"]["deployment_plan"][
            "risk_per_trade"
        ]
    ) == Decimal("0.0030")
    assert stale_status["activation_allowed"] is False


def test_explicit_approvals_become_stale_after_strategy_review_evidence_drift(
    client: TestClient,
) -> None:
    backtest = post_backtest_with_protocol(client, accepted_backtest_payload())
    assert backtest.status_code == 201

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="approval-review-evidence-drift",
            profitable_trade_count=70,
        )
        session.commit()

    paper_report = client.post("/live/deployment/paper-evidence/run")
    assert paper_report.status_code == 200
    assert paper_report.json()["status"] == ReadinessStatus.PASS

    statement = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/approval-review-evidence-drift.pdf",
            "broker_trade_count": 100,
            "broker_net_pl": "110",
            "broker_fees": "20",
            "broker_slippage": "10",
            "notes": "Approval context strategy-review drift fixture.",
        },
    )
    assert statement.status_code == 200
    assert statement.json()["status"] == ReadinessStatus.PASS

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    assert review.json()["decision"] == StrategyEvidenceDecision.CANDIDATE

    for approval_type in LiveApprovalType:
        response = client.post(
            "/live/deployment/approvals",
            json={
                "approval_type": approval_type,
                "approved": True,
                "approver": "Adonis",
                "evidence_reference": f"manual-review:{approval_type.value.lower()}",
                "notes": "Approval after clean strategy evidence review.",
            },
        )
        assert response.status_code == 200
        approval_context = response.json()["evidence_snapshot"]["approval_context"]
        assert approval_context["strategy_evidence_review"]["gate_status"] == (
            ReadinessStatus.PASS
        )

    initial_status = client.get("/live/deployment").json()
    initial_gates = gate_map(initial_status)
    assert initial_gates["explicit_user_approval"]["status"] == ReadinessStatus.PASS
    assert initial_status["plan"]["approval_snapshot"]["broker_approved"] is True

    with next(client.app.dependency_overrides[get_db]()) as session:
        run = session.execute(select(BacktestRun)).scalar_one()
        assert run.id == backtest.json()["id"]
        run.config_hash = "approval-context-mutated-config-hash"
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gates = gate_map(stale_status)
    approval_gate = stale_gates["explicit_user_approval"]
    review_gate = stale_gates["strategy_evidence_review_clear"]

    assert stale_gates["accepted_backtest_complete"]["status"] == ReadinessStatus.PASS
    assert review_gate["status"] == ReadinessStatus.BLOCKED
    assert approval_gate["status"] == ReadinessStatus.BLOCKED
    assert stale_status["plan"]["approval_snapshot"]["broker_approved"] is False
    assert "broker_strategy_evidence_review_context_changed_since_approval" in (
        approval_gate["evidence_snapshot"]["stale_reasons"]
    )
    assert "live_execution_strategy_evidence_review_context_changed_since_approval" in (
        approval_gate["evidence_snapshot"]["stale_reasons"]
    )
    assert approval_gate["evidence_snapshot"]["current_context"][
        "strategy_evidence_review"
    ]["gate_status"] == ReadinessStatus.BLOCKED
    assert "accepted_backtest_complete_evidence_changed_since_review" in (
        approval_gate["evidence_snapshot"]["current_context"][
            "strategy_evidence_review"
        ]["freshness_reasons"]
    )
    assert stale_status["activation_allowed"] is False


def test_explicit_approvals_become_stale_after_same_packet_content_drift(
    client: TestClient,
) -> None:
    packet_response = client.post(
        "/live/deployment/approval-packet",
        json=approval_packet_payload(),
    )
    assert packet_response.status_code == 200
    packet = packet_response.json()
    assert packet["status"] == LiveApprovalPacketStatus.COMPLETE
    assert packet["evidence_snapshot"]["packet_fingerprint"]

    for approval_type in LiveApprovalType:
        response = client.post(
            "/live/deployment/approvals",
            json={
                "approval_type": approval_type,
                "approved": True,
                "approver": "Adonis",
                "evidence_reference": f"manual-packet:{approval_type.value.lower()}",
                "notes": "Approval after packet review.",
            },
        )
        assert response.status_code == 200
        approval_context = response.json()["evidence_snapshot"]["approval_context"]
        assert approval_context["approval_packet_id"] == packet["id"]
        assert approval_context["approval_packet"]["fingerprint"] == packet[
            "evidence_snapshot"
        ]["packet_fingerprint"]

    initial_status = client.get("/live/deployment").json()
    initial_gates = gate_map(initial_status)
    assert initial_gates["explicit_user_approval"]["status"] == ReadinessStatus.PASS
    assert initial_status["plan"]["approval_snapshot"]["broker_approved"] is True

    with next(client.app.dependency_overrides[get_db]()) as session:
        stored_packet = session.get(LiveApprovalPacket, packet["id"])
        assert stored_packet is not None
        stored_packet.fee_slippage_model_reference = (
            "docs/broker/mutated-fee-slippage-model.md"
        )
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gates = gate_map(stale_status)
    approval_gate = stale_gates["explicit_user_approval"]
    broker_gate = stale_gates["broker_account_selected"]

    assert broker_gate["status"] == ReadinessStatus.PASS
    assert approval_gate["status"] == ReadinessStatus.BLOCKED
    assert stale_status["plan"]["approval_snapshot"]["broker_approved"] is False
    assert "broker_approval_packet_context_changed_since_approval" in (
        approval_gate["evidence_snapshot"]["stale_reasons"]
    )
    assert "live_execution_approval_packet_context_changed_since_approval" in (
        approval_gate["evidence_snapshot"]["stale_reasons"]
    )
    assert approval_gate["evidence_snapshot"]["current_context"]["approval_packet_id"] == (
        packet["id"]
    )
    assert approval_gate["evidence_snapshot"]["current_context"]["approval_packet"][
        "fingerprint"
    ] != packet["evidence_snapshot"]["packet_fingerprint"]
    assert stale_status["activation_allowed"] is False


def test_approval_packet_links_review_only_broker_and_account_without_live(
    client: TestClient,
) -> None:
    response = client.post(
        "/live/deployment/approval-packet",
        json=approval_packet_payload(),
    )

    assert response.status_code == 200
    packet = response.json()
    assert packet["status"] == LiveApprovalPacketStatus.COMPLETE
    assert packet["credentials_stored"] is False
    assert packet["leverage_allowed"] is False
    assert packet["account_constraints_reference"] == (
        "docs/broker/aurex-reviewed-broker-account-constraints.md"
    )
    assert packet["fee_slippage_model_reference"] == (
        "docs/broker/aurex-reviewed-broker-fee-slippage-model.md"
    )
    assert packet["broker_connection_id"] is not None
    assert packet["account_id"] is not None

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["broker_account_selected"]["status"] == ReadinessStatus.PASS
    assert gates["broker_account_selected"]["evidence_snapshot"]["leverage_allowed"] is False
    assert status["latest_approval_packet"]["id"] == packet["id"]
    assert status["plan"]["broker_connection_id"] == packet["broker_connection_id"]
    assert status["plan"]["account_id"] == packet["account_id"]
    assert status["live_trading_enabled"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        from aurex.db.models import BrokerConnection

        connection = session.get(BrokerConnection, packet["broker_connection_id"])
        assert connection is not None
        assert connection.environment == BrokerEnvironment.LIVE
        assert connection.live_trading_enabled is False


def test_approval_packet_with_credentials_stored_keeps_broker_gate_blocked(
    client: TestClient,
) -> None:
    payload = approval_packet_payload()
    payload["credentials_stored"] = True

    response = client.post("/live/deployment/approval-packet", json=payload)

    assert response.status_code == 200
    packet = response.json()
    assert packet["status"] == LiveApprovalPacketStatus.DRAFT
    assert packet["credentials_stored"] is True

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["broker_account_selected"]["status"] == ReadinessStatus.BLOCKED
    assert status["activation_allowed"] is False


def test_approval_packet_with_leverage_allowed_keeps_broker_gate_blocked(
    client: TestClient,
) -> None:
    payload = approval_packet_payload()
    payload["leverage_allowed"] = True

    response = client.post("/live/deployment/approval-packet", json=payload)

    assert response.status_code == 200
    packet = response.json()
    assert packet["status"] == LiveApprovalPacketStatus.DRAFT
    assert packet["leverage_allowed"] is True
    assert "leverage_not_allowed_for_micro_deployment" in packet["evidence_snapshot"][
        "packet_reasons"
    ]

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["broker_account_selected"]["status"] == ReadinessStatus.BLOCKED
    assert gates["broker_account_selected"]["evidence_snapshot"]["leverage_allowed"] is True
    assert status["activation_allowed"] is False


def test_paper_evidence_report_blocks_until_thresholds_are_met(
    client: TestClient,
) -> None:
    weak_report = client.post("/live/deployment/paper-evidence/run")

    assert weak_report.status_code == 200
    weak_body = weak_report.json()
    assert weak_body["status"] == ReadinessStatus.BLOCKED
    assert "minimum_paper_trades_not_met" in weak_body["reasons"]
    assert "minimum_calendar_days_not_met" in weak_body["reasons"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(session, total=100, calendar_days=1)
        session.commit()

    same_day_report = client.post("/live/deployment/paper-evidence/run")

    assert same_day_report.status_code == 200
    same_day_body = same_day_report.json()
    assert same_day_body["status"] == ReadinessStatus.BLOCKED
    assert same_day_body["total_trades"] == 100
    assert same_day_body["calendar_days_observed"] == 1
    assert "minimum_calendar_days_not_met" in same_day_body["reasons"]
    assert "insufficient_active_trading_days" in same_day_body["reasons"]
    assert "paper_trade_concentration_too_high" in same_day_body["reasons"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        clear_paper_evidence_fixture_data(session)
        seed_closed_paper_trades(session, total=100, calendar_days=30, prefix="spread")
        session.commit()

    strong_report = client.post("/live/deployment/paper-evidence/run")

    assert strong_report.status_code == 200
    strong_body = strong_report.json()
    assert strong_body["status"] == ReadinessStatus.PASS
    assert strong_body["total_trades"] == 100
    assert strong_body["calendar_days_observed"] == 30
    assert strong_body["evidence_snapshot"]["active_trading_days"] == 30
    assert strong_body["evidence_snapshot"]["minimum_active_trading_days"] == 15
    assert Decimal(str(strong_body["evidence_snapshot"]["max_single_day_trade_share"])) <= (
        Decimal("0.25")
    )
    assert Decimal(str(strong_body["max_allowed_drawdown"])) == Decimal("30.00000000")
    assert strong_body["unexplained_trade_count"] == 0
    assert strong_body["risk_rule_violation_count"] == 0
    assert strong_body["journaled_trade_count"] == 100
    assert strong_body["unjournaled_trade_count"] == 0
    assert strong_body["journal_rule_violation_count"] == 0
    assert strong_body["reasons"] == []

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["paper_evidence_complete"]["status"] == ReadinessStatus.PASS
    assert gates["paper_evidence_complete"]["evidence_snapshot"]["freshness_reasons"] == []
    assert status["latest_paper_evidence"]["id"] == strong_body["id"]


def test_paper_evidence_gate_blocks_stale_report_after_trade_ledger_change(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="freshness-base",
        )
        session.commit()

    report = client.post("/live/deployment/paper-evidence/run")
    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.PASS
    assert body["evidence_snapshot"]["ledger_snapshot"]["total_trades"] == 100

    clean_status = client.get("/live/deployment").json()
    clean_gate = gate_map(clean_status)["paper_evidence_complete"]
    assert clean_gate["status"] == ReadinessStatus.PASS

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=1,
            calendar_days=1,
            prefix="freshness-new-trade",
            profitable_trade_count=1,
        )
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gate = gate_map(stale_status)["paper_evidence_complete"]
    evidence = stale_gate["evidence_snapshot"]
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert "paper_evidence_trade_ledger_changed_since_report" in evidence[
        "freshness_reasons"
    ]
    assert "paper_evidence_metrics_changed_since_report" in evidence[
        "freshness_reasons"
    ]
    assert evidence["reviewed_ledger"]["total_trades"] == 100
    assert evidence["current_ledger"]["total_trades"] == 101
    assert stale_status["latest_paper_evidence"]["id"] == body["id"]
    assert stale_status["activation_allowed"] is False


def test_paper_evidence_and_profit_milestone_reject_legacy_instant_fills(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="instant-fill-block",
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        for trade in trades:
            order = trade.paper_order
            order.fill_model = "instant"
            order.execution_assumptions = {}
            order.execution_assumptions_hash = None
            order.fees = Decimal("0")
            order.slippage = Decimal("0")
            trade.fees = Decimal("0")
            trade.slippage = Decimal("0")
            trade.exit_price = trade.entry_price + (trade.realized_pl or Decimal("0"))
        session.commit()

    report = client.post("/live/deployment/paper-evidence/run")

    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.BLOCKED
    assert body["evidence_snapshot"]["evidence_grade_trade_count"] == 0
    assert body["evidence_snapshot"]["non_evidence_grade_trade_count"] == 100
    assert body["evidence_snapshot"]["execution_quality_violation_count"] == 100
    assert body["evidence_snapshot"]["fill_model_counts"] == {"instant": 100}
    assert "non_evidence_grade_paper_fills_present" in body["reasons"]
    assert "paper_execution_quality_violations_present" in body["reasons"]
    assert body["evidence_snapshot"]["execution_quality_violations"][0][
        "reason"
    ] == "non_evidence_grade_fill_model"

    milestone = client.post("/live/deployment/profit-milestone/run").json()
    assert "non_evidence_grade_paper_fills_present" in milestone["reasons"]
    assert "paper_execution_quality_violations_present" in milestone["reasons"]


def test_paper_evidence_gate_detects_fill_model_drift_after_pass(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="execution-drift",
        )
        session.commit()

    report = client.post("/live/deployment/paper-evidence/run")
    assert report.status_code == 200
    assert report.json()["status"] == ReadinessStatus.PASS

    with next(client.app.dependency_overrides[get_db]()) as session:
        order = session.execute(select(PaperOrder).order_by(PaperOrder.id)).scalars().first()
        assert order is not None
        order.fill_model = "instant"
        session.commit()

    gate = gate_map(client.get("/live/deployment").json())["paper_evidence_complete"]
    assert gate["status"] == ReadinessStatus.BLOCKED
    assert "paper_execution_quality_changed_since_report" in gate[
        "evidence_snapshot"
    ]["freshness_reasons"]


def test_paper_evidence_gate_blocks_stale_report_after_journal_change(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="freshness-journal",
        )
        session.commit()

    report = client.post("/live/deployment/paper-evidence/run")
    assert report.status_code == 200
    assert report.json()["status"] == ReadinessStatus.PASS

    with next(client.app.dependency_overrides[get_db]()) as session:
        trade = session.execute(select(PaperTrade).order_by(PaperTrade.id)).scalars().first()
        assert trade is not None
        trade.journal_entries[0].rule_followed = False
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gate = gate_map(stale_status)["paper_evidence_complete"]
    evidence = stale_gate["evidence_snapshot"]
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert "paper_evidence_journal_ledger_changed_since_report" in evidence[
        "freshness_reasons"
    ]
    assert evidence["reviewed_ledger"]["journal_rule_violation_count"] == 0
    assert evidence["current_ledger"]["journal_rule_violation_count"] == 1
    assert stale_status["activation_allowed"] is False


def test_paper_evidence_report_blocks_sparse_span_and_trade_concentration(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=1,
            prefix="sparse-calendar",
        )
        oldest_close = datetime.now(UTC) - timedelta(days=29)
        trade = session.execute(select(PaperTrade).order_by(PaperTrade.id)).scalars().first()
        assert trade is not None
        trade.opened_at = oldest_close
        trade.closed_at = oldest_close
        trade.paper_order.created_order_at = oldest_close
        trade.paper_order.filled_at = oldest_close
        session.commit()

    report = client.post("/live/deployment/paper-evidence/run")

    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.BLOCKED
    assert body["total_trades"] == 100
    assert body["calendar_days_observed"] == 30
    assert "minimum_calendar_days_not_met" not in body["reasons"]
    assert "insufficient_active_trading_days" in body["reasons"]
    assert "paper_trade_concentration_too_high" in body["reasons"]
    assert body["evidence_snapshot"]["active_trading_days"] == 2
    assert body["evidence_snapshot"]["max_single_day_trade_count"] == 99


def test_paper_evidence_report_counts_only_plan_strategy_and_symbols(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="wrong-strategy",
            strategy="breakout_v1",
        )
        session.commit()

    out_of_scope_report = client.post("/live/deployment/paper-evidence/run")

    assert out_of_scope_report.status_code == 200
    out_of_scope_body = out_of_scope_report.json()
    assert out_of_scope_body["status"] == ReadinessStatus.BLOCKED
    assert out_of_scope_body["total_trades"] == 0
    assert out_of_scope_body["evidence_snapshot"]["in_scope_trade_count"] == 0
    assert out_of_scope_body["evidence_snapshot"]["out_of_scope_trade_count"] == 100
    assert out_of_scope_body["evidence_snapshot"]["strategy_scope"] == "trend_pullback_v1"
    assert out_of_scope_body["evidence_snapshot"]["symbol_scope"] == ["BTCUSDT"]
    assert "minimum_paper_trades_not_met" in out_of_scope_body["reasons"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="right-scope",
        )
        session.commit()

    scoped_report = client.post("/live/deployment/paper-evidence/run")

    assert scoped_report.status_code == 200
    scoped_body = scoped_report.json()
    assert scoped_body["status"] == ReadinessStatus.PASS
    assert scoped_body["total_trades"] == 100
    assert scoped_body["evidence_snapshot"]["in_scope_trade_count"] == 100
    assert scoped_body["evidence_snapshot"]["out_of_scope_trade_count"] == 100
    assert scoped_body["reasons"] == []


def test_trade_journal_api_records_auditable_entry(client: TestClient) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=1,
            calendar_days=1,
            prefix="journal-api",
            create_journals=False,
        )
        trade = session.execute(select(PaperTrade)).scalar_one()
        session.commit()
        trade_id = trade.id

    response = client.post(
        "/journal/trades",
        json={
            "paper_trade_id": trade_id,
            "author": "Adonis",
            "thesis": "Trend pullback followed the tested setup.",
            "execution_notes": "Fixture execution.",
            "outcome_notes": "Closed according to the simulated plan.",
            "rule_followed": True,
            "emotional_override": False,
            "evidence_snapshot": {"source": "test"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["paper_trade_id"] == trade_id
    assert body["rule_followed"] is True
    assert body["emotional_override"] is False

    entries = client.get(f"/journal/trades?paper_trade_id={trade_id}").json()
    assert len(entries) == 1
    assert entries[0]["id"] == body["id"]


def test_paper_evidence_report_blocks_missing_and_bad_journals(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="journal-block",
            create_journals=True,
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        bad_entry = trades[1].journal_entries[0]
        bad_entry.rule_followed = False
        bad_entry.emotional_override = True
        session.delete(trades[0].journal_entries[0])
        session.commit()

    report = client.post("/live/deployment/paper-evidence/run")

    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.BLOCKED
    assert body["journaled_trade_count"] == 99
    assert body["unjournaled_trade_count"] == 1
    assert body["journal_rule_violation_count"] == 2
    assert "unjournaled_trades_present" in body["reasons"]
    assert "journal_rule_violations_present" in body["reasons"]
    assert body["evidence_snapshot"]["unjournaled_trades"][0]["reason"] == (
        "missing_trade_journal"
    )


def test_paper_evidence_report_blocks_drawdown_and_integrity_violations(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="integrity",
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        trades[0].paper_order_id = "missing-order"
        trades[1].risk_amount = Decimal("6")
        trades[2].realized_pl = Decimal("-50")
        trades[2].r_multiple = Decimal("-10")
        trades[2].exit_price = Decimal("50")
        session.commit()

    report = client.post("/live/deployment/paper-evidence/run")

    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.BLOCKED
    assert body["total_trades"] == 100
    assert body["unexplained_trade_count"] == 1
    assert body["risk_rule_violation_count"] == 2
    assert "max_drawdown_exceeds_limit" in body["reasons"]
    assert "unexplained_trades_present" in body["reasons"]
    assert "risk_rule_violations_present" in body["reasons"]
    assert body["evidence_snapshot"]["unexplained_trades"][0]["reason"] == (
        "missing_paper_order"
    )
    assert {
        item["reason"] for item in body["evidence_snapshot"]["risk_rule_violations"]
    } == {
        "trade_risk_exceeds_approved_risk",
        "trade_risk_amount_does_not_match_stop_distance",
    }


def test_broker_statement_reconciliation_blocks_then_passes(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=3,
            calendar_days=3,
            prefix="statement-recon",
            profitable_trade_count=2,
            loss_amount=Decimal("-1"),
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        for trade in trades:
            trade.fees = Decimal("0.10")
            trade.slippage = Decimal("0.05")
        closed_at_values = [
            trade.closed_at.replace(tzinfo=UTC)
            if trade.closed_at and trade.closed_at.tzinfo is None
            else trade.closed_at
            for trade in trades
            if trade.closed_at
        ]
        statement_start_at = min(closed_at_values)
        statement_end_at = max(closed_at_values)
        session.commit()

    bad_report = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/sandbox-statement-001.pdf",
            "statement_start_at": statement_start_at.isoformat(),
            "statement_end_at": statement_end_at.isoformat(),
            "broker_trade_count": 2,
            "broker_net_pl": "4",
            "broker_fees": "0.20",
            "broker_slippage": "0.15",
            "notes": "Deliberate mismatch fixture.",
        },
    )

    assert bad_report.status_code == 200
    bad_body = bad_report.json()
    assert bad_body["status"] == ReadinessStatus.BLOCKED
    assert bad_body["aurex_trade_count"] == 3
    assert Decimal(bad_body["aurex_net_pl"]) == Decimal("3")
    assert Decimal(bad_body["aurex_fees"]) == Decimal("0.30")
    assert {
        item["reason"] for item in bad_body["discrepancies"]
    } == {
        "statement_trade_count_mismatch",
        "statement_net_pl_mismatch",
        "statement_fee_mismatch",
    }

    blocked_status = client.get("/live/deployment").json()
    blocked_gates = gate_map(blocked_status)
    assert blocked_gates["broker_statement_reconciliation"]["status"] == (
        ReadinessStatus.BLOCKED
    )
    assert blocked_status["latest_broker_statement"]["id"] == bad_body["id"]
    assert blocked_status["activation_allowed"] is False

    good_report = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/sandbox-statement-001-corrected.pdf",
            "statement_start_at": statement_start_at.isoformat(),
            "statement_end_at": statement_end_at.isoformat(),
            "broker_trade_count": 3,
            "broker_net_pl": "3",
            "broker_fees": "0.30",
            "broker_slippage": "0.15",
            "notes": "Corrected statement fixture.",
        },
    )

    assert good_report.status_code == 200
    good_body = good_report.json()
    assert good_body["status"] == ReadinessStatus.PASS
    assert good_body["discrepancies"] == []
    assert good_body["broker_trade_count"] == 3
    assert good_body["aurex_trade_count"] == 3
    assert Decimal(good_body["broker_net_pl"]) == Decimal("3")
    assert Decimal(good_body["aurex_net_pl"]) == Decimal("3")

    passed_status = client.get("/live/deployment").json()
    passed_gates = gate_map(passed_status)
    assert passed_gates["broker_statement_reconciliation"]["status"] == ReadinessStatus.PASS
    assert passed_gates["broker_statement_reconciliation"]["evidence_snapshot"][
        "freshness_reasons"
    ] == []
    assert passed_status["latest_broker_statement"]["id"] == good_body["id"]
    assert passed_status["activation_allowed"] is False

    reports = client.get("/live/deployment/broker-statements").json()
    assert reports[0]["id"] == good_body["id"]
    assert reports[1]["id"] == bad_body["id"]


def test_broker_statement_gate_blocks_stale_report_after_trade_pl_change(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=3,
            calendar_days=3,
            prefix="statement-fresh-pl",
            profitable_trade_count=2,
            loss_amount=Decimal("-1"),
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        closed_at_values = [
            trade.closed_at.replace(tzinfo=UTC)
            if trade.closed_at and trade.closed_at.tzinfo is None
            else trade.closed_at
            for trade in trades
            if trade.closed_at
        ]
        statement_start_at = min(closed_at_values)
        statement_end_at = max(closed_at_values)
        session.commit()

    report = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/statement-fresh-pl.pdf",
            "statement_start_at": statement_start_at.isoformat(),
            "statement_end_at": statement_end_at.isoformat(),
            "broker_trade_count": 3,
            "broker_net_pl": "3",
            "broker_fees": "0.60",
            "broker_slippage": "0.30",
            "notes": "Statement matches before ledger edit.",
        },
    )
    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.PASS
    assert body["aurex_snapshot"]["ledger_snapshot"]["aurex_net_pl"] == "3"

    with next(client.app.dependency_overrides[get_db]()) as session:
        trade = session.execute(
            select(PaperTrade)
            .where(PaperTrade.realized_pl == Decimal("2"))
            .order_by(PaperTrade.closed_at.asc())
        ).scalars().first()
        assert trade is not None
        trade.realized_pl = Decimal("5")
        trade.exit_price = Decimal("105")
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gate = gate_map(stale_status)["broker_statement_reconciliation"]
    evidence = stale_gate["evidence_snapshot"]
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert "broker_statement_trade_ledger_changed_since_report" in evidence[
        "freshness_reasons"
    ]
    assert "broker_statement_totals_changed_since_report" in evidence[
        "freshness_reasons"
    ]
    assert evidence["reviewed_ledger"]["aurex_net_pl"] == "3"
    assert evidence["current_ledger"]["aurex_net_pl"] == "6"
    assert stale_status["activation_allowed"] is False


def test_broker_statement_gate_blocks_stale_report_after_fee_change(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=3,
            calendar_days=3,
            prefix="statement-fresh-fee",
            profitable_trade_count=2,
            loss_amount=Decimal("-1"),
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        closed_at_values = [
            trade.closed_at.replace(tzinfo=UTC)
            if trade.closed_at and trade.closed_at.tzinfo is None
            else trade.closed_at
            for trade in trades
            if trade.closed_at
        ]
        statement_start_at = min(closed_at_values)
        statement_end_at = max(closed_at_values)
        session.commit()

    report = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/statement-fresh-fee.pdf",
            "statement_start_at": statement_start_at.isoformat(),
            "statement_end_at": statement_end_at.isoformat(),
            "broker_trade_count": 3,
            "broker_net_pl": "3",
            "broker_fees": "0.60",
            "broker_slippage": "0.30",
            "notes": "Statement matches before cost edit.",
        },
    )
    assert report.status_code == 200
    assert report.json()["status"] == ReadinessStatus.PASS

    with next(client.app.dependency_overrides[get_db]()) as session:
        trade = session.execute(select(PaperTrade).order_by(PaperTrade.id)).scalars().first()
        assert trade is not None
        trade.fees = Decimal("0.25")
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gate = gate_map(stale_status)["broker_statement_reconciliation"]
    evidence = stale_gate["evidence_snapshot"]
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert "broker_statement_totals_changed_since_report" in evidence[
        "freshness_reasons"
    ]
    assert evidence["reviewed_ledger"]["aurex_fees"] == "0.6"
    assert evidence["current_ledger"]["aurex_fees"] == "0.65"
    assert stale_status["activation_allowed"] is False


def test_broker_statement_csv_preflight_and_reconcile_passes_gate(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=3,
            calendar_days=3,
            prefix="statement-csv",
            profitable_trade_count=2,
            loss_amount=Decimal("-1"),
        )
        trades = list(session.execute(select(PaperTrade)).scalars())
        for trade in trades:
            trade.fees = Decimal("0.10")
            trade.slippage = Decimal("0.05")
        statement_rows = [
            "external_trade_id,closed_at,net_pl,fees,slippage",
            *[
                (
                    f"statement-csv-{index},{trade.closed_at.isoformat()},"
                    f"{trade.realized_pl},{trade.fees},{trade.slippage}"
                )
                for index, trade in enumerate(trades, start=1)
            ],
        ]
        statement_csv = "\n".join(statement_rows)
        session.commit()

    preflight = client.post(
        "/live/deployment/broker-statements/preflight-csv",
        json={
            "statement_reference": "docs/broker/statement-csv-export.csv",
            "csv_text": statement_csv,
            "notes": "Statement CSV fixture.",
        },
    )

    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY"
    assert preflight_body["broker_trade_count"] == 3
    assert Decimal(preflight_body["broker_net_pl"]) == Decimal("3")
    assert Decimal(preflight_body["broker_fees"]) == Decimal("0.30")
    assert Decimal(preflight_body["broker_slippage"]) == Decimal("0.15")
    assert preflight_body["analysis_summary"]["ready_count"] == 3
    assert preflight_body["analysis_summary"]["active_trading_days"] == 3
    assert preflight_body["deployment_strategy"] == "trend_pullback_v1"
    assert preflight_body["deployment_symbols"] == ["BTCUSDT"]
    assert preflight_body["reconciliation_status"] == "READY"
    assert preflight_body["aurex_trade_count"] == 3
    assert Decimal(preflight_body["aurex_net_pl"]) == Decimal("3")
    assert Decimal(preflight_body["aurex_fees"]) == Decimal("0.30")
    assert Decimal(preflight_body["aurex_slippage"]) == Decimal("0.15")
    assert preflight_body["reconciliation_discrepancies"] == []
    assert preflight_body["reconciliation_next_action"] == (
        "Broker statement CSV reconciles with current Aurex closed trades."
    )

    report = client.post(
        "/live/deployment/broker-statements/reconcile-csv",
        json={
            "statement_reference": "docs/broker/statement-csv-export.csv",
            "csv_text": statement_csv,
            "notes": "Statement CSV fixture.",
        },
    )

    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.PASS
    assert body["discrepancies"] == []
    assert body["broker_trade_count"] == 3
    assert body["aurex_trade_count"] == 3
    assert Decimal(body["statement_snapshot"]["csv_analysis_summary"]["broker_net_pl"]) == (
        Decimal("3")
    )
    assert body["statement_snapshot"]["csv_required_headers"] == [
        "external_trade_id",
        "closed_at",
        "net_pl",
        "fees",
        "slippage",
    ]

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["broker_statement_reconciliation"]["status"] == ReadinessStatus.PASS
    assert status["latest_broker_statement"]["id"] == body["id"]
    assert status["activation_allowed"] is False
    assert status["live_trading_enabled"] is False


def test_broker_statement_csv_preflight_surfaces_reconciliation_mismatch(
    client: TestClient,
) -> None:
    statement_csv = "\n".join(
        [
            "external_trade_id,closed_at,net_pl,fees,slippage",
            "broker-001,2026-01-01T10:00:00Z,10,0.10,0",
        ]
    )

    preflight = client.post(
        "/live/deployment/broker-statements/preflight-csv",
        json={
            "statement_reference": "docs/broker/no-aurex-trades-statement.csv",
            "csv_text": statement_csv,
        },
    )

    assert preflight.status_code == 200
    body = preflight.json()
    assert body["status"] == "READY"
    assert body["reconciliation_status"] == "BLOCKED"
    assert body["broker_trade_count"] == 1
    assert body["aurex_trade_count"] == 0
    discrepancy_reasons = {
        discrepancy["reason"] for discrepancy in body["reconciliation_discrepancies"]
    }
    assert "no_closed_trades_in_statement_window" in discrepancy_reasons
    assert "statement_trade_count_mismatch" in discrepancy_reasons
    assert "statement_net_pl_mismatch" in discrepancy_reasons
    assert body["reconciliation_next_action"] == (
        "Use a broker statement window that contains scoped Aurex closed trades."
    )

    reports = client.get("/live/deployment/broker-statements")
    assert reports.status_code == 200
    assert reports.json() == []


def test_broker_statement_csv_reconcile_rejects_bad_rows_without_report(
    client: TestClient,
) -> None:
    bad_csv = "\n".join(
        [
            "external_trade_id,closed_at,net_pl,fees,slippage",
            "broker-001,2026-01-01T10:00:00Z,10,0.10,0",
            "broker-002,2026-01-02T10:00:00Z,5,-0.10,0",
        ]
    )

    preflight = client.post(
        "/live/deployment/broker-statements/preflight-csv",
        json={
            "statement_reference": "docs/broker/bad-statement.csv",
            "csv_text": bad_csv,
        },
    )
    reconcile = client.post(
        "/live/deployment/broker-statements/reconcile-csv",
        json={
            "statement_reference": "docs/broker/bad-statement.csv",
            "csv_text": bad_csv,
        },
    )
    reports = client.get("/live/deployment/broker-statements")

    assert preflight.status_code == 200
    assert preflight.json()["status"] == "PARTIAL"
    assert preflight.json()["reconciliation_status"] == "NOT_READY"
    assert preflight.json()["reconciliation_discrepancies"] == [
        {"reason": "broker_statement_csv_not_ready"}
    ]
    assert preflight.json()["analysis_summary"]["rejected_reasons"] == {
        "fees_cannot_be_negative": 1
    }
    assert reconcile.status_code == 400
    assert "must be READY" in reconcile.json()["detail"]
    assert reports.status_code == 200
    assert reports.json() == []


def test_first_profit_milestone_report_audits_protocol_without_enabling_live(
    client: TestClient,
) -> None:
    empty_report = client.post("/live/deployment/profit-milestone/run")

    assert empty_report.status_code == 200
    empty_body = empty_report.json()
    assert empty_body["status"] == ReadinessStatus.BLOCKED
    assert empty_body["trade_count"] == 0
    assert {
        "live_execution_adapter_not_implemented",
        "no_closed_trades",
        "target_net_profit_not_reached",
        "broker_statement_missing",
    }.issubset(set(empty_body["reasons"]))

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="profit-milestone",
            profitable_trade_count=100,
        )
        session.commit()

    statement = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/profit-milestone-statement.pdf",
            "broker_trade_count": 100,
            "broker_net_pl": "200",
            "broker_fees": "20",
            "broker_slippage": "10",
            "notes": "Statement fixture covers all milestone trades.",
        },
    )
    assert statement.status_code == 200
    assert statement.json()["status"] == ReadinessStatus.PASS

    report = client.post("/live/deployment/profit-milestone/run")

    assert report.status_code == 200
    body = report.json()
    assert body["status"] == ReadinessStatus.BLOCKED
    assert body["reasons"] == ["live_execution_adapter_not_implemented"]
    assert body["target_net_profit"] == "100.00000000"
    assert body["total_net_pl"] == "200.00000000"
    assert body["trade_count"] == 100
    assert body["journaled_trade_count"] == 100
    assert body["unjournaled_trade_count"] == 0
    assert body["journal_rule_violation_count"] == 0
    assert body["unexplained_trade_count"] == 0
    assert body["risk_rule_violation_count"] == 0
    assert body["daily_loss_breach_count"] == 0
    assert body["weekly_loss_breach_count"] == 0
    assert body["broker_statement_status"] == ReadinessStatus.PASS
    assert body["live_execution_adapter_implemented"] is False
    assert body["evidence_snapshot"]["live_execution_adapter"]["adapter"] == "disabled"
    assert body["evidence_snapshot"]["live_execution_adapter"]["implemented"] is False
    assert body["evidence_snapshot"]["live_execution_adapter"][
        "supports_live_order_submission"
    ] is False

    status = client.get("/live/deployment").json()
    assert status["latest_profit_milestone"]["id"] == body["id"]
    assert status["activation_allowed"] is False
    assert status["live_trading_enabled"] is False

    reports = client.get("/live/deployment/profit-milestones").json()
    assert reports[0]["id"] == body["id"]
    assert reports[1]["id"] == empty_body["id"]


def test_strategy_evidence_review_blocks_when_required_evidence_is_missing(
    client: TestClient,
) -> None:
    response = client.post("/live/deployment/evidence-review/run")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == StrategyEvidenceDecision.BLOCKED
    assert body["strategy"] == "trend_pullback_v1"
    assert body["symbols"] == ["BTCUSDT"]
    assert "accepted_backtest_complete_not_passed" in body["reasons"]
    assert "paper_evidence_complete_not_passed" in body["reasons"]
    assert "broker_statement_reconciliation_not_passed" in body["reasons"]
    assert body["gate_snapshot"]["live_trading_disabled"]["status"] == ReadinessStatus.PASS
    assert body["evidence_snapshot"]["live_trading_enabled"] is False
    assert body["evidence_snapshot"]["activation_allowed"] is False
    assert any("accepted backtest" in action for action in body["next_actions"])

    reviews = client.get("/live/deployment/evidence-reviews")
    assert reviews.status_code == 200
    assert reviews.json()[0]["id"] == body["id"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        saved_review = session.execute(select(StrategyEvidenceReview)).scalar_one()
        assert saved_review.decision == StrategyEvidenceDecision.BLOCKED

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["strategy_evidence_review_clear"]["status"] == ReadinessStatus.BLOCKED
    assert gates["strategy_evidence_review_clear"]["evidence_snapshot"]["decision"] == (
        StrategyEvidenceDecision.BLOCKED
    )


def test_strategy_evidence_review_explains_missing_mkt_campaign_evidence(
    client: TestClient,
) -> None:
    response = client.patch(
        "/live/deployment/plan",
        json={"strategy": "mkt_whale_research_candidate", "symbols": ["KALSHI"]},
    )
    assert response.status_code == 200

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    body = review.json()

    assert body["decision"] == StrategyEvidenceDecision.BLOCKED
    assert "prediction_demo_campaign_quality_not_passed" in body["reasons"]
    gate_evidence = body["gate_snapshot"]["prediction_demo_campaign_quality"][
        "evidence_snapshot"
    ]
    assert "prediction_demo_campaign_strategy_evidence_missing" in gate_evidence[
        "reasons"
    ]
    assert any(
        "guarded MKT DB paper/demo campaign replay for the selected MKT strategy"
        in action
        for action in body["next_actions"]
    )


def test_strategy_evidence_review_marks_mature_negative_paper_evidence_do_not_trade(
    client: TestClient,
) -> None:
    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="evidence-review-negative",
            profitable_trade_count=0,
            loss_amount=Decimal("-1"),
        )
        session.commit()

    paper_report = client.post("/live/deployment/paper-evidence/run")
    assert paper_report.status_code == 200
    assert paper_report.json()["status"] == ReadinessStatus.BLOCKED
    assert "expectancy_not_positive" in paper_report.json()["reasons"]

    response = client.post("/live/deployment/evidence-review/run")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == StrategyEvidenceDecision.DO_NOT_TRADE
    assert "expectancy_not_positive" in body["reasons"]
    assert "profit_factor_below_minimum" in body["reasons"]
    assert body["evidence_snapshot"]["latest_paper_evidence_report_id"] == (
        paper_report.json()["id"]
    )
    assert body["evidence_snapshot"]["live_trading_enabled"] is False
    assert body["next_actions"][0].startswith("Do not trade")

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["strategy_evidence_review_clear"]["status"] == ReadinessStatus.FAIL
    assert gates["strategy_evidence_review_clear"]["evidence_snapshot"]["decision"] == (
        StrategyEvidenceDecision.DO_NOT_TRADE
    )
    assert status["activation_allowed"] is False


def test_strategy_evidence_review_candidate_requires_clean_pre_live_evidence(
    client: TestClient,
) -> None:
    backtest = post_backtest_with_protocol(client, accepted_backtest_payload())
    assert backtest.status_code == 201

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="evidence-review-candidate",
            profitable_trade_count=70,
        )
        session.commit()

    paper_report = client.post("/live/deployment/paper-evidence/run")
    assert paper_report.status_code == 200
    assert paper_report.json()["status"] == ReadinessStatus.PASS

    statement = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/evidence-review-statement.pdf",
            "broker_trade_count": 100,
            "broker_net_pl": "110",
            "broker_fees": "20",
            "broker_slippage": "10",
            "notes": "Evidence review candidate fixture.",
        },
    )
    assert statement.status_code == 200
    assert statement.json()["status"] == ReadinessStatus.PASS

    response = client.post("/live/deployment/evidence-review/run")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == StrategyEvidenceDecision.CANDIDATE
    assert body["reasons"] == []
    assert body["gate_snapshot"]["accepted_backtest_complete"]["status"] == (
        ReadinessStatus.PASS
    )
    assert body["gate_snapshot"]["paper_evidence_complete"]["status"] == (
        ReadinessStatus.PASS
    )
    assert body["gate_snapshot"]["broker_statement_reconciliation"]["status"] == (
        ReadinessStatus.PASS
    )
    assert body["evidence_snapshot"]["latest_paper_evidence_report_id"] == (
        paper_report.json()["id"]
    )
    assert body["evidence_snapshot"]["latest_broker_statement_report_id"] == (
        statement.json()["id"]
    )
    assert body["evidence_snapshot"]["live_trading_enabled"] is False
    assert body["evidence_snapshot"]["activation_allowed"] is False
    assert "does not authorize live trading" in body["summary"]

    status = client.get("/live/deployment").json()
    gates = gate_map(status)
    assert gates["strategy_evidence_review_clear"]["status"] == ReadinessStatus.PASS
    assert gates["strategy_evidence_review_clear"]["evidence_snapshot"]["decision"] == (
        StrategyEvidenceDecision.CANDIDATE
    )
    assert gates["strategy_evidence_review_clear"]["evidence_snapshot"][
        "freshness_reasons"
    ] == []
    assert status["activation_allowed"] is False


def test_strategy_evidence_review_gate_blocks_stale_candidate_review(
    client: TestClient,
) -> None:
    backtest = post_backtest_with_protocol(client, accepted_backtest_payload())
    assert backtest.status_code == 201

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="evidence-review-stale",
            profitable_trade_count=70,
        )
        session.commit()

    paper_report = client.post("/live/deployment/paper-evidence/run")
    assert paper_report.status_code == 200
    assert paper_report.json()["status"] == ReadinessStatus.PASS

    statement = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/evidence-review-stale-statement.pdf",
            "broker_trade_count": 100,
            "broker_net_pl": "110",
            "broker_fees": "20",
            "broker_slippage": "10",
            "notes": "Evidence review stale fixture.",
        },
    )
    assert statement.status_code == 200
    assert statement.json()["status"] == ReadinessStatus.PASS

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    assert review.json()["decision"] == StrategyEvidenceDecision.CANDIDATE

    fresh_status = client.get("/live/deployment").json()
    fresh_gate = gate_map(fresh_status)["strategy_evidence_review_clear"]
    assert fresh_gate["status"] == ReadinessStatus.PASS
    assert fresh_gate["evidence_snapshot"]["current_artifacts"] == (
        fresh_gate["evidence_snapshot"]["reviewed_artifacts"]
    )

    newer_paper_report = client.post("/live/deployment/paper-evidence/run")
    assert newer_paper_report.status_code == 200
    assert newer_paper_report.json()["status"] == ReadinessStatus.PASS

    stale_status = client.get("/live/deployment").json()
    stale_gate = gate_map(stale_status)["strategy_evidence_review_clear"]
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert stale_gate["evidence_snapshot"]["decision"] == StrategyEvidenceDecision.CANDIDATE
    assert stale_gate["evidence_snapshot"]["reviewed_artifacts"][
        "paper_evidence_report_id"
    ] == paper_report.json()["id"]
    assert stale_gate["evidence_snapshot"]["current_artifacts"][
        "paper_evidence_report_id"
    ] == newer_paper_report.json()["id"]
    assert "paper_evidence_changed_since_review" in stale_gate["evidence_snapshot"][
        "freshness_reasons"
    ]
    assert stale_status["activation_allowed"] is False


def test_strategy_evidence_review_gate_blocks_candidate_after_plan_risk_change(
    client: TestClient,
) -> None:
    backtest = post_backtest_with_protocol(client, accepted_backtest_payload())
    assert backtest.status_code == 201

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="evidence-review-plan-risk-change",
            profitable_trade_count=70,
        )
        session.commit()

    paper_report = client.post("/live/deployment/paper-evidence/run")
    assert paper_report.status_code == 200
    assert paper_report.json()["status"] == ReadinessStatus.PASS

    statement = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/evidence-review-plan-risk-statement.pdf",
            "broker_trade_count": 100,
            "broker_net_pl": "110",
            "broker_fees": "20",
            "broker_slippage": "10",
            "notes": "Evidence review plan freshness fixture.",
        },
    )
    assert statement.status_code == 200
    assert statement.json()["status"] == ReadinessStatus.PASS

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    assert review.json()["decision"] == StrategyEvidenceDecision.CANDIDATE

    fresh_status = client.get("/live/deployment").json()
    fresh_gate = gate_map(fresh_status)["strategy_evidence_review_clear"]
    assert fresh_gate["status"] == ReadinessStatus.PASS

    plan_update = client.patch(
        "/live/deployment/plan",
        json={"risk_per_trade": "0.0030"},
    )
    assert plan_update.status_code == 200

    stale_status = client.get("/live/deployment").json()
    stale_gate = gate_map(stale_status)["strategy_evidence_review_clear"]
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert stale_gate["evidence_snapshot"]["decision"] == StrategyEvidenceDecision.CANDIDATE
    assert Decimal(
        stale_gate["evidence_snapshot"]["reviewed_plan"]["risk_per_trade"]
    ) == Decimal("0.0025")
    assert Decimal(
        stale_gate["evidence_snapshot"]["current_plan"]["risk_per_trade"]
    ) == Decimal("0.0030")
    assert "deployment_plan_risk_per_trade_changed_since_review" in stale_gate[
        "evidence_snapshot"
    ]["freshness_reasons"]
    assert stale_status["activation_allowed"] is False


def test_strategy_evidence_review_gate_blocks_candidate_after_reviewed_gate_status_change(
    client: TestClient,
) -> None:
    backtest = post_backtest_with_protocol(client, accepted_backtest_payload())
    assert backtest.status_code == 201

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="evidence-review-gate-status-change",
            profitable_trade_count=70,
        )
        session.commit()

    paper_report = client.post("/live/deployment/paper-evidence/run")
    assert paper_report.status_code == 200
    assert paper_report.json()["status"] == ReadinessStatus.PASS

    statement = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/evidence-review-gate-status.pdf",
            "broker_trade_count": 100,
            "broker_net_pl": "110",
            "broker_fees": "20",
            "broker_slippage": "10",
            "notes": "Evidence review gate-status freshness fixture.",
        },
    )
    assert statement.status_code == 200
    assert statement.json()["status"] == ReadinessStatus.PASS

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    assert review.json()["decision"] == StrategyEvidenceDecision.CANDIDATE

    fresh_status = client.get("/live/deployment").json()
    fresh_gate = gate_map(fresh_status)["strategy_evidence_review_clear"]
    assert fresh_gate["status"] == ReadinessStatus.PASS
    assert fresh_gate["evidence_snapshot"]["reviewed_gate_statuses"][
        "kill_switch_clear"
    ] == ReadinessStatus.PASS
    assert fresh_gate["evidence_snapshot"]["current_gate_statuses"][
        "kill_switch_clear"
    ] == ReadinessStatus.PASS

    with next(client.app.dependency_overrides[get_db]()) as session:
        risk_profile = session.execute(select(RiskProfile)).scalar_one()
        risk_profile.kill_switch_enabled = True
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gates = gate_map(stale_status)
    stale_gate = stale_gates["strategy_evidence_review_clear"]
    assert stale_gates["kill_switch_clear"]["status"] == ReadinessStatus.FAIL
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert stale_gate["evidence_snapshot"]["reviewed_gate_statuses"][
        "kill_switch_clear"
    ] == ReadinessStatus.PASS
    assert stale_gate["evidence_snapshot"]["current_gate_statuses"][
        "kill_switch_clear"
    ] == ReadinessStatus.FAIL
    assert "kill_switch_clear_status_changed_since_review" in stale_gate[
        "evidence_snapshot"
    ]["freshness_reasons"]
    assert stale_status["activation_allowed"] is False


def test_strategy_evidence_review_gate_blocks_candidate_after_gate_evidence_change(
    client: TestClient,
) -> None:
    backtest = post_backtest_with_protocol(client, accepted_backtest_payload())
    assert backtest.status_code == 201

    with next(client.app.dependency_overrides[get_db]()) as session:
        seed_closed_paper_trades(
            session,
            total=100,
            calendar_days=30,
            prefix="evidence-review-gate-evidence-change",
            profitable_trade_count=70,
        )
        session.commit()

    paper_report = client.post("/live/deployment/paper-evidence/run")
    assert paper_report.status_code == 200
    assert paper_report.json()["status"] == ReadinessStatus.PASS

    statement = client.post(
        "/live/deployment/broker-statements/reconcile",
        json={
            "statement_reference": "docs/broker/evidence-review-gate-evidence.pdf",
            "broker_trade_count": 100,
            "broker_net_pl": "110",
            "broker_fees": "20",
            "broker_slippage": "10",
            "notes": "Evidence review gate-evidence freshness fixture.",
        },
    )
    assert statement.status_code == 200
    assert statement.json()["status"] == ReadinessStatus.PASS

    review = client.post("/live/deployment/evidence-review/run")
    assert review.status_code == 200
    assert review.json()["decision"] == StrategyEvidenceDecision.CANDIDATE

    fresh_status = client.get("/live/deployment").json()
    fresh_gate = gate_map(fresh_status)["strategy_evidence_review_clear"]
    assert fresh_gate["status"] == ReadinessStatus.PASS
    assert fresh_gate["evidence_snapshot"]["reviewed_gate_statuses"][
        "accepted_backtest_complete"
    ] == ReadinessStatus.PASS
    assert fresh_gate["evidence_snapshot"]["current_gate_statuses"][
        "accepted_backtest_complete"
    ] == ReadinessStatus.PASS
    assert fresh_gate["evidence_snapshot"]["reviewed_gate_fingerprints"][
        "accepted_backtest_complete"
    ] == fresh_gate["evidence_snapshot"]["current_gate_fingerprints"][
        "accepted_backtest_complete"
    ]

    with next(client.app.dependency_overrides[get_db]()) as session:
        run = session.execute(select(BacktestRun)).scalar_one()
        assert run.id == backtest.json()["id"]
        run.config_hash = "mutated-config-hash-after-review"
        session.commit()

    stale_status = client.get("/live/deployment").json()
    stale_gates = gate_map(stale_status)
    stale_gate = stale_gates["strategy_evidence_review_clear"]
    assert stale_gates["accepted_backtest_complete"]["status"] == ReadinessStatus.PASS
    assert stale_gate["status"] == ReadinessStatus.BLOCKED
    assert stale_gate["evidence_snapshot"]["reviewed_gate_statuses"][
        "accepted_backtest_complete"
    ] == ReadinessStatus.PASS
    assert stale_gate["evidence_snapshot"]["current_gate_statuses"][
        "accepted_backtest_complete"
    ] == ReadinessStatus.PASS
    assert stale_gate["evidence_snapshot"]["reviewed_gate_fingerprints"][
        "accepted_backtest_complete"
    ] != stale_gate["evidence_snapshot"]["current_gate_fingerprints"][
        "accepted_backtest_complete"
    ]
    assert "accepted_backtest_complete_evidence_changed_since_review" in stale_gate[
        "evidence_snapshot"
    ]["freshness_reasons"]
    assert stale_status["activation_allowed"] is False


def approval_packet_payload() -> dict:
    return {
        "broker_name": "Aurex Reviewed Broker",
        "account_label": "micro-live-review",
        "account_type": "cash",
        "asset_class": "crypto",
        "jurisdiction": "United States",
        "currency": "USD",
        "broker_terms_reference": "docs/broker/aurex-reviewed-broker-terms.md",
        "fee_schedule_reference": "docs/broker/aurex-reviewed-broker-fees.md",
        "margin_policy_reference": "docs/broker/aurex-reviewed-broker-margin.md",
        "account_constraints_reference": (
            "docs/broker/aurex-reviewed-broker-account-constraints.md"
        ),
        "execution_policy_reference": "docs/broker/aurex-reviewed-broker-execution.md",
        "fee_slippage_model_reference": (
            "docs/broker/aurex-reviewed-broker-fee-slippage-model.md"
        ),
        "paper_to_live_checklist_reference": (
            "docs/broker/aurex-reviewed-broker-paper-to-live-checklist.md"
        ),
        "sandbox_test_reference": "docs/broker/aurex-reviewed-broker-sandbox-test.md",
        "leverage_allowed": False,
        "tax_notes": "Personal account review only.",
        "credentials_stored": False,
    }


def accepted_backtest_payload(
    strategy: str = "trend_pullback_v1",
    symbols: list[str] | None = None,
) -> dict:
    in_sample_start = datetime(2026, 1, 1, tzinfo=UTC)
    out_of_sample_start = datetime(2026, 2, 16, tzinfo=UTC)
    parameters = dict(TREND_PULLBACK_V1_PARAMETER_TEMPLATE)
    selected_symbols = symbols or ["BTCUSDT"]
    return {
        "strategy": strategy,
        "strategy_version": "1.3.0",
        "symbols": selected_symbols,
        "timeframe": "15m",
        "data_source": "tradingview-export",
        "source_format": "tradingview",
        "csv_timezone": "UTC",
        "source_reference": (
            f"tradingview://strategy-tester/BINANCE:{selected_symbols[0]}/15m"
        ),
        "data_start": "2026-01-01T00:00:00Z",
        "data_end": "2026-03-31T00:00:00Z",
        "in_sample_start": "2026-01-01T00:00:00Z",
        "in_sample_end": "2026-02-15T00:00:00Z",
        "out_of_sample_start": "2026-02-16T00:00:00Z",
        "out_of_sample_end": "2026-03-31T00:00:00Z",
        "parameters": parameters,
        "cost_model": {"commission_percent": "0.05"},
        "slippage_model": {"type": "fixed_ticks", "ticks": "2"},
        "risk_snapshot": {"risk_per_trade": "0.005"},
        "walk_forward_windows": [
            {
                "window_id": "wf-1",
                "train_start": "2026-01-01T00:00:00Z",
                "train_end": "2026-01-15T00:00:00Z",
                "test_start": "2026-01-16T00:00:00Z",
                "test_end": "2026-01-25T00:00:00Z",
                "configuration_reference": "fixture://walk-forward/wf-1",
                "parameters": parameters,
            },
            {
                "window_id": "wf-2",
                "train_start": "2026-01-01T00:00:00Z",
                "train_end": "2026-01-25T00:00:00Z",
                "test_start": "2026-01-26T00:00:00Z",
                "test_end": "2026-02-04T00:00:00Z",
                "configuration_reference": "fixture://walk-forward/wf-2",
                "parameters": parameters,
            },
            {
                "window_id": "wf-3",
                "train_start": "2026-01-01T00:00:00Z",
                "train_end": "2026-02-04T00:00:00Z",
                "test_start": "2026-02-05T00:00:00Z",
                "test_end": "2026-02-15T00:00:00Z",
                "configuration_reference": "fixture://walk-forward/wf-3",
                "parameters": parameters,
            },
        ],
        "trades": [
            {
                "sequence": index + 1,
                "external_trade_id": str(index + 1),
                "source_format": "tradingview",
                "strategy": strategy,
                "symbol": selected_symbols[0],
                "direction": "LONG",
                "realized_pl": "-1" if index % 4 == 0 else "2",
                "gross_pl": "-0.9" if index % 4 == 0 else "2.1",
                "fees": "0.1",
                "slippage": "0.02",
                "entry_price": "100",
                "exit_price": "99" if index % 4 == 0 else "102",
                "quantity": "1",
                "market_regime": "TRENDING_UP",
                "entry_at": (
                    (
                        in_sample_start + timedelta(days=index % 45)
                        if index < 50
                        else out_of_sample_start
                        + timedelta(days=(index - 50) % 44)
                    )
                    - timedelta(minutes=15)
                ).isoformat(),
                "closed_at": (
                    in_sample_start + timedelta(days=index % 45)
                    if index < 50
                    else out_of_sample_start + timedelta(days=(index - 50) % 44)
                ).isoformat(),
            }
            for index in range(100)
        ],
        "acceptance_criteria": {
            "min_trades": 100,
            "min_profit_factor": "1.15",
            "max_drawdown": "50",
            "min_out_of_sample_trades": 30,
            "min_out_of_sample_profit_factor": "1.15",
            "min_active_trading_days": 15,
            "max_single_day_trade_share": "0.25",
        },
    }


def register_backtest_protocol(client: TestClient, payload: dict) -> dict:
    protocol_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"protocol_id", "source_format", "csv_format", "csv_text", "trades"}
    }
    response = client.post("/backtests/protocols", json=protocol_payload)
    assert response.status_code == 201, response.text
    protocol = response.json()
    payload["protocol_id"] = protocol["id"]
    return protocol


def post_backtest_with_protocol(client: TestClient, payload: dict) -> object:
    register_backtest_protocol(client, payload)
    if payload.get("source_format") == "tradingview":
        csv_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"source_format", "trades"}
        }
        csv_payload["csv_format"] = "tradingview"
        csv_payload["csv_text"] = tradingview_csv_from_payload(payload)
        response = client.post("/backtests/reports/import-csv", json=csv_payload)
    else:
        response = client.post("/backtests/reports", json=payload)
    if (
        response.status_code == 201
        and response.json().get("result", {}).get("acceptance_passed") is True
        and payload["strategy"] == "trend_pullback_v1"
    ):
        enabled = client.patch(
            f"/strategies/{payload['strategy']}",
            json={"is_enabled": True},
        )
        assert enabled.status_code == 200
    return response


def tradingview_csv_from_payload(payload: dict) -> str:
    rows = [
        "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Net P&L USD,"
        "Commission USD,Symbol"
    ]
    for index, trade in enumerate(payload["trades"], start=1):
        trade_id = trade.get("external_trade_id") or str(index)
        symbol = trade.get("symbol") or payload["symbols"][0]
        rows.append(
            f"{trade_id},Entry long,AUREX-LONG-TRENDING_UP,{trade['entry_at']},"
            f"{trade['entry_price']},{trade['quantity']},,,{symbol}"
        )
        rows.append(
            f"{trade_id},Exit long,AUREX-LONG-EXIT,{trade['closed_at']},"
            f"{trade['exit_price']},{trade['quantity']},{trade['realized_pl']},"
            f"{trade['fees']},{symbol}"
        )
    return "\n".join(rows)


def weak_self_accepted_backtest_payload() -> dict:
    payload = accepted_backtest_payload()
    payload["source_format"] = "aurex_json"
    payload["trades"] = [
        {"realized_pl": "10"},
        {"realized_pl": "-5"},
    ]
    payload["acceptance_criteria"] = {
        "min_trades": 2,
        "min_profit_factor": "1.5",
        "max_drawdown": "5",
        "require_sample_windows": False,
        "require_out_of_sample_metrics": False,
        "require_trade_dates": False,
        "require_market_regime_breakdown": False,
        "require_walk_forward_validation": False,
    }
    return payload


def concentrated_self_accepted_backtest_payload() -> dict:
    payload = accepted_backtest_payload()
    same_day = "2026-02-16T00:00:00+00:00"
    payload["trades"] = [
        {
            **trade,
            "closed_at": same_day,
            "entry_at": "2026-02-15T23:45:00+00:00",
            "market_regime": "TRENDING_UP",
        }
        for trade in payload["trades"]
    ]
    payload["acceptance_criteria"] = {
        **payload["acceptance_criteria"],
        "min_active_trading_days": 1,
        "max_single_day_trade_share": "1",
        "require_walk_forward_validation": False,
    }
    return payload


def clear_paper_evidence_fixture_data(session: Session) -> None:
    session.execute(delete(TradeJournalEntry))
    session.execute(delete(EquityCurvePoint))
    session.execute(delete(PaperTrade))
    session.execute(delete(PaperOrder))
    session.execute(delete(RiskDecision))
    session.execute(delete(Signal))
    session.flush()


def seed_closed_paper_trades(
    session: Session,
    total: int,
    calendar_days: int,
    prefix: str = "paper-evidence",
    create_journals: bool = True,
    profitable_trade_count: int = 70,
    loss_amount: Decimal = Decimal("-1"),
    strategy: str = "trend_pullback_v1",
    symbol: str = "BTCUSDT",
) -> Account:
    now = datetime.now(UTC)
    account = Account(
        name=f"paper-evidence-{prefix}",
        mode="paper",
        currency="USD",
        starting_equity=Decimal("1000"),
        current_equity=Decimal("1070"),
    )
    session.add(account)
    session.flush()

    start = now - timedelta(days=calendar_days - 1)
    for index in range(total):
        day_offset = index % calendar_days
        closed_at = start + timedelta(days=day_offset)
        realized_pl = Decimal("2") if index < profitable_trade_count else loss_amount
        entry_fees = Decimal("0.10")
        entry_slippage = Decimal("0.05")
        exit_fees = Decimal("0.10")
        exit_slippage = Decimal("0.05")
        total_fees = entry_fees + exit_fees
        total_slippage = entry_slippage + exit_slippage
        exit_price = Decimal("100") + realized_pl + total_fees + total_slippage
        signal = Signal(
            source="fixture",
            strategy=strategy,
            symbol=symbol,
            timeframe="15m",
            direction=Direction.LONG,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            market_regime=MarketRegime.TRENDING_UP,
            status=SignalStatus.PAPER_EXECUTED,
            idempotency_key=f"{prefix}-{index}",
            raw_payload={"fixture": True},
            normalized_payload={"fixture": True},
            source_timestamp=closed_at,
            received_at=closed_at,
            processed_at=closed_at,
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
            rules_snapshot={"fixture": True},
        )
        session.add(decision)
        session.flush()
        execution_assumptions = {
            "schema_version": PAPER_EXECUTION_SCHEMA_VERSION,
            "fill_model": DETERMINISTIC_PAPER_FILL_MODEL,
            "lifecycle_status": "CLOSED",
            "price_semantics": "reference_prices_with_costs_recorded_separately",
            "cost_floor_enforced": True,
            "assumptions": {
                "commission_bps": "10",
                "half_spread_bps": "2.5",
                "market_impact_bps": "2.5",
                "latency_ms": 500,
            },
            "entry": {
                "requested_price": "100",
                "filled_price": "100",
                "quantity": "1",
                "fees": str(entry_fees),
                "slippage": str(entry_slippage),
                "filled_at": closed_at.isoformat(),
            },
            "exit": {
                "reference_price": str(exit_price),
                "fees": str(exit_fees),
                "slippage": str(exit_slippage),
                "closed_at": closed_at.isoformat(),
                "cost_source": "modeled_floor",
            },
            "total_fees": str(total_fees),
            "total_slippage": str(total_slippage),
        }
        order = PaperOrder(
            signal=signal,
            risk_decision_id=decision.id,
            symbol=symbol,
            direction=Direction.LONG,
            status=OrderStatus.FILLED,
            requested_price=Decimal("100"),
            filled_price=Decimal("100"),
            quantity=Decimal("1"),
            fees=entry_fees,
            slippage=entry_slippage,
            fill_model=DETERMINISTIC_PAPER_FILL_MODEL,
            execution_assumptions=execution_assumptions,
            execution_assumptions_hash=paper_execution_evidence_hash(
                execution_assumptions
            ),
            created_order_at=now,
            filled_at=closed_at,
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
            market_regime=MarketRegime.TRENDING_UP,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            quantity=Decimal("1"),
            risk_amount=Decimal("5"),
            opened_at=closed_at,
            exit_price=exit_price,
            closed_at=closed_at,
            realized_pl=realized_pl,
            r_multiple=realized_pl / Decimal("5"),
            fees=total_fees,
            slippage=total_slippage,
            close_reason="fixture",
        )
        session.add(trade)
        session.flush()
        if create_journals:
            session.add(
                TradeJournalEntry(
                    paper_trade=trade,
                    author="fixture",
                    thesis="Fixture trade follows the Stage 14 paper evidence setup.",
                    execution_notes="Risk-approved paper trade fixture.",
                    outcome_notes="Closed by deterministic test fixture.",
                    rule_followed=True,
                    emotional_override=False,
                    evidence_snapshot={"fixture": True},
                    journaled_at=closed_at,
                )
            )
    return account
