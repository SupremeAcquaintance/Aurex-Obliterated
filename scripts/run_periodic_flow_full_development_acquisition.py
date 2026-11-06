from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from itertools import chain
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (  # noqa: E402
    PeriodicFlowDevelopmentTarget,
    PeriodicFlowFullDevelopmentProtocol,
    PeriodicFlowFullDevelopmentProtocolAudit,
    audit_full_development_protocol,
    audit_full_development_protocol_audit,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    RUNNER_SOURCE_PATHS,
    PeriodicFlowAcquisitionCheckpoint,
    PeriodicFlowAcquisitionResult,
    PeriodicFlowArchiveEvidence,
    PeriodicFlowExecutionContract,
    PeriodicFlowExecutionContractAudit,
    PeriodicFlowPairedMonthEvidence,
    audit_execution_contract,
    audit_execution_contract_audit,
    build_acquisition_result,
    build_checkpoint,
    month_bounds_ms,
    source_contract_hash,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_audit_v1.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_full_development_execution_contract_v1.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_full_development_execution_contract_audit_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_v1"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_checkpoint_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_result_v1.json"
)
REQUEST_SCHEMA = "aurex-q1-periodic-flow-full-development-http-request-v1"
RESPONSE_SCHEMA = "aurex-q1-periodic-flow-full-development-http-response-v1"
TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504}
KNOWN_DUPLICATE_MEMBER = (
    "fsx-data/collector_data/data/spot/monthly/aggTrades/BTCUSDT/"
    "BTCUSDT-aggTrades-2021-12.csv"
)
SPOT_HEADER_ALIASES = {
    "agg_trade_id": "aggregate_trade_id",
    "aggregate_trade_id": "aggregate_trade_id",
    "price": "price",
    "qty": "quantity",
    "quantity": "quantity",
    "first_trade_id": "first_trade_id",
    "last_trade_id": "last_trade_id",
    "transact_time": "transact_time",
    "timestamp": "transact_time",
    "is_buyer_maker": "is_buyer_maker",
    "is_best_match": "is_best_match",
}
RAW_HEADER_ALIASES = {
    "id": "trade_id",
    "trade_id": "trade_id",
    "price": "price",
    "qty": "quantity",
    "quantity": "quantity",
    "quoteqty": "quote_quantity",
    "quote_qty": "quote_quantity",
    "quote_quantity": "quote_quantity",
    "time": "timestamp",
    "timestamp": "timestamp",
    "is_buyer_maker": "buyer_was_maker",
    "buyer_was_maker": "buyer_was_maker",
}


class RedirectRejectedError(RuntimeError):
    pass


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise RedirectRejectedError(f"Redirect refused: {code} {newurl}")


class AcquisitionFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedContext:
    protocol: PeriodicFlowFullDevelopmentProtocol
    protocol_audit: PeriodicFlowFullDevelopmentProtocolAudit
    contract: PeriodicFlowExecutionContract
    contract_audit: PeriodicFlowExecutionContractAudit


@dataclass(frozen=True)
class ArchiveInspection:
    evidence: PeriodicFlowArchiveEvidence
    minute_indexes: frozenset[int]


