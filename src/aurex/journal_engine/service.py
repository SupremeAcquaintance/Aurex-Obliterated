from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.db.base import utc_now
from aurex.db.models import PaperTrade, TradeJournalEntry
from aurex.journal_engine.schemas import TradeJournalEntryRequest
from aurex.observability.system_events import SystemEventRecorder


class TradeJournalService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_entry(self, payload: TradeJournalEntryRequest) -> TradeJournalEntry:
        trade = self.session.get(PaperTrade, payload.paper_trade_id)
        if trade is None:
            raise ValueError("Paper trade not found")

        entry = TradeJournalEntry(
            paper_trade=trade,
            author=payload.author.strip(),
            thesis=payload.thesis.strip(),
            execution_notes=payload.execution_notes,
            outcome_notes=payload.outcome_notes,
            rule_followed=payload.rule_followed,
            emotional_override=payload.emotional_override,
            evidence_snapshot={
                **payload.evidence_snapshot,
                "paper_trade_id": trade.id,
                "symbol": trade.symbol,
                "strategy": trade.strategy,
                "status": trade.status.value,
                "realized_pl": str(trade.realized_pl) if trade.realized_pl is not None else None,
            },
            journaled_at=payload.journaled_at or utc_now(),
        )
        self.session.add(entry)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "trade_journal",
            "Trade journal entry recorded",
            {
                "trade_journal_entry_id": entry.id,
                "paper_trade_id": trade.id,
                "rule_followed": entry.rule_followed,
                "emotional_override": entry.emotional_override,
            },
        )
        self.session.flush()
        return entry

    def list_entries(
        self,
        paper_trade_id: str | None = None,
        limit: int = 100,
    ) -> list[TradeJournalEntry]:
        statement = select(TradeJournalEntry).order_by(TradeJournalEntry.journaled_at.desc())
        if paper_trade_id:
            statement = statement.where(TradeJournalEntry.paper_trade_id == paper_trade_id)
        return list(self.session.execute(statement.limit(limit)).scalars())
