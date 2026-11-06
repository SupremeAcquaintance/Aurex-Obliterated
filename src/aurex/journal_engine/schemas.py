from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TradeJournalEntryRequest(BaseModel):
    paper_trade_id: str = Field(min_length=1)
    author: str = Field(min_length=1, max_length=120)
    thesis: str = Field(min_length=1, max_length=2000)
    execution_notes: str | None = Field(default=None, max_length=2000)
    outcome_notes: str | None = Field(default=None, max_length=2000)
    rule_followed: bool = True
    emotional_override: bool = False
    evidence_snapshot: dict = Field(default_factory=dict)
    journaled_at: datetime | None = None


class TradeJournalEntryResponse(BaseModel):
    id: str
    paper_trade_id: str
    author: str
    thesis: str
    execution_notes: str | None
    outcome_notes: str | None
    rule_followed: bool
    emotional_override: bool
    evidence_snapshot: dict
    journaled_at: datetime

    model_config = ConfigDict(from_attributes=True)
