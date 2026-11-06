from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (  # noqa: E402
    S5GitHubPreflightResult,
    S5GitHubPreflightResultAudit,
    audit_s5_github_preflight_result,
    audit_s5_github_preflight_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_preflight_correction import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_FAILURE_ADJUDICATION,
    S5_GITHUB_PREFLIGHT_FAILURE_NEXT,
    S5GitHubPreflightFailureAudit,
    S5GitHubPreflightInterpreterAmendmentV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_interpreter_amendment_v2.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_preflight_correction.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_preflight_interpreter_amendment_v2.py")
PRIOR_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_result_v1.json")
PRIOR_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_result_audit_v1.json"
)
FAILURE_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_github_preflight_failure_audit_v1.json")


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
            (PRIOR_RESULT_PATH, PRIOR_RESULT_AUDIT_PATH, FAILURE_AUDIT_PATH),
            key=lambda item: item.as_posix(),
        )
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_inputs() -> tuple[
    S5GitHubPreflightResult,
    S5GitHubPreflightResultAudit,
    S5GitHubPreflightFailureAudit,
]:
    result = S5GitHubPreflightResult.model_validate_json(
        PRIOR_RESULT_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5GitHubPreflightResultAudit.model_validate_json(
        PRIOR_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    failure = S5GitHubPreflightFailureAudit.model_validate_json(
        FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s5_github_preflight_result(result)
        or not audit_s5_github_preflight_result_audit(result_audit)
        or result_audit.result_evidence_hash != result.result_evidence_hash
        or not evidence_hash_valid(failure, "audit_evidence_hash")
        or failure.prior_result_evidence_hash != result.result_evidence_hash
        or failure.prior_result_audit_evidence_hash != result_audit.audit_evidence_hash
        or failure.adjudication != S5_GITHUB_PREFLIGHT_FAILURE_ADJUDICATION
        or failure.next_authorization != S5_GITHUB_PREFLIGHT_FAILURE_NEXT
        or failure.transport_succeeded is not True
        or failure.interpreter_rejected_source_compatible_response is not True
        or failure.local_revalidation_feasible is not True
        or failure.request_replay_permitted is not False
        or failure.additional_request_count != 0
        or failure.btc_market_values_read != 0
        or failure.returns_calculated != 0
        or failure.orders_submitted != 0
    )
    if changed:
        raise ValueError("S5 GitHub preflight amendment predecessor lineage changed")
    return result, result_audit, failure


def build_amendment(*, frozen_at: datetime) -> S5GitHubPreflightInterpreterAmendmentV2:
    result, result_audit, failure = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "failure_audit_evidence_hash": failure.audit_evidence_hash,
        "prior_result_evidence_hash": result.result_evidence_hash,
        "prior_result_audit_evidence_hash": result_audit.audit_evidence_hash,
        "source_bindings": source_bindings(),
        "permitted_link_paths": (
            "/repos/bitcoin/bitcoin/pulls",
            "/repositories/1181927/pulls",
        ),
        "limitations": tuple(
            sorted(
                (
                    "The original one-request STOP remains immutable and is not relabeled.",
                    "This amendment permits one local interpretation of the preserved response.",
                    "No request replay, new response, credential, or token access is permitted.",
                    "The numeric Link path is accepted only for canonical repository ID 1181927.",
                    "head.sha replaces the absent list-level merge_commit_sha identity field.",
                    "A later bulk mapper must match head.sha to a merge second parent or fail "
                    "closed.",
                    "A null merged_at is valid for a closed but unmerged pull request.",
                    "Protocol gate identities, request scope, body bytes, and limits remain "
                    "unchanged.",
                    "The correction cannot establish source completeness or predictive edge.",
                    "No BTC value, parameter, return, candidate, signal, or order is permitted.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority is created.",
                )
            )
        ),
    }
    provisional = S5GitHubPreflightInterpreterAmendmentV2.model_construct(
        **payload, amendment_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"amendment_evidence_hash"})
    )
    return S5GitHubPreflightInterpreterAmendmentV2.model_validate(complete)


def write_atomic(path: Path, amendment: S5GitHubPreflightInterpreterAmendmentV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub preflight amendment: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub preflight amendment transaction exists: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if S5GitHubPreflightInterpreterAmendmentV2.model_validate_json(serialized) != amendment:
        raise ValueError("S5 GitHub preflight amendment did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S5 preflight amendment v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubPreflightInterpreterAmendmentV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_amendment(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 GitHub preflight amendment changed")
            print(f"PASS {stored.amendment_evidence_hash}")
            return 0
        amendment = build_amendment(frozen_at=datetime.now(UTC))
        write_atomic(args.output, amendment)
        print(
            f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
            "additional_requests=0 metadata_records=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
