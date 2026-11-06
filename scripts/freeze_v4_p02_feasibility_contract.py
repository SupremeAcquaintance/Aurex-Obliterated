import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.research_v4_p02_feasibility_contract import (  # noqa: E402
    V4P02_DATASET_PRODUCTS,
    V4P02_JOURNAL_POLICY,
    V4P02_PERMITTED_OBSERVATION_FIELDS,
    V4P02_PROHIBITED_PARSED_FIELDS,
    V4P02_REQUIRED_GATE_IDS,
    V4P02_SAMPLE_DATES,
    V4P02_STOP_CONDITIONS,
    V4P02ExecutionGate,
    V4P02FeasibilityContract,
    V4P02SourceRequest,
    V4P02TerminalArtifactContract,
    V4P02TransportBudget,
    audit_v4_p02_feasibility_contract,
    build_v4_p02_feasibility_contract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v4_p01_feasibility_contract import (  # noqa: E402
    load_inputs,
)

DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v4_p02_feasibility_contract_v1.json"
)
USER_AGENT = "Aurex-V4P02-Source-Census/1.0"


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
            PROJECT_ROOT
            / "scripts"
            / "freeze_v4_p02_feasibility_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p02_feasibility_contract.py",
        ]
    )


def requests() -> list[V4P02SourceRequest]:
    values = [
        V4P02SourceRequest(
            request_id="V4P02_META_DERIBIT_EXCHANGE_DETAILS",
            phase="EXCHANGE_METADATA",
            sequence=1,
            method="GET",
            url="https://api.tardis.dev/v1/exchanges/deribit",
            expected_host="api.tardis.dev",
            dataset_data_type=None,
            dataset_symbol=None,
            dataset_role=None,
            sample_date=None,
            request_headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": USER_AGENT,
            },
            maximum_response_body_bytes=8_388_608,
            redirects_permitted=False,
            maximum_redirects=0,
        )
    ]
    sequence = 2
    for sample_date in V4P02_SAMPLE_DATES:
        compact_date = sample_date.replace("-", "")
        year, month, day = sample_date.split("-")
        for data_type, symbol, role in V4P02_DATASET_PRODUCTS:
            symbol_id = symbol.replace("-", "_")
            request_id = (
                f"V4P02_HEAD_{compact_date}_"
                f"{data_type.upper()}_{symbol_id}"
            )
            url = (
                "https://datasets.tardis.dev/v1/deribit/"
                f"{data_type}/{year}/{month}/{day}/{symbol}.csv.gz"
            )
            values.append(
                V4P02SourceRequest(
                    request_id=request_id,
                    phase="DATASET_HEADER_CENSUS",
                    sequence=sequence,
                    method="HEAD",
                    url=url,
                    expected_host="datasets.tardis.dev",
                    dataset_data_type=data_type,
                    dataset_symbol=symbol,
                    dataset_role=role,
                    sample_date=sample_date,
                    request_headers={
                        "Accept": "application/gzip",
                        "Accept-Encoding": "identity",
                        "User-Agent": USER_AGENT,
                    },
                    maximum_response_body_bytes=0,
                    redirects_permitted=True,
                    maximum_redirects=3,
                )
            )
            sequence += 1
    return values


def gate(
    gate_id: str,
    evidence_required: list[str],
    pass_condition: str,
) -> V4P02ExecutionGate:
    return V4P02ExecutionGate(
        gate_id=gate_id,
        evidence_required=evidence_required,
        pass_condition=pass_condition,
    )


