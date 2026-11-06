import argparse
import json
from dataclasses import asdict

from aurex.backtest_engine.candidate_protocols import (
    jam_reversal_spot_v1_preregistration,
    register_candidate_protocol_durably,
    slow_breakout_spot_v1_preregistrations,
    volatility_breakout_v1_preregistration,
)
from aurex.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Durably register and verify a frozen Aurex candidate protocol."
    )
    parser.add_argument(
        "candidate",
        choices=(
            "volatility_breakout_v1",
            "slow_breakout_spot_v1",
            "jam_reversal_spot_v1",
        ),
        help="Frozen candidate package to register.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_groups = {
        "volatility_breakout_v1": lambda: (volatility_breakout_v1_preregistration(),),
        "slow_breakout_spot_v1": slow_breakout_spot_v1_preregistrations,
        "jam_reversal_spot_v1": lambda: (jam_reversal_spot_v1_preregistration(),),
    }
    receipts = []
    try:
        for package in package_groups[args.candidate]():
            receipts.append(register_candidate_protocol_durably(SessionLocal, package))
    except (RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": str(exc),
                    "committed_before_block": [asdict(item) for item in receipts],
                },
                indent=2,
                default=str,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "COMMITTED",
                "candidate": args.candidate,
                "protocols": [asdict(item) for item in receipts],
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
