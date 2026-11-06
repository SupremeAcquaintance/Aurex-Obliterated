from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.schemas import TRADINGVIEW_PAIRED_EXPORT_ATTESTATION
from aurex.db.base import Base
from aurex.db.models import BacktestDatasetCandle, BacktestParityRun


def client_with_session() -> tuple[TestClient, sessionmaker[Session]]:
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
    return TestClient(app), session_factory


def replay_rows() -> list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    closes = [Decimal(value) for value in range(100, 108)]
    rows = [
        (
            start + timedelta(minutes=15 * index),
            close - Decimal("0.3"),
            close + Decimal("0.2"),
            close - Decimal("0.5"),
            close,
        )
        for index, close in enumerate(closes)
    ]
    rows.extend(
        [
            (
                start + timedelta(hours=2),
                Decimal("105.5"),
                Decimal("105.7"),
                Decimal("103.8"),
                Decimal("104"),
            ),
            (
                start + timedelta(hours=2, minutes=15),
                Decimal("104.2"),
                Decimal("106.3"),
                Decimal("104"),
                Decimal("106.1"),
            ),
            (
                start + timedelta(hours=2, minutes=30),
                Decimal("106.2"),
                Decimal("109"),
                Decimal("106"),
                Decimal("108.5"),
            ),
            (
                start + timedelta(hours=2, minutes=45),
                Decimal("108.5"),
                Decimal("109"),
                Decimal("108"),
                Decimal("108.8"),
            ),
            (
                start + timedelta(hours=3),
                Decimal("108.8"),
                Decimal("109"),
                Decimal("108.4"),
                Decimal("108.7"),
            ),
        ]
    )
    return rows


def dataset_csv() -> str:
    rows = ["timestamp,open,high,low,close,volume"]
    rows.extend(
        ",".join(
            [
                timestamp.isoformat().replace("+00:00", "Z"),
                str(open_price),
                str(high),
                str(low),
                str(close),
                "10",
            ]
        )
        for timestamp, open_price, high, low, close in replay_rows()
    )
    return "\n".join(rows)


def dataset_csv_with_changed_close() -> str:
    rows = dataset_csv().splitlines()
    changed = rows[-1].split(",")
    changed[4] = "108.6"
    rows[-1] = ",".join(changed)
    return "\n".join(rows)


def parameters() -> dict:
    return {
        "initial_capital": "1000",
        "backtest_start": "2026-01-01T02:00:00Z",
        "backtest_end": "2026-01-01T02:45:00Z",
        "higher_timeframe": "60",
        "pullback_ema_fast": 2,
        "pullback_ema_slow": 3,
        "trend_ema": 3,
        "htf_ema_fast": 1,
        "htf_ema_slow": 2,
        "rsi_length": 2,
        "atr_length": 2,
        "atr_multiplier": "1",
        "reward_risk": "1",
        "swing_lookback": 2,
        "pullback_atr_tolerance": "1",
        "stop_mode": "ATR",
        "risk_per_trade_percent": "0.5",
        "max_position_value_percent": "95",
        "enable_long": True,
        "enable_short": True,
    }


