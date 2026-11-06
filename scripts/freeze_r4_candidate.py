import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    audit_development_dataset_bundle,
)
from aurex.backtest_engine.research_r4_protocol import (
    R4CandidateProtocol,
    R4KnownOutcomeBoundary,
    R4ReplayMatrix,
    R4SelectionControl,
    R4ValidationDataContract,
    R4ValidationFold,
    R4ValidationGates,
    audit_r4_candidate_protocol,
    build_r4_candidate_protocol,
)
from aurex.backtest_engine.research_r31_execution_spec import (
    R31ExecutionSpecification,
    audit_r31_execution_specification,
)
from aurex.backtest_engine.research_r31_result import (
    R31StudyResultLedger,
    audit_r31_study_result_ledger,
)
from aurex.backtest_engine.research_r31_run_package import (
    R31RunPackage,
    audit_r31_run_package,
)
from aurex.backtest_engine.research_r31_study import (
    R31MechanismStudyProtocol,
    audit_r31_mechanism_study_protocol,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)

try:
    from scripts.build_development_dataset_bundle import (
        builder_contract_hash as development_builder_contract_hash,
    )
    from scripts.build_development_dataset_bundle import expected_universe_roles
except ModuleNotFoundError:
    from build_development_dataset_bundle import (  # type: ignore[no-redef]
        builder_contract_hash as development_builder_contract_hash,
    )
    from build_development_dataset_bundle import (  # type: ignore[no-redef]
        expected_universe_roles,
    )

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_UNIVERSE = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_DEVELOPMENT_BUNDLE = (
    DEFAULT_EVIDENCE_ROOT / "development_4h_dataset_bundle_v1.json"
)
DEFAULT_R31_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_study_v1.json"
DEFAULT_R31_EXECUTION = (
    DEFAULT_EVIDENCE_ROOT / "r31_path_quality_execution_spec_v1.json"
)
DEFAULT_R31_PACKAGE = (
    DEFAULT_EVIDENCE_ROOT / "r31_path_quality_run_package_v1.json"
)
DEFAULT_R31_RESULT = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_result_v1.json"
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_candidate_v1.json"
R4_VALIDATION_DATA_GLOB = "validation_2025_4h*"
R4_RESULT_GLOBS = (
    "r4_path_quality_validation_result*.json",
    "r4_path_quality_validation_results*",
)


