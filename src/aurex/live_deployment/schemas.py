from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurex.domain.enums import (
    LiveApprovalPacketStatus,
    LiveApprovalStatus,
    LiveApprovalType,
    LiveDailyReviewStatus,
    LiveDeploymentStatus,
    ReadinessStatus,
    ReconciliationStatus,
    StrategyEvidenceDecision,
)


class LiveDeploymentPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    broker_connection_id: str | None = Field(default=None, min_length=1)
    account_id: str | None = Field(default=None, min_length=1)
    strategy: str | None = Field(default=None, min_length=1, max_length=100)
    symbols: list[str] | None = Field(default=None, min_length=1, max_length=3)
    risk_per_trade: Decimal | None = Field(default=None, gt=0)
    max_daily_loss: Decimal | None = Field(default=None, gt=0)
    max_weekly_loss: Decimal | None = Field(default=None, gt=0)
    max_open_positions: int | None = Field(default=None, ge=1)
    target_net_profit: Decimal | None = Field(default=None, gt=0)


class DailyReviewRequest(BaseModel):
    review_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class LiveApprovalRecordRequest(BaseModel):
    approval_type: LiveApprovalType
    approved: bool
    approver: str = Field(min_length=1, max_length=120)
    evidence_reference: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=1000)
    expires_at: datetime | None = None


class LiveApprovalPacketRequest(BaseModel):
    broker_name: str = Field(min_length=1, max_length=120)
    account_label: str = Field(min_length=1, max_length=120)
    account_type: str = Field(min_length=1, max_length=80)
    asset_class: str = Field(min_length=1, max_length=80)
    jurisdiction: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="USD", min_length=3, max_length=12)
    broker_terms_reference: str = Field(min_length=1, max_length=1000)
    fee_schedule_reference: str = Field(min_length=1, max_length=1000)
    margin_policy_reference: str = Field(min_length=1, max_length=1000)
    account_constraints_reference: str = Field(min_length=1, max_length=1000)
    execution_policy_reference: str = Field(min_length=1, max_length=1000)
    fee_slippage_model_reference: str = Field(min_length=1, max_length=1000)
    paper_to_live_checklist_reference: str = Field(min_length=1, max_length=1000)
    sandbox_test_reference: str | None = Field(default=None, max_length=1000)
    leverage_allowed: bool = False
    tax_notes: str | None = Field(default=None, max_length=1000)
    credentials_stored: bool = False


class BrokerStatementReconciliationRequest(BaseModel):
    statement_reference: str = Field(min_length=1, max_length=1000)
    statement_start_at: datetime | None = None
    statement_end_at: datetime | None = None
    broker_trade_count: int = Field(ge=0)
    broker_net_pl: Decimal
    broker_fees: Decimal = Field(default=Decimal("0"), ge=0)
    broker_slippage: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class BrokerStatementCsvReconciliationRequest(BaseModel):
    statement_reference: str = Field(min_length=1, max_length=1000)
    csv_text: str = Field(min_length=1)
    statement_start_at: datetime | None = None
    statement_end_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class BrokerStatementCsvPreflightResponse(BaseModel):
    statement_reference: str
    status: str
    rows_received: int
    importable_count: int
    rejected_count: int
    broker_trade_count: int
    broker_net_pl: Decimal
    broker_fees: Decimal
    broker_slippage: Decimal
    statement_start_at: datetime | None
    statement_end_at: datetime | None
    required_headers: list[str]
    row_results: list[dict]
    analysis_summary: dict
    deployment_strategy: str
    deployment_symbols: list[str]
    aurex_trade_count: int
    aurex_net_pl: Decimal
    aurex_fees: Decimal
    aurex_slippage: Decimal
    reconciliation_status: str
    reconciliation_discrepancies: list[dict]
    reconciliation_next_action: str
    checked_at: datetime


