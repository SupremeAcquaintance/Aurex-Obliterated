import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_engine import (
    R3EquitySnapshot,
    R3OpportunityRecord,
    R3ResearchReplayResult,
)
from aurex.backtest_engine.research_failure_analysis import (
    R3_FAILURE_CORRECTED_MONTHS,
    R3_FAILURE_DIAGNOSTIC_SYMBOLS,
    R3_FAILURE_EXIT_REASONS,
    R3_FAILURE_FINDING_IDS,
    R3_FAILURE_FOLD_IDS,
    R3_FAILURE_VARIANT_ROLES,
    R3BreadthRow,
    R3CostTurnoverRow,
    R3DescriptiveFinding,
    R3DiagnosticQuarterRow,
    R3DrawdownEpisode,
    R3ExitReasonQuarterRow,
    R3FailureAnalysisPackage,
    R3HorizonComparisonRow,
    R3PrimaryQuarterRow,
    R3SymbolQuarterRow,
    audit_r3_failure_analysis_package,
    build_r3_failure_analysis_result,
)
from aurex.backtest_engine.research_failure_runner import (
    build_breadth_rows,
    build_drawdown_episodes,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r3_failure_analysis_package import (
    authoritative_package,
    load_inputs,
)

START = datetime(2024, 1, 1, tzinfo=UTC)
HASH = "a" * 64


class Args:
    failure_protocol = Path("data/evidence/r3_failure_analysis_protocol_v1.json")
    result_ledger = Path("data/evidence/r3_cross_sectional_momentum_result_v1.json")
    monthly_addendum = Path(
        "data/evidence/r3_cross_sectional_momentum_monthly_addendum_v1.json"
    )
    dataset_bundle = Path("data/evidence/development_4h_dataset_bundle_v1.json")


def package() -> R3FailureAnalysisPackage:
    protocol, ledger, addendum, bundle = load_inputs(Args())
    return authoritative_package(
        frozen_at=datetime(2026, 7, 23, tzinfo=UTC),
        protocol=protocol,
        ledger=ledger,
        addendum=addendum,
        bundle=bundle,
    )


def rehash_package(payload: dict) -> dict:
    payload["package_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "package_evidence_hash"
        }
    )
    return payload


def rehash_result(payload: dict) -> dict:
    payload["result_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "result_evidence_hash"
        }
    )
    return payload


def test_failure_package_freezes_formulas_sources_and_decision_rule() -> None:
    frozen = package()

    assert frozen.quarter_source == "INDEPENDENT_FOLD_REPLAYS"
    assert frozen.diagnostic_volatility_formula == (
        "SAMPLE_STDDEV_LOG_RETURNS_TIMES_SQRT_2190"
    )
    assert len(frozen.source_file_sha256) == 3
    assert len(frozen.continuation_criteria) == 5
    assert frozen.preexisting_analysis_artifacts == []
    assert audit_r3_failure_analysis_package(frozen) is True
    assert R3FailureAnalysisPackage.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_stored_failure_package_matches_its_authoritative_rebuild() -> None:
    stored = R3FailureAnalysisPackage.model_validate_json(
        Path("data/evidence/r3_failure_analysis_package_v1.json").read_text(
            encoding="utf-8"
        )
    )
    protocol, ledger, addendum, bundle = load_inputs(Args())
    rebuilt = authoritative_package(
        frozen_at=stored.frozen_at,
        protocol=protocol,
        ledger=ledger,
        addendum=addendum,
        bundle=bundle,
    )

    assert stored == rebuilt
    assert audit_r3_failure_analysis_package(stored) is True


def test_failure_package_refuses_removed_continuation_criterion() -> None:
    payload = package().model_dump()
    payload["continuation_criteria"].pop()

    with pytest.raises(ValidationError, match="continuation criteria are fixed"):
        R3FailureAnalysisPackage.model_validate(rehash_package(payload))


def test_failure_package_refuses_missing_frozen_source() -> None:
    payload = package().model_dump()
    payload["source_file_sha256"].pop(
        "src/aurex/backtest_engine/research_failure_runner.py"
    )

    with pytest.raises(ValidationError, match="source files are fixed"):
        R3FailureAnalysisPackage.model_validate(rehash_package(payload))


