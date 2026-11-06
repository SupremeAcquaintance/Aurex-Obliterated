from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_GATE_IDS,
    S5_GITHUB_PREFLIGHT_NEXT,
    S5_GITHUB_PREFLIGHT_NONE,
    S5_GITHUB_PREFLIGHT_PASS,
    S5_GITHUB_PREFLIGHT_STOP,
    S5GitHubPreflightGateResult,
    S5GitHubPreflightProtocol,
    S5GitHubPreflightProtocolAudit,
    S5GitHubPreflightResult,
    audit_s5_github_preflight_protocol,
    audit_s5_github_preflight_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_github_preflight_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_preflight_result_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_preflight.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_github_preflight.py")
TRANSCRIPT_SCHEMA = "aurex-s5-github-preflight-transcript-v1"
SHA1_CHARACTERS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class PreflightObservation:
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float
    request_headers: dict[str, str]
    http_status: int | None
    final_url: str | None
    response_headers: dict[str, str | None]
    response_body: bytes
    redirect_count: int
    transport_error_type: str | None
    transport_error_message: str | None


@dataclass(frozen=True)
class ParsedPreflight:
    payload_valid: bool = False
    pull_record_count: int = 0
    pull_number: int | None = None
    pull_state: str | None = None
    base_ref: str | None = None
    base_sha: str | None = None
    created_at: datetime | None = None
    merged_at: datetime | None = None
    merge_commit_sha: str | None = None
    terminal_record_count: int | None = None
    terminal_link_valid: bool = False
    error_message: str | None = None


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def load_protocol(protocol_path: Path, audit_path: Path) -> S5GitHubPreflightProtocol:
    protocol = S5GitHubPreflightProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S5GitHubPreflightProtocolAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    sources_match = all(
        file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in protocol.source_bindings
    )
    if (
        not audit_s5_github_preflight_protocol(protocol)
        or not audit_s5_github_preflight_protocol_audit(audit)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.protocol_file_sha256 != file_sha256(protocol_path)
        or audit.builder_contract_hash != protocol.builder_contract_hash
        or not sources_match
    ):
        raise ValueError("S5 GitHub preflight protocol, audit, or lineage changed")
    return protocol


def perform_request(protocol: S5GitHubPreflightProtocol) -> PreflightObservation:
    explicit_headers = {
        "Accept": protocol.accept_header,
        "X-GitHub-Api-Version": protocol.api_version_header,
        "User-Agent": protocol.user_agent,
    }
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    request_headers: dict[str, str] = {}
    http_status = None
    final_url = None
    response_headers: dict[str, str | None] = {}
    response_body = b""
    redirect_count = 0
    error_type = None
    error_message = None
    try:
        timeout = httpx.Timeout(protocol.maximum_elapsed_seconds)
        with httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            trust_env=False,
        ) as client:
            request = client.build_request(
                protocol.method,
                protocol.request_url,
                headers=explicit_headers,
            )
            request_headers = {key.lower(): value for key, value in request.headers.items()}
            if "authorization" in request_headers:
                raise ValueError("S5 GitHub preflight unexpectedly contains Authorization")
            response = client.send(request, stream=True)
            try:
                http_status = response.status_code
                final_url = str(response.url)
                redirect_count = len(response.history)
                response_headers = {
                    name: response.headers.get(name)
                    for name in (
                        "content-type",
                        "link",
                        "etag",
                        "x-ratelimit-limit",
                        "x-ratelimit-remaining",
                        "x-ratelimit-reset",
                        "x-ratelimit-resource",
                    )
                }
                chunks: list[bytes] = []
                byte_count = 0
                for chunk in response.iter_bytes():
                    remaining = protocol.maximum_response_bytes - byte_count
                    if len(chunk) > remaining:
                        if remaining > 0:
                            chunks.append(chunk[:remaining])
                        error_type = "ResponseBodyLimitExceeded"
                        error_message = (
                            "S5 GitHub preflight response exceeded the frozen byte limit"
                        )
                        break
                    chunks.append(chunk)
                    byte_count += len(chunk)
                response_body = b"".join(chunks)
            finally:
                response.close()
    except (httpx.HTTPError, OSError, ValueError) as exc:
        if error_type is None:
            error_type = type(exc).__name__
            error_message = str(exc)[:2000]
    completed_at = datetime.now(UTC)
    elapsed_seconds = round(time.monotonic() - started_clock, 6)
    return PreflightObservation(
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=elapsed_seconds,
        request_headers=request_headers,
        http_status=http_status,
        final_url=final_url,
        response_headers=response_headers,
        response_body=response_body,
        redirect_count=redirect_count,
        transport_error_type=error_type,
        transport_error_message=error_message,
    )


