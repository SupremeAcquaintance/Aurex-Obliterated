import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_r4_execution_spec import (
    R4ExecutionSpecification,
    R4InputAvailabilitySemantics,
    R4MarketLifecycleSemantics,
    R4TerminalAvailability,
    R4ValidationFoldSemantics,
    R4ValidationMetricSemantics,
    audit_r4_execution_specification,
    build_r4_execution_specification,
)
from aurex.backtest_engine.research_r4_protocol import (
    R4CandidateProtocol,
    audit_r4_candidate_protocol,
)
from aurex.backtest_engine.research_r31_execution_spec import (
    R31ExecutionSpecification,
    audit_r31_execution_specification,
)
from aurex.backtest_engine.validation_bundle import (
    ValidationDatasetBundle,
    audit_validation_dataset_bundle,
)

try:
    from scripts.build_validation_dataset_bundle import (
        builder_contract_hash as validation_builder_contract_hash,
    )
except ModuleNotFoundError:
    from build_validation_dataset_bundle import (  # type: ignore[no-redef]
        builder_contract_hash as validation_builder_contract_hash,
    )

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_R4_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_candidate_v1.json"
DEFAULT_R31_EXECUTION = (
    DEFAULT_EVIDENCE_ROOT / "r31_path_quality_execution_spec_v1.json"
)
DEFAULT_VALIDATION_BUNDLE = (
    DEFAULT_EVIDENCE_ROOT / "validation_2025_4h_bundle_v1.json"
)
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "r4_path_quality_execution_spec_v1.json"
)
R4_RESULT_GLOBS = (
    "r4_path_quality_validation_result*.json",
    "r4_path_quality_validation_results*",
)


def find_result_artifacts(evidence_root: Path) -> list[str]:
    return sorted(
        {
            path.relative_to(evidence_root).as_posix()
            for pattern in R4_RESULT_GLOBS
            for path in evidence_root.glob(pattern)
        }
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_r4_execution_spec.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r4_execution_spec.py",
    ]
    return hashlib.sha256(
        b"\n".join(
            (
                path.relative_to(project_root).as_posix().encode()
                + b":"
                + hashlib.sha256(path.read_bytes()).hexdigest().encode()
            )
            for path in paths
        )
    ).hexdigest()


def load_inputs(args):
    protocol = R4CandidateProtocol.model_validate_json(
        args.r4_protocol.read_text(encoding="utf-8")
    )
    parent = R31ExecutionSpecification.model_validate_json(
        args.r31_execution.read_text(encoding="utf-8")
    )
    validation = ValidationDatasetBundle.model_validate_json(
        args.validation_bundle.read_text(encoding="utf-8")
    )
    if not audit_r4_candidate_protocol(protocol):
        raise ValueError("R4 execution candidate audit failed")
    if not audit_r31_execution_specification(parent):
        raise ValueError("R4 execution parent specification audit failed")
    validation_audit = audit_validation_dataset_bundle(
        validation,
        evidence_root=args.evidence_root,
        current_builder_contract_hash=validation_builder_contract_hash(),
    )
    if validation_audit["status"] != "PASS" or validation.status != "READY":
        raise ValueError("R4 execution validation bundle audit failed")
    if (
        validation.r4_candidate_protocol_evidence_hash
        != protocol.protocol_evidence_hash
    ):
        raise ValueError("R4 validation bundle does not match candidate")
    if (
        protocol.parent_r31_execution_specification_evidence_hash
        != parent.specification_evidence_hash
    ):
        raise ValueError("R4 candidate does not match parent execution")
    return protocol, parent, validation


def authoritative_specification(
    *,
    registered_at: datetime,
    protocol: R4CandidateProtocol,
    parent: R31ExecutionSpecification,
    validation: ValidationDatasetBundle,
) -> R4ExecutionSpecification:
    terminal = [
        R4TerminalAvailability(
            symbol=entry.symbol,
            last_available_bar=entry.last_timestamp,
            first_missing_bar=entry.terminal_missing_start,
            missing_candle_count=len(entry.missing_timestamps),
            unavailable_archive_months=entry.unavailable_archive_months,
        )
        for entry in validation.entries
        if entry.availability_shape
        == "CONTIGUOUS_TERMINAL_SUFFIX_MISSING"
        and entry.last_timestamp is not None
        and entry.terminal_missing_start is not None
    ]
    return build_r4_execution_specification(
        registered_at=registered_at,
        r4_candidate_protocol_evidence_hash=protocol.protocol_evidence_hash,
        parent_r31_execution_specification_evidence_hash=(
            parent.specification_evidence_hash
        ),
        validation_dataset_bundle_evidence_hash=validation.bundle_evidence_hash,
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        arithmetic=parent.arithmetic,
        inputs=R4InputAvailabilitySemantics(
            terminal_symbols=terminal,
            allowed_validation_shapes=[
                "FULL_CONTINUOUS",
                "CONTIGUOUS_TERMINAL_SUFFIX_MISSING",
            ],
        ),
        signals=parent.signals,
        indicators=parent.indicators,
        orders=parent.orders,
        allocation=parent.allocation,
        lifecycle=R4MarketLifecycleSemantics(
            termination_event_order=[
                "WRITE_OFF_TERMINATED_OPEN_POSITIONS",
                "PROCESS_REBALANCE_OR_STOPS_FOR_AVAILABLE_MARKETS",
                "MARK_AVAILABLE_OPEN_POSITIONS_AT_CLOSE",
            ]
        ),
        folds=R4ValidationFoldSemantics(
            parent_fold_semantics=parent.folds,
        ),
        metrics=R4ValidationMetricSemantics(
            parent_metrics=parent.metrics,
        ),
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
    )


def write_specification(
    path: Path,
    specification: R4ExecutionSpecification,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = specification.model_dump_json(indent=2) + "\n"
    if (
        R4ExecutionSpecification.model_validate_json(serialized)
        != specification
    ):
        raise ValueError("R4 execution specification JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R4ExecutionSpecification:
    if args.output.exists():
        raise ValueError("Frozen R4 execution specification exists; use --check")
    if find_result_artifacts(args.evidence_root):
        raise ValueError("R4 result exists before execution specification freeze")
    protocol, parent, validation = load_inputs(args)
    specification = authoritative_specification(
        registered_at=datetime.now(UTC),
        protocol=protocol,
        parent=parent,
        validation=validation,
    )
    write_specification(args.output, specification)
    stored = R4ExecutionSpecification.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != specification or not audit_r4_execution_specification(stored):
        raise ValueError("R4 execution specification failed reload audit")
    print(
        f"WROTE {args.output} {stored.specification_evidence_hash} "
        f"terminal={len(stored.inputs.terminal_symbols)}",
        flush=True,
    )
    return stored


def run_check(args) -> R4ExecutionSpecification:
    protocol, parent, validation = load_inputs(args)
    stored = R4ExecutionSpecification.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_specification(
        registered_at=stored.registered_at,
        protocol=protocol,
        parent=parent,
        validation=validation,
    )
    if stored != expected or not audit_r4_execution_specification(stored):
        raise ValueError("Stored R4 execution specification differs from rebuild")
    print(
        "PASS "
        f"r4_execution={stored.specification_evidence_hash} "
        f"terminal={len(stored.inputs.terminal_symbols)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify R4 validation execution semantics."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--r4-protocol", type=Path, default=DEFAULT_R4_PROTOCOL)
    parser.add_argument("--r31-execution", type=Path, default=DEFAULT_R31_EXECUTION)
    parser.add_argument(
        "--validation-bundle",
        type=Path,
        default=DEFAULT_VALIDATION_BUNDLE,
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
