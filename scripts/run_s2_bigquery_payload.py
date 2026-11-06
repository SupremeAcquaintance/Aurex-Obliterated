from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed  # noqa: E402
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (  # noqa: E402
    S2BigQueryFeasibilityAuditV3,
    S2BigQueryFeasibilityResultV3,
)
from aurex.backtest_engine.s2_bigquery_payload import (  # noqa: E402
    S2_PAYLOAD_BLOCK_AUTH,
    S2_PAYLOAD_BLOCK_BILLING,
    S2_PAYLOAD_BLOCK_CLIENT,
    S2_PAYLOAD_BLOCK_PROJECT,
    S2_PAYLOAD_BLOCK_QUERY,
    S2_PAYLOAD_BLOCK_TOKEN,
    S2_PAYLOAD_BLOCK_VALIDATION,
    S2_PAYLOAD_NEXT,
    S2_PAYLOAD_PASS,
    S2_PAYLOAD_RETRY,
    S2BigQueryPayloadProtocol,
    S2BigQueryPayloadProtocolAudit,
    S2BigQueryPayloadResult,
    S2DevelopmentWeeklyPayload,
    S2DevelopmentWeeklyRow,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s2_bigquery_feasibility_v2 import (  # noqa: E402
    access_token,
    active_auth_available,
    active_project,
    resolve_command,
    verify_sandbox_without_billing,
)
from scripts.run_s2_bigquery_feasibility_v3 import (  # noqa: E402
    classify_rest_error,
    error_reasons,
)

DEFAULT_PROTOCOL = Path("data/evidence/s2_bigquery_payload_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s2_bigquery_payload_protocol_audit_v1.json")
DEFAULT_FEASIBILITY_RESULT = Path("data/evidence/s2_bigquery_feasibility_result_v3.json")
DEFAULT_FEASIBILITY_AUDIT = Path("data/evidence/s2_bigquery_feasibility_audit_v3.json")
DEFAULT_PAYLOAD = Path("data/evidence/s2_development_weekly_payload_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_payload_result_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_payload.py")
V2_HELPER_PATH = Path("scripts/run_s2_bigquery_feasibility_v2.py")
V3_HELPER_PATH = Path("scripts/run_s2_bigquery_feasibility_v3.py")


@dataclass(frozen=True)
class QueryOutcome:
    completed: bool
    poll_count: int
    page_count: int
    total_bytes_processed: int | None
    raw_row_count: int
    rows: tuple[S2DevelopmentWeeklyRow, ...]
    error_class: str


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def runner_contract_hash() -> str:
    path = Path(__file__).resolve()
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(MODULE_PATH),
            "v2_helper_path": V2_HELPER_PATH.as_posix(),
            "v2_helper_sha256": file_sha256(V2_HELPER_PATH),
            "v3_helper_path": V3_HELPER_PATH.as_posix(),
            "v3_helper_sha256": file_sha256(V3_HELPER_PATH),
            "runner_path": path.relative_to(PROJECT_ROOT).as_posix(),
            "runner_sha256": file_sha256(path),
        }
    )


def request_json(
    request: Request,
    *,
    timeout: int,
    maximum: int,
) -> tuple[int, object | None, str]:
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = response.read(maximum + 1)
            status = int(response.status)
    except HTTPError as exc:
        body = exc.read(maximum + 1)
        status = int(exc.code)
    except TimeoutError:
        return 0, None, "TIMEOUT"
    except (URLError, OSError):
        return 0, None, "NETWORK_ERROR"
    if len(body) > maximum:
        return status, None, "INVALID_RESPONSE"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return status, None, "INVALID_RESPONSE"
    if status != 200 or error_reasons(payload):
        return status, payload, classify_rest_error(status, payload)
    return status, payload, "NONE"


def query_request(protocol: S2BigQueryPayloadProtocol, *, token: str, project: str) -> Request:
    endpoint = protocol.query_endpoint_template.format(project=quote(project, safe=""))
    body = json.dumps(
        {
            "formatOptions": {"useInt64Timestamp": False},
            "location": protocol.processing_location,
            "maxResults": protocol.page_size,
            "maximumBytesBilled": str(protocol.query_spec.maximum_bytes_billed),
            "query": protocol.query_spec.google_sql,
            "timeoutMs": protocol.query_timeout_milliseconds,
            "useLegacySql": protocol.use_legacy_sql,
            "useQueryCache": protocol.use_query_cache,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Aurex-S2-Payload/1",
        },
    )


