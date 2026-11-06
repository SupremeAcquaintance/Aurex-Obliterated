from collections.abc import Generator
from copy import deepcopy
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.schemas import BacktestReportCreate
from aurex.db.base import Base
from aurex.db.models import BacktestRun
from tests.integration.backtest_helpers import (
    accepted_backtest_payload,
    post_accepted_backtest,
    tradingview_csv,
)

pytestmark = pytest.mark.usefixtures("active_trend_pipeline")


def client_fixture() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def register_protocol(client: TestClient, payload: BacktestReportCreate) -> None:
    protocol_payload = payload.model_dump(
        mode="json",
        exclude={"protocol_id", "source_format", "trades"},
    )
    response = client.post("/backtests/protocols", json=protocol_payload)
    assert response.status_code == 201, response.text
    payload.protocol_id = response.json()["id"]


def import_tradingview_payload(
    client: TestClient,
    payload: BacktestReportCreate,
    *,
    csv_text: str | None = None,
) -> dict:
    register_protocol(client, payload)
    request = payload.model_dump(
        mode="json",
        exclude={"source_format", "trades"},
    )
    request["csv_format"] = "tradingview"
    request["csv_text"] = csv_text or tradingview_csv(payload)
    response = client.post("/backtests/reports/import-csv", json=request)
    assert response.status_code == 201, response.text
    return response.json()


def test_valid_tradingview_import_is_paper_eligible() -> None:
    client = client_fixture()
    with client:
        report = post_accepted_backtest(client)
        eligibility = client.get("/backtests/paper-eligibility").json()

        assert report["source_format"] == "tradingview"
        assert eligibility["approved"] is True
        assert eligibility["backtest_run_id"] == report["id"]
        source = eligibility["evidence_snapshot"]["source_evidence"]
        assert source["trusted"] is True
        assert source["policy"] == "core_pine_tradingview_export_v2"
        assert source["actual_strategy_version"] == "1.3.0"
        assert source["expected_strategy_version"] == "1.3.0"
        assert source["recorded_strategy_source_evidence"]["ready"] is True
        assert source["current_strategy_source_evidence"]["ready"] is True
        expected_artifact_hash = sha256(
            tradingview_csv(accepted_backtest_payload()).encode("utf-8")
        ).hexdigest()
        assert source["source_artifact_hash"] == expected_artifact_hash
        assert source["trust_basis"] == (
            "parsed_tradingview_csv_schema_and_bound_sha256"
        )
        assert source["authenticity_limitation"] == (
            "operator_supplied_export_not_cryptographically_attested_by_tradingview"
        )
        assert source["missing_trade_field_counts"] == {
            "external_trade_id": 0,
            "direction": 0,
            "entry_at": 0,
            "closed_at": 0,
            "entry_price": 0,
            "exit_price": 0,
            "quantity": 0,
            "fees": 0,
        }


def test_json_report_cannot_claim_tradingview_origin() -> None:
    client = client_fixture()
    with client:
        payload = accepted_backtest_payload()
        response = client.post(
            "/backtests/reports",
            json=payload.model_dump(mode="json"),
        )

        assert response.status_code == 400
        assert "must use /backtests/reports/import-csv" in response.json()["detail"]
        assert client.get("/backtests/reports").json() == []


def test_metric_accepted_json_report_cannot_unlock_paper_or_signals() -> None:
    client = client_fixture()
    with client:
        payload = accepted_backtest_payload()
        payload.source_format = "aurex_json"
        register_protocol(client, payload)
        imported = client.post(
            "/backtests/reports",
            json=payload.model_dump(mode="json"),
        )
        eligibility = client.get("/backtests/paper-eligibility").json()
        signal_contract = client.get(
            "/signals/contract?strategy=trend_pullback_v1&symbol=BTCUSDT"
        ).json()

        assert imported.status_code == 201, imported.text
        assert imported.json()["result"]["acceptance_passed"] is True
        assert eligibility["approved"] is False
        assert eligibility["reason"] == "accepted_backtest_source_format_not_tradingview"
        assert eligibility["evidence_snapshot"]["source_evidence"]["trusted"] is False
        assert signal_contract["ready_for_paper"] is False
        assert signal_contract["reason"] == eligibility["reason"]


