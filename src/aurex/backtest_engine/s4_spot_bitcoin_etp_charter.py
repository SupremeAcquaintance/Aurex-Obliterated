from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S4_MECHANISM_ID = "S4-US-SPOT-BITCOIN-ETP-NET-CREATION-PRESSURE"
S4_CHARTER_DECISION = "FREEZE_S4_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY"
S4_NEXT_AUTHORIZATION = (
    "AUTHORIZE_S4_ETP_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY"
)


class S4SourceBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S4ResearchSource(BaseModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    publication_or_revision_date: str | None
    accessed_at: datetime
    source_kind: Literal[
        "OFFICIAL_REGULATOR",
        "OFFICIAL_ISSUER_DATA",
        "OFFICIAL_SEC_FILING",
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


class S4OperatorScope(BaseModel):
    execution_environment: Literal["BINANCE_SPOT_TESTNET"] = (
        "BINANCE_SPOT_TESTNET"
    )
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
    etp_trading_authority: Literal[False] = False
    production_authority: Literal[False] = False
    live_authority: Literal[False] = False
    real_capital: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class S4Partition(BaseModel):
    role: Literal[
        "PRE_ETP_NOT_APPLICABLE",
        "CASH_ONLY_DEVELOPMENT",
        "MIXED_REGIME_OUTCOME_AWARE_SCREEN",
        "PROSPECTIVE_VALIDATION",
        "FUTURE_HOLDOUT",
        "FORWARD",
    ]
    start: datetime
    end: datetime | None
    state: Literal[
        "NO_US_SPOT_BITCOIN_ETP_MECHANISM",
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
    def validate_partition(self) -> S4Partition:
        if self.end is not None and self.end <= self.start:
            raise ValueError("S4 partition end must be later than start")
        return self


class S4SpotBitcoinEtpCharter(BaseModel):
    schema_version: Literal["aurex-s4-spot-bitcoin-etp-charter-v1"] = (
        "aurex-s4-spot-bitcoin-etp-charter-v1"
    )
    charter_id: Literal["s4-spot-bitcoin-etp-charter-v1"] = (
        "s4-spot-bitcoin-etp-charter-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_CHARTER_ONLY_NO_ETP_VALUES_OR_OUTCOMES"] = (
        "FROZEN_CHARTER_ONLY_NO_ETP_VALUES_OR_OUTCOMES"
    )
    builder_contract_hash: str
    predecessor_bindings: tuple[S4SourceBinding, ...] = Field(
        min_length=20, max_length=20
    )
    research_sources: tuple[S4ResearchSource, ...] = Field(
        min_length=8, max_length=8
    )
    operator_scope: S4OperatorScope
    mechanism_id: Literal[
        "S4-US-SPOT-BITCOIN-ETP-NET-CREATION-PRESSURE"
    ] = S4_MECHANISM_ID
    mechanism_family: Literal[
        "REGULATED_US_SPOT_BITCOIN_ETP_PRIMARY_MARKET_CREATION_REDEMPTION"
    ] = "REGULATED_US_SPOT_BITCOIN_ETP_PRIMARY_MARKET_CREATION_REDEMPTION"
    economic_actor: Literal[
        "AUTHORIZED_PARTICIPANTS_SPONSORS_AND_REGULATED_ETP_ALLOCATORS"
    ] = "AUTHORIZED_PARTICIPANTS_SPONSORS_AND_REGULATED_ETP_ALLOCATORS"
    ex_ante_hypothesis: str = Field(min_length=120)
    ex_ante_direction: Literal[
        "POSITIVE_AGGREGATE_NET_CREATION_WITH_CROSS_FUND_BREADTH_LONG_ELSE_CASH"
    ] = "POSITIVE_AGGREGATE_NET_CREATION_WITH_CROSS_FUND_BREADTH_LONG_ELSE_CASH"
    source_authorities: tuple[
        Literal["UNITED_STATES_SEC", "OFFICIAL_ETP_ISSUERS"], ...
    ] = ("UNITED_STATES_SEC", "OFFICIAL_ETP_ISSUERS")
    prospective_signal_frequency: Literal["WEEKLY"] = "WEEKLY"
    universe_policy: Literal[
        "ALL_SEC_APPROVED_US_SPOT_BITCOIN_ETPS_FROM_EACH_FIRST_TRADING_DATE"
    ] = "ALL_SEC_APPROVED_US_SPOT_BITCOIN_ETPS_FROM_EACH_FIRST_TRADING_DATE"
    prospective_measurement_families: tuple[str, ...] = (
        "SHARES_OUTSTANDING_CHANGE",
        "BITCOIN_PER_SHARE",
        "ESTIMATED_NET_BITCOIN_CREATION_REDEMPTION",
        "CROSS_FUND_NET_CREATION_BREADTH",
        "CASH_VERSUS_IN_KIND_CREATION_REGIME",
    )
    cash_only_regime_start: datetime
    sec_in_kind_authorization_date: datetime
    per_fund_in_kind_effective_date_required: Literal[True] = True
    known_regulatory_regime_change_declared: Literal[True] = True
    causal_observation_policy: tuple[str, ...] = Field(min_length=9)
    exact_source_requirements: tuple[str, ...] = Field(min_length=10)
    independence_exclusions: tuple[str, ...] = Field(min_length=12)
    feasibility_gates: tuple[str, ...] = Field(min_length=14, max_length=14)
    partitions: tuple[S4Partition, ...] = Field(min_length=6, max_length=6)
    rejected_candidate_families: tuple[str, ...] = Field(min_length=3, max_length=3)
    proposal_budget: Literal[1] = 1
    selected_mechanism_count: Literal[1] = 1
    familywise_predecessor_count: Literal[11] = 11
    all_historical_etp_outcomes_declared_outcome_aware: Literal[True] = True
    historical_etp_results_cannot_qualify_s4: Literal[True] = True
    source_metadata_pages_inspected: tuple[str, ...] = Field(min_length=8)
    incidental_source_numeric_fields_observed: tuple[str, ...] = Field(
        min_length=4, max_length=4
    )
    etp_time_series_rows_parsed: Literal[0] = 0
    etp_numeric_payloads_acquired: Literal[0] = 0
    btc_market_numeric_fields_inspected: tuple[str, ...] = ()
    exact_parameters_defined: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "FREEZE_S4_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY"
    ] = S4_CHARTER_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S4_ETP_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY"
    ] = S4_NEXT_AUTHORIZATION
    authorizes_source_metadata_requests: Literal[True] = True
    authorizes_sec_filing_metadata_requests: Literal[True] = True
    authorizes_etp_numeric_value_access: Literal[False] = False
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
    limitations: tuple[str, ...] = Field(min_length=10)
    charter_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at", "cash_only_regime_start", "sec_in_kind_authorization_date")
    @classmethod
    def normalize_dates(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("builder_contract_hash", "charter_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_charter(self) -> S4SpotBitcoinEtpCharter:
        paths = tuple(item.path for item in self.predecessor_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S4 predecessor bindings must be unique and sorted")
        source_ids = tuple(item.source_id for item in self.research_sources)
        if source_ids != tuple(sorted(set(source_ids))):
            raise ValueError("S4 research sources must be unique and sorted")
        roles = tuple(item.role for item in self.partitions)
        if roles != (
            "PRE_ETP_NOT_APPLICABLE",
            "CASH_ONLY_DEVELOPMENT",
            "MIXED_REGIME_OUTCOME_AWARE_SCREEN",
            "PROSPECTIVE_VALIDATION",
            "FUTURE_HOLDOUT",
            "FORWARD",
        ):
            raise ValueError("S4 partition roles changed")
        for previous, current in zip(self.partitions, self.partitions[1:], strict=False):
            if previous.end != current.start:
                raise ValueError("S4 partitions must be contiguous")
        if self.partitions[-1].end is not None:
            raise ValueError("S4 forward partition must remain open-ended")
        if self.cash_only_regime_start >= self.sec_in_kind_authorization_date:
            raise ValueError("S4 regulatory regime dates changed")
        if self.rejected_candidate_families != tuple(
            sorted(set(self.rejected_candidate_families))
        ):
            raise ValueError("S4 rejected candidate families changed")
        if self.incidental_source_numeric_fields_observed != tuple(
            sorted(set(self.incidental_source_numeric_fields_observed))
        ):
            raise ValueError("S4 incidental source field disclosure changed")
        if any(
            (
                self.btc_market_numeric_fields_inspected,
                self.exact_parameters_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("S4 charter cannot inspect values or define parameters")
        if any(
            (
                self.authorizes_etp_numeric_value_access,
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
            raise ValueError("S4 charter cannot grant value, outcome, or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected:
            raise ValueError("S4 charter evidence hash changed")
        return self


class S4SpotBitcoinEtpCharterAudit(BaseModel):
    schema_version: Literal["aurex-s4-spot-bitcoin-etp-charter-audit-v1"] = (
        "aurex-s4-spot-bitcoin-etp-charter-audit-v1"
    )
    audit_id: Literal["s4-spot-bitcoin-etp-charter-audit-v1"] = (
        "s4-spot-bitcoin-etp-charter-audit-v1"
    )
    audited_at: datetime
    charter_path: Literal["data/evidence/s4_spot_bitcoin_etp_charter_v1.json"] = (
        "data/evidence/s4_spot_bitcoin_etp_charter_v1.json"
    )
    charter_file_sha256: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    predecessor_binding_count: Literal[20] = 20
    research_source_count: Literal[8] = 8
    partition_count: Literal[6] = 6
    incidental_source_numeric_fields_observed: tuple[str, ...] = Field(
        min_length=4, max_length=4
    )
    etp_time_series_rows_parsed: Literal[0] = 0
    etp_numeric_payloads_acquired: Literal[0] = 0
    btc_market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S4_CHARTER_RECONSTRUCTED_NO_VALUES_OR_OUTCOMES"] = (
        "PASS_S4_CHARTER_RECONSTRUCTED_NO_VALUES_OR_OUTCOMES"
    )
    next_authorization: Literal[
        "AUTHORIZE_S4_ETP_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY"
    ] = S4_NEXT_AUTHORIZATION
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
    def validate_audit(self) -> S4SpotBitcoinEtpCharterAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S4 charter audit hash changed")
        return self


def audit_s4_charter(charter: S4SpotBitcoinEtpCharter) -> bool:
    try:
        S4SpotBitcoinEtpCharter.model_validate(charter.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s4_charter_audit(audit: S4SpotBitcoinEtpCharterAudit) -> bool:
    try:
        S4SpotBitcoinEtpCharterAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True
