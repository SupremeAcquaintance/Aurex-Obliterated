from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5_GITHUB_BULK_PASS,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_correction import (  # noqa: E402
    S5_GITHUB_BULK_AMENDMENT_NEXT,
    S5GitHubBulkFailureAudit,
    S5GitHubBulkResponseHandlingAmendmentAuditV2,
    S5GitHubBulkResponseHandlingAmendmentV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
DEFAULT_FAILURE_AUDIT = Path("data/evidence/s5_bitcoin_core_github_bulk_failure_audit_v1.json")
DEFAULT_AMENDMENT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_response_handling_amendment_v2.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_response_handling_amendment_audit_v2.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v2.json")
CORRECTION_MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_correction.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_github_bulk_acquisition_v2.py")


def runner_contract_hash() -> str:
    paths = (
        base.MODULE_PATH,
        base.SCRIPT_PATH,
        CORRECTION_MODULE_PATH,
        SCRIPT_PATH,
    )
    return universe_evidence_hash(
        {
            "sources": tuple(
                {
                    "path": path.as_posix(),
                    "file_sha256": file_sha256(PROJECT_ROOT / path),
                }
                for path in paths
            )
        }
    )


def load_authorization(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    failure_audit_path: Path,
    amendment_path: Path,
    amendment_audit_path: Path,
) -> tuple[S5GitHubBulkAcquisitionProtocol, S5GitHubBulkResponseHandlingAmendmentV2]:
    protocol = base.load_protocol(protocol_path, protocol_audit_path)
    failure_audit = S5GitHubBulkFailureAudit.model_validate_json(
        failure_audit_path.read_text(encoding="utf-8")
    )
    amendment = S5GitHubBulkResponseHandlingAmendmentV2.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    amendment_audit = S5GitHubBulkResponseHandlingAmendmentAuditV2.model_validate_json(
        amendment_audit_path.read_text(encoding="utf-8")
    )
    sources_match = all(
        file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in amendment.source_bindings
    )
    if not (
        evidence_hash_valid(failure_audit, "audit_evidence_hash")
        and evidence_hash_valid(amendment, "amendment_evidence_hash")
        and evidence_hash_valid(amendment_audit, "audit_evidence_hash")
        and amendment.failure_audit_evidence_hash == failure_audit.audit_evidence_hash
        and amendment.protocol_evidence_hash == protocol.protocol_evidence_hash
        and amendment.next_authorization == S5_GITHUB_BULK_AMENDMENT_NEXT
        and amendment_audit.amendment_file_sha256 == file_sha256(amendment_path)
        and amendment_audit.amendment_evidence_hash == amendment.amendment_evidence_hash
        and amendment_audit.failure_audit_evidence_hash == failure_audit.audit_evidence_hash
        and amendment_audit.reconstructed_exactly is True
        and sources_match
    ):
        raise ValueError("S5 GitHub bulk v2 amendment, audit, or lineage changed")
    return protocol, amendment


def capture_streamed_response(
    response: httpx.Response, *, protocol: S5GitHubBulkAcquisitionProtocol
) -> tuple[dict[str, str | None], bytes]:
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
    return response_headers, b"".join(chunks)


def perform_request_v2(
    *, protocol: S5GitHubBulkAcquisitionProtocol, page: int
) -> base.RequestObservation:
    url = base.request_url(protocol, page)
    headers = base.explicit_headers(protocol)
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
            with client.stream(protocol.method, url, headers=headers) as response:
                status = response.status_code
                final_url = str(response.url)
                redirects = len(response.history)
                response_headers, body = capture_streamed_response(response, protocol=protocol)
    except Exception as exc:  # noqa: BLE001 - the exact failure is evidence
        error_type = type(exc).__name__
        error_message = str(exc)[:2000]
    completed_at = datetime.now(UTC)
    return base.RequestObservation(
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


def build_result_v2(**kwargs: Any) -> S5GitHubBulkResult:
    original = base.runner_contract_hash
    base.runner_contract_hash = runner_contract_hash
    try:
        return base.build_result(**kwargs)
    finally:
        base.runner_contract_hash = original


def run_v2(
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    amendment: S5GitHubBulkResponseHandlingAmendmentV2,
    output_path: Path,
) -> S5GitHubBulkResult:
    if output_path.exists():
        raise ValueError(f"S5 GitHub bulk v2 result already exists: {output_path}")
    page_directory = Path(protocol.raw_page_directory)
    pages, terminal_page = base.load_existing_pages(
        protocol=protocol, page_directory=page_directory
    )
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
            if new_attempts >= amendment.maximum_corrected_run_attempts:
                raise ValueError("S5 GitHub bulk v2 exhausted its corrected request ceiling")
            if time.monotonic() - run_clock > protocol.maximum_run_seconds:
                raise ValueError("S5 GitHub bulk v2 exceeded the frozen elapsed-time bound")
            observation = perform_request_v2(protocol=protocol, page=next_page)
            new_attempts += 1
            parsed = base.parse_observation(observation=observation, protocol=protocol)
            if terminal_page is None:
                terminal_page = parsed.terminal_page
            elif next_page < terminal_page and parsed.terminal_page != terminal_page:
                raise base.PageFailure(
                    "GitHub bulk terminal page drifted during v2 acquisition", observation
                )
            page_path = page_directory / protocol.page_file_pattern.format(page=next_page)
            base.write_json_atomic(
                page_path,
                base.envelope_payload(protocol=protocol, observation=observation),
            )
            pages.append((page_path, parsed))
            print(
                f"PAGE {next_page}/{terminal_page} records={len(parsed.records)} "
                f"remaining={parsed.rate_remaining} bytes={parsed.response_byte_count}",
                flush=True,
            )
            if parsed.next_page is None and next_page != terminal_page:
                raise ValueError("GitHub bulk v2 pagination ended before the terminal page")
            if (
                parsed.rate_remaining <= protocol.wait_when_remaining_at_or_below
                and next_page < terminal_page
            ):
                seconds = max(
                    0.0,
                    parsed.rate_reset - time.time() + protocol.reset_safety_seconds,
                )
                if seconds > protocol.maximum_single_wait_seconds:
                    raise ValueError("GitHub bulk v2 rate-limit wait exceeds the frozen bound")
                wait_count += 1
                wait_seconds += seconds
                print(f"RATE_WAIT seconds={seconds:.3f}", flush=True)
                time.sleep(seconds)
            next_page += 1
    except base.PageFailure as exc:
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
        failure_path = page_directory / f"failure_v2_page_{exc.observation.page:04d}.json"
        base.write_json_atomic(
            failure_path,
            base.envelope_payload(
                protocol=protocol,
                observation=exc.observation,
                schema_version="aurex-s5-github-bulk-failure-page-v2",
            ),
        )
    except Exception as exc:  # noqa: BLE001 - terminal local failure is evidence
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
        synthetic = base.RequestObservation(
            page=next_page,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            elapsed_seconds=0.0,
            request_url=base.request_url(protocol, min(next_page, protocol.maximum_terminal_page)),
            request_headers={
                name.lower(): value for name, value in base.explicit_headers(protocol).items()
            },
            http_status=None,
            final_url=None,
            response_headers={},
            response_body=b"",
            redirect_count=0,
            error_type=failure_type,
            error_message=failure_message,
        )
        failure_path = page_directory / f"failure_v2_page_{next_page:04d}.json"
        base.write_json_atomic(
            failure_path,
            base.envelope_payload(
                protocol=protocol,
                observation=synthetic,
                schema_version="aurex-s5-github-bulk-failure-page-v2",
            ),
        )
    completed_at = datetime.now(UTC)
    result = build_result_v2(
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
    base.write_result_atomic(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run corrected S5 GitHub bulk acquisition v2.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--failure-audit", type=Path, default=DEFAULT_FAILURE_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        protocol, amendment = load_authorization(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            failure_audit_path=args.failure_audit,
            amendment_path=args.amendment,
            amendment_audit_path=args.amendment_audit,
        )
        result = run_v2(protocol=protocol, amendment=amendment, output_path=args.output)
        print(
            f"{result.decision} {args.output} {result.result_evidence_hash} "
            f"pages={result.successful_request_count} records={result.raw_record_count} "
            f"cohort={result.cohort_record_count} corrected_requests="
            f"{result.logical_request_attempt_count} market_values=0 returns=0 orders=0",
            flush=True,
        )
        return 0 if result.decision == S5_GITHUB_BULK_PASS else 1
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
