from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s4_etp_source_feasibility_viability import (  # noqa: E402
    S4_VIABILITY_NEXT,
    S4_VIABILITY_STOP,
    S4EtpSourceFeasibilityViabilityReview,
    S4EtpSourceFeasibilityViabilityReviewAudit,
    audit_s4_viability_review,
    audit_s4_viability_review_audit,
)
from aurex.backtest_engine.s4_spot_bitcoin_etp_charter import (  # noqa: E402
    S4SpotBitcoinEtpCharter,
    S4SpotBitcoinEtpCharterAudit,
    audit_s4_charter,
    audit_s4_charter_audit,
)
from aurex.backtest_engine.s4_spot_bitcoin_etp_source_feasibility import (  # noqa: E402
    S4EtpSourceFeasibilityProtocol,
    S4EtpSourceFeasibilityProtocolAudit,
    audit_s4_feasibility_protocol,
    audit_s4_feasibility_protocol_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_development_charter import (  # noqa: E402
    S5BitcoinCoreDevelopmentCharter,
    S5GitRefRecord,
    S5OperatorScope,
    S5Partition,
    S5ResearchSource,
    S5SourceBinding,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_development_charter_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_development_charter.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_development_charter.py")
S4_CHARTER_PATH = Path("data/evidence/s4_spot_bitcoin_etp_charter_v1.json")
S4_CHARTER_AUDIT_PATH = Path("data/evidence/s4_spot_bitcoin_etp_charter_audit_v1.json")
S4_PROTOCOL_PATH = Path("data/evidence/s4_etp_source_feasibility_protocol_v1.json")
S4_PROTOCOL_AUDIT_PATH = Path("data/evidence/s4_etp_source_feasibility_protocol_audit_v1.json")
S4_VIABILITY_PATH = Path("data/evidence/s4_etp_source_feasibility_viability_review_v1.json")
S4_VIABILITY_AUDIT_PATH = Path(
    "data/evidence/s4_etp_source_feasibility_viability_review_audit_v1.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v27.json"
)
READINESS_AUDIT_PATH = Path("data/evidence/aurex_strategy_factory_readiness_current_audit_v27.json")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def stored_s4_charter() -> S4SpotBitcoinEtpCharter:
    return S4SpotBitcoinEtpCharter.model_validate_json(S4_CHARTER_PATH.read_text(encoding="utf-8"))


def predecessor_paths() -> tuple[Path, ...]:
    inherited = tuple(Path(item.path) for item in stored_s4_charter().predecessor_bindings)
    current = (
        S4_CHARTER_PATH,
        S4_CHARTER_AUDIT_PATH,
        S4_PROTOCOL_PATH,
        S4_PROTOCOL_AUDIT_PATH,
        S4_VIABILITY_PATH,
        S4_VIABILITY_AUDIT_PATH,
        READINESS_RESULT_PATH,
        READINESS_AUDIT_PATH,
    )
    paths = tuple(sorted((*inherited, *current), key=lambda item: item.as_posix()))
    if len(paths) != 28 or len(set(paths)) != 28:
        raise ValueError("S5 predecessor lineage must contain exactly 28 unique files")
    return paths


def bindings() -> tuple[S5SourceBinding, ...]:
    return tuple(
        S5SourceBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in predecessor_paths()
    )


def load_and_validate_inputs() -> None:
    charter = stored_s4_charter()
    charter_audit = S4SpotBitcoinEtpCharterAudit.model_validate_json(
        S4_CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    protocol = S4EtpSourceFeasibilityProtocol.model_validate_json(
        S4_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S4EtpSourceFeasibilityProtocolAudit.model_validate_json(
        S4_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    viability = S4EtpSourceFeasibilityViabilityReview.model_validate_json(
        S4_VIABILITY_PATH.read_text(encoding="utf-8")
    )
    viability_audit = S4EtpSourceFeasibilityViabilityReviewAudit.model_validate_json(
        S4_VIABILITY_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not audit_s4_charter(charter)
        or not audit_s4_charter_audit(charter_audit)
        or charter_audit.charter_evidence_hash != charter.charter_evidence_hash
        or not audit_s4_feasibility_protocol(protocol)
        or not audit_s4_feasibility_protocol_audit(protocol_audit)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not audit_s4_viability_review(viability)
        or not audit_s4_viability_review_audit(viability_audit)
        or viability_audit.review_evidence_hash != viability.review_evidence_hash
        or viability.decision != S4_VIABILITY_STOP
        or viability.next_authorization != S4_VIABILITY_NEXT
        or viability.network_requests_executed != 0
        or viability.run_authority_consumed is not False
        or viability.protocol_pass_condition_reachable is not False
        or viability.orders_submitted != 0
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.decision != "PASS_AUREX_STRATEGY_FACTORY_READY_FOR_NEW_MECHANISM_CHARTER_ONLY"
        or readiness.next_action != "DESIGN_ONE_NEW_UNRELATED_MECHANISM_CHARTER_ONLY"
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
        or charter.operator_scope.symbol != "BTCUSDT"
        or charter.operator_scope.simulated_equity_usd != "100"
    )
    if changed:
        raise ValueError("S5 predecessor lineage or operator boundary changed")


def research_sources(*, accessed_at: datetime) -> tuple[S5ResearchSource, ...]:
    records = (
        S5ResearchSource(
            source_id="BITCOIN-CORE-CANONICAL-REPOSITORY",
            title="Bitcoin Core integration and staging repository",
            publisher="Bitcoin Core developers",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_PROJECT_REPOSITORY",
            url="https://github.com/bitcoin/bitcoin",
            supported_claims=(
                "The public bitcoin/bitcoin repository is the Bitcoin Core "
                "integration and staging tree.",
                "The master branch is regularly built and tested and official "
                "releases are tagged from release branches.",
            ),
            limitations=(
                "Current repository statistics and history do not establish predictive edge.",
                "The master branch is an integration surface, not the Bitcoin "
                "consensus protocol itself.",
            ),
        ),
        S5ResearchSource(
            source_id="BITCOIN-CORE-CONTRIBUTING",
            title="Contributing to Bitcoin Core",
            publisher="Bitcoin Core developers",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_PROJECT_GOVERNANCE",
            url="https://github.com/bitcoin/bitcoin/blob/master/CONTRIBUTING.md",
            supported_claims=(
                "Bitcoin Core uses an open contributor and pull-request workflow "
                "with peer review, testing, and patches.",
                "Rebases and force pushes can rewrite proposal commits before "
                "accepted integration, while signed merge commits support auditability.",
            ),
            limitations=(
                "Governance guidance does not guarantee complete historical pull-request metadata.",
                "Contributor identities can be pseudonymous, duplicated, or changed over time.",
            ),
        ),
        S5ResearchSource(
            source_id="BITCOIN-CORE-MIT-LICENSE",
            title="Bitcoin Core MIT license",
            publisher="Bitcoin Core developers",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_LICENSE",
            url="https://github.com/bitcoin/bitcoin/blob/master/COPYING",
            supported_claims=(
                "Bitcoin Core software and accompanying documentation are available "
                "under the MIT license.",
            ),
            limitations=(
                "The license does not grant rights in third-party GitHub platform "
                "metadata beyond applicable terms.",
            ),
        ),
        S5ResearchSource(
            source_id="FASB-ASU-2023-08-CRYPTO-ASSETS",
            title="ASU 2023-08 accounting for and disclosure of crypto assets",
            publisher="Financial Accounting Standards Board",
            publication_or_revision_date="2023-12-13",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_ACCOUNTING_STANDARD",
            url="https://storage.fasb.org/ASU%202023-08.pdf",
            supported_claims=(
                "The crypto-asset amendments are effective for fiscal years beginning "
                "after December 15, 2024, with early adoption permitted.",
            ),
            limitations=(
                "The recent effective date leaves too little standardized history "
                "for the rejected corporate-treasury candidate.",
            ),
        ),
        S5ResearchSource(
            source_id="GIT-COMMIT-DOCUMENTATION",
            title="git-commit documentation",
            publisher="Git project",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_VCS_DOCUMENTATION",
            url="https://git-scm.com/docs/git-commit",
            supported_claims=(
                "Git permits the author date to be overridden, so author timestamps "
                "cannot establish public availability.",
            ),
            limitations=(
                "A commit object does not by itself prove when a hosting platform "
                "first made it public.",
            ),
        ),
        S5ResearchSource(
            source_id="GIT-LOG-DOCUMENTATION",
            title="git-log documentation",
            publisher="Git project",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_VCS_DOCUMENTATION",
            url="https://git-scm.com/docs/git-log",
            supported_claims=(
                "Git log can reconstruct exact commit topology, first-parent history, "
                "timestamps, and object identities.",
            ),
            limitations=(
                "Current reachable history alone does not prove point-in-time "
                "availability or preserve removed objects.",
            ),
        ),
        S5ResearchSource(
            source_id="GITHUB-COMMITS-REST-API",
            title="GitHub REST API endpoints for commits",
            publisher="GitHub",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_PLATFORM_API_DOCUMENTATION",
            url="https://docs.github.com/en/rest/commits/commits",
            supported_claims=(
                "Public commit resources can be requested without authentication.",
                "Commit responses expose immutable object identities and signature "
                "verification metadata.",
            ),
            limitations=(
                "REST responses are rate limited and do not guarantee preservation "
                "of unreachable history.",
            ),
        ),
        S5ResearchSource(
            source_id="GITHUB-PULLS-REST-API",
            title="GitHub REST API endpoints for pull requests",
            publisher="GitHub",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_PLATFORM_API_DOCUMENTATION",
            url="https://docs.github.com/en/rest/pulls/pulls",
            supported_claims=(
                "Public pull-request resources can be requested without authentication.",
                "Pull-request responses expose merged_at and merge-commit identity "
                "fields needed for causal timing checks.",
            ),
            limitations=(
                "Pagination, rate limits, deleted accounts, and missing legacy "
                "records require explicit completeness gates.",
            ),
        ),
        S5ResearchSource(
            source_id="GITHUB-REST-RATE-LIMITS",
            title="GitHub REST API rate limits",
            publisher="GitHub",
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_PLATFORM_API_DOCUMENTATION",
            url=("https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api"),
            supported_claims=(
                "GitHub documents separate unauthenticated and authenticated REST request limits.",
            ),
            limitations=(
                "A zero-dollar source can still be operationally infeasible if the "
                "frozen request budget is insufficient.",
            ),
        ),
        S5ResearchSource(
            source_id="SEC-2025-XBRL-TAXONOMIES",
            title="2025 XBRL taxonomies update",
            publisher="United States Securities and Exchange Commission",
            publication_or_revision_date="2025-03-17",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_REGULATOR",
            url="https://www.sec.gov/newsroom/whats-new/2503-2025-xbrl-taxonomies-update",
            supported_claims=("EDGAR began supporting the 2025 U.S. GAAP taxonomy in March 2025.",),
            limitations=(
                "Standardized corporate crypto facts remain recent, quarterly, and "
                "potentially dimensioned or issuer-specific.",
            ),
        ),
    )
    return tuple(sorted(records, key=lambda item: item.source_id))


def partitions() -> tuple[S5Partition, ...]:
    return (
        S5Partition(
            role="SOURCE_ONLY_PRE_BINANCE_SPOT_HISTORY",
            start="2009-01-03T00:00:00Z",
            end="2017-08-17T00:00:00Z",
            state="NO_BINANCE_BTCUSDT_EXECUTION_MARKET",
        ),
        S5Partition(
            role="DEVELOPMENT",
            start="2017-08-17T00:00:00Z",
            end="2023-01-01T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S5Partition(
            role="OUTCOME_AWARE_SCREEN",
            start="2023-01-01T00:00:00Z",
            end="2026-11-07T00:00:00Z",
            state="OUTCOME_AWARE_NONQUALIFYING",
        ),
        S5Partition(
            role="PROSPECTIVE_VALIDATION",
            start="2026-11-07T00:00:00Z",
            end="2027-05-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S5Partition(
            role="FUTURE_HOLDOUT",
            start="2027-05-07T00:00:00Z",
            end="2027-11-07T00:00:00Z",
            state="LOCKED_FUTURE",
        ),
        S5Partition(
            role="FORWARD",
            start="2027-11-07T00:00:00Z",
            end=None,
            state="LOCKED_FUTURE",
        ),
    )


def build_charter(*, frozen_at: datetime) -> S5BitcoinCoreDevelopmentCharter:
    load_and_validate_inputs()
    sources = research_sources(accessed_at=frozen_at)
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "predecessor_bindings": bindings(),
        "research_sources": sources,
        "operator_scope": S5OperatorScope(),
        "ex_ante_hypothesis": (
            "Sustained breadth in accepted Bitcoin Core development, peer-reviewed "
            "integration, and official release continuity may reduce protocol-software "
            "maintenance risk and support durable allocator confidence after the evidence "
            "was publicly observable. Aurex may later evaluate one monthly BTCUSDT Spot "
            "long-or-cash candidate only if accepted-history identity, publication timing, "
            "contributor aliasing, and history-mutation controls are complete; ambiguous or "
            "missing evidence means cash and never short exposure."
        ),
        "causal_observation_policy": (
            "CANONICAL_BITCOIN_BITCOIN_REPOSITORY_ONLY",
            "ACCEPTED_MASTER_HISTORY_AND_OFFICIAL_RELEASE_TAGS_ONLY",
            "NEVER_USE_AUTHOR_DATE_AS_PUBLIC_AVAILABILITY_TIME",
            "MATCH_ACCEPTED_MERGES_TO_GITHUB_PULL_REQUEST_MERGED_AT_WHERE_AVAILABLE",
            "REQUIRE_COMMIT_AND_MERGE_OBJECT_IDENTITY_CONSISTENCY",
            "APPLY_A_PREDECLARED_CONSERVATIVE_LAG_AFTER_PROVEN_PUBLIC_AVAILABILITY",
            "AGGREGATE_ONLY_COMPLETE_PRIOR_UTC_CALENDAR_MONTHS",
            "HASH_CONTRIBUTOR_IDENTIFIERS_AND_STORE_NO_UNNECESSARY_PERSONAL_DATA",
            "DO_NOT_APPLY_TODAYS_MAILMAP_RETROACTIVELY_TO_HISTORICAL_IDENTITIES",
            "TREAT_ALIAS_COLLISIONS_BOTS_AND_DELETED_ACCOUNTS_AS_EXPLICIT_UNCERTAINTY",
            "MISSING_OR_AMBIGUOUS_PULL_REQUEST_MAPPING_FORCES_CASH",
            "PIN_EVERY_SOURCE_SNAPSHOT_TO_EXACT_OBJECT_HASHES",
            "DETECT_FORCE_PUSH_REWRITE_OR_UNREACHABLE_HISTORY_BETWEEN_SNAPSHOTS",
            "PRESERVE_RELEASE_TAG_AND_SIGNATURE_METADATA_WITHOUT_TRUSTING_UNSIGNED_LABELS",
            "HASH_ALL_FUTURE_REQUESTS_RESPONSES_REFS_AND_PAYLOADS",
        ),
        "metadata_feasibility_gates": (
            "ALL_TWELVE_PREDECESSOR_FAMILIES_BOUND_AND_NONREUSABLE",
            "CANONICAL_REPOSITORY_IDENTITY_AND_MASTER_BRANCH_DOCUMENTED",
            "PUBLIC_GIT_SMART_HTTP_REF_DISCOVERY_REACHABLE_WITHOUT_CREDENTIALS",
            "MIT_REUSE_RIGHTS_DOCUMENTED",
            "AUTHOR_DATE_OVERRIDE_RISK_DOCUMENTED",
            "BITCOIN_CORE_PULL_REQUEST_REBASE_AND_SIGNED_MERGE_WORKFLOW_DOCUMENTED",
            "PUBLIC_GITHUB_COMMIT_METADATA_ENDPOINT_DOCUMENTED",
            "PUBLIC_GITHUB_PULL_REQUEST_MERGED_AT_ENDPOINT_DOCUMENTED",
            "ZERO_DOLLAR_GITHUB_RATE_LIMIT_AND_REQUEST_BUDGET_PATH_DOCUMENTED",
            "EXACT_REF_HASH_PERSISTENCE_AND_RECHECK_IS_IMPLEMENTABLE",
            "POINT_IN_TIME_AVAILABILITY_FIELDS_EXIST_WITHOUT_HISTORY_PAYLOAD_ACCESS",
            "METADATA_PROTOCOL_PASS_CONDITION_IS_REACHABLE_BY_ALLOWED_SOURCES",
            "ONE_SELECTABLE_MECHANISM_AND_ZERO_CHARTER_STAGE_PARAMETERS",
            "FAILURE_OF_ANY_GATE_STOPS_S5_BEFORE_REPOSITORY_HISTORY_OR_BTC_VALUES",
        ),
        "downstream_payload_requirements": (
            "COMPLETE_CANONICAL_REPOSITORY_CLONE_PINNED_TO_AN_EXACT_MASTER_OBJECT",
            "COMPLETE_FIRST_PARENT_AND_ACCEPTED_TOPIC_COMMIT_TOPOLOGY",
            "MERGE_COMMIT_TO_PULL_REQUEST_IDENTITY_MAPPING",
            "POINT_IN_TIME_MERGED_AT_OR_CONSERVATIVE_AVAILABILITY_EVIDENCE",
            "OFFICIAL_RELEASE_TAG_OBJECT_AND_SIGNATURE_HISTORY",
            "HISTORY_REWRITE_AND_FORCE_PUSH_DETECTION_ACROSS_SNAPSHOTS",
            "CAUSAL_CONTRIBUTOR_ALIAS_POLICY_WITHOUT_RETROACTIVE_MAILMAP_LOOKAHEAD",
            "BOT_DELETED_ACCOUNT_AND_PSEUDONYM_UNCERTAINTY_POLICY",
            "COMPONENT_CLASSIFICATION_DEFINED_BEFORE_HISTORY_MEASUREMENT",
            "SUFFICIENT_COMPLETE_MONTHLY_OBSERVATIONS_FOR_FROZEN_CHRONOLOGICAL_GATES",
            "OFFICIAL_BINANCE_SPOT_BTCUSDT_EXECUTION_PRICES_WITH_CHECKSUMS",
            "ZERO_DOLLAR_ACCESS_AND_DOCUMENTED_REUSE_RIGHTS_FOR_EVERY_SOURCE",
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
            "NO_ETP_PRIMARY_OR_SECONDARY_MARKET_INPUT",
            "NO_CORPORATE_TREASURY_HOLDING_OR_EQUITY_MARKET_INPUT",
            "NO_GITHUB_STARS_FORKS_WATCHERS_ISSUES_OR_OPEN_PULL_REQUEST_LEVEL_INPUT",
            "NO_UNMERGED_COMMIT_PROPOSAL_OR_SOCIAL_ATTENTION_INPUT",
            "NO_FUTURES_ETP_OPTIONS_SHORTING_BORROWING_OR_LEVERAGE",
            "NO_REUSE_OF_S1_S2_S3_S4_THRESHOLDS_DIAGNOSTICS_FAILURES_OR_OUTCOMES",
            "NO_PARAMETER_SEARCH_ENSEMBLE_OR_POST_HOC_SIGNAL_REVERSAL",
        ),
        "partitions": partitions(),
        "rejected_candidate_families": tuple(
            sorted(
                (
                    "DETERMINISTIC_BITCOIN_HALVING_REJECTED_FOR_TOO_FEW_INDEPENDENT_EVENTS",
                    "PUBLIC_COMPANY_BITCOIN_TREASURY_XBRL_REJECTED_FOR_SHORT_STANDARDIZED_HISTORY_AND_QUARTERLY_SAMPLE",
                    "SEARCH_AND_SOCIAL_ATTENTION_REJECTED_AS_PREVIOUSLY_EXHAUSTED_REVISED_SOURCE",
                )
            )
        ),
        "pre_freeze_git_ref_records": tuple(
            sorted(
                (
                    S5GitRefRecord(
                        ref="HEAD",
                        object_hash="fe3c92cfe0da39d7f34ee3e11fee056b141afd0e",
                    ),
                    S5GitRefRecord(
                        ref="refs/heads/master",
                        object_hash="fe3c92cfe0da39d7f34ee3e11fee056b141afd0e",
                    ),
                    S5GitRefRecord(
                        ref="refs/tags/v30.0",
                        object_hash="24d56e53d98da73f09f042ea879a662edb0565c9",
                    ),
                ),
                key=lambda item: item.ref,
            )
        ),
        "incidental_repository_numeric_context_categories": tuple(
            sorted(
                (
                    "CURRENT_AGGREGATE_COMMIT_COUNT",
                    "CURRENT_FORK_COUNT",
                    "CURRENT_OPEN_ISSUE_COUNT",
                    "CURRENT_OPEN_PULL_REQUEST_COUNT",
                    "CURRENT_STAR_COUNT",
                    "CURRENT_WATCHER_COUNT",
                )
            )
        ),
        "source_metadata_pages_inspected": tuple(source.url for source in sources),
        "limitations": tuple(
            sorted(
                (
                    "This charter selects a source-feasibility hypothesis, not a strategy.",
                    "No accepted commit history, pull-request history, release history, "
                    "or BTC return outcome was parsed by Aurex.",
                    "A public Git ref probe established transport reachability only and "
                    "does not prove complete historical availability.",
                    "Current repository aggregate statistics were incidentally visible, "
                    "are outcome-aware, and cannot qualify S5.",
                    "Exact incidental aggregate statistic values are not persisted in "
                    "the S5 charter.",
                    "Author timestamps are user-controlled and cannot establish causal "
                    "availability.",
                    "Committer timestamps can still differ from first public availability "
                    "and require platform corroboration plus lag.",
                    "Rebases and force pushes can remove proposal history before merge.",
                    "Current reachable history cannot prove that every object was "
                    "reachable at every historical decision time.",
                    "Contributor names and emails can alias, collide, change, be "
                    "pseudonymous, or identify bots.",
                    "Development activity may respond to adoption or price rather than "
                    "lead it, creating reverse-causality risk.",
                    "Software activity may measure maintenance workload rather than "
                    "protocol quality or future demand.",
                    "GitHub API pagination and rate limits may make complete metadata "
                    "acquisition operationally infeasible.",
                    "All available repository and BTC history is outcome-aware and "
                    "cannot qualify S5.",
                    "Prospective validation and holdout require twelve future months "
                    "before live eligibility can be considered.",
                    "No repository history payload, BTC market value, parameter, return, "
                    "candidate, signal, paper order, Testnet strategy order, production "
                    "action, live action, real capital, or profit is authorized.",
                    "The corporate-treasury alternative was rejected before charter "
                    "because standardized crypto reporting is recent and quarterly.",
                    "The deterministic halving alternative was rejected because too few "
                    "independent events exist for defensible inference.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreDevelopmentCharter.model_construct(
        **payload, charter_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["charter_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"charter_evidence_hash"})
    )
    return S5BitcoinCoreDevelopmentCharter.model_validate(complete)


def write_atomic(path: Path, charter: S5BitcoinCoreDevelopmentCharter) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 charter: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 charter transaction exists: {temporary}")
    serialized = charter.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreDevelopmentCharter.model_validate_json(serialized) != charter:
        raise ValueError("S5 charter did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S5 charter.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreDevelopmentCharter.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_charter(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 charter differs from reconstruction")
            print(f"PASS {stored.charter_evidence_hash}")
            return 0
        charter = build_charter(frozen_at=datetime.now(UTC))
        write_atomic(args.output, charter)
        print(
            f"FROZEN {args.output} {charter.charter_evidence_hash} "
            "git_probe_requests=1 refs=3 history_records=0 market_values=0 "
            "parameters=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
