from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_engine import R3ReplayMetrics
from aurex.backtest_engine.research_result import (
    R3_REQUIRED_GATE_IDS,
    R3GateResult,
    R3StudyReplayReceipt,
    R3StudyResultLedger,
    audit_r3_study_result_ledger,
    build_r3_study_result_ledger,
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


def ledger(*, failed_gate: str | None = None) -> R3StudyResultLedger:
    receipt = R3StudyReplayReceipt(
        run_id="overall--primary--cost-1",
        category="OVERALL",
        variant_id="primary",
        variant_role="PRIMARY",
        cost_multiplier="1",
        artifact_relative_path="results/overall.json",
        request_evidence_hash=HASH,
        result_evidence_hash=HASH,
        artifact_sha256=HASH,
        metrics=metrics(),
    )
    gates = [
        R3GateResult(
            gate_id=gate_id,
            passed=gate_id != failed_gate,
            observed="synthetic",
            requirement="synthetic",
        )
        for gate_id in R3_REQUIRED_GATE_IDS
    ]
    return build_r3_study_result_ledger(
        study_id="synthetic",
        study_version="1",
        generated_at=datetime(2026, 7, 22, tzinfo=UTC),
        status="COMPLETE",
        universe_manifest_evidence_hash=HASH,
        development_dataset_bundle_evidence_hash=HASH,
        protocol_evidence_hash=HASH,
        execution_specification_evidence_hash=HASH,
        run_package_evidence_hash=HASH,
        market_data_evidence_hash=HASH,
        planned_replay_count=1,
        replay_receipts=[receipt],
        primary_variant_id="primary",
        monthly_net_returns={"2024-01": Decimal("0.1")},
        positive_fold_counts={"primary": 6},
        leave_one_market_out_positive_fraction="1",
        supportive_falsification_variants=["fast"],
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


def test_result_ledger_advances_only_when_every_required_gate_passes() -> None:
    accepted = ledger()
    rejected = ledger(failed_gate="double_cost_net_pl")

    assert accepted.verdict == "ADVANCE_PRIMARY_TO_R4"
    assert rejected.verdict == "NO_CANDIDATE"
    assert audit_r3_study_result_ledger(accepted) is True
    assert R3StudyResultLedger.model_validate_json(accepted.model_dump_json()) == accepted


def test_result_ledger_refuses_omitted_gate_even_with_recomputed_hash() -> None:
    payload = ledger().model_dump()
    payload["gates"].pop()
    payload["verdict"] = "ADVANCE_PRIMARY_TO_R4"

    with pytest.raises(ValidationError, match="preserve every required gate"):
        R3StudyResultLedger.model_validate(rehash(payload))


def test_result_ledger_refuses_verdict_that_disagrees_with_gate_failures() -> None:
    payload = ledger(failed_gate="primary_net_pl").model_dump()
    payload["verdict"] = "ADVANCE_PRIMARY_TO_R4"

    with pytest.raises(ValidationError, match="all-gates-required"):
        R3StudyResultLedger.model_validate(rehash(payload))
