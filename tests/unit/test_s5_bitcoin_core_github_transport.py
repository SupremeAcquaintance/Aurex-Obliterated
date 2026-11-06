from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_transport import (
    S5GitHubTransportDecision,
    audit_s5_github_transport_decision,
)
from scripts.freeze_s5_bitcoin_core_github_transport_decision import build_decision


def test_transport_decision_selects_one_request_official_rest_preflight() -> None:
    decision = build_decision(frozen_at=datetime(2026, 9, 2, tzinfo=UTC))

    assert decision.selected_transport == "REST_LIST_CLOSED_MASTER_PULLS"
    assert decision.preflight_request_count == 1
    assert decision.preflight_query_per_page == 1
    assert decision.selected_query_state == "closed"
    assert decision.selected_query_base == "master"
    assert decision.selected_query_sort == "created"
    assert decision.selected_query_direction == "asc"
    assert decision.selected_transport_requires_authentication is False
    assert decision.github_api_requests_executed == 0
    assert decision.authorizes_preflight_protocol_design is True
    assert decision.authorizes_preflight_request_now is False
    assert decision.authorizes_bulk_metadata_acquisition is False
    assert decision.passed_gate_count == 12
    assert decision.failed_gate_count == 0
    assert audit_s5_github_transport_decision(decision)


def test_transport_decision_rejects_every_nonselected_path() -> None:
    decision = build_decision(frozen_at=datetime(2026, 9, 2, tzinfo=UTC))

    dispositions = {item.option_id: item.disposition for item in decision.transport_options}
    assert dispositions == {
        "DIRECT_PULL_BY_NUMBER": "REJECTED",
        "REST_LIST_CLOSED_MASTER_PULLS": "SELECTED",
        "GRAPHQL_PULL_REQUEST_PAGINATION": "REJECTED",
        "LOCAL_GIT_ONLY": "REJECTED",
        "THIRD_PARTY_ARCHIVE": "REJECTED",
    }


def test_transport_decision_hash_rejects_authority_tampering() -> None:
    decision = build_decision(frozen_at=datetime(2026, 9, 2, tzinfo=UTC))
    changed = decision.model_dump(mode="json")
    changed["authorizes_bulk_metadata_acquisition"] = True

    with pytest.raises(ValidationError, match="Input should be False"):
        S5GitHubTransportDecision.model_validate(changed)
