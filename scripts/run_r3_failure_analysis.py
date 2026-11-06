import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_failure_analysis import (
    R3FailureAnalysisPackage,
    R3FailureAnalysisResult,
    audit_r3_failure_analysis_package,
    audit_r3_failure_analysis_result,
)
from aurex.backtest_engine.research_failure_runner import (
    build_failure_analysis_result,
)

try:
    from scripts.freeze_r3_failure_analysis_package import (
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_FAILURE_PROTOCOL,
        DEFAULT_MONTHLY_ADDENDUM,
        DEFAULT_PACKAGE_OUTPUT,
        DEFAULT_RESULT_LEDGER,
        DEFAULT_RESULT_OUTPUT,
        builder_contract_hash,
        load_inputs,
    )
except ModuleNotFoundError:
    from freeze_r3_failure_analysis_package import (  # type: ignore[no-redef]
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_FAILURE_PROTOCOL,
        DEFAULT_MONTHLY_ADDENDUM,
        DEFAULT_PACKAGE_OUTPUT,
        DEFAULT_RESULT_LEDGER,
        DEFAULT_RESULT_OUTPUT,
        builder_contract_hash,
        load_inputs,
    )


def load_verified_package(path: Path, project_root: Path) -> R3FailureAnalysisPackage:
    package = R3FailureAnalysisPackage.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_r3_failure_analysis_package(package):
        raise ValueError("R3 failure-analysis package failed its hash audit")
    if package.builder_contract_hash != builder_contract_hash():
        raise ValueError("R3 failure-analysis builder contract changed")
    for relative_path, expected_hash in package.source_file_sha256.items():
        source_path = (project_root / relative_path).resolve()
        if not source_path.is_relative_to(project_root.resolve()):
            raise ValueError("R3 failure-analysis source escaped the project root")
        if file_sha256(source_path) != expected_hash:
            raise ValueError(
                f"R3 failure-analysis source hash changed: {relative_path}"
            )
    return package


def write_result(path: Path, result: R3FailureAnalysisResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_analysis(args) -> R3FailureAnalysisResult:
    if args.result_output.exists():
        raise ValueError("R3 failure-analysis result already exists; use --check")
    protocol, ledger, addendum, bundle = load_inputs(args)
    project_root = Path(__file__).resolve().parents[1]
    package = load_verified_package(args.package, project_root)
    result = build_failure_analysis_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        package=package,
        ledger=ledger,
        addendum=addendum,
        bundle=bundle,
        evidence_root=args.evidence_root,
    )
    write_result(args.result_output, result)
    stored = R3FailureAnalysisResult.model_validate_json(
        args.result_output.read_text(encoding="utf-8")
    )
    if stored != result or not audit_r3_failure_analysis_result(stored):
        raise ValueError("R3 failure-analysis result failed reload verification")
    print(
        "WROTE "
        f"{args.result_output} {stored.result_evidence_hash} "
        f"decision={stored.next_research_decision} "
        f"criteria={sum(stored.continuation_criteria.values())}/"
        f"{len(stored.continuation_criteria)}",
        flush=True,
    )
    return stored


def run_check(args) -> R3FailureAnalysisResult:
    protocol, ledger, addendum, bundle = load_inputs(args)
    project_root = Path(__file__).resolve().parents[1]
    package = load_verified_package(args.package, project_root)
    stored = R3FailureAnalysisResult.model_validate_json(
        args.result_output.read_text(encoding="utf-8")
    )
    rebuilt = build_failure_analysis_result(
        generated_at=stored.generated_at,
        protocol=protocol,
        package=package,
        ledger=ledger,
        addendum=addendum,
        bundle=bundle,
        evidence_root=args.evidence_root,
    )
    if stored != rebuilt or not audit_r3_failure_analysis_result(stored):
        raise ValueError("Stored R3 failure analysis differs from its rebuild")
    print(
        "PASS "
        f"failure_result={stored.result_evidence_hash} "
        f"decision={stored.next_research_decision} "
        f"findings={len(stored.findings)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or verify the frozen R3 descriptive failure analysis."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence"))
    parser.add_argument(
        "--failure-protocol", type=Path, default=DEFAULT_FAILURE_PROTOCOL
    )
    parser.add_argument("--result-ledger", type=Path, default=DEFAULT_RESULT_LEDGER)
    parser.add_argument(
        "--monthly-addendum", type=Path, default=DEFAULT_MONTHLY_ADDENDUM
    )
    parser.add_argument("--dataset-bundle", type=Path, default=DEFAULT_DATASET_BUNDLE)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE_OUTPUT)
    parser.add_argument("--result-output", type=Path, default=DEFAULT_RESULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_analysis(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
