from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    PeriodicFlowDevelopmentTarget,
)
from scripts.run_periodic_flow_full_development_acquisition import (
    AcquisitionFailure,
    target_archive_path,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (
    _write_request_marker_v3,
    _write_response_marker_v3,
    ensure_network_archive_v3,
    reconcile_target_markers_v3,
)


class DiskUsage:
    total = 200_000_000_000
    used = 0
    free = 200_000_000_000


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        payload: bytes,
        status: int,
        headers: dict[str, str],
        fail_after_bytes: int | None = None,
    ):
        self.url = url
        self.payload = payload
        self.status = status
        self.headers = headers
        self.fail_after_bytes = fail_after_bytes
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001
        return False

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def read1(self, size: int) -> bytes:
        if self.fail_after_bytes is not None and self.offset >= self.fail_after_bytes:
            raise TimeoutError("synthetic idle timeout")
        limit = len(self.payload)
        if self.fail_after_bytes is not None:
            limit = min(limit, self.fail_after_bytes)
        chunk = self.payload[self.offset : min(self.offset + size, limit)]
        self.offset += len(chunk)
        return chunk


class FakeOpener:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.requests = []

    def open(self, request, timeout):  # noqa: ANN001, ARG002
        self.requests.append(request)
        return self.responses.pop(0)


def _target(payload: bytes) -> PeriodicFlowDevelopmentTarget:
    url = (
        "https://data.binance.vision/data/futures/um/monthly/trades/BTCUSDT/"
        "BTCUSDT-trades-2023-01.zip"
    )
    return PeriodicFlowDevelopmentTarget.model_construct(
        product="USD_M_PERPETUAL",
        family="trades",
        symbol="BTCUSDT",
        month="2023-01",
        partition_role="DEVELOPMENT",
        archive_url=url,
        published_archive_sha256=hashlib.sha256(payload).hexdigest(),
        expected_member_name="BTCUSDT-trades-2023-01.csv",
        expected_columns=(
            "trade_id",
            "price",
            "quantity",
            "quote_quantity",
            "timestamp",
            "buyer_was_maker",
        ),
        expected_timestamp_unit="MILLISECONDS",
        reuse_candidate_path=None,
        reuse_candidate_file_sha256=None,
        reuse_revalidation_required=True,
        member_policy="EXACT_EXPECTED_MEMBER_ONLY",
    )


def _context(*, attempts: int = 12):
    protocol = SimpleNamespace(
        request_marker_schema="aurex-q1-periodic-flow-successor-http-request-v3",
        response_marker_schema="aurex-q1-periodic-flow-successor-http-response-v3",
        protocol_evidence_hash="1" * 64,
        amendment_evidence_hash="2" * 64,
        bootstrap_target_key="2020-05|USD_M_PERPETUAL",
        bootstrap_expected_total_bytes=370_923_781,
        maximum_get_attempts_per_target=attempts,
        maximum_payload_get_attempts=576,
        maximum_archive_bytes=5_000_000_000,
        maximum_new_archive_bytes_total=100_000_000_000,
        minimum_free_disk_bytes_after_acquisition=20_000_000_000,
        connect_timeout_seconds=300,
        idle_read_timeout_seconds=300,
        total_attempt_deadline_seconds=21_600,
        stream_chunk_bytes=4,
        retry_delays_seconds=tuple(0 for _ in range(max(0, attempts - 1))),
    )
    contract = SimpleNamespace(contract_evidence_hash="3" * 64)
    return SimpleNamespace(protocol=protocol, contract=contract)


def test_timeout_preserves_partial_then_exact_range_resume(tmp_path, monkeypatch) -> None:
    payload = b"0123456789abcdef"
    target = _target(payload)
    first = FakeResponse(
        url=target.archive_url,
        payload=payload,
        status=200,
        headers={"Content-Length": str(len(payload))},
        fail_after_bytes=4,
    )
    second = FakeResponse(
        url=target.archive_url,
        payload=payload[4:],
        status=206,
        headers={
            "Content-Length": str(len(payload) - 4),
            "Content-Range": f"bytes 4-{len(payload) - 1}/{len(payload)}",
        },
    )
    opener = FakeOpener([first, second])
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.urllib.request.build_opener",
        lambda *handlers: opener,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.shutil.disk_usage",
        lambda path: DiskUsage(),
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.time.sleep",
        lambda seconds: None,
    )

    path, attempts = ensure_network_archive_v3(
        root=tmp_path,
        target=target,
        context=_context(),
    )

    assert attempts == 2
    assert path.read_bytes() == payload
    assert opener.requests[0].get_header("Range") is None
    assert opener.requests[1].get_header("Range") == "bytes=4-"
    first_marker = json.loads(
        path.with_name(f"{path.name}.get.1.response.json").read_text()
    )
    second_marker = json.loads(
        path.with_name(f"{path.name}.get.2.response.json").read_text()
    )
    assert first_marker["failure_class"] == "TIMEOUT"
    assert first_marker["exception_type"] == "TimeoutError"
    assert first_marker["partial_bytes_after_attempt"] == 4
    assert second_marker["outcome"] == "PASS"


