from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_MECHANISM_ID = "S2-BTC-SETTLEMENT-DEMAND-BREADTH-SPOT"
S2_CHARTER_DECISION = "FREEZE_S2_FOR_SOURCE_AND_QUERY_FEASIBILITY_ONLY"
S2_NEXT_AUTHORIZATION = "AUTHORIZE_S2_BIGQUERY_METADATA_AND_QUERY_COST_FEASIBILITY_ONLY"


class S2SourceBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S2ResearchSource(BaseModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors_or_publisher: tuple[str, ...] = Field(min_length=1)
    publication_or_revision_date: str | None
    accessed_at: datetime
    source_kind: Literal[
        "OFFICIAL_DATA_DOCUMENTATION",
        "OFFICIAL_SOURCE_CODE",
        "PEER_REVIEWED_ARTICLE",
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


class S2OperatorScope(BaseModel):
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


class S2Partition(BaseModel):
    role: Literal[
        "DEVELOPMENT",
        "OUTCOME_AWARE_HISTORICAL_SCREEN",
        "PROSPECTIVE_VALIDATION",
        "FUTURE_HOLDOUT",
        "FORWARD",
    ]
    start: datetime
    end: datetime | None
    state: Literal[
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
    def validate_partition(self) -> S2Partition:
        if self.end is not None and self.end <= self.start:
            raise ValueError("S2 partition end must be later than start")
        return self


class S2OnchainSettlementCharter(BaseModel):
    schema_version: Literal["aurex-s2-onchain-settlement-charter-v1"] = (
        "aurex-s2-onchain-settlement-charter-v1"
    )
    charter_id: Literal["s2-onchain-settlement-charter-v1"] = (
        "s2-onchain-settlement-charter-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_CHARTER_ONLY_NO_OUTCOMES"] = (
        "FROZEN_CHARTER_ONLY_NO_OUTCOMES"
    )
    builder_contract_hash: str
    predecessor_bindings: tuple[S2SourceBinding, ...] = Field(min_length=8, max_length=8)
    research_sources: tuple[S2ResearchSource, ...] = Field(min_length=6, max_length=6)
    operator_scope: S2OperatorScope
    mechanism_id: Literal["S2-BTC-SETTLEMENT-DEMAND-BREADTH-SPOT"] = S2_MECHANISM_ID
    mechanism_family: Literal["BITCOIN_ONCHAIN_SETTLEMENT_DEMAND_BREADTH"] = (
        "BITCOIN_ONCHAIN_SETTLEMENT_DEMAND_BREADTH"
    )
    economic_actor: Literal[
        "BITCOIN_USERS_PAYING_FOR_CONFIRMED_ONCHAIN_SETTLEMENT"
    ] = "BITCOIN_USERS_PAYING_FOR_CONFIRMED_ONCHAIN_SETTLEMENT"
    ex_ante_hypothesis: str = Field(min_length=80)
    ex_ante_direction: Literal["BROADENING_SETTLEMENT_DEMAND_LONG_ELSE_CASH"] = (
        "BROADENING_SETTLEMENT_DEMAND_LONG_ELSE_CASH"
    )
    source_project: Literal["bigquery-public-data"] = "bigquery-public-data"
    source_dataset: Literal["crypto_bitcoin"] = "crypto_bitcoin"
    source_tables: tuple[str, ...] = ("blocks", "transactions")
    prospective_signal_frequency: Literal["WEEKLY"] = "WEEKLY"
    raw_measurement_families: tuple[str, ...] = (
        "CONFIRMED_NON_COINBASE_TRANSACTION_COUNT",
        "CONFIRMED_TRANSACTION_FEES_SATOSHIS",
        "CONFIRMED_SETTLEMENT_COUNT_AND_FEE_AGREEMENT",
    )
    causal_observation_policy: tuple[str, ...] = Field(min_length=1)
    exact_source_requirements: tuple[str, ...] = Field(min_length=1)
    independence_exclusions: tuple[str, ...] = Field(min_length=1)
    feasibility_gates: tuple[str, ...] = Field(min_length=1)
    partitions: tuple[S2Partition, ...] = Field(min_length=5, max_length=5)
    proposal_budget: Literal[1] = 1
    selected_mechanism_count: Literal[1] = 1
    familywise_predecessor_count: Literal[9] = 9
    prior_coin_metrics_catalog_metadata_request_count_declared: Literal[2] = 2
    prior_catalog_market_values_read_declared: Literal[0] = 0
    coin_metrics_community_data_permitted_as_trading_input: Literal[False] = False
    historical_target_outcome_awareness_declared: Literal[True] = True
    market_numeric_fields_inspected: tuple[str, ...] = ()
    blockchain_numeric_fields_inspected: tuple[str, ...] = ()
    exact_parameters_defined: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S2_FOR_SOURCE_AND_QUERY_FEASIBILITY_ONLY"] = (
        S2_CHARTER_DECISION
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_BIGQUERY_METADATA_AND_QUERY_COST_FEASIBILITY_ONLY"
    ] = S2_NEXT_AUTHORIZATION
    authorizes_source_metadata_requests: Literal[True] = True
    authorizes_bigquery_dry_runs: Literal[True] = True
    authorizes_bigquery_numeric_queries: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_payload_acquisition: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_pine_deployment: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=1)
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("builder_contract_hash", "charter_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_charter(self) -> S2OnchainSettlementCharter:
        paths = tuple(item.path for item in self.predecessor_bindings)
        if tuple(sorted(set(paths))) != paths:
            raise ValueError("S2 predecessor bindings must be unique and sorted")
        source_ids = tuple(item.source_id for item in self.research_sources)
        if tuple(sorted(set(source_ids))) != source_ids:
            raise ValueError("S2 research sources must be unique and sorted")
        roles = tuple(item.role for item in self.partitions)
        if roles != (
            "DEVELOPMENT",
            "OUTCOME_AWARE_HISTORICAL_SCREEN",
            "PROSPECTIVE_VALIDATION",
            "FUTURE_HOLDOUT",
            "FORWARD",
        ):
            raise ValueError("S2 partition roles changed")
        for previous, current in zip(self.partitions, self.partitions[1:], strict=False):
            if previous.end != current.start:
                raise ValueError("S2 partitions must be contiguous")
        if self.partitions[-1].end is not None:
            raise ValueError("S2 forward partition must remain open-ended")
        if any(
            (
                self.market_numeric_fields_inspected,
                self.blockchain_numeric_fields_inspected,
                self.exact_parameters_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("S2 charter cannot inspect values or define parameters")
        if any(
            (
                self.authorizes_bigquery_numeric_queries,
                self.authorizes_market_value_access,
                self.authorizes_payload_acquisition,
                self.authorizes_parameter_definition,
                self.authorizes_return_testing,
                self.authorizes_validation_access,
                self.authorizes_holdout_access,
                self.authorizes_pine_deployment,
                self.authorizes_paper,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("S2 charter cannot grant outcome or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected:
            raise ValueError("S2 charter evidence hash changed")
        return self


class S2OnchainSettlementCharterAudit(BaseModel):
    schema_version: Literal["aurex-s2-onchain-settlement-charter-audit-v1"] = (
        "aurex-s2-onchain-settlement-charter-audit-v1"
    )
    audit_id: Literal["s2-onchain-settlement-charter-audit-v1"] = (
        "s2-onchain-settlement-charter-audit-v1"
    )
    audited_at: datetime
    charter_path: Literal[
        "data/evidence/s2_onchain_settlement_charter_v1.json"
    ] = "data/evidence/s2_onchain_settlement_charter_v1.json"
    charter_file_sha256: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    predecessor_binding_count: Literal[8] = 8
    research_source_count: Literal[6] = 6
    partition_count: Literal[5] = 5
    market_numeric_fields_inspected: tuple[str, ...] = ()
    blockchain_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal["PASS_S2_CHARTER_RECONSTRUCTED_NO_OUTCOMES"] = (
        "PASS_S2_CHARTER_RECONSTRUCTED_NO_OUTCOMES"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_BIGQUERY_METADATA_AND_QUERY_COST_FEASIBILITY_ONLY"
    ] = S2_NEXT_AUTHORIZATION
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

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
    def validate_audit(self) -> S2OnchainSettlementCharterAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 charter audit hash changed")
        return self


def audit_s2_charter(charter: S2OnchainSettlementCharter) -> bool:
    try:
        S2OnchainSettlementCharter.model_validate(charter.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s2_charter_audit(audit: S2OnchainSettlementCharterAudit) -> bool:
    try:
        S2OnchainSettlementCharterAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True
