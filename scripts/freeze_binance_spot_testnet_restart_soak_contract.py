from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.broker_engine.binance_spot_testnet import (  # noqa: E402
    BinanceSpotTestnetError,
)
from aurex.broker_engine.binance_testnet_restart_soak import (  # noqa: E402
    DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    audit_restart_soak_contract,
    build_restart_soak_contract,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the Binance Spot Testnet Phase 2D restart-soak contract."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise BinanceSpotTestnetError(
            "Restart-soak contract already exists; refusing to overwrite it"
        )
    contract = build_restart_soak_contract(frozen_at=datetime.now(UTC))
    if not audit_restart_soak_contract(contract):
        raise BinanceSpotTestnetError(
            "Restart-soak contract failed reproducibility before persistence"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    part_path = args.output.with_suffix(f"{args.output.suffix}.part")
    part_path.write_text(
        f"{contract.model_dump_json(indent=2)}\n",
        encoding="utf-8",
    )
    part_path.replace(args.output)
    print(f"contract_sha256={contract.contract_sha256}")
    print(f"output={args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