def prepare_evidence(
    client: TestClient,
    *,
    mutate_trade: dict | None = None,
    omit_field: str | None = None,
    extra_trade: bool = False,
    include_chart_dataset: bool = True,
    chart_csv_text: str | None = None,
    chart_source: str = "tradingview-chart-export",
    chart_source_reference: str = (
        "tradingview://chart/BINANCE:BTCUSDT/15m"
    ),
    bind_protocol: bool = True,
    report_data_start: str = "2026-01-01T00:00:00Z",
) -> tuple[str, str, dict]:
    dataset = client.post(
        "/backtests/ohlcv/import-csv",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "source": "binance-vision",
            "source_reference": (
                "binance-public-data://spot/monthly/klines/BTCUSDT/15m"
            ),
            "csv_timezone": "UTC",
            "continuity": "continuous_24_7",
            "source_artifacts": [
                {
                    "uri": "https://data.binance.vision/parity-fixture.zip",
                    "filename": "parity-fixture.zip",
                    "sha256": "a" * 64,
                    "size_bytes": 1024,
                    "checksum_uri": (
                        "https://data.binance.vision/parity-fixture.zip.CHECKSUM"
                    ),
                    "checksum_file_sha256": "b" * 64,
                    "expected_sha256": "a" * 64,
                    "archive_member": "parity-fixture.csv",
                    "checksum_verified": True,
                }
            ],
            "transformation": {
                "tool": "aurex.backtest_engine.binance_vision",
                "version": "1.0.0",
                "input_format": "binance_spot_kline_csv",
                "timestamp_unit": "microseconds",
                "output_schema": "aurex_ohlcv_v1",
            },
            "csv_text": dataset_csv(),
        },
    )
    assert dataset.status_code == 201, dataset.text
    dataset_id = dataset.json()["id"]
    tradingview_chart_dataset_id = None
    if include_chart_dataset:
        chart_dataset = client.post(
            "/backtests/ohlcv/import-csv",
            json={
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "source": chart_source,
                "source_reference": chart_source_reference,
                "csv_timezone": "UTC",
                "continuity": "continuous_24_7",
                "csv_text": chart_csv_text or dataset_csv(),
            },
        )
        assert chart_dataset.status_code == 201, chart_dataset.text
        tradingview_chart_dataset_id = chart_dataset.json()["id"]
    replay = client.post(
        "/backtests/reference-replay/preflight",
        json={
            "dataset_id": dataset_id,
            "strategy": "trend_pullback_v1",
            "strategy_version": "1.3.0",
            "parameters": parameters(),
            "tick_size": "0.1",
            "point_value": "1",
            "minimum_contract": "0.001",
            "commission_percent": "0.05",
            "slippage_ticks": 2,
            "intrabar_policy": "stop_first",
        },
    )
    assert replay.status_code == 200, replay.text
    replay_body = replay.json()
    assert replay_body["status"] == "READY"
    trade = dict(replay_body["trades"][0])
    trade.pop("signal_price")
    trade.pop("stop_loss")
    trade.pop("take_profit")
    trade.pop("exit_reason")
    trade.pop("intrabar_ambiguous")
    trade["source_format"] = "tradingview"
    trade["strategy"] = "trend_pullback_v1"
    trade["symbol"] = "BTCUSDT"
    trade["external_trade_id"] = "1"
    if mutate_trade:
        trade.update(mutate_trade)
    if omit_field:
        trade.pop(omit_field)
    trades = [trade]
    if extra_trade:
        extra = dict(trade)
        extra["sequence"] = 2
        extra["external_trade_id"] = "2"
        extra["entry_at"] = "2026-01-01T02:45:00Z"
        extra["closed_at"] = "2026-01-01T03:00:00Z"
        trades.append(extra)

    csv_rows = [
        "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Net P&L USD,"
        "Commission USD,Symbol"
    ]
    for csv_trade in trades:
        trade_id = csv_trade["external_trade_id"]
        csv_rows.append(
            f"{trade_id},Entry long,AUREX-LONG-TRENDING_UP,"
            f"{csv_trade['entry_at']},{csv_trade['entry_price']},"
            f"{csv_trade['quantity']},,,BTCUSDT"
        )
        csv_rows.append(
            f"{trade_id},Exit long,AUREX-LONG-EXIT,{csv_trade['closed_at']},"
            f"{csv_trade['exit_price']},{csv_trade['quantity']},"
            f"{csv_trade['realized_pl']},{csv_trade.get('fees', '')},BTCUSDT"
        )
    report_payload = {
        "strategy": "trend_pullback_v1",
        "strategy_version": "1.3.0",
        "symbols": ["BTCUSDT"],
        "timeframe": "15m",
        "data_source": "tradingview-export",
        "csv_format": "tradingview",
        "csv_timezone": "UTC",
        "source_reference": (
            "tradingview://strategy-tester/BINANCE:BTCUSDT/15m"
        ),
        "data_start": report_data_start,
        "data_end": "2026-01-01T03:00:00Z",
        "in_sample_start": report_data_start,
        "in_sample_end": "2026-01-01T01:30:00Z",
        "out_of_sample_start": "2026-01-01T01:45:00Z",
        "out_of_sample_end": "2026-01-01T03:00:00Z",
        "parameters": parameters(),
        "cost_model": {"commission_percent": "0.05"},
        "slippage_model": {"type": "fixed_ticks", "ticks": "2"},
        "risk_snapshot": {"risk_per_trade": "0.005"},
        "acceptance_criteria": {
            "require_walk_forward_validation": False,
            "require_market_regime_breakdown": False,
        },
        "csv_text": "\n".join(csv_rows),
    }
    protocol_payload = {
        key: value
        for key, value in report_payload.items()
        if key not in {"csv_format", "csv_text"}
    }
    if bind_protocol:
        protocol = client.post("/backtests/protocols", json=protocol_payload)
        assert protocol.status_code == 201, protocol.text
        report_payload["protocol_id"] = protocol.json()["id"]
    report = client.post(
        "/backtests/reports/import-csv",
        json=report_payload,
    )
    assert report.status_code == 201, report.text
    request = {
        "dataset_id": dataset_id,
        "tradingview_chart_dataset_id": tradingview_chart_dataset_id,
        "tradingview_run_id": report.json()["id"],
        "tick_size": "0.1",
        "point_value": "1",
        "minimum_contract": "0.001",
        "tolerances": {
            "entry_time_seconds": 0,
            "exit_time_seconds": 0,
            "price_ticks": 1,
            "quantity_relative": "0.000001",
            "money_absolute": "0.01",
        },
    }
    if tradingview_chart_dataset_id is not None:
        export_attestation = {
            "statement": TRADINGVIEW_PAIRED_EXPORT_ATTESTATION,
            "attested_at": datetime.now(UTC).isoformat(),
        }
        export_manifest = client.post(
            "/backtests/parity/export-manifest/preflight",
            json={
                "dataset_id": dataset_id,
                "tradingview_chart_dataset_id": tradingview_chart_dataset_id,
                "tradingview_run_id": report.json()["id"],
                "export_attestation": export_attestation,
            },
        )
        assert export_manifest.status_code == 200, export_manifest.text
        request["export_attestation"] = export_attestation
        if export_manifest.json()["manifest_hash"]:
            request["reviewed_export_manifest_hash"] = export_manifest.json()[
                "manifest_hash"
            ]
    return dataset_id, report.json()["id"], request


