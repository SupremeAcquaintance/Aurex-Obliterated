from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_LINEAGE_SCHEMA_VERSION = "aurex-s1-successor-lineage-ledger-v1"
S1_LINEAGE_AUDIT_SCHEMA_VERSION = "aurex-s1-successor-lineage-audit-v1"
S1_CHARTER_SCHEMA_VERSION = "aurex-s1-macro-financial-conditions-charter-v1"
S1_CHARTER_AUDIT_SCHEMA_VERSION = (
    "aurex-s1-macro-financial-conditions-charter-audit-v1"
)
S1_MECHANISM_ID = "S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE"
S1_CHARTER_DECISION = "FREEZE_S1_FOR_METADATA_AND_REVISION_FEASIBILITY_ONLY"
S1_NEXT_AUTHORIZATION = "AUTHORIZE_S1_METADATA_ONLY_NFCI_VINTAGE_FEASIBILITY"


class S1SourceBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S1LineageRecord(BaseModel):
    lineage_id: str = Field(min_length=1)
    mechanism_families: tuple[str, ...] = Field(min_length=1)
    terminal_decision: str = Field(min_length=1)
    terminal_stage: Literal[
        "OUTCOME_REJECTED",
        "SOURCE_REJECTED",
        "FEASIBILITY_REJECTED",
        "MIXED_RETIRED_SET",
    ]
    source_bindings: tuple[S1SourceBinding, ...] = Field(min_length=1)
    outcomes_opened: bool
    reusable_for_s1_selection: Literal[False] = False
    successor_policy: Literal[
        "RETIRED_NO_RESCUE",
        "CLOSED_COUNTS_FOR_MULTIPLICITY",
    ]
    reason: str = Field(min_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_record(self) -> S1LineageRecord:
        if tuple(sorted(set(self.mechanism_families))) != self.mechanism_families:
            raise ValueError("S1 mechanism families must be unique and sorted")
        paths = tuple(item.path for item in self.source_bindings)
        if tuple(sorted(set(paths))) != paths:
            raise ValueError("S1 source bindings must be unique and sorted")
        return self


class S1SuccessorLineageLedger(BaseModel):
    schema_version: Literal["aurex-s1-successor-lineage-ledger-v1"] = (
        S1_LINEAGE_SCHEMA_VERSION
    )
    ledger_id: Literal["s1-successor-lineage-ledger-v1"] = (
        "s1-successor-lineage-ledger-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    records: tuple[S1LineageRecord, ...] = Field(min_length=1)
    lineage_count: Literal[8] = 8
    source_binding_count: Literal[10] = 10
    selected_successor_count: Literal[0] = 0
    new_market_numeric_fields_inspected: tuple[str, ...] = ()
    new_return_metrics_calculated: tuple[str, ...] = ()
    authorizes_market_data_import: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    decision: Literal["CLOSE_PRE_S1_LINEAGES_AUTHORIZE_NEW_CHARTER_ONLY"] = (
        "CLOSE_PRE_S1_LINEAGES_AUTHORIZE_NEW_CHARTER_ONLY"
    )
    ledger_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("builder_contract_hash", "ledger_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_ledger(self) -> S1SuccessorLineageLedger:
        ids = tuple(item.lineage_id for item in self.records)
        if tuple(sorted(set(ids))) != ids or len(ids) != self.lineage_count:
            raise ValueError("S1 lineages must be unique, sorted, and complete")
        binding_count = sum(len(item.source_bindings) for item in self.records)
        if binding_count != self.source_binding_count:
            raise ValueError("S1 source binding count changed")
        if any(item.reusable_for_s1_selection for item in self.records):
            raise ValueError("A closed lineage cannot be reusable for S1 selection")
        if self.new_market_numeric_fields_inspected or self.new_return_metrics_calculated:
            raise ValueError("The S1 lineage ledger cannot inspect new outcomes")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"ledger_evidence_hash"})
        )
        if self.ledger_evidence_hash != expected:
            raise ValueError("S1 lineage ledger evidence hash changed")
        return self


