import argparse
import hashlib
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.research_v4_discovery_charter import (
    V4MechanismDiscoveryCharter,
    audit_v4_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v4_proposal_register import (
    V4MechanismProposal,
    V4MechanismProposalRegister,
    V4ProposalExecutionFeasibilityContract,
    V4ProposalSource,
    V4ProposalSourceFeasibilityContract,
    V4ScreenedOutTheory,
    audit_v4_mechanism_proposal_register,
    build_v4_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
NON_VALUE_FIELDS = [
    "archive_or_endpoint_identity",
    "boundary_completeness",
    "checksum_and_revision_identity",
    "content_length_and_storage_projection",
    "continuity_gap_count",
    "duplicate_timestamp_count",
    "first_and_last_timestamp",
    "http_status_and_selected_headers",
    "missing_timestamp_count",
    "request_attempt_and_elapsed_time",
    "row_count",
    "schema_identity",
    "transport_journal_identity_and_hash",
]


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v4_proposal_register.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_proposal_register.py",
        ]
    )


def charter_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v4_discovery_charter.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_discovery_charter.py",
        ]
    )


def load_charter(path: Path) -> V4MechanismDiscoveryCharter:
    charter = V4MechanismDiscoveryCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_v4_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_contract_hash()
        or charter.v3_final_decision != "SELECT_ZERO_V3_PRIMARY_MECHANISMS"
        or charter.v3_selected_primary_count != 0
        or charter.maximum_theory_proposals != 3
        or charter.maximum_return_tested_mechanisms_under_charter != 0
        or charter.maximum_parameter_sets_under_charter != 0
        or charter.charter_authorizes_network_requests
        or charter.may_inspect_market_numeric_values
        or charter.may_calculate_signals_trades_or_returns
    ):
        raise ValueError("V4 discovery charter audit failed")
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
    limitations: list[str],
    historical_scope: str,
) -> V4ProposalSource:
    return V4ProposalSource(
        source_id=source_id,
        title=title,
        authors_or_publisher=authors,
        publication_or_revision_date=published,
        accessed_at=accessed_at,
        source_kind=kind,
        url=url,
        supported_claims=claims,
        explicit_limitations=limitations,
        historical_truth_scope=historical_scope,
    )


