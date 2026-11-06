from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

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
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_failure import (  # noqa: E402
    S5TargetedCorrectionV1FailureAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2 import (  # noqa: E402
    S5TargetedCorrectionV2Protocol,
    S5TargetedCorrectionV2ProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_execution import (  # noqa: E402
    S5TargetedCompletenessCorrectionResultV2,
    S5TargetedCorrectionV2ExecutionContract,
    S5TargetedCorrectionV2ExecutionContractAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction as base,
)

DEFAULT_TARGET_PROTOCOL = base.DEFAULT_PROTOCOL
DEFAULT_V2_PROTOCOL = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v2.json"
)
DEFAULT_V2_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_audit_v2.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_v2.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_audit_v2.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v2.json"
)
V1_RESULT_PATH = base.DEFAULT_RESULT
V1_FAILURE_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_v1_failure_audit_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_targeted_correction_v2_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_bitcoin_core_github_targeted_correction_v2.py")
RESPONSE_SCHEMA = "aurex-s5-github-targeted-pull-response-v2"
FAILURE_SCHEMA = "aurex-s5-github-targeted-pull-failure-v2"
ATTEMPT_SCHEMA = "aurex-s5-github-targeted-pull-attempt-v2"


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(
            {
                "path": path.as_posix(),
                "file_sha256": base.file_sha256(PROJECT_ROOT / path),
            }
            for path in sorted(
                (EXECUTION_MODULE_PATH, RUNNER_PATH), key=lambda item: item.as_posix()
            )
        )
    )


def bindings_match(bindings: tuple[Any, ...]) -> bool:
    return all(
        base.file_sha256(PROJECT_ROOT / row.path) == row.file_sha256
        for row in bindings
    )


def response_path(
    protocol: S5TargetedCorrectionV2Protocol,
    target: S5TargetedCorrectionTarget,
) -> Path:
    return Path(protocol.raw_response_directory) / protocol.response_file_pattern.format(
        pull_number=target.pull_number
    )


def attempt_path(
    protocol: S5TargetedCorrectionV2Protocol,
    target: S5TargetedCorrectionTarget,
) -> Path:
    response = response_path(protocol, target)
    return response.with_name(f"pull_{target.pull_number:06d}.attempt.json")


