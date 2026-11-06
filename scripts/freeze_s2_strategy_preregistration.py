from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import (  # noqa: E402
    S2FeasibilityBinding,
    build_hashed,
)
from aurex.backtest_engine.s2_development_measurement_execution import (  # noqa: E402
    S2_MEASUREMENT_PREREG_NEXT,
    S2DevelopmentMeasurementResult,
    S2DevelopmentMeasurementResultAudit,
)
from aurex.backtest_engine.s2_strategy_preregistration import (  # noqa: E402
    S2DevelopmentGate,
    S2StrategyCandidate,
    S2StrategyPreregistration,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_strategy_preregistration_v1.json")
MEASUREMENT_PROTOCOL_PATH = Path("data/evidence/s2_development_measurement_protocol_v1.json")
MEASUREMENT_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s2_development_measurement_protocol_audit_v1.json"
)
MEASUREMENT_EXECUTION_PATH = Path(
    "data/evidence/s2_development_measurement_execution_addendum_v1.json"
)
MEASUREMENT_EXECUTION_AUDIT_PATH = Path(
    "data/evidence/s2_development_measurement_execution_audit_v1.json"
)
MEASUREMENT_RESULT_PATH = Path("data/evidence/s2_development_measurement_result_v1.json")
MEASUREMENT_AUDIT_PATH = Path("data/evidence/s2_development_measurement_result_audit_v1.json")
MEASUREMENT_DATASET_PATH = Path("data/evidence/s2_development_measurements_v1.jsonl")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_strategy_preregistration.py")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(MODULE_PATH),
            "builder_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "builder_sha256": file_sha256(Path(__file__)),
        }
    )


def source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                MEASUREMENT_PROTOCOL_PATH,
                MEASUREMENT_PROTOCOL_AUDIT_PATH,
                MEASUREMENT_EXECUTION_PATH,
                MEASUREMENT_EXECUTION_AUDIT_PATH,
                MEASUREMENT_RESULT_PATH,
                MEASUREMENT_AUDIT_PATH,
                MEASUREMENT_DATASET_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def development_gates() -> tuple[S2DevelopmentGate, ...]:
    values = (
        ("EXACT_WEEKLY_INTERVAL_COUNT", "EQ", "272"),
        ("MINIMUM_POSITION_TRANSITIONS", "GE", "12"),
        ("MINIMUM_LONG_EXPOSURE_FRACTION", "GE", "0.15"),
        ("MAXIMUM_LONG_EXPOSURE_FRACTION", "LE", "0.85"),
        ("BASE_NET_TOTAL_RETURN_POSITIVE", "GT", "0"),
        ("STRESS_NET_TOTAL_RETURN_POSITIVE", "GT", "0"),
        ("BASE_PROFIT_FACTOR", "GE", "1.10"),
        ("STRESS_PROFIT_FACTOR", "GE", "1.00"),
        ("BASE_MAXIMUM_DRAWDOWN", "LE", "0.25"),
        ("STRESS_MAXIMUM_DRAWDOWN", "LE", "0.27"),
        ("POSITIVE_FULL_CALENDAR_YEARS", "GE", "3"),
        ("STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN", "GT", "0"),
        ("STRESS_WEEKLY_SHARPE", "GT", "0"),
        ("BASE_CALMAR_RATIO", "GE", "0.50"),
        ("BASE_MAXIMUM_DRAWDOWN_NOT_WORSE_THAN_BUY_AND_HOLD", "LE", "0"),
    )
    return tuple(
        S2DevelopmentGate(gate_id=gate_id, operator=operator, threshold=threshold)
        for gate_id, operator, threshold in values
    )


def build_protocol(*, frozen_at: datetime) -> S2StrategyPreregistration:
    result = S2DevelopmentMeasurementResult.model_validate_json(MEASUREMENT_RESULT_PATH.read_text())
    audit = S2DevelopmentMeasurementResultAudit.model_validate_json(
        MEASUREMENT_AUDIT_PATH.read_text()
    )
    paths = source_paths()
    if (
        result.next_authorization != "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RESULT_AUDIT_ONLY"
        or audit.next_authorization != S2_MEASUREMENT_PREREG_NEXT
        or file_sha256(MEASUREMENT_RESULT_PATH) != audit.result_file_sha256
        or result.result_evidence_hash != audit.result_evidence_hash
        or file_sha256(MEASUREMENT_DATASET_PATH) != result.measurement_dataset_file_sha256
        or result.measurement_dataset_file_sha256 != audit.measurement_dataset_file_sha256
        or result.measurement_dataset_bytes != MEASUREMENT_DATASET_PATH.stat().st_size
        or result.measurement_dataset_bytes != 130_754
        or result.measurement_row_count != 273
        or len(paths) != 7
        or not all(path.is_file() for path in paths)
    ):
        raise ValueError("S2 strategy preregistration basis did not reconcile")
    return build_hashed(
        S2StrategyPreregistration,
        "protocol_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "measurement_result_file_sha256": file_sha256(MEASUREMENT_RESULT_PATH),
            "measurement_result_evidence_hash": result.result_evidence_hash,
            "measurement_audit_file_sha256": file_sha256(MEASUREMENT_AUDIT_PATH),
            "measurement_audit_evidence_hash": audit.audit_evidence_hash,
            "measurement_dataset_file_sha256": result.measurement_dataset_file_sha256,
            "measurement_row_manifest_evidence_hash": (
                audit.measurement_row_manifest_evidence_hash
            ),
            "source_bindings": tuple(
                S2FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
                for path in paths
            ),
            "candidate": S2StrategyCandidate(),
            "development_gates": development_gates(),
            "limitations": tuple(
                sorted(
                    (
                        "All development BTC outcomes are outcome-aware and nonqualifying.",
                        (
                            "Both-broadening is an economic hypothesis, not evidence "
                            "of predictive edge."
                        ),
                        "Daily Binance archives require one exact Monday open per measurement row.",
                        (
                            "Development failure retires S2 without rescue candidates "
                            "or threshold tuning."
                        ),
                        (
                            "Historical screen, prospective validation, and future "
                            "holdout remain sealed."
                        ),
                        (
                            "One candidate and one parameter combination cannot be "
                            "expanded after outcomes."
                        ),
                        "Source acquisition must be separately frozen and checksum verified.",
                        (
                            "The development result cannot qualify paper, Testnet "
                            "strategy, or live use."
                        ),
                        "Trading costs are modeled at 15 bps per fill and stressed at 22.5 bps.",
                        "Zero market values or returns were read while freezing this protocol.",
                    )
                )
            ),
        },
    )


def write_protocol(path: Path, protocol: S2StrategyPreregistration) -> None:
    if path.exists():
        raise ValueError(f"S2 strategy preregistration exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2StrategyPreregistration.model_validate_json(serialized) != protocol:
        raise ValueError("S2 strategy preregistration did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze S2 strategy preregistration.")
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "measurement_rows_parsed=0 market_values=0 returns=0 candidates=1 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
