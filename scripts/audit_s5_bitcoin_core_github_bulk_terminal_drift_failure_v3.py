# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import base64
import hashlib
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
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (
    S5_GITHUB_BULK_DRIFT_ADJUDICATION,
    S5_GITHUB_BULK_DRIFT_NEXT,
    S5GitHubBulkTerminalDriftFailureAuditV3,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
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
DEFAULT_FAILURE = Path(
    "data/evidence/s5_github_pull_metadata_bulk_v1/failure_v3_page_0118.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_terminal_drift_failure_audit_v3.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_pagination.py")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_terminal_drift_failure_v3.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def observation_from_failure(
    path: Path, *, protocol_hash: str
) -> base.RequestObservation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    request = payload["request"]
    response = payload["response"]
    error = payload["error"]
    body = base64.b64decode(response["body_base64"], validate=True)
    if not (
        payload["schema_version"] == "aurex-s5-github-bulk-failure-page-v3"
        and payload["protocol_evidence_hash"] == protocol_hash
        and payload["page"] == 118
        and payload["request_attempt_count"] == 1
        and response["body_byte_count"] == len(body)
        and response["body_sha256"] == hashlib.sha256(body).hexdigest()
        and error["type"] is None
        and error["message"] is None
    ):
        raise ValueError("S5 GitHub terminal-drift failure artifact changed")
    return base.RequestObservation(
        page=118,
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


def source_paths(result_path: Path, failure_path: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                DEFAULT_PROTOCOL,
                DEFAULT_RESUME_AMENDMENT,
                DEFAULT_RESUME_AMENDMENT_AUDIT,
                result_path,
                failure_path,
                RUNNER_V3_PATH,
                RESUME_MODULE_PATH,
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
) -> S5GitHubBulkTerminalDriftFailureAuditV3:
    protocol, resume_amendment = load_authorization(
        protocol_path=DEFAULT_PROTOCOL,
        protocol_audit_path=DEFAULT_PROTOCOL_AUDIT,
        suspension_audit_path=DEFAULT_SUSPENSION_AUDIT,
        amendment_path=DEFAULT_RESUME_AMENDMENT,
        amendment_audit_path=DEFAULT_RESUME_AMENDMENT_AUDIT,
    )
    resume_audit = json.loads(DEFAULT_RESUME_AMENDMENT_AUDIT.read_text(encoding="utf-8"))
    result = S5GitHubBulkResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    observation = observation_from_failure(
        failure_path, protocol_hash=protocol.protocol_evidence_hash
    )
    candidate = base.parse_observation(observation=observation, protocol=protocol)
    pages, prefix_terminal = base.load_existing_pages(
        protocol=protocol, page_directory=Path(protocol.raw_page_directory)
    )
    prefix_numbers = {record.number for _, page in pages for record in page.records}
    candidate_numbers = {record.number for record in candidate.records}
    creation_continues = pages[-1][1].records[-1].created_at <= candidate.records[0].created_at
    numbers_disjoint = prefix_numbers.isdisjoint(candidate_numbers)
    bindings = tuple(base.page_binding(path=path, parsed=parsed) for path, parsed in pages)
    if not (
        bulk_evidence_hash_valid(result, "result_evidence_hash")
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.runner_contract_hash == runner_contract_hash()
        and result.decision == S5_GITHUB_BULK_STOP
        and result.logical_request_attempt_count == 118
        and result.new_request_attempt_count == 1
        and result.successful_request_count == 117
        and result.resumed_page_count == 117
        and result.raw_record_count == 11_700
        and result.terminal_page_count == 244
        and result.failure_type == "PageFailure"
        and result.failure_message == "GitHub bulk terminal page drifted during v3 acquisition"
        and result.failure_artifact_path == failure_path.as_posix()
        and result.failure_artifact_sha256 == file_sha256(failure_path)
        and prefix_terminal == 244
        and len(pages) == 117
        and bindings == result.page_bindings
        and candidate.page == 118
        and candidate.terminal_page == 245
        and candidate.next_page == 119
        and len(candidate.records) == 100
        and creation_continues
        and numbers_disjoint
        and result.btc_market_values_read == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
    ):
        raise ValueError("S5 GitHub terminal-drift result or candidate page changed")
    reconstructed = build_result_v3(
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
        raise ValueError("S5 GitHub terminal-drift result differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "auditor_contract_hash": auditor_contract_hash(),
        "source_bindings": source_bindings(source_paths(result_path, failure_path)),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "resume_amendment_evidence_hash": resume_amendment.amendment_evidence_hash,
        "resume_amendment_audit_evidence_hash": str(resume_audit["audit_evidence_hash"]),
        "prior_result_evidence_hash": result.result_evidence_hash,
        "prior_result_file_sha256": file_sha256(result_path),
        "failure_artifact_file_sha256": file_sha256(failure_path),
        "prior_runner_contract_hash": result.runner_contract_hash,
        "candidate_page_response_bytes": candidate.response_byte_count,
        "candidate_page_response_body_sha256": candidate.response_body_sha256,
        "adjudication": S5_GITHUB_BULK_DRIFT_ADJUDICATION,
        "next_authorization": S5_GITHUB_BULK_DRIFT_NEXT,
        "limitations": tuple(
            sorted(
                (
                    "Page 118 is a complete HTTP 200 response and needs no replay.",
                    "The terminal page moved from 244 to 245 between request windows.",
                    "The exact cause of terminal growth is not inferred from pagination alone.",
                    "The all-state query and frozen creation cutoff remain unchanged.",
                    "Page 118 continues the preserved creation order and has disjoint pull IDs.",
                    "Any local promotion must preserve response headers and body bytes exactly.",
                    "Future terminal movement may be accepted only if nondecreasing and at "
                    "most 300.",
                    "Final uniqueness, ordering, cutoff, and completeness checks remain mandatory.",
                    "All 119 requests count toward the original 300-attempt ceiling.",
                    "No credential, token, proxy, redirect, concurrency, or replay is authorized.",
                    "No BTC value, parameter, return, candidate, signal, or order was accessed.",
                    "No paper, Testnet strategy, production, live, or real-capital authority "
                    "exists.",
                    "Source completeness, predictive edge, and profit remain unestablished.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkTerminalDriftFailureAuditV3.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkTerminalDriftFailureAuditV3.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkTerminalDriftFailureAuditV3) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub terminal-drift audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub terminal-drift audit exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkTerminalDriftFailureAuditV3.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub terminal-drift audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S5 GitHub terminal-page drift.")
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
            f"AUDITED {args.output} {audit.audit_evidence_hash} prefix_pages=117 "
            "candidate_page=118 terminal=245 total_requests=119 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
