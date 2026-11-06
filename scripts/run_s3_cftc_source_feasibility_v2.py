from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_source_feasibility import (  # noqa: E402
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    build_hashed,
)
from aurex.backtest_engine.s3_cftc_source_feasibility_transport import (  # noqa: E402
    S3_TRANSPORT_RUN_AUTHORIZATION,
    S3CftcMetadataTransportAmendmentAuditV2,
    S3CftcMetadataTransportAmendmentV2,
    S3CftcSourceFeasibilityResultV2,
    S3CftcSourceTransportFailureAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s3_cftc_source_feasibility import (  # noqa: E402
    build_result as build_base_result,
)
from scripts.run_s3_cftc_source_feasibility import (  # noqa: E402
    file_sha256,
    make_attempt,
    write_atomic,
)

DEFAULT_PROTOCOL = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
DEFAULT_PRIOR_RESULT = Path(
    "data/evidence/s3_cftc_source_feasibility_result_v1.json"
)
DEFAULT_FAILURE_AUDIT = Path(
    "data/evidence/s3_cftc_source_transport_failure_audit_v1.json"
)
DEFAULT_AMENDMENT = Path(
    "data/evidence/s3_cftc_metadata_transport_amendment_v2.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/s3_cftc_metadata_transport_amendment_audit_v2.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s3_cftc_source_feasibility_result_v2.json")
DEFAULT_RESPONSE_DIR = Path("data/evidence/s3_cftc_metadata_v2")


def runner_contract_hash() -> str:
    path = Path(__file__).resolve()
    return universe_evidence_hash(
        {
            "runner_path": path.relative_to(PROJECT_ROOT).as_posix(),
            "runner_sha256": file_sha256(path),
        }
    )


def build_result(
    *,
    generated_at: datetime,
    protocol: S3CftcSourceFeasibilityProtocol,
    protocol_path: Path,
    protocol_audit: S3CftcSourceFeasibilityProtocolAudit,
    protocol_audit_path: Path,
    prior: S3CftcSourceFeasibilityResult,
    prior_path: Path,
    failure: S3CftcSourceTransportFailureAudit,
    amendment: S3CftcMetadataTransportAmendmentV2,
    amendment_path: Path,
    amendment_audit: S3CftcMetadataTransportAmendmentAuditV2,
    attempts,
) -> S3CftcSourceFeasibilityResultV2:
    base = build_base_result(
        generated_at=generated_at,
        protocol=protocol,
        protocol_path=protocol_path,
        protocol_audit=protocol_audit,
        protocol_audit_path=protocol_audit_path,
        attempts=attempts,
    )
    excluded = {"schema_version", "result_id", "result_evidence_hash"}
    values = {
        field: getattr(base, field)
        for field in type(base).model_fields
        if field not in excluded
    }
    values.update(
        {
            "runner_contract_hash": runner_contract_hash(),
            "prior_result_file_sha256": file_sha256(prior_path),
            "prior_result_evidence_hash": prior.result_evidence_hash,
            "failure_audit_evidence_hash": failure.audit_evidence_hash,
            "transport_amendment_file_sha256": file_sha256(amendment_path),
            "transport_amendment_evidence_hash": amendment.amendment_evidence_hash,
            "transport_amendment_audit_evidence_hash": amendment_audit.audit_evidence_hash,
        }
    )
    return build_hashed(
        S3CftcSourceFeasibilityResultV2,
        "result_evidence_hash",
        values,
    )


def run(args) -> S3CftcSourceFeasibilityResultV2:
    if args.output.exists():
        raise ValueError(f"S3 feasibility v2 result exists: {args.output}")
    protocol = S3CftcSourceFeasibilityProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    prior = S3CftcSourceFeasibilityResult.model_validate_json(
        args.prior_result.read_text(encoding="utf-8")
    )
    failure = S3CftcSourceTransportFailureAudit.model_validate_json(
        args.failure_audit.read_text(encoding="utf-8")
    )
    amendment = S3CftcMetadataTransportAmendmentV2.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = S3CftcMetadataTransportAmendmentAuditV2.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or prior.protocol_evidence_hash != protocol.protocol_evidence_hash
        or failure.result_evidence_hash != prior.result_evidence_hash
        or amendment.protocol_evidence_hash != protocol.protocol_evidence_hash
        or amendment.prior_result_evidence_hash != prior.result_evidence_hash
        or amendment.failure_audit_evidence_hash != failure.audit_evidence_hash
        or amendment_audit.amendment_evidence_hash != amendment.amendment_evidence_hash
        or amendment.next_authorization != S3_TRANSPORT_RUN_AUTHORIZATION
        or amendment.protocol_urls_and_tokens_unchanged is not True
        or amendment.protocol_gates_unchanged is not True
    ):
        raise ValueError("S3 feasibility v2 lineage changed")
    expected_paths = tuple(
        args.response_dir / f"{item.endpoint_id.lower()}.html"
        for item in protocol.metadata_endpoints
    )
    if any(path.exists() for path in expected_paths):
        raise ValueError("S3 feasibility v2 response artifact already exists")

    attempts = []
    pending_responses = []
    for endpoint in protocol.metadata_endpoints:
        attempt, body = make_attempt(
            endpoint,
            requested_at=datetime.now(UTC),
            response_dir=args.response_dir,
            timeout=protocol.request_timeout_seconds,
            maximum_bytes=protocol.maximum_response_bytes_each,
        )
        attempts.append(attempt)
        if body is not None and attempt.response_path is not None:
            pending_responses.append((Path(attempt.response_path), body))
    if len(pending_responses) != 3 or not all(
        attempt.request_succeeded for attempt in attempts
    ):
        raise ValueError(
            "S3 transport v2 did not receive all three responses; no v2 result was written"
        )
    result = build_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        protocol_path=args.protocol,
        protocol_audit=protocol_audit,
        protocol_audit_path=args.protocol_audit,
        prior=prior,
        prior_path=args.prior_result,
        failure=failure,
        amendment=amendment,
        amendment_path=args.amendment,
        amendment_audit=amendment_audit,
        attempts=tuple(attempts),
    )
    for path, body in pending_responses:
        write_atomic(path, body)
    write_atomic(
        args.output,
        (result.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"pass={result.passed_gate_count} fail={result.failed_gate_count} "
        f"decision={result.decision} cftc_values=0 market_values=0 orders=0"
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Run S3 CFTC metadata transport v2.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--prior-result", type=Path, default=DEFAULT_PRIOR_RESULT)
    parser.add_argument("--failure-audit", type=Path, default=DEFAULT_FAILURE_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
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
