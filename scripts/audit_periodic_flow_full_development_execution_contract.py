from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    PeriodicFlowExecutionContract,
    PeriodicFlowExecutionContractAudit,
    audit_execution_contract,
    audit_execution_contract_audit,
    build_execution_contract_audit,
    source_contract_hash,
)
from scripts.freeze_periodic_flow_full_development_execution_contract import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CONTRACT,
)
from scripts.freeze_periodic_flow_full_development_execution_contract import (  # noqa: E402
    MODULE_PATH,
    SCRIPT_PATH,
    authoritative_contract,
    file_sha256,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_full_development_execution_contract_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_full_development_execution_contract.py"
)


def auditor_contract_hash() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (MODULE_PATH, SCRIPT_PATH, AUDIT_SCRIPT_PATH),
    )


def authoritative_audit(
    *,
    contract_path: Path,
    audited_at: datetime,
) -> PeriodicFlowExecutionContractAudit:
    contract = PeriodicFlowExecutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(frozen_at=contract.frozen_at)
    if contract != expected or not audit_execution_contract(contract):
        raise ValueError("Q1 execution contract did not reconstruct")
    return build_execution_contract_audit(
        audited_at=audited_at,
        contract_file_sha256=file_sha256(contract_path),
        contract_evidence_hash=contract.contract_evidence_hash,
        parent_protocol_evidence_hash=contract.parent_protocol_evidence_hash,
        runner_source_hash=contract.runner_source_hash,
        auditor_contract_hash=auditor_contract_hash(),
    )


def write_audit(path: Path, audit: PeriodicFlowExecutionContractAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite execution-contract audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale execution-contract audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowExecutionContractAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 execution-contract audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 full-development execution addendum."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowExecutionContractAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(
                contract_path=args.contract,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_execution_contract_audit(stored):
                raise ValueError("Stored Q1 execution-contract audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                "requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(
            contract_path=args.contract,
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
