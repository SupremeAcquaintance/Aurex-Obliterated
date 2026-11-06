from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_feature_protocol import (  # noqa: E402
    JamSuccessorFeatureProtocol,
    audit_jam_successor_feature_protocol,
)
from aurex.backtest_engine.jam_successor_feature_specification import (  # noqa: E402
    JAM_FEATURE_IDS,
    JamAggTradeFixture,
    JamSuccessorFeatureSpecification,
    aggregate_fixture_trades,
    audit_jam_successor_feature_specification,
    build_conformance_case,
    build_jam_successor_feature_specification,
    compute_feature_row,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_jam_successor_feature_protocol import (  # noqa: E402
    DEFAULT_CHARTER,
    DEFAULT_CONTAMINATION_LEDGER,
    DEFAULT_QUALITY_AUDIT,
    DEFAULT_QUALITY_PROTOCOL,
    DEFAULT_QUALITY_RESULT,
    authoritative_protocol,
    load_inputs,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/jam_successor_feature_specification_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_feature_specification_v1.json"
)
SYNTHETIC_START_MS = 60_000_000_000


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
                for path in paths
            }
        }
    )


def specification_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_jam_successor_feature_specification.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_feature_specification.py",
        ]
    )


def synthetic_fixture(
    *,
    constant_baseline: bool = False,
    include_future: bool = False,
) -> list[JamAggTradeFixture]:
    trades = []
    aggregate_id = 1
    trade_id = 1
    for minute_index in range(133 + int(include_future)):
        if minute_index < 120:
            price = Decimal("100")
            sell_quantity = (
                Decimal("2")
                if constant_baseline
                else Decimal(minute_index % 5 + 1)
            )
            buy_quantity = Decimal("2")
        elif minute_index < 125:
            price = Decimal("100")
            sell_quantity = Decimal("2")
            buy_quantity = Decimal("2")
        elif minute_index < 130:
            price = Decimal(224 - minute_index)
            sell_quantity = Decimal("20")
            buy_quantity = Decimal("2")
        elif minute_index < 133:
            price = Decimal(97 + (minute_index - 130) * 2)
            sell_quantity = Decimal("2")
            buy_quantity = Decimal("8")
        else:
            price = Decimal("500")
            sell_quantity = Decimal("100")
            buy_quantity = Decimal("100")
        timestamp = SYNTHETIC_START_MS + minute_index * 60_000
        for is_buyer_maker, quantity, offset in (
            (False, buy_quantity, Decimal("0.10")),
            (True, sell_quantity, Decimal("0.00")),
        ):
            trades.append(
                JamAggTradeFixture(
                    aggregate_trade_id=aggregate_id,
                    price=price + offset,
                    quantity=quantity,
                    first_trade_id=trade_id,
                    last_trade_id=trade_id,
                    transact_time_ms=timestamp + aggregate_id % 1_000,
                    is_buyer_maker=is_buyer_maker,
                    is_best_match=True,
                )
            )
            aggregate_id += 1
            trade_id += 1
    return trades