def find_artifacts(evidence_root: Path, patterns: tuple[str, ...]) -> list[str]:
    return sorted(
        {
            path.relative_to(evidence_root).as_posix()
            for pattern in patterns
            for path in evidence_root.glob(pattern)
        }
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_r4_candidate.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r4_protocol.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_parent_evidence(args):
    universe = MarketUniverseManifest.model_validate_json(
        args.universe.read_text(encoding="utf-8")
    )
    development = DevelopmentDatasetBundle.model_validate_json(
        args.development_bundle.read_text(encoding="utf-8")
    )
    r31_protocol = R31MechanismStudyProtocol.model_validate_json(
        args.r31_protocol.read_text(encoding="utf-8")
    )
    r31_execution = R31ExecutionSpecification.model_validate_json(
        args.r31_execution.read_text(encoding="utf-8")
    )
    r31_package = R31RunPackage.model_validate_json(
        args.r31_package.read_text(encoding="utf-8")
    )
    r31_result = R31StudyResultLedger.model_validate_json(
        args.r31_result.read_text(encoding="utf-8")
    )
    if audit_market_universe_manifest(universe)["status"] != "PASS":
        raise ValueError("R4 parent universe audit failed")
    development_audit = audit_development_dataset_bundle(
        development,
        evidence_root=args.evidence_root,
        expected_roles=expected_universe_roles(universe),
        current_builder_contract_hash=development_builder_contract_hash(),
    )
    if development_audit["status"] != "PASS" or development.status != "READY":
        raise ValueError("R4 parent development bundle audit failed")
    if not audit_r31_mechanism_study_protocol(r31_protocol):
        raise ValueError("R4 parent R3.1 protocol audit failed")
    if not audit_r31_execution_specification(r31_execution):
        raise ValueError("R4 parent R3.1 execution audit failed")
    if not audit_r31_run_package(r31_package):
        raise ValueError("R4 parent R3.1 package audit failed")
    if not audit_r31_study_result_ledger(r31_result):
        raise ValueError("R4 parent R3.1 result audit failed")
    if (
        r31_result.verdict != "PERMIT_R4_PREREGISTRATION"
        or not all(gate.passed for gate in r31_result.gates)
        or r31_result.creates_eligible_strategy
        or r31_result.opens_validation_partition
    ):
        raise ValueError("R3.1 evidence does not authorize R4 preregistration")
    if r31_protocol.universe_manifest_evidence_hash != universe.manifest_evidence_hash:
        raise ValueError("R3.1 protocol universe binding changed")
    if (
        r31_protocol.development_dataset_bundle_evidence_hash
        != development.bundle_evidence_hash
    ):
        raise ValueError("R3.1 protocol development binding changed")
    if r31_execution.protocol_evidence_hash != r31_protocol.protocol_evidence_hash:
        raise ValueError("R3.1 execution/protocol binding changed")
    if r31_package.protocol_evidence_hash != r31_protocol.protocol_evidence_hash:
        raise ValueError("R3.1 package/protocol binding changed")
    if (
        r31_package.execution_specification_evidence_hash
        != r31_execution.specification_evidence_hash
    ):
        raise ValueError("R3.1 package/execution binding changed")
    if r31_result.run_package_evidence_hash != r31_package.package_evidence_hash:
        raise ValueError("R3.1 result/package binding changed")
    return (
        universe,
        development,
        r31_protocol,
        r31_execution,
        r31_package,
        r31_result,
    )


def authoritative_protocol(*, registered_at: datetime, parents) -> R4CandidateProtocol:
    universe, development, r31_protocol, r31_execution, r31_package, r31_result = (
        parents
    )
    return build_r4_candidate_protocol(
        registered_at=registered_at,
        hypothesis=(
            "The unchanged Aurex path-quality spot strategy that passed every frozen "
            "R3.1 development gate will retain positive cost-net expectancy, bounded "
            "drawdown, temporal breadth, cross-market breadth, and concentration "
            "control during the untouched 2025 Binance spot validation partition."
        ),
        falsification_claim=(
            "R4 is rejected if validation data violate the frozen integrity contract "
            "or if the unchanged candidate misses any profitability, profit-factor, "
            "drawdown, sample-size, quarterly, double-cost, leave-one-market-out, or "
            "concentration gate. No parameter, symbol replacement, rescue variant, "
            "gate change, or 2026 holdout inspection is allowed after registration."
        ),
        known_outcome_boundary=R4KnownOutcomeBoundary(),
        parent_r31_protocol_evidence_hash=r31_protocol.protocol_evidence_hash,
        parent_r31_execution_specification_evidence_hash=(
            r31_execution.specification_evidence_hash
        ),
        parent_r31_run_package_evidence_hash=r31_package.package_evidence_hash,
        parent_r31_result_ledger_evidence_hash=r31_result.ledger_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=development.bundle_evidence_hash,
        contamination_ledger_hash=universe.rule.contamination_ledger_hash,
        builder_contract_hash=builder_contract_hash(),
        decision_symbols=r31_protocol.decision_symbols,
        signal=r31_protocol.signal,
        portfolio=r31_protocol.portfolio,
        costs=r31_protocol.costs,
        validation_data=R4ValidationDataContract(
            partition_start="2025-01-01T00:00:00Z",
            partition_end="2026-01-01T00:00:00Z",
            required_archive_months=[
                f"2025-{month:02d}" for month in range(1, 13)
            ],
            warmup_ends_at="2025-01-01T00:00:00Z",
            inspected_market_fields=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
            strategy_outcome_fields_inspected=[],
            accepted_availability_shapes=[
                "FULL_CONTINUOUS",
                "CONTIGUOUS_TERMINAL_SUFFIX_MISSING",
            ],
        ),
        folds=[
            R4ValidationFold(
                fold_id="validation-fold-01-2025q1",
                evaluation_start="2025-01-01T00:00:00Z",
                evaluation_end="2025-04-01T00:00:00Z",
            ),
            R4ValidationFold(
                fold_id="validation-fold-02-2025q2",
                evaluation_start="2025-04-01T00:00:00Z",
                evaluation_end="2025-07-01T00:00:00Z",
            ),
            R4ValidationFold(
                fold_id="validation-fold-03-2025q3",
                evaluation_start="2025-07-01T00:00:00Z",
                evaluation_end="2025-10-01T00:00:00Z",
            ),
            R4ValidationFold(
                fold_id="validation-fold-04-2025q4",
                evaluation_start="2025-10-01T00:00:00Z",
                evaluation_end="2026-01-01T00:00:00Z",
            ),
        ],
        gates=R4ValidationGates(),
        replay_matrix=R4ReplayMatrix(
            overall_cost_multipliers=["1", "1.5", "2"],
        ),
        selection_control=R4SelectionControl(),
        required_diagnostics=[
            "accepted_and_rejected_opportunities",
            "active_symbol_count_at_each_rebalance",
            "cost_decomposition",
            "cost_stress",
            "drawdown_and_exposure_over_time",
            "leave_one_market_out",
            "market_termination_writeoffs",
            "monthly_net_returns",
            "ols_slope_and_r_squared_at_rebalance",
            "quarterly_fold_results",
            "score_distribution_at_rebalance",
            "symbol_gross_profit_concentration",
            "turnover",
        ],
        preexisting_validation_data_artifacts=[],
        preexisting_r4_result_artifacts=[],
        validation_outcome_fields_inspected=[],
    )


def write_protocol(path: Path, protocol: R4CandidateProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if R4CandidateProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("R4 candidate protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R4CandidateProtocol:
    if args.output.exists():
        raise ValueError("Frozen R4 candidate exists; use --check")
    validation_data = find_artifacts(
        args.evidence_root, (R4_VALIDATION_DATA_GLOB,)
    )
    results = find_artifacts(args.evidence_root, R4_RESULT_GLOBS)
    if validation_data or results:
        raise ValueError(
            "R4 candidate registration must predate validation data and outcomes"
        )
    protocol = authoritative_protocol(
        registered_at=datetime.now(UTC),
        parents=load_parent_evidence(args),
    )
    write_protocol(args.output, protocol)
    stored = R4CandidateProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != protocol or not audit_r4_candidate_protocol(stored):
        raise ValueError("R4 candidate failed reload audit")
    print(
        f"WROTE {args.output} {stored.protocol_evidence_hash} "
        f"candidate={stored.candidate_id}@{stored.candidate_version}",
        flush=True,
    )
    return stored


def run_check(args) -> R4CandidateProtocol:
    stored = R4CandidateProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        registered_at=stored.registered_at,
        parents=load_parent_evidence(args),
    )
    if stored != expected or not audit_r4_candidate_protocol(stored):
        raise ValueError("Stored R4 candidate differs from authoritative rebuild")
    print(
        "PASS "
        f"r4_candidate={stored.protocol_evidence_hash} "
        f"symbols={len(stored.decision_symbols)} "
        f"runs={stored.replay_matrix.expected_total_runs}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome R4 validation candidate."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument(
        "--development-bundle",
        type=Path,
        default=DEFAULT_DEVELOPMENT_BUNDLE,
    )
    parser.add_argument("--r31-protocol", type=Path, default=DEFAULT_R31_PROTOCOL)
    parser.add_argument("--r31-execution", type=Path, default=DEFAULT_R31_EXECUTION)
    parser.add_argument("--r31-package", type=Path, default=DEFAULT_R31_PACKAGE)
    parser.add_argument("--r31-result", type=Path, default=DEFAULT_R31_RESULT)
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