class LiveDeploymentPlanResponse(BaseModel):
    id: str
    name: str
    broker_connection_id: str | None
    account_id: str | None
    strategy: str
    symbols: list
    status: LiveDeploymentStatus
    risk_per_trade: Decimal
    max_daily_loss: Decimal
    max_weekly_loss: Decimal
    max_open_positions: int
    target_net_profit: Decimal
    live_trading_enabled: bool
    approval_snapshot: dict
    rules_snapshot: dict
    activated_at: datetime | None
    halted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LiveDeploymentGateResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    gate_key: str
    name: str
    status: ReadinessStatus
    required: bool
    evidence_snapshot: dict
    notes: str | None
    last_checked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LiveDailyReviewReportResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    review_date: date
    status: LiveDailyReviewStatus
    realized_pl: Decimal
    trade_count: int
    rule_violations: list
    reconciliation_status: ReconciliationStatus
    review_snapshot: dict
    notes: str | None
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveApprovalRecordResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    approval_type: LiveApprovalType
    status: LiveApprovalStatus
    approver: str
    evidence_reference: str | None
    notes: str | None
    evidence_snapshot: dict
    approved_at: datetime | None
    revoked_at: datetime | None
    expires_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LivePaperEvidenceReportResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    status: ReadinessStatus
    total_trades: int
    minimum_trades: int
    first_trade_at: datetime | None
    latest_trade_at: datetime | None
    calendar_days_observed: int
    minimum_calendar_days: int
    expectancy: Decimal
    profit_factor: Decimal | None
    win_rate: Decimal
    max_drawdown: Decimal
    max_allowed_drawdown: Decimal
    unexplained_trade_count: int
    risk_rule_violation_count: int
    journaled_trade_count: int
    unjournaled_trade_count: int
    journal_rule_violation_count: int
    total_net_pl: Decimal
    reasons: list
    requirements_snapshot: dict
    evidence_snapshot: dict
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveBrokerStatementReportResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    status: ReadinessStatus
    statement_reference: str
    statement_start_at: datetime | None
    statement_end_at: datetime | None
    broker_trade_count: int
    aurex_trade_count: int
    broker_net_pl: Decimal
    aurex_net_pl: Decimal
    broker_fees: Decimal
    aurex_fees: Decimal
    broker_slippage: Decimal
    aurex_slippage: Decimal
    discrepancies: list
    statement_snapshot: dict
    aurex_snapshot: dict
    notes: str | None
    reconciled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveProfitMilestoneReportResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    status: ReadinessStatus
    target_net_profit: Decimal
    total_net_pl: Decimal
    trade_count: int
    first_trade_at: datetime | None
    latest_trade_at: datetime | None
    journaled_trade_count: int
    unjournaled_trade_count: int
    journal_rule_violation_count: int
    unexplained_trade_count: int
    risk_rule_violation_count: int
    daily_loss_breach_count: int
    weekly_loss_breach_count: int
    broker_statement_report_id: str | None
    broker_statement_status: ReadinessStatus | None
    kill_switch_enabled: bool
    live_execution_adapter_implemented: bool
    reasons: list
    requirements_snapshot: dict
    evidence_snapshot: dict
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StrategyEvidenceReviewResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    decision: StrategyEvidenceDecision
    strategy: str
    symbols: list
    summary: str
    reasons: list
    next_actions: list
    gate_snapshot: dict
    evidence_snapshot: dict
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveApprovalPacketResponse(BaseModel):
    id: str
    live_deployment_plan_id: str
    broker_connection_id: str | None
    account_id: str | None
    status: LiveApprovalPacketStatus
    broker_name: str
    account_label: str
    account_type: str
    asset_class: str
    jurisdiction: str
    currency: str
    broker_terms_reference: str | None
    fee_schedule_reference: str | None
    margin_policy_reference: str | None
    account_constraints_reference: str
    execution_policy_reference: str
    fee_slippage_model_reference: str
    paper_to_live_checklist_reference: str
    sandbox_test_reference: str | None
    leverage_allowed: bool
    tax_notes: str | None
    credentials_stored: bool
    evidence_snapshot: dict
    reviewed_at: datetime
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LiveDeploymentStatusResponse(BaseModel):
    activation_allowed: bool
    live_trading_enabled: bool
    status: LiveDeploymentStatus
    summary: str
    plan: LiveDeploymentPlanResponse
    gates: list[LiveDeploymentGateResponse]
    latest_daily_review: LiveDailyReviewReportResponse | None
    approvals: list[LiveApprovalRecordResponse]
    latest_paper_evidence: LivePaperEvidenceReportResponse | None
    latest_broker_statement: LiveBrokerStatementReportResponse | None
    latest_profit_milestone: LiveProfitMilestoneReportResponse | None
    latest_approval_packet: LiveApprovalPacketResponse | None


class LiveActivationAttemptResponse(BaseModel):
    activation_allowed: bool
    live_trading_enabled: bool
    status: LiveDeploymentStatus
    blocking_gate_keys: list[str]
    blocking_gates: list[dict] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    message: str
