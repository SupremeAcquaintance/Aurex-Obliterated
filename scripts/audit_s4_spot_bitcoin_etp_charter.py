from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s4_spot_bitcoin_etp_charter import (  # noqa: E402
    S4SpotBitcoinEtpCharter,
    S4SpotBitcoinEtpCharterAudit,
    audit_s4_charter,
    audit_s4_charter_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s4_spot_bitcoin_etp_charter import (  # noqa: E402
    MODULE_PATH,
    build_charter,
    builder_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_CHARTER = Path("data/evidence/s4_spot_bitcoin_etp_charter_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s4_spot_bitcoin_etp_charter_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s4_spot_bitcoin_etp_charter.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S4SpotBitcoinEtpCharter:
    stored = S4SpotBitcoinEtpCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_s4_charter(stored):
        raise ValueError("Frozen S4 charter failed its evidence hash")
    if stored.builder_contract_hash != builder_contract_hash():
        raise ValueError("Frozen S4 charter builder source changed")
    if stored != build_charter(frozen_at=stored.frozen_at):
        raise ValueError("Frozen S4 charter differs from reconstruction")
    return stored


def build_audit(
    *, charter_path: Path, audited_at: datetime
) -> S4SpotBitcoinEtpCharterAudit:
    charter = reconstruct(charter_path)
    payload = {
        "audited_at": audited_at,
        "charter_file_sha256": file_sha256(charter_path),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "builder_contract_hash": charter.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "incidental_source_numeric_fields_observed": (
            charter.incidental_source_numeric_fields_observed
        ),
    }
    provisional = S4SpotBitcoinEtpCharterAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S4SpotBitcoinEtpCharterAudit.model_validate(complete)


def write_atomic(path: Path, audit: S4SpotBitcoinEtpCharterAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S4 charter audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S4 charter audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S4SpotBitcoinEtpCharterAudit.model_validate_json(serialized) != audit:
        raise ValueError("S4 charter audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the frozen S4 charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S4SpotBitcoinEtpCharterAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                charter_path=args.charter, audited_at=stored.audited_at
            )
            if stored != expected or not audit_s4_charter_audit(stored):
                raise ValueError("Stored S4 charter audit differs from reconstruction")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            charter_path=args.charter, audited_at=datetime.now(UTC)
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "etp_rows=0 payloads=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
