from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.strategy_factory_contract import (  # noqa: E402
    StrategyFactoryContractSource,
    build_strategy_factory_contract,
)

DEFAULT_OUTPUT = Path("data/evidence/aurex_strategy_factory_contract_v1.json")
SOURCE_PATHS = (
    "src/aurex/backtest_engine/schemas.py",
    "src/aurex/backtest_engine/service.py",
    "src/aurex/backtest_engine/strategy_factory_contract.py",
    "src/aurex/strategy_engine/registry.py",
    "tests/unit/test_universal_strategy_acceptance.py",
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    sources = [
        StrategyFactoryContractSource(
            path=relative_path(PROJECT_ROOT / relative),
            file_sha256=file_sha256(PROJECT_ROOT / relative),
            byte_count=(PROJECT_ROOT / relative).stat().st_size,
        )
        for relative in SOURCE_PATHS
    ]
    contract = build_strategy_factory_contract(
        frozen_at=datetime.now(UTC),
        source_evidence=sources,
    )
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(contract.model_dump_json(indent=2))
    return 0


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
