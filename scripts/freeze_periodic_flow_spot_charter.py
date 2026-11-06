from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.contamination import (  # noqa: E402
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.periodic_flow_spot_charter import (  # noqa: E402
    PERIODIC_FLOW_BINDING_PATHS,
    PERIODIC_FLOW_FEASIBILITY_GATES,
    PeriodicFlowEvidenceBinding,
    PeriodicFlowMechanism,
    PeriodicFlowOperatorScope,
    PeriodicFlowPartition,
    PeriodicFlowResearchSource,
    PeriodicFlowSpotCharter,
    audit_periodic_flow_spot_charter,
)
from aurex.backtest_engine.research_sandbox_capability_profile import (  # noqa: E402
    BinanceSpotTestnetSandboxProfile,
    audit_binance_spot_testnet_sandbox_profile,
)
from aurex.backtest_engine.strategy_factory_contract import (  # noqa: E402
    StrategyFactoryContract,
    audit_strategy_factory_contract,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/periodic_flow_spot_charter_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_spot_charter.py")
SCRIPT_PATH = Path("scripts/freeze_periodic_flow_spot_charter.py")

BINDING_SPECS = {
    "data/evidence/aurex_strategy_factory_contract_v1.json": (
        "contract_evidence_hash",
        "FROZEN_PRE_CANDIDATE",
    ),
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v3.json": (
        "audit_evidence_hash",
        "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY",
    ),
    "data/evidence/aurex_strategy_factory_readiness_current_result_v3.json": (
        "result_evidence_hash",
        "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY",
    ),
    "data/evidence/binance_spot_testnet_sandbox_profile_v1.json": (
        "profile_evidence_hash",
        "AUTHORIZE_SANDBOX_ADAPTER_IMPLEMENTATION_AND_SUCCESSOR_CHARTER_DESIGN_ONLY",
    ),
    "data/evidence/jam_successor_development_outcome_result_v1.json": (
        "result_evidence_hash",
        "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED",
    ),
    "data/evidence/strategy_contamination_ledger_v2.json": (
        "ledger_evidence_hash",
        "APPEND_ONLY_CONTAMINATION_LEDGER_VALID",
    ),
    "data/evidence/v3_mechanism_discovery_charter_v1.json": (
        "charter_evidence_hash",
        "FROZEN_PRE_V3_PROPOSAL_SCREEN",
    ),
    "data/evidence/v3_mechanism_feasibility_screen_v1.json": (
        "screen_evidence_hash",
        "SELECT_ZERO_V3_PRIMARY_MECHANISMS",
    ),
    "data/evidence/v3_mechanism_proposal_register_v1.json": (
        "register_evidence_hash",
        "FREEZE_THREE_PROPOSALS_FOR_NO_RETURN_FEASIBILITY_AUDIT",
    ),
    "data/evidence/v3_p02_aggtrades_census_result_v1.json": (
        "result_evidence_hash",
        "PERMIT_SEPARATE_V3P02_AGGTRADES_PILOT_PROTOCOL",
    ),
    "data/evidence/v3_p02_payload_pilot_stop_result_v1.json": (
        "result_evidence_hash",
        "STOP_V3P02_TRANSPORT_UNRESOLVED_NO_RETRY_NO_SELECTION",
    ),
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def load_json(relative_path: str) -> dict:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def validate_typed_predecessors() -> None:
    contract = StrategyFactoryContract.model_validate(
        load_json("data/evidence/aurex_strategy_factory_contract_v1.json")
    )
    if (
        not audit_strategy_factory_contract(contract)
        or contract.status != "FROZEN_PRE_CANDIDATE"
        or contract.paper_authority_granted
        or contract.live_authority_granted
    ):
        raise ValueError("Q1 requires the intact non-authorizing factory contract")

    result = StrategyFactoryReadinessResult.model_validate(
        load_json(
            "data/evidence/aurex_strategy_factory_readiness_current_result_v3.json"
        )
    )
    audit = StrategyFactoryReadinessAudit.model_validate(
        load_json(
            "data/evidence/aurex_strategy_factory_readiness_current_audit_v3.json"
        )
    )
    if (
        not audit_readiness_result(result)
        or not audit_readiness_audit(audit)
        or audit.result_evidence_hash != result.result_evidence_hash
        or not result.strategy_research_ready
        or result.next_action != "DESIGN_ONE_NEW_UNRELATED_MECHANISM_CHARTER_ONLY"
        or result.paper_operation_ready
        or result.live_ready
    ):
        raise ValueError("Q1 requires the independently audited readiness decision")

    profile = BinanceSpotTestnetSandboxProfile.model_validate(
        load_json("data/evidence/binance_spot_testnet_sandbox_profile_v1.json")
    )
    if (
        not audit_binance_spot_testnet_sandbox_profile(profile)
        or profile.operator_input.permitted_product_scope != "SPOT_ONLY"
        or profile.operator_input.permitted_symbols != ["BTCUSDT"]
        or profile.operator_input.maximum_effective_leverage != 1
        or profile.operator_input.paid_data_permitted
        or profile.production_account_authorized
        or profile.real_capital_authorized
    ):
        raise ValueError("Q1 requires the BTCUSDT Spot-only sandbox profile")

    ledger = StrategyContaminationLedger.model_validate(
        load_json("data/evidence/strategy_contamination_ledger_v2.json")
    )
    if not audit_contamination_ledger(ledger):
        raise ValueError("Q1 requires the intact contamination ledger")


def evidence_decision(path: str, payload: dict) -> str:
    if path.endswith("aurex_strategy_factory_contract_v1.json"):
        return str(payload["status"])
    if path.endswith("strategy_contamination_ledger_v2.json"):
        return "APPEND_ONLY_CONTAMINATION_LEDGER_VALID"
    if path.endswith("v3_mechanism_discovery_charter_v1.json"):
        return str(payload["status"])
    return str(payload["decision"])


def predecessor_bindings() -> tuple[PeriodicFlowEvidenceBinding, ...]:
    bindings = []
    for path in PERIODIC_FLOW_BINDING_PATHS:
        payload = load_json(path)
        evidence_field, expected_decision = BINDING_SPECS[path]
        decision = evidence_decision(path, payload)
        if decision != expected_decision:
            raise ValueError(f"Q1 predecessor decision changed: {path}")
        bindings.append(
            PeriodicFlowEvidenceBinding(
                path=path,
                file_sha256=file_sha256(PROJECT_ROOT / path),
                evidence_hash=str(payload[evidence_field]),
                decision=decision,
            )
        )
    return tuple(bindings)


def research_sources() -> tuple[PeriodicFlowResearchSource, ...]:
    return (
        PeriodicFlowResearchSource(
            source_id="BINANCE-PUBLIC-DATA",
            source_type="OFFICIAL_EXCHANGE_DOCUMENTATION",
            title="Binance Public Data",
            reference="https://github.com/binance/binance-public-data",
            bounded_claims=(
                "Official daily and monthly Spot and USD-M Futures archives are public.",
                "Aggregate trades expose exchange-native timestamps and buyer-maker identity.",
                "Archive checksum companions exist and archived files may later be revised.",
            ),
        ),
        PeriodicFlowResearchSource(
            source_id="HANSEN-KIM-KIMBROUGH-2024",
            source_type="PEER_REVIEWED_RESEARCH",
            title="Periodicity in Cryptocurrency Volatility and Liquidity",
            reference="https://doi.org/10.1093/jjfinec/nbac034",
            bounded_claims=(
                "Bitcoin and Ether show recurrent within-hour volatility and volume patterns.",
                "The documented periodicity is consistent with algorithmic activity "
                "and funding times.",
                "Activity periodicity alone does not establish positive after-cost returns.",
            ),
        ),
        PeriodicFlowResearchSource(
            source_id="KIM-HANSEN-2026",
            source_type="RESEARCH_PREPRINT",
            title=(
                "The Quarter-Hour Effect: Periodic Algorithmic Trading and Return "
                "Predictability in Cryptocurrency Futures"
            ),
            reference="https://arxiv.org/abs/2607.09426",
            bounded_claims=(
                "Perpetual-market activity clusters at one-, five-, and fifteen-minute boundaries.",
                "The paper reports that quarter-hour opening order imbalance forecasts "
                "four-to-twelve-hour returns.",
                "The result is external preprint evidence and must be independently "
                "falsified by Aurex.",
            ),
        ),
        PeriodicFlowResearchSource(
            source_id="WEN-BOURI-XU-ZHAO-2022",
            source_type="PEER_REVIEWED_RESEARCH",
            title=(
                "Intraday return predictability in the cryptocurrency markets: "
                "Momentum, reversal, or both"
            ),
            reference="https://doi.org/10.1016/j.najef.2022.101733",
            bounded_claims=(
                "Intraday crypto predictability can exhibit both momentum and reversal.",
                "Liquidity, jumps, macro events, and regimes can change the sign or strength.",
                "Aurex must freeze one direction and reject regime-dependent rescue "
                "after outcomes.",
            ),
        ),
    )


def mechanism() -> PeriodicFlowMechanism:
    return PeriodicFlowMechanism(
        causal_actor=(
            "Scheduled and algorithmic participants concentrating aggressive USD-M "
            "perpetual orders at recurring UTC quarter-hour boundaries."
        ),
        economic_premise=(
            "A concentrated burst of aggressive perpetual buying can reveal information "
            "or urgent demand before that pressure is fully incorporated into BTC spot "
            "over a slower multi-hour horizon."
        ),
        ex_ante_direction=(
            "Only positive, causally completed perpetual order-flow imbalance may later "
            "qualify a BTCUSDT spot-long decision; negative imbalance means cash, never a short."
        ),
        who_pays=(
            "Immediacy-demanding and mechanically scheduled traders pay market impact; "
            "slower cross-market assimilation is the proposed source of compensation."
        ),
        persistence_case=(
            "UTC scheduling and institutional execution constraints can recur, while a "
            "multi-hour expression is slower than latency arbitrage. Competition, venue "
            "maturation, and regime changes may erase the effect completely."
        ),
        decay_and_failure_risks=(
            "the external result may not replicate on BTCUSDT spot after fees",
            "the effect may be contemporaneous impact rather than forward information",
            "quarter-hour participation and direction may change across regimes",
            "a one-minute archive may be too coarse to isolate the causal opening burst",
            "full taker fees and adverse slippage may dominate gross movement",
            "signal overlap with momentum may make the mechanism non-independent",
        ),
        falsifiable_predictions=(
            "positive opening-window imbalance has positive net spot expectancy in development",
            "the moving-block bootstrap expectancy lower bound is above zero",
            "the result survives 1.5x and 2.0x trade-level cost stress",
            "walk-forward and regime gates pass without selecting a sign or horizon afterward",
            "validation passes before the one-shot future holdout is opened",
            "profit is not concentrated in one day, month, or market regime",
        ),
        required_input_families=(
            "BINANCE_USDM_BTCUSDT_AGGTRADES",
            "BINANCE_SPOT_BTCUSDT_AGGTRADES_OR_1M_KLINES_FOR_EXECUTION",
            "EXCHANGE_NATIVE_ARCHIVE_CHECKSUMS_AND_REVISION_RECORDS",
            "POINT_IN_TIME_SPOT_FILTERS_AND_CONSERVATIVE_TAKER_COSTS",
        ),
        observation_boundary=(
            "A later protocol must choose one UTC quarter-hour observation duration, "
            "one imbalance normalization, one positive threshold, and one holding horizon "
            "before reading development outcomes. The decision occurs only after every "
            "trade in the observation window is available."
        ),
        execution_expression=(
            "Future research may model a taker BTCUSDT Spot buy after the causal signal "
            "window and a taker Spot exit at one frozen horizon. No perpetual order, "
            "short, borrow, leverage, maker fill, or Testnet performance claim is permitted."
        ),
    )


def partitions() -> tuple[PeriodicFlowPartition, ...]:
    return (
        PeriodicFlowPartition(
            partition_id="Q1-DEVELOPMENT-2020-2023",
            start=datetime(2020, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 1, tzinfo=UTC),
            role="DEVELOPMENT",
            state="CLOSED_PENDING_SEPARATE_PROTOCOL",
            purpose=(
                "Feature arithmetic and one parameter set may be falsified here only "
                "after metadata, payload, quality, and execution protocols pass."
            ),
        ),
        PeriodicFlowPartition(
            partition_id="Q1-VALIDATION-2024-2025",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, tzinfo=UTC),
            role="VALIDATION",
            state="SEALED",
            purpose="Untouched Q1 validation opened only after every development gate passes.",
        ),
        PeriodicFlowPartition(
            partition_id="Q1-EXCLUDED-2026-PRECHARTER",
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 8, 7, tzinfo=UTC),
            role="EXCLUDED_WASHOUT",
            state="EXCLUDED_FROM_ALL_SELECTION_AND_SCORING",
            purpose=(
                "Exclude the pre-charter 2026 interval because current-market observation "
                "and prior Aurex work make it unsuitable as a clean Q1 holdout."
            ),
        ),
        PeriodicFlowPartition(
            partition_id="Q1-HOLDOUT-2026-08-07-2026-11-07",
            start=datetime(2026, 8, 7, tzinfo=UTC),
            end=datetime(2026, 11, 7, tzinfo=UTC),
            role="HOLDOUT",
            state="SEALED_FUTURE",
            purpose=(
                "One-shot future holdout. It remains sealed until development and "
                "validation independently pass the universal factory contract."
            ),
        ),
        PeriodicFlowPartition(
            partition_id="Q1-FORWARD-2026-11-07",
            start=datetime(2026, 11, 7, tzinfo=UTC),
            end=None,
            role="FORWARD",
            state="LOCKED_FORWARD",
            purpose=(
                "Potential forward paper evidence only after a passing one-shot holdout "
                "and a separate promotion decision."
            ),
        ),
    )


