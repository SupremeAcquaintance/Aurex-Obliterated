import argparse
import sys
from pathlib import Path

from aurex.backtest_engine.research_r4_run_package import R4RunPackage
from aurex.backtest_engine.research_r4_study_runner import (
    audit_r4_validation_artifacts,
    execute_r4_validation,
)

try:
    from scripts.freeze_r4_run_package import (
        DEFAULT_DEVELOPMENT_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_EXECUTION,
        DEFAULT_PROTOCOL,
        DEFAULT_UNIVERSE,
        DEFAULT_VALIDATION_BUNDLE,
        load_package_inputs,
    )
    from scripts.freeze_r4_run_package import DEFAULT_OUTPUT as DEFAULT_PACKAGE
except ModuleNotFoundError:
    from freeze_r4_run_package import (  # type: ignore[no-redef]
        DEFAULT_DEVELOPMENT_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_EXECUTION,
        DEFAULT_PROTOCOL,
        DEFAULT_UNIVERSE,
        DEFAULT_VALIDATION_BUNDLE,
        load_package_inputs,
    )
    from freeze_r4_run_package import (
        DEFAULT_OUTPUT as DEFAULT_PACKAGE,
    )


def load_validation_inputs(args):
    inputs = load_package_inputs(args)
    package = R4RunPackage.model_validate_json(
        args.package.read_text(encoding="utf-8")
    )
    return (*inputs, package)


def run_validation(args):
    inputs = load_validation_inputs(args)
    ledger = execute_r4_validation(
        protocol=inputs[2],
        validation_bundle=inputs[3],
        execution_specification=inputs[4],
        run_package=inputs[6],
        market_data=inputs[5],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
    )
    passed = sum(gate.passed for gate in ledger.gates)
    print(
        "WROTE "
        f"{inputs[6].result_ledger_relative_path} {ledger.ledger_evidence_hash} "
        f"verdict={ledger.verdict} gates={passed}/{len(ledger.gates)}",
        flush=True,
    )
    return ledger


def run_audit(args):
    inputs = load_validation_inputs(args)
    ledger = audit_r4_validation_artifacts(
        protocol=inputs[2],
        validation_bundle=inputs[3],
        execution_specification=inputs[4],
        run_package=inputs[6],
        market_data=inputs[5],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
        deterministic_replay=args.full_replay,
    )
    print(
        "PASS "
        f"r4_ledger={ledger.ledger_evidence_hash} "
        f"replays={ledger.completed_replay_count} "
        f"verdict={ledger.verdict} full_replay={args.full_replay}",
        flush=True,
    )
    return ledger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Execute once or audit the frozen R4 validation campaign."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--full-replay", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument(
        "--development-bundle",
        type=Path,
        default=DEFAULT_DEVELOPMENT_BUNDLE,
    )
    parser.add_argument(
        "--validation-bundle",
        type=Path,
        default=DEFAULT_VALIDATION_BUNDLE,
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--execution", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_validation(args)
        else:
            run_audit(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
