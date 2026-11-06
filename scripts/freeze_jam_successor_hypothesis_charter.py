import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.jam_reversal_failure_analysis import (
    JAM_FAILURE_ANALYSIS_ID,
    JamReversalFailureAnalysis,
    audit_jam_reversal_failure_analysis,
)
from aurex.backtest_engine.jam_successor_charter import (
    JAM_SELECTED_PROPOSAL_ID,
    JAM_SUCCESSOR_FEASIBILITY_GATES,
    JAM_SUCCESSOR_FINDINGS_USED,
    JamEvidencePartition,
    JamMechanismProposal,
    JamMechanismSource,
    JamSuccessorHypothesisCharter,
    audit_jam_successor_hypothesis_charter,
    utc_datetime,
)
from aurex.backtest_engine.research_sandbox_capability_profile import (
    BinanceSpotTestnetSandboxProfile,
    audit_binance_spot_testnet_sandbox_profile,
)
from aurex.backtest_engine.universe import universe_evidence_hash

FAILURE_PATH = Path(
    "data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json"
)
LEDGER_PATH = Path("data/evidence/strategy_contamination_ledger_v2.json")
PROFILE_PATH = Path("data/evidence/binance_spot_testnet_sandbox_profile_v1.json")
PHASE2_SOURCE_PATH = Path(
    "data/evidence/binance_spot_testnet_restart_soak_20260731T125305Z.json"
)
PHASE2_AUDIT_PATH = Path(
    "data/evidence/binance_spot_testnet_restart_soak_audit_20260731T125305Z.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_hypothesis_charter_v1.json"
)
EXPECTED_PHASE2_SOURCE_SHA256 = (
    "8481e2da91fd8810f41ebeffdb9dca65f6b6da2e2e678bae0ef92e05e3036e50"
)
EXPECTED_PHASE2_AUDIT_SHA256 = (
    "d23ff2ba31ab39a2a61b2d164f86f527044a4d8d9aafc60cf91f04dbbfab6487"
)
EXPECTED_PHASE2_AUDIT_EVIDENCE_HASH = (
    "0a9a62be2946516be924ffbbe7d1221363de30f648044c363e6c6224b06cfc29"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_inputs() -> tuple[
    JamReversalFailureAnalysis,
    StrategyContaminationLedger,
    BinanceSpotTestnetSandboxProfile,
]:
    failure = JamReversalFailureAnalysis.model_validate_json(
        FAILURE_PATH.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_reversal_failure_analysis(failure)
        or failure.analysis_id != JAM_FAILURE_ANALYSIS_ID
        or failure.next_research_decision
        != "STOP_CURRENT_VERSION_AND_RETURN_TO_PREREGISTERED_HYPOTHESIS_DESIGN"
    ):
        raise ValueError("Jam successor charter requires the frozen failure decision")

    ledger = StrategyContaminationLedger.model_validate_json(
        LEDGER_PATH.read_text(encoding="utf-8")
    )
    if (
        not audit_contamination_ledger(ledger)
        or ledger.ledger_evidence_hash
        != failure.contamination_ledger_evidence_hash
    ):
        raise ValueError("Jam successor charter requires contamination ledger v2")

    profile = BinanceSpotTestnetSandboxProfile.model_validate_json(
        PROFILE_PATH.read_text(encoding="utf-8")
    )
    if (
        not audit_binance_spot_testnet_sandbox_profile(profile)
        or not profile.successor_charter_design_authorized
        or profile.successor_alpha_discovery_authorized
        or profile.real_market_data_import_authorized
        or profile.parameter_definition_authorized
        or profile.return_testing_authorized
    ):
        raise ValueError("Sandbox profile does not permit this design-only charter")

    if file_sha256(PHASE2_SOURCE_PATH) != EXPECTED_PHASE2_SOURCE_SHA256:
        raise ValueError("Phase 2 source file is not the qualified checkpoint")
    if file_sha256(PHASE2_AUDIT_PATH) != EXPECTED_PHASE2_AUDIT_SHA256:
        raise ValueError("Phase 2 audit file is not the qualified checkpoint")
    phase2_audit = json.loads(PHASE2_AUDIT_PATH.read_text(encoding="utf-8"))
    if (
        phase2_audit.get("audit_sha256")
        != EXPECTED_PHASE2_AUDIT_EVIDENCE_HASH
        or phase2_audit.get("decision")
        != "BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED"
        or not phase2_audit.get("adapter_sandbox_qualified")
        or phase2_audit.get("production_authority")
        or phase2_audit.get("live_authority")
    ):
        raise ValueError("Phase 2 audit evidence is not the qualified checkpoint")
    return failure, ledger, profile


def mechanism_sources() -> tuple[JamMechanismSource, ...]:
    return (
        JamMechanismSource(
            source_id="BINANCE-COMMISSION-FAQ",
            source_type="OFFICIAL_EXCHANGE_DOCUMENTATION",
            reference=(
                "https://github.com/binance/binance-spot-api-docs/"
                "blob/master/faqs/commission_faq.md"
            ),
            bounded_use=(
                "Commission is account, symbol, side, and maker/taker dependent; "
                "future execution must query exact rates and cannot assume a discount."
            ),
        ),
        JamMechanismSource(
            source_id="BINANCE-PUBLIC-DATA",
            source_type="OFFICIAL_EXCHANGE_DOCUMENTATION",
            reference=(
                "https://github.com/binance/binance-public-data/blob/master/README.md"
            ),
            bounded_use=(
                "Official spot aggTrades expose price, quantity, timestamp, and "
                "buyer-maker identity; official klines and checksums are available."
            ),
        ),
        JamMechanismSource(
            source_id="BIANCHI-DICKERSON-BABIAK-2022",
            source_type="PEER_REVIEWED_RESEARCH",
            reference="https://doi.org/10.1016/j.jbankfin.2022.106547",
            bounded_use=(
                "Short-term crypto reversal is treated as liquidity provision and "
                "was stronger in lower-activity pairs; this cautions against assuming "
                "a strong BTC-only reversal premium."
            ),
        ),
        JamMechanismSource(
            source_id="BTC-LIQUIDITY-RESILIENCY-2026",
            source_type="PEER_REVIEWED_RESEARCH",
            reference="https://doi.org/10.3390/jrfm19050372",
            bounded_use=(
                "BTCUSDT signed-flow pressure and post-shock resiliency are measurable "
                "within one venue, motivating an event-conditioned flow hypothesis."
            ),
        ),
        JamMechanismSource(
            source_id="BTC-MARKET-EFFICIENCY-2026",
            source_type="PEER_REVIEWED_RESEARCH",
            reference="https://doi.org/10.1016/j.bir.2026.100869",
            bounded_use=(
                "BTC liquidity and efficiency have matured and shock persistence has "
                "weakened; any residual reversal claim requires conservative evidence."
            ),
        ),
    )


def mechanism_proposals() -> tuple[JamMechanismProposal, ...]:
    return (
        JamMechanismProposal(
            proposal_id=JAM_SELECTED_PROPOSAL_ID,
            name="Aggressive sell-flow exhaustion and reclaim",
            mechanism_hypothesis=(
                "A sharp BTCUSDT sell-flow shock can create temporary price impact. "
                "A long opportunity may exist only when aggressive sell imbalance "
                "decays and price reclaims a pre-shock reference, indicating liquidity "
                "resiliency rather than an unconditioned candle reversal."
            ),
            falsifiable_predictions=(
                "Event-conditioned forward returns exceed time-matched unconditional "
                "BTCUSDT returns after conservative full taker costs.",
                "The effect remains positive across separately frozen calendar and "
                "volatility segments rather than one shock cluster.",
                "Price-only wick events without signed-flow exhaustion do not receive "
                "the same hypothesis status.",
                "The mechanism is rejected if official trade-flow data cannot support "
                "stable event identity or sufficient independent observations.",
            ),
            required_inputs=(
                "BINANCE_SPOT_AGGTRADES",
                "BINANCE_SPOT_1M_KLINES_FOR_RECONCILIATION",
            ),
            exact_pine_compatible=False,
            btcusdt_spot_scope_compatible=True,
            historical_fill_identifiable=True,
            decision="SELECT_FOR_FUTURE_CAPABILITY_REVIEW_ONLY",
            reason=(
                "This is the only proposal with a causal microstructure claim, free "
                "official input candidates, conservative taker execution semantics, "
                "and compatibility with the frozen BTCUSDT spot scope."
            ),
        ),
        JamMechanismProposal(
            proposal_id="J2-P02-CANDLE-PARAMETER-RESCUE",
            name="Loosen or retune the existing candle Jam",
            mechanism_hypothesis=(
                "More permissive candle thresholds might increase trade count or "
                "alter realized payoff."
            ),
            falsifiable_predictions=(
                "A changed parameter set would outperform v1.0.1.",
            ),
            required_inputs=("BINANCE_SPOT_15M_KLINES",),
            exact_pine_compatible=True,
            btcusdt_spot_scope_compatible=True,
            historical_fill_identifiable=True,
            decision="REJECT",
            reason=(
                "This is outcome-conditioned parameter rescue on a consumed Jam "
                "window, not a new economic mechanism."
            ),
        ),
        JamMechanismProposal(
            proposal_id="J2-P03-PASSIVE-MAKER-RETEST",
            name="Passive maker entry after a reclaim",
            mechanism_hypothesis=(
                "A resting retest order could improve entry cost after a reclaim."
            ),
            falsifiable_predictions=(
                "Queue-realistic maker fills retain positive expectancy after "
                "adverse-selection and missed-fill costs.",
            ),
            required_inputs=(
                "HISTORICAL_L2_ORDER_BOOK",
                "ORDER_QUEUE_POSITION",
                "BINANCE_SPOT_TRADES",
            ),
            exact_pine_compatible=False,
            btcusdt_spot_scope_compatible=True,
            historical_fill_identifiable=False,
            decision="REJECT",
            reason=(
                "The zero-dollar official history does not identify queue position or "
                "maker fills. Assuming a touch fill would manufacture edge."
            ),
        ),
        JamMechanismProposal(
            proposal_id="J2-P04-LOW-ACTIVITY-CROSS-ASSET-REVERSAL",
            name="Cross-asset reversal in lower-activity spot pairs",
            mechanism_hypothesis=(
                "Liquidity-provision reversal may be stronger in smaller and "
                "lower-activity crypto pairs."
            ),
            falsifiable_predictions=(
                "A preregistered liquid-enough cross-section earns a cost-net reversal "
                "premium without concentration in untradeable assets.",
            ),
            required_inputs=(
                "MULTI_SYMBOL_SPOT_TRADES",
                "MULTI_SYMBOL_LIQUIDITY_AND_LISTING_HISTORY",
            ),
            exact_pine_compatible=False,
            btcusdt_spot_scope_compatible=False,
            historical_fill_identifiable=True,
            decision="DEFER",
            reason=(
                "The literature is relevant, but the frozen operator profile permits "
                "BTCUSDT only. This cannot become an Aurex executable candidate now."
            ),
        ),
    )


def evidence_partitions() -> tuple[JamEvidencePartition, ...]:
    return (
        JamEvidencePartition(
            partition_id="JAM-V1-CONSUMED-2023-2025",
            start=utc_datetime(2023, 2, 1),
            end=utc_datetime(2026, 1, 1),
            source_types=("BINANCE_SPOT_15M_KLINES",),
            state="CONSUMED",
            purpose="Retired v1.0.1 decision period; never use to rescue a successor.",
        ),
        JamEvidencePartition(
            partition_id="JAM-V1-EXPLORATORY-2026",
            start=utc_datetime(2026, 5, 1),
            end=utc_datetime(2026, 7, 21),
            source_types=("TRADINGVIEW_CANDLE_OUTCOMES",),
            state="EXPLORATORY_CONTAMINATED",
            purpose="Outcome-conditioned v1.14 neighborhood probes; not a holdout.",
        ),
        JamEvidencePartition(
            partition_id="JAM-PROVISIONAL-HISTORICAL-POOL-2019-2022",
            start=utc_datetime(2019, 1, 1),
            end=utc_datetime(2023, 1, 1),
            source_types=(
                "BINANCE_SPOT_AGGTRADES",
                "BINANCE_SPOT_1M_KLINES",
            ),
            state="PROVISIONAL_UNOPENED_UNVERIFIED",
            purpose=(
                "Potential successor research pool. Archive availability and prior "
                "access must be proven before any partition role is assigned."
            ),
        ),
        JamEvidencePartition(
            partition_id="JAM-LOCKED-FORWARD-2026-08-01",
            start=utc_datetime(2026, 8, 1),
            end=None,
            source_types=(
                "FUTURE_BINANCE_SPOT_AGGTRADES",
                "FUTURE_BINANCE_SPOT_KLINES",
            ),
            state="LOCKED_FORWARD",
            purpose=(
                "Future-only evidence. It remains inaccessible until historical "
                "qualification and a separate forward protocol exist."
            ),
        ),
    )


def build_charter(
    *,
    frozen_at: datetime,
    failure: JamReversalFailureAnalysis,
    ledger: StrategyContaminationLedger,
    profile: BinanceSpotTestnetSandboxProfile,
) -> JamSuccessorHypothesisCharter:
    payload = {
        "frozen_at": frozen_at,
        "parent_failure_analysis_evidence_hash": failure.analysis_evidence_hash,
        "contamination_ledger_evidence_hash": ledger.ledger_evidence_hash,
        "sandbox_profile_evidence_hash": profile.profile_evidence_hash,
        "phase2_source_file_sha256": EXPECTED_PHASE2_SOURCE_SHA256,
        "phase2_audit_file_sha256": EXPECTED_PHASE2_AUDIT_SHA256,
        "phase2_audit_evidence_hash": EXPECTED_PHASE2_AUDIT_EVIDENCE_HASH,
        "parent_findings_used": JAM_SUCCESSOR_FINDINGS_USED,
        "operator_scope": {
            "environment": "BINANCE_SPOT_TESTNET",
            "product": "SPOT_ONLY",
            "symbols": ["BTCUSDT"],
            "maximum_effective_leverage": "1",
            "simulated_equity_usd": "100",
            "maximum_per_trade_loss_usd": "0.50",
            "maximum_daily_loss_usd": "1.00",
            "maximum_total_loss_usd": "10.00",
            "paid_data_budget_usd": "0",
            "cost_policy": (
                "Use conservative full taker costs until exact account and symbol "
                "commission evidence is frozen; never assume a discount."
            ),
        },
        "evidence_sources": mechanism_sources(),
        "proposals": mechanism_proposals(),
        "evidence_partitions": evidence_partitions(),
        "feasibility_gates": JAM_SUCCESSOR_FEASIBILITY_GATES,
    }
    provisional = JamSuccessorHypothesisCharter.model_construct(
        **payload,
        charter_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["charter_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"charter_evidence_hash"})
    )
    return JamSuccessorHypothesisCharter.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or verify the design-only Jam successor charter."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failure, ledger, profile = load_inputs()
    if args.check:
        stored = JamSuccessorHypothesisCharter.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_charter(
            frozen_at=stored.frozen_at,
            failure=failure,
            ledger=ledger,
            profile=profile,
        )
        if not audit_jam_successor_hypothesis_charter(stored):
            raise SystemExit("Stored Jam successor charter failed its hash audit")
        if stored != expected:
            raise SystemExit("Stored Jam successor charter differs from its rebuild")
        print(f"PASS {stored.charter_evidence_hash}")
        return 0

    if args.output.exists():
        raise SystemExit("Refusing to overwrite the frozen Jam successor charter")
    frozen = build_charter(
        frozen_at=datetime.now(UTC),
        failure=failure,
        ledger=ledger,
        profile=profile,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(frozen.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"FROZEN {args.output} {frozen.charter_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
