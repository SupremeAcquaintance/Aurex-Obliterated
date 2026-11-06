from collections.abc import Generator
from copy import deepcopy
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.db.base import Base
from aurex.db.models import BacktestDataset, BacktestDatasetCandle


def dataset_csv(*, descending: bool = False, gap: bool = False) -> str:
    rows = [
        "2026-01-01T00:00:00Z,100,102,99,101,10",
        "2026-01-01T00:15:00Z,101,103,100,102,11",
        "2026-01-01T00:30:00Z,102,104,101,103,12",
    ]
    if gap:
        rows.pop(1)
    if descending:
        rows.reverse()
    return "time,Open,High,Low,Close,Volume\n" + "\n".join(rows)


def dataset_payload(
    csv_text: str | None = None,
    *,
    continuity: str = "continuous_24_7",
) -> dict:
    return {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "source": "fixture",
        "source_reference": "fixture://btc/15m/2026-01-01",
        "csv_timezone": "UTC",
        "continuity": continuity,
        "csv_text": csv_text or dataset_csv(),
    }


def verified_source_artifact(*, archive_hash: str = "a" * 64) -> dict:
    return {
        "uri": "https://data.binance.vision/example.zip",
        "filename": "example.zip",
        "sha256": archive_hash,
        "size_bytes": 1234,
        "checksum_uri": "https://data.binance.vision/example.zip.CHECKSUM",
        "checksum_file_sha256": "b" * 64,
        "expected_sha256": archive_hash,
        "archive_member": "example.csv",
        "checksum_verified": True,
    }


def binance_dataset_payload(*, archive_hash: str = "a" * 64) -> dict:
    payload = dataset_payload()
    payload.update(
        {
            "source": "binance-vision",
            "source_reference": "binance-public-data://spot/monthly/klines/BTCUSDT/15m",
            "source_artifacts": [verified_source_artifact(archive_hash=archive_hash)],
            "transformation": {
                "tool": "aurex.backtest_engine.binance_vision",
                "version": "1.0.0",
                "input_format": "binance_spot_kline_csv",
                "timestamp_unit": "microseconds",
                "output_schema": "aurex_ohlcv_v1",
            },
        }
    )
    return payload


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
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), session_factory


def test_ohlcv_preflight_is_no_write_and_canonicalizes_descending_rows() -> None:
    client, _ = client_with_session()
    with client:
        ascending = client.post("/backtests/ohlcv/preflight-csv", json=dataset_payload())
        descending = client.post(
            "/backtests/ohlcv/preflight-csv",
            json=dataset_payload(dataset_csv(descending=True)),
        )

        assert ascending.status_code == 200, ascending.text
        assert descending.status_code == 200, descending.text
        assert ascending.json()["status"] == "READY"
        assert ascending.json()["canonical_order"] == "ASCENDING"
        assert descending.json()["status"] == "READY"
        assert descending.json()["canonical_order"] == "DESCENDING_REVERSED"
        assert descending.json()["evidence_hash"] == ascending.json()["evidence_hash"]
        assert descending.json()["mutates_ledger"] is False
        assert client.get("/backtests/ohlcv/datasets").json() == []


def test_ohlcv_import_persists_exact_rows_and_is_idempotent() -> None:
    client, session_factory = client_with_session()
    with client:
        first = client.post("/backtests/ohlcv/import-csv", json=dataset_payload())
        second = client.post("/backtests/ohlcv/import-csv", json=dataset_payload())

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert second.json()["id"] == first.json()["id"]
        assert first.json()["reused_existing"] is False
        assert second.json()["reused_existing"] is True
        assert first.json()["row_count"] == 3
        assert first.json()["immutable"] is True

        datasets = client.get("/backtests/ohlcv/datasets").json()
        assert len(datasets) == 1
        audit = client.get(
            f"/backtests/ohlcv/datasets/{first.json()['id']}/audit"
        ).json()
        assert audit["status"] == "PASS"
        assert audit["evidence_hash_matches"] is True
        assert audit["row_count_matches"] is True

        with session_factory() as session:
            dataset = session.get(BacktestDataset, first.json()["id"])
            assert dataset is not None
            candles = list(
                session.execute(
                    select(BacktestDatasetCandle)
                    .where(BacktestDatasetCandle.dataset_id == dataset.id)
                    .order_by(BacktestDatasetCandle.sequence)
                ).scalars()
            )
            assert [candle.close for candle in candles] == ["101", "102", "103"]


