import hashlib
import json
import urllib.error
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    SPOT_COLUMNS,
    PeriodicFlowDevelopmentTarget,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (
    PeriodicFlowExecutionContract,
    audit_execution_contract,
)
from scripts.freeze_periodic_flow_full_development_acquisition import (
    authoritative_protocol,
)
from scripts.freeze_periodic_flow_full_development_execution_contract import (
    authoritative_contract,
)
from scripts.run_periodic_flow_full_development_acquisition import (
    KNOWN_DUPLICATE_MEMBER,
    AcquisitionFailure,
    LoadedContext,
    ensure_network_archive,
    inspect_archive,
    marker_path,
    reconcile_target_markers,
    select_zip_member,
    target_archive_path,
    write_request_marker,
    write_response_marker,
)


class FakeResponse:
    def __init__(self, *, url: str, payload: bytes, content_length: str | None = None):
        self.url = url
        self.payload = payload
        self.offset = 0
        self.headers = {
            "Content-Length": str(len(payload)) if content_length is None else content_length
        }

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


class FakeOpener:
    def __init__(self, outcomes: list):
        self.outcomes = outcomes
        self.requests = []

    def open(self, request, timeout):  # noqa: ANN001, ARG002
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class DiskUsage:
    total = 200_000_000_000
    used = 0
    free = 200_000_000_000


def context() -> LoadedContext:
    protocol = authoritative_protocol(
        frozen_at=datetime(2026, 8, 7, 15, tzinfo=UTC)
    )
    contract = authoritative_contract(
        frozen_at=datetime(2026, 8, 8, 12, tzinfo=UTC)
    )
    return LoadedContext(
        protocol=protocol,
        protocol_audit=None,  # type: ignore[arg-type]
        contract=contract,
        contract_audit=None,  # type: ignore[arg-type]
    )


def synthetic_spot_target(
    *,
    month: str,
    digest: str,
    member_policy: str = "EXACT_EXPECTED_MEMBER_ONLY",
) -> PeriodicFlowDevelopmentTarget:
    return PeriodicFlowDevelopmentTarget.model_construct(
        product="SPOT",
        family="aggTrades",
        symbol="BTCUSDT",
        month=month,
        partition_role="DEVELOPMENT",
        archive_url=(
            "https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT/"
            f"BTCUSDT-aggTrades-{month}.zip"
        ),
        published_archive_sha256=digest,
        expected_member_name=f"BTCUSDT-aggTrades-{month}.csv",
        expected_columns=SPOT_COLUMNS,
        expected_timestamp_unit="MILLISECONDS",
        reuse_candidate_path=None,
        reuse_candidate_file_sha256=None,
        reuse_revalidation_required=True,
        member_policy=member_policy,
    )


