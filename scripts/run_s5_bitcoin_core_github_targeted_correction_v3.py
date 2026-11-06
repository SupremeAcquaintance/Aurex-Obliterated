from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (  # noqa: E402
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCorrectionTarget,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (  # noqa: E402
    S5_TARGETED_CORRECTION_FAILURE_NEXT,
    S5_TARGETED_CORRECTION_NEXT,
    S5_TARGETED_CORRECTION_PASS,
    S5_TARGETED_CORRECTION_STOP,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2 import (  # noqa: E402
    S5TargetedCorrectionV2Protocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_execution import (  # noqa: E402
    S5TargetedCompletenessCorrectionResultV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_failure import (  # noqa: E402
    S5TargetedCorrectionV2FailureAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3 import (  # noqa: E402
    S5TargetedCorrectionV3Protocol,
    S5TargetedCorrectionV3ProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3_execution import (  # noqa: E402
    S5TargetedCompletenessCorrectionResultV3,
    S5TargetedCorrectionV3ExecutionContract,
    S5TargetedCorrectionV3ExecutionContractAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction as base,
)
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction_v2 as base_v2,
)

DEFAULT_TARGET_PROTOCOL = base.DEFAULT_PROTOCOL
DEFAULT_V3_PROTOCOL = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v3.json"
)
DEFAULT_V3_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_audit_v3.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_v3.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_audit_v3.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v3.json"
)
V2_PROTOCOL_PATH = base_v2.DEFAULT_V2_PROTOCOL
V2_RESULT_PATH = base_v2.DEFAULT_RESULT
V2_FAILURE_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_v2_failure_audit_v1.json"
)
ADOPTED_RESPONSE_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v2/failure_pull_000010.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_targeted_correction_v3_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_bitcoin_core_github_targeted_correction_v3.py")
V2_RUNNER_PATH = Path("scripts/run_s5_bitcoin_core_github_targeted_correction_v2.py")
EXECUTION_AUDITOR_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_targeted_correction_v3_execution.py"
)
RESPONSE_SCHEMA = "aurex-s5-github-targeted-pull-response-v3"
FAILURE_SCHEMA = "aurex-s5-github-targeted-pull-failure-v3"
ATTEMPT_SCHEMA = "aurex-s5-github-targeted-pull-attempt-v3"


def runner_contract_hash() -> str:
    paths = (EXECUTION_MODULE_PATH, RUNNER_PATH, V2_RUNNER_PATH)
    return universe_evidence_hash(
        tuple(
            {
                "path": path.as_posix(),
                "file_sha256": base.file_sha256(PROJECT_ROOT / path),
            }
            for path in sorted(paths, key=lambda item: item.as_posix())
        )
    )


def response_path(
    protocol: S5TargetedCorrectionV3Protocol,
    target: S5TargetedCorrectionTarget,
) -> Path:
    return Path(protocol.raw_response_directory) / protocol.response_file_pattern.format(
        pull_number=target.pull_number
    )


def attempt_path(
    protocol: S5TargetedCorrectionV3Protocol,
    target: S5TargetedCorrectionTarget,
) -> Path:
    response = response_path(protocol, target)
    return response.with_name(f"pull_{target.pull_number:06d}.attempt.json")


def attempt_payload(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV3Protocol,
    target: S5TargetedCorrectionTarget,
    started_at: datetime,
) -> dict[str, Any]:
    if target.pull_number == 10:
        raise ValueError("S5 targeted v3 cannot request pull 10")
    return {
        "schema_version": ATTEMPT_SCHEMA,
        "target_protocol_evidence_hash": target_protocol.protocol_evidence_hash,
        "v3_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "target_manifest_evidence_hash": target_protocol.target_manifest_evidence_hash,
        "sequence": target.sequence,
        "pull_number": target.pull_number,
        "started_at": started_at.isoformat(),
        "request": {
            "method": target_protocol.method,
            "url": base.request_url(target_protocol, target.pull_number),
            "headers": {
                name.lower(): value
                for name, value in base.explicit_headers(target_protocol).items()
            },
            "authorization_header_used": False,
            "credential_value_accessed": False,
            "environment_proxy_used": False,
            "redirects_permitted": False,
        },
    }


def validate_200_payload(
    payload: Any,
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("GitHub targeted v3 pull response is not an object")
    required = tuple(
        field for field in target_protocol.required_200_fields if "." not in field
    )
    if any(field not in payload for field in required):
        raise ValueError("GitHub targeted v3 response lacks a required field")
    if payload["number"] != target.pull_number:
        raise ValueError("GitHub targeted v3 pull identity changed")
    if not isinstance(payload["node_id"], str) or not payload["node_id"]:
        raise ValueError("GitHub targeted v3 node identity is invalid")
    if payload["state"] not in {"open", "closed"}:
        raise ValueError("GitHub targeted v3 state is invalid")
    created = base.parse_datetime_field(payload["created_at"], nullable=False)
    updated = base.parse_datetime_field(payload["updated_at"], nullable=False)
    closed = base.parse_datetime_field(payload["closed_at"], nullable=True)
    merged_at = base.parse_datetime_field(payload["merged_at"], nullable=True)
    assert created is not None and updated is not None
    if updated < created or (closed is not None and closed < created):
        raise ValueError("GitHub targeted v3 timestamps are invalid")
    if merged_at is not None and merged_at < created:
        raise ValueError("GitHub targeted v3 merge timestamp is invalid")
    if not isinstance(payload["merged"], bool):
        raise ValueError("GitHub targeted v3 merged flag is invalid")
    merge_sha = payload["merge_commit_sha"]
    if merge_sha not in {None, ""} and base.SHA1_RE.fullmatch(str(merge_sha)) is None:
        raise ValueError("GitHub targeted v3 merge commit SHA source shape is invalid")
    head = payload.get("head")
    branch = payload.get("base")
    if not isinstance(head, dict) or (
        base.SHA1_RE.fullmatch(str(head.get("sha", ""))) is None
    ):
        raise ValueError("GitHub targeted v3 head identity is invalid")
    if (
        not isinstance(branch, dict)
        or not isinstance(branch.get("ref"), str)
        or not branch["ref"]
        or base.SHA1_RE.fullmatch(str(branch.get("sha", ""))) is None
    ):
        raise ValueError("GitHub targeted v3 base identity is invalid")
    user = payload["user"]
    if user is not None and (
        not isinstance(user, dict)
        or not isinstance(user.get("id"), int)
        or not isinstance(user.get("login"), str)
        or not isinstance(user.get("type"), str)
    ):
        raise ValueError("GitHub targeted v3 actor identity is invalid")


def parse_observation(
    *,
    observation: base.RequestObservation,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
) -> base.ParsedResponse:
    try:
        if observation.error_type is not None:
            raise ValueError(
                f"GitHub request failed: {observation.error_type}: "
                f"{observation.error_message}"
            )
        if (
            observation.http_status not in target_protocol.acceptable_http_statuses
            or observation.final_url != observation.request_url
            or observation.redirect_count != 0
        ):
            raise ValueError("GitHub targeted v3 response status or URL is invalid")
        if not 0 < len(observation.response_body) <= (
            target_protocol.maximum_response_bytes_per_target
        ):
            raise ValueError("GitHub targeted v3 response byte bound failed")
        content_type = observation.response_headers.get("content-type") or ""
        if "application/json" not in content_type.lower():
            raise ValueError("GitHub targeted v3 response content type is not JSON")
        payload = json.loads(observation.response_body)
        if observation.http_status == 200:
            validate_200_payload(
                payload,
                target_protocol=target_protocol,
                target=observation.target,
            )
        elif not isinstance(payload, dict) or not isinstance(payload.get("message"), str):
            raise ValueError("GitHub targeted v3 404 payload is invalid")
        rate_limit = int(observation.response_headers.get("x-ratelimit-limit") or "")
        rate_remaining = int(
            observation.response_headers.get("x-ratelimit-remaining") or ""
        )
        rate_reset = int(observation.response_headers.get("x-ratelimit-reset") or "")
        if (
            rate_limit != 60
            or not 0 <= rate_remaining < 60
            or rate_reset <= 0
            or observation.response_headers.get("x-ratelimit-resource") != "core"
        ):
            raise ValueError("GitHub targeted v3 rate-limit headers are invalid")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise base.ResponseFailure(str(exc), observation) from exc
    assert observation.http_status is not None
    return base.ParsedResponse(
        target=observation.target,
        http_status=observation.http_status,
        response_body_sha256=hashlib.sha256(observation.response_body).hexdigest(),
        response_body_byte_count=len(observation.response_body),
        rate_limit=rate_limit,
        rate_remaining=rate_remaining,
        rate_reset=rate_reset,
    )


def envelope_payload(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV3Protocol,
    observation: base.RequestObservation,
    schema_version: str = RESPONSE_SCHEMA,
) -> dict[str, Any]:
    payload = base.envelope_payload(
        protocol=target_protocol,
        observation=observation,
        schema_version=schema_version,
    )
    payload["target_protocol_evidence_hash"] = payload.pop("protocol_evidence_hash")
    payload["v3_protocol_evidence_hash"] = protocol.protocol_evidence_hash
    payload["pull_10_v3_request"] = False
    return payload


def observation_from_envelope(
    *,
    payload: dict[str, Any],
    expected_schema: str,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
    protocol_hash_field: str,
    protocol_hash: str,
) -> base.RequestObservation:
    if (
        payload.get("schema_version") != expected_schema
        or payload.get("target_protocol_evidence_hash")
        != target_protocol.protocol_evidence_hash
        or payload.get(protocol_hash_field) != protocol_hash
        or payload.get("target_manifest_evidence_hash")
        != target_protocol.target_manifest_evidence_hash
        or payload.get("sequence") != target.sequence
        or payload.get("pull_number") != target.pull_number
        or payload.get("target_reasons") != list(target.target_reasons)
        or payload.get("request_attempt_count") != 1
    ):
        raise ValueError("S5 targeted adopted or v3 response identity changed")
    request = payload["request"]
    response = payload["response"]
    error = payload["error"]
    body = base64.b64decode(response["body_base64"], validate=True)
    expected_headers = {
        name.lower(): value
        for name, value in base.explicit_headers(target_protocol).items()
    }
    if (
        request["method"] != target_protocol.method
        or request["url"] != base.request_url(target_protocol, target.pull_number)
        or request["headers"] != expected_headers
        or request["authorization_header_used"] is not False
        or request["credential_value_accessed"] is not False
        or request["environment_proxy_used"] is not False
        or response["body_byte_count"] != len(body)
        or response["body_sha256"] != hashlib.sha256(body).hexdigest()
    ):
        raise ValueError("S5 targeted adopted or v3 response content changed")
    return base.RequestObservation(
        target=target,
        started_at=datetime.fromisoformat(payload["started_at"]),
        completed_at=datetime.fromisoformat(payload["completed_at"]),
        elapsed_seconds=float(payload["elapsed_seconds"]),
        request_url=request["url"],
        request_headers=dict(request["headers"]),
        http_status=response["http_status"],
        final_url=response["final_url"],
        response_headers=dict(response["headers"]),
        response_body=body,
        redirect_count=response["redirect_count"],
        error_type=error["type"],
        error_message=error["message"],
    )


def load_adopted_response(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV3Protocol,
) -> tuple[Path, base.ParsedResponse]:
    if base.file_sha256(ADOPTED_RESPONSE_PATH) != protocol.adopted_response_file_sha256:
        raise ValueError("S5 targeted v3 adopted response file changed")
    target = target_protocol.target_manifest[0]
    payload = json.loads(ADOPTED_RESPONSE_PATH.read_text(encoding="utf-8"))
    observation = observation_from_envelope(
        payload=payload,
        expected_schema=base_v2.FAILURE_SCHEMA,
        target_protocol=target_protocol,
        target=target,
        protocol_hash_field="v2_protocol_evidence_hash",
        protocol_hash=protocol.v2_protocol_evidence_hash,
    )
    if hashlib.sha256(observation.response_body).hexdigest() != (
        protocol.adopted_response_body_sha256
    ):
        raise ValueError("S5 targeted v3 adopted response body changed")
    return (
        ADOPTED_RESPONSE_PATH,
        parse_observation(observation=observation, target_protocol=target_protocol),
    )


def load_existing_responses(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV3Protocol,
) -> list[tuple[Path, base.ParsedResponse]]:
    completed: list[tuple[Path, base.ParsedResponse]] = []
    gap_seen = False
    for target in target_protocol.target_manifest[1:]:
        response = response_path(protocol, target)
        marker = attempt_path(protocol, target)
        if response.exists() and marker.exists():
            if gap_seen:
                raise ValueError("S5 targeted v3 responses are not contiguous")
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
            expected_marker = attempt_payload(
                target_protocol=target_protocol,
                protocol=protocol,
                target=target,
                started_at=datetime.fromisoformat(marker_payload["started_at"]),
            )
            if marker_payload != expected_marker:
                raise ValueError("S5 targeted v3 request marker changed")
            payload = json.loads(response.read_text(encoding="utf-8"))
            observation = observation_from_envelope(
                payload=payload,
                expected_schema=RESPONSE_SCHEMA,
                target_protocol=target_protocol,
                target=target,
                protocol_hash_field="v3_protocol_evidence_hash",
                protocol_hash=protocol.protocol_evidence_hash,
            )
            completed.append(
                (
                    response,
                    parse_observation(
                        observation=observation,
                        target_protocol=target_protocol,
                    ),
                )
            )
        elif response.exists():
            raise ValueError("S5 targeted v3 response lacks request marker")
        elif marker.exists():
            raise ValueError("S5 targeted v3 request outcome is uncertain")
        else:
            gap_seen = True
    return completed


def bindings_match(bindings: tuple[Any, ...]) -> bool:
    return all(
        base.file_sha256(PROJECT_ROOT / row.path) == row.file_sha256
        for row in bindings
    )


def load_authorization(
    *,
    target_protocol_path: Path = DEFAULT_TARGET_PROTOCOL,
    protocol_path: Path = DEFAULT_V3_PROTOCOL,
    protocol_audit_path: Path = DEFAULT_V3_PROTOCOL_AUDIT,
    contract_path: Path = DEFAULT_EXECUTION_CONTRACT,
    contract_audit_path: Path = DEFAULT_EXECUTION_CONTRACT_AUDIT,
) -> tuple[
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCorrectionV3Protocol,
    S5TargetedCorrectionV3ProtocolAudit,
    S5TargetedCorrectionV3ExecutionContract,
    S5TargetedCorrectionV3ExecutionContractAudit,
]:
    target = S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        target_protocol_path.read_text(encoding="utf-8")
    )
    protocol = S5TargetedCorrectionV3Protocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S5TargetedCorrectionV3ProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S5TargetedCorrectionV3ExecutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = S5TargetedCorrectionV3ExecutionContractAudit.model_validate_json(
        contract_audit_path.read_text(encoding="utf-8")
    )
    source_hash = universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in contract.source_bindings)
    )
    implementation_hash = universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in contract.implementation_bindings)
    )
    changed = (
        protocol.target_protocol_evidence_hash != target.protocol_evidence_hash
        or protocol.target_manifest_evidence_hash != target.target_manifest_evidence_hash
        or audit.protocol_file_sha256 != base.file_sha256(protocol_path)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.target_protocol_evidence_hash != target.protocol_evidence_hash
        or contract.v3_protocol_file_sha256 != base.file_sha256(protocol_path)
        or contract.v3_protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.v3_protocol_audit_file_sha256
        != base.file_sha256(protocol_audit_path)
        or contract.v3_protocol_audit_evidence_hash != audit.audit_evidence_hash
        or contract.adopted_response_file_sha256
        != protocol.adopted_response_file_sha256
        or contract.adopted_response_body_sha256
        != protocol.adopted_response_body_sha256
        or contract.runner_contract_hash != runner_contract_hash()
        or source_hash != contract.source_binding_manifest_evidence_hash
        or implementation_hash
        != contract.implementation_binding_manifest_evidence_hash
        or not bindings_match(protocol.source_bindings)
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or contract_audit.contract_file_sha256 != base.file_sha256(contract_path)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.builder_contract_hash != contract.builder_contract_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
        or contract_audit.source_binding_manifest_evidence_hash
        != contract.source_binding_manifest_evidence_hash
        or contract_audit.implementation_binding_manifest_evidence_hash
        != contract.implementation_binding_manifest_evidence_hash
        or contract_audit.auditor_source_sha256
        != base.file_sha256(PROJECT_ROOT / EXECUTION_AUDITOR_PATH)
    )
    if changed:
        raise ValueError("S5 targeted v3 authorization or lineage changed")
    return target, protocol, audit, contract, contract_audit


