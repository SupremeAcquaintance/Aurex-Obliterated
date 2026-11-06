import argparse
import hashlib
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pydantic

from aurex.backtest_engine.research_execution_spec import (
    R3ExecutionSpecification,
    audit_r3_execution_specification,
)
from aurex.backtest_engine.research_run_package import (
    R3RunPackage,
    audit_r3_run_package,
    build_r3_run_package,
)
from aurex.backtest_engine.research_study_runner import (
    build_planned_replays,
    load_decision_market_data,
)
from aurex.backtest_engine.universe import universe_evidence_hash

try:
    from scripts.freeze_r3_execution_spec import (
        DEFAULT_EXECUTION_SPEC_OUTPUT,
        load_verified_protocol,
    )
    from scripts.freeze_r3_execution_spec import (
        builder_contract_hash as execution_spec_builder_contract_hash,
    )
    from scripts.freeze_r3_mechanism_study import (
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_PROTOCOL_OUTPUT,
        DEFAULT_UNIVERSE_MANIFEST,
        find_result_artifacts,
        load_verified_inputs,
    )
except ModuleNotFoundError:
    from freeze_r3_execution_spec import (  # type: ignore[no-redef]
        DEFAULT_EXECUTION_SPEC_OUTPUT,
        load_verified_protocol,
    )
    from freeze_r3_execution_spec import (
        builder_contract_hash as execution_spec_builder_contract_hash,
    )
    from freeze_r3_mechanism_study import (  # type: ignore[no-redef]
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_PROTOCOL_OUTPUT,
        DEFAULT_UNIVERSE_MANIFEST,
        find_result_artifacts,
        load_verified_inputs,
    )

DEFAULT_RUN_PACKAGE_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_run_package_v1.json"
)
DEFAULT_RESULT_LEDGER_RELATIVE_PATH = "r3_cross_sectional_momentum_result_v1.json"
DEFAULT_REPLAY_ARTIFACT_DIRECTORY_RELATIVE_PATH = (
    "r3_cross_sectional_momentum_results_v1"
)


def load_verified_execution_specification(
    path: Path,
    *,
    protocol_hash: str,
    universe_hash: str,
    bundle_hash: str,
) -> R3ExecutionSpecification:
    specification = R3ExecutionSpecification.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_r3_execution_specification(specification):
        raise ValueError("R3 execution specification failed its hash audit")
    if specification.builder_contract_hash != execution_spec_builder_contract_hash():
        raise ValueError("R3 execution-spec builder contract has changed")
    if specification.protocol_evidence_hash != protocol_hash:
        raise ValueError("R3 execution specification does not match the protocol")
    if specification.universe_manifest_evidence_hash != universe_hash:
        raise ValueError("R3 execution specification does not match the universe")
    if specification.development_dataset_bundle_evidence_hash != bundle_hash:
        raise ValueError("R3 execution specification does not match the dataset bundle")
    return specification


def source_file_hashes(project_root: Path) -> dict[str, str]:
    relative_paths = [
        "scripts/run_r3_mechanism_study.py",
        "src/aurex/backtest_engine/research_engine.py",
        "src/aurex/backtest_engine/research_result.py",
        "src/aurex/backtest_engine/research_run_package.py",
        "src/aurex/backtest_engine/research_study_runner.py",
    ]
    return {
        relative_path: hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        for relative_path in relative_paths
    }


