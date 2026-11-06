import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aurex.backtest_engine.binance_vision import (
    download_binance_vision_archives,
    monthly_archive_names,
    prepare_binance_vision_dataset,
)


def write_archive(tmp_path: Path) -> Path:
    archive_path = tmp_path / "BTCUSDT-15m-2026-01.zip"
    rows = (
        "1767225600000000,100,102,99,101,10,1767226499999999,0,1,0,0,0\n"
        "1767226500000000,101,103,100,102,11,1767227399999999,0,1,0,0,0\n"
        "1767227400000000,102,104,101,103,12,1767228299999999,0,1,0,0,0\n"
    )
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("BTCUSDT-15m-2026-01.csv", rows)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    Path(f"{archive_path}.CHECKSUM").write_text(
        f"{digest}  {archive_path.name}\n",
        encoding="utf-8",
    )
    return archive_path


def test_prepare_binance_vision_dataset_verifies_and_normalizes_archive(
    tmp_path: Path,
) -> None:
    archive_path = write_archive(tmp_path)

    prepared = prepare_binance_vision_dataset(
        archive_paths=[archive_path],
        symbol="BTCUSDT",
        timeframe="15m",
        data_start=datetime(2026, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 1, 1, 0, 30, tzinfo=UTC),
    )

    assert prepared.manifest["row_count"] == 3
    assert prepared.manifest["transformation"]["timestamp_unit"] == "microseconds"
    assert prepared.manifest["transformation"]["timestamp_units"] == ["microseconds"]
    assert prepared.manifest["source_artifacts"][0]["checksum_verified"] is True
    assert prepared.manifest["canonical_csv_sha256"] == hashlib.sha256(
        prepared.csv_text.encode("utf-8")
    ).hexdigest()
    assert prepared.csv_text.startswith("timestamp,open,high,low,close,volume\n")
    assert "2026-01-01T00:15:00Z,101,103,100,102,11" in prepared.csv_text


def test_prepare_binance_vision_dataset_rejects_tampered_archive(tmp_path: Path) -> None:
    archive_path = write_archive(tmp_path)
    archive_path.write_bytes(archive_path.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="Checksum mismatch"):
        prepare_binance_vision_dataset(
            archive_paths=[archive_path],
            symbol="BTCUSDT",
            timeframe="15m",
            data_start=datetime(2026, 1, 1, tzinfo=UTC),
            data_end=datetime(2026, 1, 2, tzinfo=UTC),
        )


def archive_bytes(member: str, rows: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(member, rows)
    return output.getvalue()


def test_prepare_binance_vision_dataset_accepts_documented_timestamp_transition(
    tmp_path: Path,
) -> None:
    archives: list[Path] = []
    fixtures = {
        "BTCUSDT-15m-2024-12.zip": (
            "1735688700000,100,102,99,101,10,1735689599999,0,1,0,0,0\n"
        ),
        "BTCUSDT-15m-2025-01.zip": (
            "1735689600000000,101,103,100,102,11,1735690499999999,0,1,0,0,0\n"
        ),
    }
    for name, rows in fixtures.items():
        path = tmp_path / name
        path.write_bytes(archive_bytes(name.replace(".zip", ".csv"), rows))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        Path(f"{path}.CHECKSUM").write_text(
            f"{digest}  {name}\n",
            encoding="utf-8",
        )
        archives.append(path)

    prepared = prepare_binance_vision_dataset(
        archive_paths=archives,
        symbol="BTCUSDT",
        timeframe="15m",
        data_start=datetime(2024, 12, 31, 23, 45, tzinfo=UTC),
        data_end=datetime(2025, 1, 1, tzinfo=UTC),
    )

    assert prepared.manifest["row_count"] == 2
    assert prepared.manifest["transformation"]["timestamp_unit"] == "mixed"
    assert prepared.manifest["transformation"]["timestamp_units"] == [
        "microseconds",
        "milliseconds",
    ]


def test_download_binance_vision_archives_is_verified_and_resumable(
    tmp_path: Path,
) -> None:
    names = monthly_archive_names(
        symbol="btcusdt",
        timeframe="15m",
        data_start=datetime(2026, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 3, 1, tzinfo=UTC),
    )
    assert names == ["BTCUSDT-15m-2026-01.zip", "BTCUSDT-15m-2026-02.zip"]

    payloads: dict[str, bytes] = {}
    for index, name in enumerate(names, start=1):
        rows = (
            f"176722{index}000000000,100,102,99,101,10,"
            f"176722{index}899999999,0,1,0,0,0\n"
        )
        archive = archive_bytes(name.replace(".zip", ".csv"), rows)
        relative = f"BTCUSDT/15m/{name}"
        payloads[f"https://example.test/{relative}"] = archive
        payloads[f"https://example.test/{relative}.CHECKSUM"] = (
            f"{hashlib.sha256(archive).hexdigest()}  {name}\n".encode()
        )
    fetched: list[str] = []

    def fetch(url: str, maximum_bytes: int) -> bytes:
        fetched.append(url)
        payload = payloads[url]
        assert len(payload) <= maximum_bytes
        return payload

    first = download_binance_vision_archives(
        destination=tmp_path,
        symbol="BTCUSDT",
        timeframe="15m",
        data_start=datetime(2026, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 3, 1, tzinfo=UTC),
        base_uri="https://example.test",
        fetch=fetch,
    )
    second = download_binance_vision_archives(
        destination=tmp_path,
        symbol="BTCUSDT",
        timeframe="15m",
        data_start=datetime(2026, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 3, 1, tzinfo=UTC),
        base_uri="https://example.test",
        fetch=fetch,
    )

    assert [path.name for path in first] == names
    assert second == first
    assert len(fetched) == 4
