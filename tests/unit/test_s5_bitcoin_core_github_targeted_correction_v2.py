from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2 import (
    S5TargetedCorrectionV2Protocol,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction import (
    build_protocol as build_target_protocol,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction_v2 import (
    build_protocol,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction_v2_execution import (
    build_contract,
)
from scripts.run_s5_bitcoin_core_github_targeted_correction import parse_observation
from scripts.run_s5_bitcoin_core_github_targeted_correction_v2 import perform_request


@pytest.fixture(scope="module")
def protocol() -> S5TargetedCorrectionV2Protocol:
    return build_protocol(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))


def test_v2_protocol_discloses_and_bounds_remedial_retry(
    protocol: S5TargetedCorrectionV2Protocol,
) -> None:
    assert protocol.v1_uncertain_attempt_target == 10
    assert protocol.v1_uncertain_attempt_count == 1
    assert protocol.v1_accepted_response_count == 0
    assert protocol.v2_remedial_request_target_count == 1
    assert protocol.untouched_first_request_target_count == 193
    assert protocol.maximum_v2_request_count == 194
    assert protocol.maximum_cumulative_possible_request_count == 195


def test_v2_protocol_freezes_corrected_response_lifecycle(
    protocol: S5TargetedCorrectionV2Protocol,
) -> None:
    assert (
        protocol.transport_response_lifecycle
        == "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    )
    assert protocol.incomplete_v2_attempt_retry_forbidden is True
    assert protocol.completed_v2_response_resume_permitted is True


def test_v2_protocol_preserves_research_only_authority(
    protocol: S5TargetedCorrectionV2Protocol,
) -> None:
    assert protocol.credentials_permitted is False
    assert protocol.mapping_rule_change_permitted is False
    assert protocol.accepted_event_creation_permitted is False
    assert protocol.market_values_permitted is False
    assert protocol.returns_permitted is False
    assert protocol.orders_permitted is False


def test_v2_protocol_binds_failure_lineage(
    protocol: S5TargetedCorrectionV2Protocol,
) -> None:
    assert len(protocol.source_bindings) == 8
    assert protocol.v1_context_manager_defect_verified is True
    assert protocol.target_count == 194


def test_v2_protocol_rejects_broader_retry_budget(
    protocol: S5TargetedCorrectionV2Protocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["maximum_cumulative_possible_request_count"] = 196
    with pytest.raises(ValidationError):
        S5TargetedCorrectionV2Protocol.model_validate(payload)


def test_v2_protocol_rejects_trading_authority(
    protocol: S5TargetedCorrectionV2Protocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["orders_permitted"] = True
    with pytest.raises(ValidationError):
        S5TargetedCorrectionV2Protocol.model_validate(payload)


def test_v2_execution_contract_binds_corrected_lifecycle() -> None:
    contract = build_contract(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))
    assert (
        contract.corrected_response_lifecycle
        == "CLIENT_SEND_STREAM_TRUE_TRY_FINALLY_RESPONSE_CLOSE"
    )
    assert contract.maximum_v2_request_count == 194
    assert contract.maximum_cumulative_possible_request_count == 195
    assert contract.credentials_permitted is False
    assert contract.orders_permitted is False


def test_v2_response_is_closed_without_context_manager_support() -> None:
    target_protocol = build_target_protocol(
        frozen_at=datetime(2026, 9, 4, tzinfo=UTC)
    )
    target = target_protocol.target_manifest[0]
    payload = (
        b'{"number":10,"node_id":"node-10","state":"closed",'
        b'"created_at":"2020-01-01T00:00:00Z",'
        b'"updated_at":"2020-01-03T00:00:00Z",'
        b'"closed_at":"2020-01-02T00:00:00Z",'
        b'"merged_at":"2020-01-02T00:00:00Z","merged":true,'
        b'"merge_commit_sha":"cccccccccccccccccccccccccccccccccccccccc",'
        b'"head":{"sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},'
        b'"base":{"ref":"master",'
        b'"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},'
        b'"user":{"id":1,"login":"alice","type":"User"}}'
    )

    class FakeResponse:
        status_code = 200
        url = "https://api.github.com/repos/bitcoin/bitcoin/pulls/10"
        history = ()
        headers = {
            "content-type": "application/json",
            "etag": '"test"',
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "59",
            "x-ratelimit-reset": "1800000000",
            "x-ratelimit-resource": "core",
        }

        def __init__(self) -> None:
            self.closed = False

        def iter_bytes(self):
            yield payload

        def close(self) -> None:
            self.closed = True

    response = FakeResponse()

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        def build_request(self, method, url, headers):
            return SimpleNamespace(method=method, url=url, headers=headers)

        def send(self, _request, *, stream):
            assert stream is True
            return response

    observed = perform_request(
        target_protocol=target_protocol,
        target=target,
        client_factory=FakeClient,
    )
    parsed = parse_observation(
        observation=observed,
        protocol=target_protocol,
    )
    assert parsed.http_status == 200
    assert response.closed is True
    assert observed.error_type is None
