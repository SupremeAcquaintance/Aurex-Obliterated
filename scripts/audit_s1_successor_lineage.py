from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_successor_charter import (  # noqa: E402
    S1SuccessorLineageAudit,
    S1SuccessorLineageLedger,
    audit_s1_lineage,
    audit_s1_lineage_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import (  # noqa: E402
    MODULE_PATH,
    build_ledger,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_LEDGER = Path("data/evidence/s1_successor_lineage_ledger_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_successor_lineage_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s1_successor_lineage.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S1SuccessorLineageLedger:
    stored = S1SuccessorLineageLedger.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_s1_lineage(stored):
        raise ValueError("Frozen S1 lineage ledger failed its evidence hash")
    if stored.builder_contract_hash != builder_contract_hash():
        raise ValueError("Frozen S1 lineage builder source changed")
    if stored != build_ledger(frozen_at=stored.frozen_at):
        raise ValueError("Frozen S1 lineage differs from reconstruction")
    return stored


def build_audit(*, ledger_path: Path, audited_at: datetime) -> S1SuccessorLineageAudit:
    ledger = reconstruct(ledger_path)
    payload = {
        "audited_at": audited_at,
        "ledger_file_sha256": file_sha256(ledger_path),
        "ledger_evidence_hash": ledger.ledger_evidence_hash,
        "builder_contract_hash": ledger.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = S1SuccessorLineageAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return S1SuccessorLineageAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1SuccessorLineageAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 lineage audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1SuccessorLineageAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 lineage audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the frozen S1 lineage ledger.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1SuccessorLineageAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(ledger_path=args.ledger, audited_at=stored.audited_at)
        if stored != expected or not audit_s1_lineage_audit(stored):
            raise SystemExit("Stored S1 lineage audit differs from reconstruction")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S1 lineage audit: {args.output}")
    audit = build_audit(ledger_path=args.ledger, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
