from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_u1_engine import U1ReplayMetrics
from aurex.backtest_engine.research_u1_result import (
    U1_MONTH_KEYS,
    U1_REQUIRED_GATE_IDS,
    U1GateResult,
    U1ReplayReceipt,
    U1ResultLedger,
    audit_u1_result_ledger,
    build_u1_result_ledger,
)
from aurex.backtest_engine.universe import universe_evidence_hash

HASH = "a" * 64


def metrics(
    *,
    net_pl: str = "100",
    maximum_drawdown_percent: str = "10",
    realized_equity_volatility: str = "0.40",
    return_to_drawdown: str = "1",
) -> U1ReplayMetrics:
    net = Decimal(net_pl)
    return U1ReplayMetrics(
        initial_capital="1000",
        final_equity=Decimal("1000") + net,
        net_pl=net,
        gross_profit="200",
        gross_loss="-100",
        profit_factor="2",
        raw_gross_profit="220",
        raw_gross_loss="-80",
        raw_profit_factor="2.75",
        maximum_drawdown="100",
        maximum_drawdown_percent=maximum_drawdown_percent,
        completed_trades=120,
        winning_trades=70,
        losing_trades=50,
        accepted_entries=120,
        rejected_opportunities=0,
        total_commission="10",
        total_slippage="5",
        turnover="20",
        active_days=700,
        average_gross_exposure_percent="70",
        maximum_gross_exposure_percent="100",
        realized_equity_volatility=realized_equity_volatility,
        return_to_drawdown=return_to_drawdown,
        average_target_exposure="0.7",
        minimum_target_exposure="0.2",
        maximum_target_exposure="1",
        symbol_positive_raw_profit={"BTCUSDT": Decimal("50")},
        maximum_single_symbol_gross_profit_fraction="0.20",
        top_five_gross_profit_fraction="0.60",
        termination_writeoff_count=0,
        termination_writeoff_net_pl="0",
        minimum_active_symbol_count_at_rebalance=35,
        average_active_symbol_count_at_rebalance="35",
    )


def receipts(primary: U1ReplayMetrics) -> list[U1ReplayReceipt]:
    return [
        U1ReplayReceipt(
            run_id=f"run-{index:02d}",
            category="OVERALL",
            variant_role="PRIMARY",
            cost_multiplier="1",
            artifact_relative_path=f"results/run-{index:02d}.json",
            request_evidence_hash=HASH,
            result_evidence_hash=HASH,
            artifact_sha256=HASH,
            metrics=primary,
        )
        for index in range(47)
    ]


def gates(*, failed_gate: str | None = None) -> list[U1GateResult]:
    return [
        U1GateResult(
            gate_id=gate_id,
            passed=gate_id != failed_gate,
            observed="test",
            requirement="test",
        )
        for gate_id in U1_REQUIRED_GATE_IDS
    ]


def ledger(*, failed_gate: str | None = None) -> U1ResultLedger:
    primary = metrics()
    benchmark = metrics(
        maximum_drawdown_percent="15",
        realized_equity_volatility="0.50",
        return_to_drawdown="0.8",
    )
    return build_u1_result_ledger(
        generated_at=datetime(2026, 7, 27, 15, tzinfo=UTC),
        discovery_charter_evidence_hash=HASH,
        theory_screen_evidence_hash=HASH,
        universe_manifest_evidence_hash=HASH,
        development_dataset_bundle_evidence_hash=HASH,
        contamination_ledger_evidence_hash=HASH,
        primary_protocol_evidence_hash=HASH,
        execution_specification_evidence_hash=HASH,
        run_package_evidence_hash=HASH,
        market_data_evidence_hash=HASH,
        replay_receipts=receipts(primary),
        monthly_net_returns={month: Decimal("0") for month in U1_MONTH_KEYS},
        positive_temporal_folds=8,
        leave_one_market_out_positive_fraction="1",
        all_replay_audits_passed=True,
        base_cost_termination_writeoff_count=0,
        base_cost_termination_writeoff_net_pl="0",
        primary_base_metrics=primary,
        benchmark_base_metrics=benchmark,
        gates=gates(failed_gate=failed_gate),
    )


def test_u1_result_all_gates_only_permits_separate_validation_freeze() -> None:
    result = ledger()

    assert result.verdict == (
        "PERMIT_FREEZE_2025_INTERNAL_VALIDATION_CANDIDATE"
    )
    assert result.development_passes_all_gates is True
    assert result.permits_freeze_2025_internal_validation_candidate is True
    assert result.permits_validation_data_access is False
    assert result.creates_eligible_strategy is False
    assert result.creates_paper_eligibility is False
    assert result.creates_live_eligibility is False
    assert audit_u1_result_ledger(result) is True


def test_u1_result_any_gate_failure_stops_mechanism() -> None:
    result = ledger(failed_gate="primary_net_pl")

    assert result.verdict == "STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
    assert result.development_passes_all_gates is False
    assert result.permits_freeze_2025_internal_validation_candidate is False


def test_u1_result_refuses_forged_permit_verdict() -> None:
    payload = ledger(failed_gate="primary_net_pl").model_dump()
    payload["verdict"] = "PERMIT_FREEZE_2025_INTERNAL_VALIDATION_CANDIDATE"
    payload["development_passes_all_gates"] = True
    payload["permits_freeze_2025_internal_validation_candidate"] = True
    payload["ledger_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "ledger_evidence_hash"
        }
    )

    with pytest.raises(ValidationError, match="all-gates rule"):
        U1ResultLedger.model_validate(payload)
