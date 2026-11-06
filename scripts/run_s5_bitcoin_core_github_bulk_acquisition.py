from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5_GITHUB_BULK_FAILURE_NEXT,
    S5_GITHUB_BULK_GATE_IDS,
    S5_GITHUB_BULK_NEXT,
    S5_GITHUB_BULK_PASS,
    S5_GITHUB_BULK_RUN,
    S5_GITHUB_BULK_STOP,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkGateResult,
    S5GitHubBulkPageBinding,
    S5GitHubBulkProtocolAudit,
    S5GitHubBulkResult,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_github_bulk_acquisition.py")
PAGE_SCHEMA = "aurex-s5-github-bulk-page-v1"
FAILURE_SCHEMA = "aurex-s5-github-bulk-failure-page-v1"
PAGE_FILE_RE = re.compile(r"^page_(\d{4})\.json$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class PullRecord:
    number: int
    created_at: datetime
    state: str
    merged_at: datetime | None
    user_is_null: bool


@dataclass(frozen=True)
class ParsedPage:
    page: int
    records: tuple[PullRecord, ...]
    terminal_page: int
    next_page: int | None
    response_body_sha256: str
    response_byte_count: int
    rate_limit: int
    rate_remaining: int
    rate_reset: int


@dataclass(frozen=True)
class RequestObservation:
    page: int
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


class PageFailure(ValueError):
    def __init__(self, message: str, observation: RequestObservation) -> None:
        super().__init__(message)
        self.observation = observation


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def load_protocol(protocol_path: Path, audit_path: Path) -> S5GitHubBulkAcquisitionProtocol:
    protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S5GitHubBulkProtocolAudit.model_validate_json(audit_path.read_text(encoding="utf-8"))
    sources_match = all(
        file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in protocol.source_bindings
    )
    if (
        not evidence_hash_valid(protocol, "protocol_evidence_hash")
        or not evidence_hash_valid(audit, "audit_evidence_hash")
        or audit.protocol_file_sha256 != file_sha256(protocol_path)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.builder_contract_hash != protocol.builder_contract_hash
        or audit.next_authorization != S5_GITHUB_BULK_RUN
        or not sources_match
    ):
        raise ValueError("S5 GitHub bulk protocol, audit, or lineage changed")
    return protocol


def request_url(protocol: S5GitHubBulkAcquisitionProtocol, page: int) -> str:
    query = urlencode(
        {
            "state": protocol.query_state,
            "base": protocol.query_base,
            "sort": protocol.query_sort,
            "direction": protocol.query_direction,
            "per_page": protocol.records_per_page,
            "page": page,
        }
    )
    return f"{protocol.endpoint}?{query}"


def explicit_headers(protocol: S5GitHubBulkAcquisitionProtocol) -> dict[str, str]:
    return {
        "Accept": protocol.accept_header,
        "X-GitHub-Api-Version": protocol.api_version_header,
        "User-Agent": protocol.user_agent,
    }


def perform_request(*, protocol: S5GitHubBulkAcquisitionProtocol, page: int) -> RequestObservation:
    url = request_url(protocol, page)
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
            timeout=httpx.Timeout(protocol.request_timeout_seconds),
            trust_env=False,
        ) as client:
            request = client.build_request(protocol.method, url, headers=headers)
            if "authorization" in {name.lower() for name in request.headers}:
                raise ValueError("Authorization header appeared in S5 GitHub bulk request")
            with client.send(request, stream=True) as response:
                status = response.status_code
                final_url = str(response.url)
                redirects = len(response.history)
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
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    chunks.append(chunk)
                    if size > protocol.maximum_response_bytes_per_page:
                        break
                body = b"".join(chunks)
    except Exception as exc:  # noqa: BLE001 - the exact failure is evidence
        error_type = type(exc).__name__
        error_message = str(exc)[:2000]
    completed_at = datetime.now(UTC)
    return RequestObservation(
        page=page,
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


def parse_datetime(value: Any, *, nullable: bool) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError("GitHub pull datetime field is invalid")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("GitHub pull datetime lacks timezone")
    return parsed


def parse_link_page(url: str, *, protocol: S5GitHubBulkAcquisitionProtocol) -> int:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    expected = {
        "state": [protocol.query_state],
        "base": [protocol.query_base],
        "sort": [protocol.query_sort],
        "direction": [protocol.query_direction],
        "per_page": [str(protocol.records_per_page)],
    }
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.path not in protocol.canonical_link_paths
        or set(query) != {*expected, "page"}
        or any(query.get(key) != value for key, value in expected.items())
        or len(query["page"]) != 1
        or not query["page"][0].isdigit()
    ):
        raise ValueError("GitHub bulk pagination link changed query scope")
    page = int(query["page"][0])
    if not 1 <= page <= protocol.maximum_terminal_page:
        raise ValueError("GitHub bulk pagination page exceeds frozen bound")
    return page


