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
    S3CftcPositioningCharterAudit,
    audit_s3_charter,
    audit_s3_charter_audit,
)
from aurex.backtest_engine.s3_cftc_source_feasibility import (  # noqa: E402
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    audit_s3_feasibility_protocol,
    audit_s3_feasibility_protocol_audit,
    audit_s3_feasibility_result,
)
from aurex.backtest_engine.s3_cftc_source_feasibility_transport import (  # noqa: E402
    S3CftcMetadataTransportAmendmentAuditV2,
    S3CftcMetadataTransportAmendmentV2,
    S3CftcSourceTransportFailureAudit,
    audit_transport_amendment,
    audit_transport_amendment_audit,
    audit_transport_failure,
)
from aurex.backtest_engine.s3_cftc_source_transport_outcome import (  # noqa: E402
    S3_TRANSPORT_V2_RETIREMENT,
    S3CftcMetadataTransportExecutionReceiptAuditV2,
    S3CftcMetadataTransportExecutionReceiptV2,
    audit_transport_execution_receipt,
    audit_transport_execution_receipt_audit,
)
from aurex.backtest_engine.s4_spot_bitcoin_etp_charter import (  # noqa: E402
    S4OperatorScope,
    S4Partition,
    S4ResearchSource,
    S4SourceBinding,
    S4SpotBitcoinEtpCharter,
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

DEFAULT_OUTPUT = Path("data/evidence/s4_spot_bitcoin_etp_charter_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s4_spot_bitcoin_etp_charter.py")
SCRIPT_PATH = Path("scripts/freeze_s4_spot_bitcoin_etp_charter.py")
FACTORY_PATH = Path("data/evidence/aurex_strategy_factory_contract_v1.json")
PROFILE_PATH = Path("data/evidence/binance_spot_testnet_sandbox_profile_v1.json")
LINEAGE_PATH = Path("data/evidence/s1_successor_lineage_ledger_v1.json")
LINEAGE_AUDIT_PATH = Path("data/evidence/s1_successor_lineage_audit_v1.json")
S2_CHARTER_PATH = Path("data/evidence/s2_onchain_settlement_charter_v1.json")
S2_CHARTER_AUDIT_PATH = Path(
    "data/evidence/s2_onchain_settlement_charter_audit_v1.json"
)
S2_BACKTEST_RESULT_PATH = Path(
    "data/evidence/s2_development_backtest_result_v1.json"
)
S2_BACKTEST_AUDIT_PATH = Path(
    "data/evidence/s2_development_backtest_result_audit_v1.json"
)
S3_CHARTER_PATH = Path("data/evidence/s3_cftc_positioning_charter_v1.json")
S3_CHARTER_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_positioning_charter_audit_v1.json"
)
S3_PROTOCOL_PATH = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_v1.json"
)
S3_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
S3_RESULT_PATH = Path("data/evidence/s3_cftc_source_feasibility_result_v1.json")
S3_FAILURE_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_transport_failure_audit_v1.json"
)
S3_AMENDMENT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_amendment_v2.json"
)
S3_AMENDMENT_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_amendment_audit_v2.json"
)
S3_RECEIPT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_execution_receipt_v2.json"
)
S3_RECEIPT_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_execution_receipt_audit_v2.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v25.json"
)
READINESS_AUDIT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v25.json"
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


def predecessor_paths() -> tuple[Path, ...]:
    return (
        FACTORY_PATH,
        PROFILE_PATH,
        LINEAGE_PATH,
        LINEAGE_AUDIT_PATH,
        S2_CHARTER_PATH,
        S2_CHARTER_AUDIT_PATH,
        S2_BACKTEST_RESULT_PATH,
        S2_BACKTEST_AUDIT_PATH,
        S3_CHARTER_PATH,
        S3_CHARTER_AUDIT_PATH,
        S3_PROTOCOL_PATH,
        S3_PROTOCOL_AUDIT_PATH,
        S3_RESULT_PATH,
        S3_FAILURE_AUDIT_PATH,
        S3_AMENDMENT_PATH,
        S3_AMENDMENT_AUDIT_PATH,
        S3_RECEIPT_PATH,
        S3_RECEIPT_AUDIT_PATH,
        READINESS_RESULT_PATH,
        READINESS_AUDIT_PATH,
    )


def bindings() -> tuple[S4SourceBinding, ...]:
    return tuple(
        S4SourceBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(predecessor_paths(), key=lambda item: item.as_posix())
    )


