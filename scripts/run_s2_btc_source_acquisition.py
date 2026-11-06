from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_source_feasibility import S1SourceGate  # noqa: E402
from aurex.backtest_engine.s2_btc_source_acquisition import (  # noqa: E402
    S2_BTC_SOURCE_GATES,
    S2BtcSourceAcquisitionProtocol,
    S2BtcSourceAcquisitionProtocolAudit,
    S2BtcSourceTarget,
)
from aurex.backtest_engine.s2_btc_source_execution import (  # noqa: E402
    S2_BTC_ACQUISITION_NEXT,
    S2_BTC_ACQUISITION_PASS,
    S2_BTC_ACQUISITION_STOP,
    S2BtcAcquisitionCheckpoint,
    S2BtcArchiveSummary,
    S2BtcPriceRow,
    S2BtcResourceAttempt,
    S2BtcSourceAcquisitionResult,
    S2BtcSourceExecutionAudit,
    S2BtcSourceExecutionContract,
    S2BtcTargetEvidence,
    normalize_positive_decimal_text,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s2_btc_source_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s2_btc_source_acquisition_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path("data/evidence/s2_btc_source_execution_contract_v1.json")
DEFAULT_CONTRACT_AUDIT = Path("data/evidence/s2_btc_source_execution_audit_v1.json")
DEFAULT_CHECKPOINT = Path("data/evidence/s2_btc_source_acquisition_checkpoint_v1.json")
DEFAULT_RESULT = Path("data/evidence/s2_btc_source_acquisition_result_v1.json")
EXECUTION_MODULE_PATH = Path("src/aurex/backtest_engine/s2_btc_source_execution.py")
RUNNER_PATH = Path("scripts/run_s2_btc_source_acquisition.py")
BINANCE_KLINE_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
)


class RedirectRejectedError(RuntimeError):
    pass


class RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRejectedError(f"S2 BTC redirect rejected: {newurl}")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            EXECUTION_MODULE_PATH.as_posix(): file_sha256(
                PROJECT_ROOT / EXECUTION_MODULE_PATH
            ),
            RUNNER_PATH.as_posix(): file_sha256(PROJECT_ROOT / RUNNER_PATH),
        }
    )


def project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def evidence_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def build_hashed(model_type, hash_field: str, **payload):
    provisional = model_type.model_construct(**payload, **{hash_field: "0" * 64})
    complete = provisional.model_dump(mode="json")
    complete[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model_type.model_validate(complete)


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 BTC JSON transaction exists: {temporary}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def write_model_atomic(path: Path, model, model_type) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 BTC evidence transaction exists: {temporary}")
    serialized = model.model_dump_json(indent=2) + "\n"
    if model_type.model_validate_json(serialized) != model:
        raise ValueError("S2 BTC evidence model did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def validate_target(target: S2BtcSourceTarget) -> None:
    expected_base = "/data/spot/daily/klines/BTCUSDT/1h/"
    expected_name = f"BTCUSDT-1h-{target.activation_date.isoformat()}.zip"
    archive = urlparse(target.archive_url)
    checksum = urlparse(target.checksum_url)
    if (
        archive.scheme != "https"
        or archive.hostname != target.expected_final_host
        or archive.path != f"{expected_base}{expected_name}"
        or archive.query
        or archive.fragment
        or checksum.scheme != "https"
        or checksum.hostname != target.expected_final_host
        or checksum.path != f"{archive.path}.CHECKSUM"
        or checksum.query
        or checksum.fragment
    ):
        raise ValueError("S2 BTC target left the frozen URL allowlist")
    expected_root = Path(
        "data/evidence/source_snapshots/s2_btcusdt_monday_1h_v1"
    )
    archive_path = Path(target.archive_path)
    checksum_path = Path(target.checksum_path)
    if (
        archive_path.parent != expected_root / target.activation_date.isoformat()
        or archive_path.name != expected_name
        or checksum_path != archive_path.with_name(f"{archive_path.name}.CHECKSUM")
        or target.expected_member_name != archive_path.with_suffix(".csv").name
    ):
        raise ValueError("S2 BTC target left the frozen evidence root")


def parse_checksum_text(text: str, archive_name: str) -> str:
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\r\n]+)\s*", text)
    if match is None or PurePosixPath(match.group(2)).name != archive_name:
        raise ValueError("S2 BTC checksum payload is malformed")
    return match.group(1).lower()


