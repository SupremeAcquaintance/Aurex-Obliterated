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
    audit_s3_feasibility_result,
    build_hashed,
)
from aurex.backtest_engine.s3_cftc_source_feasibility_transport import (  # noqa: E402
    S3CftcSourceTransportFailureAudit,
    audit_transport_failure,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s3_cftc_source_feasibility import (  # noqa: E402
    file_sha256,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
DEFAULT_RESULT = Path("data/evidence/s3_cftc_source_feasibility_result_v1.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/s3_cftc_source_transport_failure_audit_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s3_cftc_source_feasibility_transport.py"
)
SCRIPT_PATH = Path("scripts/audit_s3_cftc_source_transport_failure.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_audit(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S3CftcSourceTransportFailureAudit:
    protocol = S3CftcSourceFeasibilityProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    result = S3CftcSourceFeasibilityResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    transport_failure = (
        len(result.metadata_attempts) == 3
        and all(
            attempt.error_class == "NETWORK_ERROR"
            and attempt.http_status == 0
            and attempt.response_bytes == 0
            and attempt.response_sha256 is None
            and attempt.response_path is None
            and attempt.request_succeeded is False
            and attempt.target_position_values_read == 0
            for attempt in result.metadata_attempts
        )
    )
    if (
        not audit_s3_feasibility_result(result)
        or result.protocol_file_sha256 != file_sha256(protocol_path)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_audit_file_sha256 != file_sha256(protocol_audit_path)
        or result.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or not transport_failure
        or result.cftc_target_position_values_read != 0
        or result.btc_market_values_read != 0
        or result.returns_calculated != 0
        or result.orders_submitted != 0
    ):
        raise ValueError("S3 result is not an exact zero-response transport failure")
    return build_hashed(
        S3CftcSourceTransportFailureAudit,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "protocol_file_sha256": file_sha256(protocol_path),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "result_file_sha256": file_sha256(result_path),
            "result_evidence_hash": result.result_evidence_hash,
            "runner_contract_hash": result.runner_contract_hash,
            "auditor_contract_hash": auditor_contract_hash(),
        },
    )


def write_atomic(path: Path, audit: S3CftcSourceTransportFailureAudit) -> None:
    if path.exists():
        raise ValueError(f"S3 transport-failure audit exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 transport-failure transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S3CftcSourceTransportFailureAudit.model_validate_json(serialized) != audit:
        raise ValueError("S3 transport-failure audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Audit the S3 zero-response failure.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.output.exists():
            stored = S3CftcSourceTransportFailureAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_transport_failure(stored):
                raise ValueError("Stored S3 transport-failure audit changed")
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
            "responses=0 cftc_values=0 market_values=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
