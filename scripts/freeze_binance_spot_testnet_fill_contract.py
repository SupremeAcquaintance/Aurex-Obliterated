from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.broker_engine.binance_testnet_fill_campaign import (  # noqa: E402
    DEFAULT_CONTRACT_PATH,
    BinanceFillFeeContract,
    audit_fill_fee_contract,
    build_fill_fee_contract,
)


def write_contract(path: Path, contract: BinanceFillFeeContract) -> None:
    if path.exists():
        raise ValueError(f"Frozen contract already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (contract.model_dump_json(indent=2) + "\n").encode("utf-8")
    if BinanceFillFeeContract.model_validate_json(serialized) != contract:
        raise ValueError("Fill-and-fee contract did not round-trip")
    part_path = path.with_suffix(f"{path.suffix}.part")
    if part_path.exists():
        raise ValueError(f"Stale contract output exists: {part_path}")
    part_path.write_bytes(serialized)
    part_path.replace(path)


def check_contract(path: Path) -> BinanceFillFeeContract:
    contract = BinanceFillFeeContract.model_validate_json(path.read_bytes())
    if not audit_fill_fee_contract(contract):
        raise ValueError("Frozen fill-and-fee contract is not reproducible")
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
        description="Freeze or audit the Binance Spot Testnet fill-and-fee contract."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            contract = build_fill_fee_contract(frozen_at=datetime.now(UTC))
            write_contract(args.output, contract)
        check_contract(args.output)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
