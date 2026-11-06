from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.db.base import Base
from aurex.db.models import PaperEvidenceImportBatch, PaperTrade
from tests.integration.backtest_helpers import (
    accepted_backtest_payload as accepted_backtest_model,
)
from tests.integration.backtest_helpers import tradingview_csv


def evidence_csv() -> str:
    return "\n".join(
        [
            (
                "external_trade_id,strategy,symbol,timeframe,direction,opened_at,closed_at,"
                "entry_price,exit_price,stop_loss,take_profit,quantity,risk_amount,fees,"
                "slippage,close_reason,journal_author,journal_thesis,rule_followed,"
                "emotional_override,market_regime,realized_pl"
            ),
            (
                "paper-001,trend_pullback_v1,BTCUSDT,15m,LONG,"
                "2026-01-01T10:00:00Z,2026-01-01T11:00:00Z,"
                "100,102,98,104,1,2,0.5,0,target_hit,Adonis,"
                "Trend pullback followed plan,true,false,TRENDING_UP,1.5"
            ),
            (
                "paper-002,trend_pullback_v1,BTCUSDT,15m,SHORT,"
                "2026-01-02T10:00:00Z,2026-01-02T11:00:00Z,"
                "100,98,102,96,1,2,0.25,0,target_hit,Adonis,"
                "Short trend pullback followed plan,true,false,TRENDING_DOWN,1.75"
            ),
        ]
    )


def full_passing_evidence_csv() -> str:
    header = (
        "external_trade_id,strategy,symbol,timeframe,direction,opened_at,closed_at,"
        "entry_price,exit_price,stop_loss,take_profit,quantity,risk_amount,fees,"
        "slippage,close_reason,journal_author,journal_thesis,rule_followed,"
        "emotional_override,market_regime,realized_pl"
    )
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    rows = [header]
    for index in range(100):
        opened_at = start + timedelta(days=index % 30, minutes=index)
        closed_at = opened_at + timedelta(hours=1)
        is_win = index < 70
        exit_price = "102" if is_win else "99"
        realized_pl = "2" if is_win else "-1"
        close_reason = "target_hit" if is_win else "stop_hit"
        rows.append(
            f"paper-full-{index:03d},trend_pullback_v1,BTCUSDT,15m,LONG,"
            f"{opened_at.isoformat()},{closed_at.isoformat()},"
            f"100,{exit_price},98,104,1,2,0,0,{close_reason},Adonis,"
            f"Full window paper trade {index},true,false,TRENDING_UP,{realized_pl}"
        )
    return "\n".join(rows)


def import_payload(csv_text: str) -> dict[str, str]:
    return {
        "source": "paper-platform-demo",
        "source_reference": "export:paper-platform-demo:2026-01",
        "csv_text": csv_text,
    }


def accepted_backtest_payload() -> dict[str, object]:
    payload = accepted_backtest_model()
    request = payload.model_dump(
        mode="json",
        exclude={"source_artifact_hash", "source_format", "trades"},
    )
    request["csv_format"] = "tradingview"
    request["csv_text"] = tradingview_csv(payload)
    return request


def register_backtest_protocol(client: TestClient, payload: dict[str, object]) -> None:
    protocol_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"protocol_id", "source_format", "csv_format", "csv_text", "trades"}
    }
    response = client.post("/backtests/protocols", json=protocol_payload)
    assert response.status_code == 201, response.text
    payload["protocol_id"] = response.json()["id"]


