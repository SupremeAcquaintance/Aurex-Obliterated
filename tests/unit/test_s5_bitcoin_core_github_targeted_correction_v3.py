from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (
    S5TargetedCompletenessCorrectionProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3 import (
    S5TargetedCorrectionV3Protocol,
    S5TargetedCorrectionV3ProtocolAudit,
)
from scripts.audit_s5_bitcoin_core_github_targeted_correction_v3_execution import (
    build_audit as build_execution_audit,
)
from scripts.freeze_s5_bitcoin_core_github_targeted_correction_v3_execution import (
    build_contract,
)
from scripts.run_s5_bitcoin_core_github_targeted_correction import (
    GitInspection,
    ResponseFailure,
)
from scripts.run_s5_bitcoin_core_github_targeted_correction_v2 import FAILURE_SCHEMA
from scripts.run_s5_bitcoin_core_github_targeted_correction_v3 import (
    ADOPTED_RESPONSE_PATH,
    attempt_payload,
    build_result,
    load_adopted_response,
    observation_from_envelope,
    parse_observation,
    response_merge_sha,
    runner_contract_hash,
)


@pytest.fixture(scope="module")
def protocol() -> S5TargetedCorrectionV3Protocol:
    return S5TargetedCorrectionV3Protocol.model_validate_json(
        Path(
            "data/evidence/"
            "s5_bitcoin_core_github_targeted_correction_protocol_v3.json"
        ).read_text(encoding="utf-8")
    )


def frozen_target_protocol() -> S5TargetedCompletenessCorrectionProtocol:
    return S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        Path(
            "data/evidence/"
            "s5_bitcoin_core_github_targeted_correction_protocol_v1.json"
        ).read_text(encoding="utf-8")
    )


def test_v3_adopts_pull_10_without_another_request(
    protocol: S5TargetedCorrectionV3Protocol,
) -> None:
    assert protocol.adopted_response_pull_number == 10
    assert protocol.adopted_response_http_status == 200
    assert protocol.adopted_response_merge_commit_sha_value == ""
    assert protocol.pull_10_v3_request_permitted is False
    assert protocol.untouched_v3_request_target_count == 193
    assert protocol.maximum_v3_request_count == 193
    assert protocol.maximum_cumulative_possible_request_count == 195


def test_v3_preserves_merge_sha_source_shapes(
    protocol: S5TargetedCorrectionV3Protocol,
) -> None:
    assert protocol.merge_commit_sha_accepted_source_shapes == (
        "NULL",
        "EMPTY_STRING",
        "SHA1_40_LOWER_HEX",
    )
    assert protocol.merge_commit_sha_source_value_normalization_permitted is False


def test_v3_remains_acquisition_only(
    protocol: S5TargetedCorrectionV3Protocol,
) -> None:
    assert protocol.credentials_permitted is False
    assert protocol.mapping_rule_change_permitted is False
    assert protocol.accepted_event_creation_permitted is False
    assert protocol.market_values_permitted is False
    assert protocol.orders_permitted is False


def test_v3_rejects_pull_10_request_authority(
    protocol: S5TargetedCorrectionV3Protocol,
) -> None:
    payload = protocol.model_dump(mode="json")
    payload["pull_10_v3_request_permitted"] = True
    with pytest.raises(ValidationError):
        S5TargetedCorrectionV3Protocol.model_validate(payload)


def test_v3_execution_adopts_real_pull_10_empty_merge_sha(
    protocol: S5TargetedCorrectionV3Protocol,
) -> None:
    target_protocol = frozen_target_protocol()
    path, parsed = load_adopted_response(
        target_protocol=target_protocol,
        protocol=protocol,
    )
    assert path == ADOPTED_RESPONSE_PATH
    assert parsed.target == target_protocol.target_manifest[0]
    assert parsed.http_status == 200
    assert response_merge_sha(path) == ""


