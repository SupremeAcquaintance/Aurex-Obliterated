from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurex.config.settings import Settings
from aurex.db.models import PaperEvidenceImportBatch, PaperOrder, PaperTrade, Signal
from aurex.domain.enums import ReadinessStatus, TradeStatus
from aurex.live_deployment.service import (
    MIN_PAPER_ACTIVE_DAYS,
    MIN_PAPER_CALENDAR_DAYS,
    MIN_PAPER_TRADES,
    LiveMicroDeploymentService,
)


class PaperEvidenceCollectionStatusService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def status(self) -> dict[str, object]:
        live_service = LiveMicroDeploymentService(self.session, self.settings)
        plan = live_service.get_or_create_default_plan()
        gates = live_service.run_gates(plan)
        latest_report = live_service.latest_paper_evidence_report(plan.id)
        import_summary = self._import_summary(plan)

        backtest_gate = gate_by_key(gates, "accepted_backtest_complete")
        paper_gate = gate_by_key(gates, "paper_evidence_complete")
        accepted_backtest_status = gate_status(backtest_gate)
        paper_evidence_status = gate_status(paper_gate)
        paper_evidence_freshness_reasons = gate_freshness_reasons(paper_gate)

        snapshot = latest_report.evidence_snapshot if latest_report else {}
        total_trades = latest_report.total_trades if latest_report else 0
        minimum_trades = latest_report.minimum_trades if latest_report else MIN_PAPER_TRADES
        calendar_days_observed = (
            latest_report.calendar_days_observed if latest_report else 0
        )
        minimum_calendar_days = (
            latest_report.minimum_calendar_days
            if latest_report
            else MIN_PAPER_CALENDAR_DAYS
        )
        active_trading_days = int(snapshot.get("active_trading_days") or 0)
        minimum_active_trading_days = int(
            snapshot.get("minimum_active_trading_days") or MIN_PAPER_ACTIVE_DAYS
        )
        in_scope_trade_count = int(snapshot.get("in_scope_trade_count") or total_trades)
        out_of_scope_trade_count = int(snapshot.get("out_of_scope_trade_count") or 0)
        evidence_grade_trade_count = int(
            snapshot.get("evidence_grade_trade_count") or 0
        )
        non_evidence_grade_trade_count = int(
            snapshot.get("non_evidence_grade_trade_count") or 0
        )
        execution_quality_violation_count = int(
            snapshot.get("execution_quality_violation_count") or 0
        )
        fill_model_counts = snapshot.get("fill_model_counts")
        fill_model_counts = (
            fill_model_counts if isinstance(fill_model_counts, dict) else {}
        )

        blocking_reasons = collection_blocking_reasons(
            accepted_backtest_status=accepted_backtest_status,
            paper_evidence_status=paper_evidence_status,
            latest_report_reasons=latest_report.reasons if latest_report else [],
            paper_evidence_freshness_reasons=paper_evidence_freshness_reasons,
            latest_report_exists=latest_report is not None,
            imported_batch_count=import_summary["imported_batch_count"],
            scoped_imported_count=import_summary["scoped_imported_count"],
            rejected_count=import_summary["rejected_count"],
            evidence_grade_trade_count=evidence_grade_trade_count,
        )
        trades_remaining = remaining(total_trades, minimum_trades)
        calendar_days_remaining = remaining(calendar_days_observed, minimum_calendar_days)
        active_days_remaining = remaining(active_trading_days, minimum_active_trading_days)

        return {
            "status": (
                ReadinessStatus.PASS
                if accepted_backtest_status == ReadinessStatus.PASS
                and paper_evidence_status == ReadinessStatus.PASS
                else ReadinessStatus.BLOCKED
            ),
            "plan_id": plan.id,
            "strategy": plan.strategy,
            "symbols": list(plan.symbols or []),
            "accepted_backtest_status": accepted_backtest_status,
            "paper_evidence_status": paper_evidence_status,
            "paper_evidence_freshness_reasons": paper_evidence_freshness_reasons,
            "latest_paper_evidence_report_id": latest_report.id if latest_report else None,
            "latest_import_batch_id": import_summary["latest_import_batch_id"],
            "latest_imported_at": import_summary["latest_imported_at"],
            "imported_batch_count": import_summary["imported_batch_count"],
            "rows_received": import_summary["rows_received"],
            "imported_count": import_summary["imported_count"],
            "scoped_imported_count": import_summary["scoped_imported_count"],
            "out_of_scope_imported_count": import_summary["out_of_scope_imported_count"],
            "out_of_scope_import_summary": import_summary["out_of_scope_import_summary"],
            "skipped_count": import_summary["skipped_count"],
            "rejected_count": import_summary["rejected_count"],
            "total_trades": total_trades,
            "minimum_trades": minimum_trades,
            "trades_remaining": trades_remaining,
            "calendar_days_observed": calendar_days_observed,
            "minimum_calendar_days": minimum_calendar_days,
            "calendar_days_remaining": calendar_days_remaining,
            "active_trading_days": active_trading_days,
            "minimum_active_trading_days": minimum_active_trading_days,
            "active_days_remaining": active_days_remaining,
            "max_single_day_trade_share": decimal_from_snapshot(
                snapshot,
                "max_single_day_trade_share",
            ),
            "max_single_day_trade_share_limit": decimal_from_snapshot(
                snapshot,
                "max_single_day_trade_share_limit",
                Decimal("0.25"),
            ),
            "in_scope_trade_count": in_scope_trade_count,
            "out_of_scope_trade_count": out_of_scope_trade_count,
            "evidence_grade_trade_count": evidence_grade_trade_count,
            "non_evidence_grade_trade_count": non_evidence_grade_trade_count,
            "execution_quality_violation_count": execution_quality_violation_count,
            "fill_model_counts": fill_model_counts,
            "unjournaled_trade_count": (
                latest_report.unjournaled_trade_count if latest_report else 0
            ),
            "journal_rule_violation_count": (
                latest_report.journal_rule_violation_count if latest_report else 0
            ),
            "unexplained_trade_count": (
                latest_report.unexplained_trade_count if latest_report else 0
            ),
            "risk_rule_violation_count": (
                latest_report.risk_rule_violation_count if latest_report else 0
            ),
            "blocking_reasons": blocking_reasons,
            "next_actions": collection_next_actions(
                strategy=plan.strategy,
                symbols=list(plan.symbols or []),
                accepted_backtest_status=accepted_backtest_status,
                latest_report_exists=latest_report is not None,
                imported_batch_count=import_summary["imported_batch_count"],
                scoped_imported_count=import_summary["scoped_imported_count"],
                rejected_count=import_summary["rejected_count"],
                paper_evidence_freshness_reasons=paper_evidence_freshness_reasons,
                trades_remaining=trades_remaining,
                calendar_days_remaining=calendar_days_remaining,
                active_days_remaining=active_days_remaining,
                unjournaled_trade_count=(
                    latest_report.unjournaled_trade_count if latest_report else 0
                ),
                journal_rule_violation_count=(
                    latest_report.journal_rule_violation_count if latest_report else 0
                ),
                unexplained_trade_count=(
                    latest_report.unexplained_trade_count if latest_report else 0
                ),
                risk_rule_violation_count=(
                    latest_report.risk_rule_violation_count if latest_report else 0
                ),
                evidence_grade_trade_count=evidence_grade_trade_count,
                non_evidence_grade_trade_count=non_evidence_grade_trade_count,
                execution_quality_violation_count=execution_quality_violation_count,
                paper_evidence_status=paper_evidence_status,
            ),
        }

    def _import_summary(self, plan: object) -> dict[str, object]:
        latest_batch = self.session.execute(
            select(PaperEvidenceImportBatch)
            .order_by(PaperEvidenceImportBatch.imported_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        summary = self.session.execute(
            select(
                func.count(PaperEvidenceImportBatch.id),
                func.coalesce(func.sum(PaperEvidenceImportBatch.rows_received), 0),
                func.coalesce(func.sum(PaperEvidenceImportBatch.imported_count), 0),
                func.coalesce(func.sum(PaperEvidenceImportBatch.skipped_count), 0),
                func.coalesce(func.sum(PaperEvidenceImportBatch.rejected_count), 0),
            )
        ).one()
        scoped_counts = self._scoped_import_counts(plan)
        return {
            "latest_import_batch_id": latest_batch.id if latest_batch else None,
            "latest_imported_at": latest_batch.imported_at if latest_batch else None,
            "imported_batch_count": int(summary[0] or 0),
            "rows_received": int(summary[1] or 0),
            "imported_count": int(summary[2] or 0),
            **scoped_counts,
            "skipped_count": int(summary[3] or 0),
            "rejected_count": int(summary[4] or 0),
        }

    def _scoped_import_counts(self, plan: object) -> dict[str, object]:
        base_query = (
            select(func.count(PaperTrade.id))
            .join(PaperOrder, PaperTrade.paper_order_id == PaperOrder.id)
            .join(Signal, PaperOrder.signal_id == Signal.id)
            .where(
                Signal.idempotency_key.like("paper-import:%"),
                PaperTrade.status == TradeStatus.CLOSED,
                PaperTrade.realized_pl.is_not(None),
            )
        )
        total_imported = int(self.session.execute(base_query).scalar_one() or 0)
        scoped_query = base_query.where(PaperTrade.strategy == plan.strategy)
        symbols = list(plan.symbols or [])
        if symbols:
            scoped_query = scoped_query.where(PaperTrade.symbol.in_(symbols))
        scoped_imported = int(self.session.execute(scoped_query).scalar_one() or 0)
        out_of_scope_summary = self._out_of_scope_import_summary(plan, symbols)
        return {
            "scoped_imported_count": scoped_imported,
            "out_of_scope_imported_count": max(total_imported - scoped_imported, 0),
            "out_of_scope_import_summary": out_of_scope_summary,
        }

    def _out_of_scope_import_summary(
        self,
        plan: object,
        symbols: list[str],
    ) -> list[dict[str, object]]:
        out_of_scope_query = (
            select(
                PaperTrade.strategy,
                PaperTrade.symbol,
                func.count(PaperTrade.id),
            )
            .join(PaperOrder, PaperTrade.paper_order_id == PaperOrder.id)
            .join(Signal, PaperOrder.signal_id == Signal.id)
            .where(
                Signal.idempotency_key.like("paper-import:%"),
                PaperTrade.status == TradeStatus.CLOSED,
                PaperTrade.realized_pl.is_not(None),
            )
        )
        if symbols:
            out_of_scope_query = out_of_scope_query.where(
                (PaperTrade.strategy != plan.strategy)
                | (PaperTrade.symbol.not_in(symbols))
            )
        else:
            out_of_scope_query = out_of_scope_query.where(
                PaperTrade.strategy != plan.strategy,
            )
        rows = self.session.execute(
            out_of_scope_query.group_by(
                PaperTrade.strategy,
                PaperTrade.symbol,
            ).order_by(func.count(PaperTrade.id).desc())
        ).all()
        return [
            {
                "strategy": strategy,
                "symbol": symbol,
                "count": int(count or 0),
            }
            for strategy, symbol, count in rows[:10]
        ]


def gate_by_key(gates: list[object], key: str) -> object | None:
    return next((gate for gate in gates if gate.gate_key == key), None)


def gate_status(gate: object | None) -> ReadinessStatus:
    return gate.status if gate is not None else ReadinessStatus.NOT_RUN


def gate_freshness_reasons(gate: object | None) -> list[str]:
    evidence = getattr(gate, "evidence_snapshot", None)
    if not isinstance(evidence, dict):
        return []
    return [str(reason) for reason in evidence.get("freshness_reasons") or []]


def remaining(current: int, required: int) -> int:
    return max(required - current, 0)


def decimal_from_snapshot(
    snapshot: dict[str, object],
    key: str,
    default: Decimal = Decimal("0"),
) -> Decimal:
    value = snapshot.get(key)
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def collection_blocking_reasons(
    *,
    accepted_backtest_status: ReadinessStatus,
    paper_evidence_status: ReadinessStatus,
    latest_report_reasons: list[object],
    paper_evidence_freshness_reasons: list[str],
    latest_report_exists: bool,
    imported_batch_count: int,
    scoped_imported_count: int,
    rejected_count: int,
    evidence_grade_trade_count: int,
) -> list[str]:
    reasons: list[str] = []
    if evidence_grade_trade_count == 0 and imported_batch_count == 0:
        reasons.append("paper_evidence_import_missing")
    elif evidence_grade_trade_count == 0 and scoped_imported_count == 0:
        reasons.append("paper_evidence_import_scope_missing")
    if accepted_backtest_status != ReadinessStatus.PASS:
        reasons.append("accepted_backtest_missing_or_wrong_scope")
    if not latest_report_exists:
        reasons.append("paper_evidence_report_missing")
    if paper_evidence_status != ReadinessStatus.PASS:
        reasons.extend(str(reason) for reason in latest_report_reasons)
        reasons.extend(paper_evidence_freshness_reasons)
    if rejected_count > 0:
        reasons.append("paper_evidence_rows_rejected")
    return sorted(set(reasons))


def collection_next_actions(
    *,
    strategy: str,
    symbols: list[str],
    accepted_backtest_status: ReadinessStatus,
    latest_report_exists: bool,
    imported_batch_count: int,
    scoped_imported_count: int,
    rejected_count: int,
    paper_evidence_freshness_reasons: list[str],
    trades_remaining: int,
    calendar_days_remaining: int,
    active_days_remaining: int,
    unjournaled_trade_count: int,
    journal_rule_violation_count: int,
    unexplained_trade_count: int,
    risk_rule_violation_count: int,
    evidence_grade_trade_count: int,
    non_evidence_grade_trade_count: int,
    execution_quality_violation_count: int,
    paper_evidence_status: ReadinessStatus,
) -> list[str]:
    actions: list[str] = []
    symbol_text = ", ".join(symbols) if symbols else "the selected symbols"
    if accepted_backtest_status != ReadinessStatus.PASS:
        actions.append(
            f"Store an accepted backtest for {strategy} covering {symbol_text}."
        )
    if evidence_grade_trade_count == 0 and imported_batch_count == 0:
        actions.append(
            "Collect deterministic costed webhook fills or import real paper-platform "
            "CSV evidence."
        )
    elif evidence_grade_trade_count == 0 and scoped_imported_count == 0:
        actions.append(
            f"Import paper-platform evidence for {strategy} covering {symbol_text}."
        )
    if rejected_count > 0:
        actions.append("Correct rejected import rows and re-import the paper evidence export.")
    if paper_evidence_freshness_reasons:
        actions.append(
            "Resolve paper-evidence ledger drift and rerun the Stage 14 paper-evidence "
            "report before broker reconciliation or live review."
        )
    if not latest_report_exists:
        actions.append("Run the Stage 14 paper-evidence report after importing evidence.")
    if trades_remaining > 0:
        actions.append(f"Collect or import {trades_remaining} more in-scope closed trades.")
    if calendar_days_remaining > 0:
        actions.append(
            f"Extend the evidence window by {calendar_days_remaining} calendar days."
        )
    if active_days_remaining > 0:
        actions.append(f"Add evidence from {active_days_remaining} more active trading days.")
    if unjournaled_trade_count > 0:
        actions.append(f"Journal {unjournaled_trade_count} remaining counted trades.")
    if journal_rule_violation_count > 0:
        actions.append("Resolve journaled rule breaks or emotional overrides before readiness.")
    if unexplained_trade_count > 0:
        actions.append("Restore missing signal/risk/order lineage for unexplained trades.")
    if risk_rule_violation_count > 0:
        actions.append("Remove or correct trades with risk-rule violations.")
    if non_evidence_grade_trade_count > 0:
        actions.append(
            "Exclude legacy instant or unverified fills and recollect them with a "
            "hashed execution model."
        )
    if execution_quality_violation_count > 0:
        actions.append(
            "Resolve paper execution assumption, cost, or evidence-hash violations."
        )
    if not actions and paper_evidence_status == ReadinessStatus.PASS:
        actions.append(
            "Proceed to broker statement reconciliation and approval packet review; "
            "live stays disabled."
        )
    return actions