def test_parity_preflight_passes_without_writing_and_is_deterministic() -> None:
    client, session_factory = client_with_session()
    with client:
        _, _, request = prepare_evidence(client)
        first = client.post("/backtests/parity/preflight", json=request)
        second = client.post("/backtests/parity/preflight", json=request)

        assert first.status_code == 200, first.text
        body = first.json()
        assert body["status"] == "PASSED"
        assert body["comparison_only"] is True
        assert body["acceptance_eligible"] is False
        assert body["mutates_ledger"] is False
        assert body["summary"]["matched_trade_count"] == 1
        assert body["summary"]["match_rate"] == "1"
        assert body["mismatches"] == []
        assert body["market_data_summary"]["exact_ohlcv_match"] is True
        assert body["market_data_summary"]["matched_candle_count"] == len(
            replay_rows()
        )
        assert body["market_data_mismatches"] == []
        assert body["tradingview_chart_dataset_id"] == request[
            "tradingview_chart_dataset_id"
        ]
        assert body["parity_evidence_hash"] == second.json()["parity_evidence_hash"]
        with session_factory() as session:
            assert session.execute(select(BacktestParityRun)).scalars().all() == []


def test_paired_export_manifest_binds_protocol_package_and_both_exports() -> None:
    client, session_factory = client_with_session()
    with client:
        _, _, request = prepare_evidence(client)

        response = client.post("/backtests/parity/preflight", json=request)

        assert response.status_code == 200, response.text
        lineage = response.json()["request_snapshot"]["tradingview_export_lineage"]
        manifest = lineage["manifest"]
        assert lineage["status"] == "READY"
        assert lineage["manifest_hash"] == request["reviewed_export_manifest_hash"]
        assert len(manifest["frozen_run"]["protocol_hash"]) == 64
        assert len(manifest["frozen_run"]["manifest_hash"]) == 64
        assert len(manifest["frozen_run"]["package_hash"]) == 64
        assert len(manifest["frozen_run"]["pine_source_sha256"]) == 64
        assert len(
            manifest["tradingview_chart_export"]["canonical_csv_sha256"]
        ) == 64
        assert len(
            manifest["tradingview_report_export"]["source_artifact_hash"]
        ) == 64
        assert "checked_at" not in lineage
        assert any("operator-attested" in warning for warning in lineage["warnings"])
        with session_factory() as session:
            assert session.execute(select(BacktestParityRun)).scalars().all() == []


