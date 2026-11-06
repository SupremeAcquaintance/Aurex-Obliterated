import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v2_p01_protocol import (
    V2P01PrimaryProtocol,
)
from aurex.backtest_engine.research_v2_source_census import (
    V2SourceCensusResult,
)
from scripts import run_v2_p01_full_acquisition as runner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / "data" / "evidence"


def load_protocol() -> V2P01PrimaryProtocol:
    return V2P01PrimaryProtocol.model_validate_json(
        (EVIDENCE_ROOT / "v2_p01_primary_protocol_v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_cli_help_is_available_without_network() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v2_p01_full_acquisition.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--preflight" in completed.stdout
    assert "--download" in completed.stdout
    assert "--run" in completed.stdout
    assert "--audit" in completed.stdout


def test_render_targets_reproduces_frozen_4464_archive_manifest() -> None:
    protocol = load_protocol()
    census = V2SourceCensusResult.model_validate_json(
        (
            EVIDENCE_ROOT / "v2_derivatives_source_census_result_v1.json"
        ).read_text(encoding="utf-8")
    )

    targets = runner.render_targets(
        protocol=protocol,
        census_result=census,
    )

    assert len(targets) == 4464
    assert len({target.key for target in targets}) == 4464
    assert targets == sorted(targets, key=lambda target: target.key)


def spot_symbol(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "status": "TRADING",
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.001",
                "stepSize": "0.001",
            },
            {
                "filterType": "MARKET_LOT_SIZE",
                "maxQty": "1000",
                "stepSize": "0",
            },
            {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
        ],
    }


def test_spot_snapshot_classification_is_complete_and_fail_closed(
    tmp_path: Path,
) -> None:
    symbols = [spot_symbol(symbol) for symbol in V2_COMPLETE_SYMBOLS]
    symbols[0]["filters"][2]["maxQty"] = "0"
    payload = json.dumps({"symbols": symbols}).encode("utf-8")
    requested_url = "https://api.binance.com/api/v3/exchangeInfo"

    snapshot = runner.classify_snapshot_payload(
        snapshot_kind="SPOT_EXCHANGE_INFO",
        requested_url=requested_url,
        final_url=requested_url,
        checked_at=datetime(2026, 7, 28, tzinfo=UTC),
        content_type="application/json",
        payload=payload,
        evidence_root=tmp_path,
        storage_root=tmp_path / "p01",
    )

    assert snapshot.present_required_symbols == sorted(V2_COMPLETE_SYMBOLS)
    assert snapshot.incomplete_filter_symbols == [V2_COMPLETE_SYMBOLS[0]]
    assert V2_COMPLETE_SYMBOLS[0] not in snapshot.complete_filter_symbols
    assert V2_COMPLETE_SYMBOLS[1] in snapshot.complete_filter_symbols
    assert (tmp_path / snapshot.snapshot_relative_path).read_bytes() == payload


def test_headerless_kline_csv_is_inspected_as_a_stream(
    tmp_path: Path,
) -> None:
    protocol = load_protocol()
    target = runner.P01FullTarget(
        symbol="AAVEUSDT",
        month="2023-01",
        family_id="spot_klines_1m",
        archive_url=(
            "https://data.binance.vision/data/spot/monthly/klines/"
            "AAVEUSDT/1m/AAVEUSDT-1m-2023-01.zip"
        ),
        checksum_url=(
            "https://data.binance.vision/data/spot/monthly/klines/"
            "AAVEUSDT/1m/AAVEUSDT-1m-2023-01.zip.CHECKSUM"
        ),
        census_checksum_sha256="a" * 64,
    )
    rows = (
        b"1672531200000,1,2,0.5,1.5,10,1672531259999,12,2,5,6,0\n"
        b"1672531260000,1.5,2,1,1.75,10,1672531319999,12,2,5,6,0\n"
    )
    archive_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("sample.csv", rows)

    with zipfile.ZipFile(archive_path) as archive:
        member, _, _ = runner._validate_zip_member(
            archive=archive,
            protocol=protocol,
        )
        evidence = runner._inspect_csv(
            archive=archive,
            member=member,
            target=target,
        )

    assert evidence["row_count"] == 2
    assert evidence["csv_header"] == []
    assert evidence["continuity_gap_count"] == 0
    assert evidence["boundary_complete"] is False
    assert evidence["continuity_pass"] is False


def test_kline_inspection_rejects_non_numeric_unused_column(
    tmp_path: Path,
) -> None:
    protocol = load_protocol()
    target = runner.P01FullTarget(
        symbol="AAVEUSDT",
        month="2023-01",
        family_id="spot_klines_1m",
        archive_url=(
            "https://data.binance.vision/data/spot/monthly/klines/"
            "AAVEUSDT/1m/AAVEUSDT-1m-2023-01.zip"
        ),
        checksum_url=(
            "https://data.binance.vision/data/spot/monthly/klines/"
            "AAVEUSDT/1m/AAVEUSDT-1m-2023-01.zip.CHECKSUM"
        ),
        census_checksum_sha256="a" * 64,
    )
    row = (
        b"1672531200000,1,2,0.5,1.5,10,1672531259999,12,2,5,6,"
        b"not-a-number\n"
    )
    archive_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("invalid.csv", row)

    with zipfile.ZipFile(archive_path) as archive:
        member, _, _ = runner._validate_zip_member(
            archive=archive,
            protocol=protocol,
        )
        with pytest.raises(ValueError, match="numeric field"):
            runner._inspect_csv(
                archive=archive,
                member=member,
                target=target,
            )


def test_symbol_qualification_reasons_are_mechanical() -> None:
    complete_symbol = V2_COMPLETE_SYMBOLS[0]
    records = [
        SimpleNamespace(symbol=complete_symbol, continuity_pass=True)
        for _ in range(144)
    ]
    snapshots = [
        SimpleNamespace(
            snapshot_kind="SPOT_EXCHANGE_INFO",
            complete_filter_symbols=list(V2_COMPLETE_SYMBOLS),
        ),
        SimpleNamespace(
            snapshot_kind="USD_M_EXCHANGE_INFO",
            complete_filter_symbols=list(V2_COMPLETE_SYMBOLS),
        ),
    ]

    qualifications = runner.build_symbol_qualifications(
        records=records,
        snapshots=snapshots,
    )
    by_symbol = {item.symbol: item for item in qualifications}

    assert by_symbol[complete_symbol].qualification_pass is True
    missing_symbol = V2_COMPLETE_SYMBOLS[1]
    assert by_symbol[missing_symbol].reason_codes == [
        "ARCHIVE_CONTINUITY_GAP"
    ]