def inspect_archive(
    archive_path: Path,
    *,
    target: S2BtcSourceTarget,
    published_archive_sha256: str,
    maximum_uncompressed_csv_bytes: int,
) -> tuple[S2BtcArchiveSummary, str]:
    if file_sha256(archive_path) != published_archive_sha256:
        raise ValueError("S2 BTC archive does not match the published SHA-256")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) != 1:
            raise ValueError("S2 BTC archive must contain exactly one member")
        member = members[0]
        member_path = PurePosixPath(member.filename)
        if (
            member.is_dir()
            or member.filename != target.expected_member_name
            or member_path.is_absolute()
            or ".." in member_path.parts
            or "\\" in member.filename
        ):
            raise ValueError("S2 BTC archive member is not the safe expected CSV")
        if member.flag_bits & 0x1:
            raise ValueError("S2 BTC archive member must not be encrypted")
        if member.file_size > maximum_uncompressed_csv_bytes:
            raise ValueError("S2 BTC archive member exceeds its uncompressed byte cap")
        with archive.open(member) as source:
            payload = source.read(maximum_uncompressed_csv_bytes + 1)
        if len(payload) > maximum_uncompressed_csv_bytes:
            raise ValueError("S2 BTC archive expanded beyond its byte cap")
    try:
        rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline="")))
    except UnicodeError as exc:
        raise ValueError("S2 BTC CSV is not valid UTF-8") from exc
    if not rows:
        raise ValueError("S2 BTC CSV is empty")
    if any(len(row) != 12 for row in rows):
        raise ValueError("S2 BTC CSV row does not contain exactly 12 fields")
    header_present = tuple(value.strip().lower() for value in rows[0]) == (
        BINANCE_KLINE_COLUMNS
    )
    data_rows = rows[1:] if header_present else rows
    if not data_rows:
        raise ValueError("S2 BTC CSV has no kline rows")
    open_times: list[int] = []
    target_prices: list[str] = []
    day_start = target.activation_open_time_ms
    day_end = day_start + 86_400_000
    for row in data_rows:
        raw_open_time = row[0].strip()
        if len(raw_open_time) != 13 or not raw_open_time.isdigit():
            raise ValueError("S2 BTC open time is not a millisecond timestamp")
        open_time = int(raw_open_time)
        open_times.append(open_time)
        if open_time == target.activation_open_time_ms:
            target_prices.append(normalize_positive_decimal_text(row[1].strip()))
    duplicate_count = len(open_times) - len(set(open_times))
    non_increasing_count = sum(
        right <= left for left, right in zip(open_times, open_times[1:], strict=False)
    )
    outside_count = sum(not day_start <= value < day_end for value in open_times)
    if duplicate_count:
        raise ValueError("S2 BTC archive contains duplicate open times")
    if non_increasing_count:
        raise ValueError("S2 BTC archive open times are not strictly increasing")
    if outside_count:
        raise ValueError("S2 BTC archive contains a row outside its target date")
    if len(target_prices) != 1:
        raise ValueError("S2 BTC archive does not contain exactly one target open")
    summary = build_hashed(
        S2BtcArchiveSummary,
        "summary_evidence_hash",
        member_name=member.filename,
        csv_row_count=len(rows),
        data_row_count=len(data_rows),
        header_present=header_present,
        first_open_time_ms=open_times[0],
        last_open_time_ms=open_times[-1],
        target_open_occurrence_count=len(target_prices),
        duplicate_open_time_count=duplicate_count,
        non_increasing_open_time_count=non_increasing_count,
        outside_target_date_count=outside_count,
        uncompressed_csv_bytes=len(payload),
    )
    return summary, target_prices[0]


def resource_url(target: S2BtcSourceTarget, resource_kind: str) -> str:
    return target.checksum_url if resource_kind == "CHECKSUM" else target.archive_url


def resource_destination(target: S2BtcSourceTarget, resource_kind: str) -> Path:
    value = target.checksum_path if resource_kind == "CHECKSUM" else target.archive_path
    return project_path(value)


def marker_path(
    target: S2BtcSourceTarget,
    resource_kind: str,
    attempt: int,
    marker_kind: str,
) -> Path:
    destination = resource_destination(target, resource_kind)
    return destination.parent / "attempts" / (
        f"{resource_kind.lower()}-{attempt:02d}-{marker_kind}.json"
    )


def part_path(target: S2BtcSourceTarget, resource_kind: str, attempt: int) -> Path:
    destination = resource_destination(target, resource_kind)
    return destination.with_name(f"{destination.name}.attempt-{attempt:02d}.part")


