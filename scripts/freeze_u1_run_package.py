import argparse
import hashlib
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pydantic

from aurex.backtest_engine.research_u1_execution_spec import (
    U1ExecutionSpecification,
    audit_u1_execution_specification,
)
from aurex.backtest_engine.research_u1_primary_protocol import (
    U1PrimaryProtocol,
    audit_u1_primary_protocol,
)
from aurex.backtest_engine.research_u1_run_package import (
    U1_SOURCE_FILES,
    U1RunPackage,
    audit_u1_run_package,
    build_u1_run_package,
)
from aurex.backtest_engine.research_u1_study_runner import (
    build_u1_planned_replays,
    load_u1_market_data,
)
from aurex.backtest_engine.universe import universe_evidence_hash

try:
    from scripts.freeze_u1_execution_spec import (
        DEFAULT_OUTPUT as DEFAULT_EXECUTION,
    )
    from scripts.freeze_u1_primary_protocol import (
        DEFAULT_CHARTER,
        DEFAULT_CONTAMINATION,
        DEFAULT_DEVELOPMENT,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_SCREEN,
        DEFAULT_UNIVERSE,
        load_inputs,
    )
    from scripts.freeze_u1_primary_protocol import (
        DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
    )
except ModuleNotFoundError:
    from freeze_u1_execution_spec import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT as DEFAULT_EXECUTION,
    )
    from freeze_u1_primary_protocol import (  # type: ignore[no-redef]
        DEFAULT_CHARTER,
        DEFAULT_CONTAMINATION,
        DEFAULT_DEVELOPMENT,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_SCREEN,
        DEFAULT_UNIVERSE,
        load_inputs,
    )
    from freeze_u1_primary_protocol import (
        DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
    )

DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "u1_primary_run_package_v1.json"
DEFAULT_RESULT = DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_result_v1.json"
DEFAULT_RESULTS_DIRECTORY = (
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_results_v1"
)


def source_file_hashes(project_root: Path) -> dict[str, str]:
    return {
        relative_path: hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        for relative_path in U1_SOURCE_FILES
    }


def load_package_inputs(args):
    charter, screen, contamination, universe, development = load_inputs(args)
    protocol = U1PrimaryProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    specification = U1ExecutionSpecification.model_validate_json(
        args.execution.read_text(encoding="utf-8")
    )
    if not audit_u1_primary_protocol(protocol):
        raise ValueError("U1 primary protocol failed its hash audit")
    if not audit_u1_execution_specification(specification):
        raise ValueError("U1 execution specification failed its hash audit")
    expected_bindings = {
        "discovery_charter_evidence_hash": charter.charter_evidence_hash,
        "theory_screen_evidence_hash": screen.screen_evidence_hash,
        "universe_manifest_evidence_hash": universe.manifest_evidence_hash,
        "development_dataset_bundle_evidence_hash": (
            development.bundle_evidence_hash
        ),
        "contamination_ledger_evidence_hash": contamination.ledger_evidence_hash,
    }
    for field, expected in expected_bindings.items():
        if getattr(protocol, field) != expected:
            raise ValueError(f"U1 protocol changed evidence binding: {field}")
    if (
        specification.primary_protocol_evidence_hash
        != protocol.protocol_evidence_hash
        or specification.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
        or specification.theory_screen_evidence_hash != screen.screen_evidence_hash
        or specification.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
        or specification.development_dataset_bundle_evidence_hash
        != development.bundle_evidence_hash
    ):
        raise ValueError("U1 execution specification lineage changed")
    market_data = load_u1_market_data(
        development_bundle=development,
        evidence_root=args.evidence_root,
        decision_symbols=protocol.decision_symbols,
    )
    return (
        charter,
        screen,
        contamination,
        universe,
        development,
        protocol,
        specification,
        market_data,
    )


def authoritative_u1_run_package(
    *,
    frozen_at: datetime,
    charter,
    screen,
    contamination,
    universe,
    development,
    protocol: U1PrimaryProtocol,
    specification: U1ExecutionSpecification,
    market_data,
) -> U1RunPackage:
    project_root = Path(__file__).resolve().parents[1]
    return build_u1_run_package(
        frozen_at=frozen_at,
        python_version=platform.python_version(),
        pydantic_version=pydantic.__version__,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        theory_screen_evidence_hash=screen.screen_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=development.bundle_evidence_hash,
        contamination_ledger_evidence_hash=contamination.ledger_evidence_hash,
        primary_protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            specification.specification_evidence_hash
        ),
        market_data_evidence_hash=market_data.market_data_evidence_hash,
        source_file_sha256=source_file_hashes(project_root),
        planned_replays=build_u1_planned_replays(protocol),
        expected_replay_count=47,
        deterministic_replay_required=True,
        validation_data_loaded=False,
        holdout_data_loaded=False,
        forward_data_loaded=False,
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
        builder_contract_hash=builder_contract_hash(),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_u1_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_u1_run_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_u1_study_runner.py",
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


def write_package(path: Path, package: U1RunPackage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = package.model_dump_json(indent=2) + "\n"
    if U1RunPackage.model_validate_json(serialized) != package:
        raise ValueError("U1 run package JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> U1RunPackage:
    if args.output.exists():
        raise ValueError("Frozen U1 run package exists; use --check")
    if args.result.exists() or args.results_directory.exists():
        raise ValueError("U1 outcome exists before its run-package freeze")
    inputs = load_package_inputs(args)
    package = authoritative_u1_run_package(
        frozen_at=datetime.now(UTC),
        charter=inputs[0],
        screen=inputs[1],
        contamination=inputs[2],
        universe=inputs[3],
        development=inputs[4],
        protocol=inputs[5],
        specification=inputs[6],
        market_data=inputs[7],
    )
    write_package(args.output, package)
    stored = U1RunPackage.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != package or not audit_u1_run_package(stored):
        raise ValueError("U1 run package failed reload verification")
    print(
        f"WROTE {args.output} {stored.package_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def run_check(args) -> U1RunPackage:
    inputs = load_package_inputs(args)
    stored = U1RunPackage.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_u1_run_package(
        frozen_at=stored.frozen_at,
        charter=inputs[0],
        screen=inputs[1],
        contamination=inputs[2],
        universe=inputs[3],
        development=inputs[4],
        protocol=inputs[5],
        specification=inputs[6],
        market_data=inputs[7],
    )
    if stored != expected or not audit_u1_run_package(stored):
        raise ValueError("Stored U1 run package differs from rebuild")
    print(
        "PASS "
        f"u1_package={stored.package_evidence_hash} "
        f"market_data={stored.market_data_evidence_hash} "
        f"replays={stored.expected_replay_count}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome U1 development run package."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--screen", type=Path, default=DEFAULT_SCREEN)
    parser.add_argument(
        "--contamination",
        type=Path,
        default=DEFAULT_CONTAMINATION,
    )
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--development", type=Path, default=DEFAULT_DEVELOPMENT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--execution", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument(
        "--results-directory",
        type=Path,
        default=DEFAULT_RESULTS_DIRECTORY,
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
