# ruff: noqa: E402

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

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5_GITHUB_BULK_FAILURE_NEXT as PRIOR_FAILURE_NEXT,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    S5_GITHUB_BULK_STOP,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkProtocolAudit,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    evidence_hash_valid as bulk_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_correction import (  # noqa: E402
    S5_GITHUB_BULK_FAILURE_ADJUDICATION,
    S5_GITHUB_BULK_FAILURE_NEXT,
    S5GitHubBulkFailureAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_github_bulk_acquisition import (  # noqa: E402
    FAILURE_SCHEMA,
    runner_contract_hash,
)
from scripts.run_s5_bitcoin_core_github_bulk_acquisition import (
    MODULE_PATH as BULK_MODULE_PATH,
)
from scripts.run_s5_bitcoin_core_github_bulk_acquisition import (
    SCRIPT_PATH as PRIOR_RUNNER_PATH,
)

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v1.json")
DEFAULT_FAILURE = Path("data/evidence/s5_github_pull_metadata_bulk_v1/failure_page_0001.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_failure_audit_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_correction.py")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_github_bulk_failure.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def source_paths(
    *, protocol_path: Path, protocol_audit_path: Path, result_path: Path, failure_path: Path
) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                protocol_path,
                protocol_audit_path,
                result_path,
                failure_path,
                BULK_MODULE_PATH,
                PRIOR_RUNNER_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def source_bindings(paths: tuple[Path, ...]) -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path)) for path in paths
    )


def inspect_failure(path: Path, protocol: S5GitHubBulkAcquisitionProtocol) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    request = payload["request"]
    response = payload["response"]
    error = payload["error"]
    body = base64.b64decode(response["body_base64"], validate=True)
    if not (
        payload["schema_version"] == FAILURE_SCHEMA
        and payload["protocol_evidence_hash"] == protocol.protocol_evidence_hash
        and payload["page"] == 1
        and payload["request_attempt_count"] == 1
        and request["method"] == protocol.method
        and request["url"].endswith("per_page=100&page=1")
        and request["authorization_header_used"] is False
        and request["token_value_accessed"] is False
        and request["environment_proxy_used"] is False
        and response["http_status"] is None
        and response["final_url"] is None
        and response["headers"] == {}
        and response["body_byte_count"] == 0
        and response["body_sha256"]
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        and body == b""
        and error["type"] == "TypeError"
        and error["message"] == "'Response' object does not support the context manager protocol"
    ):
        raise ValueError("S5 GitHub bulk failure artifact changed")


def build_audit(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    result_path: Path,
    failure_path: Path,
    audited_at: datetime,
) -> S5GitHubBulkFailureAudit:
    protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S5GitHubBulkProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    result = S5GitHubBulkResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    inspect_failure(failure_path, protocol)
    if not (
        bulk_evidence_hash_valid(protocol, "protocol_evidence_hash")
        and bulk_evidence_hash_valid(protocol_audit, "audit_evidence_hash")
        and protocol_audit.protocol_file_sha256 == file_sha256(protocol_path)
        and protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and bulk_evidence_hash_valid(result, "result_evidence_hash")
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.runner_contract_hash == runner_contract_hash()
        and result.decision == S5_GITHUB_BULK_STOP
        and result.next_authorization == PRIOR_FAILURE_NEXT
    ):
        raise ValueError("S5 GitHub bulk failure lineage changed")
    if not (
        result.logical_request_attempt_count == 1
        and result.new_request_attempt_count == 1
        and result.successful_request_count == 0
        and result.raw_record_count == 0
        and result.failure_type == "PageFailure"
        and result.failure_message
        == "GitHub request failed: TypeError: 'Response' object does not support the context "
        "manager protocol"
        and result.failure_artifact_path == failure_path.as_posix()
        and result.failure_artifact_sha256 == file_sha256(failure_path)
        and result.btc_market_values_read == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
    ):
        raise ValueError("S5 GitHub bulk failure result changed")
    paths = source_paths(
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        result_path=result_path,
        failure_path=failure_path,
    )
    payload = {
        "audited_at": audited_at,
        "auditor_contract_hash": auditor_contract_hash(),
        "source_bindings": source_bindings(paths),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "prior_result_evidence_hash": result.result_evidence_hash,
        "prior_result_file_sha256": file_sha256(result_path),
        "failure_artifact_file_sha256": file_sha256(failure_path),
        "prior_runner_contract_hash": result.runner_contract_hash,
        "adjudication": S5_GITHUB_BULK_FAILURE_ADJUDICATION,
        "next_authorization": S5_GITHUB_BULK_FAILURE_NEXT,
        "limitations": tuple(
            sorted(
                (
                    "The request was dispatched, but no status, header, or body was captured.",
                    "The failure does not establish whether GitHub returned a successful response.",
                    "One page-one replay is necessary to acquire the missing response evidence.",
                    "The replay must remain inside the original 300-attempt ceiling.",
                    "The original STOP result and empty failure artifact remain immutable.",
                    "No successful raw page or metadata record was persisted.",
                    "The correction may change only HTTP response resource handling.",
                    "No credential, token, proxy, redirect, or concurrent request is permitted.",
                    "No BTC value, parameter, return, candidate, signal, or order was accessed.",
                    "No paper, Testnet strategy, production, live, or real-capital "
                    "authority exists.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "Real net profit remains zero.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkFailureAudit.model_construct(**payload, audit_evidence_hash="0" * 64)
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkFailureAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5GitHubBulkFailureAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk failure audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk failure-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkFailureAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub bulk failure audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the first S5 GitHub bulk failure.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--failure", type=Path, default=DEFAULT_FAILURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        audit = build_audit(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            result_path=args.result,
            failure_path=args.failure,
            audited_at=datetime.now(UTC),
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "requests=1 captured_bytes=0 metadata=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
