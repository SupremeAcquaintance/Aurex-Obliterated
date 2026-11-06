from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import (  # noqa: E402
    S2_FEASIBILITY_BLOCK_BILLING,
    S2_FEASIBILITY_BLOCK_CLIENT,
    S2_FEASIBILITY_BLOCK_METADATA,
    S2_FEASIBILITY_BLOCK_PROJECT,
    S2_FEASIBILITY_RETRY,
    S2BigQueryFeasibilityProtocol,
    S2BigQueryFeasibilityProtocolAudit,
    S2BigQueryFeasibilityResult,
    S2MetadataAttempt,
    build_hashed,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s2_bigquery_feasibility_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s2_bigquery_feasibility_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_feasibility_result_v1.json")
DEFAULT_RESPONSE_DIR = Path("data/evidence/s2_bigquery_metadata_v1")
REQUIRED_FIELDS = {
    "BLOCKS_TABLE": ("hash", "number", "timestamp", "transaction_count"),
    "DATASET": (),
    "TRANSACTIONS_TABLE": (
        "block_hash",
        "block_number",
        "block_timestamp",
        "fee",
        "hash",
        "is_coinbase",
    ),
}


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def runner_contract_hash() -> str:
    path = Path(__file__).resolve()
    return universe_evidence_hash(
        {
            "runner_path": path.relative_to(PROJECT_ROOT).as_posix(),
            "runner_sha256": file_sha256(path),
        }
    )


def expected_reference(payload: dict, target_id: str) -> str | None:
    reference_key = "datasetReference" if target_id == "DATASET" else "tableReference"
    reference = payload.get(reference_key)
    if not isinstance(reference, dict):
        return None
    project = reference.get("projectId")
    dataset = reference.get("datasetId")
    if not isinstance(project, str) or not isinstance(dataset, str):
        return None
    if target_id == "DATASET":
        return f"{project}:{dataset}"
    table = reference.get("tableId")
    return f"{project}:{dataset}.{table}" if isinstance(table, str) else None


def schema_fields(payload: dict) -> tuple[str, ...]:
    fields = payload.get("schema", {}).get("fields", [])
    if not isinstance(fields, list):
        return ()
    return tuple(
        sorted(
            item["name"]
            for item in fields
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        )
    )


def fetch_metadata(endpoint, *, timeout: int, maximum_bytes: int):
    request = Request(
        endpoint.url,
        headers={"Accept": "application/json", "User-Agent": "Aurex-S2-Feasibility/1"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > maximum_bytes:
                return None, int(response.status), "INVALID_JSON"
            body = response.read(maximum_bytes + 1)
            if len(body) > maximum_bytes:
                return None, int(response.status), "INVALID_JSON"
            return body, int(response.status), "NONE"
    except HTTPError as exc:
        return None, int(exc.code), "HTTP_ERROR"
    except (TimeoutError, URLError, OSError):
        return None, 0, "NETWORK_ERROR"


def inspect_active_project(gcloud_path: str | None) -> bool:
    if not gcloud_path:
        return False
    try:
        completed = subprocess.run(
            [gcloud_path, "config", "get-value", "project", "--quiet"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    project = completed.stdout.strip()
    return completed.returncode == 0 and bool(project) and project != "(unset)"


def make_attempt(endpoint, *, requested_at: datetime, response_dir: Path):
    body, status, error_class = fetch_metadata(
        endpoint,
        timeout=20,
        maximum_bytes=2_000_000,
    )
    if body is None:
        return S2MetadataAttempt(
            target_id=endpoint.target_id,
            requested_at=requested_at,
            http_status=status,
            response_bytes=0,
            response_sha256=None,
            response_path=None,
            expected_reference_matched=False,
            error_class=error_class,
        ), None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return S2MetadataAttempt(
            target_id=endpoint.target_id,
            requested_at=requested_at,
            http_status=status,
            response_bytes=len(body),
            response_sha256=None,
            response_path=None,
            expected_reference_matched=False,
            error_class="INVALID_JSON",
        ), None
    fields = schema_fields(payload)
    reference_matches = expected_reference(payload, endpoint.target_id) == (
        endpoint.expected_reference
    )
    required = REQUIRED_FIELDS[endpoint.target_id]
    required_present = tuple(item for item in required if item in fields)
    if status != 200 or not reference_matches or required_present != required:
        return S2MetadataAttempt(
            target_id=endpoint.target_id,
            requested_at=requested_at,
            http_status=status,
            response_bytes=len(body),
            response_sha256=None,
            response_path=None,
            expected_reference_matched=False,
            required_schema_fields_present=required_present,
            error_class="INVALID_JSON",
        ), None
    path = response_dir / f"{endpoint.target_id.lower()}_metadata.json"
    relative = path.as_posix()
    return S2MetadataAttempt(
        target_id=endpoint.target_id,
        requested_at=requested_at,
        http_status=status,
        response_bytes=len(body),
        response_sha256=sha256(body).hexdigest(),
        response_path=relative,
        expected_reference_matched=True,
        required_schema_fields_present=required_present,
        error_class="NONE",
    ), body


def write_response(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"S2 metadata response already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 metadata transaction exists: {temporary}")
    temporary.write_bytes(body)
    temporary.replace(path)


def build_result(
    *,
    generated_at: datetime,
    protocol: S2BigQueryFeasibilityProtocol,
    protocol_path: Path,
    protocol_audit: S2BigQueryFeasibilityProtocolAudit,
    protocol_audit_path: Path,
    attempts: tuple[S2MetadataAttempt, ...],
    gcloud_available: bool,
    bq_available: bool,
    active_project_configured: bool,
) -> S2BigQueryFeasibilityResult:
    blockers = []
    for attempt in attempts:
        if attempt.error_class != "NONE":
            blockers.append(
                f"public_metadata_{attempt.target_id.lower()}_"
                f"{attempt.error_class.lower()}"
            )
    if not gcloud_available:
        blockers.append("gcloud_command_unavailable")
    if not bq_available:
        blockers.append("bq_command_unavailable")
    if gcloud_available and not active_project_configured:
        blockers.append("active_google_cloud_project_unconfigured")
    blockers.append("sandbox_without_billing_not_verified")
    blockers.append("dry_runs_not_executed")
    metadata_passed = len(attempts) == 3 and all(
        attempt.error_class == "NONE" for attempt in attempts
    )
    if not metadata_passed:
        decision = S2_FEASIBILITY_BLOCK_METADATA
    elif not (gcloud_available and bq_available):
        decision = S2_FEASIBILITY_BLOCK_CLIENT
    elif not active_project_configured:
        decision = S2_FEASIBILITY_BLOCK_PROJECT
    else:
        decision = S2_FEASIBILITY_BLOCK_BILLING
    return build_hashed(
        S2BigQueryFeasibilityResult,
        "result_evidence_hash",
        {
            "generated_at": generated_at,
            "protocol_file_sha256": file_sha256(protocol_path),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_file_sha256": file_sha256(protocol_audit_path),
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "runner_contract_hash": runner_contract_hash(),
            "metadata_attempts": attempts,
            "gcloud_available": gcloud_available,
            "bq_available": bq_available,
            "active_project_configured": active_project_configured,
            "sandbox_without_billing_verified": False,
            "dry_run_evidence": (),
            "metadata_request_count": len(attempts),
            "dry_run_request_count": 0,
            "blockers": tuple(sorted(set(blockers))),
            "decision": decision,
            "next_authorization": S2_FEASIBILITY_RETRY,
            "limitations": tuple(
                sorted(
                    (
                        "No blockchain table row was requested or returned.",
                        "No BigQuery dry run occurred because local prerequisites failed.",
                        "Public metadata access does not establish current chain coverage.",
                        "The preflight does not establish a profitable strategy.",
                        "The preflight grants no numeric-query or trading authority.",
                    )
                )
            ),
        },
    )


def run(args) -> S2BigQueryFeasibilityResult:
    if args.output.exists():
        raise ValueError(f"S2 BigQuery feasibility result exists: {args.output}")
    protocol = S2BigQueryFeasibilityProtocol.model_validate_json(
        args.protocol.read_text()
    )
    protocol_audit = S2BigQueryFeasibilityProtocolAudit.model_validate_json(
        args.protocol_audit.read_text()
    )
    if (
        file_sha256(args.protocol) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or not protocol_audit.reconstructed_exactly
    ):
        raise ValueError("S2 BigQuery feasibility protocol lineage changed")

    attempts = []
    pending_responses = []
    for endpoint in protocol.metadata_endpoints:
        attempt, body = make_attempt(
            endpoint,
            requested_at=datetime.now(UTC),
            response_dir=args.response_dir,
        )
        attempts.append(attempt)
        if body is not None and attempt.response_path is not None:
            pending_responses.append((Path(attempt.response_path), body))

    gcloud_path = shutil.which("gcloud")
    bq_path = shutil.which("bq")
    result = build_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        protocol_path=args.protocol,
        protocol_audit=protocol_audit,
        protocol_audit_path=args.protocol_audit,
        attempts=tuple(attempts),
        gcloud_available=gcloud_path is not None,
        bq_available=bq_path is not None,
        active_project_configured=inspect_active_project(gcloud_path),
    )
    for path, body in pending_responses:
        write_response(path, body)
    args.output.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} metadata={result.metadata_request_count}/3 "
        "dry_runs=0 rows=0 values=0 returns=0 orders=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Run bounded S2 BigQuery feasibility.")
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--protocol-audit",
        type=Path,
        default=DEFAULT_PROTOCOL_AUDIT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--response-dir", type=Path, default=DEFAULT_RESPONSE_DIR)
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
