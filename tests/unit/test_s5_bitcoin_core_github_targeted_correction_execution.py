from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCorrectionTarget,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (
    S5TargetedCorrectionExecutionContract,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction import build_protocol
from scripts.freeze_s5_bitcoin_core_github_targeted_correction_execution import (
    build_contract,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction_execution import (
    runner_contract_hash as frozen_runner_contract_hash,
)
from scripts.run_s5_bitcoin_core_github_targeted_correction import (
    RequestObservation,
    attempt_path,
    attempt_payload,
    envelope_payload,
    load_existing_responses,
    parse_commit_batch,
    parse_full_graph,
    parse_observation,
    response_path,
    runner_contract_hash,
    write_json_atomic,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


@pytest.fixture(scope="module")
def protocol() -> S5TargetedCompletenessCorrectionProtocol:
    return build_protocol(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))


def github_payload(number: int) -> dict[str, object]:
    return {
        "number": number,
        "node_id": f"node-{number}",
        "state": "closed",
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-03T00:00:00Z",
        "closed_at": "2020-01-02T00:00:00Z",
        "merged_at": "2020-01-02T00:00:00Z",
        "merged": True,
        "merge_commit_sha": SHA_C,
        "head": {"sha": SHA_B},
        "base": {"ref": "master", "sha": SHA_A},
        "user": {"id": 1, "login": "alice", "type": "User"},
    }


def observation(
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
    *,
    status: int = 200,
    payload: dict[str, object] | None = None,
) -> RequestObservation:
    from scripts.run_s5_bitcoin_core_github_targeted_correction import (
        explicit_headers,
        request_url,
    )

    body = json.dumps(
        payload if payload is not None else github_payload(target.pull_number)
    ).encode("utf-8")
    now = datetime(2026, 9, 4, tzinfo=UTC)
    url = request_url(protocol, target.pull_number)
    return RequestObservation(
        target=target,
        started_at=now,
        completed_at=now,
        elapsed_seconds=0.1,
        request_url=url,
        request_headers={
            name.lower(): value for name, value in explicit_headers(protocol).items()
        },
        http_status=status,
        final_url=url,
        response_headers={
            "content-type": "application/json; charset=utf-8",
            "etag": '"test"',
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "59",
            "x-ratelimit-reset": "1800000000",
            "x-ratelimit-resource": "core",
        },
        response_body=body,
        redirect_count=0,
        error_type=None,
        error_message=None,
    )


def test_execution_contract_binds_runner_and_denies_trading() -> None:
    contract = build_contract(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))
    assert contract.runner_contract_hash == runner_contract_hash()
    assert contract.runner_contract_hash == frozen_runner_contract_hash()
    assert contract.maximum_github_request_count == 194
    assert contract.incomplete_attempt_retry_forbidden is True
    assert contract.credentials_permitted is False
    assert contract.mapping_rule_change_permitted is False
    assert contract.market_values_permitted is False
    assert contract.orders_permitted is False


def test_execution_contract_rejects_retry_authority() -> None:
    contract = build_contract(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))
    payload = contract.model_dump(mode="json")
    payload["incomplete_attempt_retry_forbidden"] = False
    with pytest.raises(ValidationError):
        S5TargetedCorrectionExecutionContract.model_validate(payload)


def test_valid_direct_pull_response_is_parsed(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    target = protocol.target_manifest[0]
    parsed = parse_observation(
        observation=observation(protocol, target),
        protocol=protocol,
    )
    assert parsed.target == target
    assert parsed.http_status == 200
    assert parsed.rate_remaining == 59


def test_valid_404_is_preserved_as_evidence(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    target = protocol.target_manifest[0]
    parsed = parse_observation(
        observation=observation(
            protocol,
            target,
            status=404,
            payload={"message": "Not Found"},
        ),
        protocol=protocol,
    )
    assert parsed.http_status == 404


def test_response_rejects_wrong_pull_identity(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    target = protocol.target_manifest[0]
    payload = github_payload(target.pull_number + 1)
    with pytest.raises(ValueError, match="identity"):
        parse_observation(
            observation=observation(protocol, target, payload=payload),
            protocol=protocol,
        )


def test_completed_response_resumes_only_with_attempt_marker(
    protocol: S5TargetedCompletenessCorrectionProtocol,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = protocol.target_manifest[0]
    observed = observation(protocol, target)
    write_json_atomic(
        attempt_path(protocol, target),
        attempt_payload(
            protocol=protocol,
            target=target,
            started_at=observed.started_at,
        ),
    )
    write_json_atomic(
        response_path(protocol, target),
        envelope_payload(protocol=protocol, observation=observed),
    )
    resumed = load_existing_responses(protocol=protocol)
    assert len(resumed) == 1
    assert resumed[0][1].target == target


def test_uncertain_attempt_is_never_retried(
    protocol: S5TargetedCompletenessCorrectionProtocol,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = protocol.target_manifest[0]
    write_json_atomic(
        attempt_path(protocol, target),
        attempt_payload(
            protocol=protocol,
            target=target,
            started_at=datetime(2026, 9, 4, tzinfo=UTC),
        ),
    )
    with pytest.raises(ValueError, match="retry is forbidden"):
        load_existing_responses(protocol=protocol)


def test_full_graph_reconstructs_first_parent_counts() -> None:
    payload = (
        f"{SHA_C} {SHA_B} {SHA_A}\n"
        f"{SHA_B} {SHA_A}\n"
        f"{SHA_A}\n"
    ).encode("ascii")
    graph, stream_hash, first_parent_count, merge_count = parse_full_graph(
        payload,
        cutoff=SHA_C,
    )
    assert len(graph) == 3
    assert len(stream_hash) == 64
    assert first_parent_count == 3
    assert merge_count == 1


def test_commit_batch_matches_census_hash() -> None:
    first_line = b"Merge bitcoin/bitcoin#9: exact diagnostic"
    raw_object = (
        b"tree "
        + SHA_A.encode("ascii")
        + b"\nparent "
        + SHA_A.encode("ascii")
        + b"\nparent "
        + SHA_B.encode("ascii")
        + b"\n\n"
        + first_line
        + b"\n"
    )
    payload = (
        f"{SHA_C} commit {len(raw_object)}\n".encode("ascii")
        + raw_object
        + b"\n"
    )
    target = S5TargetedCorrectionTarget(
        sequence=1,
        pull_number=9,
        target_reasons=("RECOGNIZED_GAP",),
        recognized_failure_category="PRESENT_NOT_ACCEPTED_AT_CUTOFF",
        unmatched_failure_category=None,
        census_merge_commit_sha=SHA_C,
        census_pattern_id="BITCOIN_CORE_MAINTAINER_MERGE",
    )
    first_line_hash = hashlib.sha256(first_line).hexdigest()
    census = SimpleNamespace(
        accepted_pull_request_records=(
            SimpleNamespace(
                pull_request_id=9,
                merge_commit_hash=SHA_C,
                pattern_id="BITCOIN_CORE_MAINTAINER_MERGE",
                first_line_sha256=first_line_hash,
            ),
        )
    )
    diagnostics = parse_commit_batch(
        payload=payload,
        targets=(target,),
        census=census,
    )
    assert diagnostics[0].parent_count == 2
    assert diagnostics[0].first_line_sha256 == first_line_hash