def cross_venue_proposal(accessed_at: datetime) -> V4MechanismProposal:
    return V4MechanismProposal(
        proposal_id=(
            "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE"
        ),
        mechanism_name=(
            "Inventory-backed same-asset cross-venue executable-price arbitrage"
        ),
        economic_premise=(
            "The identical spot asset can trade at different executable prices on "
            "independently operated central limit-order books because venue access, "
            "capital segmentation, latency, inventory location, fiat rails, and "
            "operational risk limit immediate law-of-one-price enforcement. Aurex "
            "would test only pre-funded same-asset dislocations and would never "
            "treat unmatched last trades, candles, or post-trade transfers as an "
            "arbitrage fill."
        ),
        ex_ante_payoff_direction=(
            "When the executable bid on one accessible venue exceeds the executable "
            "ask on another, simultaneously sell pre-positioned base inventory at "
            "the high bid and buy the same quantity with pre-positioned quote "
            "inventory at the low ask. Net payoff exists only if both acknowledged "
            "fills complete and the locked spread exceeds both venue fees, adverse "
            "movement, partial-leg rollback, inventory rebalance, custody, and "
            "capital costs."
        ),
        economic_reason_edge_might_persist=[
            (
                "Capital and inventory cannot move instantaneously across separately "
                "operated venues, so local order flow can temporarily segment prices."
            ),
            (
                "Jurisdiction, account access, counterparty, custody, fee tier, and "
                "operational constraints can limit competing arbitrage capital."
            ),
        ],
        exact_point_in_time_data_requirements=[
            "exchange_and_local_receipt_timestamps_for_both_venue_feeds",
            "best_bid_best_ask_and_displayed_quantity_for_the_same_spot_asset",
            "disconnect_reconnect_sequence_and_snapshot_recovery_events",
            "full_order_lifecycle_ack_fill_partial_fill_cancel_reject_events",
            "point_in_time_fee_tier_tick_lot_notional_and_order_status_rules",
            "venue_status_product_status_and_maintenance_events",
            "pre_trade_base_quote_inventory_and_post_trade_balance_state",
        ],
        execution_path=(
            "Maintain base inventory on the prospective sell venue and quote "
            "inventory on the prospective buy venue. At a later separately frozen "
            "decision event, compare synchronized non-stale executable top-of-book "
            "prices and quantities, submit bounded IOC or FOK legs with unique "
            "client IDs, reconcile acknowledgements and fills independently, cancel "
            "or flatten any unmatched residual under a predeclared rollback path, "
            "then reconcile venue balances before another attempt. Transfers are "
            "inventory rebalancing events, never assumed atomic trade legs."
        ),
        principal_risks=[
            "cross_venue_clock_skew_and_stale_quotes",
            "fee_tier_spread_and_adverse_selection",
            "one_leg_fill_reject_timeout_or_partial_fill",
            "venue_custody_counterparty_and_withdrawal_risk",
            "inventory_depletion_and_rebalancing_cost",
            "jurisdiction_account_and_product_access_change",
            "capacity_decay_and_competing_low_latency_arbitrage",
        ],
        pre_return_falsification_condition=(
            "Reject before primary selection if Aurex cannot qualify a synchronized "
            "2023-2024 same-asset BBO archive with quantities, exchange and local "
            "timestamps, disconnect or sequence recovery, and point-in-time venue "
            "rules for two legally accessible accounts; if historical fees and "
            "filters cannot be bounded; or if a deterministic two-leg acknowledgement, "
            "partial-fill rollback, inventory, balance, and reconciliation model "
            "cannot be proven without real orders."
        ),
        independence_from_blocked_lineages=[
            (
                "This is same-asset law-of-one-price enforcement across venues, not "
                "V3P01 cross-asset cointegration, hedge-ratio estimation, or spread "
                "mean reversion."
            ),
            (
                "It does not forecast price direction and does not express trend, "
                "breakout, path quality, broad beta, clock phase, or reversal."
            ),
            (
                "It is inventory-backed spot execution and does not use funding, "
                "perpetual basis, borrow, or passive market-making compensation."
            ),
        ],
        primary_sources=[
            source(
                accessed_at=accessed_at,
                source_id="MAKAROV_SCHOAR_JFE_2020",
                title="Trading and arbitrage in cryptocurrency markets",
                authors=["Igor Makarov", "Antoinette Schoar"],
                published="2020-02-01",
                kind="PEER_REVIEWED_ARTICLE",
                url=(
                    "https://dspace.mit.edu/server/api/core/bitstreams/"
                    "a3b4b145-a125-4d4d-add5-8bd452d2869d/content"
                ),
                claims=[
                    (
                        "Cryptocurrency markets exhibited recurring cross-exchange "
                        "price deviations and market segmentation."
                    ),
                    (
                        "Capital controls, capital location, fees, and limits to "
                        "arbitrage are material to interpreting those deviations."
                    ),
                ],
                limitations=[
                    (
                        "The study used historical Kaiko trade data and does not prove "
                        "a current executable Aurex edge or current account access."
                    )
                ],
                historical_scope="DATED_RESEARCH_EVIDENCE",
            ),
            source(
                accessed_at=accessed_at,
                source_id="BINANCE_SPOT_WS_CURRENT",
                title="Binance Spot API WebSocket Streams",
                authors=["Binance"],
                published=None,
                kind="OFFICIAL_EXCHANGE_DOCUMENTATION",
                url=(
                    "https://github.com/binance/binance-spot-api-docs/blob/"
                    "master/web-socket-streams.md"
                ),
                claims=[
                    (
                        "The bookTicker stream publishes best bid and ask prices and "
                        "quantities with an order-book update identifier."
                    ),
                    (
                        "Depth reconstruction has explicit snapshot, update, and "
                        "connection-limit semantics."
                    ),
                ],
                limitations=[
                    (
                        "Current mutable documentation is not point-in-time proof of "
                        "the 2023-2024 schema, fees, filters, or venue state."
                    )
                ],
                historical_scope="CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
            ),
            source(
                accessed_at=accessed_at,
                source_id="COINBASE_EXCHANGE_WS_CURRENT",
                title="Coinbase Exchange WebSocket Channels",
                authors=["Coinbase"],
                published=None,
                kind="OFFICIAL_EXCHANGE_DOCUMENTATION",
                url=(
                    "https://docs.cdp.coinbase.com/exchange/websocket-feed/"
                    "channels"
                ),
                claims=[
                    (
                        "Coinbase publishes BBO fields and sequence-aware level-two "
                        "or full order-book feeds."
                    ),
                    (
                        "The order lifecycle includes received, open, match, change, "
                        "and done events, and dropped-message recovery matters."
                    ),
                ],
                limitations=[
                    (
                        "Current mutable documentation does not establish historical "
                        "availability, account eligibility, fee tier, or schema."
                    )
                ],
                historical_scope="CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
            ),
            source(
                accessed_at=accessed_at,
                source_id="TARDIS_DATASETS_CURRENT",
                title="Tardis downloadable CSV market data documentation",
                authors=["Tardis.dev"],
                published=None,
                kind="INDEPENDENT_MARKET_DATA_DOCUMENTATION",
                url="https://docs.tardis.dev/downloadable-csv-files",
                claims=[
                    (
                        "The vendor documents tick-level quotes, order-book updates, "
                        "trades, exchange timestamps, and local receipt timestamps."
                    ),
                    (
                        "Raw replay can preserve disconnect events that normalized "
                        "CSV quote files omit."
                    ),
                ],
                limitations=[
                    (
                        "Availability, completeness, subscription cost, checksums, "
                        "and exact Binance/Coinbase coverage require a separate "
                        "bounded census and transport contract."
                    )
                ],
                historical_scope="CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
            ),
        ],
        source_feasibility_contract=V4ProposalSourceFeasibilityContract(
            required_source_products=[
                "binance_spot_bbo_or_l2_with_exchange_and_local_timestamps",
                "coinbase_spot_bbo_or_l2_with_exchange_and_local_timestamps",
                "disconnect_reconnect_snapshot_and_sequence_recovery_records",
                "historical_product_fee_filter_status_and_maintenance_metadata",
            ],
            exact_non_value_fields=NON_VALUE_FIELDS,
            required_cross_source_bindings=[
                "same_base_asset_and_economically_equivalent_quote_currency",
                "utc_event_and_local_receipt_clock_identity",
                "venue_product_listing_status_and_calendar_boundary",
            ],
            minimum_complete_calendar_day_fraction=Decimal("0.95"),
            minimum_complete_calendar_month_fraction=Decimal("0.90"),
            missing_event_policy=(
                "Never infer, forward-fill, interpolate, or backfill a BBO, quantity, "
                "sequence, disconnect, or venue state. Any unexplained event-sequence "
                "gap invalidates the affected session; any failed calendar coverage "
                "gate rejects the proposal before primary selection."
            ),
            source_revision_policy=(
                "Freeze endpoint identity, dataset revision, content length, and "
                "available checksum before payload access. A changed or absent "
                "revision requires a terminal transport-stop result, never silent "
                "replacement or continuation."
            ),
            prohibited_substitutions=[
                "candles_or_bar_high_low_for_executable_quotes",
                "last_trades_for_simultaneous_bbo",
                "normalized_quotes_without_disconnect_or_recovery_evidence",
                "post_trade_asset_transfer_as_atomic_second_leg",
            ],
            pre_return_source_stop=(
                "Stop if a separately frozen metadata census cannot prove the exact "
                "two-venue 2023-2024 archive scope, or if a bounded payload pilot "
                "cannot prove schema, timestamp, disconnect, sequence, and checksum "
                "integrity without inspecting bid, ask, size, trade, P/L, or return "
                "values."
            ),
        ),
        execution_feasibility_contract=(
            V4ProposalExecutionFeasibilityContract(
                required_venues_or_instruments=[
                    "two_independently_operated_legally_accessible_spot_clobs",
                    "same_base_asset_with_economically_equivalent_quote_inventory",
                ],
                jurisdiction_and_account_requirements=[
                    "documented_account_and_product_access_for_the_operator_jurisdiction",
                    "kyc_tax_custody_and_transfer_constraints_recorded_before_selection",
                    "no_assumption_that_documented_api_access_equals_trading_access",
                ],
                point_in_time_metadata_requirements=[
                    "both_venue_fee_tiers_and_fee_currency",
                    "both_venue_tick_lot_notional_and_price_bands",
                    "product_listing_trading_halt_and_maintenance_state",
                    "deposit_withdrawal_network_limits_and_rebalancing_cost",
                ],
                order_lifecycle_requirements=[
                    "unique_client_order_id_per_leg_and_attempt",
                    "independent_ack_reject_fill_and_cancel_state_machine_per_venue",
                    "partial_fill_quantity_and_fee_reconciliation",
                    "venue_balance_and_inventory_reconciliation_before_rearm",
                    "timeout_state_unknown_order_query_and_idempotent_recovery",
                ],
                financing_and_collateral_requirements=[
                    "pre_funded_base_inventory_on_sell_venue",
                    "pre_funded_quote_inventory_on_buy_venue",
                    "capital_custody_and_idle_inventory_cost_accounting",
                ],
                multi_leg_failure_requirements=[
                    "no_assumed_cross_venue_atomicity",
                    "predeclared_second_leg_reject_and_partial_fill_rollback",
                    "bounded_residual_exposure_and_emergency_flattening",
                    "halt_on_unknown_order_balance_or_venue_state",
                ],
                capacity_requirements=[
                    "displayed_executable_quantity_caps_each_leg",
                    "inventory_and_rebalance_capacity_caps",
                    "latency_and_staleness_budget_before_any_order",
                ],
                mandatory_risk_controls=[
                    "maximum_attempt_and_residual_loss_bound",
                    "venue_disconnect_clock_skew_and_stale_quote_kill_switch",
                    "daily_loss_custody_and_inventory_concentration_limits",
                ],
                pre_return_execution_stop=(
                    "Reject if either venue is not legally and operationally "
                    "accessible, point-in-time fees or filters cannot be bounded, "
                    "pre-funded inventory is impractical for the intended capital, "
                    "or Aurex cannot deterministically reconcile both legs, unknown "
                    "orders, partial fills, balances, residual exposure, and rollback "
                    "without assuming atomic execution."
                ),
            )
        ),
        preliminary_fit=(
            "REQUIRES_SYNCHRONIZED_MULTI_VENUE_BBO_AND_INVENTORY_FOUNDATION"
        ),
    )


