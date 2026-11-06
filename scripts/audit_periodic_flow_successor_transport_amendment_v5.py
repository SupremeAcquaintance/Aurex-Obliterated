from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentAuditV5,
    PeriodicFlowSuccessorTransportAmendmentV5,
    audit_hash,
    build_transport_amendment_audit_v5,
)
from scripts.freeze_periodic_flow_successor_transport_amendment_v5 import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_PROTOCOL,
    DEFAULT_V4_AMENDMENT,
    DEFAULT_V4_CHECKPOINT,
    DEFAULT_V4_CONTRACT,
    DEFAULT_V4_CONTRACT_AUDIT,
    DEFAULT_V4_RESULT,
    DEFAULT_V4_TERMINAL_AUDIT,
    authoritative_amendment,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    source_contract_hash,
)

DEFAULT_AUDIT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_audit_v5.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_transport_v5.py")
FREEZE_PATH = Path("scripts/freeze_periodic_flow_successor_transport_amendment_v5.py")
AUDIT_PATH = Path("scripts/audit_periodic_flow_successor_transport_amendment_v5.py")


def auditor_contract_hash():
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, FREEZE_PATH, AUDIT_PATH))


def authoritative_audit(args, audited_at):
    amendment = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    expected = authoritative_amendment(args=args, frozen_at=amendment.frozen_at)
    if amendment != expected:
        raise ValueError("Q1 successor v5 amendment did not reconstruct")
    return build_transport_amendment_audit_v5(
        audited_at=audited_at,
        amendment_file_sha256=file_sha256(args.amendment),
        amendment_evidence_hash=amendment.amendment_evidence_hash,
        terminal_v4_audit_evidence_hash=amendment.terminal_v4_audit_evidence_hash,
        auditor_contract_hash=auditor_contract_hash(),
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Audit Q1 successor v5 amendment.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--v4-amendment", type=Path, default=DEFAULT_V4_AMENDMENT)
    parser.add_argument("--v4-contract", type=Path, default=DEFAULT_V4_CONTRACT)
    parser.add_argument(
        "--v4-contract-audit", type=Path, default=DEFAULT_V4_CONTRACT_AUDIT
    )
    parser.add_argument("--v4-checkpoint", type=Path, default=DEFAULT_V4_CHECKPOINT)
    parser.add_argument("--v4-result", type=Path, default=DEFAULT_V4_RESULT)
    parser.add_argument(
        "--v4-terminal-audit", type=Path, default=DEFAULT_V4_TERMINAL_AUDIT
    )
    parser.add_argument("--amendment", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTransportAmendmentAuditV5.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args, stored.audited_at)
            if stored != expected or not audit_hash(stored, "audit_evidence_hash"):
                raise ValueError("Stored Q1 successor v5 amendment audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}")
            return 0
        model = authoritative_audit(args, datetime.now(UTC))
        args.output.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"AUDITED {args.output} {model.audit_evidence_hash}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
