import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    audit_development_dataset_bundle,
)
from aurex.backtest_engine.research_r4_failure_analysis import (
    R4FailureAnalysisResult,
    audit_r4_failure_analysis_result,
)
from aurex.backtest_engine.research_u1_discovery_charter import (
    U1_ALLOWED_NEXT_DECISIONS,
    U1_DISCOVERY_STAGES,
    U1_FORBIDDEN_DERIVATIONS,
    U1_MINIMUM_ADVANCEMENT_GATES,
    U1_REQUIRED_CANDIDATE_BINDINGS,
    U1_REQUIRED_THEORY_EVIDENCE,
    U1_RETIRED_OR_QUARANTINED_LINEAGES,
    U1_STOP_CONDITIONS,
    U1_THEORY_SOURCE_POLICY,
    U1MechanismDiscoveryCharter,
    U1PartitionBoundary,
    audit_u1_mechanism_discovery_charter,
    build_u1_mechanism_discovery_charter,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)
from aurex.backtest_engine.validation_bundle import (
    ValidationDatasetBundle,
    audit_validation_dataset_bundle,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_R4_FAILURE_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "r4_failure_analysis_result_v1.json"
)
DEFAULT_CONTAMINATION = (
    DEFAULT_EVIDENCE_ROOT / "strategy_contamination_ledger_v1.json"
)
DEFAULT_UNIVERSE = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_DEVELOPMENT = (
    DEFAULT_EVIDENCE_ROOT / "development_4h_dataset_bundle_v1.json"
)
DEFAULT_VALIDATION = (
    DEFAULT_EVIDENCE_ROOT / "validation_2025_4h_bundle_v1.json"
)
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "u1_mechanism_discovery_charter_v1.json"
)
DEFAULT_DISCOVERY_OUTPUTS = (
    DEFAULT_EVIDENCE_ROOT / "u1_mechanism_theory_screen_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_protocol_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_result_v1.json",
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_u1_mechanism_discovery_charter.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_u1_discovery_charter.py",
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


def source_contract_hash(relative_paths: list[str]) -> str:
    project_root = Path(__file__).resolve().parents[1]
    return universe_evidence_hash(
        {
            "contract_files": {
                relative_path: hashlib.sha256(
                    (project_root / relative_path).read_bytes()
                ).hexdigest()
                for relative_path in relative_paths
            }
        }
    )


def development_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            "scripts/build_development_dataset_bundle.py",
            "src/aurex/backtest_engine/binance_vision.py",
            "src/aurex/backtest_engine/development_bundle.py",
        ]
    )


def validation_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            "scripts/build_validation_dataset_bundle.py",
            "src/aurex/backtest_engine/binance_vision.py",
            "src/aurex/backtest_engine/validation_bundle.py",
        ]
    )


def expected_universe_roles(universe: MarketUniverseManifest) -> dict[str, str]:
    return dict(
        sorted(
            (
                assessment.evidence.symbol,
                assessment.role,
            )
            for assessment in universe.assessments
            if assessment.role in {"DECISION_CANDIDATE", "DEVELOPMENT_ONLY"}
        )
    )


def load_inputs(args):
    failure = R4FailureAnalysisResult.model_validate_json(
        args.r4_failure_result.read_text(encoding="utf-8")
    )
    contamination = StrategyContaminationLedger.model_validate_json(
        args.contamination.read_text(encoding="utf-8")
    )
    universe = MarketUniverseManifest.model_validate_json(
        args.universe.read_text(encoding="utf-8")
    )
    development = DevelopmentDatasetBundle.model_validate_json(
        args.development.read_text(encoding="utf-8")
    )
    validation = ValidationDatasetBundle.model_validate_json(
        args.validation.read_text(encoding="utf-8")
    )
    if not audit_r4_failure_analysis_result(failure):
        raise ValueError("R4 failure analysis result failed its hash audit")
    if not audit_contamination_ledger(contamination):
        raise ValueError("Contamination ledger failed its hash audit")
    if audit_market_universe_manifest(universe)["status"] != "PASS":
        raise ValueError("Market universe manifest failed its hash audit")
    development_audit = audit_development_dataset_bundle(
        development,
        evidence_root=args.evidence_root,
        expected_roles=expected_universe_roles(universe),
        current_builder_contract_hash=development_builder_contract_hash(),
    )
    if development_audit["status"] != "PASS":
        raise ValueError(
            "Development dataset bundle failed its audit: "
            f"{development_audit['reasons']}"
        )
    validation_audit = audit_validation_dataset_bundle(
        validation,
        evidence_root=args.evidence_root,
        current_builder_contract_hash=validation_builder_contract_hash(),
    )
    if validation_audit["status"] != "PASS":
        raise ValueError(
            "Validation dataset bundle failed its audit: "
            f"{validation_audit['reasons']}"
        )
    if (
        failure.failure_classification != "SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS"
        or failure.next_research_decision
        != "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY"
    ):
        raise ValueError("U1 discovery requires the final R4 family-stop decision")
    if (
        universe.rule.contamination_ledger_hash
        != contamination.ledger_evidence_hash
        or development.contamination_ledger_hash
        != contamination.ledger_evidence_hash
        or validation.contamination_ledger_hash
        != contamination.ledger_evidence_hash
        or development.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
        or validation.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
        or validation.development_dataset_bundle_evidence_hash
        != development.bundle_evidence_hash
    ):
        raise ValueError("U1 discovery inputs do not share one data lineage")
    if (
        universe.status != "READY"
        or development.status != "READY"
        or validation.status != "READY"
    ):
        raise ValueError("U1 discovery requires ready source data")
    return failure, contamination, universe, development, validation