def variance_risk_premium_proposal(
    accessed_at: datetime,
) -> V4MechanismProposal:
    return V4MechanismProposal(
        proposal_id="V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM",
        mechanism_name=(
            "Delta-hedged cryptocurrency option variance-risk-premium harvesting"
        ),
        economic_premise=(
            "Option buyers may pay a persistent premium for convex protection against "
            "large cryptocurrency moves, creating a variance risk premium for "
            "capitalized sellers who absorb jump, volatility, skew, and liquidity "
            "risk. Aurex would test a delta-hedged option exposure, not forecast the "
            "underlying price and not equate quoted implied volatility with an "
            "executable return."
        ),
        ex_ante_payoff_direction=(
            "A short delta-hedged option exposure can earn only when collected "
            "executable option premium exceeds realized gamma hedging losses, option "
            "and hedge-leg fees, bid-ask spread, discrete hedging error, jumps, "
            "settlement costs, margin drag, and liquidation losses. The payoff is "
            "negatively convex and can suffer losses much larger than routine gains."
        ),
        economic_reason_edge_might_persist=[
            (
                "Protection demand can compensate option sellers for bearing crash, "
                "jump, volatility-of-volatility, and skew risk."
            ),
            (
                "Capital, margin, model, liquidity, and operational constraints can "
                "limit competition in crypto option supply."
            ),
        ],
        exact_point_in_time_data_requirements=[
            "all_listed_option_instruments_expiries_strikes_types_and_contract_sizes",
            "option_best_bid_best_ask_quantities_trades_and_exchange_timestamps",
            "underlying_index_perpetual_or_future_bbo_trades_and_local_timestamps",
            "point_in_time_option_greeks_mark_iv_underlying_and_interest_rate_inputs",
            "instrument_listing_expiry_settlement_and_delivery_price_records",
            "point_in_time_option_and_hedge_leg_fees_and_fee_caps",
            "point_in_time_standard_or_portfolio_margin_and_liquidation_parameters",
        ],
        execution_path=(
            "A later separately frozen protocol would construct one predefined "
            "delta-hedged option exposure from executable bid prices, hedge its "
            "underlying delta with a specified future or perpetual using executable "
            "quotes, update hedge state only under frozen rules, settle fees and "
            "cash flows in their actual currencies, apply point-in-time margin and "
            "liquidation, and close or cash-settle all legs with deterministic "
            "position and balance reconciliation. No mark, midpoint, or model Greek "
            "may be used as an assumed fill."
        ),
        principal_risks=[
            "unbounded_or_large_convex_tail_loss",
            "jump_and_discrete_delta_hedging_error",
            "implied_volatility_skew_and_surface_model_error",
            "wide_option_spreads_sparse_quotes_and_leg_execution",
            "margin_liquidation_collateral_and_currency_mismatch",
            "fee_delivery_and_settlement_rule_change",
            "vendor_archive_completeness_cost_and_revision",
        ],
        pre_return_falsification_condition=(
            "Reject before primary selection if Aurex cannot qualify complete "
            "2023-2024 Deribit option-chain quotes, sizes, trades, instrument "
            "lifecycle, underlying hedge quotes, settlement, fees, and margin state; "
            "if the archive omits disconnect or revision evidence; if the operator "
            "cannot legally access the venue; or if deterministic multi-leg fills, "
            "delta accounting, cash flows, liquidation, expiry, and reconciliation "
            "cannot be proven before any return test."
        ),
        independence_from_blocked_lineages=[
            (
                "The premise is compensation for transferring option convexity and "
                "tail risk, not spot-perpetual funding or basis carry."
            ),
            (
                "Delta hedging targets first-order direction and does not use trend, "
                "breakout, reversal, path-quality, beta, or clock-phase signals."
            ),
            (
                "It is an options risk-premium mechanism, not V3P03 passive spread "
                "capture or queue-position market making."
            ),
        ],
        primary_sources=[
            source(
                accessed_at=accessed_at,
                source_id="ALEXANDER_IMERAJ_JAI_2021",
                title="The Bitcoin VIX and its Variance Risk Premium",
                authors=["Carol Alexander", "Arben Imeraj"],
                published="2021-03-01",
                kind="PEER_REVIEWED_ARTICLE",
                url=(
                    "https://sussex.figshare.com/articles/journal_contribution/"
                    "Practical_applications_of_The_Bitcoin_VIX_and_its_variance_"
                    "risk_premium/23490374"
                ),
                claims=[
                    (
                        "Peer-reviewed research constructs Bitcoin implied-volatility "
                        "indices and studies variance risk premia from Deribit options."
                    ),
                    (
                        "High-frequency option observations and realized variance are "
                        "required to measure the mechanism."
                    ),
                ],
                limitations=[
                    (
                        "A variance-risk-premium estimate does not prove a tradable "
                        "short-option strategy after spreads, hedging, margin, and "
                        "tail losses."
                    )
                ],
                historical_scope="DATED_RESEARCH_EVIDENCE",
            ),
            source(
                accessed_at=accessed_at,
                source_id="DERIBIT_HISTORY_GUIDE_CURRENT",
                title="Deribit Institutional Account Setup Guide historical data",
                authors=["Deribit"],
                published=None,
                kind="OFFICIAL_EXCHANGE_DATA_ARCHIVE",
                url=(
                    "https://statics.deribit.com/files/"
                    "DeribitInstitutionalSetupGuide.pdf"
                ),
                claims=[
                    (
                        "Deribit documents public historical trade and instrument "
                        "endpoints and states that instrument history is retained."
                    ),
                    (
                        "Historical endpoints expose exchange-native instrument and "
                        "trade records for later bounded feasibility work."
                    ),
                ],
                limitations=[
                    (
                        "The guide does not provide sequence-complete historical BBO "
                        "or prove complete option-chain quote coverage."
                    )
                ],
                historical_scope="CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
            ),
            source(
                accessed_at=accessed_at,
                source_id="DERIBIT_INSTRUMENT_API_CURRENT",
                title="Deribit public get instrument API reference",
                authors=["Deribit"],
                published=None,
                kind="OFFICIAL_EXCHANGE_DOCUMENTATION",
                url=(
                    "https://docs.deribit.com/api-reference/market-data/"
                    "public-get_instrument"
                ),
                claims=[
                    (
                        "Instrument records include option type, strike, expiration, "
                        "contract size, settlement, tick size, and state."
                    ),
                    (
                        "Instrument identity is required to reconstruct option "
                        "lifecycle and cash-flow semantics."
                    ),
                ],
                limitations=[
                    (
                        "Current API documentation is not proof of point-in-time "
                        "2023-2024 specifications or later revisions."
                    )
                ],
                historical_scope="CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
            ),
            source(
                accessed_at=accessed_at,
                source_id="TARDIS_DERIBIT_OPTIONS_CURRENT",
                title="Tardis downloadable Deribit options datasets",
                authors=["Tardis.dev"],
                published=None,
                kind="INDEPENDENT_MARKET_DATA_DOCUMENTATION",
                url="https://docs.tardis.dev/downloadable-csv-files",
                claims=[
                    (
                        "The vendor documents grouped Deribit option quotes, option "
                        "chains, trades, order books, and local receipt timestamps."
                    ),
                    (
                        "Daily files and exchange-native raw replay can support a "
                        "bounded source census and disconnect-aware pilot."
                    ),
                ],
                limitations=[
                    (
                        "Exact availability, subscription cost, completeness, "
                        "revision identity, and payload integrity are unqualified."
                    )
                ],
                historical_scope="CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
            ),
            source(
                accessed_at=accessed_at,
                source_id="DERIBIT_FEES_CURRENT",
                title="Deribit fees and delivery fees",
                authors=["Deribit"],
                published="2026-07-08",
                kind="OFFICIAL_EXCHANGE_DOCUMENTATION",
                url="https://support.deribit.com/hc/en-us/articles/25944746248989-Fees",
                claims=[
                    (
                        "Options and hedge instruments have product-specific trading, "
                        "delivery, liquidation, and fee-cap semantics."
                    ),
                    (
                        "Current fee tiers are scheduled to change, demonstrating "
                        "that point-in-time fee history is mandatory."
                    ),
                ],
                limitations=[
                    (
                        "The current page cannot be projected backward as the exact "
                        "2023-2024 fee schedule without dated archive evidence."
                    )
                ],
                historical_scope="CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
            ),
        ],
        source_feasibility_contract=V4ProposalSourceFeasibilityContract(
            required_source_products=[
                "deribit_grouped_option_quotes_sizes_trades_and_option_chain",
                "deribit_option_instrument_lifecycle_and_settlement_records",
                "deribit_underlying_index_and_hedge_instrument_quotes_and_trades",
                "disconnect_reconnect_sequence_and_dataset_revision_records",
                "historical_fee_margin_liquidation_and_delivery_metadata",
            ],
            exact_non_value_fields=NON_VALUE_FIELDS,
            required_cross_source_bindings=[
                "option_symbol_expiry_strike_type_contract_and_settlement_identity",
                "option_event_underlying_index_and_hedge_instrument_clock_identity",
                "venue_session_expiry_delivery_and_margin_regime_identity",
            ],
            minimum_complete_calendar_day_fraction=Decimal("0.95"),
            minimum_complete_calendar_month_fraction=Decimal("0.90"),
            missing_event_policy=(
                "Never infer, interpolate, forward-fill, or backfill an option quote, "
                "size, trade, Greek, instrument, underlying hedge quote, disconnect, "
                "fee, or margin state. Any unexplained sequence or lifecycle gap "
                "invalidates the affected session; failed coverage rejects the "
                "proposal before primary selection."
            ),
            source_revision_policy=(
                "Freeze vendor exchange metadata, available-since and available-to "
                "fields, source revision, content length, and available integrity "
                "headers before payload access. A changed source ends in a preserved "
                "transport-stop result unless the predeclared contract permits and "
                "verifies the exact replacement."
            ),
            prohibited_substitutions=[
                "mark_midpoint_or_model_value_for_executable_option_fill",
                "option_trades_without_bbo_for_continuous_executability",
                "current_fee_margin_or_instrument_rules_as_historical_truth",
                "underlying_candles_for_hedge_leg_execution",
            ],
            pre_return_source_stop=(
                "Stop if a separate metadata census cannot establish complete daily "
                "grouped option, underlying hedge, instrument, and rule coverage for "
                "2023-2024, or if a bounded checksum-aware payload pilot cannot prove "
                "schema, timestamp, lifecycle, disconnect, and cross-product identity "
                "without inspecting prices, Greeks, signals, P/L, or returns."
            ),
        ),
        execution_feasibility_contract=(
            V4ProposalExecutionFeasibilityContract(
                required_venues_or_instruments=[
                    "legally_accessible_deribit_option_account",
                    "specified_deribit_future_or_perpetual_delta_hedge_instrument",
                    "specified_option_settlement_and_collateral_currency",
                ],
                jurisdiction_and_account_requirements=[
                    "documented_operator_jurisdiction_and_product_eligibility",
                    "kyc_tax_derivatives_suitability_and_api_access_recorded",
                    "no_assumption_that_public_market_data_implies_trading_access",
                ],
                point_in_time_metadata_requirements=[
                    "option_and_hedge_leg_fees_caps_and_delivery_fees",
                    "instrument_contract_tick_amount_expiry_and_settlement_rules",
                    "standard_or_portfolio_margin_parameters_and_account_mode",
                    "liquidation_insurance_and_collateral_currency_rules",
                    "index_composition_delivery_price_and_session_state",
                ],
                order_lifecycle_requirements=[
                    "unique_client_order_id_for_every_option_and_hedge_order",
                    "ack_reject_partial_fill_cancel_and_unknown_order_recovery",
                    "option_and_hedge_position_fee_and_cash_flow_reconciliation",
                    "expiry_exercise_delivery_and_settlement_reconciliation",
                    "balance_margin_and_liquidation_state_reconciliation",
                ],
                financing_and_collateral_requirements=[
                    "fully_funded_option_tail_loss_and_hedge_margin_budget",
                    "collateral_currency_haircut_fee_and_conversion_accounting",
                    "no_unbounded_short_option_notional_or_implicit_borrow",
                ],
                multi_leg_failure_requirements=[
                    "no_assumed_option_and_delta_hedge_atomicity",
                    "predeclared_option_or_hedge_partial_fill_rollback",
                    "bounded_unhedged_delta_gamma_and_vega_exposure",
                    "emergency_flattening_and_halt_on_unknown_state",
                ],
                capacity_requirements=[
                    "executable_option_and_hedge_displayed_quantity_caps",
                    "spread_open_interest_and_concentration_caps",
                    "hedge_turnover_fee_and_market_impact_budget",
                ],
                mandatory_risk_controls=[
                    "maximum_tail_loss_margin_usage_and_daily_loss_bound",
                    "stale_surface_stale_hedge_and_venue_disconnect_kill_switch",
                    "stress_scenarios_for_jump_volatility_skew_and_liquidity",
                    "no_automatic_rearm_after_margin_or_reconciliation_breach",
                ],
                pre_return_execution_stop=(
                    "Reject if venue access is unavailable, complete point-in-time "
                    "fees, settlement, margin, liquidation, and contract state cannot "
                    "be bounded, or Aurex cannot deterministically model executable "
                    "multi-leg fills, Greeks and cash flows, discrete hedging, expiry, "
                    "liquidation, balances, and worst-case tail-loss controls."
                ),
            )
        ),
        preliminary_fit=(
            "REQUIRES_OPTION_CHAIN_QUOTE_HEDGE_MARGIN_AND_SETTLEMENT_FOUNDATION"
        ),
    )