def build_charter(*, frozen_at: datetime) -> PeriodicFlowSpotCharter:
    validate_typed_predecessors()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": source_contract_hash(),
        "predecessor_bindings": predecessor_bindings(),
        "research_sources": research_sources(),
        "operator_scope": PeriodicFlowOperatorScope(),
        "mechanism": mechanism(),
        "partitions": partitions(),
        "feasibility_gates": PERIODIC_FLOW_FEASIBILITY_GATES,
        "limitations": (
            "External research motivates a falsifiable mechanism; it is not Aurex edge evidence.",
            "The V3P02 transport stop and prior proposal remain immutable and count "
            "in multiplicity.",
            "The charter authorizes metadata and checksum census design only, not a "
            "network attempt.",
            "No archive payload, price, signal, return, parameter, candidate, or "
            "strategy was created.",
            "Pine cannot reproduce exchange-native perpetual aggressor flow exactly.",
            "Testnet fills and zero commissions cannot establish real-market expectancy.",
            "Production account, legal, tax, live, and real-capital facts remain unresolved.",
        ),
    }
    provisional = PeriodicFlowSpotCharter.model_construct(
        **payload,
        charter_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["charter_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"charter_evidence_hash"})
    )
    return PeriodicFlowSpotCharter.model_validate(complete)


def write_charter(path: Path, charter: PeriodicFlowSpotCharter) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = charter.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSpotCharter.model_validate_json(serialized) != charter:
        raise ValueError("Q1 charter did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 charter transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Q1 periodic-flow Spot charter."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSpotCharter.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_charter(frozen_at=stored.frozen_at)
            if stored != expected or not audit_periodic_flow_spot_charter(stored):
                raise ValueError("Stored Q1 charter differs from its reconstruction")
            print(f"PASS {args.output} {stored.charter_evidence_hash}", flush=True)
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite frozen Q1 charter: {args.output}")
        charter = build_charter(frozen_at=datetime.now(UTC))
        write_charter(args.output, charter)
        print(
            f"FROZEN {args.output} {charter.charter_evidence_hash} "
            "market_values=0 returns=0 candidates=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
