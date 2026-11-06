from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.broker_engine.binance_testnet_user_stream import (  # noqa: E402
    DEFAULT_USER_STREAM_CONTRACT_PATH,
    BinanceUserStreamEvidenceAudit,
    audit_user_stream_evidence_audit,
    build_user_stream_evidence_audit,
)


def preserve_source(source: Path, destination: Path) -> None:
    if destination.exists():
        if destination.read_bytes() != source.read_bytes():
            raise ValueError("Existing preserved source differs from the supplied source")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    part_path = destination.with_suffix(f"{destination.suffix}.part")
    if part_path.exists():
        raise ValueError(f"Stale preserved-source output exists: {part_path}")
    part_path.write_bytes(source.read_bytes())
    part_path.replace(destination)


def write_audit(path: Path, audit: BinanceUserStreamEvidenceAudit) -> None:
    if path.exists():
        raise ValueError(f"User-stream audit already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (audit.model_dump_json(indent=2) + "\n").encode("utf-8")
    part_path = path.with_suffix(f"{path.suffix}.part")
    if part_path.exists():
        raise ValueError(f"Stale user-stream audit output exists: {part_path}")
    part_path.write_bytes(serialized)
    part_path.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preserve and independently audit Phase 2C user-stream evidence."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_USER_STREAM_CONTRACT_PATH,
    )
    parser.add_argument("--preserved-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write:
            if args.preserved_source is None:
                raise ValueError("--preserved-source is required with --write")
            preserve_source(args.source, args.preserved_source)
            audit = build_user_stream_evidence_audit(
                source_path=args.source,
                preserved_source_path=args.preserved_source,
                contract_path=args.contract,
                audited_at=datetime.now(UTC),
            )
            write_audit(args.output, audit)
        else:
            audit = BinanceUserStreamEvidenceAudit.model_validate_json(
                args.output.read_bytes()
            )
        if not audit_user_stream_evidence_audit(audit):
            raise ValueError("User-stream audit is not reproducible")
        print(
            "PASS "
            f"decision={audit.decision} "
            f"source={audit.source_sha256} "
            f"audit={audit.audit_sha256} "
            f"phase_2c={audit.phase_2c_qualified} "
            f"sandbox={audit.whole_sandbox_qualified} "
            f"live={audit.live_authority}",
            flush=True,
        )
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
