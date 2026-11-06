from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_FAILURE_ANALYSIS_IDS = (
    "PRIMARY_COST_DRAG",
    "BASE_DRAWDOWN_CHRONOLOGY",
    "STRESS_DRAWDOWN_CHRONOLOGY",
    "PRIMARY_EXPOSURE_EPISODES",
    "PRIMARY_STRESS_TAIL_CONCENTRATION",
    "PRIMARY_ANNUAL_INSTABILITY",
    "DIAGNOSTIC_POSITION_VECTOR_DUPLICATION",
)
S1_FAILURE_ANALYSIS_PROTOCOL_NEXT = (
    "AUTHORIZE_S1_POST_FAILURE_ANALYSIS_RUNNER_IMPLEMENTATION_ONLY"
)
S1_FAILURE_ANALYSIS_EXECUTION_NEXT = "AUTHORIZE_ONE_S1_POST_FAILURE_ANALYSIS"
S1_FAILURE_ANALYSIS_DECISION = "RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE"
S1_FAILURE_ANALYSIS_NEXT = "AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY"


class HashedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class S1PostFailureAnalysisProtocol(HashedModel):
    schema_version: Literal["aurex-s1-post-failure-analysis-protocol-v1"] = (
        "aurex-s1-post-failure-analysis-protocol-v1"
    )
    protocol_id: Literal["s1-post-failure-analysis-protocol-v1"] = (
        "s1-post-failure-analysis-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    outcome_result_file_sha256: str
    outcome_result_evidence_hash: str
    outcome_audit_file_sha256: str
    outcome_audit_evidence_hash: str
    outcome_ledger_path: Literal[
        "data/evidence/datasets/s1_1_development_outcome_ledger_v1.jsonl"
    ] = "data/evidence/datasets/s1_1_development_outcome_ledger_v1.jsonl"
    outcome_ledger_file_sha256: str
    outcome_ledger_row_count: Literal[1104] = 1104
    primary_candidate_id: Literal["S1-C1-CONSISTENT-EASING-PRIMARY"] = (
        "S1-C1-CONSISTENT-EASING-PRIMARY"
    )
    primary_interval_count: Literal[276] = 276
    diagnostic_candidate_count: Literal[3] = 3
    analysis_ids: tuple[str, ...] = S1_FAILURE_ANALYSIS_IDS
    top_tail_observation_count: Literal[5] = 5
    bottom_tail_observation_count: Literal[5] = 5
    drawdown_tie_policy: Literal["EARLIEST_PEAK_AND_EARLIEST_TROUGH"] = (
        "EARLIEST_PEAK_AND_EARLIEST_TROUGH"
    )
    drawdown_recovery_policy: Literal[
        "FIRST_POST_TROUGH_EQUITY_GTE_PRE_TROUGH_PEAK_ELSE_UNRECOVERED"
    ] = "FIRST_POST_TROUGH_EQUITY_GTE_PRE_TROUGH_PEAK_ELSE_UNRECOVERED"
    long_episode_policy: Literal["MAXIMAL_CONTIGUOUS_DESIRED_POSITION_ONE_RUN"] = (
        "MAXIMAL_CONTIGUOUS_DESIRED_POSITION_ONE_RUN"
    )
    tail_share_policy: Literal[
        "TOP_OR_BOTTOM_ABSOLUTE_PNL_SUM_DIV_CORRESPONDING_ALL_GAIN_OR_LOSS_SUM"
    ] = "TOP_OR_BOTTOM_ABSOLUTE_PNL_SUM_DIV_CORRESPONDING_ALL_GAIN_OR_LOSS_SUM"
    annual_assignment_policy: Literal["FROZEN_OUTCOME_INTERVAL_START_YEAR"] = (
        "FROZEN_OUTCOME_INTERVAL_START_YEAR"
    )
    arithmetic: Literal["PYTHON_DECIMAL_EXACT_SOURCE_TEXT"] = (
        "PYTHON_DECIMAL_EXACT_SOURCE_TEXT"
    )
    existing_development_outcome_values_available: Literal[True] = True
    analysis_metrics_calculated_during_protocol_freeze: Literal[0] = 0
    new_market_data_values_read: Literal[0] = 0
    new_candidate_definitions_created: Literal[0] = 0
    parameter_variants_permitted: Literal[0] = 0
    diagnostic_rescue_permitted: Literal[False] = False
    authorizes_runner_implementation: Literal[True] = True
    authorizes_analysis_execution_now: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_POST_FAILURE_ANALYSIS_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_FAILURE_ANALYSIS_PROTOCOL_NEXT
    protocol_evidence_hash: str

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "outcome_result_file_sha256",
        "outcome_result_evidence_hash",
        "outcome_audit_file_sha256",
        "outcome_audit_evidence_hash",
        "outcome_ledger_file_sha256",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1PostFailureAnalysisProtocol:
        if self.analysis_ids != S1_FAILURE_ANALYSIS_IDS:
            raise ValueError("S1 failure-analysis scope changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 failure-analysis protocol hash changed")
        return self


class S1PostFailureAnalysisProtocolAudit(HashedModel):
    schema_version: Literal["aurex-s1-post-failure-analysis-protocol-audit-v1"] = (
        "aurex-s1-post-failure-analysis-protocol-audit-v1"
    )
    audit_id: Literal["s1-post-failure-analysis-protocol-audit-v1"] = (
        "s1-post-failure-analysis-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    outcome_result_evidence_hash: str
    outcome_audit_evidence_hash: str
    outcome_ledger_file_sha256: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    analysis_metrics_calculated: Literal[0] = 0
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    decision: Literal["PASS_S1_POST_FAILURE_ANALYSIS_PROTOCOL_RECONSTRUCTED"] = (
        "PASS_S1_POST_FAILURE_ANALYSIS_PROTOCOL_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_POST_FAILURE_ANALYSIS_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_FAILURE_ANALYSIS_PROTOCOL_NEXT
    audit_evidence_hash: str

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "outcome_result_evidence_hash",
        "outcome_audit_evidence_hash",
        "outcome_ledger_file_sha256",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1PostFailureAnalysisProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 failure-analysis protocol audit hash changed")
        return self


class S1PostFailureAnalysisExecutionContract(HashedModel):
    schema_version: Literal["aurex-s1-post-failure-analysis-execution-contract-v1"] = (
        "aurex-s1-post-failure-analysis-execution-contract-v1"
    )
    contract_id: Literal["s1-post-failure-analysis-execution-contract-v1"] = (
        "s1-post-failure-analysis-execution-contract-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    outcome_result_file_sha256: str
    outcome_ledger_file_sha256: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=8)
    output_paths_absent: Literal[True] = True
    authorizes_one_analysis_execution: Literal[True] = True
    authorizes_parameter_variants: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal["AUTHORIZE_ONE_S1_POST_FAILURE_ANALYSIS"] = (
        S1_FAILURE_ANALYSIS_EXECUTION_NEXT
    )
    contract_evidence_hash: str

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
        "outcome_result_file_sha256",
        "outcome_ledger_file_sha256",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S1PostFailureAnalysisExecutionContract:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S1 failure-analysis execution contract hash changed")
        return self


class S1PostFailureAnalysisExecutionAudit(HashedModel):
    schema_version: Literal["aurex-s1-post-failure-analysis-execution-audit-v1"] = (
        "aurex-s1-post-failure-analysis-execution-audit-v1"
    )
    audit_id: Literal["s1-post-failure-analysis-execution-audit-v1"] = (
        "s1-post-failure-analysis-execution-audit-v1"
    )
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=8)
    reconstructed_exactly: Literal[True] = True
    analysis_values_calculated: Literal[0] = 0
    decision: Literal[
        "PASS_S1_POST_FAILURE_ANALYSIS_EXECUTION_CONTRACT_RECONSTRUCTED"
    ] = "PASS_S1_POST_FAILURE_ANALYSIS_EXECUTION_CONTRACT_RECONSTRUCTED"
    next_authorization: Literal["AUTHORIZE_ONE_S1_POST_FAILURE_ANALYSIS"] = (
        S1_FAILURE_ANALYSIS_EXECUTION_NEXT
    )
    audit_evidence_hash: str

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
    def validate_audit(self) -> S1PostFailureAnalysisExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 failure-analysis execution audit hash changed")
        return self


class S1CostDecomposition(HashedModel):
    charged_fill_count: int = Field(ge=0)
    gross_final_equity_usd: str
    gross_total_return: str
    base_final_equity_usd: str
    base_total_return: str
    base_cost_drag_usd: str
    base_cost_drag_return_points: str
    stress_final_equity_usd: str
    stress_total_return: str
    stress_cost_drag_usd: str
    stress_cost_drag_return_points: str
    base_to_stress_incremental_drag_usd: str
    stress_to_base_positive_return_retention_ratio: str | None


class S1DrawdownChronology(HashedModel):
    basis: Literal["BASE", "STRESS"]
    maximum_drawdown: str
    peak_equity_usd: str
    peak_date: date
    trough_equity_usd: str
    trough_date: date
    recovery_date: date | None
    recovered_before_development_end: bool
    terminal_equity_usd: str
    terminal_drawdown_from_peak: str


class S1ExposureEpisodeSummary(HashedModel):
    long_interval_count: int = Field(ge=0)
    long_episode_count: int = Field(ge=0)
    shortest_episode_intervals: int = Field(ge=0)
    longest_episode_intervals: int = Field(ge=0)
    mean_episode_intervals: str
    positive_long_interval_count: int = Field(ge=0)
    negative_long_interval_count: int = Field(ge=0)
    zero_long_interval_count: int = Field(ge=0)
    nonzero_long_interval_hit_rate: str | None


class S1TailConcentration(HashedModel):
    basis: Literal["STRESS"] = "STRESS"
    top_observation_count: Literal[5] = 5
    bottom_observation_count: Literal[5] = 5
    total_positive_pnl_usd: str
    total_negative_pnl_abs_usd: str
    top_five_positive_pnl_share: str
    bottom_five_negative_pnl_share: str
    top_interval_sequences: tuple[int, ...] = Field(min_length=5, max_length=5)
    bottom_interval_sequences: tuple[int, ...] = Field(min_length=5, max_length=5)


class S1PostFailureAnalysisResult(HashedModel):
    schema_version: Literal["aurex-s1-post-failure-analysis-result-v1"] = (
        "aurex-s1-post-failure-analysis-result-v1"
    )
    result_id: Literal["s1-post-failure-analysis-result-v1"] = (
        "s1-post-failure-analysis-result-v1"
    )
    completed_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    outcome_result_file_sha256: str
    outcome_result_evidence_hash: str
    outcome_ledger_file_sha256: str
    existing_development_interval_rows_read: Literal[1104] = 1104
    primary_interval_rows_analyzed: Literal[276] = 276
    analysis_ids: tuple[str, ...] = S1_FAILURE_ANALYSIS_IDS
    primary_failed_gate_ids: tuple[str, ...] = (
        "BASE_PROFIT_FACTOR",
        "BASE_MAXIMUM_DRAWDOWN",
        "STRESS_MAXIMUM_DRAWDOWN",
        "POSITIVE_FULL_CALENDAR_YEARS",
        "STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN",
    )
    cost_decomposition: S1CostDecomposition
    base_drawdown: S1DrawdownChronology
    stress_drawdown: S1DrawdownChronology
    exposure_episodes: S1ExposureEpisodeSummary
    stress_tail_concentration: S1TailConcentration
    primary_annual_base_returns: dict[str, str]
    diagnostic_unique_position_vector_count: int = Field(ge=1, le=3)
    diagnostic_duplicate_pairs: tuple[str, ...]
    primary_diagnostic_position_agreement: dict[str, str]
    empirical_findings: tuple[str, ...] = (
        "ECONOMIC_EDGE_NOT_DEMONSTRATED",
        "DRAWDOWN_RISK_UNACCEPTABLE",
        "TEMPORAL_ROBUSTNESS_FAILED",
        "DIAGNOSTIC_VARIANTS_NONPROMOTABLE",
    )
    new_market_data_values_read: Literal[0] = 0
    new_candidate_definitions_created: Literal[0] = 0
    parameter_variants_evaluated: Literal[0] = 0
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    diagnostic_promotion_count: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE"] = (
        S1_FAILURE_ANALYSIS_DECISION
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY"
    ] = S1_FAILURE_ANALYSIS_NEXT
    result_evidence_hash: str

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
        "outcome_result_file_sha256",
        "outcome_result_evidence_hash",
        "outcome_ledger_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S1PostFailureAnalysisResult:
        if self.analysis_ids != S1_FAILURE_ANALYSIS_IDS:
            raise ValueError("S1 failure-analysis result scope changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 failure-analysis result hash changed")
        return self


class S1PostFailureAnalysisAudit(HashedModel):
    schema_version: Literal["aurex-s1-post-failure-analysis-audit-v1"] = (
        "aurex-s1-post-failure-analysis-audit-v1"
    )
    audit_id: Literal["s1-post-failure-analysis-audit-v1"] = (
        "s1-post-failure-analysis-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    outcome_ledger_file_sha256: str
    runner_contract_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    primary_interval_rows_analyzed: Literal[276] = 276
    analysis_id_count: Literal[7] = 7
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    parameter_variants_evaluated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["CONFIRM_S1_RETIRED_NO_RESCUE"] = (
        "CONFIRM_S1_RETIRED_NO_RESCUE"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY"
    ] = S1_FAILURE_ANALYSIS_NEXT
    audit_evidence_hash: str

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "outcome_ledger_file_sha256",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1PostFailureAnalysisAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 failure-analysis audit hash changed")
        return self