def test_binance_vision_dataset_requires_and_binds_verified_source_artifacts() -> None:
    client, _ = client_with_session()
    missing_evidence = dataset_payload()
    missing_evidence["source"] = "binance-vision"

    with client:
        rejected = client.post("/backtests/ohlcv/preflight-csv", json=missing_evidence)
        first = client.post(
            "/backtests/ohlcv/preflight-csv",
            json=binance_dataset_payload(),
        )
        changed_artifact = client.post(
            "/backtests/ohlcv/preflight-csv",
            json=binance_dataset_payload(archive_hash="c" * 64),
        )

    assert rejected.status_code == 422
    assert "require source artifact evidence" in rejected.text
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "READY"
    assert body["source_artifacts_verified"] is True
    assert len(body["canonical_csv_sha256"]) == 64
    assert len(body["source_artifact_bundle_hash"]) == 64
    assert body["quality_snapshot"]["source_artifacts"][0]["checksum_verified"] is True
    assert "timestamp_units" not in body["quality_snapshot"]["source_artifacts"][0]
    assert body["quality_snapshot"]["transformation"]["timestamp_unit"] == "microseconds"
    assert "timestamp_units" not in body["quality_snapshot"]["transformation"]
    assert changed_artifact.json()["evidence_hash"] != body["evidence_hash"]


def test_verified_source_artifact_rejects_checksum_mismatch() -> None:
    client, _ = client_with_session()
    payload = binance_dataset_payload()
    payload["source_artifacts"][0]["expected_sha256"] = "d" * 64

    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

    assert response.status_code == 422
    assert "checksum must match" in response.text


def test_binance_vision_dataset_accepts_explicit_mixed_timestamp_provenance() -> None:
    client, _ = client_with_session()
    payload = binance_dataset_payload()
    payload["source_artifacts"][0]["timestamp_units"] = ["milliseconds"]
    payload["transformation"]["timestamp_unit"] = "mixed"
    payload["transformation"]["timestamp_units"] = [
        "microseconds",
        "milliseconds",
    ]

    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["quality_snapshot"]["source_artifacts"][0]["timestamp_units"] == [
        "milliseconds"
    ]
    assert body["quality_snapshot"]["transformation"]["timestamp_unit"] == "mixed"
    assert body["quality_snapshot"]["transformation"]["timestamp_units"] == [
        "microseconds",
        "milliseconds",
    ]


def test_mixed_timestamp_provenance_requires_multiple_units() -> None:
    client, _ = client_with_session()
    payload = binance_dataset_payload()
    payload["transformation"]["timestamp_unit"] = "mixed"
    payload["transformation"]["timestamp_units"] = ["microseconds"]

    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

    assert response.status_code == 422
    assert "requires at least two units" in response.text


def test_ohlcv_continuous_gap_blocks_import_without_writing() -> None:
    client, _ = client_with_session()
    payload = dataset_payload(dataset_csv(gap=True))
    with client:
        preflight = client.post("/backtests/ohlcv/preflight-csv", json=payload)
        imported = client.post("/backtests/ohlcv/import-csv", json=payload)

        assert preflight.status_code == 200
        body = preflight.json()
        assert body["status"] == "REJECTED"
        assert body["gap_count"] == 1
        assert body["missing_interval_count"] == 1
        assert "continuous_ohlcv_dataset_contains_missing_intervals" in body[
            "rejection_reasons"
        ]
        assert body["evidence_hash"] is None
        assert imported.status_code == 400
        assert client.get("/backtests/ohlcv/datasets").json() == []


def test_ohlcv_session_gap_is_ready_but_explicitly_warned() -> None:
    client, _ = client_with_session()
    payload = dataset_payload(dataset_csv(gap=True), continuity="session_based")
    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "READY"
        assert body["gap_count"] == 1
        assert body["missing_interval_count"] == 1
        assert any("exchange-session coverage" in warning for warning in body["warnings"])


def test_ohlcv_documented_outage_gap_is_ready_and_hashed_as_evidence() -> None:
    client, _ = client_with_session()
    payload = dataset_payload(
        dataset_csv(gap=True),
        continuity="continuous_24_7_with_documented_outages",
    )
    payload["documented_gaps"] = [
        {
            "start": "2026-01-01T00:15:00Z",
            "end": "2026-01-01T00:30:00Z",
            "reason": "Fixture exchange outage removed one complete candle.",
            "source_reference": "https://status.example.test/incidents/fixture-outage",
            "source_title": "Fixture exchange incident",
        }
    ]

    with client:
        preflight = client.post("/backtests/ohlcv/preflight-csv", json=payload)
        imported = client.post("/backtests/ohlcv/import-csv", json=payload)

    assert preflight.status_code == 200, preflight.text
    body = preflight.json()
    assert body["status"] == "READY"
    assert body["documented_gap_count"] == 1
    assert body["undocumented_gap_count"] == 0
    assert body["evidence_hash"]
    assert body["quality_snapshot"]["observed_gaps"] == [
        {
            "previous_timestamp": "2026-01-01T00:00:00Z",
            "start": "2026-01-01T00:15:00Z",
            "end": "2026-01-01T00:30:00Z",
            "next_timestamp": "2026-01-01T00:30:00Z",
            "missing_interval_count": 1,
        }
    ]
    assert body["quality_snapshot"]["documented_gap_count"] == 1
    assert body["quality_snapshot"]["undocumented_gap_count"] == 0
    assert body["quality_snapshot"]["unmatched_documented_gaps"] == []
    assert any("exactly match" in warning for warning in body["warnings"])
    assert imported.status_code == 201, imported.text
    assert imported.json()["quality_snapshot"]["documented_gaps"][0][
        "source_reference"
    ] == "https://status.example.test/incidents/fixture-outage"


