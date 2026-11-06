import argparse
import sys
from pathlib import Path

from aurex.backtest_engine.development_bundle import DevelopmentDatasetBundle
from aurex.backtest_engine.research_engine import R3ReplayMetrics
from aurex.backtest_engine.research_r4_engine import (
    R4ResearchReplayConfig,
    prepare_r4_market_data,
    run_r4_research_replay,
)
from aurex.backtest_engine.research_r4_execution_spec import (
    R4ExecutionSpecification,
)
from aurex.backtest_engine.research_r4_protocol import R4CandidateProtocol
from aurex.backtest_engine.research_r31_engine import R31ResearchReplayResult
from aurex.backtest_engine.research_study_runner import load_decision_market_data
from aurex.backtest_engine.validation_bundle import ValidationDatasetBundle

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_DEVELOPMENT_BUNDLE = (
    DEFAULT_EVIDENCE_ROOT / "development_4h_dataset_bundle_v1.json"
)
DEFAULT_R31_RESULT = (
    DEFAULT_EVIDENCE_ROOT
    / "r31_path_quality_results_v1"
    / "overall--xsmom_path_quality_84d_14d_primary--cost-1.json"
)
DEFAULT_R4_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_candidate_v1.json"
DEFAULT_VALIDATION_BUNDLE = (
    DEFAULT_EVIDENCE_ROOT / "validation_2025_4h_bundle_v1.json"
)
DEFAULT_R4_EXECUTION = (
    DEFAULT_EVIDENCE_ROOT / "r4_path_quality_execution_spec_v1.json"
)


def run_check(args) -> None:
    bundle = DevelopmentDatasetBundle.model_validate_json(
        args.development_bundle.read_text(encoding="utf-8")
    )
    expected = R31ResearchReplayResult.model_validate_json(
        args.r31_result.read_text(encoding="utf-8")
    )
    protocol = R4CandidateProtocol.model_validate_json(
        args.r4_protocol.read_text(encoding="utf-8")
    )
    validation_bundle = ValidationDatasetBundle.model_validate_json(
        args.validation_bundle.read_text(encoding="utf-8")
    )
    specification = R4ExecutionSpecification.model_validate_json(
        args.r4_execution.read_text(encoding="utf-8")
    )
    prepared_r31 = load_decision_market_data(
        bundle=bundle,
        evidence_root=args.evidence_root,
        decision_symbols=expected.config.baseline_decision_symbols,
    )
    split_index = prepared_r31.timestamps.index(expected.config.evaluation_start)
    development = {
        symbol: prepared_r31.candles_by_symbol[symbol][:split_index]
        for symbol in prepared_r31.symbols
    }
    known_evaluation = {
        symbol: prepared_r31.candles_by_symbol[symbol][split_index:]
        for symbol in prepared_r31.symbols
    }
    market_data = prepare_r4_market_data(
        development_by_symbol=development,
        validation_by_symbol=known_evaluation,
        validation_start=expected.config.evaluation_start,
        validation_end=expected.config.evaluation_end,
    )
    config = R4ResearchReplayConfig(
        evaluation_start=expected.config.evaluation_start,
        evaluation_end=expected.config.evaluation_end,
        baseline_decision_symbols=expected.config.baseline_decision_symbols,
        omitted_symbols=expected.config.omitted_symbols,
        cost_multiplier=expected.config.cost_multiplier,
        universe_manifest_evidence_hash=(
            expected.config.universe_manifest_evidence_hash
        ),
        development_dataset_bundle_evidence_hash=(
            expected.config.development_dataset_bundle_evidence_hash
        ),
        candidate_protocol_evidence_hash=protocol.protocol_evidence_hash,
        validation_dataset_bundle_evidence_hash=(
            validation_bundle.bundle_evidence_hash
        ),
        execution_specification_evidence_hash=(
            specification.specification_evidence_hash
        ),
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )
    actual = run_r4_research_replay(config, market_data)

    mismatches: list[str] = []
    if [item.model_dump() for item in actual.trades] != [
        item.model_dump() for item in expected.trades
    ]:
        mismatches.append("trades")
    if [item.model_dump() for item in actual.opportunities] != [
        item.model_dump() for item in expected.opportunities
    ]:
        mismatches.append("opportunities")
    if actual.equity_curve != expected.equity_curve:
        mismatches.append("equity_curve")
    for field in R3ReplayMetrics.model_fields:
        if getattr(actual.metrics, field) != getattr(expected.metrics, field):
            mismatches.append(f"metrics.{field}")
    if actual.availability_events:
        mismatches.append("unexpected_availability_events")
    if actual.metrics.termination_writeoff_count:
        mismatches.append("unexpected_termination_writeoffs")
    if mismatches:
        raise ValueError(
            "R4 differs from frozen R3.1 on known continuous data: "
            + ", ".join(mismatches)
        )
    print(
        "PASS "
        f"trades={len(actual.trades)} "
        f"opportunities={len(actual.opportunities)} "
        f"equity_points={len(actual.equity_curve)} "
        f"net_pl={actual.metrics.net_pl}",
        flush=True,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Prove R4 exactly reproduces frozen R3.1 on already-known continuous data."
        )
    )
    parser.add_argument(
        "--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT
    )
    parser.add_argument(
        "--development-bundle",
        type=Path,
        default=DEFAULT_DEVELOPMENT_BUNDLE,
    )
    parser.add_argument("--r31-result", type=Path, default=DEFAULT_R31_RESULT)
    parser.add_argument("--r4-protocol", type=Path, default=DEFAULT_R4_PROTOCOL)
    parser.add_argument(
        "--validation-bundle",
        type=Path,
        default=DEFAULT_VALIDATION_BUNDLE,
    )
    parser.add_argument("--r4-execution", type=Path, default=DEFAULT_R4_EXECUTION)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
