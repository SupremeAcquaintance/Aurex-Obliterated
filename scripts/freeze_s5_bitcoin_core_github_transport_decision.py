from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_transport import (  # noqa: E402
    S5_GITHUB_TRANSPORT_GATE_IDS,
    S5GitHubTransportDecision,
    S5GitHubTransportGateResult,
    S5GitHubTransportOption,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5_CENSUS_NEXT,
    S5_CENSUS_PASS,
    S5BitcoinCoreHistoryCensusProtocol,
    S5BitcoinCoreHistoryCensusProtocolAudit,
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
    audit_s5_census_protocol,
    audit_s5_census_protocol_audit,
    audit_s5_census_result,
    audit_s5_census_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_transport_decision_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_transport.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_transport_decision.py")
CENSUS_PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_history_census_protocol_v1.json")
CENSUS_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_protocol_audit_v1.json"
)
CENSUS_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_history_census_result_v1.json")
CENSUS_RESULT_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_census_result_audit_v1.json")
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v30.json"
)
READINESS_AUDIT_PATH = Path("data/evidence/aurex_strategy_factory_readiness_current_audit_v30.json")


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
                CENSUS_PROTOCOL_PATH,
                CENSUS_PROTOCOL_AUDIT_PATH,
                CENSUS_RESULT_PATH,
                CENSUS_RESULT_AUDIT_PATH,
                READINESS_RESULT_PATH,
                READINESS_AUDIT_PATH,
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
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
    StrategyFactoryReadinessResult,
]:
    protocol = S5BitcoinCoreHistoryCensusProtocol.model_validate_json(
        CENSUS_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5BitcoinCoreHistoryCensusProtocolAudit.model_validate_json(
        CENSUS_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5BitcoinCoreHistoryCensusResult.model_validate_json(
        CENSUS_RESULT_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5BitcoinCoreHistoryCensusResultAudit.model_validate_json(
        CENSUS_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s5_census_protocol(protocol)
        or not audit_s5_census_protocol_audit(protocol_audit)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or protocol_audit.protocol_file_sha256 != file_sha256(CENSUS_PROTOCOL_PATH)
        or not audit_s5_census_result(result)
        or not audit_s5_census_result_audit(result_audit)
        or result_audit.result_evidence_hash != result.result_evidence_hash
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.decision != S5_CENSUS_PASS
        or result.next_authorization != S5_CENSUS_NEXT
        or result.distinct_pull_request_count != 7_961
        or result.unrecognized_merge_count != 8_760
        or result.exact_direct_pull_request_count != 7_961
        or result.github_api_requests_executed != 0
        or result.btc_market_values_read != 0
        or result.returns_calculated != 0
        or result.orders_submitted != 0
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
    )
    if changed:
        raise ValueError("S5 GitHub transport predecessor lineage changed")
    return result, result_audit, readiness


def transport_options() -> tuple[S5GitHubTransportOption, ...]:
    return (
        S5GitHubTransportOption(
            option_id="DIRECT_PULL_BY_NUMBER",
            disposition="REJECTED",
            rationale=(
                "The census requires 7,961 requests, at least 133 unauthenticated rate-limit "
                "hours, and still cannot discover PRs missed by merge-message patterns."
            ),
        ),
        S5GitHubTransportOption(
            option_id="REST_LIST_CLOSED_MASTER_PULLS",
            disposition="SELECTED",
            rationale=(
                "The official endpoint supports closed state, master base, deterministic created "
                "ordering, and up to 100 records per page; a one-record preflight can reveal the "
                "terminal page before bulk acquisition is authorized."
            ),
        ),
        S5GitHubTransportOption(
            option_id="GRAPHQL_PULL_REQUEST_PAGINATION",
            disposition="REJECTED",
            rationale=(
                "GitHub GraphQL requires authentication, while no approved token is present and "
                "Aurex has a viable public REST path."
            ),
        ),
        S5GitHubTransportOption(
            option_id="LOCAL_GIT_ONLY",
            disposition="REJECTED",
            rationale=(
                "Git topology cannot prove GitHub public merged_at or recover authoritative "
                "pull-request metadata."
            ),
        ),
        S5GitHubTransportOption(
            option_id="THIRD_PARTY_ARCHIVE",
            disposition="REJECTED",
            rationale=(
                "A third-party archive would weaken source authority and is unnecessary before "
                "the official GitHub path is tested."
            ),
        ),
    )


def gate_results() -> tuple[S5GitHubTransportGateResult, ...]:
    evidence = (
        "The frozen census and readiness-v30 result/audit pairs are hash-bound.",
        "The census fixes 7,961 distinct PRs, 8,760 unresolved merges, and 7,961 direct calls.",
        "GitHub documents pull-list state, base, sort, direction, page, and per_page parameters.",
        "GitHub documents 60 unauthenticated and 5,000 authenticated requests per hour "
        "and 100 records per page.",
        "Direct lookup would take at least 133 unauthenticated limit windows and misses "
        "unknown PRs.",
        "GraphQL is not an unauthenticated public fallback.",
        "Local Git lacks an authoritative GitHub public merge timestamp.",
        "Third-party archives are outside the charter's authoritative source set.",
        "One official page-one request with per_page=1 is sufficient for transport preflight.",
        "The Link terminal page can bound record count before a bulk request budget is frozen.",
        "This decision executed zero network, metadata, market, strategy, or order activity.",
        "A PASS authorizes only a separately frozen one-request preflight protocol.",
    )
    return tuple(
        S5GitHubTransportGateResult(gate_id=gate_id, status="PASS", evidence=message)
        for gate_id, message in zip(S5_GITHUB_TRANSPORT_GATE_IDS, evidence, strict=True)
    )


def build_decision(*, frozen_at: datetime) -> S5GitHubTransportDecision:
    result, result_audit, readiness = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "census_result_evidence_hash": result.result_evidence_hash,
        "census_result_audit_evidence_hash": result_audit.audit_evidence_hash,
        "readiness_v30_result_evidence_hash": readiness.result_evidence_hash,
        "source_bindings": source_bindings(),
        "transport_options": transport_options(),
        "preflight_fields_permitted": (
            "http_status",
            "content_type",
            "link_header",
            "etag_header",
            "x_ratelimit_limit",
            "x_ratelimit_remaining",
            "x_ratelimit_reset",
            "x_ratelimit_resource",
            "pull_number",
            "state",
            "base_ref",
            "created_at",
            "merged_at",
            "merge_commit_sha",
        ),
        "required_gate_ids": S5_GITHUB_TRANSPORT_GATE_IDS,
        "gate_results": gate_results(),
        "limitations": tuple(
            sorted(
                (
                    "The decision relies on current official GitHub API documentation and does "
                    "not execute it.",
                    "A current GitHub snapshot cannot guarantee preservation of deleted "
                    "historical records.",
                    "The selected list endpoint includes closed but unmerged pull requests until "
                    "normalized later.",
                    "Filtering to base master may exclude proposals targeting historical "
                    "non-master branches.",
                    "The one-record preflight proves transport shape only, not full pagination "
                    "completeness.",
                    "The terminal Link page must be observed before any bulk request count is "
                    "authorized.",
                    "Unauthenticated requests share an IP-based rate limit and may have less than "
                    "60 remaining.",
                    "Secondary limits can require slower pacing than the primary hourly limit "
                    "implies.",
                    "No credential or token value is permitted in the decision or preflight "
                    "protocol.",
                    "Pull-request merged_at is platform metadata, not proof of predictive edge.",
                    "Missing or ambiguous merge mappings must fail closed to cash in any later "
                    "candidate.",
                    "No BTC value, parameter, return, candidate, signal, or order is authorized.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority is created.",
                )
            )
        ),
    }
    provisional = S5GitHubTransportDecision.model_construct(
        **payload, decision_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["decision_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"decision_evidence_hash"})
    )
    return S5GitHubTransportDecision.model_validate(complete)


def write_atomic(path: Path, decision: S5GitHubTransportDecision) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 GitHub transport decision: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub transport decision transaction exists: {temporary}")
    serialized = decision.model_dump_json(indent=2) + "\n"
    if S5GitHubTransportDecision.model_validate_json(serialized) != decision:
        raise ValueError("S5 GitHub transport decision did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze or check the S5 GitHub transport decision."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubTransportDecision.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_decision(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 GitHub transport decision changed")
            print(f"PASS {stored.decision_evidence_hash}")
            return 0
        decision = build_decision(frozen_at=datetime.now(UTC))
        write_atomic(args.output, decision)
        print(
            f"FROZEN {args.output} {decision.decision_evidence_hash} "
            f"selected={decision.selected_transport} preflight_requests=1 "
            "network=0 metadata=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