def write_spot_zip(path: Path, month: str, *, member_name: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = member_name or f"BTCUSDT-aggTrades-{month}.csv"
    payload = (
        "1,NOT_A_PRICE,NOT_A_QUANTITY,10,10,1577836800000,true,IGNORED\n"
        "2,STILL_NOT_A_PRICE,STILL_NOT_A_QUANTITY,11,11,1577836860000,false,IGNORED\n"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, payload)


def test_execution_contract_is_exactly_no_outcome_and_no_trading() -> None:
    contract = context().contract

    assert audit_execution_contract(contract)
    assert contract.processing_order == "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_RAW"
    assert contract.head_requests_permitted is False
    assert contract.range_requests_permitted is False
    assert contract.redirects_permitted is False
    assert contract.price_or_quantity_parsing_permitted is False
    assert contract.feature_calculation_permitted is False
    assert contract.return_calculation_permitted is False
    assert contract.strategy_or_order_authority is False


def test_execution_contract_rejects_rehashed_transport_expansion() -> None:
    contract = context().contract
    payload = contract.model_dump()
    payload["head_requests_permitted"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowExecutionContract.model_validate(payload)


def test_structural_parser_never_requires_price_or_quantity_values(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "BTCUSDT-aggTrades-2020-01.zip"
    write_spot_zip(archive_path, "2020-01")
    target = synthetic_spot_target(
        month="2020-01",
        digest=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    )

    inspection = inspect_archive(
        target=target,
        archive_path=archive_path,
        evidence_root=tmp_path,
        protocol=context().protocol,
        source_mode="NETWORK_ACQUIRED",
        get_attempt_count=1,
    )

    assert inspection.evidence.row_count == 2
    assert inspection.evidence.buyer_maker_values_observed == (False, True)
    assert inspection.evidence.parsed_numeric_fields == (
        "aggregate_trade_id",
        "first_trade_id",
        "last_trade_id",
        "timestamp",
    )
    assert inspection.evidence.excluded_numeric_fields == (
        "price",
        "quantity",
        "quote_quantity",
    )
    assert inspection.evidence.archive_pass is False
    assert "ROW_COUNT_BELOW_100000" in inspection.evidence.reason_codes


def test_zip_path_traversal_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../BTCUSDT-aggTrades-2020-01.csv", "x")
    target = synthetic_spot_target(month="2020-01", digest="1" * 64)

    with zipfile.ZipFile(path) as archive:
        with pytest.raises(ValueError, match="unsafe"):
            select_zip_member(archive, target=target, protocol=context().protocol)


def test_special_duplicate_member_requires_byte_identity(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.zip"
    canonical = "BTCUSDT-aggTrades-2021-12.csv"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(canonical, "same\n")
        archive.writestr(KNOWN_DUPLICATE_MEMBER, "different\n")
    target = synthetic_spot_target(
        month="2021-12",
        digest="1" * 64,
        member_policy="TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL",
    )

    with zipfile.ZipFile(path) as archive:
        with pytest.raises(ValueError, match="not byte-identical"):
            select_zip_member(archive, target=target, protocol=context().protocol)


def test_interrupted_partial_is_counted_recorded_and_deleted(tmp_path: Path) -> None:
    loaded = context()
    target = synthetic_spot_target(month="2023-01", digest="1" * 64)
    write_request_marker(root=tmp_path, target=target, context=loaded, attempt=1)
    destination = target_archive_path(tmp_path, target)
    part = destination.with_name(f"{destination.name}.part")
    part.write_bytes(b"incomplete")

    attempts = reconcile_target_markers(
        root=tmp_path,
        target=target,
        context=loaded,
    )

    assert attempts == 1
    assert not part.exists()
    response = json.loads(
        marker_path(tmp_path, target, 1, "response").read_text(encoding="utf-8")
    )
    assert response["outcome"] == "ABANDONED_INTERRUPTED"
    assert response["bytes_received"] == len(b"incomplete")


def test_exact_completed_destination_can_recover_after_interruption(
    tmp_path: Path,
) -> None:
    loaded = context()
    destination_bytes = b"verified-complete-archive"
    digest = hashlib.sha256(destination_bytes).hexdigest()
    target = synthetic_spot_target(month="2023-01", digest=digest)
    write_request_marker(root=tmp_path, target=target, context=loaded, attempt=1)
    destination = target_archive_path(tmp_path, target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(destination_bytes)

    assert reconcile_target_markers(
        root=tmp_path,
        target=target,
        context=loaded,
    ) == 1
    response = json.loads(
        marker_path(tmp_path, target, 1, "response").read_text(encoding="utf-8")
    )
    assert response["outcome"] == (
        "RECOVERED_VERIFIED_ARCHIVE_AFTER_INTERRUPTION"
    )


def test_response_without_request_fails_closed(tmp_path: Path) -> None:
    loaded = context()
    target = synthetic_spot_target(month="2023-01", digest="1" * 64)
    write_response_marker(
        root=tmp_path,
        target=target,
        context=loaded,
        attempt=1,
        status=None,
        final_url=target.archive_url,
        content_length=None,
        content_encoding="identity",
        bytes_received=0,
        outcome="ABANDONED_INTERRUPTED",
    )

    with pytest.raises(ValueError, match="without a request"):
        reconcile_target_markers(root=tmp_path, target=target, context=loaded)


def test_transport_uses_only_identity_encoded_full_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = context()
    payload = b"complete-zip-payload"
    target = synthetic_spot_target(
        month="2023-01",
        digest=hashlib.sha256(payload).hexdigest(),
    )
    opener = FakeOpener([FakeResponse(url=target.archive_url, payload=payload)])
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.urllib.request.build_opener",
        lambda *handlers: opener,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.shutil.disk_usage",
        lambda path: DiskUsage(),
    )

    path, attempts = ensure_network_archive(
        root=tmp_path,
        target=target,
        context=loaded,
    )

    assert attempts == 1
    assert path.read_bytes() == payload
    request = opener.requests[0]
    assert request.get_method() == "GET"
    assert request.get_header("Range") is None
    assert request.get_header("Accept-encoding") == "identity"
    request_marker = json.loads(
        marker_path(tmp_path, target, 1, "request").read_text(encoding="utf-8")
    )
    assert request_marker["range"] is None


def test_transport_retries_only_frozen_transient_http_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = context()
    payload = b"complete-after-transient"
    target = synthetic_spot_target(
        month="2023-01",
        digest=hashlib.sha256(payload).hexdigest(),
    )
    transient = urllib.error.HTTPError(
        target.archive_url,
        503,
        "temporary",
        hdrs=None,
        fp=None,
    )
    opener = FakeOpener(
        [transient, FakeResponse(url=target.archive_url, payload=payload)]
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.urllib.request.build_opener",
        lambda *handlers: opener,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.shutil.disk_usage",
        lambda path: DiskUsage(),
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.time.sleep",
        lambda seconds: None,
    )

    _, attempts = ensure_network_archive(
        root=tmp_path,
        target=target,
        context=loaded,
    )

    assert attempts == 2
    first = json.loads(
        marker_path(tmp_path, target, 1, "response").read_text(encoding="utf-8")
    )
    assert first["status"] == 503
    assert first["outcome"] == "TRANSIENT"


def test_checksum_failure_stops_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = context()
    target = synthetic_spot_target(month="2023-01", digest="1" * 64)
    opener = FakeOpener(
        [FakeResponse(url=target.archive_url, payload=b"wrong-checksum")]
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.urllib.request.build_opener",
        lambda *handlers: opener,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_full_development_acquisition.shutil.disk_usage",
        lambda path: DiskUsage(),
    )

    with pytest.raises(AcquisitionFailure, match="checksum mismatch"):
        ensure_network_archive(root=tmp_path, target=target, context=loaded)

    assert len(opener.requests) == 1
    response = json.loads(
        marker_path(tmp_path, target, 1, "response").read_text(encoding="utf-8")
    )
    assert response["outcome"] == "INTEGRITY_FAIL"
    assert not target_archive_path(tmp_path, target).exists()
