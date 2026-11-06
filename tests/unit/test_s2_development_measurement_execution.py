from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed
from aurex.backtest_engine.s2_bigquery_payload import (
    S2DevelopmentWeeklyPayload,
    S2DevelopmentWeeklyRow,
)
from aurex.backtest_engine.s2_development_measurement_execution import (
    S2_MEASUREMENT_PASS,
    S2_MEASUREMENT_RUN,
    S2DevelopmentMeasurementExecutionAddendum,
    S2DevelopmentMeasurementExecutionAudit,
    S2DevelopmentMeasurementResult,
    S2DevelopmentMeasurementResultAudit,
    S2DevelopmentMeasurementRow,
    S2MeasurementGate,
    build_measurement_rows,
    growth_ppm,
    measurement_row_hashes,
    serialize_measurement_rows,
    settlement_demand_agreement,
)
from aurex.backtest_engine.s2_development_measurement_protocol import S2_MEASUREMENT_GATES
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_s2_development_measurement_execution import (
    DEFAULT_ADDENDUM,
    build_addendum,
)


def synthetic_payload(*, zero_prior_fees: bool = False) -> S2DevelopmentWeeklyPayload:
    rows = []
    for index in range(280):
        week_start = date(2017, 8, 19) + timedelta(days=7 * index)
        rows.append(
            S2DevelopmentWeeklyRow(
                week_start=week_start,
                decision_cutoff_at=week_start + timedelta(days=7),
                earliest_execution_at=week_start + timedelta(days=9),
                confirmed_block_count=1000 + index,
                confirmed_non_coinbase_transaction_count=100 + 10 * index,
                confirmed_fee_satoshis=(0 if zero_prior_fees and index < 4 else 1000 + 100 * index),
                latest_sixth_confirmation_at=datetime.combine(
                    week_start + timedelta(days=6),
                    time(23, 59),
                    UTC,
                ),
            )
        )
    return build_hashed(
        S2DevelopmentWeeklyPayload,
        "payload_evidence_hash",
        {
            "acquired_at": datetime(2026, 8, 30, tzinfo=UTC),
            "protocol_evidence_hash": "1" * 64,
            "query_sha256": "2" * 64,
            "rows": tuple(rows),
        },
    )


def test_growth_ppm_uses_half_even_integer_output() -> None:
    assert growth_ppm(129, 128) == 7_812
    assert growth_ppm(127, 128) == -7_812
    assert growth_ppm(5, 4) == 250_000


@pytest.mark.parametrize("current,prior", ((-1, 1), (1, 0), (1, -1)))
def test_growth_ppm_rejects_invalid_inputs(current: int, prior: int) -> None:
    with pytest.raises(ValueError, match="positive prior"):
        growth_ppm(current, prior)


@pytest.mark.parametrize(
    "transaction_growth,fee_growth,expected",
    (
        (1, 1, "BOTH_BROADENING"),
        (-1, -1, "BOTH_CONTRACTING"),
        (1, -1, "FLAT_OR_MIXED"),
        (0, 1, "FLAT_OR_MIXED"),
        (0, 0, "FLAT_OR_MIXED"),
    ),
)
def test_settlement_demand_agreement_is_strict(
    transaction_growth: int,
    fee_growth: int,
    expected: str,
) -> None:
    assert settlement_demand_agreement(transaction_growth, fee_growth) == expected


def test_measurement_runner_constructs_exact_causal_windows() -> None:
    payload = synthetic_payload()

    rows = build_measurement_rows(payload)

    assert len(rows) == 273
    assert rows[0].sequence == 8
    assert rows[0].week_start == date(2017, 10, 7)
    assert rows[0].confirmed_tx_current_4w == 620
    assert rows[0].confirmed_tx_prior_4w == 460
    assert rows[0].confirmed_fee_sats_current_4w == 6_200
    assert rows[0].confirmed_fee_sats_prior_4w == 4_600
    assert rows[0].confirmed_tx_growth_ppm == 347_826
    assert rows[0].confirmed_fee_growth_ppm == 347_826
    assert rows[0].settlement_demand_agreement == "BOTH_BROADENING"
    assert rows[-1].sequence == 280
    assert rows[-1].week_start == date(2022, 12, 24)
    assert all(row.source_payload_evidence_hash == payload.payload_evidence_hash for row in rows)


def test_measurement_runner_rejects_zero_prior_fee_denominator() -> None:
    with pytest.raises(ValueError, match="positive prior"):
        build_measurement_rows(synthetic_payload(zero_prior_fees=True))


def test_measurement_row_rejects_inconsistent_growth() -> None:
    row = build_measurement_rows(synthetic_payload())[0].model_dump(mode="json")
    row["confirmed_tx_growth_ppm"] += 1

    with pytest.raises(ValidationError, match="measurement row changed"):
        S2DevelopmentMeasurementRow.model_validate(row)


