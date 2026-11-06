import argparse
import sys
from pathlib import Path

from aurex.backtest_engine.research_r4_failure_analysis import (
    R4FailureAnalysisPackage,
)
from aurex.backtest_engine.research_r4_failure_runner import (
    audit_r4_failure_analysis,
    execute_r4_failure_analysis,
)

try:
    from scripts.freeze_r4_failure_analysis_package import (
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_LEDGER,
        DEFAULT_OUTPUT,
        DEFAULT_PROTOCOL,
        DEFAULT_RUN_PACKAGE,
        DEFAULT_VALIDATION_BUNDLE,
        load_analysis_inputs,
    )
except ModuleNotFoundError:
    from freeze_r4_failure_analysis_package import (  # type: ignore[no-redef]
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_LEDGER,
        DEFAULT_OUTPUT,
        DEFAULT_PROTOCOL,
        DEFAULT_RUN_PACKAGE,
        DEFAULT_VALIDATION_BUNDLE,
        load_analysis_inputs,
    )


def load_run_inputs(args):
    inputs = load_analysis_inputs(args)
    package = R4FailureAnalysisPackage.model_validate_json(
        args.package.read_text(encoding="utf-8")
    )
    return (*inputs, package)


def run_analysis(args):
    inputs = load_run_inputs(args)
    result = execute_r4_failure_analysis(
        protocol=inputs[0],
        validation_bundle=inputs[1],
        run_package=inputs[2],
        ledger=inputs[3],
        package=inputs[4],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
    )
    print(
        "WROTE "
        f"{inputs[4].expected_result_relative_path} "
        f"{result.result_evidence_hash} "
        f"classification={result.failure_classification} "
        f"decision={result.next_research_decision}",
        flush=True,
    )
    return result


def run_audit(args):
    inputs = load_run_inputs(args)
    result = audit_r4_failure_analysis(
        protocol=inputs[0],
        validation_bundle=inputs[1],
        run_package=inputs[2],
        ledger=inputs[3],
        package=inputs[4],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
    )
    print(
        "PASS "
        f"r4_failure_result={result.result_evidence_hash} "
        f"classification={result.failure_classification} "
        f"decision={result.next_research_decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Execute once or audit the frozen R4 failure analysis."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--validation-bundle", type=Path, default=DEFAULT_VALIDATION_BUNDLE
    )
    parser.add_argument("--run-package", type=Path, default=DEFAULT_RUN_PACKAGE)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--package", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_analysis(args)
        else:
            run_audit(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
