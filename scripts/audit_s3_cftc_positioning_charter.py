from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_positioning_charter import (  # noqa: E402
    S3CftcPositioningCharter,
    S3CftcPositioningCharterAudit,
    audit_s3_charter,
    audit_s3_charter_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s3_cftc_positioning_charter import (  # noqa: E402
    MODULE_PATH,
    build_charter,
    builder_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_CHARTER = Path("data/evidence/s3_cftc_positioning_charter_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s3_cftc_positioning_charter_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s3_cftc_positioning_charter.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S3CftcPositioningCharter:
    stored = S3CftcPositioningCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_s3_charter(stored):
        raise ValueError("Frozen S3 charter failed its evidence hash")
    if stored.builder_contract_hash != builder_contract_hash():
        raise ValueError("Frozen S3 charter builder source changed")
    if stored != build_charter(frozen_at=stored.frozen_at):
        raise ValueError("Frozen S3 charter differs from reconstruction")
    return stored


def build_audit(
    *, charter_path: Path, audited_at: datetime
) -> S3CftcPositioningCharterAudit:
    charter = reconstruct(charter_path)
    payload = {
        "audited_at": audited_at,
        "charter_file_sha256": file_sha256(charter_path),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "builder_contract_hash": charter.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = S3CftcPositioningCharterAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S3CftcPositioningCharterAudit.model_validate(complete)


def write_atomic(path: Path, audit: S3CftcPositioningCharterAudit) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 charter audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S3CftcPositioningCharterAudit.model_validate_json(serialized) != audit:
        raise ValueError("S3 charter audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the frozen S3 charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.check:
        stored = S3CftcPositioningCharterAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(charter_path=args.charter, audited_at=stored.audited_at)
        if stored != expected or not audit_s3_charter_audit(stored):
            raise SystemExit("Stored S3 charter audit differs from reconstruction")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S3 charter audit: {args.output}")
    audit = build_audit(charter_path=args.charter, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(
        f"AUDITED {args.output} {audit.audit_evidence_hash} "
        "cftc_values=0 market_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
