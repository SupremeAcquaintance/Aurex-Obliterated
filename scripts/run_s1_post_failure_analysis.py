from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_development_outcome_audit import (  # noqa: E402
    S11DevelopmentOutcomeAudit,
)
from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S11DevelopmentOutcomeResult,
    S11IntervalOutcome,
)
from aurex.backtest_engine.s1_post_failure_analysis import (  # noqa: E402
    S1CostDecomposition,
    S1DrawdownChronology,
    S1ExposureEpisodeSummary,
    S1PostFailureAnalysisExecutionAudit,
    S1PostFailureAnalysisExecutionContract,
    S1PostFailureAnalysisProtocol,
    S1PostFailureAnalysisProtocolAudit,
    S1PostFailureAnalysisResult,
    S1TailConcentration,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_post_failure_analysis_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_post_failure_analysis_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s1_post_failure_analysis_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s1_post_failure_analysis_execution_audit_v1.json"
)
DEFAULT_OUTCOME_RESULT = Path("data/evidence/s1_1_development_outcome_result_v1.json")
DEFAULT_OUTCOME_AUDIT = Path("data/evidence/s1_1_development_outcome_audit_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_post_failure_analysis_result_v1.json")
RUNNER_PATH = Path("scripts/run_s1_post_failure_analysis.py")
MODEL_PATH = Path("src/aurex/backtest_engine/s1_post_failure_analysis.py")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            MODEL_PATH.as_posix(): file_sha256(PROJECT_ROOT / MODEL_PATH),
            RUNNER_PATH.as_posix(): file_sha256(PROJECT_ROOT / RUNNER_PATH),
        }
    )


