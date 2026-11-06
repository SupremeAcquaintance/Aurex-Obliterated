from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_source_feasibility import (  # noqa: E402
    S3_FEASIBILITY_PASS,
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    S3MetadataAttempt,
    build_hashed,
)
from aurex.backtest_engine.s3_cftc_source_feasibility_transport import (  # noqa: E402
    S3CftcMetadataTransportAmendmentAuditV2,
    S3CftcMetadataTransportAmendmentV2,
    S3CftcSourceFeasibilityResultAuditV2,
    S3CftcSourceFeasibilityResultV2,
    S3CftcSourceTransportFailureAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s3_cftc_source_feasibility import (  # noqa: E402
    file_sha256,
    normalized_html_text,
)
from scripts.run_s3_cftc_source_feasibility_v2 import (  # noqa: E402
    build_result,
    runner_contract_hash,
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
DEFAULT_RESULT = Path("data/evidence/s3_cftc_source_feasibility_result_v2.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/s3_cftc_source_feasibility_result_audit_v2.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s3_cftc_source_feasibility_transport.py"
)
SCRIPT_PATH = Path("scripts/audit_s3_cftc_source_feasibility_result_v2.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct_attempts(
    protocol: S3CftcSourceFeasibilityProtocol,
    result: S3CftcSourceFeasibilityResultV2,
) -> tuple[S3MetadataAttempt, ...]:
    specs = {item.endpoint_id: item for item in protocol.metadata_endpoints}
    attempts = []
    for stored in result.metadata_attempts:
        if stored.response_path is None or stored.response_sha256 is None:
            raise ValueError("S3 v2 metadata response artifact is missing")
        path = Path(stored.response_path)
        body = path.read_bytes()
        if len(body) != stored.response_bytes or file_sha256(path) != stored.response_sha256:
            raise ValueError("S3 v2 metadata response artifact changed")
        text = normalized_html_text(body)
        matched = tuple(
            sorted(
                token
                for token in specs[stored.endpoint_id].required_text_tokens
                if token in text
            )
        )
        attempts.append(stored.model_copy(update={"matched_text_tokens": matched}))
    return tuple(attempts)


def build_audit(args, *, audited_at: datetime) -> S3CftcSourceFeasibilityResultAuditV2:
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
    result = S3CftcSourceFeasibilityResultV2.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        result.runner_contract_hash != runner_contract_hash()
        or result.prior_result_file_sha256 != file_sha256(args.prior_result)
        or result.prior_result_evidence_hash != prior.result_evidence_hash
        or result.failure_audit_evidence_hash != failure.audit_evidence_hash
        or result.transport_amendment_file_sha256 != file_sha256(args.amendment)
        or result.transport_amendment_evidence_hash != amendment.amendment_evidence_hash
        or result.transport_amendment_audit_evidence_hash
        != amendment_audit.audit_evidence_hash
    ):
        raise ValueError("S3 feasibility v2 result lineage changed")
    attempts = reconstruct_attempts(protocol, result)
    reconstructed = build_result(
        generated_at=result.generated_at,
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
        attempts=attempts,
    )
    if reconstructed != result:
        raise ValueError("S3 feasibility v2 result differs from reconstruction")
    passed = result.decision == S3_FEASIBILITY_PASS
    return build_hashed(
        S3CftcSourceFeasibilityResultAuditV2,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "result_file_sha256": file_sha256(args.result),
            "result_evidence_hash": result.result_evidence_hash,
            "protocol_file_sha256": result.protocol_file_sha256,
            "protocol_evidence_hash": result.protocol_evidence_hash,
            "protocol_audit_evidence_hash": result.protocol_audit_evidence_hash,
            "runner_contract_hash": result.runner_contract_hash,
            "auditor_contract_hash": auditor_contract_hash(),
            "response_artifact_count": 3,
            "passed_gate_count": result.passed_gate_count,
            "failed_gate_count": result.failed_gate_count,
            "decision": (
                "CONFIRM_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PASSED"
                if passed
                else "CONFIRM_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3"
            ),
            "lineage_next_authorization": result.next_authorization,
            "prior_result_evidence_hash": prior.result_evidence_hash,
            "failure_audit_evidence_hash": failure.audit_evidence_hash,
            "transport_amendment_evidence_hash": amendment.amendment_evidence_hash,
            "transport_amendment_audit_evidence_hash": amendment_audit.audit_evidence_hash,
        },
    )


def write_atomic(path: Path, audit: S3CftcSourceFeasibilityResultAuditV2) -> None:
    if path.exists():
        raise ValueError(f"S3 feasibility v2 audit exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 feasibility v2 audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S3CftcSourceFeasibilityResultAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("S3 feasibility v2 audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Audit S3 CFTC feasibility v2.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--prior-result", type=Path, default=DEFAULT_PRIOR_RESULT)
    parser.add_argument("--failure-audit", type=Path, default=DEFAULT_FAILURE_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.output.exists():
            stored = S3CftcSourceFeasibilityResultAuditV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(args, audited_at=stored.audited_at)
            if stored != expected:
                raise ValueError("Stored S3 feasibility v2 audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(args, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"decision={audit.decision} cftc_values=0 market_values=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
