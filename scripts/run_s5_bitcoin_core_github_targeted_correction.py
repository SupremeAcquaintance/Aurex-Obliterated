from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (  # noqa: E402
    S5GitHubNormalizationProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (  # noqa: E402
    S5_TARGETED_CORRECTION_GATE_IDS,
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCompletenessCorrectionProtocolAudit,
    S5TargetedCorrectionTarget,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (  # noqa: E402
    S5_TARGETED_CORRECTION_FAILURE_NEXT,
    S5_TARGETED_CORRECTION_NEXT,
    S5_TARGETED_CORRECTION_PASS,
    S5_TARGETED_CORRECTION_STOP,
    S5TargetedCompletenessCorrectionResult,
    S5TargetedCorrectionCommitDiagnostic,
    S5TargetedCorrectionExecutionContract,
    S5TargetedCorrectionExecutionContractAudit,
    S5TargetedCorrectionGateResult,
    S5TargetedCorrectionResponseBinding,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5BitcoinCoreHistoryCensusResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_protocol_audit_v1.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_v1.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_audit_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v1.json"
)
NORMALIZATION_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
)
CENSUS_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_result_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_targeted_correction_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_bitcoin_core_github_targeted_correction.py")
RESPONSE_SCHEMA = "aurex-s5-github-targeted-pull-response-v1"
FAILURE_SCHEMA = "aurex-s5-github-targeted-pull-failure-v1"
ATTEMPT_SCHEMA = "aurex-s5-github-targeted-pull-attempt-v1"
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
RESPONSE_FILE_RE = re.compile(r"^pull_(\d{6})\.json$")
ATTEMPT_FILE_RE = re.compile(r"^pull_(\d{6})\.attempt\.json$")


@dataclass(frozen=True)
class RequestObservation:
    target: S5TargetedCorrectionTarget
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float
    request_url: str
    request_headers: dict[str, str]
    http_status: int | None
    final_url: str | None
    response_headers: dict[str, str | None]
    response_body: bytes
    redirect_count: int
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True)
class ParsedResponse:
    target: S5TargetedCorrectionTarget
    http_status: int
    response_body_sha256: str
    response_body_byte_count: int
    rate_limit: int
    rate_remaining: int
    rate_reset: int


@dataclass(frozen=True)
class GitInspection:
    full_graph_stream_sha256: str
    full_graph_commit_count: int
    first_parent_commit_count: int
    first_parent_merge_count: int
    recognized_target_reachable_count: int
    diagnostics: tuple[S5TargetedCorrectionCommitDiagnostic, ...]


class ResponseFailure(ValueError):
    def __init__(self, message: str, observation: RequestObservation) -> None:
        super().__init__(message)
        self.observation = observation


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runner_contract_hash() -> str:
    paths = tuple(
        sorted((EXECUTION_MODULE_PATH, RUNNER_PATH), key=lambda item: item.as_posix())
    )
    return universe_evidence_hash(
        tuple(
            {
                "path": path.as_posix(),
                "file_sha256": file_sha256(PROJECT_ROOT / path),
            }
            for path in paths
        )
    )


def binding_manifest_hash(bindings: tuple[Any, ...]) -> str:
    return universe_evidence_hash(
        tuple(binding.model_dump(mode="json") for binding in bindings)
    )


def bindings_match(bindings: tuple[Any, ...]) -> bool:
    return all(
        file_sha256(PROJECT_ROOT / binding.path) == binding.file_sha256
        for binding in bindings
    )


