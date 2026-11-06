from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_bigquery_feasibility import build_hashed
from aurex.backtest_engine.s2_strategy_preregistration import (
    S2_STRATEGY_PREREG_NEXT,
    S2StrategyPreregistration,
    S2StrategyPreregistrationAudit,
)
from scripts.freeze_s2_strategy_preregistration import (
    MEASUREMENT_DATASET_PATH,
    build_protocol,
)

FROZEN_AT = datetime(2026, 8, 30, 17, 0, tzinfo=UTC)


def test_s2_strategy_preregistration_reconstructs_exactly() -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)

    assert S2StrategyPreregistration.model_validate_json(protocol.model_dump_json()) == protocol
    assert len(protocol.source_bindings) == 7
    assert protocol.measurement_dataset_bytes_hashed_during_freeze == 130_754
    assert protocol.measurement_value_rows_parsed_during_freeze == 0
    assert protocol.candidate_count == 1
    assert protocol.candidate.long_rule == ("SETTLEMENT_DEMAND_AGREEMENT_EQ_BOTH_BROADENING")
    assert protocol.candidate.parameter_count == 0
    assert protocol.candidate.parameter_combinations == 1
    assert protocol.expected_weekly_interval_count == 272
    assert protocol.required_price_date_count == 273
    assert protocol.first_required_price_date == "2017-10-16"
    assert protocol.last_required_price_date == "2023-01-02"
    assert protocol.base_total_cost_bps_per_fill == "15"
    assert protocol.stress_total_cost_bps_per_fill == "22.5"
    assert len(protocol.development_gates) == 15
    assert protocol.next_authorization == S2_STRATEGY_PREREG_NEXT


def test_preregistration_hashes_dataset_without_parsing_rows(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path == MEASUREMENT_DATASET_PATH:
            raise AssertionError("preregistration cannot parse measurement value rows")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    protocol = build_protocol(frozen_at=FROZEN_AT)

    assert protocol.measurement_value_rows_parsed_during_freeze == 0


def test_preregistration_rejects_candidate_change() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["candidate"]["parameter_combinations"] = 2

    with pytest.raises(ValidationError):
        S2StrategyPreregistration.model_validate(payload)


def test_preregistration_rejects_gate_reordering() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["development_gates"] = list(reversed(payload["development_gates"]))

    with pytest.raises(ValidationError, match="gate family changed"):
        S2StrategyPreregistration.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    (
        "authorizes_btc_source_acquisition_now",
        "authorizes_btc_market_value_access",
        "authorizes_return_testing",
        "authorizes_historical_screen_access",
        "authorizes_validation_access",
        "authorizes_holdout_access",
        "authorizes_candidate_outcome",
        "authorizes_pine",
        "authorizes_paper",
        "authorizes_testnet_strategy_orders",
        "authorizes_production",
        "authorizes_live",
    ),
)
def test_preregistration_rejects_authority_escalation(field: str) -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload[field] = True

    with pytest.raises(ValidationError):
        S2StrategyPreregistration.model_validate(payload)


def test_preregistration_audit_round_trips() -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)
    audit = build_hashed(
        S2StrategyPreregistrationAudit,
        "audit_evidence_hash",
        {
            "audited_at": FROZEN_AT,
            "protocol_file_sha256": "1" * 64,
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "builder_contract_hash": protocol.builder_contract_hash,
            "measurement_result_evidence_hash": protocol.measurement_result_evidence_hash,
            "measurement_audit_evidence_hash": protocol.measurement_audit_evidence_hash,
            "measurement_dataset_file_sha256": (protocol.measurement_dataset_file_sha256),
            "measurement_row_manifest_evidence_hash": (
                protocol.measurement_row_manifest_evidence_hash
            ),
            "auditor_contract_hash": "2" * 64,
        },
    )

    assert S2StrategyPreregistrationAudit.model_validate_json(audit.model_dump_json()) == audit
    assert audit.measurement_value_rows_parsed == 0
    assert audit.btc_market_values_read == 0
    assert audit.candidate_count == 1
    assert audit.parameter_combination_count == 1
    assert audit.next_authorization == S2_STRATEGY_PREREG_NEXT
