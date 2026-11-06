from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_successor_charter import (  # noqa: E402
    S1MacroFinancialConditionsCharter,
    S1OperatorScope,
    S1Partition,
    S1ResearchSource,
    S1SourceBinding,
    S1SuccessorLineageAudit,
    S1SuccessorLineageLedger,
    audit_s1_charter,
    audit_s1_lineage,
    audit_s1_lineage_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s1_macro_financial_conditions_charter_v1.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s1_successor_charter.py")
SCRIPT_PATH = Path("scripts/freeze_s1_macro_financial_conditions_charter.py")
LINEAGE_PATH = Path("data/evidence/s1_successor_lineage_ledger_v1.json")
LINEAGE_AUDIT_PATH = Path("data/evidence/s1_successor_lineage_audit_v1.json")
FACTORY_PATH = Path("data/evidence/aurex_strategy_factory_contract_v1.json")
PROFILE_PATH = Path("data/evidence/binance_spot_testnet_sandbox_profile_v1.json")
Q1_AUDIT_PATH = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v7.json"
)


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def load_and_validate_inputs() -> None:
    lineage = S1SuccessorLineageLedger.model_validate_json(
        LINEAGE_PATH.read_text(encoding="utf-8")
    )
    audit = S1SuccessorLineageAudit.model_validate_json(
        LINEAGE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if not audit_s1_lineage(lineage) or not audit_s1_lineage_audit(audit):
        raise ValueError("S1 lineage or its audit is invalid")
    if audit.ledger_evidence_hash != lineage.ledger_evidence_hash:
        raise ValueError("S1 lineage audit does not bind the frozen ledger")

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    operator = profile.get("operator_input") or {}
    required = {
        "permitted_product_scope": "SPOT_ONLY",
        "maximum_effective_leverage": "1",
        "one_time_data_budget": "0",
        "monthly_data_budget": "0",
        "real_capital_authorized": False,
        "live_trading_authorized": False,
    }
    for key, expected in required.items():
        if operator.get(key) != expected:
            raise ValueError(f"S1 operator boundary changed: {key}")
    if operator.get("permitted_symbols") != ["BTCUSDT"]:
        raise ValueError("S1 operator symbol scope changed")
    if profile.get("decision") != (
        "AUTHORIZE_SANDBOX_ADAPTER_IMPLEMENTATION_AND_SUCCESSOR_CHARTER_DESIGN_ONLY"
    ):
        raise ValueError("S1 successor charter design authority is absent")


def bindings() -> tuple[S1SourceBinding, ...]:
    paths = sorted(
        (LINEAGE_PATH, LINEAGE_AUDIT_PATH, FACTORY_PATH, PROFILE_PATH, Q1_AUDIT_PATH),
        key=lambda item: item.as_posix(),
    )
    return tuple(
        S1SourceBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def research_sources(*, accessed_at: datetime) -> tuple[S1ResearchSource, ...]:
    return (
        S1ResearchSource(
            source_id="CHICAGO-FED-NFCI-CURRENT-DATA",
            title="National Financial Conditions Index: Current Data",
            authors_or_publisher=("Federal Reserve Bank of Chicago",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_METHOD_DOCUMENTATION",
            url="https://www.chicagofed.org/research/data/nfci/current-data",
            supported_claims=(
                "NFCI is a weekly measure spanning money, debt, equity, traditional "
                "banking, and shadow-banking conditions.",
                "The index normally updates Wednesday at 08:30 Eastern Time for the prior Friday.",
                "Historical NFCI values can change because inputs and estimated "
                "weights are revised.",
            ),
            limitations=(
                "The current-data page is not a point-in-time historical dataset.",
                "An NFCI relationship does not establish a tradeable Bitcoin edge.",
            ),
        ),
        S1ResearchSource(
            source_id="FRED-ALFRED-REALTIME-PERIODS",
            title="FRED API Real-Time Periods",
            authors_or_publisher=("Federal Reserve Bank of St. Louis",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url="https://fred.stlouisfed.org/docs/api/fred/realtime_period.html",
            supported_claims=(
                "Real-time periods identify when an observation value was known and "
                "when it changed.",
                "Historical vintages can be requested with explicit real-time boundaries.",
            ),
            limitations=(
                "Documented API capability does not prove endpoint access, coverage, "
                "or immutable response identity.",
            ),
        ),
        S1ResearchSource(
            source_id="FRED-ALFRED-VERSUS",
            title="FRED versus ALFRED",
            authors_or_publisher=("Federal Reserve Bank of St. Louis",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url="https://fred.stlouisfed.org/docs/api/fred/fred_vs_alfred.html",
            supported_claims=(
                "FRED defaults to today's best history while ALFRED can reproduce "
                "what was known on a past date.",
            ),
            limitations=(
                "Using current FRED history in a historical signal would introduce "
                "revision leakage.",
            ),
        ),
        S1ResearchSource(
            source_id="KARAU-2023-MONETARY-POLICY-BITCOIN",
            title="Monetary policy and Bitcoin",
            authors_or_publisher=("Soren Karau",),
            publication_or_revision_date="2023-10-01",
            accessed_at=accessed_at,
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1016/j.jimonfin.2023.102880",
            supported_claims=(
                "Bitcoin's response to US monetary policy has varied over time.",
                "After 2020 Bitcoin reacted more like a risky asset to tightening shocks.",
            ),
            limitations=(
                "The documented relationship is regime-dependent and does not "
                "validate NFCI timing or after-cost profitability.",
            ),
        ),
        S1ResearchSource(
            source_id="MA-TIAN-HSIAO-DENG-2022",
            title="Monetary policy shocks and Bitcoin prices",
            authors_or_publisher=(
                "Chaoqun Ma",
                "Liurui Deng",
                "Shisong Hsiao",
                "Yonggang Tian",
            ),
            publication_or_revision_date="2022-12-01",
            accessed_at=accessed_at,
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1016/j.ribaf.2022.101711",
            supported_claims=(
                "Unexpected US monetary tightening is associated with lower Bitcoin "
                "prices and persistent post-announcement effects.",
                "The estimated response varies with market state.",
            ),
            limitations=(
                "FOMC surprise evidence is not the same signal as weekly NFCI releases.",
                "The paper does not prove a deployable long-or-cash rule after retail spot costs.",
            ),
        ),
    )


def partitions() -> tuple[S1Partition, ...]:
    return (
        S1Partition(
            role="DEVELOPMENT",
            start="2017-08-17T00:00:00Z",
            end="2023-01-01T00:00:00Z",
            state="SEALED_PENDING_SOURCE_FEASIBILITY",
        ),
        S1Partition(
            role="HISTORICAL_VALIDATION",
            start="2023-01-01T00:00:00Z",
            end="2025-01-01T00:00:00Z",
            state="SEALED_PENDING_SOURCE_FEASIBILITY",
        ),
        S1Partition(
            role="CONTAMINATION_WASHOUT",
            start="2025-01-01T00:00:00Z",
            end="2026-11-07T00:00:00Z",
            state="EXCLUDED_PRIOR_OUTCOME_AWARENESS",
        ),
        S1Partition(
            role="FUTURE_HOLDOUT",
            start="2026-11-07T00:00:00Z",
            end="2027-05-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S1Partition(
            role="FORWARD",
            start="2027-05-07T00:00:00Z",
            end=None,
            state="LOCKED_FUTURE",
        ),
    )


def build_charter(*, frozen_at: datetime) -> S1MacroFinancialConditionsCharter:
    load_and_validate_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "predecessor_bindings": bindings(),
        "research_sources": research_sources(accessed_at=frozen_at),
        "operator_scope": S1OperatorScope(),
        "ex_ante_hypothesis": (
            "A causally observed easing in broad US financial conditions can increase "
            "global risk-bearing capacity and marginal demand for Bitcoin. Aurex "
            "will eventually test one preregistered weekly long-or-cash BTCUSDT Spot "
            "rule; tightening supplies a cash state, never a short."
        ),
        "causal_observation_policy": (
            "USE_ONLY_AN_ALFRED_NFCI_VALUE_WHOSE_REALTIME_START_DATE_IS_ON_OR_BEFORE_THE_DECISION_DATE",
            "NEVER_BACKFILL_A_REVISED_VALUE_INTO_AN_EARLIER_DECISION",
            "ENTER_NO_EARLIER_THAN_THE_NEXT_UTC_DAY_OPEN_AFTER_THE_RECORDED_RELEASE_DATE",
            "MISSING_AMBIGUOUS_OR_UNAVAILABLE_VINTAGE_FORCES_CASH",
            "CURRENT_FINAL_REVISED_NFCI_IS_DIAGNOSTIC_ONLY_AND_NONSELECTABLE",
        ),
        "exact_source_requirements": (
            "OFFICIAL_ALFRED_NFCI_VINTAGE_DATES_AND_REALTIME_PERIODS",
            "OFFICIAL_NFCI_RELEASE_AND_REVISION_DOCUMENTATION",
            "OFFICIAL_BINANCE_SPOT_BTCUSDT_DAILY_KLINES_WITH_PUBLISHED_CHECKSUMS",
            "POINT_IN_TIME_RELEASE_DATE_TO_NEXT_UTC_DAY_ALIGNMENT",
            "HISTORICAL_SPOT_FEES_TICK_SIZE_MINIMUM_QUANTITY_AND_NOTIONAL_OR_CONSERVATIVE_BOUNDS",
            "IMMUTABLE_REQUEST_RESPONSE_AND_FILE_HASH_EVIDENCE",
        ),
        "independence_exclusions": (
            "NO_PRICE_MOMENTUM_TREND_PULLBACK_OR_BREAKOUT_INPUT",
            "NO_VOLATILITY_SCALING_OR_PATH_QUALITY_INPUT",
            "NO_CANDLE_MEAN_REVERSION_OR_JAM_REVERSAL_INPUT",
            "NO_AGGRESSOR_FLOW_ORDER_BOOK_OR_CLOCK_PHASE_INPUT",
            "NO_FUNDING_BASIS_CARRY_OR_PERPETUAL_ORDER_FLOW_INPUT",
            "NO_CROSS_ASSET_RANKING_COINTEGRATION_OR_ROTATION",
            "NO_PASSIVE_MAKER_CROSS_VENUE_OR_OPTIONS_EXECUTION",
            "NO_REUSE_OF_PRIOR_DIAGNOSTIC_THRESHOLDS_OR_OUTCOMES",
        ),
        "feasibility_gates": (
            "S1_LINEAGE_AND_INDEPENDENT_AUDIT_VALID",
            "ZERO_PAID_DATA_AND_NO_PRODUCTION_CREDENTIAL_REQUIREMENT",
            "POINT_IN_TIME_NFCI_VINTAGES_AVAILABLE_FOR_COMPLETE_DEVELOPMENT_AND_VALIDATION",
            "RELEASE_DATES_AND_REVISIONS_RECONSTRUCTABLE_WITHOUT_FINAL_VALUE_LEAKAGE",
            "AT_LEAST_260_CAUSALLY_AVAILABLE_DEVELOPMENT_RELEASES",
            "BINANCE_SPOT_DAILY_SOURCE_METADATA_AND_CHECKSUMS_AVAILABLE",
            "NEXT_UTC_DAY_EXECUTION_IS_DETERMINISTIC_AND_SPOT_ONLY",
            "EXPECTED_TURNOVER_CAN_BE_MODELED_WITH_RETAIL_SPOT_COSTS",
            "ONE_SELECTABLE_MECHANISM_AND_ZERO_CHARTER_STAGE_PARAMETERS",
            "FAILURE_OF_ANY_GATE_SELECTS_ZERO_AND_STOPS_S1_BEFORE_OUTCOMES",
        ),
        "partitions": partitions(),
        "limitations": (
            "This charter selects a theory for source feasibility, not a profitable strategy.",
            "NFCI includes revised inputs and estimated weights; current revised "
            "history is forbidden for historical decisions.",
            "Published monetary-policy findings are mixed across regimes and do not "
            "establish NFCI predictability.",
            "Historical validation is not the final untouched test; the future "
            "holdout remains locked until 2027-05-07.",
            "No market value, parameter, return, candidate, paper order, Testnet "
            "strategy order, production action, live action, real capital, or profit "
            "is authorized.",
        ),
    }
    provisional = S1MacroFinancialConditionsCharter.model_construct(
        **payload,
        charter_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["charter_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"charter_evidence_hash"})
    )
    return S1MacroFinancialConditionsCharter.model_validate(complete)


def write_atomic(path: Path, charter: S1MacroFinancialConditionsCharter) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 charter transaction exists: {temporary}")
    serialized = charter.model_dump_json(indent=2) + "\n"
    if S1MacroFinancialConditionsCharter.model_validate_json(serialized) != charter:
        raise ValueError("S1 charter did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check the S1 macro charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1MacroFinancialConditionsCharter.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_charter(frozen_at=stored.frozen_at)
        if stored != expected or not audit_s1_charter(stored):
            raise SystemExit("Stored S1 charter differs from reconstruction")
        print(f"PASS {stored.charter_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S1 charter: {args.output}")
    charter = build_charter(frozen_at=datetime.now(UTC))
    write_atomic(args.output, charter)
    print(
        f"FROZEN {args.output} {charter.charter_evidence_hash} "
        "market_values=0 parameters=0 returns=0 candidates=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
