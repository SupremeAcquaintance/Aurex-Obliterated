from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_p01_acquisition_result import (
    P01CurrentMetadataSnapshotEvidence,
    P01FullArchiveEvidence,
    P01SymbolQualification,
    V2P01FullAcquisitionResult,
    build_p01_full_acquisition_summary,
)
from aurex.backtest_engine.universe import universe_evidence_hash

SHA = "a" * 64


def archive_record(
    *,
    symbol: str = "AAVEUSDT",
    family_id: str = "spot_klines_1m",
    continuous: bool = True,
) -> P01FullArchiveEvidence:
    start = datetime(2023, 1, 1, tzinfo=UTC)
    funding = family_id == "um_funding_rate_events"
    return P01FullArchiveEvidence(
        symbol=symbol,
        month="2023-01",
        family_id=family_id,
        archive_url=(
            "https://data.binance.vision/data/spot/monthly/klines/"
            f"{symbol}/1m/{symbol}-1m-2023-01.zip"
        ),
        checksum_url=(
            "https://data.binance.vision/data/spot/monthly/klines/"
            f"{symbol}/1m/{symbol}-1m-2023-01.zip.CHECKSUM"
        ),
        census_checksum_sha256=SHA,
        refreshed_checksum_sha256=SHA,
        checksum_checked_at=start,
        preflight_checked_at=start,
        inspected_at=start,
        archive_content_length=100,
        archive_relative_path="bundle/archive.zip",
        checksum_relative_path="bundle/archive.zip.CHECKSUM",
        archive_sha256=SHA,
        checksum_file_sha256="b" * 64,
        archive_size_bytes=100,
        zip_compressed_bytes=90,
        zip_uncompressed_bytes=1000,
        csv_member_name="archive.csv",
        schema_id=(
            "BINANCE_FUNDING_RATE_EVENT_V1"
            if funding
            else "BINANCE_POSITIONAL_KLINE_12_COLUMNS_V1"
        ),
        csv_header=(
            ["calc_time", "funding_interval_hours", "last_funding_rate"]
            if funding
            else []
        ),
        csv_column_count=3 if funding else 12,
        row_count=93 if funding else 44640,
        first_timestamp=start,
        last_timestamp=(
            start + timedelta(hours=8 * 92)
            if funding
            else start + timedelta(minutes=44639)
        ),
        expected_minute_count=None if funding else 44640,
        missing_minute_count=None if funding else (0 if continuous else 1),
        continuity_gap_count=None if funding else (0 if continuous else 1),
        boundary_complete=True,
        continuity_pass=True if funding else continuous,
    )


def snapshot(kind: str) -> P01CurrentMetadataSnapshotEvidence:
    url = {
        "SPOT_EXCHANGE_INFO": "https://api.binance.com/api/v3/exchangeInfo",
        "USD_M_EXCHANGE_INFO": (
            "https://fapi.binance.com/fapi/v1/exchangeInfo"
        ),
    }[kind]
    symbols = [
        "AAVEUSDT",
        "ADAUSDT",
        "APEUSDT",
        "APTUSDT",
        "ATOMUSDT",
        "AVAXUSDT",
        "BCHUSDT",
        "BNBUSDT",
        "CRVUSDT",
        "DOGEUSDT",
        "DOTUSDT",
        "DYDXUSDT",
        "ETCUSDT",
        "FETUSDT",
        "FILUSDT",
        "FTMUSDT",
        "GALAUSDT",
        "GRTUSDT",
        "ICPUSDT",
        "INJUSDT",
        "LDOUSDT",
        "LINKUSDT",
        "LTCUSDT",
        "MKRUSDT",
        "NEARUSDT",
        "OPUSDT",
        "RUNEUSDT",
        "SANDUSDT",
        "TRXUSDT",
        "UNIUSDT",
        "XRPUSDT",
    ]
    return P01CurrentMetadataSnapshotEvidence(
        snapshot_kind=kind,
        requested_url=url,
        final_url=url,
        checked_at=datetime(2026, 7, 28, tzinfo=UTC),
        content_type="application/json",
        response_bytes=100,
        response_sha256=SHA,
        snapshot_relative_path=f"bundle/{kind}.json",
        present_required_symbols=symbols,
        missing_required_symbols=[],
        complete_filter_symbols=symbols,
        incomplete_filter_symbols=[],
    )


def qualification(
    symbol: str = "AAVEUSDT",
    *,
    passed: bool = True,
) -> P01SymbolQualification:
    return P01SymbolQualification(
        symbol=symbol,
        archive_continuity_pass=passed,
        current_spot_filter_proxy_pass=True,
        current_futures_filter_proxy_pass=True,
        qualification_pass=passed,
        reason_codes=[] if passed else ["ARCHIVE_CONTINUITY_GAP"],
    )


def test_archive_evidence_refuses_checksum_or_continuity_drift() -> None:
    payload = archive_record().model_dump()
    payload["archive_sha256"] = "c" * 64
    with pytest.raises(ValidationError, match="checksum lineage"):
        P01FullArchiveEvidence.model_validate(payload)

    payload = archive_record().model_dump()
    payload["continuity_pass"] = False
    with pytest.raises(ValidationError, match="continuity classification"):
        P01FullArchiveEvidence.model_validate(payload)


def test_snapshot_is_explicitly_current_and_nonhistorical() -> None:
    evidence = snapshot("SPOT_EXCHANGE_INFO")

    assert evidence.historical_rule_proof is False
    assert evidence.credentials_used is False
    assert len(evidence.complete_filter_symbols) == 31


def test_qualification_reasons_are_mechanical() -> None:
    failed = qualification(passed=False)
    assert failed.reason_codes == ["ARCHIVE_CONTINUITY_GAP"]

    payload = failed.model_dump()
    payload["qualification_pass"] = True
    with pytest.raises(ValidationError, match="decision does not reconcile"):
        P01SymbolQualification.model_validate(payload)


def test_summary_reconciles_records_and_qualifications() -> None:
    records = [
        archive_record(family_id="spot_klines_1m"),
        archive_record(family_id="um_funding_rate_events"),
    ]
    items = [qualification()]
    for index in range(30):
        items.append(
            qualification(
                symbol=f"X{index:02d}USDT",
                passed=False,
            )
        )

    with pytest.raises(ValidationError):
        build_p01_full_acquisition_summary(
            records=records,
            qualifications=items,
        )


def test_result_model_refuses_return_metrics_before_full_matrix_validation() -> None:
    assert V2P01FullAcquisitionResult.model_fields[
        "return_metrics_calculated"
    ].default_factory() == []
    payload = {
        "return_metrics_calculated": ["net_pl"],
        "result_evidence_hash": SHA,
    }
    payload["result_evidence_hash"] = universe_evidence_hash(payload)
    with pytest.raises(ValidationError):
        V2P01FullAcquisitionResult.model_validate(payload)


def test_snapshot_paths_are_relative() -> None:
    payload = snapshot("USD_M_EXCHANGE_INFO").model_dump()
    payload["snapshot_relative_path"] = Path("/absolute/snapshot.json").as_posix()
    with pytest.raises(ValidationError, match="path is unsafe"):
        P01CurrentMetadataSnapshotEvidence.model_validate(payload)
