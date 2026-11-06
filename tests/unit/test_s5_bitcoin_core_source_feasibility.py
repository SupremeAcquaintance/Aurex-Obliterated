from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_source_feasibility import (
    S5_SOURCE_NEXT,
    S5_SOURCE_PASS,
    S5_SOURCE_STOP,
    S5BitcoinCoreSourceFeasibilityProtocol,
    S5BitcoinCoreSourceFeasibilityProtocolAudit,
    S5BitcoinCoreSourceFeasibilityResult,
    S5BitcoinCoreSourceFeasibilityResultAudit,
    S5GitRefRecord,
    S5MetadataAttempt,
    S5RawArtifactRecord,
    audit_s5_source_protocol,
    audit_s5_source_protocol_audit,
    audit_s5_source_result,
    audit_s5_source_result_audit,
)
from scripts.audit_s5_bitcoin_core_source_feasibility_protocol import (
    build_audit as build_protocol_audit,
)
from scripts.audit_s5_bitcoin_core_source_feasibility_result import (
    build_audit as build_result_audit,
)
from scripts.freeze_s5_bitcoin_core_source_feasibility import build_protocol
from scripts.run_s5_bitcoin_core_source_feasibility import (
    build_result,
    planned_attempts,
)

PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_source_feasibility_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_source_feasibility_protocol_audit_v1.json"
)
RESULT_PATH = Path("data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json")
RESULT_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_source_feasibility_result_audit_v1.json")
FIXED_TIME = datetime(2026, 8, 31, 21, 0, tzinfo=UTC)


def built_protocol() -> S5BitcoinCoreSourceFeasibilityProtocol:
    return build_protocol(frozen_at=FIXED_TIME)


def successful_attempts() -> tuple[S5MetadataAttempt, ...]:
    return (
        S5MetadataAttempt(
            attempt_id="01_GITHUB_REPOSITORY_METADATA",
            attempt_kind="HTTP_GET",
            attempted=True,
            succeeded=True,
            started_at=FIXED_TIME,
            completed_at=FIXED_TIME,
            status_code_or_exit_code=200,
            response_bytes=100,
            raw_artifact_path="one.json",
            raw_artifact_sha256="1" * 64,
            error_type=None,
            error_message=None,
        ),
        S5MetadataAttempt(
            attempt_id="02_GIT_REF_DISCOVERY",
            attempt_kind="GIT_LS_REMOTE",
            attempted=True,
            succeeded=True,
            started_at=FIXED_TIME,
            completed_at=FIXED_TIME,
            status_code_or_exit_code=0,
            response_bytes=100,
            raw_artifact_path="two.txt",
            raw_artifact_sha256="2" * 64,
            error_type=None,
            error_message=None,
        ),
    )


def artifacts() -> tuple[S5RawArtifactRecord, ...]:
    return (
        S5RawArtifactRecord(
            attempt_id="01_GITHUB_REPOSITORY_METADATA",
            path="one.json",
            file_sha256="1" * 64,
            byte_count=100,
        ),
        S5RawArtifactRecord(
            attempt_id="02_GIT_REF_DISCOVERY",
            path="two.txt",
            file_sha256="2" * 64,
            byte_count=100,
        ),
    )


def refs() -> tuple[S5GitRefRecord, ...]:
    return (
        S5GitRefRecord(ref="HEAD", object_hash="a" * 40),
        S5GitRefRecord(ref="refs/heads/master", object_hash="a" * 40),
        S5GitRefRecord(ref="refs/tags/v30.0", object_hash="b" * 40),
    )


def repository() -> dict[str, object]:
    return {
        "full_name": "bitcoin/bitcoin",
        "private": False,
        "archived": False,
        "disabled": False,
        "visibility": "public",
        "default_branch": "master",
        "clone_url": "https://github.com/bitcoin/bitcoin.git",
        "license_spdx_id": "MIT",
    }


def test_s5_protocol_binds_charter_and_current_readiness() -> None:
    protocol = built_protocol()
    assert audit_s5_source_protocol(protocol) is True
    assert len(protocol.source_bindings) == 4
    paths = tuple(item.path for item in protocol.source_bindings)
    assert "data/evidence/s5_bitcoin_core_development_charter_v1.json" in paths
    assert "data/evidence/aurex_strategy_factory_readiness_current_result_v27.json" in paths


