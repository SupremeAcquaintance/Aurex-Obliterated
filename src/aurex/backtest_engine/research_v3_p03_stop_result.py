from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v3_p03_source_audit import (
    V3_P03_FAIL_DECISION,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P03_STOP_RESULT_SCHEMA_VERSION = (
    "aurex-v3-p03-historical-microstructure-source-audit-stop-result-v1"
)
V3_P03_UNRESOLVED_SOURCE_IDS = [
    "BINANCE_USDM_ACCOUNT_REST_SCHEMA",
    "BINANCE_USDM_LOCAL_ORDER_BOOK_DOC",
    "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE",
    "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_CHECKSUM",
]


class V3P03FailedAttemptEvidence(BaseModel):
    attempt_id: Literal["INITIAL_HTTP_202", "AMENDED_HTTP_202_EXHAUSTED"]
    manifest_path: str = Field(min_length=20, max_length=500)
    manifest_sha256: str
    started_at: datetime
    status: Literal["ABORTED_WITHOUT_AUTHORITATIVE_RESULT"] = (
        "ABORTED_WITHOUT_AUTHORITATIVE_RESULT"
    )
    completed_source_count: Literal[1] = 1
    http_request_attempt_count: int = Field(ge=2, le=5)
    trigger_source_id: Literal["BINANCE_USDM_ACCOUNT_REST_SCHEMA"] = (
        "BINANCE_USDM_ACCOUNT_REST_SCHEMA"
    )
    trigger_http_statuses: list[int] = Field(min_length=1, max_length=4)
    pending_poll_budget_exhausted: bool
    authoritative_result_created: Literal[False] = False
    market_values_inspected: list[str] = Field(default_factory=list)
    strategy_outcomes_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("manifest_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("started_at")
    @classmethod
    def normalize_started_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("trigger_http_statuses")
    @classmethod
    def validate_statuses(cls, value: list[int]) -> list[int]:
        if any(item != 202 for item in value):
            raise ValueError("V3P03 failed attempt contains non-202 trigger status")
        return value

    @model_validator(mode="after")
    def validate_attempt(self) -> V3P03FailedAttemptEvidence:
        expected_count = (
            2 if self.attempt_id == "INITIAL_HTTP_202" else 5
        )
        expected_status_count = (
            1 if self.attempt_id == "INITIAL_HTTP_202" else 4
        )
        expected_exhausted = self.attempt_id == "AMENDED_HTTP_202_EXHAUSTED"
        if (
            self.http_request_attempt_count != expected_count
            or len(self.trigger_http_statuses) != expected_status_count
            or self.pending_poll_budget_exhausted != expected_exhausted
        ):
            raise ValueError("V3P03 failed attempt accounting changed")
        if (
            self.market_values_inspected
            or self.strategy_outcomes_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3P03 failed attempt may contain no outcomes")
        return self


class V3P03SourceAuditStopResult(BaseModel):
    schema_version: Literal[
        "aurex-v3-p03-historical-microstructure-source-audit-stop-result-v1"
    ] = V3_P03_STOP_RESULT_SCHEMA_VERSION
    result_id: Literal[
        "v3-p03-historical-microstructure-source-audit-stop-v1"
    ] = "v3-p03-historical-microstructure-source-audit-stop-v1"
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["FINAL_STOP_NO_RETURN_AUDIT_INCOMPLETE"] = (
        "FINAL_STOP_NO_RETURN_AUDIT_INCOMPLETE"
    )
    source_audit_contract_evidence_hash: str
    transport_amendment_evidence_hash: str
    source_runner_contract_hash: str
    finalizer_contract_hash: str
    attempts: list[V3P03FailedAttemptEvidence] = Field(
        min_length=2,
        max_length=2,
    )
    attempted_run_count: Literal[2] = 2
    total_http_request_attempt_count: Literal[7] = 7
    completed_source_count_per_attempt: Literal[1] = 1
    unresolved_source_ids: list[str] = Field(min_length=4, max_length=4)
    evaluated_requirement_ids: list[str] = Field(default_factory=list)
    qualified_requirement_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(min_length=2, max_length=2)
    decision: Literal[
        "REJECT_V3P03_REQUIRED_HISTORICAL_MICROSTRUCTURE_EVIDENCE_UNAVAILABLE"
    ] = V3_P03_FAIL_DECISION
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "source_audit_contract_evidence_hash",
        "transport_amendment_evidence_hash",
        "source_runner_contract_hash",
        "finalizer_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "unresolved_source_ids",
        "evaluated_requirement_ids",
        "qualified_requirement_ids",
        "reason_codes",
        "market_numeric_values_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V3P03SourceAuditStopResult:
        if self.attempts != sorted(
            self.attempts,
            key=lambda item: item.started_at,
        ):
            raise ValueError("V3P03 failed attempts are not chronological")
        if {item.attempt_id for item in self.attempts} != {
            "INITIAL_HTTP_202",
            "AMENDED_HTTP_202_EXHAUSTED",
        }:
            raise ValueError("V3P03 failed attempt matrix changed")
        if (
            sum(item.http_request_attempt_count for item in self.attempts) != 7
            or self.unresolved_source_ids != V3_P03_UNRESOLVED_SOURCE_IDS
        ):
            raise ValueError("V3P03 stop accounting does not reconcile")
        if self.evaluated_requirement_ids or self.qualified_requirement_ids:
            raise ValueError(
                "Incomplete V3P03 audit cannot claim evaluated requirements"
            )
        if self.reason_codes != [
            "FORMAL_SOURCE_AUDIT_INCOMPLETE",
            "TRIGGER_SOURCE_HTTP_202_POLL_BUDGET_EXHAUSTED",
        ]:
            raise ValueError("V3P03 stop reason codes changed")
        if (
            self.market_numeric_values_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3P03 stop result may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V3P03 stop result hash does not match")
        return self


def build_v3_p03_source_audit_stop_result(
    **values,
) -> V3P03SourceAuditStopResult:
    attempts = sorted(
        values.pop("attempts"),
        key=lambda item: item.started_at,
    )
    payload = {
        "schema_version": V3_P03_STOP_RESULT_SCHEMA_VERSION,
        "result_id": "v3-p03-historical-microstructure-source-audit-stop-v1",
        "result_version": "1.0.0",
        "status": "FINAL_STOP_NO_RETURN_AUDIT_INCOMPLETE",
        "attempts": attempts,
        "attempted_run_count": 2,
        "total_http_request_attempt_count": 7,
        "completed_source_count_per_attempt": 1,
        "unresolved_source_ids": V3_P03_UNRESOLVED_SOURCE_IDS,
        "evaluated_requirement_ids": [],
        "qualified_requirement_ids": [],
        "reason_codes": [
            "FORMAL_SOURCE_AUDIT_INCOMPLETE",
            "TRIGGER_SOURCE_HTTP_202_POLL_BUDGET_EXHAUSTED",
        ],
        "decision": V3_P03_FAIL_DECISION,
        "selects_primary": False,
        "creates_candidate": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "market_numeric_values_inspected": [],
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P03SourceAuditStopResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p03_source_audit_stop_result(
    result: V3P03SourceAuditStopResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
