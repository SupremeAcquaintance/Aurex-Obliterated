from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_1_OUTCOME_EXECUTION_NEXT = "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_EXECUTION"
S1_1_OUTCOME_PASS = "PASS_S1_1_DEVELOPMENT_OUTCOME"
S1_1_OUTCOME_STOP = "STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED"


class S11IntervalOutcome(BaseModel):
    candidate_id: str
    interval_sequence: int = Field(ge=1, le=276)
    feature_sequence: int = Field(ge=5, le=280)
    target_date: date
    next_target_date: date
    selected_open_time_ms: int = Field(ge=1)
    next_selected_open_time_ms: int = Field(ge=1)
    open_price: str
    next_open_price: str
    desired_position: int = Field(ge=0, le=1)
    prior_position: int = Field(ge=0, le=1)
    entry_fill: bool
    terminal_liquidation_fill: bool
    fill_count: int = Field(ge=0, le=2)
    gross_interval_return: str
    base_equity_before: str
    base_equity_after: str
    base_interval_return: str
    base_interval_pnl_usd: str
    stress_equity_before: str
    stress_equity_after: str
    stress_interval_return: str
    stress_interval_pnl_usd: str
    feature_row_evidence_hash: str
    current_price_row_evidence_hash: str
    next_price_row_evidence_hash: str
    interval_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "feature_row_evidence_hash",
        "current_price_row_evidence_hash",
        "next_price_row_evidence_hash",
        "interval_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_interval(self) -> S11IntervalOutcome:
        if self.next_target_date <= self.target_date:
            raise ValueError("S1.1 interval dates are not increasing")
        if self.next_selected_open_time_ms <= self.selected_open_time_ms:
            raise ValueError("S1.1 interval timestamps are not increasing")
        if self.fill_count != int(self.entry_fill) + int(
            self.terminal_liquidation_fill
        ):
            raise ValueError("S1.1 interval fill count changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"interval_evidence_hash"})
        )
        if self.interval_evidence_hash != expected:
            raise ValueError("S1.1 interval evidence hash changed")
        return self


class S11CandidateOutcome(BaseModel):
    candidate_id: str
    role: Literal["PRIMARY_ELIGIBILITY", "DIAGNOSTIC_ONLY"]
    may_be_promoted: bool
    interval_count: Literal[276] = 276
    position_transition_count: int = Field(ge=0, le=277)
    long_interval_count: int = Field(ge=0, le=276)
    long_exposure_fraction: str
    base_final_equity_usd: str
    base_net_total_return: str
    base_profit_factor: str
    base_maximum_drawdown: str
    stress_final_equity_usd: str
    stress_net_total_return: str
    stress_profit_factor: str
    stress_maximum_drawdown: str
    annual_base_returns: dict[int, str]
    positive_full_calendar_year_count: int = Field(ge=0, le=5)
    stress_bootstrap_lower_mean_weekly_return: str | None = None
    interval_manifest_evidence_hash: str
    outcome_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("interval_manifest_evidence_hash", "outcome_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> S11CandidateOutcome:
        if self.role == "PRIMARY_ELIGIBILITY" and (
            not self.may_be_promoted
            or self.stress_bootstrap_lower_mean_weekly_return is None
        ):
            raise ValueError("S1.1 primary outcome is incomplete")
        if self.role == "DIAGNOSTIC_ONLY" and self.may_be_promoted:
            raise ValueError("S1.1 diagnostic cannot be promotable")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"outcome_evidence_hash"})
        )
        if self.outcome_evidence_hash != expected:
            raise ValueError("S1.1 candidate outcome hash changed")
        return self