def screened_out_theories() -> list[V4ScreenedOutTheory]:
    return [
        V4ScreenedOutTheory(
            theory_id="TRIANGULAR_WITHIN_VENUE_ARBITRAGE",
            disposition="NOT_REGISTERED_RELATED_TO_REGISTERED_PROPOSAL",
            reason=(
                "This is another simultaneous law-of-one-price multi-leg mechanism "
                "with the same order-book synchronization, fee, partial-fill, and "
                "rollback core as V4P01. Registering it separately would spend a "
                "proposal slot on a closely related execution family."
            ),
        ),
        V4ScreenedOutTheory(
            theory_id="OPTION_PUT_CALL_PARITY_ARBITRAGE",
            disposition="NOT_REGISTERED_RELATED_TO_REGISTERED_PROPOSAL",
            reason=(
                "Put-call parity uses the same option-chain, underlying hedge, "
                "multi-leg execution, margin, and settlement foundation as V4P02. "
                "It may become a non-return data-quality diagnostic but is not an "
                "independent primary theory in this round."
            ),
        ),
        V4ScreenedOutTheory(
            theory_id="STABLECOIN_MINT_REDEMPTION_ARBITRAGE",
            disposition="NOT_REGISTERED_EXECUTION_ACCESS_NOT_CREDIBLE",
            reason=(
                "Direct issuer mint and redemption access, banking rails, limits, "
                "settlement timing, compliance, and counterparty terms are not "
                "credible assumptions for Aurex today. Exchange-only premium trades "
                "would not reproduce the redemption mechanism."
            ),
        ),
        V4ScreenedOutTheory(
            theory_id="LIQUIDATION_EVENT_DIRECTIONAL_REACTION",
            disposition="NOT_REGISTERED_RETIRED_LINEAGE_OVERLAP",
            reason=(
                "A directional post-liquidation rule would likely choose continuation "
                "or reversal from outcomes and overlap retired trend, path, breakout, "
                "or reversal families. It lacks one independent pre-outcome payoff "
                "direction suitable for this bounded round."
            ),
        ),
    ]


