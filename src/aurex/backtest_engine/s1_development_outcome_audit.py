from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S11DevelopmentOutcomeAudit(BaseModel):
    schema_version: Literal["aurex-s1-1-development-outcome-audit-v1"] = (
        "aurex-s1-1-development-outcome-audit-v1"
    )
    audit_id: Literal["s1-1-development-outcome-audit-v1"] = (
        "s1-1-development-outcome-audit-v1"
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
    feature_row_count: Literal[277] = 277
    price_row_count: Literal[277] = 277
    interval_ledger_row_count: Literal[1104] = 1104
    candidate_outcome_count: Literal[4] = 4
    primary_candidate_id: Literal["S1-C1-CONSISTENT-EASING-PRIMARY"] = (
        "S1-C1-CONSISTENT-EASING-PRIMARY"
    )
    primary_passed_gate_count: Literal[7] = 7
    primary_failed_gate_count: Literal[5] = 5
    primary_base_net_total_return: Literal[
        "0.07695828820645849360490108587610589455394410935217072100856"
    ] = "0.07695828820645849360490108587610589455394410935217072100856"
    primary_stress_net_total_return: Literal[
        "0.00804890187023937464370255809489262193398815737690473479951"
    ] = "0.00804890187023937464370255809489262193398815737690473479951"
    primary_base_profit_factor: Literal[
        "1.01395236831037631714932955595304247016237052952918400900494"
    ] = "1.01395236831037631714932955595304247016237052952918400900494"
    primary_base_maximum_drawdown: Literal[
        "0.663008741426633160528421368505154560650598786000697306393610"
    ] = "0.663008741426633160528421368505154560650598786000697306393610"
    primary_positive_full_calendar_year_count: Literal[2] = 2
    primary_stress_bootstrap_lower_mean_weekly_return: Literal[
        "-0.00483772889816540796331200158811596039371043299737925027962746"
    ] = "-0.00483772889816540796331200158811596039371043299737925027962746"
    failed_gate_ids: tuple[str, ...] = (
        "BASE_PROFIT_FACTOR",
        "BASE_MAXIMUM_DRAWDOWN",
        "STRESS_MAXIMUM_DRAWDOWN",
        "POSITIVE_FULL_CALENDAR_YEARS",
        "STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN",
    )
    diagnostic_promotion_count: Literal[0] = 0
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["CONFIRM_S1_1_DEVELOPMENT_OUTCOME_FAILED"] = (
        "CONFIRM_S1_1_DEVELOPMENT_OUTCOME_FAILED"
    )
    next_authorization: Literal["NONE_S1_1_DEVELOPMENT_OUTCOME_FAILED"] = (
        "NONE_S1_1_DEVELOPMENT_OUTCOME_FAILED"
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

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
    def validate_audit(self) -> S11DevelopmentOutcomeAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1.1 development outcome audit hash changed")
        return self