class S11DevelopmentGateResult(BaseModel):
    gate_id: str
    operator: Literal["EQ", "GE", "LE", "GT"]
    threshold: str
    observed: str
    status: Literal["PASS", "FAIL"]
    reason: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class S11DevelopmentOutcomeExecutionContract(BaseModel):
    schema_version: Literal["aurex-s1-1-development-outcome-execution-contract-v1"] = (
        "aurex-s1-1-development-outcome-execution-contract-v1"
    )
    contract_id: Literal["s1-1-development-outcome-execution-contract-v1"] = (
        "s1-1-development-outcome-execution-contract-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=10)
    feature_dataset_file_sha256: str
    price_dataset_file_sha256: str
    output_paths_absent: Literal[True] = True
    authorizes_one_development_outcome_execution: Literal[True] = True
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_diagnostic_promotion: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_EXECUTION"
    ] = S1_1_OUTCOME_EXECUTION_NEXT
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "feature_dataset_file_sha256",
        "price_dataset_file_sha256",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S11DevelopmentOutcomeExecutionContract:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S1.1 outcome execution contract hash changed")
        return self


class S11DevelopmentOutcomeExecutionAudit(BaseModel):
    schema_version: Literal["aurex-s1-1-development-outcome-execution-audit-v1"] = (
        "aurex-s1-1-development-outcome-execution-audit-v1"
    )
    audit_id: Literal["s1-1-development-outcome-execution-audit-v1"] = (
        "s1-1-development-outcome-execution-audit-v1"
    )
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=10)
    reconstructed_exactly: Literal[True] = True
    feature_values_parsed: Literal[0] = 0
    price_values_parsed: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    decision: Literal[
        "PASS_S1_1_DEVELOPMENT_OUTCOME_EXECUTION_CONTRACT_RECONSTRUCTED"
    ] = "PASS_S1_1_DEVELOPMENT_OUTCOME_EXECUTION_CONTRACT_RECONSTRUCTED"
    next_authorization: Literal[
        "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_EXECUTION"
    ] = S1_1_OUTCOME_EXECUTION_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "protocol_evidence_hash",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S11DevelopmentOutcomeExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1.1 outcome execution audit hash changed")
        return self


class S11DevelopmentOutcomeResult(BaseModel):
    schema_version: Literal["aurex-s1-1-development-outcome-result-v1"] = (
        "aurex-s1-1-development-outcome-result-v1"
    )
    result_id: Literal["s1-1-development-outcome-result-v1"] = (
        "s1-1-development-outcome-result-v1"
    )
    completed_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    feature_dataset_file_sha256: str
    price_dataset_file_sha256: str
    outcome_ledger_path: str
    outcome_ledger_file_sha256: str
    outcome_ledger_bytes: int = Field(ge=1)
    outcome_ledger_row_count: Literal[1104] = 1104
    candidate_outcomes: tuple[S11CandidateOutcome, ...] = Field(
        min_length=4,
        max_length=4,
    )
    primary_gate_results: tuple[S11DevelopmentGateResult, ...] = Field(
        min_length=12,
        max_length=12,
    )
    passed_primary_gate_count: int = Field(ge=0, le=12)
    failed_primary_gate_count: int = Field(ge=0, le=12)
    diagnostic_promotion_count: Literal[0] = 0
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S1_1_DEVELOPMENT_OUTCOME",
        "STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_1_VALIDATION_PROTOCOL_ONLY",
        "NONE_S1_1_DEVELOPMENT_OUTCOME_FAILED",
    ]
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("completed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "runner_contract_hash",
        "feature_dataset_file_sha256",
        "price_dataset_file_sha256",
        "outcome_ledger_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S11DevelopmentOutcomeResult:
        if self.passed_primary_gate_count != sum(
            item.status == "PASS" for item in self.primary_gate_results
        ):
            raise ValueError("S1.1 passed gate count changed")
        if self.failed_primary_gate_count != sum(
            item.status == "FAIL" for item in self.primary_gate_results
        ):
            raise ValueError("S1.1 failed gate count changed")
        primary = [
            item for item in self.candidate_outcomes if item.role == "PRIMARY_ELIGIBILITY"
        ]
        if len(primary) != 1:
            raise ValueError("S1.1 result must contain one primary")
        passed = self.decision == S1_1_OUTCOME_PASS
        if passed != (self.failed_primary_gate_count == 0):
            raise ValueError("S1.1 outcome decision does not match primary gates")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1.1 development outcome result hash changed")
        return self
