import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.development_bundle import safe_evidence_path
from aurex.backtest_engine.research_r4_execution_spec import (
    R4ExecutionSpecification,
    audit_r4_execution_specification,
)
from aurex.backtest_engine.research_r4_failure_protocol import (
    R4_FAILURE_ANALYSIS_DIMENSIONS,
    R4_FAILURE_PROHIBITIONS,
    R4_FAILURE_REQUIRED_OUTPUTS,
    R4_KNOWN_INSPECTED_OUTCOME_FIELDS,
    R4FailureAnalysisProtocol,
    R4KnownOutcomeBoundary,
    audit_r4_failure_analysis_protocol,
    build_r4_failure_analysis_protocol,
)
from aurex.backtest_engine.research_r4_protocol import (
    R4CandidateProtocol,
    audit_r4_candidate_protocol,
)
from aurex.backtest_engine.research_r4_result import (
    R4ValidationResultLedger,
    audit_r4_validation_result_ledger,
)
from aurex.backtest_engine.research_r4_run_package import (
    R4RunPackage,
    audit_r4_run_package,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from aurex.backtest_engine.validation_bundle import ValidationDatasetBundle

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_CANDIDATE = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_candidate_v1.json"
DEFAULT_VALIDATION_BUNDLE = (
    DEFAULT_EVIDENCE_ROOT / "validation_2025_4h_bundle_v1.json"
)
DEFAULT_EXECUTION = (
    DEFAULT_EVIDENCE_ROOT / "r4_path_quality_execution_spec_v1.json"
)
DEFAULT_RUN_PACKAGE = (
    DEFAULT_EVIDENCE_ROOT / "r4_path_quality_run_package_v1.json"
)
DEFAULT_RESULT = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_result_v1.json"
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "r4_failure_analysis_protocol_v1.json"
)
DEFAULT_ANALYSIS_PACKAGE = (
    DEFAULT_EVIDENCE_ROOT / "r4_failure_analysis_package_v1.json"
)
DEFAULT_ANALYSIS_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "r4_failure_analysis_result_v1.json"
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_r4_failure_analysis.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r4_failure_protocol.py",
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


def load_inputs(args):
    candidate = R4CandidateProtocol.model_validate_json(
        args.candidate.read_text(encoding="utf-8")
    )
    validation_bundle = ValidationDatasetBundle.model_validate_json(
        args.validation_bundle.read_text(encoding="utf-8")
    )
    execution = R4ExecutionSpecification.model_validate_json(
        args.execution.read_text(encoding="utf-8")
    )
    run_package = R4RunPackage.model_validate_json(
        args.run_package.read_text(encoding="utf-8")
    )
    result = R4ValidationResultLedger.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if not audit_r4_candidate_protocol(candidate):
        raise ValueError("R4 candidate protocol failed its hash audit")
    if not audit_r4_execution_specification(execution):
        raise ValueError("R4 execution specification failed its hash audit")
    if not audit_r4_run_package(run_package):
        raise ValueError("R4 run package failed its hash audit")
    if not audit_r4_validation_result_ledger(result):
        raise ValueError("R4 result ledger failed its hash audit")
    if (
        validation_bundle.r4_candidate_protocol_evidence_hash
        != candidate.protocol_evidence_hash
        or execution.r4_candidate_protocol_evidence_hash
        != candidate.protocol_evidence_hash
        or execution.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
        or run_package.candidate_protocol_evidence_hash
        != candidate.protocol_evidence_hash
        or run_package.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
        or run_package.execution_specification_evidence_hash
        != execution.specification_evidence_hash
        or result.candidate_protocol_evidence_hash
        != candidate.protocol_evidence_hash
        or result.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
        or result.execution_specification_evidence_hash
        != execution.specification_evidence_hash
        or result.run_package_evidence_hash != run_package.package_evidence_hash
    ):
        raise ValueError("R4 failure-analysis inputs do not share one lineage")
    if result.verdict != "RETIRE_R4_CANDIDATE":
        raise ValueError("R4 failure analysis requires the frozen rejection")
    if len(result.replay_receipts) != 42:
        raise ValueError("R4 failure analysis requires all 42 replay receipts")
    for receipt in result.replay_receipts:
        path = safe_evidence_path(args.evidence_root, receipt.artifact_relative_path)
        if file_sha256(path) != receipt.artifact_sha256:
            raise ValueError(f"R4 replay artifact hash mismatch: {receipt.run_id}")
    return candidate, validation_bundle, execution, run_package, result