def authoritative_register(
    *,
    frozen_at: datetime,
    charter: V4MechanismDiscoveryCharter,
) -> V4MechanismProposalRegister:
    return build_v4_mechanism_proposal_register(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        proposals=[
            cross_venue_proposal(frozen_at),
            variance_risk_premium_proposal(frozen_at),
        ],
        screened_out_theories=screened_out_theories(),
        limitations=[
            (
                "Registration freezes two theories and their no-return feasibility "
                "requirements; it does not claim either mechanism has current edge."
            ),
            (
                "One of three proposal slots is deliberately unused because adding a "
                "related or operationally inaccessible theory would inflate "
                "multiplicity without adding an independent mechanism."
            ),
            (
                "Cross-venue arbitrage requires pre-funded inventory, legally "
                "accessible accounts, synchronized executable BBO, and deterministic "
                "two-venue failure reconciliation."
            ),
            (
                "Variance-risk-premium exposure is negatively convex and requires "
                "complete option quotes, hedge execution, margin, settlement, and "
                "tail-loss evidence; routine premium collection is not safe income."
            ),
            (
                "Current exchange and vendor documentation cannot be projected "
                "backward as point-in-time 2023-2024 execution truth."
            ),
            (
                "Every payload request requires a separate frozen crash-safe "
                "transport contract with cumulative request, byte, timeout, retry, "
                "resume, persistence, and terminal-stop budgets."
            ),
            (
                "No price, quote value, quantity value, parameter, signal, trade, "
                "P/L, strategy outcome, or return was inspected or calculated."
            ),
            (
                "Neither proposal is selected; source and execution feasibility may "
                "still reject both and close V4 with zero primaries."
            ),
            (
                "Development outcomes, validation, holdout, forward, Pine, paper, "
                "sandbox, live trading, and capital permissions remain false."
            ),
            (
                "Commercial data access, account access, and required starting "
                "capital remain unresolved costs rather than hidden assumptions."
            ),
        ],
    )


