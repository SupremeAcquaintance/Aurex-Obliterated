from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3 import (  # noqa: E402
    S5TargetedCorrectionV3Protocol,
    S5TargetedCorrectionV3ProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_bitcoin_core_github_targeted_correction_v3 import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction_v3 import (  # noqa: E402
    build_protocol,
    file_sha256,
    source_bindings,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_audit_v3.json"
)
AUDITOR_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_targeted_correction_v3_protocol.py"
)


def build_audit(
    *, protocol_path: Path, audited_at: datetime
) -> S5TargetedCorrectionV3ProtocolAudit:
    stored = S5TargetedCorrectionV3Protocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected = build_protocol(frozen_at=stored.frozen_at)
    if stored != expected or source_bindings() != stored.source_bindings:
        raise ValueError("S5 targeted v3 protocol differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": stored.protocol_evidence_hash,
        "builder_contract_hash": stored.builder_contract_hash,
        "source_binding_manifest_evidence_hash": (
            stored.source_binding_manifest_evidence_hash
        ),
        "target_manifest_evidence_hash": stored.target_manifest_evidence_hash,
        "adopted_response_file_sha256": stored.adopted_response_file_sha256,
        "adopted_response_body_sha256": stored.adopted_response_body_sha256,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
    }
    provisional = S5TargetedCorrectionV3ProtocolAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5TargetedCorrectionV3ProtocolAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5TargetedCorrectionV3ProtocolAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted v3 protocol audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v3 protocol audit: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5TargetedCorrectionV3ProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 targeted v3 protocol audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S5 targeted v3 protocol.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5TargetedCorrectionV3ProtocolAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(protocol_path=args.protocol, audited_at=stored.audited_at)
        if stored != expected:
            raise SystemExit("Stored S5 targeted v3 protocol audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(protocol_path=args.protocol, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
