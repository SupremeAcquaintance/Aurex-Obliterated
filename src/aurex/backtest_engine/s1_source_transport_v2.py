from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_source_feasibility import S1SourceGate, S1SourceResponse
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_V2_PASS = "PASS_S1_V2_NO_KEY_VINTAGE_TRANSPORT_AWAIT_RAW_PILOT_PROTOCOL"
S1_V2_STOP = "STOP_S1_V2_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE"
S1_V2_NEXT = "AUTHORIZE_S1_RAW_NFCI_TWO_VINTAGE_PILOT_PROTOCOL_ONLY"


class S1V2SourceRequest(BaseModel):
    request_id: str = Field(min_length=1)
    method: Literal["GET"] = "GET"
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


class S1SourceTransportAmendmentV2(BaseModel):
    schema_version: Literal["aurex-s1-source-transport-amendment-v2"] = (
        "aurex-s1-source-transport-amendment-v2"
    )
    amendment_id: Literal["s1-source-transport-amendment-v2"] = (
        "s1-source-transport-amendment-v2"
    )
    frozen_at: datetime
    builder_contract_hash: str
    v1_protocol_path: Literal[
        "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
    ] = "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
    v1_protocol_file_sha256: str
    v1_protocol_evidence_hash: str
    v1_result_path: Literal[
        "data/evidence/s1_source_metadata_feasibility_result_v1.json"
    ] = "data/evidence/s1_source_metadata_feasibility_result_v1.json"
    v1_result_file_sha256: str
    v1_result_evidence_hash: str
    v1_audit_path: Literal[
        "data/evidence/s1_source_metadata_feasibility_audit_v1.json"
    ] = "data/evidence/s1_source_metadata_feasibility_audit_v1.json"
    v1_audit_file_sha256: str
    v1_audit_evidence_hash: str
    v1_decision: Literal[
        "STOP_S1_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE"
    ] = "STOP_S1_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE"
    failure_classification: Literal[
        "HEAD_METHOD_COMPATIBILITY_UNRESOLVED_ZERO_BODY_BYTES"
    ] = "HEAD_METHOD_COMPATIBILITY_UNRESOLVED_ZERO_BODY_BYTES"
    preserved_urls: tuple[str, ...] = Field(min_length=1)
    amended_method: Literal["GET_OPEN_HEADERS_CLOSE_WITHOUT_READ"] = (
        "GET_OPEN_HEADERS_CLOSE_WITHOUT_READ"
    )
    request_budget: Literal[4] = 4
    retry_budget: Literal[0] = 0
    application_body_byte_budget: Literal[0] = 0
    connect_timeout_seconds: Literal[30] = 30
    maximum_redirects_per_request: Literal[5] = 5
    unchanged_gates: tuple[str, ...] = Field(min_length=1)
    market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    authorizes_get_open_only: Literal[True] = True
    authorizes_response_read_call: Literal[False] = False
    authorizes_payload_persistence: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "v1_protocol_file_sha256",
        "v1_protocol_evidence_hash",
        "v1_result_file_sha256",
        "v1_result_evidence_hash",
        "v1_audit_file_sha256",
        "v1_audit_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S1SourceTransportAmendmentV2:
        if len(self.preserved_urls) != self.request_budget:
            raise ValueError("S1 v2 URL set changed")
        if self.market_numeric_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 v2 amendment cannot inspect outcomes")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S1 v2 amendment evidence hash changed")
        return self


class S1SourceTransportResultV2(BaseModel):
    schema_version: Literal["aurex-s1-source-transport-result-v2"] = (
        "aurex-s1-source-transport-result-v2"
    )
    result_id: Literal["s1-source-transport-result-v2"] = (
        "s1-source-transport-result-v2"
    )
    completed_at: datetime
    amendment_path: Literal[
        "data/evidence/s1_source_transport_amendment_v2.json"
    ] = "data/evidence/s1_source_transport_amendment_v2.json"
    amendment_file_sha256: str
    amendment_evidence_hash: str
    runner_source_sha256: str
    requests: tuple[S1V2SourceRequest, ...] = Field(min_length=1)
    responses: tuple[S1SourceResponse, ...] = Field(min_length=1)
    gates: tuple[S1SourceGate, ...] = Field(min_length=1)
    request_count: Literal[4] = 4
    retry_count: Literal[0] = 0
    response_read_calls: Literal[0] = 0
    application_body_bytes_read: Literal[0] = 0
    persisted_payload_bytes: Literal[0] = 0
    market_numeric_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal[
        "PASS_S1_V2_NO_KEY_VINTAGE_TRANSPORT_AWAIT_RAW_PILOT_PROTOCOL",
        "STOP_S1_V2_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_RAW_NFCI_TWO_VINTAGE_PILOT_PROTOCOL_ONLY",
        "NONE_S1_V2_SOURCE_TRANSPORT_UNAVAILABLE",
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
        "amendment_file_sha256",
        "amendment_evidence_hash",
        "runner_source_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S1SourceTransportResultV2:
        request_ids = tuple(item.request_id for item in self.requests)
        response_ids = tuple(item.request_id for item in self.responses)
        if request_ids != response_ids or len(request_ids) != self.request_count:
            raise ValueError("S1 v2 request and response identity changed")
        failed = any(gate.status == "FAIL" for gate in self.gates)
        if self.decision != (S1_V2_STOP if failed else S1_V2_PASS):
            raise ValueError("S1 v2 decision does not match gates")
        expected_next = (
            "NONE_S1_V2_SOURCE_TRANSPORT_UNAVAILABLE" if failed else S1_V2_NEXT
        )
        if self.next_authorization != expected_next:
            raise ValueError("S1 v2 next authorization changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 v2 result evidence hash changed")
        return self


class S1SourceTransportAuditV2(BaseModel):
    schema_version: Literal["aurex-s1-source-transport-audit-v2"] = (
        "aurex-s1-source-transport-audit-v2"
    )
    audit_id: Literal["s1-source-transport-audit-v2"] = (
        "s1-source-transport-audit-v2"
    )
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    runner_source_sha256: str
    auditor_source_sha256: str
    response_count: Literal[4] = 4
    application_body_bytes_read: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal[
        "PASS_S1_V2_RESULT_RECONSTRUCTED",
        "STOP_S1_V2_RESULT_RECONSTRUCTED",
    ]
    next_authorization: str = Field(min_length=1)
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "amendment_file_sha256",
        "amendment_evidence_hash",
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
    def validate_audit(self) -> S1SourceTransportAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 v2 audit evidence hash changed")
        return self
