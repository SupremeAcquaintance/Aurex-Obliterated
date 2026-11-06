from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionProtocol,
    PeriodicFlowSuccessorAcquisitionProtocolAudit,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    audit_hash as audit_protocol_hash,
)
from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    PeriodicFlowExcludedMonthEvidence,
    PeriodicFlowSuccessorCheckpoint,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV3,
    PeriodicFlowSuccessorCheckpointV3,
    PeriodicFlowSuccessorExecutionContractAuditV3,
    PeriodicFlowSuccessorExecutionContractV3,
    PeriodicFlowSuccessorTransportAmendmentAuditV3,
    PeriodicFlowSuccessorTransportAmendmentV3,
    audit_hash,
    build_acquisition_result_v3,
    build_checkpoint_v3,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    AcquisitionFailure,
    LoadedContext,
    NoRedirectHandler,
    _write_json_transactional,
    file_sha256,
    inspect_archive,
    pair_month,
    resolved_archive_path,
    select_zip_member,
    source_contract_hash,
    target_archive_path,
    verify_reuse_archive,
)
from scripts.run_periodic_flow_successor_acquisition import (  # noqa: E402
    result_limitations,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v3.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_audit_v3.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v3.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v3.json"
)
DEFAULT_V2_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v2.json"
)
DEFAULT_V2_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v2.json"
)
DEFAULT_V2_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v2.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v3"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v3.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v3.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_transport_v3.py"
)
SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v3.py")
V2_MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_runner.py")
V2_SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition.py")
INHERITED_MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_full_development_runner.py"
)
INHERITED_SCRIPT_PATH = Path(
    "scripts/run_periodic_flow_full_development_acquisition.py"
)
BOOTSTRAP_MARKER_NAME = "BTCUSDT-trades-2020-05.zip.bootstrap.json"
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class MarkerStateV3:
    request_count: int
    response_count: int
    payload_bytes_received: int
    manifest_hash: str


class IncompleteBodyError(OSError):
    pass


class ProtocolTransportAdapterV3:
    def __init__(
        self,
        protocol: PeriodicFlowSuccessorAcquisitionProtocol,
        amendment: PeriodicFlowSuccessorTransportAmendmentV3,
    ):
        self._protocol = protocol
        self._amendment = amendment
        self.maximum_archive_bytes_each = protocol.maximum_archive_bytes
        self.maximum_member_uncompressed_bytes_each = (
            protocol.maximum_member_uncompressed_bytes
        )
        self.maximum_attempts_per_network_target = (
            amendment.maximum_get_attempts_per_target
        )
        self.maximum_payload_get_attempts = amendment.maximum_payload_get_attempts
        self.retry_backoff_seconds = amendment.retry_delays_seconds
        self.request_timeout_seconds = amendment.connect_timeout_seconds

    def __getattr__(self, name: str):
        try:
            return getattr(self._amendment, name)
        except AttributeError:
            return getattr(self._protocol, name)


def current_runner_source_hash_v3() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (
            MODULE_PATH,
            SCRIPT_PATH,
            V2_MODULE_PATH,
            V2_SCRIPT_PATH,
            INHERITED_MODULE_PATH,
            INHERITED_SCRIPT_PATH,
        ),
    )


def _set_idle_socket_timeout(response, seconds: int) -> None:
    raw = getattr(getattr(response, "fp", None), "raw", None)
    socket = getattr(raw, "_sock", None)
    if socket is not None:
        socket.settimeout(seconds)


def _attempt_path(root: Path, target, attempt: int, kind: str) -> Path:
    archive = target_archive_path(root, target)
    return archive.with_name(f"{archive.name}.get.{attempt}.{kind}.json")


def _bootstrap_marker_path(root: Path, target) -> Path:
    return target_archive_path(root, target).with_name(BOOTSTRAP_MARKER_NAME)


def _safe_error(exc: BaseException | None) -> tuple[str, str]:
    if exc is None:
        return "None", ""
    message = " ".join(str(exc).split())[:500]
    return type(exc).__name__[:100], message


def _write_request_marker_v3(
    *, root: Path, target, context: LoadedContext, attempt: int, range_start: int
) -> None:
    _write_json_transactional(
        _attempt_path(root, target, attempt, "request"),
        {
            "schema_version": context.protocol.request_marker_schema,
            "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
            "transport_amendment_evidence_hash": (
                context.protocol.amendment_evidence_hash
            ),
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "target_key": f"{target.month}|{target.product}",
            "month": target.month,
            "product": target.product,
            "family": target.family,
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
            "accept": "application/zip",
            "accept_encoding": "identity",
            "range_start": range_start,
            "range": f"bytes={range_start}-" if range_start else None,
            "requested_at": datetime.now(UTC).isoformat(),
        },
        overwrite=False,
    )


def _write_response_marker_v3(
    *,
    root: Path,
    target,
    context: LoadedContext,
    attempt: int,
    status: int | None,
    final_url: str,
    response_content_length: int | None,
    expected_total_bytes: int | None,
    content_range: str | None,
    bytes_received: int,
    partial_bytes_after_attempt: int,
    outcome: str,
    failure_class: str,
    error: BaseException | None,
) -> None:
    error_type, error_message = _safe_error(error)
    _write_json_transactional(
        _attempt_path(root, target, attempt, "response"),
        {
            "schema_version": context.protocol.response_marker_schema,
            "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
            "transport_amendment_evidence_hash": (
                context.protocol.amendment_evidence_hash
            ),
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "target_key": f"{target.month}|{target.product}",
            "month": target.month,
            "product": target.product,
            "family": target.family,
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
            "status": status,
            "final_url": final_url,
            "response_content_length": response_content_length,
            "expected_total_bytes": expected_total_bytes,
            "content_range": content_range,
            "content_encoding": "identity",
            "bytes_received": bytes_received,
            "partial_bytes_after_attempt": partial_bytes_after_attempt,
            "outcome": outcome,
            "failure_class": failure_class,
            "exception_type": error_type,
            "exception_message": error_message,
            "completed_at": datetime.now(UTC).isoformat(),
        },
        overwrite=False,
    )