@dataclass(frozen=True)
class MarkerState:
    request_count: int
    response_count: int
    payload_bytes_received: int
    manifest_hash: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_transactional(path: Path, payload: dict, *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise ValueError(f"Refusing to overwrite immutable Q1 evidence: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 JSON transaction exists: {temporary}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def load_context(args: argparse.Namespace) -> LoadedContext:
    protocol = PeriodicFlowFullDevelopmentProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowFullDevelopmentProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowExecutionContract.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowExecutionContractAudit.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    current_runner_hash = source_contract_hash(PROJECT_ROOT, RUNNER_SOURCE_PATHS)
    if (
        not audit_full_development_protocol(protocol)
        or not audit_full_development_protocol_audit(protocol_audit)
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not audit_execution_contract(contract)
        or contract.parent_protocol_file_sha256 != file_sha256(args.protocol)
        or contract.parent_protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.parent_protocol_audit_file_sha256
        != file_sha256(args.protocol_audit)
        or contract.parent_protocol_audit_evidence_hash
        != protocol_audit.audit_evidence_hash
        or contract.runner_source_hash != current_runner_hash
        or not audit_execution_contract_audit(contract_audit)
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_source_hash != current_runner_hash
    ):
        raise ValueError("Q1 acquisition authority or runner source changed")
    expected_order = [
        {"month": target.month, "product": target.product}
        for target in sorted(protocol.targets, key=lambda item: item.key)
    ]
    if contract.processing_manifest_hash != universe_evidence_hash(
        {"processing_order": expected_order}
    ):
        raise ValueError("Q1 acquisition processing order changed")
    return LoadedContext(protocol, protocol_audit, contract, contract_audit)


def target_directory(root: Path, target: PeriodicFlowDevelopmentTarget) -> Path:
    return root / "BTCUSDT" / target.month / target.family


def target_archive_path(root: Path, target: PeriodicFlowDevelopmentTarget) -> Path:
    return target_directory(root, target) / PurePosixPath(
        urllib.parse.urlparse(target.archive_url).path
    ).name


def resolved_archive_path(
    *,
    evidence_root: Path,
    acquisition_root: Path,
    target: PeriodicFlowDevelopmentTarget,
) -> Path:
    if target.reuse_candidate_path is not None:
        candidate = (evidence_root / target.reuse_candidate_path).resolve()
        root = evidence_root.resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Q1 reuse candidate escapes the evidence root")
        return candidate
    return target_archive_path(acquisition_root, target)


def marker_path(
    root: Path,
    target: PeriodicFlowDevelopmentTarget,
    attempt: int,
    kind: str,
) -> Path:
    archive = target_archive_path(root, target).name
    return target_directory(root, target) / f"{archive}.get.{attempt}.{kind}.json"


def _marker_target_key(target: PeriodicFlowDevelopmentTarget) -> str:
    return f"{target.month}|{target.product}"


def write_request_marker(
    *,
    root: Path,
    target: PeriodicFlowDevelopmentTarget,
    context: LoadedContext,
    attempt: int,
) -> None:
    _write_json_transactional(
        marker_path(root, target, attempt, "request"),
        {
            "schema_version": REQUEST_SCHEMA,
            "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "target_key": _marker_target_key(target),
            "month": target.month,
            "product": target.product,
            "family": target.family,
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
            "accept": "application/zip",
            "accept_encoding": "identity",
            "range": None,
            "requested_at": datetime.now(UTC).isoformat(),
        },
        overwrite=False,
    )


def write_response_marker(
    *,
    root: Path,
    target: PeriodicFlowDevelopmentTarget,
    context: LoadedContext,
    attempt: int,
    status: int | None,
    final_url: str,
    content_length: int | None,
    content_encoding: str,
    bytes_received: int,
    outcome: str,
) -> None:
    _write_json_transactional(
        marker_path(root, target, attempt, "response"),
        {
            "schema_version": RESPONSE_SCHEMA,
            "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "target_key": _marker_target_key(target),
            "month": target.month,
            "product": target.product,
            "family": target.family,
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
            "status": status,
            "final_url": final_url,
            "content_length": content_length,
            "content_encoding": content_encoding,
            "bytes_received": bytes_received,
            "outcome": outcome,
            "completed_at": datetime.now(UTC).isoformat(),
        },
        overwrite=False,
    )


def _validate_request_marker(
    payload: dict,
    *,
    target: PeriodicFlowDevelopmentTarget,
    context: LoadedContext,
    attempt: int,
) -> None:
    if (
        payload.get("schema_version") != REQUEST_SCHEMA
        or payload.get("protocol_evidence_hash")
        != context.protocol.protocol_evidence_hash
        or payload.get("execution_contract_evidence_hash")
        != context.contract.contract_evidence_hash
        or payload.get("target_key") != _marker_target_key(target)
        or payload.get("month") != target.month
        or payload.get("product") != target.product
        or payload.get("family") != target.family
        or payload.get("method") != "GET"
        or payload.get("url") != target.archive_url
        or payload.get("attempt") != attempt
        or payload.get("accept") != "application/zip"
        or payload.get("accept_encoding") != "identity"
        or payload.get("range") is not None
    ):
        raise ValueError(f"Q1 request marker changed: {target.key} attempt {attempt}")


def _validate_response_marker(
    payload: dict,
    *,
    target: PeriodicFlowDevelopmentTarget,
    context: LoadedContext,
    attempt: int,
) -> None:
    if (
        payload.get("schema_version") != RESPONSE_SCHEMA
        or payload.get("protocol_evidence_hash")
        != context.protocol.protocol_evidence_hash
        or payload.get("execution_contract_evidence_hash")
        != context.contract.contract_evidence_hash
        or payload.get("target_key") != _marker_target_key(target)
        or payload.get("month") != target.month
        or payload.get("product") != target.product
        or payload.get("family") != target.family
        or payload.get("method") != "GET"
        or payload.get("url") != target.archive_url
        or payload.get("attempt") != attempt
        or not isinstance(payload.get("bytes_received"), int)
        or payload["bytes_received"] < 0
        or payload.get("outcome")
        not in {
            "PASS",
            "TRANSIENT",
            "HTTP_FAIL",
            "INTEGRITY_FAIL",
            "ABANDONED_INTERRUPTED",
            "RECOVERED_VERIFIED_ARCHIVE_AFTER_INTERRUPTION",
        }
    ):
        raise ValueError(f"Q1 response marker changed: {target.key} attempt {attempt}")


def target_attempt_count(root: Path, target: PeriodicFlowDevelopmentTarget) -> int:
    directory = target_directory(root, target)
    if not directory.exists():
        return 0
    archive = target_archive_path(root, target).name
    return len(list(directory.glob(f"{archive}.get.*.request.json")))


def reconcile_target_markers(
    *,
    root: Path,
    target: PeriodicFlowDevelopmentTarget,
    context: LoadedContext,
) -> int:
    directory = target_directory(root, target)
    if not directory.exists():
        return 0
    archive_name = target_archive_path(root, target).name
    request_paths = sorted(directory.glob(f"{archive_name}.get.*.request.json"))
    response_paths = sorted(directory.glob(f"{archive_name}.get.*.response.json"))
    response_by_attempt: dict[int, Path] = {}
    for path in response_paths:
        try:
            attempt = int(path.name.split(".get.", 1)[1].split(".", 1)[0])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"Malformed Q1 response marker name: {path}") from exc
        if attempt in response_by_attempt:
            raise ValueError("Duplicate Q1 response marker attempt")
        response_by_attempt[attempt] = path
    if len(response_paths) > len(request_paths):
        raise ValueError("Q1 response marker exists without a request marker")
    attempts: list[int] = []
    destination = target_archive_path(root, target)
    part = destination.with_name(f"{destination.name}.part")
    for path in request_paths:
        try:
            attempt = int(path.name.split(".get.", 1)[1].split(".", 1)[0])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"Malformed Q1 request marker name: {path}") from exc
        attempts.append(attempt)
        request_payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_request_marker(
            request_payload,
            target=target,
            context=context,
            attempt=attempt,
        )
        response_path = response_by_attempt.get(attempt)
        if response_path is not None:
            response_payload = json.loads(response_path.read_text(encoding="utf-8"))
            _validate_response_marker(
                response_payload,
                target=target,
                context=context,
                attempt=attempt,
            )
            continue
        if destination.exists():
            if file_sha256(destination) != target.published_archive_sha256:
                write_response_marker(
                    root=root,
                    target=target,
                    context=context,
                    attempt=attempt,
                    status=None,
                    final_url=target.archive_url,
                    content_length=None,
                    content_encoding="identity",
                    bytes_received=destination.stat().st_size,
                    outcome="INTEGRITY_FAIL",
                )
                raise ValueError("Interrupted Q1 destination checksum changed")
            if part.exists():
                raise ValueError("Q1 destination and partial archive coexist")
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=200,
                final_url=target.archive_url,
                content_length=destination.stat().st_size,
                content_encoding="identity",
                bytes_received=destination.stat().st_size,
                outcome="RECOVERED_VERIFIED_ARCHIVE_AFTER_INTERRUPTION",
            )
        else:
            abandoned_bytes = part.stat().st_size if part.exists() else 0
            if part.exists():
                part.unlink()
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=None,
                final_url=target.archive_url,
                content_length=None,
                content_encoding="identity",
                bytes_received=abandoned_bytes,
                outcome="ABANDONED_INTERRUPTED",
            )
    if attempts != list(range(1, len(attempts) + 1)):
        raise ValueError(f"Q1 request attempts are not contiguous: {target.key}")
    if len(attempts) > context.protocol.maximum_attempts_per_network_target:
        raise ValueError("Q1 per-target request budget exceeded")
    if part.exists():
        raise ValueError(f"Unaccounted Q1 partial archive exists: {part}")
    return len(attempts)


