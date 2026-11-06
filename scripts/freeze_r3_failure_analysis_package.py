import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.development_bundle import DevelopmentDatasetBundle
from aurex.backtest_engine.research_diagnostic_addendum import (
    R3MonthlyDiagnosticAddendum,
)
from aurex.backtest_engine.research_failure_analysis import (
    R3_FAILURE_SOURCE_FILES,
    R3FailureAnalysisPackage,
    audit_r3_failure_analysis_package,
    build_r3_failure_analysis_package,
)
from aurex.backtest_engine.research_failure_protocol import (
    R3FailureAnalysisProtocol,
    audit_r3_failure_analysis_protocol,
)
from aurex.backtest_engine.research_result import R3StudyResultLedger
from aurex.backtest_engine.universe import universe_evidence_hash

try:
    from scripts.freeze_r3_failure_analysis import (
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_MONTHLY_ADDENDUM,
        DEFAULT_RESULT_LEDGER,
    )
    from scripts.freeze_r3_failure_analysis import (
        DEFAULT_OUTPUT as DEFAULT_FAILURE_PROTOCOL,
    )
    from scripts.freeze_r3_failure_analysis import (
        builder_contract_hash as failure_protocol_builder_contract_hash,
    )
    from scripts.freeze_r3_mechanism_study import DEFAULT_DATASET_BUNDLE
except ModuleNotFoundError:
    from freeze_r3_failure_analysis import (  # type: ignore[no-redef]
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_MONTHLY_ADDENDUM,
        DEFAULT_RESULT_LEDGER,
    )
    from freeze_r3_failure_analysis import (
        DEFAULT_OUTPUT as DEFAULT_FAILURE_PROTOCOL,
    )
    from freeze_r3_failure_analysis import (
        builder_contract_hash as failure_protocol_builder_contract_hash,
    )
    from freeze_r3_mechanism_study import (  # type: ignore[no-redef]
        DEFAULT_DATASET_BUNDLE,
    )

DEFAULT_PACKAGE_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r3_failure_analysis_package_v1.json"
DEFAULT_RESULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r3_failure_analysis_result_v1.json"


def source_file_hashes(project_root: Path) -> dict[str, str]:
    return {
        relative_path: hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        for relative_path in R3_FAILURE_SOURCE_FILES
    }


def load_inputs(args):
    protocol = R3FailureAnalysisProtocol.model_validate_json(
        args.failure_protocol.read_text(encoding="utf-8")
    )
    ledger = R3StudyResultLedger.model_validate_json(
        args.result_ledger.read_text(encoding="utf-8")
    )
    addendum = R3MonthlyDiagnosticAddendum.model_validate_json(
        args.monthly_addendum.read_text(encoding="utf-8")
    )
    bundle = DevelopmentDatasetBundle.model_validate_json(
        args.dataset_bundle.read_text(encoding="utf-8")
    )
    if not audit_r3_failure_analysis_protocol(protocol):
        raise ValueError("R3 failure protocol failed its hash audit")
    if protocol.builder_contract_hash != failure_protocol_builder_contract_hash():
        raise ValueError("R3 failure-protocol builder contract changed")
    if protocol.result_ledger_evidence_hash != ledger.ledger_evidence_hash:
        raise ValueError("R3 failure protocol does not match the result ledger")
    if protocol.monthly_addendum_evidence_hash != addendum.addendum_evidence_hash:
        raise ValueError("R3 failure protocol does not match the monthly addendum")
    if (
        protocol.development_dataset_bundle_evidence_hash
        != bundle.bundle_evidence_hash
    ):
        raise ValueError("R3 failure protocol does not match the development bundle")
    return protocol, ledger, addendum, bundle


