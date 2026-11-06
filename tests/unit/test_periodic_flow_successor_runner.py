from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    PeriodicFlowDevelopmentTarget,
)
from aurex.backtest_engine.periodic_flow_successor_runner import (
    PeriodicFlowExcludedMonthEvidence,
    audit_hash,
    build_acquisition_result,
)
from scripts.freeze_periodic_flow_successor_acquisition_protocol import (
    authoritative_protocol,
)
from scripts.freeze_periodic_flow_successor_acquisition_protocol import (
    parse_args as parse_protocol_args,
)
from scripts.run_periodic_flow_successor_acquisition import (
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_V1_EXECUTION_CONTRACT,
    DEFAULT_V1_RESULT,
    ProtocolTransportAdapter,
    ensure_network_archive_v2,
    load_context,
)


class FakeResponse:
    def __init__(self, *, url: str, payload: bytes):
        self.url = url
        self.payload = payload
        self.offset = 0
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001
        return False

    def getcode(self) -> int:
        return 200

    def geturl(self) -> str:
        return self.url

    def read(self, size: int) -> bytes:
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def read1(self, size: int) -> bytes:
        return self.read(size)


class FakeOpener:
    def __init__(self, response: FakeResponse):
        self.response = response

    def open(self, request, timeout):  # noqa: ANN001, ARG002
        return self.response


class DiskUsage:
    total = 200_000_000_000
    used = 0
    free = 200_000_000_000


def test_transport_adapter_preserves_inherited_v1_limit_names(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["freeze_periodic_flow_successor_acquisition_protocol.py", "--check"],
    )
    args = parse_protocol_args()
    protocol = authoritative_protocol(
        args=args,
        frozen_at=datetime(2026, 8, 10, 20, tzinfo=UTC),
    )
    adapter = ProtocolTransportAdapter(protocol)

    assert adapter.maximum_archive_bytes_each == 5_000_000_000
    assert adapter.maximum_member_uncompressed_bytes_each == 30_000_000_000
    assert adapter.maximum_attempts_per_network_target == 3
    assert adapter.maximum_payload_get_attempts == 144
    assert adapter.retry_backoff_seconds == (5, 20)
    assert adapter.protocol_evidence_hash == protocol.protocol_evidence_hash


def test_structural_exclusion_is_month_scoped_and_no_outcome() -> None:
    exclusion = PeriodicFlowExcludedMonthEvidence(
        month="2023-02",
        failed_stage="SPOT_ARCHIVE",
        failed_product="SPOT",
        reason_codes=("EVENT_GAP_EXCEEDS_15_MINUTES",),
        archive_sha256="1" * 64,
        source_mode="NETWORK_ACQUIRED",
    )

    assert exclusion.month == "2023-02"
    assert exclusion.failed_product == "SPOT"


def test_result_requires_all_source_sufficiency_dimensions() -> None:
    base = {
        "generated_at": datetime(2026, 8, 10, 20, tzinfo=UTC),
        "protocol_file_sha256": "1" * 64,
        "protocol_evidence_hash": "2" * 64,
        "execution_contract_file_sha256": "3" * 64,
        "execution_contract_evidence_hash": "4" * 64,
        "runner_source_hash": "5" * 64,
        "checkpoint_file_sha256": "6" * 64,
        "checkpoint_evidence_hash": "7" * 64,
        "inspected_archive_count": 74,
        "qualified_paired_month_count": 30,
        "excluded_month_count": 7,
        "completed_month_count": 37,
        "qualified_months_by_year": {"2020": 6, "2021": 6, "2022": 12, "2023": 6},
        "qualified_quarter_count": 16,
        "request_marker_count": 48,
        "cumulative_payload_bytes_received": 1,
        "total_new_archive_bytes": 1,
        "hard_failure_target_key": None,
        "hard_failure_reason": None,
        "limitations": tuple(str(index) for index in range(10)),
    }
    passed = build_acquisition_result(**base)
    failed = build_acquisition_result(**{**base, "qualified_quarter_count": 15})

    assert audit_hash(passed, "result_evidence_hash")
    assert passed.decision == (
        "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
    )
    assert passed.orders_submitted == 0
    assert failed.decision == "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED"


def test_inherited_transport_runs_through_successor_adapter(
    tmp_path, monkeypatch
) -> None:
    args = argparse.Namespace(
        protocol=DEFAULT_PROTOCOL,
        protocol_audit=DEFAULT_PROTOCOL_AUDIT,
        execution_contract=DEFAULT_EXECUTION_CONTRACT,
        execution_contract_audit=DEFAULT_EXECUTION_CONTRACT_AUDIT,
        v1_execution_contract=DEFAULT_V1_EXECUTION_CONTRACT,
        v1_result=DEFAULT_V1_RESULT,
    )
    context = load_context(args)
    payload = b"successor-transport-smoke"
    url = (
        "https://data.binance.vision/data/futures/um/monthly/trades/BTCUSDT/"
        "BTCUSDT-trades-2023-01.zip"
    )
    target = PeriodicFlowDevelopmentTarget.model_construct(
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
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.urllib.request.build_opener",
        lambda *handlers: FakeOpener(FakeResponse(url=url, payload=payload)),
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.shutil.disk_usage",
        lambda path: DiskUsage(),
    )

    path, attempts = ensure_network_archive_v2(
        root=tmp_path,
        target=target,
        context=context,
    )

    assert attempts == 1
    assert path.read_bytes() == payload
