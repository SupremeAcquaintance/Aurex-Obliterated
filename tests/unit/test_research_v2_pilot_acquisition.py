import hashlib
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2AcquisitionTarget,
    V2DerivativesAcquisitionProtocol,
)
from aurex.backtest_engine.research_v2_pilot_acquisition import (
    FUNDING_SCHEMA_ID,
    KLINE_SCHEMA_ID,
    V2PilotArchiveEvidence,
    audit_v2_pilot_acquisition_result,
    build_v2_pilot_acquisition_result,
    inspect_v2_pilot_archive,
)
from scripts import run_v2_acquisition_pilot as pilot_script
from scripts.run_v2_acquisition_pilot import (
    V2PilotPreflight,
    _download_archive_once,
    preflight_target,
)

PROTOCOL_PATH = Path(
    "data/evidence/v2_derivatives_acquisition_protocol_v1.json"
)
CHECKED_AT = datetime(2026, 7, 28, 2, tzinfo=UTC)
RUNNER_HASH = "d" * 64


@pytest.fixture(scope="module")
def protocol() -> V2DerivativesAcquisitionProtocol:
    return V2DerivativesAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def write_zip(path: Path, member_name: str, csv_text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, csv_text)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_target(
    source: V2AcquisitionTarget,
    archive_sha256: str,
) -> V2AcquisitionTarget:
    return V2AcquisitionTarget(
        symbol=source.symbol,
        month=source.month,
        family_id=source.family_id,
        archive_url=source.archive_url,
        checksum_url=source.checksum_url,
        census_checksum_sha256=archive_sha256,
    )


def inspect_synthetic(
    *,
    protocol: V2DerivativesAcquisitionProtocol,
    tmp_path: Path,
    source_target: V2AcquisitionTarget,
    csv_text: str,
    member_name: str,
) -> V2PilotArchiveEvidence:
    archive_path = tmp_path / "archives" / f"{source_target.family_id}.zip"
    archive_sha256 = write_zip(archive_path, member_name, csv_text)
    target = synthetic_target(source_target, archive_sha256)
    checksum_path = Path(f"{archive_path}.CHECKSUM")
    checksum_path.write_text(
        f"{archive_sha256}  {archive_path.name}\n",
        encoding="utf-8",
    )
    return inspect_v2_pilot_archive(
        target=target,
        archive_path=archive_path,
        checksum_path=checksum_path,
        evidence_root=tmp_path,
        checksum_checked_at=CHECKED_AT,
        preflight_checked_at=CHECKED_AT,
        archive_content_length=archive_path.stat().st_size,
        archive_last_modified="Tue, 28 Jul 2026 00:00:00 GMT",
        archive_etag='"test"',
        protocol=protocol,
    )


def test_v2_pilot_inspects_headerless_kline_without_returns(
    protocol: V2DerivativesAcquisitionProtocol,
    tmp_path: Path,
) -> None:
    source = next(
        target
        for target in protocol.targets
        if target.family_id == "spot_klines_1m"
        and target.symbol == "AAVEUSDT"
        and target.month == "2023-01"
    )
    csv_text = (
        "1672531200000,10,11,9,10.5,100,1672531259999,1050,5,50,525,0\n"
        "1672531260000,10.5,12,10,11,120,1672531319999,1320,7,60,660,0\n"
    )

    evidence = inspect_synthetic(
        protocol=protocol,
        tmp_path=tmp_path,
        source_target=source,
        csv_text=csv_text,
        member_name="AAVEUSDT-1m-2023-01.csv",
    )

    assert evidence.schema_id == KLINE_SCHEMA_ID
    assert evidence.csv_header == []
    assert evidence.csv_column_count == 12
    assert evidence.row_count == 2
    assert evidence.timestamp_unit == "milliseconds"
    assert evidence.duplicate_timestamp_count == 0


def test_v2_pilot_classifies_funding_schema(
    protocol: V2DerivativesAcquisitionProtocol,
    tmp_path: Path,
) -> None:
    source = next(
        target
        for target in protocol.targets
        if target.family_id == "um_funding_rate_events"
        and target.symbol == "AAVEUSDT"
        and target.month == "2023-01"
    )
    csv_text = (
        "calc_time,funding_interval_hours,last_funding_rate\n"
        "1672531200000,8,0.00010000\n"
        "1672560000000,8,-0.00002000\n"
    )

    evidence = inspect_synthetic(
        protocol=protocol,
        tmp_path=tmp_path,
        source_target=source,
        csv_text=csv_text,
        member_name="AAVEUSDT-fundingRate-2023-01.csv",
    )

    assert evidence.schema_id == FUNDING_SCHEMA_ID
    assert evidence.csv_header == [
        "calc_time",
        "funding_interval_hours",
        "last_funding_rate",
    ]
    assert evidence.row_count == 2


