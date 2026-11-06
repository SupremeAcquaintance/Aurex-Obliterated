from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (
    S5_TARGETED_CORRECTION_GATE_IDS,
    S5TargetedCompletenessCorrectionProtocol,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction import build_protocol


@pytest.fixture(scope="module")
def protocol() -> S5TargetedCompletenessCorrectionProtocol:
    return build_protocol(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))


def test_protocol_freezes_exact_adjudicated_target_union(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    assert protocol.recognized_gap_target_count == 83
    assert protocol.unmatched_pull_target_count == 112
    assert protocol.overlap_target_count == 1
    assert protocol.unique_target_count == 194
    assert len(protocol.target_manifest) == 194
    assert protocol.target_manifest[0].pull_number == 10
    assert protocol.target_manifest[-1].pull_number == 36_048


def test_protocol_target_manifest_is_sorted_unique_and_complete(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    numbers = tuple(target.pull_number for target in protocol.target_manifest)
    assert numbers == tuple(sorted(set(numbers)))
    assert tuple(target.sequence for target in protocol.target_manifest) == tuple(
        range(1, 195)
    )
    recognized = {
        target.pull_number
        for target in protocol.target_manifest
        if "RECOGNIZED_GAP" in target.target_reasons
    }
    unmatched = {
        target.pull_number
        for target in protocol.target_manifest
        if "UNMATCHED_ACCEPTED_PULL" in target.target_reasons
    }
    assert (len(recognized), len(unmatched), len(recognized & unmatched)) == (
        83,
        112,
        1,
    )


def test_recognized_targets_bind_census_identity(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    recognized = tuple(
        target
        for target in protocol.target_manifest
        if "RECOGNIZED_GAP" in target.target_reasons
    )
    assert all(target.census_merge_commit_sha for target in recognized)
    assert all(target.census_pattern_id for target in recognized)
    assert all(
        target.recognized_failure_category
        in {
            "ABSENT_FROM_MASTER_SCOPED_COHORT",
            "PRESENT_NOT_ACCEPTED_AT_CUTOFF",
            "HEAD_SHA_MISMATCH",
            "AMBIGUOUS_HEAD_SHA",
        }
        for target in recognized
    )


def test_protocol_is_acquisition_only(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    assert protocol.required_gate_ids == S5_TARGETED_CORRECTION_GATE_IDS
    assert protocol.maximum_github_request_count == 194
    assert protocol.credentials_permitted is False
    assert protocol.mapping_rule_change_permitted is False
    assert protocol.accepted_event_creation_permitted is False
    assert protocol.btc_market_values_permitted is False
    assert protocol.orders_submitted == 0


def test_protocol_binds_exact_ten_source_artifacts(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    assert len(protocol.source_bindings) == 10
    paths = tuple(binding.path for binding in protocol.source_bindings)
    assert paths == tuple(sorted(set(paths)))


def test_protocol_rejects_target_removal(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["target_manifest"] = payload["target_manifest"][:-1]
    with pytest.raises(ValidationError):
        S5TargetedCompletenessCorrectionProtocol.model_validate(payload)


def test_protocol_rejects_mapping_authority(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["mapping_rule_change_permitted"] = True
    with pytest.raises(ValidationError):
        S5TargetedCompletenessCorrectionProtocol.model_validate(payload)


def test_protocol_rejects_target_identity_tampering(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["target_manifest"][0]["pull_number"] = 9
    with pytest.raises(ValidationError):
        S5TargetedCompletenessCorrectionProtocol.model_validate(payload)
