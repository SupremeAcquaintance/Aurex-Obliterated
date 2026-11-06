from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessGateSpec,
    StrategyFactoryReadinessProtocol,
    audit_readiness_protocol,
    build_readiness_protocol,
    file_sha256,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/aurex_strategy_factory_readiness_protocol_v1.json"
)


def gate(
    gate_id: str,
    domain: str,
    requirement: str,
    *,
    research: bool = True,
    paper: bool = True,
    sandbox: bool = True,
    live: bool = True,
) -> StrategyFactoryReadinessGateSpec:
    return StrategyFactoryReadinessGateSpec(
        gate_id=gate_id,
        domain=domain,
        requirement=requirement,
        required_for_research=research,
        required_for_paper=paper,
        required_for_sandbox_strategy_use=sandbox,
        required_for_live=live,
    )


def gate_specs() -> list[StrategyFactoryReadinessGateSpec]:
    return [
        gate(
            "CANONICAL_PROGRAM_TRUTH",
            "governance",
            "One canonical checkpoint must state current strategy, authority, and profit truth.",
        ),
        gate(
            "IMMUTABLE_EVIDENCE_INTEGRITY",
            "evidence",
            "Protocols, results, audits, and ledgers must be schema-validated and hash-bound.",
        ),
        gate(
            "MARKET_DATA_LINEAGE_AND_QUALITY",
            "market_data",
            "Historical inputs must have source identity, continuity, quality, "
            "and no-synthesis controls.",
        ),
        gate(
            "CONTAMINATION_AND_PARTITION_ISOLATION",
            "research_governance",
            "Consumed periods and retired lineages must be immutable and "
            "development/validation/holdout roles isolated.",
        ),
        gate(
            "PREREGISTRATION_BEFORE_OUTCOMES",
            "research_governance",
            "A durable protocol must be committed before any candidate outcome is recorded.",
        ),
        gate(
            "DETERMINISTIC_REPLAY_AND_RECONCILIATION",
            "backtesting",
            "Replays and audits must reproduce trades, metrics, and decisions deterministically.",
        ),
        gate(
            "UNIVERSAL_COST_STRESS_AND_INFERENCE",
            "backtesting",
            "Every future candidate promotion contract must require cost stress, "
            "uncertainty, multiplicity, concentration, regime, and chronological "
            "evidence.",
        ),
        gate(
            "CANDIDATE_LIFECYCLE_AND_RETIREMENT",
            "strategy_lifecycle",
            "Lifecycle state must be machine-enforced so retired or quarantined "
            "strategies cannot be re-enabled or promoted.",
        ),
        gate(
            "FAIL_CLOSED_PAPER_PROMOTION",
            "promotion",
            "Paper execution must require accepted protocol-bound evidence and "
            "matching signal provenance.",
        ),
        gate(
            "AUTHENTICATED_SIGNAL_DELIVERY",
            "signals",
            "Webhook authentication, exact-body evidence, idempotency, and one "
            "genuine external safe-rejection proof must exist.",
            research=False,
        ),
        gate(
            "EVIDENCE_GRADE_PAPER_EXECUTION",
            "paper_execution",
            "Paper fills, costs, positions, PnL, and imported evidence must "
            "reconcile under explicit assumptions.",
        ),
        gate(
            "RISK_LIMITS_AND_KILL_SWITCH",
            "risk",
            "Position sizing, account/session limits, stale-signal rejection, "
            "and durable kill controls must fail closed.",
        ),
        gate(
            "EXCHANGE_SANDBOX_QUALIFICATION",
            "sandbox_execution",
            "Authenticated order, fill, fee, balance, stream, restart, "
            "idempotency, and soak evidence must be independently reconciled.",
        ),
        gate(
            "LIVE_EXECUTION_ISOLATION",
            "capital_protection",
            "Production execution must remain unavailable until a separately "
            "implemented adapter, evidence gates, and explicit approval pass.",
        ),
        gate(
            "OPERATOR_READINESS_VISIBILITY",
            "operator_ui",
            "The API and UI must expose current platform readiness, blockers, "
            "authority, and next action without stale hard-coded strategy claims.",
        ),
    ]


def builder_contract_hash() -> str:
    paths = [
        PROJECT_ROOT / "scripts/freeze_strategy_factory_readiness_protocol.py",
        PROJECT_ROOT
        / "src/aurex/backtest_engine/strategy_factory_readiness.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
                for path in paths
            }
        }
    )


def authoritative_protocol(frozen_at: datetime) -> StrategyFactoryReadinessProtocol:
    return build_readiness_protocol(
        frozen_at=frozen_at,
        authorization_record=(
            "User instructed Aurex to continue with finesse while remaining grounded "
            "in truth, facts, and reality after selecting Readiness Closure as the "
            "next stage."
        ),
        purpose=(
            "Determine whether Aurex is a reusable, fail-closed strategy research "
            "factory before any new strategy mechanism is designed."
        ),
        source_scope=[
            "apps/frontend",
            "data/evidence",
            "docs/00_AUREX_MASTER_PLAN.md",
            "docs/10_PROJECT_CONTROL.md",
            "src/aurex",
            "tests",
        ],
        gate_specs=gate_specs(),
        limitations=[
            "Code presence is capability evidence, not proof of profitable operation.",
            "External TradingView delivery remains unproven until genuine evidence exists.",
            "No readiness score can create or imply a profitable strategy.",
            "Production legality, account verification, and real-capital approval "
            "remain external blockers.",
            "The audit may inspect source and existing evidence but may not open a market outcome.",
        ],
        builder_contract_hash=builder_contract_hash(),
    )


def write_protocol(
    output: Path,
    protocol: StrategyFactoryReadinessProtocol,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if StrategyFactoryReadinessProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Strategy-factory readiness protocol did not round-trip")
    temporary = output.with_name(f"{output.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional protocol exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(output)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Aurex strategy-factory readiness protocol."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            existing = StrategyFactoryReadinessProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_protocol(existing.frozen_at)
            if existing != expected or not audit_readiness_protocol(existing):
                raise ValueError("Strategy-factory readiness protocol changed")
            protocol = existing
        else:
            if args.output.exists():
                raise ValueError(
                    f"Strategy-factory readiness protocol exists: {args.output}"
                )
            protocol = authoritative_protocol(datetime.now(UTC))
            write_protocol(args.output, protocol)
        print(
            f"PASS readiness_protocol={protocol.protocol_evidence_hash} "
            f"gates={len(protocol.gate_specs)} market_values=0 strategies=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
