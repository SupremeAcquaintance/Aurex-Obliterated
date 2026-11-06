from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.freeze_s5_bitcoin_core_github_bulk_acquisition import build_protocol
from scripts.run_s5_bitcoin_core_github_bulk_acquisition import (
    RequestObservation,
    build_result,
    envelope_payload,
    observation_from_envelope,
    parse_link_header,
    parse_observation,
    request_url,
    write_json_atomic,
)


@pytest.fixture(scope="module")
def protocol():
    return build_protocol(frozen_at=datetime(2026, 9, 2, 16, 30, tzinfo=UTC))


def pull(number: int, *, created_at: str, state: str = "closed") -> dict:
    merged_at = "2020-01-03T00:00:00Z" if state == "closed" else None
    return {
        "number": number,
        "node_id": f"PR_{number}",
        "state": state,
        "created_at": created_at,
        "updated_at": "2020-01-04T00:00:00Z",
        "closed_at": "2020-01-03T00:00:00Z" if state == "closed" else None,
        "merged_at": merged_at,
        "head": {"sha": f"{number:040x}"},
        "base": {"ref": "master", "sha": "a" * 40},
        "user": {"id": number, "login": f"user-{number}", "type": "User"},
    }


def observation(protocol, *, records: list[dict], page: int = 1, link: str | None = None):
    body = json.dumps(records).encode()
    url = request_url(protocol, page)
    return RequestObservation(
        page=page,
        started_at=datetime(2026, 9, 2, tzinfo=UTC),
        completed_at=datetime(2026, 9, 2, 0, 0, 1, tzinfo=UTC),
        elapsed_seconds=1.0,
        request_url=url,
        request_headers={
            "accept": protocol.accept_header,
            "x-github-api-version": protocol.api_version_header,
            "user-agent": protocol.user_agent,
        },
        http_status=200,
        final_url=url,
        response_headers={
            "content-type": "application/json; charset=utf-8",
            "link": link,
            "etag": 'W/"evidence"',
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "59",
            "x-ratelimit-reset": "1788307200",
            "x-ratelimit-resource": "core",
        },
        response_body=body,
        redirect_count=0,
        error_type=None,
        error_message=None,
    )


def test_bulk_protocol_freezes_stable_membership_without_trading_authority(protocol) -> None:
    assert "state=all" in request_url(protocol, 1)
    assert protocol.cohort_created_at_cutoff == protocol.frozen_at
    assert protocol.authorizes_bulk_metadata_acquisition is True
    assert protocol.authorizes_market_values is False
    assert protocol.authorizes_returns is False
    assert protocol.authorizes_testnet_strategy_orders is False
    assert protocol.authorizes_live is False


def test_bulk_page_round_trip_and_terminal_parse(protocol, tmp_path: Path) -> None:
    observed = observation(
        protocol,
        records=[
            pull(1, created_at="2020-01-01T00:00:00Z"),
            pull(2, created_at="2020-01-02T00:00:00Z", state="open"),
        ],
    )
    parsed = parse_observation(observation=observed, protocol=protocol)
    path = tmp_path / "page_0001.json"
    write_json_atomic(path, envelope_payload(protocol=protocol, observation=observed))
    restored = observation_from_envelope(path=path, protocol=protocol)

    assert parsed.terminal_page == 1
    assert parsed.next_page is None
    assert len(parsed.records) == 2
    assert restored.response_body == observed.response_body


def test_bulk_parser_rejects_query_scope_drift(protocol) -> None:
    bad = (
        "<https://api.github.com/repositories/1181927/pulls?state=closed&base=master"
        '&sort=created&direction=asc&per_page=100&page=2>; rel="next", '
        "<https://api.github.com/repositories/1181927/pulls?state=closed&base=master"
        '&sort=created&direction=asc&per_page=100&page=3>; rel="last"'
    )
    with pytest.raises(ValueError, match="query scope"):
        parse_link_header(bad, protocol=protocol, page=1)