def load_authorization(
    *,
    protocol_path: Path = DEFAULT_PROTOCOL,
    protocol_audit_path: Path = DEFAULT_PROTOCOL_AUDIT,
    contract_path: Path = DEFAULT_EXECUTION_CONTRACT,
    contract_audit_path: Path = DEFAULT_EXECUTION_CONTRACT_AUDIT,
) -> tuple[
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCompletenessCorrectionProtocolAudit,
    S5TargetedCorrectionExecutionContract,
    S5TargetedCorrectionExecutionContractAudit,
]:
    protocol = S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S5TargetedCompletenessCorrectionProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S5TargetedCorrectionExecutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = S5TargetedCorrectionExecutionContractAudit.model_validate_json(
        contract_audit_path.read_text(encoding="utf-8")
    )
    changed = (
        protocol_audit.protocol_file_sha256 != file_sha256(protocol_path)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or protocol_audit.builder_contract_hash != protocol.builder_contract_hash
        or protocol_audit.target_manifest_evidence_hash
        != protocol.target_manifest_evidence_hash
        or not bindings_match(protocol.source_bindings)
        or contract.protocol_file_sha256 != file_sha256(protocol_path)
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_file_sha256 != file_sha256(protocol_audit_path)
        or contract.protocol_audit_evidence_hash
        != protocol_audit.audit_evidence_hash
        or contract.target_manifest_evidence_hash
        != protocol.target_manifest_evidence_hash
        or contract.runner_contract_hash != runner_contract_hash()
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or binding_manifest_hash(contract.source_bindings)
        != contract.source_binding_manifest_evidence_hash
        or binding_manifest_hash(contract.implementation_bindings)
        != contract.implementation_binding_manifest_evidence_hash
        or contract_audit.contract_file_sha256 != file_sha256(contract_path)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
        or contract_audit.builder_contract_hash != contract.builder_contract_hash
    )
    if changed:
        raise ValueError("S5 targeted correction authorization or lineage changed")
    return protocol, protocol_audit, contract, contract_audit


