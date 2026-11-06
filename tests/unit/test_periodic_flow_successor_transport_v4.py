from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    PeriodicFlowDevelopmentTarget,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import ensure_network_archive_v3
from scripts.run_periodic_flow_successor_acquisition_v4 import (
    ensure_bootstrap_partial_v4,
)


class DiskUsage:
    total = 200_000_000_000
    used = 0
    free = 200_000_000_000


class FakeResponse:
    def __init__(self, *, url: str, payload: bytes, status: int, headers: dict):
        self.url = url
        self.payload = payload
        self.status = status
        self.headers = headers
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001
        return False

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def read1(self, size: int) -> bytes:
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class FakeOpener:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.requests = []

    def open(self, request, timeout):  # noqa: ANN001, ARG002
        self.requests.append(request)
        return self.response


def _target(payload: bytes) -> PeriodicFlowDevelopmentTarget:
    return PeriodicFlowDevelopmentTarget.model_construct(
        product="USD_M_PERPETUAL",
        family="trades",
        symbol="BTCUSDT",
        month="2020-08",
        partition_role="DEVELOPMENT",
        archive_url="https://data.binance.vision/archive.zip",
        published_archive_sha256=hashlib.sha256(payload).hexdigest(),
        expected_member_name="BTCUSDT-trades-2020-08.csv",
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


def _context(*, source, source_hash: str, source_bytes: int, total_bytes: int):
    protocol = SimpleNamespace(
        request_marker_schema="aurex-q1-periodic-flow-successor-http-request-v4",
        response_marker_schema="aurex-q1-periodic-flow-successor-http-response-v4",
        protocol_evidence_hash="1" * 64,
        amendment_evidence_hash="2" * 64,
        continuation_bootstrap_target_key="2020-08|USD_M_PERPETUAL",
        bootstrap_target_key="V4_BOOTSTRAP_ALREADY_MANAGED",
        bootstrap_partial_path=str(source),
        bootstrap_partial_file_sha256=source_hash,
        bootstrap_partial_bytes=source_bytes,
        bootstrap_expected_total_bytes=total_bytes,
        maximum_get_attempts_per_target=12,
        maximum_payload_get_attempts=576,
        maximum_archive_bytes=5_000_000_000,
        maximum_new_archive_bytes_total=100_000_000_000,
        minimum_free_disk_bytes_after_acquisition=20_000_000_000,
        connect_timeout_seconds=300,
        idle_read_timeout_seconds=300,
        total_attempt_deadline_seconds=21_600,
        stream_chunk_bytes=4,
        retry_delays_seconds=tuple(0 for _ in range(11)),
    )
    return SimpleNamespace(
        protocol=protocol,
        contract=SimpleNamespace(contract_evidence_hash="3" * 64),
    )


def test_v4_bootstrap_copy_then_strict_range_resume(tmp_path, monkeypatch) -> None:
    payload = b"0123456789abcdef"
    source = tmp_path / "source.part"
    source.write_bytes(payload[:4])
    source_hash = hashlib.sha256(payload[:4]).hexdigest()
    target = _target(payload)
    context = _context(
        source=source,
        source_hash=source_hash,
        source_bytes=4,
        total_bytes=len(payload),
    )
    args = SimpleNamespace(acquisition_root=tmp_path / "v4")

    partial = ensure_bootstrap_partial_v4(args=args, target=target, context=context)

    assert partial.read_bytes() == payload[:4]
    assert source.read_bytes() == payload[:4]
    response = FakeResponse(
        url=target.archive_url,
        payload=payload[4:],
        status=206,
        headers={
            "Content-Length": str(len(payload) - 4),
            "Content-Range": f"bytes 4-{len(payload) - 1}/{len(payload)}",
        },
    )
    opener = FakeOpener(response)
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.urllib.request.build_opener",
        lambda *handlers: opener,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v3.shutil.disk_usage",
        lambda path: DiskUsage(),
    )

    archive, attempts = ensure_network_archive_v3(
        root=args.acquisition_root,
        target=target,
        context=context,
    )

    assert attempts == 1
    assert archive.read_bytes() == payload
    assert opener.requests[0].get_header("Range") == "bytes=4-"
    request_marker = json.loads(
        archive.with_name(f"{archive.name}.get.1.request.json").read_text()
    )
    response_marker = json.loads(
        archive.with_name(f"{archive.name}.get.1.response.json").read_text()
    )
    assert request_marker["schema_version"].endswith("request-v4")
    assert response_marker["schema_version"].endswith("response-v4")
    assert request_marker["transport_amendment_evidence_hash"] == "2" * 64
    assert response_marker["execution_contract_evidence_hash"] == "3" * 64
