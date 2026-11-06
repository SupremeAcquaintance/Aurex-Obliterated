from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.broker_engine.binance_testnet_evidence import (
    BinanceTestnetQualificationStatus,
    binance_testnet_qualification_status,
)
from aurex.broker_engine.schemas import (
    BrokerConnectionResponse,
    BrokerFillResponse,
    BrokerOrderResponse,
    BrokerReadinessResponse,
    BrokerReconciliationReportResponse,
    EmergencyStopResponse,
    OrderIntentCreateRequest,
    OrderIntentResponse,
    SandboxFillRequest,
)
from aurex.broker_engine.service import BrokerReadinessService
from aurex.config.settings import get_settings

router = APIRouter(prefix="/broker", tags=["broker-readiness"])
DbSession = Annotated[Session, Depends(get_db)]


def service(db: Session) -> BrokerReadinessService:
    return BrokerReadinessService(db, get_settings())


@router.get(
    "/binance-testnet/status",
    response_model=BinanceTestnetQualificationStatus,
)
def binance_testnet_status() -> BinanceTestnetQualificationStatus:
    return binance_testnet_qualification_status()


@router.get("/readiness", response_model=BrokerReadinessResponse)
def broker_readiness(db: DbSession) -> BrokerReadinessResponse:
    result = service(db).readiness_status()
    db.commit()
    return result


@router.post("/readiness/run", response_model=BrokerReadinessResponse)
def run_readiness_checks(db: DbSession) -> BrokerReadinessResponse:
    result = service(db).readiness_status()
    db.commit()
    return result


@router.get("/connections", response_model=list[BrokerConnectionResponse])
def list_connections(db: DbSession) -> object:
    result = service(db).list_connections()
    db.commit()
    return result


@router.post("/sandbox/order-intents", response_model=OrderIntentResponse)
def create_sandbox_order_intent(
    payload: OrderIntentCreateRequest,
    db: DbSession,
) -> object:
    try:
        intent = service(db).create_order_intent(
            payload.risk_decision_id,
            broker_connection_id=payload.broker_connection_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(intent)
    return intent


@router.get("/order-intents", response_model=list[OrderIntentResponse])
def list_order_intents(db: DbSession) -> object:
    return service(db).list_order_intents()


@router.post("/sandbox/order-intents/{order_intent_id}/submit", response_model=BrokerOrderResponse)
def submit_sandbox_order(order_intent_id: str, db: DbSession) -> object:
    try:
        order = service(db).submit_sandbox_order(order_intent_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(order)
    return order


@router.get("/orders", response_model=list[BrokerOrderResponse])
def list_broker_orders(db: DbSession) -> object:
    return service(db).list_broker_orders()


@router.post("/sandbox/orders/{broker_order_id}/simulate-fill", response_model=BrokerFillResponse)
def simulate_sandbox_fill(
    broker_order_id: str,
    payload: SandboxFillRequest,
    db: DbSession,
) -> object:
    try:
        fill = service(db).simulate_fill(
            broker_order_id,
            quantity=payload.quantity,
            price=payload.price,
            fees=payload.fees,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(fill)
    return fill


@router.post("/reconciliation/run", response_model=BrokerReconciliationReportResponse)
def run_reconciliation(db: DbSession) -> object:
    try:
        report = service(db).reconcile()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(report)
    return report


@router.get("/reconciliation", response_model=list[BrokerReconciliationReportResponse])
def list_reconciliation_reports(db: DbSession) -> object:
    return service(db).list_reconciliation_reports()


@router.post("/emergency-stop", response_model=EmergencyStopResponse)
def broker_emergency_stop(db: DbSession) -> EmergencyStopResponse:
    result = service(db).emergency_stop()
    db.commit()
    return result
