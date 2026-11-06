from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from aurex.backtest_engine.s1_btc_source_acquisition import (
    S1BtcSourceAcquisitionProtocol,
)
from aurex.backtest_engine.s1_btc_source_execution import (
    S1BtcSourceExecutionContract,
)
from scripts import run_s1_btc_source_acquisition as runner

PROTOCOL_PATH = Path("data/evidence/s1_btc_source_acquisition_protocol_v1.json")


def load_protocol() -> S1BtcSourceAcquisitionProtocol:
    return S1BtcSourceAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def kline_rows(target, *, price: str = "123.45000000") -> list[list[str]]:
    rows = []
    for hour in range(24):
        open_time = target.activation_open_time_ms + hour * 3_600_000
        rows.append(
            [
                str(open_time),
                price if hour == 0 else "124.00000000",
                "125.00000000",
                "122.00000000",
                "124.50000000",
                "10.00000000",
                str(open_time + 3_599_999),
                "1000.00000000",
                "10",
                "5.00000000",
                "500.00000000",
                "0",
            ]
        )
    return rows


def archive_bytes(target, rows: list[list[str]], *, member: str | None = None) -> bytes:
    csv_payload = "\n".join(",".join(row) for row in rows) + "\n"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member or target.expected_member_name, csv_payload)
    return output.getvalue()