def authoritative_package(
    *,
    frozen_at: datetime,
    protocol: R3FailureAnalysisProtocol,
    ledger: R3StudyResultLedger,
    addendum: R3MonthlyDiagnosticAddendum,
    bundle: DevelopmentDatasetBundle,
) -> R3FailureAnalysisPackage:
    project_root = Path(__file__).resolve().parents[1]
    return build_r3_failure_analysis_package(
        package_id="r3-cross-sectional-momentum-failure-analysis-package-v1",
        package_version="1.0.0",
        frozen_at=frozen_at,
        status="FROZEN_POST_OUTCOME_PRE_ANALYSIS",
        failure_protocol_evidence_hash=protocol.protocol_evidence_hash,
        result_ledger_evidence_hash=ledger.ledger_evidence_hash,
        monthly_addendum_evidence_hash=addendum.addendum_evidence_hash,
        development_dataset_bundle_evidence_hash=bundle.bundle_evidence_hash,
        source_file_sha256=source_file_hashes(project_root),
        decimal_precision=50,
        decimal_rounding="ROUND_HALF_EVEN",
        quarter_source="INDEPENDENT_FOLD_REPLAYS",
        trade_quarter_attribution="FOLD_ARTIFACT_MEMBERSHIP",
        diagnostic_return_formula="LAST_CLOSE_DIVIDED_BY_FIRST_OPEN_MINUS_ONE",
        diagnostic_volatility_formula=(
            "SAMPLE_STDDEV_LOG_RETURNS_TIMES_SQRT_2190"
        ),
        breadth_formula=(
            "COUNT_STRICTLY_POSITIVE_SCORES_AT_PRIMARY_BASE_REBALANCE"
        ),
        drawdown_episode_formula=(
            "CONTIGUOUS_POSITIVE_DRAWDOWN_SNAPSHOTS_CLOSED_AT_ZERO_OR_WINDOW_END"
        ),
        symbol_contribution_formula="SUM_FOLD_TRADE_NET_AND_RAW_PL_BY_SYMBOL",
        next_decision_rule=(
            "PROPOSE_ONLY_IF_ALL_DESCRIPTIVE_CONTINUATION_CRITERIA_PASS_ELSE_STOP"
        ),
        continuation_criteria=[
            "ALL_THREE_HORIZONS_POSITIVE_AT_BASE_AND_DOUBLE_COST",
            "HORIZON_POSITIVE_FOLDS_STRICTLY_IMPROVE_FAST_TO_PRIMARY_TO_SLOW",
            "PRIMARY_CONCENTRATION_GATES_PASSED",
            "PRIMARY_LEAVE_ONE_MARKET_OUT_FRACTION_AT_LEAST_0_80",
            "PRIMARY_TEMPORAL_GATE_REMAINS_FAILED_AND_UNCHANGED",
        ],
        expected_result_relative_path="r3_failure_analysis_result_v1.json",
        preexisting_analysis_artifacts=[],
        builder_contract_hash=builder_contract_hash(),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r3_failure_analysis_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_failure_analysis.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_failure_runner.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in contract_paths
            }
        }
    )


def write_package(path: Path, package: R3FailureAnalysisPackage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(package.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R3FailureAnalysisPackage:
    if args.package_output.exists():
        raise ValueError("R3 failure-analysis package already exists; use --check")
    if args.result_output.exists():
        raise ValueError("R3 failure-analysis result predates its package")
    protocol, ledger, addendum, bundle = load_inputs(args)
    package = authoritative_package(
        frozen_at=datetime.now(UTC),
        protocol=protocol,
        ledger=ledger,
        addendum=addendum,
        bundle=bundle,
    )
    write_package(args.package_output, package)
    stored = R3FailureAnalysisPackage.model_validate_json(
        args.package_output.read_text(encoding="utf-8")
    )
    if stored != package or not audit_r3_failure_analysis_package(stored):
        raise ValueError("R3 failure-analysis package failed reload verification")
    print(f"WROTE {args.package_output} {stored.package_evidence_hash}", flush=True)
    return stored


def run_check(args) -> R3FailureAnalysisPackage:
    protocol, ledger, addendum, bundle = load_inputs(args)
    stored = R3FailureAnalysisPackage.model_validate_json(
        args.package_output.read_text(encoding="utf-8")
    )
    expected = authoritative_package(
        frozen_at=stored.frozen_at,
        protocol=protocol,
        ledger=ledger,
        addendum=addendum,
        bundle=bundle,
    )
    if stored != expected or not audit_r3_failure_analysis_package(stored):
        raise ValueError("Stored R3 failure package differs from its rebuild")
    print(
        "PASS "
        f"failure_package={stored.package_evidence_hash} "
        f"sources={len(stored.source_file_sha256)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the R3 descriptive failure-analysis package."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--failure-protocol", type=Path, default=DEFAULT_FAILURE_PROTOCOL
    )
    parser.add_argument("--result-ledger", type=Path, default=DEFAULT_RESULT_LEDGER)
    parser.add_argument(
        "--monthly-addendum", type=Path, default=DEFAULT_MONTHLY_ADDENDUM
    )
    parser.add_argument("--dataset-bundle", type=Path, default=DEFAULT_DATASET_BUNDLE)
    parser.add_argument("--package-output", type=Path, default=DEFAULT_PACKAGE_OUTPUT)
    parser.add_argument("--result-output", type=Path, default=DEFAULT_RESULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            run_freeze(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