def transcript_payload(
    *, protocol: S5GitHubPreflightProtocol, observation: PreflightObservation
) -> dict[str, Any]:
    body_hash = (
        hashlib.sha256(observation.response_body).hexdigest() if observation.response_body else None
    )
    return {
        "schema_version": TRANSCRIPT_SCHEMA,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "started_at": observation.started_at.isoformat(),
        "completed_at": observation.completed_at.isoformat(),
        "elapsed_seconds": observation.elapsed_seconds,
        "request": {
            "method": protocol.method,
            "url": protocol.request_url,
            "headers": observation.request_headers,
            "authorization_header_used": False,
            "token_value_accessed": False,
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
            "type": observation.transport_error_type,
            "message": observation.transport_error_message,
        },
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub preflight artifact: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub preflight transaction exists: {temporary}")
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_result_atomic(path: Path, result: S5GitHubPreflightResult) -> None:
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5GitHubPreflightResult.model_validate_json(serialized) != result:
        raise ValueError("S5 GitHub preflight result did not round-trip")
    write_json_atomic(path, json.loads(serialized))


def observation_from_transcript(
    *, path: Path, protocol: S5GitHubPreflightProtocol
) -> PreflightObservation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != TRANSCRIPT_SCHEMA
        or payload.get("protocol_evidence_hash") != protocol.protocol_evidence_hash
    ):
        raise ValueError("S5 GitHub preflight transcript identity changed")
    request = payload["request"]
    response = payload["response"]
    error = payload["error"]
    body = base64.b64decode(response["body_base64"], validate=True)
    expected_hash = hashlib.sha256(body).hexdigest() if body else None
    if (
        request["method"] != protocol.method
        or request["url"] != protocol.request_url
        or request["authorization_header_used"] is not False
        or request["token_value_accessed"] is not False
        or request["environment_proxy_used"] is not False
        or response["body_byte_count"] != len(body)
        or response["body_sha256"] != expected_hash
    ):
        raise ValueError("S5 GitHub preflight transcript content changed")
    return PreflightObservation(
        started_at=datetime.fromisoformat(payload["started_at"]),
        completed_at=datetime.fromisoformat(payload["completed_at"]),
        elapsed_seconds=float(payload["elapsed_seconds"]),
        request_headers=dict(request["headers"]),
        http_status=response["http_status"],
        final_url=response["final_url"],
        response_headers=dict(response["headers"]),
        response_body=body,
        redirect_count=response["redirect_count"],
        transport_error_type=error["type"],
        transport_error_message=error["message"],
    )


def valid_sha1(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in SHA1_CHARACTERS for character in value)
    )


def parse_datetime(value: Any, *, nullable: bool) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError("S5 GitHub datetime field is invalid")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("S5 GitHub datetime lacks timezone")
    return parsed


def parse_terminal_link(
    link_header: str | None, *, protocol: S5GitHubPreflightProtocol
) -> tuple[int | None, bool]:
    if not link_header:
        return None, False
    relations: dict[str, str] = {}
    for segment in link_header.split(","):
        url_part, separator, parameters = segment.strip().partition(";")
        if not separator or not url_part.startswith("<") or not url_part.endswith(">"):
            return None, False
        relation = None
        for parameter in parameters.split(";"):
            key, equals, value = parameter.strip().partition("=")
            if equals and key == "rel":
                relation = value.strip('"')
        if relation:
            relations[relation] = url_part[1:-1]
    last_url = relations.get("last")
    if last_url is None:
        return None, False
    parsed = urlparse(last_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    expected = {
        "state": ["closed"],
        "base": ["master"],
        "sort": ["created"],
        "direction": ["asc"],
        "per_page": ["1"],
    }
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.path != "/repos/bitcoin/bitcoin/pulls"
        or any(query.get(key) != value for key, value in expected.items())
        or set(query) != {*expected, "page"}
        or len(query["page"]) != 1
        or not query["page"][0].isdigit()
        or int(query["page"][0]) <= 0
    ):
        return None, False
    return int(query["page"][0]), True