def write_register(
    path: Path,
    register: V4MechanismProposalRegister,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = register.model_dump_json(indent=2) + "\n"
    if V4MechanismProposalRegister.model_validate_json(serialized) != register:
        raise ValueError("V4 proposal register JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V4MechanismProposalRegister:
    if args.output.exists():
        raise ValueError("Frozen V4 proposal register exists; use --check")
    charter = load_charter(args.charter)
    register = authoritative_register(
        frozen_at=datetime.now(UTC),
        charter=charter,
    )
    write_register(args.output, register)
    print(
        f"WROTE {args.output} {register.register_evidence_hash} "
        f"proposals={len(register.proposals)} "
        f"unused={register.proposal_budget_unused}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V4MechanismProposalRegister:
    charter = load_charter(args.charter)
    register = V4MechanismProposalRegister.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_register(
        frozen_at=register.frozen_at,
        charter=charter,
    )
    if (
        register != expected
        or not audit_v4_mechanism_proposal_register(register)
    ):
        raise ValueError("V4 proposal register is not reproducible")
    print(
        "PASS "
        f"v4_proposals={register.register_evidence_hash} "
        f"count={len(register.proposals)} "
        f"unused={register.proposal_budget_unused} "
        f"selected={register.selected_primary_count} "
        f"returns={register.return_metrics_calculated}",
        flush=True,
    )
    return register


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the V4 no-return proposal register."
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
