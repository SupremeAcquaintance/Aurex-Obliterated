from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P03_TRANSPORT_AMENDMENT_SCHEMA_VERSION = (
    "aurex-v3-p03-source-audit-transport-amendment-v1"
)


class V3P03TransportAmendment(BaseModel):
    schema_version: Literal[
        "aurex-v3-p03-source-audit-transport-amendment-v1"
    ] = V3_P03_TRANSPORT_AMENDMENT_SCHEMA_VERSION
    amendment_id: Literal["v3-p03-source-audit-transport-amendment-v1"] = (
        "v3-p03-source-audit-transport-amendment-v1"
    )
    amendment_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_AFTER_TRANSPORT_FAILURE_BEFORE_SOURCE_CONTENT"] = (
        "FROZEN_AFTER_TRANSPORT_FAILURE_BEFORE_SOURCE_CONTENT"
    )
    original_contract_evidence_hash: str
    builder_contract_hash: str
    trigger_source_id: Literal["BINANCE_USDM_ACCOUNT_REST_SCHEMA"] = (
        "BINANCE_USDM_ACCOUNT_REST_SCHEMA"
    )
    trigger_observation: Literal[
        "HTTP_202_SCHEMA_GENERATION_PENDING_ABORTED_FIRST_RUN"
    ] = "HTTP_202_SCHEMA_GENERATION_PENDING_ABORTED_FIRST_RUN"
    failed_attempt_authoritative_result_created: Literal[False] = False
    source_targets_changed: Literal[False] = False
    source_substitution_permitted: Literal[False] = False
    qualification_rule_changed: Literal[False] = False
    decision_rule_changed: Literal[False] = False
    market_value_permissions_changed: Literal[False] = False
    permitted_trigger_http_statuses: list[int] = Field(
        default_factory=lambda: [200, 202]
    )
    maximum_pending_polls: Literal[3] = 3
    pending_poll_backoff_seconds: list[int] = Field(
        default_factory=lambda: [2, 5, 10]
    )
    amended_maximum_http_requests: Literal[8] = 8
    terminal_success_http_status: Literal[200] = 200
    exhausted_pending_action: Literal[
        "ABORT_WITHOUT_AUTHORITATIVE_RESULT"
    ] = "ABORT_WITHOUT_AUTHORITATIVE_RESULT"
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=5)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "original_contract_evidence_hash",
        "builder_contract_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "permitted_trigger_http_statuses",
        "pending_poll_backoff_seconds",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list) -> list:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_amendment(self) -> V3P03TransportAmendment:
        if self.permitted_trigger_http_statuses != [200, 202]:
            raise ValueError("V3P03 amended HTTP statuses changed")
        if self.pending_poll_backoff_seconds != [2, 5, 10]:
            raise ValueError("V3P03 amended backoff policy changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected_hash:
            raise ValueError("V3P03 transport amendment hash does not match")
        return self


def build_v3_p03_transport_amendment(
    **values,
) -> V3P03TransportAmendment:
    payload = {
        "schema_version": V3_P03_TRANSPORT_AMENDMENT_SCHEMA_VERSION,
        "amendment_id": "v3-p03-source-audit-transport-amendment-v1",
        "amendment_version": "1.0.0",
        "status": "FROZEN_AFTER_TRANSPORT_FAILURE_BEFORE_SOURCE_CONTENT",
        "trigger_source_id": "BINANCE_USDM_ACCOUNT_REST_SCHEMA",
        "trigger_observation": (
            "HTTP_202_SCHEMA_GENERATION_PENDING_ABORTED_FIRST_RUN"
        ),
        "failed_attempt_authoritative_result_created": False,
        "source_targets_changed": False,
        "source_substitution_permitted": False,
        "qualification_rule_changed": False,
        "decision_rule_changed": False,
        "market_value_permissions_changed": False,
        "permitted_trigger_http_statuses": [200, 202],
        "maximum_pending_polls": 3,
        "pending_poll_backoff_seconds": [2, 5, 10],
        "amended_maximum_http_requests": 8,
        "terminal_success_http_status": 200,
        "exhausted_pending_action": "ABORT_WITHOUT_AUTHORITATIVE_RESULT",
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P03TransportAmendment(
        **payload,
        amendment_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p03_transport_amendment(
    amendment: V3P03TransportAmendment,
) -> bool:
    return amendment.amendment_evidence_hash == universe_evidence_hash(
        amendment.model_dump(exclude={"amendment_evidence_hash"})
    )
