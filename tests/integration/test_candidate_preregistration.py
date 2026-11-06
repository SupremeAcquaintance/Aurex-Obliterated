from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.backtest_engine.candidate_protocols import (
    JAM_REVERSAL_SPOT_V1_DATASET_ID,
    JAM_REVERSAL_SPOT_V1_PARENT_PINE_SHA256,
    JAM_REVERSAL_SPOT_V1_PINE_SHA256,
    SLOW_BREAKOUT_SPOT_V1_DATASET_IDS,
    SLOW_BREAKOUT_SPOT_V1_EXECUTION_SPECS,
    VOLATILITY_BREAKOUT_V1_DATASET_ID,
    jam_reversal_spot_v1_preregistration,
    register_candidate_protocol_durably,
    slow_breakout_spot_v1_preregistration,
    slow_breakout_spot_v1_preregistrations,
    volatility_breakout_v1_preregistration,
)
from aurex.db.base import Base
from aurex.db.models import BacktestProtocol, BacktestReferenceReplayRun


def test_volatility_breakout_preregistration_is_outcome_blind_and_complete() -> None:
    package = volatility_breakout_v1_preregistration()
    protocol = package.protocol

    assert package.outcome_fields_inspected == ()
    assert len(package.walk_forward_plan_hash) == 64
    assert protocol.strategy == "volatility_breakout_v1"
    assert protocol.strategy_version == "1.1.0"
    assert protocol.source_reference.endswith(VOLATILITY_BREAKOUT_V1_DATASET_ID)
    assert len(protocol.walk_forward_windows) == 6
    assert all(
        window.parameters == protocol.parameters
        for window in protocol.walk_forward_windows
    )
    assert protocol.cost_model == {"commission_percent": "0.05"}
    assert protocol.slippage_model == {"type": "fixed_ticks", "ticks": "2"}
    assert protocol.risk_snapshot == {"risk_per_trade": "0.003"}
    assert protocol.acceptance_criteria.min_profit_factor == Decimal("1.15")
    assert protocol.acceptance_criteria.min_out_of_sample_profit_factor == Decimal("1.15")
    assert protocol.acceptance_criteria.max_drawdown == Decimal("50")


def test_volatility_breakout_preregistration_registers_immutably_and_idempotently() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    package = volatility_breakout_v1_preregistration()

    first = register_candidate_protocol_durably(session_factory, package)
    second = register_candidate_protocol_durably(session_factory, package)

    assert first.protocol_id == second.protocol_id
    assert first.commit_verified is True
    assert first.reused_existing is False
    assert second.reused_existing is True
    assert len(first.protocol_hash) == 64
    assert first.outcome_existed_before_registration is False

    with session_factory() as session:
        protocol = session.get(BacktestProtocol, first.protocol_id)
        assert protocol is not None
        assert protocol.backtest_run is None
        source_evidence = protocol.protocol_snapshot["strategy_source_evidence"]
        assert source_evidence["ready"] is True
        assert source_evidence["pine_version"] == "1.1.0"
        assert len(source_evidence["pine_source_sha256"]) == 64
        assert protocol.protocol_snapshot["parameters"] == package.protocol.parameters
        assert protocol.protocol_snapshot["cost_model"] == {
            "commission_percent": "0.05"
        }
        assert protocol.protocol_snapshot["slippage_model"] == {
            "type": "fixed_ticks",
            "ticks": "2",
        }

    Base.metadata.drop_all(engine)


