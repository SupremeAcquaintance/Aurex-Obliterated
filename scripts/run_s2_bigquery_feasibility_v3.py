from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed  # noqa: E402
from aurex.backtest_engine.s2_bigquery_feasibility_v2 import (  # noqa: E402
    S2BigQueryFeasibilityAuditV2,
    S2BigQueryFeasibilityResultV2,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (  # noqa: E402
    S2_FEASIBILITY_V3_BLOCK_AUTH,
    S2_FEASIBILITY_V3_BLOCK_BILLING,
    S2_FEASIBILITY_V3_BLOCK_CLIENT,
    S2_FEASIBILITY_V3_BLOCK_DRY_RUN,
    S2_FEASIBILITY_V3_BLOCK_PROJECT,
    S2_FEASIBILITY_V3_BLOCK_TOKEN,
    S2_FEASIBILITY_V3_NEXT,
    S2_FEASIBILITY_V3_PASS,
    S2_FEASIBILITY_V3_RETRY,
    S2BigQueryFeasibilityProtocolAuditV3,
    S2BigQueryFeasibilityProtocolV3,
    S2BigQueryFeasibilityResultV3,
    S2RestDryRunAttemptV3,
    S2RestErrorClass,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s2_bigquery_feasibility_v2 import (  # noqa: E402
    access_token,
    active_auth_available,
    active_project,
    resolve_command,
    verify_sandbox_without_billing,
)

DEFAULT_PROTOCOL = Path("data/evidence/s2_bigquery_feasibility_protocol_v3.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s2_bigquery_feasibility_protocol_audit_v3.json")
DEFAULT_PRIOR_RESULT = Path("data/evidence/s2_bigquery_feasibility_result_v2.json")
DEFAULT_PRIOR_AUDIT = Path("data/evidence/s2_bigquery_feasibility_audit_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_bigquery_feasibility_result_v3.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_bigquery_feasibility_v3.py")
V2_RUNNER_PATH = Path("scripts/run_s2_bigquery_feasibility_v2.py")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def runner_contract_hash() -> str:
    path = Path(__file__).resolve()
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(MODULE_PATH),
            "v2_helper_path": V2_RUNNER_PATH.as_posix(),
            "v2_helper_sha256": file_sha256(V2_RUNNER_PATH),
            "runner_path": path.relative_to(PROJECT_ROOT).as_posix(),
            "runner_sha256": file_sha256(path),
        }
    )


def error_reasons(payload: object) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    entries = []
    error = payload.get("error")
    status = payload.get("status")
    if isinstance(error, dict) and isinstance(error.get("errors"), list):
        entries.extend(error["errors"])
    if isinstance(status, dict):
        if isinstance(status.get("errors"), list):
            entries.extend(status["errors"])
        if isinstance(status.get("errorResult"), dict):
            entries.append(status["errorResult"])
    return {
        str(item.get("reason", "")).strip().lower()
        for item in entries
        if isinstance(item, dict) and item.get("reason")
    }


def classify_rest_error(status: int, payload: object) -> S2RestErrorClass:
    reasons = error_reasons(payload)
    if status == 401 or reasons & {"autherror", "invalidcredentials"}:
        return "AUTH_ERROR"
    if reasons & {"accessnotconfigured", "servicedisabled"}:
        return "API_DISABLED"
    if reasons & {"billingnotenabled", "billingtierlimitexceeded"}:
        return "BILLING_ERROR"
    if reasons & {"quotaexceeded", "ratelimitexceeded", "resourcesexceeded"}:
        return "QUOTA_ERROR"
    if status == 403 or reasons & {"accessdenied", "permissiondenied", "forbidden"}:
        return "PERMISSION_ERROR"
    if status == 400 or "invalidquery" in reasons:
        return "INVALID_QUERY"
    if status == 404 or "notfound" in reasons:
        return "NOT_FOUND"
    return "API_ERROR"


