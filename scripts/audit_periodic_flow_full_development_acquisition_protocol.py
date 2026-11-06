from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (  # noqa: E402
    PeriodicFlowFullDevelopmentProtocol,
    PeriodicFlowFullDevelopmentProtocolAudit,
    audit_full_development_protocol,
    audit_full_development_protocol_audit,
    build_full_development_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_full_development_acquisition import (  # noqa: E402
    MODULE_PATH,
    SCRIPT_PATH,
    authoritative_protocol,
    file_sha256,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_full_development_acquisition_protocol.py"
)


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                path.as_posix(): hashlib.sha256(
                    (PROJECT_ROOT / path).read_bytes()
                ).hexdigest()
                for path in (MODULE_PATH, SCRIPT_PATH, AUDIT_SCRIPT_PATH)
            }
        }
    )


def authoritative_audit(
    *,
    protocol_path: Path,
    audited_at: datetime,
) -> PeriodicFlowFullDevelopmentProtocolAudit:
    protocol = PeriodicFlowFullDevelopmentProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(frozen_at=protocol.frozen_at)
    if protocol != expected or not audit_full_development_protocol(protocol):
        raise ValueError("Q1 full-development protocol did not reconstruct")
    return build_full_development_protocol_audit(
        audited_at=audited_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        builder_contract_hash=protocol.builder_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
    )


def write_audit(
    path: Path,
    audit: PeriodicFlowFullDevelopmentProtocolAudit,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowFullDevelopmentProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 full-development protocol audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale protocol audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 full-development acquisition protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowFullDevelopmentProtocolAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(
                protocol_path=args.protocol,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_full_development_protocol_audit(
                stored
            ):
                raise ValueError("Stored Q1 full-development protocol audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                "targets=96 requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        if args.output.exists():
            raise ValueError(f"Refusing to overwrite protocol audit: {args.output}")
        audit = authoritative_audit(
            protocol_path=args.protocol,
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "targets=96 requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