def execution_gates() -> list[V4P02ExecutionGate]:
    gates = {
        "ACCOUNT_JURISDICTION_AND_DERIVATIVES_ACCESS": gate(
            "ACCOUNT_JURISDICTION_AND_DERIVATIVES_ACCESS",
            [
                "documented_operator_jurisdiction",
                "deribit_kyc_derivatives_and_api_eligibility_attestation",
                "tax_and_suitability_acknowledgement",
            ],
            (
                "The named operator must document jurisdiction, KYC status, "
                "derivatives eligibility, account mode, API eligibility, tax "
                "obligations, and any restrictions. Public data access is never "
                "accepted as evidence of legal trading access."
            ),
        ),
        "ARCHIVE_CALENDAR_INCIDENT_AND_EXPORT_COVERAGE": gate(
            "ARCHIVE_CALENDAR_INCIDENT_AND_EXPORT_COVERAGE",
            [
                "deribit_exchange_available_since_and_to",
                "datasets_exported_until",
                "incident_boundaries",
                "later_full_calendar_manifest",
            ],
            (
                "Metadata must cover all of 2023-2024, enumerate incidents, and "
                "bind dataset export state. A later credentialed census must prove "
                "at least 95 percent complete calendar days and 90 percent complete "
                "months without inferring any missing event."
            ),
        ),
        "COLLATERAL_CASH_FLOW_AND_BALANCE_RECONCILIATION": gate(
            "COLLATERAL_CASH_FLOW_AND_BALANCE_RECONCILIATION",
            [
                "collateral_currency_and_haircut_rules",
                "option_premium_fee_delivery_and_settlement_cash_flows",
                "position_margin_balance_reconciliation_state_machine",
            ],
            (
                "Aurex must deterministically reconcile collateral, premiums, "
                "trading and delivery fees, realized and unrealized cash flows, "
                "option and hedge positions, margin, balances, settlement, and "
                "currency conversion without implicit borrowing."
            ),
        ),
        "CROSS_SOURCE_CLOCK_AND_INSTRUMENT_BINDING": gate(
            "CROSS_SOURCE_CLOCK_AND_INSTRUMENT_BINDING",
            [
                "exchange_and_local_timestamps",
                "option_underlying_index_identity",
                "hedge_instrument_identity",
                "expiry_delivery_clock_identity",
            ],
            (
                "Every option event must bind to exact instrument, underlying "
                "index, hedge instrument, exchange timestamp, local timestamp, "
                "expiry, and delivery clock under a no-forward-fill policy with "
                "explicit stale-state invalidation."
            ),
        ),
        "DATASET_IDENTITY_AND_GROUPED_OPTION_SCOPE": gate(
            "DATASET_IDENTITY_AND_GROUPED_OPTION_SCOPE",
            [
                "deribit_dataset_metadata",
                "OPTIONS_group_symbol_identity",
                "BTC_PERPETUAL_dataset_identity",
                "twenty_seven_header_observations",
            ],
            (
                "Tardis metadata must expose every frozen data type for the exact "
                "OPTIONS and BTC-PERPETUAL dataset symbols, and all 27 first-day "
                "HEAD requests must return unambiguous successful identities and "
                "nonzero projected content lengths."
            ),
        ),
        "DELTA_GREEK_AND_DISCRETE_HEDGE_STATE_MACHINE": gate(
            "DELTA_GREEK_AND_DISCRETE_HEDGE_STATE_MACHINE",
            [
                "point_in_time_delta_gamma_vega_inputs",
                "frozen_hedge_trigger_and_frequency",
                "stale_greek_and_stale_hedge_fail_closed_rules",
            ],
            (
                "Aurex must reproduce point-in-time option Greeks and underlying "
                "inputs without future data, define discrete hedge timing before "
                "outcomes, cap unhedged delta/gamma/vega, and halt on stale or "
                "missing option, index, Greek, or hedge state."
            ),
        ),
        "DETERMINISTIC_MULTI_LEG_ORDER_LIFECYCLE": gate(
            "DETERMINISTIC_MULTI_LEG_ORDER_LIFECYCLE",
            [
                "option_and_hedge_client_order_ids",
                "ack_reject_partial_cancel_and_unknown_state_transitions",
                "non_atomic_leg_rollback_and_emergency_flattening",
            ],
            (
                "The option and hedge legs must use unique client IDs and explicit "
                "acknowledge, reject, partial fill, cancel, timeout, and unknown "
                "transitions. No atomic fill assumption is allowed; bounded "
                "rollback, emergency flattening, and halt rules must be testable."
            ),
        ),
        "DISCONNECT_SEQUENCE_AND_SOURCE_REVISION_INTEGRITY": gate(
            "DISCONNECT_SEQUENCE_AND_SOURCE_REVISION_INTEGRITY",
            [
                "raw_disconnect_markers",
                "book_prev_change_id_recovery",
                "dataset_revision_or_integrity_headers",
                "byte_hash_and_gzip_integrity",
            ],
            (
                "A later payload pilot must preserve disconnect markers, sequence "
                "or prev_change_id recovery, fresh snapshots, local byte hashes, "
                "gzip integrity, and upstream revision identity. CSV files alone "
                "cannot satisfy disconnect recovery because they omit disconnects."
            ),
        ),
        "HEDGE_BBO_TRADE_AND_DERIVATIVE_TICKER_FOUNDATION": gate(
            "HEDGE_BBO_TRADE_AND_DERIVATIVE_TICKER_FOUNDATION",
            [
                "BTC_PERPETUAL_quotes",
                "BTC_PERPETUAL_trades",
                "BTC_PERPETUAL_book_snapshots",
                "BTC_PERPETUAL_derivative_ticker",
            ],
            (
                "Every frozen hedge source product must exist with exchange and "
                "local timestamps, executable bid/ask quantities, trades, index "
                "and derivative state, and later sequence-aware recovery. Underlying "
                "candles, marks, or midpoints cannot substitute for hedge fills."
            ),
        ),
        "OPTION_BBO_QUANTITY_AND_BOOK_SNAPSHOT_FOUNDATION": gate(
            "OPTION_BBO_QUANTITY_AND_BOOK_SNAPSHOT_FOUNDATION",
            [
                "OPTIONS_quotes",
                "OPTIONS_book_snapshot_25",
                "bid_ask_quantity_schema",
                "later_sequence_aware_option_book_source",
            ],
            (
                "Grouped option quotes and book snapshots must cover every active "
                "instrument with executable bid and ask quantities, exchange and "
                "local timestamps, and a later raw sequence/recovery source. Marks, "
                "midpoints, model values, and trade-only evidence are prohibited."
            ),
        ),
        "OPTION_CHAIN_INSTRUMENT_LIFECYCLE_FOUNDATION": gate(
            "OPTION_CHAIN_INSTRUMENT_LIFECYCLE_FOUNDATION",
            [
                "OPTIONS_options_chain",
                "instrument_listing_and_expiry_identity",
                "strike_type_contract_size_and_settlement_identity",
            ],
            (
                "The source foundation must enumerate all active and expired BTC "
                "options with listing, expiry, strike, put/call type, contract size, "
                "tick and amount rules, underlying index, settlement currency, and "
                "delivery semantics at each point in time."
            ),
        ),
        "OPTION_TRADE_AND_LIQUIDATION_FOUNDATION": gate(
            "OPTION_TRADE_AND_LIQUIDATION_FOUNDATION",
            [
                "OPTIONS_trades",
                "OPTIONS_liquidations",
                "trade_and_liquidation_timestamp_identity",
            ],
            (
                "Grouped option trade and liquidation products must exist across "
                "the frozen dates and later prove complete identity, timestamp, "
                "side, amount-schema, and incident coverage without using trade "
                "prices as a substitute for executable BBO."
            ),
        ),
        "POINT_IN_TIME_CONTRACT_EXPIRY_AND_SETTLEMENT_RULES": gate(
            "POINT_IN_TIME_CONTRACT_EXPIRY_AND_SETTLEMENT_RULES",
            [
                "dated_contract_specifications",
                "expiry_exercise_delivery_and_settlement_rules",
                "delivery_price_and_index_composition",
            ],
            (
                "Dated evidence must bind each option and hedge contract's size, "
                "tick, amount, expiry, exercise, delivery price, index composition, "
                "settlement, and currency rules throughout 2023-2024. Current "
                "documentation cannot be projected backward."
            ),
        ),
        "POINT_IN_TIME_FEES_CAPS_AND_DELIVERY_FEES": gate(
            "POINT_IN_TIME_FEES_CAPS_AND_DELIVERY_FEES",
            [
                "dated_option_fee_schedule_and_caps",
                "dated_hedge_fee_schedule",
                "dated_delivery_and_liquidation_fees",
                "account_tier_and_fee_currency",
            ],
            (
                "A complete dated 2023-2024 fee record must establish option and "
                "hedge maker/taker fees, option fee caps, delivery, settlement and "
                "liquidation fees, account tier, and fee currency. Current or "
                "estimated fees are hard failures."
            ),
        ),
        "POINT_IN_TIME_MARGIN_LIQUIDATION_AND_ACCOUNT_MODE": gate(
            "POINT_IN_TIME_MARGIN_LIQUIDATION_AND_ACCOUNT_MODE",
            [
                "dated_standard_or_portfolio_margin_parameters",
                "dated_liquidation_and_insurance_rules",
                "account_mode_and_collateral_currency",
            ],
            (
                "Dated evidence must reproduce standard or portfolio margin, "
                "collateral and haircut rules, liquidation thresholds and process, "
                "insurance treatment, account mode, and cross-position effects for "
                "every simulated state. Current rules cannot substitute."
            ),
        ),
        "TAIL_LOSS_CAPACITY_CONCENTRATION_AND_KILL_SWITCHES": gate(
            "TAIL_LOSS_CAPACITY_CONCENTRATION_AND_KILL_SWITCHES",
            [
                "displayed_option_and_hedge_quantity_caps",
                "spread_open_interest_and_concentration_caps",
                "jump_volatility_skew_and_liquidity_stress",
                "margin_daily_loss_and_disconnect_kill_switches",
            ],
            (
                "Before returns, Aurex must cap displayed-liquidity participation, "
                "spread, open interest, strike/expiry concentration, unhedged Greeks, "
                "margin usage, daily loss, and worst-case tail loss, with no "
                "automatic rearm after stale data or reconciliation breach."
            ),
        ),
        "TRANSPORT_STORAGE_COMMERCIAL_AND_RESOURCE_FEASIBILITY": gate(
            "TRANSPORT_STORAGE_COMMERCIAL_AND_RESOURCE_FEASIBILITY",
            [
                "twenty_eight_request_journal",
                "content_length_storage_projection",
                "commercial_entitlement_and_cost",
                "bounded_payload_transport_plan",
            ],
            (
                "All 28 census requests must complete inside frozen zero-retry "
                "budgets, projected 2023-2024 storage must remain below the 2 TiB "
                "ceiling, and a credible subscription, transfer, checksum, storage, "
                "and replay plan must be approved before any dataset or raw payload "
                "GET is authorized."
            ),
        ),
    }
    return [gates[gate_id] for gate_id in V4P02_REQUIRED_GATE_IDS]