def poll_request(
    protocol: S2BigQueryPayloadProtocol,
    *,
    token: str,
    project: str,
    job_id: str,
) -> Request:
    endpoint = protocol.query_results_endpoint_template.format(
        project=quote(project, safe=""),
        job_id=quote(job_id, safe=""),
    )
    query = urlencode(
        {
            "location": protocol.processing_location,
            "maxResults": protocol.page_size,
            "timeoutMs": protocol.query_timeout_milliseconds,
        }
    )
    return Request(
        f"{endpoint}?{query}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Aurex-S2-Payload/1",
        },
    )


def response_integer(payload: dict, key: str) -> int | None:
    value = payload.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_completed_response(
    protocol: S2BigQueryPayloadProtocol,
    payload: object,
    *,
    poll_count: int,
) -> QueryOutcome:
    if not isinstance(payload, dict) or payload.get("jobComplete") is not True:
        return QueryOutcome(False, poll_count, 0, None, 0, (), "INVALID_RESPONSE")
    schema = payload.get("schema")
    schema_fields = schema.get("fields", []) if isinstance(schema, dict) else []
    if not isinstance(schema_fields, list):
        return QueryOutcome(True, poll_count, 1, None, 0, (), "SCHEMA_MISMATCH")
    names = tuple(item.get("name") for item in schema_fields if isinstance(item, dict))
    types = tuple(item.get("type") for item in schema_fields if isinstance(item, dict))
    if (
        names != protocol.query_spec.expected_field_names
        or types != protocol.query_spec.expected_field_types
        or payload.get("pageToken")
    ):
        return QueryOutcome(True, poll_count, 1, None, 0, (), "SCHEMA_MISMATCH")
    raw_rows = payload.get("rows", [])
    if not isinstance(raw_rows, list):
        return QueryOutcome(True, poll_count, 1, None, 0, (), "INVALID_ROWS")
    total_rows = response_integer(payload, "totalRows")
    processed = response_integer(payload, "totalBytesProcessed")
    if total_rows != len(raw_rows) or processed is None:
        return QueryOutcome(
            True,
            poll_count,
            1,
            processed,
            len(raw_rows),
            (),
            "ROW_COUNT_MISMATCH",
        )
    rows = []
    try:
        for raw_row in raw_rows:
            cells = raw_row["f"]
            values = [cell["v"] for cell in cells]
            if len(values) != len(names) or any(value is None for value in values):
                raise ValueError("S2 payload row is incomplete")
            rows.append(
                S2DevelopmentWeeklyRow.model_validate(dict(zip(names, values, strict=True)))
            )
    except (KeyError, TypeError, ValueError):
        return QueryOutcome(
            True,
            poll_count,
            1,
            processed,
            len(raw_rows),
            (),
            "INVALID_ROWS",
        )
    return QueryOutcome(
        True,
        poll_count,
        1,
        processed,
        len(raw_rows),
        tuple(rows),
        "NONE",
    )


def execute_query(
    protocol: S2BigQueryPayloadProtocol,
    *,
    token: str,
    project: str,
) -> QueryOutcome:
    _, payload, error = request_json(
        query_request(protocol, token=token, project=project),
        timeout=protocol.request_timeout_seconds,
        maximum=protocol.maximum_response_bytes_each,
    )
    if error != "NONE" or not isinstance(payload, dict):
        return QueryOutcome(False, 0, 0, None, 0, (), error)
    if payload.get("jobComplete") is True:
        return parse_completed_response(protocol, payload, poll_count=0)
    job_reference = payload.get("jobReference")
    job_id = job_reference.get("jobId") if isinstance(job_reference, dict) else None
    if not isinstance(job_id, str) or not job_id:
        return QueryOutcome(False, 0, 0, None, 0, (), "INVALID_RESPONSE")
    for poll_count in range(1, protocol.maximum_query_result_polls + 1):
        time.sleep(protocol.poll_interval_seconds)
        _, payload, error = request_json(
            poll_request(
                protocol,
                token=token,
                project=project,
                job_id=job_id,
            ),
            timeout=protocol.request_timeout_seconds,
            maximum=protocol.maximum_response_bytes_each,
        )
        if error != "NONE" or not isinstance(payload, dict):
            return QueryOutcome(False, poll_count, 0, None, 0, (), error)
        if payload.get("jobComplete") is True:
            return parse_completed_response(protocol, payload, poll_count=poll_count)
    return QueryOutcome(False, protocol.maximum_query_result_polls, 0, None, 0, (), "TIMEOUT")


