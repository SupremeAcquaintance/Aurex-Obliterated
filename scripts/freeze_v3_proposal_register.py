import argparse
import hashlib
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposal,
    V3MechanismProposalRegister,
    V3ProposalCoverageContract,
    V3ProposalSource,
    audit_v3_mechanism_proposal_register,
    build_v3_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_CHARTER = Path(
    "data/evidence/v3_mechanism_discovery_charter_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_mechanism_proposal_register_v1.json"
)
TIMESTAMP_EVIDENCE = [
    "archive_identity_and_checksum",
    "boundary_completeness",
    "continuity_gap_count",
    "duplicate_timestamp_count",
    "first_timestamp",
    "last_timestamp",
    "missing_timestamp_count",
    "row_count",
    "schema_identity",
]


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v3_proposal_register.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v3_proposal_register.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def charter_builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v3_discovery_charter.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v3_discovery_charter.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_charter(path: Path) -> V3MechanismDiscoveryCharter:
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_contract_hash()
    ):
        raise ValueError("V3 discovery charter audit failed")
    return charter


def source(
    *,
    accessed_at: datetime,
    source_id: str,
    title: str,
    authors: list[str],
    published: str | None,
    kind: str,
    url: str,
    claims: list[str],
) -> V3ProposalSource:
    return V3ProposalSource(
        source_id=source_id,
        title=title,
        authors_or_publisher=authors,
        publication_or_revision_date=published,
        accessed_at=accessed_at,
        source_kind=kind,
        url=url,
        supported_claims=claims,
    )


