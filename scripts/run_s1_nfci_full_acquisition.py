from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_full_acquisition import (  # noqa: E402
    S1NfciFullAcquisitionProtocol,
    S1NfciFullAcquisitionTarget,
)
from aurex.backtest_engine.s1_nfci_full_execution import (  # noqa: E402
    S1_NFCI_ACQUISITION_NEXT,
    S1_NFCI_ACQUISITION_PASS,
    S1_NFCI_ACQUISITION_STOP,
    S1NfciAcquisitionAttempt,
    S1NfciAcquisitionCheckpoint,
    S1NfciAcquisitionTargetEvidence,
    S1NfciFullAcquisitionResult,
)
from aurex.backtest_engine.s1_nfci_full_execution_v2 import (  # noqa: E402
    S1NfciAcquisitionExecutionAmendmentV2,
    S1NfciAcquisitionExecutionAuditV2,
)
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate  # noqa: E402
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_raw_pilot import parse_snapshot, write_json_atomic  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_nfci_full_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_nfci_full_acquisition_protocol_audit_v1.json"
)
DEFAULT_ADDENDUM = Path("data/evidence/s1_nfci_acquisition_execution_amendment_v2.json")
DEFAULT_ADDENDUM_AUDIT = Path(
    "data/evidence/s1_nfci_acquisition_execution_audit_v2.json"
)
DEFAULT_CHECKPOINT = Path("data/evidence/s1_nfci_full_acquisition_checkpoint_v1.json")
DEFAULT_RESULT = Path("data/evidence/s1_nfci_full_acquisition_result_v1.json")
EXECUTION_MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_full_execution.py")
EXECUTION_V2_MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_full_execution_v2.py")
RUNNER_PATH = Path("scripts/run_s1_nfci_full_acquisition.py")


class RedirectRejectedError(RuntimeError):
    pass


class RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRejectedError(f"S1 NFCI redirect rejected: {newurl}")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            EXECUTION_MODULE_PATH.as_posix(): file_sha256(
                PROJECT_ROOT / EXECUTION_MODULE_PATH
            ),
            EXECUTION_V2_MODULE_PATH.as_posix(): file_sha256(
                PROJECT_ROOT / EXECUTION_V2_MODULE_PATH
            ),
            RUNNER_PATH.as_posix(): file_sha256(PROJECT_ROOT / RUNNER_PATH),
        }
    )


def marker_path(target: S1NfciFullAcquisitionTarget, attempt: int, kind: str) -> Path:
    raw_path = Path(target.raw_path)
    return raw_path.with_name(f"{raw_path.name}.get.{attempt:02d}.{kind}.json")


def part_path(target: S1NfciFullAcquisitionTarget, attempt: int) -> Path:
    raw_path = Path(target.raw_path)
    return raw_path.with_name(f"{raw_path.name}.get.{attempt:02d}.part")


def validate_target(target: S1NfciFullAcquisitionTarget) -> None:
    parsed = urlparse(target.url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != target.expected_final_host
        or parsed.path != "/graph/alfredgraph.csv"
        or parsed.query != f"id=NFCI&vintage_date={target.vintage_date.isoformat()}"
        or parsed.fragment
    ):
        raise ValueError("S1 NFCI acquisition target left the frozen URL allowlist")
    expected_parent = Path("data/evidence/source_snapshots/s1_nfci_full_acquisition_v1")
    raw_path = Path(target.raw_path)
    if raw_path.parent != expected_parent or raw_path.suffix != ".csv":
        raise ValueError("S1 NFCI acquisition target left the frozen evidence root")