def marker_state(root: Path) -> MarkerState:
    request_paths = sorted(root.rglob("*.request.json")) if root.exists() else []
    response_paths = sorted(root.rglob("*.response.json")) if root.exists() else []
    received = 0
    files: dict[str, str] = {}
    for path in (*request_paths, *response_paths):
        files[path.relative_to(root).as_posix()] = file_sha256(path)
    for path in response_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("bytes_received")
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"Q1 response byte accounting changed: {path}")
        received += value
    return MarkerState(
        request_count=len(request_paths),
        response_count=len(response_paths),
        payload_bytes_received=received,
        manifest_hash=universe_evidence_hash({"marker_files": files}),
    )


def ensure_network_archive(
    *,
    root: Path,
    target: PeriodicFlowDevelopmentTarget,
    context: LoadedContext,
) -> tuple[Path, int]:
    if target.reuse_candidate_path is not None:
        raise ValueError("Q1 network transport refused a reuse target")
    attempts = reconcile_target_markers(root=root, target=target, context=context)
    destination = target_archive_path(root, target)
    if destination.exists():
        if file_sha256(destination) != target.published_archive_sha256:
            raise ValueError("Existing Q1 network archive checksum changed")
        if attempts == 0:
            raise ValueError("Existing Q1 network archive has no request evidence")
        latest = json.loads(
            marker_path(root, target, attempts, "response").read_text(encoding="utf-8")
        )
        if latest["outcome"] not in {
            "PASS",
            "RECOVERED_VERIFIED_ARCHIVE_AFTER_INTERRUPTION",
        }:
            raise ValueError("Existing Q1 archive lacks a successful final attempt")
        return destination, attempts
    if attempts >= context.protocol.maximum_attempts_per_network_target:
        raise AcquisitionFailure(f"Request budget exhausted for {target.key}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(
        attempts + 1,
        context.protocol.maximum_attempts_per_network_target + 1,
    ):
        state = marker_state(root)
        if state.request_count >= context.protocol.maximum_payload_get_attempts:
            raise AcquisitionFailure("Global Q1 payload request budget exhausted")
        free = shutil.disk_usage(root.parent.resolve()).free
        if free < (
            context.protocol.maximum_archive_bytes_each
            + context.protocol.minimum_free_disk_bytes_after_acquisition
        ):
            raise AcquisitionFailure("Insufficient disk for a bounded Q1 archive attempt")
        if (
            state.payload_bytes_received + context.protocol.maximum_archive_bytes_each
            > context.protocol.maximum_new_archive_bytes_total
        ):
            raise AcquisitionFailure(
                "Q1 cumulative payload byte budget cannot admit another attempt"
            )
        part = destination.with_name(f"{destination.name}.part")
        if part.exists():
            raise ValueError(f"Stale Q1 partial archive exists: {part}")
        write_request_marker(
            root=root,
            target=target,
            context=context,
            attempt=attempt,
        )
        received = 0
        status: int | None = None
        final_url = target.archive_url
        declared_length: int | None = None
        content_encoding = ""
        try:
            request = urllib.request.Request(
                target.archive_url,
                headers={
                    "Accept": "application/zip",
                    "Accept-Encoding": "identity",
                    "User-Agent": "Aurex-Q1-Full-Development-Acquisition/1.0",
                },
                method="GET",
            )
            with opener.open(
                request,
                timeout=context.protocol.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                final_url = response.geturl()
                content_encoding = response.headers.get("Content-Encoding", "").lower()
                if status != 200 or final_url != target.archive_url:
                    raise AcquisitionFailure("Q1 HTTP response identity changed")
                if content_encoding not in {"", "identity"}:
                    raise AcquisitionFailure("Q1 HTTP content encoding changed")
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    try:
                        declared_length = int(declared)
                    except ValueError as exc:
                        raise AcquisitionFailure("Q1 Content-Length is invalid") from exc
                    if not 0 < declared_length <= context.protocol.maximum_archive_bytes_each:
                        raise AcquisitionFailure("Q1 Content-Length exceeds the frozen limit")
                digest = hashlib.sha256()
                with part.open("xb") as output:
                    while chunk := response.read(1024 * 1024):
                        received += len(chunk)
                        if received > context.protocol.maximum_archive_bytes_each:
                            raise AcquisitionFailure("Q1 archive exceeded the per-file byte limit")
                        if (
                            state.payload_bytes_received + received
                            > context.protocol.maximum_new_archive_bytes_total
                        ):
                            raise AcquisitionFailure(
                                "Q1 cumulative received bytes exceeded the limit"
                            )
                        digest.update(chunk)
                        output.write(chunk)
                if declared_length is not None and received != declared_length:
                    raise AcquisitionFailure("Q1 payload size differs from Content-Length")
                if digest.hexdigest() != target.published_archive_sha256:
                    raise AcquisitionFailure("Q1 downloaded archive checksum mismatch")
            part.replace(destination)
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                content_length=declared_length,
                content_encoding=content_encoding or "identity",
                bytes_received=received,
                outcome="PASS",
            )
            return destination, attempt
        except urllib.error.HTTPError as exc:
            last_error = exc
            if part.exists():
                part.unlink()
            transient = exc.code in TRANSIENT_HTTP
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=exc.code,
                final_url=exc.geturl() or target.archive_url,
                content_length=None,
                content_encoding="identity",
                bytes_received=received,
                outcome="TRANSIENT" if transient else "HTTP_FAIL",
            )
            if not transient:
                raise AcquisitionFailure(f"Q1 HTTP {exc.code} for {target.key}") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = exc
            if part.exists():
                part.unlink()
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                content_length=declared_length,
                content_encoding=content_encoding or "identity",
                bytes_received=received,
                outcome="TRANSIENT",
            )
        except (AcquisitionFailure, RedirectRejectedError) as exc:
            if part.exists():
                part.unlink()
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                content_length=declared_length,
                content_encoding=content_encoding or "identity",
                bytes_received=received,
                outcome="INTEGRITY_FAIL",
            )
            raise AcquisitionFailure(str(exc)) from exc
        if attempt < context.protocol.maximum_attempts_per_network_target:
            time.sleep(context.protocol.retry_backoff_seconds[attempt - 1])
    raise AcquisitionFailure(f"Q1 payload unresolved for {target.key}") from last_error