def test_ohlcv_documented_outage_requires_exact_observed_window() -> None:
    client, _ = client_with_session()
    payload = dataset_payload(
        dataset_csv(gap=True),
        continuity="continuous_24_7_with_documented_outages",
    )
    payload["documented_gaps"] = [
        {
            "start": "2026-01-01T00:15:00Z",
            "end": "2026-01-01T00:45:00Z",
            "reason": "Claimed outage window does not match the observed data gap.",
            "source_reference": "https://status.example.test/incidents/wrong-window",
        }
    ]

    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["documented_gap_count"] == 0
    assert body["undocumented_gap_count"] == 1
    assert "continuous_ohlcv_dataset_contains_undocumented_missing_intervals" in body[
        "rejection_reasons"
    ]
    assert "documented_outage_evidence_does_not_match_observed_gap" in body[
        "rejection_reasons"
    ]
    assert body["evidence_hash"] is None


def test_ohlcv_documented_outage_policy_requires_evidence() -> None:
    client, _ = client_with_session()
    payload = dataset_payload(
        dataset_csv(gap=True),
        continuity="continuous_24_7_with_documented_outages",
    )

    with client:
        missing = client.post("/backtests/ohlcv/preflight-csv", json=payload)
        payload["continuity"] = "continuous_24_7"
        payload["documented_gaps"] = [
            {
                "start": "2026-01-01T00:15:00Z",
                "end": "2026-01-01T00:30:00Z",
                "reason": "Evidence supplied under the wrong continuity policy.",
                "source_reference": "https://status.example.test/incidents/wrong-policy",
            }
        ]
        wrong_policy = client.post("/backtests/ohlcv/preflight-csv", json=payload)

    assert missing.status_code == 422
    assert "requires outage evidence" in missing.text
    assert wrong_policy.status_code == 422
    assert "requires documented-outage continuity" in wrong_policy.text


def test_ohlcv_documented_outage_rejects_partial_gap_coverage() -> None:
    client, _ = client_with_session()
    csv_text = (
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00Z,100,102,99,101,10\n"
        "2026-01-01T00:30:00Z,101,103,100,102,11\n"
        "2026-01-01T01:00:00Z,102,104,101,103,12\n"
    )
    payload = dataset_payload(
        csv_text,
        continuity="continuous_24_7_with_documented_outages",
    )
    payload["documented_gaps"] = [
        {
            "start": "2026-01-01T00:15:00Z",
            "end": "2026-01-01T00:30:00Z",
            "reason": "Only the first of two observed gaps is documented.",
            "source_reference": "https://status.example.test/incidents/partial",
        }
    ]

    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["gap_count"] == 2
    assert body["documented_gap_count"] == 1
    assert body["undocumented_gap_count"] == 1
    assert "continuous_ohlcv_dataset_contains_undocumented_missing_intervals" in body[
        "rejection_reasons"
    ]


def test_ohlcv_documented_outage_rejects_overlapping_windows() -> None:
    client, _ = client_with_session()
    payload = dataset_payload(
        dataset_csv(gap=True),
        continuity="continuous_24_7_with_documented_outages",
    )
    payload["documented_gaps"] = [
        {
            "start": "2026-01-01T00:15:00Z",
            "end": "2026-01-01T00:45:00Z",
            "reason": "First claimed outage overlaps the second claim.",
            "source_reference": "https://status.example.test/incidents/overlap-1",
        },
        {
            "start": "2026-01-01T00:30:00Z",
            "end": "2026-01-01T01:00:00Z",
            "reason": "Second claimed outage overlaps the first claim.",
            "source_reference": "https://status.example.test/incidents/overlap-2",
        },
    ]

    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

    assert response.status_code == 422
    assert "must not overlap" in response.text


