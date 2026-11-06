from __future__ import annotations

from datetime import UTC, datetime
from functools import cache

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_successor_event_outcome_protocol import (
    JAM_EVENT_OUTCOME_NEXT_AUTHORIZATION,
    JamSuccessorEventOutcomeProtocol,
    audit_jam_successor_event_outcome_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_jam_successor_event_outcome_protocol import (
    DEFAULT_DISTRIBUTION_AUDIT,
    DEFAULT_DISTRIBUTION_PROTOCOL,
    DEFAULT_DISTRIBUTION_RESULT,
    DEFAULT_FEATURE_ROWS,
    DEFAULT_FEATURE_SPECIFICATION,
    authoritative_protocol,
    load_inputs,
)


@cache
def _protocol() -> JamSuccessorEventOutcomeProtocol:
    inputs = load_inputs(
        distribution_protocol_path=DEFAULT_DISTRIBUTION_PROTOCOL,
        distribution_result_path=DEFAULT_DISTRIBUTION_RESULT,
        distribution_audit_path=DEFAULT_DISTRIBUTION_AUDIT,
        feature_rows_path=DEFAULT_FEATURE_ROWS,
        feature_specification_path=DEFAULT_FEATURE_SPECIFICATION,
    )
    return authoritative_protocol(
        frozen_at=datetime(2026, 8, 5, tzinfo=UTC),
        inputs=inputs,
        distribution_protocol_path=DEFAULT_DISTRIBUTION_PROTOCOL,
        distribution_result_path=DEFAULT_DISTRIBUTION_RESULT,
        distribution_audit_path=DEFAULT_DISTRIBUTION_AUDIT,
        feature_rows_path=DEFAULT_FEATURE_ROWS,
    )


def _rehash(payload: dict) -> dict:
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        {key: value for key, value in payload.items() if key != "protocol_evidence_hash"}
    )
    return payload


def test_protocol_binds_one_event_and_one_primary_horizon() -> None:
    protocol = _protocol()
    assert audit_jam_successor_event_outcome_protocol(protocol)
    assert protocol.next_required_authorization == (JAM_EVENT_OUTCOME_NEXT_AUTHORIZATION)
    assert [
        (item.condition_id, item.feature_id, item.frozen_threshold)
        for item in protocol.event_definition.conditions
    ] == [
        (
            "EXTREME_AGGRESSIVE_SELL_FLOW",
            "shock_sell_flow_robust_z_5m",
            "4.625575808694040576",
        ),
        (
            "SELL_SIDE_DOMINANCE",
            "shock_sell_share_5m",
            "0.495418809496035904",
        ),
        (
            "NEGATIVE_SHOCK_PRICE_IMPACT",
            "shock_price_impact_bps_5m",
            "-8.269710038582845440",
        ),
        (
            "CONFIRMATION_FLOW_DECAY",
            "sell_flow_decay_ratio_3m_vs_5m",
            "0.938264464494273536",
        ),
        (
            "CAUSAL_PRICE_RECLAIM",
            "reclaim_bps_vs_pre_shock_vwap",
            "0.389389126850270272",
        ),
    ]
    assert [(item.horizon_minutes, item.role) for item in protocol.outcome_pricing.horizons] == [
        (15, "NONSELECTABLE_DIAGNOSTIC"),
        (30, "PRIMARY"),
        (60, "NONSELECTABLE_DIAGNOSTIC"),
    ]
    assert not protocol.statistical_plan.diagnostic_horizons_may_rescue_primary
    assert all(item.gate_id.startswith("HOLDOUT_") for item in protocol.sealed_holdout_gates)
    assert protocol.event_flags_calculated == 0
    assert protocol.future_labels_calculated == []
    assert protocol.return_metrics_calculated == []


def test_protocol_rejects_gate_matrix_tampering_even_when_rehashed() -> None:
    payload = _protocol().model_dump(mode="json")
    payload["development_outcome_gates"][2]["threshold"] = "0"
    with pytest.raises(ValidationError, match="gate matrix changed"):
        JamSuccessorEventOutcomeProtocol.model_validate(_rehash(payload))


def test_protocol_rejects_selectable_diagnostic_horizon() -> None:
    payload = _protocol().model_dump(mode="json")
    payload["outcome_pricing"]["horizons"][0]["role"] = "PRIMARY"
    with pytest.raises(ValidationError, match="horizon role changed"):
        JamSuccessorEventOutcomeProtocol.model_validate(_rehash(payload))


def test_protocol_rejects_any_calculated_label() -> None:
    payload = _protocol().model_dump(mode="json")
    payload["future_labels_calculated"] = ["base_net_return_bps_30m"]
    with pytest.raises(ValidationError, match="calculated an outcome"):
        JamSuccessorEventOutcomeProtocol.model_validate(_rehash(payload))