def cointegration_proposal(accessed_at: datetime) -> V3MechanismProposal:
    return V3MechanismProposal(
        proposal_id="V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
        mechanism_name=(
            "Cross-asset cointegration relative value with a long spot and "
            "short USD-M perpetual pair"
        ),
        economic_premise=(
            "Some cryptocurrency prices may share a time-varying long-run relation. "
            "A temporary spread displacement can therefore contain a convergence "
            "component distinct from outright market direction. Aurex would express "
            "only the orientation that buys the relatively underpriced asset in cash "
            "spot and shorts the relatively overpriced asset through its USD-M "
            "perpetual, avoiding spot borrowing while retaining cross-asset model, "
            "basis, funding, and collateral risk."
        ),
        ex_ante_payoff_direction=(
            "The paired position can profit only when the frozen spread converges "
            "enough to exceed both-leg fees, spread, adverse execution, funding, "
            "hedge-ratio error, collateral drag, and model-break risk. Cointegration "
            "does not guarantee convergence during the holding window."
        ),
        exact_point_in_time_data_requirements=[
            "one_minute_spot_klines_for_both_candidate_assets",
            "one_minute_usd_m_perpetual_klines_for_both_candidate_assets",
            "one_minute_mark_and_index_klines_for_each_possible_short_leg",
            "settled_funding_events_and_intervals_for_each_possible_short_leg",
            "quote_volume_for_capacity_and_participation_constraints",
        ],
        historical_metadata_requirements=[
            "contract_listing_delisting_and_status_history",
            "dated_spot_and_usd_m_fee_schedule",
            "historical_funding_formula_interval_and_cap_history",
            "point_in_time_spot_and_futures_order_filters",
            "point_in_time_margin_maintenance_and_liquidation_rules",
        ],
        execution_path=(
            "At a later frozen signal time, buy the underpriced asset in cash-funded "
            "spot and short the overvalued asset's USD-M perpetual using a separately "
            "audited cross-asset hedge ratio. Require paired fills, rollback on a "
            "failed leg, isolated collateral, funding settlement, mark-based risk, "
            "capacity limits, kill switches, and deterministic close reconciliation."
        ),
        principal_risks=[
            "cointegration_and_hedge_ratio_breakdown",
            "cross_asset_basis_and_directional_residual",
            "funding_fees_spread_slippage_and_capacity",
            "liquidation_adl_partial_fill_and_rollback",
            "pair_selection_and_multiple_testing",
        ],
        pre_return_falsification_condition=(
            "Reject before primary selection if fewer than twenty symbols satisfy "
            "the frozen synchronized timestamp coverage contract, if historical "
            "funding and execution dependencies cannot be reconstructed, or if "
            "Aurex cannot prove a deterministic long-spot short-cross-asset-perpetual "
            "lifecycle with one predeclared pair-selection and parameter policy."
        ),
        independence_from_blocked_lineages=[
            (
                "The premise is spread stationarity and cross-asset convergence, "
                "not trend, breakout, path quality, broad beta timing, or funding carry."
            ),
            (
                "Funding is modeled only as a cost or receipt on the short leg and "
                "is not the signal or the proposed source of edge."
            ),
        ],
        coverage_contract=V3ProposalCoverageContract(
            required_archive_families=[
                "spot_klines_1m",
                "um_contract_klines_1m",
                "um_funding_rate_events",
                "um_index_price_klines_1m",
                "um_mark_price_klines_1m",
            ],
            supplemental_historical_sources=[],
            timestamp_join_policy=(
                "Exact UTC symbol and one-minute open-time inner join for every "
                "required price family; funding joins only at settled event times."
            ),
            missing_row_policy=(
                "Never fill a missing row. A missing synchronized decision minute is "
                "untradable and skipped; a gap exceeding the frozen maximum resets "
                "formation state and disqualifies the affected calendar month."
            ),
            minimum_total_coverage_fraction=Decimal("0.995"),
            minimum_calendar_month_coverage_fraction=Decimal("0.95"),
            maximum_single_gap_minutes=1440,
            minimum_qualified_symbols=20,
            required_timestamp_evidence=TIMESTAMP_EVIDENCE,
            point_in_time_execution_dependencies=[
                "cross_asset_hedge_ratio_and_residual_risk_engine",
                "funding_settlement_for_short_perpetual_leg",
                "isolated_margin_liquidation_and_adl_model",
                "paired_fill_rollback_and_reconciliation",
                "spot_and_usd_m_filters_fees_and_capacity",
            ],
        ),
        primary_sources=[
            source(
                accessed_at=accessed_at,
                source_id="TADI_WITZANY_2025",
                title="Copula-based trading of cointegrated cryptocurrency pairs",
                authors=["Jiri Witzany", "Masood Tadi"],
                published="2025-01-13",
                kind="PEER_REVIEWED_ARTICLE",
                url="https://link.springer.com/article/10.1186/s40854-024-00702-7",
                claims=[
                    (
                        "Cointegration and copula methods can define relative-value "
                        "relationships among cryptocurrency prices."
                    ),
                    (
                        "Pair formation, ranking, triggers, and transaction costs are "
                        "material parts of an implementable pairs study."
                    ),
                ],
            ),
            source(
                accessed_at=accessed_at,
                source_id="FIGA_TALAMANCA_ET_AL_2021",
                title=(
                    "Common dynamic factors for cryptocurrencies and multiple "
                    "pair-trading statistical arbitrages"
                ),
                authors=[
                    "Gianna Figa-Talamanca",
                    "Marco Patacca",
                    "Sergio Focardi",
                ],
                published="2021-02-05",
                kind="PEER_REVIEWED_ARTICLE",
                url="https://link.springer.com/article/10.1007/s10203-021-00318-x",
                claims=[
                    (
                        "Cryptocurrency prices can exhibit common dynamic factors and "
                        "cointegration relationships."
                    ),
                    (
                        "Relative-value construction remains model-dependent and "
                        "requires explicit multivariate estimation."
                    ),
                ],
            ),
            source(
                accessed_at=accessed_at,
                source_id="KEILBAR_ZHANG_2021",
                title="On cointegration and cryptocurrency dynamics",
                authors=["Georg Keilbar", "Yanfen Zhang"],
                published="2021-02-17",
                kind="PEER_REVIEWED_ARTICLE",
                url="https://link.springer.com/article/10.1007/s42521-021-00027-5",
                claims=[
                    (
                        "Cointegration exposure in cryptocurrency systems can vary "
                        "through time rather than remain fixed."
                    ),
                    (
                        "A dynamic relation cannot be treated as guaranteed terminal "
                        "convergence."
                    ),
                ],
            ),
        ],
        preliminary_execution_fit=(
            "REQUIRES_SEPARATE_CROSS_ASSET_PAIRED_FOUNDATION"
        ),
    )


