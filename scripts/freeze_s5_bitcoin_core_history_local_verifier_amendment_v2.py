from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5_HISTORY_STOP,
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadProtocolAudit,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryPayloadResultAudit,
    S5HistoryBinding,
    audit_s5_history_protocol,
    audit_s5_history_protocol_audit,
    audit_s5_history_result,
    audit_s5_history_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5_VERIFIER_FAILURE_ADJUDICATION,
    S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    S5BitcoinCoreHistoryVerifierFailureAudit,
    audit_verifier_failure,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_local_verifier_amendment_v2.json")
PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_audit_v1.json")
PRIOR_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
PRIOR_RESULT_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_audit_v1.json")
FAILURE_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_verifier_failure_audit_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_history_payload_transport.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_history_local_verifier_amendment_v2.py")


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
                PROTOCOL_AUDIT_PATH,
                PRIOR_RESULT_PATH,
                PRIOR_RESULT_AUDIT_PATH,
                FAILURE_AUDIT_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_inputs() -> tuple[
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryPayloadResultAudit,
    S5BitcoinCoreHistoryVerifierFailureAudit,
]:
    protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5BitcoinCoreHistoryPayloadProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    prior = S5BitcoinCoreHistoryPayloadResult.model_validate_json(
        PRIOR_RESULT_PATH.read_text(encoding="utf-8")
    )
    prior_audit = S5BitcoinCoreHistoryPayloadResultAudit.model_validate_json(
        PRIOR_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    failure = S5BitcoinCoreHistoryVerifierFailureAudit.model_validate_json(
        FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s5_history_protocol(protocol)
        or not audit_s5_history_protocol_audit(protocol_audit)
        or not audit_s5_history_result(prior)
        or not audit_s5_history_result_audit(prior_audit)
        or not audit_verifier_failure(failure)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or prior.protocol_evidence_hash != protocol.protocol_evidence_hash
        or prior_audit.result_evidence_hash != prior.result_evidence_hash
        or failure.result_evidence_hash != prior.result_evidence_hash
        or failure.original_decision != S5_HISTORY_STOP
        or failure.adjudication != S5_VERIFIER_FAILURE_ADJUDICATION
        or failure.successful_clone_process_count != 1
        or failure.additional_network_process_count != 0
        or failure.commit_messages_read != 0
        or failure.author_identities_read != 0
        or failure.pull_request_ids_parsed != 0
        or failure.market_values_read != 0
        or failure.returns_calculated != 0
        or failure.orders_submitted != 0
    )
    if changed:
        raise ValueError("S5 local-verifier amendment lineage changed")
    return protocol, prior, prior_audit, failure


def build_amendment(*, frozen_at: datetime) -> S5BitcoinCoreHistoryLocalVerifierAmendmentV2:
    protocol, prior, prior_audit, failure = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "prior_result_evidence_hash": prior.result_evidence_hash,
        "prior_result_audit_evidence_hash": prior_audit.audit_evidence_hash,
        "failure_audit_evidence_hash": failure.audit_evidence_hash,
        "source_bindings": bindings(),
        "limitations": tuple(
            sorted(
                (
                    "The v1 STOP result and its verifier failure remain immutable.",
                    "The v1 clone succeeded once; this amendment permits no clone, fetch, or other "
                    "network process.",
                    "Only the existing preserved partial dataset may be revalidated.",
                    "The corrected object stream accepts question-mark-prefixed promised missing "
                    "blob identifiers and hashes every line incrementally.",
                    "The source cutoff, fourteen gate identifiers, and all byte limits remain "
                    "unchanged.",
                    "No commit message, author identity, timestamp, or pull-request identifier may "
                    "be read.",
                    "A successful v2 result can authorize only a separately frozen completeness "
                    "census protocol.",
                    "No GitHub API request, BTC market value, parameter, return, candidate, "
                    "signal, or order is permitted.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority is created.",
                    "A timeout, malformed identifier, changed manifest, changed cutoff, or changed "
                    "Git metadata fails the amendment without another correction.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_construct(
        **payload, amendment_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"amendment_evidence_hash"})
    )
    return S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate(complete)


def write_atomic(path: Path, amendment: S5BitcoinCoreHistoryLocalVerifierAmendmentV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 verifier amendment: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 verifier-amendment transaction exists: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate_json(serialized) != amendment:
        raise ValueError("S5 verifier amendment did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S5 verifier amendment v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_amendment(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 verifier amendment changed")
            print(f"PASS {stored.amendment_evidence_hash}")
            return 0
        amendment = build_amendment(frozen_at=datetime.now(UTC))
        write_atomic(args.output, amendment)
        print(
            f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
            "additional_network=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
