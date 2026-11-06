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
from aurex.backtest_engine.s5_bitcoin_core_source_feasibility import (  # noqa: E402
    S5_SOURCE_GATE_IDS,
    S5BitcoinCoreSourceFeasibilityProtocol,
    S5FeasibilityBinding,
    S5GitProbeSpec,
    S5RepositoryEndpointSpec,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_source_feasibility_protocol_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_source_feasibility.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_source_feasibility.py")
CHARTER_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_v1.json")
CHARTER_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_audit_v1.json")
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v27.json"
)
READINESS_AUDIT_PATH = Path("data/evidence/aurex_strategy_factory_readiness_current_audit_v27.json")


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
                READINESS_RESULT_PATH,
                READINESS_AUDIT_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def bindings() -> tuple[S5FeasibilityBinding, ...]:
    return tuple(
        S5FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_and_validate_inputs() -> S5BitcoinCoreDevelopmentCharter:
    charter = S5BitcoinCoreDevelopmentCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    charter_audit = S5BitcoinCoreDevelopmentCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
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
        or charter.metadata_protocol_pass_condition_reachable_by_allowed_sources is not True
        or charter.authorizes_public_git_metadata_requests is not True
        or charter.authorizes_github_api_metadata_requests is not True
        or charter.authorizes_repository_history_access is not False
        or charter.authorizes_market_value_access is not False
        or charter.orders_submitted != 0
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
    )
    if changed:
        raise ValueError("S5 source-feasibility predecessor lineage changed")
    return charter


def build_protocol(*, frozen_at: datetime) -> S5BitcoinCoreSourceFeasibilityProtocol:
    charter = load_and_validate_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "source_bindings": bindings(),
        "repository_endpoint": S5RepositoryEndpointSpec(),
        "git_probe": S5GitProbeSpec(),
        "required_gate_ids": S5_SOURCE_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This protocol tests metadata transport and identity only, not "
                    "predictive edge.",
                    "The GitHub repository response can contain incidental current "
                    "aggregate statistics; the raw response is evidence but those "
                    "fields are nonqualifying.",
                    "Only one repository GET and one git ls-remote attempt are permitted.",
                    "No authentication header, token, cookie, API key, or stored "
                    "credential is permitted.",
                    "No clone, fetch, commit history, pull-request history, release "
                    "history, or market data is permitted.",
                    "The API version header is transport metadata and can be rejected "
                    "by GitHub without authorizing an amendment or rerun.",
                    "A successful metadata result authorizes only a separately frozen "
                    "history-payload protocol.",
                    "Any failed mandatory gate retires S5 within this frozen protocol.",
                    "Partial responses and every planned attempt record must survive "
                    "all normal exits.",
                    "A machine-level termination can still interrupt persistence "
                    "despite atomic writes.",
                    "Current ref identities can change after the run and do not prove "
                    "historical availability.",
                    "No repository activity value, BTC market value, parameter, return, "
                    "candidate, signal, order, real capital, or profit is authorized.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreSourceFeasibilityProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5BitcoinCoreSourceFeasibilityProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5BitcoinCoreSourceFeasibilityProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreSourceFeasibilityProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 source-feasibility protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze or check the S5 source-feasibility protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreSourceFeasibilityProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_protocol(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 protocol differs from reconstruction")
            print(f"PASS {stored.protocol_evidence_hash}")
            return 0
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_atomic(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "planned_attempts=2 network=0 history=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
