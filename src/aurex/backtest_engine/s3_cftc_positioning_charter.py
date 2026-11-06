from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S3_MECHANISM_ID = "S3-CFTC-LEVERAGED-MONEY-POSITIONING-SPOT"
S3_CHARTER_DECISION = "FREEZE_S3_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY"
S3_NEXT_AUTHORIZATION = (
    "AUTHORIZE_S3_CFTC_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY"
)


class S3SourceBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S3ResearchSource(BaseModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors_or_publisher: tuple[str, ...] = Field(min_length=1)
    publication_or_revision_date: str | None
    accessed_at: datetime
    source_kind: Literal["OFFICIAL_DATA_DOCUMENTATION", "PEER_REVIEWED_ARTICLE"]
    url: str = Field(min_length=10)
    supported_claims: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    does_not_prove_edge: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("accessed_at")
    @classmethod
    def normalize_accessed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)


class S3OperatorScope(BaseModel):
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
    futures_trading_authority: Literal[False] = False
    production_authority: Literal[False] = False
    live_authority: Literal[False] = False
    real_capital: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class S3Partition(BaseModel):
    role: Literal[
        "PUBLISHED_STUDY_CONTAMINATED_REFERENCE",
        "DEVELOPMENT",
        "OUTCOME_AWARE_HISTORICAL_SCREEN",
        "PROSPECTIVE_VALIDATION",
        "FUTURE_HOLDOUT",
        "FORWARD",
    ]
    start: datetime
    end: datetime | None
    state: Literal[
        "PUBLISHED_OUTCOME_CONTAMINATED_NONQUALIFYING",
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
    def validate_partition(self) -> S3Partition:
        if self.end is not None and self.end <= self.start:
            raise ValueError("S3 partition end must be later than start")
        return self


class S3CftcPositioningCharter(BaseModel):
    schema_version: Literal["aurex-s3-cftc-positioning-charter-v1"] = (
        "aurex-s3-cftc-positioning-charter-v1"
    )
    charter_id: Literal["s3-cftc-positioning-charter-v1"] = (
        "s3-cftc-positioning-charter-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_CHARTER_ONLY_NO_POSITION_VALUES_OR_OUTCOMES"] = (
        "FROZEN_CHARTER_ONLY_NO_POSITION_VALUES_OR_OUTCOMES"
    )
    builder_contract_hash: str
    predecessor_bindings: tuple[S3SourceBinding, ...] = Field(min_length=12, max_length=12)
    research_sources: tuple[S3ResearchSource, ...] = Field(min_length=8, max_length=8)
    operator_scope: S3OperatorScope
    mechanism_id: Literal["S3-CFTC-LEVERAGED-MONEY-POSITIONING-SPOT"] = S3_MECHANISM_ID
    mechanism_family: Literal[
        "REGULATED_BITCOIN_FUTURES_LEVERAGED_MONEY_POSITION_CHANGE"
    ] = "REGULATED_BITCOIN_FUTURES_LEVERAGED_MONEY_POSITION_CHANGE"
    economic_actor: Literal[
        "CFTC_REPORTABLE_LEVERAGED_FUNDS_IN_CME_BITCOIN_FUTURES"
    ] = "CFTC_REPORTABLE_LEVERAGED_FUNDS_IN_CME_BITCOIN_FUTURES"
    ex_ante_hypothesis: str = Field(min_length=100)
    ex_ante_direction: Literal[
        "WEEK_OVER_WEEK_LEVERAGED_MONEY_NET_POSITION_INCREASE_LONG_ELSE_CASH"
    ] = "WEEK_OVER_WEEK_LEVERAGED_MONEY_NET_POSITION_INCREASE_LONG_ELSE_CASH"
    source_authority: Literal["UNITED_STATES_CFTC"] = "UNITED_STATES_CFTC"
    report_family: Literal["TRADERS_IN_FINANCIAL_FUTURES_FUTURES_ONLY"] = (
        "TRADERS_IN_FINANCIAL_FUTURES_FUTURES_ONLY"
    )
    cftc_contract_market_code: Literal["133741"] = "133741"
    cftc_market_identity: Literal["BITCOIN_CHICAGO_MERCANTILE_EXCHANGE"] = (
        "BITCOIN_CHICAGO_MERCANTILE_EXCHANGE"
    )
    prospective_signal_frequency: Literal["WEEKLY"] = "WEEKLY"
    prospective_measurement_families: tuple[str, ...] = (
        "LEVERAGED_MONEY_LONG_CONTRACTS",
        "LEVERAGED_MONEY_SHORT_CONTRACTS",
        "LEVERAGED_MONEY_NET_POSITION",
        "WEEK_OVER_WEEK_NET_POSITION_CHANGE",
    )
    causal_observation_policy: tuple[str, ...] = Field(min_length=8)
    exact_source_requirements: tuple[str, ...] = Field(min_length=8)
    independence_exclusions: tuple[str, ...] = Field(min_length=10)
    feasibility_gates: tuple[str, ...] = Field(min_length=12, max_length=12)
    partitions: tuple[S3Partition, ...] = Field(min_length=6, max_length=6)
    proposal_budget: Literal[1] = 1
    selected_mechanism_count: Literal[1] = 1
    familywise_predecessor_count: Literal[10] = 10
    published_rule_outcome_awareness_declared: Literal[True] = True
    published_study_sample: Literal["2018-01_THROUGH_2021-07"] = (
        "2018-01_THROUGH_2021-07"
    )
    published_study_rule_overlap: Literal[
        "LEVERAGED_MONEY_NET_POSITION_CHANGE_DIRECTION"
    ] = "LEVERAGED_MONEY_NET_POSITION_CHANGE_DIRECTION"
    published_study_results_cannot_qualify_s3: Literal[True] = True
    source_metadata_pages_inspected: tuple[str, ...] = Field(min_length=6)
    cftc_position_values_inspected: tuple[str, ...] = ()
    btc_market_numeric_fields_inspected: tuple[str, ...] = ()
    exact_parameters_defined: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "FREEZE_S3_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY"
    ] = S3_CHARTER_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S3_CFTC_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY"
    ] = S3_NEXT_AUTHORIZATION
    authorizes_source_metadata_requests: Literal[True] = True
    authorizes_release_calendar_metadata_requests: Literal[True] = True
    authorizes_cftc_position_value_access: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_payload_acquisition: Literal[False] = False
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
    limitations: tuple[str, ...] = Field(min_length=8)
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
    def validate_charter(self) -> S3CftcPositioningCharter:
        paths = tuple(item.path for item in self.predecessor_bindings)
        if tuple(sorted(set(paths))) != paths:
            raise ValueError("S3 predecessor bindings must be unique and sorted")
        source_ids = tuple(item.source_id for item in self.research_sources)
        if tuple(sorted(set(source_ids))) != source_ids:
            raise ValueError("S3 research sources must be unique and sorted")
        roles = tuple(item.role for item in self.partitions)
        if roles != (
            "PUBLISHED_STUDY_CONTAMINATED_REFERENCE",
            "DEVELOPMENT",
            "OUTCOME_AWARE_HISTORICAL_SCREEN",
            "PROSPECTIVE_VALIDATION",
            "FUTURE_HOLDOUT",
            "FORWARD",
        ):
            raise ValueError("S3 partition roles changed")
        for previous, current in zip(self.partitions, self.partitions[1:], strict=False):
            if previous.end != current.start:
                raise ValueError("S3 partitions must be contiguous")
        if self.partitions[-1].end is not None:
            raise ValueError("S3 forward partition must remain open-ended")
        if any(
            (
                self.cftc_position_values_inspected,
                self.btc_market_numeric_fields_inspected,
                self.exact_parameters_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("S3 charter cannot inspect values or define parameters")
        if any(
            (
                self.authorizes_cftc_position_value_access,
                self.authorizes_market_value_access,
                self.authorizes_payload_acquisition,
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
            raise ValueError("S3 charter cannot grant value, outcome, or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected:
            raise ValueError("S3 charter evidence hash changed")
        return self


class S3CftcPositioningCharterAudit(BaseModel):
    schema_version: Literal["aurex-s3-cftc-positioning-charter-audit-v1"] = (
        "aurex-s3-cftc-positioning-charter-audit-v1"
    )
    audit_id: Literal["s3-cftc-positioning-charter-audit-v1"] = (
        "s3-cftc-positioning-charter-audit-v1"
    )
    audited_at: datetime
    charter_path: Literal["data/evidence/s3_cftc_positioning_charter_v1.json"] = (
        "data/evidence/s3_cftc_positioning_charter_v1.json"
    )
    charter_file_sha256: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    predecessor_binding_count: Literal[12] = 12
    research_source_count: Literal[8] = 8
    partition_count: Literal[6] = 6
    cftc_position_values_inspected: tuple[str, ...] = ()
    btc_market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal["PASS_S3_CHARTER_RECONSTRUCTED_NO_VALUES_OR_OUTCOMES"] = (
        "PASS_S3_CHARTER_RECONSTRUCTED_NO_VALUES_OR_OUTCOMES"
    )
    next_authorization: Literal[
        "AUTHORIZE_S3_CFTC_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY"
    ] = S3_NEXT_AUTHORIZATION
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
    def validate_audit(self) -> S3CftcPositioningCharterAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S3 charter audit hash changed")
        return self


def audit_s3_charter(charter: S3CftcPositioningCharter) -> bool:
    try:
        S3CftcPositioningCharter.model_validate(charter.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s3_charter_audit(audit: S3CftcPositioningCharterAudit) -> bool:
    try:
        S3CftcPositioningCharterAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True
