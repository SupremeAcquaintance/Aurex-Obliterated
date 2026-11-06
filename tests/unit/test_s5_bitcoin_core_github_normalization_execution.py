from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (
    S5GitHubNormalizedPull,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (
    S5AcceptedPullRequestRecord,
)
from scripts.freeze_s5_bitcoin_core_github_normalization_execution import (
    SYNTHETIC_TEST_IDS,
    build_contract,
)
from scripts.run_s5_bitcoin_core_github_normalization import (
    GitMerge,
    GitTopology,
    map_git_merges,
    normalize_pull,
    parse_git_parent_stream,
    serialize_rows,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40
SHA_E = "e" * 40
SHA_F = "f" * 40
SHA_G = "1" * 40
CUTOFF = datetime(2026, 9, 2, 21, 43, 33, tzinfo=UTC)


def pull_payload(
    number: int,
    *,
    head_sha: str,
    login: str | None = "alice",
    user_type: str = "User",
) -> dict[str, object]:
    user = None if login is None else {"id": number + 100, "login": login, "type": user_type}
    return {
        "number": number,
        "node_id": f"node-{number}",
        "state": "closed",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-03T00:00:00Z",
        "closed_at": "2026-01-02T00:00:00Z",
        "merged_at": "2026-01-02T00:00:00Z",
        "head": {"sha": head_sha},
        "base": {"ref": "master", "sha": SHA_A},
        "user": user,
    }


def normalized_pull(
    number: int,
    *,
    head_sha: str,
    login: str | None = "alice",
    user_type: str = "User",
) -> S5GitHubNormalizedPull:
    return normalize_pull(
        pull_payload(number, head_sha=head_sha, login=login, user_type=user_type),
        sequence=number,
        source_page=1,
        source_page_sha256="2" * 64,
        source_response_body_sha256="3" * 64,
    )


def topology(*merges: GitMerge) -> GitTopology:
    return GitTopology(
        first_parent_count=len(merges) + 2,
        root_count=1,
        single_parent_count=1,
        merge_count=len(merges),
        octopus_count=0,
        merges=merges,
        stream_sha256="4" * 64,
    )


def census_record(commit_sha: str, pull_number: int) -> S5AcceptedPullRequestRecord:
    return S5AcceptedPullRequestRecord(
        sequence=1,
        merge_commit_hash=commit_sha,
        parent_count=2,
        pull_request_id=pull_number,
        pattern_id="BITCOIN_CORE_MAINTAINER_MERGE",
        first_line_sha256="5" * 64,
    )


def test_normalize_pull_classifies_null_and_bot_actor() -> None:
    unknown = normalized_pull(1, head_sha=SHA_D, login=None)
    bot = normalized_pull(2, head_sha=SHA_E, login="builder[bot]")
    typed_bot = normalized_pull(3, head_sha=SHA_F, login="builder", user_type="Bot")
    assert unknown.actor_identity_status == "UNKNOWN_DELETED_OR_NULL"
    assert unknown.actor_class == "UNKNOWN"
    assert bot.actor_class == "BOT"
    assert typed_bot.actor_class == "BOT"


def test_git_parent_stream_reconstructs_topology() -> None:
    payload = (
        f"{SHA_A}\n"
        f"{SHA_B} {SHA_A}\n"
        f"{SHA_C} {SHA_B} {SHA_D}\n"
    ).encode("ascii")
    parsed = parse_git_parent_stream(payload)
    assert parsed.first_parent_count == 3
    assert parsed.root_count == 1
    assert parsed.single_parent_count == 1
    assert parsed.merge_count == 1
    assert parsed.merges[0].second_parent_sha == SHA_D


def test_git_parent_stream_rejects_invalid_sha() -> None:
    with pytest.raises(ValueError, match="invalid SHA1"):
        parse_git_parent_stream(b"not-a-sha\n")


def test_mapping_requires_recognized_number_and_head_sha() -> None:
    merge = GitMerge(3, SHA_C, SHA_B, SHA_D)
    census = SimpleNamespace(accepted_pull_request_records=(census_record(SHA_C, 1),))
    outcome = map_git_merges(
        pulls=(normalized_pull(1, head_sha=SHA_D),),
        topology=topology(merge),
        census=census,
        cutoff=CUTOFF,
    )
    assert outcome.recognized_exact_count == 1
    assert outcome.recovered_count == 0
    assert outcome.unmatched_accepted_count == 0
    assert outcome.mappings[0].pull_number == 1


def test_mapping_recovers_unrecognized_head_and_preserves_unresolved() -> None:
    recovered = GitMerge(3, SHA_C, SHA_B, SHA_D)
    unresolved = GitMerge(4, SHA_E, SHA_C, SHA_F)
    census = SimpleNamespace(accepted_pull_request_records=())
    outcome = map_git_merges(
        pulls=(normalized_pull(1, head_sha=SHA_D),),
        topology=topology(recovered, unresolved),
        census=census,
        cutoff=CUTOFF,
    )
    assert outcome.recovered_count == 1
    assert len(outcome.unresolved) == 1
    assert outcome.unresolved[0].resolution_status == "NO_ACCEPTED_GITHUB_HEAD_MATCH"


def test_reverse_coverage_detects_unmatched_accepted_pull() -> None:
    census = SimpleNamespace(accepted_pull_request_records=())
    outcome = map_git_merges(
        pulls=(normalized_pull(1, head_sha=SHA_D),),
        topology=topology(),
        census=census,
        cutoff=CUTOFF,
    )
    assert outcome.unmatched_accepted_count == 1
    assert "do not map" in outcome.diagnostics[0]


def test_mapping_detects_ambiguous_head_sha() -> None:
    merge = GitMerge(3, SHA_C, SHA_B, SHA_D)
    census = SimpleNamespace(accepted_pull_request_records=())
    outcome = map_git_merges(
        pulls=(
            normalized_pull(1, head_sha=SHA_D),
            normalized_pull(2, head_sha=SHA_D),
        ),
        topology=topology(merge),
        census=census,
        cutoff=CUTOFF,
    )
    assert outcome.ambiguous_count == 1
    assert len(outcome.unresolved) == 1


def test_jsonl_serialization_is_deterministic() -> None:
    rows = (normalized_pull(1, head_sha=SHA_D),)
    first = serialize_rows(rows)
    assert first == serialize_rows(rows)
    assert first.endswith(b"\n")
    assert b'"actor_class"' in first


def test_normalized_row_rejects_inconsistent_actor_class() -> None:
    row = normalized_pull(1, head_sha=SHA_D)
    payload = row.model_dump(mode="json")
    payload["actor_class"] = "UNKNOWN"
    with pytest.raises(ValidationError):
        S5GitHubNormalizedPull.model_validate(payload)


def test_execution_contract_binds_runner_and_synthetic_tests() -> None:
    contract = build_contract(frozen_at=datetime(2026, 9, 3, tzinfo=UTC))
    assert contract.synthetic_test_ids == SYNTHETIC_TEST_IDS
    assert contract.authorizes_single_local_normalization_run is True
    assert contract.authorizes_network_access is False
    assert contract.authorizes_btc_market_values is False
