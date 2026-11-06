from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed
from aurex.backtest_engine.s2_development_measurement_protocol import (
    S2_MEASUREMENT_GATES,
    S2_MEASUREMENT_NEXT,
    S2DevelopmentMeasurementProtocol,
    S2DevelopmentMeasurementProtocolAudit,
)
from scripts.freeze_s2_development_measurement_protocol import (
    PAYLOAD_PATH,
    build_protocol,
)

FROZEN_AT = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)


def test_measurement_protocol_reconstructs_exactly() -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)

    assert (
        S2DevelopmentMeasurementProtocol.model_validate_json(protocol.model_dump_json()) == protocol
    )
    assert len(protocol.source_bindings) == 15
    assert tuple(item.path for item in protocol.source_bindings) == tuple(
        sorted(item.path for item in protocol.source_bindings)
    )
    assert protocol.payload_bytes_hashed_during_freeze == 94_662
    assert protocol.payload_value_rows_parsed_during_freeze == 0
    assert protocol.input_row_count == 280
    assert protocol.expected_measurement_row_count == 273
    assert protocol.quality_gates == S2_MEASUREMENT_GATES
    assert protocol.future_strategy_family_budget == 1
    assert protocol.future_candidate_budget == 1
    assert protocol.future_parameter_combination_budget == 1
    assert protocol.strategy_parameters_defined == ()
    assert protocol.strategy_rules_defined == ()
    assert protocol.next_authorization == S2_MEASUREMENT_NEXT


def test_builder_hashes_payload_without_parsing_value_rows(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path == PAYLOAD_PATH:
            raise AssertionError("payload value rows must not be parsed during freeze")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    protocol = build_protocol(frozen_at=FROZEN_AT)

    assert protocol.payload_value_rows_parsed_during_freeze == 0


def test_measurement_family_change_is_rejected() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["measurement_definitions"] = list(reversed(payload["measurement_definitions"]))

    with pytest.raises(ValidationError, match="measurement family changed"):
        S2DevelopmentMeasurementProtocol.model_validate(payload)


def test_measurement_gate_change_is_rejected() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["quality_gates"] = list(reversed(payload["quality_gates"]))

    with pytest.raises(ValidationError, match="measurement gates changed"):
        S2DevelopmentMeasurementProtocol.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    (
        "authorizes_payload_value_read_now",
        "authorizes_measurement_calculation_now",
        "authorizes_strategy_parameter_definition",
        "authorizes_market_value_access",
        "authorizes_return_testing",
        "authorizes_validation_access",
        "authorizes_holdout_access",
        "authorizes_strategy_candidate",
        "authorizes_pine",
        "authorizes_paper",
        "authorizes_testnet_strategy_orders",
        "authorizes_production",
        "authorizes_live",
    ),
)
def test_measurement_protocol_rejects_authority_escalation(field: str) -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload[field] = True

    with pytest.raises(ValidationError):
        S2DevelopmentMeasurementProtocol.model_validate(payload)


def test_measurement_protocol_audit_round_trips() -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)
    audit = build_hashed(
        S2DevelopmentMeasurementProtocolAudit,
        "audit_evidence_hash",
        {
            "audited_at": FROZEN_AT,
            "protocol_file_sha256": "1" * 64,
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "builder_contract_hash": protocol.builder_contract_hash,
            "auditor_contract_hash": "2" * 64,
            "payload_file_sha256": protocol.payload_file_sha256,
            "payload_evidence_hash": protocol.payload_evidence_hash,
        },
    )

    assert (
        S2DevelopmentMeasurementProtocolAudit.model_validate_json(audit.model_dump_json()) == audit
    )
    assert audit.source_binding_count == 15
    assert audit.payload_value_rows_parsed == 0
    assert audit.market_values_read == 0
    assert audit.returns_calculated == 0
    assert audit.orders_submitted == 0
    assert audit.next_authorization == S2_MEASUREMENT_NEXT
