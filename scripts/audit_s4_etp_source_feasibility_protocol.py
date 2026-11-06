from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s4_spot_bitcoin_etp_source_feasibility import (  # noqa: E402
    S4EtpSourceFeasibilityProtocol,
    S4EtpSourceFeasibilityProtocolAudit,
    audit_s4_feasibility_protocol,
    audit_s4_feasibility_protocol_audit,
    build_hashed,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s4_etp_source_feasibility import (  # noqa: E402
    MODULE_PATH,
    build_protocol,
    builder_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s4_etp_source_feasibility_protocol_v1.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/s4_etp_source_feasibility_protocol_audit_v1.json"
)
SCRIPT_PATH = Path("scripts/audit_s4_etp_source_feasibility_protocol.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(path: Path) -> S4EtpSourceFeasibilityProtocol:
    stored = S4EtpSourceFeasibilityProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_s4_feasibility_protocol(stored):
        raise ValueError("Frozen S4 feasibility protocol failed its hash")
    if stored.builder_contract_hash != builder_contract_hash():
        raise ValueError("Frozen S4 feasibility builder source changed")
    if stored != build_protocol(frozen_at=stored.frozen_at):
        raise ValueError("Frozen S4 feasibility protocol differs from reconstruction")
    return stored


def build_audit(
    *, protocol_path: Path, audited_at: datetime
) -> S4EtpSourceFeasibilityProtocolAudit:
    protocol = reconstruct(protocol_path)
    return build_hashed(
        S4EtpSourceFeasibilityProtocolAudit,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "protocol_file_sha256": file_sha256(protocol_path),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "charter_evidence_hash": protocol.charter_evidence_hash,
            "builder_contract_hash": protocol.builder_contract_hash,
            "auditor_contract_hash": auditor_contract_hash(),
        },
    )


def write_atomic(path: Path, audit: S4EtpSourceFeasibilityProtocolAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S4 protocol audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S4 protocol-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S4EtpSourceFeasibilityProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("S4 feasibility protocol audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S4 ETP feasibility protocol.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S4EtpSourceFeasibilityProtocolAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                protocol_path=args.protocol,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_s4_feasibility_protocol_audit(stored):
                raise ValueError("Stored S4 protocol audit differs from reconstruction")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(protocol_path=args.protocol, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "network=0 etp_values=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