def test_drawdown_episode_builder_preserves_recovery_and_open_episode() -> None:
    snapshots = [
        R3EquitySnapshot(
            timestamp=START + timedelta(hours=4 * index),
            cash="1000",
            marked_position_value="0",
            equity=str(1000 - drawdown),
            gross_exposure_percent="0",
            open_positions=0,
            drawdown=str(drawdown),
            drawdown_percent=str(drawdown / 10),
        )
        for index, drawdown in enumerate([0, 10, 20, 0, 5])
    ]
    result = R3ResearchReplayResult.model_construct(equity_curve=snapshots)

    episodes = build_drawdown_episodes(result)

    assert len(episodes) == 2
    assert episodes[0].recovered is True
    assert episodes[0].maximum_drawdown == 20
    assert episodes[0].duration_snapshots == 2
    assert episodes[1].recovered is False
    assert episodes[1].maximum_drawdown == 5


def opportunity(
    *,
    rebalance_at: datetime,
    symbol: str,
    score: str,
    selected: bool,
    accepted: bool,
    reason: str,
) -> R3OpportunityRecord:
    return R3OpportunityRecord(
        rebalance_at=rebalance_at,
        symbol=symbol,
        score=score,
        rank=1 if Decimal(score) > 0 else None,
        signal_at=rebalance_at - timedelta(hours=4),
        reference_at=rebalance_at - timedelta(days=1),
        signal_close="10",
        reference_close="9",
        signal_atr="1",
        signal_volatility="0.1",
        selected_by_rank=selected,
        accepted_entry=accepted,
        reason=reason,
    )


def test_breadth_builder_uses_strictly_positive_scores() -> None:
    opportunities = [
        opportunity(
            rebalance_at=START,
            symbol="AAAUSDT",
            score="0.2",
            selected=True,
            accepted=True,
            reason="ENTRY_ACCEPTED",
        ),
        opportunity(
            rebalance_at=START,
            symbol="BBBUSDT",
            score="0",
            selected=False,
            accepted=False,
            reason="NON_POSITIVE_MOMENTUM",
        ),
        opportunity(
            rebalance_at=START + timedelta(days=1),
            symbol="AAAUSDT",
            score="-0.1",
            selected=False,
            accepted=False,
            reason="NON_POSITIVE_MOMENTUM",
        ),
    ]
    result = R3ResearchReplayResult.model_construct(opportunities=opportunities)

    rows = build_breadth_rows(result)

    assert [row.positive_market_count for row in rows] == [1, 0]
    assert rows[0].average_positive_score == Decimal("0.2")
    assert rows[1].average_positive_score is None


