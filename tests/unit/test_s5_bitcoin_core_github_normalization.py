from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (
    S5_GITHUB_NORMALIZATION_GATE_IDS,
    S5GitHubNormalizationProtocol,
)
from scripts.freeze_s5_bitcoin_core_github_normalization import (
    build_protocol,
    file_sha256,
)


@pytest.fixture(scope="module")
def protocol() -> S5GitHubNormalizationProtocol:
    return build_protocol(frozen_at=datetime(2026, 9, 3, tzinfo=UTC))


def test_protocol_freezes_exact_predecessor_counts_and_zero_trading_authority(
    protocol: S5GitHubNormalizationProtocol,
) -> None:
    assert protocol.expected_page_count == 245
    assert protocol.expected_raw_record_count == 24_407
    assert protocol.expected_cohort_record_count == 24_398
    assert protocol.expected_post_cutoff_record_count == 9
    assert protocol.expected_first_parent_commit_count == 17_543
    assert protocol.expected_merge_commit_count == 16_721
    assert protocol.expected_recognized_pull_merge_count == 7_961
    assert protocol.required_gate_ids == S5_GITHUB_NORMALIZATION_GATE_IDS
    assert protocol.btc_market_values_permitted is False
    assert protocol.returns_permitted is False
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.live_permitted is False


def test_protocol_requires_exact_bidirectional_sha_mapping(
    protocol: S5GitHubNormalizationProtocol,
) -> None:
    assert (
        protocol.recognized_pull_rule
        == "CENSUS_PULL_NUMBER_AND_SECOND_PARENT_HEAD_SHA_MUST_BOTH_MATCH"
    )
    assert (
        protocol.reverse_coverage_rule
        == "EVERY_ACCEPTED_GITHUB_PULL_MUST_MAP_TO_EXACTLY_ONE_FROZEN_GIT_MERGE"
    )
    assert (
        protocol.unresolved_git_merge_rule
        == "PRESERVE_WITH_STATUS_AND_NEVER_IMPUTE_AS_ACCEPTED_PULL"
    )


def test_protocol_preserves_actor_uncertainty(protocol: S5GitHubNormalizationProtocol) -> None:
    assert protocol.actor_identity_rule.startswith("USER_ID_PRIMARY")
    assert protocol.actor_alias_rule.startswith("DO_NOT_MERGE")
    assert "actor_identity_status" in protocol.normalized_pull_fields
    assert "actor_class" in protocol.normalized_pull_fields


def test_protocol_source_bindings_rehash(protocol: S5GitHubNormalizationProtocol) -> None:
    assert len(protocol.source_bindings) == 16
    assert tuple(item.path for item in protocol.source_bindings) == tuple(
        sorted(item.path for item in protocol.source_bindings)
    )
    assert all(
        file_sha256(Path(item.path)) == item.file_sha256
        for item in protocol.source_bindings
    )


def test_protocol_rejects_relaxed_recognized_count(
    protocol: S5GitHubNormalizationProtocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["expected_recognized_pull_merge_count"] = 7_960
    with pytest.raises(ValidationError):
        S5GitHubNormalizationProtocol.model_validate(payload)


def test_protocol_rejects_market_authority(
    protocol: S5GitHubNormalizationProtocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["btc_market_values_permitted"] = True
    with pytest.raises(ValidationError):
        S5GitHubNormalizationProtocol.model_validate(payload)
