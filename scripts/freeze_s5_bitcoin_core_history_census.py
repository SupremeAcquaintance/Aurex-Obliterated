from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5_CENSUS_GATE_IDS,
    S5BitcoinCoreHistoryCensusProtocol,
    S5PullRequestMessagePattern,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5_HISTORY_NEXT,
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadResultAuditV2,
    S5BitcoinCoreHistoryPayloadResultV2,
    audit_s5_history_result_audit_v2,
    audit_s5_history_result_v2,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_census_protocol_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_history_census.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_history_census.py")
HISTORY_PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
HISTORY_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_protocol_audit_v1.json"
)
HISTORY_RESULT_V1_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
HISTORY_RESULT_AUDIT_V1_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_audit_v1.json"
)
HISTORY_FAILURE_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_verifier_failure_audit_v1.json"
)
HISTORY_AMENDMENT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_local_verifier_amendment_v2.json"
)
HISTORY_AMENDMENT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_local_verifier_amendment_audit_v2.json"
)
HISTORY_RESULT_V2_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v2.json")
HISTORY_RESULT_AUDIT_V2_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_audit_v2.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v29.json"
)
READINESS_AUDIT_PATH = Path("data/evidence/aurex_strategy_factory_readiness_current_audit_v29.json")


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
                HISTORY_PROTOCOL_PATH,
                HISTORY_PROTOCOL_AUDIT_PATH,
                HISTORY_RESULT_V1_PATH,
                HISTORY_RESULT_AUDIT_V1_PATH,
                HISTORY_FAILURE_AUDIT_PATH,
                HISTORY_AMENDMENT_PATH,
                HISTORY_AMENDMENT_AUDIT_PATH,
                HISTORY_RESULT_V2_PATH,
                HISTORY_RESULT_AUDIT_V2_PATH,
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


def dataset_manifest_valid(result: S5BitcoinCoreHistoryPayloadResultV2) -> bool:
    root = PROJECT_ROOT / result.dataset_path
    if not root.is_dir():
        return False
    records = {item.relative_path: item for item in result.dataset_file_manifest}
    files = tuple(path for path in root.rglob("*") if path.is_file() and not path.is_symlink())
    return (
        len(records) == result.dataset_file_count == len(files)
        and all(
            (relative := path.relative_to(root).as_posix()) in records
            and path.stat().st_size == records[relative].byte_count
            and sha256(path.read_bytes()).hexdigest() == records[relative].file_sha256
            for path in files
        )
        and universe_evidence_hash(
            [item.model_dump(mode="json") for item in result.dataset_file_manifest]
        )
        == result.dataset_directory_sha256
    )


def load_inputs() -> tuple[
    S5BitcoinCoreHistoryPayloadResultV2,
    S5BitcoinCoreHistoryPayloadResultAuditV2,
    StrategyFactoryReadinessResult,
]:
    result = S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(
        HISTORY_RESULT_V2_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate_json(
        HISTORY_RESULT_AUDIT_V2_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s5_history_result_v2(result)
        or not audit_s5_history_result_audit_v2(result_audit)
        or result_audit.result_evidence_hash != result.result_evidence_hash
        or result.next_authorization != S5_HISTORY_NEXT
        or result.authorizes_history_completeness_census_protocol is not True
        or result.authorizes_history_semantic_parsing is not False
        or result.btc_market_values_read != 0
        or result.parameters_defined != 0
        or result.returns_calculated != 0
        or result.orders_submitted != 0
        or not dataset_manifest_valid(result)
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
    )
    if changed:
        raise ValueError("S5 history census predecessor lineage changed")
    return result, result_audit, readiness


def message_patterns() -> tuple[S5PullRequestMessagePattern, ...]:
    return (
        S5PullRequestMessagePattern(
            pattern_id="BITCOIN_CORE_MAINTAINER_MERGE",
            regular_expression=r"^Merge bitcoin/bitcoin#([1-9][0-9]*):(?: |$)",
        ),
        S5PullRequestMessagePattern(
            pattern_id="GITHUB_DEFAULT_PULL_MERGE",
            regular_expression=r"^Merge pull request #([1-9][0-9]*) from .+$",
        ),
    )


def build_protocol(*, frozen_at: datetime) -> S5BitcoinCoreHistoryCensusProtocol:
    history, history_audit, readiness = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "history_result_evidence_hash": history.result_evidence_hash,
        "history_result_audit_evidence_hash": history_audit.audit_evidence_hash,
        "readiness_v29_result_evidence_hash": readiness.result_evidence_hash,
        "source_bindings": bindings(),
        "dataset_directory_sha256": history.dataset_directory_sha256,
        "source_cutoff_commit": history.source_cutoff_commit,
        "maximum_reachable_commit_count": history.cutoff_commit_count,
        "message_patterns": message_patterns(),
        "required_gate_ids": S5_CENSUS_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This census inventories source structure only and cannot establish predictive "
                    "edge.",
                    "Only commits on master first-parent ancestry through the frozen cutoff are "
                    "included.",
                    "Pull-request IDs are recognized only from two patterns frozen before message "
                    "access.",
                    "Unrecognized merges are counted and only the first 25 first lines may be "
                    "persisted for source diagnosis.",
                    "Raw commit objects contain incidental author and committer headers; the "
                    "parser must skip rather than decode or persist them.",
                    "Git commit and committer timestamps do not prove first public availability "
                    "and are not parsed in this census.",
                    "Recognized pull-request references do not prove that GitHub retains complete "
                    "historical metadata.",
                    "The exact direct endpoint budget is one request per distinct recognized pull "
                    "request; list-endpoint pages are only a lower bound.",
                    "No network, fetch, GitHub API call, credential, or repository mutation is "
                    "permitted.",
                    "No BTC market value, parameter, return, candidate, signal, or order is "
                    "permitted.",
                    "A PASS authorizes only a metadata transport decision, not metadata access.",
                    "Source completeness remains explicitly unadjudicated after this census.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority is created.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreHistoryCensusProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5BitcoinCoreHistoryCensusProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5BitcoinCoreHistoryCensusProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 census protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 census protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryCensusProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 census protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S5 history census protocol.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreHistoryCensusProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_protocol(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 census protocol differs from reconstruction")
            print(f"PASS {stored.protocol_evidence_hash}")
            return 0
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_atomic(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "local_git=0 commits=0 github_requests=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