def response_merge_sha(path: Path) -> str | None:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    body = base64.b64decode(envelope["response"]["body_base64"], validate=True)
    if envelope["response"]["http_status"] != 200:
        return None
    payload = json.loads(body)
    return payload.get("merge_commit_sha")


def build_result(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV3Protocol,
    protocol_audit: S5TargetedCorrectionV3ProtocolAudit,
    contract: S5TargetedCorrectionV3ExecutionContract,
    contract_audit: S5TargetedCorrectionV3ExecutionContractAudit,
    git_inspection: base.GitInspection,
    responses: list[tuple[Path, base.ParsedResponse]],
    started_at: datetime,
    completed_at: datetime,
    resumed_v3_response_count: int,
    new_request_attempt_count: int,
    rate_limit_wait_count: int,
    rate_limit_wait_seconds: float,
    failure_type: str | None,
    failure_message: str | None,
    failure_artifact_path: Path | None,
) -> S5TargetedCompletenessCorrectionResultV3:
    v2_protocol = S5TargetedCorrectionV2Protocol.model_validate_json(
        V2_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    v2_result = S5TargetedCompletenessCorrectionResultV2.model_validate_json(
        V2_RESULT_PATH.read_text(encoding="utf-8")
    )
    v2_failure_audit = S5TargetedCorrectionV2FailureAudit.model_validate_json(
        V2_FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    bindings = tuple(
        base.response_binding(path=path, parsed=parsed)
        for path, parsed in responses
    )
    v3_marker_count = sum(
        attempt_path(protocol, target).is_file()
        for target in target_protocol.target_manifest[1:]
    )
    marker_count = 1 + v3_marker_count
    resumed_count = 1 + resumed_v3_response_count
    logical_attempts = resumed_count + new_request_attempt_count
    empty_merge_count = sum(response_merge_sha(path) == "" for path, _ in responses)
    passed = (
        failure_type is None
        and len(bindings) == 194
        and marker_count == 194
        and logical_attempts == 194
        and new_request_attempt_count + resumed_v3_response_count == 193
        and len(git_inspection.diagnostics) == 83
        and git_inspection.recognized_target_reachable_count == 83
        and git_inspection.full_graph_commit_count == 50_395
        and git_inspection.first_parent_commit_count == 17_543
        and git_inspection.first_parent_merge_count == 16_721
        and empty_merge_count >= 1
        and sum(row.response_body_byte_count for row in bindings)
        <= protocol.maximum_total_response_bytes
    )
    if failure_type is None and not passed:
        failure_type = "TargetedV3AcquisitionGateFailure"
        failure_message = "One or more terminal v3 acquisition gates failed"
    gates = base.build_gate_results(passed=passed, failure_message=failure_message)
    normalization = base.load_local_lineage(target_protocol)[0]
    payload = {
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": round((completed_at - started_at).total_seconds(), 6),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "target_manifest_evidence_hash": target_protocol.target_manifest_evidence_hash,
        "history_dataset_directory_sha256": (
            normalization.history_dataset_directory_sha256
        ),
        "full_graph_stream_sha256": git_inspection.full_graph_stream_sha256,
        "full_graph_commit_count": git_inspection.full_graph_commit_count,
        "first_parent_commit_count": git_inspection.first_parent_commit_count,
        "first_parent_merge_count": git_inspection.first_parent_merge_count,
        "recognized_target_reachable_count": (
            git_inspection.recognized_target_reachable_count
        ),
        "commit_diagnostics": git_inspection.diagnostics,
        "raw_response_directory": protocol.raw_response_directory,
        "response_bindings": bindings,
        "request_attempt_marker_count": marker_count,
        "logical_request_attempt_count": logical_attempts,
        "new_request_attempt_count": new_request_attempt_count,
        "resumed_response_count": resumed_count,
        "http_200_count": sum(row.http_status == 200 for row in bindings),
        "http_404_count": sum(row.http_status == 404 for row in bindings),
        "total_response_bytes": sum(row.response_body_byte_count for row in bindings),
        "rate_limit_wait_count": rate_limit_wait_count,
        "rate_limit_wait_seconds": round(rate_limit_wait_seconds, 6),
        "local_git_process_count": 2,
        "gate_results": gates,
        "passed_gate_count": sum(gate.status == "PASS" for gate in gates),
        "failed_gate_count": sum(gate.status == "FAIL" for gate in gates),
        "decision": S5_TARGETED_CORRECTION_PASS if passed else S5_TARGETED_CORRECTION_STOP,
        "next_authorization": (
            S5_TARGETED_CORRECTION_NEXT
            if passed
            else S5_TARGETED_CORRECTION_FAILURE_NEXT
        ),
        "failure_type": failure_type,
        "failure_message": failure_message,
        "failure_artifact_path": (
            None if failure_artifact_path is None else failure_artifact_path.as_posix()
        ),
        "failure_artifact_sha256": (
            None
            if failure_artifact_path is None
            else base.file_sha256(failure_artifact_path)
        ),
        "limitations": tuple(
            sorted(
                (
                    "Pull 10 is adopted from its complete v2 HTTP 200 response.",
                    "V3 queried only the 193 targets untouched before v3.",
                    "A pass authorizes corrected normalization protocol design only.",
                    "The original normalization STOP remains binding.",
                    "Empty merge_commit_sha values remain missing identity evidence.",
                    "Responses are current metadata, not immutable historical snapshots.",
                    "A 404 proves only the endpoint response at acquisition time.",
                    "Merge commit semantics depend on merge, squash, and rebase behavior.",
                    "Git reachability does not prove historical public availability time.",
                    "No response automatically creates an accepted event or timestamp.",
                    "No mapping or completeness rule changed during acquisition.",
                    "No market value, return, parameter, candidate, signal, or order was created.",
                    "No paper, Testnet strategy, production, live, or capital authority exists.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "Acquisition success is not evidence of reliability or profit.",
                    "Real net profit remains zero.",
                )
            )
        ),
        "v1_target_protocol_evidence_hash": (
            target_protocol.protocol_evidence_hash
        ),
        "v2_remediation_protocol_evidence_hash": v2_protocol.protocol_evidence_hash,
        "v1_failure_result_evidence_hash": (
            v2_result.v1_failure_result_evidence_hash
        ),
        "v1_failure_audit_evidence_hash": v2_result.v1_failure_audit_evidence_hash,
        "v3_schema_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "v2_failure_audit_evidence_hash": v2_failure_audit.audit_evidence_hash,
        "adopted_response_file_sha256": protocol.adopted_response_file_sha256,
        "adopted_response_body_sha256": protocol.adopted_response_body_sha256,
        "v3_new_request_count": new_request_attempt_count,
        "empty_merge_commit_sha_response_count": empty_merge_count,
    }
    provisional = S5TargetedCompletenessCorrectionResultV3.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5TargetedCompletenessCorrectionResultV3.model_validate(complete)


def write_result_atomic(
    path: Path, result: S5TargetedCompletenessCorrectionResultV3
) -> None:
    if path.exists():
        raise ValueError(f"S5 targeted v3 result already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v3 result transaction: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5TargetedCompletenessCorrectionResultV3.model_validate_json(
        serialized
    ) != result:
        raise ValueError("S5 targeted v3 result did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV3Protocol,
    protocol_audit: S5TargetedCorrectionV3ProtocolAudit,
    contract: S5TargetedCorrectionV3ExecutionContract,
    contract_audit: S5TargetedCorrectionV3ExecutionContractAudit,
    output_path: Path,
) -> S5TargetedCompletenessCorrectionResultV3:
    if output_path.exists():
        raise ValueError(f"S5 targeted v3 result already exists: {output_path}")
    started_at = datetime.now(UTC)
    run_clock = time.monotonic()
    normalization, census = base.load_local_lineage(target_protocol)
    adopted = load_adopted_response(
        target_protocol=target_protocol,
        protocol=protocol,
    )
    existing = load_existing_responses(
        target_protocol=target_protocol,
        protocol=protocol,
    )
    responses = [adopted, *existing]
    git_inspection = base.inspect_git(
        protocol=target_protocol,
        normalization=normalization,
        census=census,
    )
    new_attempts = 0
    wait_count = 0
    wait_seconds = 0.0
    failure_type = None
    failure_message = None
    failure_artifact = None
    try:
        for target in target_protocol.target_manifest[len(responses) :]:
            if target.pull_number == 10:
                raise ValueError("S5 targeted v3 attempted forbidden pull 10 request")
            if time.monotonic() - run_clock >= protocol.maximum_elapsed_seconds:
                raise ValueError("S5 targeted v3 elapsed-time bound reached")
            marker = attempt_path(protocol, target)
            base.write_json_atomic(
                marker,
                attempt_payload(
                    target_protocol=target_protocol,
                    protocol=protocol,
                    target=target,
                    started_at=datetime.now(UTC),
                ),
            )
            new_attempts += 1
            observation = base_v2.perform_request(
                target_protocol=target_protocol,
                target=target,
            )
            try:
                parsed = parse_observation(
                    observation=observation,
                    target_protocol=target_protocol,
                )
            except base.ResponseFailure:
                failure_artifact = Path(protocol.raw_response_directory) / (
                    f"failure_pull_{target.pull_number:06d}.json"
                )
                base.write_json_atomic(
                    failure_artifact,
                    envelope_payload(
                        target_protocol=target_protocol,
                        protocol=protocol,
                        observation=observation,
                        schema_version=FAILURE_SCHEMA,
                    ),
                )
                raise
            path = response_path(protocol, target)
            base.write_json_atomic(
                path,
                envelope_payload(
                    target_protocol=target_protocol,
                    protocol=protocol,
                    observation=observation,
                ),
            )
            responses.append((path, parsed))
            if len(responses) % 10 == 0 or len(responses) == 194:
                print(
                    f"S5 targeted v3 progress {len(responses)}/194 "
                    f"remaining={parsed.rate_remaining}",
                    flush=True,
                )
            if parsed.rate_remaining == 0 and len(responses) < 194:
                wait = max(0.0, parsed.rate_reset - time.time() + 5.0)
                if time.monotonic() - run_clock + wait > protocol.maximum_elapsed_seconds:
                    raise ValueError("S5 targeted v3 rate wait exceeds run bound")
                if wait > 0:
                    wait_count += 1
                    wait_seconds += wait
                    print(
                        f"S5 targeted v3 rate limit reached; waiting {wait:.1f}s",
                        flush=True,
                    )
                    time.sleep(wait)
    except Exception as exc:  # noqa: BLE001 - terminal acquisition failure is evidence
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
    completed_at = datetime.now(UTC)
    result = build_result(
        target_protocol=target_protocol,
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        git_inspection=git_inspection,
        responses=responses,
        started_at=started_at,
        completed_at=completed_at,
        resumed_v3_response_count=len(existing),
        new_request_attempt_count=new_attempts,
        rate_limit_wait_count=wait_count,
        rate_limit_wait_seconds=wait_seconds,
        failure_type=failure_type,
        failure_message=failure_message,
        failure_artifact_path=failure_artifact,
    )
    write_result_atomic(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S5 targeted v3 acquisition.")
    parser.add_argument(
        "--target-protocol", type=Path, default=DEFAULT_TARGET_PROTOCOL
    )
    parser.add_argument("--v3-protocol", type=Path, default=DEFAULT_V3_PROTOCOL)
    parser.add_argument(
        "--v3-protocol-audit", type=Path, default=DEFAULT_V3_PROTOCOL_AUDIT
    )
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        target, protocol, audit, contract, contract_audit = load_authorization(
            target_protocol_path=args.target_protocol,
            protocol_path=args.v3_protocol,
            protocol_audit_path=args.v3_protocol_audit,
            contract_path=args.execution_contract,
            contract_audit_path=args.execution_contract_audit,
        )
        result = run(
            target_protocol=target,
            protocol=protocol,
            protocol_audit=audit,
            contract=contract,
            contract_audit=contract_audit,
            output_path=args.output,
        )
        print(
            f"{result.decision} {args.output} {result.result_evidence_hash} "
            f"responses={len(result.response_bindings)} "
            f"http_200={result.http_200_count} http_404={result.http_404_count} "
            f"empty_merge_sha={result.empty_merge_commit_sha_response_count} "
            "market_values=0 returns=0 orders=0",
            flush=True,
        )
        return 0 if result.decision == S5_TARGETED_CORRECTION_PASS else 1
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