def authoritative_run_package(
    *,
    frozen_at: datetime,
    universe,
    bundle,
    protocol,
    execution_specification: R3ExecutionSpecification,
    market_data_evidence_hash: str,
) -> R3RunPackage:
    project_root = Path(__file__).resolve().parents[1]
    return build_r3_run_package(
        package_id="r3-cross-sectional-momentum-run-package-v1",
        package_version="1.0.0",
        frozen_at=frozen_at,
        status="FROZEN_PRE_OUTCOME",
        python_version=platform.python_version(),
        pydantic_version=pydantic.__version__,
        decimal_precision=50,
        decimal_rounding="ROUND_HALF_EVEN",
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=bundle.bundle_evidence_hash,
        market_data_evidence_hash=market_data_evidence_hash,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            execution_specification.specification_evidence_hash
        ),
        source_file_sha256=source_file_hashes(project_root),
        planned_replays=build_planned_replays(protocol),
        result_ledger_relative_path=DEFAULT_RESULT_LEDGER_RELATIVE_PATH,
        replay_artifact_directory_relative_path=(
            DEFAULT_REPLAY_ARTIFACT_DIRECTORY_RELATIVE_PATH
        ),
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
        builder_contract_hash=builder_contract_hash(),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r3_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_study_runner.py",
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


def load_package_inputs(args):
    universe, bundle = load_verified_inputs(
        evidence_root=args.evidence_root,
        universe_path=args.universe_manifest,
        bundle_path=args.dataset_bundle,
    )
    protocol = load_verified_protocol(
        args.protocol,
        universe=universe,
        bundle=bundle,
    )
    execution_specification = load_verified_execution_specification(
        args.execution_specification,
        protocol_hash=protocol.protocol_evidence_hash,
        universe_hash=universe.manifest_evidence_hash,
        bundle_hash=bundle.bundle_evidence_hash,
    )
    market_data = load_decision_market_data(
        bundle=bundle,
        evidence_root=args.evidence_root,
        decision_symbols=protocol.decision_symbols,
    )
    return universe, bundle, protocol, execution_specification, market_data


def write_package(path: Path, package: R3RunPackage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(package.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R3RunPackage:
    if args.run_package_output.exists():
        raise ValueError("Frozen R3 run package already exists; use --check")
    result_artifacts = find_result_artifacts(args.evidence_root)
    result_directory = args.evidence_root / (
        DEFAULT_REPLAY_ARTIFACT_DIRECTORY_RELATIVE_PATH
    )
    if result_artifacts or result_directory.exists():
        raise ValueError(
            "R3 result artifacts already exist before run-package freeze: "
            f"{result_artifacts}"
        )
    universe, bundle, protocol, execution_specification, market_data = (
        load_package_inputs(args)
    )
    package = authoritative_run_package(
        frozen_at=datetime.now(UTC),
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        execution_specification=execution_specification,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )
    write_package(args.run_package_output, package)
    stored = R3RunPackage.model_validate_json(
        args.run_package_output.read_text(encoding="utf-8")
    )
    if stored != package or not audit_r3_run_package(stored):
        raise ValueError("R3 run package failed reload verification")
    print(
        f"WROTE {args.run_package_output} {stored.package_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def run_check(args) -> R3RunPackage:
    universe, bundle, protocol, execution_specification, market_data = (
        load_package_inputs(args)
    )
    stored = R3RunPackage.model_validate_json(
        args.run_package_output.read_text(encoding="utf-8")
    )
    expected = authoritative_run_package(
        frozen_at=stored.frozen_at,
        universe=universe,
        bundle=bundle,
        protocol=protocol,
        execution_specification=execution_specification,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )
    if stored != expected or not audit_r3_run_package(stored):
        raise ValueError("Stored R3 run package differs from authoritative rebuild")
    print(
        "PASS "
        f"run_package={stored.package_evidence_hash} "
        f"market_data={stored.market_data_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or offline-verify the pre-outcome Aurex R3 run package."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--universe-manifest", type=Path, default=DEFAULT_UNIVERSE_MANIFEST
    )
    parser.add_argument("--dataset-bundle", type=Path, default=DEFAULT_DATASET_BUNDLE)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_OUTPUT)
    parser.add_argument(
        "--execution-specification",
        type=Path,
        default=DEFAULT_EXECUTION_SPEC_OUTPUT,
    )
    parser.add_argument(
        "--run-package-output", type=Path, default=DEFAULT_RUN_PACKAGE_OUTPUT
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