def terminal_artifacts() -> V4P02TerminalArtifactContract:
    return V4P02TerminalArtifactContract(
        complete_artifact=(
            "data/evidence/v4_p02_source_census_complete_v1.json"
        ),
        reject_artifact="data/evidence/v4_p02_source_census_reject_v1.json",
        transport_stop_artifact=(
            "data/evidence/v4_p02_source_census_transport_stop_v1.json"
        ),
    )


def authoritative_contract(
    *,
    frozen_at: datetime,
    charter,
    register,
) -> V4P02FeasibilityContract:
    proposal = register.proposals[1]
    if proposal.proposal_id != (
        "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM"
    ):
        raise ValueError("V4P02 proposal identity changed")
    return build_v4_p02_feasibility_contract(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        proposal_evidence_hash=universe_evidence_hash(proposal.model_dump()),
        builder_contract_hash=builder_contract_hash(),
        proposal_id=proposal.proposal_id,
        development_start=datetime(2023, 1, 1, tzinfo=UTC),
        development_end=datetime(2025, 1, 1, tzinfo=UTC),
        sample_dates=V4P02_SAMPLE_DATES,
        dataset_products=[
            {
                "data_type": data_type,
                "symbol": symbol,
                "role": role,
            }
            for data_type, symbol, role in V4P02_DATASET_PRODUCTS
        ],
        requests=requests(),
        transport_budget=V4P02TransportBudget(),
        execution_gates=execution_gates(),
        permitted_observation_fields=V4P02_PERMITTED_OBSERVATION_FIELDS,
        prohibited_parsed_fields=V4P02_PROHIBITED_PARSED_FIELDS,
        journal_policy=V4P02_JOURNAL_POLICY,
        stop_conditions=V4P02_STOP_CONDITIONS,
        official_documentation_sources=[
            "https://docs.tardis.dev/api/http",
            "https://docs.tardis.dev/downloadable-csv-files",
            "https://docs.tardis.dev/historical-data-details/deribit",
            (
                "https://docs.deribit.com/api-reference/market-data/"
                "public-get_instrument"
            ),
            "https://statics.deribit.com/files/DeribitInstitutionalSetupGuide.pdf",
            "https://support.deribit.com/hc/en-us/articles/25944746248989-Fees",
        ],
        journal_path=(
            "data/evidence/v4_p02_source_census/transport_journal_v1.ndjson"
        ),
        metadata_observation_path=(
            "data/evidence/v4_p02_source_census/"
            "metadata_observation_v1.json"
        ),
        header_observation_path=(
            "data/evidence/v4_p02_source_census/"
            "header_observations_v1.ndjson"
        ),
        terminal_artifacts=terminal_artifacts(),
        limitations=[
            (
                "This contract performs one public metadata GET and 27 public "
                "zero-body HEAD requests only; it cannot inspect dataset schemas."
            ),
            (
                "The three first-of-month dates are bounded source probes and do "
                "not establish 95 percent daily or 90 percent monthly completeness."
            ),
            (
                "No dataset payload, raw replay, Deribit API request, credential, "
                "retry, range, or resume is authorized; dataset HEAD redirects are "
                "limited to three manually validated public HTTPS hops."
            ),
            (
                "Content-Length is a storage projection, not proof of gzip, row, "
                "timestamp, symbol, quote, trade, or option-chain integrity."
            ),
            (
                "CSV datasets omit disconnect events; a later raw pilot is "
                "mandatory for disconnect and sequence recovery."
            ),
            (
                "Current Deribit instrument, fee, margin, liquidation, delivery, "
                "and settlement documentation is not historical 2023-2024 truth."
            ),
            (
                "The option strategy is negatively convex and passing source "
                "headers would not establish bounded tail loss or profitability."
            ),
            (
                "Public source access does not establish operator jurisdiction, "
                "KYC, derivatives eligibility, account mode, or API access."
            ),
            (
                "Grouped OPTIONS data must later be cross-bound to BTC-PERPETUAL "
                "hedge and index state at exchange and local timestamps."
            ),
            (
                "No mark, midpoint, model value, Greek, trade, or candle may be "
                "used as an assumed executable option or hedge fill."
            ),
            (
                "No parameter, price, Greek, margin value, signal, trade, P/L, "
                "return, candidate, validation, paper, sandbox, live, or capital "
                "permission exists."
            ),
        ],
    )


