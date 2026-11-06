from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_successor_feature_protocol import (
    audit_jam_successor_feature_protocol,
    build_jam_successor_feature_protocol,
)
from aurex.backtest_engine.jam_successor_feature_specification import (
    JAM_FEATURE_NEXT_AUTHORIZATION,
    JAM_FEATURE_PASS_DECISION,
    JamSuccessorFeatureSpecification,
    audit_jam_successor_feature_specification,
)

HASH = "a" * 64


def limitations() -> list[str]:
    return [f"Feature protocol limitation {index}" for index in range(14)]


def test_feature_protocol_grants_only_causal_design_authority() -> None:
    protocol = build_jam_successor_feature_protocol(
        frozen_at=datetime(2026, 8, 4, tzinfo=UTC),
        parent_charter_file_sha256=HASH,
        parent_charter_evidence_hash=HASH,
        quality_protocol_file_sha256=HASH,
        quality_protocol_evidence_hash=HASH,
        quality_result_file_sha256=HASH,
        quality_result_evidence_hash=HASH,
        quality_audit_file_sha256=HASH,
        quality_audit_evidence_hash=HASH,
        contamination_ledger_file_sha256=HASH,
        contamination_ledger_evidence_hash=HASH,
        builder_contract_hash=HASH,
        quarantine_manifest_hash=HASH,
        limitations=limitations(),
    )

    assert audit_jam_successor_feature_protocol(protocol)
    assert protocol.causal_feature_definition_permitted
    assert protocol.feature_lookback_definition_permitted
    assert not protocol.raw_market_payload_access_permitted
    assert not protocol.decision_threshold_definition_permitted
    assert not protocol.return_calculation_permitted
    assert not protocol.strategy_creation_permitted


def test_feature_protocol_rejects_return_authority_tampering() -> None:
    protocol = build_jam_successor_feature_protocol(
        frozen_at=datetime(2026, 8, 4, tzinfo=UTC),
        parent_charter_file_sha256=HASH,
        parent_charter_evidence_hash=HASH,
        quality_protocol_file_sha256=HASH,
        quality_protocol_evidence_hash=HASH,
        quality_result_file_sha256=HASH,
        quality_result_evidence_hash=HASH,
        quality_audit_file_sha256=HASH,
        quality_audit_evidence_hash=HASH,
        contamination_ledger_file_sha256=HASH,
        contamination_ledger_evidence_hash=HASH,
        builder_contract_hash=HASH,
        quarantine_manifest_hash=HASH,
        limitations=limitations(),
    )
    payload = protocol.model_dump()
    payload["return_calculation_permitted"] = True

    with pytest.raises(ValidationError):
        type(protocol).model_validate(payload)


def test_stored_feature_specification_has_no_outcome_authority() -> None:
    path = Path(
        "data/evidence/jam_successor_feature_specification_v1.json"
    )
    specification = JamSuccessorFeatureSpecification.model_validate_json(
        path.read_text(encoding="utf-8")
    )

    assert audit_jam_successor_feature_specification(specification)
    assert specification.decision == JAM_FEATURE_PASS_DECISION
    assert (
        specification.next_required_authorization
        == JAM_FEATURE_NEXT_AUTHORIZATION
    )
    assert specification.real_market_rows_inspected == 0
    assert specification.decision_thresholds_defined == []
    assert specification.return_metrics_calculated == []
    assert not specification.creates_signal
    assert not specification.creates_candidate