def test_tradingview_import_missing_fees_cannot_unlock_paper() -> None:
    client = client_fixture()
    with client:
        payload = accepted_backtest_payload()
        csv_text = tradingview_csv(payload)
        rows = csv_text.splitlines()
        without_fees = [rows[0]]
        for row in rows[1:]:
            parts = row.split(",")
            if parts[1] == "Exit long":
                parts[7] = ""
            without_fees.append(",".join(parts))
        report = import_tradingview_payload(
            client,
            payload,
            csv_text="\n".join(without_fees),
        )
        eligibility = client.get("/backtests/paper-eligibility").json()

        assert report["result"]["acceptance_passed"] is True
        assert eligibility["approved"] is False
        assert "accepted_backtest_required_trade_fields_missing" in (
            eligibility["evidence_snapshot"]["reasons"]
        )
        assert eligibility["evidence_snapshot"]["source_evidence"][
            "missing_trade_field_counts"
        ]["fees"] == 100


def test_execution_assumption_drift_blocks_paper_and_live_readiness() -> None:
    client = client_fixture()
    with client:
        payload = accepted_backtest_payload()
        payload.cost_model = {"commission_percent": "0.10"}
        payload.slippage_model = {"type": "fixed_ticks", "ticks": "4"}
        report = import_tradingview_payload(client, payload)
        eligibility = client.get("/backtests/paper-eligibility").json()
        deployment = client.get("/live/deployment").json()
        gates = {gate["gate_key"]: gate for gate in deployment["gates"]}
        backtest_gate = gates["accepted_backtest_complete"]

        assert report["result"]["acceptance_passed"] is True
        assert eligibility["approved"] is False
        reasons = eligibility["evidence_snapshot"]["reasons"]
        assert "accepted_backtest_cost_model_mismatch" in reasons
        assert "accepted_backtest_slippage_model_mismatch" in reasons
        assert backtest_gate["status"] == "BLOCKED"
        live_reasons = backtest_gate["evidence_snapshot"]["live_readiness_reasons"]
        assert "accepted_backtest_cost_model_mismatch" in live_reasons
        assert "accepted_backtest_slippage_model_mismatch" in live_reasons
        assert backtest_gate["evidence_snapshot"]["source_evidence"]["trusted"] is False


def test_corrupted_source_artifact_hash_blocks_promotion() -> None:
    client = client_fixture()
    with client:
        report = post_accepted_backtest(client)
        override = client.app.dependency_overrides[get_db]
        session_generator = override()
        session = next(session_generator)
        try:
            run = session.get(BacktestRun, report["id"])
            assert run is not None
            run.source_artifact_hash = "not-a-sha256"
            session.commit()
        finally:
            session_generator.close()

        eligibility = client.get("/backtests/paper-eligibility").json()

        assert eligibility["approved"] is False
        assert "accepted_backtest_source_artifact_hash_invalid" in (
            eligibility["evidence_snapshot"]["reasons"]
        )
        assert eligibility["evidence_snapshot"]["source_evidence"]["trusted"] is False


def test_recorded_pine_source_hash_drift_blocks_promotion() -> None:
    client = client_fixture()
    with client:
        report = post_accepted_backtest(client)
        override = client.app.dependency_overrides[get_db]
        session_generator = override()
        session = next(session_generator)
        try:
            run = session.get(BacktestRun, report["id"])
            assert run is not None
            assert run.protocol is not None
            snapshot = deepcopy(run.protocol.protocol_snapshot)
            snapshot["strategy_source_evidence"]["pine_source_sha256"] = "0" * 64
            run.protocol.protocol_snapshot = snapshot
            session.commit()
        finally:
            session_generator.close()

        eligibility = client.get("/backtests/paper-eligibility").json()

        assert eligibility["approved"] is False
        assert "accepted_backtest_pine_source_hash_mismatch" in (
            eligibility["evidence_snapshot"]["reasons"]
        )
        source = eligibility["evidence_snapshot"]["source_evidence"]
        assert source["trusted"] is False
        assert source["recorded_strategy_source_evidence"][
            "pine_source_sha256"
        ] == "0" * 64
