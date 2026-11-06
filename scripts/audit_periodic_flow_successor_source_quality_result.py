from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    source_contract_hash,
)
from aurex.backtest_engine.periodic_flow_successor_source_quality import (  # noqa: E402
    PeriodicFlowSuccessorSourceQualityResult,
    PeriodicFlowSuccessorSourceQualityResultAudit,
    audit_hash,
    build_successor_source_quality_result_audit,
)
from scripts.audit_periodic_flow_successor_source_quality_protocol import (  # noqa: E402
    DEFAULT_AUDIT_OUTPUT as DEFAULT_PROTOCOL_AUDIT,
)
from scripts.freeze_periodic_flow_successor_source_quality import (  # noqa: E402
    DEFAULT_JAM_FULL_AUDIT,
    DEFAULT_JAM_FULL_RESULT,
    DEFAULT_JAM_REMEDIATION_AUDIT,
    DEFAULT_JAM_REMEDIATION_RESULT,
    DEFAULT_TERMINAL_AUDIT,
    DEFAULT_V1_PROTOCOL,
)
from scripts.freeze_periodic_flow_successor_source_quality import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.run_periodic_flow_successor_source_quality_census import (  # noqa: E402
    DEFAULT_OUTPUT,
    authoritative_result,
    file_sha256,
)

DEFAULT_AUDIT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_source_quality_result_audit_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_source_quality.py"
)
RUN_SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_source_quality_census.py")
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_successor_source_quality_result.py"
)


def auditor_contract_hash() -> str:
    return source_contract_hash(
        PROJECT_ROOT, (MODULE_PATH, RUN_SCRIPT_PATH, AUDIT_SCRIPT_PATH)
    )


def authoritative_audit(
    *, args: argparse.Namespace, audited_at: datetime
) -> PeriodicFlowSuccessorSourceQualityResultAudit:
    result = PeriodicFlowSuccessorSourceQualityResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    census_args = argparse.Namespace()
    for name in (
        "terminal_audit",
        "v1_protocol",
        "jam_full_result",
        "jam_full_audit",
        "jam_remediation_result",
        "jam_remediation_audit",
        "protocol",
        "protocol_audit",
    ):
        setattr(census_args, name, getattr(args, name))
    expected = authoritative_result(args=census_args, generated_at=result.generated_at)
    if result != expected or not audit_hash(result, "result_evidence_hash"):
        raise ValueError("Q1 successor source-quality result did not reconstruct")
    return build_successor_source_quality_result_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        auditor_contract_hash=auditor_contract_hash(),
        known_eligible_month_count=result.known_eligible_month_count,
        known_ineligible_month_count=result.known_ineligible_month_count,
    )


def write_audit(path: Path, audit: PeriodicFlowSuccessorSourceQualityResultAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor result audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor result audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 successor source-quality result."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--terminal-audit", type=Path, default=DEFAULT_TERMINAL_AUDIT)
    parser.add_argument("--v1-protocol", type=Path, default=DEFAULT_V1_PROTOCOL)
    parser.add_argument("--jam-full-result", type=Path, default=DEFAULT_JAM_FULL_RESULT)
    parser.add_argument("--jam-full-audit", type=Path, default=DEFAULT_JAM_FULL_AUDIT)
    parser.add_argument(
        "--jam-remediation-result", type=Path, default=DEFAULT_JAM_REMEDIATION_RESULT
    )
    parser.add_argument(
        "--jam-remediation-audit", type=Path, default=DEFAULT_JAM_REMEDIATION_AUDIT
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorSourceQualityResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_hash(stored, "audit_evidence_hash"):
                raise ValueError("Stored Q1 successor result audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                f"eligible={stored.known_eligible_month_count} "
                f"excluded={stored.known_ineligible_month_count} "
                "requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"eligible={audit.known_eligible_month_count} "
            f"excluded={audit.known_ineligible_month_count} "
            "requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
