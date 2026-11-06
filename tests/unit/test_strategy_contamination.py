from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    StrategyContaminationRecord,
    audit_contamination_ledger,
    build_contamination_ledger,
    contamination_reasons,
)


def record(
    record_id: str,
    *,
    symbol: str = "btcusdt",
    timeframe: str = "4H",
) -> StrategyContaminationRecord:
    return StrategyContaminationRecord(
        record_id=record_id,
        strategy_family="slow_trend_breakout_spot",
        strategy="slow_breakout_spot_v1",
        strategy_version="1.0.0",
        symbols=[symbol],
        timeframes=[timeframe],
        window_start="2023-01-01T00:00:00Z",
        window_end="2026-07-01T00:00:00Z",
        first_observed_at="2026-07-22T12:08:32Z",
        classification="HOLDOUT_OPENED_RETIRED",
        outcome_fields_inspected=["profit_factor", "net_pl"],
        evidence_references=["reference-replay:test"],
        source_evidence_hashes={"dataset": "a" * 64},
        reason="Held-out outcome was opened and the candidate was retired.",
    )


def test_ledger_is_sorted_hash_stable_and_auditable() -> None:
    second = record("slow-sol", symbol="solusdt")
    first = record("slow-eth", symbol="ethusdt")

    ledger = build_contamination_ledger([second, first])
    repeated = build_contamination_ledger([first, second])

    assert [item.record_id for item in ledger.records] == ["slow-eth", "slow-sol"]
    assert ledger.ledger_evidence_hash == repeated.ledger_evidence_hash
    assert audit_contamination_ledger(ledger) is True
    assert ledger.records[0].symbols == ["ETHUSDT"]
    assert ledger.records[0].timeframes == ["4h"]


def test_audit_detects_record_tampering() -> None:
    ledger = build_contamination_ledger([record("slow-eth", symbol="ethusdt")])
    payload = ledger.model_dump()
    payload["records"][0]["reason"] = "Changed after hashing."
    tampered = StrategyContaminationLedger.model_validate(payload)

    assert audit_contamination_ledger(tampered) is False


def test_overlap_query_matches_only_family_symbol_timeframe_and_time() -> None:
    ledger = build_contamination_ledger([record("slow-eth", symbol="ethusdt")])

    reasons = contamination_reasons(
        ledger,
        strategy_family="slow_trend_breakout_spot",
        symbol="ETHUSDT",
        timeframe="4h",
        window_start=datetime(2025, 1, 1, tzinfo=UTC),
        window_end=datetime(2025, 2, 1, tzinfo=UTC),
    )
    wrong_family = contamination_reasons(
        ledger,
        strategy_family="range_mean_reversion",
        symbol="ETHUSDT",
        timeframe="4h",
        window_start=datetime(2025, 1, 1, tzinfo=UTC),
        window_end=datetime(2025, 2, 1, tzinfo=UTC),
    )

    assert reasons == ["slow-eth"]
    assert wrong_family == []


def test_duplicate_record_ids_are_refused() -> None:
    with pytest.raises(ValueError, match="record IDs must be unique"):
        build_contamination_ledger([record("duplicate"), record("duplicate")])


def test_naive_timestamps_are_refused() -> None:
    payload = record("slow-eth").model_dump()
    payload["window_start"] = datetime(2023, 1, 1)

    with pytest.raises(ValidationError, match="must include a timezone"):
        StrategyContaminationRecord.model_validate(payload)


def test_authoritative_contamination_artifact_is_hash_valid() -> None:
    ledger = StrategyContaminationLedger.model_validate_json(
        Path("data/evidence/strategy_contamination_ledger_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert audit_contamination_ledger(ledger) is True
    assert len(ledger.records) == 6
    assert contamination_reasons(
        ledger,
        strategy_family="slow_trend_breakout_spot",
        symbol="ETHUSDT",
        timeframe="4h",
        window_start=datetime(2025, 1, 1, tzinfo=UTC),
        window_end=datetime(2025, 2, 1, tzinfo=UTC),
    ) == ["slow-breakout-eth-holdout-2023-2026"]


def test_v2_contamination_artifact_extends_frozen_v1() -> None:
    v1 = StrategyContaminationLedger.model_validate_json(
        Path("data/evidence/strategy_contamination_ledger_v1.json").read_text(
            encoding="utf-8"
        )
    )
    v2 = StrategyContaminationLedger.model_validate_json(
        Path("data/evidence/strategy_contamination_ledger_v2.json").read_text(
            encoding="utf-8"
        )
    )

    assert audit_contamination_ledger(v1) is True
    assert audit_contamination_ledger(v2) is True
    assert len(v1.records) == 6
    assert len(v2.records) == 7
    jam_record_id = "jam-reversal-spot-btc-15m-2023-2026"
    assert [record for record in v2.records if record.record_id != jam_record_id] == (
        v1.records
    )
    assert [record.record_id for record in v2.records].count(jam_record_id) == 1