def load_and_validate_inputs() -> None:
    StrategyFactoryContract.model_validate_json(
        FACTORY_PATH.read_text(encoding="utf-8")
    )
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
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
    s2_result = S2DevelopmentBacktestResult.model_validate_json(
        S2_BACKTEST_RESULT_PATH.read_text(encoding="utf-8")
    )
    s2_audit = S2DevelopmentBacktestResultAudit.model_validate_json(
        S2_BACKTEST_AUDIT_PATH.read_text(encoding="utf-8")
    )
    s3_charter = S3CftcPositioningCharter.model_validate_json(
        S3_CHARTER_PATH.read_text(encoding="utf-8")
    )
    s3_charter_audit = S3CftcPositioningCharterAudit.model_validate_json(
        S3_CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    protocol = S3CftcSourceFeasibilityProtocol.model_validate_json(
        S3_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        S3_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S3CftcSourceFeasibilityResult.model_validate_json(
        S3_RESULT_PATH.read_text(encoding="utf-8")
    )
    failure = S3CftcSourceTransportFailureAudit.model_validate_json(
        S3_FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    amendment = S3CftcMetadataTransportAmendmentV2.model_validate_json(
        S3_AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    amendment_audit = S3CftcMetadataTransportAmendmentAuditV2.model_validate_json(
        S3_AMENDMENT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    receipt = S3CftcMetadataTransportExecutionReceiptV2.model_validate_json(
        S3_RECEIPT_PATH.read_text(encoding="utf-8")
    )
    receipt_audit = S3CftcMetadataTransportExecutionReceiptAuditV2.model_validate_json(
        S3_RECEIPT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    operator = profile.get("operator_input") or {}
    changed = (
        not audit_s1_lineage(lineage)
        or not audit_s1_lineage_audit(lineage_audit)
        or lineage_audit.ledger_evidence_hash != lineage.ledger_evidence_hash
        or not audit_s2_charter(s2_charter)
        or not audit_s2_charter_audit(s2_charter_audit)
        or s2_charter_audit.charter_evidence_hash
        != s2_charter.charter_evidence_hash
        or s2_result.decision
        != "STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        or s2_audit.result_evidence_hash != s2_result.result_evidence_hash
        or not audit_s3_charter(s3_charter)
        or not audit_s3_charter_audit(s3_charter_audit)
        or s3_charter_audit.charter_evidence_hash
        != s3_charter.charter_evidence_hash
        or not audit_s3_feasibility_protocol(protocol)
        or not audit_s3_feasibility_protocol_audit(protocol_audit)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not audit_s3_feasibility_result(result)
        or not audit_transport_failure(failure)
        or failure.result_evidence_hash != result.result_evidence_hash
        or not audit_transport_amendment(amendment)
        or not audit_transport_amendment_audit(amendment_audit)
        or amendment_audit.amendment_evidence_hash
        != amendment.amendment_evidence_hash
        or not audit_transport_execution_receipt(receipt)
        or not audit_transport_execution_receipt_audit(receipt_audit)
        or receipt_audit.receipt_evidence_hash != receipt.receipt_evidence_hash
        or receipt.decision != S3_TRANSPORT_V2_RETIREMENT
        or receipt.rerun_authority_exhausted is not True
        or receipt.cftc_target_position_values_read != 0
        or receipt.btc_market_values_read != 0
        or receipt.orders_submitted != 0
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
        or operator.get("permitted_symbols") != ["BTCUSDT"]
        or operator.get("simulated_starting_equity") != "1E+2"
    )
    if changed:
        raise ValueError("S4 predecessor lineage or operator boundary changed")


def research_sources(*, accessed_at: datetime) -> tuple[S4ResearchSource, ...]:
    records = (
        S4ResearchSource(
            source_id="ARK-ARKB-OFFICIAL-DATA",
            title="ARK 21Shares Bitcoin ETF official fund data",
            publisher="ARK Invest",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_ISSUER_DATA",
            url="https://www.ark-funds.com/funds/arkb",
            supported_claims=(
                "Official issuer page exposes holdings downloads and fund metadata.",
                "NAV is ordinarily calculated after the United States market close.",
            ),
            limitations=(
                "Current page availability does not prove a complete historical archive.",
                "Issuer as-of dates do not by themselves prove publication timestamps.",
            ),
        ),
        S4ResearchSource(
            source_id="ISHARES-IBIT-OFFICIAL-DATA",
            title="iShares Bitcoin Trust ETF official fund and holdings data",
            publisher="BlackRock iShares",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_ISSUER_DATA",
            url="https://www.ishares.com/us/products/333011/ishares-bitcoin-trustIBIT",
            supported_claims=(
                "Official issuer page exposes holdings and shares-outstanding fields.",
                "Holdings downloads identify bitcoin quantity as an issuer data field.",
            ),
            limitations=(
                "Visible date selectors do not prove complete daily historical coverage.",
                "Investment-book holdings can differ from accounting-book holdings.",
            ),
        ),
        S4ResearchSource(
            source_id="SEC-2024-SPOT-BITCOIN-ETP-APPROVAL",
            title="Order approving United States spot Bitcoin ETP listings",
            publisher="United States Securities and Exchange Commission",
            publication_or_revision_date="2024-01-10",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_REGULATOR",
            url="https://www.sec.gov/files/rules/sro/nysearca/2024/34-99306.pdf",
            supported_claims=(
                "The SEC approved the listing and trading of multiple spot Bitcoin ETPs.",
                "The approved 2024 structure used cash creations and redemptions.",
            ),
            limitations=(
                "Regulatory approval does not prove investor demand or future returns.",
            ),
        ),
        S4ResearchSource(
            source_id="SEC-2025-CRYPTO-ETP-DISCLOSURE",
            title="Crypto Asset Exchange-Traded Products disclosure statement",
            publisher="United States Securities and Exchange Commission",
            publication_or_revision_date="2025-07-01",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_REGULATOR",
            url=(
                "https://www.sec.gov/newsroom/speeches-statements/"
                "cf-crypto-asset-exchange-traded-products-070125"
            ),
            supported_claims=(
                "Authorized participants facilitate creation and redemption units.",
                "Crypto ETP trusts hold spot assets or derivative instruments.",
            ),
            limitations=(
                "Disclosure guidance does not provide a daily cross-fund history.",
            ),
        ),
        S4ResearchSource(
            source_id="SEC-2025-IN-KIND-APPROVAL",
            title="SEC permits in-kind creations and redemptions for crypto ETPs",
            publisher="United States Securities and Exchange Commission",
            publication_or_revision_date="2025-07-29",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_REGULATOR",
            url=(
                "https://www.sec.gov/newsroom/press-releases/"
                "2025-101-sec-permits-kind-creations-redemptions-crypto-etps"
            ),
            supported_claims=(
                "The SEC permitted in-kind creation and redemption in July 2025.",
                "This changed the earlier cash-only transmission regime.",
            ),
            limitations=(
                "Approval date may differ from each trust's operational effective date.",
            ),
        ),
        S4ResearchSource(
            source_id="SEC-ARKB-IN-KIND-PROSPECTUS-SUPPLEMENT",
            title="ARK 21Shares Bitcoin ETF in-kind prospectus supplement",
            publisher="United States Securities and Exchange Commission EDGAR",
            publication_or_revision_date="2025-07-30",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_SEC_FILING",
            url=(
                "https://www.sec.gov/Archives/edgar/data/1869699/"
                "000121390025069319/ea0250862-424b3_ark21shares.htm"
            ),
            supported_claims=(
                "The trust disclosed in-kind as an alternative to cash processing.",
                "Per-fund filings are required to establish operational regime dates.",
            ),
            limitations=(
                "One trust's filing cannot establish the regime for every ETP.",
            ),
        ),
        S4ResearchSource(
            source_id="SEC-BITB-2025-ANNUAL-REPORT",
            title="Bitwise Bitcoin ETF 2025 annual report",
            publisher="United States Securities and Exchange Commission EDGAR",
            publication_or_revision_date="2026-03-02",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_SEC_FILING",
            url=(
                "https://www.sec.gov/Archives/edgar/data/1763415/"
                "000119312526085335/bitb-20251231.htm"
            ),
            supported_claims=(
                "The filing establishes trust identity, ticker, and first trading date.",
                "Periodic filings can anchor audited fund lifecycle facts.",
            ),
            limitations=(
                "Annual totals cannot replace daily point-in-time creation records.",
            ),
        ),
        S4ResearchSource(
            source_id="SEC-IBIT-2025-ANNUAL-REPORT",
            title="iShares Bitcoin Trust ETF 2025 annual report",
            publisher="United States Securities and Exchange Commission EDGAR",
            publication_or_revision_date="2026-02-27",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_SEC_FILING",
            url=(
                "https://www.sec.gov/Archives/edgar/data/1980994/"
                "000143774926006058/bit20251231_10k.htm"
            ),
            supported_claims=(
                "The filing describes creations, redemptions, and trust operations.",
                "The filing distinguishes cash and in-kind effects in the later regime.",
            ),
            limitations=(
                "Annual disclosures are too coarse for a weekly causal signal.",
            ),
        ),
    )
    return tuple(sorted(records, key=lambda item: item.source_id))


def partitions() -> tuple[S4Partition, ...]:
    return (
        S4Partition(
            role="PRE_ETP_NOT_APPLICABLE",
            start="2017-08-17T00:00:00Z",
            end="2024-01-11T00:00:00Z",
            state="NO_US_SPOT_BITCOIN_ETP_MECHANISM",
        ),
        S4Partition(
            role="CASH_ONLY_DEVELOPMENT",
            start="2024-01-11T00:00:00Z",
            end="2025-07-29T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S4Partition(
            role="MIXED_REGIME_OUTCOME_AWARE_SCREEN",
            start="2025-07-29T00:00:00Z",
            end="2026-11-07T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S4Partition(
            role="PROSPECTIVE_VALIDATION",
            start="2026-11-07T00:00:00Z",
            end="2027-05-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S4Partition(
            role="FUTURE_HOLDOUT",
            start="2027-05-07T00:00:00Z",
            end="2027-11-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S4Partition(
            role="FORWARD",
            start="2027-11-07T00:00:00Z",
            end=None,
            state="LOCKED_FUTURE",
        ),
    )


def build_charter(*, frozen_at: datetime) -> S4SpotBitcoinEtpCharter:
    load_and_validate_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "predecessor_bindings": bindings(),
        "research_sources": research_sources(accessed_at=frozen_at),
        "operator_scope": S4OperatorScope(),
        "ex_ante_hypothesis": (
            "Persistent positive net primary-market creations across the complete "
            "universe of United States spot Bitcoin ETPs may represent regulated "
            "allocator demand and bitcoin inventory absorption that transfers to "
            "BTCUSDT Spot after every included issuer record is publicly available. "
            "Aurex may later evaluate one weekly long-or-cash candidate, but only "
            "after complete point-in-time issuer history and each fund's cash-versus-"
            "in-kind regime are proven; missing, late, revised, or narrow fund "
            "participation means cash, never short exposure."
        ),
        "cash_only_regime_start": datetime(2024, 1, 11, tzinfo=UTC),
        "sec_in_kind_authorization_date": datetime(2025, 7, 29, tzinfo=UTC),
        "causal_observation_policy": (
            "INCLUDE_EVERY_SEC_APPROVED_US_SPOT_BITCOIN_ETP_FROM_FIRST_TRADING_DATE",
            "USE_ONLY_OFFICIAL_ISSUER_OR_SEC_FILED_RECORDS_AVAILABLE_AT_DECISION_TIME",
            "REQUIRE_ACTUAL_PUBLICATION_TIMESTAMP_OR_VERIFIABLE_AVAILABILITY_MARKER",
            "AGGREGATE_ONLY_COMPLETE_BUSINESS_DAYS_THROUGH_THE_PRIOR_FRIDAY",
            "EARLIEST_EXECUTION_IS_MONDAY_00_00_UTC_AFTER_A_24_HOUR_BUFFER",
            "SEPARATE_CASH_ONLY_AND_PER_FUND_CASH_OR_IN_KIND_REGIMES",
            "ADJUST_FOR_FEES_SPLITS_MERGERS_CLOSURES_AND_NON_CREATION_HOLDING_CHANGES",
            "NEW_LAUNCHES_ENTER_PROSPECTIVELY_AND_CLOSED_FUNDS_REMAIN_IN_HISTORY",
            "MISSING_LATE_REVISED_OR_AMBIGUOUS_FUND_RECORD_FORCES_CASH",
            "HASH_ALL_METADATA_FILINGS_REQUESTS_RESPONSES_AND_FUTURE_PAYLOADS",
        ),
        "exact_source_requirements": (
            "OFFICIAL_SEC_APPROVAL_AND_FILING_IDENTITY_FOR_COMPLETE_ETP_UNIVERSE",
            "OFFICIAL_FIRST_TRADING_DATE_AND_TERMINATION_OR_REORGANIZATION_DATE",
            "OFFICIAL_DAILY_SHARES_OUTSTANDING_HISTORY_FOR_EVERY_INCLUDED_FUND",
            "OFFICIAL_DAILY_BITCOIN_HOLDINGS_OR_BITCOIN_PER_SHARE_HISTORY",
            "ACTUAL_PUBLICATION_TIMESTAMP_OR_CAUSALLY_VERIFIABLE_AVAILABILITY_MARKER",
            "PER_FUND_CASH_AND_IN_KIND_OPERATIONAL_EFFECTIVE_DATES",
            "CREATION_BASKET_SIZE_AND_CORPORATE_ACTION_HISTORY",
            "SPONSOR_FEE_AND_NON_CREATION_BITCOIN_DISPOSAL_RECONCILIATION",
            "SURVIVORSHIP_SAFE_NEW_LAUNCH_CLOSURE_MERGER_AND_TICKER_HISTORY",
            "IMMUTABLE_REQUEST_RESPONSE_FILING_AND_DOWNLOAD_HASHES",
            "OFFICIAL_BINANCE_SPOT_BTCUSDT_EXECUTION_PRICES_WITH_CHECKSUMS",
            "ZERO_DOLLAR_ACCESS_WITH_DOCUMENTED_REUSE_RIGHTS",
        ),
        "independence_exclusions": (
            "NO_PRICE_MOMENTUM_TREND_PULLBACK_BREAKOUT_OR_MEAN_REVERSION_INPUT",
            "NO_VOLATILITY_SCALING_PATH_QUALITY_OR_CROSS_SECTIONAL_RANKING_INPUT",
            "NO_AGGRESSOR_FLOW_ORDER_BOOK_CLOCK_PHASE_OR_JAM_EXHAUSTION_INPUT",
            "NO_FUNDING_BASIS_CARRY_PERPETUAL_FLOW_OR_CROSS_VENUE_INPUT",
            "NO_NFCI_MONETARY_FINANCIAL_CONDITIONS_OR_OTHER_MACRO_INPUT",
            "NO_BITCOIN_ONCHAIN_TRANSACTION_FEE_OR_SETTLEMENT_DEMAND_INPUT",
            "NO_STABLECOIN_ISSUANCE_TRANSFER_OR_ONCHAIN_LIQUIDITY_INPUT",
            "NO_VARIANCE_RISK_PREMIUM_OPTION_OR_DERIVATIVES_PRICING_INPUT",
            "NO_CFTC_POSITION_OPEN_INTEREST_VOLUME_OR_FUTURES_RETURN_INPUT",
            "NO_ETP_SECONDARY_MARKET_VOLUME_PREMIUM_DISCOUNT_OR_PRICE_SIGNAL_INPUT",
            "NO_FUTURES_ETP_OPTIONS_SHORTING_BORROWING_OR_LEVERAGE",
            "NO_REUSE_OF_S1_S2_S3_THRESHOLDS_DIAGNOSTICS_FAILURES_OR_OUTCOMES",
            "NO_PARAMETER_SEARCH_ENSEMBLE_OR_POST_HOC_SIGNAL_REVERSAL",
        ),
        "feasibility_gates": (
            "ALL_ELEVEN_PREDECESSOR_FAMILIES_BOUND_AND_NONREUSABLE",
            "COMPLETE_SEC_APPROVED_US_SPOT_BITCOIN_ETP_UNIVERSE_IS_RECONSTRUCTABLE",
            "EVERY_FUND_FIRST_TRADE_CLOSURE_MERGER_AND_TICKER_EVENT_IS_RECONSTRUCTABLE",
            "OFFICIAL_DAILY_SHARES_OUTSTANDING_HISTORY_IS_COMPLETE_POINT_IN_TIME",
            "OFFICIAL_DAILY_BITCOIN_HOLDINGS_OR_PER_SHARE_HISTORY_IS_COMPLETE",
            "ACTUAL_PUBLICATION_TIMING_IS_CAUSALLY_RECONSTRUCTABLE_FOR_EVERY_RECORD",
            "CASH_ONLY_AND_PER_FUND_IN_KIND_EFFECTIVE_DATES_ARE_RECONSTRUCTABLE",
            "FEES_SPLITS_AND_NON_CREATION_HOLDING_CHANGES_ARE_DISTINGUISHABLE",
            "SURVIVORSHIP_SAFE_CROSS_FUND_CALENDAR_AND_MISSINGNESS_ARE_IMPLEMENTABLE",
            "WEEKLY_FRIDAY_CUTOFF_AND_MONDAY_EXECUTION_BUFFER_ARE_IMPLEMENTABLE",
            "ZERO_DOLLAR_ACCESS_AND_REUSE_RIGHTS_ARE_DOCUMENTED_FOR_ALL_SOURCES",
            "INCIDENTAL_SOURCE_NUMERIC_FIELD_EXPOSURE_IS_DECLARED_AND_NONQUALIFYING",
            "ONE_SELECTABLE_MECHANISM_AND_ZERO_CHARTER_STAGE_PARAMETERS",
            "FAILURE_OF_ANY_GATE_SELECTS_ZERO_AND_STOPS_S4_BEFORE_ETP_VALUES",
        ),
        "partitions": partitions(),
        "rejected_candidate_families": tuple(
            sorted(
                (
                    "MINER_INVENTORY_SELF_REPORTING_REJECTED_FOR_SPARSE_NONUNIFORM_TIMING",
                    "SEARCH_AND_SOCIAL_ATTENTION_REJECTED_FOR_REVISED_NORMALIZED_SOURCE",
                    "STABLECOIN_ISSUANCE_REJECTED_FOR_ONCHAIN_OVERLAP_AND_SOURCE_FRAGMENTATION",
                )
            )
        ),
        "source_metadata_pages_inspected": tuple(
            source.url for source in research_sources(accessed_at=frozen_at)
        ),
        "incidental_source_numeric_fields_observed": (
            "BITCOIN_QUANTITY_HELD",
            "NET_ASSET_VALUE",
            "SHARES_CREATED_OR_REDEEMED_ANNUAL_TOTAL",
            "SHARES_OUTSTANDING",
        ),
        "limitations": tuple(
            sorted(
                (
                    "This charter selects a source-feasibility hypothesis, not a strategy.",
                    "Official search snippets exposed example issuer numeric fields; "
                    "those fields and all historical periods are nonqualifying.",
                    "No ETP time-series row, downloadable numeric payload, or BTC return "
                    "outcome was parsed or persisted by Aurex.",
                    "Shares outstanding can change for reasons requiring corporate-action "
                    "and trust-operation reconciliation.",
                    "Bitcoin holdings can change because of sponsor fees or expenses, not "
                    "only creations and redemptions.",
                    "Cash creations can cause open-market purchases while in-kind creations "
                    "can transfer inventory, so transmission is regime-dependent.",
                    "Issuer pages may revise history or omit publication timestamps.",
                    "Annual SEC filings are authoritative but too coarse for weekly signals.",
                    "The short post-2024 history limits development and regime sample size.",
                    "All available ETP and BTC history is outcome-aware and cannot qualify S4.",
                    "Prospective validation and holdout require twelve future months before "
                    "live eligibility can be considered.",
                    "No ETP value, BTC market value, parameter, return, candidate, signal, "
                    "paper order, Testnet strategy order, production action, live action, "
                    "real capital, or profit is authorized.",
                )
            )
        ),
    }
    provisional = S4SpotBitcoinEtpCharter.model_construct(
        **payload, charter_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["charter_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"charter_evidence_hash"})
    )
    return S4SpotBitcoinEtpCharter.model_validate(complete)


def write_atomic(path: Path, charter: S4SpotBitcoinEtpCharter) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S4 charter: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S4 charter transaction exists: {temporary}")
    serialized = charter.model_dump_json(indent=2) + "\n"
    if S4SpotBitcoinEtpCharter.model_validate_json(serialized) != charter:
        raise ValueError("S4 charter did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S4 charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S4SpotBitcoinEtpCharter.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_charter(frozen_at=stored.frozen_at):
                raise ValueError("Stored S4 charter differs from reconstruction")
            print(f"PASS {stored.charter_evidence_hash}")
            return 0
        charter = build_charter(frozen_at=datetime.now(UTC))
        write_atomic(args.output, charter)
        print(
            f"FROZEN {args.output} {charter.charter_evidence_hash} "
            "etp_rows=0 payloads=0 market_values=0 parameters=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
