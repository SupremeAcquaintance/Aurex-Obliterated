from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.datasets import ensure_utc
from aurex.backtest_engine.schemas import (
    AcceptanceCriteria,
    BacktestProtocolCreate,
    WalkForwardPlanRequest,
)
from aurex.backtest_engine.service import (
    JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE,
    SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE,
    VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE,
    BacktestLab,
    build_backtest_protocol_hash,
    build_backtest_protocol_snapshot,
    plan_walk_forward_windows,
)
from aurex.db.base import utc_now
from aurex.db.models import BacktestProtocol, BacktestReferenceReplayRun

VOLATILITY_BREAKOUT_V1_DATASET_ID = "9724b9c7-03fa-4cba-9d5f-1e3bd69aa322"
JAM_REVERSAL_SPOT_V1_DATASET_ID = "9724b9c7-03fa-4cba-9d5f-1e3bd69aa322"
JAM_REVERSAL_SPOT_V1_PARENT_PINE_SHA256 = (
    "f1c7231bd2f9a919157dbe14388fc838d6d484f9cda50c2a36c4e6b79b49a7c3"
)
JAM_REVERSAL_SPOT_V1_PINE_SHA256 = (
    "7aa2aaa04e17ccbad70adba9279b4e5eb3057393b5e74f0a7db4cc5dd39d7270"
)
SLOW_BREAKOUT_SPOT_V1_DATASET_IDS = {
    "ETHUSDT": "287e1cca-27d9-4308-8ae7-458d563d4867",
    "SOLUSDT": "411799dd-1e55-4b97-ba7b-b6952146ecb5",
}
SLOW_BREAKOUT_SPOT_V1_EXECUTION_SPECS = {
    "ETHUSDT": {
        "tick_size": "0.01",
        "point_value": "1",
        "minimum_contract": "0.0001",
    },
    "SOLUSDT": {
        "tick_size": "0.01",
        "point_value": "1",
        "minimum_contract": "0.001",
    },
}


@dataclass(frozen=True)
class CandidateProtocolPackage:
    protocol: BacktestProtocolCreate
    walk_forward_plan_hash: str
    outcome_fields_inspected: tuple[str, ...]


@dataclass(frozen=True)
class CandidateProtocolCommitReceipt:
    protocol_id: str
    protocol_hash: str
    strategy: str
    strategy_version: str
    registered_at: datetime
    commit_verified_at: datetime
    walk_forward_plan_hash: str
    outcome_fields_inspected: tuple[str, ...]
    reused_existing: bool
    commit_verified: bool = True
    outcome_existed_before_registration: bool = False