def load_local_lineage(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> tuple[S5GitHubNormalizationProtocol, S5BitcoinCoreHistoryCensusResult]:
    normalization = S5GitHubNormalizationProtocol.model_validate_json(
        NORMALIZATION_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    census = S5BitcoinCoreHistoryCensusResult.model_validate_json(
        CENSUS_RESULT_PATH.read_text(encoding="utf-8")
    )
    if (
        normalization.protocol_evidence_hash
        != protocol.normalization_protocol_evidence_hash
        or census.result_evidence_hash != protocol.census_result_evidence_hash
        or normalization.census_result_evidence_hash != census.result_evidence_hash
    ):
        raise ValueError("S5 targeted correction local lineage changed")
    return normalization, census


def request_url(
    protocol: S5TargetedCompletenessCorrectionProtocol, pull_number: int
) -> str:
    return protocol.direct_pull_endpoint_template.format(pull_number=pull_number)


def explicit_headers(
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> dict[str, str]:
    return {
        "Accept": protocol.accept_header,
        "X-GitHub-Api-Version": protocol.api_version_header,
        "User-Agent": protocol.user_agent,
    }


def response_path(
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
) -> Path:
    return Path(protocol.raw_response_directory) / protocol.response_file_pattern.format(
        pull_number=target.pull_number
    )


def attempt_path(
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
) -> Path:
    response = response_path(protocol, target)
    return response.with_name(f"pull_{target.pull_number:06d}.attempt.json")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted artifact: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted transaction exists: {temporary}")
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def attempt_payload(
    *,
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
    started_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "target_manifest_evidence_hash": protocol.target_manifest_evidence_hash,
        "sequence": target.sequence,
        "pull_number": target.pull_number,
        "started_at": started_at.isoformat(),
        "request": {
            "method": protocol.method,
            "url": request_url(protocol, target.pull_number),
            "headers": {
                name.lower(): value for name, value in explicit_headers(protocol).items()
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
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = attempt_payload(
        protocol=protocol,
        target=target,
        started_at=datetime.fromisoformat(payload["started_at"]),
    )
    if payload != expected:
        raise ValueError("S5 targeted request marker changed")


def perform_request(
    *,
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
) -> RequestObservation:
    url = request_url(protocol, target.pull_number)
    headers = explicit_headers(protocol)
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    status = None
    final_url = None
    response_headers: dict[str, str | None] = {}
    body = b""
    redirects = 0
    error_type = None
    error_message = None
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(120),
            trust_env=False,
        ) as client:
            request = client.build_request(protocol.method, url, headers=headers)
            if "authorization" in {name.lower() for name in request.headers}:
                raise ValueError("Authorization appeared in S5 targeted request")
            with client.send(request, stream=True) as response:
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
                    if size > protocol.maximum_response_bytes_per_target:
                        break
                body = b"".join(chunks)
    except Exception as exc:  # noqa: BLE001 - exact terminal failure is evidence
        error_type = type(exc).__name__
        error_message = str(exc)[:2000]
    completed_at = datetime.now(UTC)
    return RequestObservation(
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


def parse_datetime_field(value: Any, *, nullable: bool) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError("GitHub targeted datetime field is invalid")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("GitHub targeted datetime lacks timezone")
    return parsed


def validate_200_payload(
    payload: Any,
    *,
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("GitHub targeted pull response is not an object")
    top_level_fields = tuple(
        field for field in protocol.required_200_fields if "." not in field
    )
    if any(field not in payload for field in top_level_fields):
        raise ValueError("GitHub targeted pull response lacks a required field")
    if payload["number"] != target.pull_number:
        raise ValueError("GitHub targeted pull identity changed")
    if not isinstance(payload["node_id"], str) or not payload["node_id"]:
        raise ValueError("GitHub targeted node identity is invalid")
    if payload["state"] not in {"open", "closed"}:
        raise ValueError("GitHub targeted pull state is invalid")
    created_at = parse_datetime_field(payload["created_at"], nullable=False)
    updated_at = parse_datetime_field(payload["updated_at"], nullable=False)
    closed_at = parse_datetime_field(payload["closed_at"], nullable=True)
    merged_at = parse_datetime_field(payload["merged_at"], nullable=True)
    assert created_at is not None and updated_at is not None
    if updated_at < created_at:
        raise ValueError("GitHub targeted update precedes creation")
    if closed_at is not None and closed_at < created_at:
        raise ValueError("GitHub targeted close precedes creation")
    if merged_at is not None and merged_at < created_at:
        raise ValueError("GitHub targeted merge precedes creation")
    if not isinstance(payload["merged"], bool):
        raise ValueError("GitHub targeted merged flag is invalid")
    merge_commit_sha = payload["merge_commit_sha"]
    if merge_commit_sha is not None and (
        SHA1_RE.fullmatch(str(merge_commit_sha)) is None
    ):
        raise ValueError("GitHub targeted merge commit SHA is invalid")
    head = payload.get("head")
    base = payload.get("base")
    if not isinstance(head, dict) or (
        SHA1_RE.fullmatch(str(head.get("sha", ""))) is None
    ):
        raise ValueError("GitHub targeted head identity is invalid")
    if (
        not isinstance(base, dict)
        or not isinstance(base.get("ref"), str)
        or not base["ref"]
        or SHA1_RE.fullmatch(str(base.get("sha", ""))) is None
    ):
        raise ValueError("GitHub targeted base identity is invalid")
    user = payload["user"]
    if user is not None and (
        not isinstance(user, dict)
        or not isinstance(user.get("id"), int)
        or not isinstance(user.get("login"), str)
        or not isinstance(user.get("type"), str)
    ):
        raise ValueError("GitHub targeted actor identity is invalid")


def parse_observation(
    *,
    observation: RequestObservation,
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> ParsedResponse:
    try:
        if observation.error_type is not None:
            raise ValueError(
                f"GitHub request failed: {observation.error_type}: "
                f"{observation.error_message}"
            )
        if (
            observation.http_status not in protocol.acceptable_http_statuses
            or observation.final_url != observation.request_url
            or observation.redirect_count != 0
        ):
            raise ValueError("GitHub targeted response status, URL, or redirect changed")
        if not 0 < len(observation.response_body) <= (
            protocol.maximum_response_bytes_per_target
        ):
            raise ValueError("GitHub targeted response byte bound failed")
        content_type = observation.response_headers.get("content-type") or ""
        if "application/json" not in content_type.lower():
            raise ValueError("GitHub targeted response content type is not JSON")
        payload = json.loads(observation.response_body)
        if observation.http_status == 200:
            validate_200_payload(
                payload,
                protocol=protocol,
                target=observation.target,
            )
        elif not isinstance(payload, dict) or not isinstance(payload.get("message"), str):
            raise ValueError("GitHub targeted 404 payload is invalid")
        rate_limit = int(observation.response_headers.get("x-ratelimit-limit") or "")
        rate_remaining = int(
            observation.response_headers.get("x-ratelimit-remaining") or ""
        )
        rate_reset = int(observation.response_headers.get("x-ratelimit-reset") or "")
        rate_resource = observation.response_headers.get("x-ratelimit-resource")
        if (
            rate_limit != 60
            or not 0 <= rate_remaining < rate_limit
            or rate_reset <= 0
            or rate_resource != "core"
        ):
            raise ValueError("GitHub targeted rate-limit headers are invalid")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ResponseFailure(str(exc), observation) from exc
    assert observation.http_status is not None
    return ParsedResponse(
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
    protocol: S5TargetedCompletenessCorrectionProtocol,
    observation: RequestObservation,
    schema_version: str = RESPONSE_SCHEMA,
) -> dict[str, Any]:
    body_hash = hashlib.sha256(observation.response_body).hexdigest()
    return {
        "schema_version": schema_version,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "target_manifest_evidence_hash": protocol.target_manifest_evidence_hash,
        "sequence": observation.target.sequence,
        "pull_number": observation.target.pull_number,
        "target_reasons": list(observation.target.target_reasons),
        "request_attempt_count": 1,
        "started_at": observation.started_at.isoformat(),
        "completed_at": observation.completed_at.isoformat(),
        "elapsed_seconds": observation.elapsed_seconds,
        "request": {
            "method": protocol.method,
            "url": observation.request_url,
            "headers": observation.request_headers,
            "authorization_header_used": False,
            "credential_value_accessed": False,
            "environment_proxy_used": False,
        },
        "response": {
            "http_status": observation.http_status,
            "final_url": observation.final_url,
            "redirect_count": observation.redirect_count,
            "headers": observation.response_headers,
            "body_byte_count": len(observation.response_body),
            "body_sha256": body_hash,
            "body_base64": base64.b64encode(observation.response_body).decode("ascii"),
        },
        "error": {
            "type": observation.error_type,
            "message": observation.error_message,
        },
    }


def observation_from_envelope(
    *,
    path: Path,
    protocol: S5TargetedCompletenessCorrectionProtocol,
    target: S5TargetedCorrectionTarget,
) -> RequestObservation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != RESPONSE_SCHEMA
        or payload.get("protocol_evidence_hash") != protocol.protocol_evidence_hash
        or payload.get("target_manifest_evidence_hash")
        != protocol.target_manifest_evidence_hash
        or payload.get("sequence") != target.sequence
        or payload.get("pull_number") != target.pull_number
        or payload.get("target_reasons") != list(target.target_reasons)
        or payload.get("request_attempt_count") != 1
    ):
        raise ValueError("S5 targeted response envelope identity changed")
    request = payload["request"]
    response = payload["response"]
    error = payload["error"]
    body = base64.b64decode(response["body_base64"], validate=True)
    expected_headers = {
        name.lower(): value for name, value in explicit_headers(protocol).items()
    }
    if (
        request["method"] != protocol.method
        or request["url"] != request_url(protocol, target.pull_number)
        or request["headers"] != expected_headers
        or request["authorization_header_used"] is not False
        or request["credential_value_accessed"] is not False
        or request["environment_proxy_used"] is not False
        or response["body_byte_count"] != len(body)
        or response["body_sha256"] != hashlib.sha256(body).hexdigest()
    ):
        raise ValueError("S5 targeted response envelope content changed")
    return RequestObservation(
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


def response_binding(
    *, path: Path, parsed: ParsedResponse
) -> S5TargetedCorrectionResponseBinding:
    return S5TargetedCorrectionResponseBinding(
        sequence=parsed.target.sequence,
        pull_number=parsed.target.pull_number,
        path=path.as_posix(),
        file_sha256=file_sha256(path),
        file_byte_count=path.stat().st_size,
        response_body_sha256=parsed.response_body_sha256,
        response_body_byte_count=parsed.response_body_byte_count,
        http_status=parsed.http_status,
        rate_limit=parsed.rate_limit,
        rate_remaining=parsed.rate_remaining,
        rate_reset=parsed.rate_reset,
    )


def load_existing_responses(
    *,
    protocol: S5TargetedCompletenessCorrectionProtocol,
) -> list[tuple[Path, ParsedResponse]]:
    directory = Path(protocol.raw_response_directory)
    if not directory.exists():
        return []
    response_numbers = {
        int(match.group(1))
        for path in directory.iterdir()
        if (match := RESPONSE_FILE_RE.fullmatch(path.name)) is not None
    }
    attempt_numbers = {
        int(match.group(1))
        for path in directory.iterdir()
        if (match := ATTEMPT_FILE_RE.fullmatch(path.name)) is not None
    }
    target_numbers = {target.pull_number for target in protocol.target_manifest}
    if (response_numbers | attempt_numbers) - target_numbers:
        raise ValueError("S5 targeted response directory contains an unknown target")
    completed: list[tuple[Path, ParsedResponse]] = []
    gap_seen = False
    for target in protocol.target_manifest:
        response = response_path(protocol, target)
        marker = attempt_path(protocol, target)
        if response.exists() and marker.exists():
            if gap_seen:
                raise ValueError("S5 targeted completed responses are not contiguous")
            validate_attempt_marker(path=marker, protocol=protocol, target=target)
            observation = observation_from_envelope(
                path=response,
                protocol=protocol,
                target=target,
            )
            completed.append(
                (
                    response,
                    parse_observation(observation=observation, protocol=protocol),
                )
            )
        elif response.exists():
            raise ValueError("S5 targeted response lacks its pre-request marker")
        elif marker.exists():
            raise ValueError(
                "S5 targeted request outcome is uncertain; retry is forbidden"
            )
        else:
            gap_seen = True
    return completed


def dataset_manifest_hash(path: Path) -> str:
    records: list[dict[str, Any]] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError("S5 history dataset contains a symbolic link")
        if candidate.is_file():
            records.append(
                {
                    "relative_path": candidate.relative_to(path).as_posix(),
                    "file_sha256": file_sha256(candidate),
                    "byte_count": candidate.stat().st_size,
                }
            )
    return universe_evidence_hash(records)


def git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
        }
    )
    environment.pop("GITHUB_TOKEN", None)
    environment.pop("GH_TOKEN", None)
    return environment


def git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        raise ValueError("Git executable is unavailable")
    return executable


def git_command(repo: Path, *arguments: str) -> list[str]:
    return [
        git_executable(),
        "-c",
        "credential.helper=",
        "-c",
        "http.extraHeader=",
        "-C",
        str(repo),
        *arguments,
    ]


def parse_full_graph(
    payload: bytes, *, cutoff: str
) -> tuple[dict[str, tuple[str, ...]], str, int, int]:
    try:
        decoded = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("S5 targeted full graph was not ASCII") from exc
    rows = tuple(line.strip() for line in decoded.splitlines() if line.strip())
    if not rows:
        raise ValueError("S5 targeted full graph is empty")
    graph: dict[str, tuple[str, ...]] = {}
    canonical: list[str] = []
    for row in rows:
        parts = row.split()
        if not parts or any(SHA1_RE.fullmatch(item) is None for item in parts):
            raise ValueError("S5 targeted full graph row is malformed")
        commit, parents = parts[0], tuple(parts[1:])
        if commit in graph:
            raise ValueError("S5 targeted full graph repeats a commit")
        graph[commit] = parents
        canonical.append(" ".join(parts))
    if rows[0].split()[0] != cutoff or cutoff not in graph:
        raise ValueError("S5 targeted full graph cutoff identity changed")
    first_parent_count = 0
    first_parent_merge_count = 0
    visited: set[str] = set()
    current = cutoff
    while True:
        if current in visited or current not in graph:
            raise ValueError("S5 targeted first-parent topology is invalid")
        visited.add(current)
        first_parent_count += 1
        parents = graph[current]
        if len(parents) >= 2:
            first_parent_merge_count += 1
        if not parents:
            break
        current = parents[0]
    stream = ("\n".join(canonical) + "\n").encode("ascii")
    return (
        graph,
        hashlib.sha256(stream).hexdigest(),
        first_parent_count,
        first_parent_merge_count,
    )


def execute_full_graph(
    *, repo: Path, cutoff: str, timeout: float
) -> tuple[dict[str, tuple[str, ...]], str, int, int]:
    completed = subprocess.run(
        git_command(repo, "rev-list", "--parents", cutoff),
        capture_output=True,
        check=False,
        env=git_environment(),
        timeout=timeout,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"S5 targeted full graph failed: {message}")
    return parse_full_graph(completed.stdout, cutoff=cutoff)


def parse_commit_batch(
    *,
    payload: bytes,
    targets: tuple[S5TargetedCorrectionTarget, ...],
    census: S5BitcoinCoreHistoryCensusResult,
) -> tuple[S5TargetedCorrectionCommitDiagnostic, ...]:
    census_by_pull = {
        row.pull_request_id: row for row in census.accepted_pull_request_records
    }
    stream = io.BytesIO(payload)
    diagnostics: list[S5TargetedCorrectionCommitDiagnostic] = []
    for sequence, target in enumerate(targets, start=1):
        assert target.census_merge_commit_sha is not None
        header = stream.readline().rstrip(b"\n").split(b" ")
        if len(header) != 3:
            raise ValueError("S5 targeted cat-file response header is malformed")
        returned, object_type, object_size = header
        if (
            returned.decode("ascii") != target.census_merge_commit_sha
            or object_type != b"commit"
            or not object_size.isdigit()
        ):
            raise ValueError("S5 targeted cat-file returned an unexpected object")
        size = int(object_size)
        raw_object = stream.read(size)
        if len(raw_object) != size or stream.read(1) != b"\n":
            raise ValueError("S5 targeted cat-file response is truncated")
        header_block, separator, message = raw_object.partition(b"\n\n")
        if not separator:
            raise ValueError("S5 targeted commit object lacks a message separator")
        parent_count = sum(
            line.startswith(b"parent ") for line in header_block.splitlines()
        )
        first_line_bytes = message.split(b"\n", 1)[0].removesuffix(b"\r")
        first_line_hash = hashlib.sha256(first_line_bytes).hexdigest()
        census_row = census_by_pull[target.pull_number]
        if (
            census_row.merge_commit_hash != target.census_merge_commit_sha
            or census_row.pattern_id != target.census_pattern_id
            or census_row.first_line_sha256 != first_line_hash
            or parent_count < 2
        ):
            raise ValueError("S5 targeted commit diagnostic differs from census")
        diagnostics.append(
            S5TargetedCorrectionCommitDiagnostic(
                sequence=sequence,
                pull_number=target.pull_number,
                census_merge_commit_sha=target.census_merge_commit_sha,
                parent_count=parent_count,
                first_line=first_line_bytes.decode("utf-8", errors="replace")[:300],
                first_line_sha256=first_line_hash,
                census_first_line_sha256=census_row.first_line_sha256,
            )
        )
    if stream.read(1):
        raise ValueError("S5 targeted cat-file emitted trailing bytes")
    return tuple(diagnostics)


def execute_commit_diagnostics(
    *,
    repo: Path,
    targets: tuple[S5TargetedCorrectionTarget, ...],
    census: S5BitcoinCoreHistoryCensusResult,
    timeout: float,
) -> tuple[S5TargetedCorrectionCommitDiagnostic, ...]:
    request = (
        "\n".join(str(target.census_merge_commit_sha) for target in targets) + "\n"
    ).encode("ascii")
    completed = subprocess.run(
        git_command(repo, "cat-file", "--batch"),
        input=request,
        capture_output=True,
        check=False,
        env=git_environment(),
        timeout=timeout,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"S5 targeted commit diagnostics failed: {message}")
    return parse_commit_batch(payload=completed.stdout, targets=targets, census=census)


def inspect_git(
    *,
    protocol: S5TargetedCompletenessCorrectionProtocol,
    normalization: S5GitHubNormalizationProtocol,
    census: S5BitcoinCoreHistoryCensusResult,
) -> GitInspection:
    repo = Path(normalization.history_dataset_path)
    if not repo.is_dir():
        raise ValueError("S5 targeted history dataset is missing")
    if dataset_manifest_hash(repo) != normalization.history_dataset_directory_sha256:
        raise ValueError("S5 targeted history dataset hash changed")
    graph, stream_hash, first_parent_count, merge_count = execute_full_graph(
        repo=repo,
        cutoff=normalization.source_cutoff_commit,
        timeout=600,
    )
    recognized = tuple(
        target
        for target in protocol.target_manifest
        if "RECOGNIZED_GAP" in target.target_reasons
    )
    reachable_count = sum(
        target.census_merge_commit_sha in graph for target in recognized
    )
    diagnostics = execute_commit_diagnostics(
        repo=repo,
        targets=recognized,
        census=census,
        timeout=600,
    )
    return GitInspection(
        full_graph_stream_sha256=stream_hash,
        full_graph_commit_count=len(graph),
        first_parent_commit_count=first_parent_count,
        first_parent_merge_count=merge_count,
        recognized_target_reachable_count=reachable_count,
        diagnostics=diagnostics,
    )


def build_gate_results(
    *, passed: bool, failure_message: str | None
) -> tuple[S5TargetedCorrectionGateResult, ...]:
    preserved_on_stop = {
        "NORMALIZATION_STOP_AND_FAILURE_ADJUDICATION_LINEAGE_BOUND",
        "EXACT_83_RECOGNIZED_112_UNMATCHED_1_OVERLAP_194_UNION_TARGETS",
        "TARGET_PULL_IDS_AND_REASONS_FROZEN_BEFORE_DIRECT_ACCESS",
        "ONE_CREDENTIAL_FREE_DIRECT_PULL_REQUEST_PER_TARGET_MAXIMUM",
        "EXACT_83_CENSUS_MERGE_COMMIT_FIRST_LINES_ONLY",
        "FULL_REACHABILITY_GRAPH_AND_TARGET_OBJECT_ACCESS_BOUNDED_TO_TWO_GIT_PROCESSES",
        "NO_MAPPING_OR_COMPLETENESS_RULE_CHANGES_DURING_ACQUISITION",
        "ZERO_MARKET_VALUES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
    }
    rows: list[S5TargetedCorrectionGateResult] = []
    for gate_id in S5_TARGETED_CORRECTION_GATE_IDS:
        gate_passed = passed or gate_id in preserved_on_stop
        if passed:
            evidence = "The complete targeted acquisition satisfies this frozen gate."
        elif gate_passed:
            evidence = "This invariant remained preserved during the acquisition stop."
        else:
            evidence = (
                "Targeted acquisition stopped before this gate could pass: "
                f"{failure_message}."
            )
        rows.append(
            S5TargetedCorrectionGateResult(
                gate_id=gate_id,
                status="PASS" if gate_passed else "FAIL",
                evidence=evidence,
            )
        )
    return tuple(rows)


def build_result(
    *,
    protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol_audit: S5TargetedCompletenessCorrectionProtocolAudit,
    contract: S5TargetedCorrectionExecutionContract,
    contract_audit: S5TargetedCorrectionExecutionContractAudit,
    normalization: S5GitHubNormalizationProtocol,
    git_inspection: GitInspection,
    responses: list[tuple[Path, ParsedResponse]],
    started_at: datetime,
    completed_at: datetime,
    resumed_response_count: int,
    new_request_attempt_count: int,
    rate_limit_wait_count: int,
    rate_limit_wait_seconds: float,
    failure_type: str | None,
    failure_message: str | None,
    failure_artifact_path: Path | None,
) -> S5TargetedCompletenessCorrectionResult:
    response_bindings = tuple(
        response_binding(path=path, parsed=parsed) for path, parsed in responses
    )
    marker_count = sum(
        attempt_path(protocol, target).is_file()
        for target in protocol.target_manifest
    )
    logical_attempts = resumed_response_count + new_request_attempt_count
    passed = (
        failure_type is None
        and len(response_bindings) == 194
        and marker_count == 194
        and logical_attempts == 194
        and len(git_inspection.diagnostics) == 83
        and git_inspection.recognized_target_reachable_count == 83
        and git_inspection.full_graph_commit_count == 50_395
        and git_inspection.first_parent_commit_count == 17_543
        and git_inspection.first_parent_merge_count == 16_721
        and sum(row.response_body_byte_count for row in response_bindings)
        <= protocol.maximum_total_response_bytes
    )
    if failure_type is None and not passed:
        failure_type = "TargetedAcquisitionGateFailure"
        failure_message = "One or more terminal targeted-acquisition gates failed"
    gates = build_gate_results(passed=passed, failure_message=failure_message)
    payload = {
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": round((completed_at - started_at).total_seconds(), 6),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "target_manifest_evidence_hash": protocol.target_manifest_evidence_hash,
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
        "response_bindings": response_bindings,
        "request_attempt_marker_count": marker_count,
        "logical_request_attempt_count": logical_attempts,
        "new_request_attempt_count": new_request_attempt_count,
        "resumed_response_count": resumed_response_count,
        "http_200_count": sum(row.http_status == 200 for row in response_bindings),
        "http_404_count": sum(row.http_status == 404 for row in response_bindings),
        "total_response_bytes": sum(
            row.response_body_byte_count for row in response_bindings
        ),
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
            else file_sha256(failure_artifact_path)
        ),
        "limitations": tuple(
            sorted(
                (
                    "A pass authorizes corrected normalization protocol design only.",
                    "The original normalization STOP remains binding after acquisition.",
                    "Direct responses are current GitHub metadata, not immutable "
                    "historical snapshots.",
                    "A 404 establishes only that the direct endpoint returned 404 at "
                    "acquisition time.",
                    "GitHub merge_commit_sha semantics depend on merge, squash, and "
                    "rebase behavior.",
                    "Local Git reachability does not establish historical public "
                    "availability time.",
                    "Commit first lines are diagnostics and do not independently "
                    "establish acceptance time.",
                    "No acquired response automatically creates an accepted development event.",
                    "No mapping or completeness rule was changed during this acquisition.",
                    "No BTC market value, parameter, return, candidate, signal, or "
                    "order was created.",
                    "No paper, Testnet strategy, production, live, or real-capital "
                    "authority exists.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "A source acquisition pass is not evidence of a reliable strategy or profit.",
                    "Real net profit remains zero.",
                )
            )
        ),
    }
    provisional = S5TargetedCompletenessCorrectionResult.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5TargetedCompletenessCorrectionResult.model_validate(complete)


def write_result_atomic(
    path: Path, result: S5TargetedCompletenessCorrectionResult
) -> None:
    if path.exists():
        raise ValueError(f"S5 targeted correction result already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted result transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5TargetedCompletenessCorrectionResult.model_validate_json(serialized) != result:
        raise ValueError("S5 targeted correction result did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run(
    *,
    protocol: S5TargetedCompletenessCorrectionProtocol,
    protocol_audit: S5TargetedCompletenessCorrectionProtocolAudit,
    contract: S5TargetedCorrectionExecutionContract,
    contract_audit: S5TargetedCorrectionExecutionContractAudit,
    output_path: Path,
) -> S5TargetedCompletenessCorrectionResult:
    if output_path.exists():
        raise ValueError(f"S5 targeted correction result already exists: {output_path}")
    started_at = datetime.now(UTC)
    run_clock = time.monotonic()
    normalization, census = load_local_lineage(protocol)
    responses = load_existing_responses(protocol=protocol)
    resumed_response_count = len(responses)
    git_inspection = inspect_git(
        protocol=protocol,
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
        for target in protocol.target_manifest[len(responses) :]:
            elapsed = time.monotonic() - run_clock
            if elapsed >= protocol.maximum_elapsed_seconds:
                raise ValueError("S5 targeted correction elapsed-time bound reached")
            marker = attempt_path(protocol, target)
            write_json_atomic(
                marker,
                attempt_payload(
                    protocol=protocol,
                    target=target,
                    started_at=datetime.now(UTC),
                ),
            )
            new_attempts += 1
            observation = perform_request(protocol=protocol, target=target)
            try:
                parsed = parse_observation(
                    observation=observation,
                    protocol=protocol,
                )
            except ResponseFailure:
                failure_artifact = Path(protocol.raw_response_directory) / (
                    f"failure_pull_{target.pull_number:06d}.json"
                )
                write_json_atomic(
                    failure_artifact,
                    envelope_payload(
                        protocol=protocol,
                        observation=observation,
                        schema_version=FAILURE_SCHEMA,
                    ),
                )
                raise
            path = response_path(protocol, target)
            write_json_atomic(
                path,
                envelope_payload(protocol=protocol, observation=observation),
            )
            responses.append((path, parsed))
            if len(responses) % 10 == 0 or len(responses) == 194:
                print(
                    f"S5 targeted acquisition progress {len(responses)}/194 "
                    f"remaining={parsed.rate_remaining}",
                    flush=True,
                )
            if parsed.rate_remaining == 0 and len(responses) < 194:
                wait = max(0.0, parsed.rate_reset - time.time() + 5.0)
                if time.monotonic() - run_clock + wait > protocol.maximum_elapsed_seconds:
                    raise ValueError("S5 targeted rate-limit wait exceeds run bound")
                if wait > 0:
                    wait_count += 1
                    wait_seconds += wait
                    print(
                        f"S5 targeted rate limit reached; waiting {wait:.1f}s",
                        flush=True,
                    )
                    time.sleep(wait)
    except Exception as exc:  # noqa: BLE001 - terminal acquisition failure is evidence
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
    completed_at = datetime.now(UTC)
    result = build_result(
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        normalization=normalization,
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
    parser = argparse.ArgumentParser(description="Run S5 targeted correction acquisition.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
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
        protocol, protocol_audit, contract, contract_audit = load_authorization(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            contract_path=args.execution_contract,
            contract_audit_path=args.execution_contract_audit,
        )
        result = run(
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
