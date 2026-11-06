# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    S5_GITHUB_BULK_NEXT,
    S5_GITHUB_BULK_PASS,
    S5GitHubBulkResult,
    evidence_hash_valid as bulk_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (
    S5GitHubBulkFinalResultAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentAuditV4,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base
from scripts.audit_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4 import (
    DEFAULT_OUTPUT as DEFAULT_AMENDMENT_AUDIT,
)
from scripts.audit_s5_bitcoin_core_github_bulk_terminal_drift_failure_v3 import (
    DEFAULT_OUTPUT as DEFAULT_DRIFT_AUDIT,
)
from scripts.freeze_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4 import (
    DEFAULT_OUTPUT as DEFAULT_AMENDMENT,
)
from scripts.run_s1_btc_source_acquisition import file_sha256
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v3 import (
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
)
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v4 import (
    DEFAULT_OUTPUT as DEFAULT_RESULT,
    SCRIPT_PATH as RUNNER_V4_PATH,
    build_result_v4,
    load_authorization,
    load_monotonic_pages,
    normalize_terminal_pages,
    runner_contract_hash,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_final_result_audit_v4.json"
)
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_final_result_v4.py")
EXPECTED_FAILURE_FILES = (
    Path("data/evidence/s5_github_pull_metadata_bulk_v1/failure_page_0001.json"),
    Path("data/evidence/s5_github_pull_metadata_bulk_v1/failure_v2_page_0118.json"),
    Path("data/evidence/s5_github_pull_metadata_bulk_v1/failure_v3_page_0118.json"),
)
PRIOR_RESULT_FILES = (
    Path("data/evidence/s5_bitcoin_core_github_bulk_result_v1.json"),
    Path("data/evidence/s5_bitcoin_core_github_bulk_result_v2.json"),
    Path("data/evidence/s5_bitcoin_core_github_bulk_result_v3.json"),
)


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "runner_path": RUNNER_V4_PATH.as_posix(),
            "runner_sha256": file_sha256(PROJECT_ROOT / RUNNER_V4_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def verify_historical_failures(page_directory: Path) -> None:
    observed = tuple(sorted(page_directory.glob("failure*.json")))
    expected = tuple(sorted(EXPECTED_FAILURE_FILES))
    if observed != expected:
        raise ValueError("S5 GitHub bulk failure-artifact set changed")
    for result_path, failure_path in zip(
        PRIOR_RESULT_FILES, EXPECTED_FAILURE_FILES, strict=True
    ):
        result = S5GitHubBulkResult.model_validate_json(
            result_path.read_text(encoding="utf-8")
        )
        if not (
            bulk_evidence_hash_valid(result, "result_evidence_hash")
            and result.failure_artifact_path == failure_path.as_posix()
            and result.failure_artifact_sha256 == file_sha256(failure_path)
        ):
            raise ValueError("S5 GitHub bulk historical failure lineage changed")


def reconstruct(
    result_path: Path,
) -> tuple[S5GitHubBulkResult, str, str]:
    protocol, amendment, _ = load_authorization(
        protocol_path=DEFAULT_PROTOCOL,
        protocol_audit_path=DEFAULT_PROTOCOL_AUDIT,
        drift_audit_path=DEFAULT_DRIFT_AUDIT,
        amendment_path=DEFAULT_AMENDMENT,
        amendment_audit_path=DEFAULT_AMENDMENT_AUDIT,
    )
    amendment_audit = S5GitHubBulkMonotonicTerminalAmendmentAuditV4.model_validate_json(
        DEFAULT_AMENDMENT_AUDIT.read_text(encoding="utf-8")
    )
    result = S5GitHubBulkResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if not (
        bulk_evidence_hash_valid(result, "result_evidence_hash")
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.runner_contract_hash == runner_contract_hash()
        and result.decision == S5_GITHUB_BULK_PASS
        and result.next_authorization == S5_GITHUB_BULK_NEXT
        and result.failed_gate_count == 0
        and 245 <= result.successful_request_count <= 299
        and result.terminal_page_count == result.successful_request_count
        and result.resumed_page_count >= 118
        and result.logical_request_attempt_count == result.successful_request_count
        and result.failure_artifact_path is None
        and result.failure_artifact_sha256 is None
    ):
        raise ValueError("S5 GitHub bulk v4 result is not an auditable PASS")
    page_directory = Path(result.raw_page_directory)
    verify_historical_failures(page_directory)
    pages, terminal_page = load_monotonic_pages(
        protocol=protocol, page_directory=page_directory
    )
    if terminal_page != len(pages) or not 245 <= len(pages) <= 299:
        raise ValueError("S5 GitHub bulk v4 terminal page count changed")
    normalized = normalize_terminal_pages(pages, terminal_page=terminal_page)
    bindings = tuple(base.page_binding(path=path, parsed=parsed) for path, parsed in pages)
    if bindings != result.page_bindings:
        raise ValueError("S5 GitHub bulk v4 raw page manifest changed")
    reconstructed = build_result_v4(
        protocol=protocol,
        pages=normalized,
        started_at=result.started_at,
        completed_at=result.completed_at,
        new_request_attempt_count=result.new_request_attempt_count,
        resumed_page_count=result.resumed_page_count,
        wait_count=result.rate_limit_wait_count,
        wait_seconds=result.rate_limit_wait_seconds,
    )
    if reconstructed != result:
        raise ValueError("S5 GitHub bulk v4 result differs from full reconstruction")
    return result, amendment.amendment_evidence_hash, amendment_audit.audit_evidence_hash


def build_audit(*, result_path: Path, audited_at: datetime) -> S5GitHubBulkFinalResultAuditV4:
    result, amendment_hash, amendment_audit_hash = reconstruct(result_path)
    corrected_v4_requests = result.successful_request_count - 118
    total_requests = 1 + 117 + 1 + corrected_v4_requests
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "amendment_evidence_hash": amendment_hash,
        "amendment_audit_evidence_hash": amendment_audit_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "corrected_v4_request_attempt_count": corrected_v4_requests,
        "total_request_attempt_count": total_requests,
        "page_count": result.successful_request_count,
        "raw_record_count": result.raw_record_count,
        "cohort_record_count": result.cohort_record_count,
        "post_cutoff_record_count": result.post_cutoff_record_count,
    }
    provisional = S5GitHubBulkFinalResultAuditV4.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkFinalResultAuditV4.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkFinalResultAuditV4) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk v4 result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk v4 result-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkFinalResultAuditV4.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub bulk v4 result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final S5 GitHub bulk result v4.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkFinalResultAuditV4.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected or not evidence_hash_valid(stored, "audit_evidence_hash"):
                raise ValueError("Stored S5 GitHub bulk v4 result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"pages={audit.page_count} records={audit.raw_record_count} "
            f"cohort={audit.cohort_record_count} "
            f"total_requests={audit.total_request_attempt_count} "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