def _common_marker_values(target, context: LoadedContext, attempt: int) -> dict:
    return {
        "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
        "transport_amendment_evidence_hash": (
            context.protocol.amendment_evidence_hash
        ),
        "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
        "target_key": f"{target.month}|{target.product}",
        "month": target.month,
        "product": target.product,
        "family": target.family,
        "method": "GET",
        "url": target.archive_url,
        "attempt": attempt,
    }


def _validate_request_marker_v3(
    payload: dict, *, target, context: LoadedContext, attempt: int
) -> None:
    common = _common_marker_values(target, context, attempt)
    range_start = payload.get("range_start")
    expected_range = (
        f"bytes={range_start}-" if isinstance(range_start, int) and range_start else None
    )
    if (
        payload.get("schema_version") != context.protocol.request_marker_schema
        or any(payload.get(key) != value for key, value in common.items())
        or payload.get("accept") != "application/zip"
        or payload.get("accept_encoding") != "identity"
        or not isinstance(range_start, int)
        or range_start < 0
        or payload.get("range") != expected_range
        or not isinstance(payload.get("requested_at"), str)
    ):
        raise ValueError(f"Q1 successor v3 request marker changed: {target.key}")


def _validate_response_marker_v3(
    payload: dict, *, target, context: LoadedContext, attempt: int
) -> None:
    common = _common_marker_values(target, context, attempt)
    integer_fields = ("bytes_received", "partial_bytes_after_attempt")
    nullable_positive = ("response_content_length", "expected_total_bytes")
    if (
        payload.get("schema_version") != context.protocol.response_marker_schema
        or any(payload.get(key) != value for key, value in common.items())
        or payload.get("final_url") != target.archive_url
        or payload.get("content_encoding") != "identity"
        or any(
            not isinstance(payload.get(field), int) or payload[field] < 0
            for field in integer_fields
        )
        or any(
            payload.get(field) is not None
            and (not isinstance(payload[field], int) or payload[field] <= 0)
            for field in nullable_positive
        )
        or payload.get("outcome")
        not in {
            "PASS",
            "TRANSIENT",
            "HTTP_FAIL",
            "INTEGRITY_FAIL",
            "INTERRUPTED_RESUMABLE",
        }
        or not isinstance(payload.get("failure_class"), str)
        or not isinstance(payload.get("exception_type"), str)
        or not isinstance(payload.get("exception_message"), str)
        or len(payload["exception_message"]) > 500
        or not isinstance(payload.get("completed_at"), str)
    ):
        raise ValueError(f"Q1 successor v3 response marker changed: {target.key}")


def marker_state_v3(root: Path) -> MarkerStateV3:
    request_paths = sorted(root.rglob("*.request.json")) if root.exists() else []
    response_paths = sorted(root.rglob("*.response.json")) if root.exists() else []
    bootstrap_paths = sorted(root.rglob("*.bootstrap.json")) if root.exists() else []
    files: dict[str, str] = {}
    received = 0
    for path in (*bootstrap_paths, *request_paths, *response_paths):
        files[path.relative_to(root).as_posix()] = file_sha256(path)
    for path in response_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("bytes_received")
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"Q1 successor v3 response byte accounting changed: {path}")
        received += value
    return MarkerStateV3(
        request_count=len(request_paths),
        response_count=len(response_paths),
        payload_bytes_received=received,
        manifest_hash=universe_evidence_hash({"marker_files": files}),
    )