def verify_reuse_archive(
    *,
    evidence_root: Path,
    target: PeriodicFlowDevelopmentTarget,
) -> Path:
    if target.reuse_candidate_path is None or target.reuse_candidate_file_sha256 is None:
        raise ValueError("Q1 reuse verification received a network target")
    path = resolved_archive_path(
        evidence_root=evidence_root,
        acquisition_root=Path("."),
        target=target,
    )
    if not path.is_file():
        raise AcquisitionFailure(f"Q1 reuse archive is missing: {target.key}")
    digest = file_sha256(path)
    if digest not in {
        target.reuse_candidate_file_sha256,
        target.published_archive_sha256,
    } or target.reuse_candidate_file_sha256 != target.published_archive_sha256:
        raise AcquisitionFailure(f"Q1 reuse archive checksum changed: {target.key}")
    return path


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("Q1 buyer-maker value is not boolean")


def normalized_header(row: list[str], aliases: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        aliases.get(value.strip().lower(), value.strip().lower()) for value in row
    )


def _validate_member_safety(
    member: zipfile.ZipInfo,
    *,
    protocol: PeriodicFlowFullDevelopmentProtocol,
) -> None:
    path = PurePosixPath(member.filename)
    unix_mode = (member.external_attr >> 16) & 0o170000
    if (
        member.is_dir()
        or path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or "\\" in member.filename
        or member.filename.startswith(("/", "\\"))
        or member.flag_bits & 0x1
        or unix_mode == stat.S_IFLNK
        or member.CRC == 0
        or member.compress_size <= 0
        or member.file_size <= 0
        or member.file_size > protocol.maximum_member_uncompressed_bytes_each
        or member.file_size
        > member.compress_size * protocol.maximum_zip_expansion_ratio
    ):
        raise ValueError(f"Q1 ZIP member is unsafe or outside limits: {member.filename}")


def select_zip_member(
    archive: zipfile.ZipFile,
    *,
    target: PeriodicFlowDevelopmentTarget,
    protocol: PeriodicFlowFullDevelopmentProtocol,
) -> tuple[zipfile.ZipInfo, int, int, str | None, str | None, str | None, bool | None]:
    files = [member for member in archive.infolist() if not member.is_dir()]
    for member in files:
        _validate_member_safety(member, protocol=protocol)
    canonical = [
        member
        for member in files
        if member.filename == target.expected_member_name
        and len(PurePosixPath(member.filename).parts) == 1
    ]
    if len(canonical) != 1:
        raise ValueError(f"Q1 canonical ZIP member changed: {target.key}")
    duplicate_name = None
    canonical_hash = None
    duplicate_hash = None
    identical = None
    if target.member_policy == "EXACT_EXPECTED_MEMBER_ONLY":
        if len(files) != 1:
            raise ValueError(f"Q1 ordinary ZIP member matrix changed: {target.key}")
    else:
        duplicates = [member for member in files if member is not canonical[0]]
        if (
            len(files) != 2
            or len(duplicates) != 1
            or duplicates[0].filename != KNOWN_DUPLICATE_MEMBER
        ):
            raise ValueError("Q1 2021-12 duplicate-member matrix changed")

        def member_sha256(member: zipfile.ZipInfo) -> str:
            digest = hashlib.sha256()
            with archive.open(member) as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()

        canonical_hash = member_sha256(canonical[0])
        duplicate_hash = member_sha256(duplicates[0])
        duplicate_name = duplicates[0].filename
        identical = (
            canonical[0].file_size == duplicates[0].file_size
            and canonical_hash == duplicate_hash
        )
        if not identical:
            raise ValueError("Q1 2021-12 ZIP members are not byte-identical")
    return (
        canonical[0],
        sum(member.compress_size for member in files),
        sum(member.file_size for member in files),
        duplicate_name,
        canonical_hash,
        duplicate_hash,
        identical,
    )


