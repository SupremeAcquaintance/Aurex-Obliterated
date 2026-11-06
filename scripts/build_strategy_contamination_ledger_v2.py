import argparse
import json
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    StrategyContaminationRecord,
    audit_contamination_ledger,
    build_contamination_ledger,
)

V1_LEDGER = Path("data/evidence/strategy_contamination_ledger_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/strategy_contamination_ledger_v2.json")
EXPECTED_V1_HASH = (
    "9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207"
)


def jam_reversal_spot_record() -> StrategyContaminationRecord:
    return StrategyContaminationRecord(
        record_id="jam-reversal-spot-btc-15m-2023-2026",
        strategy_family="jam_reversal",
        strategy="jam_reversal_spot_v1",
        strategy_version="1.0.1",
        symbols=["BTCUSDT"],
        timeframes=["15m"],
        window_start="2023-02-01T00:00:00Z",
        window_end="2026-01-01T00:00:00Z",
        first_observed_at="2026-07-31T18:29:31.816328Z",
        classification="HOLDOUT_OPENED_RETIRED",
        outcome_fields_inspected=[
            "cost_sensitivity",
            "expectancy",
            "max_drawdown",
            "net_pl",
            "oos",
            "profit_factor",
            "walk_forward",
        ],
        evidence_references=[
            "reference-replay:82e5ff23-a4de-423b-b8df-6394d09566a1",
            "validation:6ad2fef6-ffd3-4773-9f02-52e80596bdd4",
            "data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json",
        ],
        source_evidence_hashes={
            "artifact": (
                "d8b108df43a82b3bb5db0cdffd3ec94992e9baf43fede05bbd01dd518a03c5fd"
            ),
            "replay_record": (
                "e744038580b0d413c15ba25b7a8936faa6fc3f08d67f7ffbd01f29ffe77db257"
            ),
            "validation": (
                "02e2f67a72569a177cfea56ac2ec3dd3265a7cc460359188fa7611d25da64762"
            ),
        },
        reason=(
            "The preregistered long-only BTCUSDT decision set was opened and "
            "failed sample-size, fee-net profitability, OOS, active-day, and "
            "walk-forward gates."
        ),
    )


def authoritative_v2_ledger() -> StrategyContaminationLedger:
    v1 = StrategyContaminationLedger.model_validate_json(
        V1_LEDGER.read_text(encoding="utf-8")
    )
    if not audit_contamination_ledger(v1):
        raise ValueError("The v1 contamination ledger failed its evidence-hash audit")
    if v1.ledger_evidence_hash != EXPECTED_V1_HASH:
        raise ValueError("The v1 contamination ledger is not the frozen parent")
    return build_contamination_ledger([*v1.records, jam_reversal_spot_record()])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or verify the append-only Aurex contamination ledger v2."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = authoritative_v2_ledger()
    if args.check:
        stored = StrategyContaminationLedger.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if not audit_contamination_ledger(stored):
            raise SystemExit("Stored contamination ledger v2 failed its hash audit")
        if stored != expected:
            raise SystemExit("Stored contamination ledger v2 differs from its contract")
        print(f"PASS {stored.ledger_evidence_hash}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(expected.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {args.output} {expected.ledger_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
