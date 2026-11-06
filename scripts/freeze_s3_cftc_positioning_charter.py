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
    S1SuccessorLineageAudit,
    S1SuccessorLineageLedger,
    audit_s1_lineage,
    audit_s1_lineage_audit,
)
from aurex.backtest_engine.s2_btc_source_execution import (  # noqa: E402
    S2BtcSourceAcquisitionAudit,
    S2BtcSourceAcquisitionResult,
)
from aurex.backtest_engine.s2_development_backtest import (  # noqa: E402
    S2DevelopmentBacktestResult,
    S2DevelopmentBacktestResultAudit,
)
from aurex.backtest_engine.s2_onchain_settlement_charter import (  # noqa: E402
    S2OnchainSettlementCharter,
    S2OnchainSettlementCharterAudit,
    audit_s2_charter,
    audit_s2_charter_audit,
)
from aurex.backtest_engine.s3_cftc_positioning_charter import (  # noqa: E402
    S3CftcPositioningCharter,
    S3OperatorScope,
    S3Partition,
    S3ResearchSource,
    S3SourceBinding,
)
from aurex.backtest_engine.strategy_factory_contract import (  # noqa: E402
    StrategyFactoryContract,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s3_cftc_positioning_charter_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s3_cftc_positioning_charter.py")
SCRIPT_PATH = Path("scripts/freeze_s3_cftc_positioning_charter.py")
FACTORY_PATH = Path("data/evidence/aurex_strategy_factory_contract_v1.json")
PROFILE_PATH = Path("data/evidence/binance_spot_testnet_sandbox_profile_v1.json")
LINEAGE_PATH = Path("data/evidence/s1_successor_lineage_ledger_v1.json")
LINEAGE_AUDIT_PATH = Path("data/evidence/s1_successor_lineage_audit_v1.json")
S2_CHARTER_PATH = Path("data/evidence/s2_onchain_settlement_charter_v1.json")
S2_CHARTER_AUDIT_PATH = Path(
    "data/evidence/s2_onchain_settlement_charter_audit_v1.json"
)
S2_SOURCE_RESULT_PATH = Path(
    "data/evidence/s2_btc_source_acquisition_result_v1.json"
)
S2_SOURCE_AUDIT_PATH = Path(
    "data/evidence/s2_btc_source_acquisition_audit_v1.json"
)
S2_BACKTEST_RESULT_PATH = Path(
    "data/evidence/s2_development_backtest_result_v1.json"
)
S2_BACKTEST_AUDIT_PATH = Path(
    "data/evidence/s2_development_backtest_result_audit_v1.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v23.json"
)
READINESS_AUDIT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v23.json"
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
    StrategyFactoryContract.model_validate_json(
        FACTORY_PATH.read_text(encoding="utf-8")
    )
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    operator = profile.get("operator_input") or {}
    lineage = S1SuccessorLineageLedger.model_validate_json(
        LINEAGE_PATH.read_text(encoding="utf-8")
    )
    lineage_audit = S1SuccessorLineageAudit.model_validate_json(
        LINEAGE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    s2_charter = S2OnchainSettlementCharter.model_validate_json(
        S2_CHARTER_PATH.read_text(encoding="utf-8")
    )
    s2_charter_audit = S2OnchainSettlementCharterAudit.model_validate_json(
        S2_CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    source_result = S2BtcSourceAcquisitionResult.model_validate_json(
        S2_SOURCE_RESULT_PATH.read_text(encoding="utf-8")
    )
    source_audit = S2BtcSourceAcquisitionAudit.model_validate_json(
        S2_SOURCE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    backtest_result = S2DevelopmentBacktestResult.model_validate_json(
        S2_BACKTEST_RESULT_PATH.read_text(encoding="utf-8")
    )
    backtest_audit = S2DevelopmentBacktestResultAudit.model_validate_json(
        S2_BACKTEST_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    input_boundary_changed = (
        not audit_s1_lineage(lineage)
        or not audit_s1_lineage_audit(lineage_audit)
        or lineage_audit.ledger_evidence_hash != lineage.ledger_evidence_hash
        or not audit_s2_charter(s2_charter)
        or not audit_s2_charter_audit(s2_charter_audit)
        or s2_charter_audit.charter_evidence_hash
        != s2_charter.charter_evidence_hash
        or source_result.decision
        != "PASS_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION"
        or source_audit.decision != "PASS_S2_BTC_SOURCE_ACQUISITION_AUDIT"
        or source_audit.result_evidence_hash != source_result.result_evidence_hash
        or backtest_result.decision
        != "STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        or backtest_result.next_authorization
        != "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        or backtest_result.failed_gate_count != 6
        or backtest_audit.decision
        != "CONFIRM_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        or backtest_audit.result_evidence_hash
        != backtest_result.result_evidence_hash
        or backtest_audit.lineage_next_authorization
        != "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.passed_gate_count != 14
        or readiness.partial_gate_count != 1
        or readiness.failed_gate_count != 0
        or readiness.decision
        != "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY"
        or readiness.next_action != "DESIGN_ONE_NEW_UNRELATED_MECHANISM_CHARTER_ONLY"
        or operator.get("permitted_product_scope") != "SPOT_ONLY"
        or operator.get("permitted_symbols") != ["BTCUSDT"]
        or operator.get("maximum_effective_leverage") != "1"
        or operator.get("one_time_data_budget") != "0"
        or operator.get("monthly_data_budget") != "0"
        or operator.get("real_capital_authorized") is not False
        or operator.get("live_trading_authorized") is not False
    )
    if input_boundary_changed:
        raise ValueError("S3 charter input lineage or operator boundary changed")


def bindings() -> tuple[S3SourceBinding, ...]:
    paths = (
        FACTORY_PATH,
        PROFILE_PATH,
        LINEAGE_PATH,
        LINEAGE_AUDIT_PATH,
        S2_CHARTER_PATH,
        S2_CHARTER_AUDIT_PATH,
        S2_SOURCE_RESULT_PATH,
        S2_SOURCE_AUDIT_PATH,
        S2_BACKTEST_RESULT_PATH,
        S2_BACKTEST_AUDIT_PATH,
        READINESS_RESULT_PATH,
        READINESS_AUDIT_PATH,
    )
    return tuple(
        S3SourceBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def research_sources(*, accessed_at: datetime) -> tuple[S3ResearchSource, ...]:
    return (
        S3ResearchSource(
            source_id="BAUR-SMALES-2022",
            title='Trading behavior in Bitcoin futures: Following the "smart money"',
            authors_or_publisher=("Dirk G. Baur", "Lee A. Smales"),
            publication_or_revision_date="2022-07-01",
            accessed_at=accessed_at,
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1002/fut.22332",
            supported_claims=(
                "The published study tests changes in CFTC trader-category net positions "
                "as Bitcoin timing information over 2018 through July 2021.",
                "Its reported leveraged-money directional rule creates direct outcome "
                "awareness for the overlapping mechanism family.",
            ),
            limitations=(
                "The published sample, rule, and favorable outcome contaminate that period "
                "and cannot qualify Aurex S3.",
                "Published futures-market results do not establish a reproducible, "
                "after-cost Binance Spot edge in a later regime.",
            ),
        ),
        S3ResearchSource(
            source_id="CFTC-ABOUT-COT",
            title="Commitments of Traders: About the COT Reports",
            authors_or_publisher=("United States CFTC",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url=(
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "AbouttheCOTReports/index.htm"
            ),
            supported_claims=(
                "COT reports provide Tuesday open-interest breakdowns and are generally "
                "released on Friday at 15:30 Eastern Time.",
                "The TFF report separates dealer, asset manager, leveraged funds, and "
                "other reportable categories.",
            ),
            limitations=(
                "Generally scheduled Friday publication is not proof of the actual release "
                "timestamp for any historical report.",
                "CFTC categories aggregate reporting firms and do not reveal trader intent.",
            ),
        ),
        S3ResearchSource(
            source_id="CFTC-COT-RELEASE-SCHEDULE",
            title="Commitments of Traders: Release Schedule",
            authors_or_publisher=("United States CFTC",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url=(
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "ReleaseSchedule/index.htm"
            ),
            supported_claims=(
                "The official schedule identifies holiday-related release delays.",
            ),
            limitations=(
                "A planned schedule does not prove that a particular report was actually "
                "available at the planned time or was never corrected later.",
            ),
        ),
        S3ResearchSource(
            source_id="CFTC-HISTORICAL-COMPRESSED",
            title="Commitments of Traders: Historical Compressed",
            authors_or_publisher=("United States CFTC",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url=(
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "HistoricalCompressed/index.htm"
            ),
            supported_claims=(
                "CFTC publishes annual compressed futures-only TFF history for research.",
            ),
            limitations=(
                "Annual files expose report dates but are not, by themselves, a historical "
                "publication-timestamp or revision ledger.",
            ),
        ),
        S3ResearchSource(
            source_id="CFTC-HISTORICAL-SPECIAL-ANNOUNCEMENTS",
            title="Commitments of Traders: Historical Special Announcements",
            authors_or_publisher=("United States CFTC",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url=(
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "HistoricalSpecialAnnouncements/index.htm"
            ),
            supported_claims=(
                "Exceptional reporting delays and publication interruptions have occurred.",
            ),
            limitations=(
                "Announcement coverage must be reconciled to each affected report; absent "
                "an announcement is not proof of normal publication.",
            ),
        ),
        S3ResearchSource(
            source_id="CFTC-TFF-FIELD-DESCRIPTIONS",
            title="Traders in Financial Futures: Explanatory Notes and Field Descriptions",
            authors_or_publisher=("United States CFTC",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url=(
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "HistoricalViewable/cotvariablestfm.html"
            ),
            supported_claims=(
                "The TFF schema includes leveraged-money long and short positions and "
                "contract-market identity fields.",
            ),
            limitations=(
                "A schema description does not prove historical row completeness, "
                "classification stability, or point-in-time availability.",
            ),
        ),
        S3ResearchSource(
            source_id="FERKO-MOIN-ONUR-PENICK-2023",
            title="Who trades bitcoin futures and why?",
            authors_or_publisher=(
                "Alex Ferko",
                "Amani Moin",
                "Esen Onur",
                "Michael Penick",
            ),
            publication_or_revision_date="2023-02-01",
            accessed_at=accessed_at,
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1016/j.gfj.2022.100778",
            supported_claims=(
                "Regulatory position data reveal heterogeneous CME Bitcoin futures trader "
                "types and motives.",
            ),
            limitations=(
                "Heterogeneous motives weaken any claim that aggregate leveraged-money "
                "position changes identify one stable causal trading signal.",
            ),
        ),
        S3ResearchSource(
            source_id="SHI-2022",
            title="Bitcoin futures risk premia",
            authors_or_publisher=("Shimeng Shi",),
            publication_or_revision_date="2022-12-01",
            accessed_at=accessed_at,
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1002/fut.22373",
            supported_claims=(
                "The paper studies position-based predictors and risk premia in Bitcoin "
                "futures.",
            ),
            limitations=(
                "A futures risk-premium relation is not proof of a causal, after-cost, "
                "long-or-cash Bitcoin Spot strategy.",
            ),
        ),
    )


def partitions() -> tuple[S3Partition, ...]:
    return (
        S3Partition(
            role="PUBLISHED_STUDY_CONTAMINATED_REFERENCE",
            start="2017-12-18T00:00:00Z",
            end="2022-01-01T00:00:00Z",
            state="PUBLISHED_OUTCOME_CONTAMINATED_NONQUALIFYING",
        ),
        S3Partition(
            role="DEVELOPMENT",
            start="2022-01-01T00:00:00Z",
            end="2025-01-01T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S3Partition(
            role="OUTCOME_AWARE_HISTORICAL_SCREEN",
            start="2025-01-01T00:00:00Z",
            end="2026-11-07T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S3Partition(
            role="PROSPECTIVE_VALIDATION",
            start="2026-11-07T00:00:00Z",
            end="2027-05-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S3Partition(
            role="FUTURE_HOLDOUT",
            start="2027-05-07T00:00:00Z",
            end="2027-11-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S3Partition(
            role="FORWARD",
            start="2027-11-07T00:00:00Z",
            end=None,
            state="LOCKED_FUTURE",
        ),
    )


def build_charter(*, frozen_at: datetime) -> S3CftcPositioningCharter:
    load_and_validate_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "predecessor_bindings": bindings(),
        "research_sources": research_sources(accessed_at=frozen_at),
        "operator_scope": S3OperatorScope(),
        "ex_ante_hypothesis": (
            "A week-over-week increase in the net reported long exposure of leveraged "
            "money in regulated CME Bitcoin futures may represent persistent institutional "
            "risk demand that transfers to Bitcoin Spot after the public CFTC release. "
            "Aurex may later evaluate one weekly BTCUSDT Spot long-or-cash candidate, but "
            "only after actual publication timing and point-in-time source identity are "
            "proven; a non-increase, missing report, delay, correction, or ambiguity means "
            "cash, never short exposure."
        ),
        "causal_observation_policy": (
            "USE_ONLY_FUTURES_ONLY_TFF_ROWS_FOR_CFTC_CONTRACT_MARKET_CODE_133741",
            "REPORT_AS_OF_DATE_IS_NOT_A_RELEASE_TIMESTAMP",
            "ACTUAL_RELEASE_TIMESTAMP_REQUIRED_FOR_EACH_REPORT_BEFORE_SIGNAL_USE",
            "EARLIEST_EXECUTION_IS_FIRST_MONDAY_00_00_UTC_AT_LEAST_24_HOURS_AFTER_RELEASE",
            "DELAYED_OR_BACKLOGGED_REPORTS_ARE_NEVER_BACKFILLED_INTO_EARLIER_DECISIONS",
            "ANNUAL_COMPRESSED_ROWS_MUST_RECONCILE_TO_ORIGINAL_WEEKLY_PUBLICATIONS",
            "MISSING_DUPLICATE_REVISED_OR_AMBIGUOUS_REPORT_IDENTITY_FORCES_CASH",
            "HASH_ALL_METADATA_RELEASE_RECORDS_RESPONSES_AND_FUTURE_SOURCE_PAYLOADS",
        ),
        "exact_source_requirements": (
            "OFFICIAL_CFTC_TFF_FUTURES_ONLY_CONTRACT_MARKET_CODE_133741",
            "OFFICIAL_CFTC_REPORT_AS_OF_DATE_AND_CONTRACT_MARKET_NAME_FIELDS",
            "OFFICIAL_CFTC_LEVERAGED_MONEY_LONG_AND_SHORT_POSITION_FIELDS",
            "ACTUAL_HISTORICAL_PUBLICATION_TIMESTAMP_OR_VERIFIABLE_EQUIVALENT",
            "HOLIDAY_DELAY_SHUTDOWN_BACKLOG_AND_SPECIAL_ANNOUNCEMENT_RECONCILIATION",
            "ORIGINAL_WEEKLY_TO_ANNUAL_COMPRESSED_ROW_IDENTITY_RECONCILIATION",
            "CORRECTION_REVISION_AND_CLASSIFICATION_CHANGE_DETECTION",
            "IMMUTABLE_REQUEST_RESPONSE_RELEASE_METADATA_AND_FILE_HASHES",
            "OFFICIAL_BINANCE_SPOT_BTCUSDT_EXECUTION_PRICES_WITH_PUBLISHED_CHECKSUMS",
            "ZERO_DOLLAR_SOURCE_ACCESS_WITH_DOCUMENTED_REUSE_RIGHTS",
        ),
        "independence_exclusions": (
            "NO_PRICE_MOMENTUM_TREND_PULLBACK_BREAKOUT_OR_MEAN_REVERSION_SIGNAL_INPUT",
            "NO_VOLATILITY_SCALING_PATH_QUALITY_OR_CROSS_SECTIONAL_RANKING_INPUT",
            "NO_AGGRESSOR_FLOW_ORDER_BOOK_CLOCK_PHASE_OR_JAM_EXHAUSTION_INPUT",
            "NO_FUNDING_BASIS_CARRY_PERPETUAL_FLOW_OR_CROSS_VENUE_INPUT",
            "NO_NFCI_MONETARY_FINANCIAL_CONDITIONS_OR_OTHER_MACRO_INPUT",
            "NO_ONCHAIN_SETTLEMENT_TRANSACTION_FEE_OR_NETWORK_DEMAND_INPUT",
            "NO_VARIANCE_RISK_PREMIUM_OPTION_OR_DERIVATIVES_PRICING_INPUT",
            "NO_REUSE_OF_S2_THRESHOLDS_DIAGNOSTICS_FAILURES_OR_OUTCOMES",
            "NO_CFTC_DEALER_ASSET_MANAGER_OTHER_REPORTABLE_OR_NONREPORTABLE_SIGNAL",
            "NO_OPEN_INTEREST_VOLUME_BASIS_CURVE_OR_FUTURES_RETURN_SIGNAL_INPUT",
            "NO_FUTURES_TRADING_SHORTING_BORROWING_OR_LEVERAGE",
            "NO_PARAMETER_SEARCH_ENSEMBLE_OR_POST_HOC_SIGNAL_REVERSAL",
        ),
        "feasibility_gates": (
            "ALL_TEN_PREDECESSOR_FAMILIES_BOUND_AND_NONREUSABLE",
            "OFFICIAL_CFTC_TFF_FUTURES_ONLY_ARCHIVES_EXIST_FOR_REQUIRED_PERIOD",
            "CFTC_CODE_133741_MAPS_UNAMBIGUOUSLY_TO_CME_BITCOIN_ACROSS_REQUIRED_PERIOD",
            "LEVERAGED_MONEY_LONG_AND_SHORT_FIELDS_ARE_SCHEMA_STABLE_OR_MAPPED_EX_ANTE",
            "ACTUAL_RELEASE_TIMESTAMPS_ARE_RECONSTRUCTABLE_FOR_EVERY_REQUIRED_REPORT",
            "HOLIDAY_DELAY_SHUTDOWN_AND_BACKLOG_RELEASES_ARE_RECONSTRUCTABLE_CAUSALLY",
            "ORIGINAL_WEEKLY_PUBLICATIONS_RECONCILE_EXACTLY_TO_ANNUAL_COMPRESSED_ROWS",
            "CORRECTIONS_REVISIONS_AND_CLASSIFICATION_CHANGES_ARE_DETECTABLE",
            "ZERO_DOLLAR_ACCESS_AND_REUSE_RIGHTS_ARE_DOCUMENTED",
            "MONDAY_00_00_UTC_AFTER_24_HOUR_CAUSAL_BUFFER_IS_IMPLEMENTABLE",
            "ONE_SELECTABLE_MECHANISM_AND_ZERO_CHARTER_STAGE_PARAMETERS",
            "FAILURE_OF_ANY_GATE_SELECTS_ZERO_AND_STOPS_S3_BEFORE_POSITION_VALUES",
        ),
        "partitions": partitions(),
        "source_metadata_pages_inspected": (
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
            "AbouttheCOTReports/index.htm",
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
            "HistoricalCompressed/index.htm",
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
            "HistoricalSpecialAnnouncements/index.htm",
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
            "HistoricalViewable/cotvariablestfm.html",
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
            "ReleaseSchedule/index.htm",
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
        ),
        "limitations": (
            "This charter selects a source-feasibility hypothesis, not a profitable strategy.",
            "The exact leveraged-money directional rule and its published 2018 through "
            "July 2021 outcome are known, so that rule and period cannot qualify S3.",
            "COT categories aggregate reporting firms and do not reveal trader intent; "
            "heterogeneous motives can destabilize the aggregate relation.",
            "CME-regulated futures represent only part of global Bitcoin activity.",
            "Position changes may follow prior Bitcoin returns rather than cause future "
            "Spot returns.",
            "Annual compressed files are not point-in-time archives and may contain later "
            "corrections or classifications.",
            "Actual release timing, holiday delays, outages, revisions, and contract-code "
            "continuity are not yet qualified.",
            "Published futures-market findings do not prove after-cost Binance Spot returns "
            "in the later development period.",
            "All historical target periods currently available are outcome-aware and cannot "
            "serve as untouched qualification evidence.",
            "Prospective validation and holdout together require twelve future months before "
            "live eligibility can be considered.",
            "No CFTC position value, BTC market value, parameter, return, candidate, signal, "
            "paper order, Testnet strategy order, production action, live action, real "
            "capital, or profit is authorized.",
        ),
    }
    provisional = S3CftcPositioningCharter.model_construct(
        **payload, charter_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["charter_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"charter_evidence_hash"})
    )
    return S3CftcPositioningCharter.model_validate(complete)


def write_atomic(path: Path, charter: S3CftcPositioningCharter) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 charter transaction exists: {temporary}")
    serialized = charter.model_dump_json(indent=2) + "\n"
    if S3CftcPositioningCharter.model_validate_json(serialized) != charter:
        raise ValueError("S3 charter did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S3 charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.check:
        stored = S3CftcPositioningCharter.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_charter(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S3 charter differs from reconstruction")
        print(f"PASS {stored.charter_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S3 charter: {args.output}")
    charter = build_charter(frozen_at=datetime.now(UTC))
    write_atomic(args.output, charter)
    print(
        f"FROZEN {args.output} {charter.charter_evidence_hash} "
        "cftc_values=0 market_values=0 parameters=0 returns=0 candidates=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
