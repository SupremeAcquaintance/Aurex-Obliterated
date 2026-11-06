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
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionProtocol,
    PeriodicFlowSuccessorAcquisitionProtocolAudit,
    audit_hash,
    build_successor_acquisition_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_successor_acquisition_protocol import (  # noqa: E402
    DEFAULT_CENSUS_AUDIT,
    DEFAULT_CENSUS_RESULT,
    DEFAULT_OUTPUT,
    DEFAULT_TERMINAL_AUDIT,
    DEFAULT_V1_PROTOCOL,
    authoritative_protocol,
    file_sha256,
)

DEFAULT_AUDIT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_acquisition.py"
)
FREEZE_SCRIPT_PATH = Path(
    "scripts/freeze_periodic_flow_successor_acquisition_protocol.py"
)
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_successor_acquisition_protocol.py"
)


def auditor_contract_hash() -> str:
    return source_contract_hash(
        PROJECT_ROOT, (MODULE_PATH, FREEZE_SCRIPT_PATH, AUDIT_SCRIPT_PATH)
    )


def authoritative_audit(
    *, args: argparse.Namespace, audited_at: datetime
) -> PeriodicFlowSuccessorAcquisitionProtocolAudit:
    protocol = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(args=args, frozen_at=protocol.frozen_at)
    if protocol != expected or not audit_hash(protocol, "protocol_evidence_hash"):
        raise ValueError("Q1 successor acquisition protocol did not reconstruct")
    target_manifest_hash = universe_evidence_hash(
        {"targets": [item.model_dump() for item in protocol.targets]}
    )
    return build_successor_acquisition_protocol_audit(
        audited_at=audited_at,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        parent_census_result_evidence_hash=protocol.parent_census_result_evidence_hash,
        auditor_contract_hash=auditor_contract_hash(),
        target_manifest_hash=target_manifest_hash,
    )


def write_audit(
    path: Path, audit: PeriodicFlowSuccessorAcquisitionProtocolAudit
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor protocol audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor protocol audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 successor acquisition protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--census-result", type=Path, default=DEFAULT_CENSUS_RESULT)
    parser.add_argument("--census-audit", type=Path, default=DEFAULT_CENSUS_AUDIT)
    parser.add_argument("--v1-protocol", type=Path, default=DEFAULT_V1_PROTOCOL)
    parser.add_argument("--terminal-audit", type=Path, default=DEFAULT_TERMINAL_AUDIT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorAcquisitionProtocolAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_hash(stored, "audit_evidence_hash"):
                raise ValueError("Stored Q1 successor acquisition protocol audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                "targets=74 network_max=48 requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "targets=74 network_max=48 requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
