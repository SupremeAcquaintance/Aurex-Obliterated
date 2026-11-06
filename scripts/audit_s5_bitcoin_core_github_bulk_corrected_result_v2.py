# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5_GITHUB_BULK_NEXT,
    S5_GITHUB_BULK_PASS,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    evidence_hash_valid as bulk_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_correction import (  # noqa: E402
    S5GitHubBulkCorrectedResultAuditV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v2 import (  # noqa: E402
    CORRECTION_MODULE_PATH,
    build_result_v2,
    load_authorization,
    runner_contract_hash,
)
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v2 import (
    SCRIPT_PATH as RUNNER_V2_PATH,
)

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
DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_corrected_result_audit_v2.json")
ORIGINAL_FAILURE = Path("data/evidence/s5_github_pull_metadata_bulk_v1/failure_page_0001.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_corrected_result_v2.py")


def auditor_contract_hash() -> str:
    paths = (
        base.MODULE_PATH,
        base.SCRIPT_PATH,
        CORRECTION_MODULE_PATH,
        RUNNER_V2_PATH,
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


def reconstruct(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    failure_audit_path: Path,
    amendment_path: Path,
    amendment_audit_path: Path,
    result_path: Path,
) -> tuple[S5GitHubBulkResult, str, str]:
    protocol, amendment = load_authorization(
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        failure_audit_path=failure_audit_path,
        amendment_path=amendment_path,
        amendment_audit_path=amendment_audit_path,
    )
    amendment_audit_payload = json.loads(amendment_audit_path.read_text(encoding="utf-8"))
    result = S5GitHubBulkResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    if not (
        bulk_evidence_hash_valid(result, "result_evidence_hash")
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.runner_contract_hash == runner_contract_hash()
        and result.decision == S5_GITHUB_BULK_PASS
        and result.next_authorization == S5_GITHUB_BULK_NEXT
        and result.failed_gate_count == 0
        and result.failure_artifact_path is None
        and result.failure_artifact_sha256 is None
        and result.logical_request_attempt_count <= amendment.maximum_corrected_run_attempts
    ):
        raise ValueError("S5 GitHub bulk v2 result is not an auditable PASS")
    if not ORIGINAL_FAILURE.is_file():
        raise ValueError("Original S5 GitHub bulk failure artifact is missing")
    page_directory = Path(result.raw_page_directory)
    if list(page_directory.glob("failure_v2_page_*.json")):
        raise ValueError("S5 GitHub bulk page directory contains a v2 failure artifact")
    pages, terminal_page = base.load_existing_pages(
        protocol=protocol, page_directory=page_directory
    )
    if terminal_page != result.terminal_page_count or len(pages) != result.successful_request_count:
        raise ValueError("S5 GitHub bulk v2 page count changed")
    bindings = tuple(base.page_binding(path=path, parsed=parsed) for path, parsed in pages)
    if bindings != result.page_bindings:
        raise ValueError("S5 GitHub bulk v2 raw page manifest changed")
    reconstructed = build_result_v2(
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
        raise ValueError("S5 GitHub bulk v2 result differs from full reconstruction")
    return (
        result,
        amendment.amendment_evidence_hash,
        str(amendment_audit_payload["audit_evidence_hash"]),
    )


def build_audit(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    failure_audit_path: Path,
    amendment_path: Path,
    amendment_audit_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S5GitHubBulkCorrectedResultAuditV2:
    result, amendment_hash, amendment_audit_hash = reconstruct(
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        failure_audit_path=failure_audit_path,
        amendment_path=amendment_path,
        amendment_audit_path=amendment_audit_path,
        result_path=result_path,
    )
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "amendment_evidence_hash": amendment_hash,
        "amendment_audit_evidence_hash": amendment_audit_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "corrected_request_attempt_count": result.logical_request_attempt_count,
        "total_request_attempt_count": 1 + result.logical_request_attempt_count,
        "page_count": result.successful_request_count,
        "raw_record_count": result.raw_record_count,
        "cohort_record_count": result.cohort_record_count,
    }
    provisional = S5GitHubBulkCorrectedResultAuditV2.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkCorrectedResultAuditV2.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkCorrectedResultAuditV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk v2 result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk v2 result-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkCorrectedResultAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub bulk v2 result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit corrected S5 GitHub bulk result v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--failure-audit", type=Path, default=DEFAULT_FAILURE_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkCorrectedResultAuditV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                failure_audit_path=args.failure_audit,
                amendment_path=args.amendment,
                amendment_audit_path=args.amendment_audit,
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected or not evidence_hash_valid(stored, "audit_evidence_hash"):
                raise ValueError("Stored S5 GitHub bulk v2 result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            failure_audit_path=args.failure_audit,
            amendment_path=args.amendment,
            amendment_audit_path=args.amendment_audit,
            result_path=args.result,
            audited_at=datetime.now(UTC),
        )
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
