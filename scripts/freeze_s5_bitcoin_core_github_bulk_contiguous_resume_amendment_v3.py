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
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkResult,
    evidence_hash_valid as bulk_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_correction import (
    S5GitHubBulkResponseHandlingAmendmentV2,
    evidence_hash_valid as correction_evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_resume import (
    S5_GITHUB_BULK_RESUME_DECISION,
    S5_GITHUB_BULK_RESUME_NEXT,
    S5_GITHUB_BULK_SUSPENSION_ADJUDICATION,
    S5_GITHUB_BULK_SUSPENSION_NEXT,
    S5GitHubBulkContiguousResumeAmendmentV3,
    S5GitHubBulkSuspensionFailureAuditV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.run_s1_btc_source_acquisition import file_sha256

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_resume.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.py")
PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
RESPONSE_AMENDMENT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_response_handling_amendment_v2.json"
)
SUSPENSION_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_suspension_failure_audit_v2.json"
)
PRIOR_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v2.json")
FAILURE_ARTIFACT_PATH = Path(
    "data/evidence/s5_github_pull_metadata_bulk_v1/failure_v2_page_0118.json"
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
                SUSPENSION_AUDIT_PATH,
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
    S5GitHubBulkSuspensionFailureAuditV2,
    S5GitHubBulkResult,
    S5GitHubBulkResponseHandlingAmendmentV2,
]:
    protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    suspension = S5GitHubBulkSuspensionFailureAuditV2.model_validate_json(
        SUSPENSION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5GitHubBulkResult.model_validate_json(PRIOR_RESULT_PATH.read_text(encoding="utf-8"))
    response_amendment = S5GitHubBulkResponseHandlingAmendmentV2.model_validate_json(
        RESPONSE_AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    if not (
        bulk_evidence_hash_valid(protocol, "protocol_evidence_hash")
        and evidence_hash_valid(suspension, "audit_evidence_hash")
        and suspension.adjudication == S5_GITHUB_BULK_SUSPENSION_ADJUDICATION
        and suspension.next_authorization == S5_GITHUB_BULK_SUSPENSION_NEXT
        and suspension.prior_result_evidence_hash == result.result_evidence_hash
        and bulk_evidence_hash_valid(result, "result_evidence_hash")
        and result.successful_request_count == 117
        and result.raw_record_count == 11_700
        and result.terminal_page_count == 244
        and correction_evidence_hash_valid(response_amendment, "amendment_evidence_hash")
        and response_amendment.amendment_evidence_hash
        == suspension.response_amendment_evidence_hash
        and result.failure_artifact_sha256 == file_sha256(FAILURE_ARTIFACT_PATH)
        and result.btc_market_values_read == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
    ):
        raise ValueError("S5 GitHub contiguous-resume predecessor lineage changed")
    return protocol, suspension, result, response_amendment


def build_amendment(*, frozen_at: datetime) -> S5GitHubBulkContiguousResumeAmendmentV3:
    protocol, suspension, result, response_amendment = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "suspension_failure_audit_evidence_hash": suspension.audit_evidence_hash,
        "prior_result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "response_amendment_evidence_hash": response_amendment.amendment_evidence_hash,
        "source_bindings": source_bindings(),
        "decision": S5_GITHUB_BULK_RESUME_DECISION,
        "next_authorization": S5_GITHUB_BULK_RESUME_NEXT,
        "limitations": tuple(
            sorted(
                (
                    "Only a contiguous resume at page 118 is authorized.",
                    "Pages 1 through 117 must reverify before any new request.",
                    "The prior 118 request attempts remain charged to the 300 ceiling.",
                    "At most 182 new requests may execute in the resumed process.",
                    "The new elapsed clock does not alter the frozen cohort cutoff.",
                    "The endpoint, query, headers, body limits, and page schema are unchanged.",
                    "No prior successful page may be overwritten or requested again.",
                    "No automatic retry, credential, proxy, redirect, or concurrency "
                    "is introduced.",
                    "No BTC value, parameter, return, candidate, signal, or order is permitted.",
                    "No paper, Testnet strategy, production, live, or real-capital "
                    "authority exists.",
                    "Source completeness and predictive edge remain unadjudicated.",
                    "A completed transport still cannot establish reliable profit.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkContiguousResumeAmendmentV3.model_construct(
        **payload, amendment_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"amendment_evidence_hash"})
    )
    return S5GitHubBulkContiguousResumeAmendmentV3.model_validate(complete)


def write_atomic(path: Path, amendment: S5GitHubBulkContiguousResumeAmendmentV3) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub resume amendment: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub resume-amendment transaction exists: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkContiguousResumeAmendmentV3.model_validate_json(serialized) != amendment:
        raise ValueError("S5 GitHub resume amendment did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check S5 GitHub resume amendment v3.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkContiguousResumeAmendmentV3.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_amendment(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 GitHub resume amendment changed")
            print(f"PASS {stored.amendment_evidence_hash}")
            return 0
        amendment = build_amendment(frozen_at=datetime.now(UTC))
        write_atomic(args.output, amendment)
        print(
            f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
            "additional_requests=0 preserved_pages=117 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
