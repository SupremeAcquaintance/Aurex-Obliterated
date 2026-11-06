import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_execution_spec import (
    R3ExecutionSpecification,
    audit_r3_execution_specification,
)
from aurex.backtest_engine.research_r31_execution_spec import (
    R31ArithmeticSemantics,
    R31ExecutionSpecification,
    R31SignalExecutionSemantics,
    audit_r31_execution_specification,
    build_r31_execution_specification,
)
from aurex.backtest_engine.research_r31_study import (
    R31MechanismStudyProtocol,
    audit_r31_mechanism_study_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_study_v1.json"
DEFAULT_PARENT_EXECUTION = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_execution_spec_v1.json"
)
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r31_path_quality_execution_spec_v1.json"
R31_RESULT_GLOB = "r31_path_quality_result*.json"


def load_inputs(args):
    protocol = R31MechanismStudyProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    parent = R3ExecutionSpecification.model_validate_json(
        args.parent_execution.read_text(encoding="utf-8")
    )
    if not audit_r31_mechanism_study_protocol(protocol):
        raise ValueError("R3.1 execution input protocol failed its audit")
    if not audit_r3_execution_specification(parent):
        raise ValueError("R3.1 parent execution specification failed its audit")
    if (
        protocol.parent_r3_execution_spec_evidence_hash
        != parent.specification_evidence_hash
    ):
        raise ValueError("R3.1 protocol does not match its parent execution contract")
    return protocol, parent


def authoritative_specification(
    *,
    registered_at: datetime,
    protocol: R31MechanismStudyProtocol,
    parent: R3ExecutionSpecification,
) -> R31ExecutionSpecification:
    return build_r31_execution_specification(
        specification_id="r3.1-path-quality-execution-v1",
        specification_version="1.0.0",
        registered_at=registered_at,
        status="FROZEN_PRE_R31_OUTCOME",
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        parent_r3_execution_specification_evidence_hash=(
            parent.specification_evidence_hash
        ),
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        permitted_semantic_delta=(
            "REPLACE_ENDPOINT_RETURN_SCORE_WITH_FIXED_OLS_SLOPE_TIMES_R_SQUARED"
        ),
        arithmetic=R31ArithmeticSemantics(),
        inputs=parent.inputs,
        signals=R31SignalExecutionSemantics(
            recorded_signal_fields=["INTERCEPT", "R_SQUARED", "SCORE", "SLOPE"]
        ),
        indicators=parent.indicators,
        orders=parent.orders,
        allocation=parent.allocation,
        folds=parent.folds,
        metrics=parent.metrics,
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r31_execution_spec.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r31_execution_spec.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_execution_spec.py",
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


def find_result_artifacts(evidence_root: Path) -> list[str]:
    return sorted(
        path.relative_to(evidence_root).as_posix()
        for path in evidence_root.glob(R31_RESULT_GLOB)
        if path.is_file()
    )


def write_specification(
    path: Path, specification: R31ExecutionSpecification
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = specification.model_dump_json(indent=2) + "\n"
    if R31ExecutionSpecification.model_validate_json(serialized) != specification:
        raise ValueError("R3.1 execution specification JSON does not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R31ExecutionSpecification:
    if args.output.exists():
        raise ValueError("Frozen R3.1 execution specification exists; use --check")
    result_artifacts = find_result_artifacts(args.evidence_root)
    if result_artifacts:
        raise ValueError(f"R3.1 result predates execution freeze: {result_artifacts}")
    protocol, parent = load_inputs(args)
    specification = authoritative_specification(
        registered_at=datetime.now(UTC),
        protocol=protocol,
        parent=parent,
    )
    write_specification(args.output, specification)
    stored = R31ExecutionSpecification.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != specification or not audit_r31_execution_specification(stored):
        raise ValueError("R3.1 execution specification failed reload verification")
    print(f"WROTE {args.output} {stored.specification_evidence_hash}", flush=True)
    return stored


def run_check(args) -> R31ExecutionSpecification:
    protocol, parent = load_inputs(args)
    stored = R31ExecutionSpecification.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_specification(
        registered_at=stored.registered_at,
        protocol=protocol,
        parent=parent,
    )
    if stored != expected or not audit_r31_execution_specification(stored):
        raise ValueError("Stored R3.1 execution specification differs from rebuild")
    print(
        "PASS "
        f"r31_execution={stored.specification_evidence_hash} "
        f"observations={stored.signals.close_observation_count} "
        f"sxx={stored.signals.regression_sxx}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome R3.1 execution specification."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--parent-execution", type=Path, default=DEFAULT_PARENT_EXECUTION
    )
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
