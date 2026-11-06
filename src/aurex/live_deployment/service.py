import json
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.analytics_engine.service import summarize_paper_trades
from aurex.backtest_engine.eligibility import (
    accepted_backtest_source_evidence,
    accepted_backtest_source_reasons,
    persisted_backtest_protocol_reasons,
    persisted_trade_evidence_reasons,
)
from aurex.backtest_engine.service import (
    EXPLICIT_WALK_FORWARD_METHOD,
    accepted_backtest_strategy_parameter_reasons,
    strategy_parameter_evidence_snapshot,
    walk_forward_evidence_hash,
)
from aurex.broker_engine.service import BrokerReadinessService
from aurex.config.settings import Settings
from aurex.db.base import utc_now
from aurex.db.models import (
    Account,
    BacktestRun,
    BrokerConnection,
    LiveApprovalPacket,
    LiveApprovalRecord,
    LiveBrokerStatementReport,
    LiveDailyReviewReport,
    LiveDeploymentGate,
    LiveDeploymentPlan,
    LivePaperEvidenceReport,
    LiveProfitMilestoneReport,
    PaperOrder,
    PaperTrade,
    RiskDecision,
    Signal,
    StrategyEvidenceReview,
    TradeJournalEntry,
)
from aurex.domain.enums import (
    BrokerConnectionStatus,
    BrokerEnvironment,
    LiveApprovalPacketStatus,
    LiveApprovalStatus,
    LiveApprovalType,
    LiveDailyReviewStatus,
    LiveDeploymentStatus,
    OrderStatus,
    ReadinessStatus,
    ReconciliationStatus,
    StrategyEvidenceDecision,
    TradeStatus,
)
from aurex.execution_engine.evidence_import import (
    imported_paper_trade_evidence_hash,
    imported_paper_trade_evidence_payload_from_models,
)
from aurex.execution_engine.paper import (
    DETERMINISTIC_PAPER_FILL_MODEL,
    EVIDENCE_GRADE_PAPER_FILL_MODELS,
    IMPORTED_PAPER_FILL_MODEL,
    PAPER_EXECUTION_SCHEMA_VERSION,
    calculate_trade_pl,
    paper_execution_evidence_hash,
)
from aurex.live_deployment.execution_adapter import live_execution_adapter_audit
from aurex.live_deployment.schemas import (
    BrokerStatementCsvReconciliationRequest,
    BrokerStatementReconciliationRequest,
    DailyReviewRequest,
    LiveActivationAttemptResponse,
    LiveApprovalPacketRequest,
    LiveApprovalRecordRequest,
    LiveDeploymentPlanUpdate,
    LiveDeploymentStatusResponse,
)
from aurex.live_deployment.statement_csv import (
    BROKER_STATEMENT_REQUIRED_HEADERS,
    preflight_broker_statement_csv,
    statement_payload_from_csv_summary,
    summarize_broker_statement_csv,
)
from aurex.observability.system_events import SystemEventRecorder
from aurex.risk_engine.calculations import calculate_stop_risk_amount
from aurex.risk_engine.service import RiskEngine
from aurex.strategy_engine.service import StrategyPortfolioService

DEFAULT_PLAN_NAME = "Stage 14 Micro Deployment"
DEFAULT_TARGET_PROFIT = Decimal("100")
MAX_MICRO_RISK_PER_TRADE = Decimal("0.005")
MAX_MICRO_DAILY_LOSS = Decimal("0.01")
MAX_MICRO_WEEKLY_LOSS = Decimal("0.03")
MIN_PAPER_TRADES = 100
MIN_PAPER_CALENDAR_DAYS = 30
MIN_PAPER_PROFIT_FACTOR = Decimal("1.20")
MIN_PAPER_ACTIVE_DAYS = 15
MAX_SINGLE_DAY_TRADE_SHARE = Decimal("0.25")
RISK_TOLERANCE = Decimal("0.00000001")
MIN_ACCEPTED_BACKTEST_TRADES = 100
MIN_ACCEPTED_BACKTEST_OOS_TRADES = 30
MIN_ACCEPTED_BACKTEST_OOS_PROFIT_FACTOR = Decimal("1.15")
MIN_ACCEPTED_BACKTEST_ACTIVE_DAYS = 15
MAX_ACCEPTED_BACKTEST_SINGLE_DAY_SHARE = Decimal("0.25")
MIN_ACCEPTED_BACKTEST_WALK_FORWARD_WINDOWS = 3
MIN_ACCEPTED_BACKTEST_WALK_FORWARD_PASS_RATE = Decimal("0.66")
STRATEGY_EVIDENCE_REVIEW_GATE_KEYS = (
    "live_trading_disabled",
    "mkt_donor_credential_boundary",
    "one_strategy_selected",
    "accepted_backtest_complete",
    "symbol_scope_limited",
    "tiny_risk_limits",
    "paper_evidence_complete",
    "prediction_demo_campaign_quality",
    "broker_statement_reconciliation",
    "kill_switch_clear",
)
NEGATIVE_BACKTEST_REASONS = {
    "accepted_backtest_oos_expectancy_not_positive",
    "accepted_backtest_oos_profit_factor_below_minimum",
    "accepted_backtest_max_drawdown_exceeds_declared_limit",
    "accepted_backtest_walk_forward_pass_rate_not_met",
}
NEGATIVE_PAPER_EVIDENCE_REASONS = {
    "expectancy_not_positive",
    "profit_factor_below_minimum",
    "max_drawdown_exceeds_limit",
    "unexplained_trades_present",
    "risk_rule_violations_present",
    "journal_rule_violations_present",
}