def build_payload(
    protocol: S2BigQueryPayloadProtocol,
    *,
    acquired_at: datetime,
    rows: tuple[S2DevelopmentWeeklyRow, ...],
) -> S2DevelopmentWeeklyPayload:
    return build_hashed(
        S2DevelopmentWeeklyPayload,
        "payload_evidence_hash",
        {
            "acquired_at": acquired_at,
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "query_sha256": protocol.query_spec.query_sha256,
            "rows": rows,
        },
    )


def serialized_model(model) -> bytes:
    return (model.model_dump_json(indent=2) + "\n").encode("utf-8")


def build_result(
    *,
    generated_at: datetime,
    protocol: S2BigQueryPayloadProtocol,
    protocol_path: Path,
    protocol_audit: S2BigQueryPayloadProtocolAudit,
    protocol_audit_path: Path,
    feasibility_result: S2BigQueryFeasibilityResultV3,
    feasibility_audit: S2BigQueryFeasibilityAuditV3,
    gcloud_available: bool,
    active_auth_configured: bool,
    active_project_configured: bool,
    billing_boundary_request_count: int,
    sandbox_without_billing_verified: bool,
    access_token_request_count: int,
    access_token_available: bool,
    query_submission_count: int,
    outcome: QueryOutcome,
    payload: S2DevelopmentWeeklyPayload | None,
    payload_bytes: bytes | None,
) -> S2BigQueryPayloadResult:
    blockers = []
    if not gcloud_available:
        blockers.append("gcloud_command_unavailable")
    if gcloud_available and not active_auth_configured:
        blockers.append("active_google_cloud_auth_unavailable")
    if active_auth_configured and not active_project_configured:
        blockers.append("active_google_cloud_project_unconfigured")
    if active_project_configured and not sandbox_without_billing_verified:
        blockers.append("sandbox_without_billing_not_verified")
    if sandbox_without_billing_verified and not access_token_available:
        blockers.append("access_token_unavailable")
    if query_submission_count == 1 and not outcome.completed:
        blockers.append(f"query_{outcome.error_class.lower()}")
    if outcome.completed and payload is None:
        blockers.append(f"payload_{outcome.error_class.lower()}")
    payload_present = payload is not None and payload_bytes is not None
    if not gcloud_available:
        decision = S2_PAYLOAD_BLOCK_CLIENT
    elif not active_auth_configured:
        decision = S2_PAYLOAD_BLOCK_AUTH
    elif not active_project_configured:
        decision = S2_PAYLOAD_BLOCK_PROJECT
    elif not sandbox_without_billing_verified:
        decision = S2_PAYLOAD_BLOCK_BILLING
    elif not access_token_available:
        decision = S2_PAYLOAD_BLOCK_TOKEN
    elif query_submission_count != 1 or not outcome.completed:
        decision = S2_PAYLOAD_BLOCK_QUERY
    elif not payload_present:
        decision = S2_PAYLOAD_BLOCK_VALIDATION
    else:
        decision = S2_PAYLOAD_PASS
    return build_hashed(
        S2BigQueryPayloadResult,
        "result_evidence_hash",
        {
            "generated_at": generated_at,
            "protocol_file_sha256": file_sha256(protocol_path),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_file_sha256": file_sha256(protocol_audit_path),
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "feasibility_result_evidence_hash": feasibility_result.result_evidence_hash,
            "feasibility_result_audit_evidence_hash": feasibility_audit.audit_evidence_hash,
            "runner_contract_hash": runner_contract_hash(),
            "gcloud_available": gcloud_available,
            "active_auth_configured": active_auth_configured,
            "active_project_configured": active_project_configured,
            "billing_boundary_request_count": billing_boundary_request_count,
            "sandbox_without_billing_verified": sandbox_without_billing_verified,
            "access_token_request_count": access_token_request_count,
            "access_token_available": access_token_available,
            "query_submission_count": query_submission_count,
            "query_result_poll_count": outcome.poll_count,
            "query_result_page_count": outcome.page_count,
            "query_completed": outcome.completed,
            "total_bytes_processed": outcome.total_bytes_processed,
            "query_result_rows_returned": outcome.raw_row_count,
            "blockchain_row_values_read": outcome.raw_row_count,
            "payload_path": protocol.payload_path if payload_present else None,
            "payload_file_sha256": sha256(payload_bytes).hexdigest() if payload_bytes else None,
            "payload_evidence_hash": payload.payload_evidence_hash if payload else None,
            "payload_byte_count": len(payload_bytes) if payload_bytes else 0,
            "blockers": tuple(sorted(set(blockers))),
            "decision": decision,
            "next_authorization": (
                S2_PAYLOAD_NEXT if decision == S2_PAYLOAD_PASS else S2_PAYLOAD_RETRY
            ),
            "authorizes_measurement_protocol": decision == S2_PAYLOAD_PASS,
            "limitations": protocol.limitations,
        },
    )