def clock_phase_proposal(accessed_at: datetime) -> V3MechanismProposal:
    return V3MechanismProposal(
        proposal_id="V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY",
        mechanism_name=(
            "Clock-phase intraday predictability around recurring algorithmic "
            "activity windows"
        ),
        economic_premise=(
            "Continuous cryptocurrency venues can still exhibit recurring bursts in "
            "algorithmic activity, volume, volatility, and serial dependence near "
            "fixed clock boundaries. A strictly preregistered UTC clock-phase rule "
            "could test whether this scheduled activity supplies directional "
            "information after costs, but the documented sign changes across regimes "
            "and may overlap momentum or reversal rather than represent a durable edge."
        ),
        ex_ante_payoff_direction=(
            "A later rule could earn only if the return direction associated with a "
            "predeclared clock phase persists out of sample and exceeds taker costs, "
            "spread, adverse execution, funding, and directional drawdown. Recurring "
            "activity or volatility alone does not imply positive return expectancy."
        ),
        exact_point_in_time_data_requirements=[
            "one_minute_usd_m_perpetual_klines",
            "trade_level_or_aggregate_trade_timestamps_price_quantity_and_side_proxy",
            "utc_clock_phase_without_exchange_local_time_inference",
            "quote_volume_and_trade_count_for_activity_coverage",
        ],
        historical_metadata_requirements=[
            "dated_usd_m_fee_and_funding_schedule",
            "historical_contract_status_and_order_filters",
            "trade_archive_schema_and_side_classification_history",
        ],
        execution_path=(
            "A later separately frozen engine would take a bounded long or short "
            "USD-M perpetual position only at a predeclared UTC phase, use taker "
            "fills with adverse costs, settle funding when crossed, apply isolated "
            "margin and hard loss limits, and close at an exact time rather than an "
            "outcome-conditioned technical exit."
        ),
        principal_risks=[
            "clock_effect_decay_and_regime_sign_change",
            "directional_futures_and_liquidation_risk",
            "false_discovery_across_clock_phases_and_horizons",
            "funding_fees_spread_and_adverse_execution",
            "overlap_with_retired_momentum_or_reversal_families",
        ],
        pre_return_falsification_condition=(
            "Reject before primary selection if complete aggregate-trade history "
            "cannot distinguish clock-phase activity and signed order flow, if fewer "
            "than ten contracts satisfy the frozen coverage floor, if standalone "
            "directional futures risk is not deterministically modeled, or if the "
            "premise cannot be separated from a retired momentum or reversal rule."
        ),
        independence_from_blocked_lineages=[
            (
                "The proposed cause is scheduled algorithmic clock activity rather "
                "than price trend, breakout, broad beta, or funding carry."
            ),
            (
                "Any sign or horizon must come from theory before Aurex outcomes and "
                "cannot be selected among momentum and reversal variants."
            ),
        ],
        coverage_contract=V3ProposalCoverageContract(
            required_archive_families=["um_contract_klines_1m"],
            supplemental_historical_sources=[
                "usd_m_monthly_aggregate_trades",
            ],
            timestamp_join_policy=(
                "Exact UTC trade timestamp aggregation into one-minute and fixed "
                "quarter-hour clock phases joined to closed perpetual minutes."
            ),
            missing_row_policy=(
                "Never fill missing trades or candles. Exclude the affected clock "
                "event and reject a symbol-month when a gap exceeds fifteen minutes."
            ),
            minimum_total_coverage_fraction=Decimal("0.999"),
            minimum_calendar_month_coverage_fraction=Decimal("0.99"),
            maximum_single_gap_minutes=15,
            minimum_qualified_symbols=10,
            required_timestamp_evidence=TIMESTAMP_EVIDENCE,
            point_in_time_execution_dependencies=[
                "aggregate_trade_side_and_clock_phase_normalization",
                "dated_funding_fees_and_contract_filters",
                "isolated_directional_futures_margin_and_liquidation",
                "taker_fill_cost_and_capacity_model",
            ],
        ),
        primary_sources=[
            source(
                accessed_at=accessed_at,
                source_id="KIM_HANSEN_2026",
                title=(
                    "The Quarter-Hour Effect: Periodic Algorithmic Trading and "
                    "Return Predictability in Cryptocurrency Futures"
                ),
                authors=["Chan Kim", "Peter Reinhard Hansen"],
                published="2026-07-10",
                kind="PREPRINT",
                url="https://arxiv.org/abs/2607.09426",
                claims=[
                    (
                        "Crypto futures activity can cluster at fixed one-, five-, "
                        "and fifteen-minute clock boundaries."
                    ),
                    (
                        "Order imbalance, not the clock label alone, is part of the "
                        "reported return-prediction mechanism."
                    ),
                ],
            ),
            source(
                accessed_at=accessed_at,
                source_id="WEN_ET_AL_2022",
                title=(
                    "Intraday return predictability in the cryptocurrency markets: "
                    "Momentum, reversal, or both"
                ),
                authors=["Elie Bouri", "Yahua Xu", "Yang Zhao", "Zhuzhu Wen"],
                published="2022-11-01",
                kind="PEER_REVIEWED_ARTICLE",
                url=(
                    "https://www.sciencedirect.com/science/article/abs/pii/"
                    "S1062940822000833"
                ),
                claims=[
                    (
                        "Intraday cryptocurrency predictability has included both "
                        "momentum and reversal."
                    ),
                    (
                        "Jumps, liquidity, macro announcements, and regimes can "
                        "change the observed pattern."
                    ),
                ],
            ),
            source(
                accessed_at=accessed_at,
                source_id="CAPORALE_PLASTUN_2024",
                title="Revisiting seasonality in cryptocurrencies",
                authors=["Guglielmo Maria Caporale", "Alex Plastun"],
                published="2024-05-01",
                kind="PEER_REVIEWED_ARTICLE",
                url=(
                    "https://www.sciencedirect.com/science/article/pii/"
                    "S1544612324004598"
                ),
                claims=[
                    (
                        "Cryptocurrency calendar and seasonal effects have not been "
                        "uniformly robust across specifications."
                    ),
                    (
                        "A clock-based proposal requires strong falsification and "
                        "cannot assume stable return direction."
                    ),
                ],
            ),
        ],
        preliminary_execution_fit=(
            "REQUIRES_AGGREGATE_TRADES_AND_DIRECTIONAL_FUTURES_FOUNDATION"
        ),
    )


