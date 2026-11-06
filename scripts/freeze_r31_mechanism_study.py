import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.development_bundle import DevelopmentDatasetBundle
from aurex.backtest_engine.research_execution_spec import (
    R3ExecutionSpecification,
    audit_r3_execution_specification,
)
from aurex.backtest_engine.research_failure_analysis import (
    R3FailureAnalysisPackage,
    R3FailureAnalysisResult,
    audit_r3_failure_analysis_package,
    audit_r3_failure_analysis_result,
)
from aurex.backtest_engine.research_failure_protocol import (
    R3FailureAnalysisProtocol,
    audit_r3_failure_analysis_protocol,
)
from aurex.backtest_engine.research_r31_study import (
    R31_REQUIRED_DIAGNOSTICS,
    R31AdvancementGates,
    R31CostModel,
    R31ExternalEvidence,
    R31KnownOutcomeBoundary,
    R31MechanismStudyProtocol,
    R31PortfolioConstruction,
    R31SelectionControl,
    R31SignalDefinition,
    R31StudyFold,
    audit_r31_mechanism_study_protocol,
    build_r31_mechanism_study_protocol,
)
from aurex.backtest_engine.research_result import R3StudyResultLedger
from aurex.backtest_engine.research_study import (
    R3MechanismStudyProtocol,
    audit_r3_mechanism_study_protocol,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    universe_evidence_hash,
)

try:
    from scripts.freeze_r3_mechanism_study import load_verified_inputs
except ModuleNotFoundError:
    from freeze_r3_mechanism_study import load_verified_inputs  # type: ignore[no-redef]

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_UNIVERSE = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_BUNDLE = DEFAULT_EVIDENCE_ROOT / "development_4h_dataset_bundle_v1.json"
DEFAULT_R3_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_study_v1.json"
)
DEFAULT_R3_EXECUTION = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_execution_spec_v1.json"
)
DEFAULT_R3_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_result_v1.json"
)
DEFAULT_FAILURE_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "r3_failure_analysis_protocol_v1.json"
DEFAULT_FAILURE_PACKAGE = DEFAULT_EVIDENCE_ROOT / "r3_failure_analysis_package_v1.json"
DEFAULT_FAILURE_RESULT = DEFAULT_EVIDENCE_ROOT / "r3_failure_analysis_result_v1.json"
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_study_v1.json"
R31_RESULT_GLOB = "r31_path_quality_result*.json"


def load_parent_evidence(args):
    universe, bundle = load_verified_inputs(
        evidence_root=args.evidence_root,
        universe_path=args.universe,
        bundle_path=args.bundle,
    )
    r3_protocol = R3MechanismStudyProtocol.model_validate_json(
        args.r3_protocol.read_text(encoding="utf-8")
    )
    r3_execution = R3ExecutionSpecification.model_validate_json(
        args.r3_execution.read_text(encoding="utf-8")
    )
    r3_result = R3StudyResultLedger.model_validate_json(
        args.r3_result.read_text(encoding="utf-8")
    )
    failure_protocol = R3FailureAnalysisProtocol.model_validate_json(
        args.failure_protocol.read_text(encoding="utf-8")
    )
    failure_package = R3FailureAnalysisPackage.model_validate_json(
        args.failure_package.read_text(encoding="utf-8")
    )
    failure_result = R3FailureAnalysisResult.model_validate_json(
        args.failure_result.read_text(encoding="utf-8")
    )
    if not audit_r3_mechanism_study_protocol(r3_protocol):
        raise ValueError("R3.1 parent study protocol failed its audit")
    if not audit_r3_execution_specification(r3_execution):
        raise ValueError("R3.1 parent execution specification failed its audit")
    if not audit_r3_failure_analysis_protocol(failure_protocol):
        raise ValueError("R3.1 failure protocol failed its audit")
    if not audit_r3_failure_analysis_package(failure_package):
        raise ValueError("R3.1 failure package failed its audit")
    if not audit_r3_failure_analysis_result(failure_result):
        raise ValueError("R3.1 failure result failed its audit")
    if r3_result.verdict != "NO_CANDIDATE":
        raise ValueError("R3.1 requires the immutable R3 NO_CANDIDATE verdict")
    if failure_result.next_research_decision != "PROPOSE_BOUNDED_R3_1":
        raise ValueError("Frozen failure analysis does not authorize R3.1")
    if failure_result.creates_candidate or failure_result.opens_sealed_partition:
        raise ValueError("R3.1 parent analysis crossed a prohibited boundary")
    if r3_execution.protocol_evidence_hash != r3_protocol.protocol_evidence_hash:
        raise ValueError("R3.1 parent execution specification does not match R3")
    if r3_result.protocol_evidence_hash != r3_protocol.protocol_evidence_hash:
        raise ValueError("R3.1 parent result does not match the R3 protocol")
    if (
        failure_protocol.result_ledger_evidence_hash != r3_result.ledger_evidence_hash
        or failure_package.result_ledger_evidence_hash != r3_result.ledger_evidence_hash
        or failure_result.result_ledger_evidence_hash != r3_result.ledger_evidence_hash
    ):
        raise ValueError("R3.1 failure evidence does not bind the parent result")
    return (
        universe,
        bundle,
        r3_protocol,
        r3_execution,
        r3_result,
        failure_protocol,
        failure_package,
        failure_result,
    )