def run_conformance_cases():
    trades = synthetic_fixture()
    minutes = aggregate_fixture_trades(trades)
    evaluation = SYNTHETIC_START_MS + 132 * 60_000
    first = minutes[0]
    expected_buy = trades[0].price * trades[0].quantity
    expected_sell = trades[1].price * trades[1].quantity
    if (
        first.taker_buy_quote_volume != expected_buy
        or first.taker_sell_quote_volume != expected_sell
    ):
        raise ValueError("Jam synthetic aggressor-side mapping failed")
    cases = [
        build_conformance_case(
            case_id="C01_AGGRESSOR_MAPPING",
            assertion=(
                "buyer_maker false maps to taker buy and true maps to taker sell"
            ),
            synthetic_row_count=len(trades),
            observed_state="BUY_AND_SELL_NOTIONAL_MATCH",
        )
    ]
    ready = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )
    if ready.quality_state != "READY" or tuple(ready.feature_values) != JAM_FEATURE_IDS:
        raise ValueError("Jam synthetic ready-vector conformance failed")
    cases.append(
        build_conformance_case(
            case_id="C02_CAUSAL_READY_VECTOR",
            assertion="exactly seventeen causal features exist after 133 valid minutes",
            synthetic_row_count=len(trades),
            observed_state="READY_17_FEATURES",
        )
    )
    future_trades = synthetic_fixture(include_future=True)
    with_future = compute_feature_row(
        minutes=aggregate_fixture_trades(future_trades),
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )
    if with_future != ready:
        raise ValueError("Jam future observation changed current feature row")
    cases.append(
        build_conformance_case(
            case_id="C03_FUTURE_INVARIANCE",
            assertion="a later synthetic minute cannot change the current feature row",
            synthetic_row_count=len(future_trades),
            observed_state="CURRENT_ROW_UNCHANGED",
        )
    )
    partition_reset = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=evaluation,
        partition_start_ms=evaluation - 100 * 60_000,
    )
    if partition_reset.quality_state != "PARTITION_RESET_WARMUP":
        raise ValueError("Jam partition reset conformance failed")
    cases.append(
        build_conformance_case(
            case_id="C04_PARTITION_RESET",
            assertion="rolling state cannot cross an evidence-partition boundary",
            synthetic_row_count=len(trades),
            observed_state=partition_reset.quality_state,
        )
    )
    current_quarantine = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
        quarantined_open_times={evaluation},
    )
    if current_quarantine.quality_state != "SOURCE_QUARANTINE":
        raise ValueError("Jam current quarantine conformance failed")
    cases.append(
        build_conformance_case(
            case_id="C05_CURRENT_QUARANTINE",
            assertion="a quarantined evaluation minute emits no feature values",
            synthetic_row_count=len(trades),
            observed_state=current_quarantine.quality_state,
        )
    )
    post_defect = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
        quarantined_open_times={evaluation - 10 * 60_000},
    )
    if post_defect.quality_state != "POST_DEFECT_WARMUP":
        raise ValueError("Jam post-defect warm-up conformance failed")
    cases.append(
        build_conformance_case(
            case_id="C06_POST_DEFECT_WARMUP",
            assertion="a defect inside the 133-minute window withholds all features",
            synthetic_row_count=len(trades),
            observed_state=post_defect.quality_state,
        )
    )
    no_current = compute_feature_row(
        minutes=minutes[:-1],
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )
    if no_current.quality_state != "NO_AGGTRADE_MINUTE":
        raise ValueError("Jam no-aggregate-minute conformance failed")
    cases.append(
        build_conformance_case(
            case_id="C07_NO_AGGTRADE_MINUTE",
            assertion="an absent aggregate minute is not synthesized from klines",
            synthetic_row_count=len(trades) - 2,
            observed_state=no_current.quality_state,
        )
    )
    constant_trades = synthetic_fixture(constant_baseline=True)
    degenerate = compute_feature_row(
        minutes=aggregate_fixture_trades(constant_trades),
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )
    if degenerate.quality_state != "DEGENERATE_ROBUST_SCALE":
        raise ValueError("Jam robust-scale conformance failed")
    cases.append(
        build_conformance_case(
            case_id="C08_DEGENERATE_ROBUST_SCALE",
            assertion="zero baseline MAD emits no robust-z feature values",
            synthetic_row_count=len(constant_trades),
            observed_state=degenerate.quality_state,
        )
    )
    repeated = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )
    if repeated.model_dump_json() != ready.model_dump_json():
        raise ValueError("Jam decimal determinism conformance failed")
    cases.append(
        build_conformance_case(
            case_id="C09_DECIMAL_DETERMINISM",
            assertion="repeated Decimal calculation is byte-stable",
            synthetic_row_count=len(trades),
            observed_state="BYTE_STABLE_ROUND_HALF_EVEN_18DP",
        )
    )
    return sorted(cases, key=lambda item: item.case_id)


def load_protocol(
    *,
    protocol_path: Path,
    charter_path: Path,
    quality_protocol_path: Path,
    quality_result_path: Path,
    quality_audit_path: Path,
    contamination_ledger_path: Path,
) -> JamSuccessorFeatureProtocol:
    inputs = load_inputs(
        charter_path=charter_path,
        quality_protocol_path=quality_protocol_path,
        quality_result_path=quality_result_path,
        quality_audit_path=quality_audit_path,
        contamination_ledger_path=contamination_ledger_path,
    )
    protocol = JamSuccessorFeatureProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        charter=inputs[0],
        quality_protocol=inputs[1],
        quality_result=inputs[2],
        quality_audit=inputs[3],
        contamination=inputs[4],
        charter_path=charter_path,
        quality_protocol_path=quality_protocol_path,
        quality_result_path=quality_result_path,
        quality_audit_path=quality_audit_path,
        contamination_ledger_path=contamination_ledger_path,
    )
    if (
        protocol != expected
        or not audit_jam_successor_feature_protocol(protocol)
        or protocol.raw_market_payload_access_permitted
        or protocol.decision_threshold_definition_permitted
        or protocol.future_return_definition_permitted
        or protocol.return_calculation_permitted
        or protocol.strategy_creation_permitted
        or protocol.signal_creation_permitted
        or protocol.candidate_creation_permitted
        or protocol.testnet_strategy_orders_permitted
        or protocol.production_permitted
        or protocol.live_permitted
    ):
        raise ValueError("Jam feature protocol lineage or authority changed")
    return protocol


