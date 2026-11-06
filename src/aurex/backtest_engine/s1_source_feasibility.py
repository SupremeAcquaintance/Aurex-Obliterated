from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_SOURCE_PROTOCOL_SCHEMA = "aurex-s1-source-metadata-feasibility-protocol-v1"
S1_SOURCE_RESULT_SCHEMA = "aurex-s1-source-metadata-feasibility-result-v1"
S1_SOURCE_AUDIT_SCHEMA = "aurex-s1-source-metadata-feasibility-audit-v1"
S1_SOURCE_PASS_DECISION = (
    "PASS_S1_NO_KEY_VINTAGE_TRANSPORT_AWAIT_RAW_VINTAGE_PILOT_PROTOCOL"
)
S1_SOURCE_STOP_DECISION = "STOP_S1_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE"
S1_SOURCE_NEXT_AUTHORIZATION = (
    "AUTHORIZE_S1_RAW_NFCI_TWO_VINTAGE_PILOT_PROTOCOL_ONLY"
)


class S1SourceRequest(BaseModel):
    request_id: str = Field(min_length=1)
    method: Literal["HEAD"] = "HEAD"
    url: str = Field(min_length=10)
    expected_final_host: Literal[
        "alfred.stlouisfed.org",
        "api.stlouisfed.org",
        "fred.stlouisfed.org",
    ]
    role: Literal[
        "ALFRED_SERIES_PAGE",
        "NO_KEY_VINTAGE_CSV",
        "STRUCTURED_API_AUTH_CLASSIFICATION",
    ]

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1SourceMetadataProtocol(BaseModel):
    schema_version: Literal[
        "aurex-s1-source-metadata-feasibility-protocol-v1"
    ] = S1_SOURCE_PROTOCOL_SCHEMA
    protocol_id: Literal["s1-source-metadata-feasibility-protocol-v1"] = (
        "s1-source-metadata-feasibility-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    charter_path: Literal[
        "data/evidence/s1_macro_financial_conditions_charter_v1.json"
    ] = "data/evidence/s1_macro_financial_conditions_charter_v1.json"
    charter_file_sha256: str
    charter_evidence_hash: str
    requests: tuple[S1SourceRequest, ...] = Field(min_length=1)
    request_budget: Literal[4] = 4
    response_body_byte_budget: Literal[0] = 0
    maximum_redirects_per_request: Literal[5] = 5
    connect_timeout_seconds: Literal[15] = 15
    feasibility_gates: tuple[str, ...] = Field(min_length=1)
    market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    authorizes_head_requests_only: Literal[True] = True
    authorizes_response_body_read: Literal[False] = False
    authorizes_payload_acquisition: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "charter_file_sha256",
        "charter_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1SourceMetadataProtocol:
        request_ids = tuple(item.request_id for item in self.requests)
        if tuple(sorted(set(request_ids))) != request_ids:
            raise ValueError("S1 metadata requests must be unique and sorted")
        if len(self.requests) != self.request_budget:
            raise ValueError("S1 metadata request budget changed")
        if self.market_numeric_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 metadata protocol cannot inspect outcomes")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 metadata protocol evidence hash changed")
        return self


class S1SourceResponse(BaseModel):
    request_id: str = Field(min_length=1)
    attempted_at: datetime
    status_code: int | None = Field(default=None, ge=100, le=599)
    final_url: str | None = None
    final_host: str | None = None
    content_type: str | None = None
    content_length: int | None = Field(default=None, ge=0)
    etag: str | None = None
    last_modified: str | None = None
    body_bytes_read: Literal[0] = 0
    outcome: Literal["HTTP_RESPONSE", "TRANSPORT_ERROR"]
    error_type: str | None = None
    error_message: str | None = None
    response_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("attempted_at")
    @classmethod
    def normalize_attempted_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("response_evidence_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_response(self) -> S1SourceResponse:
        if self.outcome == "HTTP_RESPONSE" and self.status_code is None:
            raise ValueError("S1 HTTP response requires a status code")
        if self.outcome == "TRANSPORT_ERROR" and not self.error_type:
            raise ValueError("S1 transport error requires an error type")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"response_evidence_hash"})
        )
        if self.response_evidence_hash != expected:
            raise ValueError("S1 response evidence hash changed")
        return self


class S1SourceGate(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    reason: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1SourceMetadataResult(BaseModel):
    schema_version: Literal[
        "aurex-s1-source-metadata-feasibility-result-v1"
    ] = S1_SOURCE_RESULT_SCHEMA
    result_id: Literal["s1-source-metadata-feasibility-result-v1"] = (
        "s1-source-metadata-feasibility-result-v1"
    )
    completed_at: datetime
    protocol_path: Literal[
        "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
    ] = "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    runner_source_sha256: str
    responses: tuple[S1SourceResponse, ...] = Field(min_length=1)
    gates: tuple[S1SourceGate, ...] = Field(min_length=1)
    request_count: Literal[4] = 4
    response_body_bytes_read: Literal[0] = 0
    market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal[
        "PASS_S1_NO_KEY_VINTAGE_TRANSPORT_AWAIT_RAW_VINTAGE_PILOT_PROTOCOL",
        "STOP_S1_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_RAW_NFCI_TWO_VINTAGE_PILOT_PROTOCOL_ONLY",
        "NONE_SOURCE_TRANSPORT_UNAVAILABLE",
    ]
    authorizes_payload_acquisition: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("completed_at")
    @classmethod
    def normalize_completed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "runner_source_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S1SourceMetadataResult:
        request_ids = tuple(item.request_id for item in self.responses)
        if tuple(sorted(set(request_ids))) != request_ids:
            raise ValueError("S1 responses must be unique and sorted")
        if len(self.responses) != self.request_count:
            raise ValueError("S1 response count changed")
        failed = any(gate.status == "FAIL" for gate in self.gates)
        expected_decision = S1_SOURCE_STOP_DECISION if failed else S1_SOURCE_PASS_DECISION
        if self.decision != expected_decision:
            raise ValueError("S1 source decision does not match its gates")
        expected_next = (
            "NONE_SOURCE_TRANSPORT_UNAVAILABLE"
            if failed
            else S1_SOURCE_NEXT_AUTHORIZATION
        )
        if self.next_authorization != expected_next:
            raise ValueError("S1 source next authorization changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 source result evidence hash changed")
        return self


class S1SourceMetadataAudit(BaseModel):
    schema_version: Literal[
        "aurex-s1-source-metadata-feasibility-audit-v1"
    ] = S1_SOURCE_AUDIT_SCHEMA
    audit_id: Literal["s1-source-metadata-feasibility-audit-v1"] = (
        "s1-source-metadata-feasibility-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    runner_source_sha256: str
    auditor_source_sha256: str
    response_count: Literal[4] = 4
    response_body_bytes_read: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal[
        "PASS_S1_METADATA_RESULT_RECONSTRUCTED",
        "STOP_S1_METADATA_RESULT_RECONSTRUCTED",
    ]
    next_authorization: str = Field(min_length=1)
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "runner_source_sha256",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1SourceMetadataAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 source audit evidence hash changed")
        return self


def evidence_hash_without(model: BaseModel, field: str) -> str:
    return universe_evidence_hash(model.model_dump(exclude={field}))