def test_paired_export_manifest_allows_verified_warmup_before_report_window() -> None:
    client, _ = client_with_session()
    with client:
        _, _, request = prepare_evidence(
            client,
            report_data_start="2026-01-01T00:15:00Z",
        )

        response = client.post("/backtests/parity/preflight", json=request)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "PASSED"
        report_lineage = response.json()["request_snapshot"][
            "tradingview_export_lineage"
        ]["manifest"]["tradingview_report_export"]
        assert report_lineage["data_start"] == "2026-01-01T00:15:00+00:00"


def test_parity_blocks_missing_or_unreviewed_export_lineage() -> None:
    client, _ = client_with_session()
    with client:
        _, _, request = prepare_evidence(client)
        request.pop("reviewed_export_manifest_hash")

        missing = client.post("/backtests/parity/preflight", json=request)
        request["reviewed_export_manifest_hash"] = "0" * 64
        mismatched = client.post("/backtests/parity/preflight", json=request)

        assert missing.status_code == 200, missing.text
        assert missing.json()["status"] == "BLOCKED"
        assert (
            "reviewed_tradingview_export_manifest_hash_required"
            in missing.json()["reasons"]
        )
        assert mismatched.status_code == 200, mismatched.text
        assert mismatched.json()["status"] == "BLOCKED"
        assert (
            "reviewed_tradingview_export_manifest_hash_mismatch"
            in mismatched.json()["reasons"]
        )


def test_parity_cannot_pass_without_frozen_protocol_lineage() -> None:
    client, _ = client_with_session()
    with client:
        _, _, request = prepare_evidence(client, bind_protocol=False)

        response = client.post("/backtests/parity/preflight", json=request)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "BLOCKED"
        assert (
            "tradingview_export_manifest_report_frozen_protocol_missing"
            in response.json()["reasons"]
        )


def test_parity_blocks_without_tradingview_chart_dataset() -> None:
    client, session_factory = client_with_session()
    with client:
        _, _, request = prepare_evidence(
            client,
            include_chart_dataset=False,
        )

        preflight = client.post("/backtests/parity/preflight", json=request)
        record = client.post("/backtests/parity/runs", json=request)

        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["status"] == "BLOCKED"
        assert "tradingview_chart_dataset_required" in preflight.json()["reasons"]
        assert preflight.json()["parity_evidence_hash"] is None
        assert record.status_code == 400
        with session_factory() as session:
            assert session.execute(select(BacktestParityRun)).scalars().all() == []


def test_parity_blocks_wrong_tradingview_chart_source_identity() -> None:
    client, _ = client_with_session()
    with client:
        _, _, request = prepare_evidence(
            client,
            chart_source="manual-export",
            chart_source_reference="fixture://unqualified-chart",
        )

        response = client.post("/backtests/parity/preflight", json=request)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "BLOCKED"
        assert "tradingview_chart_dataset_source_invalid" in response.json()["reasons"]
        assert "tradingview_chart_source_reference_mismatch" in response.json()["reasons"]


def test_market_data_mismatch_is_frozen_before_trade_comparison() -> None:
    client, _ = client_with_session()
    with client:
        _, _, request = prepare_evidence(
            client,
            chart_csv_text=dataset_csv_with_changed_close(),
        )

        preflight = client.post("/backtests/parity/preflight", json=request)
        record = client.post("/backtests/parity/runs", json=request)

        assert preflight.status_code == 200, preflight.text
        body = preflight.json()
        assert body["status"] == "FAILED"
        assert body["summary"]["aligned_trade_count"] == 0
        assert body["mismatches"] == []
        assert body["market_data_summary"]["exact_ohlcv_match"] is False
        assert body["market_data_summary"]["mismatched_candle_count"] == 1
        assert body["market_data_summary"]["field_mismatch_counts"] == {
            "close_mismatch": 1
        }
        assert body["market_data_mismatches"][0]["status"] == "VALUE_MISMATCH"
        assert body["market_data_mismatches"][0]["reasons"] == ["close_mismatch"]
        assert body["reasons"] == [
            "market_data_parity_mismatches",
            "trade_level_comparison_not_run_due_to_market_data_mismatch",
        ]
        assert body["parity_evidence_hash"] is not None
        assert record.status_code == 201, record.text
        assert record.json()["status"] == "FAILED"