def test_resume_hard_stops_when_server_ignores_range(tmp_path, monkeypatch) -> None:
    payload = b"0123456789abcdef"
    target = _target(payload)
    first = FakeResponse(
        url=target.archive_url,
        payload=payload,
        status=200,
        headers={"Content-Length": str(len(payload))},
        fail_after_bytes=4,
    )
    ignored = FakeResponse(
        url=target.archive_url,
        payload=payload,
        status=200,
        headers={"Content-Length": str(len(payload))},
    )
    opener = FakeOpener([first, ignored])
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.urllib.request.build_opener",
        lambda *handlers: opener,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.shutil.disk_usage",
        lambda path: DiskUsage(),
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.time.sleep",
        lambda seconds: None,
    )

    with pytest.raises(AcquisitionFailure, match="not honored"):
        ensure_network_archive_v3(
            root=tmp_path,
            target=target,
            context=_context(),
        )

    partial = target_archive_path(tmp_path, target).with_suffix(".zip.part")
    assert partial.read_bytes() == payload[:4]
    marker = json.loads(
        partial.with_name(
            "BTCUSDT-trades-2023-01.zip.get.2.response.json"
        ).read_text()
    )
    assert marker["outcome"] == "INTEGRITY_FAIL"
    assert marker["failure_class"] == "INTEGRITY_OR_IDENTITY_FAILURE"


def test_interrupted_request_is_reconciled_without_deleting_partial(tmp_path) -> None:
    payload = b"0123456789abcdef"
    target = _target(payload)
    context = _context()
    partial = target_archive_path(tmp_path, target).with_suffix(".zip.part")
    partial.parent.mkdir(parents=True)
    partial.write_bytes(payload[:6])
    _write_request_marker_v3(
        root=tmp_path,
        target=target,
        context=context,
        attempt=1,
        range_start=0,
    )

    attempts = reconcile_target_markers_v3(
        root=tmp_path,
        target=target,
        context=context,
    )

    assert attempts == 1
    assert partial.read_bytes() == payload[:6]
    marker = json.loads(
        partial.with_name(
            "BTCUSDT-trades-2023-01.zip.get.1.response.json"
        ).read_text()
    )
    assert marker["outcome"] == "INTERRUPTED_RESUMABLE"
    assert marker["bytes_received"] == 6
    assert marker["partial_bytes_after_attempt"] == 6


def test_pass_marker_before_rename_recovers_without_network(tmp_path, monkeypatch) -> None:
    payload = b"0123456789abcdef"
    target = _target(payload)
    context = _context()
    partial = target_archive_path(tmp_path, target).with_suffix(".zip.part")
    partial.parent.mkdir(parents=True)
    partial.write_bytes(payload)
    _write_request_marker_v3(
        root=tmp_path,
        target=target,
        context=context,
        attempt=1,
        range_start=0,
    )
    _write_response_marker_v3(
        root=tmp_path,
        target=target,
        context=context,
        attempt=1,
        status=200,
        final_url=target.archive_url,
        response_content_length=len(payload),
        expected_total_bytes=len(payload),
        content_range=None,
        bytes_received=len(payload),
        partial_bytes_after_attempt=len(payload),
        outcome="PASS",
        failure_class="NONE",
        error=None,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.urllib.request.build_opener",
        lambda *handlers: pytest.fail("local PASS recovery must not open the network"),
    )

    path, attempts = ensure_network_archive_v3(
        root=tmp_path,
        target=target,
        context=context,
    )

    assert attempts == 1
    assert path.read_bytes() == payload
    assert not partial.exists()