def register_candidate_protocol_durably(
    session_factory: Callable[[], Session],
    package: CandidateProtocolPackage,
) -> CandidateProtocolCommitReceipt:
    payload = package.protocol
    expected_snapshot = build_backtest_protocol_snapshot(payload)
    expected_hash = build_backtest_protocol_hash(expected_snapshot)

    with session_factory() as session:
        prior_outcome = session.execute(
            select(BacktestReferenceReplayRun)
            .where(
                BacktestReferenceReplayRun.strategy == payload.strategy,
                BacktestReferenceReplayRun.strategy_version == payload.strategy_version,
            )
            .order_by(BacktestReferenceReplayRun.recorded_at)
            .limit(1)
        ).scalar_one_or_none()
        if prior_outcome is not None:
            raise ValueError(
                "candidate_protocol_registration_blocked_outcome_already_recorded:"
                f"{prior_outcome.id}@{ensure_utc(prior_outcome.recorded_at).isoformat()}"
            )

        existing = session.execute(
            select(BacktestProtocol)
            .where(BacktestProtocol.protocol_hash == expected_hash)
            .order_by(BacktestProtocol.registered_at)
        ).scalars().first()
        protocol = BacktestLab(session).register_protocol(payload)
        protocol_id = protocol.id
        registered_at = ensure_utc(protocol.registered_at)
        reused_existing = existing is not None and existing.id == protocol_id
        session.commit()

    with session_factory() as verification_session:
        persisted = verification_session.get(BacktestProtocol, protocol_id)
        if persisted is None:
            raise RuntimeError("candidate_protocol_commit_not_persisted")
        current_hash = build_backtest_protocol_hash(persisted.protocol_snapshot)
        if current_hash != expected_hash or persisted.protocol_hash != expected_hash:
            raise RuntimeError("candidate_protocol_commit_hash_mismatch")
        prior_outcome = verification_session.execute(
            select(BacktestReferenceReplayRun)
            .where(
                BacktestReferenceReplayRun.strategy == payload.strategy,
                BacktestReferenceReplayRun.strategy_version == payload.strategy_version,
                BacktestReferenceReplayRun.recorded_at < persisted.registered_at,
            )
            .order_by(BacktestReferenceReplayRun.recorded_at)
            .limit(1)
        ).scalar_one_or_none()
        if prior_outcome is not None:
            raise RuntimeError(
                "candidate_protocol_commit_temporal_binding_failed:"
                f"{prior_outcome.id}@{ensure_utc(prior_outcome.recorded_at).isoformat()}"
            )

    return CandidateProtocolCommitReceipt(
        protocol_id=protocol_id,
        protocol_hash=expected_hash,
        strategy=payload.strategy,
        strategy_version=payload.strategy_version,
        registered_at=registered_at,
        commit_verified_at=utc_now(),
        walk_forward_plan_hash=package.walk_forward_plan_hash,
        outcome_fields_inspected=package.outcome_fields_inspected,
        reused_existing=reused_existing,
    )


def volatility_breakout_v1_preregistration() -> CandidateProtocolPackage:
    parameters = dict(VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE)
    in_sample_start = datetime(2023, 2, 1, tzinfo=UTC)
    in_sample_end = datetime(2025, 1, 31, 23, 59, 59, 999999, tzinfo=UTC)
    plan = plan_walk_forward_windows(
        WalkForwardPlanRequest(
            strategy="volatility_breakout_v1",
            in_sample_start=in_sample_start,
            in_sample_end=in_sample_end,
            parameters=parameters,
            window_count=6,
            initial_training_fraction=Decimal("0.333333"),
        )
    )
    protocol = BacktestProtocolCreate(
        strategy="volatility_breakout_v1",
        strategy_version="1.1.0",
        symbols=["BTCUSDT"],
        timeframe="15m",
        data_source="binance-vision-reference-replay",
        csv_timezone="UTC",
        source_reference=(
            f"aurex://ohlcv-dataset/{VOLATILITY_BREAKOUT_V1_DATASET_ID}"
        ),
        data_start=datetime(2023, 2, 1, tzinfo=UTC),
        data_end=datetime(2026, 7, 1, tzinfo=UTC),
        in_sample_start=in_sample_start,
        in_sample_end=in_sample_end,
        out_of_sample_start=datetime(2025, 2, 1, tzinfo=UTC),
        out_of_sample_end=datetime(2026, 7, 1, tzinfo=UTC),
        parameters=parameters,
        cost_model={"commission_percent": "0.05"},
        slippage_model={"type": "fixed_ticks", "ticks": "2"},
        risk_snapshot={"risk_per_trade": "0.003"},
        walk_forward_windows=plan.windows,
        acceptance_criteria=AcceptanceCriteria(
            min_trades=100,
            min_profit_factor=Decimal("1.15"),
            require_positive_expectancy=True,
            max_drawdown=Decimal("50"),
            require_sample_windows=True,
            require_out_of_sample_metrics=True,
            min_out_of_sample_trades=30,
            min_out_of_sample_profit_factor=Decimal("1.15"),
            require_out_of_sample_positive_expectancy=True,
            require_cost_model=True,
            require_slippage_model=True,
            require_risk_snapshot=True,
            require_trade_dates=True,
            min_active_trading_days=15,
            max_single_day_trade_share=Decimal("0.25"),
            require_market_regime_breakdown=True,
            require_walk_forward_validation=True,
            min_walk_forward_windows=3,
            min_walk_forward_trades_per_window=10,
            min_walk_forward_pass_rate=Decimal("0.66"),
        ),
    )
    return CandidateProtocolPackage(
        protocol=protocol,
        walk_forward_plan_hash=plan.plan_hash,
        outcome_fields_inspected=tuple(plan.outcome_fields_inspected),
    )