def read_marker(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("S2 BTC marker is not a JSON object")
    return payload


def attempt_from_markers(
    target: S2BtcSourceTarget,
    resource_kind: str,
    attempt: int,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
) -> S2BtcResourceAttempt:
    request_path = marker_path(target, resource_kind, attempt, "request")
    response_path = marker_path(target, resource_kind, attempt, "response")
    request = read_marker(request_path)
    response = read_marker(response_path)
    identity = (target.target_id, target.sequence, resource_kind, attempt)
    if (
        request.get("schema_version") != "aurex-s2-btc-http-request-v1"
        or response.get("schema_version") != "aurex-s2-btc-http-response-v1"
        or tuple(request.get(key) for key in ("target_id", "sequence", "resource_kind", "attempt"))
        != identity
        or tuple(response.get(key) for key in ("target_id", "sequence", "resource_kind", "attempt"))
        != identity
        or request.get("protocol_evidence_hash") != protocol.protocol_evidence_hash
        or response.get("protocol_evidence_hash") != protocol.protocol_evidence_hash
        or request.get("method") != "GET"
        or request.get("url") != resource_url(target, resource_kind)
        or request.get("range") is not None
    ):
        raise ValueError("S2 BTC request/response marker identity changed")
    body_sha = response.get("body_sha256")
    destination = resource_destination(target, resource_kind)
    if response.get("outcome") == "COMPLETE" and (
        not destination.is_file() or file_sha256(destination) != body_sha
    ):
        raise ValueError("S2 BTC complete response lost its hash-bound source file")
    return build_hashed(
        S2BtcResourceAttempt,
        "attempt_evidence_hash",
        sequence=target.sequence,
        resource_kind=resource_kind,
        attempt=attempt,
        requested_at=datetime.fromisoformat(request["requested_at"]),
        completed_at=datetime.fromisoformat(response["completed_at"]),
        url=request["url"],
        status_code=response.get("status_code"),
        final_url=response.get("final_url"),
        final_host=response.get("final_host"),
        content_type=response.get("content_type"),
        bytes_received=response["bytes_received"],
        body_sha256=body_sha,
        outcome=response["outcome"],
        error_type=response.get("error_type"),
        error_message=response.get("error_message"),
        request_marker_path=evidence_path(request_path),
        request_marker_sha256=file_sha256(request_path),
        response_marker_path=evidence_path(response_path),
        response_marker_sha256=file_sha256(response_path),
    )


def recover_interrupted_attempt(
    target: S2BtcSourceTarget,
    resource_kind: str,
    attempt: int,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
) -> None:
    request_path = marker_path(target, resource_kind, attempt, "request")
    response_path = marker_path(target, resource_kind, attempt, "response")
    partial = part_path(target, resource_kind, attempt)
    if not request_path.exists() or response_path.exists():
        return
    request = read_marker(request_path)
    if request.get("protocol_evidence_hash") != protocol.protocol_evidence_hash:
        raise ValueError("S2 BTC interrupted request lineage changed")
    interrupted_bytes = partial.stat().st_size if partial.exists() else 0
    if partial.exists():
        partial.unlink()
    write_json_atomic(
        response_path,
        {
            "schema_version": "aurex-s2-btc-http-response-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "resource_kind": resource_kind,
            "attempt": attempt,
            "status_code": None,
            "final_url": None,
            "final_host": None,
            "content_type": None,
            "bytes_received": interrupted_bytes,
            "body_sha256": None,
            "outcome": "TRANSIENT_FAILURE",
            "error_type": "InterruptedAttempt",
            "error_message": "Request marker existed without a terminal response marker.",
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )


def existing_attempts(
    target: S2BtcSourceTarget,
    resource_kind: str,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
) -> tuple[S2BtcResourceAttempt, ...]:
    attempts = []
    for attempt in range(1, protocol.maximum_attempts_per_resource + 1):
        request_path = marker_path(target, resource_kind, attempt, "request")
        response_path = marker_path(target, resource_kind, attempt, "response")
        if response_path.exists() and not request_path.exists():
            raise ValueError("S2 BTC response marker exists without its request marker")
        recover_interrupted_attempt(
            target, resource_kind, attempt, protocol=protocol
        )
        if not request_path.exists():
            break
        attempts.append(
            attempt_from_markers(
                target, resource_kind, attempt, protocol=protocol
            )
        )
    return tuple(attempts)


def classify_error(
    exc: Exception, *, protocol: S2BtcSourceAcquisitionProtocol
) -> tuple[str, str]:
    if isinstance(exc, HTTPError):
        return (
            "TRANSIENT_FAILURE"
            if exc.code in protocol.transient_http_statuses
            else "PERMANENT_FAILURE",
            "HTTPError",
        )
    if isinstance(exc, (TimeoutError, URLError, ConnectionError, OSError)):
        return "TRANSIENT_FAILURE", type(exc).__name__
    return "PERMANENT_FAILURE", type(exc).__name__


def execute_resource_attempt(
    target: S2BtcSourceTarget,
    resource_kind: str,
    attempt: int,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
    network_body_bytes_before: int = 0,
    opener_factory: Callable[[], object] | None = None,
) -> S2BtcResourceAttempt:
    request_path = marker_path(target, resource_kind, attempt, "request")
    response_path = marker_path(target, resource_kind, attempt, "response")
    partial = part_path(target, resource_kind, attempt)
    destination = resource_destination(target, resource_kind)
    if any(path.exists() for path in (request_path, response_path, partial)):
        raise ValueError("S2 BTC resource-attempt evidence already exists")
    if destination.exists():
        raise ValueError("S2 BTC destination exists without a complete attempt")
    url = resource_url(target, resource_kind)
    requested_at = datetime.now(UTC)
    write_json_atomic(
        request_path,
        {
            "schema_version": "aurex-s2-btc-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "resource_kind": resource_kind,
            "attempt": attempt,
            "method": "GET",
            "url": url,
            "range": None,
            "requested_at": requested_at.isoformat(),
        },
    )
    status_code = None
    final_url = None
    final_host = None
    content_type = None
    bytes_received = 0
    body_sha256 = None
    outcome = "COMPLETE"
    error_type = None
    error_message = None
    cap = (
        protocol.maximum_checksum_bytes_per_target
        if resource_kind == "CHECKSUM"
        else protocol.maximum_archive_bytes_per_target
    )
    try:
        request = Request(
            url,
            headers={"User-Agent": "Aurex-S2-BTC-Source-Acquisition/1.0"},
            method="GET",
        )
        opener = opener_factory() if opener_factory else build_opener(RejectRedirectHandler())
        with opener.open(request, timeout=protocol.connect_timeout_seconds) as response:
            status_code = response.status
            final_url = response.geturl()
            final_host = urlparse(final_url).hostname
            content_type = response.headers.get("Content-Type")
            if status_code != 200:
                raise ValueError(f"S2 BTC source returned HTTP {status_code}")
            if final_url != url or final_host != target.expected_final_host:
                raise ValueError("S2 BTC source identity changed")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with partial.open("xb") as output:
                while True:
                    chunk = response.read(protocol.chunk_size_bytes)
                    if not chunk:
                        break
                    bytes_received += len(chunk)
                    if bytes_received > cap:
                        raise ValueError("S2 BTC source payload exceeded its byte cap")
                    if (
                        network_body_bytes_before + bytes_received
                        > protocol.maximum_total_payload_bytes
                    ):
                        raise ValueError("S2 BTC source exceeded its total byte budget")
                    output.write(chunk)
            if bytes_received == 0:
                raise ValueError("S2 BTC source returned an empty payload")
            body_sha256 = file_sha256(partial)
            partial.replace(destination)
    except Exception as exc:
        outcome, error_type = classify_error(exc, protocol=protocol)
        error_message = str(exc)
        if isinstance(exc, HTTPError):
            status_code = exc.code
            final_url = exc.geturl()
            final_host = urlparse(final_url).hostname
            content_type = exc.headers.get("Content-Type") if exc.headers else None
        if partial.exists():
            partial.unlink()
    write_json_atomic(
        response_path,
        {
            "schema_version": "aurex-s2-btc-http-response-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "resource_kind": resource_kind,
            "attempt": attempt,
            "status_code": status_code,
            "final_url": final_url,
            "final_host": final_host,
            "content_type": content_type,
            "bytes_received": bytes_received,
            "body_sha256": body_sha256,
            "outcome": outcome,
            "error_type": error_type,
            "error_message": error_message,
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )
    return attempt_from_markers(
        target, resource_kind, attempt, protocol=protocol
    )


def acquire_resource(
    target: S2BtcSourceTarget,
    resource_kind: str,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
    network_body_bytes_before: int,
) -> tuple[S2BtcResourceAttempt, ...]:
    attempts = list(existing_attempts(target, resource_kind, protocol=protocol))
    destination = resource_destination(target, resource_kind)
    if attempts and attempts[-1].outcome == "COMPLETE":
        if not destination.is_file():
            raise ValueError("S2 BTC complete attempt lost its source file")
        return tuple(attempts)
    if destination.exists():
        raise ValueError("S2 BTC source file exists without a complete attempt")
    while len(attempts) < protocol.maximum_attempts_per_resource:
        item = execute_resource_attempt(
            target,
            resource_kind,
            len(attempts) + 1,
            protocol=protocol,
            network_body_bytes_before=(
                network_body_bytes_before
                + sum(attempt.bytes_received for attempt in attempts)
            ),
        )
        attempts.append(item)
        if item.outcome in {"COMPLETE", "PERMANENT_FAILURE"}:
            break
        time.sleep(protocol.polite_delay_milliseconds / 1_000)
    return tuple(attempts)


def target_evidence_from_files(
    target: S2BtcSourceTarget,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
    contract: S2BtcSourceExecutionContract,
    attempts: tuple[S2BtcResourceAttempt, ...],
    source_mode: str,
) -> S2BtcTargetEvidence:
    archive_path = project_path(target.archive_path)
    checksum_path = project_path(target.checksum_path)
    try:
        published = parse_checksum_text(
            checksum_path.read_text(encoding="utf-8"), archive_path.name
        )
        archive_sha = file_sha256(archive_path)
        summary, open_price = inspect_archive(
            archive_path,
            target=target,
            published_archive_sha256=published,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )
        checksum_sha = file_sha256(checksum_path)
        price_row = build_hashed(
            S2BtcPriceRow,
            "price_evidence_hash",
            sequence=target.sequence,
            measurement_sequence=target.measurement_sequence,
            activation_date=target.activation_date,
            activation_open_time_ms=target.activation_open_time_ms,
            open_price=open_price,
            archive_file_sha256=archive_sha,
            published_archive_sha256=published,
            checksum_file_sha256=checksum_sha,
            source_target_id=target.target_id,
        )
        return build_hashed(
            S2BtcTargetEvidence,
            "target_evidence_hash",
            sequence=target.sequence,
            target_id=target.target_id,
            activation_date=target.activation_date,
            outcome="COMPLETE",
            source_mode=source_mode,
            attempts=attempts,
            archive_path=target.archive_path,
            archive_file_sha256=archive_sha,
            archive_bytes=archive_path.stat().st_size,
            checksum_path=target.checksum_path,
            checksum_file_sha256=checksum_sha,
            checksum_bytes=checksum_path.stat().st_size,
            published_archive_sha256=published,
            archive_summary=summary,
            price_row=price_row,
            failure_gate=None,
        )
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
        return build_hashed(
            S2BtcTargetEvidence,
            "target_evidence_hash",
            sequence=target.sequence,
            target_id=target.target_id,
            activation_date=target.activation_date,
            outcome="FAILED",
            source_mode=source_mode,
            attempts=attempts,
            archive_path=target.archive_path if archive_path.is_file() else None,
            archive_file_sha256=(file_sha256(archive_path) if archive_path.is_file() else None),
            archive_bytes=archive_path.stat().st_size if archive_path.is_file() else 0,
            checksum_path=target.checksum_path if checksum_path.is_file() else None,
            checksum_file_sha256=(
                file_sha256(checksum_path) if checksum_path.is_file() else None
            ),
            checksum_bytes=checksum_path.stat().st_size if checksum_path.is_file() else 0,
            published_archive_sha256=None,
            archive_summary=None,
            price_row=None,
            failure_gate=f"SOURCE_STRUCTURE_OR_CHECKSUM_FAILED:{type(exc).__name__}",
        )


def build_failed_transport_target(
    target: S2BtcSourceTarget,
    attempts: tuple[S2BtcResourceAttempt, ...],
) -> S2BtcTargetEvidence:
    archive_path = project_path(target.archive_path)
    checksum_path = project_path(target.checksum_path)
    return build_hashed(
        S2BtcTargetEvidence,
        "target_evidence_hash",
        sequence=target.sequence,
        target_id=target.target_id,
        activation_date=target.activation_date,
        outcome="FAILED",
        source_mode="NETWORK",
        attempts=attempts,
        archive_path=target.archive_path if archive_path.is_file() else None,
        archive_file_sha256=(file_sha256(archive_path) if archive_path.is_file() else None),
        archive_bytes=archive_path.stat().st_size if archive_path.is_file() else 0,
        checksum_path=target.checksum_path if checksum_path.is_file() else None,
        checksum_file_sha256=(
            file_sha256(checksum_path) if checksum_path.is_file() else None
        ),
        checksum_bytes=checksum_path.stat().st_size if checksum_path.is_file() else 0,
        published_archive_sha256=None,
        archive_summary=None,
        price_row=None,
        failure_gate="PAYLOAD_TRANSPORT_OR_ATTEMPT_BUDGET_FAILED",
    )


def acquire_target(
    target: S2BtcSourceTarget,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
    contract: S2BtcSourceExecutionContract,
    network_body_bytes_before: int = 0,
) -> S2BtcTargetEvidence:
    validate_target(target)
    archive_path = project_path(target.archive_path)
    checksum_path = project_path(target.checksum_path)
    has_markers = any(
        marker_path(target, kind, attempt, "request").exists()
        for kind in ("CHECKSUM", "ARCHIVE")
        for attempt in range(1, protocol.maximum_attempts_per_resource + 1)
    )
    if archive_path.is_file() and checksum_path.is_file() and not has_markers:
        return target_evidence_from_files(
            target,
            protocol=protocol,
            contract=contract,
            attempts=(),
            source_mode="LOCAL_REUSE",
        )
    if not has_markers and (archive_path.exists() or checksum_path.exists()):
        raise ValueError("S2 BTC incomplete unmarked local source pair exists")
    checksum_attempts = acquire_resource(
        target,
        "CHECKSUM",
        protocol=protocol,
        network_body_bytes_before=network_body_bytes_before,
    )
    if not checksum_attempts or checksum_attempts[-1].outcome != "COMPLETE":
        return build_failed_transport_target(target, checksum_attempts)
    archive_attempts = acquire_resource(
        target,
        "ARCHIVE",
        protocol=protocol,
        network_body_bytes_before=(
            network_body_bytes_before
            + sum(attempt.bytes_received for attempt in checksum_attempts)
        ),
    )
    attempts = checksum_attempts + archive_attempts
    if not archive_attempts or archive_attempts[-1].outcome != "COMPLETE":
        return build_failed_transport_target(target, attempts)
    return target_evidence_from_files(
        target,
        protocol=protocol,
        contract=contract,
        attempts=attempts,
        source_mode="NETWORK",
    )


def build_checkpoint(
    *,
    started_at: datetime,
    updated_at: datetime,
    protocol_path: Path,
    protocol: S2BtcSourceAcquisitionProtocol,
    contract_path: Path,
    contract: S2BtcSourceExecutionContract,
    target_evidence: tuple[S2BtcTargetEvidence, ...],
) -> S2BtcAcquisitionCheckpoint:
    terminal = len(target_evidence) == protocol.target_count or any(
        item.outcome == "FAILED" for item in target_evidence
    )
    return build_hashed(
        S2BtcAcquisitionCheckpoint,
        "checkpoint_evidence_hash",
        started_at=started_at,
        updated_at=updated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(contract_path),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        target_evidence=target_evidence,
        classified_target_count=len(target_evidence),
        complete_target_count=sum(item.outcome == "COMPLETE" for item in target_evidence),
        failed_target_count=sum(item.outcome == "FAILED" for item in target_evidence),
        network_request_count=sum(len(item.attempts) for item in target_evidence),
        network_body_bytes=sum(
            attempt.bytes_received for item in target_evidence for attempt in item.attempts
        ),
        persisted_source_bytes=sum(
            item.archive_bytes + item.checksum_bytes for item in target_evidence
        ),
        next_sequence=None if terminal else len(target_evidence) + 1,
        terminal=terminal,
    )


def verify_checkpoint_sources(
    checkpoint: S2BtcAcquisitionCheckpoint,
    *,
    protocol: S2BtcSourceAcquisitionProtocol,
    contract: S2BtcSourceExecutionContract,
) -> None:
    if checkpoint.runner_contract_hash != runner_contract_hash():
        raise ValueError("S2 BTC checkpoint runner contract changed")
    for target, evidence in zip(
        protocol.targets, checkpoint.target_evidence, strict=True
    ):
        if target.sequence != evidence.sequence or target.target_id != evidence.target_id:
            raise ValueError("S2 BTC checkpoint target identity changed")
        for attempt in evidence.attempts:
            if (
                file_sha256(project_path(attempt.request_marker_path))
                != attempt.request_marker_sha256
                or file_sha256(project_path(attempt.response_marker_path))
                != attempt.response_marker_sha256
            ):
                raise ValueError("S2 BTC checkpoint marker hash changed")
        if evidence.outcome == "COMPLETE" or evidence.failure_gate.startswith(
            "SOURCE_STRUCTURE_OR_CHECKSUM_FAILED"
        ):
            reconstructed = target_evidence_from_files(
                target,
                protocol=protocol,
                contract=contract,
                attempts=evidence.attempts,
                source_mode=evidence.source_mode,
            )
            if reconstructed != evidence:
                raise ValueError("S2 BTC checkpoint source evidence changed")


def evaluate_result_gates(
    protocol: S2BtcSourceAcquisitionProtocol,
    checkpoint: S2BtcAcquisitionCheckpoint,
) -> tuple[S1SourceGate, ...]:
    evidence = checkpoint.target_evidence
    complete = len(evidence) == protocol.target_count and all(
        item.outcome == "COMPLETE" for item in evidence
    )
    checks = {
        "ALL_273_MONDAY_TARGETS_CLASSIFIED": len(evidence) == protocol.target_count,
        "EVERY_ZIP_MATCHES_ITS_PUBLISHED_SHA256": complete
        and all(
            item.archive_file_sha256 == item.published_archive_sha256
            for item in evidence
        ),
        "EVERY_ZIP_HAS_EXACTLY_ONE_SAFE_EXPECTED_CSV_MEMBER": complete
        and all(
            item.archive_summary is not None
            and item.archive_summary.member_name == target.expected_member_name
            for target, item in zip(protocol.targets, evidence, strict=True)
        ),
        "EVERY_CSV_ROW_HAS_EXACTLY_12_KLINE_FIELDS": complete,
        "OPEN_TIMES_ARE_UNIQUE_STRICTLY_INCREASING_AND_WITHIN_TARGET_DATE": complete
        and all(
            item.archive_summary is not None
            and item.archive_summary.duplicate_open_time_count == 0
            and item.archive_summary.non_increasing_open_time_count == 0
            and item.archive_summary.outside_target_date_count == 0
            for item in evidence
        ),
        "EXACT_00_00_UTC_TARGET_OPEN_EXISTS_ONCE_PER_DATE": complete
        and all(
            item.archive_summary is not None
            and item.archive_summary.target_open_occurrence_count == 1
            for item in evidence
        ),
        "TARGET_OPEN_IS_POSITIVE_FINITE_DECIMAL_SOURCE_TEXT": complete
        and all(item.price_row is not None for item in evidence),
        "REQUEST_AND_RESPONSE_MARKERS_RECONCILE_EXACTLY": all(
            project_path(attempt.request_marker_path).is_file()
            and project_path(attempt.response_marker_path).is_file()
            for item in evidence
            for attempt in item.attempts
        ),
        "OUTPUT_HAS_273_CHRONOLOGICAL_HASH_LINKED_PRICE_ROWS": complete
        and tuple(item.price_row.sequence for item in evidence if item.price_row)
        == tuple(range(1, 274)),
        (
            "ZERO_RETURNS_CANDIDATE_OUTCOMES_HISTORICAL_SCREEN_VALIDATION_"
            "HOLDOUT_AND_ORDERS"
        ): True,
    }
    if tuple(sorted(checks)) != tuple(sorted(S2_BTC_SOURCE_GATES)):
        raise ValueError("S2 BTC gate implementation changed")
    return tuple(
        S1SourceGate(
            gate_id=gate_id,
            status="PASS" if passed else "FAIL",
            reason=(
                "Observed evidence satisfies the frozen acquisition condition."
                if passed
                else "Observed evidence does not satisfy the frozen acquisition condition."
            ),
        )
        for gate_id, passed in sorted(checks.items())
    )


def dataset_bytes(price_rows: tuple[S2BtcPriceRow, ...]) -> bytes:
    return b"".join(
        (json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n").encode("utf-8")
        for row in price_rows
    )


def materialize_dataset(path: Path, price_rows: tuple[S2BtcPriceRow, ...]) -> None:
    payload = dataset_bytes(price_rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("Existing S2 BTC dataset bytes changed")
        return
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError("Stale S2 BTC dataset transaction exists")
    temporary.write_bytes(payload)
    temporary.replace(path)


def build_result(
    *,
    checkpoint_path: Path,
    checkpoint: S2BtcAcquisitionCheckpoint,
    protocol: S2BtcSourceAcquisitionProtocol,
    completed_at: datetime,
) -> S2BtcSourceAcquisitionResult:
    gates = evaluate_result_gates(protocol, checkpoint)
    failed = any(gate.status == "FAIL" for gate in gates)
    price_rows = tuple(
        item.price_row for item in checkpoint.target_evidence if item.price_row is not None
    )
    dataset_path = project_path(protocol.output_path)
    if not failed:
        materialize_dataset(dataset_path, price_rows)
    return build_hashed(
        S2BtcSourceAcquisitionResult,
        "result_evidence_hash",
        completed_at=completed_at,
        checkpoint_file_sha256=file_sha256(checkpoint_path),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        protocol_evidence_hash=checkpoint.protocol_evidence_hash,
        execution_contract_evidence_hash=checkpoint.execution_contract_evidence_hash,
        runner_contract_hash=checkpoint.runner_contract_hash,
        target_evidence=checkpoint.target_evidence,
        price_rows=price_rows if not failed else (),
        gates=gates,
        classified_target_count=checkpoint.classified_target_count,
        complete_target_count=checkpoint.complete_target_count,
        failed_target_count=checkpoint.failed_target_count,
        network_request_count=checkpoint.network_request_count,
        network_body_bytes=checkpoint.network_body_bytes,
        persisted_source_bytes=checkpoint.persisted_source_bytes,
        dataset_path=protocol.output_path if not failed else None,
        dataset_file_sha256=file_sha256(dataset_path) if not failed else None,
        dataset_bytes=dataset_path.stat().st_size if not failed else 0,
        decision=S2_BTC_ACQUISITION_STOP if failed else S2_BTC_ACQUISITION_PASS,
        next_authorization=(
            "NONE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_FAILED"
            if failed
            else S2_BTC_ACQUISITION_NEXT
        ),
    )


def load_authority(
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
) -> tuple[S2BtcSourceAcquisitionProtocol, S2BtcSourceExecutionContract]:
    protocol = S2BtcSourceAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S2BtcSourceAcquisitionProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S2BtcSourceExecutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = S2BtcSourceExecutionAudit.model_validate_json(
        contract_audit_path.read_text(encoding="utf-8")
    )
    if (
        file_sha256(protocol_path) != contract.protocol_file_sha256
        or protocol.protocol_evidence_hash != contract.protocol_evidence_hash
        or file_sha256(protocol_audit_path) != contract.protocol_audit_file_sha256
        or protocol_audit.audit_evidence_hash != contract.protocol_audit_evidence_hash
        or runner_contract_hash() != contract.runner_contract_hash
        or file_sha256(contract_path) != contract_audit.contract_file_sha256
        or contract.contract_evidence_hash != contract_audit.contract_evidence_hash
        or contract.runner_contract_hash != contract_audit.runner_contract_hash
        or not contract.authorizes_network_acquisition
    ):
        raise ValueError("S2 BTC source acquisition authority lineage changed")
    return protocol, contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded, resumable S2 BTCUSDT source acquisition."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol_path = project_path(args.protocol)
    protocol_audit_path = project_path(args.protocol_audit)
    contract_path = project_path(args.contract)
    contract_audit_path = project_path(args.contract_audit)
    checkpoint_path = project_path(args.checkpoint)
    output_path = project_path(args.output)
    if output_path.exists():
        raise SystemExit(f"Refusing to overwrite S2 BTC result: {output_path}")
    protocol, contract = load_authority(
        protocol_path, protocol_audit_path, contract_path, contract_audit_path
    )
    if shutil.disk_usage(PROJECT_ROOT).free < protocol.minimum_free_disk_bytes:
        raise SystemExit("Insufficient free disk for S2 BTC source acquisition")
    if checkpoint_path.exists():
        checkpoint = S2BtcAcquisitionCheckpoint.model_validate_json(
            checkpoint_path.read_text(encoding="utf-8")
        )
        verify_checkpoint_sources(checkpoint, protocol=protocol, contract=contract)
        if checkpoint.terminal:
            result = build_result(
                checkpoint_path=checkpoint_path,
                checkpoint=checkpoint,
                protocol=protocol,
                completed_at=datetime.now(UTC),
            )
            write_model_atomic(output_path, result, S2BtcSourceAcquisitionResult)
            return 0
        started_at = checkpoint.started_at
        evidence = list(checkpoint.target_evidence)
    else:
        started_at = datetime.now(UTC)
        evidence = []
        checkpoint = build_checkpoint(
            started_at=started_at,
            updated_at=started_at,
            protocol_path=protocol_path,
            protocol=protocol,
            contract_path=contract_path,
            contract=contract,
            target_evidence=(),
        )
        write_model_atomic(
            checkpoint_path, checkpoint, S2BtcAcquisitionCheckpoint
        )
    for target in protocol.targets[len(evidence) :]:
        item = acquire_target(
            target,
            protocol=protocol,
            contract=contract,
            network_body_bytes_before=checkpoint.network_body_bytes,
        )
        evidence.append(item)
        checkpoint = build_checkpoint(
            started_at=started_at,
            updated_at=datetime.now(UTC),
            protocol_path=protocol_path,
            protocol=protocol,
            contract_path=contract_path,
            contract=contract,
            target_evidence=tuple(evidence),
        )
        write_model_atomic(
            checkpoint_path, checkpoint, S2BtcAcquisitionCheckpoint
        )
        print(
            f"CHECKPOINT {len(evidence)}/{protocol.target_count} "
            f"requests={checkpoint.network_request_count} "
            f"bytes={checkpoint.network_body_bytes} outcome={item.outcome}",
            flush=True,
        )
        if item.outcome == "FAILED":
            break
        time.sleep(protocol.polite_delay_milliseconds / 1_000)
    result = build_result(
        checkpoint_path=checkpoint_path,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=datetime.now(UTC),
    )
    write_model_atomic(output_path, result, S2BtcSourceAcquisitionResult)
    print(
        f"COMPLETE {output_path} {result.result_evidence_hash} "
        f"decision={result.decision} targets={result.classified_target_count} "
        f"requests={result.network_request_count} bytes={result.network_body_bytes} "
        f"prices={len(result.price_rows)} returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
