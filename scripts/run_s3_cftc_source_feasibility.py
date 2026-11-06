from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_source_feasibility import (  # noqa: E402
    S3_FEASIBILITY_GATE_IDS,
    S3_FEASIBILITY_NONE,
    S3_FEASIBILITY_STOP,
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    S3FeasibilityGateResult,
    S3MetadataAttempt,
    S3MetadataEndpointSpec,
    build_hashed,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s3_cftc_source_feasibility_result_v1.json")
DEFAULT_RESPONSE_DIR = Path("data/evidence/s3_cftc_metadata_v1")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def runner_contract_hash() -> str:
    path = Path(__file__).resolve()
    return universe_evidence_hash(
        {
            "runner_path": path.relative_to(PROJECT_ROOT).as_posix(),
            "runner_sha256": file_sha256(path),
        }
    )


def normalized_html_text(body: bytes) -> str:
    decoded = body.decode("utf-8", errors="strict")
    without_scripts = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        " ",
        decoded,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return " ".join(html.unescape(without_tags).split())


def fetch_metadata(
    endpoint: S3MetadataEndpointSpec,
    *,
    timeout: int,
    maximum_bytes: int,
) -> tuple[bytes | None, int, str]:
    request = Request(
        endpoint.url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Aurex-S3-CFTC-Feasibility/1",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > maximum_bytes:
                return None, int(response.status), "RESPONSE_TOO_LARGE"
            body = response.read(maximum_bytes + 1)
            if len(body) > maximum_bytes:
                return None, int(response.status), "RESPONSE_TOO_LARGE"
            normalized_html_text(body)
            return body, int(response.status), "NONE"
    except UnicodeDecodeError:
        return None, 0, "INVALID_TEXT"
    except HTTPError as exc:
        return None, int(exc.code), "HTTP_ERROR"
    except (TimeoutError, URLError, OSError):
        return None, 0, "NETWORK_ERROR"


def attempt_from_body(
    endpoint: S3MetadataEndpointSpec,
    *,
    requested_at: datetime,
    body: bytes | None,
    http_status: int,
    error_class: str,
    response_path: Path,
) -> S3MetadataAttempt:
    authority = endpoint.url.startswith("https://www.cftc.gov/")
    if body is None:
        return S3MetadataAttempt(
            endpoint_id=endpoint.endpoint_id,
            requested_at=requested_at,
            http_status=http_status,
            response_bytes=0,
            response_sha256=None,
            response_path=None,
            official_authority_matched=authority,
            matched_text_tokens=(),
            request_succeeded=False,
            error_class=error_class,
        )
    try:
        text = normalized_html_text(body)
    except UnicodeDecodeError:
        return S3MetadataAttempt(
            endpoint_id=endpoint.endpoint_id,
            requested_at=requested_at,
            http_status=http_status,
            response_bytes=0,
            response_sha256=None,
            response_path=None,
            official_authority_matched=authority,
            matched_text_tokens=(),
            request_succeeded=False,
            error_class="INVALID_TEXT",
        )
    matched = tuple(sorted(token for token in endpoint.required_text_tokens if token in text))
    return S3MetadataAttempt(
        endpoint_id=endpoint.endpoint_id,
        requested_at=requested_at,
        http_status=http_status,
        response_bytes=len(body),
        response_sha256=sha256(body).hexdigest(),
        response_path=response_path.as_posix(),
        official_authority_matched=authority,
        matched_text_tokens=matched,
        request_succeeded=http_status == 200 and authority and error_class == "NONE",
        error_class=error_class,
    )


def make_attempt(
    endpoint: S3MetadataEndpointSpec,
    *,
    requested_at: datetime,
    response_dir: Path,
    timeout: int,
    maximum_bytes: int,
) -> tuple[S3MetadataAttempt, bytes | None]:
    body, http_status, error_class = fetch_metadata(
        endpoint,
        timeout=timeout,
        maximum_bytes=maximum_bytes,
    )
    response_path = response_dir / f"{endpoint.endpoint_id.lower()}.html"
    attempt = attempt_from_body(
        endpoint,
        requested_at=requested_at,
        body=body,
        http_status=http_status,
        error_class=error_class,
        response_path=response_path,
    )
    return attempt, body


def gate(gate_id: str, passed: bool, detail: str) -> S3FeasibilityGateResult:
    return S3FeasibilityGateResult(
        gate_id=gate_id,
        status="PASS" if passed else "FAIL",
        detail=detail,
    )


def build_result(
    *,
    generated_at: datetime,
    protocol: S3CftcSourceFeasibilityProtocol,
    protocol_path: Path,
    protocol_audit: S3CftcSourceFeasibilityProtocolAudit,
    protocol_audit_path: Path,
    attempts: tuple[S3MetadataAttempt, ...],
) -> S3CftcSourceFeasibilityResult:
    endpoint_specs = {item.endpoint_id: item for item in protocol.metadata_endpoints}
    attempt_map = {item.endpoint_id: item for item in attempts}
    endpoints_available = len(attempts) == 3 and all(
        item.request_succeeded
        and set(item.matched_text_tokens)
        == set(endpoint_specs[item.endpoint_id].required_text_tokens)
        for item in attempts
    )
    official_authority = len(attempts) == 3 and all(
        item.official_authority_matched for item in attempts
    )
    viewable = attempt_map["HISTORICAL_VIEWABLE_INDEX"]
    faq = attempt_map["COT_FAQ"]
    announcements = attempt_map["HISTORICAL_SPECIAL_ANNOUNCEMENTS"]
    report_date_distinct = (
        "Dates indicate the report date and not the release date"
        in viewable.matched_text_tokens
    )
    faq_declares_history_unavailable = {
        "Is there a list of historical release dates?",
        "There is not a list of historical release dates",
        "only available release dates are for the 13 months",
    }.issubset(set(faq.matched_text_tokens))
    historical_release_list = False
    per_report_actual_timestamp = False
    delay_metadata = {
        "Historical Special Announcements",
        "New Publish Date",
        "Original Publish Date",
    }.issubset(set(announcements.matched_text_tokens))
    revision_ledger_complete = False
    zero_dollar_access = endpoints_available
    reuse_rights_explicit = False
    zero_values = all(
        item.target_position_rows_parsed == 0
        and item.target_position_values_read == 0
        for item in attempts
    )
    gate_results = (
        gate(
            "METADATA_ENDPOINTS_AVAILABLE",
            endpoints_available,
            "All three bounded official metadata pages returned and matched frozen text."
            if endpoints_available
            else "One or more bounded official metadata pages failed or changed.",
        ),
        gate(
            "OFFICIAL_CFTC_AUTHORITY",
            official_authority,
            "Every request remained on HTTPS CFTC authority."
            if official_authority
            else "A request escaped or could not prove official CFTC authority.",
        ),
        gate(
            "REPORT_DATE_DISTINCT_FROM_RELEASE_DATE",
            report_date_distinct,
            "CFTC explicitly states that historical dates are report dates, not release dates."
            if report_date_distinct
            else "The required report-date versus release-date warning was unavailable.",
        ),
        gate(
            "HISTORICAL_RELEASE_DATE_COVERAGE_2022_2024",
            historical_release_list,
            "A complete actual release-date list covers every 2022-2024 report."
            if historical_release_list
            else (
                "CFTC states no historical release-date list exists and only 13 months "
                "are available."
                if faq_declares_history_unavailable
                else "No complete official 2022-2024 release-date list was proven."
            ),
        ),
        gate(
            "PER_REPORT_ACTUAL_RELEASE_TIMESTAMP_AVAILABLE",
            per_report_actual_timestamp,
            "Every development report has an actual publication timestamp."
            if per_report_actual_timestamp
            else "No per-report actual publication timestamp field or ledger was proven.",
        ),
        gate(
            "DELAY_AND_BACKLOG_METADATA_AVAILABLE",
            delay_metadata,
            "Official announcements expose original and revised publication dates."
            if delay_metadata
            else "Delay and backlog publication metadata were not reconstructable.",
        ),
        gate(
            "REVISION_IDENTITY_LEDGER_COMPLETE",
            revision_ledger_complete,
            "An exhaustive per-report correction and revision ledger is available."
            if revision_ledger_complete
            else "No exhaustive per-report correction and revision ledger was proven.",
        ),
        gate(
            "ZERO_DOLLAR_PUBLIC_METADATA_ACCESS",
            zero_dollar_access,
            "The bounded metadata pages were read without credentials or payment."
            if zero_dollar_access
            else "Zero-dollar public metadata access was not established.",
        ),
        gate(
            "REUSE_RIGHTS_EXPLICIT",
            reuse_rights_explicit,
            "Explicit reuse rights cover the required evidence artifacts."
            if reuse_rights_explicit
            else "The inspected pages did not explicitly establish required reuse rights.",
        ),
        gate(
            "ZERO_TARGET_POSITION_OR_MARKET_VALUES_ACCESSED",
            zero_values,
            "The run parsed zero target position rows and read zero target or market values.",
        ),
    )
    if tuple(item.gate_id for item in gate_results) != S3_FEASIBILITY_GATE_IDS:
        raise ValueError("S3 feasibility runner gate order changed")
    blockers = tuple(
        sorted(
            {
                item.gate_id.lower()
                for item in gate_results
                if item.status == "FAIL"
            }
        )
    )
    return build_hashed(
        S3CftcSourceFeasibilityResult,
        "result_evidence_hash",
        {
            "generated_at": generated_at,
            "protocol_file_sha256": file_sha256(protocol_path),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_file_sha256": file_sha256(protocol_audit_path),
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
            "runner_contract_hash": runner_contract_hash(),
            "metadata_attempts": attempts,
            "gate_results": gate_results,
            "passed_gate_count": sum(item.status == "PASS" for item in gate_results),
            "failed_gate_count": sum(item.status == "FAIL" for item in gate_results),
            "historical_release_date_list_available": historical_release_list,
            "per_report_actual_release_timestamp_available": per_report_actual_timestamp,
            "delay_and_backlog_metadata_available": delay_metadata,
            "revision_identity_ledger_complete": revision_ledger_complete,
            "zero_dollar_public_access_observed": zero_dollar_access,
            "reuse_rights_explicit": reuse_rights_explicit,
            "blockers": blockers,
            "decision": S3_FEASIBILITY_STOP,
            "next_authorization": S3_FEASIBILITY_NONE,
            "limitations": tuple(
                sorted(
                    (
                        "CFTC explicitly distinguishes report dates from release dates.",
                        "CFTC states that a complete historical release-date list is unavailable.",
                        "HTTP availability does not prove historical point-in-time identity.",
                        "No complete per-report timestamp or revision ledger was proven.",
                        "No CFTC target position row or value was parsed.",
                        "No BTC market value, parameter, return, candidate, or order was created.",
                        "S3 cannot be backtested causally under the frozen source requirements.",
                        "The metadata result establishes infeasibility, not profitability.",
                    )
                )
            ),
        },
    )


def write_atomic(path: Path, body: bytes) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S3 feasibility artifact: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 feasibility transaction exists: {temporary}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(body)
    temporary.replace(path)


def run(args) -> S3CftcSourceFeasibilityResult:
    if args.output.exists():
        raise ValueError(f"S3 feasibility result exists: {args.output}")
    protocol = S3CftcSourceFeasibilityProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    if (
        file_sha256(args.protocol) != protocol_audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.next_authorization
        != "RUN_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_ONCE"
        or protocol_audit.reconstructed_exactly is not True
    ):
        raise ValueError("S3 feasibility protocol lineage changed")
    expected_paths = tuple(
        args.response_dir / f"{item.endpoint_id.lower()}.html"
        for item in protocol.metadata_endpoints
    )
    if any(path.exists() for path in expected_paths):
        raise ValueError("S3 feasibility response artifact already exists")

    attempts = []
    pending_responses = []
    for endpoint in protocol.metadata_endpoints:
        attempt, body = make_attempt(
            endpoint,
            requested_at=datetime.now(UTC),
            response_dir=args.response_dir,
            timeout=protocol.request_timeout_seconds,
            maximum_bytes=protocol.maximum_response_bytes_each,
        )
        attempts.append(attempt)
        if body is not None and attempt.response_path is not None:
            pending_responses.append((Path(attempt.response_path), body))
    result = build_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        protocol_path=args.protocol,
        protocol_audit=protocol_audit,
        protocol_audit_path=args.protocol_audit,
        attempts=tuple(attempts),
    )
    for path, body in pending_responses:
        write_atomic(path, body)
    serialized = (result.model_dump_json(indent=2) + "\n").encode("utf-8")
    write_atomic(args.output, serialized)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"pass={result.passed_gate_count} fail={result.failed_gate_count} "
        f"decision={result.decision} cftc_values=0 market_values=0 orders=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Run S3 CFTC metadata feasibility once.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--response-dir", type=Path, default=DEFAULT_RESPONSE_DIR)
    return parser.parse_args()


def main() -> int:
    try:
        run(parse_args())
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
