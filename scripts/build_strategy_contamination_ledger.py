import argparse
import json
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    StrategyContaminationRecord,
    audit_contamination_ledger,
    build_contamination_ledger,
)

DEFAULT_OUTPUT = Path("data/evidence/strategy_contamination_ledger_v1.json")


def authoritative_records() -> list[StrategyContaminationRecord]:
    return [
        StrategyContaminationRecord(
            record_id="jam-reversal-btc-neighbor-probes-2026",
            strategy_family="jam_reversal",
            strategy="jam_reversal_v1",
            strategy_version="1.14.0",
            symbols=["BTCUSDT"],
            timeframes=["5m", "15m", "30m", "1h"],
            window_start="2026-05-01T00:00:00Z",
            window_end="2026-07-21T00:00:00Z",
            first_observed_at="2026-07-20T00:00:00Z",
            classification="EXPLORATORY_CONTAMINATED",
            outcome_fields_inspected=[
                "closed_trades",
                "max_drawdown",
                "net_pl",
                "profitable_trades",
            ],
            evidence_references=[
                "docs/pine/jam_reversal_v1.md",
                "tradingview://strategy-tester/BINANCE:BTCUSDT/15m",
            ],
            source_evidence_hashes={
                "pine_source": (
                    "f1c7231bd2f9a919157dbe14388fc838d6d484f9cda50c2a36c4e6b79b49a7c3"
                )
            },
            reason=(
                "Repeated entry, exit, filter, target, stop, timeframe, and symbol "
                "probes were inspected on this research window."
            ),
        ),
        StrategyContaminationRecord(
            record_id="slow-breakout-btc-development-2023-2026",
            strategy_family="slow_trend_breakout_spot",
            strategy="slow_breakout_spot_v1",
            strategy_version="1.0.0",
            symbols=["BTCUSDT"],
            timeframes=["4h"],
            window_start="2023-01-01T00:00:00Z",
            window_end="2026-07-01T00:00:00Z",
            first_observed_at="2026-07-22T11:49:17Z",
            classification="DEVELOPMENT_CONTAMINATED",
            outcome_fields_inspected=["prior_strategy_results", "research_design"],
            evidence_references=[
                "dataset:1c39d87b-683b-4d3d-a180-6e825f7b622b",
                "docs/14_STRATEGY_FAILURE_ANALYSIS.md",
            ],
            source_evidence_hashes={
                "dataset": (
                    "8059290d0af5108f6c2167bfcba21b755b5ab8d14310a48321cb995e22d15056"
                )
            },
            reason=(
                "BTC was explicitly assigned to development after prior strategy "
                "results and failure analysis influenced the slow-breakout design."
            ),
        ),
        StrategyContaminationRecord(
            record_id="slow-breakout-eth-holdout-2023-2026",
            strategy_family="slow_trend_breakout_spot",
            strategy="slow_breakout_spot_v1",
            strategy_version="1.0.0",
            symbols=["ETHUSDT"],
            timeframes=["4h"],
            window_start="2023-01-01T00:00:00Z",
            window_end="2026-07-01T00:00:00Z",
            first_observed_at="2026-07-22T12:08:32Z",
            classification="HOLDOUT_OPENED_RETIRED",
            outcome_fields_inspected=[
                "cost_stress",
                "expectancy",
                "net_pl",
                "oos",
                "profit_factor",
                "walk_forward",
            ],
            evidence_references=[
                "reference-replay:0bbe94e9-4596-41f0-9889-e21ab26085e7",
                "validation:efa5db06-08f9-4344-8869-294cdca54d38",
            ],
            source_evidence_hashes={
                "validation": (
                    "238aacc86272b3f945ecc59f8d7e31cecde5f643ac237e25de9066fdc227c515"
                )
            },
            reason=(
                "The preregistered ETH holdout was opened and failed its individual "
                "walk-forward requirement."
            ),
        ),
        StrategyContaminationRecord(
            record_id="slow-breakout-sol-holdout-2023-2026",
            strategy_family="slow_trend_breakout_spot",
            strategy="slow_breakout_spot_v1",
            strategy_version="1.0.0",
            symbols=["SOLUSDT"],
            timeframes=["4h"],
            window_start="2023-01-01T00:00:00Z",
            window_end="2026-07-01T00:00:00Z",
            first_observed_at="2026-07-22T12:08:32Z",
            classification="HOLDOUT_OPENED_RETIRED",
            outcome_fields_inspected=[
                "cost_stress",
                "expectancy",
                "net_pl",
                "oos",
                "profit_factor",
                "walk_forward",
            ],
            evidence_references=[
                "reference-replay:97700413-7a29-4dff-aa7c-aab086e8c1b1",
                "validation:9ea9e6dd-61d1-4e4e-a1d6-f15cfb899d72",
            ],
            source_evidence_hashes={
                "validation": (
                    "9f0ce8605f461a019fd1d43d636b1adeae898d1c38060c3bd6258f1bb12289d3"
                )
            },
            reason=(
                "The preregistered SOL holdout was opened and failed OOS and "
                "walk-forward requirements."
            ),
        ),
        StrategyContaminationRecord(
            record_id="trend-pullback-btc-15m-2023-2026",
            strategy_family="intraday_trend_pullback",
            strategy="trend_pullback_v1",
            strategy_version="1.3.0",
            symbols=["BTCUSDT"],
            timeframes=["15m"],
            window_start="2023-02-01T00:00:00Z",
            window_end="2026-07-01T00:00:00Z",
            first_observed_at="2026-07-18T15:03:58Z",
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
                "reference-replay:e1e5539a-49df-409d-8790-93639e173dc5",
                "validation:454b85d7-75b2-4a6e-8571-b9d951cbc178",
            ],
            source_evidence_hashes={
                "replay_record": (
                    "a8b1263e9bde08de46038b053a7f2886bc36656554211c0ee098aa2b40a8d60e"
                )
            },
            reason=(
                "The complete multi-year result was opened, analyzed, and rejected."
            ),
        ),
        StrategyContaminationRecord(
            record_id="volatility-breakout-btc-15m-2023-2026",
            strategy_family="intraday_volatility_breakout",
            strategy="volatility_breakout_v1",
            strategy_version="1.1.0",
            symbols=["BTCUSDT"],
            timeframes=["15m"],
            window_start="2023-02-01T00:00:00Z",
            window_end="2026-07-01T00:00:00Z",
            first_observed_at="2026-07-21T12:11:20Z",
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
                "reference-replay:9c2f12c7-9ee8-46c3-b8ea-c4aacbb5fae7",
                "docs/14_STRATEGY_FAILURE_ANALYSIS.md",
            ],
            source_evidence_hashes={
                "replay_record": (
                    "67fbd22e0b195cb16c3bc37caadb269e292b91e0e4859bd88d3c89dfcff4c20f"
                )
            },
            reason=(
                "The complete multi-year result was opened, analyzed, and retired."
            ),
        ),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or verify the authoritative Aurex contamination ledger."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = build_contamination_ledger(authoritative_records())
    if args.check:
        stored = StrategyContaminationLedger.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if not audit_contamination_ledger(stored):
            raise SystemExit("Stored contamination ledger failed its evidence-hash audit")
        if stored != expected:
            raise SystemExit("Stored contamination ledger differs from authoritative records")
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