def write_contract(path: Path, contract: V4P02FeasibilityContract) -> None:
    serialized = (contract.model_dump_json(indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale V4P02 output exists: {temporary}")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def run_check(args) -> V4P02FeasibilityContract:
    charter, register = load_inputs(args.charter, args.register)
    stored = V4P02FeasibilityContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=stored.frozen_at,
        charter=charter,
        register=register,
    )
    if stored != expected or not audit_v4_p02_feasibility_contract(stored):
        raise ValueError("Frozen V4P02 feasibility contract audit failed")
    print(
        f"PASS v4p02_contract={stored.contract_evidence_hash} "
        f"metadata_gets={stored.transport_budget.metadata_get_budget} "
        f"dataset_heads={stored.transport_budget.dataset_head_budget} "
        f"payload_gets={stored.dataset_payload_gets_permitted} "
        f"selected={stored.selects_primary} returns={stored.return_metrics_calculated}",
        flush=True,
    )
    return stored


def run_freeze(args) -> V4P02FeasibilityContract:
    if args.output.exists():
        raise ValueError("V4P02 feasibility contract exists; use --check")
    charter, register = load_inputs(args.charter, args.register)
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
    )
    write_contract(args.output, contract)
    return run_check(args)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or audit the pre-network V4P02 Deribit metadata and "
            "dataset-header census contract."
        )
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            run_check(args)
        else:
            run_freeze(args)
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