def evidence_reason_codes(
    *,
    product: str,
    row_count: int,
    coverage: Decimal,
    maximum_event_gap_minutes: int,
    non_increasing: int,
    duplicates: int,
    forward_gaps: int,
    skipped_fraction: Decimal,
    max_skip: int,
    raw_range_gaps: int | None,
    raw_range_non_increasing: int | None,
    timestamp_regressions: int,
    makers: tuple[bool, ...],
) -> tuple[str, ...]:
    reasons = []
    if row_count < 100_000:
        reasons.append("ROW_COUNT_BELOW_100000")
    if coverage < Decimal("0.99"):
        reasons.append("MINUTE_COVERAGE_BELOW_0_99")
    if maximum_event_gap_minutes > 15:
        reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
    if non_increasing:
        reasons.append("PRIMARY_ID_NOT_STRICTLY_INCREASING")
    if duplicates:
        reasons.append("PRIMARY_ID_DUPLICATE")
    if timestamp_regressions:
        reasons.append("TIMESTAMP_REGRESSION")
    if makers != (False, True):
        reasons.append("BUYER_MAKER_DOMAIN_INCOMPLETE")
    if product == "SPOT":
        if forward_gaps:
            reasons.append("SPOT_AGGREGATE_ID_GAP")
        if raw_range_gaps:
            reasons.append("SPOT_RAW_RANGE_GAP")
        if raw_range_non_increasing:
            reasons.append("SPOT_RAW_RANGE_OVERLAP_OR_REGRESSION")
    else:
        if skipped_fraction > Decimal("0.001"):
            reasons.append("SKIPPED_TRADE_ID_FRACTION_EXCEEDS_0_001")
        if max_skip > 100:
            reasons.append("SINGLE_SKIPPED_TRADE_ID_COUNT_EXCEEDS_100")
    return tuple(sorted(reasons))


