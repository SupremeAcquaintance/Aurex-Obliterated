import csv
import hashlib
import json
import subprocess
import sys
import urllib.error
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.validation_bundle import (
    ValidationArchiveRequest,
    ValidationDatasetBundle,
    build_validation_dataset_bundle,
    build_validation_dataset_entry,
    classify_availability,
)
from scripts import build_validation_dataset_bundle as validation_builder

HASH = "a" * 64
START = datetime(2025, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, tzinfo=UTC)


def test_validation_availability_accepts_full_and_terminal_only() -> None:
    full = classify_availability(
        partition_start=START,
        partition_end=END,
        row_count=2190,
        expected_row_count=2190,
        first_timestamp=START,
        last_timestamp=END - timedelta(hours=4),
        missing_timestamps=[],
    )
    terminal_start = datetime(2025, 2, 1, tzinfo=UTC)
    terminal_missing = []
    cursor = terminal_start
    while cursor < END:
        terminal_missing.append(cursor)
        cursor += timedelta(hours=4)
    terminal = classify_availability(
        partition_start=START,
        partition_end=END,
        row_count=186,
        expected_row_count=2190,
        first_timestamp=START,
        last_timestamp=terminal_start - timedelta(hours=4),
        missing_timestamps=terminal_missing,
    )

    assert full == ("FULL_CONTINUOUS", None)
    assert terminal == (
        "CONTIGUOUS_TERMINAL_SUFFIX_MISSING",
        terminal_start,
    )


def test_validation_availability_blocks_internal_or_leading_gap() -> None:
    internal_missing = [datetime(2025, 2, 1, tzinfo=UTC)]

    assert classify_availability(
        partition_start=START,
        partition_end=END,
        row_count=2189,
        expected_row_count=2190,
        first_timestamp=START,
        last_timestamp=END - timedelta(hours=4),
        missing_timestamps=internal_missing,
    ) == ("BLOCKED", None)
    assert classify_availability(
        partition_start=START,
        partition_end=END,
        row_count=2189,
        expected_row_count=2190,
        first_timestamp=START + timedelta(hours=4),
        last_timestamp=END - timedelta(hours=4),
        missing_timestamps=[START],
    ) == ("BLOCKED", None)


def test_unavailable_archive_receipt_cannot_claim_local_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot name local artifacts"):
        ValidationArchiveRequest(
            month="2025-01",
            archive_name="AAVEUSDT-4h-2025-01.zip",
            archive_uri=(
                "https://data.binance.vision/data/spot/monthly/klines/"
                "AAVEUSDT/4h/AAVEUSDT-4h-2025-01.zip"
            ),
            checksum_uri=(
                "https://data.binance.vision/data/spot/monthly/klines/"
                "AAVEUSDT/4h/AAVEUSDT-4h-2025-01.zip.CHECKSUM"
            ),
            observed_at=START,
            status="UNAVAILABLE_404",
            archive_relative_path="unexpected.zip",
        )