def _known_total_from_markers(root: Path, target) -> int | None:
    values: set[int] = set()
    archive = target_archive_path(root, target)
    for path in sorted(archive.parent.glob(f"{archive.name}.get.*.response.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("expected_total_bytes")
        if isinstance(value, int):
            values.add(value)
    if len(values) > 1:
        raise ValueError(f"Q1 successor v3 target total changed: {target.key}")
    return next(iter(values), None)


def _parse_content_range(value: str, *, start: int) -> tuple[int, int]:
    try:
        unit, interval = value.split(" ", 1)
        bounds, total_text = interval.split("/", 1)
        start_text, end_text = bounds.split("-", 1)
        observed_start = int(start_text)
        end = int(end_text)
        total = int(total_text)
    except (TypeError, ValueError) as exc:
        raise AcquisitionFailure("Q1 successor v3 Content-Range is malformed") from exc
    if unit != "bytes" or observed_start != start or not start <= end < total:
        raise AcquisitionFailure("Q1 successor v3 Content-Range identity changed")
    return end, total


def ensure_bootstrap_partial(
    *, root: Path, target, context: LoadedContext
) -> Path:
    if f"{target.month}|{target.product}" != context.protocol.bootstrap_target_key:
        raise ValueError("Q1 successor v3 bootstrap target changed")
    source = (PROJECT_ROOT / context.protocol.bootstrap_partial_path).resolve()
    destination = target_archive_path(root, target)
    partial = destination.with_name(f"{destination.name}.part")
    marker = _bootstrap_marker_path(root, target)
    request_paths = tuple(destination.parent.glob(f"{destination.name}.get.*.request.json"))
    if marker.exists():
        payload = json.loads(marker.read_text(encoding="utf-8"))
        partial_is_valid = (
            partial.exists()
            and partial.stat().st_size >= context.protocol.bootstrap_partial_bytes
        )
        destination_is_valid = (
            destination.exists()
            and destination.stat().st_size
            == context.protocol.bootstrap_expected_total_bytes
            and file_sha256(destination) == target.published_archive_sha256
        )
        if (
            payload.get("schema_version")
            != "aurex-q1-periodic-flow-successor-partial-bootstrap-v3"
            or payload.get("transport_amendment_evidence_hash")
            != context.protocol.amendment_evidence_hash
            or payload.get("execution_contract_evidence_hash")
            != context.contract.contract_evidence_hash
            or payload.get("source_file_sha256")
            != context.protocol.bootstrap_partial_file_sha256
            or payload.get("source_bytes") != context.protocol.bootstrap_partial_bytes
            or not (partial_is_valid or destination_is_valid)
        ):
            raise ValueError("Q1 successor v3 bootstrap marker changed")
        return partial if partial_is_valid else destination
    if request_paths:
        raise ValueError("Q1 successor v3 requests exist without bootstrap evidence")
    if (
        not source.is_file()
        or source.stat().st_size != context.protocol.bootstrap_partial_bytes
        or file_sha256(source) != context.protocol.bootstrap_partial_file_sha256
    ):
        raise ValueError("Q1 successor v3 bootstrap source changed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if partial.exists():
        if (
            partial.stat().st_size != context.protocol.bootstrap_partial_bytes
            or file_sha256(partial) != context.protocol.bootstrap_partial_file_sha256
        ):
            raise ValueError("Q1 successor v3 unmarked bootstrap partial changed")
    else:
        transaction = partial.with_name(f"{partial.name}.bootstrap.part")
        if transaction.exists():
            transaction.unlink()
        shutil.copyfile(source, transaction)
        if (
            transaction.stat().st_size != context.protocol.bootstrap_partial_bytes
            or file_sha256(transaction) != context.protocol.bootstrap_partial_file_sha256
        ):
            raise ValueError("Q1 successor v3 bootstrap copy failed verification")
        transaction.replace(partial)
    _write_json_transactional(
        marker,
        {
            "schema_version": "aurex-q1-periodic-flow-successor-partial-bootstrap-v3",
            "transport_amendment_evidence_hash": (
                context.protocol.amendment_evidence_hash
            ),
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "target_key": context.protocol.bootstrap_target_key,
            "source_path": context.protocol.bootstrap_partial_path,
            "source_file_sha256": context.protocol.bootstrap_partial_file_sha256,
            "source_bytes": context.protocol.bootstrap_partial_bytes,
            "expected_total_bytes": context.protocol.bootstrap_expected_total_bytes,
            "copied_at": datetime.now(UTC).isoformat(),
        },
        overwrite=False,
    )
    return partial


def reconcile_target_markers_v3(
    *, root: Path, target, context: LoadedContext
) -> int:
    destination = target_archive_path(root, target)
    directory = destination.parent
    if not directory.exists():
        return 0
    request_paths = sorted(directory.glob(f"{destination.name}.get.*.request.json"))
    response_paths = sorted(directory.glob(f"{destination.name}.get.*.response.json"))
    response_by_attempt: dict[int, Path] = {}
    for path in response_paths:
        attempt = int(path.name.split(".get.", 1)[1].split(".", 1)[0])
        if attempt in response_by_attempt:
            raise ValueError("Duplicate Q1 successor v3 response attempt")
        response_by_attempt[attempt] = path
    attempts: list[int] = []
    partial = destination.with_name(f"{destination.name}.part")
    for path in request_paths:
        attempt = int(path.name.split(".get.", 1)[1].split(".", 1)[0])
        attempts.append(attempt)
        request = json.loads(path.read_text(encoding="utf-8"))
        _validate_request_marker_v3(
            request, target=target, context=context, attempt=attempt
        )
        response_path = response_by_attempt.get(attempt)
        if response_path is not None:
            response = json.loads(response_path.read_text(encoding="utf-8"))
            _validate_response_marker_v3(
                response, target=target, context=context, attempt=attempt
            )
            continue
        if attempt != len(request_paths):
            raise ValueError("Q1 successor v3 non-final request lacks response evidence")
        current_size = partial.stat().st_size if partial.exists() else 0
        range_start = request["range_start"]
        if current_size < range_start:
            raise ValueError("Q1 successor v3 interrupted partial shrank")
        interrupted = RuntimeError("Prior process ended before response marker write")
        known_total = _known_total_from_markers(root, target)
        if (
            known_total is None
            and f"{target.month}|{target.product}"
            == context.protocol.bootstrap_target_key
        ):
            known_total = context.protocol.bootstrap_expected_total_bytes
        recovered_complete = (
            known_total is not None
            and current_size == known_total
            and partial.exists()
            and file_sha256(partial) == target.published_archive_sha256
        )
        _write_response_marker_v3(
            root=root,
            target=target,
            context=context,
            attempt=attempt,
            status=None,
            final_url=target.archive_url,
            response_content_length=None,
            expected_total_bytes=known_total,
            content_range=None,
            bytes_received=current_size - range_start,
            partial_bytes_after_attempt=current_size,
            outcome="PASS" if recovered_complete else "INTERRUPTED_RESUMABLE",
            failure_class=(
                "PROCESS_INTERRUPTED_AFTER_COMPLETE_BODY"
                if recovered_complete
                else "PROCESS_INTERRUPTED"
            ),
            error=interrupted,
        )
    if attempts != list(range(1, len(attempts) + 1)):
        raise ValueError(f"Q1 successor v3 attempts are not contiguous: {target.key}")
    if len(response_by_attempt) > len(request_paths):
        raise ValueError("Q1 successor v3 response exists without request")
    if len(attempts) > context.protocol.maximum_get_attempts_per_target:
        raise ValueError("Q1 successor v3 target request budget exceeded")
    if destination.exists() and partial.exists():
        raise ValueError("Q1 successor v3 completed and partial archives coexist")
    if destination.exists():
        if not attempts:
            raise ValueError("Q1 successor v3 completed archive lacks request evidence")
        latest = json.loads(
            _attempt_path(root, target, attempts[-1], "response").read_text(
                encoding="utf-8"
            )
        )
        if latest["outcome"] != "PASS":
            raise ValueError("Q1 successor v3 completed archive lacks PASS marker")
    return len(attempts)


def _transient_failure_class(exc: BaseException) -> str:
    if isinstance(exc, IncompleteBodyError):
        return "INCOMPLETE_BODY"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, urllib.error.URLError):
        return "URL_ERROR"
    return "OS_ERROR"


def ensure_network_archive_v3(
    *, root: Path, target, context: LoadedContext
) -> tuple[Path, int]:
    if target.reuse_candidate_path is not None:
        raise ValueError("Q1 successor v3 network transport refused a reuse target")
    if f"{target.month}|{target.product}" == context.protocol.bootstrap_target_key:
        ensure_bootstrap_partial(root=root, target=target, context=context)
    attempts = reconcile_target_markers_v3(root=root, target=target, context=context)
    destination = target_archive_path(root, target)
    partial = destination.with_name(f"{destination.name}.part")
    if destination.exists():
        if file_sha256(destination) != target.published_archive_sha256:
            raise AcquisitionFailure("Existing Q1 successor v3 archive identity changed")
        return destination, attempts
    if attempts:
        latest = json.loads(
            _attempt_path(root, target, attempts, "response").read_text(encoding="utf-8")
        )
        if latest["outcome"] == "PASS":
            expected_total = latest.get("expected_total_bytes")
            if (
                not partial.is_file()
                or not isinstance(expected_total, int)
                or partial.stat().st_size != expected_total
                or file_sha256(partial) != target.published_archive_sha256
            ):
                raise AcquisitionFailure(
                    "Q1 successor v3 PASS marker lacks a recoverable archive"
                )
            partial.replace(destination)
            return destination, attempts
        if latest["outcome"] in {"HTTP_FAIL", "INTEGRITY_FAIL"}:
            raise AcquisitionFailure("Q1 successor v3 target has terminal failure evidence")
    if attempts >= context.protocol.maximum_get_attempts_per_target:
        raise AcquisitionFailure(f"Q1 successor v3 request budget exhausted for {target.key}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoRedirectHandler())
    last_error: BaseException | None = None
    for attempt in range(
        attempts + 1, context.protocol.maximum_get_attempts_per_target + 1
    ):
        state = marker_state_v3(root)
        if state.request_count >= context.protocol.maximum_payload_get_attempts:
            raise AcquisitionFailure("Global Q1 successor v3 request budget exhausted")
        offset = partial.stat().st_size if partial.exists() else 0
        expected_total = _known_total_from_markers(root, target)
        if expected_total is None and (
            f"{target.month}|{target.product}" == context.protocol.bootstrap_target_key
        ):
            expected_total = context.protocol.bootstrap_expected_total_bytes
        remaining_capacity = (
            context.protocol.maximum_archive_bytes - offset
            if expected_total is None
            else expected_total - offset
        )
        if remaining_capacity <= 0:
            raise AcquisitionFailure("Q1 successor v3 partial size is not resumable")
        free = shutil.disk_usage(root.parent.resolve()).free
        if free < (
            remaining_capacity + context.protocol.minimum_free_disk_bytes_after_acquisition
        ):
            raise AcquisitionFailure("Insufficient disk for Q1 successor v3 resume")
        if (
            state.payload_bytes_received + remaining_capacity
            > context.protocol.maximum_new_archive_bytes_total
        ):
            raise AcquisitionFailure("Q1 successor v3 payload budget cannot admit target")
        _write_request_marker_v3(
            root=root,
            target=target,
            context=context,
            attempt=attempt,
            range_start=offset,
        )
        status: int | None = None
        final_url = target.archive_url
        response_length: int | None = None
        content_range: str | None = None
        bytes_this_attempt = 0
        started = time.monotonic()
        marker_written = False
        try:
            headers = {
                "Accept": "application/zip",
                "Accept-Encoding": "identity",
                "User-Agent": "Aurex/1.0 (+q1-successor-resumable-acquisition)",
            }
            if offset:
                headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(
                target.archive_url, headers=headers, method="GET"
            )
            with opener.open(
                request, timeout=context.protocol.connect_timeout_seconds
            ) as response:
                status = response.getcode()
                final_url = response.geturl()
                if final_url != target.archive_url:
                    raise AcquisitionFailure("Q1 successor v3 final URL changed")
                content_encoding = response.headers.get(
                    "Content-Encoding", "identity"
                ).lower()
                if content_encoding not in {"", "identity"}:
                    raise AcquisitionFailure("Q1 successor v3 content encoding changed")
                length_text = response.headers.get("Content-Length")
                if length_text is not None:
                    response_length = int(length_text)
                    if response_length <= 0:
                        raise AcquisitionFailure(
                            "Q1 successor v3 response Content-Length is invalid"
                        )
                content_range = response.headers.get("Content-Range")
                if offset:
                    if status != 206 or content_range is None:
                        raise AcquisitionFailure(
                            "Q1 successor v3 resume was not honored with HTTP 206"
                        )
                    end, observed_total = _parse_content_range(
                        content_range, start=offset
                    )
                    if (
                        response_length is not None
                        and response_length != end - offset + 1
                    ):
                        raise AcquisitionFailure(
                            "Q1 successor v3 ranged Content-Length changed"
                        )
                else:
                    if status != 200 or response_length is None:
                        raise AcquisitionFailure(
                            "Q1 successor v3 initial response identity changed"
                        )
                    observed_total = response_length
                if (
                    observed_total <= offset
                    or observed_total > context.protocol.maximum_archive_bytes
                    or (
                        expected_total is not None and observed_total != expected_total
                    )
                ):
                    raise AcquisitionFailure("Q1 successor v3 total archive size changed")
                expected_total = observed_total
                _set_idle_socket_timeout(
                    response, context.protocol.idle_read_timeout_seconds
                )
                with partial.open("ab" if offset else "wb") as output:
                    while True:
                        if (
                            time.monotonic() - started
                            > context.protocol.total_attempt_deadline_seconds
                        ):
                            raise TimeoutError(
                                "Q1 successor v3 total attempt deadline exceeded"
                            )
                        chunk = response.read1(context.protocol.stream_chunk_bytes)
                        if not chunk:
                            break
                        bytes_this_attempt += len(chunk)
                        if offset + bytes_this_attempt > expected_total:
                            raise AcquisitionFailure(
                                "Q1 successor v3 response exceeded expected total"
                            )
                        if (
                            state.payload_bytes_received + bytes_this_attempt
                            > context.protocol.maximum_new_archive_bytes_total
                        ):
                            raise AcquisitionFailure(
                                "Q1 successor v3 cumulative byte budget exceeded"
                            )
                        output.write(chunk)
                current_size = partial.stat().st_size
                if current_size != expected_total:
                    raise IncompleteBodyError(
                        f"Q1 successor v3 response ended at {current_size} of "
                        f"{expected_total} bytes"
                    )
                if file_sha256(partial) != target.published_archive_sha256:
                    raise AcquisitionFailure(
                        "Q1 successor v3 completed archive checksum mismatch"
                    )
            _write_response_marker_v3(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                response_content_length=response_length,
                expected_total_bytes=expected_total,
                content_range=content_range,
                bytes_received=bytes_this_attempt,
                partial_bytes_after_attempt=partial.stat().st_size,
                outcome="PASS",
                failure_class="NONE",
                error=None,
            )
            marker_written = True
            partial.replace(destination)
            return destination, attempt
        except urllib.error.HTTPError as exc:
            last_error = exc
            transient = exc.code in TRANSIENT_HTTP_STATUSES
            _write_response_marker_v3(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=exc.code,
                final_url=exc.geturl() or target.archive_url,
                response_content_length=None,
                expected_total_bytes=expected_total,
                content_range=None,
                bytes_received=bytes_this_attempt,
                partial_bytes_after_attempt=(partial.stat().st_size if partial.exists() else 0),
                outcome="TRANSIENT" if transient else "HTTP_FAIL",
                failure_class="HTTP_TRANSIENT" if transient else "HTTP_TERMINAL",
                error=exc,
            )
            marker_written = True
            if not transient:
                raise AcquisitionFailure(
                    f"Q1 successor v3 HTTP {exc.code} for {target.key}"
                ) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = exc
            _write_response_marker_v3(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                response_content_length=response_length,
                expected_total_bytes=expected_total,
                content_range=content_range,
                bytes_received=bytes_this_attempt,
                partial_bytes_after_attempt=(partial.stat().st_size if partial.exists() else 0),
                outcome="TRANSIENT",
                failure_class=_transient_failure_class(exc),
                error=exc,
            )
            marker_written = True
        except AcquisitionFailure as exc:
            last_error = exc
            if not marker_written:
                _write_response_marker_v3(
                    root=root,
                    target=target,
                    context=context,
                    attempt=attempt,
                    status=status,
                    final_url=final_url,
                    response_content_length=response_length,
                    expected_total_bytes=expected_total,
                    content_range=content_range,
                    bytes_received=bytes_this_attempt,
                    partial_bytes_after_attempt=(
                        partial.stat().st_size if partial.exists() else 0
                    ),
                    outcome="INTEGRITY_FAIL",
                    failure_class="INTEGRITY_OR_IDENTITY_FAILURE",
                    error=exc,
                )
            raise
        if attempt < context.protocol.maximum_get_attempts_per_target:
            time.sleep(context.protocol.retry_delays_seconds[attempt - 1])
    error_type, error_message = _safe_error(last_error)
    raise AcquisitionFailure(
        f"Q1 successor v3 transport unresolved for {target.key} after "
        f"{context.protocol.maximum_get_attempts_per_target} attempts; "
        f"last_error={error_type}: {error_message}"
    ) from last_error


def load_context(args: argparse.Namespace) -> LoadedContext:
    protocol = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowSuccessorAcquisitionProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    amendment = PeriodicFlowSuccessorTransportAmendmentV3.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV3.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV3.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV3.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    runner_hash = current_runner_source_hash_v3()
    if (
        not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or not audit_hash(contract, "contract_evidence_hash")
        or not audit_hash(contract_audit, "audit_evidence_hash")
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or amendment.parent_protocol_evidence_hash != protocol.protocol_evidence_hash
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or amendment_audit.amendment_evidence_hash != amendment.amendment_evidence_hash
        or contract.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_evidence_hash != amendment.amendment_evidence_hash
        or contract.amendment_audit_file_sha256 != file_sha256(args.amendment_audit)
        or contract.amendment_audit_evidence_hash != amendment_audit.audit_evidence_hash
        or contract.runner_source_hash != runner_hash
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_source_hash != runner_hash
    ):
        raise ValueError("Q1 successor v3 acquisition authority or source changed")
    adapter = ProtocolTransportAdapterV3(protocol, amendment)
    return LoadedContext(  # type: ignore[arg-type]
        protocol=adapter,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
    )


def _seed_checkpoint(
    args: argparse.Namespace, context: LoadedContext
) -> PeriodicFlowSuccessorCheckpointV3:
    seed = PeriodicFlowSuccessorCheckpoint.model_validate_json(
        args.v2_checkpoint.read_text(encoding="utf-8")
    )
    if (
        file_sha256(args.v2_checkpoint) != context.contract.seed_v2_checkpoint_file_sha256
        or seed.checkpoint_evidence_hash
        != context.contract.seed_v2_checkpoint_evidence_hash
        or len(seed.archive_evidence) != context.contract.seed_archive_count
        or len(seed.paired_month_evidence) != context.contract.seed_paired_month_count
        or seed.excluded_month_evidence
    ):
        raise ValueError("Q1 successor v3 seed checkpoint changed")
    state = marker_state_v3(args.acquisition_root)
    return build_checkpoint_v3(
        updated_at=datetime.now(UTC),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        archive_evidence=seed.archive_evidence,
        paired_month_evidence=seed.paired_month_evidence,
        excluded_month_evidence=seed.excluded_month_evidence,
        request_marker_count=state.request_count,
        response_marker_count=state.response_count,
        request_marker_manifest_hash=state.manifest_hash,
        cumulative_payload_bytes_received=state.payload_bytes_received,
        total_new_archive_bytes=sum(
            item.new_archive_bytes for item in seed.archive_evidence
        ),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes_total for item in seed.archive_evidence
        ),
    )


def load_checkpoint_v3(
    *, args: argparse.Namespace, context: LoadedContext
) -> PeriodicFlowSuccessorCheckpointV3:
    if not args.checkpoint.exists():
        return _seed_checkpoint(args, context)
    checkpoint = PeriodicFlowSuccessorCheckpointV3.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    state = marker_state_v3(args.acquisition_root)
    if (
        checkpoint.protocol_evidence_hash != context.protocol.protocol_evidence_hash
        or checkpoint.execution_contract_evidence_hash
        != context.contract.contract_evidence_hash
        or checkpoint.runner_source_hash != context.contract.runner_source_hash
        or checkpoint.request_marker_count != state.request_count
        or checkpoint.response_marker_count != state.response_count
        or checkpoint.request_marker_manifest_hash != state.manifest_hash
        or checkpoint.cumulative_payload_bytes_received != state.payload_bytes_received
    ):
        raise ValueError("Q1 successor v3 checkpoint lineage or marker state changed")
    return checkpoint


def write_checkpoint_v3(
    *, args: argparse.Namespace, context: LoadedContext, archives, pairs, exclusions
) -> PeriodicFlowSuccessorCheckpointV3:
    state = marker_state_v3(args.acquisition_root)
    if state.request_count != state.response_count:
        raise ValueError("Q1 successor v3 checkpoint refused unmatched markers")
    checkpoint = build_checkpoint_v3(
        updated_at=datetime.now(UTC),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        archive_evidence=tuple(archives),
        paired_month_evidence=tuple(pairs),
        excluded_month_evidence=tuple(exclusions),
        request_marker_count=state.request_count,
        response_marker_count=state.response_count,
        request_marker_manifest_hash=state.manifest_hash,
        cumulative_payload_bytes_received=state.payload_bytes_received,
        total_new_archive_bytes=sum(item.new_archive_bytes for item in archives),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes_total for item in archives
        ),
    )
    _write_json_transactional(
        args.checkpoint, checkpoint.model_dump(mode="json"), overwrite=True
    )
    return checkpoint


def verify_checkpoint_archives_v3(
    *, checkpoint: PeriodicFlowSuccessorCheckpointV3, evidence_root: Path
) -> None:
    for evidence in checkpoint.archive_evidence:
        path = (evidence_root / evidence.local_path).resolve()
        if (
            not path.is_relative_to(evidence_root.resolve())
            or not path.is_file()
            or path.stat().st_size != evidence.archive_bytes
            or file_sha256(path) != evidence.archive_sha256
        ):
            raise ValueError(f"Q1 successor v3 checkpoint archive changed: {evidence.key}")


def preflight(args: argparse.Namespace, context: LoadedContext) -> dict:
    if args.result.exists():
        raise ValueError("A terminal Q1 successor v3 result already exists")
    seed = PeriodicFlowSuccessorCheckpoint.model_validate_json(
        args.v2_checkpoint.read_text(encoding="utf-8")
    )
    if (
        file_sha256(args.v2_checkpoint) != context.contract.seed_v2_checkpoint_file_sha256
        or seed.checkpoint_evidence_hash
        != context.contract.seed_v2_checkpoint_evidence_hash
    ):
        raise ValueError("Q1 successor v3 preflight seed changed")
    verify_checkpoint_archives_v3(
        checkpoint=PeriodicFlowSuccessorCheckpointV3.model_validate(
            build_checkpoint_v3(
                updated_at=datetime.now(UTC),
                protocol_evidence_hash=context.protocol.protocol_evidence_hash,
                execution_contract_evidence_hash=context.contract.contract_evidence_hash,
                runner_source_hash=context.contract.runner_source_hash,
                archive_evidence=seed.archive_evidence,
                paired_month_evidence=seed.paired_month_evidence,
                excluded_month_evidence=seed.excluded_month_evidence,
                request_marker_count=0,
                response_marker_count=0,
                request_marker_manifest_hash=universe_evidence_hash(
                    {"marker_files": {}}
                ),
                cumulative_payload_bytes_received=0,
                total_new_archive_bytes=0,
                total_member_uncompressed_bytes=sum(
                    item.zip_uncompressed_bytes_total for item in seed.archive_evidence
                ),
            )
        ),
        evidence_root=args.evidence_root,
    )
    reused = [item for item in context.protocol.targets if item.reuse_candidate_path]
    reused_bytes = 0
    for index, target in enumerate(reused, start=1):
        path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
        reused_bytes += path.stat().st_size
        with zipfile.ZipFile(path) as archive:
            select_zip_member(archive, target=target, protocol=context.protocol)
        print(
            f"PREFLIGHT_REUSE {index}/26 {target.month} {target.product} PASS",
            flush=True,
        )
    bootstrap = (PROJECT_ROOT / context.protocol.bootstrap_partial_path).resolve()
    if (
        not bootstrap.is_file()
        or bootstrap.stat().st_size != context.protocol.bootstrap_partial_bytes
        or file_sha256(bootstrap) != context.protocol.bootstrap_partial_file_sha256
    ):
        raise ValueError("Q1 successor v3 preflight bootstrap partial changed")
    state = marker_state_v3(args.acquisition_root)
    free = shutil.disk_usage(args.acquisition_root.parent.resolve()).free
    required = context.contract.required_free_disk_bytes_before_acquisition
    result = {
        "status": "PASS" if free >= required else "BLOCKED_INSUFFICIENT_FREE_DISK",
        "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
        "transport_amendment_evidence_hash": context.protocol.amendment_evidence_hash,
        "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
        "runner_source_hash": context.contract.runner_source_hash,
        "seed_archives_verified": len(seed.archive_evidence),
        "seed_paired_months_verified": len(seed.paired_month_evidence),
        "reuse_candidates_verified": len(reused),
        "reuse_candidate_bytes": reused_bytes,
        "bootstrap_partial_bytes_verified": bootstrap.stat().st_size,
        "free_disk_bytes": free,
        "required_free_disk_bytes_before_acquisition": required,
        "additional_free_disk_bytes_required": max(0, required - free),
        "network_requests_made": state.request_count,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise AcquisitionFailure("Q1 successor v3 preflight disk requirement failed")
    return result


def _qualification_counts(pairs: list) -> tuple[dict[str, int], int]:
    by_year = {str(year): 0 for year in range(2020, 2024)}
    quarters: set[tuple[str, int]] = set()
    for pair in pairs:
        year, month = pair.month.split("-")
        by_year[year] += 1
        quarters.add((year, (int(month) - 1) // 3 + 1))
    return by_year, len(quarters)


def write_result_v3(
    *,
    args: argparse.Namespace,
    context: LoadedContext,
    checkpoint: PeriodicFlowSuccessorCheckpointV3,
    hard_failure_target_key: str | None,
    hard_failure_reason: str | None,
) -> PeriodicFlowSuccessorAcquisitionResultV3:
    by_year, quarter_count = _qualification_counts(list(checkpoint.paired_month_evidence))
    result = build_acquisition_result_v3(
        generated_at=datetime.now(UTC),
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        inspected_archive_count=len(checkpoint.archive_evidence),
        qualified_paired_month_count=len(checkpoint.paired_month_evidence),
        excluded_month_count=len(checkpoint.excluded_month_evidence),
        completed_month_count=(
            len(checkpoint.paired_month_evidence)
            + len(checkpoint.excluded_month_evidence)
        ),
        qualified_months_by_year=by_year,
        qualified_quarter_count=quarter_count,
        request_marker_count=checkpoint.request_marker_count,
        cumulative_payload_bytes_received=checkpoint.cumulative_payload_bytes_received,
        total_new_archive_bytes=checkpoint.total_new_archive_bytes,
        hard_failure_target_key=hard_failure_target_key,
        hard_failure_reason=hard_failure_reason,
        limitations=result_limitations(),
    )
    _write_json_transactional(args.result, result.model_dump(mode="json"), overwrite=False)
    return result


def inspect_target_v3(*, args: argparse.Namespace, context: LoadedContext, target):
    try:
        if target.reuse_candidate_path is not None:
            path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
            source_mode = "REUSED_LOCAL"
            attempts = 0
        else:
            path, attempts = ensure_network_archive_v3(
                root=args.acquisition_root, target=target, context=context
            )
            source_mode = "NETWORK_ACQUIRED"
        return inspect_archive(
            target=target,
            archive_path=path,
            evidence_root=args.evidence_root,
            protocol=context.protocol,
            source_mode=source_mode,
            get_attempt_count=attempts,
        )
    except AcquisitionFailure:
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise AcquisitionFailure(
            f"Q1 successor v3 archive integrity failed for {target.key}: {exc}"
        ) from exc


def rebuild_inspection_v3(
    *, args: argparse.Namespace, context: LoadedContext, evidence
):
    target = next(item for item in context.protocol.targets if item.key == evidence.key)
    path = resolved_archive_path(
        evidence_root=args.evidence_root,
        acquisition_root=args.acquisition_root,
        target=target,
    )
    rebuilt = inspect_archive(
        target=target,
        archive_path=path,
        evidence_root=args.evidence_root,
        protocol=context.protocol,
        source_mode=evidence.source_mode,
        get_attempt_count=evidence.payload_get_attempt_count,
    )
    if rebuilt.evidence != evidence:
        raise ValueError(f"Q1 successor v3 archive evidence changed: {evidence.key}")
    return rebuilt


def run_acquisition_v3(
    args: argparse.Namespace, context: LoadedContext
) -> PeriodicFlowSuccessorAcquisitionResultV3:
    preflight(args, context)
    bootstrap_target = next(
        item
        for item in context.protocol.targets
        if f"{item.month}|{item.product}" == context.protocol.bootstrap_target_key
    )
    ensure_bootstrap_partial(
        root=args.acquisition_root, target=bootstrap_target, context=context
    )
    checkpoint = load_checkpoint_v3(args=args, context=context)
    if not args.checkpoint.exists():
        checkpoint = write_checkpoint_v3(
            args=args,
            context=context,
            archives=list(checkpoint.archive_evidence),
            pairs=list(checkpoint.paired_month_evidence),
            exclusions=list(checkpoint.excluded_month_evidence),
        )
    verify_checkpoint_archives_v3(
        checkpoint=checkpoint, evidence_root=args.evidence_root
    )
    archives = list(checkpoint.archive_evidence)
    pairs = list(checkpoint.paired_month_evidence)
    exclusions = list(checkpoint.excluded_month_evidence)
    archive_by_key = {item.key: item for item in archives}
    completed_months = {item.month for item in pairs} | {item.month for item in exclusions}
    target_by_key = {item.key: item for item in context.protocol.targets}
    months = sorted({item.month for item in context.protocol.targets})
    active_key = "PRE_ACQUISITION"
    try:
        for month in months:
            if month in completed_months:
                continue
            inspections = {}
            for target in (
                target_by_key[(month, "SPOT")],
                target_by_key[(month, "USD_M_PERPETUAL")],
            ):
                active_key = f"{target.month}|{target.product}"
                if target.key in archive_by_key:
                    inspection = rebuild_inspection_v3(
                        args=args,
                        context=context,
                        evidence=archive_by_key[target.key],
                    )
                else:
                    inspection = inspect_target_v3(
                        args=args, context=context, target=target
                    )
                    archives.append(inspection.evidence)
                    archive_by_key[target.key] = inspection.evidence
                    checkpoint = write_checkpoint_v3(
                        args=args,
                        context=context,
                        archives=archives,
                        pairs=pairs,
                        exclusions=exclusions,
                    )
                    print(
                        f"ARCHIVE {len(archives)}/74 {month} {target.product} "
                        f"{'PASS' if inspection.evidence.archive_pass else 'EXCLUDE'} "
                        f"rows={inspection.evidence.row_count}",
                        flush=True,
                    )
                inspections[target.product] = inspection
                if not inspection.evidence.archive_pass:
                    exclusions.append(
                        PeriodicFlowExcludedMonthEvidence(
                            month=month,
                            failed_stage=(
                                "SPOT_ARCHIVE"
                                if target.product == "SPOT"
                                else "USDM_ARCHIVE"
                            ),
                            failed_product=target.product,
                            reason_codes=inspection.evidence.reason_codes,
                            archive_sha256=inspection.evidence.archive_sha256,
                            source_mode=inspection.evidence.source_mode,
                        )
                    )
                    completed_months.add(month)
                    checkpoint = write_checkpoint_v3(
                        args=args,
                        context=context,
                        archives=archives,
                        pairs=pairs,
                        exclusions=exclusions,
                    )
                    print(
                        f"MONTH {month} EXCLUDED stage={exclusions[-1].failed_stage} "
                        f"reasons={exclusions[-1].reason_codes}",
                        flush=True,
                    )
                    break
            if month in completed_months:
                continue
            pair = pair_month(
                month, inspections["SPOT"], inspections["USD_M_PERPETUAL"]
            )
            if pair.paired_clock_pass:
                pairs.append(pair)
                print(
                    f"PAIRED {len(pairs)}/37 {month} PASS "
                    f"coverage={pair.paired_minute_coverage_fraction}",
                    flush=True,
                )
            else:
                exclusions.append(
                    PeriodicFlowExcludedMonthEvidence(
                        month=month,
                        failed_stage="PAIRED_CLOCK",
                        failed_product="PAIRED",
                        reason_codes=pair.reason_codes,
                    )
                )
                print(
                    f"MONTH {month} EXCLUDED stage=PAIRED_CLOCK "
                    f"reasons={pair.reason_codes}",
                    flush=True,
                )
            completed_months.add(month)
            checkpoint = write_checkpoint_v3(
                args=args,
                context=context,
                archives=archives,
                pairs=pairs,
                exclusions=exclusions,
            )
        return write_result_v3(
            args=args,
            context=context,
            checkpoint=checkpoint,
            hard_failure_target_key=None,
            hard_failure_reason=None,
        )
    except AcquisitionFailure as exc:
        checkpoint = write_checkpoint_v3(
            args=args,
            context=context,
            archives=archives,
            pairs=pairs,
            exclusions=exclusions,
        )
        return write_result_v3(
            args=args,
            context=context,
            checkpoint=checkpoint,
            hard_failure_target_key=active_key,
            hard_failure_reason=str(exc),
        )


def check_state_v3(args: argparse.Namespace, context: LoadedContext) -> dict:
    checkpoint = load_checkpoint_v3(args=args, context=context)
    verify_checkpoint_archives_v3(
        checkpoint=checkpoint, evidence_root=args.evidence_root
    )
    result = None
    if args.result.exists():
        result = PeriodicFlowSuccessorAcquisitionResultV3.model_validate_json(
            args.result.read_text(encoding="utf-8")
        )
        if (
            result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
            or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
            or result.runner_source_hash != context.contract.runner_source_hash
        ):
            raise ValueError("Q1 successor v3 terminal result changed")
    summary = {
        "status": "PASS",
        "inspected_archives": len(checkpoint.archive_evidence),
        "qualified_paired_months": len(checkpoint.paired_month_evidence),
        "excluded_months": len(checkpoint.excluded_month_evidence),
        "request_markers": checkpoint.request_marker_count,
        "payload_bytes_received": checkpoint.cumulative_payload_bytes_received,
        "terminal_result": None if result is None else result.decision,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight, run, or check the Q1 successor v3 acquisition."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT
    )
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--v2-checkpoint", type=Path, default=DEFAULT_V2_CHECKPOINT)
    parser.add_argument("--v2-result", type=Path, default=DEFAULT_V2_RESULT)
    parser.add_argument(
        "--v2-terminal-audit", type=Path, default=DEFAULT_V2_TERMINAL_AUDIT
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
            check_state_v3(args, context)
        else:
            result = run_acquisition_v3(args, context)
            print(
                f"RESULT {result.decision} archives={result.inspected_archive_count} "
                f"paired={result.qualified_paired_month_count} "
                f"excluded={result.excluded_month_count} "
                f"requests={result.request_marker_count}",
                flush=True,
            )
            if result.decision != (
                "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
            ):
                return 1
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
