from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.config.settings import get_settings
from aurex.db.models import Signal
from aurex.signal_gateway.schemas import (
    SignalContractResponse,
    SignalResponse,
    TradingViewAlertSetupResponse,
    TradingViewRunbookResponse,
    TradingViewSignalPayload,
    TradingViewSignalPreflightResponse,
    TradingViewVerificationResponse,
)
from aurex.signal_gateway.service import (
    signal_contract_preflight,
    tradingview_alert_setup,
    tradingview_signal_preflight,
    tradingview_signal_runbook,
    tradingview_signal_verification,
)

router = APIRouter(prefix="/signals", tags=["signals"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[SignalResponse])
def list_signals(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[Signal]:
    return list(
        db.execute(select(Signal).order_by(Signal.received_at.desc()).limit(limit)).scalars()
    )


@router.get("/contract", response_model=SignalContractResponse)
def get_signal_contract(
    db: DbSession,
    strategy: str = Query(default="trend_pullback_v1", min_length=1, max_length=100),
    symbol: str = Query(default="BTCUSDT", min_length=1, max_length=64),
) -> SignalContractResponse:
    return signal_contract_preflight(db, strategy=strategy, symbol=symbol)


@router.get("/tradingview-runbook", response_model=TradingViewRunbookResponse)
def get_tradingview_runbook(
    db: DbSession,
    strategy: str = Query(default="trend_pullback_v1", min_length=1, max_length=100),
    symbol: str = Query(default="BTCUSDT", min_length=1, max_length=64),
) -> TradingViewRunbookResponse:
    return tradingview_signal_runbook(
        db,
        get_settings(),
        strategy=strategy,
        symbol=symbol,
    )


@router.get("/tradingview-alert-setup", response_model=TradingViewAlertSetupResponse)
def get_tradingview_alert_setup(
    db: DbSession,
    strategy: str = Query(default="trend_pullback_v1", min_length=1, max_length=100),
    symbol: str = Query(default="BTCUSDT", min_length=1, max_length=64),
) -> TradingViewAlertSetupResponse:
    return tradingview_alert_setup(
        db,
        get_settings(),
        strategy=strategy,
        symbol=symbol,
    )


@router.get("/tradingview-verification", response_model=TradingViewVerificationResponse)
def get_tradingview_verification(
    db: DbSession,
    strategy: str = Query(default="trend_pullback_v1", min_length=1, max_length=100),
    symbol: str = Query(default="BTCUSDT", min_length=1, max_length=64),
) -> TradingViewVerificationResponse:
    return tradingview_signal_verification(
        db,
        get_settings(),
        strategy=strategy,
        symbol=symbol,
    )


@router.post("/preflight/tradingview", response_model=TradingViewSignalPreflightResponse)
def preflight_tradingview_signal(
    payload: TradingViewSignalPayload,
    db: DbSession,
) -> TradingViewSignalPreflightResponse:
    return tradingview_signal_preflight(db, get_settings(), payload)


@router.get("/{signal_id}", response_model=SignalResponse)
def get_signal(signal_id: str, db: DbSession) -> Signal:
    signal = db.get(Signal, signal_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )
    return signal
