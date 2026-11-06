import argparse
import hashlib
import sys
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from aurex.backtest_engine.development_bundle import DevelopmentDatasetBundle
from aurex.backtest_engine.research_execution_spec import (
    R3AllocationSemantics,
    R3ExecutionSpecification,
    R3FoldSemantics,
    R3IndicatorSemantics,
    R3InputSemantics,
    R3MetricSemantics,
    R3OrderSemantics,
    R3SignalSemantics,
    audit_r3_execution_specification,
    build_r3_execution_specification,
)
from aurex.backtest_engine.research_study import (
    R3MechanismStudyProtocol,
    audit_r3_mechanism_study_protocol,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    universe_evidence_hash,
)

try:
    from scripts.freeze_r3_mechanism_study import (
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_PROTOCOL_OUTPUT,
        DEFAULT_UNIVERSE_MANIFEST,
        find_result_artifacts,
        load_verified_inputs,
    )
    from scripts.freeze_r3_mechanism_study import (
        builder_contract_hash as protocol_builder_contract_hash,
    )
except ModuleNotFoundError:
    from freeze_r3_mechanism_study import (  # type: ignore[no-redef]
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_PROTOCOL_OUTPUT,
        DEFAULT_UNIVERSE_MANIFEST,
        find_result_artifacts,
        load_verified_inputs,
    )
    from freeze_r3_mechanism_study import (
        builder_contract_hash as protocol_builder_contract_hash,
    )

DEFAULT_EXECUTION_SPEC_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_execution_spec_v1.json"
)


def load_verified_protocol(
    path: Path,
    *,
    universe: MarketUniverseManifest,
    bundle: DevelopmentDatasetBundle,
) -> R3MechanismStudyProtocol:
    protocol = R3MechanismStudyProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_r3_mechanism_study_protocol(protocol):
        raise ValueError("R3 protocol failed its evidence-hash audit")
    if protocol.status != "FROZEN_PRE_OUTCOME":
        raise ValueError("R3 protocol is not frozen pre-outcome")
    if protocol.builder_contract_hash != protocol_builder_contract_hash():
        raise ValueError("R3 protocol builder contract has changed")
    if protocol.universe_manifest_evidence_hash != universe.manifest_evidence_hash:
        raise ValueError("R3 protocol does not match the frozen universe")
    if protocol.development_dataset_bundle_evidence_hash != bundle.bundle_evidence_hash:
        raise ValueError("R3 protocol does not match the development dataset bundle")
    return protocol


def selected_count(protocol: R3MechanismStudyProtocol) -> int:
    primary = [variant for variant in protocol.variants if variant.role == "PRIMARY"]
    if len(primary) != 1:
        raise ValueError("R3 execution specification requires exactly one primary variant")
    count = int(
        (
            primary[0].selected_fraction * Decimal(len(protocol.decision_symbols))
        ).to_integral_value(rounding=ROUND_CEILING)
    )
    if count != protocol.portfolio.max_open_positions:
        raise ValueError(
            "R3 selected count must equal the predeclared maximum open positions"
        )
    return count


def authoritative_execution_specification(
    *,
    registered_at: datetime,
    protocol: R3MechanismStudyProtocol,
    universe: MarketUniverseManifest,
    bundle: DevelopmentDatasetBundle,
) -> R3ExecutionSpecification:
    return build_r3_execution_specification(
        specification_id="r3-cross-sectional-momentum-execution-v1",
        specification_version="1.0.0",
        registered_at=registered_at,
        status="FROZEN_PRE_OUTCOME",
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=bundle.bundle_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        inputs=R3InputSemantics(
            decision_symbol_count=len(protocol.decision_symbols),
        ),
        signals=R3SignalSemantics(
            fixed_selected_count=selected_count(protocol),
        ),
        indicators=R3IndicatorSemantics(),
        orders=R3OrderSemantics(
            rebalance_event_order=[
                "EXIT_EXISTING_AT_OPEN",
                "RANK_FROM_PRIOR_CLOSE",
                "ALLOCATE_NEW_AT_OPEN",
                "DISABLE_NEW_POSITION_SAME_BAR_STOP",
                "MARK_ALL_POSITIONS_AT_CLOSE",
            ],
            non_rebalance_event_order=[
                "CHECK_FIXED_STOP",
                "MARK_ALL_POSITIONS_AT_CLOSE",
            ],
        ),
        allocation=R3AllocationSemantics(
            candidate_quantity_order=[
                "COMPUTE_RISK_QUANTITY",
                "APPLY_SYMBOL_CAP",
                "APPLY_MAX_POSITION_COUNT",
                "APPLY_PROPORTIONAL_CAPACITY_SCALE",
                "ROUND_DOWN_TO_QUANTITY_INCREMENT",
                "REJECT_ZERO_QUANTITY",
            ],
        ),
        folds=R3FoldSemantics(),
        metrics=R3MetricSemantics(),
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r3_execution_spec.py",
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


def write_specification(
    path: Path,
    specification: R3ExecutionSpecification,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(
        specification.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_inputs(args) -> tuple[
    MarketUniverseManifest,
    DevelopmentDatasetBundle,
    R3MechanismStudyProtocol,
]:
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
    return universe, bundle, protocol


def run_freeze(args) -> R3ExecutionSpecification:
    if args.execution_spec_output.exists():
        raise ValueError("Frozen R3 execution specification already exists; use --check")
    result_artifacts = find_result_artifacts(args.evidence_root)
    if result_artifacts:
        raise ValueError(
            "R3 result artifacts already exist before execution-spec freeze: "
            f"{result_artifacts}"
        )
    universe, bundle, protocol = load_inputs(args)
    specification = authoritative_execution_specification(
        registered_at=datetime.now(UTC),
        protocol=protocol,
        universe=universe,
        bundle=bundle,
    )
    write_specification(args.execution_spec_output, specification)
    stored = R3ExecutionSpecification.model_validate_json(
        args.execution_spec_output.read_text(encoding="utf-8")
    )
    if stored != specification or not audit_r3_execution_specification(stored):
        raise ValueError("R3 execution specification failed reload verification")
    print(
        f"WROTE {args.execution_spec_output} {stored.specification_evidence_hash}",
        flush=True,
    )
    return stored


def run_check(args) -> R3ExecutionSpecification:
    universe, bundle, protocol = load_inputs(args)
    stored = R3ExecutionSpecification.model_validate_json(
        args.execution_spec_output.read_text(encoding="utf-8")
    )
    expected = authoritative_execution_specification(
        registered_at=stored.registered_at,
        protocol=protocol,
        universe=universe,
        bundle=bundle,
    )
    if stored != expected or not audit_r3_execution_specification(stored):
        raise ValueError(
            "Stored R3 execution specification differs from authoritative rebuild"
        )
    print(
        "PASS "
        f"execution_spec={stored.specification_evidence_hash} "
        f"protocol={stored.protocol_evidence_hash} "
        f"decision_symbols={stored.inputs.decision_symbol_count} "
        f"selected={stored.signals.fixed_selected_count}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or offline-verify exact pre-outcome Aurex R3 execution semantics."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--universe-manifest",
        type=Path,
        default=DEFAULT_UNIVERSE_MANIFEST,
    )
    parser.add_argument(
        "--dataset-bundle",
        type=Path,
        default=DEFAULT_DATASET_BUNDLE,
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_OUTPUT)
    parser.add_argument(
        "--execution-spec-output",
        type=Path,
        default=DEFAULT_EXECUTION_SPEC_OUTPUT,
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
