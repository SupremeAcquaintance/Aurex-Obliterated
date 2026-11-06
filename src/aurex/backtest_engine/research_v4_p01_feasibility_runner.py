from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v4_p01_feasibility_contract import (
    V4P01_REQUIRED_GATE_IDS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

EMPTY_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb924"
    "27ae41e4649b934ca495991b7852b855"
)
V4P01_RUNNER_SCHEMA_VERSION = "aurex-v4-p01-feasibility-runner-v1"


def _normalized_strings(values: list[str]) -> list[str]:
    return sorted({item.strip() for item in values if item.strip()})


class V4P01JournalRecord(BaseModel):
    schema_version: Literal[
        "aurex-v4-p01-transport-journal-record-v1"
    ] = "aurex-v4-p01-transport-journal-record-v1"
    record_sequence: int = Field(ge=1, le=16)
    record_type: Literal["REQUEST_INTENT", "RESPONSE", "FAILURE"]
    recorded_at: datetime
    contract_evidence_hash: str
    request_id: str
    request_sequence: int = Field(ge=1, le=8)
    attempt: Literal[1] = 1
    previous_record_hash: str | None
    request_url_hash: str
    request_headers_hash: str
    http_status: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str] = Field(default_factory=dict)
    elapsed_milliseconds: int | None = Field(default=None, ge=0)
    byte_count: int = Field(default=0, ge=0)
    payload_sha256: str = EMPTY_SHA256
    raw_relative_path: str | None = None
    failure_class: str | None = None
    failure_message: str | None = None
    record_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("recorded_at")
    @classmethod
    def normalize_recorded_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "previous_record_hash",
        "request_url_hash",
        "request_headers_hash",
        "payload_sha256",
        "record_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_record(self) -> V4P01JournalRecord:
        if self.record_sequence == 1 and self.previous_record_hash is not None:
            raise ValueError("First V4P01 journal record cannot have a predecessor")
        if self.record_sequence > 1 and self.previous_record_hash is None:
            raise ValueError("V4P01 journal chain predecessor is absent")
        if self.record_type == "REQUEST_INTENT":
            if (
                self.http_status is not None
                or self.response_headers
                or self.elapsed_milliseconds is not None
                or self.byte_count != 0
                or self.payload_sha256 != EMPTY_SHA256
                or self.raw_relative_path is not None
                or self.failure_class is not None
                or self.failure_message is not None
            ):
                raise ValueError("V4P01 request intent contains outcome evidence")
        elif self.record_type == "RESPONSE":
            if (
                self.http_status != 200
                or self.elapsed_milliseconds is None
                or self.byte_count < 1
                or self.raw_relative_path is None
                or self.failure_class is not None
                or self.failure_message is not None
            ):
                raise ValueError("V4P01 response record is incomplete")
        elif (
            self.elapsed_milliseconds is None
            or not self.failure_class
            or not self.failure_message
            or self.raw_relative_path is not None
        ):
            raise ValueError("V4P01 failure record is incomplete")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"record_evidence_hash"})
        )
        if self.record_evidence_hash != expected:
            raise ValueError("V4P01 journal record hash does not match")
        return self


def build_v4_p01_journal_record(**values) -> V4P01JournalRecord:
    payload = {
        "schema_version": "aurex-v4-p01-transport-journal-record-v1",
        "attempt": 1,
        "http_status": None,
        "response_headers": {},
        "elapsed_milliseconds": None,
        "byte_count": 0,
        "payload_sha256": EMPTY_SHA256,
        "raw_relative_path": None,
        "failure_class": None,
        "failure_message": None,
        **values,
    }
    payload["recorded_at"] = normalize_timestamp(payload["recorded_at"])
    return V4P01JournalRecord(
        **payload,
        record_evidence_hash=universe_evidence_hash(payload),
    )