def parse_payload(
    *, observation: PreflightObservation, protocol: S5GitHubPreflightProtocol
) -> ParsedPreflight:
    terminal_count, link_valid = parse_terminal_link(
        observation.response_headers.get("link"), protocol=protocol
    )
    try:
        payload = json.loads(observation.response_body)
        if not isinstance(payload, list) or len(payload) != 1:
            raise ValueError("S5 GitHub preflight must return exactly one record")
        pull = payload[0]
        if not isinstance(pull, dict):
            raise ValueError("S5 GitHub preflight pull record is not an object")
        if any(
            field not in pull
            for field in ("number", "state", "created_at", "merged_at", "merge_commit_sha", "base")
        ):
            raise ValueError("S5 GitHub preflight pull record lacks a required field")
        base = pull.get("base")
        if not isinstance(base, dict):
            raise ValueError("S5 GitHub preflight base record is invalid")
        if "ref" not in base or "sha" not in base:
            raise ValueError("S5 GitHub preflight base record lacks a required field")
        number = pull.get("number")
        state = pull.get("state")
        base_ref = base.get("ref")
        base_sha = base.get("sha")
        merge_sha = pull.get("merge_commit_sha")
        if not isinstance(number, int) or number <= 0:
            raise ValueError("S5 GitHub preflight pull number is invalid")
        if state != "closed" or base_ref != "master":
            raise ValueError("S5 GitHub preflight pull scope changed")
        if not valid_sha1(base_sha) or (merge_sha is not None and not valid_sha1(merge_sha)):
            raise ValueError("S5 GitHub preflight object identity is invalid")
        return ParsedPreflight(
            payload_valid=True,
            pull_record_count=1,
            pull_number=number,
            pull_state=state,
            base_ref=base_ref,
            base_sha=base_sha,
            created_at=parse_datetime(pull.get("created_at"), nullable=False),
            merged_at=parse_datetime(pull.get("merged_at"), nullable=True),
            merge_commit_sha=merge_sha,
            terminal_record_count=terminal_count,
            terminal_link_valid=link_valid,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return ParsedPreflight(
            terminal_record_count=terminal_count,
            terminal_link_valid=link_valid,
            error_message=str(exc)[:2000],
        )


def integer_header(headers: dict[str, str | None], name: str) -> int | None:
    value = headers.get(name)
    return int(value) if value is not None and value.isdigit() else None


def build_gate_results(
    *,
    protocol: S5GitHubPreflightProtocol,
    observation: PreflightObservation,
    parsed: ParsedPreflight,
) -> tuple[S5GitHubPreflightGateResult, ...]:
    body_hash = (
        hashlib.sha256(observation.response_body).hexdigest() if observation.response_body else None
    )
    limit = integer_header(observation.response_headers, "x-ratelimit-limit")
    remaining = integer_header(observation.response_headers, "x-ratelimit-remaining")
    reset = integer_header(observation.response_headers, "x-ratelimit-reset")
    content_type = observation.response_headers.get("content-type")
    page_count = (
        None
        if parsed.terminal_record_count is None
        else (parsed.terminal_record_count + protocol.bulk_records_per_page - 1)
        // protocol.bulk_records_per_page
    )
    conditions = (
        len(protocol.source_bindings) == 4,
        observation.request_headers.get("accept") == protocol.accept_header
        and observation.request_headers.get("x-github-api-version") == protocol.api_version_header
        and observation.request_headers.get("user-agent") == protocol.user_agent,
        True,
        observation.transport_error_type is None
        and observation.http_status == 200
        and observation.final_url == protocol.request_url
        and observation.redirect_count == 0
        and observation.elapsed_seconds <= protocol.maximum_elapsed_seconds,
        observation.transport_error_type is None
        and 0 < len(observation.response_body) <= protocol.maximum_response_bytes
        and body_hash is not None,
        isinstance(content_type, str)
        and content_type.lower().startswith("application/json")
        and parsed.payload_valid,
        limit == protocol.unauthenticated_requests_per_hour
        and remaining is not None
        and 0 <= remaining < protocol.unauthenticated_requests_per_hour
        and reset is not None
        and observation.response_headers.get("x-ratelimit-resource") == "core",
        parsed.terminal_link_valid and parsed.terminal_record_count is not None,
        parsed.pull_record_count == 1
        and parsed.pull_state == "closed"
        and parsed.base_ref == "master"
        and parsed.created_at is not None
        and valid_sha1(parsed.base_sha)
        and (parsed.merge_commit_sha is None or valid_sha1(parsed.merge_commit_sha)),
        parsed.terminal_record_count is not None
        and page_count is not None
        and page_count == (parsed.terminal_record_count + 99) // 100,
        "authorization" not in observation.request_headers,
        True,
        True,
        parsed.terminal_record_count is not None and page_count is not None,
    )
    evidence = (
        "The transport decision and readiness-v31 result/audit artifacts remain hash-bound.",
        "The exact page-one GET and three explicit nonauthorization headers match protocol.",
        "Exactly one request attempt was executed; retry is structurally unavailable.",
        "The response must be HTTP 200 at the exact URL with zero redirect and bounded time.",
        "The nonempty response body is byte-bounded, SHA-256 hashed, and transcript-preserved.",
        "The response content type and one-record JSON payload both validate.",
        "Unauthenticated core rate-limit limit, remaining, reset, and resource headers validate.",
        "The terminal Link page retains every frozen query parameter and yields record count.",
        "Exactly one closed master pull record exposes required timestamps and object IDs.",
        "The record count yields exact 100-record page and 60-request-hour lower bounds.",
        "No Authorization header, token value, or environment proxy was used.",
        "Zero BTC values, parameters, returns, candidates, strategy executions, or orders ran.",
        "Source completeness and predictive edge remain explicitly unadjudicated.",
        "A PASS can authorize only a separately frozen bulk-acquisition protocol.",
    )
    return tuple(
        S5GitHubPreflightGateResult(
            gate_id=gate_id,
            status="PASS" if condition else "FAIL",
            evidence=message,
        )
        for gate_id, condition, message in zip(
            S5_GITHUB_PREFLIGHT_GATE_IDS, conditions, evidence, strict=True
        )
    )


def build_result(
    *,
    protocol: S5GitHubPreflightProtocol,
    observation: PreflightObservation,
    transcript_path: Path,
    executed_at: datetime,
) -> S5GitHubPreflightResult:
    parsed = parse_payload(observation=observation, protocol=protocol)
    gates = build_gate_results(protocol=protocol, observation=observation, parsed=parsed)
    failed = sum(item.status == "FAIL" for item in gates)
    passed = len(gates) - failed
    success = failed == 0
    page_count = (
        None
        if parsed.terminal_record_count is None
        else (parsed.terminal_record_count + protocol.bulk_records_per_page - 1)
        // protocol.bulk_records_per_page
    )
    unauthenticated_hours = (
        None
        if page_count is None
        else (page_count + protocol.unauthenticated_requests_per_hour - 1)
        // protocol.unauthenticated_requests_per_hour
    )
    body_hash = (
        hashlib.sha256(observation.response_body).hexdigest() if observation.response_body else None
    )
    failure_type = None
    failure_message = None
    if not success:
        failure_type = observation.transport_error_type or "PreflightGateFailure"
        failure_message = observation.transport_error_message or (
            "Failed gates: " + ", ".join(item.gate_id for item in gates if item.status == "FAIL")
        )
    payload: dict[str, Any] = {
        "executed_at": executed_at,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "transcript_file_sha256": file_sha256(transcript_path),
        "transcript_byte_count": transcript_path.stat().st_size,
        "started_at": observation.started_at,
        "completed_at": observation.completed_at,
        "elapsed_seconds": observation.elapsed_seconds,
        "request_url": protocol.request_url,
        "http_status": observation.http_status,
        "final_url": observation.final_url,
        "response_byte_count": len(observation.response_body),
        "response_body_sha256": body_hash,
        "content_type": observation.response_headers.get("content-type"),
        "link_header": observation.response_headers.get("link"),
        "etag_header": observation.response_headers.get("etag"),
        "x_ratelimit_limit": integer_header(observation.response_headers, "x-ratelimit-limit"),
        "x_ratelimit_remaining": integer_header(
            observation.response_headers, "x-ratelimit-remaining"
        ),
        "x_ratelimit_reset": integer_header(observation.response_headers, "x-ratelimit-reset"),
        "x_ratelimit_resource": observation.response_headers.get("x-ratelimit-resource"),
        "parsed_pull_record_count": parsed.pull_record_count,
        "first_pull_number": parsed.pull_number,
        "first_pull_state": parsed.pull_state,
        "first_pull_base_ref": parsed.base_ref,
        "first_pull_base_sha": parsed.base_sha,
        "first_pull_created_at": parsed.created_at,
        "first_pull_merged_at": parsed.merged_at,
        "first_pull_merge_commit_sha": parsed.merge_commit_sha,
        "terminal_record_count": parsed.terminal_record_count,
        "bulk_request_page_count_at_100": page_count,
        "bulk_unauthenticated_hours_lower_bound": unauthenticated_hours,
        "gate_results": gates,
        "passed_gate_count": passed,
        "failed_gate_count": failed,
        "github_metadata_records_parsed": parsed.pull_record_count,
        "decision": S5_GITHUB_PREFLIGHT_PASS if success else S5_GITHUB_PREFLIGHT_STOP,
        "next_authorization": S5_GITHUB_PREFLIGHT_NEXT if success else S5_GITHUB_PREFLIGHT_NONE,
        "authorizes_bulk_acquisition_protocol_design": success,
        "failure_type": failure_type,
        "failure_message": failure_message,
        "limitations": tuple(
            sorted(
                (
                    "The preflight validates one current GitHub response, not historical "
                    "completeness.",
                    "The terminal record count can change after this response snapshot.",
                    "Closed pull records include both merged and unmerged proposals.",
                    "The first record is used only for schema validation and cannot qualify a "
                    "signal.",
                    "Current platform metadata cannot guarantee preservation of deleted records.",
                    "A passing preflight authorizes only bulk-acquisition protocol design.",
                    "Bulk acquisition must be separately rate-limited, resumable, and audited.",
                    "No token, Authorization header, environment proxy, redirect, or retry was "
                    "used.",
                    "No BTC market value, parameter, return, candidate, signal, or order was "
                    "created.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority was created.",
                )
            )
        ),
    }
    provisional = S5GitHubPreflightResult.model_construct(**payload, result_evidence_hash="0" * 64)
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5GitHubPreflightResult.model_validate(complete)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the S5 GitHub metadata preflight once.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        protocol = load_protocol(args.protocol, args.protocol_audit)
        transcript_path = Path(protocol.transcript_path)
        if args.output.exists() or transcript_path.exists():
            raise ValueError("S5 GitHub preflight already ran; rerun forbidden")
        observation = perform_request(protocol)
        write_json_atomic(
            transcript_path,
            transcript_payload(protocol=protocol, observation=observation),
        )
        preserved = observation_from_transcript(path=transcript_path, protocol=protocol)
        result = build_result(
            protocol=protocol,
            observation=preserved,
            transcript_path=transcript_path,
            executed_at=datetime.now(UTC),
        )
        write_result_atomic(args.output, result)
        print(
            f"RECORDED {args.output} {result.result_evidence_hash} "
            f"decision={result.decision} status={result.http_status} "
            f"records={result.terminal_record_count} "
            f"bulk_pages={result.bulk_request_page_count_at_100} "
            f"rate_remaining={result.x_ratelimit_remaining} "
            f"gates={result.passed_gate_count}/14 requests=1 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