def liquidity_provision_proposal(accessed_at: datetime) -> V3MechanismProposal:
    return V3MechanismProposal(
        proposal_id="V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION",
        mechanism_name=(
            "Passive limit-order liquidity provision with queue and toxicity control"
        ),
        economic_premise=(
            "A passive market maker can earn the bid-ask spread for supplying "
            "liquidity, but the compensation exists only against uncertain fills, "
            "queue priority, adverse selection, inventory, cancellation latency, and "
            "fees. Candle-based apparent spread capture is not executable evidence; "
            "the mechanism requires event-level order-book and own-order state."
        ),
        ex_ante_payoff_direction=(
            "Expected spread and maker rebates must exceed adverse post-fill price "
            "movement, missed fills, inventory liquidation, queue decay, latency, "
            "cancellation failures, and exchange fees. High fill probability can "
            "coincide with more toxic fills rather than higher profit."
        ),
        exact_point_in_time_data_requirements=[
            "level_two_order_book_updates_with_sequence_numbers",
            "trade_level_price_quantity_aggressor_and_timestamp",
            "own_order_acknowledgement_queue_fill_cancel_and_reject_events",
            "subsecond_latency_and_clock_synchronization",
            "top_of_book_depth_spread_and_queue_position",
        ],
        historical_metadata_requirements=[
            "dated_maker_taker_fee_and_rebate_schedule",
            "historical_tick_lot_notional_and_order_limits",
            "historical_matching_queue_and_self_trade_prevention_rules",
        ],
        execution_path=(
            "Continuously quote bounded bid and ask orders only after reconstructing "
            "price-time priority, own queue position, acknowledgements, partial "
            "fills, cancellations, rejects, latency, inventory, toxicity, fees, and "
            "emergency flattening. Every simulated fill must be justified by event "
            "sequence rather than candle high-low contact."
        ),
        principal_risks=[
            "adverse_selection_and_post_fill_loss",
            "queue_position_and_uncertain_fill_probability",
            "inventory_latency_and_cancellation_failure",
            "maker_fee_rebate_and_matching_rule_change",
            "subsecond_data_loss_or_sequence_gap",
        ],
        pre_return_falsification_condition=(
            "Reject before primary selection unless immutable historical L2 updates, "
            "trades, sequence continuity, queue reconstruction, dated maker fees, "
            "and own-order-equivalent fill semantics are available at sufficient "
            "resolution. One-minute OHLCV or top-of-book snapshots cannot substitute."
        ),
        independence_from_blocked_lineages=[
            (
                "The premise is compensation for executable liquidity supply, not "
                "directional trend, breakout, reversal timing, beta, or funding carry."
            ),
            (
                "The edge can be evaluated only from queue-aware passive fills and "
                "cannot inherit any candle-based Aurex outcome."
            ),
        ],
        coverage_contract=V3ProposalCoverageContract(
            required_archive_families=[],
            supplemental_historical_sources=[
                "historical_l2_order_book_diffs_and_snapshots",
                "historical_own_order_equivalent_queue_events",
                "spot_or_usd_m_aggregate_trades",
            ],
            timestamp_join_policy=(
                "Strict exchange sequence and subsecond event-time replay joining "
                "book updates, trades, and own-order-equivalent lifecycle events."
            ),
            missing_row_policy=(
                "Never infer a book update, queue position, fill, or cancellation. "
                "Any sequence gap stops the affected session and source feasibility."
            ),
            minimum_total_coverage_fraction=Decimal("0.9999"),
            minimum_calendar_month_coverage_fraction=Decimal("0.999"),
            maximum_single_gap_minutes=0,
            minimum_qualified_symbols=1,
            required_timestamp_evidence=TIMESTAMP_EVIDENCE,
            point_in_time_execution_dependencies=[
                "dated_maker_taker_fees_and_rebates",
                "exchange_sequence_and_price_time_priority",
                "latency_ack_cancel_reject_and_partial_fill_model",
                "own_queue_position_and_inventory_reconciliation",
                "toxicity_and_emergency_flattening_controls",
            ],
        ),
        primary_sources=[
            source(
                accessed_at=accessed_at,
                source_id="ALBERS_ET_AL_2024",
                title=(
                    "The Market Maker's Dilemma: Navigating the Fill Probability "
                    "vs. Post-Fill Returns Trade-Off"
                ),
                authors=[
                    "Alexander Y. Shestopaloff",
                    "Jakob Albers",
                    "Mihai Cucuringu",
                    "Sam Howison",
                ],
                published="2024-12-28",
                kind="INSTITUTIONAL_WORKING_PAPER",
                url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5074873",
                claims=[
                    (
                        "A live Binance Bitcoin perpetual experiment finds a trade-off "
                        "between passive fill likelihood and post-fill returns."
                    ),
                    (
                        "Queue sizes, queue position, and immediate price dynamics are "
                        "required to evaluate maker fills."
                    ),
                ],
            ),
            source(
                accessed_at=accessed_at,
                source_id="CHANG_2026",
                title=(
                    "Do Order-Book States Predict Passive-Buy Toxicity? Evidence "
                    "from BTC Perpetual Futures"
                ),
                authors=["Lawrence Chang"],
                published="2026-05-02",
                kind="PREPRINT",
                url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6693260",
                claims=[
                    (
                        "Passive-fill toxicity depends on local order flow, displayed "
                        "support, and liquidity fragility."
                    ),
                    (
                        "L2 snapshots and aggregate trades are necessary inputs to the "
                        "reported empirical design."
                    ),
                ],
            ),
            source(
                accessed_at=accessed_at,
                source_id="TINIC_ET_AL_2022",
                title="Adverse Selection in Cryptocurrency Markets",
                authors=[
                    "Ahmet Sensoy",
                    "Erdin Akyildirim",
                    "Murat Tinic",
                    "Shaen Corbet",
                ],
                published="2022-07-06",
                kind="INSTITUTIONAL_WORKING_PAPER",
                url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4175306",
                claims=[
                    (
                        "Cryptocurrency limit-order markets exhibit economically "
                        "meaningful adverse-selection costs."
                    ),
                    (
                        "Order and trade data are needed to estimate effective spread "
                        "and information asymmetry."
                    ),
                ],
            ),
        ],
        preliminary_execution_fit=(
            "BLOCKED_PENDING_L2_QUEUE_FILL_AND_LATENCY_HISTORY"
        ),
    )


