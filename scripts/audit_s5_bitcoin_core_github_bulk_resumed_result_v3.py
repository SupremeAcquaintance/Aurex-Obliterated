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
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_resume import (
    S5GitHubBulkContiguousResumeAmendmentAuditV3,
    S5GitHubBulkResumedResultAuditV3,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base
from scripts.run_s1_btc_source_acquisition import file_sha256
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v3 import (
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESUME_AMENDMENT,
    DEFAULT_RESUME_AMENDMENT_AUDIT,
    DEFAULT_SUSPENSION_AUDIT,
    RESUME_MODULE_PATH,
    SCRIPT_PATH as RUNNER_V3_PATH,
    build_result_v3,
    load_authorization,
    runner_contract_hash,
)

DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v3.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_resumed_result_audit_v3.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_resumed_result_v3.py")


def auditor_contract_hash() -> str:
    paths = (base.MODULE_PATH, base.SCRIPT_PATH, RESUME_MODULE_PATH, RUNNER_V3_PATH, SCRIPT_PATH)
    return universe_evidence_hash(
        {
            "sources": tuple(
                {"path": path.as_posix(), "file_sha256": file_sha256(PROJECT_ROOT / path)}
                for path in paths
            )
        }
    )


def reconstruct(result_path: Path) -> tuple[S5GitHubBulkResult, str, str]:
    protocol, amendment = load_authorization(
        protocol_path=DEFAULT_PROTOCOL,
        protocol_audit_path=DEFAULT_PROTOCOL_AUDIT,
        suspension_audit_path=DEFAULT_SUSPENSION_AUDIT,
        amendment_path=DEFAULT_RESUME_AMENDMENT,
        amendment_audit_path=DEFAULT_RESUME_AMENDMENT_AUDIT,
    )
    amendment_audit = S5GitHubBulkContiguousResumeAmendmentAuditV3.model_validate_json(
        DEFAULT_RESUME_AMENDMENT_AUDIT.read_text(encoding="utf-8")
    )
    result = S5GitHubBulkResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    if not (
        bulk_evidence_hash_valid(result, "result_evidence_hash")
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.runner_contract_hash == runner_contract_hash()
        and result.decision == S5_GITHUB_BULK_PASS
        and result.next_authorization == S5_GITHUB_BULK_NEXT
        and result.failed_gate_count == 0
        and result.successful_request_count == 244
        and result.terminal_page_count == 244
        and result.resumed_page_count >= 117
        and result.logical_request_attempt_count == 244
        and result.failure_artifact_path is None
        and result.failure_artifact_sha256 is None
    ):
        raise ValueError("S5 GitHub bulk v3 result is not an auditable PASS")
    page_directory = Path(result.raw_page_directory)
    if list(page_directory.glob("failure_v3_page_*.json")):
        raise ValueError("S5 GitHub bulk page directory contains a v3 failure artifact")
    pages, terminal_page = base.load_existing_pages(
        protocol=protocol, page_directory=page_directory
    )
    if terminal_page != 244 or len(pages) != 244:
        raise ValueError("S5 GitHub bulk v3 terminal page count changed")
    bindings = tuple(base.page_binding(path=path, parsed=parsed) for path, parsed in pages)
    if bindings != result.page_bindings:
        raise ValueError("S5 GitHub bulk v3 raw page manifest changed")
    reconstructed = build_result_v3(
        protocol=protocol,
        pages=pages,
        started_at=result.started_at,
        completed_at=result.completed_at,
        new_request_attempt_count=result.new_request_attempt_count,
        resumed_page_count=result.resumed_page_count,
        wait_count=result.rate_limit_wait_count,
        wait_seconds=result.rate_limit_wait_seconds,
    )
    if reconstructed != result:
        raise ValueError("S5 GitHub bulk v3 result differs from full reconstruction")
    return result, amendment.amendment_evidence_hash, amendment_audit.audit_evidence_hash


def build_audit(*, result_path: Path, audited_at: datetime) -> S5GitHubBulkResumedResultAuditV3:
    result, amendment_hash, amendment_audit_hash = reconstruct(result_path)
    corrected_v3_requests = result.successful_request_count - 117
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "resume_amendment_evidence_hash": amendment_hash,
        "resume_amendment_audit_evidence_hash": amendment_audit_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "corrected_v3_request_attempt_count": corrected_v3_requests,
        "total_request_attempt_count": 1 + 117 + corrected_v3_requests,
        "raw_record_count": result.raw_record_count,
        "cohort_record_count": result.cohort_record_count,
    }
    provisional = S5GitHubBulkResumedResultAuditV3.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkResumedResultAuditV3.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkResumedResultAuditV3) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk v3 result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk v3 result-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkResumedResultAuditV3.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub bulk v3 result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit resumed S5 GitHub bulk result v3.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkResumedResultAuditV3.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected or not evidence_hash_valid(stored, "audit_evidence_hash"):
                raise ValueError("Stored S5 GitHub bulk v3 result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} pages=244 "
            f"records={audit.raw_record_count} cohort={audit.cohort_record_count} "
            f"total_requests={audit.total_request_attempt_count} "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
