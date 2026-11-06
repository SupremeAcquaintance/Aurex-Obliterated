from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_spot_charter import (  # noqa: E402
    PeriodicFlowSpotCharter,
    PeriodicFlowSpotCharterAudit,
    audit_periodic_flow_spot_charter,
    audit_periodic_flow_spot_charter_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_spot_charter import (  # noqa: E402
    MODULE_PATH,
    build_charter,
    file_sha256,
    source_contract_hash,
)

DEFAULT_CHARTER = Path("data/evidence/periodic_flow_spot_charter_v1.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/periodic_flow_spot_charter_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path("scripts/audit_periodic_flow_spot_charter.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "audit_script_path": AUDIT_SCRIPT_PATH.as_posix(),
            "audit_script_sha256": file_sha256(PROJECT_ROOT / AUDIT_SCRIPT_PATH),
        }
    )


def reconstruct_charter(path: Path) -> PeriodicFlowSpotCharter:
    stored = PeriodicFlowSpotCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_periodic_flow_spot_charter(stored):
        raise ValueError("Frozen Q1 charter failed its evidence-hash audit")
    if stored.builder_contract_hash != source_contract_hash():
        raise ValueError("Frozen Q1 charter builder source changed")
    reconstructed = build_charter(frozen_at=stored.frozen_at)
    if reconstructed != stored:
        raise ValueError("Frozen Q1 charter differs from exact reconstruction")
    return stored


def build_audit(
    *,
    charter_path: Path,
    audited_at: datetime,
) -> PeriodicFlowSpotCharterAudit:
    charter = reconstruct_charter(charter_path)
    payload = {
        "audited_at": audited_at,
        "charter_file_sha256": file_sha256(charter_path),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "builder_contract_hash": charter.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = PeriodicFlowSpotCharterAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowSpotCharterAudit.model_validate(complete)


def write_audit(path: Path, audit: PeriodicFlowSpotCharterAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSpotCharterAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 charter audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 charter audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently reconstruct and audit the frozen Q1 charter."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSpotCharterAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                charter_path=args.charter,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_periodic_flow_spot_charter_audit(stored):
                raise ValueError("Stored Q1 charter audit differs from reconstruction")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite frozen Q1 audit: {args.output}")
        audit = build_audit(
            charter_path=args.charter,
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "market_values=0 returns=0 candidates=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
