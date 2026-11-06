from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.freeze_s5_bitcoin_core_github_preflight import build_protocol
from scripts.run_s5_bitcoin_core_github_preflight import (
    PreflightObservation,
    build_gate_results,
    build_result,
    observation_from_transcript,
    parse_payload,
    parse_terminal_link,
    transcript_payload,
    write_json_atomic,
)


@pytest.fixture(scope="module")
def protocol():
    return build_protocol(frozen_at=datetime(2026, 9, 2, tzinfo=UTC))


def link_header(*, last_page: int = 20_000, base: str = "master") -> str:
    prefix = (
        "https://api.github.com/repos/bitcoin/bitcoin/pulls?state=closed"
        f"&base={base}&sort=created&direction=asc&per_page=1&page="
    )
    return f'<{prefix}2>; rel="next", <{prefix}{last_page}>; rel="last"'


def observation(protocol, *, last_page: int = 20_000) -> PreflightObservation:
    body = json.dumps(
        [
            {
                "number": 142,
                "state": "closed",
                "created_at": "2011-02-01T00:00:00Z",
                "merged_at": "2011-02-02T00:00:00Z",
                "merge_commit_sha": "b" * 40,
                "base": {"ref": "master", "sha": "a" * 40},
            }
        ]
    ).encode()
    return PreflightObservation(
        started_at=datetime(2026, 9, 2, tzinfo=UTC),
        completed_at=datetime(2026, 9, 2, 0, 0, 1, tzinfo=UTC),
        elapsed_seconds=1.0,
        request_headers={
            "accept": protocol.accept_header,
            "x-github-api-version": protocol.api_version_header,
            "user-agent": protocol.user_agent,
        },
        http_status=200,
        final_url=protocol.request_url,
        response_headers={
            "content-type": "application/json; charset=utf-8",
            "link": link_header(last_page=last_page),
            "etag": 'W/"evidence"',
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "59",
            "x-ratelimit-reset": "1788307200",
            "x-ratelimit-resource": "core",
        },
        response_body=body,
        redirect_count=0,
        transport_error_type=None,
        transport_error_message=None,
    )


def test_preflight_parser_recovers_exact_terminal_record_count(protocol) -> None:
    observed = observation(protocol, last_page=20_001)
    parsed = parse_payload(observation=observed, protocol=protocol)

    assert parsed.payload_valid is True
    assert parsed.pull_record_count == 1
    assert parsed.pull_number == 142
    assert parsed.pull_state == "closed"
    assert parsed.base_ref == "master"
    assert parsed.terminal_link_valid is True
    assert parsed.terminal_record_count == 20_001


def test_preflight_gates_pass_for_exact_bounded_response(protocol) -> None:
    observed = observation(protocol)
    parsed = parse_payload(observation=observed, protocol=protocol)
    gates = build_gate_results(protocol=protocol, observation=observed, parsed=parsed)

    assert len(gates) == 14
    assert all(gate.status == "PASS" for gate in gates)


def test_preflight_accepts_closed_unmerged_record_schema(protocol) -> None:
    observed = observation(protocol)
    payload = json.loads(observed.response_body)
    payload[0]["merged_at"] = None
    payload[0]["merge_commit_sha"] = None
    observed = PreflightObservation(
        **{
            **observed.__dict__,
            "response_body": json.dumps(payload).encode(),
        }
    )
    parsed = parse_payload(observation=observed, protocol=protocol)
    gates = build_gate_results(protocol=protocol, observation=observed, parsed=parsed)

    assert parsed.payload_valid is True
    assert parsed.merged_at is None
    assert parsed.merge_commit_sha is None
    assert all(gate.status == "PASS" for gate in gates)


def test_terminal_link_rejects_query_scope_drift(protocol) -> None:
    terminal, valid = parse_terminal_link(
        link_header(last_page=20_000, base="release"), protocol=protocol
    )
    assert terminal is None
    assert valid is False


def test_transcript_round_trip_and_result_budget(protocol, tmp_path: Path) -> None:
    observed = observation(protocol, last_page=20_001)
    transcript = tmp_path / "preflight.json"
    write_json_atomic(
        transcript,
        transcript_payload(protocol=protocol, observation=observed),
    )
    reconstructed = observation_from_transcript(path=transcript, protocol=protocol)
    result = build_result(
        protocol=protocol,
        observation=reconstructed,
        transcript_path=transcript,
        executed_at=datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
    )

    assert reconstructed.response_body == observed.response_body
    assert result.passed_gate_count == 14
    assert result.failed_gate_count == 0
    assert result.terminal_record_count == 20_001
    assert result.bulk_request_page_count_at_100 == 201
    assert result.bulk_unauthenticated_hours_lower_bound == 4
    assert result.authorizes_bulk_acquisition_protocol_design is True
    assert result.authorizes_bulk_metadata_acquisition_now is False
