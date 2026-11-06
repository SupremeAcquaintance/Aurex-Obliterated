import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_u1_execution_spec import (
    U1AllocationSemantics,
    U1ArithmeticSemantics,
    U1AvailabilitySemantics,
    U1ExecutionSpecification,
    U1FoldSemantics,
    U1InputSemantics,
    U1MetricSemantics,
    U1OrderSemantics,
    U1SignalExecutionSemantics,
    audit_u1_execution_specification,
    build_u1_execution_specification,
)
from aurex.backtest_engine.research_u1_primary_protocol import (
    U1PrimaryProtocol,
    audit_u1_primary_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_protocol_v1.json"
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "u1_primary_execution_spec_v1.json"
DEFAULT_POST_SPEC_ARTIFACTS = (
    DEFAULT_EVIDENCE_ROOT / "u1_primary_run_package_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_result_v1.json",
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_u1_execution_spec.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_u1_execution_spec.py",
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


def load_protocol(path: Path) -> U1PrimaryProtocol:
    protocol = U1PrimaryProtocol.model_validate_json(path.read_text(encoding="utf-8"))
    if not audit_u1_primary_protocol(protocol):
        raise ValueError("U1 primary protocol failed its hash audit")
    if protocol.outcome_fields_inspected or protocol.preexisting_result_artifacts:
        raise ValueError("U1 primary protocol no longer predates outcomes")
    return protocol


def authoritative_specification(
    *,
    registered_at: datetime,
    protocol: U1PrimaryProtocol,
) -> U1ExecutionSpecification:
    return build_u1_execution_specification(
        registered_at=registered_at,
        primary_protocol_evidence_hash=protocol.protocol_evidence_hash,
        discovery_charter_evidence_hash=protocol.discovery_charter_evidence_hash,
        theory_screen_evidence_hash=protocol.theory_screen_evidence_hash,
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        arithmetic=U1ArithmeticSemantics(),
        inputs=U1InputSemantics(),
        signals=U1SignalExecutionSemantics(),
        orders=U1OrderSemantics(
            rebalance_event_order=[
                "APPLY_TERMINAL_MARKET_EVENTS",
                "EXIT_EXISTING_AT_OPEN",
                "COMPUTE_SIGNAL_FROM_PRIOR_CLOSES",
                "ALLOCATE_EQUAL_WEIGHT_AT_OPEN",
                "MARK_ALL_POSITIONS_AT_CLOSE",
            ],
            non_rebalance_event_order=[
                "APPLY_TERMINAL_MARKET_EVENTS",
                "MARK_ALL_POSITIONS_AT_CLOSE",
            ],
        ),
        allocation=U1AllocationSemantics(),
        availability=U1AvailabilitySemantics(),
        folds=U1FoldSemantics(),
        metrics=U1MetricSemantics(),
        outcome_fields_inspected=[],
        preexisting_engine_or_result_artifacts=[],
    )


def write_specification(
    path: Path,
    specification: U1ExecutionSpecification,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = specification.model_dump_json(indent=2) + "\n"
    if U1ExecutionSpecification.model_validate_json(serialized) != specification:
        raise ValueError("U1 execution specification JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> U1ExecutionSpecification:
    if args.output.exists():
        raise ValueError("Frozen U1 execution specification exists; use --check")
    preexisting = [path.as_posix() for path in args.post_spec_artifact if path.exists()]
    if preexisting:
        raise ValueError(f"U1 artifact predates execution specification: {preexisting}")
    protocol = load_protocol(args.protocol)
    specification = authoritative_specification(
        registered_at=datetime.now(UTC),
        protocol=protocol,
    )
    write_specification(args.output, specification)
    stored = U1ExecutionSpecification.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != specification or not audit_u1_execution_specification(stored):
        raise ValueError("U1 execution specification failed reload verification")
    print(
        f"WROTE {args.output} {stored.specification_evidence_hash}",
        flush=True,
    )
    return stored


def run_check(args) -> U1ExecutionSpecification:
    protocol = load_protocol(args.protocol)
    stored = U1ExecutionSpecification.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_specification(
        registered_at=stored.registered_at,
        protocol=protocol,
    )
    if stored != expected or not audit_u1_execution_specification(stored):
        raise ValueError("Stored U1 execution specification differs from rebuild")
    print(
        f"PASS u1_execution_spec={stored.specification_evidence_hash}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-engine U1 execution specification."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--post-spec-artifact",
        type=Path,
        nargs="*",
        default=list(DEFAULT_POST_SPEC_ARTIFACTS),
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