def authoritative_register(
    *,
    frozen_at: datetime,
    charter: V3MechanismDiscoveryCharter,
) -> V3MechanismProposalRegister:
    return build_v3_mechanism_proposal_register(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        proposals=[
            cointegration_proposal(frozen_at),
            clock_phase_proposal(frozen_at),
            liquidity_provision_proposal(frozen_at),
        ],
        limitations=[
            (
                "Registration freezes theory and source requirements only and makes "
                "no claim that any proposal is profitable or selectable."
            ),
            (
                "Cointegration remains model-dependent and requires a separate "
                "cross-asset paired execution foundation plus multiplicity controls."
            ),
            (
                "Clock-phase evidence is mixed and requires aggregate trades plus a "
                "separate directional futures foundation."
            ),
            (
                "Passive liquidity provision remains blocked unless historical L2, "
                "queue, fill, latency, and dated maker-fee evidence is qualified."
            ),
            (
                "Coverage thresholds were frozen before a proposal-specific coverage "
                "result and cannot be relaxed after observing feasibility."
            ),
            (
                "No price value, parameter, signal, trade, P/L, or return was "
                "inspected or calculated."
            ),
            (
                "Candidate, validation, holdout, forward, Pine, paper, sandbox, live, "
                "and capital permissions remain false."
            ),
        ],
    )


