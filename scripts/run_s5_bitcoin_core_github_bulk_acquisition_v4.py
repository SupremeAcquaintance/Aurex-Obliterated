# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
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
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (
    S5_GITHUB_BULK_DRIFT_ADJUDICATION,
    S5_GITHUB_BULK_MONOTONIC_NEXT,
    S5GitHubBulkMonotonicTerminalAmendmentAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentV4,
    S5GitHubBulkTerminalDriftFailureAuditV3,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base
from scripts.audit_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4 import (
    DEFAULT_OUTPUT as DEFAULT_AMENDMENT_AUDIT,
    SCRIPT_PATH as AMENDMENT_AUDITOR_PATH,
    auditor_contract_hash as amendment_auditor_contract_hash,
)
from scripts.audit_s5_bitcoin_core_github_bulk_terminal_drift_failure_v3 import (
    DEFAULT_OUTPUT as DEFAULT_DRIFT_AUDIT,
    SCRIPT_PATH as DRIFT_AUDITOR_PATH,
    auditor_contract_hash as drift_auditor_contract_hash,
    observation_from_failure,
)
from scripts.freeze_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4 import (
    DEFAULT_OUTPUT as DEFAULT_AMENDMENT,
    FAILURE_ARTIFACT_PATH,
    MODULE_PATH as PAGINATION_MODULE_PATH,
    SCRIPT_PATH as AMENDMENT_BUILDER_PATH,
    builder_contract_hash as amendment_builder_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v2 import (
    CORRECTION_MODULE_PATH,
    SCRIPT_PATH as RUNNER_V2_PATH,
    perform_request_v2,
)
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v3 import (
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    RESUME_MODULE_PATH,
    SCRIPT_PATH as RUNNER_V3_PATH,
)

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v4.json")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_github_bulk_acquisition_v4.py")


def runner_contract_hash() -> str:
    paths = (
        base.MODULE_PATH,
        base.SCRIPT_PATH,
        CORRECTION_MODULE_PATH,
        RUNNER_V2_PATH,
        RESUME_MODULE_PATH,
        RUNNER_V3_PATH,
        PAGINATION_MODULE_PATH,
        DRIFT_AUDITOR_PATH,
        AMENDMENT_BUILDER_PATH,
        AMENDMENT_AUDITOR_PATH,
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
    drift_audit_path: Path,
    amendment_path: Path,
    amendment_audit_path: Path,
) -> tuple[
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkMonotonicTerminalAmendmentV4,
    S5GitHubBulkTerminalDriftFailureAuditV3,
]:
    protocol = base.load_protocol(protocol_path, protocol_audit_path)
    drift = S5GitHubBulkTerminalDriftFailureAuditV3.model_validate_json(
        drift_audit_path.read_text(encoding="utf-8")
    )
    amendment = S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    amendment_audit = S5GitHubBulkMonotonicTerminalAmendmentAuditV4.model_validate_json(
        amendment_audit_path.read_text(encoding="utf-8")
    )
    drift_sources_match = all(
        file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in drift.source_bindings
    )
    amendment_sources_match = all(
        file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in amendment.source_bindings
    )
    if not (
        evidence_hash_valid(drift, "audit_evidence_hash")
        and evidence_hash_valid(amendment, "amendment_evidence_hash")
        and evidence_hash_valid(amendment_audit, "audit_evidence_hash")
        and drift.auditor_contract_hash == drift_auditor_contract_hash()
        and drift_sources_match
        and amendment_sources_match
        and drift.adjudication == S5_GITHUB_BULK_DRIFT_ADJUDICATION
        and drift.protocol_evidence_hash == protocol.protocol_evidence_hash
        and amendment.protocol_evidence_hash == protocol.protocol_evidence_hash
        and amendment.terminal_drift_audit_evidence_hash == drift.audit_evidence_hash
        and amendment.next_authorization == S5_GITHUB_BULK_MONOTONIC_NEXT
        and amendment.builder_contract_hash == amendment_builder_contract_hash()
        and amendment_audit.amendment_file_sha256 == file_sha256(amendment_path)
        and amendment_audit.amendment_evidence_hash == amendment.amendment_evidence_hash
        and amendment_audit.terminal_drift_audit_evidence_hash == drift.audit_evidence_hash
        and amendment_audit.builder_contract_hash == amendment.builder_contract_hash
        and amendment_audit.auditor_contract_hash == amendment_auditor_contract_hash()
        and amendment_audit.reconstructed_exactly is True
        and amendment_audit.candidate_page_reverified is True
    ):
        raise ValueError("S5 GitHub bulk v4 authorization changed")
    return protocol, amendment, drift


def load_monotonic_pages(
    *, protocol: S5GitHubBulkAcquisitionProtocol, page_directory: Path
) -> tuple[list[tuple[Path, base.ParsedPage]], int | None]:
    if not page_directory.exists():
        return [], None
    files = sorted(
        path for path in page_directory.iterdir() if base.PAGE_FILE_RE.fullmatch(path.name)
    )
    expected_names = [
        protocol.page_file_pattern.format(page=index) for index in range(1, len(files) + 1)
    ]
    if [path.name for path in files] != expected_names:
        raise ValueError("Existing S5 GitHub bulk v4 pages are not contiguous")
    pages: list[tuple[Path, base.ParsedPage]] = []
    terminal_page = None
    for index, path in enumerate(files):
        observation = base.observation_from_envelope(path=path, protocol=protocol)
        parsed = base.parse_observation(observation=observation, protocol=protocol)
        if terminal_page is not None and parsed.terminal_page < terminal_page:
            raise ValueError("Existing S5 GitHub bulk v4 terminal page regressed")
        if parsed.terminal_page > protocol.maximum_terminal_page:
            raise ValueError("Existing S5 GitHub bulk v4 terminal page exceeds bound")
        if index < len(files) - 1 and parsed.next_page != parsed.page + 1:
            raise ValueError("Existing S5 GitHub bulk v4 page ended before its successor")
        terminal_page = parsed.terminal_page
        pages.append((path, parsed))
    if terminal_page is not None and len(pages) > terminal_page:
        raise ValueError("Existing S5 GitHub bulk v4 pages exceed terminal page")
    return pages, terminal_page


def promote_page_118(
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    amendment: S5GitHubBulkMonotonicTerminalAmendmentV4,
    page_directory: Path,
) -> tuple[list[tuple[Path, base.ParsedPage]], int]:
    target = page_directory / protocol.page_file_pattern.format(page=118)
    source = observation_from_failure(
        FAILURE_ARTIFACT_PATH, protocol_hash=protocol.protocol_evidence_hash
    )
    if not target.exists():
        prefix, terminal = base.load_existing_pages(
            protocol=protocol, page_directory=page_directory
        )
        if len(prefix) != 117 or terminal != 244:
            raise ValueError("S5 GitHub bulk v4 promotion prefix changed")
        base.write_json_atomic(
            target,
            base.envelope_payload(protocol=protocol, observation=source),
        )
    promoted = base.observation_from_envelope(path=target, protocol=protocol)
    parsed = base.parse_observation(observation=promoted, protocol=protocol)
    if not (
        promoted == source
        and parsed.page == amendment.locally_promoted_page
        and parsed.terminal_page == amendment.observed_terminal_page
        and parsed.next_page == amendment.resume_page
        and len(parsed.records) == protocol.records_per_page
    ):
        raise ValueError("S5 GitHub bulk v4 promoted page differs from preserved response")
    pages, terminal_page = load_monotonic_pages(
        protocol=protocol, page_directory=page_directory
    )
    if terminal_page is None or len(pages) < amendment.preserved_page_last_after_promotion:
        raise ValueError("S5 GitHub bulk v4 promoted prefix is incomplete")
    return pages, terminal_page


def normalize_terminal_pages(
    pages: list[tuple[Path, base.ParsedPage]], *, terminal_page: int
) -> list[tuple[Path, base.ParsedPage]]:
    return [
        (path, replace(parsed, terminal_page=terminal_page)) for path, parsed in pages
    ]


def build_result_v4(**kwargs: Any) -> S5GitHubBulkResult:
    original = base.runner_contract_hash
    base.runner_contract_hash = runner_contract_hash
    try:
        return base.build_result(**kwargs)
    finally:
        base.runner_contract_hash = original


def run_v4(
    *,
    protocol: S5GitHubBulkAcquisitionProtocol,
    amendment: S5GitHubBulkMonotonicTerminalAmendmentV4,
    output_path: Path,
) -> S5GitHubBulkResult:
    if output_path.exists():
        raise ValueError(f"S5 GitHub bulk v4 result already exists: {output_path}")
    page_directory = Path(protocol.raw_page_directory)
    if list(page_directory.glob("failure_v4_page_*.json")):
        raise ValueError("S5 GitHub bulk v4 already has an unaudited failure artifact")
    pages, terminal_page = promote_page_118(
        protocol=protocol,
        amendment=amendment,
        page_directory=page_directory,
    )
    prior_v4_pages = len(pages) - amendment.preserved_page_last_after_promotion
    if not 0 <= prior_v4_pages <= amendment.maximum_v4_request_attempts:
        raise ValueError("S5 GitHub bulk v4 prior page count is invalid")
    if terminal_page > amendment.maximum_completable_terminal_page:
        raise ValueError("S5 GitHub bulk v4 existing terminal exceeds completion budget")
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
        while next_page <= terminal_page:
            if prior_v4_pages + new_attempts >= amendment.maximum_v4_request_attempts:
                raise ValueError("S5 GitHub bulk v4 exhausted its lifetime request ceiling")
            if time.monotonic() - run_clock > protocol.maximum_run_seconds:
                raise ValueError("S5 GitHub bulk v4 exceeded the frozen elapsed-time bound")
            observation = perform_request_v2(protocol=protocol, page=next_page)
            new_attempts += 1
            parsed = base.parse_observation(observation=observation, protocol=protocol)
            if parsed.terminal_page < terminal_page:
                raise base.PageFailure(
                    "GitHub bulk terminal page regressed during v4 acquisition", observation
                )
            if parsed.terminal_page > amendment.maximum_completable_terminal_page:
                raise base.PageFailure(
                    "GitHub bulk terminal page exceeds the v4 completion budget", observation
                )
            terminal_page = parsed.terminal_page
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
                raise ValueError("GitHub bulk v4 pagination ended before the terminal page")
            if (
                parsed.rate_remaining <= protocol.wait_when_remaining_at_or_below
                and next_page < terminal_page
            ):
                seconds = max(
                    0.0,
                    parsed.rate_reset - time.time() + protocol.reset_safety_seconds,
                )
                if seconds > protocol.maximum_single_wait_seconds:
                    raise ValueError("GitHub bulk v4 rate-limit wait exceeds the frozen bound")
                wait_count += 1
                wait_seconds += seconds
                print(f"RATE_WAIT seconds={seconds:.3f}", flush=True)
                time.sleep(seconds)
            next_page += 1
    except base.PageFailure as exc:
        failure_type = type(exc).__name__
        failure_message = str(exc)[:2000]
        failure_path = page_directory / f"failure_v4_page_{exc.observation.page:04d}.json"
        base.write_json_atomic(
            failure_path,
            base.envelope_payload(
                protocol=protocol,
                observation=exc.observation,
                schema_version="aurex-s5-github-bulk-failure-page-v4",
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
            request_url=base.request_url(
                protocol, min(next_page, protocol.maximum_terminal_page)
            ),
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
        failure_path = page_directory / f"failure_v4_page_{next_page:04d}.json"
        base.write_json_atomic(
            failure_path,
            base.envelope_payload(
                protocol=protocol,
                observation=synthetic,
                schema_version="aurex-s5-github-bulk-failure-page-v4",
            ),
        )
    completed_at = datetime.now(UTC)
    normalized_pages = normalize_terminal_pages(pages, terminal_page=terminal_page)
    result = build_result_v4(
        protocol=protocol,
        pages=normalized_pages,
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
    parser = argparse.ArgumentParser(description="Resume S5 GitHub bulk acquisition v4.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--drift-audit", type=Path, default=DEFAULT_DRIFT_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        protocol, amendment, _ = load_authorization(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            drift_audit_path=args.drift_audit,
            amendment_path=args.amendment,
            amendment_audit_path=args.amendment_audit,
        )
        result = run_v4(protocol=protocol, amendment=amendment, output_path=args.output)
        print(
            f"{result.decision} {args.output} {result.result_evidence_hash} "
            f"pages={result.successful_request_count} records={result.raw_record_count} "
            f"cohort={result.cohort_record_count} resumed_from=119 "
            "market_values=0 returns=0 orders=0",
            flush=True,
        )
        return 0 if result.decision == S5_GITHUB_BULK_PASS else 1
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
