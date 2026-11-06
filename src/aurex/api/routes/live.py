from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.config.settings import get_settings
from aurex.live_deployment.schemas import (
    BrokerStatementCsvPreflightResponse,
    BrokerStatementCsvReconciliationRequest,
    BrokerStatementReconciliationRequest,
    DailyReviewRequest,
    LiveActivationAttemptResponse,
    LiveApprovalPacketRequest,
    LiveApprovalPacketResponse,
    LiveApprovalRecordRequest,
    LiveApprovalRecordResponse,
    LiveBrokerStatementReportResponse,
    LiveDailyReviewReportResponse,
    LiveDeploymentPlanResponse,
    LiveDeploymentPlanUpdate,
    LiveDeploymentStatusResponse,
    LivePaperEvidenceReportResponse,
    LiveProfitMilestoneReportResponse,
    StrategyEvidenceReviewResponse,
)
from aurex.live_deployment.service import LiveMicroDeploymentService

router = APIRouter(prefix="/live", tags=["live-micro-deployment"])
DbSession = Annotated[Session, Depends(get_db)]


def service(db: Session) -> LiveMicroDeploymentService:
    return LiveMicroDeploymentService(db, get_settings())


@router.get("/deployment", response_model=LiveDeploymentStatusResponse)
def live_deployment_status(db: DbSession) -> LiveDeploymentStatusResponse:
    result = service(db).deployment_status()
    db.commit()
    return result


@router.patch("/deployment/plan", response_model=LiveDeploymentPlanResponse)
def update_live_deployment_plan(
    payload: LiveDeploymentPlanUpdate,
    db: DbSession,
) -> object:
    plan = service(db).update_plan(payload)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/deployment/checks/run", response_model=LiveDeploymentStatusResponse)
def run_live_deployment_checks(db: DbSession) -> LiveDeploymentStatusResponse:
    result = service(db).deployment_status()
    db.commit()
    return result


@router.post("/deployment/daily-review", response_model=LiveDailyReviewReportResponse)
def create_daily_review(
    payload: DailyReviewRequest,
    db: DbSession,
) -> object:
    report = service(db).create_daily_review(payload)
    db.commit()
    db.refresh(report)
    return report


@router.get("/deployment/daily-reviews", response_model=list[LiveDailyReviewReportResponse])
def list_daily_reviews(db: DbSession) -> object:
    return service(db).list_daily_reviews()


@router.post("/deployment/approvals", response_model=LiveApprovalRecordResponse)
def record_approval(
    payload: LiveApprovalRecordRequest,
    db: DbSession,
) -> object:
    record = service(db).record_approval(payload)
    db.commit()
    db.refresh(record)
    return record


@router.get("/deployment/approvals", response_model=list[LiveApprovalRecordResponse])
def list_approvals(db: DbSession) -> object:
    return service(db).list_approval_records()


@router.post(
    "/deployment/paper-evidence/run",
    response_model=LivePaperEvidenceReportResponse,
)
def generate_paper_evidence(db: DbSession) -> object:
    report = service(db).generate_paper_evidence_report()
    db.commit()
    db.refresh(report)
    return report


@router.get(
    "/deployment/paper-evidence",
    response_model=list[LivePaperEvidenceReportResponse],
)
def list_paper_evidence(db: DbSession) -> object:
    return service(db).list_paper_evidence_reports()


@router.post(
    "/deployment/broker-statements/reconcile",
    response_model=LiveBrokerStatementReportResponse,
)
def reconcile_broker_statement(
    payload: BrokerStatementReconciliationRequest,
    db: DbSession,
) -> object:
    report = service(db).reconcile_broker_statement(payload)
    db.commit()
    db.refresh(report)
    return report


@router.post(
    "/deployment/broker-statements/preflight-csv",
    response_model=BrokerStatementCsvPreflightResponse,
)
def preflight_broker_statement_csv(
    payload: BrokerStatementCsvReconciliationRequest,
    db: DbSession,
) -> dict[str, object]:
    try:
        return service(db).preflight_broker_statement_csv(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/deployment/broker-statements/reconcile-csv",
    response_model=LiveBrokerStatementReportResponse,
)
def reconcile_broker_statement_csv(
    payload: BrokerStatementCsvReconciliationRequest,
    db: DbSession,
) -> object:
    try:
        report = service(db).reconcile_broker_statement_csv(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.commit()
    db.refresh(report)
    return report


@router.get(
    "/deployment/broker-statements",
    response_model=list[LiveBrokerStatementReportResponse],
)
def list_broker_statement_reports(db: DbSession) -> object:
    return service(db).list_broker_statement_reports()


@router.post(
    "/deployment/profit-milestone/run",
    response_model=LiveProfitMilestoneReportResponse,
)
def generate_profit_milestone(db: DbSession) -> object:
    report = service(db).generate_profit_milestone_report()
    db.commit()
    db.refresh(report)
    return report


@router.get(
    "/deployment/profit-milestones",
    response_model=list[LiveProfitMilestoneReportResponse],
)
def list_profit_milestone_reports(db: DbSession) -> object:
    return service(db).list_profit_milestone_reports()


@router.post(
    "/deployment/evidence-review/run",
    response_model=StrategyEvidenceReviewResponse,
)
def generate_strategy_evidence_review(db: DbSession) -> object:
    review = service(db).generate_strategy_evidence_review()
    db.commit()
    db.refresh(review)
    return review


@router.get(
    "/deployment/evidence-reviews",
    response_model=list[StrategyEvidenceReviewResponse],
)
def list_strategy_evidence_reviews(db: DbSession) -> object:
    return service(db).list_strategy_evidence_reviews()


@router.post("/deployment/approval-packet", response_model=LiveApprovalPacketResponse)
def submit_approval_packet(
    payload: LiveApprovalPacketRequest,
    db: DbSession,
) -> object:
    packet = service(db).submit_approval_packet(payload)
    db.commit()
    db.refresh(packet)
    return packet


@router.get(
    "/deployment/approval-packets",
    response_model=list[LiveApprovalPacketResponse],
)
def list_approval_packets(db: DbSession) -> object:
    return service(db).list_approval_packets()


@router.post("/deployment/activation-attempt", response_model=LiveActivationAttemptResponse)
def activation_attempt(db: DbSession) -> LiveActivationAttemptResponse:
    result = service(db).activation_attempt()
    db.commit()
    return result