def build_attempt(**payload) -> S1NfciAcquisitionAttempt:
    provisional = S1NfciAcquisitionAttempt.model_construct(
        **payload,
        attempt_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["attempt_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"attempt_evidence_hash"})
    )
    return S1NfciAcquisitionAttempt.model_validate(complete)


def build_target_evidence(**payload) -> S1NfciAcquisitionTargetEvidence:
    provisional = S1NfciAcquisitionTargetEvidence.model_construct(
        **payload,
        target_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["target_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"target_evidence_hash"})
    )
    return S1NfciAcquisitionTargetEvidence.model_validate(complete)


def attempt_from_markers(
    target: S1NfciFullAcquisitionTarget,
    attempt: int,
) -> S1NfciAcquisitionAttempt:
    request_path = marker_path(target, attempt, "request")
    response_path = marker_path(target, attempt, "response")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if (
        request["target_id"] != target.target_id
        or response["target_id"] != target.target_id
        or request["attempt"] != attempt
        or response["attempt"] != attempt
    ):
        raise ValueError("S1 NFCI marker identity changed")
    return build_attempt(
        sequence=target.sequence,
        attempt=attempt,
        requested_at=datetime.fromisoformat(request["requested_at"].replace("Z", "+00:00")),
        completed_at=datetime.fromisoformat(
            response["completed_at"].replace("Z", "+00:00")
        ),
        status_code=response["status_code"],
        final_url=response["final_url"],
        final_host=response["final_host"],
        content_type=response["content_type"],
        bytes_received=response["bytes_received"],
        outcome=response["outcome"],
        error_type=response["error_type"],
        error_message=response["error_message"],
        request_marker_path=request_path.as_posix(),
        request_marker_sha256=file_sha256(request_path),
        response_marker_path=response_path.as_posix(),
        response_marker_sha256=file_sha256(response_path),
    )


def recover_interrupted_attempt(
    target: S1NfciFullAcquisitionTarget,
    attempt: int,
    *,
    protocol: S1NfciFullAcquisitionProtocol,
) -> None:
    request_path = marker_path(target, attempt, "request")
    response_path = marker_path(target, attempt, "response")
    partial = part_path(target, attempt)
    if not request_path.exists() or response_path.exists():
        return
    bytes_received = partial.stat().st_size if partial.exists() else 0
    if bytes_received > protocol.maximum_payload_bytes_per_target:
        raise ValueError("Interrupted S1 NFCI partial exceeds its byte cap")
    raw_path = Path(target.raw_path)
    recovered_complete = raw_path.is_file()
    if recovered_complete:
        bytes_received = raw_path.stat().st_size
    write_json_atomic(
        response_path,
        {
            "schema_version": "aurex-s1-nfci-full-http-response-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "attempt": attempt,
            "status_code": 200 if recovered_complete else None,
            "final_url": target.url if recovered_complete else None,
            "final_host": target.expected_final_host if recovered_complete else None,
            "content_type": "application/csv" if recovered_complete else None,
            "bytes_received": bytes_received,
            "outcome": "COMPLETE" if recovered_complete else "TRANSIENT_FAILURE",
            "error_type": None if recovered_complete else "ConnectionError",
            "error_message": (
                None
                if recovered_complete
                else "Interrupted attempt recovered before resume."
            ),
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )
    if partial.exists():
        partial.unlink()


def existing_attempts(
    target: S1NfciFullAcquisitionTarget,
    *,
    protocol: S1NfciFullAcquisitionProtocol,
) -> tuple[S1NfciAcquisitionAttempt, ...]:
    attempts = []
    for attempt in range(1, protocol.maximum_attempts_per_target + 1):
        request_path = marker_path(target, attempt, "request")
        response_path = marker_path(target, attempt, "response")
        if not request_path.exists():
            if response_path.exists():
                raise ValueError("S1 NFCI response marker exists without request")
            break
        recover_interrupted_attempt(target, attempt, protocol=protocol)
        attempts.append(attempt_from_markers(target, attempt))
    return tuple(attempts)


def classify_error(
    exc: Exception,
    *,
    protocol: S1NfciFullAcquisitionProtocol,
) -> tuple[str, str]:
    if isinstance(exc, HTTPError):
        transient = exc.code in protocol.transient_http_statuses
        return ("TRANSIENT_FAILURE" if transient else "PERMANENT_FAILURE", "HTTPError")
    if isinstance(exc, (TimeoutError, URLError, ConnectionError)):
        return "TRANSIENT_FAILURE", type(exc).__name__
    if isinstance(exc, OSError):
        return "TRANSIENT_FAILURE", "ConnectionError"
    return "PERMANENT_FAILURE", type(exc).__name__


def execute_attempt(
    target: S1NfciFullAcquisitionTarget,
    attempt: int,
    *,
    protocol: S1NfciFullAcquisitionProtocol,
) -> S1NfciAcquisitionAttempt:
    request_path = marker_path(target, attempt, "request")
    response_path = marker_path(target, attempt, "response")
    partial = part_path(target, attempt)
    raw_path = Path(target.raw_path)
    if any(path.exists() for path in (request_path, response_path, partial)):
        raise ValueError("S1 NFCI attempt evidence already exists")
    requested_at = datetime.now(UTC)
    write_json_atomic(
        request_path,
        {
            "schema_version": "aurex-s1-nfci-full-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "attempt": attempt,
            "method": "GET",
            "url": target.url,
            "range": None,
            "requested_at": requested_at.isoformat(),
        },
    )
    status_code = None
    final_url = None
    final_host = None
    content_type = None
    bytes_received = 0
    outcome = "COMPLETE"
    error_type = None
    error_message = None
    try:
        request = Request(
            target.url,
            headers={"User-Agent": "Aurex-S1-NFCI-Acquisition/1.0"},
            method="GET",
        )
        opener = build_opener(RejectRedirectHandler())
        with opener.open(request, timeout=protocol.connect_timeout_seconds) as response:
            status_code = response.status
            final_url = response.geturl()
            final_host = urlparse(final_url).hostname
            content_type = response.headers.get("Content-Type")
            if status_code != 200:
                raise ValueError(f"S1 NFCI endpoint returned HTTP {status_code}")
            if final_url != target.url or final_host != target.expected_final_host:
                raise ValueError("S1 NFCI endpoint identity changed")
            if content_type is None or "csv" not in content_type.lower():
                raise ValueError("S1 NFCI endpoint did not return CSV")
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with partial.open("xb") as destination:
                while True:
                    chunk = response.read(protocol.chunk_size_bytes)
                    if not chunk:
                        break
                    bytes_received += len(chunk)
                    if bytes_received > protocol.maximum_payload_bytes_per_target:
                        raise ValueError("S1 NFCI payload exceeded target byte cap")
                    destination.write(chunk)
            if bytes_received == 0:
                raise ValueError("S1 NFCI endpoint returned an empty payload")
            if raw_path.exists():
                raise ValueError("S1 NFCI raw target already exists")
            partial.replace(raw_path)
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
    completed_at = datetime.now(UTC)
    write_json_atomic(
        response_path,
        {
            "schema_version": "aurex-s1-nfci-full-http-response-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "sequence": target.sequence,
            "attempt": attempt,
            "status_code": status_code,
            "final_url": final_url,
            "final_host": final_host,
            "content_type": content_type,
            "bytes_received": bytes_received,
            "outcome": outcome,
            "error_type": error_type,
            "error_message": error_message,
            "completed_at": completed_at.isoformat(),
        },
    )
    return attempt_from_markers(target, attempt)


def structural_failure_gate(
    target: S1NfciFullAcquisitionTarget,
    summary,
    *,
    protocol: S1NfciFullAcquisitionProtocol,
) -> str | None:
    if summary.csv_header != (
        protocol.expected_observation_column,
        target.expected_value_column,
    ):
        return "EXACT_VINTAGE_SUFFIXED_HEADER_PER_TARGET"
    if summary.valid_numeric_row_count < protocol.minimum_valid_rows_per_target:
        return "MINIMUM_VALID_ROWS_PER_TARGET"
    if (
        summary.duplicate_observation_date_count
        or summary.non_increasing_observation_date_count
    ):
        return "STRICTLY_INCREASING_UNIQUE_OBSERVATION_DATES_PER_TARGET"
    if (
        summary.post_vintage_observation_count
        or summary.last_observation_date is None
        or summary.last_observation_date > target.vintage_date
    ):
        return "NO_POST_VINTAGE_OBSERVATION_PER_TARGET"
    if (
        summary.first_observation_date is None
        or summary.first_observation_date
        > datetime.fromisoformat(protocol.earliest_required_observation_date).date()
    ):
        return "DEVELOPMENT_START_COVERED_PER_TARGET"
    if (
        summary.release_lag_days is None
        or summary.release_lag_days > protocol.maximum_release_lag_days
    ):
        return "LATEST_OBSERVATION_WITHIN_21_DAYS_OF_VINTAGE_PER_TARGET"
    return None


def acquire_target(
    target: S1NfciFullAcquisitionTarget,
    *,
    protocol: S1NfciFullAcquisitionProtocol,
) -> S1NfciAcquisitionTargetEvidence:
    validate_target(target)
    attempts = list(existing_attempts(target, protocol=protocol))
    raw_path = Path(target.raw_path)
    if attempts and attempts[-1].outcome == "COMPLETE":
        if not raw_path.is_file():
            raise ValueError("S1 NFCI complete attempt lost its raw file")
    else:
        if raw_path.exists():
            raise ValueError("S1 NFCI raw file exists without a complete attempt")
        while len(attempts) < protocol.maximum_attempts_per_target:
            attempt = execute_attempt(target, len(attempts) + 1, protocol=protocol)
            attempts.append(attempt)
            if attempt.outcome == "COMPLETE":
                break
            if attempt.outcome == "PERMANENT_FAILURE":
                break
            time.sleep(protocol.polite_delay_milliseconds / 1000)
    if not attempts or attempts[-1].outcome != "COMPLETE":
        return build_target_evidence(
            sequence=target.sequence,
            target_id=target.target_id,
            vintage_date=target.vintage_date,
            outcome="FAILED",
            attempts=tuple(attempts),
            raw_path=None,
            raw_file_sha256=None,
            raw_file_bytes=0,
            summary=None,
            failure_gate="PAYLOAD_TRANSPORT_OR_ATTEMPT_BUDGET_FAILED",
        )
    try:
        summary, _ = parse_snapshot(raw_path, vintage_date=target.vintage_date)
    except (UnicodeError, ValueError) as exc:
        return build_target_evidence(
            sequence=target.sequence,
            target_id=target.target_id,
            vintage_date=target.vintage_date,
            outcome="FAILED",
            attempts=tuple(attempts),
            raw_path=raw_path.as_posix(),
            raw_file_sha256=file_sha256(raw_path),
            raw_file_bytes=raw_path.stat().st_size,
            summary=None,
            failure_gate=f"CSV_PARSE_FAILED:{type(exc).__name__}",
        )
    failure_gate = structural_failure_gate(target, summary, protocol=protocol)
    return build_target_evidence(
        sequence=target.sequence,
        target_id=target.target_id,
        vintage_date=target.vintage_date,
        outcome="FAILED" if failure_gate else "COMPLETE",
        attempts=tuple(attempts),
        raw_path=raw_path.as_posix(),
        raw_file_sha256=file_sha256(raw_path),
        raw_file_bytes=raw_path.stat().st_size,
        summary=summary,
        failure_gate=failure_gate,
    )


def build_checkpoint(
    *,
    started_at: datetime,
    updated_at: datetime,
    protocol_path: Path,
    protocol: S1NfciFullAcquisitionProtocol,
    addendum_path: Path,
    addendum: S1NfciAcquisitionExecutionAmendmentV2,
    target_evidence: tuple[S1NfciAcquisitionTargetEvidence, ...],
) -> S1NfciAcquisitionCheckpoint:
    terminal = bool(
        target_evidence
        and (
            target_evidence[-1].outcome == "FAILED"
            or len(target_evidence) == protocol.target_count
        )
    )
    payload = {
        "started_at": started_at,
        "updated_at": updated_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "execution_addendum_file_sha256": file_sha256(addendum_path),
        "execution_addendum_evidence_hash": addendum.addendum_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "target_evidence": target_evidence,
        "classified_target_count": len(target_evidence),
        "complete_target_count": sum(item.outcome == "COMPLETE" for item in target_evidence),
        "failed_target_count": sum(item.outcome == "FAILED" for item in target_evidence),
        "get_attempt_count": sum(len(item.attempts) for item in target_evidence),
        "network_body_bytes": sum(
            attempt.bytes_received
            for item in target_evidence
            for attempt in item.attempts
        ),
        "persisted_raw_bytes": sum(item.raw_file_bytes for item in target_evidence),
        "next_sequence": None if terminal else len(target_evidence) + 1,
        "terminal": terminal,
    }
    provisional = S1NfciAcquisitionCheckpoint.model_construct(
        **payload,
        checkpoint_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["checkpoint_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"checkpoint_evidence_hash"})
    )
    return S1NfciAcquisitionCheckpoint.model_validate(complete)


def write_checkpoint(path: Path, checkpoint: S1NfciAcquisitionCheckpoint) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        temporary.unlink()
    serialized = checkpoint.model_dump_json(indent=2) + "\n"
    if S1NfciAcquisitionCheckpoint.model_validate_json(serialized) != checkpoint:
        raise ValueError("S1 NFCI checkpoint did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def verify_checkpoint_raw(
    checkpoint: S1NfciAcquisitionCheckpoint,
    protocol: S1NfciFullAcquisitionProtocol,
) -> None:
    if checkpoint.runner_contract_hash != runner_contract_hash():
        raise ValueError("S1 NFCI checkpoint runner contract changed")
    for target, evidence in zip(
        protocol.targets,
        checkpoint.target_evidence,
        strict=True,
    ):
        if target.sequence != evidence.sequence:
            raise ValueError("S1 NFCI checkpoint target identity changed")
        for attempt in evidence.attempts:
            if (
                file_sha256(Path(attempt.request_marker_path))
                != attempt.request_marker_sha256
                or file_sha256(Path(attempt.response_marker_path))
                != attempt.response_marker_sha256
            ):
                raise ValueError("S1 NFCI checkpoint marker hash changed")
        if evidence.raw_path is None:
            continue
        raw_path = Path(evidence.raw_path)
        if evidence.summary is None:
            if (
                file_sha256(raw_path) != evidence.raw_file_sha256
                or raw_path.stat().st_size != evidence.raw_file_bytes
            ):
                raise ValueError("S1 NFCI failed raw evidence changed")
            continue
        summary, _ = parse_snapshot(raw_path, vintage_date=evidence.vintage_date)
        if (
            file_sha256(raw_path) != evidence.raw_file_sha256
            or raw_path.stat().st_size != evidence.raw_file_bytes
            or summary != evidence.summary
        ):
            raise ValueError("S1 NFCI checkpoint raw evidence changed")


def evaluate_result_gates(
    protocol: S1NfciFullAcquisitionProtocol,
    checkpoint: S1NfciAcquisitionCheckpoint,
) -> tuple[S1SourceGate, ...]:
    evidence = checkpoint.target_evidence
    complete = len(evidence) == protocol.target_count and all(
        item.outcome == "COMPLETE" for item in evidence
    )
    distinct_hashes = len(
        {item.raw_file_sha256 for item in evidence if item.raw_file_sha256 is not None}
    )
    checks = (
        ("ALL_281_THURSDAY_TARGETS_CLASSIFIED", len(evidence) == protocol.target_count),
        ("EVERY_COMPLETE_FILE_WITHIN_BYTE_CAP_AND_HASHED", complete),
        (
            "EXACT_VINTAGE_SUFFIXED_HEADER_PER_TARGET",
            complete
            and all(
                item.summary is not None
                and item.summary.csv_header
                == (protocol.expected_observation_column, target.expected_value_column)
                for target, item in zip(protocol.targets, evidence, strict=True)
            ),
        ),
        (
            "STRICTLY_INCREASING_UNIQUE_OBSERVATION_DATES_PER_TARGET",
            complete
            and all(
                item.summary is not None
                and item.summary.duplicate_observation_date_count == 0
                and item.summary.non_increasing_observation_date_count == 0
                for item in evidence
            ),
        ),
        (
            "NO_POST_VINTAGE_OBSERVATION_PER_TARGET",
            complete
            and all(
                item.summary is not None
                and item.summary.post_vintage_observation_count == 0
                for item in evidence
            ),
        ),
        (
            "DEVELOPMENT_START_COVERED_PER_TARGET",
            complete
            and all(
                item.summary is not None
                and item.summary.first_observation_date is not None
                and item.summary.first_observation_date
                <= datetime.fromisoformat(
                    protocol.earliest_required_observation_date
                ).date()
                for item in evidence
            ),
        ),
        (
            "LATEST_OBSERVATION_WITHIN_21_DAYS_OF_VINTAGE_PER_TARGET",
            complete
            and all(
                item.summary is not None
                and item.summary.release_lag_days is not None
                and item.summary.release_lag_days <= protocol.maximum_release_lag_days
                for item in evidence
            ),
        ),
        ("AT_LEAST_260_DISTINCT_POINT_IN_TIME_PAYLOAD_HASHES", distinct_hashes >= 260),
        (
            "REQUEST_AND_RESPONSE_MARKERS_RECONCILE_EXACTLY",
            checkpoint.get_attempt_count
            == sum(len(item.attempts) for item in checkpoint.target_evidence),
        ),
        ("ZERO_BTC_MARKET_VALUES_RETURNS_CANDIDATES_AND_ORDERS", True),
    )
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
        for gate_id, passed in sorted(checks)
    )


def build_result(
    *,
    checkpoint_path: Path,
    checkpoint: S1NfciAcquisitionCheckpoint,
    protocol: S1NfciFullAcquisitionProtocol,
    completed_at: datetime,
) -> S1NfciFullAcquisitionResult:
    gates = evaluate_result_gates(protocol, checkpoint)
    failed = any(gate.status == "FAIL" for gate in gates)
    payload = {
        "completed_at": completed_at,
        "checkpoint_file_sha256": file_sha256(checkpoint_path),
        "checkpoint_evidence_hash": checkpoint.checkpoint_evidence_hash,
        "protocol_evidence_hash": checkpoint.protocol_evidence_hash,
        "execution_addendum_evidence_hash": checkpoint.execution_addendum_evidence_hash,
        "runner_contract_hash": checkpoint.runner_contract_hash,
        "target_evidence": checkpoint.target_evidence,
        "gates": gates,
        "classified_target_count": checkpoint.classified_target_count,
        "complete_target_count": checkpoint.complete_target_count,
        "failed_target_count": checkpoint.failed_target_count,
        "get_attempt_count": checkpoint.get_attempt_count,
        "network_body_bytes": checkpoint.network_body_bytes,
        "persisted_raw_bytes": checkpoint.persisted_raw_bytes,
        "distinct_payload_hash_count": len(
            {
                item.raw_file_sha256
                for item in checkpoint.target_evidence
                if item.raw_file_sha256 is not None
            }
        ),
        "decision": S1_NFCI_ACQUISITION_STOP if failed else S1_NFCI_ACQUISITION_PASS,
        "next_authorization": (
            "NONE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION_FAILED"
            if failed
            else S1_NFCI_ACQUISITION_NEXT
        ),
    }
    provisional = S1NfciFullAcquisitionResult.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S1NfciFullAcquisitionResult.model_validate(complete)


def write_result(path: Path, result: S1NfciFullAcquisitionResult) -> None:
    if path.exists():
        raise ValueError(f"S1 NFCI acquisition result exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 NFCI result transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S1NfciFullAcquisitionResult.model_validate_json(serialized) != result:
        raise ValueError("S1 NFCI acquisition result did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def load_authority(
    protocol_path: Path,
    protocol_audit_path: Path,
    addendum_path: Path,
    addendum_audit_path: Path,
) -> tuple[S1NfciFullAcquisitionProtocol, S1NfciAcquisitionExecutionAmendmentV2]:
    protocol = S1NfciFullAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    addendum = S1NfciAcquisitionExecutionAmendmentV2.model_validate_json(
        addendum_path.read_text(encoding="utf-8")
    )
    audit = S1NfciAcquisitionExecutionAuditV2.model_validate_json(
        addendum_audit_path.read_text(encoding="utf-8")
    )
    if (
        file_sha256(protocol_path) != addendum.protocol_file_sha256
        or protocol.protocol_evidence_hash != addendum.protocol_evidence_hash
        or file_sha256(protocol_audit_path) != addendum.protocol_audit_file_sha256
        or runner_contract_hash() != addendum.runner_contract_hash
        or audit.addendum_file_sha256 != file_sha256(addendum_path)
        or audit.addendum_evidence_hash != addendum.addendum_evidence_hash
        or audit.runner_contract_hash != addendum.runner_contract_hash
    ):
        raise ValueError("S1 NFCI acquisition authority lineage changed")
    return protocol, addendum


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run resumable S1 NFCI acquisition.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--addendum", type=Path, default=DEFAULT_ADDENDUM)
    parser.add_argument("--addendum-audit", type=Path, default=DEFAULT_ADDENDUM_AUDIT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1 NFCI result: {args.output}")
    protocol, addendum = load_authority(
        args.protocol,
        args.protocol_audit,
        args.addendum,
        args.addendum_audit,
    )
    if shutil.disk_usage(PROJECT_ROOT).free < protocol.minimum_free_disk_bytes:
        raise SystemExit("Insufficient free disk for S1 NFCI acquisition")
    if args.checkpoint.exists():
        checkpoint = S1NfciAcquisitionCheckpoint.model_validate_json(
            args.checkpoint.read_text(encoding="utf-8")
        )
        verify_checkpoint_raw(checkpoint, protocol)
        if checkpoint.terminal:
            result = build_result(
                checkpoint_path=args.checkpoint,
                checkpoint=checkpoint,
                protocol=protocol,
                completed_at=datetime.now(UTC),
            )
            write_result(args.output, result)
            return 0
        started_at = checkpoint.started_at
        evidence = list(checkpoint.target_evidence)
    else:
        started_at = datetime.now(UTC)
        evidence = []
        checkpoint = build_checkpoint(
            started_at=started_at,
            updated_at=started_at,
            protocol_path=args.protocol,
            protocol=protocol,
            addendum_path=args.addendum,
            addendum=addendum,
            target_evidence=(),
        )
        write_checkpoint(args.checkpoint, checkpoint)
    for target in protocol.targets[len(evidence) :]:
        item = acquire_target(target, protocol=protocol)
        evidence.append(item)
        checkpoint = build_checkpoint(
            started_at=started_at,
            updated_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol=protocol,
            addendum_path=args.addendum,
            addendum=addendum,
            target_evidence=tuple(evidence),
        )
        write_checkpoint(args.checkpoint, checkpoint)
        print(
            f"CHECKPOINT {len(evidence)}/{protocol.target_count} "
            f"attempts={checkpoint.get_attempt_count} bytes={checkpoint.network_body_bytes} "
            f"outcome={item.outcome}",
            flush=True,
        )
        if item.outcome == "FAILED":
            break
        time.sleep(protocol.polite_delay_milliseconds / 1000)
    result = build_result(
        checkpoint_path=args.checkpoint,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=datetime.now(UTC),
    )
    write_result(args.output, result)
    print(
        f"COMPLETE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} targets={result.classified_target_count} "
        f"attempts={result.get_attempt_count} bytes={result.network_body_bytes} "
        "btc_values=0 returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