def slow_breakout_spot_v1_preregistration(
    symbol: str,
) -> CandidateProtocolPackage:
    normalized_symbol = symbol.strip().upper()
    try:
        dataset_id = SLOW_BREAKOUT_SPOT_V1_DATASET_IDS[normalized_symbol]
        execution_spec = SLOW_BREAKOUT_SPOT_V1_EXECUTION_SPECS[normalized_symbol]
    except KeyError as exc:
        supported = ", ".join(sorted(SLOW_BREAKOUT_SPOT_V1_DATASET_IDS))
        raise ValueError(
            f"slow_breakout_spot_v1 requires an untouched holdout: {supported}"
        ) from exc

    parameters = dict(SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE)
    in_sample_start = datetime(2023, 2, 1, tzinfo=UTC)
    in_sample_end = datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    plan = plan_walk_forward_windows(
        WalkForwardPlanRequest(
            strategy="slow_breakout_spot_v1",
            in_sample_start=in_sample_start,
            in_sample_end=in_sample_end,
            parameters=parameters,
            window_count=5,
            initial_training_fraction=Decimal("0.4"),
        )
    )
    protocol = BacktestProtocolCreate(
        strategy="slow_breakout_spot_v1",
        strategy_version="1.0.0",
        symbols=[normalized_symbol],
        timeframe="4h",
        data_source="binance-vision-reference-replay",
        csv_timezone="UTC",
        source_reference=f"aurex://ohlcv-dataset/{dataset_id}",
        data_start=datetime(2023, 2, 1, tzinfo=UTC),
        data_end=datetime(2026, 7, 1, tzinfo=UTC),
        in_sample_start=in_sample_start,
        in_sample_end=in_sample_end,
        out_of_sample_start=datetime(2025, 1, 1, tzinfo=UTC),
        out_of_sample_end=datetime(2026, 7, 1, tzinfo=UTC),
        parameters=parameters,
        cost_model={"commission_percent": "0.05"},
        slippage_model={"type": "fixed_ticks", "ticks": "2"},
        risk_snapshot={"risk_per_trade": "0.0025", **execution_spec},
        walk_forward_windows=plan.windows,
        acceptance_criteria=AcceptanceCriteria(
            min_trades=25,
            min_profit_factor=Decimal("1.15"),
            require_positive_expectancy=True,
            max_drawdown=Decimal("100"),
            require_sample_windows=True,
            require_out_of_sample_metrics=True,
            min_out_of_sample_trades=10,
            min_out_of_sample_profit_factor=Decimal("1.15"),
            require_out_of_sample_positive_expectancy=True,
            require_cost_model=True,
            require_slippage_model=True,
            require_risk_snapshot=True,
            require_trade_dates=True,
            min_active_trading_days=15,
            max_single_day_trade_share=Decimal("0.25"),
            require_market_regime_breakdown=True,
            require_walk_forward_validation=True,
            min_walk_forward_windows=3,
            min_walk_forward_trades_per_window=5,
            min_walk_forward_pass_rate=Decimal("0.66"),
        ),
    )
    return CandidateProtocolPackage(
        protocol=protocol,
        walk_forward_plan_hash=plan.plan_hash,
        outcome_fields_inspected=tuple(plan.outcome_fields_inspected),
    )


