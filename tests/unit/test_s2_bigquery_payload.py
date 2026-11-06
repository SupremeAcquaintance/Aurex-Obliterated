from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed
from aurex.backtest_engine.s2_bigquery_payload import (
    S2_PAYLOAD_NEXT,
    S2_PAYLOAD_PASS,
    S2BigQueryPayloadProtocol,
    S2BigQueryPayloadResult,
    S2DevelopmentWeeklyPayload,
    S2DevelopmentWeeklyRow,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_s2_bigquery_payload_protocol import build_protocol
from scripts.run_s2_bigquery_payload import (
    build_payload,
    parse_completed_response,
    query_request,
)

PROTOCOL_PATH = Path("data/evidence/s2_bigquery_payload_protocol_v1.json")


def canonical_protocol() -> S2BigQueryPayloadProtocol:
    return S2BigQueryPayloadProtocol.model_validate_json(PROTOCOL_PATH.read_text())


def row(index: int) -> S2DevelopmentWeeklyRow:
    week_start = date(2017, 8, 19) + timedelta(days=7 * index)
    return S2DevelopmentWeeklyRow(
        week_start=week_start,
        decision_cutoff_at=week_start + timedelta(days=7),
        earliest_execution_at=week_start + timedelta(days=9),
        confirmed_block_count=1,
        confirmed_non_coinbase_transaction_count=1,
        confirmed_fee_satoshis=1,
        latest_sixth_confirmation_at=datetime.combine(
            week_start + timedelta(days=6),
            datetime.min.time(),
            tzinfo=UTC,
        ),
    )


def test_payload_protocol_builds_without_network_or_values() -> None:
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    assert isinstance(protocol, S2BigQueryPayloadProtocol)
    assert len(protocol.source_bindings) == 8
    assert protocol.query_spec.expected_row_count == 280
    assert protocol.query_spec.maximum_bytes_billed == 60_000_000_000
    assert protocol.market_values_permitted is False
    assert protocol.parameters_permitted is False
    assert protocol.returns_permitted is False
    assert protocol.orders_permitted is False
    assert protocol.live_permitted is False
    assert protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )


def test_payload_query_enforces_confirmation_cutoff_and_execution_lag() -> None:
    sql = build_protocol(frozen_at=datetime.now(UTC)).query_spec.google_sql
    assert "confirmation.number = b.number + 6" in sql
    assert "WEEK(SATURDAY)" in sql
    assert "INTERVAL 7 DAY" in sql
    assert "INTERVAL 9 DAY" in sql
    assert "maximumBytesBilled" not in sql
    assert "BTCUSDT" not in sql
    assert "price" not in sql.lower()


def test_weekly_row_rejects_confirmation_at_cutoff() -> None:
    week_start = date(2017, 8, 19)
    with pytest.raises(ValidationError):
        S2DevelopmentWeeklyRow(
            week_start=week_start,
            decision_cutoff_at=week_start + timedelta(days=7),
            earliest_execution_at=week_start + timedelta(days=9),
            confirmed_block_count=1,
            confirmed_non_coinbase_transaction_count=1,
            confirmed_fee_satoshis=1,
            latest_sixth_confirmation_at=datetime.combine(
                week_start + timedelta(days=7),
                datetime.min.time(),
                tzinfo=UTC,
            ),
        )


def test_payload_requires_exact_contiguous_280_week_coverage() -> None:
    rows = tuple(row(index) for index in range(280))
    values = {
        "acquired_at": datetime.now(UTC),
        "protocol_evidence_hash": "0" * 64,
        "query_sha256": "1" * 64,
        "rows": rows,
    }
    payload = build_hashed(
        S2DevelopmentWeeklyPayload,
        "payload_evidence_hash",
        values,
    )
    assert payload.row_count == 280
    assert payload.rows[0].week_start == date(2017, 8, 19)
    assert payload.rows[-1].week_start == date(2022, 12, 24)


def test_payload_rejects_noncontiguous_coverage() -> None:
    rows = [row(index) for index in range(280)]
    rows[100] = row(101)
    values = {
        "acquired_at": datetime.now(UTC),
        "protocol_evidence_hash": "0" * 64,
        "query_sha256": "1" * 64,
        "rows": tuple(rows),
    }
    with pytest.raises(ValidationError):
        build_hashed(
            S2DevelopmentWeeklyPayload,
            "payload_evidence_hash",
            values,
        )