def test_validation_acquisition_records_404_without_creating_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def missing(_url: str, _maximum_bytes: int) -> bytes:
        raise urllib.error.HTTPError(
            url="https://example.invalid",
            code=404,
            msg="not found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(validation_builder, "fetch_url_bytes", missing)
    archive_directory = (
        tmp_path / "validation_2025_4h_bundle_v1" / "archives" / "AAVEUSDT"
    )
    archive_directory.mkdir(parents=True)

    receipt = validation_builder.acquire_archive_request(
        evidence_root=tmp_path,
        archive_directory=archive_directory,
        symbol="AAVEUSDT",
        month="2025-01",
    )

    assert receipt.status == "UNAVAILABLE_404"
    assert list(archive_directory.iterdir()) == []


def test_validation_acquisition_writes_only_checksum_verified_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    archive_bytes = b"synthetic archive bytes"
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    archive_name = "AAVEUSDT-4h-2025-01.zip"

    def fetched(url: str, _maximum_bytes: int) -> bytes:
        if url.endswith(".CHECKSUM"):
            return f"{archive_hash}  {archive_name}\n".encode()
        return archive_bytes

    monkeypatch.setattr(validation_builder, "fetch_url_bytes", fetched)
    archive_directory = (
        tmp_path / "validation_2025_4h_bundle_v1" / "archives" / "AAVEUSDT"
    )
    archive_directory.mkdir(parents=True)

    receipt = validation_builder.acquire_archive_request(
        evidence_root=tmp_path,
        archive_directory=archive_directory,
        symbol="AAVEUSDT",
        month="2025-01",
    )

    assert receipt.status == "CHECKSUM_VERIFIED"
    assert receipt.archive_sha256 == archive_hash
    assert (archive_directory / archive_name).read_bytes() == archive_bytes


def write_archive(
    root: Path,
    *,
    symbol: str,
    month: str,
    rows: list[list[str]],
) -> tuple[Path, Path]:
    archive_dir = root / "validation_2025_4h_bundle_v1" / "archives" / symbol
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f"{symbol}-4h-{month}.zip"
    member = f"{symbol}-4h-{month}.csv"
    content = "\n".join(",".join(row) for row in rows) + "\n"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(member, content)
    checksum = Path(f"{archive}.CHECKSUM")
    checksum.write_text(
        f"{file_sha256(archive)}  {archive.name}\n",
        encoding="utf-8",
    )
    return archive, checksum


def canonical_rows(count: int) -> list[list[str]]:
    rows = []
    for index in range(count):
        timestamp = START + timedelta(hours=4 * index)
        rows.append(
            [
                timestamp.isoformat().replace("+00:00", "Z"),
                "10",
                "11",
                "9",
                "10.5",
                "100",
            ]
        )
    return rows


def test_validation_entry_and_bundle_rebuild_from_local_evidence(
    tmp_path: Path,
) -> None:
    symbol = "AAVEUSDT"
    dataset_dir = tmp_path / "validation_2025_4h_bundle_v1" / "datasets"
    dataset_dir.mkdir(parents=True)
    csv_path = dataset_dir / f"{symbol}.csv"
    rows = canonical_rows(2190)
    with csv_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerows(rows)
    requests = []
    for month in [f"2025-{value:02d}" for value in range(1, 13)]:
        archive, checksum = write_archive(
            tmp_path,
            symbol=symbol,
            month=month,
            rows=[["synthetic"]],
        )
        digest = file_sha256(archive)
        requests.append(
            ValidationArchiveRequest(
                month=month,
                archive_name=archive.name,
                archive_uri=(
                    "https://data.binance.vision/data/spot/monthly/klines/"
                    f"{symbol}/4h/{archive.name}"
                ),
                checksum_uri=(
                    "https://data.binance.vision/data/spot/monthly/klines/"
                    f"{symbol}/4h/{archive.name}.CHECKSUM"
                ),
                observed_at=START,
                status="CHECKSUM_VERIFIED",
                archive_relative_path=archive.relative_to(tmp_path).as_posix(),
                checksum_relative_path=checksum.relative_to(tmp_path).as_posix(),
                archive_sha256=digest,
                checksum_file_sha256=file_sha256(checksum),
                expected_archive_sha256=digest,
                archive_size_bytes=archive.stat().st_size,
            )
        )
    manifest = {
        "symbol": symbol,
        "timeframe": "4h",
        "row_count": 2190,
        "canonical_csv_sha256": file_sha256(csv_path),
        "transformation": {"timestamp_units": ["milliseconds"]},
        "source_artifacts": [
            {
                "filename": request.archive_name,
                "sha256": request.archive_sha256,
                "checksum_file_sha256": request.checksum_file_sha256,
                "expected_sha256": request.expected_archive_sha256,
                "size_bytes": request.archive_size_bytes,
                "checksum_verified": True,
            }
            for request in requests
        ],
        "validation_archive_requests": [
            request.model_dump(mode="json") for request in requests
        ],
        "strategy_outcome_fields_inspected": [],
    }
    manifest_path = dataset_dir / f"{symbol}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    entry = build_validation_dataset_entry(
        evidence_root=tmp_path,
        symbol=symbol,
        partition_start=START,
        partition_end=END,
        archive_directory_relative_path=(
            f"validation_2025_4h_bundle_v1/archives/{symbol}"
        ),
        csv_relative_path=f"validation_2025_4h_bundle_v1/datasets/{symbol}.csv",
        source_manifest_relative_path=(
            f"validation_2025_4h_bundle_v1/datasets/{symbol}.manifest.json"
        ),
    )

    assert entry.status == "READY"
    assert entry.availability_shape == "FULL_CONTINUOUS"
    assert entry.verified_archive_count == 12


def test_validation_bundle_refuses_outcome_inspection() -> None:
    with pytest.raises((ValidationError, ValueError)):
        build_validation_dataset_bundle(
            generated_at=START,
            r4_candidate_protocol_evidence_hash=HASH,
            universe_manifest_evidence_hash=HASH,
            development_dataset_bundle_evidence_hash=HASH,
            contamination_ledger_hash=HASH,
            builder_contract_hash=HASH,
            entries=[],
            limitations=["synthetic"],
        )


def test_validation_bundle_hash_tamper_is_detected() -> None:
    payload = {
        "schema_version": "aurex-r4-validation-dataset-bundle-v1",
        "generated_at": START,
        "r4_candidate_protocol_evidence_hash": HASH,
        "universe_manifest_evidence_hash": HASH,
        "development_dataset_bundle_evidence_hash": HASH,
        "contamination_ledger_hash": HASH,
        "builder_contract_hash": HASH,
        "partition_name": "VALIDATION",
        "partition_start": START,
        "partition_end": END,
        "timeframe": "4h",
        "entries": [],
        "summary": {
            "dataset_count": 35,
            "ready_dataset_count": 0,
            "blocked_dataset_count": 35,
            "full_continuous_count": 0,
            "terminal_unavailable_count": 0,
            "total_rows": 0,
            "verified_archive_count": 0,
            "unavailable_archive_count": 0,
            "symbols": [],
            "blocked_symbols": [],
            "terminal_unavailable_symbols": [],
        },
        "limitations": ["synthetic"],
        "strategy_outcome_fields_inspected": [],
        "status": "BLOCKED",
    }
    payload["bundle_evidence_hash"] = hashlib.sha256(b"not-canonical").hexdigest()

    with pytest.raises(ValidationError):
        ValidationDatasetBundle.model_validate(payload)


def test_validation_bundle_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/build_validation_dataset_bundle.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
