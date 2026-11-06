from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.jam_successor_development_outcome import (
    JAM_OUTCOME_DEVELOPMENT_END_EXCLUSIVE_MS,
    JamAggregateMinutePrice,
    JamControlFeatureRow,
    JamOutcomeArchiveEvidence,
    JamOutcomeBucketMetric,
    JamOutcomeMonthContribution,
    JamSuccessorDevelopmentOutcomeAudit,
    JamSuccessorDevelopmentOutcomeExecutionProtocol,
    JamSuccessorDevelopmentOutcomeResult,
    activity_quartile,
    audit_jam_successor_outcome_audit,
    audit_jam_successor_outcome_protocol,
    audit_jam_successor_outcome_result,
    build_jam_successor_outcome_result,
    build_outcome_gate_results,
    calculate_horizon_outcome,
    cluster_bootstrap_lower_bound,
    profit_factor,
    select_matched_controls,
)
from aurex.backtest_engine.jam_successor_distribution_protocol import (
    JAM_DISTRIBUTION_MONTHS,
)
from aurex.backtest_engine.jam_successor_event_prevalence import (
    JAM_PREVALENCE_QUARTERS,
)

HASH = "0" * 64
ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PROTOCOL = (
    ROOT
    / "data/evidence/jam_successor_development_outcome_execution_protocol_v1.json"
)
CANONICAL_CONTROL_LEDGER = (
    ROOT
    / "data/evidence/jam_successor_development_matched_control_ledger_v1.jsonl"
)
CANONICAL_OUTCOME_LEDGER = (
    ROOT
    / "data/evidence/jam_successor_development_outcome_ledger_v1.jsonl"
)
CANONICAL_RESULT = (
    ROOT
    / "data/evidence/jam_successor_development_outcome_result_v1.json"
)
CANONICAL_AUDIT = (
    ROOT
    / "data/evidence/jam_successor_development_outcome_audit_v1.json"
)


def open_time(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
) -> int:
    return int(
        datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=UTC,
        ).timestamp()
        * 1_000
    )


def control_row(
    timestamp: int,
    *,
    value: str = "10",
    quartile: str = "Q1",
) -> JamControlFeatureRow:
    parsed = datetime.fromtimestamp(timestamp / 1_000, tz=UTC)
    return JamControlFeatureRow(
        open_time_ms=timestamp,
        month=parsed.strftime("%Y-%m"),
        utc_hour=parsed.hour,
        activity_value=value,
        activity_quartile=quartile,
    )


def minute_price(
    timestamp: int,
    *,
    first: str,
    high: str,
    low: str,
    last: str,
) -> JamAggregateMinutePrice:
    return JamAggregateMinutePrice(
        open_time_ms=timestamp,
        first_price=first,
        high_price=high,
        low_price=low,
        last_price=last,
    )


def test_activity_quartile_edges_are_frozen_left_closed():
    q25 = Decimal("25")
    q50 = Decimal("50")
    q75 = Decimal("75")
    assert activity_quartile(Decimal("25"), q25=q25, q50=q50, q75=q75) == "Q1"
    assert (
        activity_quartile(
            Decimal("25.000000000000000001"),
            q25=q25,
            q50=q50,
            q75=q75,
        )
        == "Q2"
    )
    assert activity_quartile(Decimal("50"), q25=q25, q50=q50, q75=q75) == "Q2"
    assert activity_quartile(Decimal("75"), q25=q25, q50=q50, q75=q75) == "Q3"
    assert (
        activity_quartile(
            Decimal("75.000000000000000001"),
            q25=q25,
            q50=q50,
            q75=q75,
        )
        == "Q4"
    )


def test_control_matching_uses_nearest_then_earlier_without_replacement():
    event_one = open_time(2019, 1, 10, 0)
    event_two = open_time(2019, 1, 12, 0)
    earlier = control_row(open_time(2019, 1, 8, 0))
    later = control_row(open_time(2019, 1, 12, 0))
    fallback = control_row(open_time(2019, 1, 6, 0))
    event_rows = {
        event_one: control_row(event_one),
        event_two: control_row(event_two),
    }
    records = select_matched_controls(
        accepted_event_times=[event_one, event_two],
        event_activity_rows=event_rows,
        candidate_groups={
            ("2019-01", 0, "Q1"): [later, earlier, fallback],
        },
    )
    assert records[0].control_open_time_ms == earlier.open_time_ms
    assert records[1].control_open_time_ms == later.open_time_ms
    assert len(
        {
            record.control_open_time_ms
            for record in records
            if record.control_open_time_ms is not None
        }
    ) == 2


