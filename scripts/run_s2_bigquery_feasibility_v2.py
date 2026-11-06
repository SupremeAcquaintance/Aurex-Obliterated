from __future__ import annotations

import argparse
import json
import os
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
    S2BigQueryFeasibilityAudit,
    S2BigQueryFeasibilityResult,
    S2MetadataAttempt,
    build_hashed,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v2 import (  # noqa: E402
    S2_FEASIBILITY_V2_BLOCK_AUTH,
    S2_FEASIBILITY_V2_BLOCK_BILLING,
    S2_FEASIBILITY_V2_BLOCK_CLIENT,
    S2_FEASIBILITY_V2_BLOCK_DRY_RUN,
    S2_FEASIBILITY_V2_BLOCK_METADATA,
    S2_FEASIBILITY_V2_BLOCK_PROJECT,
    S2_FEASIBILITY_V2_NEXT,
    S2_FEASIBILITY_V2_PASS,
    S2_FEASIBILITY_V2_RETRY,
    S2BigQueryFeasibilityProtocolAuditV2,
    S2BigQueryFeasibilityProtocolV2,
    S2BigQueryFeasibilityResultV2,
    S2DryRunAttemptV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s2_bigquery_feasibility_protocol_v2.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v2.json")
DEFAULT_PRIOR_RESULT = Path("data/evidence/s2_bigquery_feasibility_result_v1.json")
DEFAULT_PRIOR_AUDIT = Path("data/evidence/s2_bigquery_feasibility_audit_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_feasibility_result_v2.json")
DEFAULT_RESPONSE_DIR = Path("data/evidence/s2_bigquery_metadata_v2")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_feasibility_v2.py")
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
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(MODULE_PATH),
            "runner_path": path.relative_to(PROJECT_ROOT).as_posix(),
            "runner_sha256": file_sha256(path),
        }
    )


def command_environment() -> dict[str, str]:
    environment = os.environ.copy()
    if not environment.get("CLOUDSDK_PYTHON"):
        environment["CLOUDSDK_PYTHON"] = str(getattr(sys, "_base_executable", sys.executable))
    return environment


def resolve_command(name: str) -> str | None:
    configured = os.environ.get(f"AUREX_{name.upper()}_BIN")
    candidates = [configured, shutil.which(name)]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            str(Path(local_app_data) / "AurexTools579" / "google-cloud-sdk" / "bin" / f"{name}.cmd")
        )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return None


def run_command(command: list[str], *, timeout: int = 20):
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=command_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def active_auth_available(gcloud_path: str | None) -> bool:
    if not gcloud_path:
        return False
    completed = run_command(
        [
            gcloud_path,
            "auth",
            "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
        ]
    )
    return bool(completed and completed.returncode == 0 and completed.stdout.strip())


def active_project(gcloud_path: str | None) -> str | None:
    if not gcloud_path:
        return None
    completed = run_command([gcloud_path, "config", "get-value", "project", "--quiet"])
    if not completed or completed.returncode != 0:
        return None
    project = completed.stdout.strip()
    return project if project and project != "(unset)" else None


def verify_sandbox_without_billing(
    gcloud_path: str,
    project: str,
) -> tuple[int, bool]:
    completed = run_command(
        [
            gcloud_path,
            "billing",
            "projects",
            "describe",
            project,
            "--format=value(billingEnabled)",
            "--quiet",
        ]
    )
    if not completed or completed.returncode != 0:
        return 1, False
    value = completed.stdout.strip().lower()
    return 1, value == "false"


def access_token(gcloud_path: str) -> tuple[int, str | None]:
    completed = run_command([gcloud_path, "auth", "print-access-token"])
    if not completed or completed.returncode != 0:
        return 1, None
    token = completed.stdout.strip()
    return 1, token if token else None


def expected_reference(payload: dict, target_id: str) -> str | None:
    key = "datasetReference" if target_id == "DATASET" else "tableReference"
    reference = payload.get(key)
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


