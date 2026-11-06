from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_release_tag_source_remediation import (
    S5_RELEASE_REMEDIATION_GATES,
    S5_RELEASE_REMEDIATION_NEXT,
    S5ReleaseTagSourceRemediationProtocolV1,
)
from scripts.audit_s5_release_tag_source_remediation_protocol import build_audit
from scripts.freeze_s5_release_tag_source_remediation import (
    build_protocol,
    repository_has_no_tags,
    write_protocol,
)


def frozen_time() -> datetime:
    return datetime(2026, 9, 8, 23, 0, tzinfo=UTC)


def test_remediation_protocol_preserves_original_and_locks_outcomes() -> None:
    protocol = build_protocol(frozen_at=frozen_time())

    assert protocol.required_gate_ids == S5_RELEASE_REMEDIATION_GATES
    assert protocol.original_history_dataset_path != (
        protocol.destination_history_dataset_path
    )
    assert protocol.original_tag_opt_no_tags_observed
    assert protocol.original_tag_ref_count == 0
    assert not protocol.destination_overwrite_permitted
    assert protocol.maximum_selected_stable_tag_refs == 500
    assert protocol.expected_local_git_process_count == 2
    assert protocol.expected_network_git_process_count == 2
    assert protocol.authorizes_runner_implementation
    assert not protocol.authorizes_tag_discovery_now
    assert not protocol.authorizes_repository_copy_now
    assert not protocol.authorizes_tag_fetch_now
    assert not protocol.authorizes_original_repository_mutation
    assert not protocol.authorizes_market_value_access
    assert not protocol.authorizes_return_testing
    assert not protocol.authorizes_strategy_candidate
    assert not protocol.authorizes_testnet_strategy_orders
    assert protocol.next_authorization == S5_RELEASE_REMEDIATION_NEXT


def test_remediation_protocol_uses_exact_official_remote_and_stable_ref_filter() -> None:
    protocol = build_protocol(frozen_at=frozen_time())

    assert protocol.discovery_command == (
        "git",
        "ls-remote",
        "--tags",
        "--sort=refname",
        "https://github.com/bitcoin/bitcoin.git",
    )
    assert protocol.fetch_command_prefix[-1] == "https://github.com/bitcoin/bitcoin.git"
    assert protocol.stable_release_tag_regex.startswith("^refs/tags/v")
    assert repository_has_no_tags()


def test_remediation_protocol_rejects_original_mutation_authority() -> None:
    protocol = build_protocol(frozen_at=frozen_time())
    payload = protocol.model_dump(mode="json")
    payload["authorizes_original_repository_mutation"] = True

    with pytest.raises(ValidationError):
        S5ReleaseTagSourceRemediationProtocolV1.model_validate(payload)


def test_remediation_protocol_and_audit_reconstruct_exactly(tmp_path) -> None:
    protocol_path = tmp_path / "protocol.json"
    protocol = build_protocol(frozen_at=frozen_time())
    write_protocol(protocol_path, protocol)
    audit = build_audit(protocol_path=protocol_path, audited_at=frozen_time())

    assert audit.protocol_evidence_hash == protocol.protocol_evidence_hash
    assert audit.source_binding_count == 11
    assert audit.protocol_reconstructed_exactly
    assert audit.discovery_processes_executed == 0
    assert audit.repository_copies_executed == 0
    assert audit.fetch_processes_executed == 0
    assert audit.network_requests_executed == 0
    assert audit.market_values_read == 0
    assert audit.orders_submitted == 0
