import argparse
import hashlib
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pydantic

from aurex.backtest_engine.research_r31_execution_spec import (
    R31ExecutionSpecification,
    audit_r31_execution_specification,
)
from aurex.backtest_engine.research_r31_run_package import (
    R31_SOURCE_FILES,
    R31RunPackage,
    audit_r31_run_package,
    build_r31_run_package,
)
from aurex.backtest_engine.research_r31_study import (
    R31MechanismStudyProtocol,
    audit_r31_mechanism_study_protocol,
)
from aurex.backtest_engine.research_r31_study_runner import build_planned_replays
from aurex.backtest_engine.research_study_runner import load_decision_market_data
from aurex.backtest_engine.universe import universe_evidence_hash

try:
    from scripts.freeze_r31_execution_spec import (
        DEFAULT_OUTPUT as DEFAULT_EXECUTION,
    )
    from scripts.freeze_r31_mechanism_study import (
        DEFAULT_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_UNIVERSE,
        load_verified_inputs,
    )
    from scripts.freeze_r31_mechanism_study import (
        DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
    )
except ModuleNotFoundError:
    from freeze_r31_execution_spec import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT as DEFAULT_EXECUTION,
    )
    from freeze_r31_mechanism_study import (  # type: ignore[no-redef]
        DEFAULT_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_UNIVERSE,
        load_verified_inputs,
    )
    from freeze_r31_mechanism_study import (
        DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
    )

DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_run_package_v1.json"
DEFAULT_RESULT = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_result_v1.json"
DEFAULT_RESULTS_DIRECTORY = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_results_v1"


def source_file_hashes(project_root: Path) -> dict[str, str]:
    return {
        relative_path: hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        for relative_path in R31_SOURCE_FILES
    }


def load_package_inputs(args):
    universe, bundle = load_verified_inputs(
        evidence_root=args.evidence_root,
        universe_path=args.universe,
        bundle_path=args.bundle,
    )
    protocol = R31MechanismStudyProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    specification = R31ExecutionSpecification.model_validate_json(
        args.execution.read_text(encoding="utf-8")
    )
    if not audit_r31_mechanism_study_protocol(protocol):
        raise ValueError("R3.1 package protocol failed its audit")
    if not audit_r31_execution_specification(specification):
        raise ValueError("R3.1 package execution specification failed its audit")
    if specification.protocol_evidence_hash != protocol.protocol_evidence_hash:
        raise ValueError("R3.1 execution specification does not match protocol")
    if protocol.universe_manifest_evidence_hash != universe.manifest_evidence_hash:
        raise ValueError("R3.1 protocol does not match universe")
    if protocol.development_dataset_bundle_evidence_hash != bundle.bundle_evidence_hash:
        raise ValueError("R3.1 protocol does not match dataset bundle")
    market_data = load_decision_market_data(
        bundle=bundle,
        evidence_root=args.evidence_root,
        decision_symbols=protocol.decision_symbols,
    )
    return universe, bundle, protocol, specification, market_data


def authoritative_run_package(
    *,
    frozen_at: datetime,
    universe,
    bundle,
    protocol: R31MechanismStudyProtocol,
    specification: R31ExecutionSpecification,
    market_data_evidence_hash: str,
) -> R31RunPackage:
    project_root = Path(__file__).resolve().parents[1]
    return build_r31_run_package(
        package_id="r3.1-path-quality-run-package-v1",
        package_version="1.0.0",
        frozen_at=frozen_at,
        status="FROZEN_PRE_R31_OUTCOME",
        python_version=platform.python_version(),
        pydantic_version=pydantic.__version__,
        decimal_precision=50,
        decimal_rounding="ROUND_HALF_EVEN",
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=bundle.bundle_evidence_hash,
        market_data_evidence_hash=market_data_evidence_hash,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            specification.specification_evidence_hash
        ),
        source_file_sha256=source_file_hashes(project_root),
        planned_replays=build_planned_replays(protocol),
        expected_replay_count=44,
        result_ledger_relative_path="r31_path_quality_result_v1.json",
        replay_artifact_directory_relative_path="r31_path_quality_results_v1",
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
        builder_contract_hash=builder_contract_hash(),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r31_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r31_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r31_study_runner.py",
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


def write_package(path: Path, package: R31RunPackage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = package.model_dump_json(indent=2) + "\n"
    if R31RunPackage.model_validate_json(serialized) != package:
        raise ValueError("R3.1 run package JSON does not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R31RunPackage:
    if args.output.exists():
        raise ValueError("Frozen R3.1 run package exists; use --check")
    if args.result.exists() or args.results_directory.exists():
        raise ValueError("R3.1 outcome exists before its run-package freeze")
    universe, bundle, protocol, specification, market_data = load_package_inputs(args)
    package = authoritative_run_package(
        frozen_at=datetime.now(UTC),
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        specification=specification,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )
    write_package(args.output, package)
    stored = R31RunPackage.model_validate_json(args.output.read_text(encoding="utf-8"))
    if stored != package or not audit_r31_run_package(stored):
        raise ValueError("R3.1 run package failed reload verification")
    print(
        f"WROTE {args.output} {stored.package_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def run_check(args) -> R31RunPackage:
    universe, bundle, protocol, specification, market_data = load_package_inputs(args)
    stored = R31RunPackage.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_run_package(
        frozen_at=stored.frozen_at,
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        specification=specification,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )
    if stored != expected or not audit_r31_run_package(stored):
        raise ValueError("Stored R3.1 run package differs from rebuild")
    print(
        "PASS "
        f"r31_package={stored.package_evidence_hash} "
        f"market_data={stored.market_data_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome R3.1 run package."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--execution", type=Path, default=DEFAULT_EXECUTION)
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
