from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_engine import R3ReplayMetrics
from aurex.backtest_engine.research_r31_result import (
    R31_MONTH_KEYS,
    R31_REQUIRED_GATE_IDS,
    R31GateResult,
    R31StudyReplayReceipt,
    R31StudyResultLedger,
    audit_r31_study_result_ledger,
    build_r31_study_result_ledger,
)
from aurex.backtest_engine.universe import universe_evidence_hash

HASH = "a" * 64


def metrics() -> R3ReplayMetrics:
    return R3ReplayMetrics(
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
    )


def receipts() -> list[R31StudyReplayReceipt]:
    return [
        R31StudyReplayReceipt(
            run_id=f"synthetic-run-{index:02d}",
            category="OVERALL",
            cost_multiplier="1",
            artifact_relative_path=f"results/synthetic-run-{index:02d}.json",
            request_evidence_hash=HASH,
            result_evidence_hash=HASH,
            artifact_sha256=HASH,
            metrics=metrics(),
        )
        for index in range(44)
    ]


def ledger(*, failed_gate: str | None = None) -> R31StudyResultLedger:
    gates = [
        R31GateResult(
            gate_id=gate_id,
            passed=gate_id != failed_gate,
            observed="synthetic",
            requirement="synthetic",
        )
        for gate_id in R31_REQUIRED_GATE_IDS
    ]
    return build_r31_study_result_ledger(
        generated_at=datetime(2026, 7, 23, tzinfo=UTC),
        universe_manifest_evidence_hash=HASH,
        development_dataset_bundle_evidence_hash=HASH,
        protocol_evidence_hash=HASH,
        execution_specification_evidence_hash=HASH,
        run_package_evidence_hash=HASH,
        market_data_evidence_hash=HASH,
        planned_replay_count=44,
        replay_receipts=receipts(),
        monthly_net_returns={month: Decimal("0") for month in R31_MONTH_KEYS},
        positive_quarterly_folds=6,
        leave_one_market_out_positive_fraction="1",
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


def test_r31_ledger_only_permits_preregistration_when_every_gate_passes() -> None:
    accepted = ledger()
    rejected = ledger(failed_gate="primary_positive_quarterly_folds")

    assert accepted.verdict == "PERMIT_R4_PREREGISTRATION"
    assert rejected.verdict == "STOP_FAMILY"
    assert accepted.creates_eligible_strategy is False
    assert accepted.opens_validation_partition is False
    assert audit_r31_study_result_ledger(accepted) is True
    assert R31StudyResultLedger.model_validate_json(
        accepted.model_dump_json()
    ) == accepted


def test_r31_ledger_refuses_replaced_gate_even_with_recomputed_hash() -> None:
    payload = ledger().model_dump()
    payload["gates"][-1]["gate_id"] = "zzz-not-a-required-gate"

    with pytest.raises(ValidationError, match="preserve every required gate"):
        R31StudyResultLedger.model_validate(rehash(payload))


def test_r31_ledger_refuses_verdict_that_disagrees_with_gate_failure() -> None:
    payload = ledger(failed_gate="primary_net_pl").model_dump()
    payload["verdict"] = "PERMIT_R4_PREREGISTRATION"

    with pytest.raises(ValidationError, match="all-gates rule"):
        R31StudyResultLedger.model_validate(rehash(payload))


def test_r31_ledger_requires_exact_development_months() -> None:
    payload = ledger().model_dump()
    payload["monthly_net_returns"].pop("2024-12")

    with pytest.raises(ValidationError, match="exact 18 development months"):
        R31StudyResultLedger.model_validate(rehash(payload))
