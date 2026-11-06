from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_GATE_IDS,
    S5GitHubPreflightProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_transport import (  # noqa: E402
    S5_GITHUB_TRANSPORT_DECISION,
    S5_GITHUB_TRANSPORT_NEXT,
    S5GitHubTransportDecision,
    S5GitHubTransportDecisionAudit,
    audit_s5_github_transport_decision,
    audit_s5_github_transport_decision_audit,
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

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_preflight_protocol_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_preflight.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_preflight.py")
TRANSPORT_DECISION_PATH = Path("data/evidence/s5_bitcoin_core_github_transport_decision_v1.json")
TRANSPORT_DECISION_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_transport_decision_audit_v1.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v31.json"
)
READINESS_AUDIT_PATH = Path("data/evidence/aurex_strategy_factory_readiness_current_audit_v31.json")


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
                TRANSPORT_DECISION_PATH,
                TRANSPORT_DECISION_AUDIT_PATH,
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
    S5GitHubTransportDecision,
    S5GitHubTransportDecisionAudit,
    StrategyFactoryReadinessResult,
]:
    decision = S5GitHubTransportDecision.model_validate_json(
        TRANSPORT_DECISION_PATH.read_text(encoding="utf-8")
    )
    decision_audit = S5GitHubTransportDecisionAudit.model_validate_json(
        TRANSPORT_DECISION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s5_github_transport_decision(decision)
        or not audit_s5_github_transport_decision_audit(decision_audit)
        or decision_audit.decision_evidence_hash != decision.decision_evidence_hash
        or decision_audit.decision_file_sha256 != file_sha256(TRANSPORT_DECISION_PATH)
        or decision.decision != S5_GITHUB_TRANSPORT_DECISION
        or decision.next_authorization != S5_GITHUB_TRANSPORT_NEXT
        or decision.selected_transport != "REST_LIST_CLOSED_MASTER_PULLS"
        or decision.preflight_request_count != 1
        or decision.authorizes_preflight_protocol_design is not True
        or decision.authorizes_preflight_request_now is not False
        or decision.authorizes_bulk_metadata_acquisition is not False
        or decision.github_api_requests_executed != 0
        or decision.btc_market_values_read != 0
        or decision.returns_calculated != 0
        or decision.orders_submitted != 0
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
    )
    if changed:
        raise ValueError("S5 GitHub preflight predecessor lineage changed")
    return decision, decision_audit, readiness


def build_protocol(*, frozen_at: datetime) -> S5GitHubPreflightProtocol:
    decision, decision_audit, readiness = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "transport_decision_evidence_hash": decision.decision_evidence_hash,
        "transport_decision_audit_evidence_hash": decision_audit.audit_evidence_hash,
        "readiness_v31_result_evidence_hash": readiness.result_evidence_hash,
        "source_bindings": source_bindings(),
        "required_response_headers": (
            "content-type",
            "link",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
            "x-ratelimit-resource",
        ),
        "required_pull_fields": (
            "number",
            "state",
            "created_at",
            "merged_at",
            "merge_commit_sha",
            "base.ref",
            "base.sha",
        ),
        "required_gate_ids": S5_GITHUB_PREFLIGHT_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This protocol authorizes one unauthenticated GitHub request and no retry.",
                    "A transport preflight cannot establish historical source completeness.",
                    "The first closed master pull request can be unmerged and is used only for "
                    "schema validation.",
                    "A current terminal page count can change after the preflight snapshot.",
                    "The Link terminal page is treated as record count only because per_page is "
                    "exactly one.",
                    "A shared unauthenticated IP rate limit may have fewer than 60 requests "
                    "remaining.",
                    "Secondary limits can make later bulk acquisition slower than the hourly "
                    "lower bound.",
                    "The exact response body is preserved for independent local reconstruction.",
                    "No Authorization header, token value, environment proxy, redirect, or retry "
                    "is permitted.",
                    "HTTP, schema, pagination, rate, byte, or timing failure retires S5 without "
                    "rerun.",
                    "No BTC value, parameter, return, candidate, signal, or order is permitted.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority is created.",
                )
            )
        ),
    }
    provisional = S5GitHubPreflightProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5GitHubPreflightProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5GitHubPreflightProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 GitHub preflight protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub preflight protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5GitHubPreflightProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 GitHub preflight protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze or check the S5 GitHub preflight protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubPreflightProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_protocol(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 GitHub preflight protocol changed")
            print(f"PASS {stored.protocol_evidence_hash}")
            return 0
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_atomic(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "requests=0 metadata=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