def authoritative_specification(
    *,
    frozen_at: datetime,
    protocol: JamSuccessorFeatureProtocol,
    protocol_path: Path,
) -> JamSuccessorFeatureSpecification:
    return build_jam_successor_feature_specification(
        frozen_at=frozen_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        specification_contract_hash=specification_contract_hash(),
        source_quarantine_manifest_hash=protocol.quarantine_manifest_hash,
        conformance_cases=run_conformance_cases(),
        limitations=[
            (
                "This artifact specifies causal transformations only and inspects "
                "zero real market rows."
            ),
            (
                "The 133-minute input window is fixed as 120 baseline, five "
                "pre-shock, five shock, and three confirmation minutes."
            ),
            (
                "All four temporal phases are non-overlapping, contiguous, and "
                "available by the close of the evaluation minute."
            ),
            (
                "Buyer-maker true means the seller was taker; buyer-maker false "
                "means the buyer was taker."
            ),
            (
                "Quote notional is the exact sum of price multiplied by quantity; "
                "no candle volume is substituted."
            ),
            (
                "Robust flow normalization uses the conventional 1.4826 median "
                "absolute-deviation scale without defining a trade cutoff."
            ),
            (
                "Every output uses Decimal arithmetic and ROUND_HALF_EVEN at "
                "eighteen decimal places."
            ),
            (
                "A source quarantine, absent aggregate minute, or partition "
                "boundary withholds the complete feature vector."
            ),
            (
                "A quarantined or absent minute requires 133 subsequent contiguous "
                "valid minutes before feature readiness can resume."
            ),
            (
                "Official one-minute klines remain QA-only and cannot fill, carry, "
                "or overwrite an aggregate-trade feature value."
            ),
            (
                "The nine conformance cases use deterministic synthetic values "
                "only and contain no copied market observation or outcome."
            ),
            (
                "No future label, decision threshold, signal conjunction, entry "
                "rule, exit rule, stop, target, or sizing rule is defined."
            ),
            (
                "No future return, PnL, profit factor, expectancy, drawdown, or "
                "strategy outcome was calculated."
            ),
            (
                "Exact Pine parity remains unavailable because Pine has no exact "
                "Binance aggregate-trade aggressor stream."
            ),
            (
                "The earliest theoretical order time is the next minute only if "
                "later candidate, backtest, risk, and execution gates pass."
            ),
            (
                "This specification creates no strategy, signal, candidate, paper "
                "eligibility, Testnet order authority, production, live, capital, "
                "or profit authority."
            ),
        ],
    )


def write_specification(
    path: Path,
    specification: JamSuccessorFeatureSpecification,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = specification.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorFeatureSpecification.model_validate_json(serialized)
        != specification
    ):
        raise ValueError("Jam feature specification JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> JamSuccessorFeatureSpecification:
    if args.output.exists():
        raise ValueError("Jam feature specification exists; use --check")
    protocol = load_protocol(
        protocol_path=args.protocol,
        charter_path=args.charter,
        quality_protocol_path=args.quality_protocol,
        quality_result_path=args.quality_result,
        quality_audit_path=args.quality_audit,
        contamination_ledger_path=args.contamination_ledger,
    )
    specification = authoritative_specification(
        frozen_at=datetime.now(UTC),
        protocol=protocol,
        protocol_path=args.protocol,
    )
    write_specification(args.output, specification)
    print(
        f"WROTE {args.output} {specification.specification_evidence_hash} "
        f"features={specification.feature_count} "
        f"lookback={specification.maximum_lookback_minutes} "
        f"conformance={len(specification.conformance_cases)} returns=False",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamSuccessorFeatureSpecification:
    protocol = load_protocol(
        protocol_path=args.protocol,
        charter_path=args.charter,
        quality_protocol_path=args.quality_protocol,
        quality_result_path=args.quality_result,
        quality_audit_path=args.quality_audit,
        contamination_ledger_path=args.contamination_ledger,
    )
    specification = JamSuccessorFeatureSpecification.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_specification(
        frozen_at=specification.frozen_at,
        protocol=protocol,
        protocol_path=args.protocol,
    )
    if (
        specification != expected
        or not audit_jam_successor_feature_specification(specification)
    ):
        raise ValueError("Jam feature specification is not reproducible")
    print(
        "PASS "
        f"jam_feature_specification={specification.specification_evidence_hash} "
        f"conformance={specification.conformance_manifest_hash} "
        "market_rows=0 thresholds=0 returns=0 orders=0 live=False",
        flush=True,
    )
    return specification


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Jam successor feature specification."
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument(
        "--quality-protocol",
        type=Path,
        default=DEFAULT_QUALITY_PROTOCOL,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
    )
    parser.add_argument(
        "--quality-audit",
        type=Path,
        default=DEFAULT_QUALITY_AUDIT,
    )
    parser.add_argument(
        "--contamination-ledger",
        type=Path,
        default=DEFAULT_CONTAMINATION_LEDGER,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_check(args) if args.check else run_freeze(args)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