def write_register(
    path: Path,
    register: V3MechanismProposalRegister,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = register.model_dump_json(indent=2) + "\n"
    if V3MechanismProposalRegister.model_validate_json(serialized) != register:
        raise ValueError("V3 proposal register JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V3MechanismProposalRegister:
    if args.output.exists():
        raise ValueError("Frozen V3 proposal register exists; use --check")
    charter = load_charter(args.charter)
    register = authoritative_register(
        frozen_at=datetime.now(UTC),
        charter=charter,
    )
    write_register(args.output, register)
    print(
        f"WROTE {args.output} {register.register_evidence_hash} "
        f"proposals={len(register.proposals)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V3MechanismProposalRegister:
    charter = load_charter(args.charter)
    register = V3MechanismProposalRegister.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_register(
        frozen_at=register.frozen_at,
        charter=charter,
    )
    if register != expected:
        raise ValueError("V3 proposal register is not reproducible")
    if not audit_v3_mechanism_proposal_register(register):
        raise ValueError("V3 proposal register hash audit failed")
    print(
        "PASS "
        f"v3_proposals={register.register_evidence_hash} "
        f"count={len(register.proposals)} "
        f"selected={register.selected_primary_count} "
        f"returns={register.return_metrics_calculated}",
        flush=True,
    )
    return register


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the V3 no-return proposal register."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            run_freeze(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
