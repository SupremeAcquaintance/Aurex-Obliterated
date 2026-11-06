from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_source_feasibility import (  # noqa: E402
    S3_FEASIBILITY_NONE,
    S3_FEASIBILITY_PASS,
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    S3CftcSourceFeasibilityResultAudit,
    S3MetadataAttempt,
    audit_s3_feasibility_result,
    audit_s3_feasibility_result_audit,
    build_hashed,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s3_cftc_source_feasibility import (  # noqa: E402
    build_result,
    file_sha256,
    normalized_html_text,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
DEFAULT_RESULT = Path("data/evidence/s3_cftc_source_feasibility_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s3_cftc_source_feasibility_result_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s3_cftc_source_feasibility_result.py")
MODULE_PATH = Path("src/aurex/backtest_engine/s3_cftc_source_feasibility.py")


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
    stored: S3CftcSourceFeasibilityResult,
) -> tuple[S3MetadataAttempt, ...]:
    specs = {item.endpoint_id: item for item in protocol.metadata_endpoints}
    reconstructed = []
    for attempt in stored.metadata_attempts:
        if attempt.response_path is None or attempt.response_sha256 is None:
            raise ValueError("S3 metadata response artifact is missing")
        path = Path(attempt.response_path)
        body = path.read_bytes()
        if (
            len(body) != attempt.response_bytes
            or file_sha256(path) != attempt.response_sha256
        ):
            raise ValueError("S3 metadata response artifact changed")
        text = normalized_html_text(body)
        spec = specs[attempt.endpoint_id]
        matched = tuple(
            sorted(token for token in spec.required_text_tokens if token in text)
        )
        reconstructed.append(
            attempt.model_copy(update={"matched_text_tokens": matched})
        )
    return tuple(reconstructed)


def build_audit(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S3CftcSourceFeasibilityResultAudit:
    protocol = S3CftcSourceFeasibilityProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    result = S3CftcSourceFeasibilityResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_s3_feasibility_result(result)
        or result.protocol_file_sha256 != file_sha256(protocol_path)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_audit_file_sha256 != file_sha256(protocol_audit_path)
        or result.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("S3 feasibility result lineage changed")
    attempts = reconstruct_attempts(protocol, result)
    reconstructed = build_result(
        generated_at=result.generated_at,
        protocol=protocol,
        protocol_path=protocol_path,
        protocol_audit=protocol_audit,
        protocol_audit_path=protocol_audit_path,
        attempts=attempts,
    )
    if reconstructed != result:
        raise ValueError("S3 feasibility result differs from reconstruction")
    passed = result.decision == S3_FEASIBILITY_PASS
    return build_hashed(
        S3CftcSourceFeasibilityResultAudit,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "result_file_sha256": file_sha256(result_path),
            "result_evidence_hash": result.result_evidence_hash,
            "protocol_file_sha256": result.protocol_file_sha256,
            "protocol_evidence_hash": result.protocol_evidence_hash,
            "protocol_audit_evidence_hash": result.protocol_audit_evidence_hash,
            "runner_contract_hash": result.runner_contract_hash,
            "auditor_contract_hash": auditor_contract_hash(),
            "passed_gate_count": result.passed_gate_count,
            "failed_gate_count": result.failed_gate_count,
            "decision": (
                "CONFIRM_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PASSED"
                if passed
                else "CONFIRM_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3"
            ),
            "lineage_next_authorization": (
                result.next_authorization if passed else S3_FEASIBILITY_NONE
            ),
        },
    )


def write_atomic(path: Path, audit: S3CftcSourceFeasibilityResultAudit) -> None:
    if path.exists():
        raise ValueError(f"S3 feasibility result audit exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 result-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S3CftcSourceFeasibilityResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S3 feasibility result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Audit the S3 feasibility result.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.output.exists():
            stored = S3CftcSourceFeasibilityResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_s3_feasibility_result_audit(stored):
                raise ValueError("Stored S3 feasibility result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            result_path=args.result,
            audited_at=datetime.now(UTC),
        )
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