def attempt_payload(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV2Protocol,
    target: S5TargetedCorrectionTarget,
    started_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA,
        "target_protocol_evidence_hash": target_protocol.protocol_evidence_hash,
        "v2_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "target_manifest_evidence_hash": target_protocol.target_manifest_evidence_hash,
        "sequence": target.sequence,
        "pull_number": target.pull_number,
        "remedial_retry_of_v1_uncertain_get": target.pull_number == 10,
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


def validate_attempt_marker(
    *,
    path: Path,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV2Protocol,
    target: S5TargetedCorrectionTarget,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = attempt_payload(
        target_protocol=target_protocol,
        protocol=protocol,
        target=target,
        started_at=datetime.fromisoformat(payload["started_at"]),
    )
    if payload != expected:
        raise ValueError("S5 targeted v2 request marker changed")


def perform_request(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
    client_factory: Callable[..., Any] = httpx.Client,
) -> base.RequestObservation:
    url = base.request_url(target_protocol, target.pull_number)
    headers = base.explicit_headers(target_protocol)
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    status = None
    final_url = None
    response_headers: dict[str, str | None] = {}
    body = b""
    redirects = 0
    error_type = None
    error_message = None
    response = None
    try:
        with client_factory(
            follow_redirects=False,
            timeout=httpx.Timeout(120),
            trust_env=False,
        ) as client:
            request = client.build_request(target_protocol.method, url, headers=headers)
            if "authorization" in {name.lower() for name in request.headers}:
                raise ValueError("Authorization appeared in S5 targeted v2 request")
            response = client.send(request, stream=True)
            try:
                status = response.status_code
                final_url = str(response.url)
                redirects = len(response.history)
                response_headers = {
                    name: response.headers.get(name)
                    for name in (
                        "content-type",
                        "etag",
                        "x-ratelimit-limit",
                        "x-ratelimit-remaining",
                        "x-ratelimit-reset",
                        "x-ratelimit-resource",
                    )
                }
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    chunks.append(chunk)
                    if size > target_protocol.maximum_response_bytes_per_target:
                        break
                body = b"".join(chunks)
            finally:
                response.close()
    except Exception as exc:  # noqa: BLE001 - exact terminal failure is evidence
        error_type = type(exc).__name__
        error_message = str(exc)[:2000]
    completed_at = datetime.now(UTC)
    return base.RequestObservation(
        target=target,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=round(time.monotonic() - started_clock, 6),
        request_url=url,
        request_headers={name.lower(): value for name, value in headers.items()},
        http_status=status,
        final_url=final_url,
        response_headers=response_headers,
        response_body=body,
        redirect_count=redirects,
        error_type=error_type,
        error_message=error_message,
    )


def envelope_payload(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV2Protocol,
    observation: base.RequestObservation,
    schema_version: str = RESPONSE_SCHEMA,
) -> dict[str, Any]:
    payload = base.envelope_payload(
        protocol=target_protocol,
        observation=observation,
        schema_version=schema_version,
    )
    payload["schema_version"] = schema_version
    payload["target_protocol_evidence_hash"] = payload.pop("protocol_evidence_hash")
    payload["v2_protocol_evidence_hash"] = protocol.protocol_evidence_hash
    payload["remedial_retry_of_v1_uncertain_get"] = (
        observation.target.pull_number == 10
    )
    return payload


def observation_from_envelope(
    *,
    path: Path,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV2Protocol,
    target: S5TargetedCorrectionTarget,
) -> base.RequestObservation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != RESPONSE_SCHEMA
        or payload.get("target_protocol_evidence_hash")
        != target_protocol.protocol_evidence_hash
        or payload.get("v2_protocol_evidence_hash") != protocol.protocol_evidence_hash
        or payload.get("target_manifest_evidence_hash")
        != target_protocol.target_manifest_evidence_hash
        or payload.get("remedial_retry_of_v1_uncertain_get")
        != (target.pull_number == 10)
    ):
        raise ValueError("S5 targeted v2 response identity changed")
    request = payload["request"]
    response = payload["response"]
    error = payload["error"]
    body = base64.b64decode(response["body_base64"], validate=True)
    expected_headers = {
        name.lower(): value
        for name, value in base.explicit_headers(target_protocol).items()
    }
    if (
        payload.get("sequence") != target.sequence
        or payload.get("pull_number") != target.pull_number
        or payload.get("target_reasons") != list(target.target_reasons)
        or payload.get("request_attempt_count") != 1
        or request["method"] != target_protocol.method
        or request["url"] != base.request_url(target_protocol, target.pull_number)
        or request["headers"] != expected_headers
        or request["authorization_header_used"] is not False
        or request["credential_value_accessed"] is not False
        or request["environment_proxy_used"] is not False
        or response["body_byte_count"] != len(body)
        or response["body_sha256"] != hashlib.sha256(body).hexdigest()
    ):
        raise ValueError("S5 targeted v2 response content changed")
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


def load_existing_responses(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV2Protocol,
) -> list[tuple[Path, base.ParsedResponse]]:
    completed: list[tuple[Path, base.ParsedResponse]] = []
    gap_seen = False
    for target in target_protocol.target_manifest:
        response = response_path(protocol, target)
        marker = attempt_path(protocol, target)
        if response.exists() and marker.exists():
            if gap_seen:
                raise ValueError("S5 targeted v2 responses are not contiguous")
            validate_attempt_marker(
                path=marker,
                target_protocol=target_protocol,
                protocol=protocol,
                target=target,
            )
            observation = observation_from_envelope(
                path=response,
                target_protocol=target_protocol,
                protocol=protocol,
                target=target,
            )
            completed.append(
                (
                    response,
                    base.parse_observation(
                        observation=observation,
                        protocol=target_protocol,
                    ),
                )
            )
        elif response.exists():
            raise ValueError("S5 targeted v2 response lacks request marker")
        elif marker.exists():
            raise ValueError("S5 targeted v2 request outcome is uncertain")
        else:
            gap_seen = True
    return completed


def load_authorization(
    *,
    target_protocol_path: Path = DEFAULT_TARGET_PROTOCOL,
    v2_protocol_path: Path = DEFAULT_V2_PROTOCOL,
    v2_protocol_audit_path: Path = DEFAULT_V2_PROTOCOL_AUDIT,
    contract_path: Path = DEFAULT_EXECUTION_CONTRACT,
    contract_audit_path: Path = DEFAULT_EXECUTION_CONTRACT_AUDIT,
) -> tuple[
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCorrectionV2Protocol,
    S5TargetedCorrectionV2ProtocolAudit,
    S5TargetedCorrectionV2ExecutionContract,
    S5TargetedCorrectionV2ExecutionContractAudit,
]:
    target_protocol = S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        target_protocol_path.read_text(encoding="utf-8")
    )
    protocol = S5TargetedCorrectionV2Protocol.model_validate_json(
        v2_protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S5TargetedCorrectionV2ProtocolAudit.model_validate_json(
        v2_protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S5TargetedCorrectionV2ExecutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = S5TargetedCorrectionV2ExecutionContractAudit.model_validate_json(
        contract_audit_path.read_text(encoding="utf-8")
    )
    source_hash = universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in contract.source_bindings)
    )
    implementation_hash = universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in contract.implementation_bindings)
    )
    changed = (
        protocol.v1_protocol_evidence_hash != target_protocol.protocol_evidence_hash
        or protocol.target_manifest_evidence_hash
        != target_protocol.target_manifest_evidence_hash
        or protocol_audit.protocol_file_sha256 != base.file_sha256(v2_protocol_path)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or protocol_audit.target_manifest_evidence_hash
        != target_protocol.target_manifest_evidence_hash
        or not bindings_match(protocol.source_bindings)
        or contract.v1_target_protocol_evidence_hash
        != target_protocol.protocol_evidence_hash
        or contract.v2_protocol_file_sha256 != base.file_sha256(v2_protocol_path)
        or contract.v2_protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.v2_protocol_audit_file_sha256
        != base.file_sha256(v2_protocol_audit_path)
        or contract.v2_protocol_audit_evidence_hash
        != protocol_audit.audit_evidence_hash
        or contract.target_manifest_evidence_hash
        != target_protocol.target_manifest_evidence_hash
        or contract.runner_contract_hash != runner_contract_hash()
        or source_hash != contract.source_binding_manifest_evidence_hash
        or implementation_hash
        != contract.implementation_binding_manifest_evidence_hash
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or contract_audit.contract_file_sha256 != base.file_sha256(contract_path)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
    )
    if changed:
        raise ValueError("S5 targeted v2 authorization or lineage changed")
    return target_protocol, protocol, protocol_audit, contract, contract_audit