def validate_lineage(args):
    protocol = S2BigQueryPayloadProtocol.model_validate_json(args.protocol.read_text())
    protocol_audit = S2BigQueryPayloadProtocolAudit.model_validate_json(
        args.protocol_audit.read_text()
    )
    feasibility_result = S2BigQueryFeasibilityResultV3.model_validate_json(
        args.feasibility_result.read_text()
    )
    feasibility_audit = S2BigQueryFeasibilityAuditV3.model_validate_json(
        args.feasibility_audit.read_text()
    )
    if (
        file_sha256(args.protocol) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.feasibility_result_evidence_hash != feasibility_result.result_evidence_hash
        or protocol.feasibility_result_audit_evidence_hash != feasibility_audit.audit_evidence_hash
        or feasibility_result.result_evidence_hash != feasibility_audit.result_evidence_hash
    ):
        raise ValueError("S2 BigQuery payload lineage changed")
    for binding in protocol.source_bindings:
        path = PROJECT_ROOT / binding.path
        if not path.is_file() or file_sha256(path) != binding.file_sha256:
            raise ValueError("S2 BigQuery payload source binding changed")
    return protocol, protocol_audit, feasibility_result, feasibility_audit


def write_once(path: Path, body: bytes) -> None:
    if path.exists():
        raise ValueError(f"S2 payload artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 payload transaction exists: {temporary}")
    temporary.write_bytes(body)
    temporary.replace(path)


def run(args) -> S2BigQueryPayloadResult:
    if args.output.exists() or args.payload.exists():
        raise ValueError("S2 BigQuery payload result or payload already exists")
    protocol, protocol_audit, feasibility_result, feasibility_audit = validate_lineage(args)
    if args.payload.as_posix() != protocol.payload_path:
        raise ValueError("S2 payload output path changed")
    gcloud_path = resolve_command("gcloud")
    auth = active_auth_available(gcloud_path)
    project = active_project(gcloud_path) if auth else None
    billing_count = 0
    no_billing = False
    token_count = 0
    token = None
    submission_count = 0
    outcome = QueryOutcome(False, 0, 0, None, 0, (), "NOT_ATTEMPTED")
    payload = None
    payload_bytes = None
    if gcloud_path and auth and project:
        billing_count, no_billing = verify_sandbox_without_billing(gcloud_path, project)
    if no_billing and gcloud_path:
        token_count, token = access_token(gcloud_path)
    if token and project:
        submission_count = 1
        outcome = execute_query(protocol, token=token, project=project)
    if (
        outcome.completed
        and outcome.error_class == "NONE"
        and outcome.total_bytes_processed is not None
        and outcome.total_bytes_processed <= protocol.query_spec.maximum_bytes_billed
        and outcome.raw_row_count == protocol.query_spec.expected_row_count
    ):
        try:
            payload = build_payload(
                protocol,
                acquired_at=datetime.now(UTC),
                rows=outcome.rows,
            )
            payload_bytes = serialized_model(payload)
        except ValueError:
            payload = None
            payload_bytes = None
    result = build_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        protocol_path=args.protocol,
        protocol_audit=protocol_audit,
        protocol_audit_path=args.protocol_audit,
        feasibility_result=feasibility_result,
        feasibility_audit=feasibility_audit,
        gcloud_available=gcloud_path is not None,
        active_auth_configured=auth,
        active_project_configured=project is not None,
        billing_boundary_request_count=billing_count,
        sandbox_without_billing_verified=no_billing,
        access_token_request_count=token_count,
        access_token_available=token is not None,
        query_submission_count=submission_count,
        outcome=outcome,
        payload=payload,
        payload_bytes=payload_bytes,
    )
    result_bytes = serialized_model(result)
    if payload_bytes is not None:
        write_once(args.payload, payload_bytes)
    write_once(args.output, result_bytes)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} submissions={result.query_submission_count}/1 "
        f"polls={result.query_result_poll_count}/30 rows={result.query_result_rows_returned}/280 "
        f"processed={result.total_bytes_processed or 0}/60000000000 "
        "market_values=0 returns=0 orders=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Run S2 development payload once.")
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--feasibility-result", type=Path, default=DEFAULT_FEASIBILITY_RESULT)
    parser.add_argument("--feasibility-audit", type=Path, default=DEFAULT_FEASIBILITY_AUDIT)
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        run(parse_args())
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
