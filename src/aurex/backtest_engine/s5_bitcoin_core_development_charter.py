from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_MECHANISM_ID = "S5-BITCOIN-CORE-ACCEPTED-DEVELOPMENT-BREADTH"
S5_CHARTER_DECISION = "FREEZE_S5_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY"
S5_NEXT_AUTHORIZATION = "AUTHORIZE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_PROTOCOL_ONLY"


class S5SourceBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S5ResearchSource(BaseModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    publication_or_revision_date: str | None
    accessed_at: datetime
    source_kind: Literal[
        "OFFICIAL_ACCOUNTING_STANDARD",
        "OFFICIAL_LICENSE",
        "OFFICIAL_PLATFORM_API_DOCUMENTATION",
        "OFFICIAL_PROJECT_GOVERNANCE",
        "OFFICIAL_PROJECT_REPOSITORY",
        "OFFICIAL_REGULATOR",
        "OFFICIAL_VCS_DOCUMENTATION",
    ]
    url: str = Field(min_length=10)
    supported_claims: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    does_not_prove_edge: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("accessed_at")
    @classmethod
    def normalize_accessed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)


class S5GitRefRecord(BaseModel):
    ref: str = Field(min_length=1)
    object_hash: str = Field(pattern=r"^[0-9a-f]{40}$")

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5OperatorScope(BaseModel):
    execution_environment: Literal["BINANCE_SPOT_TESTNET"] = "BINANCE_SPOT_TESTNET"
    product: Literal["SPOT"] = "SPOT"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    direction: Literal["LONG_OR_CASH"] = "LONG_OR_CASH"
    maximum_effective_leverage: Literal["1"] = "1"
    simulated_equity_usd: Literal["100"] = "100"
    maximum_per_trade_loss_usd: Literal["0.5"] = "0.5"
    maximum_daily_loss_usd: Literal["1"] = "1"
    maximum_total_loss_usd: Literal["10"] = "10"
    one_time_data_budget_usd: Literal["0"] = "0"
    monthly_data_budget_usd: Literal["0"] = "0"
    production_authority: Literal[False] = False
    live_authority: Literal[False] = False
    real_capital: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5Partition(BaseModel):
    role: Literal[
        "SOURCE_ONLY_PRE_BINANCE_SPOT_HISTORY",
        "DEVELOPMENT",
        "OUTCOME_AWARE_SCREEN",
        "PROSPECTIVE_VALIDATION",
        "FUTURE_HOLDOUT",
        "FORWARD",
    ]
    start: datetime
    end: datetime | None
    state: Literal[
        "NO_BINANCE_BTCUSDT_EXECUTION_MARKET",
        "OUTCOME_AWARE_NONQUALIFYING",
        "LOCKED_FUTURE",
    ]
    outcome_access_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("start", "end")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_partition(self) -> S5Partition:
        if self.end is not None and self.end <= self.start:
            raise ValueError("S5 partition end must be later than start")
        return self