def parse_link_header(
    link_header: str | None,
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    page: int,
) -> tuple[int, int | None]:
    if not link_header:
        return page, None
    relations: dict[str, int] = {}
    for segment in link_header.split(","):
        url_part, separator, parameters = segment.strip().partition(";")
        if not separator or not url_part.startswith("<") or not url_part.endswith(">"):
            raise ValueError("GitHub bulk Link header is malformed")
        relation = None
        for parameter in parameters.split(";"):
            key, equals, value = parameter.strip().partition("=")
            if equals and key == "rel":
                relation = value.strip('"')
        if relation:
            relations[relation] = parse_link_page(url_part[1:-1], protocol=protocol)
    next_page = relations.get("next")
    if next_page is not None and next_page != page + 1:
        raise ValueError("GitHub bulk next-page relation is not contiguous")
    terminal_page = relations.get("last", page if next_page is None else None)
    if terminal_page is None or terminal_page < page:
        raise ValueError("GitHub bulk terminal page is unavailable or regressed")
    return terminal_page, next_page


def parse_pull_record(value: Any, *, protocol: S5GitHubBulkAcquisitionProtocol) -> PullRecord:
    if not isinstance(value, dict) or any(
        field not in value for field in protocol.required_pull_fields if "." not in field
    ):
        raise ValueError("GitHub bulk pull record lacks a required top-level field")
    number = value["number"]
    node_id = value["node_id"]
    state = value["state"]
    head = value.get("head")
    base = value.get("base")
    user = value["user"]
    if not isinstance(number, int) or number <= 0:
        raise ValueError("GitHub bulk pull number is invalid")
    if not isinstance(node_id, str) or not node_id:
        raise ValueError("GitHub bulk pull node ID is invalid")
    if state not in {"open", "closed"}:
        raise ValueError("GitHub bulk pull state is invalid")
    if not isinstance(head, dict) or not SHA1_RE.fullmatch(str(head.get("sha", ""))):
        raise ValueError("GitHub bulk pull head SHA is invalid")
    if (
        not isinstance(base, dict)
        or base.get("ref") != protocol.query_base
        or not SHA1_RE.fullmatch(str(base.get("sha", "")))
    ):
        raise ValueError("GitHub bulk pull base identity is invalid")
    if user is not None and (
        not isinstance(user, dict)
        or not isinstance(user.get("id"), int)
        or not isinstance(user.get("login"), str)
        or not isinstance(user.get("type"), str)
    ):
        raise ValueError("GitHub bulk pull user identity is invalid")
    created_at = parse_datetime(value["created_at"], nullable=False)
    updated_at = parse_datetime(value["updated_at"], nullable=False)
    closed_at = parse_datetime(value["closed_at"], nullable=True)
    merged_at = parse_datetime(value["merged_at"], nullable=True)
    assert created_at is not None and updated_at is not None
    if updated_at < created_at:
        raise ValueError("GitHub bulk pull update precedes creation")
    if closed_at is not None and closed_at < created_at:
        raise ValueError("GitHub bulk pull close precedes creation")
    if merged_at is not None and (merged_at < created_at or state != "closed"):
        raise ValueError("GitHub bulk pull merge time or state is invalid")
    return PullRecord(
        number=number,
        created_at=created_at,
        state=state,
        merged_at=merged_at,
        user_is_null=user is None,
    )


