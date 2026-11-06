from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_successor_event_outcome_protocol import (
    JamEventCondition,
    JamSuccessorEventOutcomeProtocol,
)
from aurex.backtest_engine.jam_successor_event_prevalence import (
    JAM_PREVALENCE_FAIL_DECISION,
    JAM_PREVALENCE_NO_NEXT_AUTHORIZATION,
    JAM_PREVALENCE_PASS_DECISION,
    JamDevelopmentEventLedgerRecord,
    JamPrevalenceInputRow,
    JamSuccessorDevelopmentEventPrevalenceAudit,
    JamSuccessorDevelopmentEventPrevalenceProtocol,
    JamSuccessorDevelopmentEventPrevalenceResult,
    audit_jam_successor_prevalence_audit,
    audit_jam_successor_prevalence_protocol,
    audit_jam_successor_prevalence_result,
    build_event_ledger,
    build_jam_successor_prevalence_protocol,
    build_jam_successor_prevalence_result,
    build_prevalence_gate_results,
    event_row_matches,
    validate_event_ledger,
)
from scripts.run_jam_successor_development_event_prevalence import _event_query

ROOT = Path(__file__).resolve().parents[2]
PARENT_PROTOCOL = (
    ROOT / "data/evidence/jam_successor_event_outcome_protocol_v1.json"
)
CANONICAL_PROTOCOL = (
    ROOT
    / "data/evidence/jam_successor_development_event_prevalence_protocol_v1.json"
)
CANONICAL_RESULT = (
    ROOT
    / "data/evidence/jam_successor_development_event_prevalence_result_v1.json"
)
CANONICAL_LEDGER = (
    ROOT / "data/evidence/jam_successor_development_event_ledger_v1.jsonl"
)
CANONICAL_AUDIT = (
    ROOT
    / "data/evidence/jam_successor_development_event_prevalence_audit_v1.json"
)
HASH = "0" * 64


@cache
def parent_protocol() -> JamSuccessorEventOutcomeProtocol:
    return JamSuccessorEventOutcomeProtocol.model_validate_json(
        PARENT_PROTOCOL.read_text(encoding="utf-8")
    )


def conditions() -> list[JamEventCondition]:
    return parent_protocol().event_definition.conditions


def limitations() -> list[str]:
    return [f"Frozen prevalence limitation {index}" for index in range(1, 14)]


def event_row(
    minute: int,
    **overrides: Decimal,
) -> JamPrevalenceInputRow:
    timestamp = datetime(2019, 1, 1, tzinfo=UTC)
    values = {
        item.feature_id: Decimal(item.frozen_threshold) for item in conditions()
    }
    values.update(overrides)
    return JamPrevalenceInputRow(
        open_time_ms=int(timestamp.timestamp() * 1_000) + minute * 60_000,
        month="2019-01",
        **values,
    )


def prevalence_protocol() -> JamSuccessorDevelopmentEventPrevalenceProtocol:
    parent = parent_protocol()
    return build_jam_successor_prevalence_protocol(
        frozen_at=datetime(2026, 8, 5, tzinfo=UTC),
        parent_event_protocol_path=(
            "data/evidence/jam_successor_event_outcome_protocol_v1.json"
        ),
        parent_event_protocol_file_sha256=HASH,
        parent_event_protocol_evidence_hash=parent.protocol_evidence_hash,
        parent_event_audit_path=(
            "data/evidence/jam_successor_event_outcome_protocol_audit_v1.json"
        ),
        parent_event_audit_file_sha256=HASH,
        parent_event_audit_evidence_hash=HASH,
        feature_rows_path=(
            "data/evidence/jam_successor_development_feature_rows_v1.parquet"
        ),
        feature_rows_file_sha256=parent.feature_rows_file_sha256,
        feature_rows_schema_hash=parent.feature_rows_schema_hash,
        feature_rows_bytes=parent.feature_rows_bytes,
        event_conditions=conditions(),
        builder_contract_hash=HASH,
        limitations=limitations(),
    )


def prevalence_result():
    records = build_event_ledger(
        [event_row(0), event_row(59), event_row(60)],
        conditions=conditions(),
    )
    return build_jam_successor_prevalence_result(
        records=records,
        generated_at=datetime(2026, 8, 5, tzinfo=UTC),
        protocol_evidence_hash=HASH,
        runner_contract_hash=HASH,
        parent_event_protocol_evidence_hash=(
            parent_protocol().protocol_evidence_hash
        ),
        feature_rows_file_sha256=parent_protocol().feature_rows_file_sha256,
        feature_rows_schema_hash=parent_protocol().feature_rows_schema_hash,
        event_ledger_file_sha256=HASH,
        event_ledger_bytes=1,
        limitations=limitations(),
    )


def test_frozen_event_predicate_uses_exact_boundaries_and_all_five_conditions():
    expected = {
        "shock_sell_flow_robust_z_5m": "4.625575808694040576",
        "shock_sell_share_5m": "0.495418809496035904",
        "shock_price_impact_bps_5m": "-8.269710038582845440",
        "sell_flow_decay_ratio_3m_vs_5m": "0.938264464494273536",
        "reclaim_bps_vs_pre_shock_vwap": "0.389389126850270272",
    }
    assert {
        item.feature_id: item.frozen_threshold for item in conditions()
    } == expected
    assert event_row_matches(event_row(0), conditions())
    for condition in conditions():
        threshold = Decimal(condition.frozen_threshold)
        outside = (
            threshold - Decimal("0.000000000000000001")
            if condition.comparison == "GREATER_THAN_OR_EQUAL"
            else threshold + Decimal("0.000000000000000001")
        )
        assert not event_row_matches(
            event_row(0, **{condition.feature_id: outside}),
            conditions(),
        )


