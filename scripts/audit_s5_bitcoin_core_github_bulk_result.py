from __future__ import annotations

import argparse
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
    S5GitHubBulkResultAudit,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_github_bulk_acquisition import (  # noqa: E402
    MODULE_PATH,
    build_result,
    load_existing_pages,
    load_protocol,
    page_binding,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_result.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct(
    *, protocol_path: Path, protocol_audit_path: Path, result_path: Path
) -> S5GitHubBulkResult:
    protocol = load_protocol(protocol_path, protocol_audit_path)
    result = S5GitHubBulkResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    if (
        not evidence_hash_valid(result, "result_evidence_hash")
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.decision != S5_GITHUB_BULK_PASS
        or result.next_authorization != S5_GITHUB_BULK_NEXT
        or result.failed_gate_count != 0
        or result.failure_artifact_path is not None
        or result.failure_artifact_sha256 is not None
    ):
        raise ValueError("S5 GitHub bulk result is not an auditable PASS")
    page_directory = Path(result.raw_page_directory)
    if list(page_directory.glob("failure_page_*.json")):
        raise ValueError("S5 GitHub bulk page directory contains a failure artifact")
    pages, terminal_page = load_existing_pages(protocol=protocol, page_directory=page_directory)
    if terminal_page != result.terminal_page_count or len(pages) != result.successful_request_count:
        raise ValueError("S5 GitHub bulk page count changed")
    bindings = tuple(page_binding(path=path, parsed=parsed) for path, parsed in pages)
    if bindings != result.page_bindings:
        raise ValueError("S5 GitHub bulk raw page manifest changed")
    reconstructed = build_result(
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
        raise ValueError("S5 GitHub bulk result differs from full reconstruction")
    return result


def build_audit(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S5GitHubBulkResultAudit:
    result = reconstruct(
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        result_path=result_path,
    )
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "page_count": result.successful_request_count,
        "raw_record_count": result.raw_record_count,
        "cohort_record_count": result.cohort_record_count,
    }
    provisional = S5GitHubBulkResultAudit.model_construct(**payload, audit_evidence_hash="0" * 64)
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkResultAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk result audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub bulk result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S5 GitHub bulk result.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected or not evidence_hash_valid(stored, "audit_evidence_hash"):
                raise ValueError("Stored S5 GitHub bulk result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            result_path=args.result,
            audited_at=datetime.now(UTC),
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"pages={audit.page_count} records={audit.raw_record_count} "
            f"cohort={audit.cohort_record_count} market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
