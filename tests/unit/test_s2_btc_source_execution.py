from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_btc_source_execution import (
    S2BtcSourceExecutionContract,
)
from scripts import run_s2_btc_source_acquisition as runner
from scripts.freeze_s2_btc_source_acquisition_protocol import build_protocol

FROZEN_AT = datetime(2026, 8, 30, 20, 0, tzinfo=UTC)


def build_contract() -> S2BtcSourceExecutionContract:
    return runner.build_hashed(
        S2BtcSourceExecutionContract,
        "contract_evidence_hash",
        frozen_at=FROZEN_AT,
        builder_contract_hash="1" * 64,
        protocol_file_sha256="2" * 64,
        protocol_evidence_hash="3" * 64,
        protocol_audit_file_sha256="4" * 64,
        protocol_audit_evidence_hash="5" * 64,
        runner_contract_hash="6" * 64,
        free_disk_bytes_observed=1_000_000_000,
        synthetic_test_ids=tuple(f"synthetic-{index:02d}" for index in range(1, 13)),
    )


def kline_rows(target, *, price: str = "100.25", include_midnight: bool = True) -> list[list[str]]:
    rows = []
    start_hour = 0 if include_midnight else 1
    for hour in range(start_hour, 24):
        open_time = target.activation_open_time_ms + hour * 3_600_000
        rows.append(
            [
                str(open_time),
                price,
                price,
                price,
                price,
                "1",
                str(open_time + 3_599_999),
                "1",
                "1",
                "1",
                "1",
                "0",
            ]
        )
    return rows


def write_archive(
    root: Path,
    target,
    *,
    rows: list[list[str]] | None = None,
    member_name: str | None = None,
    extra_member: bool = False,
) -> tuple[Path, str]:
    archive_path = root / target.archive_path
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(row) for row in (rows or kline_rows(target))]
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name or target.expected_member_name, "\n".join(lines) + "\n")
        if extra_member:
            archive.writestr("extra.csv", "x\n")
    return archive_path, runner.file_sha256(archive_path)


@pytest.fixture
def source_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    protocol = build_protocol(frozen_at=FROZEN_AT)
    return protocol, protocol.targets[0], build_contract(), tmp_path


def test_frozen_target_allowlist_rejects_wrong_evidence_root(source_boundary) -> None:
    protocol, target, _, _ = source_boundary
    payload = target.model_dump(mode="json")
    payload["archive_path"] = payload["archive_path"].replace(
        "s2_btcusdt_monday_1h_v1", "wrong"
    )

    with pytest.raises(ValidationError, match="archive path changed"):
        type(target).model_validate(payload)
    runner.validate_target(protocol.targets[0])


def test_checksum_filename_binding() -> None:
    digest = "a" * 64

    assert (
        runner.parse_checksum_text(
            f"{digest}  BTCUSDT-1h-2017-10-16.zip\n",
            "BTCUSDT-1h-2017-10-16.zip",
        )
        == digest
    )
    with pytest.raises(ValueError, match="malformed"):
        runner.parse_checksum_text(f"{digest}  other.zip\n", "BTCUSDT-1h-2017-10-16.zip")


def test_official_shaped_archive_extracts_exact_midnight_open(source_boundary) -> None:
    _, target, contract, root = source_boundary
    archive_path, digest = write_archive(root, target)

    summary, price = runner.inspect_archive(
        archive_path,
        target=target,
        published_archive_sha256=digest,
        maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
    )

    assert summary.data_row_count == 24
    assert summary.target_open_occurrence_count == 1
    assert summary.first_open_time_ms == target.activation_open_time_ms
    assert price == "100.25"


def test_published_checksum_mismatch_is_rejected(source_boundary) -> None:
    _, target, contract, root = source_boundary
    archive_path, _ = write_archive(root, target)

    with pytest.raises(ValueError, match="published SHA-256"):
        runner.inspect_archive(
            archive_path,
            target=target,
            published_archive_sha256="0" * 64,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )


@pytest.mark.parametrize(
    ("member_name", "extra_member", "message"),
    (("../escape.csv", False, "safe expected CSV"), (None, True, "exactly one member")),
)
def test_unsafe_or_multiple_zip_members_are_rejected(
    source_boundary, member_name, extra_member, message
) -> None:
    _, target, contract, root = source_boundary
    archive_path, digest = write_archive(
        root, target, member_name=member_name, extra_member=extra_member
    )

    with pytest.raises(ValueError, match=message):
        runner.inspect_archive(
            archive_path,
            target=target,
            published_archive_sha256=digest,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )


def test_twelve_column_kline_enforcement(source_boundary) -> None:
    _, target, contract, root = source_boundary
    rows = kline_rows(target)
    rows[0] = rows[0][:-1]
    archive_path, digest = write_archive(root, target, rows=rows)

    with pytest.raises(ValueError, match="exactly 12 fields"):
        runner.inspect_archive(
            archive_path,
            target=target,
            published_archive_sha256=digest,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )


@pytest.mark.parametrize(
    ("row_mutator", "message"),
    (
        (lambda rows, target: rows.insert(1, rows[0].copy()), "duplicate open times"),
        (lambda rows, target: rows.reverse(), "not strictly increasing"),
        (
            lambda rows, target: rows.__setitem__(
                0, [str(target.activation_open_time_ms - 1)] + rows[0][1:]
            ),
            "outside its target date",
        ),
    ),
)
def test_open_time_integrity_is_enforced(source_boundary, row_mutator, message) -> None:
    _, target, contract, root = source_boundary
    rows = kline_rows(target)
    row_mutator(rows, target)
    archive_path, digest = write_archive(root, target, rows=rows)

    with pytest.raises(ValueError, match=message):
        runner.inspect_archive(
            archive_path,
            target=target,
            published_archive_sha256=digest,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )


