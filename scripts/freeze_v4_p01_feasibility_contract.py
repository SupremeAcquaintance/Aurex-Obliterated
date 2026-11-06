import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from aurex.backtest_engine.research_v4_discovery_charter import (
    V4MechanismDiscoveryCharter,
    audit_v4_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v4_p01_feasibility_contract import (
    V4P01_JOURNAL_POLICY,
    V4P01_PERMITTED_OBSERVATION_FIELDS,
    V4P01_PROHIBITED_PARSED_FIELDS,
    V4P01_REQUIRED_GATE_IDS,
    V4P01_STOP_CONDITIONS,
    V4P01ExecutionGate,
    V4P01FeasibilityContract,
    V4P01SourceRequest,
    V4P01TerminalArtifactContract,
    V4P01TransportBudget,
    audit_v4_p01_feasibility_contract,
    build_v4_p01_feasibility_contract,
)
from aurex.backtest_engine.research_v4_proposal_register import (
    V4MechanismProposalRegister,
    audit_v4_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v4_p01_feasibility_contract_v1.json"
)
REQUEST_HEADERS = {
    "Accept": "application/json, application/x-ndjson",
    "Accept-Encoding": "gzip",
    "User-Agent": "Aurex-V4P01-Feasibility/1.0",
}


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
            / "freeze_v4_p01_feasibility_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p01_feasibility_contract.py",
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


def register_builder_contract_hash() -> str:
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


def load_inputs(
    charter_path: Path,
    register_path: Path,
) -> tuple[V4MechanismDiscoveryCharter, V4MechanismProposalRegister]:
    charter = V4MechanismDiscoveryCharter.model_validate_json(
        charter_path.read_text(encoding="utf-8")
    )
    if (
        not audit_v4_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_contract_hash()
        or charter.v3_final_decision != "SELECT_ZERO_V3_PRIMARY_MECHANISMS"
        or charter.charter_authorizes_network_requests
        or charter.maximum_selected_primary_mechanisms != 1
        or charter.maximum_return_tested_mechanisms_under_charter != 0
    ):
        raise ValueError("V4 discovery charter audit failed")

    register = V4MechanismProposalRegister.model_validate_json(
        register_path.read_text(encoding="utf-8")
    )
    if (
        not audit_v4_mechanism_proposal_register(register)
        or register.builder_contract_hash != register_builder_contract_hash()
        or register.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
        or register.selected_primary_count != 0
        or register.parameter_set_count != 0
        or register.authorizes_network_requests
        or register.authorizes_return_testing
    ):
        raise ValueError("V4 proposal register audit failed")
    return charter, register


def metadata_request(
    *,
    sequence: int,
    exchange_id: str,
) -> V4P01SourceRequest:
    return V4P01SourceRequest(
        request_id=f"V4P01_META_{exchange_id.upper()}_EXCHANGE_DETAILS",
        phase="METADATA_CENSUS",
        sequence=sequence,
        url=f"https://api.tardis.dev/v1/exchanges/{exchange_id}",
        exchange_id=exchange_id,
        product_id=None,
        sample_at=None,
        offset_minutes=None,
        required_channels=["exchange_metadata"],
        request_headers=REQUEST_HEADERS,
        total_wall_clock_timeout_seconds=60,
        maximum_response_bytes=8_388_608,
    )


def payload_url(
    *,
    exchange_id: str,
    sample_date: datetime,
    offset_minutes: int,
) -> str:
    if exchange_id == "binance":
        filters = [
            {"channel": channel, "symbols": ["ethbtc"]}
            for channel in ("bookTicker", "depth", "depthSnapshot")
        ]
    else:
        filters = [
            {"channel": channel, "symbols": ["ETH-BTC"]}
            for channel in ("l2update", "snapshot")
        ]
    query = urlencode(
        {
            "from": sample_date.date().isoformat(),
            "offset": str(offset_minutes),
            "filters": json.dumps(
                filters,
                ensure_ascii=True,
                separators=(",", ":"),
            ),
        }
    )
    return f"https://api.tardis.dev/v1/data-feeds/{exchange_id}?{query}"


def payload_request(
    *,
    sequence: int,
    exchange_id: str,
    sample_date: datetime,
    offset_minutes: int,
) -> V4P01SourceRequest:
    sample_at = sample_date + timedelta(minutes=offset_minutes)
    stamp = sample_at.strftime("%Y%m%d_%H%M")
    product_id = "ethbtc" if exchange_id == "binance" else "ETH-BTC"
    channels = (
        ["bookTicker", "depth", "depthSnapshot"]
        if exchange_id == "binance"
        else ["l2update", "snapshot"]
    )
    return V4P01SourceRequest(
        request_id=f"V4P01_PILOT_{exchange_id.upper()}_{stamp}",
        phase="PAYLOAD_SCHEMA_PILOT",
        sequence=sequence,
        url=payload_url(
            exchange_id=exchange_id,
            sample_date=sample_date,
            offset_minutes=offset_minutes,
        ),
        exchange_id=exchange_id,
        product_id=product_id,
        sample_at=sample_at,
        offset_minutes=offset_minutes,
        required_channels=channels,
        request_headers=REQUEST_HEADERS,
        total_wall_clock_timeout_seconds=180,
        maximum_response_bytes=16_777_216,
    )


def requests() -> list[V4P01SourceRequest]:
    result = [
        metadata_request(sequence=1, exchange_id="binance"),
        metadata_request(sequence=2, exchange_id="coinbase"),
    ]
    sample_specs = [
        (datetime(2023, 1, 1, tzinfo=UTC), 0),
        (datetime(2023, 12, 1, tzinfo=UTC), 720),
        (datetime(2024, 12, 1, tzinfo=UTC), 1439),
    ]
    sequence = 3
    for sample_date, offset_minutes in sample_specs:
        for exchange_id in ("binance", "coinbase"):
            result.append(
                payload_request(
                    sequence=sequence,
                    exchange_id=exchange_id,
                    sample_date=sample_date,
                    offset_minutes=offset_minutes,
                )
            )
            sequence += 1
    return result


def gate(
    gate_id: str,
    evidence: list[str],
    pass_condition: str,
) -> V4P01ExecutionGate:
    return V4P01ExecutionGate(
        gate_id=gate_id,
        evidence_required=evidence,
        pass_condition=pass_condition,
    )


def execution_gates() -> list[V4P01ExecutionGate]:
    gates = [
        gate(
            "ACCOUNT_AND_JURISDICTION_ACCESS",
            [
                "current_official_venue_terms_and_restriction_evidence",
                "operator_attestation_for_two_verified_trade_capable_accounts",
            ],
            (
                "The operator jurisdiction is not prohibited, and separate Binance "
                "Spot and Coinbase Exchange accounts are verified as able to hold "
                "ETH and BTC and trade the exact bound products. Public API access "
                "or documentation alone cannot pass this gate."
            ),
        ),
        gate(
            "ARCHIVE_CALENDAR_AND_INCIDENT_COVERAGE",
            [
                "binance_tardis_exchange_metadata_hash",
                "coinbase_tardis_exchange_metadata_hash",
                "target_symbol_availability_and_incident_boundaries",
            ],
            (
                "Both exact products cover the complete 2023-2024 development "
                "boundary, all source-declared incidents are preserved, at least "
                "95 percent of calendar days and 90 percent of months can be "
                "qualified, and no incident is silently treated as tradable time."
            ),
        ),
        gate(
            "CAPACITY_AND_STALENESS_FOUNDATION",
            [
                "bbo_quantity_schema_presence",
                "exchange_and_local_timestamp_schema",
                "future_predeclared_capacity_and_staleness_model_requirement",
            ],
            (
                "Both feeds expose displayed BBO quantity and exchange/local timing "
                "needed for a later capacity and staleness model. No numeric threshold "
                "or market value is selected under this feasibility contract."
            ),
        ),
        gate(
            "COMMON_ETH_BTC_PRODUCT_IDENTITY",
            [
                "binance_ethbtc_metadata_identity",
                "coinbase_eth_btc_metadata_identity",
                "base_quote_asset_mapping",
            ],
            (
                "Binance ethbtc and Coinbase ETH-BTC both identify ETH as base and "
                "BTC as quote throughout the development boundary, with no synthetic "
                "USD, stablecoin, index, derivative, or asset-conversion substitution."
            ),
        ),
        gate(
            "DETERMINISTIC_TWO_LEG_STATE_MACHINE",
            [
                "synthetic_order_lifecycle_scenarios",
                "unique_client_order_identity_contract",
                "balance_position_inventory_reconciliation_contract",
            ],
            (
                "A separately tested state machine can represent independent submit, "
                "ack, reject, partial fill, cancel, unknown, rollback, flatten, "
                "balance, and inventory states for both venues without assuming "
                "cross-venue atomicity."
            ),
        ),
        gate(
            "DISCONNECT_SNAPSHOT_AND_SEQUENCE_RECOVERY",
            [
                "raw_disconnect_marker_schema",
                "reconnect_snapshot_schema",
                "venue_sequence_or_update_identifier_schema",
            ],
            (
                "Every source disconnect begins a nontradable segment and requires a "
                "fresh snapshot before rearm. Binance update identifiers and Coinbase "
                "ordered L2 updates or reconnect snapshots must support gap detection "
                "or fail closed without inferred book state."
            ),
        ),
        gate(
            "EXCHANGE_AND_LOCAL_TIMESTAMP_IDENTITY",
            [
                "raw_local_capture_timestamp_schema",
                "exchange_event_timestamp_or_documented_absence",
                "clock_order_and_duplicate_evidence",
            ],
            (
                "Every event has a source local capture timestamp, exchange timestamps "
                "are preserved where supplied, absence is explicit, and line order is "
                "available as the tie breaker without modifying or synthesizing time."
            ),
        ),
        gate(
            "IOC_OR_FOK_ORDER_SEMANTICS",
            [
                "binance_current_official_order_semantics",
                "coinbase_current_official_order_semantics",
                "historical_rule_change_limitations",
            ],
            (
                "Both venues document an immediately executable bounded order path "
                "and acknowledgement lifecycle suitable for one-leg risk control. "
                "Any unsupported historical rule period is rejected rather than "
                "filled using current behavior."
            ),
        ),
        gate(
            "POINT_IN_TIME_FEES_AND_FEE_CURRENCY",
            [
                "dated_binance_spot_fee_schedule_or_hard_upper_bound",
                "dated_coinbase_exchange_fee_schedule_or_hard_upper_bound",
                "fee_currency_discount_and_tier_history",
            ],
            (
                "A date-effective, account-applicable taker-fee and fee-currency upper "
                "bound exists for every development session on both venues. Current "
                "rates, assumed VIP tiers, rebates, or unbounded estimates cannot pass."
            ),
        ),
        gate(
            "POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE",
            [
                "dated_tick_lot_notional_and_price_band_evidence",
                "product_listing_halt_auction_and_maintenance_evidence",
                "historical_rule_change_evidence",
            ],
            (
                "Both products have date-effective tick, lot, notional, price-band, "
                "listing, halt, auction, and maintenance state for every modeled "
                "session. Current filters cannot be projected backward."
            ),
        ),
        gate(
            "PRE_FUNDED_INVENTORY_AND_BALANCE_ACCOUNTING",
            [
                "base_inventory_on_prospective_sell_venue",
                "quote_inventory_on_prospective_buy_venue",
                "transfer_rebalance_and_custody_cost_contract",
            ],
            (
                "The design requires pre-funded ETH and BTC on both venues, treats "
                "transfers only as non-atomic rebalancing, accounts for custody and "
                "idle capital, and blocks a new attempt until both balances reconcile."
            ),
        ),
        gate(
            "RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES",
            [
                "binance_book_ticker_depth_and_snapshot_schema",
                "coinbase_l2_update_and_snapshot_schema",
                "bid_ask_and_quantity_key_presence_without_value_parsing",
            ],
            (
                "All six sample responses preserve exchange-native BBO or L2 updates, "
                "snapshots, symbols, bid/ask prices and quantities as schema keys. "
                "Trades, candles, or schema-less normalized values cannot substitute."
            ),
        ),
        gate(
            "SOURCE_REVISION_AND_BYTE_INTEGRITY",
            [
                "response_header_and_local_sha256_manifest",
                "metadata_revision_identity",
                "partial_byte_count_and_hash_policy",
            ],
            (
                "Every retained response has request identity, selected headers, byte "
                "count, SHA-256, and source metadata revision identity. Any mutable "
                "source limitation is explicit and no failed partial response is "
                "reported as complete."
            ),
        ),
        gate(
            "TRANSPORT_RESOURCE_AND_STORAGE_FEASIBILITY",
            [
                "durable_attempt_journal",
                "cumulative_byte_elapsed_and_storage_totals",
                "all_eight_terminal_request_records",
            ],
            (
                "All eight one-attempt requests complete within their frozen response, "
                "wall-clock, total-byte, and storage budgets, with no retry, resume, "
                "or unreconciled intent. Otherwise the protocol stops as transport "
                "unresolved."
            ),
        ),
    ]
    by_id = {item.gate_id: item for item in gates}
    return [by_id[gate_id] for gate_id in V4P01_REQUIRED_GATE_IDS]


def terminal_artifacts() -> V4P01TerminalArtifactContract:
    return V4P01TerminalArtifactContract(
        complete_artifact=(
            "data/evidence/v4_p01_feasibility_complete_result_v1.json"
        ),
        reject_artifact=(
            "data/evidence/v4_p01_feasibility_reject_result_v1.json"
        ),
        transport_stop_artifact=(
            "data/evidence/v4_p01_feasibility_transport_stop_v1.json"
        ),
        required_common_fields=[
            "builder_and_contract_hashes",
            "completed_and_failed_request_ids",
            "decision",
            "execution_gate_results",
            "metadata_and_payload_observation_hashes",
            "parsed_and_prohibited_field_manifest",
            "request_journal_hash",
            "resource_totals",
            "selection_and_permission_boundary",
            "terminal_timestamp",
        ],
        required_transport_stop_fields=[
            "failed_request_id_and_attempt",
            "failure_class_and_message",
            "partial_byte_count_and_sha256",
            "request_intent_record_hash",
            "response_headers_if_received",
            "unconsumed_request_and_byte_budgets",
            "unreconciled_intent_status",
        ],
    )


def authoritative_contract(
    *,
    frozen_at: datetime,
    charter: V4MechanismDiscoveryCharter,
    register: V4MechanismProposalRegister,
) -> V4P01FeasibilityContract:
    proposal = register.proposals[0]
    if proposal.proposal_id != (
        "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE"
    ):
        raise ValueError("V4P01 proposal identity changed")
    return build_v4_p01_feasibility_contract(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        proposal_evidence_hash=universe_evidence_hash(proposal.model_dump()),
        builder_contract_hash=builder_contract_hash(),
        proposal_id=proposal.proposal_id,
        development_start=datetime(2023, 1, 1, tzinfo=UTC),
        development_end=datetime(2025, 1, 1, tzinfo=UTC),
        requests=requests(),
        transport_budget=V4P01TransportBudget(),
        execution_gates=execution_gates(),
        permitted_observation_fields=V4P01_PERMITTED_OBSERVATION_FIELDS,
        prohibited_parsed_fields=V4P01_PROHIBITED_PARSED_FIELDS,
        journal_policy=V4P01_JOURNAL_POLICY,
        stop_conditions=V4P01_STOP_CONDITIONS,
        journal_path="data/evidence/v4_p01/transport_journal_v1.ndjson",
        metadata_observation_path=(
            "data/evidence/v4_p01/metadata_observations_v1.ndjson"
        ),
        payload_observation_path=(
            "data/evidence/v4_p01/payload_observations_v1.ndjson"
        ),
        raw_payload_directory="data/evidence/v4_p01/raw",
        terminal_artifacts=terminal_artifacts(),
        limitations=[
            (
                "This contract authorizes exactly eight public Tardis GET requests "
                "and no other network target, method, credential, retry, or resume."
            ),
            (
                "The six payload samples are one-minute schema and transport pilots "
                "on free first-of-month data and cannot establish a tradable edge."
            ),
            (
                "Only ETH/BTC on Binance Spot and Coinbase Exchange is in scope; "
                "no USD, stablecoin, derivative, or asset-conversion proxy is allowed."
            ),
            (
                "Raw payload bytes contain market values, but the runner may only "
                "hash and inspect schema, identity, timestamp, sequence, disconnect, "
                "snapshot, row-count, and resource fields."
            ),
            (
                "Tardis is an independent vendor and its locally captured bytes are "
                "not exchange-signed or guaranteed immutable by the venues."
            ),
            (
                "Free sample access does not establish affordable complete-history "
                "access; commercial entitlement and full storage cost remain unresolved."
            ),
            (
                "Current exchange documentation is not point-in-time proof of "
                "2023-2024 fees, filters, product state, or order semantics."
            ),
            (
                "No conservative override is permitted for account access, fees, "
                "filters, venue state, source integrity, or two-leg reconciliation."
            ),
            (
                "A metadata or payload transport failure writes a terminal stop and "
                "cannot be retried or repaired under this contract."
            ),
            (
                "Passing all source pilots still does not select V4P01; every "
                "execution gate must independently pass before a terminal screen."
            ),
            (
                "No parameter, market value, signal, trade, P/L, return, candidate, "
                "validation, Pine, paper, sandbox, live, or capital permission exists."
            ),
        ],
    )


def write_contract(path: Path, contract: V4P01FeasibilityContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if V4P01FeasibilityContract.model_validate_json(serialized) != contract:
        raise ValueError("V4P01 feasibility contract JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V4P01FeasibilityContract:
    if args.output.exists():
        raise ValueError("Frozen V4P01 contract exists; use --check")
    charter, register = load_inputs(args.charter, args.register)
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
    )
    write_contract(args.output, contract)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"requests={len(contract.requests)} "
        f"attempts={contract.transport_budget.total_attempt_budget} "
        f"returns={contract.return_metrics_calculated}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V4P01FeasibilityContract:
    charter, register = load_inputs(args.charter, args.register)
    contract = V4P01FeasibilityContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=contract.frozen_at,
        charter=charter,
        register=register,
    )
    if (
        contract != expected
        or not audit_v4_p01_feasibility_contract(contract)
    ):
        raise ValueError("V4P01 feasibility contract is not reproducible")
    print(
        "PASS "
        f"v4p01_contract={contract.contract_evidence_hash} "
        f"network={contract.authorized_network_scope} "
        f"requests={len(contract.requests)} "
        f"selected={contract.selects_primary} "
        f"returns={contract.return_metrics_calculated}",
        flush=True,
    )
    return contract


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the V4P01 crash-safe no-return feasibility contract."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
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