def fetch_authenticated_metadata(endpoint, *, token: str, timeout: int, maximum: int):
    request = Request(
        endpoint.url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Aurex-S2-Feasibility/2",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            length = response.headers.get("Content-Length")
            if length and int(length) > maximum:
                return None, int(response.status), "INVALID_JSON"
            body = response.read(maximum + 1)
            if len(body) > maximum:
                return None, int(response.status), "INVALID_JSON"
            return body, int(response.status), "NONE"
    except HTTPError as exc:
        return None, int(exc.code), "HTTP_ERROR"
    except (TimeoutError, URLError, OSError):
        return None, 0, "NETWORK_ERROR"


def make_metadata_attempt(endpoint, *, token: str, requested_at: datetime, response_dir: Path):
    body, status, error_class = fetch_authenticated_metadata(
        endpoint,
        token=token,
        timeout=20,
        maximum=2_000_000,
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
    required = REQUIRED_FIELDS[endpoint.target_id]
    required_present = tuple(item for item in required if item in fields)
    reference_matches = expected_reference(payload, endpoint.target_id) == (
        endpoint.expected_reference
    )
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
    return S2MetadataAttempt(
        target_id=endpoint.target_id,
        requested_at=requested_at,
        http_status=status,
        response_bytes=len(body),
        response_sha256=sha256(body).hexdigest(),
        response_path=path.as_posix(),
        expected_reference_matched=True,
        required_schema_fields_present=required_present,
        error_class="NONE",
    ), body


def write_response(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"S2 metadata v2 response already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 metadata v2 transaction exists: {temporary}")
    temporary.write_bytes(body)
    temporary.replace(path)


def make_dry_run_attempt(
    bq_path: str,
    *,
    project: str,
    location: str,
    spec,
    requested_at: datetime,
) -> S2DryRunAttemptV2:
    completed = run_command(
        [
            bq_path,
            "--format=json",
            f"--project_id={project}",
            f"--location={location}",
            "query",
            "--use_legacy_sql=false",
            "--dry_run=true",
            spec.google_sql,
        ],
        timeout=60,
    )
    if completed is None:
        return S2DryRunAttemptV2(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=requested_at,
            succeeded=False,
            error_class="TIMEOUT",
        )
    if completed.returncode != 0:
        error_text = completed.stderr.lower()
        error_class = (
            "AUTH_ERROR" if "auth" in error_text or "credential" in error_text else "API_ERROR"
        )
        return S2DryRunAttemptV2(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=requested_at,
            succeeded=False,
            error_class=error_class,
        )
    try:
        payload = json.loads(completed.stdout)
        processed = int(payload["statistics"]["query"]["totalBytesProcessed"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return S2DryRunAttemptV2(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=requested_at,
            succeeded=False,
            error_class="INVALID_RESPONSE",
        )
    return S2DryRunAttemptV2(
        query_id=spec.query_id,
        query_sha256=spec.query_sha256,
        requested_at=requested_at,
        succeeded=True,
        total_bytes_processed=processed,
        error_class="NONE",
    )


def build_result(
    *,
    generated_at: datetime,
    protocol: S2BigQueryFeasibilityProtocolV2,
    protocol_path: Path,
    protocol_audit: S2BigQueryFeasibilityProtocolAuditV2,
    protocol_audit_path: Path,
    prior_result: S2BigQueryFeasibilityResult,
    prior_audit: S2BigQueryFeasibilityAudit,
    gcloud_available: bool,
    bq_available: bool,
    active_auth_configured: bool,
    active_project_configured: bool,
    billing_boundary_request_count: int,
    sandbox_without_billing_verified: bool,
    access_token_request_count: int,
    metadata_attempts: tuple[S2MetadataAttempt, ...],
    dry_run_attempts: tuple[S2DryRunAttemptV2, ...],
) -> S2BigQueryFeasibilityResultV2:
    blockers = []
    if not gcloud_available:
        blockers.append("gcloud_command_unavailable")
    if not bq_available:
        blockers.append("bq_command_unavailable")
    if gcloud_available and not active_auth_configured:
        blockers.append("active_google_cloud_auth_unavailable")
    if active_auth_configured and not active_project_configured:
        blockers.append("active_google_cloud_project_unconfigured")
    if active_project_configured and not sandbox_without_billing_verified:
        blockers.append("sandbox_without_billing_not_verified")
    for attempt in metadata_attempts:
        if attempt.error_class != "NONE":
            blockers.append(
                f"authenticated_metadata_{attempt.target_id.lower()}_{attempt.error_class.lower()}"
            )
    for attempt in dry_run_attempts:
        if not attempt.succeeded:
            blockers.append(f"dry_run_{attempt.query_id.lower()}_{attempt.error_class.lower()}")
    metadata_passed = len(metadata_attempts) == 3 and all(
        item.error_class == "NONE" for item in metadata_attempts
    )
    dry_runs_passed = len(dry_run_attempts) == 2 and all(
        item.succeeded for item in dry_run_attempts
    )
    if not (gcloud_available and bq_available):
        decision = S2_FEASIBILITY_V2_BLOCK_CLIENT
    elif not active_auth_configured:
        decision = S2_FEASIBILITY_V2_BLOCK_AUTH
    elif not active_project_configured:
        decision = S2_FEASIBILITY_V2_BLOCK_PROJECT
    elif not sandbox_without_billing_verified:
        decision = S2_FEASIBILITY_V2_BLOCK_BILLING
    elif not metadata_passed:
        decision = S2_FEASIBILITY_V2_BLOCK_METADATA
    elif not dry_runs_passed:
        decision = S2_FEASIBILITY_V2_BLOCK_DRY_RUN
    else:
        decision = S2_FEASIBILITY_V2_PASS
    return build_hashed(
        S2BigQueryFeasibilityResultV2,
        "result_evidence_hash",
        {
            "generated_at": generated_at,
            "protocol_file_sha256": file_sha256(protocol_path),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_file_sha256": file_sha256(protocol_audit_path),
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "prior_result_evidence_hash": prior_result.result_evidence_hash,
            "prior_result_audit_evidence_hash": prior_audit.audit_evidence_hash,
            "runner_contract_hash": runner_contract_hash(),
            "gcloud_available": gcloud_available,
            "bq_available": bq_available,
            "active_auth_configured": active_auth_configured,
            "active_project_configured": active_project_configured,
            "billing_boundary_request_count": billing_boundary_request_count,
            "sandbox_without_billing_verified": sandbox_without_billing_verified,
            "access_token_request_count": access_token_request_count,
            "metadata_attempts": metadata_attempts,
            "dry_run_attempts": dry_run_attempts,
            "metadata_request_count": len(metadata_attempts),
            "dry_run_request_count": len(dry_run_attempts),
            "blockers": tuple(sorted(set(blockers))),
            "decision": decision,
            "next_authorization": (
                S2_FEASIBILITY_V2_NEXT
                if decision == S2_FEASIBILITY_V2_PASS
                else S2_FEASIBILITY_V2_RETRY
            ),
            "limitations": tuple(
                sorted(
                    (
                        "Account and project identifiers were used only in memory.",
                        "Credentials and access tokens were not persisted.",
                        "Dry-runs returned estimates but no query result rows.",
                        "No blockchain table row was requested or returned.",
                        "The preflight does not establish a profitable strategy.",
                        "The preflight grants no numeric-query or trading authority.",
                    )
                )
            ),
        },
    )


def validate_lineage(args):
    protocol = S2BigQueryFeasibilityProtocolV2.model_validate_json(args.protocol.read_text())
    protocol_audit = S2BigQueryFeasibilityProtocolAuditV2.model_validate_json(
        args.protocol_audit.read_text()
    )
    prior_result = S2BigQueryFeasibilityResult.model_validate_json(args.prior_result.read_text())
    prior_audit = S2BigQueryFeasibilityAudit.model_validate_json(args.prior_audit.read_text())
    if (
        file_sha256(args.protocol) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.prior_result_evidence_hash != prior_result.result_evidence_hash
        or protocol.prior_result_audit_evidence_hash != prior_audit.audit_evidence_hash
        or prior_result.result_evidence_hash != prior_audit.result_evidence_hash
    ):
        raise ValueError("S2 BigQuery feasibility v2 lineage changed")
    return protocol, protocol_audit, prior_result, prior_audit


def run(args) -> S2BigQueryFeasibilityResultV2:
    if args.output.exists():
        raise ValueError(f"S2 BigQuery feasibility result v2 exists: {args.output}")
    protocol, protocol_audit, prior_result, prior_audit = validate_lineage(args)
    gcloud_path = resolve_command("gcloud")
    bq_path = resolve_command("bq")
    auth = active_auth_available(gcloud_path)
    project = active_project(gcloud_path) if auth else None
    billing_count = 0
    no_billing = False
    token_count = 0
    token = None
    attempts = []
    pending_responses = []
    dry_runs = []
    if gcloud_path and bq_path and auth and project:
        billing_count, no_billing = verify_sandbox_without_billing(
            gcloud_path,
            project,
        )
    if no_billing and gcloud_path:
        token_count, token = access_token(gcloud_path)
    if token:
        for endpoint in protocol.metadata_endpoints:
            attempt, body = make_metadata_attempt(
                endpoint,
                token=token,
                requested_at=datetime.now(UTC),
                response_dir=args.response_dir,
            )
            attempts.append(attempt)
            if body is not None and attempt.response_path is not None:
                pending_responses.append((Path(attempt.response_path), body))
    metadata_passed = len(attempts) == 3 and all(item.error_class == "NONE" for item in attempts)
    if metadata_passed and bq_path and project:
        for spec in protocol.dry_run_specs:
            attempt = make_dry_run_attempt(
                bq_path,
                project=project,
                location=protocol.processing_location,
                spec=spec,
                requested_at=datetime.now(UTC),
            )
            dry_runs.append(attempt)
            if not attempt.succeeded:
                break
    result = build_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        protocol_path=args.protocol,
        protocol_audit=protocol_audit,
        protocol_audit_path=args.protocol_audit,
        prior_result=prior_result,
        prior_audit=prior_audit,
        gcloud_available=gcloud_path is not None,
        bq_available=bq_path is not None,
        active_auth_configured=auth,
        active_project_configured=project is not None,
        billing_boundary_request_count=billing_count,
        sandbox_without_billing_verified=no_billing,
        access_token_request_count=token_count,
        metadata_attempts=tuple(attempts),
        dry_run_attempts=tuple(dry_runs),
    )
    for path, body in pending_responses:
        write_response(path, body)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} metadata={result.metadata_request_count}/3 "
        f"dry_runs={result.dry_run_request_count}/2 identifiers=0 rows=0 "
        "values=0 returns=0 orders=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Run bounded S2 BigQuery v2.")
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--protocol-audit",
        type=Path,
        default=DEFAULT_PROTOCOL_AUDIT,
    )
    parser.add_argument("--prior-result", type=Path, default=DEFAULT_PRIOR_RESULT)
    parser.add_argument("--prior-audit", type=Path, default=DEFAULT_PRIOR_AUDIT)
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