def partition_boundaries(universe: MarketUniverseManifest) -> list[U1PartitionBoundary]:
    partitions = {item.name: item for item in universe.partitions}
    return [
        U1PartitionBoundary(
            partition="DEVELOPMENT",
            start=partitions["DEVELOPMENT"].start,
            end=partitions["DEVELOPMENT"].end,
            research_role="DEVELOPMENT_FALSIFICATION",
            access="OPEN",
        ),
        U1PartitionBoundary(
            partition="VALIDATION",
            start=partitions["VALIDATION"].start,
            end=partitions["VALIDATION"].end,
            research_role="INTERNAL_VALIDATION_NOT_ELIGIBILITY",
            access="SEALED_FOR_UNRELATED_MECHANISM",
        ),
        U1PartitionBoundary(
            partition="HOLDOUT",
            start=partitions["HOLDOUT"].start,
            end=partitions["HOLDOUT"].end,
            research_role="FINAL_ELIGIBILITY_HOLDOUT",
            access="SEALED_AND_NOT_IMPORTED",
        ),
        U1PartitionBoundary(
            partition="FORWARD",
            start=partitions["FORWARD"].start,
            end=partitions["FORWARD"].end,
            research_role="LOCKED_FORWARD_EVIDENCE",
            access="LOCKED",
        ),
    ]


def authoritative_charter(
    *,
    registered_at: datetime,
    failure: R4FailureAnalysisResult,
    contamination: StrategyContaminationLedger,
    universe: MarketUniverseManifest,
    development: DevelopmentDatasetBundle,
    validation: ValidationDatasetBundle,
) -> U1MechanismDiscoveryCharter:
    return build_u1_mechanism_discovery_charter(
        registered_at=registered_at,
        r4_failure_analysis_result_evidence_hash=failure.result_evidence_hash,
        contamination_ledger_evidence_hash=contamination.ledger_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=development.bundle_evidence_hash,
        validation_dataset_bundle_evidence_hash=validation.bundle_evidence_hash,
        partition_boundaries=partition_boundaries(universe),
        retired_or_quarantined_lineages=U1_RETIRED_OR_QUARANTINED_LINEAGES,
        forbidden_derivations=U1_FORBIDDEN_DERIVATIONS,
        required_theory_evidence=U1_REQUIRED_THEORY_EVIDENCE,
        theory_source_policy=U1_THEORY_SOURCE_POLICY,
        discovery_stages=U1_DISCOVERY_STAGES,
        required_candidate_bindings=U1_REQUIRED_CANDIDATE_BINDINGS,
        minimum_advancement_gates=U1_MINIMUM_ADVANCEMENT_GATES,
        stop_conditions=U1_STOP_CONDITIONS,
        allowed_next_decisions=U1_ALLOWED_NEXT_DECISIONS,
        preexisting_discovery_artifacts=[],
        builder_contract_hash=builder_contract_hash(),
    )


def write_charter(
    path: Path,
    charter: U1MechanismDiscoveryCharter,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = charter.model_dump_json(indent=2) + "\n"
    if U1MechanismDiscoveryCharter.model_validate_json(serialized) != charter:
        raise ValueError("U1 discovery charter JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> U1MechanismDiscoveryCharter:
    if args.output.exists():
        raise ValueError("Frozen U1 discovery charter exists; use --check")
    preexisting = [path.as_posix() for path in args.discovery_output if path.exists()]
    if preexisting:
        raise ValueError(f"Discovery artifact predates its charter: {preexisting}")
    inputs = load_inputs(args)
    charter = authoritative_charter(
        registered_at=datetime.now(UTC),
        failure=inputs[0],
        contamination=inputs[1],
        universe=inputs[2],
        development=inputs[3],
        validation=inputs[4],
    )
    write_charter(args.output, charter)
    stored = U1MechanismDiscoveryCharter.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != charter or not audit_u1_mechanism_discovery_charter(stored):
        raise ValueError("U1 discovery charter failed reload verification")
    print(f"WROTE {args.output} {stored.charter_evidence_hash}", flush=True)
    return stored


def run_check(args) -> U1MechanismDiscoveryCharter:
    inputs = load_inputs(args)
    stored = U1MechanismDiscoveryCharter.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_charter(
        registered_at=stored.registered_at,
        failure=inputs[0],
        contamination=inputs[1],
        universe=inputs[2],
        development=inputs[3],
        validation=inputs[4],
    )
    if stored != expected or not audit_u1_mechanism_discovery_charter(stored):
        raise ValueError("Stored U1 discovery charter differs from rebuild")
    print(f"PASS u1_discovery_charter={stored.charter_evidence_hash}", flush=True)
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome U1 mechanism-discovery charter."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT
    )
    parser.add_argument(
        "--r4-failure-result", type=Path, default=DEFAULT_R4_FAILURE_RESULT
    )
    parser.add_argument("--contamination", type=Path, default=DEFAULT_CONTAMINATION)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--development", type=Path, default=DEFAULT_DEVELOPMENT)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--discovery-output",
        type=Path,
        nargs="*",
        default=list(DEFAULT_DISCOVERY_OUTPUTS),
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
