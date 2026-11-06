from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization import (
    S5_ACCEPTED_LOCAL_INCLUSION_UNVERIFIED_PULLS,
    S5_RECOGNIZED_ENDPOINT_404_PULLS,
    S5GitHubCorrectedNormalizationProtocolV2,
)
from scripts import run_s5_bitcoin_core_github_normalization as legacy
from scripts.freeze_s5_bitcoin_core_github_corrected_normalization import (
    build_protocol,
)
from scripts.freeze_s5_bitcoin_core_github_corrected_normalization_execution import (
    build_contract,
)
from scripts.run_s5_bitcoin_core_github_corrected_normalization import (
    accepted_coverage_rows,
    canonical_mapping_rows,
    decode_target_contexts,
    inspect_git,
    target_resolution_rows,
    unresolved_rows,
)


@pytest.fixture(scope="module")
def protocol() -> S5GitHubCorrectedNormalizationProtocolV2:
    return build_protocol(frozen_at=datetime(2026, 9, 8, tzinfo=UTC))


def test_corrected_protocol_preserves_distinct_event_universes(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> None:
    assert protocol.expected_github_accepted_pull_count == 16_279
    assert protocol.expected_canonical_mapping_count == 16_242
    assert protocol.event_universe_rule.startswith("GITHUB_ACCEPTED_PULLS_AND_GIT")


def test_corrected_protocol_freezes_exact_exception_sets(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> None:
    assert protocol.recognized_endpoint_404_pull_numbers == (
        S5_RECOGNIZED_ENDPOINT_404_PULLS
    )
    assert protocol.accepted_local_inclusion_unverified_pull_numbers == (
        S5_ACCEPTED_LOCAL_INCLUSION_UNVERIFIED_PULLS
    )
    assert protocol.disclosed_many_to_one_pull_groups == (
        (25_882, 25_891),
        (26_081, 26_084),
    )


def test_corrected_protocol_coverage_accounts_exactly(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> None:
    assert protocol.expected_accepted_source_linked_count == 16_271
    assert protocol.expected_accepted_source_unverified_count == 8
    assert (
        protocol.expected_accepted_source_linked_count
        + protocol.expected_accepted_source_unverified_count
        == protocol.expected_github_accepted_pull_count
    )


def test_corrected_protocol_remains_research_only(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> None:
    assert protocol.network_access_permitted is False
    assert protocol.github_api_requests_permitted is False
    assert protocol.btc_market_values_permitted is False
    assert protocol.parameters_permitted is False
    assert protocol.returns_permitted is False
    assert protocol.strategy_candidate_permitted is False
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.production_permitted is False
    assert protocol.live_permitted is False


def test_corrected_protocol_rejects_hidden_coverage(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["expected_accepted_source_unverified_count"] = 0
    with pytest.raises(ValidationError):
        S5GitHubCorrectedNormalizationProtocolV2.model_validate(payload)


def test_corrected_protocol_rejects_trading_authority(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["testnet_strategy_orders_permitted"] = True
    with pytest.raises(ValidationError):
        S5GitHubCorrectedNormalizationProtocolV2.model_validate(payload)


def test_corrected_execution_contract_binds_runner_without_authority() -> None:
    contract = build_contract(frozen_at=datetime(2026, 9, 8, tzinfo=UTC))
    assert contract.maximum_local_git_process_count == 2
    assert contract.network_access_permitted is False
    assert contract.github_api_requests_permitted is False
    assert contract.market_values_permitted is False
    assert contract.testnet_strategy_orders_permitted is False
    assert contract.live_permitted is False


def test_corrected_dataset_construction_matches_frozen_counts(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> None:
    lineage = legacy.load_lineage()
    pulls, raw_count, post_cutoff = legacy.load_normalized_pulls(lineage)
    timed, graph, _ = inspect_git(protocol)
    original = legacy.map_git_merges(
        pulls=pulls,
        topology=timed.topology,
        census=lineage.census_result,
        cutoff=lineage.protocol.cohort_created_at_cutoff,
    )
    _, _, contexts = decode_target_contexts()
    accepted = tuple(
        row
        for row in pulls
        if legacy.accepted_pull(
            row,
            cutoff=lineage.protocol.cohort_created_at_cutoff,
        )
    )
    accepted_by_number = {row.pull_number: row for row in accepted}
    merges_by_commit = {row.commit_sha: row for row in timed.topology.merges}
    second_parent_lists: dict[str, list[legacy.GitMerge]] = {}
    for merge in timed.topology.merges:
        second_parent_lists.setdefault(merge.second_parent_sha, []).append(merge)
    merges_by_second_parent = {
        key: tuple(value) for key, value in second_parent_lists.items()
    }
    census_by_pull = {
        row.pull_request_id: row
        for row in lineage.census_result.accepted_pull_request_records
    }
    census_by_commit = {
        row.merge_commit_hash: row
        for row in lineage.census_result.accepted_pull_request_records
    }
    canonical = canonical_mapping_rows(
        legacy_outcome=original,
        topology=timed,
        pulls_by_number={row.pull_number: row for row in pulls},
        census_by_pull=census_by_pull,
        merges_by_commit=merges_by_commit,
        contexts=contexts,
    )
    canonical_by_pull = {row.canonical_pull_number: row for row in canonical}
    resolutions = target_resolution_rows(
        contexts=contexts,
        accepted_by_number=accepted_by_number,
        canonical_by_pull=canonical_by_pull,
        full_graph=graph,
        merges_by_commit=merges_by_commit,
        merges_by_second_parent=merges_by_second_parent,
    )
    coverage = accepted_coverage_rows(
        accepted=accepted,
        canonical_by_pull=canonical_by_pull,
        resolutions_by_pull={row.pull_number: row for row in resolutions},
    )
    accepted_head_lists: dict[str, list[int]] = {}
    for pull in accepted:
        accepted_head_lists.setdefault(pull.head_sha, []).append(pull.pull_number)
    unresolved = unresolved_rows(
        topology=timed,
        canonical_commits={row.merge_commit_sha for row in canonical},
        accepted_by_head={
            key: tuple(value) for key, value in accepted_head_lists.items()
        },
        census_by_commit=census_by_commit,
        contexts=contexts,
    )
    assert (raw_count, len(pulls), post_cutoff) == (24_407, 24_398, 9)
    assert (len(timed.topology.merges), len(graph), len(contexts)) == (
        16_721,
        50_395,
        194,
    )
    assert (len(original.mappings), len(original.unresolved)) == (16_167, 554)
    assert len(canonical) == 16_242
    assert len(unresolved) == 479
    assert len(coverage) == 16_279
    assert sum(row.local_source_link_verified for row in coverage) == 16_271
    assert tuple(
        row.pull_number for row in coverage if not row.local_source_link_verified
    ) == protocol.accepted_local_inclusion_unverified_pull_numbers