def parse_observation(
    *, observation: RequestObservation, protocol: S5GitHubBulkAcquisitionProtocol
) -> ParsedPage:
    if observation.error_type is not None:
        raise PageFailure(
            f"GitHub request failed: {observation.error_type}: {observation.error_message}",
            observation,
        )
    if (
        observation.http_status != 200
        or observation.final_url != observation.request_url
        or observation.redirect_count != 0
    ):
        raise PageFailure("GitHub bulk response status, URL, or redirect changed", observation)
    if not 0 < len(observation.response_body) <= protocol.maximum_response_bytes_per_page:
        raise PageFailure("GitHub bulk response byte bound failed", observation)
    content_type = observation.response_headers.get("content-type") or ""
    if "application/json" not in content_type.lower():
        raise PageFailure("GitHub bulk response content type is not JSON", observation)
    try:
        payload = json.loads(observation.response_body)
        if not isinstance(payload, list) or not 1 <= len(payload) <= protocol.records_per_page:
            raise ValueError("GitHub bulk page is empty or oversized")
        records = tuple(parse_pull_record(item, protocol=protocol) for item in payload)
        terminal_page, next_page = parse_link_header(
            observation.response_headers.get("link"),
            protocol=protocol,
            page=observation.page,
        )
        if next_page is not None and len(records) != protocol.records_per_page:
            raise ValueError("GitHub bulk nonterminal page is not full")
        if next_page is None and observation.page != terminal_page:
            raise ValueError("GitHub bulk terminal relation is inconsistent")
        rate_limit = int(observation.response_headers.get("x-ratelimit-limit") or "")
        rate_remaining = int(observation.response_headers.get("x-ratelimit-remaining") or "")
        rate_reset = int(observation.response_headers.get("x-ratelimit-reset") or "")
        rate_resource = observation.response_headers.get("x-ratelimit-resource")
        if (
            rate_limit != protocol.unauthenticated_rate_limit
            or not 0 <= rate_remaining < rate_limit
            or rate_reset <= 0
            or rate_resource != "core"
        ):
            raise ValueError("GitHub bulk rate-limit headers are invalid")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PageFailure(str(exc), observation) from exc
    return ParsedPage(
        page=observation.page,
        records=records,
        terminal_page=terminal_page,
        next_page=next_page,
        response_body_sha256=hashlib.sha256(observation.response_body).hexdigest(),
        response_byte_count=len(observation.response_body),
        rate_limit=rate_limit,
        rate_remaining=rate_remaining,
        rate_reset=rate_reset,
    )