def inspect_archive(
    *,
    target: PeriodicFlowDevelopmentTarget,
    archive_path: Path,
    evidence_root: Path,
    protocol: PeriodicFlowFullDevelopmentProtocol,
    source_mode: str,
    get_attempt_count: int,
) -> ArchiveInspection:
    archive_hash = file_sha256(archive_path)
    if archive_hash != target.published_archive_sha256:
        raise ValueError(f"Q1 archive checksum changed during inspection: {target.key}")
    start_ms, end_ms, expected_minutes = month_bounds_ms(target.month)
    row_count = 0
    min_timestamp: int | None = None
    max_timestamp: int | None = None
    previous_timestamp: int | None = None
    min_primary: int | None = None
    max_primary: int | None = None
    previous_primary: int | None = None
    non_increasing = 0
    duplicates = 0
    forward_gap_count = 0
    skipped_count = 0
    max_skip = 0
    min_raw: int | None = None
    max_raw: int | None = None
    previous_last_raw: int | None = None
    raw_range_gaps = 0
    raw_range_non_increasing = 0
    timestamp_regressions = 0
    makers: set[bool] = set()
    minutes: set[int] = set()
    header_present = False
    with zipfile.ZipFile(archive_path) as archive:
        (
            member,
            compressed_total,
            uncompressed_total,
            duplicate_name,
            canonical_hash,
            duplicate_hash,
            duplicate_identical,
        ) = select_zip_member(archive, target=target, protocol=protocol)
        with archive.open(member) as binary:
            reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline=""))
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("Q1 structural CSV is empty") from exc
            if len(first_row) != len(target.expected_columns):
                raise ValueError("Q1 structural CSV column count changed")
            try:
                int(first_row[0])
            except ValueError:
                header_present = True
                aliases = SPOT_HEADER_ALIASES if target.product == "SPOT" else RAW_HEADER_ALIASES
                if normalized_header(first_row, aliases) != target.expected_columns:
                    raise ValueError("Q1 structural CSV header changed") from None
                rows = reader
            else:
                rows = chain((first_row,), reader)
            for row in rows:
                if len(row) != len(target.expected_columns):
                    raise ValueError("Q1 structural CSV column count changed")
                try:
                    primary_id = int(row[0])
                    if target.product == "SPOT":
                        first_raw = int(row[3])
                        last_raw = int(row[4])
                        timestamp = int(row[5])
                        maker = parse_bool(row[6])
                        if first_raw > last_raw:
                            raise ValueError("Q1 Spot raw trade range is reversed")
                    else:
                        first_raw = None
                        last_raw = None
                        timestamp = int(row[4])
                        maker = parse_bool(row[5])
                except ValueError as exc:
                    raise ValueError(
                        "Q1 structural ID, timestamp, or maker value is invalid"
                    ) from exc
                if not start_ms <= timestamp < end_ms:
                    raise ValueError("Q1 structural timestamp is outside the frozen month")
                if previous_primary is not None:
                    if primary_id <= previous_primary:
                        non_increasing += 1
                        if primary_id == previous_primary:
                            duplicates += 1
                    elif primary_id > previous_primary + 1:
                        forward_gap_count += 1
                        skipped = primary_id - previous_primary - 1
                        skipped_count += skipped
                        max_skip = max(max_skip, skipped)
                if previous_timestamp is not None and timestamp < previous_timestamp:
                    timestamp_regressions += 1
                if target.product == "SPOT" and first_raw is not None and last_raw is not None:
                    if previous_last_raw is not None:
                        if first_raw <= previous_last_raw:
                            raw_range_non_increasing += 1
                        elif first_raw > previous_last_raw + 1:
                            raw_range_gaps += 1
                    min_raw = first_raw if min_raw is None else min(min_raw, first_raw)
                    max_raw = last_raw if max_raw is None else max(max_raw, last_raw)
                    previous_last_raw = last_raw
                min_primary = primary_id if min_primary is None else min(min_primary, primary_id)
                max_primary = primary_id if max_primary is None else max(max_primary, primary_id)
                min_timestamp = (
                    timestamp if min_timestamp is None else min(min_timestamp, timestamp)
                )
                max_timestamp = (
                    timestamp if max_timestamp is None else max(max_timestamp, timestamp)
                )
                previous_primary = primary_id
                previous_timestamp = timestamp
                makers.add(maker)
                minutes.add((timestamp - start_ms) // 60_000)
                row_count += 1
    if (
        row_count == 0
        or min_timestamp is None
        or max_timestamp is None
        or min_primary is None
        or max_primary is None
    ):
        raise ValueError("Q1 structural CSV has no rows")
    ordered_minutes = sorted(minutes)
    maximum_event_gap = max(
        (
            current - previous
            for previous, current in zip(
                ordered_minutes, ordered_minutes[1:], strict=False
            )
        ),
        default=0,
    )
    span = max_primary - min_primary + 1
    skipped_fraction = Decimal(skipped_count) / Decimal(span) if span > 0 else Decimal(0)
    if target.product == "SPOT":
        skipped_count_for_model = 0
        skipped_fraction_for_model = Decimal(0)
        max_skip_for_model = 0
    else:
        skipped_count_for_model = skipped_count
        skipped_fraction_for_model = skipped_fraction
        max_skip_for_model = max_skip
    coverage = Decimal(len(minutes)) / Decimal(expected_minutes)
    maker_tuple = tuple(sorted(makers))
    reasons = evidence_reason_codes(
        product=target.product,
        row_count=row_count,
        coverage=coverage,
        maximum_event_gap_minutes=maximum_event_gap,
        non_increasing=non_increasing,
        duplicates=duplicates,
        forward_gaps=forward_gap_count,
        skipped_fraction=skipped_fraction_for_model,
        max_skip=max_skip_for_model,
        raw_range_gaps=raw_range_gaps if target.product == "SPOT" else None,
        raw_range_non_increasing=(
            raw_range_non_increasing if target.product == "SPOT" else None
        ),
        timestamp_regressions=timestamp_regressions,
        makers=maker_tuple,
    )
    local_path = archive_path.resolve().relative_to(evidence_root.resolve()).as_posix()
    evidence = PeriodicFlowArchiveEvidence(
        month=target.month,
        product=target.product,
        family=target.family,
        source_mode=source_mode,
        archive_url=target.archive_url,
        local_path=local_path,
        archive_bytes=archive_path.stat().st_size,
        archive_sha256=archive_hash,
        zip_member_count=(2 if duplicate_name is not None else 1),
        selected_member_name=member.filename,
        zip_compressed_bytes_total=compressed_total,
        zip_uncompressed_bytes_total=uncompressed_total,
        selected_member_uncompressed_bytes=member.file_size,
        duplicate_member_name=duplicate_name,
        canonical_member_sha256=canonical_hash,
        duplicate_member_sha256=duplicate_hash,
        duplicate_member_byte_identical=duplicate_identical,
        column_count=len(target.expected_columns),
        header_present=header_present,
        row_count=row_count,
        first_timestamp_ms=min_timestamp,
        last_timestamp_ms=max_timestamp,
        unique_minute_count=len(minutes),
        expected_minute_count=expected_minutes,
        minute_coverage_fraction=coverage,
        maximum_event_gap_minutes=maximum_event_gap,
        first_primary_id=min_primary,
        last_primary_id=max_primary,
        primary_id_non_increasing_count=non_increasing,
        primary_id_duplicate_count=duplicates,
        primary_id_forward_gap_count=forward_gap_count,
        primary_id_skipped_count=skipped_count_for_model,
        primary_id_skipped_fraction=skipped_fraction_for_model,
        maximum_single_primary_id_skip_count=max_skip_for_model,
        first_raw_trade_id=min_raw if target.product == "SPOT" else None,
        last_raw_trade_id=max_raw if target.product == "SPOT" else None,
        raw_range_gap_count=raw_range_gaps if target.product == "SPOT" else None,
        raw_range_non_increasing_count=(
            raw_range_non_increasing if target.product == "SPOT" else None
        ),
        timestamp_regression_count=timestamp_regressions,
        buyer_maker_values_observed=maker_tuple,
        payload_get_attempt_count=get_attempt_count,
        new_archive_bytes=(archive_path.stat().st_size if source_mode == "NETWORK_ACQUIRED" else 0),
        archive_pass=not reasons,
        reason_codes=reasons,
        parsed_numeric_fields=(
            ("aggregate_trade_id", "first_trade_id", "last_trade_id", "timestamp")
            if target.product == "SPOT"
            else ("timestamp", "trade_id")
        ),
    )
    return ArchiveInspection(evidence=evidence, minute_indexes=frozenset(minutes))


def pair_month(
    month: str,
    spot: ArchiveInspection,
    raw: ArchiveInspection,
) -> PeriodicFlowPairedMonthEvidence:
    _, _, expected = month_bounds_ms(month)
    paired = len(spot.minute_indexes & raw.minute_indexes)
    coverage = Decimal(paired) / Decimal(expected)
    reasons = () if coverage >= Decimal("0.99") else ("PAIRED_MINUTE_COVERAGE_BELOW_0_99",)
    return PeriodicFlowPairedMonthEvidence(
        month=month,
        spot_unique_minute_count=len(spot.minute_indexes),
        raw_unique_minute_count=len(raw.minute_indexes),
        paired_unique_minute_count=paired,
        expected_minute_count=expected,
        paired_minute_coverage_fraction=coverage,
        paired_clock_pass=not reasons,
        reason_codes=reasons,
    )


def empty_or_loaded_checkpoint(
    *,
    path: Path,
    context: LoadedContext,
    acquisition_root: Path,
) -> PeriodicFlowAcquisitionCheckpoint:
    if path.exists():
        checkpoint = PeriodicFlowAcquisitionCheckpoint.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        state = marker_state(acquisition_root)
        if (
            checkpoint.protocol_evidence_hash != context.protocol.protocol_evidence_hash
            or checkpoint.execution_contract_evidence_hash
            != context.contract.contract_evidence_hash
            or checkpoint.runner_source_hash != context.contract.runner_source_hash
            or checkpoint.request_marker_count != state.request_count
            or checkpoint.response_marker_count != state.response_count
            or checkpoint.request_marker_manifest_hash != state.manifest_hash
            or checkpoint.cumulative_payload_bytes_received
            != state.payload_bytes_received
        ):
            raise ValueError("Q1 checkpoint authority or marker state changed")
        return checkpoint
    return build_checkpoint(
        updated_at=datetime.now(UTC),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        archive_evidence=(),
        paired_month_evidence=(),
        request_marker_count=0,
        response_marker_count=0,
        request_marker_manifest_hash=universe_evidence_hash({"marker_files": {}}),
        cumulative_payload_bytes_received=0,
        total_new_archive_bytes=0,
        total_member_uncompressed_bytes=0,
    )


def write_checkpoint(
    *,
    path: Path,
    context: LoadedContext,
    acquisition_root: Path,
    archives: list[PeriodicFlowArchiveEvidence],
    pairs: list[PeriodicFlowPairedMonthEvidence],
) -> PeriodicFlowAcquisitionCheckpoint:
    state = marker_state(acquisition_root)
    if state.request_count != state.response_count:
        raise ValueError("Q1 checkpoint refused unmatched HTTP markers")
    checkpoint = build_checkpoint(
        updated_at=datetime.now(UTC),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        archive_evidence=tuple(archives),
        paired_month_evidence=tuple(pairs),
        request_marker_count=state.request_count,
        response_marker_count=state.response_count,
        request_marker_manifest_hash=state.manifest_hash,
        cumulative_payload_bytes_received=state.payload_bytes_received,
        total_new_archive_bytes=sum(item.new_archive_bytes for item in archives),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes_total for item in archives
        ),
    )
    _write_json_transactional(path, checkpoint.model_dump(mode="json"), overwrite=True)
    stored = PeriodicFlowAcquisitionCheckpoint.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if stored != checkpoint:
        raise ValueError("Q1 checkpoint did not round-trip")
    return checkpoint


