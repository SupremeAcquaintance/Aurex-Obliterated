from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_development_charter import (  # noqa: E402
    S5BitcoinCoreDevelopmentCharter,
    S5BitcoinCoreDevelopmentCharterAudit,
    audit_s5_charter,
    audit_s5_charter_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5_HISTORY_GATE_IDS,
    S5BitcoinCoreHistoryPayloadProtocol,
    S5HistoryBinding,
    S5HistoryCloneSpec,
)
from aurex.backtest_engine.s5_bitcoin_core_source_feasibility import (  # noqa: E402
    S5_SOURCE_NEXT,
    S5_SOURCE_PASS,
    S5BitcoinCoreSourceFeasibilityProtocol,
    S5BitcoinCoreSourceFeasibilityProtocolAudit,
    S5BitcoinCoreSourceFeasibilityResult,
    S5BitcoinCoreSourceFeasibilityResultAudit,
    audit_s5_source_protocol,
    audit_s5_source_protocol_audit,
    audit_s5_source_result,
    audit_s5_source_result_audit,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_history_payload.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_history_payload.py")
CHARTER_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_v1.json")
CHARTER_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_audit_v1.json")
SOURCE_PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_source_feasibility_protocol_v1.json")
SOURCE_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_source_feasibility_protocol_audit_v1.json"
)
SOURCE_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_source_feasibility_result_v1.json")
SOURCE_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_source_feasibility_result_audit_v1.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v28.json"
)
READINESS_AUDIT_PATH = Path("data/evidence/aurex_strategy_factory_readiness_current_audit_v28.json")


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
                CHARTER_PATH,
                CHARTER_AUDIT_PATH,
                SOURCE_PROTOCOL_PATH,
                SOURCE_PROTOCOL_AUDIT_PATH,
                SOURCE_RESULT_PATH,
                SOURCE_RESULT_AUDIT_PATH,
                READINESS_RESULT_PATH,
                READINESS_AUDIT_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_and_validate_inputs() -> tuple[
    S5BitcoinCoreDevelopmentCharter,
    S5BitcoinCoreSourceFeasibilityResult,
    StrategyFactoryReadinessResult,
]:
    charter = S5BitcoinCoreDevelopmentCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    charter_audit = S5BitcoinCoreDevelopmentCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    source_protocol = S5BitcoinCoreSourceFeasibilityProtocol.model_validate_json(
        SOURCE_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    source_protocol_audit = S5BitcoinCoreSourceFeasibilityProtocolAudit.model_validate_json(
        SOURCE_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    source_result = S5BitcoinCoreSourceFeasibilityResult.model_validate_json(
        SOURCE_RESULT_PATH.read_text(encoding="utf-8")
    )
    source_result_audit = S5BitcoinCoreSourceFeasibilityResultAudit.model_validate_json(
        SOURCE_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s5_charter(charter)
        or not audit_s5_charter_audit(charter_audit)
        or charter_audit.charter_evidence_hash != charter.charter_evidence_hash
        or not audit_s5_source_protocol(source_protocol)
        or not audit_s5_source_protocol_audit(source_protocol_audit)
        or source_protocol_audit.protocol_evidence_hash != source_protocol.protocol_evidence_hash
        or not audit_s5_source_result(source_result)
        or not audit_s5_source_result_audit(source_result_audit)
        or source_result.protocol_evidence_hash != source_protocol.protocol_evidence_hash
        or source_result_audit.result_evidence_hash != source_result.result_evidence_hash
        or source_result.decision != S5_SOURCE_PASS
        or source_result.next_authorization != S5_SOURCE_NEXT
        or source_result.authorizes_history_payload_protocol is not True
        or source_result.authorizes_repository_history_access is not False
        or source_result.btc_market_values_read != 0
        or source_result.parameters_defined != 0
        or source_result.returns_calculated != 0
        or source_result.orders_submitted != 0
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
    )
    if changed:
        raise ValueError("S5 history payload predecessor lineage changed")
    return charter, source_result, readiness


def source_ref(source_result: S5BitcoinCoreSourceFeasibilityResult, ref: str) -> str:
    ref_map = {item.ref: item.object_hash for item in source_result.git_ref_records}
    value = ref_map.get(ref)
    if value is None:
        raise ValueError(f"S5 source feasibility result is missing {ref}")
    return value


def build_protocol(*, frozen_at: datetime) -> S5BitcoinCoreHistoryPayloadProtocol:
    charter, source_result, readiness = load_and_validate_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "source_feasibility_result_evidence_hash": source_result.result_evidence_hash,
        "readiness_v28_result_evidence_hash": readiness.result_evidence_hash,
        "source_bindings": bindings(),
        "clone_spec": S5HistoryCloneSpec(),
        "source_cutoff_commit": source_ref(source_result, "refs/heads/master"),
        "source_v30_tag_object": source_ref(source_result, "refs/tags/v30.0"),
        "required_gate_ids": S5_HISTORY_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This protocol acquires Git commit topology and object identities only; "
                    "it does not test predictive edge.",
                    "The frozen source cutoff excludes every later commit from all future "
                    "analysis, even if the clone incidentally receives a newer master ref.",
                    "Exactly one public git clone process is permitted and no retry is authorized.",
                    "Credential helpers, interactive prompts, authentication tokens, and cookies "
                    "are not permitted.",
                    "The clone is bare, single-branch, tagless, and requests the blob:none partial "
                    "clone filter.",
                    "Git servers may ignore partial-clone filters; the byte ceiling still applies "
                    "and failure preserves the partial dataset.",
                    "Integrity checks may count commits and hash opaque object identifiers but may "
                    "not read messages, authors, timestamps, or pull-request identifiers.",
                    "The v30.0 tag identity is lineage evidence only and is not fetched by this "
                    "tagless clone.",
                    "A PASS authorizes only a separately frozen completeness-census protocol.",
                    "No GitHub REST request, pull-request metadata request, or release metadata "
                    "request is permitted.",
                    "No BTC market value, parameter, return, candidate, signal, paper order, "
                    "Testnet strategy order, production action, or live action is permitted.",
                    "Repository history is inherently outcome-aware and remains "
                    "nonqualifying until a later preregistered chronological design exists.",
                    "A machine-level termination can interrupt result persistence despite atomic "
                    "writes.",
                    "No acquired repository data can establish profitability or justify capital "
                    "deployment.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreHistoryPayloadProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5BitcoinCoreHistoryPayloadProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5BitcoinCoreHistoryPayloadProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 history protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 history protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 history protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S5 history payload protocol.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_protocol(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 history protocol differs from reconstruction")
            print(f"PASS {stored.protocol_evidence_hash}")
            return 0
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_atomic(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "network=0 history=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
