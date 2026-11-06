from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from aurex.backtest_engine.research_engine import R3EquitySnapshot, R3ReplayMetrics
from aurex.backtest_engine.research_r31_engine import R31ResearchReplayResult
from aurex.backtest_engine.research_r31_study import R31MechanismStudyProtocol
from aurex.backtest_engine.research_r31_study_runner import (
    build_planned_replays,
    corrected_monthly_net_returns,
    evaluate_gates,
)


def protocol() -> R31MechanismStudyProtocol:
    return R31MechanismStudyProtocol.model_validate_json(
        Path("data/evidence/r31_path_quality_study_v1.json").read_text(
            encoding="utf-8"
        )
    )


def metrics(**changes) -> R3ReplayMetrics:
    values = {
        "initial_capital": "1000",
        "final_equity": "1100",
        "net_pl": "100",
        "gross_profit": "150",
        "gross_loss": "50",
        "profit_factor": "1.5",
        "raw_gross_profit": "180",
        "raw_gross_loss": "40",
        "raw_profit_factor": "4.5",
        "maximum_drawdown": "100",
        "maximum_drawdown_percent": "10",
        "completed_trades": 120,
        "winning_trades": 70,
        "losing_trades": 50,
        "accepted_entries": 120,
        "rejected_opportunities": 20,
        "total_commission": "10",
        "total_slippage": "5",
        "turnover": "25",
        "active_days": 300,
        "average_gross_exposure_percent": "70",
        "maximum_gross_exposure_percent": "95",
        "symbol_positive_raw_profit": {"ALPHAUSDT": Decimal("180")},
        "maximum_single_symbol_gross_profit_fraction": "0.2",
        "top_five_gross_profit_fraction": "0.6",
    }
    values.update(changes)
    return R3ReplayMetrics(**values)


def result_with_metrics(value: R3ReplayMetrics) -> R31ResearchReplayResult:
    return R31ResearchReplayResult.model_construct(metrics=value)


def test_r31_runner_builds_exact_protocol_bound_plan() -> None:
    frozen = protocol()
    plans = build_planned_replays(frozen)

    assert len(plans) == 44
    assert [plan.run_id for plan in plans] == sorted(plan.run_id for plan in plans)
    assert {
        plan.fold_id for plan in plans if plan.category == "QUARTERLY_FOLD"
    } == {fold.fold_id for fold in frozen.folds}
    assert {
        plan.omitted_symbols[0]
        for plan in plans
        if plan.category == "LEAVE_ONE_MARKET_OUT"
    } == set(frozen.decision_symbols)


def test_r31_gate_evaluation_is_all_required_gates_and_no_hidden_gate() -> None:
    gates = evaluate_gates(
        protocol=protocol(),
        primary=result_with_metrics(metrics()),
        double_cost=result_with_metrics(metrics(net_pl="1")),
        positive_folds=4,
        lomo_positive_fraction=Decimal("0.8"),
    )

    assert len(gates) == 9
    assert all(gate.passed for gate in gates)
    assert [gate.gate_id for gate in sorted(gates, key=lambda item: item.gate_id)] == [
        "double_cost_net_pl",
        "leave_one_market_out_positive_fraction",
        "primary_completed_trades",
        "primary_maximum_drawdown_percent",
        "primary_net_pl",
        "primary_positive_quarterly_folds",
        "primary_profit_factor",
        "single_symbol_gross_profit_fraction",
        "top_five_gross_profit_fraction",
    ]


def test_r31_gate_boundary_is_inclusive_but_profit_is_strictly_positive() -> None:
    gates = evaluate_gates(
        protocol=protocol(),
        primary=result_with_metrics(
            metrics(
                net_pl="0",
                profit_factor="1.10",
                maximum_drawdown_percent="20",
                completed_trades=100,
                maximum_single_symbol_gross_profit_fraction="0.30",
                top_five_gross_profit_fraction="0.65",
            )
        ),
        double_cost=result_with_metrics(metrics(net_pl="0")),
        positive_folds=4,
        lomo_positive_fraction=Decimal("0.80"),
    )
    by_id = {gate.gate_id: gate.passed for gate in gates}

    assert by_id["primary_net_pl"] is False
    assert by_id["double_cost_net_pl"] is False
    assert all(
        passed
        for gate_id, passed in by_id.items()
        if gate_id not in {"primary_net_pl", "double_cost_net_pl"}
    )


def test_r31_monthly_returns_attribute_midnight_snapshot_to_prior_month() -> None:
    result = SimpleNamespace(
        config=SimpleNamespace(
            evaluation_end=datetime(2023, 9, 1, tzinfo=UTC),
        ),
        metrics=SimpleNamespace(
            initial_capital=Decimal("1000"),
            final_equity=Decimal("1200"),
        ),
        equity_curve=[
            R3EquitySnapshot(
                timestamp=datetime(2023, 8, 1, tzinfo=UTC),
                cash="1100",
                marked_position_value="0",
                equity="1100",
                gross_exposure_percent="0",
                open_positions=0,
                drawdown="0",
                drawdown_percent="0",
            ),
            R3EquitySnapshot(
                timestamp=datetime(2023, 9, 1, tzinfo=UTC),
                cash="1200",
                marked_position_value="0",
                equity="1200",
                gross_exposure_percent="0",
                open_positions=0,
                drawdown="0",
                drawdown_percent="0",
            ),
        ],
    )

    returns = corrected_monthly_net_returns(result)

    assert list(returns) == ["2023-07", "2023-08"]
    assert returns["2023-07"] == Decimal("0.1")
    assert returns["2023-08"] == Decimal("1200") / Decimal("1100") - Decimal("1")
