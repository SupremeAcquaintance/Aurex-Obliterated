import argparse
import platform
import sys
from pathlib import Path

import pydantic

from aurex.backtest_engine.research_run_package import (
    R3RunPackage,
    audit_r3_run_package,
)
from aurex.backtest_engine.research_study_runner import (
    audit_r3_study_artifacts,
    execute_r3_study,
)

try:
    from scripts.freeze_r3_execution_spec import DEFAULT_EXECUTION_SPEC_OUTPUT
    from scripts.freeze_r3_mechanism_study import (
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_PROTOCOL_OUTPUT,
        DEFAULT_UNIVERSE_MANIFEST,
    )
    from scripts.freeze_r3_run_package import (
        DEFAULT_RUN_PACKAGE_OUTPUT,
        builder_contract_hash,
        load_package_inputs,
    )
except ModuleNotFoundError:
    from freeze_r3_execution_spec import (  # type: ignore[no-redef]
        DEFAULT_EXECUTION_SPEC_OUTPUT,
    )
    from freeze_r3_mechanism_study import (  # type: ignore[no-redef]
        DEFAULT_DATASET_BUNDLE,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_PROTOCOL_OUTPUT,
        DEFAULT_UNIVERSE_MANIFEST,
    )
    from freeze_r3_run_package import (  # type: ignore[no-redef]
        DEFAULT_RUN_PACKAGE_OUTPUT,
        builder_contract_hash,
        load_package_inputs,
    )


def load_verified_run_package(path: Path) -> R3RunPackage:
    package = R3RunPackage.model_validate_json(path.read_text(encoding="utf-8"))
    if not audit_r3_run_package(package):
        raise ValueError("R3 run package failed its evidence-hash audit")
    if package.builder_contract_hash != builder_contract_hash():
        raise ValueError("R3 run-package builder contract has changed")
    if package.python_version != platform.python_version():
        raise ValueError("R3 run package requires its frozen Python version")
    if package.pydantic_version != pydantic.__version__:
        raise ValueError("R3 run package requires its frozen Pydantic version")
    return package


def load_study_inputs(args):
    universe, bundle, protocol, execution_specification, market_data = (
        load_package_inputs(args)
    )
    package = load_verified_run_package(args.run_package)
    return universe, bundle, protocol, execution_specification, market_data, package


def run_study(args) -> int:
    _, _, protocol, execution_specification, market_data, package = load_study_inputs(
        args
    )
    ledger = execute_r3_study(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=package,
        market_data=market_data,
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
    )
    primary = next(
        receipt
        for receipt in ledger.replay_receipts
        if receipt.category == "OVERALL"
        and receipt.variant_id == ledger.primary_variant_id
        and receipt.cost_multiplier == 1
    )
    passed = sum(gate.passed for gate in ledger.gates)
    print(
        "COMPLETE "
        f"verdict={ledger.verdict} "
        f"ledger={ledger.ledger_evidence_hash} "
        f"primary_net_pl={primary.metrics.net_pl} "
        f"primary_pf={primary.metrics.profit_factor} "
        f"primary_max_dd_pct={primary.metrics.maximum_drawdown_percent} "
        f"gates={passed}/{len(ledger.gates)}",
        flush=True,
    )
    return 0


def check_study(args, *, deterministic: bool) -> int:
    _, _, protocol, execution_specification, market_data, package = load_study_inputs(
        args
    )
    ledger = audit_r3_study_artifacts(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=package,
        market_data=market_data,
        evidence_root=args.evidence_root,
        project_root=Path(__file__).resolve().parents[1],
        deterministic_replay=deterministic,
    )
    passed = sum(gate.passed for gate in ledger.gates)
    print(
        "PASS "
        f"ledger={ledger.ledger_evidence_hash} "
        f"verdict={ledger.verdict} "
        f"replays={ledger.completed_replay_count} "
        f"gates={passed}/{len(ledger.gates)} "
        f"deterministic={str(deterministic).lower()}",
        flush=True,
    )
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or audit the one-shot Aurex R3 development mechanism study."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--deterministic-check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--universe-manifest", type=Path, default=DEFAULT_UNIVERSE_MANIFEST
    )
    parser.add_argument("--dataset-bundle", type=Path, default=DEFAULT_DATASET_BUNDLE)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_OUTPUT)
    parser.add_argument(
        "--execution-specification",
        type=Path,
        default=DEFAULT_EXECUTION_SPEC_OUTPUT,
    )
    parser.add_argument("--run-package", type=Path, default=DEFAULT_RUN_PACKAGE_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            return run_study(args)
        return check_study(args, deterministic=args.deterministic_check)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