def verify_checkpoint_archives(
    *,
    checkpoint: PeriodicFlowAcquisitionCheckpoint,
    evidence_root: Path,
) -> None:
    for evidence in checkpoint.archive_evidence:
        path = (evidence_root / evidence.local_path).resolve()
        if (
            not path.is_relative_to(evidence_root.resolve())
            or not path.is_file()
            or path.stat().st_size != evidence.archive_bytes
            or file_sha256(path) != evidence.archive_sha256
        ):
            raise ValueError(f"Q1 checkpoint archive changed: {evidence.key}")


def preflight(args: argparse.Namespace, context: LoadedContext) -> dict:
    if args.result.exists():
        raise ValueError("A terminal Q1 acquisition result already exists")
    if list(args.acquisition_root.rglob("*.part")):
        raise ValueError("Unaccounted Q1 partial files exist before preflight")
    reused = [target for target in context.protocol.targets if target.reuse_candidate_path]
    reused_bytes = 0
    for index, target in enumerate(reused, start=1):
        path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
        reused_bytes += path.stat().st_size
        with zipfile.ZipFile(path) as archive:
            select_zip_member(archive, target=target, protocol=context.protocol)
        print(f"PREFLIGHT_REUSE {index}/37 {target.month} {target.product} PASS", flush=True)
    free = shutil.disk_usage(args.acquisition_root.parent.resolve()).free
    required = (
        context.protocol.maximum_new_archive_bytes_total
        + context.protocol.minimum_free_disk_bytes_after_acquisition
    )
    result = {
        "status": "PASS" if free >= required else "BLOCKED_INSUFFICIENT_FREE_DISK",
        "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
        "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
        "runner_source_hash": context.contract.runner_source_hash,
        "reuse_candidates_verified": len(reused),
        "reuse_candidate_bytes": reused_bytes,
        "network_targets_authorized": context.protocol.network_target_count,
        "free_disk_bytes": free,
        "required_free_disk_bytes_before_acquisition": required,
        "additional_free_disk_bytes_required": max(0, required - free),
        "network_requests_made": marker_state(args.acquisition_root).request_count,
        "price_or_quantity_values_parsed": [],
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise AcquisitionFailure(
            "Q1 preflight requires the full 100 GB new-archive ceiling plus the "
            "20 GB remaining-disk reserve"
        )
    return result


def result_limitations() -> tuple[str, ...]:
    return (
        "A pass covers structural paired development archives only.",
        "Archive acquisition does not establish a market mechanism or edge.",
        "Buyer-maker flags are structural source fields, not trading signals.",
        "Development covers 2020-01 through 2023-12 only.",
        "No price, quantity, quote quantity, feature, or return was parsed.",
        "No parameter, strategy candidate, or Pine implementation was created.",
        "Validation, holdout, and forward outcomes remained sealed.",
        "Paper and Testnet strategy-order authority remain false.",
        "Production, live, real-capital authority, and profit remain false.",
        "A pass permits only a separately frozen no-outcome measurement protocol.",
    )


def write_result(
    *,
    args: argparse.Namespace,
    context: LoadedContext,
    checkpoint: PeriodicFlowAcquisitionCheckpoint,
    failed_target_key: str | None,
    failure_reason: str | None,
) -> PeriodicFlowAcquisitionResult:
    result = build_acquisition_result(
        generated_at=datetime.now(UTC),
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        completed_archive_count=len(checkpoint.archive_evidence),
        completed_paired_month_count=len(checkpoint.paired_month_evidence),
        request_marker_count=checkpoint.request_marker_count,
        cumulative_payload_bytes_received=checkpoint.cumulative_payload_bytes_received,
        total_new_archive_bytes=checkpoint.total_new_archive_bytes,
        failed_target_key=failed_target_key,
        failure_reason=failure_reason,
        limitations=result_limitations(),
    )
    _write_json_transactional(args.result, result.model_dump(mode="json"), overwrite=False)
    if PeriodicFlowAcquisitionResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    ) != result:
        raise ValueError("Q1 acquisition result did not round-trip")
    return result


