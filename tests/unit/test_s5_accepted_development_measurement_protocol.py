from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_accepted_development_measurement_protocol import (
    S5_MEASUREMENT_GATES,
    S5_MEASUREMENT_NEXT,
    S5_MEASUREMENT_OUTPUT_FIELDS,
    S5AcceptedDevelopmentMeasurementProtocolV1,
    audit_s5_measurement_protocol,
)
from scripts.audit_s5_accepted_development_measurement_protocol import build_audit
from scripts.freeze_s5_accepted_development_measurement_protocol import (
    build_protocol,
    write_protocol,
)


def frozen_time() -> datetime:
    return datetime(2026, 9, 8, 20, 0, tzinfo=UTC)


def test_protocol_freezes_separate_event_universes_without_outcomes() -> None:
    protocol = build_protocol(frozen_at=frozen_time())

    assert audit_s5_measurement_protocol(protocol)
    assert protocol.input_row_counts == (24_398, 16_242, 194, 16_279, 479)
    assert tuple(item.row_count for item in protocol.event_universes) == (
        16_271,
        16_279,
        16_242,
    )
    assert tuple(item.role for item in protocol.event_universes) == (
        "PRIMARY",
        "SENSITIVITY",
        "CORROBORATION",
    )
    assert protocol.many_to_one_pull_groups == ((25_882, 25_891), (26_081, 26_084))
    assert protocol.quality_gates == S5_MEASUREMENT_GATES
    assert protocol.output_fields == S5_MEASUREMENT_OUTPUT_FIELDS
    assert protocol.expected_measurement_month_count == 212
    assert protocol.source_jsonl_rows_parsed_during_freeze == 0
    assert protocol.git_processes_executed_during_freeze == 0
    assert protocol.network_requests_executed_during_freeze == 0
    assert protocol.market_values_read_during_freeze == 0


def test_protocol_keeps_release_review_and_execution_authority_locked() -> None:
    protocol = build_protocol(frozen_at=frozen_time())

    assert not protocol.release_continuity_candidate_feature_eligible
    assert not protocol.review_continuity_candidate_feature_eligible
    assert protocol.review_event_records_acquired == 0
    assert protocol.authorizes_measurement_runner_implementation
    assert not protocol.authorizes_measurement_execution_now
    assert not protocol.authorizes_network_requests
    assert not protocol.authorizes_market_value_access
    assert not protocol.authorizes_return_testing
    assert not protocol.authorizes_strategy_candidate
    assert not protocol.authorizes_signal_generation
    assert not protocol.authorizes_pine
    assert not protocol.authorizes_paper
    assert not protocol.authorizes_testnet_strategy_orders
    assert not protocol.authorizes_production
    assert not protocol.authorizes_live
    assert protocol.next_authorization == S5_MEASUREMENT_NEXT


def test_protocol_emits_only_counts_hashes_and_source_identity() -> None:
    protocol = build_protocol(frozen_at=frozen_time())

    assert not set(protocol.output_fields) & set(protocol.forbidden_output_fields)
    assert "actor_id" not in protocol.output_fields
    assert "actor_login" not in protocol.output_fields
    assert "btc_return" not in protocol.output_fields
    assert "signal" not in protocol.output_fields
    assert tuple(
        definition.measurement_id for definition in protocol.measurement_definitions
    ) == protocol.output_fields[4:21]


def test_protocol_rejects_event_universe_tampering() -> None:
    protocol = build_protocol(frozen_at=frozen_time())
    payload = protocol.model_dump(mode="json")
    payload["event_universes"][0]["role"] = "SENSITIVITY"

    with pytest.raises(ValidationError):
        S5AcceptedDevelopmentMeasurementProtocolV1.model_validate(payload)


def test_protocol_rejects_source_binding_manifest_tampering() -> None:
    protocol = build_protocol(frozen_at=frozen_time())
    payload = protocol.model_dump(mode="json")
    payload["source_bindings"][0]["file_sha256"] = "f" * 64

    with pytest.raises(ValidationError):
        S5AcceptedDevelopmentMeasurementProtocolV1.model_validate(payload)


def test_protocol_rejects_trading_authority_tampering() -> None:
    protocol = build_protocol(frozen_at=frozen_time())
    payload = protocol.model_dump(mode="json")
    payload["authorizes_testnet_strategy_orders"] = True

    with pytest.raises(ValidationError):
        S5AcceptedDevelopmentMeasurementProtocolV1.model_validate(payload)


def test_protocol_rejects_formula_tampering() -> None:
    protocol = build_protocol(frozen_at=frozen_time())
    payload = protocol.model_dump(mode="json")
    payload["measurement_definitions"][0]["formula"] = "COUNT_SOMETHING_ELSE"

    with pytest.raises(ValidationError):
        S5AcceptedDevelopmentMeasurementProtocolV1.model_validate(payload)


def test_protocol_and_audit_reconstruct_exactly(tmp_path) -> None:
    protocol_path = tmp_path / "protocol.json"
    protocol = build_protocol(frozen_at=frozen_time())
    write_protocol(protocol_path, protocol)

    stored = S5AcceptedDevelopmentMeasurementProtocolV1.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = build_audit(protocol_path=protocol_path, audited_at=frozen_time())

    assert stored == protocol
    assert audit.protocol_evidence_hash == protocol.protocol_evidence_hash
    assert len(audit.auditor_implementation_bindings) == 2
    assert audit.source_binding_count == 25
    assert audit.input_row_count == 57_592
    assert audit.primary_event_count == 16_271
    assert audit.canonical_integration_count == 16_242
    assert audit.protocol_reconstructed_exactly
    assert audit.network_requests_executed == 0
    assert audit.market_values_read == 0
    assert audit.orders_submitted == 0