def test_s5_protocol_has_reachable_two_attempt_boundary() -> None:
    protocol = built_protocol()
    assert protocol.protocol_pass_condition_reachable_by_allowed_sources is True
    assert protocol.maximum_http_requests == 1
    assert protocol.maximum_git_transport_requests == 1
    assert protocol.maximum_total_attempts == 2
    assert protocol.repository_endpoint.authentication_permitted is False
    assert protocol.git_probe.credentials_permitted is False
    assert protocol.result_artifact_required_on_every_exit is True
    assert protocol.partial_response_artifacts_must_be_preserved is True


def test_s5_protocol_denies_history_outcomes_and_trading() -> None:
    protocol = built_protocol()
    assert protocol.repository_clone_permitted is False
    assert protocol.repository_history_permitted is False
    assert protocol.github_commit_history_permitted is False
    assert protocol.github_pull_request_history_permitted is False
    assert protocol.market_values_permitted is False
    assert protocol.parameters_permitted is False
    assert protocol.returns_permitted is False
    assert protocol.paper_permitted is False
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.production_permitted is False
    assert protocol.live_permitted is False


def test_s5_protocol_rejects_history_authority_tampering() -> None:
    payload = json.loads(built_protocol().model_dump_json())
    payload["repository_history_permitted"] = True
    with pytest.raises(ValidationError, match="Input should be False|cannot grant history"):
        S5BitcoinCoreSourceFeasibilityProtocol.model_validate(payload)


def test_s5_planned_attempts_are_explicit_and_empty() -> None:
    attempts = planned_attempts()
    assert [item.attempt_id for item in attempts] == [
        "01_GITHUB_REPOSITORY_METADATA",
        "02_GIT_REF_DISCOVERY",
    ]
    assert all(item.attempted is False for item in attempts)
    assert all(item.succeeded is False for item in attempts)


def test_s5_synthetic_pass_authorizes_payload_protocol_only() -> None:
    result = build_result(
        protocol=built_protocol(),
        attempts=successful_attempts(),
        artifacts=artifacts(),
        repository=repository(),
        headers={"x-ratelimit-limit": "60", "x-ratelimit-remaining": "59"},
        refs=refs(),
        executed_at=FIXED_TIME,
    )
    assert audit_s5_source_result(result) is True
    assert result.decision == S5_SOURCE_PASS
    assert result.next_authorization == S5_SOURCE_NEXT
    assert result.authorizes_history_payload_protocol is True
    assert result.authorizes_repository_history_access is False
    assert result.passed_gate_count == 14
    assert result.failed_gate_count == 0
    assert result.orders_submitted == 0


def test_s5_synthetic_transport_failure_retires_without_inference() -> None:
    result = build_result(
        protocol=built_protocol(),
        attempts=tuple(planned_attempts()),
        artifacts=(),
        repository={},
        headers={},
        refs=(),
        executed_at=FIXED_TIME,
    )
    assert audit_s5_source_result(result) is True
    assert result.decision == S5_SOURCE_STOP
    assert result.authorizes_history_payload_protocol is False
    assert result.predictive_edge_conclusion == "NOT_EVALUATED"
    assert result.repository_history_records_parsed == 0
    assert result.btc_market_values_read == 0


def test_s5_result_rejects_market_authority_tampering() -> None:
    result = build_result(
        protocol=built_protocol(),
        attempts=successful_attempts(),
        artifacts=artifacts(),
        repository=repository(),
        headers={"x-ratelimit-limit": "60", "x-ratelimit-remaining": "59"},
        refs=refs(),
        executed_at=FIXED_TIME,
    )
    payload = json.loads(result.model_dump_json())
    payload["authorizes_market_values"] = True
    with pytest.raises(ValidationError, match="Input should be False|cannot grant history"):
        S5BitcoinCoreSourceFeasibilityResult.model_validate(payload)


def test_s5_frozen_protocol_result_and_audits_reconstruct_exactly() -> None:
    protocol = S5BitcoinCoreSourceFeasibilityProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5BitcoinCoreSourceFeasibilityProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5BitcoinCoreSourceFeasibilityResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5BitcoinCoreSourceFeasibilityResultAudit.model_validate_json(
        RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert protocol_audit == build_protocol_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=protocol_audit.audited_at,
    )
    assert result_audit == build_result_audit(
        protocol_path=PROTOCOL_PATH,
        result_path=RESULT_PATH,
        audited_at=result_audit.audited_at,
    )
    assert audit_s5_source_protocol_audit(protocol_audit) is True
    assert audit_s5_source_result(result) is True
    assert audit_s5_source_result_audit(result_audit) is True