def authoritative_protocol(
    *,
    registered_at: datetime,
    universe: MarketUniverseManifest,
    bundle: DevelopmentDatasetBundle,
    r3_protocol: R3MechanismStudyProtocol,
    r3_execution: R3ExecutionSpecification,
    r3_result: R3StudyResultLedger,
    failure_protocol: R3FailureAnalysisProtocol,
    failure_package: R3FailureAnalysisPackage,
    failure_result: R3FailureAnalysisResult,
) -> R31MechanismStudyProtocol:
    return build_r31_mechanism_study_protocol(
        study_id="r3.1-cross-sectional-path-quality-spot-v1",
        study_version="1.0.0",
        registered_at=registered_at,
        status="FROZEN_PRE_R31_OUTCOME",
        research_class="DEVELOPMENT_ONLY_MECHANISM_FOLLOW_UP",
        mechanism_family="CROSS_SECTIONAL_MOMENTUM_PATH_QUALITY",
        hypothesis=(
            "For the fixed Aurex 84-day formation and 14-day rebalance schedule, "
            "cross-sectional ranking by a positive, path-consistent log-price trend "
            "will be temporally more reliable after costs than ranking by endpoint "
            "return because gradual price adjustment should produce both a stronger "
            "positive slope and higher regression fit, while isolated jumps and noisy "
            "reversals should receive weaker scores."
        ),
        falsification_claim=(
            "The path-quality mechanism is not supported if its single fixed primary "
            "misses any preregistered profitability, drawdown, trade-count, 4-of-6 "
            "quarter, double-cost, leave-one-market-out, or concentration gate. A "
            "failure stops this cross-sectional momentum family without a rescue "
            "variant, parameter change, gate change, or sealed-data inspection."
        ),
        known_outcome_boundary=R31KnownOutcomeBoundary(),
        parent_r3_protocol_evidence_hash=r3_protocol.protocol_evidence_hash,
        parent_r3_execution_spec_evidence_hash=r3_execution.specification_evidence_hash,
        parent_r3_result_ledger_evidence_hash=r3_result.ledger_evidence_hash,
        failure_protocol_evidence_hash=failure_protocol.protocol_evidence_hash,
        failure_package_evidence_hash=failure_package.package_evidence_hash,
        failure_result_evidence_hash=failure_result.result_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=bundle.bundle_evidence_hash,
        contamination_ledger_hash=universe.rule.contamination_ledger_hash,
        builder_contract_hash=builder_contract_hash(),
        venue="BINANCE",
        market_type="SPOT",
        quote_asset="USDT",
        timeframe="4h",
        development_data_start=bundle.partition_start,
        development_data_end=bundle.partition_end,
        evaluation_start="2023-07-01T00:00:00Z",
        evaluation_end="2025-01-01T00:00:00Z",
        decision_symbols=universe.summary.decision_symbols,
        diagnostic_only_symbols=universe.summary.development_only_symbols,
        forbidden_partitions=["VALIDATION", "HOLDOUT", "FORWARD"],
        signal=R31SignalDefinition(),
        folds=[
            R31StudyFold(
                fold_id="fold-01-2023q3",
                evaluation_start="2023-07-01T00:00:00Z",
                evaluation_end="2023-10-01T00:00:00Z",
            ),
            R31StudyFold(
                fold_id="fold-02-2023q4",
                evaluation_start="2023-10-01T00:00:00Z",
                evaluation_end="2024-01-01T00:00:00Z",
            ),
            R31StudyFold(
                fold_id="fold-03-2024q1",
                evaluation_start="2024-01-01T00:00:00Z",
                evaluation_end="2024-04-01T00:00:00Z",
            ),
            R31StudyFold(
                fold_id="fold-04-2024q2",
                evaluation_start="2024-04-01T00:00:00Z",
                evaluation_end="2024-07-01T00:00:00Z",
            ),
            R31StudyFold(
                fold_id="fold-05-2024q3",
                evaluation_start="2024-07-01T00:00:00Z",
                evaluation_end="2024-10-01T00:00:00Z",
            ),
            R31StudyFold(
                fold_id="fold-06-2024q4",
                evaluation_start="2024-10-01T00:00:00Z",
                evaluation_end="2025-01-01T00:00:00Z",
            ),
        ],
        portfolio=R31PortfolioConstruction(),
        costs=R31CostModel(stress_multipliers=["1", "1.5", "2"]),
        gates=R31AdvancementGates(),
        selection_control=R31SelectionControl(),
        required_diagnostics=list(R31_REQUIRED_DIAGNOSTICS),
        external_evidence=[
            R31ExternalEvidence(
                evidence_id="CRYPTO_CROSS_SECTIONAL_FACTOR",
                citation=(
                    "Liu, Tsyvinski, and Wu (2022), Common Risk Factors in "
                    "Cryptocurrency, Journal of Finance 77(2), 1133-1177."
                ),
                url="https://www.nber.org/papers/w25882",
                relevance=(
                    "Documents cryptocurrency market, size, and momentum factors and "
                    "supports testing cross-sectional momentum as an economic mechanism."
                ),
                limitation=(
                    "Its factor evidence is not a guarantee that Aurex's long-only, "
                    "costed spot implementation or this exact signal has positive edge."
                ),
            ),
            R31ExternalEvidence(
                evidence_id="CRYPTO_MOMENTUM_REVERSAL",
                citation=(
                    "Dobrynskaya (2023), Cryptocurrency Momentum and Reversal, "
                    "Journal of Alternative Investments 26(1), 65-76."
                ),
                url="https://doi.org/10.3905/jai.2023.1.189",
                relevance=(
                    "Finds crypto momentum and reversal vary materially by formation "
                    "and holding horizon, supporting strict temporal falsification."
                ),
                limitation=(
                    "Its broad 2014-2020 universe and long-short portfolio construction "
                    "differ from Aurex and argue against assuming slow momentum persists."
                ),
            ),
            R31ExternalEvidence(
                evidence_id="CRYPTO_REALISTIC_ASSUMPTIONS",
                citation=(
                    "Han, Kang, and Ryu (2026 revision), Momentum in the "
                    "Cryptocurrency Market: A Comprehensive Analysis under Realistic "
                    "Assumptions."
                ),
                url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565",
                relevance=(
                    "Reports weak cross-sectional momentum under realistic costs and "
                    "fat-tailed outcomes, supporting the all-gates stop rule."
                ),
                limitation=(
                    "Its design and leverage assumptions differ from Aurex; it is "
                    "adverse prior evidence, not proof that this study must fail."
                ),
            ),
            R31ExternalEvidence(
                evidence_id="MOMENTUM_PRICE_PATH",
                citation=(
                    "Grinblatt and Han (2005), Prospect Theory, Mental Accounting, "
                    "and Momentum, Journal of Financial Economics 78(2), 311-339."
                ),
                url="https://www.nber.org/papers/w8734",
                relevance=(
                    "Provides a behavioral mechanism in which momentum profitability "
                    "depends on the path of past prices, motivating a path-aware signal."
                ),
                limitation=(
                    "The evidence is from equities and does not validate OLS trend "
                    "quality in cryptocurrency; R3.1 must earn support from its gates."
                ),
            ),
        ],
        preexisting_r31_result_artifacts=[],
        r31_outcome_fields_inspected=[],
        decision_rule=(
            "IF_ALL_GATES_PASS_FREEZE_SEPARATE_R4_CANDIDATE_ELSE_STOP_FAMILY"
        ),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r31_mechanism_study.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r31_study.py",
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


def find_r31_result_artifacts(evidence_root: Path) -> list[str]:
    return sorted(
        path.relative_to(evidence_root).as_posix()
        for path in evidence_root.glob(R31_RESULT_GLOB)
        if path.is_file()
    )


def write_protocol(path: Path, protocol: R31MechanismStudyProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if R31MechanismStudyProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("R3.1 protocol JSON does not round-trip before commit")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R31MechanismStudyProtocol:
    if args.output.exists():
        raise ValueError("Frozen R3.1 protocol already exists; use --check")
    result_artifacts = find_r31_result_artifacts(args.evidence_root)
    if result_artifacts:
        raise ValueError(f"R3.1 result predates its protocol: {result_artifacts}")
    inputs = load_parent_evidence(args)
    protocol = authoritative_protocol(
        registered_at=datetime.now(UTC),
        universe=inputs[0],
        bundle=inputs[1],
        r3_protocol=inputs[2],
        r3_execution=inputs[3],
        r3_result=inputs[4],
        failure_protocol=inputs[5],
        failure_package=inputs[6],
        failure_result=inputs[7],
    )
    write_protocol(args.output, protocol)
    stored = R31MechanismStudyProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != protocol or not audit_r31_mechanism_study_protocol(stored):
        raise ValueError("R3.1 protocol failed reload verification")
    print(f"WROTE {args.output} {stored.protocol_evidence_hash}", flush=True)
    return stored


def run_check(args) -> R31MechanismStudyProtocol:
    inputs = load_parent_evidence(args)
    stored = R31MechanismStudyProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        registered_at=stored.registered_at,
        universe=inputs[0],
        bundle=inputs[1],
        r3_protocol=inputs[2],
        r3_execution=inputs[3],
        r3_result=inputs[4],
        failure_protocol=inputs[5],
        failure_package=inputs[6],
        failure_result=inputs[7],
    )
    if stored != expected or not audit_r31_mechanism_study_protocol(stored):
        raise ValueError("Stored R3.1 protocol differs from its authoritative rebuild")
    print(
        "PASS "
        f"r31_protocol={stored.protocol_evidence_hash} "
        f"selectable={stored.selection_control.selectable_primary_count} "
        f"folds={len(stored.folds)} sealed={len(stored.forbidden_partitions)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome Aurex R3.1 mechanism study."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--r3-protocol", type=Path, default=DEFAULT_R3_PROTOCOL)
    parser.add_argument("--r3-execution", type=Path, default=DEFAULT_R3_EXECUTION)
    parser.add_argument("--r3-result", type=Path, default=DEFAULT_R3_RESULT)
    parser.add_argument(
        "--failure-protocol", type=Path, default=DEFAULT_FAILURE_PROTOCOL
    )
    parser.add_argument("--failure-package", type=Path, default=DEFAULT_FAILURE_PACKAGE)
    parser.add_argument("--failure-result", type=Path, default=DEFAULT_FAILURE_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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
