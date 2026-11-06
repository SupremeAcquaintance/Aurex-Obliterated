from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_diagnostic_addendum import (
    R3MonthlyDiagnosticAddendum,
    audit_r3_monthly_diagnostic_addendum,
)
from aurex.backtest_engine.research_result import R3StudyResultLedger
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.audit_r3_monthly_returns import authoritative_addendum


def addendum() -> R3MonthlyDiagnosticAddendum:
    ledger = R3StudyResultLedger.model_validate_json(
        Path("data/evidence/r3_cross_sectional_momentum_result_v1.json").read_text(
            encoding="utf-8"
        )
    )
    return authoritative_addendum(
        generated_at=datetime(2026, 7, 22, 21, tzinfo=UTC),
        evidence_root=Path("data/evidence"),
        ledger=ledger,
    )


def rehash(payload: dict) -> dict:
    payload["addendum_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "addendum_evidence_hash"
        }
    )
    return payload


def test_monthly_addendum_corrects_only_diagnostic_boundaries() -> None:
    frozen = addendum()

    assert frozen.original_month_count == 19
    assert frozen.corrected_month_count == 18
    assert "2025-01" in frozen.original_monthly_net_returns
    assert list(frozen.corrected_monthly_net_returns) == [
        f"{year}-{month:02d}"
        for year, months in [(2023, range(7, 13)), (2024, range(1, 13))]
        for month in months
    ]
    assert frozen.affected_gate_ids == []
    assert frozen.original_verdict == "NO_CANDIDATE"
    assert frozen.corrected_verdict == "NO_CANDIDATE"
    assert audit_r3_monthly_diagnostic_addendum(frozen) is True
    assert R3MonthlyDiagnosticAddendum.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_monthly_addendum_refuses_gate_or_verdict_changes() -> None:
    payload = addendum().model_dump()
    payload["affected_gate_ids"] = ["primary_net_pl"]
    payload["corrected_verdict"] = "ADVANCE_PRIMARY_TO_R4"

    with pytest.raises(ValidationError, match="cannot alter an advancement gate"):
        R3MonthlyDiagnosticAddendum.model_validate(rehash(payload))
