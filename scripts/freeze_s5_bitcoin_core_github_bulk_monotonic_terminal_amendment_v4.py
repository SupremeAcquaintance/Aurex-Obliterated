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
    S5_GITHUB_BULK_STOP,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkResult,
    evidence_hash_valid as bulk_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (
    S5_GITHUB_BULK_DRIFT_ADJUDICATION,
    S5_GITHUB_BULK_DRIFT_NEXT,
    S5_GITHUB_BULK_MONOTONIC_DECISION,
    S5_GITHUB_BULK_MONOTONIC_NEXT,
    S5GitHubBulkMonotonicTerminalAmendmentV4,
    S5GitHubBulkTerminalDriftFailureAuditV3,
    evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.audit_s5_bitcoin_core_github_bulk_terminal_drift_failure_v3 import (
    auditor_contract_hash as drift_auditor_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_pagination.py")
SCRIPT_PATH = Path(
    "scripts/freeze_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.py"
)
PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
DRIFT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_terminal_drift_failure_audit_v3.json"
)
PRIOR_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v3.json")
FAILURE_ARTIFACT_PATH = Path(
    "data/evidence/s5_github_pull_metadata_bulk_v1/failure_v3_page_0118.json"
)


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                PROTOCOL_PATH,
                DRIFT_AUDIT_PATH,
                PRIOR_RESULT_PATH,
                FAILURE_ARTIFACT_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_inputs() -> tuple[
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkTerminalDriftFailureAuditV3,
    S5GitHubBulkResult,
]:
    protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    drift = S5GitHubBulkTerminalDriftFailureAuditV3.model_validate_json(
        DRIFT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5GitHubBulkResult.model_validate_json(
        PRIOR_RESULT_PATH.read_text(encoding="utf-8")
    )
    drift_sources_match = all(
        file_sha256(PROJECT_ROOT / item.path) == item.file_sha256
        for item in drift.source_bindings
    )
    if not (
        bulk_evidence_hash_valid(protocol, "protocol_evidence_hash")
        and evidence_hash_valid(drift, "audit_evidence_hash")
        and drift.auditor_contract_hash == drift_auditor_contract_hash()
        and drift_sources_match
        and drift.adjudication == S5_GITHUB_BULK_DRIFT_ADJUDICATION
        and drift.next_authorization == S5_GITHUB_BULK_DRIFT_NEXT
        and drift.protocol_evidence_hash == protocol.protocol_evidence_hash
        and bulk_evidence_hash_valid(result, "result_evidence_hash")
        and drift.prior_result_evidence_hash == result.result_evidence_hash
        and drift.prior_result_file_sha256 == file_sha256(PRIOR_RESULT_PATH)
        and drift.failure_artifact_file_sha256 == file_sha256(FAILURE_ARTIFACT_PATH)
        and result.decision == S5_GITHUB_BULK_STOP
        and result.successful_request_count == 117
        and result.terminal_page_count == 244
        and drift.candidate_page == 118
        and drift.observed_terminal_page == 245
        and drift.total_request_attempt_count == 119
        and result.btc_market_values_read == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
    ):
        raise ValueError("S5 GitHub monotonic-terminal predecessor lineage changed")
    return protocol, drift, result


def build_amendment(*, frozen_at: datetime) -> S5GitHubBulkMonotonicTerminalAmendmentV4:
    protocol, drift, result = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "terminal_drift_audit_evidence_hash": drift.audit_evidence_hash,
        "prior_result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "source_bindings": source_bindings(),
        "decision": S5_GITHUB_BULK_MONOTONIC_DECISION,
        "next_authorization": S5_GITHUB_BULK_MONOTONIC_NEXT,
        "limitations": tuple(
            sorted(
                (
                    "Page 118 is promoted locally from its preserved HTTP 200 response.",
                    "Promotion changes only the envelope schema, never response headers or body.",
                    "Promotion consumes zero additional network requests.",
                    "Pages 1 through 118 must reverify before any new request.",
                    "Only contiguous acquisition beginning at page 119 is authorized.",
                    "Terminal pages may stay flat or grow, but must never regress or exceed 300.",
                    "The remaining request budget can complete at most terminal page 299.",
                    "An observed terminal page 300 requires a STOP before budget overrun.",
                    "The original all-state query and creation cutoff remain unchanged.",
                    "Final ordering, uniqueness, cutoff, and byte gates remain mandatory.",
                    "The endpoint, headers, limits, serial access, and no-retry rule are "
                    "unchanged.",
                    "No credential, token, proxy, redirect, or concurrency is authorized.",
                    "No BTC value, parameter, return, candidate, signal, or order is permitted.",
                    "No paper, Testnet strategy, production, live, or capital authority exists.",
                    "The collection is not a transactionally isolated GitHub snapshot.",
                    "Source completeness, predictive edge, and profit remain unestablished.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkMonotonicTerminalAmendmentV4.model_construct(
        **payload, amendment_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"amendment_evidence_hash"})
    )
    return S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate(complete)


def write_atomic(path: Path, amendment: S5GitHubBulkMonotonicTerminalAmendmentV4) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub monotonic amendment: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub monotonic-amendment transaction exists: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate_json(serialized) != amendment:
        raise ValueError("S5 GitHub monotonic-terminal amendment did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze S5 GitHub monotonic-terminal v4 rule.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        amendment = build_amendment(frozen_at=datetime.now(UTC))
        write_atomic(args.output, amendment)
        print(
            f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
            "promote=118 resume=119 observed_terminal=245 max_complete=299 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