class V4P01SourceObservation(BaseModel):
    schema_version: Literal[
        "aurex-v4-p01-source-observation-v1"
    ] = "aurex-v4-p01-source-observation-v1"
    observation_sequence: int = Field(ge=1, le=8)
    observed_at: datetime
    contract_evidence_hash: str
    request_id: str
    request_sequence: int = Field(ge=1, le=8)
    phase: Literal["METADATA_CENSUS", "PAYLOAD_SCHEMA_PILOT"]
    exchange_id: Literal["binance", "coinbase"]
    product_identity: str | None
    product_identity_matches: bool
    http_status: int = Field(ge=100, le=599)
    response_header_subset: dict[str, str]
    content_type: str | None
    content_encoding: str | None
    content_length: int | None = Field(default=None, ge=0)
    elapsed_milliseconds: int = Field(ge=0)
    byte_count: int = Field(ge=1)
    payload_sha256: str
    row_count: int = Field(ge=0)
    capture_line_count: int = Field(ge=0)
    channel_identity: list[str]
    schema_key_presence: list[str]
    missing_required_schema_keys: dict[str, list[str]]
    local_timestamp_presence_count: int = Field(ge=0)
    exchange_timestamp_presence_count: int = Field(ge=0)
    sequence_or_update_id_presence_count: int = Field(ge=0)
    disconnect_marker_count: int = Field(ge=0)
    reconnect_snapshot_count: int = Field(ge=0)
    duplicate_local_timestamp_count: int = Field(ge=0)
    first_local_timestamp: datetime | None
    last_local_timestamp: datetime | None
    first_exchange_timestamp: datetime | None
    last_exchange_timestamp: datetime | None
    source_available_since: datetime | None
    source_available_to: datetime | None
    symbol_available_since: datetime | None
    symbol_available_to: datetime | None
    source_revision_identity: list[str]
    incident_identity_and_time_boundary: list[str]
    boundary_completeness: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    observation_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "observed_at",
        "first_local_timestamp",
        "last_local_timestamp",
        "first_exchange_timestamp",
        "last_exchange_timestamp",
        "source_available_since",
        "source_available_to",
        "symbol_available_since",
        "symbol_available_to",
    )
    @classmethod
    def normalize_timestamps(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None

    @field_validator(
        "contract_evidence_hash",
        "payload_sha256",
        "observation_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "channel_identity",
        "schema_key_presence",
        "source_revision_identity",
        "incident_identity_and_time_boundary",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return _normalized_strings(value)

    @field_validator("missing_required_schema_keys")
    @classmethod
    def normalize_missing_keys(
        cls,
        value: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        return {
            key.strip(): _normalized_strings(items)
            for key, items in sorted(value.items())
            if key.strip()
        }

    @model_validator(mode="after")
    def validate_observation(self) -> V4P01SourceObservation:
        if self.phase == "METADATA_CENSUS":
            if (
                self.capture_line_count != 0
                or self.local_timestamp_presence_count != 0
                or self.boundary_completeness != "NOT_APPLICABLE"
            ):
                raise ValueError("V4P01 metadata observation shape changed")
        elif (
            self.source_available_since is not None
            or self.source_available_to is not None
            or self.symbol_available_since is not None
            or self.symbol_available_to is not None
            or self.capture_line_count != self.row_count
            or self.boundary_completeness == "NOT_APPLICABLE"
        ):
            raise ValueError("V4P01 payload observation shape changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"observation_evidence_hash"})
        )
        if self.observation_evidence_hash != expected:
            raise ValueError("V4P01 source observation hash does not match")
        return self


def build_v4_p01_source_observation(**values) -> V4P01SourceObservation:
    payload = {
        "schema_version": "aurex-v4-p01-source-observation-v1",
        **values,
    }
    payload["observed_at"] = normalize_timestamp(payload["observed_at"])
    return V4P01SourceObservation(
        **payload,
        observation_evidence_hash=universe_evidence_hash(payload),
    )


class V4P01MetadataGateResult(BaseModel):
    schema_version: Literal[
        "aurex-v4-p01-metadata-gate-result-v1"
    ] = "aurex-v4-p01-metadata-gate-result-v1"
    evaluated_at: datetime
    contract_evidence_hash: str
    observation_hashes: list[str] = Field(min_length=2, max_length=2)
    request_ids: list[str] = Field(min_length=2, max_length=2)
    status: Literal["PASS", "FAIL"]
    reasons: list[str] = Field(min_length=1)
    payload_phase_authorized: bool
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "observation_hashes",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(
        cls,
        value: str | list[str],
    ) -> str | list[str]:
        if isinstance(value, list):
            return [normalize_sha256(item) for item in value]
        return normalize_sha256(value)

    @field_validator("request_ids", "reasons")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return _normalized_strings(value)

    @model_validator(mode="after")
    def validate_result(self) -> V4P01MetadataGateResult:
        if self.payload_phase_authorized != (self.status == "PASS"):
            raise ValueError("V4P01 metadata gate permission is inconsistent")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("V4P01 metadata gate result hash does not match")
        return self


def build_v4_p01_metadata_gate_result(**values) -> V4P01MetadataGateResult:
    payload = {
        "schema_version": "aurex-v4-p01-metadata-gate-result-v1",
        **values,
    }
    payload["evaluated_at"] = normalize_timestamp(payload["evaluated_at"])
    payload["request_ids"] = _normalized_strings(payload["request_ids"])
    payload["reasons"] = _normalized_strings(payload["reasons"])
    return V4P01MetadataGateResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


class V4P01ExecutionGateResult(BaseModel):
    gate_id: str
    status: Literal["PASS", "FAIL", "UNRESOLVED"]
    evidence_hashes: list[str]
    reason: str = Field(min_length=20, max_length=1600)
    conservative_override_used: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_hashes")
    @classmethod
    def normalize_evidence_hashes(cls, value: list[str]) -> list[str]:
        return sorted({normalize_sha256(item) for item in value})


class V4P01ResourceTotals(BaseModel):
    attempts_used: int = Field(ge=0, le=8)
    responses_completed: int = Field(ge=0, le=8)
    failures_recorded: int = Field(ge=0, le=1)
    response_bytes: int = Field(ge=0, le=117_440_512)
    active_elapsed_milliseconds: int = Field(ge=0, le=1_200_000)
    durable_storage_bytes: int = Field(ge=0, le=268_435_456)

    model_config = ConfigDict(extra="forbid")


class V4P01TerminalResult(BaseModel):
    schema_version: Literal[
        "aurex-v4-p01-feasibility-terminal-result-v1"
    ] = "aurex-v4-p01-feasibility-terminal-result-v1"
    terminal_kind: Literal["COMPLETE", "REJECT", "TRANSPORT_STOP"]
    terminal_timestamp: datetime
    builder_and_contract_hashes: dict[str, str]
    completed_and_failed_request_ids: dict[str, list[str]]
    decision: str
    execution_gate_results: list[V4P01ExecutionGateResult] = Field(
        min_length=14,
        max_length=14,
    )
    metadata_and_payload_observation_hashes: dict[str, list[str]]
    parsed_and_prohibited_field_manifest: dict[str, list[str]]
    request_journal_hash: str
    resource_totals: V4P01ResourceTotals
    selection_and_permission_boundary: dict[str, bool]
    failed_request_id_and_attempt: dict[str, str | int] | None = None
    failure_class_and_message: dict[str, str] | None = None
    partial_byte_count_and_sha256: dict[str, str | int] | None = None
    request_intent_record_hash: str | None = None
    response_headers_if_received: dict[str, str] | None = None
    unconsumed_request_and_byte_budgets: dict[str, int] | None = None
    unreconciled_intent_status: str | None = None
    selects_primary: Literal[False] = False
    authorizes_returns: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("terminal_timestamp")
    @classmethod
    def normalize_terminal_timestamp(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "request_journal_hash",
        "request_intent_record_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @field_validator("builder_and_contract_hashes")
    @classmethod
    def normalize_hash_map(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            key: normalize_sha256(item)
            for key, item in sorted(value.items())
        }

    @model_validator(mode="after")
    def validate_terminal_result(self) -> V4P01TerminalResult:
        if [item.gate_id for item in self.execution_gate_results] != (
            V4P01_REQUIRED_GATE_IDS
        ):
            raise ValueError("V4P01 terminal execution gate order changed")
        transport_fields = (
            self.failed_request_id_and_attempt,
            self.failure_class_and_message,
            self.partial_byte_count_and_sha256,
            self.request_intent_record_hash,
            self.response_headers_if_received,
            self.unconsumed_request_and_byte_budgets,
            self.unreconciled_intent_status,
        )
        if self.terminal_kind == "TRANSPORT_STOP":
            if any(item is None for item in transport_fields):
                raise ValueError("V4P01 transport stop evidence is incomplete")
        elif any(item is not None for item in transport_fields):
            raise ValueError("V4P01 non-transport result has transport fields")
        statuses = {item.status for item in self.execution_gate_results}
        if self.terminal_kind == "COMPLETE" and statuses != {"PASS"}:
            raise ValueError("V4P01 complete result requires all gates to pass")
        if self.terminal_kind == "REJECT" and statuses == {"PASS"}:
            raise ValueError("V4P01 reject result requires a failed gate")
        if any(self.selection_and_permission_boundary.values()):
            raise ValueError("V4P01 terminal result cannot grant permission")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("V4P01 terminal result hash does not match")
        return self


def build_v4_p01_terminal_result(**values) -> V4P01TerminalResult:
    payload = {
        "schema_version": "aurex-v4-p01-feasibility-terminal-result-v1",
        "failed_request_id_and_attempt": None,
        "failure_class_and_message": None,
        "partial_byte_count_and_sha256": None,
        "request_intent_record_hash": None,
        "response_headers_if_received": None,
        "unconsumed_request_and_byte_budgets": None,
        "unreconciled_intent_status": None,
        "selects_primary": False,
        "authorizes_returns": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["terminal_timestamp"] = normalize_timestamp(
        payload["terminal_timestamp"]
    )
    return V4P01TerminalResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_p01_terminal_result(result: V4P01TerminalResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def unresolved_execution_gates() -> list[V4P01ExecutionGateResult]:
    return [
        V4P01ExecutionGateResult(
            gate_id=gate_id,
            status="UNRESOLVED",
            evidence_hashes=[],
            reason=(
                "This hard gate has not been evidenced by the bounded source "
                "transport and schema pilot."
            ),
        )
        for gate_id in V4P01_REQUIRED_GATE_IDS
    ]
