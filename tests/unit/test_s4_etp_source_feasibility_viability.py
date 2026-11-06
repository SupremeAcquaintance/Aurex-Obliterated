from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s4_etp_source_feasibility_viability import (
    S4_UNREACHABLE_GATE_IDS,
    S4EtpSourceFeasibilityViabilityReview,
    audit_s4_viability_review,
)
from scripts.record_s4_etp_source_feasibility_viability import build_review

FIXED_TIME = datetime(2026, 8, 31, 19, 0, tzinfo=UTC)


def built_review() -> S4EtpSourceFeasibilityViabilityReview:
    return build_review(reviewed_at=FIXED_TIME)


def test_s4_viability_review_binds_frozen_protocol_and_audit() -> None:
    review = built_review()
    assert audit_s4_viability_review(review) is True
    assert len(review.source_bindings) == 2
    assert review.protocol_reconstructed_before_review is True
    assert review.unreachable_gate_ids == S4_UNREACHABLE_GATE_IDS


def test_s4_viability_review_proves_protocol_pass_is_unreachable() -> None:
    review = built_review()
    assert review.allowed_sec_submission_keys_insufficient is True
    assert review.issuer_page_bodies_forbidden is True
    assert review.sec_filing_bodies_forbidden is True
    assert review.xbrl_fact_endpoints_forbidden is True
    assert review.permitted_sources_cannot_prove_daily_history_descriptors is True
    assert review.permitted_sources_cannot_prove_per_fund_regime_dates is True
    assert review.protocol_pass_condition_reachable is False


def test_s4_viability_review_stops_before_network_without_consuming_run() -> None:
    review = built_review()
    assert review.network_requests_executed == 0
    assert review.run_authority_consumed is False
    assert review.protocol_run_permitted_after_review is False
    assert review.authorizes_protocol_run is False
    assert review.authorizes_protocol_amendment is False
    assert review.decision == "BLOCK_S4_RUN_PROTOCOL_PASS_CONDITION_UNREACHABLE"


def test_s4_viability_review_does_not_infer_source_or_edge_failure() -> None:
    review = built_review()
    assert review.source_feasibility_conclusion == (
        "NOT_EVALUATED_PROTOCOL_STOPPED_BEFORE_NETWORK"
    )
    assert review.predictive_edge_conclusion == "NOT_EVALUATED"
    assert review.etp_numeric_values_read == 0
    assert review.btc_market_values_read == 0
    assert review.returns_calculated == 0
    assert review.orders_submitted == 0
    assert review.real_net_profit_usd == "0"


def test_s4_viability_review_authorizes_only_distinct_s5_charter() -> None:
    review = built_review()
    assert review.next_authorization == (
        "FREEZE_AND_AUDIT_DISTINCT_S5_MECHANISM_CHARTER_ONLY"
    )
    assert review.authorizes_etp_numeric_payload is False
    assert review.authorizes_market_values is False
    assert review.authorizes_returns is False
    assert review.authorizes_paper is False
    assert review.authorizes_testnet_strategy_orders is False
    assert review.authorizes_production is False
    assert review.authorizes_live is False


def test_s4_viability_review_rejects_run_authority_tampering() -> None:
    payload = json.loads(built_review().model_dump_json())
    payload["authorizes_protocol_run"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        S4EtpSourceFeasibilityViabilityReview.model_validate(payload)
