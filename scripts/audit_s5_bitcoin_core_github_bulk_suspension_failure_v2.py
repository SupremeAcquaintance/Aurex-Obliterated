# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    S5_GITHUB_BULK_STOP,
    S5GitHubBulkResult,
    evidence_hash_valid as bulk_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_resume import (
    S5_GITHUB_BULK_SUSPENSION_ADJUDICATION,
    S5_GITHUB_BULK_SUSPENSION_NEXT,
    S5GitHubBulkSuspensionFailureAuditV2,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base
from scripts.run_s1_btc_source_acquisition import file_sha256
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v2 import (
    CORRECTION_MODULE_PATH,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_FAILURE_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    SCRIPT_PATH as RUNNER_V2_PATH,
    build_result_v2,
    load_authorization,
    runner_contract_hash,
)

DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v2.json")
DEFAULT_FAILURE = Path("data/evidence/s5_github_pull_metadata_bulk_v1/failure_v2_page_0118.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_suspension_failure_audit_v2.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_resume.py")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_suspension_failure_v2.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def inspect_failure(path: Path, protocol_hash: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    response = payload["response"]
    error = payload["error"]
    body = base64.b64decode(response["body_base64"], validate=True)
    if not (
        payload["schema_version"] == "aurex-s5-github-bulk-failure-page-v2"
        and payload["protocol_evidence_hash"] == protocol_hash
        and payload["page"] == 118
        and payload["request_attempt_count"] == 1
        and response["http_status"] is None
        and response["final_url"] is None
        and response["headers"] == {}
        and response["body_byte_count"] == 0
        and body == b""
        and error["type"] == "ValueError"
        and error["message"] == "S5 GitHub bulk v2 exceeded the frozen elapsed-time bound"
    ):
        raise ValueError("S5 GitHub bulk suspension failure artifact changed")


def source_paths(*, result_path: Path, failure_path: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                DEFAULT_PROTOCOL,
                DEFAULT_AMENDMENT,
                DEFAULT_AMENDMENT_AUDIT,
                result_path,
                failure_path,
                RUNNER_V2_PATH,
                CORRECTION_MODULE_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def source_bindings(paths: tuple[Path, ...]) -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path)) for path in paths
    )


def build_audit(
    *, result_path: Path, failure_path: Path, audited_at: datetime
) -> S5GitHubBulkSuspensionFailureAuditV2:
    protocol, amendment = load_authorization(
        protocol_path=DEFAULT_PROTOCOL,
        protocol_audit_path=DEFAULT_PROTOCOL_AUDIT,
        failure_audit_path=DEFAULT_FAILURE_AUDIT,
        amendment_path=DEFAULT_AMENDMENT,
        amendment_audit_path=DEFAULT_AMENDMENT_AUDIT,
    )
    amendment_audit = json.loads(DEFAULT_AMENDMENT_AUDIT.read_text(encoding="utf-8"))
    result = S5GitHubBulkResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    inspect_failure(failure_path, protocol.protocol_evidence_hash)
    pages, terminal_page = base.load_existing_pages(
        protocol=protocol, page_directory=Path(protocol.raw_page_directory)
    )
    bindings = tuple(base.page_binding(path=path, parsed=parsed) for path, parsed in pages)
    if not (
        bulk_evidence_hash_valid(result, "result_evidence_hash")
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.runner_contract_hash == runner_contract_hash()
        and result.decision == S5_GITHUB_BULK_STOP
        and result.logical_request_attempt_count == 117
        and result.new_request_attempt_count == 117
        and result.successful_request_count == 117
        and result.resumed_page_count == 0
        and result.raw_record_count == 11_700
        and result.cohort_record_count == 11_700
        and result.terminal_page_count == 244
        and result.failure_type == "ValueError"
        and result.failure_message == "S5 GitHub bulk v2 exceeded the frozen elapsed-time bound"
        and result.failure_artifact_path == failure_path.as_posix()
        and result.failure_artifact_sha256 == file_sha256(failure_path)
        and terminal_page == 244
        and len(pages) == 117
        and bindings == result.page_bindings
        and result.btc_market_values_read == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
    ):
        raise ValueError("S5 GitHub bulk suspension result or pages changed")
    reconstructed = build_result_v2(
        protocol=protocol,
        pages=pages,
        started_at=result.started_at,
        completed_at=result.completed_at,
        new_request_attempt_count=result.new_request_attempt_count,
        resumed_page_count=result.resumed_page_count,
        wait_count=result.rate_limit_wait_count,
        wait_seconds=result.rate_limit_wait_seconds,
        failure_type=result.failure_type,
        failure_message=result.failure_message,
        failure_path=failure_path,
    )
    if reconstructed != result:
        raise ValueError("S5 GitHub suspension result differs from reconstruction")
    paths = source_paths(result_path=result_path, failure_path=failure_path)
    payload = {
        "audited_at": audited_at,
        "auditor_contract_hash": auditor_contract_hash(),
        "source_bindings": source_bindings(paths),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "response_amendment_evidence_hash": amendment.amendment_evidence_hash,
        "response_amendment_audit_evidence_hash": str(amendment_audit["audit_evidence_hash"]),
        "prior_result_evidence_hash": result.result_evidence_hash,
        "prior_result_file_sha256": file_sha256(result_path),
        "failure_artifact_file_sha256": file_sha256(failure_path),
        "prior_runner_contract_hash": result.runner_contract_hash,
        "adjudication": S5_GITHUB_BULK_SUSPENSION_ADJUDICATION,
        "next_authorization": S5_GITHUB_BULK_SUSPENSION_NEXT,
        "limitations": tuple(
            sorted(
                (
                    "Pages 1 through 117 and their response hashes reverify exactly.",
                    "No page-118 network request was made after the stale wait completed.",
                    "The host suspension caused the process clock to exceed the 12-hour bound.",
                    "A new process clock may resume only from page 118.",
                    "The original cohort cutoff, endpoint, query, and page files remain unchanged.",
                    "The first failed request and all 117 v2 requests count toward the ceiling.",
                    "The remaining 182-request capacity is greater than the 127-page minimum.",
                    "No prior page may be requested again.",
                    "No credential, token, proxy, redirect, or concurrency is permitted.",
                    "No BTC value, parameter, return, candidate, signal, or order was accessed.",
                    "No paper, Testnet strategy, production, live, or real-capital "
                    "authority exists.",
                    "Source completeness, predictive edge, and profit remain unestablished.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkSuspensionFailureAuditV2.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkSuspensionFailureAuditV2.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkSuspensionFailureAuditV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub suspension audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub suspension-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkSuspensionFailureAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub suspension audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S5 GitHub host-suspension stop.")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--failure", type=Path, default=DEFAULT_FAILURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        audit = build_audit(
            result_path=args.result,
            failure_path=args.failure,
            audited_at=datetime.now(UTC),
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} pages=117 records=11700 "
            "total_requests=118 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
