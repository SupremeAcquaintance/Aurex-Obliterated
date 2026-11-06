# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5_GITHUB_BULK_STOP,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    evidence_hash_valid as bulk_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_correction import (  # noqa: E402
    S5_GITHUB_BULK_AMENDMENT_DECISION,
    S5_GITHUB_BULK_AMENDMENT_NEXT,
    S5_GITHUB_BULK_FAILURE_ADJUDICATION,
    S5_GITHUB_BULK_FAILURE_NEXT,
    S5GitHubBulkFailureAudit,
    S5GitHubBulkResponseHandlingAmendmentV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_response_handling_amendment_v2.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_correction.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_bulk_response_amendment_v2.py")
PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
FAILURE_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_failure_audit_v1.json")
PRIOR_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v1.json")
FAILURE_ARTIFACT_PATH = Path("data/evidence/s5_github_pull_metadata_bulk_v1/failure_page_0001.json")


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
    return tuple(sorted((FAILURE_AUDIT_PATH, PRIOR_RESULT_PATH, FAILURE_ARTIFACT_PATH)))


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_inputs() -> tuple[
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkFailureAudit,
    S5GitHubBulkResult,
]:
    protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    failure_audit = S5GitHubBulkFailureAudit.model_validate_json(
        FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    prior_result = S5GitHubBulkResult.model_validate_json(
        PRIOR_RESULT_PATH.read_text(encoding="utf-8")
    )
    if not (
        bulk_evidence_hash_valid(protocol, "protocol_evidence_hash")
        and evidence_hash_valid(failure_audit, "audit_evidence_hash")
        and failure_audit.adjudication == S5_GITHUB_BULK_FAILURE_ADJUDICATION
        and failure_audit.next_authorization == S5_GITHUB_BULK_FAILURE_NEXT
        and failure_audit.prior_result_evidence_hash == prior_result.result_evidence_hash
        and bulk_evidence_hash_valid(prior_result, "result_evidence_hash")
        and prior_result.decision == S5_GITHUB_BULK_STOP
        and prior_result.logical_request_attempt_count == 1
        and prior_result.successful_request_count == 0
        and prior_result.raw_record_count == 0
        and prior_result.failure_artifact_sha256 == file_sha256(FAILURE_ARTIFACT_PATH)
        and prior_result.btc_market_values_read == 0
        and prior_result.returns_calculated == 0
        and prior_result.orders_submitted == 0
    ):
        raise ValueError("S5 GitHub bulk amendment predecessor lineage changed")
    return protocol, failure_audit, prior_result


def build_amendment(*, frozen_at: datetime) -> S5GitHubBulkResponseHandlingAmendmentV2:
    protocol, failure_audit, prior_result = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "failure_audit_evidence_hash": failure_audit.audit_evidence_hash,
        "prior_result_evidence_hash": prior_result.result_evidence_hash,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "source_bindings": source_bindings(),
        "decision": S5_GITHUB_BULK_AMENDMENT_DECISION,
        "next_authorization": S5_GITHUB_BULK_AMENDMENT_NEXT,
        "limitations": tuple(
            sorted(
                (
                    "The original bulk STOP and empty response artifact remain immutable.",
                    "The prior request counts toward the original 300-attempt ceiling.",
                    "Only page one may receive a second lifetime request attempt.",
                    "Every other page remains limited to one request attempt.",
                    "The corrected run can make at most 299 additional requests.",
                    "The endpoint, all-state query, cutoff, headers, and limits are unchanged.",
                    "No automatic HTTP retry is introduced.",
                    "No credential, token, proxy, redirect, or concurrency is permitted.",
                    "No BTC value, parameter, return, candidate, signal, or order is permitted.",
                    "No paper, Testnet strategy, production, live, or real-capital "
                    "authority exists.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "A corrected transport pass cannot establish strategy reliability or profit.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkResponseHandlingAmendmentV2.model_construct(
        **payload, amendment_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"amendment_evidence_hash"})
    )
    return S5GitHubBulkResponseHandlingAmendmentV2.model_validate(complete)


def write_atomic(path: Path, amendment: S5GitHubBulkResponseHandlingAmendmentV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub bulk amendment: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk amendment transaction exists: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkResponseHandlingAmendmentV2.model_validate_json(serialized) != amendment:
        raise ValueError("S5 GitHub bulk amendment did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S5 bulk v2 amendment.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkResponseHandlingAmendmentV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_amendment(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 GitHub bulk amendment changed")
            print(f"PASS {stored.amendment_evidence_hash}")
            return 0
        amendment = build_amendment(frozen_at=datetime.now(UTC))
        write_atomic(args.output, amendment)
        print(
            f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
            "additional_requests=0 metadata=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
