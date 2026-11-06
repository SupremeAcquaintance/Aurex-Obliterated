import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTAMINATION_LEDGER_SCHEMA_VERSION = "aurex-strategy-contamination-ledger-v1"
ContaminationClassification = Literal[
    "DEVELOPMENT_CONTAMINATED",
    "EXPLORATORY_CONTAMINATED",
    "HOLDOUT_OPENED_RETIRED",
]


class StrategyContaminationRecord(BaseModel):
    record_id: str = Field(min_length=1, max_length=128)
    strategy_family: str = Field(min_length=1, max_length=128)
    strategy: str = Field(min_length=1, max_length=128)
    strategy_version: str = Field(min_length=1, max_length=64)
    symbols: list[str] = Field(min_length=1)
    timeframes: list[str] = Field(min_length=1)
    window_start: datetime
    window_end: datetime
    first_observed_at: datetime
    classification: ContaminationClassification
    outcome_fields_inspected: list[str] = Field(min_length=1)
    evidence_references: list[str] = Field(min_length=1)
    source_evidence_hashes: dict[str, str] = Field(default_factory=dict)
    reason: str = Field(min_length=10, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip().upper() for item in value if item.strip()})
        if not normalized:
            raise ValueError("Contamination symbols cannot be blank")
        return normalized

    @field_validator("timeframes")
    @classmethod
    def normalize_timeframes(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip().lower() for item in value if item.strip()})
        if not normalized:
            raise ValueError("Contamination timeframes cannot be blank")
        return normalized

    @field_validator("window_start", "window_end", "first_observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Contamination timestamps must include a timezone")
        return value.astimezone(UTC)

    @field_validator("outcome_fields_inspected", "evidence_references")
    @classmethod
    def normalize_nonempty_list(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if not normalized:
            raise ValueError("Contamination evidence lists cannot be blank")
        return normalized

    @field_validator("source_evidence_hashes")
    @classmethod
    def validate_source_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, evidence_hash in value.items():
            label = key.strip()
            candidate = evidence_hash.strip().lower()
            if not label:
                raise ValueError("Contamination hash labels cannot be blank")
            if len(candidate) != 64 or any(char not in "0123456789abcdef" for char in candidate):
                raise ValueError("Contamination evidence hashes must be SHA-256 values")
            if label in normalized:
                raise ValueError("Contamination hash labels must be unique after normalization")
            normalized[label] = candidate
        return dict(sorted(normalized.items()))

    @model_validator(mode="after")
    def validate_window(self) -> "StrategyContaminationRecord":
        if self.window_end <= self.window_start:
            raise ValueError("Contamination window end must be later than its start")
        if self.first_observed_at < self.window_start:
            raise ValueError("First observation cannot precede the contaminated window")
        return self


class StrategyContaminationLedger(BaseModel):
    schema_version: Literal["aurex-strategy-contamination-ledger-v1"] = (
        CONTAMINATION_LEDGER_SCHEMA_VERSION
    )
    records: list[StrategyContaminationRecord]
    ledger_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_records(self) -> "StrategyContaminationLedger":
        record_ids = [record.record_id for record in self.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("Contamination record IDs must be unique")
        if record_ids != sorted(record_ids):
            raise ValueError("Contamination records must be sorted by record ID")
        return self


def build_contamination_ledger(
    records: list[StrategyContaminationRecord],
) -> StrategyContaminationLedger:
    ordered = sorted(records, key=lambda record: record.record_id)
    record_ids = [record.record_id for record in ordered]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Contamination record IDs must be unique")
    payload = {
        "schema_version": CONTAMINATION_LEDGER_SCHEMA_VERSION,
        "records": ordered,
    }
    return StrategyContaminationLedger(
        **payload,
        ledger_evidence_hash=contamination_evidence_hash(payload),
    )


def audit_contamination_ledger(ledger: StrategyContaminationLedger) -> bool:
    payload = {
        "schema_version": ledger.schema_version,
        "records": ledger.records,
    }
    return ledger.ledger_evidence_hash == contamination_evidence_hash(payload)


def contamination_reasons(
    ledger: StrategyContaminationLedger,
    *,
    strategy_family: str,
    symbol: str,
    timeframe: str,
    window_start: datetime,
    window_end: datetime,
) -> list[str]:
    start = normalize_query_timestamp(window_start)
    end = normalize_query_timestamp(window_end)
    if end <= start:
        raise ValueError("Contamination query end must be later than its start")
    normalized_family = strategy_family.strip()
    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip().lower()
    return [
        record.record_id
        for record in ledger.records
        if record.strategy_family == normalized_family
        and normalized_symbol in record.symbols
        and normalized_timeframe in record.timeframes
        and record.window_start < end
        and start < record.window_end
    ]


def normalize_query_timestamp(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("Contamination query timestamps must include a timezone")
    return value.astimezone(UTC)


def contamination_evidence_hash(payload: object) -> str:
    serialized = json.dumps(
        canonical_value(payload),
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def canonical_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump())
    if isinstance(value, dict):
        return {
            str(key): canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value
