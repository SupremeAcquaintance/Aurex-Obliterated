# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    S5_GITHUB_BULK_PASS,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_resume import (
    S5_GITHUB_BULK_RESUME_NEXT,
    S5GitHubBulkContiguousResumeAmendmentAuditV3,
    S5GitHubBulkContiguousResumeAmendmentV3,
    S5GitHubBulkSuspensionFailureAuditV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base
from scripts.run_s1_btc_source_acquisition import file_sha256
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v2 import (
    CORRECTION_MODULE_PATH,
    SCRIPT_PATH as RUNNER_V2_PATH,
    perform_request_v2,
)

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
DEFAULT_SUSPENSION_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_suspension_failure_audit_v2.json"
)
DEFAULT_RESUME_AMENDMENT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.json"
)
DEFAULT_RESUME_AMENDMENT_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_contiguous_resume_amendment_audit_v3.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v3.json")
RESUME_MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_resume.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_github_bulk_acquisition_v3.py")


def runner_contract_hash() -> str:
    paths = (
        base.MODULE_PATH,
        base.SCRIPT_PATH,
        CORRECTION_MODULE_PATH,
        RUNNER_V2_PATH,
        RESUME_MODULE_PATH,
        SCRIPT_PATH,
    )
    return universe_evidence_hash(
        {
            "sources": tuple(
                {"path": path.as_posix(), "file_sha256": file_sha256(PROJECT_ROOT / path)}
                for path in paths
            )
        }
    )


def load_authorization(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    suspension_audit_path: Path,
    amendment_path: Path,
    amendment_audit_path: Path,
) -> tuple[S5GitHubBulkAcquisitionProtocol, S5GitHubBulkContiguousResumeAmendmentV3]:
    protocol = base.load_protocol(protocol_path, protocol_audit_path)
    suspension = S5GitHubBulkSuspensionFailureAuditV2.model_validate_json(
        suspension_audit_path.read_text(encoding="utf-8")
    )
    amendment = S5GitHubBulkContiguousResumeAmendmentV3.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    amendment_audit = S5GitHubBulkContiguousResumeAmendmentAuditV3.model_validate_json(
        amendment_audit_path.read_text(encoding="utf-8")
    )
    sources_match = all(
        file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in amendment.source_bindings
    )
    if not (
        evidence_hash_valid(suspension, "audit_evidence_hash")
        and evidence_hash_valid(amendment, "amendment_evidence_hash")
        and evidence_hash_valid(amendment_audit, "audit_evidence_hash")
        and amendment.suspension_failure_audit_evidence_hash == suspension.audit_evidence_hash
        and amendment.protocol_evidence_hash == protocol.protocol_evidence_hash
        and amendment.next_authorization == S5_GITHUB_BULK_RESUME_NEXT
        and amendment_audit.amendment_file_sha256 == file_sha256(amendment_path)
        and amendment_audit.amendment_evidence_hash == amendment.amendment_evidence_hash
        and amendment_audit.suspension_failure_audit_evidence_hash == suspension.audit_evidence_hash
        and amendment_audit.reconstructed_exactly is True
        and sources_match
    ):
        raise ValueError("S5 GitHub bulk v3 resume authorization changed")
    return protocol, amendment


def build_result_v3(**kwargs: Any) -> S5GitHubBulkResult:
    original = base.runner_contract_hash
    base.runner_contract_hash = runner_contract_hash
    try:
        return base.build_result(**kwargs)
    finally:
        base.runner_contract_hash = original


def run_v3(
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    amendment: S5GitHubBulkContiguousResumeAmendmentV3,
    output_path: Path,
) -> S5GitHubBulkResult:
    if output_path.exists():
        raise ValueError(f"S5 GitHub bulk v3 result already exists: {output_path}")
    page_directory = Path(protocol.raw_page_directory)
    pages, terminal_page = base.load_existing_pages(
        protocol=protocol, page_directory=page_directory
    )
    if not (
        len(pages) >= amendment.preserved_page_last
        and terminal_page == amendment.terminal_page
        and all(binding.page == index for index, (_, binding) in enumerate(pages, start=1))
    ):
        raise ValueError("S5 GitHub bulk v3 preserved page prefix changed")
    prior_v3_pages = len(pages) - amendment.preserved_page_last
    if prior_v3_pages < 0 or prior_v3_pages > amendment.maximum_resume_request_attempts:
        raise ValueError("S5 GitHub bulk v3 prior resume-page count is invalid")
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
            if prior_v3_pages + new_attempts >= amendment.maximum_resume_request_attempts:
                raise ValueError("S5 GitHub bulk v3 exhausted its lifetime resume ceiling")
            if time.monotonic() - run_clock > protocol.maximum_run_seconds:
                raise ValueError("S5 GitHub bulk v3 exceeded the frozen elapsed-time bound")
            observation = perform_request_v2(protocol=protocol, page=next_page)
            new_attempts += 1
            parsed = base.parse_observation(observation=observation, protocol=protocol)
            if next_page < terminal_page and parsed.terminal_page != terminal_page:
                raise base.PageFailure(
                    "GitHub bulk terminal page drifted during v3 acquisition", observation
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
                raise ValueError("GitHub bulk v3 pagination ended before the terminal page")
            if (
                parsed.rate_remaining <= protocol.wait_when_remaining_at_or_below
                and next_page < terminal_page
            ):
                seconds = max(
                    0.0,
                    parsed.rate_reset - time.time() + protocol.reset_safety_seconds,
                )
                if seconds > protocol.maximum_single_wait_seconds:
                    raise ValueError("GitHub bulk v3 rate-limit wait exceeds the frozen bound")
                wait_count += 1
                wait_seconds += seconds
                print(f"RATE_WAIT seconds={seconds:.3f}", flush=True)
                time.sleep(seconds)
            next_page += 1
    except base.PageFailure as exc:
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
        failure_path = page_directory / f"failure_v3_page_{exc.observation.page:04d}.json"
        base.write_json_atomic(
            failure_path,
            base.envelope_payload(
                protocol=protocol,
                observation=exc.observation,
                schema_version="aurex-s5-github-bulk-failure-page-v3",
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
        failure_path = page_directory / f"failure_v3_page_{next_page:04d}.json"
        base.write_json_atomic(
            failure_path,
            base.envelope_payload(
                protocol=protocol,
                observation=synthetic,
                schema_version="aurex-s5-github-bulk-failure-page-v3",
            ),
        )
    completed_at = datetime.now(UTC)
    result = build_result_v3(
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
    parser = argparse.ArgumentParser(description="Resume S5 GitHub bulk acquisition v3.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--suspension-audit", type=Path, default=DEFAULT_SUSPENSION_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_RESUME_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_RESUME_AMENDMENT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        protocol, amendment = load_authorization(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            suspension_audit_path=args.suspension_audit,
            amendment_path=args.amendment,
            amendment_audit_path=args.amendment_audit,
        )
        result = run_v3(protocol=protocol, amendment=amendment, output_path=args.output)
        print(
            f"{result.decision} {args.output} {result.result_evidence_hash} "
            f"pages={result.successful_request_count} records={result.raw_record_count} "
            f"cohort={result.cohort_record_count} resumed_from=118 "
            "market_values=0 returns=0 orders=0",
            flush=True,
        )
        return 0 if result.decision == S5_GITHUB_BULK_PASS else 1
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
