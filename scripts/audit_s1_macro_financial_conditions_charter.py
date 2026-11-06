from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_successor_charter import (  # noqa: E402
    S1MacroFinancialConditionsCharter,
    S1MacroFinancialConditionsCharterAudit,
    audit_s1_charter,
    audit_s1_charter_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_macro_financial_conditions_charter import (  # noqa: E402
    MODULE_PATH,
    build_charter,
    builder_contract_hash,
)
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_CHARTER = Path(
    "data/evidence/s1_macro_financial_conditions_charter_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_macro_financial_conditions_charter_audit_v1.json"
)
SCRIPT_PATH = Path("scripts/audit_s1_macro_financial_conditions_charter.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S1MacroFinancialConditionsCharter:
    stored = S1MacroFinancialConditionsCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_s1_charter(stored):
        raise ValueError("Frozen S1 charter failed its evidence hash")
    if stored.builder_contract_hash != builder_contract_hash():
        raise ValueError("Frozen S1 charter builder source changed")
    if stored != build_charter(frozen_at=stored.frozen_at):
        raise ValueError("Frozen S1 charter differs from reconstruction")
    return stored


def build_audit(
    *,
    charter_path: Path,
    audited_at: datetime,
) -> S1MacroFinancialConditionsCharterAudit:
    charter = reconstruct(charter_path)
    payload = {
        "audited_at": audited_at,
        "charter_file_sha256": file_sha256(charter_path),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "builder_contract_hash": charter.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = S1MacroFinancialConditionsCharterAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return S1MacroFinancialConditionsCharterAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1MacroFinancialConditionsCharterAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 charter audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1MacroFinancialConditionsCharterAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 charter audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the frozen S1 macro charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1MacroFinancialConditionsCharterAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(charter_path=args.charter, audited_at=stored.audited_at)
        if stored != expected or not audit_s1_charter_audit(stored):
            raise SystemExit("Stored S1 charter audit differs from reconstruction")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S1 charter audit: {args.output}")
    audit = build_audit(charter_path=args.charter, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