def synthetic_result(*, criterion_value: bool):
    criteria = {
        "ALL_THREE_HORIZONS_POSITIVE_AT_BASE_AND_DOUBLE_COST": criterion_value,
        "HORIZON_POSITIVE_FOLDS_STRICTLY_IMPROVE_FAST_TO_PRIMARY_TO_SLOW": True,
        "PRIMARY_CONCENTRATION_GATES_PASSED": True,
        "PRIMARY_LEAVE_ONE_MARKET_OUT_FRACTION_AT_LEAST_0_80": True,
        "PRIMARY_TEMPORAL_GATE_REMAINS_FAILED_AND_UNCHANGED": True,
    }
    quarters = [
        R3PrimaryQuarterRow(
            fold_id=fold_id,
            evaluation_start=START,
            evaluation_end=START + timedelta(days=90),
            net_pl="1",
            profit_factor="1.1",
            maximum_drawdown_percent="1",
            completed_trades=1,
            winning_trades=1,
            losing_trades=0,
            total_commission="0",
            total_slippage="0",
            turnover="1",
            average_gross_exposure_percent="1",
            maximum_gross_exposure_percent="1",
            rebalance_count=1,
            average_positive_market_breadth="1",
            minimum_positive_market_breadth=1,
            insufficient_breadth_rebalances=0,
        )
        for fold_id in R3_FAILURE_FOLD_IDS
    ]
    costs = [
        R3CostTurnoverRow(
            variant_id=variant_id,
            variant_role=role,
            cost_multiplier=cost_multiplier,
            net_pl="1",
            profit_factor="1.1",
            maximum_drawdown_percent="1",
            completed_trades=1,
            total_commission="0",
            total_slippage="0",
            turnover="1",
        )
        for variant_id, role in R3_FAILURE_VARIANT_ROLES.items()
        for cost_multiplier in (Decimal("1"), Decimal("1.5"), Decimal("2"))
    ]
    diagnostics = [
        R3DiagnosticQuarterRow(
            fold_id=fold_id,
            symbol=symbol,
            total_return="0",
            annualized_log_return_volatility="0",
        )
        for fold_id in R3_FAILURE_FOLD_IDS
        for symbol in R3_FAILURE_DIAGNOSTIC_SYMBOLS
    ]
    exits = [
        R3ExitReasonQuarterRow(
            fold_id=fold_id,
            exit_reason=reason,
            trades=0,
            raw_price_pl="0",
            net_pl="0",
            commission="0",
            slippage="0",
        )
        for fold_id in R3_FAILURE_FOLD_IDS
        for reason in R3_FAILURE_EXIT_REASONS
    ]
    horizons = [
        R3HorizonComparisonRow(
            variant_id=variant_id,
            variant_role=role,
            lookback_bars=(index + 1) * 10,
            rebalance_bars=(index + 1) * 5,
            base_net_pl="1",
            base_profit_factor="1.1",
            base_maximum_drawdown_percent="1",
            double_cost_net_pl="1",
            positive_quarterly_folds=index + 2,
        )
        for index, (variant_id, role) in enumerate(R3_FAILURE_VARIANT_ROLES.items())
    ]
    findings = [
        R3DescriptiveFinding(
            finding_id=finding_id,
            dimension="TEST",
            observation="Synthetic observation",
            interpretation_limit="Synthetic limitation",
        )
        for finding_id in R3_FAILURE_FINDING_IDS
    ]
    return build_r3_failure_analysis_result(
        generated_at=START,
        status="COMPLETE_DESCRIPTIVE_ANALYSIS",
        package_evidence_hash=HASH,
        failure_protocol_evidence_hash=HASH,
        result_ledger_evidence_hash=HASH,
        monthly_addendum_evidence_hash=HASH,
        original_verdict="NO_CANDIDATE",
        primary_quarters=quarters,
        cost_and_turnover=costs,
        diagnostic_quarters=diagnostics,
        drawdown_episodes=[
            R3DrawdownEpisode(
                sequence=1,
                started_at=START,
                trough_at=START,
                recovered_at=START,
                ended_at=START,
                recovered=True,
                duration_snapshots=1,
                maximum_drawdown="1",
                maximum_drawdown_percent="1",
            )
        ],
        exit_reasons_by_quarter=exits,
        horizon_comparison=horizons,
        breadth_at_rebalance=[
            R3BreadthRow(
                rebalance_at=START,
                positive_market_count=1,
                selected_market_count=1,
                accepted_entry_count=1,
                insufficient_breadth=False,
                average_positive_score="0.1",
            )
        ],
        symbol_contribution_by_quarter=[
            R3SymbolQuarterRow(
                fold_id=fold_id,
                symbol="AAAUSDT",
                trades=1,
                raw_price_pl="1",
                net_pl="1",
                commission="0",
                slippage="0",
                fixed_stop_exits=0,
                rebalance_exits=1,
                end_of_window_exits=0,
            )
            for fold_id in R3_FAILURE_FOLD_IDS
        ],
        corrected_monthly_net_returns={
            month: Decimal("0") for month in R3_FAILURE_CORRECTED_MONTHS
        },
        continuation_criteria=criteria,
        findings=findings,
        creates_candidate=False,
        changes_r3_verdict=False,
        opens_sealed_partition=False,
    )


def test_result_decision_is_mechanical_and_never_creates_candidate() -> None:
    proposed = synthetic_result(criterion_value=True)
    stopped = synthetic_result(criterion_value=False)

    assert proposed.next_research_decision == "PROPOSE_BOUNDED_R3_1"
    assert stopped.next_research_decision == "STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY"
    assert proposed.creates_candidate is False
    assert proposed.changes_r3_verdict is False
    assert proposed.opens_sealed_partition is False


def test_result_refuses_duplicate_diagnostic_key() -> None:
    payload = synthetic_result(criterion_value=True).model_dump()
    payload["diagnostic_quarters"][0] = payload["diagnostic_quarters"][1]

    with pytest.raises(ValidationError, match="exact diagnostic grid"):
        type(synthetic_result(criterion_value=True)).model_validate(
            rehash_result(payload)
        )


def test_failure_analysis_scripts_support_direct_invocation() -> None:
    for script in [
        "scripts/freeze_r3_failure_analysis_package.py",
        "scripts/run_r3_failure_analysis.py",
    ]:
        completed = subprocess.run(
            [sys.executable, script, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
