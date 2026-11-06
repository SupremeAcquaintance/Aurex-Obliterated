from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from aurex.backtest_engine.research_u1_engine import U1ReplayMetrics
from aurex.backtest_engine.research_u1_study_runner import (
    build_u1_planned_replays,
    build_u1_replay_config,
    evaluate_u1_gates,
    verify_u1_study_bindings,
)
from scripts.freeze_u1_run_package import (
    authoritative_u1_run_package,
    load_package_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    charter = evidence_root / "u1_mechanism_discovery_charter_v1.json"
    screen = evidence_root / "u1_mechanism_theory_screen_v1.json"
    contamination = evidence_root / "strategy_contamination_ledger_v1.json"
    universe = evidence_root / "market_universe_manifest_v1.json"
    development = evidence_root / "development_4h_dataset_bundle_v1.json"
    protocol = evidence_root / "u1_primary_mechanism_protocol_v1.json"
    execution = evidence_root / "u1_primary_execution_spec_v1.json"


@lru_cache(maxsize=1)
def inputs():
    return load_package_inputs(Args())


@lru_cache(maxsize=1)
def package():
    loaded = inputs()
    return authoritative_u1_run_package(
        frozen_at=datetime(2026, 7, 27, 14, tzinfo=UTC),
        charter=loaded[0],
        screen=loaded[1],
        contamination=loaded[2],
        universe=loaded[3],
        development=loaded[4],
        protocol=loaded[5],
        specification=loaded[6],
        market_data=loaded[7],
    )


def replay_metrics(
    *,
    net_pl: str = "100",
    drawdown_percent: str = "10",
    volatility: str = "0.40",
    efficiency: str = "1",
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
        maximum_drawdown_percent=drawdown_percent,
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
        realized_equity_volatility=volatility,
        return_to_drawdown=efficiency,
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


class Result:
    def __init__(self, metrics: U1ReplayMetrics):
        self.metrics = metrics


def test_u1_runner_preserves_plan_and_evidence_bindings() -> None:
    loaded = inputs()
    protocol = loaded[5]
    specification = loaded[6]
    market_data = loaded[7]
    frozen = package()
    plans = build_u1_planned_replays(protocol)

    assert plans == frozen.planned_replays
    verify_u1_study_bindings(
        protocol=protocol,
        execution_specification=specification,
        run_package=frozen,
        market_data=market_data,
    )
    fold = next(plan for plan in plans if plan.category == "TEMPORAL_FOLD")
    fold_config = build_u1_replay_config(
        plan=fold,
        protocol=protocol,
        execution_specification=specification,
        market_data=market_data,
    )
    assert fold_config.evaluation_start == fold.evaluation_start
    assert fold_config.evaluation_end == fold.evaluation_end
    assert fold_config.omitted_symbols == []
    lomo = next(plan for plan in plans if plan.category == "LEAVE_ONE_MARKET_OUT")
    lomo_config = build_u1_replay_config(
        plan=lomo,
        protocol=protocol,
        execution_specification=specification,
        market_data=market_data,
    )
    assert lomo_config.omitted_symbols == lomo.omitted_symbols
    assert len(lomo_config.active_symbols) == 34


def test_u1_gate_evaluation_requires_every_profit_and_benchmark_gate() -> None:
    protocol = inputs()[5]
    primary = Result(replay_metrics())
    double_cost = Result(replay_metrics(net_pl="20"))
    benchmark = Result(
        replay_metrics(
            drawdown_percent="15",
            volatility="0.50",
            efficiency="0.8",
        )
    )

    passing = evaluate_u1_gates(
        protocol=protocol,
        primary=primary,
        double_cost=double_cost,
        benchmark=benchmark,
        positive_folds=8,
        lomo_positive_fraction=Decimal("1"),
        all_replay_audits_passed=True,
    )
    assert len(passing) == 13
    assert all(gate.passed for gate in passing)

    failing = evaluate_u1_gates(
        protocol=protocol,
        primary=primary,
        double_cost=Result(replay_metrics(net_pl="-1")),
        benchmark=benchmark,
        positive_folds=5,
        lomo_positive_fraction=Decimal("0.79"),
        all_replay_audits_passed=False,
    )
    failed_ids = {gate.gate_id for gate in failing if not gate.passed}
    assert failed_ids == {
        "deterministic_replay_audit",
        "double_cost_net_pl",
        "leave_one_market_out_positive_fraction",
        "primary_positive_temporal_folds",
    }