def test_measurement_serialization_and_manifest_are_deterministic() -> None:
    rows = build_measurement_rows(synthetic_payload())

    assert serialize_measurement_rows(rows) == serialize_measurement_rows(rows)
    assert measurement_row_hashes(rows) == measurement_row_hashes(rows)
    assert len(measurement_row_hashes(rows)) == 273


def test_execution_addendum_cannot_escalate_to_market_or_return_authority() -> None:
    addendum = build_hashed(
        S2DevelopmentMeasurementExecutionAddendum,
        "addendum_evidence_hash",
        {
            "frozen_at": datetime(2026, 8, 30, tzinfo=UTC),
            "builder_contract_hash": "1" * 64,
            "protocol_file_sha256": "2" * 64,
            "protocol_evidence_hash": "3" * 64,
            "protocol_audit_file_sha256": "4" * 64,
            "protocol_audit_evidence_hash": "5" * 64,
            "payload_result_evidence_hash": "6" * 64,
            "payload_result_audit_evidence_hash": "7" * 64,
            "payload_file_sha256": "8" * 64,
            "payload_evidence_hash": "9" * 64,
            "runner_contract_hash": "a" * 64,
            "synthetic_test_ids": tuple(f"test_{index:02d}" for index in range(8)),
        },
    )
    payload = addendum.model_dump(mode="json")
    payload["authorizes_return_testing"] = True

    assert addendum.next_authorization == S2_MEASUREMENT_RUN
    assert addendum.authorizes_payload_value_read is True
    assert addendum.authorizes_market_value_access is False
    with pytest.raises(ValidationError):
        S2DevelopmentMeasurementExecutionAddendum.model_validate(payload)


def test_consumed_execution_addendum_cannot_be_rebuilt_or_reused() -> None:
    with pytest.raises(ValueError, match="basis did not reconcile"):
        build_addendum(frozen_at=datetime(2026, 8, 30, tzinfo=UTC))


def test_execution_audit_round_trips() -> None:
    addendum = S2DevelopmentMeasurementExecutionAddendum.model_validate_json(
        DEFAULT_ADDENDUM.read_text()
    )
    audit = build_hashed(
        S2DevelopmentMeasurementExecutionAudit,
        "audit_evidence_hash",
        {
            "audited_at": datetime(2026, 8, 30, tzinfo=UTC),
            "addendum_file_sha256": "b" * 64,
            "addendum_evidence_hash": addendum.addendum_evidence_hash,
            "protocol_evidence_hash": addendum.protocol_evidence_hash,
            "runner_contract_hash": addendum.runner_contract_hash,
            "auditor_contract_hash": "c" * 64,
        },
    )

    assert (
        S2DevelopmentMeasurementExecutionAudit.model_validate_json(audit.model_dump_json()) == audit
    )
    assert audit.payload_value_rows_parsed == 0
    assert audit.measurement_rows_calculated == 0
    assert audit.next_authorization == S2_MEASUREMENT_RUN


def test_result_and_independent_audit_round_trip_without_outcomes() -> None:
    rows = build_measurement_rows(synthetic_payload())
    serialized = serialize_measurement_rows(rows)
    result = build_hashed(
        S2DevelopmentMeasurementResult,
        "result_evidence_hash",
        {
            "completed_at": datetime(2026, 8, 30, tzinfo=UTC),
            "protocol_evidence_hash": "1" * 64,
            "protocol_audit_evidence_hash": "2" * 64,
            "execution_addendum_file_sha256": "3" * 64,
            "execution_addendum_evidence_hash": "4" * 64,
            "execution_audit_evidence_hash": "5" * 64,
            "runner_contract_hash": "6" * 64,
            "payload_file_sha256": "7" * 64,
            "payload_evidence_hash": "8" * 64,
            "measurement_dataset_file_sha256": "9" * 64,
            "measurement_dataset_bytes": len(serialized),
            "row_evidence_hashes": measurement_row_hashes(rows),
            "gates": tuple(
                S2MeasurementGate(gate_id=gate_id, status="PASS", reason="exact")
                for gate_id in S2_MEASUREMENT_GATES
            ),
        },
    )
    audit = build_hashed(
        S2DevelopmentMeasurementResultAudit,
        "audit_evidence_hash",
        {
            "audited_at": datetime(2026, 8, 30, tzinfo=UTC),
            "result_file_sha256": "a" * 64,
            "result_evidence_hash": result.result_evidence_hash,
            "measurement_dataset_file_sha256": result.measurement_dataset_file_sha256,
            "runner_contract_hash": result.runner_contract_hash,
            "auditor_contract_hash": "b" * 64,
            "measurement_row_manifest_evidence_hash": universe_evidence_hash(
                result.row_evidence_hashes
            ),
        },
    )

    assert result.decision == S2_MEASUREMENT_PASS
    assert result.market_values_read == 0
    assert result.returns_calculated == 0
    assert result.strategy_candidates_created == 0
    assert result.orders_submitted == 0
    assert result.real_net_profit_usd == "0"
    assert S2DevelopmentMeasurementResultAudit.model_validate_json(audit.model_dump_json()) == audit