def test_paper_evidence_csv_import_creates_auditable_closed_trades() -> None:
    with test_client() as client:
        response = client.post("/paper/evidence/import-csv", json=import_payload(evidence_csv()))

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "IMPORTED"
        assert body["rows_received"] == 2
        assert body["imported_count"] == 2
        assert body["skipped_count"] == 0
        assert body["rejected_count"] == 0
        assert [row["status"] for row in body["row_results"]] == ["IMPORTED", "IMPORTED"]
        assert body["analysis_summary"]["status_counts"] == {"IMPORTED": 2}
        assert body["analysis_summary"]["ready_or_imported_count"] == 2
        assert body["analysis_summary"]["net_realized_pl"] == "3.25"
        assert body["analysis_summary"]["active_trading_days"] == 2
        assert body["evidence_snapshot"]["analysis_summary"]["symbol_counts"] == {"BTCUSDT": 2}
        assert body["row_results"][0]["evidence_hash"]
        assert body["evidence_snapshot"]["imported_trade_hashes"]
        assert body["evidence_snapshot"]["imported_external_trade_hashes"]["paper-001"] == (
            body["row_results"][0]["evidence_hash"]
        )

        list_response = client.get("/paper/evidence/imports")
        assert list_response.status_code == 200
        batches = list_response.json()
        assert len(batches) == 1
        assert batches[0]["id"] == body["id"]
        assert batches[0]["source_reference"] == "export:paper-platform-demo:2026-01"
        assert batches[0]["analysis_summary"]["direction_counts"] == {"LONG": 1, "SHORT": 1}

        detail_response = client.get(f"/paper/evidence/imports/{body['id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["row_results"][0]["external_trade_id"] == "paper-001"
        assert detail_response.json()["analysis_summary"]["strategy_counts"] == {
            "trend_pullback_v1": 2
        }

        evidence_response = client.post("/live/deployment/paper-evidence/run")

        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert evidence["total_trades"] == 2
        assert evidence["unexplained_trade_count"] == 0
        assert evidence["risk_rule_violation_count"] == 0
        assert evidence["journaled_trade_count"] == 2
        assert evidence["unjournaled_trade_count"] == 0
        assert evidence["journal_rule_violation_count"] == 0
        assert evidence["evidence_snapshot"]["evidence_grade_trade_count"] == 2
        assert evidence["evidence_snapshot"]["non_evidence_grade_trade_count"] == 0
        assert evidence["evidence_snapshot"]["execution_quality_violation_count"] == 0
        assert evidence["evidence_snapshot"]["fill_model_counts"] == {
            "paper_evidence_import": 2
        }
        assert "minimum_paper_trades_not_met" in evidence["reasons"]
        assert "unexplained_trades_present" not in evidence["reasons"]


def test_paper_evidence_report_flags_imported_trade_evidence_drift() -> None:
    with test_client() as client:
        imported = client.post("/paper/evidence/import-csv", json=import_payload(evidence_csv()))
        assert imported.status_code == 200

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade = session.execute(
                select(PaperTrade).where(PaperTrade.symbol == "BTCUSDT").limit(1)
            ).scalar_one()
            trade.realized_pl = Decimal("99")
            session.commit()

        evidence_response = client.post("/live/deployment/paper-evidence/run")

        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert evidence["risk_rule_violation_count"] == 1
        assert "risk_rule_violations_present" in evidence["reasons"]
        violations = evidence["evidence_snapshot"]["risk_rule_violations"]
        assert violations[0]["reason"] == "imported_trade_evidence_payload_mismatch"
        assert violations[0]["external_trade_id"] == "paper-001"
        assert violations[0]["expected_evidence_hash"]
        assert violations[0]["current_evidence_hash"]
        assert violations[0]["expected_evidence_hash"] != violations[0][
            "current_evidence_hash"
        ]


def test_collection_status_surfaces_stale_imported_paper_evidence() -> None:
    with test_client() as client:
        backtest_payload = accepted_backtest_payload()
        register_backtest_protocol(client, backtest_payload)
        backtest = client.post("/backtests/reports/import-csv", json=backtest_payload)
        imported = client.post(
            "/paper/evidence/import-csv",
            json=import_payload(full_passing_evidence_csv()),
        )
        report = client.post("/live/deployment/paper-evidence/run")
        fresh_status = client.get("/paper/evidence/collection-status")

        assert backtest.status_code == 201
        assert imported.status_code == 200
        assert report.status_code == 200
        assert report.json()["status"] == "PASS"
        assert fresh_status.status_code == 200
        assert fresh_status.json()["status"] == "PASS"
        assert fresh_status.json()["paper_evidence_freshness_reasons"] == []

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade = session.execute(
                select(PaperTrade).order_by(PaperTrade.closed_at.asc()).limit(1)
            ).scalar_one()
            trade.realized_pl = Decimal("99")
            session.commit()

        stale_status = client.get("/paper/evidence/collection-status")

        assert stale_status.status_code == 200
        body = stale_status.json()
        assert body["status"] == "BLOCKED"
        assert body["paper_evidence_status"] == "BLOCKED"
        assert "paper_evidence_lineage_changed_since_report" in body[
            "paper_evidence_freshness_reasons"
        ]
        assert "paper_evidence_lineage_changed_since_report" in body["blocking_reasons"]
        assert body["next_actions"][0] == (
            "Resolve paper-evidence ledger drift and rerun the Stage 14 paper-evidence "
            "report before broker reconciliation or live review."
        )


def test_paper_evidence_csv_preflight_validates_without_mutating_ledger() -> None:
    with test_client() as client:
        response = client.post(
            "/paper/evidence/preflight-csv",
            json=import_payload(evidence_csv()),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "READY"
        assert body["rows_received"] == 2
        assert body["importable_count"] == 2
        assert body["skipped_count"] == 0
        assert body["rejected_count"] == 0
        assert [row["status"] for row in body["row_results"]] == ["READY", "READY"]
        assert body["analysis_summary"]["status_counts"] == {"READY": 2}
        assert body["analysis_summary"]["calendar_day_span"] == 2
        assert body["analysis_summary"]["active_trading_days"] == 2
        assert body["analysis_summary"]["net_realized_pl"] == "3.25"
        assert body["analysis_summary"]["symbol_counts"] == {"BTCUSDT": 2}
        assert body["deployment_strategy"] == "trend_pullback_v1"
        assert body["deployment_symbols"] == ["BTCUSDT"]
        assert body["scope_status"] == "IN_SCOPE"
        assert body["scoped_importable_count"] == 2
        assert body["out_of_scope_importable_count"] == 0
        assert body["out_of_scope_import_summary"] == []
        assert body["scope_next_action"] == (
            "CSV importable rows match the current deployment scope."
        )

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade_count = session.execute(select(func.count(PaperTrade.id))).scalar_one()
            batch_count = session.execute(
                select(func.count(PaperEvidenceImportBatch.id))
            ).scalar_one()

        assert trade_count == 0
        assert batch_count == 0


def test_paper_evidence_csv_preflight_warns_for_out_of_scope_export() -> None:
    out_of_scope_csv = evidence_csv().replace("BTCUSDT", "ETHUSDT")

    with test_client() as client:
        response = client.post(
            "/paper/evidence/preflight-csv",
            json=import_payload(out_of_scope_csv),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "READY"
        assert body["scope_status"] == "OUT_OF_SCOPE"
        assert body["scoped_importable_count"] == 0
        assert body["out_of_scope_importable_count"] == 2
        assert body["out_of_scope_import_summary"] == [
            {
                "strategy": "trend_pullback_v1",
                "symbol": "ETHUSDT",
                "count": 2,
            }
        ]
        assert body["scope_next_action"] == (
            "This CSV has no importable rows for trend_pullback_v1 covering BTCUSDT; "
            "use a paper export for the active deployment scope."
        )

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade_count = session.execute(select(func.count(PaperTrade.id))).scalar_one()
            batch_count = session.execute(
                select(func.count(PaperEvidenceImportBatch.id))
            ).scalar_one()

        assert trade_count == 0
        assert batch_count == 0


def test_paper_evidence_csv_preflight_flags_duplicates_and_bad_rows() -> None:
    bad_csv = evidence_csv().replace(
        "paper-002,trend_pullback_v1,BTCUSDT,15m,SHORT",
        "paper-001,trend_pullback_v1,BTCUSDT,15m,SHORT",
    ).replace(
        "100,102,98,104,1,2,0.5,0,target_hit",
        "100,102,98,104,1,1.99,0.5,0,target_hit",
        1,
    )

    with test_client() as client:
        response = client.post(
            "/paper/evidence/preflight-csv",
            json=import_payload(bad_csv),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "REJECTED"
        assert body["importable_count"] == 0
        assert body["rejected_count"] == 2
        reasons = [row["reason"] for row in body["row_results"]]
        assert "risk_amount_does_not_match_entry_stop_and_quantity" in reasons
        assert "duplicate_external_trade_id_in_csv" in reasons
        assert body["analysis_summary"]["rejected_reasons"] == {
            "duplicate_external_trade_id_in_csv": 1,
            "risk_amount_does_not_match_entry_stop_and_quantity": 1,
        }
        assert body["analysis_summary"]["fix_queue"] == [
            {"reason": "duplicate_external_trade_id_in_csv", "count": 1, "rows": [3]},
            {
                "reason": "risk_amount_does_not_match_entry_stop_and_quantity",
                "count": 1,
                "rows": [2],
            },
        ]

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade_count = session.execute(select(func.count(PaperTrade.id))).scalar_one()
            batch_count = session.execute(
                select(func.count(PaperEvidenceImportBatch.id))
            ).scalar_one()

        assert trade_count == 0
        assert batch_count == 0


def test_paper_evidence_collection_status_reports_missing_evidence() -> None:
    with test_client() as client:
        response = client.get("/paper/evidence/collection-status")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "BLOCKED"
        assert body["accepted_backtest_status"] == "BLOCKED"
        assert body["paper_evidence_status"] == "NOT_RUN"
        assert body["imported_batch_count"] == 0
        assert body["imported_count"] == 0
        assert body["scoped_imported_count"] == 0
        assert body["out_of_scope_imported_count"] == 0
        assert body["out_of_scope_import_summary"] == []
        assert body["total_trades"] == 0
        assert body["trades_remaining"] == 100
        assert body["calendar_days_remaining"] == 30
        assert body["active_days_remaining"] == 15
        assert "paper_evidence_import_missing" in body["blocking_reasons"]
        assert "accepted_backtest_missing_or_wrong_scope" in body["blocking_reasons"]
        assert "paper_evidence_report_missing" in body["blocking_reasons"]


def test_paper_evidence_collection_status_tracks_partial_collection() -> None:
    with test_client() as client:
        backtest_payload = accepted_backtest_payload()
        register_backtest_protocol(client, backtest_payload)
        backtest = client.post("/backtests/reports/import-csv", json=backtest_payload)
        imported = client.post("/paper/evidence/import-csv", json=import_payload(evidence_csv()))
        evidence = client.post("/live/deployment/paper-evidence/run")
        response = client.get("/paper/evidence/collection-status")

        assert backtest.status_code == 201
        assert imported.status_code == 200
        assert evidence.status_code == 200
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "BLOCKED"
        assert body["accepted_backtest_status"] == "PASS"
        assert body["paper_evidence_status"] == "BLOCKED"
        assert body["latest_import_batch_id"] == imported.json()["id"]
        assert body["latest_paper_evidence_report_id"] == evidence.json()["id"]
        assert body["imported_batch_count"] == 1
        assert body["rows_received"] == 2
        assert body["imported_count"] == 2
        assert body["scoped_imported_count"] == 2
        assert body["out_of_scope_imported_count"] == 0
        assert body["out_of_scope_import_summary"] == []
        assert body["rejected_count"] == 0
        assert body["total_trades"] == 2
        assert body["in_scope_trade_count"] == 2
        assert body["out_of_scope_trade_count"] == 0
        assert body["trades_remaining"] == 98
        assert body["calendar_days_observed"] == 2
        assert body["active_trading_days"] == 2
        assert body["active_days_remaining"] == 13
        assert "minimum_paper_trades_not_met" in body["blocking_reasons"]
        assert "Collect or import 98 more in-scope closed trades." in body["next_actions"]


def test_paper_evidence_collection_status_blocks_out_of_scope_imports() -> None:
    out_of_scope_csv = evidence_csv().replace("BTCUSDT", "ETHUSDT")

    with test_client() as client:
        imported = client.post(
            "/paper/evidence/import-csv",
            json=import_payload(out_of_scope_csv),
        )
        response = client.get("/paper/evidence/collection-status")

        assert imported.status_code == 200
        assert response.status_code == 200
        body = response.json()
        assert body["imported_batch_count"] == 1
        assert body["imported_count"] == 2
        assert body["scoped_imported_count"] == 0
        assert body["out_of_scope_imported_count"] == 2
        assert body["out_of_scope_import_summary"] == [
            {
                "strategy": "trend_pullback_v1",
                "symbol": "ETHUSDT",
                "count": 2,
            }
        ]
        assert "paper_evidence_import_scope_missing" in body["blocking_reasons"]
        assert body["next_actions"][0] == (
            "Store an accepted backtest for trend_pullback_v1 covering BTCUSDT."
        )
        assert (
            "Import paper-platform evidence for trend_pullback_v1 covering BTCUSDT."
            in body["next_actions"]
        )


def test_duplicate_paper_evidence_import_is_skipped_without_double_counting() -> None:
    with test_client() as client:
        first_response = client.post(
            "/paper/evidence/import-csv",
            json=import_payload(evidence_csv()),
        )
        second_response = client.post(
            "/paper/evidence/import-csv",
            json=import_payload(evidence_csv()),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        body = second_response.json()
        assert body["status"] == "SKIPPED"
        assert body["imported_count"] == 0
        assert body["skipped_count"] == 2
        assert body["rejected_count"] == 0

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade_count = session.execute(select(func.count(PaperTrade.id))).scalar_one()
            batch_count = session.execute(
                select(func.count(PaperEvidenceImportBatch.id))
            ).scalar_one()

        assert trade_count == 2
        assert batch_count == 2


def test_paper_evidence_csv_import_rejects_missing_required_headers() -> None:
    with test_client() as client:
        response = client.post(
            "/paper/evidence/import-csv",
            json=import_payload("external_trade_id,realized_pl\npaper-001,1.25"),
        )

        assert response.status_code == 400
        assert "missing required columns" in response.json()["detail"]

        with next(client.app.dependency_overrides[get_db]()) as session:
            batch_count = session.execute(
                select(func.count(PaperEvidenceImportBatch.id))
            ).scalar_one()
            trade_count = session.execute(select(func.count(PaperTrade.id))).scalar_one()

        assert batch_count == 0
        assert trade_count == 0


def test_paper_evidence_csv_import_rejects_risk_amount_mismatch() -> None:
    bad_csv = evidence_csv().replace(
        "100,102,98,104,1,2,0.5,0,target_hit",
        "100,102,98,104,1,1.99,0.5,0,target_hit",
        1,
    )

    with test_client() as client:
        response = client.post("/paper/evidence/import-csv", json=import_payload(bad_csv))

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "PARTIAL"
        assert body["imported_count"] == 1
        assert body["rejected_count"] == 1
        assert body["row_results"][0]["status"] == "REJECTED"
        assert body["row_results"][0]["reason"] == (
            "risk_amount_does_not_match_entry_stop_and_quantity"
        )

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade_count = session.execute(select(func.count(PaperTrade.id))).scalar_one()

        assert trade_count == 1


def test_paper_evidence_csv_import_rejects_duplicate_external_ids_in_same_csv() -> None:
    duplicate_csv = evidence_csv().replace(
        "paper-002,trend_pullback_v1,BTCUSDT,15m,SHORT",
        "paper-001,trend_pullback_v1,BTCUSDT,15m,SHORT",
    )

    with test_client() as client:
        response = client.post(
            "/paper/evidence/import-csv",
            json=import_payload(duplicate_csv),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "PARTIAL"
        assert body["imported_count"] == 1
        assert body["rejected_count"] == 1
        assert body["row_results"][1]["reason"] == "duplicate_external_trade_id_in_csv"

        with next(client.app.dependency_overrides[get_db]()) as session:
            trade_count = session.execute(select(func.count(PaperTrade.id))).scalar_one()

        assert trade_count == 1


def test_paper_evidence_template_csv_exposes_required_headers() -> None:
    with test_client() as client:
        response = client.get("/paper/evidence/template.csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "external_trade_id,strategy,symbol" in response.text
        assert "rule_followed,emotional_override" in response.text
        assert "paper-001,trend_pullback_v1,BTCUSDT" in response.text


def test_paper_evidence_import_detail_404s_for_unknown_batch() -> None:
    with test_client() as client:
        response = client.get("/paper/evidence/imports/missing-batch")

        assert response.status_code == 404


class test_client:
    def __enter__(self) -> TestClient:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
        )
        self.app = create_app()

        def override_get_db() -> Generator[Session]:
            with self.session_factory() as db_session:
                yield db_session

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)
        return self.client.__enter__()

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.client.__exit__(exc_type, exc_value, traceback)
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
