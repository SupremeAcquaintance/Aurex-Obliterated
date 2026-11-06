from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (
    S5_HISTORY_NEXT,
    S5_HISTORY_PASS,
    S5_HISTORY_STOP,
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadProtocolAudit,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryPayloadResultAudit,
    S5HistoryCloneAttempt,
    S5HistoryFileRecord,
    audit_s5_history_protocol,
    audit_s5_history_protocol_audit,
    audit_s5_history_result,
    audit_s5_history_result_audit,
)
from scripts.audit_s5_bitcoin_core_history_payload_protocol import (
    build_audit as build_protocol_audit,
)
from scripts.freeze_s5_bitcoin_core_history_payload import build_protocol
from scripts.run_s5_bitcoin_core_history_payload import DatasetInspection, build_result

PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_audit_v1.json")
RESULT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
RESULT_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_audit_v1.json")
FIXED_TIME = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


def built_protocol() -> S5BitcoinCoreHistoryPayloadProtocol:
    return build_protocol(frozen_at=FIXED_TIME)


def successful_attempt() -> S5HistoryCloneAttempt:
    return S5HistoryCloneAttempt(
        attempted=True,
        succeeded=True,
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
        elapsed_seconds=1.0,
        exit_code=0,
        transcript_path="transcript.json",
        transcript_file_sha256="a" * 64,
        transcript_byte_count=100,
        error_type=None,
        error_message=None,
    )


def successful_inspection(protocol: S5BitcoinCoreHistoryPayloadProtocol) -> DatasetInspection:
    manifest = (
        S5HistoryFileRecord(
            relative_path="objects/pack/pack-a.pack",
            file_sha256="b" * 64,
            byte_count=100,
        ),
    )
    return DatasetInspection(
        manifest=manifest,
        directory_sha256="c" * 64,
        byte_count=100,
        fetched_master_head=protocol.source_cutoff_commit,
        cutoff_commit_present=True,
        cutoff_is_ancestor=True,
        repository_is_bare=True,
        repository_is_shallow=False,
        remote_origin_url=protocol.clone_spec.remote_url,
        remote_promisor=True,
        remote_partial_clone_filter="blob:none",
        local_branch_refs=("refs/heads/master",),
        local_tag_ref_count=0,
        reachable_object_id_count=10,
        reachable_object_id_stream_sha256="d" * 64,
        cutoff_commit_count=5,
    )


def test_s5_history_protocol_binds_exact_predecessors_and_cutoff() -> None:
    protocol = built_protocol()
    assert audit_s5_history_protocol(protocol) is True
    assert len(protocol.source_bindings) == 8
    paths = tuple(item.path for item in protocol.source_bindings)
    assert "data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json" in paths
    assert "data/evidence/aurex_strategy_factory_readiness_current_result_v28.json" in paths
    assert len(protocol.source_cutoff_commit) == 40
    assert len(protocol.source_v30_tag_object) == 40


def test_s5_history_protocol_is_one_run_blobless_and_bounded() -> None:
    protocol = built_protocol()
    spec = protocol.clone_spec
    assert spec.maximum_git_process_count == 1
    assert spec.minimum_free_disk_bytes == 5_000_000_000
    assert spec.maximum_dataset_bytes == 2_000_000_000
    assert spec.credentials_permitted is False
    assert spec.git_arguments == (
        "clone",
        "--bare",
        "--filter=blob:none",
        "--single-branch",
        "--no-tags",
        "--branch",
        "master",
        "--quiet",
    )


def test_s5_history_protocol_denies_semantics_outcomes_and_trading() -> None:
    protocol = built_protocol()
    assert protocol.repository_history_payload_permitted is True
    assert protocol.history_semantic_parsing_permitted is False
    assert protocol.commit_message_access_permitted is False
    assert protocol.author_identity_access_permitted is False
    assert protocol.pull_request_id_parsing_permitted is False
    assert protocol.github_api_requests_permitted is False
    assert protocol.market_values_permitted is False
    assert protocol.parameters_permitted is False
    assert protocol.returns_permitted is False
    assert protocol.paper_permitted is False
    assert protocol.live_permitted is False


def test_s5_history_protocol_rejects_market_authority_tampering() -> None:
    payload = json.loads(built_protocol().model_dump_json())
    payload["market_values_permitted"] = True
    with pytest.raises(ValidationError, match="Input should be False|cannot grant research"):
        S5BitcoinCoreHistoryPayloadProtocol.model_validate(payload)


def test_s5_history_synthetic_pass_authorizes_census_protocol_only() -> None:
    protocol = built_protocol()
    result = build_result(
        protocol=protocol,
        attempt=successful_attempt(),
        inspection=successful_inspection(protocol),
        dataset_path=Path(protocol.clone_spec.final_dataset_path),
        free_disk_bytes_before=6_000_000_000,
        network_process_count=1,
        executed_at=FIXED_TIME,
    )
    assert audit_s5_history_result(result) is True
    assert result.decision == S5_HISTORY_PASS
    assert result.next_authorization == S5_HISTORY_NEXT
    assert result.authorizes_history_completeness_census_protocol is True
    assert result.authorizes_history_semantic_parsing is False
    assert result.authorizes_market_values is False
    assert result.cutoff_commit_count == 5
    assert result.repository_history_records_semantically_parsed == 0
    assert result.orders_submitted == 0


def test_s5_history_insufficient_disk_stops_without_network() -> None:
    protocol = built_protocol()
    result = build_result(
        protocol=protocol,
        attempt=S5HistoryCloneAttempt(
            attempted=False,
            succeeded=False,
            started_at=None,
            completed_at=None,
            elapsed_seconds=None,
            exit_code=None,
            transcript_path=None,
            transcript_file_sha256=None,
            transcript_byte_count=0,
            error_type=None,
            error_message=None,
        ),
        inspection=DatasetInspection(),
        dataset_path=None,
        free_disk_bytes_before=1,
        network_process_count=0,
        executed_at=FIXED_TIME,
    )
    assert result.decision == S5_HISTORY_STOP
    assert result.authorizes_history_completeness_census_protocol is False
    assert result.predictive_edge_conclusion == "NOT_EVALUATED"
    assert result.repository_history_records_acquired == 0


def test_s5_history_result_rejects_trading_authority_tampering() -> None:
    protocol = built_protocol()
    result = build_result(
        protocol=protocol,
        attempt=successful_attempt(),
        inspection=successful_inspection(protocol),
        dataset_path=Path(protocol.clone_spec.final_dataset_path),
        free_disk_bytes_before=6_000_000_000,
        network_process_count=1,
        executed_at=FIXED_TIME,
    )
    payload = json.loads(result.model_dump_json())
    payload["authorizes_live"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        S5BitcoinCoreHistoryPayloadResult.model_validate(payload)


def test_s5_history_frozen_protocol_result_and_audits_reconstruct_exactly() -> None:
    protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5BitcoinCoreHistoryPayloadProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5BitcoinCoreHistoryPayloadResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5BitcoinCoreHistoryPayloadResultAudit.model_validate_json(
        RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert protocol_audit == build_protocol_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=protocol_audit.audited_at,
    )
    # The audited v2 amendment promotes the preserved `.partial` repository to
    # its final path. The frozen v1 audit remains hash-valid, while v2 owns the
    # post-promotion dataset reconstruction.
    assert result_audit.result_evidence_hash == result.result_evidence_hash
    assert audit_s5_history_protocol_audit(protocol_audit) is True
    assert audit_s5_history_result(result) is True
    assert audit_s5_history_result_audit(result_audit) is True