def authoritative_protocol(
    *,
    registered_at: datetime,
    candidate: R4CandidateProtocol,
    validation_bundle: ValidationDatasetBundle,
    execution: R4ExecutionSpecification,
    run_package: R4RunPackage,
    result: R4ValidationResultLedger,
) -> R4FailureAnalysisProtocol:
    primary = next(
        receipt
        for receipt in result.replay_receipts
        if receipt.run_id == "overall--path_quality_spot_v1--cost-1"
    )
    double_cost = next(
        receipt
        for receipt in result.replay_receipts
        if receipt.run_id == "overall--path_quality_spot_v1--cost-2"
    )
    replay_hashes = {
        receipt.run_id: receipt.result_evidence_hash
        for receipt in result.replay_receipts
    }
    return build_r4_failure_analysis_protocol(
        registered_at=registered_at,
        candidate_protocol_evidence_hash=candidate.protocol_evidence_hash,
        validation_dataset_bundle_evidence_hash=(
            validation_bundle.bundle_evidence_hash
        ),
        execution_specification_evidence_hash=execution.specification_evidence_hash,
        run_package_evidence_hash=run_package.package_evidence_hash,
        result_ledger_evidence_hash=result.ledger_evidence_hash,
        replay_result_evidence_hashes=replay_hashes,
        known_outcome_boundary=R4KnownOutcomeBoundary(
            failed_gate_ids=[
                gate.gate_id for gate in result.gates if not gate.passed
            ],
            base_cost_net_pl=primary.metrics.net_pl,
            base_cost_profit_factor=primary.metrics.profit_factor,
            base_cost_raw_profit_factor=primary.metrics.raw_profit_factor,
            base_cost_maximum_drawdown_percent=(
                primary.metrics.maximum_drawdown_percent
            ),
            double_cost_net_pl=double_cost.metrics.net_pl,
        ),
        known_outcome_fields_inspected=R4_KNOWN_INSPECTED_OUTCOME_FIELDS,
        allowed_data_scopes=[
            "R4_RESULT_LEDGER",
            "R4_STORED_REPLAY_ARTIFACTS",
            "R4_VALIDATION_BUNDLE_METADATA",
        ],
        analysis_dimensions=R4_FAILURE_ANALYSIS_DIMENSIONS,
        required_outputs=R4_FAILURE_REQUIRED_OUTPUTS,
        prohibited_actions=R4_FAILURE_PROHIBITIONS,
        allowed_next_decisions=[
            "STOP_ALL_STRATEGY_RESEARCH_BRANCH",
            "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY",
        ],
        preexisting_analysis_artifacts=[],
        builder_contract_hash=builder_contract_hash(),
    )


def write_protocol(path: Path, protocol: R4FailureAnalysisProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if R4FailureAnalysisProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("R4 failure protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R4FailureAnalysisProtocol:
    if args.output.exists():
        raise ValueError("Frozen R4 failure protocol exists; use --check")
    if args.analysis_package.exists() or args.analysis_result.exists():
        raise ValueError("R4 failure-analysis artifact predates its protocol")
    inputs = load_inputs(args)
    protocol = authoritative_protocol(
        registered_at=datetime.now(UTC),
        candidate=inputs[0],
        validation_bundle=inputs[1],
        execution=inputs[2],
        run_package=inputs[3],
        result=inputs[4],
    )
    write_protocol(args.output, protocol)
    stored = R4FailureAnalysisProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != protocol or not audit_r4_failure_analysis_protocol(stored):
        raise ValueError("R4 failure protocol failed reload verification")
    print(
        f"WROTE {args.output} {stored.protocol_evidence_hash} "
        f"replays={len(stored.replay_result_evidence_hashes)}",
        flush=True,
    )
    return stored


def run_check(args) -> R4FailureAnalysisProtocol:
    inputs = load_inputs(args)
    stored = R4FailureAnalysisProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        registered_at=stored.registered_at,
        candidate=inputs[0],
        validation_bundle=inputs[1],
        execution=inputs[2],
        run_package=inputs[3],
        result=inputs[4],
    )
    if stored != expected or not audit_r4_failure_analysis_protocol(stored):
        raise ValueError("Stored R4 failure protocol differs from rebuild")
    print(
        "PASS "
        f"r4_failure_protocol={stored.protocol_evidence_hash} "
        f"replays={len(stored.replay_result_evidence_hashes)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the post-outcome R4 failure-analysis protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--validation-bundle", type=Path, default=DEFAULT_VALIDATION_BUNDLE
    )
    parser.add_argument("--execution", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--run-package", type=Path, default=DEFAULT_RUN_PACKAGE)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--analysis-package", type=Path, default=DEFAULT_ANALYSIS_PACKAGE
    )
    parser.add_argument(
        "--analysis-result", type=Path, default=DEFAULT_ANALYSIS_RESULT
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