def test_ohlcv_documented_outage_rejects_invalid_boundaries() -> None:
    client, _ = client_with_session()
    payload = dataset_payload(
        dataset_csv(gap=True),
        continuity="continuous_24_7_with_documented_outages",
    )
    payload["documented_gaps"] = [
        {
            "start": "2026-01-01T00:30:00Z",
            "end": "2026-01-01T00:30:00Z",
            "reason": "Contradictory outage has no positive duration.",
            "source_reference": "https://status.example.test/incidents/invalid",
        }
    ]
    naive_payload = deepcopy(payload)
    naive_payload["documented_gaps"][0].update(
        {
            "start": "2026-01-01T00:15:00",
            "end": "2026-01-01T00:30:00",
        }
    )

    with client:
        contradictory = client.post("/backtests/ohlcv/preflight-csv", json=payload)
        naive = client.post("/backtests/ohlcv/preflight-csv", json=naive_payload)

    assert contradictory.status_code == 422
    assert "end must be later" in contradictory.text
    assert naive.status_code == 422
    assert "must include a timezone" in naive.text


def test_ohlcv_invalid_geometry_and_duplicates_are_rejected() -> None:
    client, _ = client_with_session()
    invalid_geometry = (
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00Z,100,99,98,101,10\n"
    )
    duplicate = (
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00Z,100,102,99,101,10\n"
        "2026-01-01T00:00:00Z,101,103,100,102,11\n"
    )
    with client:
        geometry_response = client.post(
            "/backtests/ohlcv/preflight-csv",
            json=dataset_payload(invalid_geometry),
        )
        duplicate_response = client.post(
            "/backtests/ohlcv/preflight-csv",
            json=dataset_payload(duplicate),
        )

        assert geometry_response.json()["status"] == "REJECTED"
        assert geometry_response.json()["row_errors"][0]["reasons"] == [
            "high_is_below_ohlc_value"
        ]
        assert duplicate_response.json()["status"] == "REJECTED"
        assert duplicate_response.json()["duplicate_count"] == 1
        assert "ohlcv_dataset_contains_duplicate_timestamps" in duplicate_response.json()[
            "rejection_reasons"
        ]


def test_ohlcv_persisted_candle_tampering_fails_integrity_audit() -> None:
    client, session_factory = client_with_session()
    with client:
        imported = client.post("/backtests/ohlcv/import-csv", json=dataset_payload())
        assert imported.status_code == 201
        dataset_id = imported.json()["id"]

        with session_factory() as session:
            candle = session.execute(
                select(BacktestDatasetCandle)
                .where(BacktestDatasetCandle.dataset_id == dataset_id)
                .order_by(BacktestDatasetCandle.sequence)
                .limit(1)
            ).scalar_one()
            candle.close = "999"
            session.commit()

        audit = client.get(f"/backtests/ohlcv/datasets/{dataset_id}/audit")
        assert audit.status_code == 200
        assert audit.json()["status"] == "BLOCKED"
        assert audit.json()["evidence_hash_matches"] is False
        assert audit.json()["reasons"] == ["dataset_evidence_hash_mismatch"]


def test_ohlcv_quality_and_coverage_tampering_fail_integrity_audit() -> None:
    client, session_factory = client_with_session()
    with client:
        imported = client.post("/backtests/ohlcv/import-csv", json=dataset_payload())
        assert imported.status_code == 201
        dataset_id = imported.json()["id"]

        with session_factory() as session:
            dataset = session.get(BacktestDataset, dataset_id)
            assert dataset is not None
            quality = deepcopy(dataset.quality_snapshot)
            quality["status"] = "TAMPERED"
            dataset.quality_snapshot = quality
            dataset.data_start = dataset.data_start + timedelta(minutes=15)
            session.commit()

        audit = client.get(f"/backtests/ohlcv/datasets/{dataset_id}/audit").json()
        assert audit["status"] == "BLOCKED"
        assert "dataset_evidence_hash_mismatch" in audit["reasons"]
        assert "dataset_data_start_mismatch" in audit["reasons"]


def test_ohlcv_naive_timestamps_use_declared_timezone() -> None:
    client, _ = client_with_session()
    csv_text = (
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01 02:00:00,100,102,99,101,10\n"
        "2026-01-01 02:15:00,101,103,100,102,11\n"
    )
    payload = dataset_payload(csv_text)
    payload["csv_timezone"] = "Africa/Johannesburg"
    with client:
        response = client.post("/backtests/ohlcv/preflight-csv", json=payload)

        assert response.status_code == 200
        assert response.json()["data_start"] == "2026-01-01T00:00:00Z"
        assert response.json()["data_end"] == "2026-01-01T00:15:00Z"