def write_archive(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256(payload).hexdigest()


def inspect(path: Path, target, digest: str):
    return runner.inspect_archive(
        path,
        target=target,
        published_archive_sha256=digest,
        maximum_uncompressed_csv_bytes=1_000_000,
    )


def test_all_frozen_targets_remain_inside_the_allowlist() -> None:
    protocol = load_protocol()
    for target in protocol.targets:
        runner.validate_target(target)


def test_checksum_parser_accepts_only_bound_sha256_and_filename() -> None:
    digest = "a" * 64
    assert runner.parse_checksum_text(f"{digest}  BTCUSDT.zip\n", "BTCUSDT.zip") == digest
    with pytest.raises(ValueError, match="malformed"):
        runner.parse_checksum_text(f"{digest}  OTHER.zip\n", "BTCUSDT.zip")
    with pytest.raises(ValueError, match="malformed"):
        runner.parse_checksum_text("not-a-checksum", "BTCUSDT.zip")


def test_valid_official_shaped_archive_extracts_exact_target_open(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    path = tmp_path / "valid.zip"
    digest = write_archive(path, archive_bytes(target, kline_rows(target)))

    summary, price = inspect(path, target, digest)

    assert summary.member_name == target.expected_member_name
    assert summary.data_row_count == 24
    assert summary.target_open_occurrence_count == 1
    assert summary.duplicate_open_time_count == 0
    assert summary.non_increasing_open_time_count == 0
    assert summary.outside_target_date_count == 0
    assert price == "123.45000000"


def test_archive_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    path = tmp_path / "mismatch.zip"
    write_archive(path, archive_bytes(target, kline_rows(target)))
    with pytest.raises(ValueError, match="published SHA-256"):
        inspect(path, target, "0" * 64)


def test_archive_rejects_unsafe_or_multiple_members(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    unsafe = tmp_path / "unsafe.zip"
    digest = write_archive(
        unsafe,
        archive_bytes(target, kline_rows(target), member=f"../{target.expected_member_name}"),
    )
    with pytest.raises(ValueError, match="safe expected CSV"):
        inspect(unsafe, target, digest)

    multiple = tmp_path / "multiple.zip"
    with zipfile.ZipFile(multiple, "w") as archive:
        archive.writestr(target.expected_member_name, "x")
        archive.writestr("extra.csv", "x")
    with pytest.raises(ValueError, match="exactly one member"):
        inspect(multiple, target, runner.file_sha256(multiple))


def test_archive_rejects_wrong_kline_width(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    rows = kline_rows(target)
    rows[3] = rows[3][:-1]
    path = tmp_path / "width.zip"
    digest = write_archive(path, archive_bytes(target, rows))
    with pytest.raises(ValueError, match="exactly 12 fields"):
        inspect(path, target, digest)


@pytest.mark.parametrize("defect", ["duplicate", "outside", "missing_target"])
def test_archive_rejects_time_integrity_defects(tmp_path: Path, defect: str) -> None:
    target = load_protocol().targets[0]
    rows = kline_rows(target)
    if defect == "duplicate":
        rows[4][0] = rows[3][0]
    elif defect == "outside":
        rows[-1][0] = str(target.activation_open_time_ms + 86_400_000)
    else:
        rows = rows[1:]
    path = tmp_path / f"{defect}.zip"
    digest = write_archive(path, archive_bytes(target, rows))
    with pytest.raises(ValueError):
        inspect(path, target, digest)


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity", "not-a-number"])
def test_archive_rejects_nonpositive_or_nonfinite_target_price(
    tmp_path: Path,
    price: str,
) -> None:
    target = load_protocol().targets[0]
    path = tmp_path / "price.zip"
    digest = write_archive(path, archive_bytes(target, kline_rows(target, price=price)))
    with pytest.raises(ValueError, match="price"):
        inspect(path, target, digest)


class FakeResponse:
    def __init__(self, url: str, payload: bytes) -> None:
        self.status = 200
        self._url = url
        self._payload = io.BytesIO(payload)
        self.headers = {"Content-Type": "application/octet-stream"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, size: int) -> bytes:
        return self._payload.read(size)


class FakeOpener:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def open(self, request, timeout: int) -> FakeResponse:
        assert timeout == 60
        return FakeResponse(request.full_url, self._payload)


def test_resource_attempt_is_atomic_and_hash_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = load_protocol()
    target = protocol.targets[0]
    payload = b"a" * 64 + b"  BTCUSDT-1h-2017-09-15.zip\n"
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)

    attempt = runner.execute_resource_attempt(
        target,
        "CHECKSUM",
        1,
        protocol=protocol,
        opener_factory=lambda: FakeOpener(payload),
    )

    destination = tmp_path / target.checksum_path
    assert attempt.outcome == "COMPLETE"
    assert attempt.body_sha256 == sha256(payload).hexdigest()
    assert destination.read_bytes() == payload
    assert not runner.part_path(target, "CHECKSUM", 1).exists()
    assert runner.project_path(attempt.request_marker_path).is_file()
    assert runner.project_path(attempt.response_marker_path).is_file()


def test_resource_attempt_enforces_total_network_byte_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = load_protocol()
    target = protocol.targets[0]
    payload = b"checksum"
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)

    attempt = runner.execute_resource_attempt(
        target,
        "CHECKSUM",
        1,
        protocol=protocol,
        network_body_bytes_before=protocol.maximum_total_payload_bytes - 1,
        opener_factory=lambda: FakeOpener(payload),
    )

    assert attempt.outcome == "PERMANENT_FAILURE"
    assert "total byte budget" in (attempt.error_message or "")
    assert not (tmp_path / target.checksum_path).exists()


def test_interrupted_attempt_recovers_without_reusing_partial_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = load_protocol()
    target = protocol.targets[0]
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    request_path = runner.marker_path(target, "ARCHIVE", 1, "request")
    runner.write_json_atomic(
        request_path,
        {
            "schema_version": "aurex-s1-btc-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "resource_kind": "ARCHIVE",
            "attempt": 1,
            "method": "GET",
            "url": target.archive_url,
            "range": None,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )
    partial = runner.part_path(target, "ARCHIVE", 1)
    partial.write_bytes(b"partial")

    attempts = runner.existing_attempts(target, "ARCHIVE", protocol=protocol)

    assert len(attempts) == 1
    assert attempts[0].outcome == "TRANSIENT_FAILURE"
    assert not partial.exists()


def test_execution_contract_cannot_encode_returns_or_order_authority() -> None:
    protocol = load_protocol()
    payload = {
        "frozen_at": datetime.now(UTC),
        "builder_contract_hash": "1" * 64,
        "protocol_file_sha256": "2" * 64,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": "3" * 64,
        "protocol_audit_evidence_hash": "4" * 64,
        "runner_contract_hash": "5" * 64,
        "free_disk_bytes_observed": 250_000_000,
        "synthetic_test_ids": tuple(f"synthetic-{index}" for index in range(8)),
    }
    contract = runner.build_hashed(
        S1BtcSourceExecutionContract,
        "contract_evidence_hash",
        **payload,
    )
    dumped = json.loads(contract.model_dump_json())
    assert dumped["authorizes_network_acquisition"] is True
    assert dumped["authorizes_execution_price_values_only"] is True
    assert dumped["authorizes_return_testing"] is False
    assert dumped["authorizes_candidate_outcome"] is False
    assert dumped["authorizes_testnet_strategy_orders"] is False
    assert dumped["authorizes_live"] is False
