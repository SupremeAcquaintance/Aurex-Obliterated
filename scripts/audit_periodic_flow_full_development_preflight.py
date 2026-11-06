from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_preflight import (  # noqa: E402
    PeriodicFlowAcquisitionPreflightAudit,
    PeriodicFlowAcquisitionPreflightResult,
    audit_preflight_audit,
    audit_preflight_result,
    build_preflight_audit,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    source_contract_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)
from scripts.run_periodic_flow_full_development_preflight import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    MODULE_PATH,
    SCRIPT_PATH,
    authoritative_result,
)
from scripts.run_periodic_flow_full_development_preflight import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RESULT,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_full_development_preflight_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path("scripts/audit_periodic_flow_full_development_preflight.py")


def auditor_contract_hash() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (MODULE_PATH, SCRIPT_PATH, AUDIT_SCRIPT_PATH),
    )


def authoritative_audit(
    *,
    args: argparse.Namespace,
    audited_at: datetime,
) -> PeriodicFlowAcquisitionPreflightAudit:
    result = PeriodicFlowAcquisitionPreflightResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    reconstructed = authoritative_result(
        args=args,
        generated_at=result.generated_at,
        free_disk_bytes=result.free_disk_bytes,
        emit_progress=False,
    )
    if reconstructed != result or not audit_preflight_result(result):
        raise ValueError("Q1 preflight result did not reconstruct")
    return build_preflight_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        execution_contract_evidence_hash=result.execution_contract_evidence_hash,
        runner_source_hash=result.runner_source_hash,
        auditor_contract_hash=auditor_contract_hash(),
        reuse_manifest_hash=result.reuse_manifest_hash,
        decision=result.decision,
    )


def write_audit(path: Path, audit: PeriodicFlowAcquisitionPreflightAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 preflight audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 preflight audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowAcquisitionPreflightAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 preflight audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 acquisition preflight result."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowAcquisitionPreflightAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_preflight_audit(stored):
                raise ValueError("Stored Q1 preflight audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                f"decision={stored.decision} requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"decision={audit.decision} requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
