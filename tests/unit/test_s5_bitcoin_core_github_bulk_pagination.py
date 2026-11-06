from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (
    S5GitHubBulkFinalResultAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentV4,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_s5_bitcoin_core_github_bulk_acquisition import build_protocol
from scripts.run_s5_bitcoin_core_github_bulk_acquisition import (
    RequestObservation,
    envelope_payload,
    request_url,
    write_json_atomic,
)
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v4 import (
    build_result_v4,
    load_monotonic_pages,
    normalize_terminal_pages,
)


@pytest.fixture(scope="module")
def protocol():
    return build_protocol(frozen_at=datetime(2026, 9, 2, 16, 30, tzinfo=UTC))


def pull(number: int, *, created_at: str) -> dict:
    return {
        "number": number,
        "node_id": f"PR_{number}",
        "state": "closed",
        "created_at": created_at,
        "updated_at": "2020-01-04T00:00:00Z",
        "closed_at": "2020-01-03T00:00:00Z",
        "merged_at": "2020-01-03T00:00:00Z",
        "head": {"sha": f"{number:040x}"},
        "base": {"ref": "master", "sha": "a" * 40},
        "user": {"id": number, "login": f"user-{number}", "type": "User"},
    }


def observation(
    protocol, *, page: int, records: list[dict], terminal: int
) -> RequestObservation:
    prefix = (
        "https://api.github.com/repositories/1181927/pulls?state=all&base=master"
        "&sort=created&direction=asc&per_page=100&page="
    )
    link = None
    if page < terminal:
        link = f'<{prefix}{page + 1}>; rel="next", <{prefix}{terminal}>; rel="last"'
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


def write_page(path: Path, *, protocol, observed: RequestObservation) -> None:
    write_json_atomic(path, envelope_payload(protocol=protocol, observation=observed))


def test_monotonic_terminal_growth_reconstructs_a_passing_manifest(
    protocol, tmp_path: Path
) -> None:
    records_one = [
        pull(number, created_at="2020-01-01T00:00:00Z") for number in range(1, 101)
    ]
    records_two = [
        pull(number, created_at="2020-01-02T00:00:00Z") for number in range(101, 201)
    ]
    observations = (
        observation(protocol, page=1, records=records_one, terminal=2),
        observation(protocol, page=2, records=records_two, terminal=3),
        observation(
            protocol,
            page=3,
            records=[pull(201, created_at="2020-01-03T00:00:00Z")],
            terminal=3,
        ),
    )
    for index, observed in enumerate(observations, start=1):
        write_page(
            tmp_path / protocol.page_file_pattern.format(page=index),
            protocol=protocol,
            observed=observed,
        )

    pages, terminal = load_monotonic_pages(protocol=protocol, page_directory=tmp_path)
    assert terminal == 3
    assert [parsed.terminal_page for _, parsed in pages] == [2, 3, 3]

    normalized = normalize_terminal_pages(pages, terminal_page=terminal)
    result = build_result_v4(
        protocol=protocol,
        pages=normalized,
        started_at=datetime(2026, 9, 2, tzinfo=UTC),
        completed_at=datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        new_request_attempt_count=2,
        resumed_page_count=1,
        wait_count=0,
        wait_seconds=0,
    )

    assert result.failed_gate_count == 0
    assert result.terminal_page_count == 3
    assert result.successful_request_count == 3


def test_monotonic_loader_rejects_terminal_regression(protocol, tmp_path: Path) -> None:
    first = observation(
        protocol,
        page=1,
        records=[
            pull(number, created_at="2020-01-01T00:00:00Z")
            for number in range(1, 101)
        ],
        terminal=3,
    )
    second = observation(
        protocol,
        page=2,
        records=[pull(101, created_at="2020-01-02T00:00:00Z")],
        terminal=2,
    )
    write_page(tmp_path / "page_0001.json", protocol=protocol, observed=first)
    write_page(tmp_path / "page_0002.json", protocol=protocol, observed=second)

    with pytest.raises(ValueError, match="terminal page regressed"):
        load_monotonic_pages(protocol=protocol, page_directory=tmp_path)


def amendment_payload() -> dict:
    bindings = tuple(
        S5HistoryBinding(path=f"source/{index}", file_sha256=f"{index}" * 64)
        for index in range(1, 5)
    )
    payload = {
        "frozen_at": datetime(2026, 9, 3, tzinfo=UTC),
        "builder_contract_hash": "a" * 64,
        "terminal_drift_audit_evidence_hash": "b" * 64,
        "prior_result_evidence_hash": "c" * 64,
        "protocol_evidence_hash": "d" * 64,
        "source_bindings": bindings,
        "limitations": tuple(f"limitation-{index}" for index in range(12)),
    }
    provisional = S5GitHubBulkMonotonicTerminalAmendmentV4.model_construct(
        **payload, amendment_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"amendment_evidence_hash"})
    )
    return complete


def test_amendment_encodes_the_true_completion_bound() -> None:
    complete = amendment_payload()
    amendment = S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate(complete)
    assert amendment.maximum_terminal_page == 300
    assert amendment.maximum_completable_terminal_page == 299
    assert amendment.previous_total_request_attempts == 119
    assert amendment.maximum_v4_request_attempts == 181

    complete["maximum_completable_terminal_page"] = 300
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        {key: value for key, value in complete.items() if key != "amendment_evidence_hash"}
    )
    with pytest.raises(ValidationError):
        S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate(complete)


def final_audit_payload() -> dict:
    payload = {
        "audited_at": datetime(2026, 9, 3, tzinfo=UTC),
        "result_file_sha256": "1" * 64,
        "result_evidence_hash": "2" * 64,
        "protocol_evidence_hash": "3" * 64,
        "amendment_evidence_hash": "4" * 64,
        "amendment_audit_evidence_hash": "5" * 64,
        "runner_contract_hash": "6" * 64,
        "auditor_contract_hash": "7" * 64,
        "corrected_v4_request_attempt_count": 127,
        "total_request_attempt_count": 246,
        "page_count": 245,
        "raw_record_count": 24_500,
        "cohort_record_count": 24_012,
        "post_cutoff_record_count": 488,
    }
    provisional = S5GitHubBulkFinalResultAuditV4.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return complete


def test_final_audit_charges_the_historical_extra_request() -> None:
    complete = final_audit_payload()
    audit = S5GitHubBulkFinalResultAuditV4.model_validate(complete)
    assert audit.total_request_attempt_count == audit.page_count + 1

    complete["total_request_attempt_count"] = 245
    complete["audit_evidence_hash"] = universe_evidence_hash(
        {key: value for key, value in complete.items() if key != "audit_evidence_hash"}
    )
    with pytest.raises(ValidationError):
        S5GitHubBulkFinalResultAuditV4.model_validate(complete)
