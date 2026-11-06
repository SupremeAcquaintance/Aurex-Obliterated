import argparse
import hashlib
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pydantic

from aurex.backtest_engine.research_r4_execution_spec import (
    R4ExecutionSpecification,
    audit_r4_execution_specification,
)
from aurex.backtest_engine.research_r4_protocol import (
    R4CandidateProtocol,
    audit_r4_candidate_protocol,
)
from aurex.backtest_engine.research_r4_run_package import (
    R4_SOURCE_FILES,
    R4RunPackage,
    audit_r4_run_package,
    build_r4_run_package,
)
from aurex.backtest_engine.research_r4_study_runner import (
    build_planned_replays,
    load_r4_market_data,
)
from aurex.backtest_engine.research_r31_engine import R31ResearchReplayResult
from aurex.backtest_engine.universe import universe_evidence_hash
from aurex.backtest_engine.validation_bundle import (
    ValidationDatasetBundle,
    audit_validation_dataset_bundle,
)

try:
    from scripts.build_validation_dataset_bundle import (
        DEFAULT_OUTPUT as DEFAULT_VALIDATION_BUNDLE,
    )
    from scripts.build_validation_dataset_bundle import (
        builder_contract_hash as validation_builder_contract_hash,
    )
    from scripts.freeze_r3_mechanism_study import load_verified_inputs
    from scripts.freeze_r4_candidate import DEFAULT_OUTPUT as DEFAULT_PROTOCOL
    from scripts.freeze_r4_execution_spec import (
        DEFAULT_OUTPUT as DEFAULT_EXECUTION,
    )
    from scripts.freeze_r31_mechanism_study import (
        DEFAULT_BUNDLE as DEFAULT_DEVELOPMENT_BUNDLE,
    )
    from scripts.freeze_r31_mechanism_study import (
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_UNIVERSE,
    )
except ModuleNotFoundError:
    from build_validation_dataset_bundle import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT as DEFAULT_VALIDATION_BUNDLE,
    )
    from build_validation_dataset_bundle import (  # type: ignore[no-redef]
        builder_contract_hash as validation_builder_contract_hash,
    )
    from freeze_r3_mechanism_study import (  # type: ignore[no-redef]
        load_verified_inputs,
    )
    from freeze_r4_candidate import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
    )
    from freeze_r4_execution_spec import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT as DEFAULT_EXECUTION,
    )
    from freeze_r31_mechanism_study import (  # type: ignore[no-redef]
        DEFAULT_BUNDLE as DEFAULT_DEVELOPMENT_BUNDLE,
    )
    from freeze_r31_mechanism_study import (  # type: ignore[no-redef]
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_UNIVERSE,
    )

DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_run_package_v1.json"
DEFAULT_RESULT = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_result_v1.json"
DEFAULT_RESULTS_DIRECTORY = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_results_v1"
DEFAULT_R31_REGRESSION_RESULT = (
    DEFAULT_EVIDENCE_ROOT
    / "r31_path_quality_results_v1"
    / "overall--xsmom_path_quality_84d_14d_primary--cost-1.json"
)


def source_file_hashes(project_root: Path) -> dict[str, str]:
    return {
        relative_path: hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        for relative_path in R4_SOURCE_FILES
    }


def load_package_inputs(args):
    universe, development_bundle = load_verified_inputs(
        evidence_root=args.evidence_root,
        universe_path=args.universe,
        bundle_path=args.development_bundle,
    )
    protocol = R4CandidateProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    validation_bundle = ValidationDatasetBundle.model_validate_json(
        args.validation_bundle.read_text(encoding="utf-8")
    )
    specification = R4ExecutionSpecification.model_validate_json(
        args.execution.read_text(encoding="utf-8")
    )
    if not audit_r4_candidate_protocol(protocol):
        raise ValueError("R4 candidate protocol failed its audit")
    validation_audit = audit_validation_dataset_bundle(
        validation_bundle,
        evidence_root=args.evidence_root,
        current_builder_contract_hash=validation_builder_contract_hash(),
    )
    if validation_audit["status"] != "PASS":
        raise ValueError("R4 validation bundle failed its audit")
    if not audit_r4_execution_specification(specification):
        raise ValueError("R4 execution specification failed its audit")
    if validation_bundle.status != "READY":
        raise ValueError("R4 validation bundle is not ready")
    if protocol.universe_manifest_evidence_hash != universe.manifest_evidence_hash:
        raise ValueError("R4 protocol does not match universe")
    if (
        protocol.development_dataset_bundle_evidence_hash
        != development_bundle.bundle_evidence_hash
    ):
        raise ValueError("R4 protocol does not match development bundle")
    if (
        validation_bundle.r4_candidate_protocol_evidence_hash
        != protocol.protocol_evidence_hash
    ):
        raise ValueError("R4 validation bundle does not match protocol")
    if (
        validation_bundle.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
    ):
        raise ValueError("R4 validation bundle does not match universe")
    if (
        specification.r4_candidate_protocol_evidence_hash
        != protocol.protocol_evidence_hash
        or specification.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
    ):
        raise ValueError("R4 execution specification input hashes changed")
    market_data = load_r4_market_data(
        development_bundle=development_bundle,
        validation_bundle=validation_bundle,
        evidence_root=args.evidence_root,
        decision_symbols=protocol.decision_symbols,
    )
    return (
        universe,
        development_bundle,
        protocol,
        validation_bundle,
        specification,
        market_data,
    )


