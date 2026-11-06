import argparse
import hashlib
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_diagnostic_addendum import (
    R3MonthlyDiagnosticAddendum,
    audit_r3_monthly_diagnostic_addendum,
    build_r3_monthly_diagnostic_addendum,
)
from aurex.backtest_engine.research_engine import R3ResearchReplayResult
from aurex.backtest_engine.research_result import R3StudyResultLedger
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_LEDGER = DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_result_v1.json"
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_monthly_addendum_v1.json"
)


def primary_base_receipt(ledger: R3StudyResultLedger):
    matches = [
        receipt
        for receipt in ledger.replay_receipts
        if receipt.category == "OVERALL"
        and receipt.variant_id == ledger.primary_variant_id
        and receipt.cost_multiplier == Decimal("1")
    ]
    if len(matches) != 1:
        raise ValueError("R3 result ledger does not contain one primary base replay")
    return matches[0]


def corrected_monthly_returns(
    result: R3ResearchReplayResult,
) -> dict[str, Decimal]:
    month_end_equity: dict[str, Decimal] = {}
    for snapshot in result.equity_curve:
        interval_month = (snapshot.timestamp - timedelta(microseconds=1)).strftime(
            "%Y-%m"
        )
        month_end_equity[interval_month] = snapshot.equity
    final_month = (result.config.evaluation_end - timedelta(microseconds=1)).strftime(
        "%Y-%m"
    )
    month_end_equity[final_month] = result.metrics.final_equity
    returns: dict[str, Decimal] = {}
    prior_equity = result.metrics.initial_capital
    for month, ending_equity in sorted(month_end_equity.items()):
        returns[month] = ending_equity / prior_equity - Decimal("1")
        prior_equity = ending_equity
    return returns


def authoritative_addendum(
    *,
    generated_at: datetime,
    evidence_root: Path,
    ledger: R3StudyResultLedger,
) -> R3MonthlyDiagnosticAddendum:
    receipt = primary_base_receipt(ledger)
    artifact_path = evidence_root / receipt.artifact_relative_path
    if file_sha256(artifact_path) != receipt.artifact_sha256:
        raise ValueError("R3 primary replay artifact hash mismatch")
    result = R3ResearchReplayResult.model_validate_json(
        artifact_path.read_text(encoding="utf-8")
    )
    if result.result_evidence_hash != receipt.result_evidence_hash:
        raise ValueError("R3 primary replay result hash mismatch")
    corrected = corrected_monthly_returns(result)
    if len(ledger.monthly_net_returns) != 19 or "2025-01" not in ledger.monthly_net_returns:
        raise ValueError("R3 stored monthly diagnostic no longer matches the known defect")
    if len(corrected) != 18 or list(corrected)[0] != "2023-07" or list(corrected)[-1] != "2024-12":
        raise ValueError("R3 corrected monthly diagnostic has an unexpected boundary")
    return build_r3_monthly_diagnostic_addendum(
        generated_at=generated_at,
        status="POST_OUTCOME_DIAGNOSTIC_CORRECTION",
        result_ledger_evidence_hash=ledger.ledger_evidence_hash,
        primary_replay_result_evidence_hash=result.result_evidence_hash,
        primary_replay_artifact_sha256=receipt.artifact_sha256,
        builder_contract_hash=builder_contract_hash(),
        defect=(
            "The v1 monthly diagnostic grouped close snapshots by the close timestamp's "
            "calendar month. A 4h bar closing exactly at 00:00 UTC belongs to the "
            "interval ending in the prior month, which created an extraneous 2025-01 "
            "entry and shifted boundary-bar equity. Trades, portfolio accounting, "
            "folds, gates, and verdict do not use this diagnostic."
        ),
        correction_method="ATTRIBUTE_CLOSE_TO_TIMESTAMP_MINUS_ONE_MICROSECOND",
        original_monthly_net_returns=ledger.monthly_net_returns,
        corrected_monthly_net_returns=corrected,
        original_verdict=ledger.verdict,
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "audit_r3_monthly_returns.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_diagnostic_addendum.py",
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


def write_addendum(path: Path, addendum: R3MonthlyDiagnosticAddendum) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(addendum.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_create(args) -> R3MonthlyDiagnosticAddendum:
    if args.output.exists():
        raise ValueError("R3 monthly addendum already exists; use --check")
    ledger = R3StudyResultLedger.model_validate_json(
        args.ledger.read_text(encoding="utf-8")
    )
    addendum = authoritative_addendum(
        generated_at=datetime.now(UTC),
        evidence_root=args.evidence_root,
        ledger=ledger,
    )
    write_addendum(args.output, addendum)
    stored = R3MonthlyDiagnosticAddendum.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != addendum or not audit_r3_monthly_diagnostic_addendum(stored):
        raise ValueError("R3 monthly addendum failed reload verification")
    print(f"WROTE {args.output} {stored.addendum_evidence_hash}", flush=True)
    return stored


def run_check(args) -> R3MonthlyDiagnosticAddendum:
    ledger = R3StudyResultLedger.model_validate_json(
        args.ledger.read_text(encoding="utf-8")
    )
    stored = R3MonthlyDiagnosticAddendum.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_addendum(
        generated_at=stored.generated_at,
        evidence_root=args.evidence_root,
        ledger=ledger,
    )
    if stored != expected or not audit_r3_monthly_diagnostic_addendum(stored):
        raise ValueError("Stored R3 monthly addendum differs from its rebuild")
    print(
        "PASS "
        f"addendum={stored.addendum_evidence_hash} "
        f"months={stored.corrected_month_count} "
        f"verdict={stored.corrected_verdict}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create or verify the post-outcome R3 monthly diagnostic addendum."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.create:
            run_create(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
