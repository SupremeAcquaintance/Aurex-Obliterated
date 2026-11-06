from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r4_engine import R4ReplayMetrics
from aurex.backtest_engine.research_r4_result import (
    R4_MONTH_KEYS,
    R4_REQUIRED_GATE_IDS,
    R4GateResult,
    R4ValidationReplayReceipt,
    R4ValidationResultLedger,
    audit_r4_validation_result_ledger,
    build_r4_validation_result_ledger,
)
from aurex.backtest_engine.universe import universe_evidence_hash

HASH = "a" * 64


def metrics() -> R4ReplayMetrics:
    return R4ReplayMetrics(
        initial_capital="1000",
        final_equity="1100",
        net_pl="100",
        gross_profit="150",
        gross_loss="50",
        profit_factor="3",
        raw_gross_profit="180",
        raw_gross_loss="40",
        raw_profit_factor="4.5",
        maximum_drawdown="75",
        maximum_drawdown_percent="7.5",
        completed_trades=120,
        winning_trades=70,
        losing_trades=50,
        accepted_entries=120,
        rejected_opportunities=20,
        total_commission="10",
        total_slippage="5",
        turnover="25",
        active_days=300,
        average_gross_exposure_percent="70",
        maximum_gross_exposure_percent="95",
        symbol_positive_raw_profit={"ALPHAUSDT": Decimal("180")},
        maximum_single_symbol_gross_profit_fraction="0.2",
        top_five_gross_profit_fraction="0.6",
        termination_writeoff_count=1,
        termination_writeoff_net_pl="-10",
        minimum_active_symbol_count_at_rebalance=33,
        average_active_symbol_count_at_rebalance="34",
    )


def receipts() -> list[R4ValidationReplayReceipt]:
    return [
        R4ValidationReplayReceipt(
            run_id=f"synthetic-run-{index:02d}",
            category="OVERALL",
            cost_multiplier="1",
            artifact_relative_path=f"results/synthetic-run-{index:02d}.json",
            request_evidence_hash=HASH,
            result_evidence_hash=HASH,
            artifact_sha256=HASH,
            metrics=metrics(),
        )
        for index in range(42)
    ]


def ledger(*, failed_gate: str | None = None) -> R4ValidationResultLedger:
    gates = [
        R4GateResult(
            gate_id=gate_id,
            passed=gate_id != failed_gate,
            observed="synthetic",
            requirement="synthetic",
        )
        for gate_id in R4_REQUIRED_GATE_IDS
    ]
    return build_r4_validation_result_ledger(
        generated_at=datetime(2026, 7, 23, tzinfo=UTC),
        universe_manifest_evidence_hash=HASH,
        development_dataset_bundle_evidence_hash=HASH,
        validation_dataset_bundle_evidence_hash=HASH,
        candidate_protocol_evidence_hash=HASH,
        execution_specification_evidence_hash=HASH,
        run_package_evidence_hash=HASH,
        market_data_evidence_hash=HASH,
        replay_receipts=receipts(),
        monthly_net_returns={month: Decimal("0") for month in R4_MONTH_KEYS},
        positive_quarterly_folds=4,
        leave_one_market_out_positive_fraction="1",
        base_cost_termination_writeoff_count=1,
        base_cost_termination_writeoff_net_pl="-10",
        gates=gates,
    )


def rehash(payload: dict) -> dict:
    payload["ledger_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "ledger_evidence_hash"
        }
    )
    return payload


def test_r4_ledger_only_permits_pine_review_when_every_gate_passes() -> None:
    accepted = ledger()
    rejected = ledger(failed_gate="positive_quarterly_folds")

    assert accepted.verdict == "PERMIT_PINE_PARITY_REVIEW_ONLY"
    assert rejected.verdict == "RETIRE_R4_CANDIDATE"
    assert accepted.creates_eligible_strategy is False
    assert accepted.creates_paper_eligibility is False
    assert accepted.creates_live_eligibility is False
    assert accepted.permits_pine_parity_review is True
    assert audit_r4_validation_result_ledger(accepted) is True


def test_r4_ledger_refuses_replaced_gate_even_with_recomputed_hash() -> None:
    payload = ledger().model_dump()
    payload["gates"][-1]["gate_id"] = "zzz-not-a-required-gate"

    with pytest.raises(ValidationError, match="preserve every required gate"):
        R4ValidationResultLedger.model_validate(rehash(payload))


def test_r4_ledger_refuses_verdict_that_disagrees_with_gate_failure() -> None:
    payload = ledger(failed_gate="base_cost_net_pl").model_dump()
    payload["verdict"] = "PERMIT_PINE_PARITY_REVIEW_ONLY"

    with pytest.raises(ValidationError, match="all-gates rule"):
        R4ValidationResultLedger.model_validate(rehash(payload))


def test_r4_ledger_requires_exact_validation_months() -> None:
    payload = ledger().model_dump()
    payload["monthly_net_returns"].pop("2025-12")

    with pytest.raises(ValidationError, match="exact 12 validation months"):
        R4ValidationResultLedger.model_validate(rehash(payload))