def test_bulk_result_passes_only_for_complete_unique_monotonic_pages(
    protocol, tmp_path: Path
) -> None:
    observed = observation(
        protocol,
        records=[
            pull(1, created_at="2020-01-01T00:00:00Z"),
            pull(2, created_at="2020-01-02T00:00:00Z"),
        ],
    )
    parsed = parse_observation(observation=observed, protocol=protocol)
    path = tmp_path / "page_0001.json"
    write_json_atomic(path, envelope_payload(protocol=protocol, observation=observed))
    result = build_result(
        protocol=protocol,
        pages=[(path, parsed)],
        started_at=datetime(2026, 9, 2, tzinfo=UTC),
        completed_at=datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        new_request_attempt_count=1,
        resumed_page_count=0,
        wait_count=0,
        wait_seconds=0,
    )

    assert result.passed_gate_count == 16
    assert result.failed_gate_count == 0
    assert result.raw_record_count == 2
    assert result.cohort_record_count == 2
    assert result.unique_pull_number_count == 2
    assert result.authorizes_normalization_protocol_design is True
    assert result.authorizes_returns is False
    assert result.orders_submitted == 0


def test_bulk_two_page_result_reconstructs_contiguous_manifest(protocol, tmp_path: Path) -> None:
    prefix = (
        "https://api.github.com/repositories/1181927/pulls?state=all&base=master"
        "&sort=created&direction=asc&per_page=100&page="
    )
    first_observation = observation(
        protocol,
        records=[pull(number, created_at="2020-01-01T00:00:00Z") for number in range(1, 101)],
        link=f'<{prefix}2>; rel="next", <{prefix}2>; rel="last"',
    )
    second_observation = observation(
        protocol,
        records=[pull(101, created_at="2020-01-02T00:00:00Z")],
        page=2,
        link=f'<{prefix}1>; rel="prev", <{prefix}1>; rel="first"',
    )
    first = parse_observation(observation=first_observation, protocol=protocol)
    second = parse_observation(observation=second_observation, protocol=protocol)
    first_path = tmp_path / "page_0001.json"
    second_path = tmp_path / "page_0002.json"
    write_json_atomic(
        first_path,
        envelope_payload(protocol=protocol, observation=first_observation),
    )
    write_json_atomic(
        second_path,
        envelope_payload(protocol=protocol, observation=second_observation),
    )
    result = build_result(
        protocol=protocol,
        pages=[(first_path, first), (second_path, second)],
        started_at=datetime(2026, 9, 2, tzinfo=UTC),
        completed_at=datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        new_request_attempt_count=1,
        resumed_page_count=1,
        wait_count=0,
        wait_seconds=0,
    )

    assert result.passed_gate_count == 16
    assert result.terminal_page_count == 2
    assert result.raw_record_count == 101
    assert result.logical_request_attempt_count == 2
    assert result.resumed_page_count == 1


def test_bulk_duplicate_identity_fails_terminal_gate(protocol, tmp_path: Path) -> None:
    observed = observation(
        protocol,
        records=[
            pull(1, created_at="2020-01-01T00:00:00Z"),
            pull(1, created_at="2020-01-02T00:00:00Z"),
        ],
    )
    parsed = parse_observation(observation=observed, protocol=protocol)
    path = tmp_path / "page_0001.json"
    write_json_atomic(path, envelope_payload(protocol=protocol, observation=observed))
    result = build_result(
        protocol=protocol,
        pages=[(path, parsed)],
        started_at=datetime(2026, 9, 2, tzinfo=UTC),
        completed_at=datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        new_request_attempt_count=1,
        resumed_page_count=0,
        wait_count=0,
        wait_seconds=0,
    )

    assert result.failed_gate_count > 0
    assert result.duplicate_pull_number_count == 1
    assert result.authorizes_normalization_protocol_design is False


def test_bulk_parser_rejects_invalid_head_identity(protocol) -> None:
    record = pull(1, created_at="2020-01-01T00:00:00Z")
    record["head"]["sha"] = "not-a-sha"
    with pytest.raises(ValueError, match="head SHA"):
        parse_observation(
            observation=observation(protocol, records=[record]),
            protocol=protocol,
        )
