"""Synthetic mechanics only; never import these fixtures into an operator ledger."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    strategy_parameter_fingerprint,
)
from aurex.config.settings import Settings
from aurex.db.base import Base
from aurex.db.models import (
    BrokerFill,
    BrokerOrder,
    OrderIntent,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
    Signal,
    SignalEvent,
)
from aurex.domain.enums import PositionStatus, SignalStatus, TradeStatus
from aurex.execution_engine.paper import PaperExecutionEngine, paper_execution_evidence_hash
from aurex.risk_engine.service import RiskEngine
from aurex.signal_gateway.schemas import NativeSignalPayload, TradingViewSignalPayload
from aurex.signal_gateway.service import SignalIntakeService, tradingview_signal_verification
from aurex.strategy_engine.service import StrategyPortfolioService
from tests.integration.backtest_helpers import seed_accepted_backtest

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)


def native_payload(**changes: object) -> NativeSignalPayload:
    fields = {
        "source": "aurex_native",
        "strategy": "trend_pullback_v1",
        "strategy_version": "1.3.0",
        "settings_fingerprint": strategy_parameter_fingerprint(
            "trend_pullback_v1", TREND_PULLBACK_V1_PARAMETER_TEMPLATE
        ),
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": "LONG",
        "entry_price": "100",
        "stop_loss": "95",
        "take_profit": "112",
        "market_regime": "TRENDING_UP",
        "timestamp": NOW,
    }
    fields.update(changes)
    return NativeSignalPayload.model_validate(fields)


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        live_trading_enabled=False,
        live_execution_adapter="disabled",
        duplicate_cooldown_minutes=30,
        paper_commission_bps=Decimal("10"),
        paper_half_spread_bps=Decimal("2.5"),
        paper_market_impact_bps=Decimal("2.5"),
    )


@pytest.fixture()
def session(monkeypatch):
    monkeypatch.setattr("aurex.signal_gateway.service.utc_now", lambda: NOW)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        account, profile = RiskEngine(session).get_or_create_default_profile()
        account.starting_equity = account.current_equity = Decimal("100")
        profile.risk_per_trade = Decimal("0.005")
        profile.max_open_positions = 1
        yield session
    engine.dispose()


@pytest.fixture()
def eligible_fixture(session, active_trend_pipeline):
    # Qualification is synthetic and confined to this disposable test database.
    strategy = StrategyPortfolioService(session).get_config("trend_pullback_v1")
    strategy.is_enabled = True
    seed_accepted_backtest(session)
    session.flush()


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "tradingview"},
        {"strategy_version": None},
        {"strategy_version": " "},
        {"settings_fingerprint": None},
        {"settings_fingerprint": " "},
        {"timestamp": NOW.replace(tzinfo=None)},
        {"entry_price": "NaN"},
        {"stop_loss": "105"},
        {"webhook_delivery": {"verified": True}},
    ],
)
def test_native_payload_requires_explicit_provenance_and_valid_geometry(changes):
    with pytest.raises(ValidationError):
        native_payload(**changes)


def test_native_payload_normalizes_source_timeframe_and_timezone():
    payload = native_payload(
        source=" AUREX_NATIVE ", timeframe="15", timestamp="2026-09-27T14:00:00+02:00"
    )
    assert payload.source == "aurex_native"
    assert payload.timeframe == "15m"
    assert payload.timestamp == NOW


@pytest.mark.parametrize("field", ["strategy_version", "settings_fingerprint"])
def test_native_payload_requires_provenance_fields(field):
    fields = native_payload().model_dump()
    del fields[field]
    with pytest.raises(ValidationError):
        NativeSignalPayload.model_validate(fields)


def test_native_intake_preserves_retired_strategy_block(session, settings):
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "lifecycle" in result.signal.rejection_reason
    assert session.scalars(select(PaperOrder)).all() == []


def test_native_intake_requires_accepted_evidence(session, settings, active_trend_pipeline):
    strategy = StrategyPortfolioService(session).get_config("trend_pullback_v1")
    strategy.is_enabled = True
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "accepted backtest evidence" in result.signal.rejection_reason
    assert session.scalars(select(PaperOrder)).all() == []


@pytest.mark.parametrize(
    "changes, expected_reason",
    [
        ({"timestamp": NOW - timedelta(minutes=10)}, "stale"),
        ({"timestamp": NOW + timedelta(seconds=1)}, "future"),
        ({"stop_loss": None}, "Missing stop loss"),
        ({"settings_fingerprint": "wrong-settings"}, "provenance"),
        ({"strategy_version": "wrong-version"}, "provenance"),
    ],
)
def test_native_intake_preserves_risk_checks(
    session, settings, eligible_fixture, changes, expected_reason
):
    result = SignalIntakeService(session, settings).ingest_native(native_payload(**changes))
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert expected_reason in result.signal.rejection_reason
    assert session.scalars(select(PaperOrder)).all() == []


def test_native_intake_preserves_kill_switch(session, settings, eligible_fixture):
    RiskEngine(session).set_kill_switch(True)
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert result.signal.rejection_reason == "Kill switch is enabled"
    assert session.scalars(select(PaperOrder)).all() == []


def test_native_intake_preserves_disabled_strategy(session, settings, eligible_fixture):
    StrategyPortfolioService(session).get_config("trend_pullback_v1").is_enabled = False
    result = SignalIntakeService(session, settings).ingest_native(native_payload())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "disabled" in result.signal.rejection_reason
    assert session.scalars(select(PaperOrder)).all() == []


def test_native_intake_preserves_position_limit(session, settings, eligible_fixture):
    service = SignalIntakeService(session, settings)
    assert service.ingest_native(native_payload()).signal.status == SignalStatus.PAPER_EXECUTED
    service.settings = settings.model_copy(update={"duplicate_cooldown_minutes": 0})
    result = service.ingest_native(native_payload(timestamp=NOW - timedelta(seconds=1)))
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "positions" in result.signal.rejection_reason
    assert len(session.scalars(select(PaperOrder)).all()) == 1


@pytest.mark.parametrize(
    "changes", [{"live_trading_enabled": True}, {"live_execution_adapter": "binance"}]
)
def test_native_intake_refuses_live_configuration_without_writes(session, settings, changes):
    settings = settings.model_copy(update=changes)
    with pytest.raises(ValueError, match="live execution to remain disabled"):
        SignalIntakeService(session, settings).ingest_native(native_payload())
    assert session.scalars(select(Signal)).all() == []


def test_sources_cannot_be_swapped_at_service_boundary(session, settings):
    service = SignalIntakeService(session, settings)
    payload = native_payload()
    with pytest.raises(ValidationError, match="source must be tradingview"):
        service.ingest_tradingview(payload)
    tv_payload = TradingViewSignalPayload.model_validate(
        {**payload.model_dump(), "source": "tradingview"}
    )
    with pytest.raises(ValidationError, match="source must be aurex_native"):
        service.ingest_native(tv_payload)
    assert session.scalars(select(Signal)).all() == []


def test_native_costed_round_trip_and_duplicate_are_isolated_from_external_proof(
    session, settings, eligible_fixture
):
    service = SignalIntakeService(session, settings)
    payload = native_payload()
    result = service.ingest_native(payload)
    assert result.signal.status == SignalStatus.PAPER_EXECUTED
    assert result.signal.source == "aurex_native"
    assert result.signal.raw_payload["source"] == "aurex_native"
    decision = session.scalars(select(RiskDecision)).one()
    quantity = ((Decimal("0.5") - Decimal("0.00000005")) / Decimal("5.2925")).quantize(
        Decimal("0.000000000001"), rounding=ROUND_DOWN
    )
    assert Decimal("0") < decision.risk_amount <= Decimal("0.5")
    assert decision.position_size == quantity
    order = session.scalars(select(PaperOrder)).one()
    trade = session.scalars(select(PaperTrade)).one()
    assert order.fees == (Decimal("0.1") * quantity).quantize(Decimal("0.00000001"))
    assert order.slippage == (Decimal("0.05") * quantity).quantize(Decimal("0.00000001"))
    duplicate = service.ingest_native(payload)
    assert duplicate.signal.status == SignalStatus.DUPLICATE_REJECTED
    assert duplicate.signal.duplicate_of_signal_id == result.signal.id
    assert len(session.scalars(select(PaperOrder)).all()) == 1
    closed = PaperExecutionEngine(session, settings).close_trade(
        trade.id, Decimal("112"), "synthetic fixture exit", now=NOW + timedelta(minutes=15)
    )
    assert closed.status == TradeStatus.CLOSED
    expected_fees = order.fees + (Decimal("0.112") * quantity).quantize(Decimal("0.00000001"))
    expected_slippage = order.slippage + (Decimal("0.056") * quantity).quantize(
        Decimal("0.00000001")
    )
    expected_net = (12 * quantity - expected_fees - expected_slippage).quantize(
        Decimal("0.00000001")
    )
    assert closed.fees == expected_fees
    assert closed.slippage == expected_slippage
    assert closed.realized_pl == expected_net
    assert closed.account.current_equity == Decimal("100") + expected_net
    assert session.scalars(select(Position)).one().status == PositionStatus.CLOSED
    assert order.execution_assumptions_hash == paper_execution_evidence_hash(
        order.execution_assumptions
    )
    with pytest.raises(ValueError, match="already closed"):
        PaperExecutionEngine(session, settings).close_trade(
            trade.id, Decimal("110"), "duplicate close"
        )
    assert closed.account.current_equity == Decimal("100") + expected_net
    for event in session.scalars(select(SignalEvent)):
        assert "webhook_delivery" not in event.metadata_json
    verification = tradingview_signal_verification(
        session, settings, strategy=payload.strategy, symbol=payload.symbol
    )
    assert verification.status == "NO_SIGNAL"
    assert verification.delivery_verified is False
    assert verification.pipeline_verified is False
    for model in (OrderIntent, BrokerOrder, BrokerFill):
        assert session.scalars(select(model)).all() == []


def test_native_source_does_not_suppress_tradingview_signal(session, settings):
    service = SignalIntakeService(session, settings)
    payload = native_payload()
    native = service.ingest_native(payload)
    tv = service.ingest_tradingview(
        TradingViewSignalPayload.model_validate(
            {**payload.model_dump(), "source": "tradingview"}
        )
    )
    assert tv.signal.status == SignalStatus.RISK_REJECTED
    assert tv.signal.duplicate_of_signal_id is None
    assert tv.signal.idempotency_key != native.signal.idempotency_key
