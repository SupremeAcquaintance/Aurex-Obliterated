from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure import (
    S5_NORMALIZATION_FAILURE_GATE_IDS,
    S5_RECOGNIZED_FAILURE_CATEGORIES,
    S5_UNMATCHED_PULL_CATEGORIES,
    S5NormalizationFailureAdjudicationProtocol,
)
from scripts import run_s5_bitcoin_core_github_normalization as original
from scripts.freeze_s5_bitcoin_core_github_normalization_failure_adjudication import (
    build_protocol,
)
from scripts.run_s5_bitcoin_core_github_normalization_failure_adjudication import (
    DiagnosticPull,
    FullGraph,
    classify_recognized,
    classify_unmatched,
    parse_full_graph,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40
SHA_E = "e" * 40
CUTOFF = datetime(2026, 9, 2, 21, 43, 33, tzinfo=UTC)


def diagnostic_pull(
    number: int,
    *,
    head_sha: str,
    merge_commit_sha: str | None,
) -> DiagnosticPull:
    normalized = original.normalize_pull(
        {
            "number": number,
            "node_id": f"node-{number}",
            "state": "closed",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-03T00:00:00Z",
            "closed_at": "2026-01-02T00:00:00Z",
            "merged_at": "2026-01-02T00:00:00Z",
            "head": {"sha": head_sha},
            "base": {"ref": "master", "sha": SHA_A},
            "user": {"id": number + 100, "login": "alice", "type": "User"},
        },
        sequence=number,
        source_page=1,
        source_page_sha256="1" * 64,
        source_response_body_sha256="2" * 64,
    )
    return DiagnosticPull(normalized=normalized, merge_commit_sha=merge_commit_sha)


@pytest.fixture(scope="module")
def protocol() -> S5NormalizationFailureAdjudicationProtocol:
    return build_protocol(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))


def test_failure_protocol_binds_the_observed_stop(
    protocol: S5NormalizationFailureAdjudicationProtocol,
) -> None:
    assert protocol.original_passed_gate_count == 13
    assert protocol.original_failed_gate_count == 4
    assert protocol.original_recognized_gap_count == 83
    assert protocol.original_unmatched_accepted_pull_count == 112
    assert protocol.original_ambiguous_git_merge_count == 1
    assert protocol.required_gate_ids == S5_NORMALIZATION_FAILURE_GATE_IDS


def test_failure_protocol_freezes_complete_diagnostic_categories(
    protocol: S5NormalizationFailureAdjudicationProtocol,
) -> None:
    assert protocol.recognized_classification_order == S5_RECOGNIZED_FAILURE_CATEGORIES
    assert protocol.unmatched_classification_order == S5_UNMATCHED_PULL_CATEGORIES
    assert protocol.fixed_recent_merge_windows_days == (1, 7, 30)
    assert "merge_commit_sha" in protocol.diagnostic_github_fields


def test_failure_protocol_grants_no_correction_or_trading_authority(
    protocol: S5NormalizationFailureAdjudicationProtocol,
) -> None:
    assert protocol.network_access_permitted is False
    assert protocol.direct_pull_requests_permitted is False
    assert protocol.merge_commit_sha_mapping_change_permitted is False
    assert protocol.normalization_rule_change_permitted is False
    assert protocol.btc_market_values_read == 0
    assert protocol.orders_submitted == 0


def test_failure_protocol_rejects_relaxed_observed_gap(
    protocol: S5NormalizationFailureAdjudicationProtocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["original_recognized_gap_count"] = 82
    with pytest.raises(ValidationError):
        S5NormalizationFailureAdjudicationProtocol.model_validate(payload)


def test_failure_protocol_rejects_mapping_change_authority(
    protocol: S5NormalizationFailureAdjudicationProtocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["merge_commit_sha_mapping_change_permitted"] = True
    with pytest.raises(ValidationError):
        S5NormalizationFailureAdjudicationProtocol.model_validate(payload)


def test_full_graph_reconstructs_first_parent_chain() -> None:
    payload = (
        f"{SHA_C} {SHA_B} {SHA_D}\n"
        f"{SHA_D} {SHA_A}\n"
        f"{SHA_B} {SHA_A}\n"
        f"{SHA_A}\n"
    ).encode("ascii")
    graph = parse_full_graph(payload, source_cutoff_commit=SHA_C)
    assert len(graph.commit_parents) == 4
    assert graph.first_parent_topology.first_parent_count == 3
    assert graph.first_parent_topology.merge_count == 1
    assert graph.first_parent_topology.merges[0].second_parent_sha == SHA_D


def test_unmatched_pull_can_be_diagnosed_by_exact_merge_commit_sha() -> None:
    merge = original.GitMerge(3, SHA_C, SHA_B, SHA_D)
    topology = original.GitTopology(3, 1, 1, 1, 0, (merge,), "3" * 64)
    graph = FullGraph(
        commit_parents={SHA_A: (), SHA_B: (SHA_A,), SHA_C: (SHA_B, SHA_D), SHA_D: ()},
        first_parent_topology=topology,
        stream_sha256="4" * 64,
    )
    pull = diagnostic_pull(1, head_sha=SHA_E, merge_commit_sha=SHA_C)
    outcome = original.map_git_merges(
        pulls=(pull.normalized,),
        topology=topology,
        census=SimpleNamespace(accepted_pull_request_records=()),
        cutoff=CUTOFF,
    )
    categories, rows = classify_unmatched(
        pulls=(pull,),
        topology=topology,
        full_graph=graph,
        original_outcome=outcome,
        cutoff=CUTOFF,
    )
    assert len(rows) == 1
    assert categories["MERGE_COMMIT_SHA_EQUALS_FIRST_PARENT_MERGE"] == (1,)


def test_recognized_pull_absent_from_master_scope_is_explicit() -> None:
    merge = original.GitMerge(3, SHA_C, SHA_B, SHA_D)
    topology = original.GitTopology(3, 1, 1, 1, 0, (merge,), "3" * 64)
    census_row = SimpleNamespace(
        pull_request_id=9,
        merge_commit_hash=SHA_C,
    )
    lineage = SimpleNamespace(
        protocol=SimpleNamespace(cohort_created_at_cutoff=CUTOFF),
        census_result=SimpleNamespace(accepted_pull_request_records=(census_row,)),
    )
    categories = classify_recognized(
        pulls=(),
        topology=topology,
        lineage=lineage,
    )
    assert categories["ABSENT_FROM_MASTER_SCOPED_COHORT"] == (9,)
