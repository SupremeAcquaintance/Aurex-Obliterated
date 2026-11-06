import argparse
import sys
from pathlib import Path

from aurex.backtest_engine.research_u1_run_package import U1RunPackage
from aurex.backtest_engine.research_u1_study_runner import (
    audit_u1_study_artifacts,
    execute_u1_study,
)

try:
    from scripts.freeze_u1_run_package import (
        DEFAULT_CHARTER,
        DEFAULT_CONTAMINATION,
        DEFAULT_DEVELOPMENT,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_EXECUTION,
        DEFAULT_PROTOCOL,
        DEFAULT_SCREEN,
        DEFAULT_UNIVERSE,
        load_package_inputs,
    )
    from scripts.freeze_u1_run_package import DEFAULT_OUTPUT as DEFAULT_PACKAGE
except ModuleNotFoundError:
    from freeze_u1_run_package import (  # type: ignore[no-redef]
        DEFAULT_CHARTER,
        DEFAULT_CONTAMINATION,
        DEFAULT_DEVELOPMENT,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_EXECUTION,
        DEFAULT_PROTOCOL,
        DEFAULT_SCREEN,
        DEFAULT_UNIVERSE,
        load_package_inputs,
    )
    from freeze_u1_run_package import (  # type: ignore[no-redef]
        DEFAULT_OUTPUT as DEFAULT_PACKAGE,
    )


def load_study_inputs(args):
    inputs = load_package_inputs(args)
    package = U1RunPackage.model_validate_json(
        args.package.read_text(encoding="utf-8")
    )
    return (*inputs, package)


def run_study(args):
    inputs = load_study_inputs(args)
    ledger = execute_u1_study(
        protocol=inputs[5],
        execution_specification=inputs[6],
        run_package=inputs[8],
        market_data=inputs[7],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
    )
    passed = sum(gate.passed for gate in ledger.gates)
    print(
        "WROTE "
        f"{inputs[8].result_ledger_relative_path} "
        f"{ledger.ledger_evidence_hash} verdict={ledger.verdict} "
        f"gates={passed}/{len(ledger.gates)}",
        flush=True,
    )
    return ledger


def run_audit(args):
    inputs = load_study_inputs(args)
    ledger = audit_u1_study_artifacts(
        protocol=inputs[5],
        execution_specification=inputs[6],
        run_package=inputs[8],
        market_data=inputs[7],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
        deterministic_replay=args.full_replay,
    )
    print(
        "PASS "
        f"u1_ledger={ledger.ledger_evidence_hash} "
        f"replays={ledger.completed_replay_count} "
        f"verdict={ledger.verdict} full_replay={args.full_replay}",
        flush=True,
    )
    return ledger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Execute once or audit the frozen U1 development campaign."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--full-replay", action="store_true")
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
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_study(args)
        else:
            run_audit(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