class S5BitcoinCoreDevelopmentCharter(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-development-charter-v1"] = (
        "aurex-s5-bitcoin-core-development-charter-v1"
    )
    charter_id: Literal["s5-bitcoin-core-development-charter-v1"] = (
        "s5-bitcoin-core-development-charter-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_CHARTER_ONLY_NO_REPOSITORY_HISTORY_OR_MARKET_OUTCOMES"] = (
        "FROZEN_CHARTER_ONLY_NO_REPOSITORY_HISTORY_OR_MARKET_OUTCOMES"
    )
    builder_contract_hash: str
    predecessor_bindings: tuple[S5SourceBinding, ...] = Field(min_length=28, max_length=28)
    research_sources: tuple[S5ResearchSource, ...] = Field(min_length=10, max_length=10)
    operator_scope: S5OperatorScope
    mechanism_id: Literal["S5-BITCOIN-CORE-ACCEPTED-DEVELOPMENT-BREADTH"] = S5_MECHANISM_ID
    mechanism_family: Literal[
        "OPEN_SOURCE_PROTOCOL_MAINTENANCE_AND_ACCEPTED_DEVELOPMENT_BREADTH"
    ] = "OPEN_SOURCE_PROTOCOL_MAINTENANCE_AND_ACCEPTED_DEVELOPMENT_BREADTH"
    economic_actor: Literal["BITCOIN_CORE_CONTRIBUTORS_REVIEWERS_AND_MERGE_MAINTAINERS"] = (
        "BITCOIN_CORE_CONTRIBUTORS_REVIEWERS_AND_MERGE_MAINTAINERS"
    )
    ex_ante_hypothesis: str = Field(min_length=160)
    ex_ante_direction: Literal[
        "PERSISTENT_ACCEPTED_DEVELOPMENT_BREADTH_AND_RELEASE_CONTINUITY_LONG_ELSE_CASH"
    ] = "PERSISTENT_ACCEPTED_DEVELOPMENT_BREADTH_AND_RELEASE_CONTINUITY_LONG_ELSE_CASH"
    source_authorities: tuple[
        Literal[
            "BITCOIN_CORE_CANONICAL_REPOSITORY",
            "GIT_OFFICIAL_DOCUMENTATION",
            "GITHUB_OFFICIAL_API",
        ],
        ...,
    ] = (
        "BITCOIN_CORE_CANONICAL_REPOSITORY",
        "GIT_OFFICIAL_DOCUMENTATION",
        "GITHUB_OFFICIAL_API",
    )
    prospective_signal_frequency: Literal["MONTHLY"] = "MONTHLY"
    universe_policy: Literal["CANONICAL_BITCOIN_BITCOIN_MASTER_AND_OFFICIAL_RELEASE_TAGS_ONLY"] = (
        "CANONICAL_BITCOIN_BITCOIN_MASTER_AND_OFFICIAL_RELEASE_TAGS_ONLY"
    )
    prospective_measurement_families: tuple[str, ...] = (
        "ACCEPTED_MASTER_MERGE_CADENCE",
        "ACCEPTED_CONTRIBUTOR_IDENTITY_BREADTH",
        "ACCEPTED_SOURCE_COMPONENT_BREADTH",
        "MERGED_PULL_REQUEST_REVIEW_AND_INTEGRATION_CONTINUITY",
        "OFFICIAL_RELEASE_TAG_CONTINUITY",
    )
    causal_observation_policy: tuple[str, ...] = Field(min_length=12)
    metadata_feasibility_gates: tuple[str, ...] = Field(min_length=14, max_length=14)
    downstream_payload_requirements: tuple[str, ...] = Field(min_length=10)
    independence_exclusions: tuple[str, ...] = Field(min_length=14)
    partitions: tuple[S5Partition, ...] = Field(min_length=6, max_length=6)
    rejected_candidate_families: tuple[str, ...] = Field(min_length=3, max_length=3)
    proposal_budget: Literal[1] = 1
    selected_mechanism_count: Literal[1] = 1
    familywise_predecessor_count: Literal[12] = 12
    metadata_protocol_pass_condition_reachable_by_allowed_sources: Literal[True] = True
    pre_freeze_public_git_probe_executed: Literal[True] = True
    pre_freeze_public_git_probe_request_count: Literal[1] = 1
    pre_freeze_git_ref_records: tuple[S5GitRefRecord, ...] = Field(min_length=3, max_length=3)
    pre_freeze_probe_used_credentials: Literal[False] = False
    pre_freeze_repository_aggregate_numeric_context_observed: Literal[True] = True
    incidental_repository_numeric_context_categories: tuple[str, ...] = Field(
        min_length=6, max_length=6
    )
    incidental_repository_exact_numeric_values_persisted: Literal[False] = False
    all_historical_repository_and_btc_outcomes_declared_outcome_aware: Literal[True] = True
    historical_results_cannot_qualify_s5: Literal[True] = True
    source_metadata_pages_inspected: tuple[str, ...] = Field(min_length=10)
    repository_commit_history_records_parsed: Literal[0] = 0
    github_historical_api_records_parsed: Literal[0] = 0
    repository_history_payload_bytes_acquired: Literal[0] = 0
    btc_market_numeric_fields_inspected: tuple[str, ...] = ()
    exact_parameters_defined: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S5_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY"] = S5_CHARTER_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_PROTOCOL_ONLY"
    ] = S5_NEXT_AUTHORIZATION
    authorizes_public_git_metadata_requests: Literal[True] = True
    authorizes_github_api_metadata_requests: Literal[True] = True
    authorizes_repository_clone: Literal[False] = False
    authorizes_repository_history_access: Literal[False] = False
    authorizes_github_historical_payload: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_historical_screen_access: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_pine_deployment: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=14)
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("builder_contract_hash", "charter_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_charter(self) -> S5BitcoinCoreDevelopmentCharter:
        paths = tuple(item.path for item in self.predecessor_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 predecessor bindings must be unique and sorted")
        source_ids = tuple(item.source_id for item in self.research_sources)
        if source_ids != tuple(sorted(set(source_ids))):
            raise ValueError("S5 research sources must be unique and sorted")
        refs = tuple(item.ref for item in self.pre_freeze_git_ref_records)
        if refs != tuple(sorted(set(refs))):
            raise ValueError("S5 pre-freeze Git refs must be unique and sorted")
        roles = tuple(item.role for item in self.partitions)
        if roles != (
            "SOURCE_ONLY_PRE_BINANCE_SPOT_HISTORY",
            "DEVELOPMENT",
            "OUTCOME_AWARE_SCREEN",
            "PROSPECTIVE_VALIDATION",
            "FUTURE_HOLDOUT",
            "FORWARD",
        ):
            raise ValueError("S5 partition roles changed")
        for previous, current in zip(self.partitions, self.partitions[1:], strict=False):
            if previous.end != current.start:
                raise ValueError("S5 partitions must be contiguous")
        if self.partitions[-1].end is not None:
            raise ValueError("S5 forward partition must remain open-ended")
        if self.rejected_candidate_families != tuple(sorted(set(self.rejected_candidate_families))):
            raise ValueError("S5 rejected candidate families changed")
        if self.incidental_repository_numeric_context_categories != tuple(
            sorted(set(self.incidental_repository_numeric_context_categories))
        ):
            raise ValueError("S5 incidental repository context changed")
        if any(
            (
                self.btc_market_numeric_fields_inspected,
                self.exact_parameters_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("S5 charter cannot inspect outcomes or define parameters")
        if any(
            (
                self.authorizes_repository_clone,
                self.authorizes_repository_history_access,
                self.authorizes_github_historical_payload,
                self.authorizes_market_value_access,
                self.authorizes_parameter_definition,
                self.authorizes_return_testing,
                self.authorizes_historical_screen_access,
                self.authorizes_validation_access,
                self.authorizes_holdout_access,
                self.authorizes_pine_deployment,
                self.authorizes_paper,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("S5 charter cannot grant payload, outcome, or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected:
            raise ValueError("S5 charter evidence hash changed")
        return self


class S5BitcoinCoreDevelopmentCharterAudit(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-development-charter-audit-v1"] = (
        "aurex-s5-bitcoin-core-development-charter-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-development-charter-audit-v1"] = (
        "s5-bitcoin-core-development-charter-audit-v1"
    )
    audited_at: datetime
    charter_path: Literal["data/evidence/s5_bitcoin_core_development_charter_v1.json"] = (
        "data/evidence/s5_bitcoin_core_development_charter_v1.json"
    )
    charter_file_sha256: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    predecessor_binding_count: Literal[28] = 28
    research_source_count: Literal[10] = 10
    partition_count: Literal[6] = 6
    pre_freeze_public_git_probe_request_count: Literal[1] = 1
    pre_freeze_git_ref_record_count: Literal[3] = 3
    repository_commit_history_records_parsed: Literal[0] = 0
    github_historical_api_records_parsed: Literal[0] = 0
    repository_history_payload_bytes_acquired: Literal[0] = 0
    btc_market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_CHARTER_RECONSTRUCTED_NO_HISTORY_OR_MARKET_OUTCOMES"] = (
        "PASS_S5_CHARTER_RECONSTRUCTED_NO_HISTORY_OR_MARKET_OUTCOMES"
    )
    next_authorization: Literal[
        "AUTHORIZE_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_PROTOCOL_ONLY"
    ] = S5_NEXT_AUTHORIZATION
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "charter_file_sha256",
        "charter_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5BitcoinCoreDevelopmentCharterAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 charter audit hash changed")
        return self


def audit_s5_charter(charter: S5BitcoinCoreDevelopmentCharter) -> bool:
    try:
        S5BitcoinCoreDevelopmentCharter.model_validate(charter.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s5_charter_audit(audit: S5BitcoinCoreDevelopmentCharterAudit) -> bool:
    try:
        S5BitcoinCoreDevelopmentCharterAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True