def build_hashed(model_type, hash_field: str, **payload):
    provisional = model_type.model_construct(**payload, **{hash_field: "0" * 64})
    complete = provisional.model_dump(mode="json")
    complete[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model_type.model_validate(complete)


def load_ledger(path: Path) -> tuple[S11IntervalOutcome, ...]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                rows.append(S11IntervalOutcome.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"Invalid S1 outcome ledger row {line_number}") from exc
    return tuple(rows)


def gross_equity(rows: tuple[S11IntervalOutcome, ...]) -> Decimal:
    with localcontext() as context:
        context.prec = 80
        equity = Decimal("100")
        for row in rows:
            equity *= Decimal(1) + Decimal(row.gross_interval_return)
        return +equity


def drawdown_chronology(
    rows: tuple[S11IntervalOutcome, ...], *, basis: str
) -> S1DrawdownChronology:
    if not rows:
        raise ValueError("S1 drawdown analysis requires rows")
    field = "base_equity_after" if basis == "BASE" else "stress_equity_after"
    points: list[tuple[date, Decimal]] = [(rows[0].target_date, Decimal("100"))]
    points.extend((row.next_target_date, Decimal(getattr(row, field))) for row in rows)
    running_peak = points[0][1]
    running_peak_date = points[0][0]
    maximum = Decimal(0)
    episode_peak = running_peak
    episode_peak_date = running_peak_date
    trough = running_peak
    trough_date = running_peak_date
    trough_index = 0
    for index, (point_date, equity) in enumerate(points):
        if equity > running_peak:
            running_peak = equity
            running_peak_date = point_date
        decline = (running_peak - equity) / running_peak
        if decline > maximum:
            maximum = decline
            episode_peak = running_peak
            episode_peak_date = running_peak_date
            trough = equity
            trough_date = point_date
            trough_index = index
    recovery_date = next(
        (
            point_date
            for point_date, equity in points[trough_index + 1 :]
            if equity >= episode_peak
        ),
        None,
    )
    all_time_peak = max(equity for _, equity in points)
    terminal = points[-1][1]
    return S1DrawdownChronology(
        basis=basis,
        maximum_drawdown=str(maximum),
        peak_equity_usd=str(episode_peak),
        peak_date=episode_peak_date,
        trough_equity_usd=str(trough),
        trough_date=trough_date,
        recovery_date=recovery_date,
        recovered_before_development_end=recovery_date is not None,
        terminal_equity_usd=str(terminal),
        terminal_drawdown_from_peak=str((all_time_peak - terminal) / all_time_peak),
    )


def exposure_episode_summary(
    rows: tuple[S11IntervalOutcome, ...],
) -> S1ExposureEpisodeSummary:
    lengths: list[int] = []
    active = 0
    wins = losses = zeros = 0
    for row in rows:
        if row.desired_position == 1:
            active += 1
            gross = Decimal(row.gross_interval_return)
            wins += gross > 0
            losses += gross < 0
            zeros += gross == 0
        elif active:
            lengths.append(active)
            active = 0
    if active:
        lengths.append(active)
    nonzero = wins + losses
    return S1ExposureEpisodeSummary(
        long_interval_count=sum(lengths),
        long_episode_count=len(lengths),
        shortest_episode_intervals=min(lengths, default=0),
        longest_episode_intervals=max(lengths, default=0),
        mean_episode_intervals=(
            str(Decimal(sum(lengths)) / Decimal(len(lengths))) if lengths else "0"
        ),
        positive_long_interval_count=wins,
        negative_long_interval_count=losses,
        zero_long_interval_count=zeros,
        nonzero_long_interval_hit_rate=(str(Decimal(wins) / Decimal(nonzero)) if nonzero else None),
    )


def stress_tail_concentration(
    rows: tuple[S11IntervalOutcome, ...], *, count: int = 5
) -> S1TailConcentration:
    gains = sorted(
        (
            (Decimal(row.stress_interval_pnl_usd), row.interval_sequence)
            for row in rows
            if Decimal(row.stress_interval_pnl_usd) > 0
        ),
        key=lambda item: (-item[0], item[1]),
    )
    losses = sorted(
        (
            (Decimal(row.stress_interval_pnl_usd), row.interval_sequence)
            for row in rows
            if Decimal(row.stress_interval_pnl_usd) < 0
        ),
        key=lambda item: (item[0], item[1]),
    )
    if len(gains) < count or len(losses) < count:
        raise ValueError("S1 tail analysis has insufficient gain or loss observations")
    total_gain = sum((value for value, _ in gains), Decimal(0))
    total_loss = -sum((value for value, _ in losses), Decimal(0))
    return S1TailConcentration(
        total_positive_pnl_usd=str(total_gain),
        total_negative_pnl_abs_usd=str(total_loss),
        top_five_positive_pnl_share=str(
            sum((value for value, _ in gains[:count]), Decimal(0)) / total_gain
        ),
        bottom_five_negative_pnl_share=str(
            -sum((value for value, _ in losses[:count]), Decimal(0)) / total_loss
        ),
        top_interval_sequences=tuple(sequence for _, sequence in gains[:count]),
        bottom_interval_sequences=tuple(sequence for _, sequence in losses[:count]),
    )


def diagnostic_position_analysis(
    rows_by_candidate: dict[str, tuple[S11IntervalOutcome, ...]], *, primary_id: str
) -> tuple[int, tuple[str, ...], dict[str, str]]:
    primary = tuple(row.desired_position for row in rows_by_candidate[primary_id])
    diagnostic = {
        candidate_id: tuple(row.desired_position for row in rows)
        for candidate_id, rows in rows_by_candidate.items()
        if candidate_id != primary_id
    }
    duplicate_pairs = []
    ids = sorted(diagnostic)
    for left_index, left in enumerate(ids):
        for right in ids[left_index + 1 :]:
            if diagnostic[left] == diagnostic[right]:
                duplicate_pairs.append(f"{left}=={right}")
    agreement = {
        candidate_id: str(
            Decimal(sum(a == b for a, b in zip(primary, vector, strict=True)))
            / Decimal(len(primary))
        )
        for candidate_id, vector in sorted(diagnostic.items())
    }
    return len(set(diagnostic.values())), tuple(duplicate_pairs), agreement


def reconstruct_analysis(
    *,
    completed_at: datetime,
    protocol: S1PostFailureAnalysisProtocol,
    contract: S1PostFailureAnalysisExecutionContract,
    outcome_result: S11DevelopmentOutcomeResult,
    rows: tuple[S11IntervalOutcome, ...],
    protocol_path: Path,
    contract_path: Path,
    outcome_result_path: Path,
) -> S1PostFailureAnalysisResult:
    grouped = {
        candidate.candidate_id: tuple(
            row for row in rows if row.candidate_id == candidate.candidate_id
        )
        for candidate in outcome_result.candidate_outcomes
    }
    if set(map(len, grouped.values())) != {protocol.primary_interval_count}:
        raise ValueError("S1 failure-analysis candidate interval counts changed")
    primary_rows = grouped[protocol.primary_candidate_id]
    primary = next(
        item
        for item in outcome_result.candidate_outcomes
        if item.candidate_id == protocol.primary_candidate_id
    )
    with localcontext() as context:
        context.prec = 80
        gross_final = gross_equity(primary_rows)
        base_final = Decimal(primary.base_final_equity_usd)
        stress_final = Decimal(primary.stress_final_equity_usd)
        base_return = Decimal(primary.base_net_total_return)
        stress_return = Decimal(primary.stress_net_total_return)
        cost = S1CostDecomposition(
            charged_fill_count=sum(row.fill_count for row in primary_rows),
            gross_final_equity_usd=str(gross_final),
            gross_total_return=str(gross_final / Decimal("100") - 1),
            base_final_equity_usd=str(base_final),
            base_total_return=str(base_return),
            base_cost_drag_usd=str(gross_final - base_final),
            base_cost_drag_return_points=str((gross_final - base_final) / Decimal("100")),
            stress_final_equity_usd=str(stress_final),
            stress_total_return=str(stress_return),
            stress_cost_drag_usd=str(gross_final - stress_final),
            stress_cost_drag_return_points=str((gross_final - stress_final) / Decimal("100")),
            base_to_stress_incremental_drag_usd=str(base_final - stress_final),
            stress_to_base_positive_return_retention_ratio=(
                str(stress_return / base_return) if base_return > 0 else None
            ),
        )
    unique_count, duplicate_pairs, agreement = diagnostic_position_analysis(
        grouped, primary_id=protocol.primary_candidate_id
    )
    failed = tuple(
        gate.gate_id for gate in outcome_result.primary_gate_results if gate.status == "FAIL"
    )
    return build_hashed(
        S1PostFailureAnalysisResult,
        "result_evidence_hash",
        completed_at=completed_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(contract_path),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        outcome_result_file_sha256=file_sha256(outcome_result_path),
        outcome_result_evidence_hash=outcome_result.result_evidence_hash,
        outcome_ledger_file_sha256=file_sha256(PROJECT_ROOT / protocol.outcome_ledger_path),
        primary_failed_gate_ids=failed,
        cost_decomposition=cost,
        base_drawdown=drawdown_chronology(primary_rows, basis="BASE"),
        stress_drawdown=drawdown_chronology(primary_rows, basis="STRESS"),
        exposure_episodes=exposure_episode_summary(primary_rows),
        stress_tail_concentration=stress_tail_concentration(primary_rows),
        primary_annual_base_returns=primary.annual_base_returns,
        diagnostic_unique_position_vector_count=unique_count,
        diagnostic_duplicate_pairs=duplicate_pairs,
        primary_diagnostic_position_agreement=agreement,
    )


def load_authority(args):
    protocol = S1PostFailureAnalysisProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = S1PostFailureAnalysisProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    contract = S1PostFailureAnalysisExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    contract_audit = S1PostFailureAnalysisExecutionAudit.model_validate_json(
        args.contract_audit.read_text(encoding="utf-8")
    )
    outcome_result = S11DevelopmentOutcomeResult.model_validate_json(
        args.outcome_result.read_text(encoding="utf-8")
    )
    outcome_audit = S11DevelopmentOutcomeAudit.model_validate_json(
        args.outcome_audit.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract.runner_contract_hash != runner_contract_hash()
        or protocol.outcome_result_evidence_hash != outcome_result.result_evidence_hash
        or protocol.outcome_audit_evidence_hash != outcome_audit.audit_evidence_hash
        or file_sha256(PROJECT_ROOT / protocol.outcome_ledger_path)
        != protocol.outcome_ledger_file_sha256
    ):
        raise ValueError("S1 failure-analysis execution authority changed")
    return protocol, contract, outcome_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the one-shot S1 failure analysis.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--outcome-result", type=Path, default=DEFAULT_OUTCOME_RESULT)
    parser.add_argument("--outcome-audit", type=Path, default=DEFAULT_OUTCOME_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"S1 failure-analysis result exists: {args.output}")
    protocol, contract, outcome_result = load_authority(args)
    rows = load_ledger(PROJECT_ROOT / protocol.outcome_ledger_path)
    if len(rows) != protocol.outcome_ledger_row_count:
        raise SystemExit("S1 failure-analysis ledger row count changed")
    result = reconstruct_analysis(
        completed_at=datetime.now(UTC),
        protocol=protocol,
        contract=contract,
        outcome_result=outcome_result,
        rows=rows,
        protocol_path=args.protocol,
        contract_path=args.contract,
        outcome_result_path=args.outcome_result,
    )
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(
        result.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} decision={result.decision} "
        f"gross_return={result.cost_decomposition.gross_total_return} "
        f"base_return={result.cost_decomposition.base_total_return} "
        f"stress_return={result.cost_decomposition.stress_total_return} "
        "validation=0 holdout=0 variants=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