def build_result(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV2Protocol,
    protocol_audit: S5TargetedCorrectionV2ProtocolAudit,
    contract: S5TargetedCorrectionV2ExecutionContract,
    contract_audit: S5TargetedCorrectionV2ExecutionContractAudit,
    git_inspection: base.GitInspection,
    responses: list[tuple[Path, base.ParsedResponse]],
    started_at: datetime,
    completed_at: datetime,
    resumed_response_count: int,
    new_request_attempt_count: int,
    rate_limit_wait_count: int,
    rate_limit_wait_seconds: float,
    failure_type: str | None,
    failure_message: str | None,
    failure_artifact_path: Path | None,
) -> S5TargetedCompletenessCorrectionResultV2:
    v1_result = json.loads(V1_RESULT_PATH.read_text(encoding="utf-8"))
    v1_failure_audit = S5TargetedCorrectionV1FailureAudit.model_validate_json(
        V1_FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    bindings = tuple(
        base.response_binding(path=path, parsed=parsed)
        for path, parsed in responses
    )
    marker_count = sum(
        attempt_path(protocol, target).is_file()
        for target in target_protocol.target_manifest
    )
    logical_attempts = resumed_response_count + new_request_attempt_count
    passed = (
        failure_type is None
        and len(bindings) == 194
        and marker_count == 194
        and logical_attempts == 194
        and len(git_inspection.diagnostics) == 83
        and git_inspection.recognized_target_reachable_count == 83
        and git_inspection.full_graph_commit_count == 50_395
        and git_inspection.first_parent_commit_count == 17_543
        and git_inspection.first_parent_merge_count == 16_721
        and sum(row.response_body_byte_count for row in bindings)
        <= protocol.maximum_total_response_bytes
    )
    if failure_type is None and not passed:
        failure_type = "TargetedV2AcquisitionGateFailure"
        failure_message = "One or more terminal v2 acquisition gates failed"
    gates = base.build_gate_results(passed=passed, failure_message=failure_message)
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
            base.load_local_lineage(target_protocol)[0].history_dataset_directory_sha256
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
        "resumed_response_count": resumed_response_count,
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
                    "V1 made one uncertain pull-10 GET before the transport defect stopped it.",
                    "V2 made one disclosed remedial pull-10 GET under a frozen protocol.",
                    "A pass authorizes corrected normalization protocol design only.",
                    "The original normalization STOP remains binding after acquisition.",
                    "Responses are current metadata, not immutable historical snapshots.",
                    "A 404 proves only the endpoint response at acquisition time.",
                    "Merge commit semantics depend on merge, squash, and rebase behavior.",
                    "Git reachability does not prove historical public availability time.",
                    "No response automatically creates an accepted development event.",
                    "No mapping or completeness rule changed during acquisition.",
                    "No market value, return, parameter, candidate, signal, or order was created.",
                    "No paper, Testnet strategy, production, live, or real-capital "
                    "authority exists.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "Acquisition success is not evidence of reliability or profit.",
                    "Real net profit remains zero.",
                )
            )
        ),
        "v1_target_protocol_evidence_hash": target_protocol.protocol_evidence_hash,
        "v2_remediation_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "v1_failure_result_evidence_hash": v1_result["result_evidence_hash"],
        "v1_failure_audit_evidence_hash": v1_failure_audit.audit_evidence_hash,
    }
    provisional = S5TargetedCompletenessCorrectionResultV2.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5TargetedCompletenessCorrectionResultV2.model_validate(complete)


