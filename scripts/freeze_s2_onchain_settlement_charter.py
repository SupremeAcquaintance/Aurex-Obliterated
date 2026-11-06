from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_development_outcome_audit import (  # noqa: E402
    S11DevelopmentOutcomeAudit,
)
from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S11DevelopmentOutcomeResult,
)
from aurex.backtest_engine.s1_post_failure_analysis import (  # noqa: E402
    S1PostFailureAnalysisAudit,
    S1PostFailureAnalysisResult,
)
from aurex.backtest_engine.s1_successor_charter import (  # noqa: E402
    S1SuccessorLineageAudit,
    S1SuccessorLineageLedger,
    audit_s1_lineage,
    audit_s1_lineage_audit,
)
from aurex.backtest_engine.s2_onchain_settlement_charter import (  # noqa: E402
    S2OnchainSettlementCharter,
    S2OperatorScope,
    S2Partition,
    S2ResearchSource,
    S2SourceBinding,
)
from aurex.backtest_engine.strategy_factory_contract import (  # noqa: E402
    StrategyFactoryContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_onchain_settlement_charter_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_onchain_settlement_charter.py")
SCRIPT_PATH = Path("scripts/freeze_s2_onchain_settlement_charter.py")
LINEAGE_PATH = Path("data/evidence/s1_successor_lineage_ledger_v1.json")
LINEAGE_AUDIT_PATH = Path("data/evidence/s1_successor_lineage_audit_v1.json")
S1_RESULT_PATH = Path("data/evidence/s1_1_development_outcome_result_v1.json")
S1_AUDIT_PATH = Path("data/evidence/s1_1_development_outcome_audit_v1.json")
POST_RESULT_PATH = Path("data/evidence/s1_post_failure_analysis_result_v1.json")
POST_AUDIT_PATH = Path("data/evidence/s1_post_failure_analysis_audit_v1.json")
FACTORY_PATH = Path("data/evidence/aurex_strategy_factory_contract_v1.json")
PROFILE_PATH = Path("data/evidence/binance_spot_testnet_sandbox_profile_v1.json")


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
    lineage_audit = S1SuccessorLineageAudit.model_validate_json(
        LINEAGE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    s1_result = S11DevelopmentOutcomeResult.model_validate_json(
        S1_RESULT_PATH.read_text(encoding="utf-8")
    )
    s1_audit = S11DevelopmentOutcomeAudit.model_validate_json(
        S1_AUDIT_PATH.read_text(encoding="utf-8")
    )
    post_result = S1PostFailureAnalysisResult.model_validate_json(
        POST_RESULT_PATH.read_text(encoding="utf-8")
    )
    post_audit = S1PostFailureAnalysisAudit.model_validate_json(
        POST_AUDIT_PATH.read_text(encoding="utf-8")
    )
    StrategyFactoryContract.model_validate_json(FACTORY_PATH.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    operator = profile.get("operator_input") or {}
    if (
        not audit_s1_lineage(lineage)
        or not audit_s1_lineage_audit(lineage_audit)
        or lineage_audit.ledger_evidence_hash != lineage.ledger_evidence_hash
        or s1_result.decision != "STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED"
        or s1_audit.result_evidence_hash != s1_result.result_evidence_hash
        or post_result.decision != "RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE"
        or post_audit.result_evidence_hash != post_result.result_evidence_hash
        or post_result.next_authorization
        != "AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY"
        or operator.get("permitted_product_scope") != "SPOT_ONLY"
        or operator.get("permitted_symbols") != ["BTCUSDT"]
        or operator.get("maximum_effective_leverage") != "1"
        or operator.get("one_time_data_budget") != "0"
        or operator.get("monthly_data_budget") != "0"
        or operator.get("real_capital_authorized") is not False
        or operator.get("live_trading_authorized") is not False
    ):
        raise ValueError("S2 charter input lineage or operator boundary changed")


def bindings() -> tuple[S2SourceBinding, ...]:
    paths = (
        FACTORY_PATH,
        PROFILE_PATH,
        S1_AUDIT_PATH,
        S1_RESULT_PATH,
        POST_AUDIT_PATH,
        POST_RESULT_PATH,
        LINEAGE_AUDIT_PATH,
        LINEAGE_PATH,
    )
    return tuple(
        S2SourceBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def research_sources(*, accessed_at: datetime) -> tuple[S2ResearchSource, ...]:
    return (
        S2ResearchSource(
            source_id="BLOCKCHAIN-ETL-BITCOIN-SCHEMA",
            title="Bitcoin ETL",
            authors_or_publisher=("Blockchain ETL",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_SOURCE_CODE",
            url="https://github.com/blockchain-etl/bitcoin-etl",
            supported_claims=(
                "The open-source ETL publishes block and transaction schemas used by "
                "the public dataset.",
                "The repository is MIT licensed and documents Bitcoin BigQuery availability.",
            ),
            limitations=(
                "Parser availability does not establish dataset completeness, query "
                "affordability, or predictive value.",
            ),
        ),
        S2ResearchSource(
            source_id="BLOCKCHAIN-ETL-PUBLIC-DATASETS",
            title="Public Blockchain Datasets",
            authors_or_publisher=("Blockchain ETL",),
            publication_or_revision_date="2024-06-26",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_SOURCE_CODE",
            url="https://github.com/blockchain-etl/public-datasets",
            supported_claims=(
                "Bitcoin is listed as a BigQuery public blockchain dataset with a "
                "documented update lag.",
            ),
            limitations=(
                "The listed lag and availability can change and require fresh metadata "
                "verification.",
            ),
        ),
        S2ResearchSource(
            source_id="COIN-METRICS-COMMUNITY-LICENSE",
            title="Coin Metrics API Conventions",
            authors_or_publisher=("Coin Metrics",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url="https://gitbook-docs.coinmetrics.io/access-our-data/api",
            supported_claims=(
                "Community API access requires no key and is rate limited.",
                "Community data is offered for non-commercial use.",
            ),
            limitations=(
                "A non-commercial license is incompatible with treating the free feed "
                "as an authorized live-trading input without separate permission.",
            ),
        ),
        S2ResearchSource(
            source_id="GOOGLE-BIGQUERY-PUBLIC-DATA",
            title="BigQuery public datasets",
            authors_or_publisher=("Google Cloud",),
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url="https://docs.cloud.google.com/bigquery/public-data",
            supported_claims=(
                "Google hosts public datasets while users pay query-processing costs.",
                "The first one terabyte of query processing per month is free subject "
                "to pricing terms.",
            ),
            limitations=(
                "Access requires a Google Cloud project and cost controls; the free tier "
                "is not an unlimited guarantee.",
            ),
        ),
        S2ResearchSource(
            source_id="GOOGLE-BITCOIN-BIGQUERY",
            title="Bitcoin in BigQuery: blockchain analytics on public data",
            authors_or_publisher=("Google Cloud",),
            publication_or_revision_date="2018-02-08",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_DATA_DOCUMENTATION",
            url="https://cloud.google.com/blog/topics/public-datasets/bitcoin-in-bigquery-blockchain-analytics-on-public-data",
            supported_claims=(
                "The public Bitcoin dataset exposes historical blockchain records for "
                "SQL analysis.",
            ),
            limitations=(
                "An announcement and example queries do not prove current completeness "
                "or economical query plans.",
            ),
        ),
        S2ResearchSource(
            source_id="KAPAR-OLMO-2018",
            title="Bitcoin returns and transaction activity",
            authors_or_publisher=("Burcu Kapar", "Jose Olmo"),
            publication_or_revision_date="2018-06-01",
            accessed_at=accessed_at,
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1016/j.econlet.2018.03.021",
            supported_claims=(
                "The paper examines bidirectional links between Bitcoin returns and "
                "transaction activity.",
            ),
            limitations=(
                "Return shocks contributed more to transaction activity than the reverse, "
                "and the paper does not establish a deployable after-cost rule.",
            ),
        ),
    )


def partitions() -> tuple[S2Partition, ...]:
    return (
        S2Partition(
            role="DEVELOPMENT",
            start="2017-08-17T00:00:00Z",
            end="2023-01-01T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S2Partition(
            role="OUTCOME_AWARE_HISTORICAL_SCREEN",
            start="2023-01-01T00:00:00Z",
            end="2026-11-07T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S2Partition(
            role="PROSPECTIVE_VALIDATION",
            start="2026-11-07T00:00:00Z",
            end="2027-05-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S2Partition(
            role="FUTURE_HOLDOUT",
            start="2027-05-07T00:00:00Z",
            end="2027-11-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S2Partition(
            role="FORWARD",
            start="2027-11-07T00:00:00Z",
            end=None,
            state="LOCKED_FUTURE",
        ),
    )


def build_charter(*, frozen_at: datetime) -> S2OnchainSettlementCharter:
    load_and_validate_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "predecessor_bindings": bindings(),
        "research_sources": research_sources(accessed_at=frozen_at),
        "operator_scope": S2OperatorScope(),
        "ex_ante_hypothesis": (
            "A persistent, jointly broadening level of confirmed non-coinbase Bitcoin "
            "settlement activity and user-paid transaction fees may represent network "
            "demand that is economically distinct from exchange price, candle, funding, "
            "volatility, and order-flow signals. Aurex will eventually test one weekly "
            "BTCUSDT Spot long-or-cash formulation; disagreement or weak demand means "
            "cash, never short exposure."
        ),
        "causal_observation_policy": (
            "USE_ONLY_BLOCKS_WITH_AT_LEAST_SIX_CONFIRMATIONS_AT_THE_DECISION_CUTOFF",
            "WEEKLY_DECISION_MAY_USE_ONLY_COMPLETE_UTC_DAYS_THROUGH_PRIOR_FRIDAY",
            "EARLIEST_EXECUTION_IS_THE_FOLLOWING_MONDAY_00_00_UTC_BINANCE_OPEN",
            "MISSING_REORGED_INCOMPLETE_OR_AMBIGUOUS_CHAIN_DATA_FORCES_CASH",
            "RAW_BLOCK_AND_TRANSACTION_FIELDS_ARE_HASH_BOUND_BEFORE_TRANSFORMATION",
        ),
        "exact_source_requirements": (
            "GOOGLE_BIGQUERY_PUBLIC_CRYPTO_BITCOIN_BLOCKS_AND_TRANSACTIONS_METADATA",
            "BLOCKCHAIN_ETL_SCHEMA_AND_MIT_LICENSE_BINDING",
            "PARTITION_FILTERED_GOOGLESQL_WITH_DRY_RUN_TOTAL_BYTES_PROCESSED",
            "MAXIMUM_BYTES_BILLED_AND_ZERO_DOLLAR_BUDGET_PREFLIGHT",
            "NON_COINBASE_TRANSACTION_CLASSIFICATION_AND_FEE_UNITS_RECONSTRUCTABLE",
            "OFFICIAL_BINANCE_SPOT_BTCUSDT_EXECUTION_PRICES_WITH_PUBLISHED_CHECKSUMS",
            "IMMUTABLE_QUERY_TEXT_JOB_METADATA_RESPONSE_AND_OUTPUT_HASHES",
        ),
        "independence_exclusions": (
            "NO_PRICE_MOMENTUM_TREND_PULLBACK_BREAKOUT_OR_MEAN_REVERSION_SIGNAL_INPUT",
            "NO_VOLATILITY_SCALING_PATH_QUALITY_OR_CROSS_SECTIONAL_RANKING_INPUT",
            "NO_AGGRESSOR_FLOW_ORDER_BOOK_CLOCK_PHASE_OR_JAM_EXHAUSTION_INPUT",
            "NO_FUNDING_BASIS_CARRY_PERPETUAL_FLOW_OR_CROSS_VENUE_INPUT",
            "NO_NFCI_MONETARY_FINANCIAL_CONDITIONS_OR_OTHER_MACRO_INPUT",
            "NO_HASHRATE_AS_PRIMARY_PREDICTIVE_INPUT",
            "NO_ACTIVE_ADDRESS_COUNT_AS_A_USER_COUNT_PROXY",
            "NO_COIN_METRICS_COMMUNITY_VALUES_AS_TRADING_INPUT",
            "NO_REUSE_OF_RETIRED_THRESHOLDS_DIAGNOSTICS_OR_OUTCOMES",
        ),
        "feasibility_gates": (
            "ALL_NINE_PREDECESSOR_FAMILIES_BOUND_AND_NONREUSABLE",
            "BIGQUERY_PUBLIC_DATASET_AND_REQUIRED_TABLES_CURRENTLY_EXIST",
            "REQUIRED_SCHEMA_FIELDS_AND_PARTITION_COLUMNS_RECONSTRUCT_EXACTLY",
            "DRY_RUN_BYTES_FOR_EACH_BOUNDED_QUERY_FIT_ZERO_DOLLAR_BUDGET_CONTROLS",
            "GOOGLE_CLOUD_PROJECT_AUTHENTICATION_AND_BILLING_GUARDRAILS_AVAILABLE",
            "COMPLETE_CHAIN_COVERAGE_FROM_2017_08_17_WITH_DOCUMENTED_UPDATE_LAG",
            "SIX_CONFIRMATION_AND_PRIOR_FRIDAY_CAUSAL_CUTOFF_IS_IMPLEMENTABLE",
            "RAW_FEE_AND_TRANSACTION_AGGREGATION_EXCLUDES_COINBASE_EXACTLY",
            "BINANCE_EXECUTION_SOURCE_REMAINS_CHECKSUM_BOUND_AND_SPOT_ONLY",
            "ONE_SELECTABLE_MECHANISM_AND_ZERO_CHARTER_STAGE_PARAMETERS",
            "FAILURE_OF_ANY_GATE_SELECTS_ZERO_AND_STOPS_S2_BEFORE_NUMERIC_QUERY",
        ),
        "partitions": partitions(),
        "limitations": (
            "This charter selects a source-feasibility hypothesis, not a profitable strategy.",
            "All historical BTC target periods are outcome-aware and cannot serve as "
            "untouched qualification evidence.",
            "Prospective validation and holdout together require twelve future months "
            "before live eligibility can be considered.",
            "Transaction activity can be caused by price, batching, congestion, or "
            "non-investment usage; published evidence is bidirectional and weak for "
            "trading claims.",
            "BigQuery authentication, schema, current coverage, dry-run bytes, and "
            "zero-dollar cost controls are not yet qualified.",
            "Coin Metrics community values are excluded because free access is documented "
            "for non-commercial use.",
            "No blockchain value, market value, parameter, return, candidate, signal, "
            "paper order, Testnet strategy order, production action, live action, real "
            "capital, or profit is authorized.",
        ),
    }
    provisional = S2OnchainSettlementCharter.model_construct(
        **payload, charter_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["charter_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"charter_evidence_hash"})
    )
    return S2OnchainSettlementCharter.model_validate(complete)


def write_atomic(path: Path, charter: S2OnchainSettlementCharter) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 charter transaction exists: {temporary}")
    serialized = charter.model_dump_json(indent=2) + "\n"
    if S2OnchainSettlementCharter.model_validate_json(serialized) != charter:
        raise ValueError("S2 charter did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S2 charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.check:
        stored = S2OnchainSettlementCharter.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_charter(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S2 charter differs from reconstruction")
        print(f"PASS {stored.charter_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite frozen S2 charter: {args.output}")
    charter = build_charter(frozen_at=datetime.now(UTC))
    write_atomic(args.output, charter)
    print(
        f"FROZEN {args.output} {charter.charter_evidence_hash} "
        "blockchain_values=0 market_values=0 parameters=0 returns=0 candidates=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