def test_suppression_is_chronological_and_does_not_reset_at_sixty_minutes():
    records = build_event_ledger(
        [
            event_row(0),
            event_row(59),
            event_row(60),
            event_row(119),
            event_row(120),
        ],
        conditions=conditions(),
    )
    assert [record.accepted for record in records] == [
        True,
        False,
        True,
        False,
        True,
    ]
    assert [
        record.accepted_event_sequence for record in records
    ] == [1, None, 2, None, 3]
    assert records[1].prior_accepted_open_time_ms == records[0].open_time_ms
    assert records[2].minutes_since_prior_accepted == 60
    validate_event_ledger(records, conditions=conditions())

    tampered = records[1].model_copy(
        update={"accepted": True, "accepted_event_sequence": 2}
    )
    with pytest.raises(ValueError, match="suppression"):
        validate_event_ledger(
            [records[0], tampered, *records[2:]],
            conditions=conditions(),
        )


def test_prevalence_gates_are_exact_and_outcomes_remain_unavailable():
    passing = build_prevalence_gate_results(
        ["1000", "240", "20", "15", "0.10", "0.02", "0"]
    )
    assert all(item.passed for item in passing)
    failing = build_prevalence_gate_results(
        ["999", "239", "19", "14", "0.100000000000000001", "0.0201", "1"]
    )
    assert not any(item.passed for item in failing)

    result = prevalence_result()
    assert result.decision == JAM_PREVALENCE_FAIL_DECISION
    assert result.next_required_authorization == (
        JAM_PREVALENCE_NO_NEXT_AUTHORIZATION
    )
    assert result.raw_event_count == 3
    assert result.accepted_event_count == 2
    assert result.suppressed_event_count == 1
    assert result.future_price_rows_accessed == 0
    assert result.future_labels_calculated == []
    assert result.return_metrics_calculated == []
    assert result.matched_controls_constructed == 0
    assert result.backtests_executed == 0
    assert result.strategy_executions == 0

    payload = result.model_dump()
    payload["future_labels_calculated"] = ["ILLEGAL_FUTURE_LABEL"]
    with pytest.raises(ValidationError, match="outcome boundary"):
        JamSuccessorDevelopmentEventPrevalenceResult.model_validate(payload)


def test_protocol_and_query_reject_authority_and_future_data():
    protocol = prevalence_protocol()
    assert protocol.event_conditions == conditions()
    assert len(protocol.prevalence_gates) == 7
    assert protocol.minimum_event_separation_minutes == 60
    assert not protocol.validation_2021_access_permitted
    assert not protocol.holdout_2022_access_permitted
    assert not protocol.future_price_access_permitted
    assert not protocol.return_calculation_permitted

    payload = protocol.model_dump()
    payload["future_price_access_permitted"] = True
    with pytest.raises(ValidationError):
        JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate(payload)

    query = _event_query(protocol)
    assert "quality_state = 'READY'" in query
    assert "ORDER BY open_time_ms" in query
    assert "entry" not in query.lower()
    assert "exit" not in query.lower()
    assert "return" not in query.lower()
    assert "2021" not in query
    assert "2022" not in query


def test_canonical_prevalence_evidence_passes_without_outcomes():
    protocol = JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate_json(
        CANONICAL_PROTOCOL.read_text(encoding="utf-8")
    )
    result = JamSuccessorDevelopmentEventPrevalenceResult.model_validate_json(
        CANONICAL_RESULT.read_text(encoding="utf-8")
    )
    audit = JamSuccessorDevelopmentEventPrevalenceAudit.model_validate_json(
        CANONICAL_AUDIT.read_text(encoding="utf-8")
    )
    ledger = [
        JamDevelopmentEventLedgerRecord.model_validate_json(line)
        for line in CANONICAL_LEDGER.read_text(encoding="utf-8").splitlines()
    ]
    assert audit_jam_successor_prevalence_protocol(protocol)
    assert audit_jam_successor_prevalence_result(result)
    assert audit_jam_successor_prevalence_audit(audit)
    validate_event_ledger(ledger, conditions=protocol.event_conditions)
    assert protocol.protocol_evidence_hash == (
        "e43339f5186b5702c6db0d316b236415c5bb02f0bc2cb18d9188f5122adbe0cd"
    )
    assert result.result_evidence_hash == (
        "444fe28b86c6283181f3e99cfe55258fd4e9136cbca1c92b978cbdfae9ea77ea"
    )
    assert audit.audit_evidence_hash == (
        "414e9affc9e138a38a25c7a3d3432f0672217c9ff3e8707b73147200ea5f544d"
    )
    assert result.raw_event_count == len(ledger) == 1_430
    assert result.accepted_event_count == 991
    assert result.suppressed_event_count == 439
    assert result.months_with_at_least_five_events == 24
    assert result.minimum_quarter_event_count == 70
    assert result.largest_month_event_share == (
        "0.08274470232088799192734611504"
    )
    assert result.largest_day_event_share == (
        "0.006054490413723511604439959637"
    )
    assert result.passed_gate_count == 7
    assert result.failed_gate_count == 0
    assert result.decision == JAM_PREVALENCE_PASS_DECISION
    assert result.future_price_rows_accessed == 0
    assert result.future_labels_calculated == []
    assert result.return_metrics_calculated == []
    assert result.matched_controls_constructed == 0
    assert result.backtests_executed == 0
    assert result.strategy_executions == 0
