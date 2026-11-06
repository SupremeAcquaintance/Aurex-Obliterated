import argparse
import hashlib
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.research_diagnostic_addendum import (
    R3MonthlyDiagnosticAddendum,
    audit_r3_monthly_diagnostic_addendum,
)
from aurex.backtest_engine.research_failure_protocol import (
    R3_FAILURE_ANALYSIS_DIMENSIONS,
    R3_FAILURE_PROHIBITIONS,
    R3FailureAnalysisProtocol,
    R3KnownOutcomeBoundary,
    audit_r3_failure_analysis_protocol,
    build_r3_failure_analysis_protocol,
)
from aurex.backtest_engine.research_result import R3StudyResultLedger
from aurex.backtest_engine.research_run_package import (
    R3RunPackage,
    audit_r3_run_package,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_RUN_PACKAGE = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_run_package_v1.json"
)
DEFAULT_RESULT_LEDGER = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_result_v1.json"
)
DEFAULT_MONTHLY_ADDENDUM = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_monthly_addendum_v1.json"
)
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "r3_failure_analysis_protocol_v1.json"
DEFAULT_ANALYSIS_RESULT = DEFAULT_EVIDENCE_ROOT / "r3_failure_analysis_result_v1.json"


def primary_base_receipt(ledger: R3StudyResultLedger):
    matches = [
        receipt
        for receipt in ledger.replay_receipts
        if receipt.category == "OVERALL"
        and receipt.variant_id == ledger.primary_variant_id
        and receipt.cost_multiplier == Decimal("1")
    ]
    if len(matches) != 1:
        raise ValueError("R3 ledger does not contain one primary base receipt")
    return matches[0]


def authoritative_protocol(
    *,
    registered_at: datetime,
    package: R3RunPackage,
    ledger: R3StudyResultLedger,
    addendum: R3MonthlyDiagnosticAddendum,
) -> R3FailureAnalysisProtocol:
    if ledger.run_package_evidence_hash != package.package_evidence_hash:
        raise ValueError("R3 failure inputs disagree on the run package")
    if addendum.result_ledger_evidence_hash != ledger.ledger_evidence_hash:
        raise ValueError("R3 failure inputs disagree on the result ledger")
    failed = [gate for gate in ledger.gates if not gate.passed]
    if len(failed) != 1 or failed[0].gate_id != "primary_positive_quarterly_folds":
        raise ValueError("R3 failure boundary no longer matches the frozen verdict")
    primary = primary_base_receipt(ledger)
    return build_r3_failure_analysis_protocol(
        protocol_id="r3-cross-sectional-momentum-failure-analysis-v1",
        protocol_version="1.0.0",
        registered_at=registered_at,
        status="FROZEN_POST_OUTCOME_PRE_ANALYSIS",
        run_package_evidence_hash=package.package_evidence_hash,
        result_ledger_evidence_hash=ledger.ledger_evidence_hash,
        monthly_addendum_evidence_hash=addendum.addendum_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            package.development_dataset_bundle_evidence_hash
        ),
        replay_result_evidence_hashes={
            receipt.run_id: receipt.result_evidence_hash
            for receipt in ledger.replay_receipts
        },
        known_outcome_boundary=R3KnownOutcomeBoundary(
            primary_net_pl=primary.metrics.net_pl,
            primary_profit_factor=primary.metrics.profit_factor,
            primary_maximum_drawdown_percent=(
                primary.metrics.maximum_drawdown_percent
            ),
        ),
        allowed_data_scopes=[
            "R3_STORED_REPLAY_ARTIFACTS",
            "R3_DEVELOPMENT_DECISION_OHLC_2023_2024",
            "R3_DIAGNOSTIC_BTC_ETH_SOL_OHLC_2023_2024",
        ],
        analysis_dimensions=R3_FAILURE_ANALYSIS_DIMENSIONS,
        required_outputs=[
            "corrected_monthly_return_table",
            "cost_and_turnover_table",
            "diagnostic_benchmark_quarter_table",
            "drawdown_episode_table",
            "exit_reason_by_quarter_table",
            "limitations_and_noncausal_findings",
            "momentum_horizon_comparison_table",
            "next_research_decision",
            "positive_market_breadth_table",
            "primary_quarter_table",
            "symbol_contribution_by_quarter_table",
        ],
        prohibited_actions=R3_FAILURE_PROHIBITIONS,
        allowed_next_decisions=[
            "PROPOSE_BOUNDED_R3_1",
            "STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY",
        ],
        analysis_is_descriptive_only=True,
        creates_candidate=False,
        opens_sealed_partition=False,
        preexisting_analysis_artifacts=[],
        builder_contract_hash=builder_contract_hash(),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r3_failure_analysis.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_failure_protocol.py",
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


def load_inputs(args):
    package = R3RunPackage.model_validate_json(
        args.run_package.read_text(encoding="utf-8")
    )
    ledger = R3StudyResultLedger.model_validate_json(
        args.result_ledger.read_text(encoding="utf-8")
    )
    addendum = R3MonthlyDiagnosticAddendum.model_validate_json(
        args.monthly_addendum.read_text(encoding="utf-8")
    )
    if not audit_r3_run_package(package):
        raise ValueError("R3 run package failed its hash audit")
    if not audit_r3_monthly_diagnostic_addendum(addendum):
        raise ValueError("R3 monthly addendum failed its hash audit")
    return package, ledger, addendum


def write_protocol(path: Path, protocol: R3FailureAnalysisProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(protocol.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R3FailureAnalysisProtocol:
    if args.output.exists():
        raise ValueError("R3 failure-analysis protocol already exists; use --check")
    if args.analysis_result.exists():
        raise ValueError("R3 failure-analysis result predates its protocol")
    package, ledger, addendum = load_inputs(args)
    protocol = authoritative_protocol(
        registered_at=datetime.now(UTC),
        package=package,
        ledger=ledger,
        addendum=addendum,
    )
    write_protocol(args.output, protocol)
    stored = R3FailureAnalysisProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != protocol or not audit_r3_failure_analysis_protocol(stored):
        raise ValueError("R3 failure-analysis protocol failed reload verification")
    print(f"WROTE {args.output} {stored.protocol_evidence_hash}", flush=True)
    return stored


def run_check(args) -> R3FailureAnalysisProtocol:
    package, ledger, addendum = load_inputs(args)
    stored = R3FailureAnalysisProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        registered_at=stored.registered_at,
        package=package,
        ledger=ledger,
        addendum=addendum,
    )
    if stored != expected or not audit_r3_failure_analysis_protocol(stored):
        raise ValueError("Stored R3 failure protocol differs from its rebuild")
    print(
        "PASS "
        f"failure_protocol={stored.protocol_evidence_hash} "
        f"replays={len(stored.replay_result_evidence_hashes)} "
        f"verdict={stored.known_outcome_boundary.verdict}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the post-outcome R3 failure-analysis scope."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--run-package", type=Path, default=DEFAULT_RUN_PACKAGE)
    parser.add_argument("--result-ledger", type=Path, default=DEFAULT_RESULT_LEDGER)
    parser.add_argument(
        "--monthly-addendum", type=Path, default=DEFAULT_MONTHLY_ADDENDUM
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--analysis-result", type=Path, default=DEFAULT_ANALYSIS_RESULT)
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