def test_v2_pilot_rejects_unsafe_nested_zip_member(
    protocol: V2DerivativesAcquisitionProtocol,
    tmp_path: Path,
) -> None:
    source = next(
        target
        for target in protocol.targets
        if target.family_id == "spot_klines_1m"
    )
    archive_path = tmp_path / "nested.zip"
    archive_sha256 = write_zip(
        archive_path,
        "../escape.csv",
        "1672531200000,10,11,9,10.5,100,1672531259999,1050,5,50,525,0\n",
    )
    target = synthetic_target(source, archive_sha256)
    checksum_path = Path(f"{archive_path}.CHECKSUM")
    checksum_path.write_text(
        f"{archive_sha256}  {archive_path.name}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsafe nested member"):
        inspect_v2_pilot_archive(
            target=target,
            archive_path=archive_path,
            checksum_path=checksum_path,
            evidence_root=tmp_path,
            checksum_checked_at=CHECKED_AT,
            preflight_checked_at=CHECKED_AT,
            archive_content_length=archive_path.stat().st_size,
            archive_last_modified=None,
            archive_etag=None,
            protocol=protocol,
        )


class FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: bytes = b"",
        headers: dict[str, str] | None = None,
    ):
        self.status = status
        self.payload = payload
        self.headers = headers or {}
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def read(self, size: int = -1):
        if size < 0:
            size = len(self.payload) - self.offset
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def test_v2_pilot_preflight_stops_on_checksum_revision(
    protocol: V2DerivativesAcquisitionProtocol,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = protocol.targets[0]
    archive_name = Path(target.archive_url).name
    revised = "e" * 64
    calls = []

    def request(**kwargs):
        calls.append(kwargs["method"])
        return FakeResponse(
            payload=f"{revised}  {archive_name}\n".encode(),
        )

    monkeypatch.setattr(pilot_script, "_request", request)

    with pytest.raises(ValueError, match="changed after the source census"):
        preflight_target(target=target, protocol=protocol)

    assert calls == ["GET"]


def test_v2_pilot_failed_download_removes_part_file(
    protocol: V2DerivativesAcquisitionProtocol,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = protocol.targets[0]
    payload = b"wrong archive bytes"
    preflight = V2PilotPreflight(
        target=target,
        checksum_checked_at=CHECKED_AT,
        preflight_checked_at=CHECKED_AT,
        content_length=len(payload),
        last_modified=None,
        etag=None,
    )
    monkeypatch.setattr(
        pilot_script,
        "_request",
        lambda **_kwargs: FakeResponse(
            payload=payload,
            headers={"Content-Length": str(len(payload))},
        ),
    )
    archive_path = tmp_path / "archive.zip"

    with pytest.raises(ValueError, match="checksum does not match"):
        _download_archive_once(
            preflight=preflight,
            protocol=protocol,
            archive_path=archive_path,
        )

    assert not archive_path.exists()
    assert not archive_path.with_name(f"{archive_path.name}.part").exists()


def complete_records(
    protocol: V2DerivativesAcquisitionProtocol,
) -> list[V2PilotArchiveEvidence]:
    records = []
    for index, target in enumerate(protocol.targets, start=1):
        year, month = (int(part) for part in target.month.split("-"))
        first_timestamp = datetime(year, month, 1, tzinfo=UTC)
        records.append(
            V2PilotArchiveEvidence(
                symbol=target.symbol,
                month=target.month,
                family_id=target.family_id,
                archive_url=target.archive_url,
                checksum_url=target.checksum_url,
                census_checksum_sha256=target.census_checksum_sha256,
                refreshed_checksum_sha256=target.census_checksum_sha256,
                checksum_checked_at=CHECKED_AT,
                checksum_file_sha256=f"{index:064x}",
                preflight_checked_at=CHECKED_AT,
                archive_content_length=100 + index,
                archive_relative_path=f"pilot/{index}.zip",
                checksum_relative_path=f"pilot/{index}.zip.CHECKSUM",
                archive_sha256=target.census_checksum_sha256,
                archive_size_bytes=100 + index,
                zip_compressed_bytes=50,
                zip_uncompressed_bytes=500,
                csv_member_name=f"{index}.csv",
                csv_header=[],
                csv_column_count=(
                    3 if target.family_id == "um_funding_rate_events" else 12
                ),
                row_count=2,
                first_timestamp=first_timestamp,
                last_timestamp=first_timestamp.replace(minute=1),
                schema_id=(
                    FUNDING_SCHEMA_ID
                    if target.family_id == "um_funding_rate_events"
                    else KLINE_SCHEMA_ID
                ),
            )
        )
    return records


def test_v2_pilot_result_permits_protocol_design_not_full_download(
    protocol: V2DerivativesAcquisitionProtocol,
) -> None:
    result = build_v2_pilot_acquisition_result(
        generated_at=CHECKED_AT,
        protocol=protocol,
        runner_contract_hash=RUNNER_HASH,
        records=complete_records(protocol),
        limitations=[
            "Pilot only.",
            "No returns.",
            "No signals.",
            "No candidate.",
            "No live.",
        ],
    )

    assert result.summary.target_count == 54
    assert result.summary.classified_family_count == 6
    assert result.permits_full_acquisition_protocol_design is True
    assert result.authorizes_full_archive_payload_download is False
    assert result.authorizes_market_data_import is False
    assert result.authorizes_strategy_return_calculation is False
    assert (
        audit_v2_pilot_acquisition_result(
            result=result,
            protocol=protocol,
            current_runner_contract_hash=RUNNER_HASH,
            evidence_root=Path("."),
            inspect_local_archives=False,
        )["status"]
        == "PASS"
    )


def test_v2_pilot_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v2_acquisition_pilot.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