def run_acquisition(
    args: argparse.Namespace,
    context: LoadedContext,
) -> PeriodicFlowAcquisitionResult:
    preflight(args, context)
    checkpoint = empty_or_loaded_checkpoint(
        path=args.checkpoint,
        context=context,
        acquisition_root=args.acquisition_root,
    )
    if not args.checkpoint.exists():
        checkpoint = write_checkpoint(
            path=args.checkpoint,
            context=context,
            acquisition_root=args.acquisition_root,
            archives=[],
            pairs=[],
        )
    verify_checkpoint_archives(checkpoint=checkpoint, evidence_root=args.evidence_root)
    archives = list(checkpoint.archive_evidence)
    pairs = list(checkpoint.paired_month_evidence)
    completed = {item.key: item for item in archives}
    paired = {item.month: item for item in pairs}
    targets = sorted(context.protocol.targets, key=lambda item: item.key)
    target_by_key = {target.key: target for target in targets}
    in_memory: dict[tuple[str, str], ArchiveInspection] = {}
    active_key = "PRE_ACQUISITION"
    try:
        for target in targets:
            active_key = _marker_target_key(target)
            if target.key not in completed:
                if target.reuse_candidate_path is not None:
                    archive_path = verify_reuse_archive(
                        evidence_root=args.evidence_root,
                        target=target,
                    )
                    source_mode = "REUSED_LOCAL"
                    attempts = 0
                else:
                    archive_path, attempts = ensure_network_archive(
                        root=args.acquisition_root,
                        target=target,
                        context=context,
                    )
                    source_mode = "NETWORK_ACQUIRED"
                inspection = inspect_archive(
                    target=target,
                    archive_path=archive_path,
                    evidence_root=args.evidence_root,
                    protocol=context.protocol,
                    source_mode=source_mode,
                    get_attempt_count=attempts,
                )
                if not inspection.evidence.archive_pass:
                    raise AcquisitionFailure(
                        f"Archive structural gates failed: {inspection.evidence.reason_codes}"
                    )
                archives.append(inspection.evidence)
                completed[target.key] = inspection.evidence
                in_memory[target.key] = inspection
                checkpoint = write_checkpoint(
                    path=args.checkpoint,
                    context=context,
                    acquisition_root=args.acquisition_root,
                    archives=archives,
                    pairs=pairs,
                )
                print(
                    f"ARCHIVE {len(archives)}/96 {target.month} {target.product} PASS "
                    f"rows={inspection.evidence.row_count}",
                    flush=True,
                )
            if target.product == "USD_M_PERPETUAL" and target.month not in paired:
                spot_target = target_by_key[(target.month, "SPOT")]
                raw_target = target
                for pair_target in (spot_target, raw_target):
                    if pair_target.key not in in_memory:
                        evidence = completed[pair_target.key]
                        path = (args.evidence_root / evidence.local_path).resolve()
                        rebuilt = inspect_archive(
                            target=pair_target,
                            archive_path=path,
                            evidence_root=args.evidence_root,
                            protocol=context.protocol,
                            source_mode=evidence.source_mode,
                            get_attempt_count=evidence.payload_get_attempt_count,
                        )
                        if rebuilt.evidence != evidence:
                            raise ValueError(
                                "Q1 checkpoint evidence did not reconstruct: "
                                f"{pair_target.key}"
                            )
                        in_memory[pair_target.key] = rebuilt
                pair = pair_month(
                    target.month,
                    in_memory[spot_target.key],
                    in_memory[raw_target.key],
                )
                if not pair.paired_clock_pass:
                    raise AcquisitionFailure(
                        f"Paired-minute gate failed: {pair.reason_codes}"
                    )
                pairs.append(pair)
                paired[target.month] = pair
                checkpoint = write_checkpoint(
                    path=args.checkpoint,
                    context=context,
                    acquisition_root=args.acquisition_root,
                    archives=archives,
                    pairs=pairs,
                )
                in_memory.pop(spot_target.key, None)
                in_memory.pop(raw_target.key, None)
                print(
                    f"PAIRED {len(pairs)}/48 {target.month} PASS "
                    f"coverage={pair.paired_minute_coverage_fraction}",
                    flush=True,
                )
        result = write_result(
            args=args,
            context=context,
            checkpoint=checkpoint,
            failed_target_key=None,
            failure_reason=None,
        )
        return result
    except AcquisitionFailure as exc:
        checkpoint = write_checkpoint(
            path=args.checkpoint,
            context=context,
            acquisition_root=args.acquisition_root,
            archives=archives,
            pairs=pairs,
        )
        return write_result(
            args=args,
            context=context,
            checkpoint=checkpoint,
            failed_target_key=active_key,
            failure_reason=str(exc),
        )


def check_state(args: argparse.Namespace, context: LoadedContext) -> dict:
    checkpoint = empty_or_loaded_checkpoint(
        path=args.checkpoint,
        context=context,
        acquisition_root=args.acquisition_root,
    )
    verify_checkpoint_archives(checkpoint=checkpoint, evidence_root=args.evidence_root)
    result = None
    if args.result.exists():
        result = PeriodicFlowAcquisitionResult.model_validate_json(
            args.result.read_text(encoding="utf-8")
        )
        if (
            result.protocol_evidence_hash != context.protocol.protocol_evidence_hash
            or result.execution_contract_evidence_hash
            != context.contract.contract_evidence_hash
            or result.runner_source_hash != context.contract.runner_source_hash
            or result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
            or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        ):
            raise ValueError("Q1 terminal result changed")
    summary = {
        "status": "PASS",
        "completed_archives": len(checkpoint.archive_evidence),
        "completed_paired_months": len(checkpoint.paired_month_evidence),
        "request_markers": checkpoint.request_marker_count,
        "terminal_result": None if result is None else result.decision,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight, run, or check the frozen Q1 paired development acquisition."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        context = load_context(args)
        if args.preflight:
            preflight(args, context)
        elif args.check:
            check_state(args, context)
        else:
            result = run_acquisition(args, context)
            print(
                f"RESULT {result.decision} archives={result.completed_archive_count} "
                f"paired_months={result.completed_paired_month_count} "
                f"requests={result.request_marker_count}",
                flush=True,
            )
            if result.decision != "PERMIT_Q1_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL":
                return 1
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