class S1SuccessorLineageAudit(BaseModel):
    schema_version: Literal["aurex-s1-successor-lineage-audit-v1"] = (
        S1_LINEAGE_AUDIT_SCHEMA_VERSION
    )
    audit_id: Literal["s1-successor-lineage-audit-v1"] = (
        "s1-successor-lineage-audit-v1"
    )
    audited_at: datetime
    ledger_path: Literal[
        "data/evidence/s1_successor_lineage_ledger_v1.json"
    ] = "data/evidence/s1_successor_lineage_ledger_v1.json"
    ledger_file_sha256: str
    ledger_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    lineage_count: Literal[8] = 8
    source_binding_count: Literal[10] = 10
    new_market_numeric_fields_inspected: tuple[str, ...] = ()
    new_return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal["PASS_S1_LINEAGE_RECONSTRUCTED_NO_AUTHORITY"] = (
        "PASS_S1_LINEAGE_RECONSTRUCTED_NO_AUTHORITY"
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "ledger_file_sha256",
        "ledger_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1SuccessorLineageAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 lineage audit evidence hash changed")
        return self


class S1ResearchSource(BaseModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors_or_publisher: tuple[str, ...] = Field(min_length=1)
    publication_or_revision_date: str | None
    accessed_at: datetime
    source_kind: Literal[
        "OFFICIAL_DATA_DOCUMENTATION",
        "OFFICIAL_METHOD_DOCUMENTATION",
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


class S1OperatorScope(BaseModel):
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


class S1Partition(BaseModel):
    role: Literal[
        "DEVELOPMENT",
        "HISTORICAL_VALIDATION",
        "CONTAMINATION_WASHOUT",
        "FUTURE_HOLDOUT",
        "FORWARD",
    ]
    start: datetime
    end: datetime | None
    outcome_access_permitted: Literal[False] = False
    state: Literal[
        "SEALED_PENDING_SOURCE_FEASIBILITY",
        "EXCLUDED_PRIOR_OUTCOME_AWARENESS",
        "LOCKED_FUTURE",
    ]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("start", "end")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_partition(self) -> S1Partition:
        if self.end is not None and self.end <= self.start:
            raise ValueError("S1 partition end must be later than start")
        return self


class S1MacroFinancialConditionsCharter(BaseModel):
    schema_version: Literal[
        "aurex-s1-macro-financial-conditions-charter-v1"
    ] = S1_CHARTER_SCHEMA_VERSION
    charter_id: Literal["s1-macro-financial-conditions-charter-v1"] = (
        "s1-macro-financial-conditions-charter-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_CHARTER_ONLY_NO_OUTCOMES"] = (
        "FROZEN_CHARTER_ONLY_NO_OUTCOMES"
    )
    builder_contract_hash: str
    predecessor_bindings: tuple[S1SourceBinding, ...] = Field(min_length=1)
    research_sources: tuple[S1ResearchSource, ...] = Field(min_length=1)
    operator_scope: S1OperatorScope
    mechanism_id: Literal["S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE"] = S1_MECHANISM_ID
    economic_actor: Literal[
        "GLOBAL_RISK_BEARING_CAPITAL_RESPONDING_TO_US_FINANCIAL_CONDITIONS"
    ] = "GLOBAL_RISK_BEARING_CAPITAL_RESPONDING_TO_US_FINANCIAL_CONDITIONS"
    ex_ante_hypothesis: str = Field(min_length=50)
    ex_ante_direction: Literal["EASING_CONDITIONS_LONG_TIGHTENING_CONDITIONS_CASH"] = (
        "EASING_CONDITIONS_LONG_TIGHTENING_CONDITIONS_CASH"
    )
    causal_observation_policy: tuple[str, ...] = Field(min_length=1)
    exact_source_requirements: tuple[str, ...] = Field(min_length=1)
    independence_exclusions: tuple[str, ...] = Field(min_length=1)
    feasibility_gates: tuple[str, ...] = Field(min_length=1)
    partitions: tuple[S1Partition, ...] = Field(min_length=1)
    proposal_budget: Literal[1] = 1
    selected_mechanism_count: Literal[1] = 1
    familywise_predecessor_count: Literal[8] = 8
    market_numeric_fields_inspected: tuple[str, ...] = ()
    exact_parameters_defined: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "FREEZE_S1_FOR_METADATA_AND_REVISION_FEASIBILITY_ONLY"
    ] = S1_CHARTER_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S1_METADATA_ONLY_NFCI_VINTAGE_FEASIBILITY"
    ] = S1_NEXT_AUTHORIZATION
    authorizes_source_metadata_requests: Literal[True] = True
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
    def validate_charter(self) -> S1MacroFinancialConditionsCharter:
        source_ids = tuple(item.source_id for item in self.research_sources)
        if tuple(sorted(set(source_ids))) != source_ids:
            raise ValueError("S1 research sources must be unique and sorted")
        roles = tuple(item.role for item in self.partitions)
        if roles != (
            "DEVELOPMENT",
            "HISTORICAL_VALIDATION",
            "CONTAMINATION_WASHOUT",
            "FUTURE_HOLDOUT",
            "FORWARD",
        ):
            raise ValueError("S1 partition roles changed")
        for previous, current in zip(self.partitions, self.partitions[1:], strict=False):
            if previous.end != current.start:
                raise ValueError("S1 partitions must be contiguous")
        if self.partitions[-1].end is not None:
            raise ValueError("The S1 forward partition must remain open-ended")
        if any(
            (
                self.market_numeric_fields_inspected,
                self.exact_parameters_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("The S1 charter cannot inspect outcomes or define parameters")
        if any(
            (
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
            raise ValueError("The S1 charter cannot grant outcome or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"charter_evidence_hash"})
        )
        if self.charter_evidence_hash != expected:
            raise ValueError("S1 charter evidence hash changed")
        return self


class S1MacroFinancialConditionsCharterAudit(BaseModel):
    schema_version: Literal[
        "aurex-s1-macro-financial-conditions-charter-audit-v1"
    ] = S1_CHARTER_AUDIT_SCHEMA_VERSION
    audit_id: Literal["s1-macro-financial-conditions-charter-audit-v1"] = (
        "s1-macro-financial-conditions-charter-audit-v1"
    )
    audited_at: datetime
    charter_path: Literal[
        "data/evidence/s1_macro_financial_conditions_charter_v1.json"
    ] = "data/evidence/s1_macro_financial_conditions_charter_v1.json"
    charter_file_sha256: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    predecessor_binding_count: Literal[5] = 5
    research_source_count: Literal[5] = 5
    partition_count: Literal[5] = 5
    market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal["PASS_S1_CHARTER_RECONSTRUCTED_NO_OUTCOMES"] = (
        "PASS_S1_CHARTER_RECONSTRUCTED_NO_OUTCOMES"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_METADATA_ONLY_NFCI_VINTAGE_FEASIBILITY"
    ] = S1_NEXT_AUTHORIZATION
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
    def validate_audit(self) -> S1MacroFinancialConditionsCharterAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 charter audit evidence hash changed")
        return self


def audit_s1_lineage(ledger: S1SuccessorLineageLedger) -> bool:
    return ledger.ledger_evidence_hash == universe_evidence_hash(
        ledger.model_dump(exclude={"ledger_evidence_hash"})
    )


def audit_s1_lineage_audit(audit: S1SuccessorLineageAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )


def audit_s1_charter(charter: S1MacroFinancialConditionsCharter) -> bool:
    return charter.charter_evidence_hash == universe_evidence_hash(
        charter.model_dump(exclude={"charter_evidence_hash"})
    )


def audit_s1_charter_audit(
    audit: S1MacroFinancialConditionsCharterAudit,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
