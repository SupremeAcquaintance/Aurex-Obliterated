from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.analyst_engine.schemas import (
    AnalystScanResponse,
    AnalystSummaryResponse,
    PatternSimilarityResponse,
    SimilarTradeItem,
)
from aurex.db.base import utc_now
from aurex.db.models import AnalystNote, PaperTrade
from aurex.domain.enums import AnalystNoteType, SystemEventSeverity, TradeStatus
from aurex.observability.system_events import SystemEventRecorder

ZERO = Decimal("0")
ONE = Decimal("1")


class AnalystEngine:
    def __init__(self, session: Session) -> None:
        self.session = session

    def summary(self, limit: int = 5) -> AnalystSummaryResponse:
        closed_trades = self._closed_trades()
        notes = self._latest_notes(limit=limit)
        all_notes = self._all_notes()
        warning_count = sum(1 for note in all_notes if note.severity == SystemEventSeverity.WARNING)
        critical_count = sum(
            1 for note in all_notes if note.severity == SystemEventSeverity.CRITICAL
        )

        if not closed_trades:
            headline = "No closed paper trades available for analyst review."
        else:
            expectancy = self._expectancy(closed_trades)
            headline = (
                f"{len(closed_trades)} closed trades reviewed. "
                f"Current expectancy is {expectancy:.8f}."
            )

        return AnalystSummaryResponse(
            advisory_only=True,
            closed_trades=len(closed_trades),
            note_count=len(all_notes),
            warning_count=warning_count,
            critical_count=critical_count,
            latest_notes=notes,
            headline=headline,
            evidence_snapshot={
                "closed_trades": len(closed_trades),
                "advisory_only": True,
                "execution_authority": "none",
            },
        )

    def review_trade(self, trade_id: str) -> AnalystNote:
        trade = self._get_trade(trade_id)
        severity = SystemEventSeverity.INFO
        r_multiple = trade.r_multiple or ZERO
        fees_and_slippage = (trade.fees or ZERO) + (trade.slippage or ZERO)

        if r_multiple <= Decimal("-1.25"):
            severity = SystemEventSeverity.WARNING
            title = "Oversized losing trade review"
            recommendation = "Review stop execution, slippage assumptions, and strategy fit."
        elif trade.realized_pl is not None and trade.realized_pl < 0:
            title = "Losing trade review"
            recommendation = "Compare against similar trades before changing strategy parameters."
        elif trade.realized_pl is not None and trade.realized_pl > 0:
            title = "Winning trade review"
            recommendation = (
                "Keep the rule set unchanged unless repeated evidence supports adjustment."
            )
        else:
            title = "Breakeven trade review"
            recommendation = "Check fees, slippage, and opportunity cost."

        if trade.risk_amount and fees_and_slippage >= trade.risk_amount * Decimal("0.25"):
            severity = SystemEventSeverity.WARNING
            recommendation = "Execution costs consumed a large share of planned risk."

        summary = (
            f"{trade.strategy} {trade.direction.value} on {trade.symbol} closed with "
            f"{trade.realized_pl or ZERO} realized P/L and {r_multiple}R."
        )

        return self._create_note(
            trade=trade,
            note_type=AnalystNoteType.TRADE_REVIEW,
            severity=severity,
            title=title,
            summary=summary,
            recommendation=recommendation,
            confidence=Decimal("0.75"),
            evidence_snapshot=trade_evidence(trade),
        )

    def pattern_similarity(self, trade_id: str, limit: int = 5) -> PatternSimilarityResponse:
        source = self._get_trade(trade_id)
        candidates = [
            trade
            for trade in self._closed_trades()
            if trade.id != source.id and trade.strategy == source.strategy
        ]
        similar_items = sorted(
            [self._similar_trade_item(source, candidate) for candidate in candidates],
            key=lambda item: item.similarity_score,
            reverse=True,
        )[:limit]
        note = self._create_note(
            trade=source,
            note_type=AnalystNoteType.PATTERN_SIMILARITY,
            severity=SystemEventSeverity.INFO,
            title="Similar trade pattern review",
            summary=f"Found {len(similar_items)} similar closed trades for {source.strategy}.",
            recommendation="Use similar outcomes as context, not as permission to trade.",
            confidence=Decimal("0.70") if similar_items else Decimal("0.40"),
            evidence_snapshot={
                "source_trade": trade_evidence(source),
                "similar_trade_ids": [item.trade_id for item in similar_items],
                "advisory_only": True,
            },
        )
        return PatternSimilarityResponse(
            advisory_only=True,
            source_trade_id=source.id,
            similar_trades=similar_items,
            note=note,
        )

    def scan_risk_anomalies(
        self,
        strategy: str | None = None,
        limit: int = 100,
    ) -> AnalystScanResponse:
        trades = self._closed_trades(strategy=strategy, limit=limit)
        created: list[AnalystNote] = []
        for trade in trades:
            r_multiple = trade.r_multiple or ZERO
            fees_and_slippage = (trade.fees or ZERO) + (trade.slippage or ZERO)
            cost_ratio = fees_and_slippage / trade.risk_amount if trade.risk_amount else ZERO
            reasons: list[str] = []
            if r_multiple <= Decimal("-1.25"):
                reasons.append("loss exceeded planned risk")
            if cost_ratio >= Decimal("0.25"):
                reasons.append("costs consumed at least 25% of planned risk")
            if trade.realized_pl is None or trade.r_multiple is None:
                reasons.append("closed trade is missing analysis fields")

            if not reasons:
                continue

            created.append(
                self._create_note(
                    trade=trade,
                    note_type=AnalystNoteType.RISK_ANOMALY,
                    severity=SystemEventSeverity.WARNING,
                    title="Risk anomaly detected",
                    summary=f"{trade.strategy} on {trade.symbol}: {', '.join(reasons)}.",
                    recommendation=(
                        "Review execution quality before increasing size "
                        "or enabling live readiness."
                    ),
                    confidence=Decimal("0.85"),
                    evidence_snapshot={
                        **trade_evidence(trade),
                        "cost_ratio": str(cost_ratio),
                        "reasons": reasons,
                    },
                )
            )

        message = (
            f"Created {len(created)} risk anomaly notes."
            if created
            else "No risk anomalies detected in scanned trades."
        )
        return AnalystScanResponse(
            advisory_only=True,
            created_notes=created,
            scanned_trades=len(trades),
            message=message,
        )

    def scan_strategy_degradation(
        self,
        strategy: str | None = None,
        limit: int = 100,
    ) -> AnalystScanResponse:
        trades = self._closed_trades(strategy=strategy, limit=limit)
        by_strategy: dict[str, list[PaperTrade]] = defaultdict(list)
        for trade in trades:
            by_strategy[trade.strategy].append(trade)

        created: list[AnalystNote] = []
        for strategy_name, strategy_trades in by_strategy.items():
            if len(strategy_trades) < 10:
                continue

            ordered = sorted(
                strategy_trades,
                key=lambda trade: sort_datetime(trade.closed_at or trade.opened_at),
            )
            midpoint = len(ordered) // 2
            baseline = ordered[:midpoint]
            recent = ordered[midpoint:]
            baseline_expectancy = self._expectancy(baseline)
            recent_expectancy = self._expectancy(recent)
            recent_loss_rate = self._loss_rate(recent)
            should_flag = (
                baseline_expectancy > ZERO
                and recent_expectancy < ZERO
                and recent_loss_rate >= Decimal("0.5")
            )
            if not should_flag:
                continue

            created.append(
                self._create_note(
                    trade=recent[-1],
                    note_type=AnalystNoteType.STRATEGY_DEGRADATION,
                    severity=SystemEventSeverity.WARNING,
                    title="Strategy degradation warning",
                    summary=(
                        f"{strategy_name} recent expectancy fell from "
                        f"{baseline_expectancy:.8f} to {recent_expectancy:.8f}."
                    ),
                    recommendation=(
                        "Pause parameter expansion and review recent trades before adding exposure."
                    ),
                    confidence=Decimal("0.80"),
                    evidence_snapshot={
                        "strategy": strategy_name,
                        "baseline_trades": len(baseline),
                        "recent_trades": len(recent),
                        "baseline_expectancy": str(baseline_expectancy),
                        "recent_expectancy": str(recent_expectancy),
                        "recent_loss_rate": str(recent_loss_rate),
                        "advisory_only": True,
                    },
                )
            )

        message = (
            f"Created {len(created)} strategy degradation notes."
            if created
            else "No strategy degradation detected with the current evidence."
        )
        return AnalystScanResponse(
            advisory_only=True,
            created_notes=created,
            scanned_trades=len(trades),
            message=message,
        )

    def list_notes(self, limit: int = 50) -> list[AnalystNote]:
        return self._latest_notes(limit=limit)

    def _get_trade(self, trade_id: str) -> PaperTrade:
        trade = self.session.get(PaperTrade, trade_id)
        if trade is None:
            raise ValueError("Paper trade not found")
        if trade.status != TradeStatus.CLOSED:
            raise ValueError("Analyst review requires a closed paper trade")
        return trade

    def _closed_trades(
        self,
        strategy: str | None = None,
        limit: int | None = None,
    ) -> list[PaperTrade]:
        statement = (
            select(PaperTrade)
            .where(PaperTrade.status == TradeStatus.CLOSED)
            .order_by(PaperTrade.closed_at.desc(), PaperTrade.opened_at.desc())
        )
        if strategy is not None:
            statement = statement.where(PaperTrade.strategy == strategy)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.execute(statement).scalars())

    def _latest_notes(self, limit: int) -> list[AnalystNote]:
        return list(
            self.session.execute(
                select(AnalystNote)
                .order_by(AnalystNote.generated_at.desc())
                .limit(limit)
            ).scalars()
        )

    def _all_notes(self) -> list[AnalystNote]:
        return list(self.session.execute(select(AnalystNote)).scalars())

    def _create_note(
        self,
        *,
        trade: PaperTrade | None,
        note_type: AnalystNoteType,
        severity: SystemEventSeverity,
        title: str,
        summary: str,
        recommendation: str | None,
        confidence: Decimal,
        evidence_snapshot: dict,
    ) -> AnalystNote:
        note = AnalystNote(
            trade=trade,
            strategy=trade.strategy if trade else evidence_snapshot.get("strategy"),
            symbol=trade.symbol if trade else evidence_snapshot.get("symbol"),
            note_type=note_type,
            severity=severity,
            title=title,
            summary=summary,
            recommendation=recommendation,
            confidence=confidence,
            evidence_snapshot={**evidence_snapshot, "advisory_only": True},
            model_name="deterministic_v1",
            advisory_only=True,
            generated_at=utc_now(),
        )
        self.session.add(note)
        SystemEventRecorder(self.session).info(
            "analyst_engine",
            "Analyst note created",
            {
                "note_type": note_type.value,
                "trade_id": trade.id if trade else None,
                "strategy": note.strategy,
                "severity": severity.value,
                "advisory_only": True,
            },
        )
        self.session.flush()
        return note

    def _similar_trade_item(self, source: PaperTrade, candidate: PaperTrade) -> SimilarTradeItem:
        score = Decimal("0.35")
        if candidate.symbol == source.symbol:
            score += Decimal("0.15")
        if candidate.timeframe == source.timeframe:
            score += Decimal("0.10")
        if candidate.market_regime == source.market_regime:
            score += Decimal("0.15")
        if candidate.direction == source.direction:
            score += Decimal("0.10")
        if candidate.r_multiple is not None and source.r_multiple is not None:
            distance = min(abs(candidate.r_multiple - source.r_multiple), ONE)
            score += (ONE - distance) * Decimal("0.15")

        return SimilarTradeItem(
            trade_id=candidate.id,
            strategy=candidate.strategy,
            symbol=candidate.symbol,
            timeframe=candidate.timeframe,
            market_regime=candidate.market_regime.value,
            direction=candidate.direction.value,
            realized_pl=candidate.realized_pl,
            r_multiple=candidate.r_multiple,
            similarity_score=min(score, ONE),
        )

    def _expectancy(self, trades: list[PaperTrade]) -> Decimal:
        values = [trade.realized_pl or ZERO for trade in trades]
        if not values:
            return ZERO
        return sum(values, ZERO) / Decimal(len(values))

    def _loss_rate(self, trades: list[PaperTrade]) -> Decimal:
        if not trades:
            return ZERO
        losses = sum(1 for trade in trades if (trade.realized_pl or ZERO) < ZERO)
        return Decimal(losses) / Decimal(len(trades))


def trade_evidence(trade: PaperTrade) -> dict[str, object]:
    return {
        "trade_id": trade.id,
        "strategy": trade.strategy,
        "symbol": trade.symbol,
        "timeframe": trade.timeframe,
        "direction": trade.direction.value,
        "market_regime": trade.market_regime.value,
        "entry_price": str(trade.entry_price),
        "exit_price": str(trade.exit_price) if trade.exit_price is not None else None,
        "realized_pl": str(trade.realized_pl) if trade.realized_pl is not None else None,
        "r_multiple": str(trade.r_multiple) if trade.r_multiple is not None else None,
        "risk_amount": str(trade.risk_amount),
        "fees": str(trade.fees),
        "slippage": str(trade.slippage),
        "close_reason": trade.close_reason,
    }


def sort_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