def test_v3_execution_rejects_malformed_nonempty_merge_sha(
    protocol: S5TargetedCorrectionV3Protocol,
) -> None:
    target_protocol = frozen_target_protocol()
    target = target_protocol.target_manifest[0]
    envelope = json.loads(ADOPTED_RESPONSE_PATH.read_text(encoding="utf-8"))
    body = json.loads(base64.b64decode(envelope["response"]["body_base64"]))
    body["merge_commit_sha"] = "not-a-sha"
    encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
    envelope["response"]["body_base64"] = base64.b64encode(encoded).decode("ascii")
    envelope["response"]["body_byte_count"] = len(encoded)
    envelope["response"]["body_sha256"] = hashlib.sha256(encoded).hexdigest()
    observation = observation_from_envelope(
        payload=envelope,
        expected_schema=FAILURE_SCHEMA,
        target_protocol=target_protocol,
        target=target,
        protocol_hash_field="v2_protocol_evidence_hash",
        protocol_hash=protocol.v2_protocol_evidence_hash,
    )
    with pytest.raises(ResponseFailure, match="source shape"):
        parse_observation(
            observation=observation,
            target_protocol=target_protocol,
        )


def test_v3_execution_forbids_a_second_pull_10_request(
    protocol: S5TargetedCorrectionV3Protocol,
) -> None:
    target_protocol = frozen_target_protocol()
    with pytest.raises(ValueError, match="cannot request pull 10"):
        attempt_payload(
            target_protocol=target_protocol,
            protocol=protocol,
            target=target_protocol.target_manifest[0],
            started_at=datetime(2026, 9, 4, tzinfo=UTC),
        )


def test_v3_execution_contract_binds_runner_and_denies_trading() -> None:
    contract = build_contract(frozen_at=datetime(2026, 9, 4, tzinfo=UTC))
    assert contract.runner_contract_hash == runner_contract_hash()
    assert contract.adopted_response_count == 1
    assert contract.pull_10_v3_request_permitted is False
    assert contract.maximum_v3_request_count == 193
    assert contract.credentials_permitted is False
    assert contract.mapping_rule_change_permitted is False
    assert contract.market_values_permitted is False
    assert contract.orders_permitted is False


def test_v3_terminal_stop_result_round_trips_before_network(
    protocol: S5TargetedCorrectionV3Protocol,
    tmp_path: Path,
) -> None:
    target_protocol = frozen_target_protocol()
    protocol_audit = S5TargetedCorrectionV3ProtocolAudit.model_validate_json(
        Path(
            "data/evidence/"
            "s5_bitcoin_core_github_targeted_correction_protocol_audit_v3.json"
        ).read_text(encoding="utf-8")
    )
    now = datetime(2026, 9, 4, tzinfo=UTC)
    contract = build_contract(frozen_at=now)
    contract_path = tmp_path / "execution_contract.json"
    contract_path.write_text(contract.model_dump_json(indent=2) + "\n", encoding="utf-8")
    contract_audit = build_execution_audit(
        contract_path=contract_path,
        audited_at=now,
    )
    adopted = load_adopted_response(
        target_protocol=target_protocol,
        protocol=protocol,
    )
    result = build_result(
        target_protocol=target_protocol,
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        git_inspection=GitInspection(
            full_graph_stream_sha256="a" * 64,
            full_graph_commit_count=0,
            first_parent_commit_count=0,
            first_parent_merge_count=0,
            recognized_target_reachable_count=0,
            diagnostics=(),
        ),
        responses=[adopted],
        started_at=now,
        completed_at=now,
        resumed_v3_response_count=0,
        new_request_attempt_count=0,
        rate_limit_wait_count=0,
        rate_limit_wait_seconds=0.0,
        failure_type="SyntheticPreflightStop",
        failure_message="No network request was made.",
        failure_artifact_path=None,
    )
    serialized = result.model_dump_json(indent=2)
    assert type(result).model_validate_json(serialized) == result
    assert result.decision.endswith("REQUIRES_FAILURE_ADJUDICATION")
    assert result.resumed_response_count == 1
    assert result.logical_request_attempt_count == 1
    assert result.v3_new_request_count == 0
    assert result.empty_merge_commit_sha_response_count == 1