def response_total_bytes(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    statistics = payload.get("statistics")
    if not isinstance(statistics, dict):
        return None
    value = statistics.get("totalBytesProcessed")
    if value is None and isinstance(statistics.get("query"), dict):
        value = statistics["query"].get("totalBytesProcessed")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def rest_dry_run(
    *,
    endpoint_template: str,
    token: str,
    project: str,
    location: str,
    spec,
    requested_at: datetime,
    timeout: int,
    maximum: int,
) -> S2RestDryRunAttemptV3:
    endpoint = endpoint_template.format(project=quote(project, safe=""))
    body = json.dumps(
        {
            "configuration": {
                "dryRun": True,
                "query": {
                    "query": spec.google_sql,
                    "useLegacySql": False,
                },
            },
            "jobReference": {"location": location, "projectId": project},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Aurex-S2-Feasibility/3",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            response_body = response.read(maximum + 1)
            status = int(response.status)
    except HTTPError as exc:
        response_body = exc.read(maximum + 1)
        status = int(exc.code)
    except TimeoutError:
        return S2RestDryRunAttemptV3(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=requested_at,
            http_status=0,
            response_bytes=0,
            succeeded=False,
            error_class="TIMEOUT",
        )
    except (URLError, OSError):
        return S2RestDryRunAttemptV3(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=requested_at,
            http_status=0,
            response_bytes=0,
            succeeded=False,
            error_class="NETWORK_ERROR",
        )
    if len(response_body) > maximum:
        return S2RestDryRunAttemptV3(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=requested_at,
            http_status=status,
            response_bytes=maximum,
            succeeded=False,
            error_class="INVALID_RESPONSE",
        )
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        return S2RestDryRunAttemptV3(
            query_id=spec.query_id,
            query_sha256=spec.query_sha256,
            requested_at=requested_at,
            http_status=status,
            response_bytes=len(response_body),
            succeeded=False,
            error_class="INVALID_RESPONSE",
        )
    reasons = error_reasons(payload)
    processed = response_total_bytes(payload)
    succeeded = status == 200 and not reasons and processed is not None
    return S2RestDryRunAttemptV3(
        query_id=spec.query_id,
        query_sha256=spec.query_sha256,
        requested_at=requested_at,
        http_status=status,
        response_bytes=len(response_body),
        succeeded=succeeded,
        total_bytes_processed=processed if succeeded else None,
        error_class="NONE" if succeeded else classify_rest_error(status, payload),
    )


def build_result(
    *,
    generated_at: datetime,
    protocol: S2BigQueryFeasibilityProtocolV3,
    protocol_path: Path,
    protocol_audit: S2BigQueryFeasibilityProtocolAuditV3,
    protocol_audit_path: Path,
    prior_result: S2BigQueryFeasibilityResultV2,
    prior_audit: S2BigQueryFeasibilityAuditV2,
    gcloud_available: bool,
    active_auth_configured: bool,
    active_project_configured: bool,
    billing_boundary_request_count: int,
    sandbox_without_billing_verified: bool,
    access_token_request_count: int,
    access_token_available: bool,
    attempts: tuple[S2RestDryRunAttemptV3, ...],
) -> S2BigQueryFeasibilityResultV3:
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
    for attempt in attempts:
        if not attempt.succeeded:
            blockers.append(
                f"rest_dry_run_{attempt.query_id.lower()}_{attempt.error_class.lower()}"
            )
    passed = len(attempts) == 2 and all(item.succeeded for item in attempts)
    if not gcloud_available:
        decision = S2_FEASIBILITY_V3_BLOCK_CLIENT
    elif not active_auth_configured:
        decision = S2_FEASIBILITY_V3_BLOCK_AUTH
    elif not active_project_configured:
        decision = S2_FEASIBILITY_V3_BLOCK_PROJECT
    elif not sandbox_without_billing_verified:
        decision = S2_FEASIBILITY_V3_BLOCK_BILLING
    elif not access_token_available:
        decision = S2_FEASIBILITY_V3_BLOCK_TOKEN
    elif not passed:
        decision = S2_FEASIBILITY_V3_BLOCK_DRY_RUN
    else:
        decision = S2_FEASIBILITY_V3_PASS
    return build_hashed(
        S2BigQueryFeasibilityResultV3,
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
            "active_auth_configured": active_auth_configured,
            "active_project_configured": active_project_configured,
            "billing_boundary_request_count": billing_boundary_request_count,
            "sandbox_without_billing_verified": sandbox_without_billing_verified,
            "access_token_request_count": access_token_request_count,
            "access_token_available": access_token_available,
            "rest_dry_run_attempts": attempts,
            "rest_dry_run_request_count": len(attempts),
            "blockers": tuple(sorted(set(blockers))),
            "decision": decision,
            "next_authorization": (
                S2_FEASIBILITY_V3_NEXT
                if decision == S2_FEASIBILITY_V3_PASS
                else S2_FEASIBILITY_V3_RETRY
            ),
            "limitations": protocol.limitations,
        },
    )


def validate_lineage(args):
    protocol = S2BigQueryFeasibilityProtocolV3.model_validate_json(args.protocol.read_text())
    protocol_audit = S2BigQueryFeasibilityProtocolAuditV3.model_validate_json(
        args.protocol_audit.read_text()
    )
    prior_result = S2BigQueryFeasibilityResultV2.model_validate_json(args.prior_result.read_text())
    prior_audit = S2BigQueryFeasibilityAuditV2.model_validate_json(args.prior_audit.read_text())
    if (
        file_sha256(args.protocol) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.prior_result_evidence_hash != prior_result.result_evidence_hash
        or protocol.prior_result_audit_evidence_hash != prior_audit.audit_evidence_hash
        or prior_result.result_evidence_hash != prior_audit.result_evidence_hash
    ):
        raise ValueError("S2 BigQuery feasibility v3 lineage changed")
    for binding in protocol.source_bindings:
        path = PROJECT_ROOT / binding.path
        if not path.is_file() or file_sha256(path) != binding.file_sha256:
            raise ValueError("S2 BigQuery feasibility v3 source binding changed")
    return protocol, protocol_audit, prior_result, prior_audit


def run(args) -> S2BigQueryFeasibilityResultV3:
    if args.output.exists():
        raise ValueError(f"S2 BigQuery feasibility result v3 exists: {args.output}")
    protocol, protocol_audit, prior_result, prior_audit = validate_lineage(args)
    gcloud_path = resolve_command("gcloud")
    auth = active_auth_available(gcloud_path)
    project = active_project(gcloud_path) if auth else None
    billing_count = 0
    no_billing = False
    token_count = 0
    token = None
    attempts = []
    if gcloud_path and auth and project:
        billing_count, no_billing = verify_sandbox_without_billing(gcloud_path, project)
    if no_billing and gcloud_path:
        token_count, token = access_token(gcloud_path)
    if token and project:
        for spec in protocol.dry_run_specs:
            attempt = rest_dry_run(
                endpoint_template=protocol.jobs_endpoint_template,
                token=token,
                project=project,
                location=protocol.processing_location,
                spec=spec,
                requested_at=datetime.now(UTC),
                timeout=protocol.request_timeout_seconds,
                maximum=protocol.maximum_response_bytes_each,
            )
            attempts.append(attempt)
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
        active_auth_configured=auth,
        active_project_configured=project is not None,
        billing_boundary_request_count=billing_count,
        sandbox_without_billing_verified=no_billing,
        access_token_request_count=token_count,
        access_token_available=token is not None,
        attempts=tuple(attempts),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} rest_dry_runs={result.rest_dry_run_request_count}/2 "
        "identifiers=0 responses=0 rows=0 values=0 returns=0 orders=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Run bounded S2 BigQuery REST v3.")
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--prior-result", type=Path, default=DEFAULT_PRIOR_RESULT)
    parser.add_argument("--prior-audit", type=Path, default=DEFAULT_PRIOR_AUDIT)
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