def test_successful_payload_result_only_authorizes_measurement_protocol() -> None:
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    result = build_hashed(
        S2BigQueryPayloadResult,
        "result_evidence_hash",
        {
            "generated_at": datetime.now(UTC),
            "protocol_file_sha256": "0" * 64,
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_file_sha256": "1" * 64,
            "protocol_audit_evidence_hash": "2" * 64,
            "feasibility_result_evidence_hash": (protocol.feasibility_result_evidence_hash),
            "feasibility_result_audit_evidence_hash": (
                protocol.feasibility_result_audit_evidence_hash
            ),
            "runner_contract_hash": "3" * 64,
            "gcloud_available": True,
            "active_auth_configured": True,
            "active_project_configured": True,
            "billing_boundary_request_count": 1,
            "sandbox_without_billing_verified": True,
            "access_token_request_count": 1,
            "access_token_available": True,
            "query_submission_count": 1,
            "query_result_poll_count": 0,
            "query_result_page_count": 1,
            "query_completed": True,
            "total_bytes_processed": 1,
            "query_result_rows_returned": 280,
            "blockchain_row_values_read": 280,
            "payload_path": protocol.payload_path,
            "payload_file_sha256": "4" * 64,
            "payload_evidence_hash": "5" * 64,
            "payload_byte_count": 1,
            "blockers": (),
            "decision": S2_PAYLOAD_PASS,
            "next_authorization": S2_PAYLOAD_NEXT,
            "authorizes_measurement_protocol": True,
            "limitations": protocol.limitations,
        },
    )
    assert result.authorizes_measurement_protocol is True
    assert result.authorizes_parameters is False
    assert result.authorizes_returns is False
    assert result.authorizes_paper is False
    assert result.authorizes_live is False


def synthetic_query_response(*, page_token: str | None = None) -> dict:
    protocol = canonical_protocol()
    rows = []
    for index in range(280):
        week_start = date(2017, 8, 19) + timedelta(days=7 * index)
        rows.append(
            {
                "f": [
                    {"v": week_start.isoformat()},
                    {"v": (week_start + timedelta(days=7)).isoformat()},
                    {"v": (week_start + timedelta(days=9)).isoformat()},
                    {"v": "1"},
                    {"v": "1"},
                    {"v": "1"},
                    {"v": (f"{(week_start + timedelta(days=6)).isoformat()}T00:00:00.000000Z")},
                ]
            }
        )
    payload = {
        "jobComplete": True,
        "schema": {
            "fields": [
                {"name": name, "type": field_type}
                for name, field_type in zip(
                    protocol.query_spec.expected_field_names,
                    protocol.query_spec.expected_field_types,
                    strict=True,
                )
            ]
        },
        "totalRows": "280",
        "totalBytesProcessed": "46852212436",
        "rows": rows,
    }
    if page_token is not None:
        payload["pageToken"] = page_token
    return payload


def test_query_request_enforces_cost_and_cache_controls() -> None:
    protocol = canonical_protocol()
    request = query_request(
        protocol,
        token="in-memory-token",
        project="in-memory-project",
    )
    body = json.loads(request.data)
    assert body["maximumBytesBilled"] == "60000000000"
    assert body["maxResults"] == 1000
    assert body["useLegacySql"] is False
    assert body["useQueryCache"] is False
    assert body["query"] == protocol.query_spec.google_sql


def test_completed_response_parses_exact_280_week_payload() -> None:
    protocol = canonical_protocol()
    outcome = parse_completed_response(
        protocol,
        synthetic_query_response(),
        poll_count=0,
    )
    assert outcome.completed is True
    assert outcome.error_class == "NONE"
    assert outcome.raw_row_count == 280
    assert outcome.total_bytes_processed == 46_852_212_436
    payload = build_payload(
        protocol,
        acquired_at=datetime.now(UTC),
        rows=outcome.rows,
    )
    assert payload.row_count == 280
    assert payload.rows[-1].earliest_execution_at == date(2023, 1, 2)


def test_completed_response_rejects_second_result_page() -> None:
    outcome = parse_completed_response(
        canonical_protocol(),
        synthetic_query_response(page_token="forbidden"),
        poll_count=0,
    )
    assert outcome.completed is True
    assert outcome.error_class == "SCHEMA_MISMATCH"
    assert outcome.rows == ()