def write_result_atomic(
    path: Path, result: S5TargetedCompletenessCorrectionResultV2
) -> None:
    if path.exists():
        raise ValueError(f"S5 targeted v2 result already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v2 result transaction: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5TargetedCompletenessCorrectionResultV2.model_validate_json(
        serialized
    ) != result:
        raise ValueError("S5 targeted v2 result did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run(
    *,
    target_protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol: S5TargetedCorrectionV2Protocol,
    protocol_audit: S5TargetedCorrectionV2ProtocolAudit,
    contract: S5TargetedCorrectionV2ExecutionContract,
    contract_audit: S5TargetedCorrectionV2ExecutionContractAudit,
    output_path: Path,
) -> S5TargetedCompletenessCorrectionResultV2:
    if output_path.exists():
        raise ValueError(f"S5 targeted v2 result already exists: {output_path}")
    started_at = datetime.now(UTC)
    run_clock = time.monotonic()
    normalization, census = base.load_local_lineage(target_protocol)
    responses = load_existing_responses(
        target_protocol=target_protocol,
        protocol=protocol,
    )
    resumed_response_count = len(responses)
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
            if time.monotonic() - run_clock >= protocol.maximum_elapsed_seconds:
                raise ValueError("S5 targeted v2 elapsed-time bound reached")
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
            observation = perform_request(
                target_protocol=target_protocol,
                target=target,
            )
            try:
                parsed = base.parse_observation(
                    observation=observation,
                    protocol=target_protocol,
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
                    f"S5 targeted v2 progress {len(responses)}/194 "
                    f"remaining={parsed.rate_remaining}",
                    flush=True,
                )
            if parsed.rate_remaining == 0 and len(responses) < 194:
                wait = max(0.0, parsed.rate_reset - time.time() + 5.0)
                if time.monotonic() - run_clock + wait > protocol.maximum_elapsed_seconds:
                    raise ValueError("S5 targeted v2 rate wait exceeds run bound")
                if wait > 0:
                    wait_count += 1
                    wait_seconds += wait
                    print(
                        f"S5 targeted v2 rate limit reached; waiting {wait:.1f}s",
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
        resumed_response_count=resumed_response_count,
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
    parser = argparse.ArgumentParser(description="Run S5 targeted v2 acquisition.")
    parser.add_argument(
        "--target-protocol", type=Path, default=DEFAULT_TARGET_PROTOCOL
    )
    parser.add_argument("--v2-protocol", type=Path, default=DEFAULT_V2_PROTOCOL)
    parser.add_argument(
        "--v2-protocol-audit", type=Path, default=DEFAULT_V2_PROTOCOL_AUDIT
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
        target, protocol, protocol_audit, contract, contract_audit = (
            load_authorization(
                target_protocol_path=args.target_protocol,
                v2_protocol_path=args.v2_protocol,
                v2_protocol_audit_path=args.v2_protocol_audit,
                contract_path=args.execution_contract,
                contract_audit_path=args.execution_contract_audit,
            )
        )
        result = run(
            target_protocol=target,
            protocol=protocol,
            protocol_audit=protocol_audit,
            contract=contract,
            contract_audit=contract_audit,
            output_path=args.output,
        )
        print(
            f"{result.decision} {args.output} {result.result_evidence_hash} "
            f"responses={len(result.response_bindings)} "
            f"http_200={result.http_200_count} http_404={result.http_404_count} "
            "market_values=0 returns=0 orders=0",
            flush=True,
        )
        return 0 if result.decision == S5_TARGETED_CORRECTION_PASS else 1
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
