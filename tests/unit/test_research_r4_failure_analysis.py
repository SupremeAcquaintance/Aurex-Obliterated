import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_engine import R3EquitySnapshot
from aurex.backtest_engine.research_r4_engine import R4ResearchTrade
from aurex.backtest_engine.research_r4_failure_analysis import (
    R4AvailabilitySummary,
    R4CostAttribution,
    R4DescriptiveFinding,
    R4DrawdownEpisode,
    R4ExitReasonSummary,
    R4FailureAnalysisPackage,
    R4FailureAnalysisResult,
    R4HoldingDurationSummary,
    R4QuarterSummary,
    R4RebalanceCohortSummary,
    R4SymbolContribution,
    audit_r4_failure_analysis_package,
    audit_r4_failure_analysis_result,
    build_r4_failure_analysis_result,
)
from aurex.backtest_engine.research_r4_failure_runner import (
    build_cost_attribution,
    build_drawdown_episodes,
    build_holding_summary,
    classify_failure,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r4_failure_analysis_package import (
    authoritative_package,
    load_analysis_inputs,
    source_file_hashes,
)

HASH = "a" * 64
START = datetime(2025, 1, 1, tzinfo=UTC)


class Args:
    evidence_root = Path("data/evidence")
    protocol = evidence_root / "r4_failure_analysis_protocol_v1.json"
    validation_bundle = evidence_root / "validation_2025_4h_bundle_v1.json"
    run_package = evidence_root / "r4_path_quality_run_package_v1.json"
    ledger = evidence_root / "r4_path_quality_result_v1.json"


@lru_cache(maxsize=1)
def package() -> R4FailureAnalysisPackage:
    inputs = load_analysis_inputs(Args())
    return authoritative_package(
        frozen_at=datetime(2026, 7, 27, 13, tzinfo=UTC),
        protocol=inputs[0],
        validation_bundle=inputs[1],
        run_package=inputs[2],
        ledger=inputs[3],
    )


def trade(
    *,
    sequence: int = 1,
    entry_at: datetime = START,
    exit_at: datetime = START + timedelta(days=3),
    raw_price_pl: str = "10",
    net_pl: str = "7",
) -> R4ResearchTrade:
    entry_fee = Decimal("1")
    exit_fee = Decimal("1")
    slippage = Decimal("1")
    return R4ResearchTrade(
        sequence=sequence,
        symbol="ALPHAUSDT",
        entry_at=entry_at,
        exit_at=exit_at,
        entry_bar_timestamp=entry_at,
        exit_bar_timestamp=exit_at,
        exit_reason="REBALANCE",
        raw_entry_price="100",
        entry_fill_price="101",
        raw_exit_price="110",
        exit_fill_price="109",
        stop_price="90",
        quantity="1",
        entry_notional="101",
        exit_notional="109",
        entry_fee=entry_fee,
        exit_fee=exit_fee,
        entry_slippage_cost=slippage,
        exit_slippage_cost="0",
        total_slippage_cost=slippage,
        raw_price_pl=raw_price_pl,
        net_pl=net_pl,
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


def synthetic_result() -> R4FailureAnalysisResult:
    findings = [
        R4DescriptiveFinding(
            finding_id=finding_id,
            dimension="SYNTHETIC",
            observation="Synthetic observation.",
            interpretation_limit="Synthetic test only.",
        )
        for finding_id in (
            "F-01-RAW-SIGNAL-EDGE",
            "F-02-MODELED-COSTS",
            "F-03-TEMPORAL-STABILITY",
            "F-04-LOMO-ROBUSTNESS",
            "F-05-CONCENTRATION",
            "F-06-AVAILABILITY",
            "F-07-DRAWDOWN-EXPOSURE",
        )
    ]
    return build_r4_failure_analysis_result(
        generated_at=datetime(2026, 7, 27, tzinfo=UTC),
        package_evidence_hash=HASH,
        failure_protocol_evidence_hash=HASH,
        run_package_evidence_hash=HASH,
        result_ledger_evidence_hash=HASH,
        cost_attribution=R4CostAttribution(
            raw_price_pl="-1",
            commission="1",
            slippage="1",
            modeled_costs="2",
            net_pl="-3",
            reconciliation_delta="0",
            reconciles=True,
            raw_profit_factor="0.9",
            net_profit_factor="0.8",
            raw_expectancy="-0.1",
            net_expectancy="-0.3",
            modeled_cost_per_trade="0.2",
        ),
        quarterly_summary=[
            R4QuarterSummary(
                fold_id=f"validation-fold-0{index}-2025q{index}",
                net_pl="-1",
                profit_factor="0.8",
                raw_price_pl="0",
                completed_trades=10,
                maximum_drawdown_percent="5",
                average_gross_exposure_percent="20",
                minimum_active_symbol_count_at_rebalance=33,
            )
            for index in range(1, 5)
        ],
        monthly_net_returns={
            f"2025-{month:02d}": Decimal("0") for month in range(1, 13)
        },
        exit_reason_summary=[
            R4ExitReasonSummary(
                exit_reason=reason,
                trades=0,
                raw_price_pl="0",
                net_pl="0",
                commission="0",
                slippage="0",
            )
            for reason in (
                "END_OF_WINDOW",
                "FIXED_STOP",
                "MARKET_TERMINATION_WRITE_OFF",
                "REBALANCE",
            )
        ],
        holding_duration_summary=[
            R4HoldingDurationSummary(
                bucket_id=bucket,
                trades=0,
                average_hours="0",
                raw_price_pl="0",
                net_pl="0",
            )
            for bucket in (
                "01_UP_TO_7_DAYS",
                "02_OVER_7_TO_14_DAYS",
                "03_OVER_14_DAYS",
            )
        ],
        rebalance_cohorts=[
            R4RebalanceCohortSummary(
                entry_at=START,
                trades=1,
                raw_price_pl="-1",
                net_pl="-3",
                commission="1",
                slippage="1",
            )
        ],
        symbol_contribution=[
            R4SymbolContribution(
                symbol=f"SYMBOL{index:02d}USDT",
                trades=0,
                raw_price_pl="0",
                net_pl="0",
                commission="0",
                slippage="0",
                leave_one_market_out_net_pl="-1",
            )
            for index in range(35)
        ],
        drawdown_episodes=[
            R4DrawdownEpisode(
                sequence=1,
                started_at=START,
                trough_at=START,
                recovered_at=None,
                ended_at=START + timedelta(hours=4),
                recovered=False,
                duration_snapshots=1,
                maximum_drawdown="1",
                maximum_drawdown_percent="0.1",
            )
        ],
        availability_summary=R4AvailabilitySummary(
            configured_terminal_markets=2,
            observed_availability_events=2,
            held_position_writeoffs=0,
            writeoff_net_pl="0",
            minimum_active_symbol_count_at_rebalance=33,
            average_active_symbol_count_at_rebalance="34",
            availability_caused_base_loss=False,
        ),
        positive_months=0,
        flat_months=12,
        negative_months=0,
        failure_classification="SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS",
        integrity_checks={"synthetic_integrity": True},
        findings=findings,
    )


def test_failure_package_binds_all_sources_and_outcomes() -> None:
    frozen = package()

    assert len(frozen.replay_result_evidence_hashes) == 42
    assert tuple(frozen.source_file_sha256) == tuple(source_file_hashes(Path.cwd()))
    assert frozen.preexisting_analysis_artifacts == []
    assert audit_r4_failure_analysis_package(frozen) is True


def test_failure_package_refuses_changed_source_set() -> None:
    payload = package().model_dump()
    payload["source_file_sha256"].pop(next(iter(payload["source_file_sha256"])))

    with pytest.raises(ValidationError, match="source files are fixed"):
        R4FailureAnalysisPackage.model_validate(rehash_package(payload))


def test_cost_attribution_reconciles_exactly() -> None:
    result = SimpleNamespace(trades=[trade()])

    attribution = build_cost_attribution(result)

    assert attribution.raw_price_pl == Decimal("10")
    assert attribution.modeled_costs == Decimal("3")
    assert attribution.net_pl == Decimal("7")
    assert attribution.reconciliation_delta == 0
    assert attribution.reconciles is True


def test_holding_duration_buckets_are_fixed_at_7_and_14_days() -> None:
    trades = [
        trade(sequence=1, exit_at=START + timedelta(days=7)),
        trade(sequence=2, exit_at=START + timedelta(days=14)),
        trade(sequence=3, exit_at=START + timedelta(days=15)),
    ]

    rows = build_holding_summary(trades)

    assert [row.trades for row in rows] == [1, 1, 1]


def test_failure_classification_prioritizes_raw_signal_then_costs() -> None:
    raw_negative = R4CostAttribution(
        raw_price_pl="-1",
        commission="1",
        slippage="1",
        modeled_costs="2",
        net_pl="-3",
        reconciliation_delta="0",
        reconciles=True,
        raw_profit_factor="0.9",
        net_profit_factor="0.8",
        raw_expectancy="-1",
        net_expectancy="-3",
        modeled_cost_per_trade="2",
    )
    cost_dominated = raw_negative.model_copy(
        update={"raw_price_pl": Decimal("1"), "net_pl": Decimal("-1")}
    )

    assert (
        classify_failure(
            cost_attribution=raw_negative,
            positive_quarters=1,
            lomo_fraction=Decimal("0"),
        )
        == "SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS"
    )
    assert (
        classify_failure(
            cost_attribution=cost_dominated,
            positive_quarters=1,
            lomo_fraction=Decimal("0"),
        )
        == "MODELED_COSTS_OVERWHELM_POSITIVE_RAW_EDGE"
    )


def test_drawdown_episode_closes_at_recovery() -> None:
    result = SimpleNamespace(
        equity_curve=[
            R3EquitySnapshot(
                timestamp=START,
                cash="999",
                marked_position_value="0",
                equity="999",
                gross_exposure_percent="0",
                open_positions=0,
                drawdown="1",
                drawdown_percent="0.1",
            ),
            R3EquitySnapshot(
                timestamp=START + timedelta(hours=4),
                cash="998",
                marked_position_value="0",
                equity="998",
                gross_exposure_percent="0",
                open_positions=0,
                drawdown="2",
                drawdown_percent="0.2",
            ),
            R3EquitySnapshot(
                timestamp=START + timedelta(hours=8),
                cash="1000",
                marked_position_value="0",
                equity="1000",
                gross_exposure_percent="0",
                open_positions=0,
                drawdown="0",
                drawdown_percent="0",
            ),
        ]
    )

    episodes = build_drawdown_episodes(result)

    assert len(episodes) == 1
    assert episodes[0].trough_at == START + timedelta(hours=4)
    assert episodes[0].recovered_at == START + timedelta(hours=8)


def test_failure_result_is_hash_audited_and_cannot_promote() -> None:
    result = synthetic_result()

    assert result.next_research_decision == (
        "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY"
    )
    assert result.creates_candidate is False
    assert result.permits_pine_parity_review is False
    assert result.creates_paper_eligibility is False
    assert result.creates_live_eligibility is False
    assert audit_r4_failure_analysis_result(result) is True
    assert R4FailureAnalysisResult.model_validate_json(
        result.model_dump_json()
    ) == result


def test_failure_result_refuses_promotion_even_with_recomputed_hash() -> None:
    payload = synthetic_result().model_dump()
    payload["permits_pine_parity_review"] = True

    with pytest.raises(ValidationError):
        R4FailureAnalysisResult.model_validate(rehash_result(payload))


def test_failure_analysis_scripts_support_direct_invocation() -> None:
    for script in [
        "scripts/freeze_r4_failure_analysis_package.py",
        "scripts/run_r4_failure_analysis.py",
    ]:
        completed = subprocess.run(
            [sys.executable, script, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
