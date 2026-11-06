from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_MONTHLY_ADDENDUM_SCHEMA_VERSION = "aurex-r3-monthly-diagnostic-addendum-v1"


class R3MonthlyDiagnosticAddendum(BaseModel):
    schema_version: Literal["aurex-r3-monthly-diagnostic-addendum-v1"] = (
        R3_MONTHLY_ADDENDUM_SCHEMA_VERSION
    )
    generated_at: datetime
    status: Literal["POST_OUTCOME_DIAGNOSTIC_CORRECTION"] = (
        "POST_OUTCOME_DIAGNOSTIC_CORRECTION"
    )
    result_ledger_evidence_hash: str
    primary_replay_result_evidence_hash: str
    primary_replay_artifact_sha256: str
    builder_contract_hash: str
    defect: str = Field(min_length=1, max_length=1000)
    correction_method: Literal[
        "ATTRIBUTE_CLOSE_TO_TIMESTAMP_MINUS_ONE_MICROSECOND"
    ] = "ATTRIBUTE_CLOSE_TO_TIMESTAMP_MINUS_ONE_MICROSECOND"
    original_monthly_net_returns: dict[str, Decimal]
    corrected_monthly_net_returns: dict[str, Decimal]
    original_month_count: int = Field(gt=0)
    corrected_month_count: int = Field(gt=0)
    affected_gate_ids: list[str] = Field(default_factory=list)
    original_verdict: Literal["NO_CANDIDATE", "ADVANCE_PRIMARY_TO_R4"]
    corrected_verdict: Literal["NO_CANDIDATE", "ADVANCE_PRIMARY_TO_R4"]
    addendum_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_ledger_evidence_hash",
        "primary_replay_result_evidence_hash",
        "primary_replay_artifact_sha256",
        "builder_contract_hash",
        "addendum_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_addendum(self) -> "R3MonthlyDiagnosticAddendum":
        if self.affected_gate_ids:
            raise ValueError("R3 monthly correction cannot alter an advancement gate")
        if self.original_verdict != self.corrected_verdict:
            raise ValueError("R3 monthly correction cannot alter the frozen verdict")
        if self.original_month_count != len(self.original_monthly_net_returns):
            raise ValueError("R3 original monthly count does not match its values")
        if self.corrected_month_count != len(self.corrected_monthly_net_returns):
            raise ValueError("R3 corrected monthly count does not match its values")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"addendum_evidence_hash"})
        )
        if self.addendum_evidence_hash != expected_hash:
            raise ValueError("R3 monthly addendum hash does not match its evidence")
        return self


def build_r3_monthly_diagnostic_addendum(**values) -> R3MonthlyDiagnosticAddendum:
    payload = {
        "schema_version": R3_MONTHLY_ADDENDUM_SCHEMA_VERSION,
        **values,
    }
    payload["generated_at"] = normalize_timestamp(payload["generated_at"])
    payload["original_monthly_net_returns"] = dict(
        sorted(payload["original_monthly_net_returns"].items())
    )
    payload["corrected_monthly_net_returns"] = dict(
        sorted(payload["corrected_monthly_net_returns"].items())
    )
    payload["original_month_count"] = len(payload["original_monthly_net_returns"])
    payload["corrected_month_count"] = len(payload["corrected_monthly_net_returns"])
    payload["affected_gate_ids"] = []
    payload["corrected_verdict"] = payload["original_verdict"]
    return R3MonthlyDiagnosticAddendum(
        **payload,
        addendum_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r3_monthly_diagnostic_addendum(
    addendum: R3MonthlyDiagnosticAddendum,
) -> bool:
    return addendum.addendum_evidence_hash == universe_evidence_hash(
        addendum.model_dump(exclude={"addendum_evidence_hash"})
    )
