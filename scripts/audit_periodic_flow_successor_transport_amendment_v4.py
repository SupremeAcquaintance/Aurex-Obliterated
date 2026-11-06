from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_transport_v4 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentAuditV4,
    PeriodicFlowSuccessorTransportAmendmentV4,
    audit_hash,
    build_transport_amendment_audit_v4,
)
from scripts.freeze_periodic_flow_successor_transport_amendment_v4 import (  # noqa: E402
    DEFAULT_BOOTSTRAP_PARTIAL,
    DEFAULT_OUTPUT,
    DEFAULT_PROTOCOL,
    DEFAULT_V3_AMENDMENT,
    DEFAULT_V3_CHECKPOINT,
    DEFAULT_V3_CONTRACT,
    DEFAULT_V3_CONTRACT_AUDIT,
    DEFAULT_V3_RESULT,
    DEFAULT_V3_TERMINAL_AUDIT,
    authoritative_amendment,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    source_contract_hash,
)

DEFAULT_AUDIT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_audit_v4.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_transport_v4.py")
FREEZE_PATH = Path("scripts/freeze_periodic_flow_successor_transport_amendment_v4.py")
AUDIT_PATH = Path("scripts/audit_periodic_flow_successor_transport_amendment_v4.py")


def auditor_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, FREEZE_PATH, AUDIT_PATH))


def authoritative_audit(
    *, args: argparse.Namespace, audited_at: datetime
) -> PeriodicFlowSuccessorTransportAmendmentAuditV4:
    amendment = PeriodicFlowSuccessorTransportAmendmentV4.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    expected = authoritative_amendment(args=args, frozen_at=amendment.frozen_at)
    if amendment != expected or not audit_hash(amendment, "amendment_evidence_hash"):
        raise ValueError("Q1 successor v4 amendment did not reconstruct")
    return build_transport_amendment_audit_v4(
        audited_at=audited_at,
        amendment_file_sha256=file_sha256(args.amendment),
        amendment_evidence_hash=amendment.amendment_evidence_hash,
        parent_protocol_evidence_hash=amendment.parent_protocol_evidence_hash,
        terminal_v3_audit_evidence_hash=amendment.terminal_v3_audit_evidence_hash,
        bootstrap_partial_file_sha256=amendment.bootstrap_partial_file_sha256,
        auditor_contract_hash=auditor_contract_hash(),
    )


def _write(
    path: Path, audit: PeriodicFlowSuccessorTransportAmendmentAuditV4
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v4 amendment audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    serialized = audit.model_dump_json(indent=2) + "\n"
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Q1 successor v4 continuation.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--v3-amendment", type=Path, default=DEFAULT_V3_AMENDMENT)
    parser.add_argument("--v3-contract", type=Path, default=DEFAULT_V3_CONTRACT)
    parser.add_argument(
        "--v3-contract-audit", type=Path, default=DEFAULT_V3_CONTRACT_AUDIT
    )
    parser.add_argument("--v3-checkpoint", type=Path, default=DEFAULT_V3_CHECKPOINT)
    parser.add_argument("--v3-result", type=Path, default=DEFAULT_V3_RESULT)
    parser.add_argument(
        "--v3-terminal-audit", type=Path, default=DEFAULT_V3_TERMINAL_AUDIT
    )
    parser.add_argument(
        "--bootstrap-partial", type=Path, default=DEFAULT_BOOTSTRAP_PARTIAL
    )
    parser.add_argument("--amendment", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTransportAmendmentAuditV4.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_hash(stored, "audit_evidence_hash"):
                raise ValueError("Stored Q1 successor v4 amendment audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        _write(args.output, audit)
        print(f"AUDITED {args.output} {audit.audit_evidence_hash}", flush=True)
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
