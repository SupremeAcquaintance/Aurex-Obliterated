from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_acquisition import (  # noqa: E402
    S1BtcSourceAcquisitionProtocol,
    S1BtcSourceAcquisitionProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_btc_source_acquisition_protocol import (  # noqa: E402
    build_protocol,
)
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v1.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_btc_source_acquisition_protocol_audit_v1.json"
)
AUDITOR_PATH = Path("scripts/audit_s1_btc_source_acquisition_protocol.py")


def build_audit(
    *,
    protocol_path: Path,
    audited_at: datetime,
) -> S1BtcSourceAcquisitionProtocolAudit:
    protocol = S1BtcSourceAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    if protocol != build_protocol(frozen_at=protocol.frozen_at):
        raise ValueError("S1 BTC source protocol differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "builder_contract_hash": protocol.builder_contract_hash,
        "preregistration_evidence_hash": protocol.preregistration_evidence_hash,
        "preregistration_audit_evidence_hash": (
            protocol.preregistration_audit_evidence_hash
        ),
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
    }
    provisional = S1BtcSourceAcquisitionProtocolAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S1BtcSourceAcquisitionProtocolAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1BtcSourceAcquisitionProtocolAudit) -> None:
    if path.exists():
        raise ValueError(f"S1 BTC source audit exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 BTC source audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1BtcSourceAcquisitionProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 BTC source protocol audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S1 BTC source protocol.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1BtcSourceAcquisitionProtocolAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(protocol_path=args.protocol, audited_at=stored.audited_at)
        if stored != expected:
            raise SystemExit("Stored S1 BTC source protocol audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(protocol_path=args.protocol, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