def test_missing_exact_midnight_open_is_not_substituted(source_boundary) -> None:
    _, target, contract, root = source_boundary
    archive_path, digest = write_archive(
        root, target, rows=kline_rows(target, include_midnight=False)
    )

    with pytest.raises(ValueError, match="exactly one target open"):
        runner.inspect_archive(
            archive_path,
            target=target,
            published_archive_sha256=digest,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )


@pytest.mark.parametrize("price", ("0", "-1", "NaN", "Infinity", "not-a-number"))
def test_target_price_must_be_positive_and_finite(source_boundary, price) -> None:
    _, target, contract, root = source_boundary
    archive_path, digest = write_archive(root, target, rows=kline_rows(target, price=price))

    with pytest.raises(ValueError, match="decimal|positive and finite"):
        runner.inspect_archive(
            archive_path,
            target=target,
            published_archive_sha256=digest,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )


def test_hash_bound_local_reuse_builds_one_price_row(source_boundary) -> None:
    protocol, target, contract, root = source_boundary
    archive_path, digest = write_archive(root, target)
    checksum_path = root / target.checksum_path
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")

    evidence = runner.acquire_target(target, protocol=protocol, contract=contract)

    assert evidence.outcome == "COMPLETE"
    assert evidence.source_mode == "LOCAL_REUSE"
    assert evidence.attempts == ()
    assert evidence.price_row is not None
    assert evidence.price_row.measurement_sequence == 8
    assert evidence.archive_file_sha256 == digest


class FakeResponse:
    def __init__(self, *, url: str, body: bytes, final_url: str | None = None):
        self.status = 200
        self.url = url
        self.final_url = final_url or url
        self.body = body
        self.offset = 0
        self.headers = {"Content-Type": "application/octet-stream"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self) -> str:
        return self.final_url

    def read(self, size: int) -> bytes:
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class FakeOpener:
    def __init__(self, response: FakeResponse):
        self.response = response

    def open(self, request, timeout):
        return self.response


def test_atomic_resource_attempt_records_hash_bound_markers(source_boundary) -> None:
    protocol, target, _, _ = source_boundary
    body = b"a" * 64 + b"  BTCUSDT-1h-2017-10-16.zip\n"
    response = FakeResponse(url=target.checksum_url, body=body)

    attempt = runner.execute_resource_attempt(
        target,
        "CHECKSUM",
        1,
        protocol=protocol,
        opener_factory=lambda: FakeOpener(response),
    )

    assert attempt.outcome == "COMPLETE"
    assert attempt.bytes_received == len(body)
    assert runner.project_path(attempt.request_marker_path).is_file()
    assert runner.project_path(attempt.response_marker_path).is_file()
    assert runner.resource_destination(target, "CHECKSUM").read_bytes() == body


def test_source_identity_drift_fails_permanently(source_boundary) -> None:
    protocol, target, _, _ = source_boundary
    response = FakeResponse(
        url=target.checksum_url,
        body=b"x",
        final_url="https://example.com/changed",
    )

    attempt = runner.execute_resource_attempt(
        target,
        "CHECKSUM",
        1,
        protocol=protocol,
        opener_factory=lambda: FakeOpener(response),
    )

    assert attempt.outcome == "PERMANENT_FAILURE"
    assert attempt.error_type == "ValueError"
    assert not runner.resource_destination(target, "CHECKSUM").exists()


def test_aggregate_network_byte_budget_is_enforced(source_boundary) -> None:
    protocol, target, _, _ = source_boundary
    response = FakeResponse(url=target.checksum_url, body=b"too-large-for-remaining-budget")

    attempt = runner.execute_resource_attempt(
        target,
        "CHECKSUM",
        1,
        protocol=protocol,
        network_body_bytes_before=protocol.maximum_total_payload_bytes - 1,
        opener_factory=lambda: FakeOpener(response),
    )

    assert attempt.outcome == "PERMANENT_FAILURE"
    assert "total byte budget" in (attempt.error_message or "")


def test_interrupted_partial_is_terminally_marked_before_retry(source_boundary) -> None:
    protocol, target, _, _ = source_boundary
    request_path = runner.marker_path(target, "CHECKSUM", 1, "request")
    runner.write_json_atomic(
        request_path,
        {
            "schema_version": "aurex-s2-btc-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "resource_kind": "CHECKSUM",
            "attempt": 1,
            "method": "GET",
            "url": target.checksum_url,
            "range": None,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )
    partial = runner.part_path(target, "CHECKSUM", 1)
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(b"partial")

    attempts = runner.existing_attempts(target, "CHECKSUM", protocol=protocol)

    assert len(attempts) == 1
    assert attempts[0].outcome == "TRANSIENT_FAILURE"
    assert attempts[0].error_type == "InterruptedAttempt"
    assert attempts[0].bytes_received == 7
    assert not partial.exists()


def test_execution_contract_rejects_authority_escalation() -> None:
    payload = build_contract().model_dump(mode="json")
    payload["authorizes_return_testing"] = True

    with pytest.raises(ValidationError):
        S2BtcSourceExecutionContract.model_validate(payload)


def test_dataset_bytes_are_deterministic_and_hash_linked(source_boundary) -> None:
    protocol, target, contract, root = source_boundary
    archive_path, digest = write_archive(root, target)
    (root / target.checksum_path).write_text(
        f"{digest}  {archive_path.name}\n", encoding="utf-8"
    )
    evidence = runner.acquire_target(target, protocol=protocol, contract=contract)
    row = evidence.price_row
    assert row is not None

    first = runner.dataset_bytes((row,))
    second = runner.dataset_bytes((row,))

    assert first == second
    decoded = json.loads(first)
    assert decoded["price_evidence_hash"] == row.price_evidence_hash
