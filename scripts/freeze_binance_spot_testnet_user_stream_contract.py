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
    BinanceUserStreamContract,
    audit_user_stream_contract,
    build_user_stream_contract,
)


def write_contract(path: Path, contract: BinanceUserStreamContract) -> None:
    if path.exists():
        raise ValueError(f"Frozen contract already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (contract.model_dump_json(indent=2) + "\n").encode("utf-8")
    if BinanceUserStreamContract.model_validate_json(serialized) != contract:
        raise ValueError("User-stream contract did not round-trip")
    part_path = path.with_suffix(f"{path.suffix}.part")
    if part_path.exists():
        raise ValueError(f"Stale contract output exists: {part_path}")
    part_path.write_bytes(serialized)
    part_path.replace(path)


def check_contract(path: Path) -> BinanceUserStreamContract:
    contract = BinanceUserStreamContract.model_validate_json(path.read_bytes())
    if not audit_user_stream_contract(contract):
        raise ValueError("Frozen user-stream contract is not reproducible")
    print(
        "PASS "
        f"contract={contract.contract_id} "
        f"sha256={contract.contract_sha256} "
        f"sandbox_qualified={contract.sandbox_qualified} "
        f"live={contract.live_authority}",
        flush=True,
    )
    return contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or audit the Binance Spot Testnet user-stream contract."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_USER_STREAM_CONTRACT_PATH,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            contract = build_user_stream_contract(frozen_at=datetime.now(UTC))
            write_contract(args.output, contract)
        check_contract(args.output)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