def test_durable_preregistration_refuses_a_candidate_with_recorded_outcome() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    package = volatility_breakout_v1_preregistration()

    with session_factory() as session:
        session.add(
            BacktestReferenceReplayRun(
                dataset_id=VOLATILITY_BREAKOUT_V1_DATASET_ID,
                strategy=package.protocol.strategy,
                strategy_version=package.protocol.strategy_version,
                engine_version="test-engine-v1",
                status="READY",
                dataset_evidence_hash="a" * 64,
                engine_evidence_hash="b" * 64,
                record_evidence_hash="c" * 64,
                request_snapshot={},
                result_snapshot={},
                recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()

    with pytest.raises(
        ValueError,
        match="candidate_protocol_registration_blocked_outcome_already_recorded",
    ):
        register_candidate_protocol_durably(session_factory, package)

    with session_factory() as session:
        assert session.execute(select(BacktestProtocol)).scalars().all() == []

    Base.metadata.drop_all(engine)


def test_slow_breakout_spot_preregistrations_freeze_two_untouched_holdouts() -> None:
    packages = slow_breakout_spot_v1_preregistrations()

    assert len(packages) == 2
    assert {package.protocol.symbols[0] for package in packages} == {
        "ETHUSDT",
        "SOLUSDT",
    }
    for package in packages:
        protocol = package.protocol
        symbol = protocol.symbols[0]
        assert package.outcome_fields_inspected == ()
        assert len(package.walk_forward_plan_hash) == 64
        assert protocol.strategy == "slow_breakout_spot_v1"
        assert protocol.strategy_version == "1.0.0"
        assert protocol.timeframe == "4h"
        assert protocol.source_reference.endswith(
            SLOW_BREAKOUT_SPOT_V1_DATASET_IDS[symbol]
        )
        assert len(protocol.walk_forward_windows) == 5
        assert all(
            window.parameters == protocol.parameters
            for window in protocol.walk_forward_windows
        )
        assert protocol.cost_model == {"commission_percent": "0.05"}
        assert protocol.slippage_model == {"type": "fixed_ticks", "ticks": "2"}
        assert protocol.risk_snapshot == {
            "risk_per_trade": "0.0025",
            **SLOW_BREAKOUT_SPOT_V1_EXECUTION_SPECS[symbol],
        }
        assert protocol.acceptance_criteria.min_trades == 25
        assert protocol.acceptance_criteria.min_profit_factor == Decimal("1.15")
        assert protocol.acceptance_criteria.max_drawdown == Decimal("100")
        assert protocol.acceptance_criteria.min_out_of_sample_trades == 10
        assert protocol.acceptance_criteria.min_walk_forward_trades_per_window == 5


def test_slow_breakout_spot_rejects_non_holdout_symbol() -> None:
    with pytest.raises(ValueError, match="requires an untouched holdout"):
        slow_breakout_spot_v1_preregistration("BTCUSDT")


def test_slow_breakout_spot_preregistrations_commit_before_any_outcome() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    receipts = [
        register_candidate_protocol_durably(session_factory, package)
        for package in slow_breakout_spot_v1_preregistrations()
    ]

    assert len({receipt.protocol_id for receipt in receipts}) == 2
    assert all(receipt.commit_verified for receipt in receipts)
    assert all(not receipt.reused_existing for receipt in receipts)
    assert all(not receipt.outcome_existed_before_registration for receipt in receipts)
    with session_factory() as session:
        protocols = session.execute(
            select(BacktestProtocol).where(
                BacktestProtocol.strategy == "slow_breakout_spot_v1"
            )
        ).scalars().all()
        outcomes = session.execute(
            select(BacktestReferenceReplayRun).where(
                BacktestReferenceReplayRun.strategy == "slow_breakout_spot_v1"
            )
        ).scalars().all()
        assert len(protocols) == 2
        assert outcomes == []
        assert {protocol.symbols[0] for protocol in protocols} == {
            "ETHUSDT",
            "SOLUSDT",
        }

    Base.metadata.drop_all(engine)


def test_jam_reversal_spot_preregistration_is_outcome_blind_and_spot_safe() -> None:
    package = jam_reversal_spot_v1_preregistration()
    protocol = package.protocol

    assert package.outcome_fields_inspected == ()
    assert len(package.walk_forward_plan_hash) == 64
    assert protocol.strategy == "jam_reversal_spot_v1"
    assert protocol.strategy_version == "1.0.1"
    assert protocol.symbols == ["BTCUSDT"]
    assert protocol.timeframe == "15m"
    assert protocol.source_reference.endswith(JAM_REVERSAL_SPOT_V1_DATASET_ID)
    assert protocol.parameters["initial_capital"] == "100"
    assert protocol.parameters["direction_mode"] == "Long only"
    assert protocol.parameters["enable_short"] is False
    assert protocol.parameters["allowed_timeframe_mode"] == "15m only"
    assert protocol.parameters["estimated_commission_percent"] == "0.10"
    assert protocol.cost_model == {
        "commission_percent": "0.10",
        "stress_commission_percent": "0.15",
    }
    assert protocol.slippage_model == {
        "type": "fixed_ticks",
        "ticks": "2",
        "stress_ticks": "10",
    }
    assert protocol.risk_snapshot["long_only"] is True
    assert protocol.risk_snapshot["maximum_leverage"] == "1"
    assert protocol.risk_snapshot["lineage_parent_pine_sha256"] == (
        JAM_REVERSAL_SPOT_V1_PARENT_PINE_SHA256
    )
    assert protocol.risk_snapshot["candidate_pine_sha256"] == (
        JAM_REVERSAL_SPOT_V1_PINE_SHA256
    )
    assert len(protocol.walk_forward_windows) == 6
    assert protocol.acceptance_criteria.min_trades == 60
    assert protocol.acceptance_criteria.min_out_of_sample_trades == 20
    assert protocol.acceptance_criteria.min_profit_factor == Decimal("1.20")
    assert protocol.acceptance_criteria.max_drawdown == Decimal("10")


def test_jam_reversal_spot_protocol_commits_before_any_outcome() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    receipt = register_candidate_protocol_durably(
        session_factory,
        jam_reversal_spot_v1_preregistration(),
    )

    assert receipt.commit_verified is True
    assert receipt.outcome_existed_before_registration is False
    with session_factory() as session:
        protocol = session.get(BacktestProtocol, receipt.protocol_id)
        assert protocol is not None
        assert protocol.strategy == "jam_reversal_spot_v1"
        assert protocol.protocol_snapshot["strategy_source_evidence"]["ready"] is True
        assert (
            protocol.protocol_snapshot["strategy_source_evidence"]["pine_source_sha256"]
            == JAM_REVERSAL_SPOT_V1_PINE_SHA256
        )
        outcomes = session.execute(
            select(BacktestReferenceReplayRun).where(
                BacktestReferenceReplayRun.strategy == "jam_reversal_spot_v1"
            )
        ).scalars().all()
        assert outcomes == []

    Base.metadata.drop_all(engine)