class LiveMicroDeploymentService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def deployment_status(self) -> LiveDeploymentStatusResponse:
        plan = self.get_or_create_default_plan()
        gates = self.run_gates(plan)
        latest_review = self.latest_daily_review(plan.id)
        approvals = self.list_approval_records()
        latest_paper_evidence = self.latest_paper_evidence_report(plan.id)
        latest_broker_statement = self.latest_broker_statement_report(plan.id)
        latest_profit_milestone = self.latest_profit_milestone_report(plan.id)
        latest_approval_packet = self.latest_approval_packet(plan.id)
        activation_allowed = self._activation_allowed(gates)
        plan.status = (
            LiveDeploymentStatus.READY_FOR_APPROVAL
            if activation_allowed
            else LiveDeploymentStatus.BLOCKED
        )
        plan.live_trading_enabled = False
        summary = (
            "Live micro-deployment gates are ready for explicit approval."
            if activation_allowed
            else "Live micro-deployment is blocked until every required gate is proven."
        )
        self.session.flush()
        return LiveDeploymentStatusResponse(
            activation_allowed=activation_allowed,
            live_trading_enabled=self.settings.live_trading_enabled,
            status=plan.status,
            summary=summary,
            plan=plan,
            gates=gates,
            latest_daily_review=latest_review,
            approvals=approvals,
            latest_paper_evidence=latest_paper_evidence,
            latest_broker_statement=latest_broker_statement,
            latest_profit_milestone=latest_profit_milestone,
            latest_approval_packet=latest_approval_packet,
        )

    def get_or_create_default_plan(self) -> LiveDeploymentPlan:
        plan = self.session.execute(
            select(LiveDeploymentPlan).where(LiveDeploymentPlan.name == DEFAULT_PLAN_NAME)
        ).scalar_one_or_none()
        if plan is not None:
            return plan

        plan = LiveDeploymentPlan(
            name=DEFAULT_PLAN_NAME,
            strategy="trend_pullback_v1",
            symbols=["BTCUSDT"],
            status=LiveDeploymentStatus.BLOCKED,
            risk_per_trade=Decimal("0.0025"),
            max_daily_loss=MAX_MICRO_DAILY_LOSS,
            max_weekly_loss=MAX_MICRO_WEEKLY_LOSS,
            max_open_positions=1,
            target_net_profit=DEFAULT_TARGET_PROFIT,
            live_trading_enabled=False,
            approval_snapshot={
                "broker_approved": False,
                "account_approved": False,
                "jurisdiction_approved": False,
                "live_execution_approved": False,
            },
            rules_snapshot=self._rules_snapshot(),
        )
        self.session.add(plan)
        self.session.flush()
        return plan

    def update_plan(self, payload: LiveDeploymentPlanUpdate) -> LiveDeploymentPlan:
        plan = self.get_or_create_default_plan()
        changes = payload.model_dump(exclude_unset=True)
        if "symbols" in changes and changes["symbols"] is not None:
            changes["symbols"] = normalized_symbols(changes["symbols"])
        for field, value in changes.items():
            setattr(plan, field, value)

        plan.status = LiveDeploymentStatus.BLOCKED
        plan.live_trading_enabled = False
        plan.rules_snapshot = self._rules_snapshot()
        self.run_gates(plan)
        SystemEventRecorder(self.session).info(
            "live_micro_deployment",
            "Live micro-deployment plan updated",
            {
                "plan_id": plan.id,
                "strategy": plan.strategy,
                "symbols": plan.symbols,
                "risk_per_trade": str(plan.risk_per_trade),
            },
        )
        self.session.flush()
        return plan

    def run_gates(self, plan: LiveDeploymentPlan | None = None) -> list[LiveDeploymentGate]:
        plan = plan or self.get_or_create_default_plan()
        now = utc_now()
        broker_readiness = BrokerReadinessService(self.session, self.settings).readiness_status()
        _, risk_profile = RiskEngine(self.session).get_or_create_default_profile()
        strategy_config = StrategyPortfolioService(self.session).get_config(plan.strategy)
        connection = (
            self.session.get(BrokerConnection, plan.broker_connection_id)
            if plan.broker_connection_id
            else None
        )
        latest_review = self.latest_daily_review(plan.id)
        latest_paper_evidence = self.latest_paper_evidence_report(plan.id)
        latest_backtest = self.latest_accepted_backtest(plan)
        latest_broker_statement = self.latest_broker_statement_report(plan.id)
        latest_packet = self.latest_approval_packet(plan.id)
        latest_strategy_review = self.latest_strategy_evidence_review(plan)
        live_execution_audit = live_execution_adapter_audit(
            settings=self.settings,
            plan=plan,
            connection=connection,
        )
        paper_evidence_audit = self._paper_evidence_report_freshness_audit(
            plan,
            latest_paper_evidence,
        )
        paper_evidence_status = paper_evidence_audit["status"]
        broker_statement_audit = self._broker_statement_report_freshness_audit(
            plan,
            latest_broker_statement,
        )
        broker_statement_status = broker_statement_audit["status"]
        prediction_demo_campaign_audit = prediction_demo_campaign_gate_audit(
            self.session,
            plan.strategy,
        )
        mkt_credential_boundary_audit = mkt_donor_credential_boundary_audit(
            plan.strategy,
        )
        backtest_audit = accepted_backtest_live_readiness_audit(latest_backtest)
        backtest_status = backtest_audit["status"]
        strategy_status = (
            ReadinessStatus.PASS
            if strategy_config is not None and strategy_config.is_enabled
            else ReadinessStatus.BLOCKED
        )
        broker_account_status = (
            ReadinessStatus.PASS
            if connection is not None
            and connection.environment == BrokerEnvironment.LIVE
            and plan.account_id is not None
            and not connection.live_trading_enabled
            and latest_packet is not None
            and latest_packet.status == LiveApprovalPacketStatus.COMPLETE
            and latest_packet.credentials_stored is False
            and latest_packet.leverage_allowed is False
            else ReadinessStatus.BLOCKED
        )
        gate_specs = [
            (
                "live_trading_disabled",
                "Live trading flag disabled",
                (
                    ReadinessStatus.PASS
                    if not self.settings.live_trading_enabled
                    else ReadinessStatus.FAIL
                ),
                {"live_trading_enabled": self.settings.live_trading_enabled},
                "The platform-level live flag must remain disabled until approval.",
            ),
            (
                "stage13_broker_readiness",
                "Stage 13 broker readiness complete",
                (
                    ReadinessStatus.PASS
                    if broker_readiness.ready_for_live
                    else ReadinessStatus.BLOCKED
                ),
                {
                    "broker_ready_for_live": broker_readiness.ready_for_live,
                    "broker_summary": broker_readiness.summary,
                },
                (
                    "Sandbox broker readiness, reconciliation, paper evidence, and "
                    "emergency stop must pass."
                ),
            ),
            (
                "mkt_donor_credential_boundary",
                "MKT donor credential boundary",
                mkt_credential_boundary_audit["status"],
                mkt_credential_boundary_audit,
                (
                    "MKT-derived strategies require the donor runtime to remain demo-scoped: "
                    "production credential files must be absent from inspected donor profiles, "
                    "and Aurex must not read or store credential contents."
                ),
            ),
            (
                "broker_account_selected",
                "One live broker and account selected",
                broker_account_status,
                {
                    "broker_connection_id": plan.broker_connection_id,
                    "account_id": plan.account_id,
                    "environment": connection.environment.value if connection else None,
                    "connection_live_trading_enabled": (
                        connection.live_trading_enabled if connection else None
                    ),
                    "approval_packet_id": latest_packet.id if latest_packet else None,
                    "approval_packet_status": (
                        latest_packet.status.value if latest_packet else None
                    ),
                    "credentials_stored": (
                        latest_packet.credentials_stored if latest_packet else None
                    ),
                    "leverage_allowed": latest_packet.leverage_allowed if latest_packet else None,
                    "account_constraints_reference": (
                        latest_packet.account_constraints_reference
                        if latest_packet
                        else None
                    ),
                    "execution_policy_reference": (
                        latest_packet.execution_policy_reference
                        if latest_packet
                        else None
                    ),
                    "fee_slippage_model_reference": (
                        latest_packet.fee_slippage_model_reference
                        if latest_packet
                        else None
                    ),
                    "paper_to_live_checklist_reference": (
                        latest_packet.paper_to_live_checklist_reference
                        if latest_packet
                        else None
                    ),
                },
                (
                    "A complete no-credentials, no-leverage broker/account/jurisdiction "
                    "packet with due-diligence references is required."
                ),
            ),
            (
                "one_strategy_selected",
                "One proven strategy selected",
                strategy_status,
                {
                    "strategy": plan.strategy,
                    "strategy_enabled": strategy_config.is_enabled if strategy_config else None,
                },
                "Stage 14 is limited to one enabled strategy.",
            ),
            (
                "accepted_backtest_complete",
                "Accepted backtest complete",
                backtest_status,
                {
                    "backtest_run_id": latest_backtest.id if latest_backtest else None,
                    "strategy": plan.strategy,
                    "symbols": list(plan.symbols or []),
                    "config_hash": latest_backtest.config_hash if latest_backtest else None,
                    "strategy_version": (
                        latest_backtest.strategy_version if latest_backtest else None
                    ),
                    "timeframe": latest_backtest.timeframe if latest_backtest else None,
                    "data_source": latest_backtest.data_source if latest_backtest else None,
                    "total_trades": (
                        latest_backtest.result.total_trades
                        if latest_backtest and latest_backtest.result
                        else 0
                    ),
                    "acceptance_passed": (
                        latest_backtest.result.acceptance_passed
                        if latest_backtest and latest_backtest.result
                        else False
                    ),
                    "acceptance_reasons": (
                        latest_backtest.result.acceptance_reasons
                        if latest_backtest and latest_backtest.result
                        else []
                    ),
                    "minimum_trades": MIN_ACCEPTED_BACKTEST_TRADES,
                    "minimum_out_of_sample_trades": MIN_ACCEPTED_BACKTEST_OOS_TRADES,
                    "minimum_out_of_sample_profit_factor": str(
                        MIN_ACCEPTED_BACKTEST_OOS_PROFIT_FACTOR
                    ),
                    "minimum_active_trading_days": MIN_ACCEPTED_BACKTEST_ACTIVE_DAYS,
                    "max_single_day_trade_share_limit": str(
                        MAX_ACCEPTED_BACKTEST_SINGLE_DAY_SHARE
                    ),
                    "minimum_walk_forward_windows": (
                        MIN_ACCEPTED_BACKTEST_WALK_FORWARD_WINDOWS
                    ),
                    "minimum_walk_forward_pass_rate": str(
                        MIN_ACCEPTED_BACKTEST_WALK_FORWARD_PASS_RATE
                    ),
                    "out_of_sample": backtest_audit["out_of_sample"],
                    "walk_forward": backtest_audit["walk_forward"],
                    "trade_distribution": backtest_audit["trade_distribution"],
                    "market_regime_breakdown": backtest_audit[
                        "market_regime_breakdown"
                    ],
                    "strategy_parameter_evidence": backtest_audit[
                        "strategy_parameter_evidence"
                    ],
                    "source_evidence": backtest_audit["source_evidence"],
                    "live_readiness_reasons": backtest_audit["reasons"],
                },
                (
                    "A completed accepted backtest with minimum trade count, "
                    "out-of-sample evidence, walk-forward validation, trade-date "
                    "distribution, regime coverage, and cost/risk assumptions is "
                    "required before paper evidence can support readiness."
                ),
            ),
            (
                "symbol_scope_limited",
                "One to three symbols selected",
                symbol_scope_status(plan.symbols),
                {"symbols": list(plan.symbols or []), "symbol_count": len(plan.symbols or [])},
                "Stage 14 can monitor only one to three approved symbols.",
            ),
            (
                "tiny_risk_limits",
                "Tiny live risk limits configured",
                tiny_risk_status(plan),
                {
                    "risk_per_trade": str(plan.risk_per_trade),
                    "max_daily_loss": str(plan.max_daily_loss),
                    "max_weekly_loss": str(plan.max_weekly_loss),
                    "max_open_positions": plan.max_open_positions,
                },
                "Risk must stay within the first-live micro-deployment limits.",
            ),
            (
                "paper_evidence_complete",
                "Paper evidence complete",
                paper_evidence_status,
                {
                    "paper_evidence_report_id": (
                        latest_paper_evidence.id if latest_paper_evidence else None
                    ),
                    "total_paper_trades": (
                        latest_paper_evidence.total_trades if latest_paper_evidence else 0
                    ),
                    "expectancy": (
                        str(latest_paper_evidence.expectancy)
                        if latest_paper_evidence
                        else None
                    ),
                    "profit_factor": (
                        str(latest_paper_evidence.profit_factor)
                        if latest_paper_evidence and latest_paper_evidence.profit_factor
                        else None
                    ),
                    "max_drawdown": (
                        str(latest_paper_evidence.max_drawdown)
                        if latest_paper_evidence
                        else None
                    ),
                    "max_allowed_drawdown": (
                        str(latest_paper_evidence.max_allowed_drawdown)
                        if latest_paper_evidence
                        else None
                    ),
                    "unexplained_trade_count": (
                        latest_paper_evidence.unexplained_trade_count
                        if latest_paper_evidence
                        else 0
                    ),
                    "risk_rule_violation_count": (
                        latest_paper_evidence.risk_rule_violation_count
                        if latest_paper_evidence
                        else 0
                    ),
                    "journaled_trade_count": (
                        latest_paper_evidence.journaled_trade_count
                        if latest_paper_evidence
                        else 0
                    ),
                    "unjournaled_trade_count": (
                        latest_paper_evidence.unjournaled_trade_count
                        if latest_paper_evidence
                        else 0
                    ),
                    "journal_rule_violation_count": (
                        latest_paper_evidence.journal_rule_violation_count
                        if latest_paper_evidence
                        else 0
                    ),
                    "minimum_trades": MIN_PAPER_TRADES,
                    "calendar_days_observed": (
                        latest_paper_evidence.calendar_days_observed
                        if latest_paper_evidence
                        else 0
                    ),
                    "minimum_calendar_days": MIN_PAPER_CALENDAR_DAYS,
                    "active_trading_days": (
                        latest_paper_evidence.evidence_snapshot.get(
                            "active_trading_days",
                            0,
                        )
                        if latest_paper_evidence
                        else 0
                    ),
                    "minimum_active_trading_days": MIN_PAPER_ACTIVE_DAYS,
                    "max_single_day_trade_share": (
                        latest_paper_evidence.evidence_snapshot.get(
                            "max_single_day_trade_share",
                            "0",
                        )
                        if latest_paper_evidence
                        else "0"
                    ),
                    "max_single_day_trade_share_limit": str(MAX_SINGLE_DAY_TRADE_SHARE),
                    "minimum_profit_factor": str(MIN_PAPER_PROFIT_FACTOR),
                    "strategy_scope": plan.strategy,
                    "symbol_scope": list(plan.symbols or []),
                    "out_of_scope_trade_count": (
                        latest_paper_evidence.evidence_snapshot.get(
                            "out_of_scope_trade_count",
                            0,
                        )
                        if latest_paper_evidence
                        else 0
                    ),
                    "reasons": latest_paper_evidence.reasons if latest_paper_evidence else [],
                    **paper_evidence_audit,
                },
                (
                    "At least 100 closed paper trades over 30 calendar days with "
                    "sustained active-day coverage, positive expectancy, profit factor "
                    ">= 1.20, drawdown within limits, clean risk lineage, and trade "
                    "journals are required."
                ),
            ),
            (
                "prediction_demo_campaign_quality",
                "Prediction demo campaign quality",
                prediction_demo_campaign_audit["status"],
                prediction_demo_campaign_audit,
                (
                    "MKT/prediction-market live review requires a clean, diverse, "
                    "reconciled prediction paper-demo campaign; non-MKT strategies "
                    "treat this gate as not applicable."
                ),
            ),
            (
                "broker_statement_reconciliation",
                "Broker statement reconciliation complete",
                broker_statement_status,
                {
                    "broker_statement_report_id": (
                        latest_broker_statement.id if latest_broker_statement else None
                    ),
                    "latest_status": (
                        latest_broker_statement.status.value
                        if latest_broker_statement
                        else None
                    ),
                    "broker_trade_count": (
                        latest_broker_statement.broker_trade_count
                        if latest_broker_statement
                        else 0
                    ),
                    "aurex_trade_count": (
                        latest_broker_statement.aurex_trade_count
                        if latest_broker_statement
                        else 0
                    ),
                    "broker_net_pl": (
                        str(latest_broker_statement.broker_net_pl)
                        if latest_broker_statement
                        else None
                    ),
                    "aurex_net_pl": (
                        str(latest_broker_statement.aurex_net_pl)
                        if latest_broker_statement
                        else None
                    ),
                    "discrepancies": (
                        latest_broker_statement.discrepancies
                        if latest_broker_statement
                        else []
                    ),
                    **broker_statement_audit,
                },
                (
                    "A reviewed broker statement must reconcile with Aurex closed-trade "
                    "count, net P/L, fees, and slippage."
                ),
            ),
            (
                "live_execution_adapter_ready",
                "Live execution adapter ready",
                live_execution_audit.status,
                live_execution_audit.evidence_snapshot,
                (
                    "A concrete live broker execution adapter must be implemented, "
                    "configured, and audited before activation can submit orders."
                ),
            ),
            (
                "kill_switch_clear",
                "Risk kill switch clear",
                (
                    ReadinessStatus.PASS
                    if not risk_profile.kill_switch_enabled
                    else ReadinessStatus.FAIL
                ),
                {"kill_switch_enabled": risk_profile.kill_switch_enabled},
                "The risk kill switch must be reset before any live deployment attempt.",
            ),
        ]
        current_review_gate_statuses = strategy_evidence_current_gate_statuses(
            gate_specs,
        )
        current_review_gate_fingerprints = strategy_evidence_current_gate_fingerprints(
            gate_specs,
        )
        strategy_review_audit = strategy_evidence_review_gate_audit(
            plan=plan,
            review=latest_strategy_review,
            latest_backtest=latest_backtest,
            latest_paper_evidence=latest_paper_evidence,
            latest_broker_statement=latest_broker_statement,
            current_gate_statuses=current_review_gate_statuses,
            current_gate_fingerprints=current_review_gate_fingerprints,
        )
        approval_audit = explicit_approval_audit(
            records=self._approval_records_for_plan(plan),
            current_context=live_approval_context_snapshot(
                plan,
                latest_backtest,
                latest_paper_evidence,
                latest_broker_statement,
                latest_strategy_review,
                latest_packet,
                strategy_review_audit=strategy_review_audit,
            ),
            now=now,
        )
        plan.approval_snapshot = approval_audit["approval_snapshot"]
        gate_specs.append(
            (
                "explicit_user_approval",
                "Explicit broker, account, jurisdiction, and live approval",
                approval_audit["status"],
                {
                    **dict(plan.approval_snapshot or {}),
                    "stale_reasons": approval_audit["stale_reasons"],
                    "current_context": approval_audit["current_context"],
                },
                (
                    "The user must explicitly approve the broker, account, jurisdiction, "
                    "and live execution boundary for the current plan and evidence."
                ),
            ),
        )
        strategy_review_status = strategy_review_audit["status"]
        gate_specs.append(
            (
                "strategy_evidence_review_clear",
                "Strategy evidence review clear",
                strategy_review_status,
                {
                    "strategy_review_id": (
                        latest_strategy_review.id if latest_strategy_review else None
                    ),
                    "decision": (
                        latest_strategy_review.decision.value
                        if latest_strategy_review
                        else None
                    ),
                    "strategy": plan.strategy,
                    "symbols": list(plan.symbols or []),
                    "review_symbols": (
                        list(latest_strategy_review.symbols or [])
                        if latest_strategy_review
                        else []
                    ),
                    "summary": (
                        latest_strategy_review.summary if latest_strategy_review else None
                    ),
                    "reasons": (
                        latest_strategy_review.reasons if latest_strategy_review else []
                    ),
                    "next_actions": (
                        latest_strategy_review.next_actions
                        if latest_strategy_review
                        else []
                    ),
                    "reviewed_at": (
                        latest_strategy_review.reviewed_at.isoformat()
                        if latest_strategy_review
                        else None
                    ),
                    **strategy_review_audit,
                },
                (
                    "A latest scoped CANDIDATE strategy evidence review is required "
                    "for the current accepted backtest, paper-evidence report, and "
                    "broker-statement reconciliation before live readiness can proceed."
                ),
            ),
        )
        daily_review_context = daily_review_context_snapshot(
            plan,
            latest_backtest,
            latest_paper_evidence,
            latest_broker_statement,
            latest_strategy_review,
            latest_packet,
            strategy_review_audit=strategy_review_audit,
        )
        daily_review_audit = daily_review_gate_audit(
            latest_review,
            daily_review_context,
        )
        gate_specs.append(
            (
                "daily_review_ready",
                "Daily review report ready",
                daily_review_audit["status"],
                {
                    "latest_daily_review_id": latest_review.id if latest_review else None,
                    "latest_daily_review_status": (
                        latest_review.status.value if latest_review else None
                    ),
                    **daily_review_audit,
                },
                "A clean daily review report is required before activation.",
            ),
        )

        for key, name, status, evidence, notes in gate_specs:
            self._upsert_gate(
                plan,
                key,
                name,
                status,
                {**evidence, "checked_at": now.isoformat()},
                notes,
            )
        self.session.flush()
        return list(
            self.session.execute(
                select(LiveDeploymentGate)
                .where(LiveDeploymentGate.live_deployment_plan_id == plan.id)
                .order_by(LiveDeploymentGate.gate_key.asc())
            ).scalars()
        )

    def create_daily_review(self, payload: DailyReviewRequest) -> LiveDailyReviewReport:
        plan = self.get_or_create_default_plan()
        review_date = payload.review_date or datetime.now(UTC).date()
        existing = self.session.execute(
            select(LiveDailyReviewReport).where(
                LiveDailyReviewReport.live_deployment_plan_id == plan.id,
                LiveDailyReviewReport.review_date == review_date,
            )
        ).scalar_one_or_none()
        latest_reconciliation = BrokerReadinessService(
            self.session,
            self.settings,
        ).latest_reconciliation_report(
            BrokerReadinessService(self.session, self.settings).ensure_sandbox_connection().id
        )
        trades = self._closed_trades_for_date(review_date)
        realized_pl = sum((trade.realized_pl or Decimal("0") for trade in trades), Decimal("0"))
        account, _ = RiskEngine(self.session).get_or_create_default_profile()
        week_trades = self._closed_trades_since(week_start_for_date(review_date))
        weekly_realized_pl = sum(
            (trade.realized_pl or Decimal("0") for trade in week_trades),
            Decimal("0"),
        )
        daily_loss_limit = -(account.current_equity * plan.max_daily_loss)
        weekly_loss_limit = -(account.current_equity * plan.max_weekly_loss)
        consecutive_losses = consecutive_loss_count(self._latest_closed_trades())
        journal_audit = self._paper_evidence_journal_audit(trades)
        latest_backtest = self.latest_accepted_backtest(plan)
        latest_paper_evidence = self.latest_paper_evidence_report(plan.id)
        latest_broker_statement = self.latest_broker_statement_report(plan.id)
        latest_strategy_review = self.latest_strategy_evidence_review(plan)
        latest_packet = self.latest_approval_packet(plan.id)
        current_gates = self.run_gates(plan)
        strategy_review_gate = next(
            (
                gate
                for gate in current_gates
                if gate.gate_key == "strategy_evidence_review_clear"
            ),
            None,
        )
        review_context = daily_review_context_snapshot(
            plan,
            latest_backtest,
            latest_paper_evidence,
            latest_broker_statement,
            latest_strategy_review,
            latest_packet,
            strategy_review_audit=strategy_review_audit_from_gate(strategy_review_gate),
        )
        readiness_violations = []
        protocol_violations = []
        reconciliation_status = (
            latest_reconciliation.status
            if latest_reconciliation
            else ReconciliationStatus.NOT_READY
        )
        if reconciliation_status != ReconciliationStatus.MATCHED:
            readiness_violations.append("broker_reconciliation_not_matched")
        if self.settings.live_trading_enabled:
            protocol_violations.append("live_flag_enabled_without_stage14_approval")
        if realized_pl <= daily_loss_limit and trades:
            protocol_violations.append("daily_loss_limit_breached")
        if weekly_realized_pl <= weekly_loss_limit and week_trades:
            protocol_violations.append("weekly_loss_limit_breached")
        if consecutive_losses >= 3:
            protocol_violations.append("three_consecutive_losses")
        if int(journal_audit["unjournaled_trade_count"]) > 0:
            protocol_violations.append("unjournaled_trades_present")
        if int(journal_audit["journal_rule_violation_count"]) > 0:
            protocol_violations.append("journal_rule_violations_present")

        status = (
            LiveDailyReviewStatus.CLEAN
            if not readiness_violations and not protocol_violations
            else (
                LiveDailyReviewStatus.VIOLATION
                if protocol_violations
                else LiveDailyReviewStatus.BLOCKED
            )
        )
        rule_violations = [*readiness_violations, *protocol_violations]
        report = existing or LiveDailyReviewReport(
            live_deployment_plan=plan,
            review_date=review_date,
        )
        report.status = status
        report.realized_pl = realized_pl
        report.trade_count = len(trades)
        report.rule_violations = rule_violations
        report.reconciliation_status = reconciliation_status
        report.review_snapshot = {
            "live_trading_enabled": self.settings.live_trading_enabled,
            "target_net_profit": str(plan.target_net_profit),
            "closed_trade_ids": [trade.id for trade in trades],
            "latest_reconciliation_id": latest_reconciliation.id if latest_reconciliation else None,
            "daily_realized_pl": str(realized_pl),
            "weekly_realized_pl": str(weekly_realized_pl),
            "daily_loss_limit": str(daily_loss_limit),
            "weekly_loss_limit": str(weekly_loss_limit),
            "consecutive_losses": consecutive_losses,
            "readiness_violations": readiness_violations,
            "protocol_violations": protocol_violations,
            "journal_audit": journal_audit,
            "review_context": review_context,
        }
        report.notes = payload.notes
        report.reviewed_at = utc_now()
        self.session.add(report)
        self.session.flush()
        self.run_gates(plan)
        SystemEventRecorder(self.session).info(
            "live_micro_deployment",
            "Live micro-deployment daily review recorded",
            {"report_id": report.id, "status": report.status.value},
        )
        self.session.flush()
        return report

    def record_approval(self, payload: LiveApprovalRecordRequest) -> LiveApprovalRecord:
        plan = self.get_or_create_default_plan()
        now = utc_now()
        latest_backtest = self.latest_accepted_backtest(plan)
        latest_paper_evidence = self.latest_paper_evidence_report(plan.id)
        latest_broker_statement = self.latest_broker_statement_report(plan.id)
        latest_strategy_review = self.latest_strategy_evidence_review(plan)
        latest_packet = self.latest_approval_packet(plan.id)
        current_gates = self.run_gates(plan)
        strategy_review_gate = next(
            (
                gate
                for gate in current_gates
                if gate.gate_key == "strategy_evidence_review_clear"
            ),
            None,
        )
        strategy_review_gate_evidence = (
            strategy_review_gate.evidence_snapshot
            if strategy_review_gate is not None
            and isinstance(strategy_review_gate.evidence_snapshot, dict)
            else {}
        )
        strategy_review_audit = {
            "status": (
                strategy_review_gate.status
                if strategy_review_gate is not None
                else ReadinessStatus.NOT_RUN
            ),
            "freshness_reasons": strategy_review_gate_evidence.get(
                "freshness_reasons",
                ["strategy_evidence_review_missing"],
            ),
            "current_gate_fingerprints": strategy_review_gate_evidence.get(
                "current_gate_fingerprints",
                {},
            ),
        }
        status = LiveApprovalStatus.APPROVED if payload.approved else LiveApprovalStatus.REVOKED
        record = LiveApprovalRecord(
            live_deployment_plan=plan,
            approval_type=payload.approval_type,
            status=status,
            approver=payload.approver,
            evidence_reference=payload.evidence_reference,
            notes=payload.notes,
            evidence_snapshot={
                "approval_type": payload.approval_type.value,
                "approved": payload.approved,
                "approver": payload.approver,
                "evidence_reference": payload.evidence_reference,
                "live_trading_enabled": self.settings.live_trading_enabled,
                "plan_id": plan.id,
                "approval_context": live_approval_context_snapshot(
                    plan,
                    latest_backtest,
                    latest_paper_evidence,
                    latest_broker_statement,
                    latest_strategy_review,
                    latest_packet,
                    strategy_review_audit=strategy_review_audit,
                ),
            },
            approved_at=now if payload.approved else None,
            revoked_at=now if not payload.approved else None,
            expires_at=payload.expires_at,
        )
        self.session.add(record)
        self.session.flush()
        self.run_gates(plan)
        SystemEventRecorder(self.session).info(
            "live_micro_deployment",
            "Live deployment approval recorded",
            {
                "approval_record_id": record.id,
                "approval_type": record.approval_type.value,
                "status": record.status.value,
            },
        )
        self.session.flush()
        return record

    def submit_approval_packet(self, payload: LiveApprovalPacketRequest) -> LiveApprovalPacket:
        plan = self.get_or_create_default_plan()
        now = utc_now()
        packet_reasons = approval_packet_reasons(payload)
        status = (
            LiveApprovalPacketStatus.DRAFT
            if packet_reasons
            else LiveApprovalPacketStatus.COMPLETE
        )
        account = self._get_or_create_review_account(payload)
        connection = self._get_or_create_review_connection(payload)
        packet = LiveApprovalPacket(
            live_deployment_plan=plan,
            broker_connection=connection,
            account=account,
            status=status,
            broker_name=payload.broker_name.strip(),
            account_label=payload.account_label.strip(),
            account_type=payload.account_type.strip(),
            asset_class=payload.asset_class.strip(),
            jurisdiction=payload.jurisdiction.strip(),
            currency=payload.currency.strip().upper(),
            broker_terms_reference=payload.broker_terms_reference,
            fee_schedule_reference=payload.fee_schedule_reference,
            margin_policy_reference=payload.margin_policy_reference,
            account_constraints_reference=payload.account_constraints_reference,
            execution_policy_reference=payload.execution_policy_reference,
            fee_slippage_model_reference=payload.fee_slippage_model_reference,
            paper_to_live_checklist_reference=payload.paper_to_live_checklist_reference,
            sandbox_test_reference=payload.sandbox_test_reference,
            leverage_allowed=payload.leverage_allowed,
            tax_notes=payload.tax_notes,
            credentials_stored=payload.credentials_stored,
            evidence_snapshot={
                "broker_name": payload.broker_name.strip(),
                "account_label": payload.account_label.strip(),
                "account_type": payload.account_type.strip(),
                "asset_class": payload.asset_class.strip(),
                "jurisdiction": payload.jurisdiction.strip(),
                "currency": payload.currency.strip().upper(),
                "broker_terms_reference": payload.broker_terms_reference,
                "fee_schedule_reference": payload.fee_schedule_reference,
                "margin_policy_reference": payload.margin_policy_reference,
                "account_constraints_reference": payload.account_constraints_reference,
                "execution_policy_reference": payload.execution_policy_reference,
                "fee_slippage_model_reference": payload.fee_slippage_model_reference,
                "paper_to_live_checklist_reference": (
                    payload.paper_to_live_checklist_reference
                ),
                "sandbox_test_reference": payload.sandbox_test_reference,
                "leverage_allowed": payload.leverage_allowed,
                "packet_reasons": packet_reasons,
                "credentials_stored": payload.credentials_stored,
                "live_trading_enabled": self.settings.live_trading_enabled,
                "packet_fingerprint": live_approval_packet_payload_fingerprint(
                    payload,
                    status,
                    broker_connection_id=connection.id,
                    account_id=account.id,
                ),
            },
            reviewed_at=now,
        )
        connection.live_trading_enabled = False
        connection.status = BrokerConnectionStatus.CONFIGURED
        account.mode = "live-review"
        plan.broker_connection = connection
        plan.account = account
        plan.live_trading_enabled = False
        self.session.add(packet)
        self.session.flush()
        self.run_gates(plan)
        SystemEventRecorder(self.session).info(
            "live_micro_deployment",
            "Live approval packet submitted",
            {
                "approval_packet_id": packet.id,
                "broker_connection_id": connection.id,
                "account_id": account.id,
                "status": packet.status.value,
            },
        )
        self.session.flush()
        return packet

    def list_approval_packets(self) -> list[LiveApprovalPacket]:
        plan = self.get_or_create_default_plan()
        return list(
            self.session.execute(
                select(LiveApprovalPacket)
                .where(LiveApprovalPacket.live_deployment_plan_id == plan.id)
                .order_by(LiveApprovalPacket.reviewed_at.desc())
            ).scalars()
        )

    def latest_approval_packet(self, plan_id: str) -> LiveApprovalPacket | None:
        return self.session.execute(
            select(LiveApprovalPacket)
            .where(LiveApprovalPacket.live_deployment_plan_id == plan_id)
            .order_by(LiveApprovalPacket.reviewed_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def latest_accepted_backtest(self, plan: LiveDeploymentPlan) -> BacktestRun | None:
        plan_symbols = set(plan.symbols or [])
        fallback: BacktestRun | None = None
        runs = list(
            self.session.execute(
                select(BacktestRun)
                .where(BacktestRun.strategy == plan.strategy)
                .order_by(BacktestRun.created_at.desc())
            ).scalars()
        )
        for run in runs:
            result = run.result
            if result is None or result.acceptance_passed is not True:
                continue
            run_symbols = set(run.symbols or [])
            if plan_symbols and not plan_symbols.issubset(run_symbols):
                continue
            if fallback is None:
                fallback = run
            if (
                accepted_backtest_live_readiness_audit(run)["status"]
                == ReadinessStatus.PASS
            ):
                return run
        return fallback

    def list_approval_records(self) -> list[LiveApprovalRecord]:
        plan = self.get_or_create_default_plan()
        return list(reversed(self._approval_records_for_plan(plan)))

    def _approval_records_for_plan(
        self,
        plan: LiveDeploymentPlan,
    ) -> list[LiveApprovalRecord]:
        return list(
            self.session.execute(
                select(LiveApprovalRecord)
                .where(LiveApprovalRecord.live_deployment_plan_id == plan.id)
                .order_by(LiveApprovalRecord.created_at.asc())
            ).scalars()
        )

    def generate_paper_evidence_report(self) -> LivePaperEvidenceReport:
        plan = self.get_or_create_default_plan()
        all_closed_trades = self._all_closed_trades_for_evidence()
        closed_trades = self._closed_trades_for_evidence(plan)
        performance = summarize_paper_trades(closed_trades)
        account, _ = RiskEngine(self.session).get_or_create_default_profile()
        max_allowed_drawdown = account.current_equity * plan.max_weekly_loss
        integrity_audit = self._paper_evidence_integrity_audit(closed_trades)
        journal_audit = self._paper_evidence_journal_audit(closed_trades)
        coverage_audit = paper_evidence_coverage_audit(closed_trades)
        scope_audit = paper_evidence_scope_audit(all_closed_trades, closed_trades, plan)
        first_trade_at = min(
            (trade.closed_at for trade in closed_trades if trade.closed_at),
            default=None,
        )
        latest_trade_at = max(
            (trade.closed_at for trade in closed_trades if trade.closed_at),
            default=None,
        )
        calendar_days_observed = observed_calendar_days(first_trade_at, latest_trade_at)
        ledger_snapshot = paper_evidence_ledger_snapshot(
            plan=plan,
            closed_trades=closed_trades,
            performance=performance,
            first_trade_at=first_trade_at,
            latest_trade_at=latest_trade_at,
            calendar_days_observed=calendar_days_observed,
            integrity_audit=integrity_audit,
            journal_audit=journal_audit,
            coverage_audit=coverage_audit,
            scope_audit=scope_audit,
            journal_hash=self._paper_evidence_journal_hash(closed_trades),
            lineage_hash=self._paper_evidence_lineage_hash(closed_trades),
        )
        reasons = paper_evidence_reasons(
            performance,
            calendar_days_observed,
            max_allowed_drawdown,
            integrity_audit,
            journal_audit,
            coverage_audit,
        )
        report = LivePaperEvidenceReport(
            live_deployment_plan=plan,
            status=ReadinessStatus.PASS if not reasons else ReadinessStatus.BLOCKED,
            total_trades=performance.total_trades,
            minimum_trades=MIN_PAPER_TRADES,
            first_trade_at=first_trade_at,
            latest_trade_at=latest_trade_at,
            calendar_days_observed=calendar_days_observed,
            minimum_calendar_days=MIN_PAPER_CALENDAR_DAYS,
            expectancy=performance.expectancy,
            profit_factor=performance.profit_factor,
            win_rate=performance.win_rate,
            max_drawdown=performance.max_drawdown,
            max_allowed_drawdown=max_allowed_drawdown,
            unexplained_trade_count=integrity_audit["unexplained_trade_count"],
            risk_rule_violation_count=integrity_audit["risk_rule_violation_count"],
            journaled_trade_count=journal_audit["journaled_trade_count"],
            unjournaled_trade_count=journal_audit["unjournaled_trade_count"],
            journal_rule_violation_count=journal_audit["journal_rule_violation_count"],
            total_net_pl=performance.total_net_pl,
            reasons=reasons,
            requirements_snapshot={
                "minimum_trades": MIN_PAPER_TRADES,
                "minimum_calendar_days": MIN_PAPER_CALENDAR_DAYS,
                "minimum_active_trading_days": MIN_PAPER_ACTIVE_DAYS,
                "max_single_day_trade_share": str(MAX_SINGLE_DAY_TRADE_SHARE),
                "minimum_profit_factor": str(MIN_PAPER_PROFIT_FACTOR),
                "max_allowed_drawdown": str(max_allowed_drawdown),
                "expectancy_must_be_positive": True,
                "unexplained_trade_count_must_be_zero": True,
                "risk_rule_violation_count_must_be_zero": True,
                "every_fill_must_be_evidence_grade": True,
                "execution_quality_violation_count_must_be_zero": True,
                "evidence_grade_fill_models": sorted(
                    EVIDENCE_GRADE_PAPER_FILL_MODELS
                ),
                "journal_required_for_every_trade": True,
                "journal_rule_violation_count_must_be_zero": True,
                "strategy_scope": plan.strategy,
                "symbol_scope": list(plan.symbols or []),
            },
            evidence_snapshot={
                **performance_snapshot(performance),
                "first_trade_at": first_trade_at.isoformat() if first_trade_at else None,
                "latest_trade_at": latest_trade_at.isoformat() if latest_trade_at else None,
                "calendar_days_observed": calendar_days_observed,
                "minimum_calendar_days": MIN_PAPER_CALENDAR_DAYS,
                "max_allowed_drawdown": str(max_allowed_drawdown),
                **integrity_audit,
                **journal_audit,
                **coverage_audit,
                **scope_audit,
                "ledger_snapshot": ledger_snapshot,
            },
            generated_at=utc_now(),
        )
        self.session.add(report)
        self.session.flush()
        self.run_gates(plan)
        SystemEventRecorder(self.session).info(
            "live_micro_deployment",
            "Paper evidence report generated",
            {"report_id": report.id, "status": report.status.value},
        )
        self.session.flush()
        return report

    def list_paper_evidence_reports(self) -> list[LivePaperEvidenceReport]:
        plan = self.get_or_create_default_plan()
        return list(
            self.session.execute(
                select(LivePaperEvidenceReport)
                .where(LivePaperEvidenceReport.live_deployment_plan_id == plan.id)
                .order_by(LivePaperEvidenceReport.generated_at.desc())
            ).scalars()
        )

    def latest_paper_evidence_report(
        self,
        plan_id: str,
    ) -> LivePaperEvidenceReport | None:
        return self.session.execute(
            select(LivePaperEvidenceReport)
            .where(LivePaperEvidenceReport.live_deployment_plan_id == plan_id)
            .order_by(LivePaperEvidenceReport.generated_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _paper_evidence_report_freshness_audit(
        self,
        plan: LiveDeploymentPlan,
        report: LivePaperEvidenceReport | None,
    ) -> dict[str, object]:
        if report is None:
            return {
                "status": ReadinessStatus.NOT_RUN,
                "freshness_reasons": ["paper_evidence_report_missing"],
                "reviewed_ledger": {},
                "current_ledger": self._current_paper_evidence_ledger_snapshot(plan),
            }

        reviewed_ledger = (report.evidence_snapshot or {}).get("ledger_snapshot")
        current_ledger = self._current_paper_evidence_ledger_snapshot(plan)
        freshness_reasons = paper_evidence_report_freshness_reasons(
            reviewed_ledger,
            current_ledger,
        )
        status = (
            ReadinessStatus.BLOCKED
            if report.status == ReadinessStatus.PASS and freshness_reasons
            else report.status
        )
        return {
            "status": status,
            "freshness_reasons": freshness_reasons,
            "reviewed_ledger": reviewed_ledger if isinstance(reviewed_ledger, dict) else {},
            "current_ledger": current_ledger,
        }

    def _current_paper_evidence_ledger_snapshot(
        self,
        plan: LiveDeploymentPlan,
    ) -> dict[str, object]:
        all_closed_trades = self._all_closed_trades_for_evidence()
        closed_trades = self._closed_trades_for_evidence(plan)
        performance = summarize_paper_trades(closed_trades)
        integrity_audit = self._paper_evidence_integrity_audit(closed_trades)
        journal_audit = self._paper_evidence_journal_audit(closed_trades)
        coverage_audit = paper_evidence_coverage_audit(closed_trades)
        scope_audit = paper_evidence_scope_audit(all_closed_trades, closed_trades, plan)
        first_trade_at = min(
            (trade.closed_at for trade in closed_trades if trade.closed_at),
            default=None,
        )
        latest_trade_at = max(
            (trade.closed_at for trade in closed_trades if trade.closed_at),
            default=None,
        )
        return paper_evidence_ledger_snapshot(
            plan=plan,
            closed_trades=closed_trades,
            performance=performance,
            first_trade_at=first_trade_at,
            latest_trade_at=latest_trade_at,
            calendar_days_observed=observed_calendar_days(
                first_trade_at,
                latest_trade_at,
            ),
            integrity_audit=integrity_audit,
            journal_audit=journal_audit,
            coverage_audit=coverage_audit,
            scope_audit=scope_audit,
            journal_hash=self._paper_evidence_journal_hash(closed_trades),
            lineage_hash=self._paper_evidence_lineage_hash(closed_trades),
        )

    def _paper_evidence_journal_hash(
        self,
        closed_trades: list[PaperTrade],
    ) -> str:
        trade_ids = [trade.id for trade in closed_trades]
        if not trade_ids:
            return stable_snapshot_hash([])
        entries = list(
            self.session.execute(
                select(TradeJournalEntry).where(
                    TradeJournalEntry.paper_trade_id.in_(trade_ids)
                )
            ).scalars()
        )
        rows = [
            {
                "id": entry.id,
                "paper_trade_id": entry.paper_trade_id,
                "author": entry.author,
                "thesis": entry.thesis,
                "execution_notes": entry.execution_notes,
                "outcome_notes": entry.outcome_notes,
                "rule_followed": entry.rule_followed,
                "emotional_override": entry.emotional_override,
                "journaled_at": normalized_datetime_text(entry.journaled_at),
            }
            for entry in sorted(entries, key=lambda item: item.id)
        ]
        return stable_snapshot_hash(rows)

    def _paper_evidence_lineage_hash(
        self,
        closed_trades: list[PaperTrade],
    ) -> str:
        trade_ids = [trade.id for trade in closed_trades]
        if not trade_ids:
            return stable_snapshot_hash([])
        rows = self.session.execute(
            select(PaperTrade, PaperOrder, RiskDecision, Signal)
            .outerjoin(PaperOrder, PaperTrade.paper_order_id == PaperOrder.id)
            .outerjoin(RiskDecision, PaperOrder.risk_decision_id == RiskDecision.id)
            .outerjoin(Signal, PaperOrder.signal_id == Signal.id)
            .where(PaperTrade.id.in_(trade_ids))
        ).all()
        snapshot = [
            {
                "trade_id": trade.id,
                "paper_order_id": order.id if order else None,
                "paper_order_status": order.status.value if order else None,
                "paper_order_fees": normalized_optional_decimal_text(
                    order.fees if order else None
                ),
                "paper_order_slippage": normalized_optional_decimal_text(
                    order.slippage if order else None
                ),
                "risk_decision_id": decision.id if decision else None,
                "risk_decision_approved": decision.approved if decision else None,
                "risk_decision_risk_amount": normalized_optional_decimal_text(
                    decision.risk_amount if decision else None
                ),
                "risk_decision_position_size": normalized_optional_decimal_text(
                    decision.position_size if decision else None
                ),
                "signal_id": signal.id if signal else None,
                "signal_status": signal.status.value if signal else None,
                "signal_strategy": signal.strategy if signal else None,
                "signal_symbol": signal.symbol if signal else None,
            }
            for trade, order, decision, signal in rows
        ]
        return stable_snapshot_hash(
            sorted(snapshot, key=lambda item: str(item["trade_id"]))
        )

    def reconcile_broker_statement(
        self,
        payload: BrokerStatementReconciliationRequest,
    ) -> LiveBrokerStatementReport:
        plan = self.get_or_create_default_plan()
        closed_trades = self._closed_trades_for_statement(
            plan,
            payload.statement_start_at,
            payload.statement_end_at,
        )
        aurex_trade_count = len(closed_trades)
        aurex_net_pl = sum(
            (trade.realized_pl or Decimal("0") for trade in closed_trades),
            Decimal("0"),
        )
        aurex_fees = sum((trade.fees or Decimal("0") for trade in closed_trades), Decimal("0"))
        aurex_slippage = sum(
            (trade.slippage or Decimal("0") for trade in closed_trades),
            Decimal("0"),
        )
        ledger_snapshot = broker_statement_ledger_snapshot(
            plan=plan,
            closed_trades=closed_trades,
            statement_start_at=payload.statement_start_at,
            statement_end_at=payload.statement_end_at,
        )
        discrepancies = broker_statement_discrepancies(
            payload,
            aurex_trade_count=aurex_trade_count,
            aurex_net_pl=aurex_net_pl,
            aurex_fees=aurex_fees,
            aurex_slippage=aurex_slippage,
        )
        report = LiveBrokerStatementReport(
            live_deployment_plan=plan,
            status=ReadinessStatus.PASS if not discrepancies else ReadinessStatus.BLOCKED,
            statement_reference=payload.statement_reference,
            statement_start_at=payload.statement_start_at,
            statement_end_at=payload.statement_end_at,
            broker_trade_count=payload.broker_trade_count,
            aurex_trade_count=aurex_trade_count,
            broker_net_pl=payload.broker_net_pl,
            aurex_net_pl=aurex_net_pl,
            broker_fees=payload.broker_fees,
            aurex_fees=aurex_fees,
            broker_slippage=payload.broker_slippage,
            aurex_slippage=aurex_slippage,
            discrepancies=discrepancies,
            statement_snapshot={
                "statement_reference": payload.statement_reference,
                "statement_start_at": (
                    payload.statement_start_at.isoformat()
                    if payload.statement_start_at
                    else None
                ),
                "statement_end_at": (
                    payload.statement_end_at.isoformat() if payload.statement_end_at else None
                ),
                "broker_trade_count": payload.broker_trade_count,
                "broker_net_pl": str(payload.broker_net_pl),
                "broker_fees": str(payload.broker_fees),
                "broker_slippage": str(payload.broker_slippage),
            },
            aurex_snapshot={
                "closed_trade_ids": [trade.id for trade in closed_trades],
                "aurex_trade_count": aurex_trade_count,
                "aurex_net_pl": str(aurex_net_pl),
                "aurex_fees": str(aurex_fees),
                "aurex_slippage": str(aurex_slippage),
                "strategy": plan.strategy,
                "symbols": list(plan.symbols or []),
                "ledger_snapshot": ledger_snapshot,
            },
            notes=payload.notes,
            reconciled_at=utc_now(),
        )
        self.session.add(report)
        self.session.flush()
        self.run_gates(plan)
        SystemEventRecorder(self.session).info(
            "live_micro_deployment",
            "Broker statement reconciliation recorded",
            {"report_id": report.id, "status": report.status.value},
        )
        self.session.flush()
        return report

    def preflight_broker_statement_csv(
        self,
        payload: BrokerStatementCsvReconciliationRequest,
    ) -> dict[str, object]:
        plan = self.get_or_create_default_plan()
        summary = summarize_broker_statement_csv(payload)
        if summary.status == "READY":
            csv_payload = statement_payload_from_csv_summary(payload, summary)
            ledger_preview = self._broker_statement_reconciliation_preview(
                plan,
                csv_payload,
            )
        else:
            ledger_preview = {
                "deployment_strategy": plan.strategy,
                "deployment_symbols": list(plan.symbols or []),
                "aurex_trade_count": 0,
                "aurex_net_pl": Decimal("0"),
                "aurex_fees": Decimal("0"),
                "aurex_slippage": Decimal("0"),
                "reconciliation_status": "NOT_READY",
                "reconciliation_discrepancies": [
                    {"reason": "broker_statement_csv_not_ready"}
                ],
                "reconciliation_next_action": broker_statement_preflight_next_action(
                    [{"reason": "broker_statement_csv_not_ready"}],
                ),
            }
        return {
            **preflight_broker_statement_csv(payload),
            **ledger_preview,
        }

    def reconcile_broker_statement_csv(
        self,
        payload: BrokerStatementCsvReconciliationRequest,
    ) -> LiveBrokerStatementReport:
        summary = summarize_broker_statement_csv(payload)
        report = self.reconcile_broker_statement(
            statement_payload_from_csv_summary(payload, summary)
        )
        report.statement_snapshot = {
            **report.statement_snapshot,
            "csv_required_headers": BROKER_STATEMENT_REQUIRED_HEADERS,
            "csv_row_results": summary.row_results,
            "csv_analysis_summary": summary.analysis_summary,
        }
        self.session.flush()
        return report

    def _broker_statement_reconciliation_preview(
        self,
        plan: LiveDeploymentPlan,
        payload: BrokerStatementReconciliationRequest,
    ) -> dict[str, object]:
        closed_trades = self._closed_trades_for_statement(
            plan,
            payload.statement_start_at,
            payload.statement_end_at,
        )
        aurex_trade_count = len(closed_trades)
        aurex_net_pl = sum(
            (trade.realized_pl or Decimal("0") for trade in closed_trades),
            Decimal("0"),
        )
        aurex_fees = sum((trade.fees or Decimal("0") for trade in closed_trades), Decimal("0"))
        aurex_slippage = sum(
            (trade.slippage or Decimal("0") for trade in closed_trades),
            Decimal("0"),
        )
        discrepancies = broker_statement_discrepancies(
            payload,
            aurex_trade_count=aurex_trade_count,
            aurex_net_pl=aurex_net_pl,
            aurex_fees=aurex_fees,
            aurex_slippage=aurex_slippage,
        )
        return {
            "deployment_strategy": plan.strategy,
            "deployment_symbols": list(plan.symbols or []),
            "aurex_trade_count": aurex_trade_count,
            "aurex_net_pl": aurex_net_pl,
            "aurex_fees": aurex_fees,
            "aurex_slippage": aurex_slippage,
            "reconciliation_status": "READY" if not discrepancies else "BLOCKED",
            "reconciliation_discrepancies": discrepancies,
            "reconciliation_next_action": broker_statement_preflight_next_action(
                discrepancies,
            ),
        }

    def list_broker_statement_reports(self) -> list[LiveBrokerStatementReport]:
        plan = self.get_or_create_default_plan()
        return list(
            self.session.execute(
                select(LiveBrokerStatementReport)
                .where(LiveBrokerStatementReport.live_deployment_plan_id == plan.id)
                .order_by(LiveBrokerStatementReport.reconciled_at.desc())
            ).scalars()
        )

    def latest_broker_statement_report(
        self,
        plan_id: str,
    ) -> LiveBrokerStatementReport | None:
        return self.session.execute(
            select(LiveBrokerStatementReport)
            .where(LiveBrokerStatementReport.live_deployment_plan_id == plan_id)
            .order_by(LiveBrokerStatementReport.reconciled_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _broker_statement_report_freshness_audit(
        self,
        plan: LiveDeploymentPlan,
        report: LiveBrokerStatementReport | None,
    ) -> dict[str, object]:
        if report is None:
            return {
                "status": ReadinessStatus.NOT_RUN,
                "freshness_reasons": ["broker_statement_report_missing"],
                "reviewed_ledger": {},
                "current_ledger": {},
            }

        reviewed_ledger = (report.aurex_snapshot or {}).get("ledger_snapshot")
        current_ledger = self._current_broker_statement_ledger_snapshot(plan, report)
        freshness_reasons = broker_statement_report_freshness_reasons(
            reviewed_ledger,
            current_ledger,
        )
        status = (
            ReadinessStatus.BLOCKED
            if report.status == ReadinessStatus.PASS and freshness_reasons
            else report.status
        )
        return {
            "status": status,
            "freshness_reasons": freshness_reasons,
            "reviewed_ledger": reviewed_ledger if isinstance(reviewed_ledger, dict) else {},
            "current_ledger": current_ledger,
        }

    def _current_broker_statement_ledger_snapshot(
        self,
        plan: LiveDeploymentPlan,
        report: LiveBrokerStatementReport,
    ) -> dict[str, object]:
        return broker_statement_ledger_snapshot(
            plan=plan,
            closed_trades=self._closed_trades_for_statement(
                plan,
                report.statement_start_at,
                report.statement_end_at,
            ),
            statement_start_at=report.statement_start_at,
            statement_end_at=report.statement_end_at,
        )

    def generate_profit_milestone_report(self) -> LiveProfitMilestoneReport:
        plan = self.get_or_create_default_plan()
        closed_trades = self._closed_trades_for_evidence(plan)
        total_net_pl = sum(
            (trade.realized_pl or Decimal("0") for trade in closed_trades),
            Decimal("0"),
        )
        first_trade_at = min(
            (trade.closed_at for trade in closed_trades if trade.closed_at),
            default=None,
        )
        latest_trade_at = max(
            (trade.closed_at for trade in closed_trades if trade.closed_at),
            default=None,
        )
        _, risk_profile = RiskEngine(self.session).get_or_create_default_profile()
        account = risk_profile.account
        integrity_audit = self._paper_evidence_integrity_audit(closed_trades)
        journal_audit = self._paper_evidence_journal_audit(closed_trades)
        loss_audit = profit_milestone_loss_audit(closed_trades, plan, account)
        broker_statement = self.latest_broker_statement_report(plan.id)
        broker_statement_audit = self._broker_statement_report_freshness_audit(
            plan,
            broker_statement,
        )
        connection = (
            self.session.get(BrokerConnection, plan.broker_connection_id)
            if plan.broker_connection_id
            else None
        )
        live_execution_audit = live_execution_adapter_audit(
            settings=self.settings,
            plan=plan,
            connection=connection,
        )
        reasons = profit_milestone_reasons(
            plan=plan,
            total_net_pl=total_net_pl,
            closed_trade_count=len(closed_trades),
            integrity_audit=integrity_audit,
            journal_audit=journal_audit,
            loss_audit=loss_audit,
            broker_statement=broker_statement,
            broker_statement_freshness_reasons=broker_statement_audit[
                "freshness_reasons"
            ],
            risk_kill_switch_enabled=risk_profile.kill_switch_enabled,
            live_execution_reasons=live_execution_audit.reasons,
        )
        report = LiveProfitMilestoneReport(
            live_deployment_plan=plan,
            status=ReadinessStatus.PASS if not reasons else ReadinessStatus.BLOCKED,
            target_net_profit=plan.target_net_profit,
            total_net_pl=total_net_pl,
            trade_count=len(closed_trades),
            first_trade_at=first_trade_at,
            latest_trade_at=latest_trade_at,
            journaled_trade_count=journal_audit["journaled_trade_count"],
            unjournaled_trade_count=journal_audit["unjournaled_trade_count"],
            journal_rule_violation_count=journal_audit["journal_rule_violation_count"],
            unexplained_trade_count=integrity_audit["unexplained_trade_count"],
            risk_rule_violation_count=integrity_audit["risk_rule_violation_count"],
            daily_loss_breach_count=loss_audit["daily_loss_breach_count"],
            weekly_loss_breach_count=loss_audit["weekly_loss_breach_count"],
            broker_statement_report=broker_statement,
            broker_statement_status=broker_statement.status if broker_statement else None,
            kill_switch_enabled=risk_profile.kill_switch_enabled,
            live_execution_adapter_implemented=live_execution_audit.implemented,
            reasons=reasons,
            requirements_snapshot={
                "target_net_profit": str(plan.target_net_profit),
                "net_realized_pl_after_fees_must_reach_target": True,
                "every_trade_requires_journal": True,
                "journal_rule_violation_count_must_be_zero": True,
                "unexplained_trade_count_must_be_zero": True,
                "risk_rule_violation_count_must_be_zero": True,
                "every_fill_must_be_evidence_grade": True,
                "execution_quality_violation_count_must_be_zero": True,
                "daily_loss_breach_count_must_be_zero": True,
                "weekly_loss_breach_count_must_be_zero": True,
                "broker_statement_reconciliation_must_pass": True,
                "kill_switch_must_be_clear": True,
                "live_execution_adapter_must_exist": True,
                "live_execution_adapter_gate_must_pass": True,
            },
            evidence_snapshot={
                "closed_trade_ids": [trade.id for trade in closed_trades],
                "first_trade_at": first_trade_at.isoformat() if first_trade_at else None,
                "latest_trade_at": latest_trade_at.isoformat() if latest_trade_at else None,
                "total_net_pl": str(total_net_pl),
                "target_net_profit": str(plan.target_net_profit),
                "broker_statement_report_id": (
                    broker_statement.id if broker_statement else None
                ),
                "broker_statement_status": (
                    broker_statement.status.value if broker_statement else None
                ),
                "broker_statement_freshness_reasons": broker_statement_audit[
                    "freshness_reasons"
                ],
                "broker_statement_current": broker_statement_current(
                    broker_statement,
                    closed_trade_count=len(closed_trades),
                    total_net_pl=total_net_pl,
                    freshness_reasons=broker_statement_audit["freshness_reasons"],
                ),
                "kill_switch_enabled": risk_profile.kill_switch_enabled,
                "live_execution_adapter_implemented": live_execution_audit.implemented,
                "live_execution_adapter": live_execution_audit.evidence_snapshot,
                **integrity_audit,
                **journal_audit,
                **loss_audit,
            },
            generated_at=utc_now(),
        )
        self.session.add(report)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "live_micro_deployment",
            "First profit milestone report generated",
            {"report_id": report.id, "status": report.status.value},
        )
        self.session.flush()
        return report

    def list_profit_milestone_reports(self) -> list[LiveProfitMilestoneReport]:
        plan = self.get_or_create_default_plan()
        return list(
            self.session.execute(
                select(LiveProfitMilestoneReport)
                .where(LiveProfitMilestoneReport.live_deployment_plan_id == plan.id)
                .order_by(LiveProfitMilestoneReport.generated_at.desc())
            ).scalars()
        )

    def latest_profit_milestone_report(
        self,
        plan_id: str,
    ) -> LiveProfitMilestoneReport | None:
        return self.session.execute(
            select(LiveProfitMilestoneReport)
            .where(LiveProfitMilestoneReport.live_deployment_plan_id == plan_id)
            .order_by(LiveProfitMilestoneReport.generated_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def generate_strategy_evidence_review(self) -> StrategyEvidenceReview:
        plan = self.get_or_create_default_plan()
        gates = self.run_gates(plan)
        latest_backtest = self.latest_accepted_backtest(plan)
        latest_paper_evidence = self.latest_paper_evidence_report(plan.id)
        latest_broker_statement = self.latest_broker_statement_report(plan.id)
        latest_profit_milestone = self.latest_profit_milestone_report(plan.id)
        decision, reasons, next_actions, summary = strategy_evidence_review_outcome(
            gates=gates,
            live_trading_enabled=self.settings.live_trading_enabled,
            latest_paper_evidence=latest_paper_evidence,
        )
        review = StrategyEvidenceReview(
            live_deployment_plan=plan,
            decision=decision,
            strategy=plan.strategy,
            symbols=list(plan.symbols or []),
            summary=summary,
            reasons=reasons,
            next_actions=next_actions,
            gate_snapshot=strategy_evidence_gate_snapshot(gates),
            evidence_snapshot={
                "live_trading_enabled": self.settings.live_trading_enabled,
                "activation_allowed": self._activation_allowed(gates),
                "deployment_plan_snapshot": strategy_review_plan_snapshot(plan),
                "latest_accepted_backtest_run_id": (
                    latest_backtest.id if latest_backtest else None
                ),
                "latest_paper_evidence_report_id": (
                    latest_paper_evidence.id if latest_paper_evidence else None
                ),
                "latest_paper_evidence_status": (
                    latest_paper_evidence.status.value if latest_paper_evidence else None
                ),
                "latest_paper_evidence_reasons": (
                    latest_paper_evidence.reasons if latest_paper_evidence else []
                ),
                "latest_broker_statement_report_id": (
                    latest_broker_statement.id if latest_broker_statement else None
                ),
                "latest_broker_statement_status": (
                    latest_broker_statement.status.value if latest_broker_statement else None
                ),
                "latest_broker_statement_discrepancies": (
                    latest_broker_statement.discrepancies
                    if latest_broker_statement
                    else []
                ),
                "latest_profit_milestone_report_id": (
                    latest_profit_milestone.id if latest_profit_milestone else None
                ),
                "latest_profit_milestone_status": (
                    latest_profit_milestone.status.value if latest_profit_milestone else None
                ),
                "latest_profit_milestone_reasons": (
                    latest_profit_milestone.reasons if latest_profit_milestone else []
                ),
            },
            reviewed_at=utc_now(),
        )
        self.session.add(review)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "strategy_evidence_review",
            "Strategy evidence review generated",
            {
                "review_id": review.id,
                "decision": review.decision.value,
                "strategy": review.strategy,
                "symbols": review.symbols,
            },
        )
        self.session.flush()
        return review

    def list_strategy_evidence_reviews(self) -> list[StrategyEvidenceReview]:
        plan = self.get_or_create_default_plan()
        return list(
            self.session.execute(
                select(StrategyEvidenceReview)
                .where(StrategyEvidenceReview.live_deployment_plan_id == plan.id)
                .order_by(StrategyEvidenceReview.reviewed_at.desc())
            ).scalars()
        )

    def latest_strategy_evidence_review(
        self,
        plan: LiveDeploymentPlan,
    ) -> StrategyEvidenceReview | None:
        plan_symbols = {symbol.upper() for symbol in plan.symbols or []}
        reviews = self.session.execute(
            select(StrategyEvidenceReview)
            .where(StrategyEvidenceReview.strategy == plan.strategy)
            .order_by(StrategyEvidenceReview.reviewed_at.desc())
        ).scalars()
        for review in reviews:
            review_symbols = {symbol.upper() for symbol in review.symbols or []}
            if plan_symbols and not plan_symbols.issubset(review_symbols):
                continue
            return review
        return None

    def list_daily_reviews(self) -> list[LiveDailyReviewReport]:
        plan = self.get_or_create_default_plan()
        return list(
            self.session.execute(
                select(LiveDailyReviewReport)
                .where(LiveDailyReviewReport.live_deployment_plan_id == plan.id)
                .order_by(LiveDailyReviewReport.review_date.desc())
            ).scalars()
        )

    def latest_daily_review(self, plan_id: str) -> LiveDailyReviewReport | None:
        return self.session.execute(
            select(LiveDailyReviewReport)
            .where(LiveDailyReviewReport.live_deployment_plan_id == plan_id)
            .order_by(LiveDailyReviewReport.review_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def activation_attempt(self) -> LiveActivationAttemptResponse:
        status = self.deployment_status()
        blocking_gates = [
            gate for gate in status.gates if gate.required and gate.status != ReadinessStatus.PASS
        ]
        blocking_gate_keys = [gate.gate_key for gate in blocking_gates]
        blocking_gate_summaries = [
            activation_blocking_gate_summary(gate) for gate in blocking_gates
        ]
        next_actions = activation_next_actions(blocking_gate_summaries)
        message = (
            "Activation remains blocked; no live broker execution was attempted."
            if blocking_gate_keys or not self.settings.live_trading_enabled
            else (
                "Activation gates are clear, but no live execution adapter is implemented "
                "in this stage."
            )
        )
        SystemEventRecorder(self.session).warning(
            "live_micro_deployment",
            "Live activation attempt audited",
            {
                "activation_allowed": False,
                "blocking_gate_keys": blocking_gate_keys,
                "next_actions": next_actions,
                "live_trading_enabled": self.settings.live_trading_enabled,
            },
        )
        self.session.flush()
        return LiveActivationAttemptResponse(
            activation_allowed=False,
            live_trading_enabled=self.settings.live_trading_enabled,
            status=LiveDeploymentStatus.BLOCKED,
            blocking_gate_keys=blocking_gate_keys,
            blocking_gates=blocking_gate_summaries,
            next_actions=next_actions,
            message=message,
        )

    def _activation_allowed(self, gates: list[LiveDeploymentGate]) -> bool:
        required_passed = all(
            gate.status == ReadinessStatus.PASS for gate in gates if gate.required
        )
        return bool(required_passed and self.settings.live_trading_enabled)

    def _closed_trades_for_date(self, review_date: date) -> list[PaperTrade]:
        start = datetime.combine(review_date, datetime.min.time(), tzinfo=UTC)
        end = datetime.combine(review_date, datetime.max.time(), tzinfo=UTC)
        return list(
            self.session.execute(
                select(PaperTrade).where(
                    PaperTrade.status == TradeStatus.CLOSED,
                    PaperTrade.closed_at >= start,
                    PaperTrade.closed_at <= end,
                )
            ).scalars()
        )

    def _closed_trades_since(self, since: datetime) -> list[PaperTrade]:
        return list(
            self.session.execute(
                select(PaperTrade).where(
                    PaperTrade.status == TradeStatus.CLOSED,
                    PaperTrade.closed_at >= since,
                    PaperTrade.realized_pl.is_not(None),
                )
            ).scalars()
        )

    def _latest_closed_trades(self) -> list[PaperTrade]:
        return list(
            self.session.execute(
                select(PaperTrade)
                .where(
                    PaperTrade.status == TradeStatus.CLOSED,
                    PaperTrade.closed_at.is_not(None),
                    PaperTrade.realized_pl.is_not(None),
                )
                .order_by(PaperTrade.closed_at.desc())
            ).scalars()
        )

    def _all_closed_trades_for_evidence(self) -> list[PaperTrade]:
        return list(
            self.session.execute(
                select(PaperTrade)
                .where(
                    PaperTrade.status == TradeStatus.CLOSED,
                    PaperTrade.realized_pl.is_not(None),
                )
                .order_by(PaperTrade.closed_at.asc())
            ).scalars()
        )

    def _closed_trades_for_evidence(self, plan: LiveDeploymentPlan) -> list[PaperTrade]:
        query = (
            select(PaperTrade)
            .where(
                PaperTrade.status == TradeStatus.CLOSED,
                PaperTrade.realized_pl.is_not(None),
                PaperTrade.strategy == plan.strategy,
            )
            .order_by(PaperTrade.closed_at.asc())
        )
        symbols = list(plan.symbols or [])
        if symbols:
            query = query.where(PaperTrade.symbol.in_(symbols))
        return list(self.session.execute(query).scalars())

    def _closed_trades_for_statement(
        self,
        plan: LiveDeploymentPlan,
        statement_start_at: datetime | None,
        statement_end_at: datetime | None,
    ) -> list[PaperTrade]:
        if (
            statement_start_at is not None
            and statement_end_at is not None
            and statement_start_at > statement_end_at
        ):
            return []
        query = select(PaperTrade).where(
            PaperTrade.status == TradeStatus.CLOSED,
            PaperTrade.realized_pl.is_not(None),
            PaperTrade.strategy == plan.strategy,
        )
        symbols = list(plan.symbols or [])
        if symbols:
            query = query.where(PaperTrade.symbol.in_(symbols))
        if statement_start_at is not None:
            query = query.where(PaperTrade.closed_at >= statement_start_at)
        if statement_end_at is not None:
            query = query.where(PaperTrade.closed_at <= statement_end_at)
        return list(self.session.execute(query.order_by(PaperTrade.closed_at.asc())).scalars())

    def _paper_evidence_integrity_audit(
        self,
        closed_trades: list[PaperTrade],
    ) -> dict[str, object]:
        trade_ids = [trade.id for trade in closed_trades]
        if not trade_ids:
            return {
                "unexplained_trade_count": 0,
                "risk_rule_violation_count": 0,
                "evidence_grade_trade_count": 0,
                "non_evidence_grade_trade_count": 0,
                "execution_quality_violation_count": 0,
                "fill_model_counts": {},
                "unexplained_trades": [],
                "risk_rule_violations": [],
                "execution_quality_violations": [],
            }

        rows = self.session.execute(
            select(PaperTrade, PaperOrder, RiskDecision, Signal)
            .outerjoin(PaperOrder, PaperTrade.paper_order_id == PaperOrder.id)
            .outerjoin(RiskDecision, PaperOrder.risk_decision_id == RiskDecision.id)
            .outerjoin(Signal, PaperOrder.signal_id == Signal.id)
            .where(PaperTrade.id.in_(trade_ids))
        ).all()
        journal_rows = list(
            self.session.execute(
                select(TradeJournalEntry)
                .where(TradeJournalEntry.paper_trade_id.in_(trade_ids))
                .order_by(
                    TradeJournalEntry.journaled_at.asc(),
                    TradeJournalEntry.id.asc(),
                )
            ).scalars()
        )
        imported_journals_by_trade: dict[str, TradeJournalEntry] = {}
        for entry in journal_rows:
            snapshot = (
                entry.evidence_snapshot
                if isinstance(entry.evidence_snapshot, dict)
                else {}
            )
            if snapshot.get("source") == "paper_evidence_import":
                imported_journals_by_trade.setdefault(entry.paper_trade_id, entry)

        unexplained: list[dict[str, object]] = []
        risk_violations: list[dict[str, object]] = []
        execution_quality_violations: list[dict[str, object]] = []
        fill_model_counts: dict[str, int] = {}
        evidence_grade_trade_count = 0

        for trade, order, decision, signal in rows:
            if order is None:
                unexplained.append(
                    {
                        "trade_id": trade.id,
                        "reason": "missing_paper_order",
                    }
                )
                execution_quality_violations.append(
                    {
                        "trade_id": trade.id,
                        "reason": "paper_execution_order_missing",
                    }
                )
                continue

            fill_model_counts[order.fill_model] = (
                fill_model_counts.get(order.fill_model, 0) + 1
            )

            missing = []
            if decision is None:
                missing.append("risk_decision")
            if signal is None:
                missing.append("signal")
            if missing:
                unexplained.append(
                    {
                        "trade_id": trade.id,
                        "reason": f"missing_{'_'.join(missing)}",
                    }
                )
                execution_quality_violations.append(
                    {
                        "trade_id": trade.id,
                        "fill_model": order.fill_model,
                        "reason": "paper_execution_lineage_missing",
                    }
                )
                continue

            if not decision.approved:
                risk_violations.append(
                    {
                        "trade_id": trade.id,
                        "reason": "risk_decision_not_approved",
                    }
                )
            if decision.risk_amount is None or trade.risk_amount > decision.risk_amount:
                risk_violations.append(
                    {
                        "trade_id": trade.id,
                        "reason": "trade_risk_exceeds_approved_risk",
                    }
                )
            if decision.position_size is None or trade.quantity > decision.position_size:
                risk_violations.append(
                    {
                        "trade_id": trade.id,
                        "reason": "trade_quantity_exceeds_approved_size",
                    }
                )
            stop_risk_amount = calculate_stop_risk_amount(
                trade.entry_price,
                trade.stop_loss,
                trade.quantity,
            )
            if abs(trade.risk_amount - stop_risk_amount) > RISK_TOLERANCE:
                risk_violations.append(
                    {
                        "trade_id": trade.id,
                        "reason": "trade_risk_amount_does_not_match_stop_distance",
                    }
                )
            import_violation = imported_trade_evidence_violation(
                trade=trade,
                order=order,
                decision=decision,
                signal=signal,
                journal=imported_journals_by_trade.get(trade.id),
            )
            if import_violation is not None:
                risk_violations.append(import_violation)
            execution_violation = paper_execution_quality_violation(
                trade=trade,
                order=order,
                signal=signal,
                import_violation=import_violation,
            )
            if execution_violation is None:
                evidence_grade_trade_count += 1
            else:
                execution_quality_violations.append(execution_violation)

        return {
            "unexplained_trade_count": len(unexplained),
            "risk_rule_violation_count": len(risk_violations),
            "evidence_grade_trade_count": evidence_grade_trade_count,
            "non_evidence_grade_trade_count": (
                len(closed_trades) - evidence_grade_trade_count
            ),
            "execution_quality_violation_count": len(
                execution_quality_violations
            ),
            "fill_model_counts": dict(sorted(fill_model_counts.items())),
            "unexplained_trades": unexplained[:10],
            "risk_rule_violations": risk_violations[:10],
            "execution_quality_violations": execution_quality_violations[:10],
        }

    def _paper_evidence_journal_audit(
        self,
        closed_trades: list[PaperTrade],
    ) -> dict[str, object]:
        trade_ids = [trade.id for trade in closed_trades]
        if not trade_ids:
            return {
                "journaled_trade_count": 0,
                "unjournaled_trade_count": 0,
                "journal_rule_violation_count": 0,
                "unjournaled_trades": [],
                "journal_rule_violations": [],
            }

        entries = list(
            self.session.execute(
                select(TradeJournalEntry).where(
                    TradeJournalEntry.paper_trade_id.in_(trade_ids)
                )
            ).scalars()
        )
        entries_by_trade: dict[str, list[TradeJournalEntry]] = {}
        for entry in entries:
            entries_by_trade.setdefault(entry.paper_trade_id, []).append(entry)

        unjournaled: list[dict[str, str]] = []
        journal_violations: list[dict[str, str]] = []
        for trade in closed_trades:
            trade_entries = entries_by_trade.get(trade.id, [])
            if not trade_entries:
                unjournaled.append(
                    {
                        "trade_id": trade.id,
                        "reason": "missing_trade_journal",
                    }
                )
                continue

            if any(not entry.rule_followed for entry in trade_entries):
                journal_violations.append(
                    {
                        "trade_id": trade.id,
                        "reason": "journal_reports_rule_break",
                    }
                )
            if any(entry.emotional_override for entry in trade_entries):
                journal_violations.append(
                    {
                        "trade_id": trade.id,
                        "reason": "journal_reports_emotional_override",
                    }
                )

        return {
            "journaled_trade_count": len(trade_ids) - len(unjournaled),
            "unjournaled_trade_count": len(unjournaled),
            "journal_rule_violation_count": len(journal_violations),
            "unjournaled_trades": unjournaled[:10],
            "journal_rule_violations": journal_violations[:10],
        }

    def _get_or_create_review_account(self, payload: LiveApprovalPacketRequest) -> Account:
        name = f"live-review:{payload.broker_name.strip()}:{payload.account_label.strip()}"
        account = self.session.execute(
            select(Account).where(Account.name == name)
        ).scalar_one_or_none()
        if account is not None:
            return account
        account = Account(
            name=name,
            mode="live-review",
            currency=payload.currency.strip().upper(),
            starting_equity=Decimal("0"),
            current_equity=Decimal("0"),
            is_active=True,
        )
        self.session.add(account)
        self.session.flush()
        return account

    def _get_or_create_review_connection(
        self,
        payload: LiveApprovalPacketRequest,
    ) -> BrokerConnection:
        broker_name = payload.broker_name.strip()
        account_label = payload.account_label.strip()
        connection = self.session.execute(
            select(BrokerConnection).where(
                BrokerConnection.broker_name == broker_name,
                BrokerConnection.environment == BrokerEnvironment.LIVE,
                BrokerConnection.account_label == account_label,
            )
        ).scalar_one_or_none()
        if connection is not None:
            return connection
        connection = BrokerConnection(
            broker_name=broker_name,
            environment=BrokerEnvironment.LIVE,
            account_label=account_label,
            status=BrokerConnectionStatus.CONFIGURED,
            live_trading_enabled=False,
            capabilities={
                "review_only": True,
                "credentials_stored": False,
                "asset_class": payload.asset_class.strip(),
                "jurisdiction": payload.jurisdiction.strip(),
                "account_constraints_reference": payload.account_constraints_reference,
                "execution_policy_reference": payload.execution_policy_reference,
                "fee_slippage_model_reference": payload.fee_slippage_model_reference,
                "paper_to_live_checklist_reference": (
                    payload.paper_to_live_checklist_reference
                ),
                "sandbox_test_reference": payload.sandbox_test_reference,
                "leverage_allowed": payload.leverage_allowed,
            },
            last_heartbeat_at=None,
            is_active=True,
        )
        self.session.add(connection)
        self.session.flush()
        return connection

    def _sync_approval_snapshot(self, plan: LiveDeploymentPlan) -> None:
        now = utc_now()
        records = list(
            self.session.execute(
                select(LiveApprovalRecord)
                .where(LiveApprovalRecord.live_deployment_plan_id == plan.id)
                .order_by(LiveApprovalRecord.created_at.asc())
            ).scalars()
        )
        latest_by_type: dict[LiveApprovalType, LiveApprovalRecord] = {}
        for record in records:
            latest_by_type[record.approval_type] = record

        snapshot: dict[str, object] = {}
        for approval_type in LiveApprovalType:
            record = latest_by_type.get(approval_type)
            is_current = (
                record is not None
                and record.status == LiveApprovalStatus.APPROVED
                and (record.expires_at is None or record.expires_at > now)
            )
            key = approval_snapshot_key(approval_type)
            snapshot[key] = is_current
            snapshot[f"{approval_type.value.lower()}_approval_record_id"] = (
                record.id if record else None
            )
            snapshot[f"{approval_type.value.lower()}_approval_status"] = (
                record.status.value if record else LiveApprovalStatus.PENDING.value
            )
        plan.approval_snapshot = snapshot

    def _upsert_gate(
        self,
        plan: LiveDeploymentPlan,
        gate_key: str,
        name: str,
        status: ReadinessStatus,
        evidence_snapshot: dict,
        notes: str,
        required: bool = True,
    ) -> LiveDeploymentGate:
        gate = self.session.execute(
            select(LiveDeploymentGate).where(
                LiveDeploymentGate.live_deployment_plan_id == plan.id,
                LiveDeploymentGate.gate_key == gate_key,
            )
        ).scalar_one_or_none()
        if gate is None:
            gate = LiveDeploymentGate(live_deployment_plan=plan, gate_key=gate_key, name=name)
            self.session.add(gate)
        gate.name = name
        gate.status = status
        gate.required = required
        gate.evidence_snapshot = evidence_snapshot
        gate.notes = notes
        gate.last_checked_at = utc_now()
        return gate

    def _rules_snapshot(self) -> dict[str, object]:
        return {
            "stage": "Stage 14",
            "max_risk_per_trade": str(MAX_MICRO_RISK_PER_TRADE),
            "max_daily_loss": str(MAX_MICRO_DAILY_LOSS),
            "max_weekly_loss": str(MAX_MICRO_WEEKLY_LOSS),
            "max_open_positions": 3,
            "target_net_profit": str(DEFAULT_TARGET_PROFIT),
            "minimum_paper_trades": MIN_PAPER_TRADES,
            "minimum_paper_calendar_days": MIN_PAPER_CALENDAR_DAYS,
            "live_broker_execution_implemented": False,
        }


def activation_blocking_gate_summary(gate: object) -> dict[str, object]:
    evidence = getattr(gate, "evidence_snapshot", None)
    evidence = evidence if isinstance(evidence, dict) else {}
    reasons = activation_gate_reasons(evidence)
    next_action = activation_gate_next_action(gate, evidence, reasons)
    return {
        "gate_key": getattr(gate, "gate_key", None),
        "name": getattr(gate, "name", None),
        "status": readiness_status_value(getattr(gate, "status", None)),
        "reason": reasons[0] if reasons else None,
        "reasons": reasons[:5],
        "next_action": next_action,
    }


def activation_gate_reasons(evidence: dict[str, object]) -> list[str]:
    for key in (
        "freshness_reasons",
        "stale_reasons",
        "reasons",
        "live_readiness_reasons",
        "blockers",
    ):
        values = evidence.get(key)
        if isinstance(values, list) and values:
            return [str(value) for value in values if value is not None]
    current_check = evidence.get("current_check")
    if isinstance(current_check, dict) and current_check.get("key"):
        return [str(current_check["key"])]
    return []


def activation_gate_next_action(
    gate: object,
    evidence: dict[str, object],
    reasons: list[str],
) -> str:
    gate_key = str(getattr(gate, "gate_key", "") or "")
    next_action = evidence.get("next_action")
    if isinstance(next_action, str) and next_action.strip():
        return next_action
    next_actions = evidence.get("next_actions")
    if isinstance(next_actions, list) and next_actions:
        return str(next_actions[0])
    if gate_key == "live_trading_disabled":
        return "Keep live trading disabled until all evidence, approval, and adapter gates pass."
    if gate_key == "live_execution_adapter_ready":
        return (
            "Implement, configure, and audit a live execution adapter before any "
            "activation attempt."
        )
    if gate_key == "explicit_user_approval":
        if reasons:
            reason = activation_reason_label(reasons[0])
            return f"Refresh manual approvals after resolving {reason}."
        return (
            "Record broker, account, jurisdiction, and live-execution approvals for "
            "the current evidence context."
        )
    if gate_key == "strategy_evidence_review_clear":
        return "Run a fresh strategy evidence review after all required evidence gates pass."
    if gate_key == "accepted_backtest_complete":
        return "Store a strict accepted backtest for the selected strategy and symbols."
    if gate_key == "paper_evidence_complete":
        return (
            "Import or generate current paper evidence that passes trade count, "
            "duration, risk, and journal gates."
        )
    if gate_key == "prediction_demo_campaign_quality":
        return "Complete the selected-strategy prediction paper/demo campaign quality gate."
    if gate_key == "broker_statement_reconciliation":
        return "Reconcile a current broker or paper statement against Aurex closed-trade records."
    if gate_key == "broker_account_selected":
        return "Submit a complete no-credentials, no-leverage broker/account approval packet."
    if gate_key == "daily_review_ready":
        return "Record a clean daily review before any activation attempt."
    if gate_key == "kill_switch_clear":
        return "Reset the risk kill switch before activation can proceed."
    if gate_key == "mkt_donor_credential_boundary":
        return "Remove production MKT credential material or use a clean scoped demo donor profile."
    if gate_key == "tiny_risk_limits":
        return "Reduce configured risk to the micro-live limits."
    return f"Resolve {str(getattr(gate, 'name', gate_key) or gate_key)} before activation."


def activation_next_actions(blocking_gate_summaries: list[dict[str, object]]) -> list[str]:
    actions: list[str] = []
    for summary in blocking_gate_summaries:
        action = str(summary.get("next_action") or "").strip()
        if action and action not in actions:
            actions.append(action)
    return actions


def activation_reason_label(reason: str) -> str:
    return reason.replace("_", " ")


def normalized_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    for symbol in symbols:
        candidate = symbol.strip().upper()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def approval_packet_reasons(payload: LiveApprovalPacketRequest) -> list[str]:
    reasons: list[str] = []
    if payload.credentials_stored:
        reasons.append("credentials_stored")
    if payload.leverage_allowed:
        reasons.append("leverage_not_allowed_for_micro_deployment")
    return reasons


def symbol_scope_status(symbols: list | None) -> ReadinessStatus:
    count = len(symbols or [])
    if 1 <= count <= 3:
        return ReadinessStatus.PASS
    return ReadinessStatus.FAIL


def tiny_risk_status(plan: LiveDeploymentPlan) -> ReadinessStatus:
    if (
        Decimal("0") < plan.risk_per_trade <= MAX_MICRO_RISK_PER_TRADE
        and Decimal("0") < plan.max_daily_loss <= MAX_MICRO_DAILY_LOSS
        and Decimal("0") < plan.max_weekly_loss <= MAX_MICRO_WEEKLY_LOSS
        and 1 <= plan.max_open_positions <= 3
    ):
        return ReadinessStatus.PASS
    return ReadinessStatus.FAIL


def mkt_strategy_requires_donor_boundary(strategy: str) -> bool:
    return strategy.lower().startswith("mkt_")


def mkt_donor_credential_boundary_audit(strategy: str) -> dict[str, object]:
    required = mkt_strategy_requires_donor_boundary(strategy)
    root = Path("My-Krypt-Trader")
    credential_dirs = mkt_donor_credential_dir_snapshots(root)
    production_material = [
        item
        for directory in credential_dirs
        for item in directory["credentials"]
        if item["env"] == "production" and item["credential_material_present"]
    ]
    demo_pairs = [
        item
        for directory in credential_dirs
        for item in directory["credentials"]
        if item["env"] == "demo" and item["credential_pair_present"]
    ]

    if not required:
        return {
            "status": ReadinessStatus.PASS,
            "required_for_strategy": False,
            "strategy": strategy,
            "reason": "mkt_donor_credentials_not_required_for_non_mkt_strategy",
            "mkt_root": str(root),
            "credential_dirs": credential_dirs,
            "production_credential_material_present": bool(production_material),
            "demo_credential_pair_present": bool(demo_pairs),
            "contents_read": False,
            "reasons": [],
            "next_action": "No MKT donor credential boundary is required for this strategy.",
        }

    if production_material:
        status = ReadinessStatus.FAIL
        reasons = ["mkt_production_credential_material_present"]
        next_action = (
            "Remove production MKT credentials from the donor runtime profile or switch "
            "collection to a clean scoped demo userData path before any live-readiness review."
        )
    else:
        status = ReadinessStatus.PASS
        reasons = []
        next_action = (
            "MKT donor credential boundary is clean; continue demo-only donor collection "
            "and keep Aurex live execution disabled."
        )

    return {
        "status": status,
        "required_for_strategy": True,
        "strategy": strategy,
        "mkt_root": str(root),
        "credential_dirs": credential_dirs,
        "inspected_credential_dir_count": len(credential_dirs),
        "production_credential_material_present": bool(production_material),
        "production_credential_material_count": len(production_material),
        "demo_credential_pair_present": bool(demo_pairs),
        "contents_read": False,
        "reasons": reasons,
        "next_action": next_action,
    }


def mkt_donor_credential_dir_snapshots(root: Path) -> list[dict[str, object]]:
    snapshots = []
    seen: set[str] = set()
    for key, path, source in mkt_donor_credential_dir_candidates(root):
        normalized = normalized_path_key(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        snapshots.append(
            {
                "key": key,
                "path": str(path),
                "source": source,
                "exists": safe_path_is_dir(path),
                "credentials": [
                    mkt_donor_credential_file_snapshot(path, env)
                    for env in ("demo", "production")
                ],
            }
        )
    return snapshots


def mkt_donor_credential_dir_candidates(root: Path) -> list[tuple[str, Path, str]]:
    candidates: list[tuple[str, Path, str]] = []
    userdata = os.environ.get("KRYPT_TRADER_USERDATA")
    if userdata:
        candidates.append(
            (
                "krypt_trader_userdata_credentials",
                Path(userdata).expanduser() / "credentials",
                "KRYPT_TRADER_USERDATA",
            ),
        )
    candidates.extend(
        [
            (
                "aurex_demo_userdata_credentials",
                root / ".aurex-demo-userdata" / "credentials",
                "Aurex scoped demo userData",
            ),
            (
                "mkt_python_credentials",
                root / "python" / "credentials",
                "My-Krypt-Trader Python fallback",
            ),
        ],
    )
    return candidates


def mkt_donor_credential_file_snapshot(credentials_dir: Path, env: str) -> dict[str, object]:
    api_key_path = credentials_dir / f"apikey.{env}.txt"
    rsa_key_path = credentials_dir / f"rsakey.{env}.pem"
    api_key_exists = safe_path_is_file(api_key_path)
    rsa_key_exists = safe_path_is_file(rsa_key_path)
    return {
        "env": env,
        "api_key_path": str(api_key_path),
        "rsa_key_path": str(rsa_key_path),
        "api_key_file_present": api_key_exists,
        "rsa_key_file_present": rsa_key_exists,
        "credential_pair_present": api_key_exists and rsa_key_exists,
        "credential_material_present": api_key_exists or rsa_key_exists,
        "contents_read": False,
    }


def safe_path_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def safe_path_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def normalized_path_key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path).lower()


def prediction_demo_campaign_gate_audit(
    session: Session,
    strategy: str,
) -> dict[str, object]:
    required = strategy.lower().startswith("mkt_")
    if not required:
        return {
            "status": ReadinessStatus.PASS,
            "required_for_strategy": False,
            "strategy": strategy,
            "reason": "prediction_demo_campaign_not_required_for_non_mkt_strategy",
            "ready_for_live_review": True,
            "reasons": [],
        }

    from aurex.api.routes.prediction_market import (
        build_prediction_paper_demo_batch_audit,
        build_prediction_paper_demo_campaign_audit,
        build_prediction_paper_demo_progress,
    )

    progress = build_prediction_paper_demo_progress(session, strategy=strategy)
    failed_checks = [
        str(check["key"]) for check in progress.checks if not bool(check.get("passed"))
    ]
    campaign_audit = build_prediction_paper_demo_campaign_audit(session, limit=5)
    batch_audit = build_prediction_paper_demo_batch_audit(session, limit=5)
    latest_campaign_record = (
        campaign_audit.records[0] if campaign_audit.records else None
    )
    latest_batch_record = batch_audit.records[0] if batch_audit.records else None
    strategy_campaign_records = prediction_demo_strategy_audit_records(
        campaign_audit.records,
        strategy,
    )
    strategy_batch_records = prediction_demo_strategy_audit_records(
        batch_audit.records,
        strategy,
    )
    latest_strategy_campaign_record = (
        strategy_campaign_records[0] if strategy_campaign_records else None
    )
    latest_strategy_batch_record = (
        strategy_batch_records[0] if strategy_batch_records else None
    )
    audit_reasons = prediction_demo_campaign_gate_audit_reasons(
        campaign_audit,
        batch_audit,
        strategy_campaign_records,
        strategy_batch_records,
    )
    ready_for_live_review = bool(progress.ready_for_live_review and not audit_reasons)
    if progress.raw_closed_records == 0 and campaign_audit.record_count == 0:
        status = ReadinessStatus.NOT_RUN
    elif ready_for_live_review:
        status = ReadinessStatus.PASS
    else:
        status = ReadinessStatus.BLOCKED
    reasons = sorted(set([*failed_checks, *audit_reasons]))
    if "prediction_demo_campaign_strategy_evidence_missing" in audit_reasons:
        next_action = (
            "Run a guarded MKT DB campaign replay for the selected strategy before "
            "live review."
        )
    elif audit_reasons and any(
        reason.startswith("prediction_demo_campaign_") for reason in audit_reasons
    ):
        next_action = campaign_audit.next_action
    elif (
        audit_reasons
        and "prediction_demo_batch_current_result_drifted" in audit_reasons
    ):
        next_action = batch_audit.next_action
    else:
        next_action = progress.next_action

    return {
        "status": status,
        "required_for_strategy": True,
        "strategy": strategy,
        "ready_for_live_review": ready_for_live_review,
        "progress_ready_for_live_review": progress.ready_for_live_review,
        "progress_status": progress.status,
        "current_check": progress.current_check,
        "completed_check_count": progress.completed_check_count,
        "total_check_count": progress.total_check_count,
        "progress_pct": progress.progress_pct,
        "raw_closed_records": progress.raw_closed_records,
        "closed_records": progress.closed_records,
        "target_closed_records": progress.target_closed_records,
        "remaining_records": progress.remaining_records,
        "calendar_days": progress.calendar_days,
        "target_calendar_days": progress.target_calendar_days,
        "remaining_calendar_days": progress.remaining_calendar_days,
        "active_days": progress.active_days,
        "target_active_days": progress.target_active_days,
        "remaining_active_days": progress.remaining_active_days,
        "unique_contracts": progress.unique_contracts,
        "target_unique_contracts": progress.target_unique_contracts,
        "remaining_unique_contracts": progress.remaining_unique_contracts,
        "fee_net_realized_pl": str(progress.fee_net_realized_pl),
        "expectancy": str(progress.expectancy),
        "profit_factor": (
            str(progress.profit_factor) if progress.profit_factor is not None else None
        ),
        "max_drawdown": str(progress.max_drawdown),
        "winning_records": progress.winning_records,
        "losing_records": progress.losing_records,
        "breakeven_records": progress.breakeven_records,
        "countable_ledger_records": progress.countable_ledger_records,
        "ledger_blocked_records": progress.ledger_blocked_records,
        "provenance_complete_records": progress.provenance_complete_records,
        "provenance_missing_records": progress.provenance_missing_records,
        "max_single_day_records": progress.max_single_day_records,
        "max_single_day_record_share": str(progress.max_single_day_record_share),
        "max_single_contract_records": progress.max_single_contract_records,
        "max_single_contract_record_share": str(
            progress.max_single_contract_record_share
        ),
        "first_closed_at": (
            progress.first_closed_at.isoformat() if progress.first_closed_at else None
        ),
        "latest_closed_at": (
            progress.latest_closed_at.isoformat() if progress.latest_closed_at else None
        ),
        "latest_reconciliation_status": (
            progress.latest_reconciliation_status.value
            if progress.latest_reconciliation_status
            else None
        ),
        "campaign_audit_records": campaign_audit.record_count,
        "campaign_acknowledged_records": campaign_audit.acknowledged_records,
        "campaign_side_sensitive_records": campaign_audit.side_sensitive_records,
        "campaign_current_result_clean_records": (
            campaign_audit.current_result_clean_records
        ),
        "campaign_current_result_drifted_records": (
            campaign_audit.current_result_drifted_records
        ),
        "campaign_latest_evidence_hash": campaign_audit.latest_evidence_hash,
        "campaign_next_action": campaign_audit.next_action,
        "latest_campaign_record": prediction_demo_audit_record_snapshot(
            latest_campaign_record
        ),
        "strategy_campaign_audit_records": len(strategy_campaign_records),
        "strategy_campaign_current_result_clean_records": (
            prediction_demo_clean_audit_record_count(strategy_campaign_records)
        ),
        "strategy_campaign_current_result_drifted_records": (
            prediction_demo_drifted_audit_record_count(strategy_campaign_records)
        ),
        "latest_strategy_campaign_record": prediction_demo_audit_record_snapshot(
            latest_strategy_campaign_record
        ),
        "batch_audit_records": batch_audit.record_count,
        "batch_current_result_clean_records": batch_audit.current_result_clean_records,
        "batch_current_result_drifted_records": (
            batch_audit.current_result_drifted_records
        ),
        "batch_latest_evidence_hash": batch_audit.latest_evidence_hash,
        "batch_next_action": batch_audit.next_action,
        "latest_batch_record": prediction_demo_audit_record_snapshot(latest_batch_record),
        "strategy_batch_audit_records": len(strategy_batch_records),
        "strategy_batch_current_result_clean_records": (
            prediction_demo_clean_audit_record_count(strategy_batch_records)
        ),
        "strategy_batch_current_result_drifted_records": (
            prediction_demo_drifted_audit_record_count(strategy_batch_records)
        ),
        "latest_strategy_batch_record": prediction_demo_audit_record_snapshot(
            latest_strategy_batch_record
        ),
        "reasons": reasons,
        "next_action": next_action,
        "live_execution_enabled": progress.live_execution_enabled,
    }


def prediction_demo_strategy_audit_records(
    records: list[object],
    strategy: str,
) -> list[object]:
    return [record for record in records if getattr(record, "strategy", None) == strategy]


def prediction_demo_clean_audit_record_count(records: list[object]) -> int:
    return sum(
        1
        for record in records
        if getattr(record, "current_result_ledger_status", None)
        == "CURRENT_RESULT_LEDGER_CLEAN"
    )


def prediction_demo_drifted_audit_record_count(records: list[object]) -> int:
    return sum(
        1
        for record in records
        if getattr(record, "current_result_ledger_status", None)
        in {"CURRENT_RESULT_LEDGER_DRIFTED", "CURRENT_RESULT_LEDGER_MISSING"}
    )


def prediction_demo_campaign_gate_audit_reasons(
    campaign_audit: object,
    batch_audit: object,
    strategy_campaign_records: list[object],
    strategy_batch_records: list[object],
) -> list[str]:
    reasons: list[str] = []
    if int(getattr(campaign_audit, "record_count", 0) or 0) == 0:
        reasons.append("prediction_demo_campaign_evidence_missing")
    if not strategy_campaign_records:
        reasons.append("prediction_demo_campaign_strategy_evidence_missing")
    if int(getattr(campaign_audit, "current_result_drifted_records", 0) or 0) > 0:
        reasons.append("prediction_demo_campaign_current_result_drifted")
    if prediction_demo_drifted_audit_record_count(strategy_campaign_records) > 0:
        reasons.append("prediction_demo_campaign_strategy_current_result_drifted")
    side_sensitive_records = int(
        getattr(campaign_audit, "side_sensitive_records", 0) or 0
    )
    acknowledged_records = int(getattr(campaign_audit, "acknowledged_records", 0) or 0)
    if side_sensitive_records > acknowledged_records:
        reasons.append("prediction_demo_campaign_side_sensitivity_unacknowledged")
    strategy_side_sensitive_records = sum(
        1
        for record in strategy_campaign_records
        if getattr(record, "side_sensitivity_warning", None) is not None
    )
    strategy_acknowledged_records = sum(
        1
        for record in strategy_campaign_records
        if bool(getattr(record, "side_sensitivity_acknowledged", False))
    )
    if strategy_side_sensitive_records > strategy_acknowledged_records:
        reasons.append(
            "prediction_demo_campaign_strategy_side_sensitivity_unacknowledged"
        )
    if int(getattr(batch_audit, "current_result_drifted_records", 0) or 0) > 0:
        reasons.append("prediction_demo_batch_current_result_drifted")
    if prediction_demo_drifted_audit_record_count(strategy_batch_records) > 0:
        reasons.append("prediction_demo_batch_strategy_current_result_drifted")
    return sorted(set(reasons))


def prediction_demo_audit_record_snapshot(record: object | None) -> dict[str, object] | None:
    if record is None:
        return None
    return {
        "evidence_event_id": getattr(record, "evidence_event_id", None),
        "evidence_hash": getattr(record, "evidence_hash", None),
        "strategy": getattr(record, "strategy", None),
        "status": getattr(record, "status", None),
        "source": getattr(record, "source", None),
        "source_reference": getattr(record, "source_reference", None),
        "side": str(getattr(record, "side", "")) or None,
        "completed_records": getattr(record, "completed_records", 0),
        "countable_records": getattr(record, "countable_records", 0),
        "blocked_records": getattr(record, "blocked_records", 0),
        "ready_for_live_review": getattr(record, "ready_for_live_review", False),
        "current_result_records": getattr(record, "current_result_records", 0),
        "current_result_countable_records": getattr(
            record,
            "current_result_countable_records",
            0,
        ),
        "current_result_blocked_records": getattr(
            record,
            "current_result_blocked_records",
            0,
        ),
        "current_result_ledger_status": getattr(
            record,
            "current_result_ledger_status",
            None,
        ),
        "current_result_ledger_blockers": list(
            getattr(record, "current_result_ledger_blockers", []) or []
        ),
    }


def strategy_evidence_review_outcome(
    *,
    gates: list[LiveDeploymentGate],
    live_trading_enabled: bool,
    latest_paper_evidence: LivePaperEvidenceReport | None,
) -> tuple[StrategyEvidenceDecision, list[str], list[str], str]:
    gate_lookup = {gate.gate_key: gate for gate in gates}
    blocking_reasons = strategy_evidence_blocking_reasons(gate_lookup)
    negative_reasons = strategy_evidence_negative_reasons(
        gate_lookup,
        latest_paper_evidence,
    )
    if live_trading_enabled:
        negative_reasons.append("live_trading_flag_enabled_before_review_completion")

    if negative_reasons:
        reasons = sorted(set(negative_reasons))
        return (
            StrategyEvidenceDecision.DO_NOT_TRADE,
            reasons,
            [
                "Do not trade this strategy live under the current evidence record.",
                (
                    "Document the failure reasons, redesign or reject the strategy, "
                    "then require a fresh accepted backtest and paper-evidence cycle."
                ),
            ],
            "Strategy evidence is negative or unsafe; live deployment must not proceed.",
        )

    if blocking_reasons:
        reasons = sorted(set(blocking_reasons))
        return (
            StrategyEvidenceDecision.BLOCKED,
            reasons,
            strategy_evidence_next_actions(reasons, gate_lookup=gate_lookup),
            "Strategy evidence review is blocked until the required evidence gates pass.",
        )

    return (
        StrategyEvidenceDecision.CANDIDATE,
        [],
        [
            (
                "Proceed to broker/account approval, daily review, and micro-live "
                "readiness review; live trading remains disabled."
            )
        ],
        (
            "Strategy evidence is complete enough to remain a micro-live candidate, "
            "but this review does not authorize live trading."
        ),
    )


def strategy_evidence_blocking_reasons(
    gate_lookup: dict[str, LiveDeploymentGate],
) -> list[str]:
    reasons: list[str] = []
    for gate_key in STRATEGY_EVIDENCE_REVIEW_GATE_KEYS:
        gate = gate_lookup.get(gate_key)
        if gate is None:
            reasons.append(f"{gate_key}_not_run")
        elif gate.status != ReadinessStatus.PASS:
            reasons.append(f"{gate_key}_not_passed")
    return reasons


def strategy_evidence_negative_reasons(
    gate_lookup: dict[str, LiveDeploymentGate],
    latest_paper_evidence: LivePaperEvidenceReport | None,
) -> list[str]:
    reasons: list[str] = []
    backtest_gate = gate_lookup.get("accepted_backtest_complete")
    if backtest_gate is not None:
        backtest_evidence = backtest_gate.evidence_snapshot or {}
        backtest_reasons = set(backtest_evidence.get("live_readiness_reasons") or [])
        if backtest_reasons & NEGATIVE_BACKTEST_REASONS:
            reasons.extend(sorted(backtest_reasons & NEGATIVE_BACKTEST_REASONS))

    if latest_paper_evidence is None:
        return reasons

    mature_paper_sample = (
        latest_paper_evidence.total_trades >= latest_paper_evidence.minimum_trades
        and latest_paper_evidence.calendar_days_observed
        >= latest_paper_evidence.minimum_calendar_days
        and int(
            latest_paper_evidence.evidence_snapshot.get("active_trading_days") or 0
        )
        >= MIN_PAPER_ACTIVE_DAYS
    )
    if mature_paper_sample:
        paper_reasons = set(latest_paper_evidence.reasons or [])
        reasons.extend(sorted(paper_reasons & NEGATIVE_PAPER_EVIDENCE_REASONS))
    return reasons


def strategy_evidence_next_actions(
    reasons: list[str],
    *,
    gate_lookup: dict[str, LiveDeploymentGate] | None = None,
) -> list[str]:
    actions: list[str] = []
    if "accepted_backtest_complete_not_passed" in reasons:
        actions.append(
            "Store a strict accepted backtest for the selected strategy and symbols."
        )
    if "paper_evidence_complete_not_passed" in reasons:
        actions.append(
            "Import real paper evidence and run the Stage 14 paper-evidence report."
        )
    if "broker_statement_reconciliation_not_passed" in reasons:
        actions.append("Reconcile a current paper/broker statement against Aurex records.")
    if "kill_switch_clear_not_passed" in reasons:
        actions.append("Reset the risk kill switch before any readiness review.")
    if "tiny_risk_limits_not_passed" in reasons:
        actions.append("Reduce configured risk to the micro-live limits.")
    if "live_trading_disabled_not_passed" in reasons:
        actions.append("Disable live trading before continuing evidence review.")
    if "mkt_donor_credential_boundary_not_passed" in reasons:
        actions.append(
            "Remove production MKT credential files from the donor runtime profile or use a "
            "clean scoped demo userData directory before reviewing MKT-derived live readiness."
        )
    if "prediction_demo_campaign_quality_not_passed" in reasons:
        actions.extend(prediction_demo_campaign_quality_next_actions(gate_lookup))
    if not actions:
        actions.append("Resolve the listed evidence gate blockers before continuing.")
    return actions


def prediction_demo_campaign_quality_next_actions(
    gate_lookup: dict[str, LiveDeploymentGate] | None,
) -> list[str]:
    gate = gate_lookup.get("prediction_demo_campaign_quality") if gate_lookup else None
    evidence = gate.evidence_snapshot if gate is not None else {}
    gate_reasons = set(evidence.get("reasons") or []) if isinstance(evidence, dict) else set()
    actions: list[str] = []
    if gate_reasons & {
        "prediction_demo_campaign_evidence_missing",
        "prediction_demo_campaign_strategy_evidence_missing",
    }:
        actions.append(
            "Run a guarded MKT DB paper/demo campaign replay for the selected MKT "
            "strategy, then rerun live evidence review."
        )
    if gate_reasons & {
        "prediction_demo_campaign_current_result_drifted",
        "prediction_demo_campaign_strategy_current_result_drifted",
        "prediction_demo_batch_current_result_drifted",
        "prediction_demo_batch_strategy_current_result_drifted",
    }:
        actions.append(
            "Resolve prediction paper/demo campaign or batch current-result ledger "
            "drift, rerun clean reconciliation, then rerun live evidence review."
        )
    if gate_reasons & {
        "prediction_demo_campaign_side_sensitivity_unacknowledged",
        "prediction_demo_campaign_strategy_side_sensitivity_unacknowledged",
    }:
        actions.append(
            "Review the campaign side-sensitivity warning and record an explicit "
            "side-selection rationale before replay evidence can support live review."
        )
    if not actions:
        actions.append(
            "Complete the prediction-market paper/demo campaign quality gate for the "
            "selected MKT strategy before evidence review can pass."
        )
    return actions


def strategy_evidence_gate_snapshot(gates: list[LiveDeploymentGate]) -> dict[str, dict]:
    snapshot: dict[str, dict] = {}
    for gate in gates:
        if gate.gate_key not in STRATEGY_EVIDENCE_REVIEW_GATE_KEYS:
            continue
        snapshot[gate.gate_key] = {
            "name": gate.name,
            "status": gate.status.value,
            "required": gate.required,
            "evidence_snapshot": gate.evidence_snapshot,
            "notes": gate.notes,
            "last_checked_at": (
                gate.last_checked_at.isoformat() if gate.last_checked_at else None
            ),
        }
    return snapshot


def readiness_status_value(status: object) -> str:
    if isinstance(status, ReadinessStatus):
        return status.value
    return str(status)


def strategy_evidence_current_gate_statuses(
    gate_specs: list[tuple[str, str, object, dict[str, object], str]],
) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for gate_key, _name, status, _evidence, _notes in gate_specs:
        if gate_key in STRATEGY_EVIDENCE_REVIEW_GATE_KEYS:
            statuses[gate_key] = readiness_status_value(status)
    return statuses


def strategy_evidence_current_gate_fingerprints(
    gate_specs: list[tuple[str, str, object, dict[str, object], str]],
) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for gate_key, _name, _status, evidence, _notes in gate_specs:
        if gate_key in STRATEGY_EVIDENCE_REVIEW_GATE_KEYS:
            fingerprints[gate_key] = strategy_evidence_gate_evidence_fingerprint(
                evidence,
            )
    return fingerprints


def reviewed_strategy_evidence_gate_statuses(
    review: StrategyEvidenceReview,
) -> dict[str, str]:
    gate_snapshot = review.gate_snapshot if isinstance(review.gate_snapshot, dict) else {}
    statuses: dict[str, str] = {}
    for gate_key in STRATEGY_EVIDENCE_REVIEW_GATE_KEYS:
        gate = gate_snapshot.get(gate_key)
        if not isinstance(gate, dict):
            continue
        status = gate.get("status")
        if status is not None:
            statuses[gate_key] = readiness_status_value(status)
    return statuses


def reviewed_strategy_evidence_gate_fingerprints(
    review: StrategyEvidenceReview,
) -> dict[str, str]:
    gate_snapshot = review.gate_snapshot if isinstance(review.gate_snapshot, dict) else {}
    fingerprints: dict[str, str] = {}
    for gate_key in STRATEGY_EVIDENCE_REVIEW_GATE_KEYS:
        gate = gate_snapshot.get(gate_key)
        if not isinstance(gate, dict):
            continue
        evidence = gate.get("evidence_snapshot")
        if isinstance(evidence, dict):
            fingerprints[gate_key] = strategy_evidence_gate_evidence_fingerprint(
                evidence,
            )
    return fingerprints


def strategy_evidence_gate_evidence_fingerprint(evidence: dict[str, object]) -> str:
    payload = stable_strategy_evidence_gate_value(evidence)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def stable_strategy_evidence_gate_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): stable_strategy_evidence_gate_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) != "checked_at"
        }
    if isinstance(value, (list, tuple)):
        return [stable_strategy_evidence_gate_value(item) for item in value]
    if isinstance(value, Decimal):
        return normalized_decimal_text(value)
    if isinstance(value, datetime):
        return normalized_datetime_text(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def week_start_for_date(value: date) -> datetime:
    week_start = value - timedelta(days=value.weekday())
    return datetime.combine(week_start, datetime.min.time(), tzinfo=UTC)


def consecutive_loss_count(trades: list[PaperTrade]) -> int:
    losses = 0
    for trade in trades:
        realized_pl = trade.realized_pl or Decimal("0")
        if realized_pl < 0:
            losses += 1
            continue
        break
    return losses


def paper_execution_quality_violation(
    *,
    trade: PaperTrade,
    order: PaperOrder,
    signal: Signal,
    import_violation: dict[str, object] | None,
) -> dict[str, object] | None:
    violation = {
        "trade_id": trade.id,
        "paper_order_id": order.id,
        "fill_model": order.fill_model,
    }
    if order.fill_model not in EVIDENCE_GRADE_PAPER_FILL_MODELS:
        return {
            **violation,
            "reason": "non_evidence_grade_fill_model",
        }
    if order.status != OrderStatus.FILLED:
        return {**violation, "reason": "paper_order_not_filled"}
    if order.filled_price is None or order.filled_price <= 0:
        return {**violation, "reason": "paper_order_filled_price_invalid"}
    if order.filled_at is None:
        return {**violation, "reason": "paper_order_filled_at_missing"}
    if order.quantity <= 0:
        return {**violation, "reason": "paper_order_quantity_invalid"}

    snapshot = (
        order.execution_assumptions
        if isinstance(order.execution_assumptions, dict)
        else {}
    )
    if snapshot.get("schema_version") != PAPER_EXECUTION_SCHEMA_VERSION:
        return {**violation, "reason": "execution_assumptions_schema_invalid"}
    if snapshot.get("fill_model") != order.fill_model:
        return {**violation, "reason": "execution_assumptions_model_mismatch"}
    if snapshot.get("lifecycle_status") != "CLOSED":
        return {**violation, "reason": "execution_assumptions_lifecycle_incomplete"}
    if not isinstance(snapshot.get("entry"), dict):
        return {**violation, "reason": "execution_entry_assumptions_missing"}
    if not isinstance(snapshot.get("exit"), dict):
        return {**violation, "reason": "execution_exit_assumptions_missing"}
    if not order.execution_assumptions_hash:
        return {**violation, "reason": "execution_assumptions_hash_missing"}
    if order.execution_assumptions_hash != paper_execution_evidence_hash(snapshot):
        return {**violation, "reason": "execution_assumptions_hash_mismatch"}
    if not snapshot_decimal_equals(snapshot, "total_fees", trade.fees):
        return {**violation, "reason": "execution_total_fees_mismatch"}
    if not snapshot_decimal_equals(snapshot, "total_slippage", trade.slippage):
        return {**violation, "reason": "execution_total_slippage_mismatch"}
    if trade.exit_price is None or trade.realized_pl is None:
        return {**violation, "reason": "execution_close_values_missing"}
    expected_realized_pl = calculate_trade_pl(
        trade.direction,
        trade.entry_price,
        trade.exit_price,
        trade.quantity,
    ) - trade.fees - trade.slippage
    if abs(expected_realized_pl - trade.realized_pl) > RISK_TOLERANCE:
        return {**violation, "reason": "execution_realized_pl_cost_mismatch"}

    entry = snapshot["entry"]
    if not snapshot_decimal_equals(entry, "fees", order.fees):
        return {**violation, "reason": "execution_entry_fees_mismatch"}
    if not snapshot_decimal_equals(entry, "slippage", order.slippage):
        return {**violation, "reason": "execution_entry_slippage_mismatch"}
    exit_snapshot = snapshot["exit"]
    entry_fees = snapshot_decimal_value(entry, "fees")
    entry_slippage = snapshot_decimal_value(entry, "slippage")
    exit_fees = snapshot_decimal_value(exit_snapshot, "fees")
    exit_slippage = snapshot_decimal_value(exit_snapshot, "slippage")
    if None in (entry_fees, entry_slippage, exit_fees, exit_slippage):
        return {**violation, "reason": "execution_cost_breakdown_invalid"}
    if entry_fees + exit_fees != trade.fees:
        return {**violation, "reason": "execution_fee_breakdown_mismatch"}
    if entry_slippage + exit_slippage != trade.slippage:
        return {**violation, "reason": "execution_slippage_breakdown_mismatch"}

    if order.fill_model == DETERMINISTIC_PAPER_FILL_MODEL:
        if snapshot.get("cost_floor_enforced") is not True:
            return {**violation, "reason": "execution_cost_floor_not_enforced"}
        if trade.fees + trade.slippage <= 0:
            return {**violation, "reason": "modeled_execution_costs_not_positive"}
        assumptions = snapshot.get("assumptions")
        if not isinstance(assumptions, dict):
            return {**violation, "reason": "execution_cost_assumptions_missing"}
        if not all(
            key in assumptions
            for key in (
                "commission_bps",
                "half_spread_bps",
                "market_impact_bps",
                "latency_ms",
            )
        ):
            return {**violation, "reason": "execution_cost_assumptions_incomplete"}
        return None

    if order.fill_model == IMPORTED_PAPER_FILL_MODEL:
        if not is_imported_trade_signal(signal):
            return {**violation, "reason": "imported_fill_source_lineage_missing"}
        if import_violation is not None:
            return {**violation, "reason": "imported_fill_evidence_invalid"}
        raw_payload = signal.raw_payload if isinstance(signal.raw_payload, dict) else {}
        if snapshot.get("source_verified_by_hash") is not True:
            return {**violation, "reason": "imported_fill_source_hash_unverified"}
        if snapshot.get("import_evidence_hash") != raw_payload.get(
            "import_evidence_hash"
        ):
            return {**violation, "reason": "imported_fill_source_hash_mismatch"}
        return None

    return {**violation, "reason": "non_evidence_grade_fill_model"}


def snapshot_decimal_equals(
    snapshot: dict[str, object],
    key: str,
    expected: Decimal,
) -> bool:
    value = snapshot.get(key)
    if value is None:
        return False
    try:
        return Decimal(str(value)) == Decimal(str(expected))
    except (ArithmeticError, ValueError):
        return False


def snapshot_decimal_value(
    snapshot: dict[str, object],
    key: str,
) -> Decimal | None:
    value = snapshot.get(key)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None


def is_imported_trade_signal(signal: Signal) -> bool:
    raw_payload = signal.raw_payload if isinstance(signal.raw_payload, dict) else {}
    return bool(raw_payload.get("import_batch_id")) or signal.idempotency_key.startswith(
        "paper-import:"
    )


def imported_trade_evidence_violation(
    *,
    trade: PaperTrade,
    order: PaperOrder,
    decision: RiskDecision,
    signal: Signal,
    journal: TradeJournalEntry | None,
) -> dict[str, object] | None:
    raw_payload = signal.raw_payload if isinstance(signal.raw_payload, dict) else {}
    if not is_imported_trade_signal(signal):
        return None

    expected_hash = raw_payload.get("import_evidence_hash")
    external_trade_id = raw_payload.get("external_trade_id")
    if not expected_hash:
        return {
            "trade_id": trade.id,
            "reason": "imported_trade_evidence_hash_missing",
            "external_trade_id": external_trade_id,
        }
    if journal is None:
        return {
            "trade_id": trade.id,
            "reason": "imported_trade_journal_evidence_missing",
            "external_trade_id": external_trade_id,
            "expected_evidence_hash": expected_hash,
        }

    current_payload = imported_paper_trade_evidence_payload_from_models(
        trade=trade,
        order=order,
        decision=decision,
        signal=signal,
        journal=journal,
    )
    current_hash = imported_paper_trade_evidence_hash(current_payload)
    if current_hash == expected_hash:
        return None
    return {
        "trade_id": trade.id,
        "reason": "imported_trade_evidence_payload_mismatch",
        "external_trade_id": external_trade_id,
        "expected_evidence_hash": expected_hash,
        "current_evidence_hash": current_hash,
    }


def paper_evidence_gate_status(report: LivePaperEvidenceReport | None) -> ReadinessStatus:
    if report is None:
        return ReadinessStatus.NOT_RUN
    return report.status


def strategy_evidence_review_gate_audit(
    *,
    plan: LiveDeploymentPlan,
    review: StrategyEvidenceReview | None,
    latest_backtest: BacktestRun | None,
    latest_paper_evidence: LivePaperEvidenceReport | None,
    latest_broker_statement: LiveBrokerStatementReport | None,
    current_gate_statuses: dict[str, str],
    current_gate_fingerprints: dict[str, str],
) -> dict[str, object]:
    if review is None:
        return {
            "status": ReadinessStatus.NOT_RUN,
            "freshness_reasons": ["strategy_evidence_review_missing"],
            "reviewed_artifacts": {},
            "current_artifacts": current_strategy_evidence_artifacts(
                latest_backtest,
                latest_paper_evidence,
                latest_broker_statement,
            ),
            "reviewed_plan": {},
            "current_plan": strategy_review_plan_snapshot(plan),
            "reviewed_gate_statuses": {},
            "current_gate_statuses": current_gate_statuses,
            "reviewed_gate_fingerprints": {},
            "current_gate_fingerprints": current_gate_fingerprints,
        }

    freshness_reasons = strategy_evidence_review_freshness_reasons(
        plan,
        review,
        latest_backtest,
        latest_paper_evidence,
        latest_broker_statement,
        current_gate_statuses,
        current_gate_fingerprints,
    )
    if review.decision == StrategyEvidenceDecision.CANDIDATE:
        status = ReadinessStatus.BLOCKED if freshness_reasons else ReadinessStatus.PASS
    elif review.decision == StrategyEvidenceDecision.DO_NOT_TRADE:
        status = ReadinessStatus.FAIL
    else:
        status = ReadinessStatus.BLOCKED

    return {
        "status": status,
        "freshness_reasons": freshness_reasons,
        "reviewed_artifacts": reviewed_strategy_evidence_artifacts(review),
        "current_artifacts": current_strategy_evidence_artifacts(
            latest_backtest,
            latest_paper_evidence,
            latest_broker_statement,
        ),
        "reviewed_plan": reviewed_strategy_review_plan_snapshot(review),
        "current_plan": strategy_review_plan_snapshot(plan),
        "reviewed_gate_statuses": reviewed_strategy_evidence_gate_statuses(review),
        "current_gate_statuses": current_gate_statuses,
        "reviewed_gate_fingerprints": reviewed_strategy_evidence_gate_fingerprints(
            review,
        ),
        "current_gate_fingerprints": current_gate_fingerprints,
    }


def strategy_evidence_review_freshness_reasons(
    plan: LiveDeploymentPlan,
    review: StrategyEvidenceReview,
    latest_backtest: BacktestRun | None,
    latest_paper_evidence: LivePaperEvidenceReport | None,
    latest_broker_statement: LiveBrokerStatementReport | None,
    current_gate_statuses: dict[str, str],
    current_gate_fingerprints: dict[str, str],
) -> list[str]:
    reviewed = reviewed_strategy_evidence_artifacts(review)
    current = current_strategy_evidence_artifacts(
        latest_backtest,
        latest_paper_evidence,
        latest_broker_statement,
    )
    checks = {
        "accepted_backtest_run_id": "accepted_backtest_changed_since_review",
        "paper_evidence_report_id": "paper_evidence_changed_since_review",
        "broker_statement_report_id": "broker_statement_changed_since_review",
    }
    reasons: list[str] = []
    for key, reason in checks.items():
        if current.get(key) and reviewed.get(key) != current.get(key):
            reasons.append(reason)
    reviewed_plan = reviewed_strategy_review_plan_snapshot(review)
    current_plan = strategy_review_plan_snapshot(plan)
    for key, current_value in current_plan.items():
        if reviewed_plan.get(key) != current_value:
            reasons.append(f"deployment_plan_{key}_changed_since_review")
    reviewed_gate_statuses = reviewed_strategy_evidence_gate_statuses(review)
    reviewed_gate_fingerprints = reviewed_strategy_evidence_gate_fingerprints(review)
    for gate_key in STRATEGY_EVIDENCE_REVIEW_GATE_KEYS:
        current_status = current_gate_statuses.get(gate_key)
        if current_status is None:
            continue
        reviewed_status = reviewed_gate_statuses.get(gate_key)
        if reviewed_status is None:
            reasons.append(f"{gate_key}_missing_from_review")
        elif reviewed_status != current_status:
            reasons.append(f"{gate_key}_status_changed_since_review")
            continue
        reviewed_fingerprint = reviewed_gate_fingerprints.get(gate_key)
        current_fingerprint = current_gate_fingerprints.get(gate_key)
        if (
            reviewed_fingerprint is not None
            and current_fingerprint is not None
            and reviewed_fingerprint != current_fingerprint
        ):
            reasons.append(f"{gate_key}_evidence_changed_since_review")
    return reasons


def strategy_review_plan_snapshot(plan: LiveDeploymentPlan) -> dict[str, object]:
    return {
        "strategy": plan.strategy,
        "symbols": list(plan.symbols or []),
        "risk_per_trade": normalized_decimal_text(plan.risk_per_trade),
        "max_daily_loss": normalized_decimal_text(plan.max_daily_loss),
        "max_weekly_loss": normalized_decimal_text(plan.max_weekly_loss),
        "max_open_positions": plan.max_open_positions,
        "target_net_profit": normalized_decimal_text(plan.target_net_profit),
    }


def normalized_decimal_text(value: Decimal) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def normalized_optional_decimal_text(value: Decimal | None) -> str | None:
    return normalized_decimal_text(value) if value is not None else None


def normalized_datetime_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def stable_snapshot_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def paper_evidence_ledger_snapshot(
    *,
    plan: LiveDeploymentPlan,
    closed_trades: list[PaperTrade],
    performance,
    first_trade_at: datetime | None,
    latest_trade_at: datetime | None,
    calendar_days_observed: int,
    integrity_audit: dict[str, object],
    journal_audit: dict[str, object],
    coverage_audit: dict[str, object],
    scope_audit: dict[str, object],
    journal_hash: str,
    lineage_hash: str,
) -> dict[str, object]:
    trade_rows = [
        {
            "id": trade.id,
            "strategy": trade.strategy,
            "symbol": trade.symbol,
            "status": trade.status.value,
            "entry_price": normalized_decimal_text(trade.entry_price),
            "exit_price": normalized_optional_decimal_text(trade.exit_price),
            "stop_loss": normalized_decimal_text(trade.stop_loss),
            "take_profit": normalized_optional_decimal_text(trade.take_profit),
            "quantity": normalized_decimal_text(trade.quantity),
            "risk_amount": normalized_decimal_text(trade.risk_amount),
            "realized_pl": normalized_optional_decimal_text(trade.realized_pl),
            "fees": normalized_decimal_text(trade.fees),
            "slippage": normalized_decimal_text(trade.slippage),
            "fill_model": (
                trade.paper_order.fill_model if trade.paper_order is not None else None
            ),
            "execution_assumptions_hash": (
                trade.paper_order.execution_assumptions_hash
                if trade.paper_order is not None
                else None
            ),
            "opened_at": normalized_datetime_text(trade.opened_at),
            "closed_at": normalized_datetime_text(trade.closed_at),
        }
        for trade in sorted(closed_trades, key=lambda item: item.id)
    ]
    return {
        "strategy_scope": plan.strategy,
        "symbol_scope": list(plan.symbols or []),
        "closed_trade_ids": [row["id"] for row in trade_rows],
        "material_trade_hash": stable_snapshot_hash(trade_rows),
        "journal_hash": journal_hash,
        "lineage_hash": lineage_hash,
        "total_trades": performance.total_trades,
        "total_net_pl": normalized_decimal_text(performance.total_net_pl),
        "expectancy": normalized_decimal_text(performance.expectancy),
        "profit_factor": (
            normalized_decimal_text(performance.profit_factor)
            if performance.profit_factor is not None
            else None
        ),
        "max_drawdown": normalized_decimal_text(performance.max_drawdown),
        "first_trade_at": normalized_datetime_text(first_trade_at),
        "latest_trade_at": normalized_datetime_text(latest_trade_at),
        "calendar_days_observed": calendar_days_observed,
        "active_trading_days": coverage_audit["active_trading_days"],
        "max_single_day_trade_count": coverage_audit["max_single_day_trade_count"],
        "max_single_day_trade_share": coverage_audit["max_single_day_trade_share"],
        "in_scope_trade_count": scope_audit["in_scope_trade_count"],
        "out_of_scope_trade_count": scope_audit["out_of_scope_trade_count"],
        "journaled_trade_count": journal_audit["journaled_trade_count"],
        "unjournaled_trade_count": journal_audit["unjournaled_trade_count"],
        "journal_rule_violation_count": journal_audit["journal_rule_violation_count"],
        "unexplained_trade_count": integrity_audit["unexplained_trade_count"],
        "risk_rule_violation_count": integrity_audit["risk_rule_violation_count"],
        "evidence_grade_trade_count": integrity_audit[
            "evidence_grade_trade_count"
        ],
        "non_evidence_grade_trade_count": integrity_audit[
            "non_evidence_grade_trade_count"
        ],
        "execution_quality_violation_count": integrity_audit[
            "execution_quality_violation_count"
        ],
        "fill_model_counts": integrity_audit["fill_model_counts"],
    }


def paper_evidence_report_freshness_reasons(
    reviewed_ledger: object,
    current_ledger: dict[str, object],
) -> list[str]:
    if not isinstance(reviewed_ledger, dict):
        return ["paper_evidence_report_missing_ledger_snapshot"]

    checks = {
        "strategy_scope": "paper_evidence_strategy_scope_changed_since_report",
        "symbol_scope": "paper_evidence_symbol_scope_changed_since_report",
        "closed_trade_ids": "paper_evidence_trade_ledger_changed_since_report",
        "material_trade_hash": "paper_evidence_trade_ledger_changed_since_report",
        "journal_hash": "paper_evidence_journal_ledger_changed_since_report",
        "lineage_hash": "paper_evidence_lineage_changed_since_report",
        "total_trades": "paper_evidence_metrics_changed_since_report",
        "total_net_pl": "paper_evidence_metrics_changed_since_report",
        "expectancy": "paper_evidence_metrics_changed_since_report",
        "profit_factor": "paper_evidence_metrics_changed_since_report",
        "max_drawdown": "paper_evidence_metrics_changed_since_report",
        "first_trade_at": "paper_evidence_window_changed_since_report",
        "latest_trade_at": "paper_evidence_window_changed_since_report",
        "calendar_days_observed": "paper_evidence_window_changed_since_report",
        "active_trading_days": "paper_evidence_coverage_changed_since_report",
        "max_single_day_trade_count": "paper_evidence_coverage_changed_since_report",
        "max_single_day_trade_share": "paper_evidence_coverage_changed_since_report",
        "in_scope_trade_count": "paper_evidence_scope_changed_since_report",
        "out_of_scope_trade_count": "paper_evidence_scope_changed_since_report",
        "journaled_trade_count": "paper_evidence_journal_ledger_changed_since_report",
        "unjournaled_trade_count": "paper_evidence_journal_ledger_changed_since_report",
        "journal_rule_violation_count": (
            "paper_evidence_journal_ledger_changed_since_report"
        ),
        "unexplained_trade_count": "paper_evidence_lineage_changed_since_report",
        "risk_rule_violation_count": "paper_evidence_lineage_changed_since_report",
        "evidence_grade_trade_count": "paper_execution_quality_changed_since_report",
        "non_evidence_grade_trade_count": "paper_execution_quality_changed_since_report",
        "execution_quality_violation_count": (
            "paper_execution_quality_changed_since_report"
        ),
        "fill_model_counts": "paper_execution_quality_changed_since_report",
    }
    reasons = [
        reason
        for key, reason in checks.items()
        if reviewed_ledger.get(key) != current_ledger.get(key)
    ]
    return sorted(set(reasons))


def reviewed_strategy_review_plan_snapshot(
    review: StrategyEvidenceReview,
) -> dict[str, object]:
    snapshot = review.evidence_snapshot or {}
    plan_snapshot = snapshot.get("deployment_plan_snapshot")
    if isinstance(plan_snapshot, dict):
        return plan_snapshot
    return {
        "strategy": review.strategy,
        "symbols": list(review.symbols or []),
    }


def reviewed_strategy_evidence_artifacts(review: StrategyEvidenceReview) -> dict[str, str | None]:
    snapshot = review.evidence_snapshot or {}
    gate_snapshot = review.gate_snapshot or {}
    accepted_backtest_gate = gate_snapshot.get("accepted_backtest_complete") or {}
    accepted_backtest_evidence = accepted_backtest_gate.get("evidence_snapshot") or {}
    return {
        "accepted_backtest_run_id": snapshot.get("latest_accepted_backtest_run_id")
        or accepted_backtest_evidence.get("backtest_run_id"),
        "paper_evidence_report_id": snapshot.get("latest_paper_evidence_report_id"),
        "broker_statement_report_id": snapshot.get("latest_broker_statement_report_id"),
    }


def current_strategy_evidence_artifacts(
    latest_backtest: BacktestRun | None,
    latest_paper_evidence: LivePaperEvidenceReport | None,
    latest_broker_statement: LiveBrokerStatementReport | None,
) -> dict[str, str | None]:
    return {
        "accepted_backtest_run_id": latest_backtest.id if latest_backtest else None,
        "paper_evidence_report_id": (
            latest_paper_evidence.id if latest_paper_evidence else None
        ),
        "broker_statement_report_id": (
            latest_broker_statement.id if latest_broker_statement else None
        ),
    }


def accepted_backtest_gate_status(run: BacktestRun | None) -> ReadinessStatus:
    return accepted_backtest_live_readiness_audit(run)["status"]


def accepted_backtest_live_readiness_audit(run: BacktestRun | None) -> dict:
    reasons: list[str] = []
    out_of_sample: dict | None = None
    walk_forward: dict | None = None
    trade_distribution: dict | None = None
    market_regime_breakdown: dict | None = None
    parameter_evidence: dict | None = None
    if run is None:
        return {
            "status": ReadinessStatus.BLOCKED,
            "reasons": ["accepted_backtest_missing"],
            "out_of_sample": None,
            "walk_forward": None,
            "trade_distribution": None,
            "market_regime_breakdown": None,
            "strategy_parameter_evidence": None,
            "source_evidence": None,
        }

    result = run.result
    parameter_evidence = strategy_parameter_evidence_snapshot(
        run.strategy,
        run.parameters or {},
    )
    if result is None:
        reasons.append("accepted_backtest_result_missing")
    elif result.acceptance_passed is not True:
        reasons.append("accepted_backtest_report_not_accepted")
    else:
        reasons.extend(persisted_trade_evidence_reasons(run, result))
        reasons.extend(persisted_backtest_protocol_reasons(run, result))
        reasons.extend(accepted_backtest_strategy_parameter_reasons(run))
        reasons.extend(accepted_backtest_source_reasons(run))
        if result.total_trades < MIN_ACCEPTED_BACKTEST_TRADES:
            reasons.append("accepted_backtest_minimum_trades_not_met")
        max_drawdown_limit = snapshot_decimal(result.acceptance_snapshot or {}, "max_drawdown")
        if max_drawdown_limit is None:
            reasons.append("accepted_backtest_max_drawdown_limit_missing")
        elif result.max_drawdown is not None and result.max_drawdown > max_drawdown_limit:
            reasons.append("accepted_backtest_max_drawdown_exceeds_declared_limit")
        metrics_snapshot = result.metrics_snapshot or {}
        out_of_sample = metrics_snapshot.get("out_of_sample")
        walk_forward = metrics_snapshot.get("walk_forward")
        trade_distribution = metrics_snapshot.get("trade_distribution")
        market_regime_breakdown = metrics_snapshot.get("market_regime_breakdown")
        if not isinstance(out_of_sample, dict):
            reasons.append("accepted_backtest_out_of_sample_metrics_missing")
        else:
            oos_trades = snapshot_int(out_of_sample, "total_trades")
            oos_expectancy = snapshot_decimal(out_of_sample, "expectancy")
            oos_profit_factor = snapshot_decimal(out_of_sample, "profit_factor")
            if oos_trades < MIN_ACCEPTED_BACKTEST_OOS_TRADES:
                reasons.append("accepted_backtest_oos_minimum_trades_not_met")
            if oos_expectancy is None or oos_expectancy <= 0:
                reasons.append("accepted_backtest_oos_expectancy_not_positive")
            if (
                oos_profit_factor is not None
                and oos_profit_factor < MIN_ACCEPTED_BACKTEST_OOS_PROFIT_FACTOR
            ):
                reasons.append("accepted_backtest_oos_profit_factor_below_minimum")
        if not isinstance(trade_distribution, dict):
            reasons.append("accepted_backtest_trade_distribution_missing")
        else:
            reasons.extend(accepted_backtest_distribution_reasons(trade_distribution, result))
        if not isinstance(walk_forward, dict):
            reasons.append("accepted_backtest_walk_forward_missing")
        else:
            reasons.extend(accepted_backtest_walk_forward_reasons(walk_forward))
        if not isinstance(market_regime_breakdown, dict):
            reasons.append("accepted_backtest_market_regime_breakdown_missing")
        else:
            reasons.extend(
                accepted_backtest_market_regime_reasons(market_regime_breakdown)
            )

    if any(
        value is None
        for value in (
            run.in_sample_start,
            run.in_sample_end,
            run.out_of_sample_start,
            run.out_of_sample_end,
        )
    ):
        reasons.append("accepted_backtest_sample_windows_missing")
    elif run.in_sample_end is not None and run.out_of_sample_start is not None:
        if run.in_sample_end >= run.out_of_sample_start:
            reasons.append("accepted_backtest_sample_windows_overlap")

    if not run.cost_model:
        reasons.append("accepted_backtest_cost_model_missing")
    if not run.slippage_model:
        reasons.append("accepted_backtest_slippage_model_missing")
    if not run.risk_snapshot:
        reasons.append("accepted_backtest_risk_snapshot_missing")

    return {
        "status": ReadinessStatus.PASS if not reasons else ReadinessStatus.BLOCKED,
        "reasons": reasons,
        "out_of_sample": out_of_sample,
        "walk_forward": walk_forward,
        "trade_distribution": trade_distribution,
        "market_regime_breakdown": market_regime_breakdown,
        "strategy_parameter_evidence": parameter_evidence,
        "source_evidence": accepted_backtest_source_evidence(run),
    }


def accepted_backtest_distribution_reasons(
    snapshot: dict,
    result: object,
) -> list[str]:
    reasons: list[str] = []
    total_trades = result.total_trades
    dated_trades = snapshot_int(snapshot, "dated_trade_count")
    active_days = snapshot_int(snapshot, "active_trading_days")
    max_share = snapshot_decimal(snapshot, "max_single_day_trade_share")
    if dated_trades < total_trades:
        reasons.append("accepted_backtest_closed_at_timestamps_missing")
    if active_days < MIN_ACCEPTED_BACKTEST_ACTIVE_DAYS:
        reasons.append("accepted_backtest_active_trading_days_not_met")
    if (
        max_share is not None
        and max_share > MAX_ACCEPTED_BACKTEST_SINGLE_DAY_SHARE
    ):
        reasons.append("accepted_backtest_trade_concentration_too_high")
    return reasons


def accepted_backtest_walk_forward_reasons(snapshot: dict) -> list[str]:
    reasons: list[str] = []
    if snapshot.get("method") != EXPLICIT_WALK_FORWARD_METHOD or not bool(
        snapshot.get("acceptance_eligible")
    ):
        reasons.append("accepted_backtest_walk_forward_not_explicit")
    if snapshot_int(snapshot, "invalid_window_count") > 0:
        reasons.append("accepted_backtest_walk_forward_windows_invalid")
    if (
        snapshot_int(snapshot, "valid_window_count")
        < MIN_ACCEPTED_BACKTEST_WALK_FORWARD_WINDOWS
    ):
        reasons.append("accepted_backtest_walk_forward_windows_not_met")
    pass_rate = snapshot_decimal(snapshot, "pass_rate")
    if (
        pass_rate is None
        or pass_rate < MIN_ACCEPTED_BACKTEST_WALK_FORWARD_PASS_RATE
    ):
        reasons.append("accepted_backtest_walk_forward_pass_rate_not_met")
    evidence_hash = snapshot.get("evidence_hash")
    if not isinstance(evidence_hash, str) or evidence_hash != walk_forward_evidence_hash(
        snapshot
    ):
        reasons.append("accepted_backtest_walk_forward_evidence_hash_mismatch")
    return reasons


def accepted_backtest_market_regime_reasons(snapshot: dict) -> list[str]:
    missing_count = snapshot_int(snapshot, "missing_market_regime_count")
    regime_count = snapshot_int(snapshot, "regime_count")
    if missing_count > 0:
        return ["accepted_backtest_market_regime_missing"]
    if regime_count == 0:
        return ["accepted_backtest_market_regime_breakdown_empty"]
    return []


def snapshot_int(snapshot: dict, key: str) -> int:
    value = snapshot.get(key)
    if value is None:
        return 0
    return int(value)


def snapshot_decimal(snapshot: dict, key: str) -> Decimal | None:
    value = snapshot.get(key)
    if value is None:
        return None
    return Decimal(str(value))


def broker_statement_gate_status(
    report: LiveBrokerStatementReport | None,
) -> ReadinessStatus:
    if report is None:
        return ReadinessStatus.NOT_RUN
    return report.status


def broker_statement_ledger_snapshot(
    *,
    plan: LiveDeploymentPlan,
    closed_trades: list[PaperTrade],
    statement_start_at: datetime | None,
    statement_end_at: datetime | None,
) -> dict[str, object]:
    trade_rows = [
        {
            "id": trade.id,
            "strategy": trade.strategy,
            "symbol": trade.symbol,
            "status": trade.status.value,
            "realized_pl": normalized_optional_decimal_text(trade.realized_pl),
            "fees": normalized_decimal_text(trade.fees),
            "slippage": normalized_decimal_text(trade.slippage),
            "exit_price": normalized_optional_decimal_text(trade.exit_price),
            "quantity": normalized_decimal_text(trade.quantity),
            "closed_at": normalized_datetime_text(trade.closed_at),
        }
        for trade in sorted(closed_trades, key=lambda item: item.id)
    ]
    return {
        "strategy_scope": plan.strategy,
        "symbol_scope": list(plan.symbols or []),
        "statement_start_at": normalized_datetime_text(statement_start_at),
        "statement_end_at": normalized_datetime_text(statement_end_at),
        "closed_trade_ids": [row["id"] for row in trade_rows],
        "material_trade_hash": stable_snapshot_hash(trade_rows),
        "aurex_trade_count": len(closed_trades),
        "aurex_net_pl": normalized_decimal_text(
            sum((trade.realized_pl or Decimal("0") for trade in closed_trades), Decimal("0"))
        ),
        "aurex_fees": normalized_decimal_text(
            sum((trade.fees or Decimal("0") for trade in closed_trades), Decimal("0"))
        ),
        "aurex_slippage": normalized_decimal_text(
            sum((trade.slippage or Decimal("0") for trade in closed_trades), Decimal("0"))
        ),
    }


def broker_statement_report_freshness_reasons(
    reviewed_ledger: object,
    current_ledger: dict[str, object],
) -> list[str]:
    if not isinstance(reviewed_ledger, dict):
        return ["broker_statement_missing_ledger_snapshot"]

    checks = {
        "strategy_scope": "broker_statement_strategy_scope_changed_since_report",
        "symbol_scope": "broker_statement_symbol_scope_changed_since_report",
        "statement_start_at": "broker_statement_window_changed_since_report",
        "statement_end_at": "broker_statement_window_changed_since_report",
        "closed_trade_ids": "broker_statement_trade_ledger_changed_since_report",
        "material_trade_hash": "broker_statement_trade_ledger_changed_since_report",
        "aurex_trade_count": "broker_statement_totals_changed_since_report",
        "aurex_net_pl": "broker_statement_totals_changed_since_report",
        "aurex_fees": "broker_statement_totals_changed_since_report",
        "aurex_slippage": "broker_statement_totals_changed_since_report",
    }
    reasons = [
        reason
        for key, reason in checks.items()
        if reviewed_ledger.get(key) != current_ledger.get(key)
    ]
    return sorted(set(reasons))


def broker_statement_discrepancies(
    payload: BrokerStatementReconciliationRequest,
    aurex_trade_count: int,
    aurex_net_pl: Decimal,
    aurex_fees: Decimal,
    aurex_slippage: Decimal,
) -> list[dict[str, str]]:
    discrepancies: list[dict[str, str]] = []
    if (
        payload.statement_start_at is not None
        and payload.statement_end_at is not None
        and payload.statement_start_at > payload.statement_end_at
    ):
        discrepancies.append(
            {
                "reason": "statement_window_invalid",
                "statement_start_at": payload.statement_start_at.isoformat(),
                "statement_end_at": payload.statement_end_at.isoformat(),
            }
        )
    if aurex_trade_count == 0:
        discrepancies.append({"reason": "no_closed_trades_in_statement_window"})
    if payload.broker_trade_count != aurex_trade_count:
        discrepancies.append(
            {
                "reason": "statement_trade_count_mismatch",
                "broker_trade_count": str(payload.broker_trade_count),
                "aurex_trade_count": str(aurex_trade_count),
            }
        )
    if payload.broker_net_pl != aurex_net_pl:
        discrepancies.append(
            {
                "reason": "statement_net_pl_mismatch",
                "broker_net_pl": str(payload.broker_net_pl),
                "aurex_net_pl": str(aurex_net_pl),
            }
        )
    if payload.broker_fees != aurex_fees:
        discrepancies.append(
            {
                "reason": "statement_fee_mismatch",
                "broker_fees": str(payload.broker_fees),
                "aurex_fees": str(aurex_fees),
            }
        )
    if payload.broker_slippage != aurex_slippage:
        discrepancies.append(
            {
                "reason": "statement_slippage_mismatch",
                "broker_slippage": str(payload.broker_slippage),
                "aurex_slippage": str(aurex_slippage),
            }
        )
    return discrepancies


def broker_statement_preflight_next_action(discrepancies: list[dict[str, str]]) -> str:
    reasons = {str(item.get("reason")) for item in discrepancies}
    if not reasons:
        return "Broker statement CSV reconciles with current Aurex closed trades."
    if "broker_statement_csv_not_ready" in reasons:
        return "Fix rejected broker statement CSV rows before reconciliation."
    if "no_closed_trades_in_statement_window" in reasons:
        return "Use a broker statement window that contains scoped Aurex closed trades."
    if "statement_trade_count_mismatch" in reasons:
        return "Compare broker rows with Aurex scoped closed trades before reconciling."
    if reasons & {
        "statement_net_pl_mismatch",
        "statement_fee_mismatch",
        "statement_slippage_mismatch",
    }:
        return "Resolve broker versus Aurex totals before recording reconciliation."
    if "statement_window_invalid" in reasons:
        return "Correct the broker statement start/end window before reconciliation."
    return "Resolve broker statement discrepancies before reconciliation."


def profit_milestone_loss_audit(
    closed_trades: list[PaperTrade],
    plan: LiveDeploymentPlan,
    account: Account,
) -> dict[str, object]:
    daily_totals: dict[str, Decimal] = {}
    weekly_totals: dict[str, Decimal] = {}
    for trade in closed_trades:
        if trade.closed_at is None:
            continue
        realized_pl = trade.realized_pl or Decimal("0")
        day_key = trade.closed_at.date().isoformat()
        week_key = week_start_for_date(trade.closed_at.date()).date().isoformat()
        daily_totals[day_key] = daily_totals.get(day_key, Decimal("0")) + realized_pl
        weekly_totals[week_key] = weekly_totals.get(week_key, Decimal("0")) + realized_pl

    daily_loss_limit = -(account.current_equity * plan.max_daily_loss)
    weekly_loss_limit = -(account.current_equity * plan.max_weekly_loss)
    daily_breaches = [
        {
            "date": date_key,
            "realized_pl": str(realized_pl),
            "limit": str(daily_loss_limit),
        }
        for date_key, realized_pl in daily_totals.items()
        if realized_pl <= daily_loss_limit
    ]
    weekly_breaches = [
        {
            "week_start": week_key,
            "realized_pl": str(realized_pl),
            "limit": str(weekly_loss_limit),
        }
        for week_key, realized_pl in weekly_totals.items()
        if realized_pl <= weekly_loss_limit
    ]
    return {
        "daily_loss_limit": str(daily_loss_limit),
        "weekly_loss_limit": str(weekly_loss_limit),
        "daily_realized_pl": {key: str(value) for key, value in daily_totals.items()},
        "weekly_realized_pl": {key: str(value) for key, value in weekly_totals.items()},
        "daily_loss_breach_count": len(daily_breaches),
        "weekly_loss_breach_count": len(weekly_breaches),
        "daily_loss_breaches": daily_breaches[:10],
        "weekly_loss_breaches": weekly_breaches[:10],
    }


def broker_statement_current(
    report: LiveBrokerStatementReport | None,
    closed_trade_count: int,
    total_net_pl: Decimal,
    freshness_reasons: list[object] | None = None,
) -> bool:
    return bool(
        report is not None
        and report.status == ReadinessStatus.PASS
        and not (freshness_reasons or [])
        and report.aurex_trade_count == closed_trade_count
        and report.aurex_net_pl == total_net_pl
    )


def profit_milestone_reasons(
    plan: LiveDeploymentPlan,
    total_net_pl: Decimal,
    closed_trade_count: int,
    integrity_audit: dict[str, object],
    journal_audit: dict[str, object],
    loss_audit: dict[str, object],
    broker_statement: LiveBrokerStatementReport | None,
    broker_statement_freshness_reasons: list[object],
    risk_kill_switch_enabled: bool,
    live_execution_reasons: list[str],
) -> list[str]:
    reasons: list[str] = []
    reasons.extend(live_execution_reasons)
    if closed_trade_count == 0:
        reasons.append("no_closed_trades")
    if total_net_pl < plan.target_net_profit:
        reasons.append("target_net_profit_not_reached")
    if int(journal_audit["unjournaled_trade_count"]) > 0:
        reasons.append("unjournaled_trades_present")
    if int(journal_audit["journal_rule_violation_count"]) > 0:
        reasons.append("journal_rule_violations_present")
    if int(integrity_audit["unexplained_trade_count"]) > 0:
        reasons.append("unexplained_trades_present")
    if int(integrity_audit["risk_rule_violation_count"]) > 0:
        reasons.append("risk_rule_violations_present")
    if int(integrity_audit["non_evidence_grade_trade_count"]) > 0:
        reasons.append("non_evidence_grade_paper_fills_present")
    if int(integrity_audit["execution_quality_violation_count"]) > 0:
        reasons.append("paper_execution_quality_violations_present")
    if int(loss_audit["daily_loss_breach_count"]) > 0:
        reasons.append("daily_loss_limit_breached")
    if int(loss_audit["weekly_loss_breach_count"]) > 0:
        reasons.append("weekly_loss_limit_breached")
    if broker_statement is None:
        reasons.append("broker_statement_missing")
    elif broker_statement.status != ReadinessStatus.PASS:
        reasons.append("broker_statement_not_reconciled")
    elif broker_statement_freshness_reasons:
        reasons.append("broker_statement_not_current")
    elif not broker_statement_current(
        broker_statement,
        closed_trade_count=closed_trade_count,
        total_net_pl=total_net_pl,
        freshness_reasons=broker_statement_freshness_reasons,
    ):
        reasons.append("broker_statement_not_current")
    if risk_kill_switch_enabled:
        reasons.append("risk_kill_switch_enabled")
    return reasons


def paper_evidence_reasons(
    performance,
    calendar_days_observed: int,
    max_allowed_drawdown: Decimal,
    integrity_audit: dict[str, object],
    journal_audit: dict[str, object],
    coverage_audit: dict[str, object],
) -> list[str]:
    reasons: list[str] = []
    if performance.total_trades < MIN_PAPER_TRADES:
        reasons.append("minimum_paper_trades_not_met")
    if calendar_days_observed < MIN_PAPER_CALENDAR_DAYS:
        reasons.append("minimum_calendar_days_not_met")
    if int(coverage_audit["active_trading_days"]) < MIN_PAPER_ACTIVE_DAYS:
        reasons.append("insufficient_active_trading_days")
    if Decimal(str(coverage_audit["max_single_day_trade_share"])) > MAX_SINGLE_DAY_TRADE_SHARE:
        reasons.append("paper_trade_concentration_too_high")
    if performance.expectancy <= 0:
        reasons.append("expectancy_not_positive")
    if (
        performance.profit_factor is not None
        and performance.profit_factor < MIN_PAPER_PROFIT_FACTOR
    ):
        reasons.append("profit_factor_below_minimum")
    if performance.max_drawdown > max_allowed_drawdown:
        reasons.append("max_drawdown_exceeds_limit")
    if int(integrity_audit["unexplained_trade_count"]) > 0:
        reasons.append("unexplained_trades_present")
    if int(integrity_audit["risk_rule_violation_count"]) > 0:
        reasons.append("risk_rule_violations_present")
    if int(integrity_audit["non_evidence_grade_trade_count"]) > 0:
        reasons.append("non_evidence_grade_paper_fills_present")
    if int(integrity_audit["execution_quality_violation_count"]) > 0:
        reasons.append("paper_execution_quality_violations_present")
    if int(journal_audit["unjournaled_trade_count"]) > 0:
        reasons.append("unjournaled_trades_present")
    if int(journal_audit["journal_rule_violation_count"]) > 0:
        reasons.append("journal_rule_violations_present")
    return reasons


def paper_evidence_coverage_audit(closed_trades: list[PaperTrade]) -> dict[str, object]:
    daily_counts: dict[str, int] = {}
    for trade in closed_trades:
        if trade.closed_at is None:
            continue
        day_key = trade.closed_at.date().isoformat()
        daily_counts[day_key] = daily_counts.get(day_key, 0) + 1

    total_trades = sum(daily_counts.values())
    max_daily_trade_count = max(daily_counts.values(), default=0)
    max_single_day_trade_share = (
        Decimal(max_daily_trade_count) / Decimal(total_trades)
        if total_trades
        else Decimal("0")
    )
    top_days = sorted(
        daily_counts.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )[:10]
    return {
        "active_trading_days": len(daily_counts),
        "minimum_active_trading_days": MIN_PAPER_ACTIVE_DAYS,
        "max_single_day_trade_count": max_daily_trade_count,
        "max_single_day_trade_share": str(max_single_day_trade_share),
        "max_single_day_trade_share_limit": str(MAX_SINGLE_DAY_TRADE_SHARE),
        "daily_trade_counts": dict(sorted(daily_counts.items())),
        "top_trade_count_days": [
            {"date": day_key, "trade_count": count}
            for day_key, count in top_days
        ],
    }


def paper_evidence_scope_audit(
    all_closed_trades: list[PaperTrade],
    scoped_trades: list[PaperTrade],
    plan: LiveDeploymentPlan,
) -> dict[str, object]:
    scoped_ids = {trade.id for trade in scoped_trades}
    out_of_scope = [
        trade for trade in all_closed_trades
        if trade.id not in scoped_ids
    ]
    return {
        "strategy_scope": plan.strategy,
        "symbol_scope": list(plan.symbols or []),
        "in_scope_trade_count": len(scoped_trades),
        "out_of_scope_trade_count": len(out_of_scope),
        "out_of_scope_trades": [
            {
                "trade_id": trade.id,
                "strategy": trade.strategy,
                "symbol": trade.symbol,
                "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
            }
            for trade in out_of_scope[:10]
        ],
    }


def observed_calendar_days(
    first_trade_at: datetime | None,
    latest_trade_at: datetime | None,
) -> int:
    if first_trade_at is None or latest_trade_at is None:
        return 0
    return (latest_trade_at.date() - first_trade_at.date()).days + 1


def performance_snapshot(performance) -> dict[str, object]:
    return {
        "total_trades": performance.total_trades,
        "wins": performance.wins,
        "losses": performance.losses,
        "breakeven": performance.breakeven,
        "win_rate": str(performance.win_rate),
        "expectancy": str(performance.expectancy),
        "profit_factor": str(performance.profit_factor) if performance.profit_factor else None,
        "max_drawdown": str(performance.max_drawdown),
        "total_net_pl": str(performance.total_net_pl),
        "by_strategy": [item.model_dump(mode="json") for item in performance.by_strategy],
        "by_regime": [item.model_dump(mode="json") for item in performance.by_regime],
    }


def explicit_approval_audit(
    *,
    records: list[LiveApprovalRecord],
    current_context: dict[str, object],
    now: datetime,
) -> dict[str, object]:
    latest_by_type: dict[LiveApprovalType, LiveApprovalRecord] = {}
    for record in records:
        latest_by_type[record.approval_type] = record

    approval_snapshot: dict[str, object] = {}
    stale_reasons: list[str] = []
    for approval_type in LiveApprovalType:
        record = latest_by_type.get(approval_type)
        type_key = approval_type.value.lower()
        key = approval_snapshot_key(approval_type)
        is_approved = (
            record is not None
            and record.status == LiveApprovalStatus.APPROVED
            and (record.expires_at is None or record.expires_at > now)
        )
        context_reasons = (
            live_approval_context_stale_reasons(record, current_context)
            if is_approved and record is not None
            else []
        )
        approval_snapshot[key] = bool(is_approved and not context_reasons)
        approval_snapshot[f"{type_key}_approval_record_id"] = record.id if record else None
        approval_snapshot[f"{type_key}_approval_status"] = (
            record.status.value if record else LiveApprovalStatus.PENDING.value
        )
        approval_snapshot[f"{type_key}_approval_context_stale_reasons"] = context_reasons
        stale_reasons.extend(
            f"{type_key}_{reason}" for reason in context_reasons
        )

    required = (
        approval_snapshot.get("broker_approved"),
        approval_snapshot.get("account_approved"),
        approval_snapshot.get("jurisdiction_approved"),
        approval_snapshot.get("live_execution_approved"),
    )
    return {
        "status": ReadinessStatus.PASS if all(required) else ReadinessStatus.BLOCKED,
        "approval_snapshot": approval_snapshot,
        "stale_reasons": sorted(set(stale_reasons)),
        "current_context": current_context,
    }


def live_approval_context_stale_reasons(
    record: LiveApprovalRecord,
    current_context: dict[str, object],
) -> list[str]:
    snapshot = record.evidence_snapshot or {}
    approved_context = snapshot.get("approval_context")
    if not isinstance(approved_context, dict):
        approved_context = {}

    reasons: list[str] = []
    approved_plan = approved_context.get("deployment_plan")
    current_plan = current_context.get("deployment_plan")
    if not isinstance(approved_plan, dict):
        approved_plan = {}
    if isinstance(current_plan, dict):
        for key, current_value in current_plan.items():
            if approved_plan.get(key) != current_value:
                reasons.append(f"deployment_plan_{key}_changed_since_approval")

    approved_artifacts = approved_context.get("artifacts")
    current_artifacts = current_context.get("artifacts")
    if not isinstance(approved_artifacts, dict):
        approved_artifacts = {}
    if isinstance(current_artifacts, dict):
        artifact_reasons = {
            "accepted_backtest_run_id": "accepted_backtest_changed_since_approval",
            "paper_evidence_report_id": "paper_evidence_changed_since_approval",
            "broker_statement_report_id": "broker_statement_changed_since_approval",
        }
        for key, reason in artifact_reasons.items():
            current_value = current_artifacts.get(key)
            if current_value and approved_artifacts.get(key) != current_value:
                reasons.append(reason)

    for key, reason in {
        "strategy_evidence_review_id": "strategy_evidence_review_changed_since_approval",
        "approval_packet_id": "approval_packet_changed_since_approval",
    }.items():
        if current_context.get(key) and approved_context.get(key) != current_context.get(key):
            reasons.append(reason)
    approved_packet = approved_context.get("approval_packet")
    current_packet = current_context.get("approval_packet")
    if not isinstance(approved_packet, dict):
        approved_packet = {}
    if isinstance(current_packet, dict) and approved_packet != current_packet:
        reasons.append("approval_packet_context_changed_since_approval")
    approved_strategy_review = approved_context.get("strategy_evidence_review")
    current_strategy_review = current_context.get("strategy_evidence_review")
    if not isinstance(approved_strategy_review, dict):
        approved_strategy_review = {}
    if isinstance(current_strategy_review, dict):
        if approved_strategy_review != current_strategy_review:
            reasons.append("strategy_evidence_review_context_changed_since_approval")
    return reasons


def live_approval_context_snapshot(
    plan: LiveDeploymentPlan,
    latest_backtest: BacktestRun | None,
    latest_paper_evidence: LivePaperEvidenceReport | None,
    latest_broker_statement: LiveBrokerStatementReport | None,
    latest_strategy_review: StrategyEvidenceReview | None,
    latest_packet: LiveApprovalPacket | None,
    *,
    strategy_review_audit: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "deployment_plan": strategy_review_plan_snapshot(plan),
        "artifacts": current_strategy_evidence_artifacts(
            latest_backtest,
            latest_paper_evidence,
            latest_broker_statement,
        ),
        "strategy_evidence_review_id": (
            latest_strategy_review.id if latest_strategy_review else None
        ),
        "strategy_evidence_review": live_approval_strategy_review_context(
            latest_strategy_review,
            strategy_review_audit,
        ),
        "approval_packet_id": latest_packet.id if latest_packet else None,
        "approval_packet": live_approval_packet_context(latest_packet),
    }


def live_approval_packet_context(
    latest_packet: LiveApprovalPacket | None,
) -> dict[str, object]:
    if latest_packet is None:
        return {
            "approval_packet_id": None,
            "status": None,
            "fingerprint": None,
        }
    return {
        "approval_packet_id": latest_packet.id,
        "status": latest_packet.status.value,
        "fingerprint": live_approval_packet_fingerprint(latest_packet),
    }


def live_approval_packet_fingerprint(packet: LiveApprovalPacket) -> str:
    return stable_snapshot_hash(live_approval_packet_fingerprint_payload(packet))


def live_approval_packet_payload_fingerprint(
    payload: LiveApprovalPacketRequest,
    status: LiveApprovalPacketStatus,
    *,
    broker_connection_id: str | None,
    account_id: str | None,
) -> str:
    return stable_snapshot_hash(
        {
            "broker_connection_id": broker_connection_id,
            "account_id": account_id,
            "status": status.value,
            "broker_name": payload.broker_name.strip(),
            "account_label": payload.account_label.strip(),
            "account_type": payload.account_type.strip(),
            "asset_class": payload.asset_class.strip(),
            "jurisdiction": payload.jurisdiction.strip(),
            "currency": payload.currency.strip().upper(),
            "broker_terms_reference": payload.broker_terms_reference,
            "fee_schedule_reference": payload.fee_schedule_reference,
            "margin_policy_reference": payload.margin_policy_reference,
            "account_constraints_reference": payload.account_constraints_reference,
            "execution_policy_reference": payload.execution_policy_reference,
            "fee_slippage_model_reference": payload.fee_slippage_model_reference,
            "paper_to_live_checklist_reference": (
                payload.paper_to_live_checklist_reference
            ),
            "sandbox_test_reference": payload.sandbox_test_reference,
            "leverage_allowed": payload.leverage_allowed,
            "tax_notes": payload.tax_notes,
            "credentials_stored": payload.credentials_stored,
        }
    )


def live_approval_packet_fingerprint_payload(packet: LiveApprovalPacket) -> dict[str, object]:
    return {
        "broker_connection_id": packet.broker_connection_id,
        "account_id": packet.account_id,
        "status": packet.status.value,
        "broker_name": packet.broker_name,
        "account_label": packet.account_label,
        "account_type": packet.account_type,
        "asset_class": packet.asset_class,
        "jurisdiction": packet.jurisdiction,
        "currency": packet.currency,
        "broker_terms_reference": packet.broker_terms_reference,
        "fee_schedule_reference": packet.fee_schedule_reference,
        "margin_policy_reference": packet.margin_policy_reference,
        "account_constraints_reference": packet.account_constraints_reference,
        "execution_policy_reference": packet.execution_policy_reference,
        "fee_slippage_model_reference": packet.fee_slippage_model_reference,
        "paper_to_live_checklist_reference": packet.paper_to_live_checklist_reference,
        "sandbox_test_reference": packet.sandbox_test_reference,
        "leverage_allowed": packet.leverage_allowed,
        "tax_notes": packet.tax_notes,
        "credentials_stored": packet.credentials_stored,
    }


def live_approval_strategy_review_context(
    latest_strategy_review: StrategyEvidenceReview | None,
    strategy_review_audit: dict[str, object] | None,
) -> dict[str, object]:
    if latest_strategy_review is None:
        return {
            "strategy_evidence_review_id": None,
            "decision": None,
            "gate_status": ReadinessStatus.NOT_RUN.value,
            "freshness_reasons": ["strategy_evidence_review_missing"],
            "current_gate_fingerprints": {},
        }
    audit = strategy_review_audit if isinstance(strategy_review_audit, dict) else {}
    status = audit.get("status")
    return {
        "strategy_evidence_review_id": latest_strategy_review.id,
        "decision": latest_strategy_review.decision.value,
        "gate_status": readiness_status_value(status or ReadinessStatus.NOT_RUN),
        "freshness_reasons": list(audit.get("freshness_reasons") or []),
        "current_gate_fingerprints": dict(audit.get("current_gate_fingerprints") or {}),
    }


def strategy_review_audit_from_gate(
    gate: LiveDeploymentGate | None,
) -> dict[str, object]:
    if gate is None:
        return {
            "status": ReadinessStatus.NOT_RUN,
            "freshness_reasons": ["strategy_evidence_review_gate_missing"],
            "current_gate_fingerprints": {},
        }
    evidence = gate.evidence_snapshot if isinstance(gate.evidence_snapshot, dict) else {}
    return {
        "status": gate.status,
        "freshness_reasons": list(evidence.get("freshness_reasons") or []),
        "current_gate_fingerprints": dict(
            evidence.get("current_gate_fingerprints") or {},
        ),
    }


def daily_review_context_snapshot(
    plan: LiveDeploymentPlan,
    latest_backtest: BacktestRun | None,
    latest_paper_evidence: LivePaperEvidenceReport | None,
    latest_broker_statement: LiveBrokerStatementReport | None,
    latest_strategy_review: StrategyEvidenceReview | None,
    latest_packet: LiveApprovalPacket | None,
    *,
    strategy_review_audit: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "deployment_plan": strategy_review_plan_snapshot(plan),
        "artifacts": current_strategy_evidence_artifacts(
            latest_backtest,
            latest_paper_evidence,
            latest_broker_statement,
        ),
        "strategy_evidence_review_id": (
            latest_strategy_review.id if latest_strategy_review else None
        ),
        "strategy_evidence_review": live_approval_strategy_review_context(
            latest_strategy_review,
            strategy_review_audit,
        ),
        "approval_packet_id": latest_packet.id if latest_packet else None,
        "approval_packet": live_approval_packet_context(latest_packet),
    }


def daily_review_gate_audit(
    review: LiveDailyReviewReport | None,
    current_context: dict[str, object],
) -> dict[str, object]:
    if review is None:
        return {
            "status": ReadinessStatus.NOT_RUN,
            "freshness_reasons": ["daily_review_missing"],
            "reviewed_context": {},
            "current_context": current_context,
        }

    reviewed_context = daily_review_reviewed_context(review)
    freshness_reasons = (
        daily_review_freshness_reasons(reviewed_context, current_context)
        if review.status == LiveDailyReviewStatus.CLEAN
        else []
    )
    status = (
        ReadinessStatus.BLOCKED
        if review.status == LiveDailyReviewStatus.CLEAN and freshness_reasons
        else (
            ReadinessStatus.PASS
            if review.status == LiveDailyReviewStatus.CLEAN
            else ReadinessStatus.NOT_RUN
        )
    )
    return {
        "status": status,
        "freshness_reasons": freshness_reasons,
        "reviewed_context": reviewed_context,
        "current_context": current_context,
    }


def daily_review_reviewed_context(review: LiveDailyReviewReport) -> dict[str, object]:
    snapshot = review.review_snapshot if isinstance(review.review_snapshot, dict) else {}
    context = snapshot.get("review_context")
    return context if isinstance(context, dict) else {}


def daily_review_freshness_reasons(
    reviewed_context: dict[str, object],
    current_context: dict[str, object],
) -> list[str]:
    if not reviewed_context:
        return ["daily_review_missing_review_context"]

    reasons: list[str] = []

    def add_reason(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    reviewed_plan = reviewed_context.get("deployment_plan")
    current_plan = current_context.get("deployment_plan")
    if not isinstance(reviewed_plan, dict):
        reviewed_plan = {}
    if isinstance(current_plan, dict):
        for key, current_value in current_plan.items():
            if reviewed_plan.get(key) != current_value:
                add_reason(f"daily_review_deployment_plan_{key}_changed_since_review")

    reviewed_artifacts = reviewed_context.get("artifacts")
    current_artifacts = current_context.get("artifacts")
    if not isinstance(reviewed_artifacts, dict):
        reviewed_artifacts = {}
    if isinstance(current_artifacts, dict):
        artifact_reasons = {
            "accepted_backtest_run_id": (
                "daily_review_accepted_backtest_changed_since_review"
            ),
            "paper_evidence_report_id": (
                "daily_review_paper_evidence_changed_since_review"
            ),
            "broker_statement_report_id": (
                "daily_review_broker_statement_changed_since_review"
            ),
        }
        for key, reason in artifact_reasons.items():
            if reviewed_artifacts.get(key) != current_artifacts.get(key):
                add_reason(reason)

    if reviewed_context.get("strategy_evidence_review_id") != current_context.get(
        "strategy_evidence_review_id",
    ):
        add_reason("daily_review_strategy_evidence_review_changed_since_review")
    else:
        reviewed_strategy_review = reviewed_context.get("strategy_evidence_review")
        current_strategy_review = current_context.get("strategy_evidence_review")
        if not isinstance(reviewed_strategy_review, dict):
            reviewed_strategy_review = {}
        if (
            isinstance(current_strategy_review, dict)
            and reviewed_strategy_review != current_strategy_review
        ):
            add_reason(
                "daily_review_strategy_evidence_review_context_changed_since_review",
            )

    if reviewed_context.get("approval_packet_id") != current_context.get(
        "approval_packet_id",
    ):
        add_reason("daily_review_approval_packet_changed_since_review")
    else:
        reviewed_packet = reviewed_context.get("approval_packet")
        current_packet = current_context.get("approval_packet")
        if not isinstance(reviewed_packet, dict):
            reviewed_packet = {}
        if isinstance(current_packet, dict) and reviewed_packet != current_packet:
            add_reason("daily_review_approval_packet_context_changed_since_review")

    return reasons


def explicit_approval_status(plan: LiveDeploymentPlan) -> ReadinessStatus:
    approvals = plan.approval_snapshot or {}
    required = (
        approvals.get("broker_approved"),
        approvals.get("account_approved"),
        approvals.get("jurisdiction_approved"),
        approvals.get("live_execution_approved"),
    )
    return ReadinessStatus.PASS if all(required) else ReadinessStatus.BLOCKED


def approval_snapshot_key(approval_type: LiveApprovalType) -> str:
    return {
        LiveApprovalType.BROKER: "broker_approved",
        LiveApprovalType.ACCOUNT: "account_approved",
        LiveApprovalType.JURISDICTION: "jurisdiction_approved",
        LiveApprovalType.LIVE_EXECUTION: "live_execution_approved",
    }[approval_type]