def slow_breakout_spot_v1_preregistrations() -> tuple[CandidateProtocolPackage, ...]:
    return tuple(
        slow_breakout_spot_v1_preregistration(symbol)
        for symbol in sorted(SLOW_BREAKOUT_SPOT_V1_DATASET_IDS)
    )


def jam_reversal_spot_v1_preregistration() -> CandidateProtocolPackage:
    parameters = dict(JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE)
    in_sample_start = datetime(2023, 2, 1, tzinfo=UTC)
    in_sample_end = datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    plan = plan_walk_forward_windows(
        WalkForwardPlanRequest(
            strategy="jam_reversal_spot_v1",
            in_sample_start=in_sample_start,
            in_sample_end=in_sample_end,
            parameters=parameters,
            window_count=6,
            initial_training_fraction=Decimal("0.333333"),
        )
    )
    protocol = BacktestProtocolCreate(
        strategy="jam_reversal_spot_v1",
        strategy_version="1.0.1",
        symbols=["BTCUSDT"],
        timeframe="15m",
        data_source="binance-vision-reference-replay",
        csv_timezone="UTC",
        source_reference=f"aurex://ohlcv-dataset/{JAM_REVERSAL_SPOT_V1_DATASET_ID}",
        data_start=datetime(2023, 2, 1, tzinfo=UTC),
        data_end=datetime(2026, 1, 1, tzinfo=UTC),
        in_sample_start=in_sample_start,
        in_sample_end=in_sample_end,
        out_of_sample_start=datetime(2025, 1, 1, tzinfo=UTC),
        out_of_sample_end=datetime(2026, 1, 1, tzinfo=UTC),
        parameters=parameters,
        cost_model={
            "commission_percent": "0.10",
            "stress_commission_percent": "0.15",
        },
        slippage_model={
            "type": "fixed_ticks",
            "ticks": "2",
            "stress_ticks": "10",
        },
        risk_snapshot={
            "venue": "BINANCE_SPOT",
            "product": "SPOT",
            "symbol": "BTCUSDT",
            "long_only": True,
            "maximum_leverage": "1",
            "initial_capital_usd": "100",
            "risk_per_trade": "0.005",
            "maximum_position_value": "0.95",
            "tick_size": "0.01",
            "point_value": "1",
            "minimum_contract": "0.00001",
            "lineage_parent": "jam_reversal_v1@1.14.0",
            "lineage_parent_pine_sha256": JAM_REVERSAL_SPOT_V1_PARENT_PINE_SHA256,
            "candidate_pine_sha256": JAM_REVERSAL_SPOT_V1_PINE_SHA256,
            "quarantined_parent_window": (
                "2026-05-01T00:00:00Z/2026-07-21T00:00:00Z"
            ),
        },
        walk_forward_windows=plan.windows,
        acceptance_criteria=AcceptanceCriteria(
            min_trades=60,
            min_profit_factor=Decimal("1.20"),
            require_positive_expectancy=True,
            max_drawdown=Decimal("10"),
            require_sample_windows=True,
            require_out_of_sample_metrics=True,
            min_out_of_sample_trades=20,
            min_out_of_sample_profit_factor=Decimal("1.15"),
            require_out_of_sample_positive_expectancy=True,
            require_cost_model=True,
            require_slippage_model=True,
            require_risk_snapshot=True,
            require_trade_dates=True,
            min_active_trading_days=30,
            max_single_day_trade_share=Decimal("0.10"),
            require_market_regime_breakdown=True,
            require_walk_forward_validation=True,
            min_walk_forward_windows=6,
            min_walk_forward_trades_per_window=7,
            min_walk_forward_pass_rate=Decimal("0.66"),
        ),
    )
    return CandidateProtocolPackage(
        protocol=protocol,
        walk_forward_plan_hash=plan.plan_hash,
        outcome_fields_inspected=tuple(plan.outcome_fields_inspected),
    )