def test_parity_audit_detects_chart_dataset_tampering() -> None:
    client, session_factory = client_with_session()
    with client:
        _, _, request = prepare_evidence(client)
        record = client.post("/backtests/parity/runs", json=request)
        assert record.status_code == 201, record.text

        with session_factory() as session:
            candle = session.execute(
                select(BacktestDatasetCandle).where(
                    BacktestDatasetCandle.dataset_id
                    == request["tradingview_chart_dataset_id"]
                )
            ).scalars().first()
            assert candle is not None
            candle.close = "999"
            session.commit()

        audit = client.get(f"/backtests/parity/runs/{record.json()['id']}/audit")

        assert audit.status_code == 200, audit.text
        assert audit.json()["status"] == "BLOCKED"
        assert "parity_source_recheck_blocked" in audit.json()["reasons"]
        assert any(
            "tradingview_chart_dataset_dataset_evidence_hash_mismatch" in reason
            for reason in audit.json()["reasons"]
        )


def test_failed_parity_records_exact_field_mismatch() -> None:
    client, _ = client_with_session()
    with client:
        _, _, request = prepare_evidence(
            client,
            mutate_trade={"realized_pl": "999"},
        )
        response = client.post("/backtests/parity/preflight", json=request)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["summary"]["mismatched_trade_count"] == 1
        assert body["summary"]["field_mismatch_counts"]["realized_pl_mismatch"] == 1
        assert "realized_pl_mismatch" in body["mismatches"][0]["reasons"]


def test_parity_alignment_isolates_reference_only_trade() -> None:
    client, _ = client_with_session()
    with client:
        _, _, request = prepare_evidence(client, extra_trade=True)
        response = client.post("/backtests/parity/preflight", json=request)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["summary"]["matched_trade_count"] == 1
        assert body["summary"]["reference_only_count"] == 1
        assert body["summary"]["mismatched_trade_count"] == 0
        assert body["mismatches"][0]["status"] == "REFERENCE_ONLY"


def test_parity_blocks_when_tradingview_fields_are_incomplete() -> None:
    client, session_factory = client_with_session()
    with client:
        _, _, request = prepare_evidence(client, omit_field="fees")
        preflight = client.post("/backtests/parity/preflight", json=request)
        record = client.post("/backtests/parity/runs", json=request)

        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["status"] == "BLOCKED"
        assert "tradingview_comparison_fields_missing" in preflight.json()["reasons"]
        assert record.status_code == 400
        with session_factory() as session:
            assert session.execute(select(BacktestParityRun)).scalars().all() == []


def test_parity_record_is_idempotent_and_auditable() -> None:
    client, session_factory = client_with_session()
    with client:
        _, _, request = prepare_evidence(client)
        first = client.post("/backtests/parity/runs", json=request)
        second = client.post("/backtests/parity/runs", json=request)

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["id"] == second.json()["id"]
        assert first.json()["immutable"] is True
        assert first.json()["mutates_ledger"] is True
        assert first.json()["reused_existing"] is False
        assert second.json()["reused_existing"] is True
        audit = client.get(f"/backtests/parity/runs/{first.json()['id']}/audit")
        assert audit.status_code == 200, audit.text
        assert audit.json()["status"] == "PASS"
        assert audit.json()["evidence_hash_matches"] is True
        assert audit.json()["replay_matches"] is True
        assert len(client.get("/backtests/parity/runs").json()) == 1

        with session_factory() as session:
            record = session.get(BacktestParityRun, first.json()["id"])
            assert record is not None
            record.summary_snapshot = {**record.summary_snapshot, "matched_trade_count": 99}
            session.commit()
        tampered = client.get(f"/backtests/parity/runs/{first.json()['id']}/audit")
        assert tampered.json()["status"] == "BLOCKED"
        assert "parity_record_evidence_hash_mismatch" in tampered.json()["reasons"]
