from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.broker_engine.binance_testnet_evidence import (  # noqa: E402
    BinanceFillFeeEvidenceAudit,
    audit_fill_fee_evidence_audit,
    build_fill_fee_evidence_audit,
)
from aurex.broker_engine.binance_testnet_fill_campaign import (  # noqa: E402
    DEFAULT_CONTRACT_PATH,
)

DEFAULT_SOURCE = Path("data/evidence/binance_spot_testnet_fill_fee_latest.json")


def write_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part_path = path.with_suffix(f"{path.suffix}.part")
    if part_path.exists():
        raise ValueError(f"Stale audit output exists: {part_path}")
    part_path.write_bytes(raw)
    part_path.replace(path)


def write_audit(args: argparse.Namespace) -> BinanceFillFeeEvidenceAudit:
    if args.output.exists():
        raise ValueError(f"Fill-and-fee audit already exists: {args.output}")
    source_raw = args.source.read_bytes()
    if args.preserved_source.exists():
        if args.preserved_source.read_bytes() != source_raw:
            raise ValueError("Existing preserved source is not byte-identical")
    else:
        write_atomic(args.preserved_source, source_raw)
    audit = build_fill_fee_evidence_audit(
        audited_at=datetime.now(UTC),
        source_path=args.source,
        preserved_source_path=args.preserved_source,
        contract_path=args.contract,
    )
    serialized = (audit.model_dump_json(indent=2) + "\n").encode("utf-8")
    if BinanceFillFeeEvidenceAudit.model_validate_json(serialized) != audit:
        raise ValueError("Fill-and-fee audit did not round-trip")
    write_atomic(args.output, serialized)
    return audit


def check_audit(path: Path) -> BinanceFillFeeEvidenceAudit:
    audit = BinanceFillFeeEvidenceAudit.model_validate_json(path.read_bytes())
    if not audit_fill_fee_evidence_audit(audit):
        raise ValueError("Fill-and-fee audit is not reproducible")
    print(
        "PASS "
        f"decision={audit.decision} "
        f"source={audit.source_sha256} "
        f"audit={audit.audit_sha256} "
        f"phase_2b={audit.phase_2b_qualified} "
        f"sandbox={audit.whole_sandbox_qualified} "
        f"live={audit.live_authority}",
        flush=True,
    )
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preserve, independently audit, or recheck one Binance Spot Testnet "
            "fill-and-fee campaign."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--preserved-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.write and args.preserved_source is None:
        parser.error("--write requires --preserved-source")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.write:
            write_audit(args)
        check_audit(args.output)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