def test_horizon_outcome_uses_cash_correct_costs_and_complete_path():
    evaluation = open_time(2019, 1, 1, 0)
    prices = {}
    for offset in range(1, 16):
        timestamp = evaluation + offset * 60_000
        prices[timestamp] = minute_price(
            timestamp,
            first="100.00" if offset == 1 else "100.50",
            high="102.00",
            low="99.00",
            last="101.00" if offset == 15 else "100.50",
        )
    outcome = calculate_horizon_outcome(
        subject_type="EVENT",
        subject_sequence=1,
        paired_event_sequence=1,
        evaluation_open_time_ms=evaluation,
        horizon_minutes=15,
        minute_prices=prices,
        quarantined_minutes=set(),
    )
    expected_base = Decimal(10_000) * (
        (Decimal("100.98") * Decimal("0.9990"))
        / (Decimal("100.02") * Decimal("1.0010"))
        - Decimal(1)
    )
    expected_stress = Decimal(10_000) * (
        (Decimal("100.90") * Decimal("0.9985"))
        / (Decimal("100.10") * Decimal("1.0015"))
        - Decimal(1)
    )
    assert outcome.status == "AVAILABLE"
    assert Decimal(outcome.base_net_return_bps) == expected_base.quantize(
        Decimal("0.000000000000000001")
    )
    assert Decimal(outcome.stress_net_return_bps) == expected_stress.quantize(
        Decimal("0.000000000000000001")
    )
    assert outcome.maximum_favorable_excursion_bps is not None
    assert outcome.maximum_adverse_excursion_bps is not None

    quarantined = calculate_horizon_outcome(
        subject_type="EVENT",
        subject_sequence=1,
        paired_event_sequence=1,
        evaluation_open_time_ms=evaluation,
        horizon_minutes=15,
        minute_prices=prices,
        quarantined_minutes={evaluation + 5 * 60_000},
    )
    assert quarantined.status == "UNAVAILABLE_QUARANTINED_PATH_MINUTE"
    assert quarantined.entry_reference_price is None

    crossing = calculate_horizon_outcome(
        subject_type="EVENT",
        subject_sequence=1,
        paired_event_sequence=1,
        evaluation_open_time_ms=JAM_OUTCOME_DEVELOPMENT_END_EXCLUSIVE_MS - 60_000,
        horizon_minutes=15,
        minute_prices={},
        quarantined_minutes=set(),
    )
    assert crossing.status == "UNAVAILABLE_CROSSES_DEVELOPMENT_PARTITION"


def test_bootstrap_and_profit_factor_are_deterministic():
    values = {
        f"{year}-{month:02d}": [
            Decimal(str((year - 2018) * month)),
            Decimal(str((year - 2018) * month + 1)),
        ]
        for year in (2019, 2020)
        for month in range(1, 13)
    }
    first = cluster_bootstrap_lower_bound(values)
    second = cluster_bootstrap_lower_bound(values)
    assert first == second
    assert first == Decimal("8.125000000000000000")
    assert profit_factor(
        [Decimal("10"), Decimal("-5"), Decimal("5")]
    ) == "3.000000000000000000"
    assert profit_factor([Decimal("1"), Decimal("2")]) == "POSITIVE_INFINITY"


def test_all_eleven_gate_boundaries_are_conjunctive():
    passing = build_outcome_gate_results(
        [
            "200",
            "180",
            "5",
            "1.20",
            "0.000000000000000001",
            "5",
            "0.000000000000000001",
            "0.000000000000000001",
            "2",
            "6",
            "0.20",
        ]
    )
    assert all(item.passed for item in passing)
    failing = build_outcome_gate_results(
        [
            "199",
            "179",
            "4.999999999999999999",
            "1.199999999999999999",
            "0",
            "4.999999999999999999",
            "0",
            "0",
            "1",
            "5",
            "0.200000000000000001",
        ]
    )
    assert not any(item.passed for item in failing)


