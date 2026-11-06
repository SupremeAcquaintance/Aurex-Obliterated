import argparse
import sys
from pathlib import Path

from aurex.backtest_engine.research_r31_run_package import R31RunPackage
from aurex.backtest_engine.research_r31_study_runner import (
    audit_r31_study_artifacts,
    execute_r31_study,
)

try:
    from scripts.freeze_r31_run_package import (
        DEFAULT_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_EXECUTION,
        DEFAULT_PROTOCOL,
        DEFAULT_UNIVERSE,
        load_package_inputs,
    )
    from scripts.freeze_r31_run_package import (
        DEFAULT_OUTPUT as DEFAULT_PACKAGE,
    )
except ModuleNotFoundError:
    from freeze_r31_run_package import (  # type: ignore[no-redef]
        DEFAULT_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_EXECUTION,
        DEFAULT_PROTOCOL,
        DEFAULT_UNIVERSE,
        load_package_inputs,
    )
    from freeze_r31_run_package import (
        DEFAULT_OUTPUT as DEFAULT_PACKAGE,
    )


def load_study_inputs(args):
    universe, bundle, protocol, specification, market_data = load_package_inputs(args)
    package = R31RunPackage.model_validate_json(
        args.package.read_text(encoding="utf-8")
    )
    return universe, bundle, protocol, specification, market_data, package


def run_study(args):
    inputs = load_study_inputs(args)
    ledger = execute_r31_study(
        protocol=inputs[2],
        execution_specification=inputs[3],
        run_package=inputs[5],
        market_data=inputs[4],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
    )
    passed = sum(gate.passed for gate in ledger.gates)
    print(
        "WROTE "
        f"{inputs[5].result_ledger_relative_path} {ledger.ledger_evidence_hash} "
        f"verdict={ledger.verdict} gates={passed}/{len(ledger.gates)}",
        flush=True,
    )
    return ledger


def run_audit(args):
    inputs = load_study_inputs(args)
    ledger = audit_r31_study_artifacts(
        protocol=inputs[2],
        execution_specification=inputs[3],
        run_package=inputs[5],
        market_data=inputs[4],
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
        deterministic_replay=args.full_replay,
    )
    print(
        "PASS "
        f"r31_ledger={ledger.ledger_evidence_hash} "
        f"replays={ledger.completed_replay_count} "
        f"verdict={ledger.verdict} full_replay={args.full_replay}",
        flush=True,
    )
    return ledger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Execute once or audit the frozen R3.1 mechanism study."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--full-replay", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
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