def verify_regression_receipt(path: Path) -> R31ResearchReplayResult:
    result = R31ResearchReplayResult.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        len(result.trades) != 230
        or len(result.opportunities) != 1400
        or len(result.equity_curve) != 3300
        or str(result.metrics.net_pl) != "488.79400413881589814287390"
    ):
        raise ValueError("Frozen R3.1 regression source result changed")
    return result


def authoritative_run_package(
    *,
    frozen_at: datetime,
    universe,
    development_bundle,
    protocol: R4CandidateProtocol,
    validation_bundle: ValidationDatasetBundle,
    specification: R4ExecutionSpecification,
    market_data_evidence_hash: str,
    regression_result: R31ResearchReplayResult,
) -> R4RunPackage:
    project_root = Path(__file__).resolve().parents[1]
    return build_r4_run_package(
        package_id="r4-path-quality-validation-run-package-v1",
        package_version="1.0.0",
        frozen_at=frozen_at,
        status="FROZEN_PRE_R4_OUTCOME",
        python_version=platform.python_version(),
        pydantic_version=pydantic.__version__,
        decimal_precision=50,
        decimal_rounding="ROUND_HALF_EVEN",
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            development_bundle.bundle_evidence_hash
        ),
        validation_dataset_bundle_evidence_hash=(
            validation_bundle.bundle_evidence_hash
        ),
        market_data_evidence_hash=market_data_evidence_hash,
        candidate_protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            specification.specification_evidence_hash
        ),
        source_file_sha256=source_file_hashes(project_root),
        planned_replays=build_planned_replays(protocol),
        expected_replay_count=42,
        result_ledger_relative_path="r4_path_quality_result_v1.json",
        replay_artifact_directory_relative_path="r4_path_quality_results_v1",
        known_data_regression_status="PASS",
        known_data_regression_source_result_evidence_hash=(
            regression_result.result_evidence_hash
        ),
        known_data_regression_trade_count=230,
        known_data_regression_opportunity_count=1400,
        known_data_regression_equity_point_count=3300,
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
        builder_contract_hash=builder_contract_hash(),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r4_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r4_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r4_study_runner.py",
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


def write_package(path: Path, package: R4RunPackage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = package.model_dump_json(indent=2) + "\n"
    if R4RunPackage.model_validate_json(serialized) != package:
        raise ValueError("R4 run package JSON does not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R4RunPackage:
    if args.output.exists():
        raise ValueError("Frozen R4 run package exists; use --check")
    if args.result.exists() or args.results_directory.exists():
        raise ValueError("R4 outcome exists before its run-package freeze")
    inputs = load_package_inputs(args)
    regression_result = verify_regression_receipt(args.r31_regression_result)
    package = authoritative_run_package(
        frozen_at=datetime.now(UTC),
        universe=inputs[0],
        development_bundle=inputs[1],
        protocol=inputs[2],
        validation_bundle=inputs[3],
        specification=inputs[4],
        market_data_evidence_hash=inputs[5].market_data_evidence_hash,
        regression_result=regression_result,
    )
    write_package(args.output, package)
    stored = R4RunPackage.model_validate_json(args.output.read_text(encoding="utf-8"))
    if stored != package or not audit_r4_run_package(stored):
        raise ValueError("R4 run package failed reload verification")
    print(
        f"WROTE {args.output} {stored.package_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def run_check(args) -> R4RunPackage:
    inputs = load_package_inputs(args)
    regression_result = verify_regression_receipt(args.r31_regression_result)
    stored = R4RunPackage.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_run_package(
        frozen_at=stored.frozen_at,
        universe=inputs[0],
        development_bundle=inputs[1],
        protocol=inputs[2],
        validation_bundle=inputs[3],
        specification=inputs[4],
        market_data_evidence_hash=inputs[5].market_data_evidence_hash,
        regression_result=regression_result,
    )
    if stored != expected or not audit_r4_run_package(stored):
        raise ValueError("Stored R4 run package differs from rebuild")
    print(
        "PASS "
        f"r4_package={stored.package_evidence_hash} "
        f"market_data={stored.market_data_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome R4 run package."
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
    parser.add_argument(
        "--validation-bundle",
        type=Path,
        default=DEFAULT_VALIDATION_BUNDLE,
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--execution", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument(
        "--r31-regression-result",
        type=Path,
        default=DEFAULT_R31_REGRESSION_RESULT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument(
        "--results-directory", type=Path, default=DEFAULT_RESULTS_DIRECTORY
    )
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