def test_result_model_reconciles_decision_and_rejects_sealed_access():
    gates = build_outcome_gate_results(
        [
            "991",
            "0",
            "1",
            "1",
            "-1",
            "0",
            "-1",
            "-1",
            "2",
            "8",
            "0.10",
        ]
    )
    result = build_jam_successor_outcome_result(
        generated_at=datetime(2026, 8, 5, tzinfo=UTC),
        protocol_evidence_hash=HASH,
        runner_contract_hash=HASH,
        prevalence_result_evidence_hash=HASH,
        event_ledger_file_sha256=HASH,
        feature_rows_file_sha256=HASH,
        control_ledger_file_sha256=HASH,
        control_ledger_bytes=0,
        matched_control_count=0,
        unmatched_event_count=991,
        outcome_ledger_file_sha256=HASH,
        outcome_ledger_bytes=0,
        outcome_ledger_record_count=2_973,
        archive_evidence=[
            JamOutcomeArchiveEvidence(
                month=month,
                archive_path=f"{month}.zip",
                archive_sha256=HASH,
                requested_minute_count=0,
                recovered_minute_count=0,
                missing_minute_count=0,
                archive_identity_passed=True,
            )
            for month in JAM_DISTRIBUTION_MONTHS
        ],
        primary_outcome_qualified_event_count=991,
        primary_outcome_qualified_control_count=0,
        matched_primary_pair_count=0,
        event_horizon_available_counts={"15": 991, "30": 991, "60": 991},
        control_horizon_available_counts={"15": 0, "30": 0, "60": 0},
        base_net_mean_30m_bps="1",
        base_net_profit_factor_30m="1",
        stress_net_mean_30m_bps="-1",
        matched_excess_mean_30m_bps="0",
        bootstrap_lower_95_base_net_mean_30m_bps="-1",
        bootstrap_lower_95_matched_excess_mean_30m_bps="-1",
        yearly_metrics=[
            JamOutcomeBucketMetric(
                bucket=year,
                outcome_count=1,
                base_net_mean_bps="1",
            )
            for year in ("2019", "2020")
        ],
        quarterly_metrics=[
            JamOutcomeBucketMetric(
                bucket=quarter,
                outcome_count=1,
                base_net_mean_bps="1",
            )
            for quarter in JAM_PREVALENCE_QUARTERS
        ],
        positive_year_count=2,
        positive_quarter_count=8,
        monthly_absolute_return_contributions=[
            JamOutcomeMonthContribution(
                month=month,
                absolute_return_sum_bps="1",
                contribution_share=(
                    "0.10" if month == "2020-12" else "0.01"
                ),
            )
            for month in JAM_DISTRIBUTION_MONTHS
        ],
        largest_month_absolute_return_contribution="0.10",
        largest_contribution_month="2020-12",
        gates=gates,
        return_metrics_calculated=[
            f"RETURN_METRIC_{index}" for index in range(1, 9)
        ],
        limitations=[f"Limitation {index}" for index in range(1, 19)],
    )
    assert result.failed_gate_count > 0
    assert not result.creates_candidate
    payload = result.model_dump()
    payload["sealed_market_periods_opened"] = ["2021_VALIDATION"]
    with pytest.raises(ValidationError, match="authority boundary"):
        JamSuccessorDevelopmentOutcomeResult.model_validate(payload)


def test_canonical_development_outcome_evidence_is_terminal_and_sealed():
    protocol = (
        JamSuccessorDevelopmentOutcomeExecutionProtocol.model_validate_json(
            CANONICAL_PROTOCOL.read_text(encoding="utf-8")
        )
    )
    result = JamSuccessorDevelopmentOutcomeResult.model_validate_json(
        CANONICAL_RESULT.read_text(encoding="utf-8")
    )
    audit = JamSuccessorDevelopmentOutcomeAudit.model_validate_json(
        CANONICAL_AUDIT.read_text(encoding="utf-8")
    )

    assert audit_jam_successor_outcome_protocol(protocol)
    assert audit_jam_successor_outcome_result(result)
    assert audit_jam_successor_outcome_audit(audit)
    assert protocol.protocol_evidence_hash == (
        "e7ed92d708c80a87b36c7d24d903cd7be1c1f594def74daab22618ed9bc6e07d"
    )
    assert result.result_evidence_hash == (
        "560d990748bcefce3e7a46c4bb88e89bf16563bef659213e55b2934005bff430"
    )
    assert audit.audit_evidence_hash == (
        "8c62f09705fe2013cdbc2d61234aa92070badd9b70189a620be0e37088251c95"
    )
    assert file_sha256(CANONICAL_CONTROL_LEDGER) == (
        "c23ea774b26fa50bd4bc37dfc3273efe28d56d4a4ccd545243bbca08d0ab6e34"
    )
    assert file_sha256(CANONICAL_OUTCOME_LEDGER) == (
        "0d322ac7c88f990bc7f714c47f4d4192cb4f81ca8f930e154aa7669336de53d8"
    )
    assert result.primary_outcome_qualified_event_count == 991
    assert result.matched_control_count == 456
    assert result.matched_primary_pair_count == 456
    assert result.base_net_mean_30m_bps == "-16.008098281388651150"
    assert result.base_net_profit_factor_30m == "0.464374516027724364"
    assert result.stress_net_mean_30m_bps == "-26.189788269683100509"
    assert result.matched_excess_mean_30m_bps == "2.984977884653180892"
    assert result.bootstrap_lower_95_base_net_mean_30m_bps == (
        "-19.768677643106546730"
    )
    assert result.bootstrap_lower_95_matched_excess_mean_30m_bps == (
        "-3.041289366472522414"
    )
    assert result.positive_year_count == 0
    assert result.positive_quarter_count == 0
    assert result.passed_gate_count == 3
    assert result.failed_gate_count == 8
    assert result.decision == "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED"
    assert result.next_required_authorization == (
        "NONE_DEVELOPMENT_OUTCOME_FAILED"
    )
    assert result.sealed_market_periods_opened == []
    assert not result.creates_strategy
    assert not result.creates_signal
    assert not result.creates_candidate
    assert not result.creates_paper_eligibility
    assert not result.creates_testnet_order_authority
    assert not result.creates_production_authority
    assert not result.creates_live_eligibility
    assert audit.sealed_market_periods_opened == 0
    assert audit.threshold_changes == 0
    assert audit.strategy_executions == 0