def envelope_payload(
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    observation: RequestObservation,
    schema_version: str = PAGE_SCHEMA,
) -> dict[str, Any]:
    body_hash = hashlib.sha256(observation.response_body).hexdigest()
    return {
        "schema_version": schema_version,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "page": observation.page,
        "request_attempt_count": 1,
        "started_at": observation.started_at.isoformat(),
        "completed_at": observation.completed_at.isoformat(),
        "elapsed_seconds": observation.elapsed_seconds,
        "request": {
            "method": protocol.method,
            "url": observation.request_url,
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
        "error": {"type": observation.error_type, "message": observation.error_message},
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk artifact: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk transaction exists: {temporary}")
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def observation_from_envelope(
    *, path: Path, protocol: S5GitHubBulkAcquisitionProtocol
) -> RequestObservation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != PAGE_SCHEMA
        or payload.get("protocol_evidence_hash") != protocol.protocol_evidence_hash
        or payload.get("request_attempt_count") != 1
    ):
        raise ValueError("S5 GitHub bulk page envelope identity changed")
    request = payload["request"]
    response = payload["response"]
    error = payload["error"]
    page = int(payload["page"])
    body = base64.b64decode(response["body_base64"], validate=True)
    if (
        request["method"] != protocol.method
        or request["url"] != request_url(protocol, page)
        or request["headers"]
        != {name.lower(): value for name, value in explicit_headers(protocol).items()}
        or request["authorization_header_used"] is not False
        or request["token_value_accessed"] is not False
        or request["environment_proxy_used"] is not False
        or response["body_byte_count"] != len(body)
        or response["body_sha256"] != hashlib.sha256(body).hexdigest()
    ):
        raise ValueError("S5 GitHub bulk page envelope content changed")
    return RequestObservation(
        page=page,
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


def page_binding(*, path: Path, parsed: ParsedPage) -> S5GitHubBulkPageBinding:
    return S5GitHubBulkPageBinding(
        page=parsed.page,
        path=path.as_posix(),
        file_sha256=file_sha256(path),
        file_byte_count=path.stat().st_size,
        response_body_sha256=parsed.response_body_sha256,
        response_byte_count=parsed.response_byte_count,
        record_count=len(parsed.records),
        first_pull_number=parsed.records[0].number,
        last_pull_number=parsed.records[-1].number,
        rate_limit=parsed.rate_limit,
        rate_remaining=parsed.rate_remaining,
        rate_reset=parsed.rate_reset,
    )


def load_existing_pages(
    *, protocol: S5GitHubBulkAcquisitionProtocol, page_directory: Path
) -> tuple[list[tuple[Path, ParsedPage]], int | None]:
    if not page_directory.exists():
        return [], None
    files = sorted(path for path in page_directory.iterdir() if PAGE_FILE_RE.fullmatch(path.name))
    expected_names = [
        protocol.page_file_pattern.format(page=index) for index in range(1, len(files) + 1)
    ]
    if [path.name for path in files] != expected_names:
        raise ValueError("Existing S5 GitHub bulk pages are not contiguous")
    parsed_pages: list[tuple[Path, ParsedPage]] = []
    expected_terminal = None
    for path in files:
        observation = observation_from_envelope(path=path, protocol=protocol)
        parsed = parse_observation(observation=observation, protocol=protocol)
        if expected_terminal is None:
            expected_terminal = parsed.terminal_page
        if parsed.page < expected_terminal and parsed.terminal_page != expected_terminal:
            raise ValueError("Existing S5 GitHub bulk terminal page drifted")
        parsed_pages.append((path, parsed))
    if expected_terminal is not None and len(parsed_pages) > expected_terminal:
        raise ValueError("Existing S5 GitHub bulk pages exceed terminal page")
    return parsed_pages, expected_terminal


def summarize_records(pages: list[tuple[Path, ParsedPage]], *, cutoff: datetime) -> dict[str, Any]:
    records = [record for _, page in pages for record in page.records]
    numbers = [record.number for record in records]
    created = [record.created_at for record in records]
    monotonic = all(left <= right for left, right in zip(created, created[1:], strict=False))
    unique = len(set(numbers))
    return {
        "records": records,
        "raw_record_count": len(records),
        "cohort_record_count": sum(record.created_at <= cutoff for record in records),
        "post_cutoff_record_count": sum(record.created_at > cutoff for record in records),
        "open_record_count": sum(record.state == "open" for record in records),
        "closed_unmerged_record_count": sum(
            record.state == "closed" and record.merged_at is None for record in records
        ),
        "merged_record_count": sum(record.merged_at is not None for record in records),
        "null_user_record_count": sum(record.user_is_null for record in records),
        "unique_pull_number_count": unique,
        "duplicate_pull_number_count": len(records) - unique,
        "minimum_created_at": min(created) if created else None,
        "maximum_created_at": max(created) if created else None,
        "creation_order_monotonic": monotonic,
    }


def build_gate_results(*, passed: bool, reason: str | None) -> tuple[S5GitHubBulkGateResult, ...]:
    always_pass = {
        "CORRECTED_PREFLIGHT_AND_READINESS_V32_LINEAGE_BOUND",
        "ALL_STATE_STABLE_MEMBERSHIP_QUERY_EXACTLY_BOUND",
        "UNAUTHENTICATED_SERIAL_REQUEST_POLICY_PRESERVED",
        "NO_TOKEN_PROXY_MARKET_VALUE_PARAMETER_RETURN_OR_ORDER",
        "SOURCE_COMPLETENESS_AND_PREDICTIVE_EDGE_NOT_ADJUDICATED",
    }
    return tuple(
        S5GitHubBulkGateResult(
            gate_id=gate_id,
            status="PASS" if passed or gate_id in always_pass else "FAIL",
            evidence=(
                "The complete raw-page acquisition satisfies this frozen gate."
                if passed
                else (
                    "This invariant remains preserved despite the transport stop."
                    if gate_id in always_pass
                    else f"Bulk acquisition stopped before this gate could pass: {reason}."
                )
            ),
        )
        for gate_id in S5_GITHUB_BULK_GATE_IDS
    )


def build_result(
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    pages: list[tuple[Path, ParsedPage]],
    started_at: datetime,
    completed_at: datetime,
    new_request_attempt_count: int,
    resumed_page_count: int,
    wait_count: int,
    wait_seconds: float,
    failure_type: str | None = None,
    failure_message: str | None = None,
    failure_path: Path | None = None,
) -> S5GitHubBulkResult:
    summary = summarize_records(pages, cutoff=protocol.cohort_created_at_cutoff)
    expected_terminal = pages[0][1].terminal_page if pages else None
    pages_complete = bool(
        pages
        and expected_terminal == len(pages)
        and pages[-1][1].next_page is None
        and all(
            parsed.terminal_page == expected_terminal or parsed.page == expected_terminal
            for _, parsed in pages
        )
    )
    passed = (
        failure_type is None
        and pages_complete
        and summary["duplicate_pull_number_count"] == 0
        and summary["creation_order_monotonic"]
        and summary["cohort_record_count"] > 0
        and sum(page.response_byte_count for _, page in pages)
        <= protocol.maximum_total_response_bytes
    )
    reason = failure_message
    if failure_type is None and not passed:
        failure_type = "BulkAcquisitionGateFailure"
        reason = "One or more terminal bulk-acquisition invariants failed"
        failure_message = reason
    gates = build_gate_results(passed=passed, reason=reason)
    bindings = tuple(page_binding(path=path, parsed=parsed) for path, parsed in pages)
    payload = {
        "executed_at": completed_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": round((completed_at - started_at).total_seconds(), 6),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "raw_page_directory": protocol.raw_page_directory,
        "page_bindings": bindings,
        "logical_request_attempt_count": resumed_page_count + new_request_attempt_count,
        "new_request_attempt_count": new_request_attempt_count,
        "successful_request_count": len(pages),
        "resumed_page_count": resumed_page_count,
        "acquired_page_count": len(pages) - resumed_page_count,
        "terminal_page_count": expected_terminal,
        **{
            key: value
            for key, value in summary.items()
            if key not in {"records", "creation_order_monotonic"}
        },
        "total_response_bytes": sum(page.response_byte_count for _, page in pages),
        "rate_limit_wait_count": wait_count,
        "rate_limit_wait_seconds": round(wait_seconds, 6),
        "gate_results": gates,
        "passed_gate_count": sum(gate.status == "PASS" for gate in gates),
        "failed_gate_count": sum(gate.status == "FAIL" for gate in gates),
        "decision": S5_GITHUB_BULK_PASS if passed else S5_GITHUB_BULK_STOP,
        "next_authorization": S5_GITHUB_BULK_NEXT if passed else S5_GITHUB_BULK_FAILURE_NEXT,
        "authorizes_normalization_protocol_design": passed,
        "failure_type": failure_type,
        "failure_message": failure_message,
        "failure_artifact_path": None if failure_path is None else failure_path.as_posix(),
        "failure_artifact_sha256": None if failure_path is None else file_sha256(failure_path),
        "limitations": tuple(
            sorted(
                (
                    "A passing result authorizes normalization protocol design only.",
                    "Raw records created after the frozen cutoff are excluded from the cohort.",
                    "Merged-only filtering and Git second-parent identity matching remain undone.",
                    "Page membership is stable against state changes but not every "
                    "metadata mutation.",
                    "Deleted or retargeted historical records can still prevent completeness.",
                    "GitHub current metadata does not prove historical publication timing "
                    "by itself.",
                    "Public account identifiers require explicit uncertainty handling before use.",
                    "No BTC market value, parameter, return, candidate, signal, or order "
                    "was created.",
                    "No paper, Testnet strategy, production, live, or real-capital "
                    "authority exists.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "A transport pass is not evidence of a reliable strategy or profit.",
                    "Real net profit remains zero.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkResult.model_construct(**payload, result_evidence_hash="0" * 64)
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5GitHubBulkResult.model_validate(complete)


def write_result_atomic(path: Path, result: S5GitHubBulkResult) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk result: {path}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkResult.model_validate_json(serialized) != result:
        raise ValueError("S5 GitHub bulk result did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk result transaction exists: {temporary}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run(
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    output_path: Path,
) -> S5GitHubBulkResult:
    if output_path.exists():
        raise ValueError(f"S5 GitHub bulk result already exists: {output_path}")
    page_directory = Path(protocol.raw_page_directory)
    pages, terminal_page = load_existing_pages(protocol=protocol, page_directory=page_directory)
    resumed_page_count = len(pages)
    started_at = datetime.now(UTC)
    run_clock = time.monotonic()
    new_attempts = 0
    wait_count = 0
    wait_seconds = 0.0
    failure_path = None
    failure_type = None
    failure_message = None
    next_page = len(pages) + 1
    try:
        while terminal_page is None or next_page <= terminal_page:
            if time.monotonic() - run_clock > protocol.maximum_run_seconds:
                raise ValueError("S5 GitHub bulk run exceeded the frozen elapsed-time bound")
            observation = perform_request(protocol=protocol, page=next_page)
            new_attempts += 1
            try:
                parsed = parse_observation(observation=observation, protocol=protocol)
                if terminal_page is None:
                    terminal_page = parsed.terminal_page
                elif next_page < terminal_page and parsed.terminal_page != terminal_page:
                    raise PageFailure(
                        "GitHub bulk terminal page drifted during acquisition", observation
                    )
                page_path = page_directory / protocol.page_file_pattern.format(page=next_page)
                write_json_atomic(
                    page_path,
                    envelope_payload(protocol=protocol, observation=observation),
                )
                pages.append((page_path, parsed))
                print(
                    f"PAGE {next_page}/{terminal_page} records={len(parsed.records)} "
                    f"remaining={parsed.rate_remaining} bytes={parsed.response_byte_count}",
                    flush=True,
                )
                if parsed.next_page is None and next_page != terminal_page:
                    raise ValueError("GitHub bulk pagination ended before the frozen terminal page")
                if (
                    parsed.rate_remaining <= protocol.wait_when_remaining_at_or_below
                    and next_page < terminal_page
                ):
                    seconds = max(
                        0.0,
                        parsed.rate_reset - time.time() + protocol.reset_safety_seconds,
                    )
                    if seconds > protocol.maximum_single_wait_seconds:
                        raise ValueError("GitHub bulk rate-limit wait exceeds the frozen bound")
                    wait_count += 1
                    wait_seconds += seconds
                    print(f"RATE_WAIT seconds={seconds:.3f}", flush=True)
                    time.sleep(seconds)
                next_page += 1
            except PageFailure:
                raise
    except PageFailure as exc:
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
        failure_path = page_directory / f"failure_page_{exc.observation.page:04d}.json"
        write_json_atomic(
            failure_path,
            envelope_payload(
                protocol=protocol,
                observation=exc.observation,
                schema_version=FAILURE_SCHEMA,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - terminal local failure is evidence
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
        synthetic = RequestObservation(
            page=next_page,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            elapsed_seconds=0.0,
            request_url=request_url(protocol, min(next_page, protocol.maximum_terminal_page)),
            request_headers={
                name.lower(): value for name, value in explicit_headers(protocol).items()
            },
            http_status=None,
            final_url=None,
            response_headers={},
            response_body=b"",
            redirect_count=0,
            error_type=failure_type,
            error_message=failure_message,
        )
        failure_path = page_directory / f"failure_page_{next_page:04d}.json"
        write_json_atomic(
            failure_path,
            envelope_payload(
                protocol=protocol,
                observation=synthetic,
                schema_version=FAILURE_SCHEMA,
            ),
        )
    completed_at = datetime.now(UTC)
    result = build_result(
        protocol=protocol,
        pages=pages,
        started_at=started_at,
        completed_at=completed_at,
        new_request_attempt_count=new_attempts,
        resumed_page_count=resumed_page_count,
        wait_count=wait_count,
        wait_seconds=wait_seconds,
        failure_type=failure_type,
        failure_message=failure_message,
        failure_path=failure_path,
    )
    write_result_atomic(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen S5 GitHub bulk acquisition.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        protocol = load_protocol(args.protocol, args.protocol_audit)
        result = run(protocol=protocol, output_path=args.output)
        print(
            f"{result.decision} {args.output} {result.result_evidence_hash} "
            f"pages={result.successful_request_count} records={result.raw_record_count} "
            f"cohort={result.cohort_record_count} requests={result.logical_request_attempt_count} "
            "market_values=0 returns=0 orders=0",
            flush=True,
        )
        return 0 if result.decision == S5_GITHUB_BULK_PASS else 1
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
