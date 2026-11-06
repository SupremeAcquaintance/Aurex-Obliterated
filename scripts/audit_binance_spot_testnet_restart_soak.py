from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.broker_engine.binance_testnet_restart_soak import (  # noqa: E402
    DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    DEFAULT_RESTART_SOAK_EVIDENCE_PATH,
    BinanceRestartSoakEvidenceAudit,
    audit_restart_soak_evidence_audit,
    build_restart_soak_evidence_audit,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit one completed Phase 2D restart-soak campaign."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_RESTART_SOAK_EVIDENCE_PATH,
    )
    parser.add_argument("--preserved-source", type=Path, required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise ValueError("Restart-soak audit already exists; refusing to overwrite it")
    source_raw = args.source.read_bytes()
    if args.preserved_source.exists():
        raise ValueError(
            "Preserved restart-soak source already exists; refusing to overwrite it"
        )
    args.preserved_source.parent.mkdir(parents=True, exist_ok=True)
    args.preserved_source.write_bytes(source_raw)
    audit = build_restart_soak_evidence_audit(
        source_path=args.source,
        preserved_source_path=args.preserved_source,
        contract_path=args.contract,
        audited_at=datetime.now(UTC),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{audit.model_dump_json(indent=2)}\n", encoding="utf-8")
    persisted = BinanceRestartSoakEvidenceAudit.model_validate_json(
        args.output.read_bytes()
    )
    if not audit_restart_soak_evidence_audit(persisted):
        raise ValueError("Persisted restart-soak audit is not reproducible")
    print(
        "PASS "
        f"decision={persisted.decision} "
        f"source={hashlib.sha256(source_raw).hexdigest()} "
        f"audit={persisted.audit_sha256} "
        f"adapter_sandbox={persisted.adapter_sandbox_qualified} "
        f"live={persisted.live_authority}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
