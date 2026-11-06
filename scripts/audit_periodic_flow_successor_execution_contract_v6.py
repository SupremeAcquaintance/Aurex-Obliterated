from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    PeriodicFlowSuccessorExecutionContractAuditV6,
    PeriodicFlowSuccessorExecutionContractV6,
    audit_hash,
    build_execution_contract_audit_v6,
)
from scripts.freeze_periodic_flow_successor_execution_contract_v6 import (  # noqa: E402
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_OUTPUT,
    authoritative_contract,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    source_contract_hash,
)
from scripts.run_periodic_flow_successor_acquisition_v6 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_CHECKPOINT,
    DEFAULT_RESULT,
    DEFAULT_V5_CHECKPOINT,
    DEFAULT_V5_RESULT,
    DEFAULT_V5_TERMINAL_AUDIT,
    MODULE_PATH,
    SCRIPT_PATH,
)

DEFAULT_AUDIT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v6.json"
)
FREEZE_PATH = Path("scripts/freeze_periodic_flow_successor_execution_contract_v6.py")
AUDIT_PATH = Path("scripts/audit_periodic_flow_successor_execution_contract_v6.py")


def auditor_contract_hash():
    return source_contract_hash(
        PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH, FREEZE_PATH, AUDIT_PATH)
    )


def authoritative_audit(args, audited_at):
    contract = PeriodicFlowSuccessorExecutionContractV6.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(args, contract.frozen_at)
    if contract != expected:
        raise ValueError("Q1 successor v6 contract did not reconstruct")
    return build_execution_contract_audit_v6(
        audited_at=audited_at,
        contract_file_sha256=file_sha256(args.contract),
        contract_evidence_hash=contract.contract_evidence_hash,
        runner_source_hash=contract.runner_source_hash,
        auditor_contract_hash=auditor_contract_hash(),
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Audit Q1 successor v6 contract.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--v5-checkpoint", type=Path, default=DEFAULT_V5_CHECKPOINT)
    parser.add_argument("--v5-result", type=Path, default=DEFAULT_V5_RESULT)
    parser.add_argument(
        "--v5-terminal-audit", type=Path, default=DEFAULT_V5_TERMINAL_AUDIT
    )
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    return parser.parse_args()


def _write(path, model):
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v6 contract audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorExecutionContractAuditV6.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args, stored.audited_at)
            if stored != expected or not audit_hash(stored, "audit_evidence_hash"):
                raise ValueError("Stored Q1 successor v6 contract audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}")
            return 0
        model = authoritative_audit(args, datetime.now(UTC))
        _write(args.output, model)
        print(f"AUDITED {args.output} {model.audit_evidence_hash}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
