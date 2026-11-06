from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v4_p02_feasibility_contract import (
    V4P02_PERMITTED_OBSERVATION_FIELDS,
    V4P02_PROHIBITED_PARSED_FIELDS,
    V4P02_REQUIRED_GATE_IDS,
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
V4P02_PERMISSION_BOUNDARY = {
    "selects_primary": False,
    "authorizes_dataset_payload_gets": False,
    "authorizes_raw_replay_requests": False,
    "authorizes_deribit_api_requests": False,
    "authorizes_returns": False,
    "creates_candidate": False,
    "opens_validation": False,
    "opens_holdout": False,
    "opens_forward": False,
    "creates_paper_eligibility": False,
    "creates_sandbox_eligibility": False,
    "creates_live_eligibility": False,
}


def _normalized_strings(values: list[str]) -> list[str]:
    return sorted({item.strip() for item in values if item.strip()})


class V4P02RedirectHop(BaseModel):
    hop_sequence: int = Field(ge=1, le=3)
    request_url: str = Field(min_length=8, max_length=1600)
    http_status: Literal[301, 302, 303, 307, 308]
    location: str = Field(min_length=1, max_length=1600)
    resolved_target_url: str = Field(min_length=8, max_length=1600)
    response_header_subset: dict[str, str]

    model_config = ConfigDict(extra="forbid")


class V4P02JournalRecord(BaseModel):
    schema_version: Literal[
        "aurex-v4-p02-transport-journal-record-v1"
    ] = "aurex-v4-p02-transport-journal-record-v1"
    record_sequence: int = Field(ge=1, le=56)
    record_type: Literal["REQUEST_INTENT", "RESPONSE", "FAILURE"]
    recorded_at: datetime
    contract_evidence_hash: str
    request_id: str
    request_sequence: int = Field(ge=1, le=28)
    request_method: Literal["GET", "HEAD"]
    attempt: Literal[1] = 1
    previous_record_hash: str | None
    initial_url_hash: str
    request_headers_hash: str
    redirect_chain: list[V4P02RedirectHop] = Field(default_factory=list)
    final_url_hash: str | None = None
    final_host: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str] = Field(default_factory=dict)
    elapsed_milliseconds: int | None = Field(default=None, ge=0)
    http_hop_count: int = Field(default=0, ge=0, le=4)
    byte_count: int = Field(default=0, ge=0, le=8_388_608)
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
        "initial_url_hash",
        "request_headers_hash",
        "final_url_hash",
        "payload_sha256",
        "record_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_record(self) -> V4P02JournalRecord:
        if self.record_sequence == 1 and self.previous_record_hash is not None:
            raise ValueError("First V4P02 journal record cannot have a predecessor")
        if self.record_sequence > 1 and self.previous_record_hash is None:
            raise ValueError("V4P02 journal chain predecessor is absent")
        if [hop.hop_sequence for hop in self.redirect_chain] != list(
            range(1, len(self.redirect_chain) + 1)
        ):
            raise ValueError("V4P02 redirect hop sequence changed")
        if self.request_method == "GET" and self.redirect_chain:
            raise ValueError("V4P02 metadata GET cannot redirect")
        if self.record_type == "REQUEST_INTENT":
            if (
                self.redirect_chain
                or self.final_url_hash is not None
                or self.final_host is not None
                or self.http_status is not None
                or self.response_headers
                or self.elapsed_milliseconds is not None
                or self.http_hop_count != 0
                or self.byte_count != 0
                or self.payload_sha256 != EMPTY_SHA256
                or self.raw_relative_path is not None
                or self.failure_class is not None
                or self.failure_message is not None
            ):
                raise ValueError("V4P02 request intent contains outcome evidence")
        elif self.record_type == "RESPONSE":
            if (
                self.http_status != 200
                or self.final_url_hash is None
                or not self.final_host
                or self.elapsed_milliseconds is None
                or self.http_hop_count != len(self.redirect_chain) + 1
                or self.failure_class is not None
                or self.failure_message is not None
            ):
                raise ValueError("V4P02 response record is incomplete")
            if self.request_method == "GET":
                if (
                    self.byte_count < 1
                    or self.payload_sha256 == EMPTY_SHA256
                    or self.raw_relative_path is None
                ):
                    raise ValueError("V4P02 metadata response body is absent")
            elif (
                self.byte_count != 0
                or self.payload_sha256 != EMPTY_SHA256
                or self.raw_relative_path is not None
            ):
                raise ValueError("V4P02 HEAD response contains body evidence")
        elif (
            self.elapsed_milliseconds is None
            or self.failure_class is None
            or self.failure_message is None
            or self.raw_relative_path is not None
        ):
            raise ValueError("V4P02 failure record is incomplete")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"record_evidence_hash"})
        )
        if self.record_evidence_hash != expected:
            raise ValueError("V4P02 journal record hash does not match")
        return self


def build_v4_p02_journal_record(**values) -> V4P02JournalRecord:
    payload = {
        "schema_version": "aurex-v4-p02-transport-journal-record-v1",
        "attempt": 1,
        "redirect_chain": [],
        "final_url_hash": None,
        "final_host": None,
        "http_status": None,
        "response_headers": {},
        "elapsed_milliseconds": None,
        "http_hop_count": 0,
        "byte_count": 0,
        "payload_sha256": EMPTY_SHA256,
        "raw_relative_path": None,
        "failure_class": None,
        "failure_message": None,
        **values,
    }
    payload["recorded_at"] = normalize_timestamp(payload["recorded_at"])
    return V4P02JournalRecord(
        **payload,
        record_evidence_hash=universe_evidence_hash(payload),
    )


class V4P02MetadataObservation(BaseModel):
    schema_version: Literal[
        "aurex-v4-p02-metadata-observation-v1"
    ] = "aurex-v4-p02-metadata-observation-v1"
    observed_at: datetime
    contract_evidence_hash: str
    request_id: str
    request_sequence: Literal[1] = 1
    exchange_id: str | None
    http_status: Literal[200] = 200
    response_header_subset: dict[str, str]
    elapsed_milliseconds: int = Field(ge=0)
    byte_count: int = Field(ge=1, le=8_388_608)
    payload_sha256: str
    exchange_available_since: datetime | None
    exchange_available_to: datetime | None
    available_channel_identity: list[str]
    dataset_exported_until: datetime | None
    dataset_symbol_data_types: dict[str, list[str]]
    symbol_available_since_and_to: dict[str, dict[str, datetime | None]]
    incident_identity_and_time_boundary: list[str]
    source_revision_identity: list[str]
    observation_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "observed_at",
        "exchange_available_since",
        "exchange_available_to",
        "dataset_exported_until",
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
        "available_channel_identity",
        "incident_identity_and_time_boundary",
        "source_revision_identity",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return _normalized_strings(value)

    @field_validator("dataset_symbol_data_types")
    @classmethod
    def normalize_symbol_types(
        cls,
        value: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        return {
            key.strip(): _normalized_strings(items)
            for key, items in sorted(value.items())
            if key.strip()
        }

    @field_validator("symbol_available_since_and_to")
    @classmethod
    def normalize_symbol_boundaries(
        cls,
        value: dict[str, dict[str, datetime | None]],
    ) -> dict[str, dict[str, datetime | None]]:
        result: dict[str, dict[str, datetime | None]] = {}
        for symbol, boundaries in sorted(value.items()):
            if set(boundaries) != {"available_since", "available_to"}:
                raise ValueError("V4P02 symbol boundary fields changed")
            result[symbol.strip()] = {
                key: (
                    normalize_timestamp(item) if item is not None else None
                )
                for key, item in boundaries.items()
            }
        return result

    @model_validator(mode="after")
    def validate_observation(self) -> V4P02MetadataObservation:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"observation_evidence_hash"})
        )
        if self.observation_evidence_hash != expected:
            raise ValueError("V4P02 metadata observation hash does not match")
        return self


def build_v4_p02_metadata_observation(**values) -> V4P02MetadataObservation:
    payload = {
        "schema_version": "aurex-v4-p02-metadata-observation-v1",
        **values,
    }
    payload["observed_at"] = normalize_timestamp(payload["observed_at"])
    return V4P02MetadataObservation(
        **payload,
        observation_evidence_hash=universe_evidence_hash(payload),
    )


class V4P02HeaderObservation(BaseModel):
    schema_version: Literal[
        "aurex-v4-p02-header-observation-v1"
    ] = "aurex-v4-p02-header-observation-v1"
    observation_sequence: int = Field(ge=1, le=27)
    observed_at: datetime
    contract_evidence_hash: str
    request_id: str
    request_sequence: int = Field(ge=2, le=28)
    dataset_data_type: str
    dataset_symbol: Literal["OPTIONS", "BTC-PERPETUAL"]
    dataset_role: str
    sample_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    redirect_chain: list[V4P02RedirectHop]
    final_url_hash: str
    final_host: str
    http_status: Literal[200] = 200
    response_header_subset: dict[str, str]
    content_type: str | None
    content_encoding: str | None
    content_length: int | None = Field(default=None, ge=0)
    source_revision_identity: list[str]
    elapsed_milliseconds: int = Field(ge=0)
    body_byte_count: Literal[0] = 0
    payload_sha256: Literal[
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    ] = EMPTY_SHA256
    observation_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "final_url_hash",
        "payload_sha256",
        "observation_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("source_revision_identity")
    @classmethod
    def normalize_revision_identity(cls, value: list[str]) -> list[str]:
        return _normalized_strings(value)

    @model_validator(mode="after")
    def validate_observation(self) -> V4P02HeaderObservation:
        if self.observation_sequence != self.request_sequence - 1:
            raise ValueError("V4P02 header observation sequence changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"observation_evidence_hash"})
        )
        if self.observation_evidence_hash != expected:
            raise ValueError("V4P02 header observation hash does not match")
        return self


def build_v4_p02_header_observation(**values) -> V4P02HeaderObservation:
    payload = {
        "schema_version": "aurex-v4-p02-header-observation-v1",
        "body_byte_count": 0,
        "payload_sha256": EMPTY_SHA256,
        **values,
    }
    payload["observed_at"] = normalize_timestamp(payload["observed_at"])
    return V4P02HeaderObservation(
        **payload,
        observation_evidence_hash=universe_evidence_hash(payload),
    )


class V4P02MetadataGateResult(BaseModel):
    schema_version: Literal[
        "aurex-v4-p02-metadata-gate-result-v1"
    ] = "aurex-v4-p02-metadata-gate-result-v1"
    evaluated_at: datetime
    contract_evidence_hash: str
    metadata_observation_hash: str
    status: Literal["PASS", "FAIL"]
    reasons: list[str] = Field(min_length=1)
    dataset_header_phase_authorized: bool
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "metadata_observation_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("reasons")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        return _normalized_strings(value)

    @model_validator(mode="after")
    def validate_result(self) -> V4P02MetadataGateResult:
        if self.dataset_header_phase_authorized != (self.status == "PASS"):
            raise ValueError("V4P02 metadata gate permission is inconsistent")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("V4P02 metadata gate hash does not match")
        return self


def build_v4_p02_metadata_gate_result(**values) -> V4P02MetadataGateResult:
    payload = {
        "schema_version": "aurex-v4-p02-metadata-gate-result-v1",
        **values,
    }
    payload["evaluated_at"] = normalize_timestamp(payload["evaluated_at"])
    payload["reasons"] = _normalized_strings(payload["reasons"])
    return V4P02MetadataGateResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


class V4P02DatasetStorageProjection(BaseModel):
    data_type: str
    dataset_symbol: Literal["OPTIONS", "BTC-PERPETUAL"]
    sample_content_lengths: list[int] = Field(min_length=3, max_length=3)
    average_daily_bytes: int = Field(ge=1)
    development_calendar_days: Literal[731] = 731
    projected_storage_bytes: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_projection(self) -> V4P02DatasetStorageProjection:
        expected_average = round(sum(self.sample_content_lengths) / 3)
        if self.average_daily_bytes != expected_average:
            raise ValueError("V4P02 average daily storage changed")
        if self.projected_storage_bytes != expected_average * 731:
            raise ValueError("V4P02 projected storage changed")
        return self


class V4P02StorageProjection(BaseModel):
    formula: Literal[
        "SUM(ROUND(SUM(THREE_SAMPLE_LENGTHS)/3)*731)"
    ] = "SUM(ROUND(SUM(THREE_SAMPLE_LENGTHS)/3)*731)"
    development_calendar_days: Literal[731] = 731
    products: list[V4P02DatasetStorageProjection] = Field(
        min_length=9,
        max_length=9,
    )
    total_projected_storage_bytes: int = Field(ge=1)
    ceiling_bytes: Literal[2_199_023_255_552] = 2_199_023_255_552
    status: Literal["PASS", "FAIL"]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_projection(self) -> V4P02StorageProjection:
        expected_total = sum(
            item.projected_storage_bytes for item in self.products
        )
        if self.total_projected_storage_bytes != expected_total:
            raise ValueError("V4P02 total storage projection changed")
        if self.status != (
            "PASS" if expected_total <= self.ceiling_bytes else "FAIL"
        ):
            raise ValueError("V4P02 storage projection status changed")
        return self


class V4P02ExecutionGateResult(BaseModel):
    gate_id: str
    status: Literal["PASS", "FAIL", "UNRESOLVED"]
    evidence_hashes: list[str]
    reason: str = Field(min_length=20, max_length=1800)
    conservative_override_used: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_hashes")
    @classmethod
    def normalize_evidence_hashes(cls, value: list[str]) -> list[str]:
        return sorted({normalize_sha256(item) for item in value})


class V4P02ResourceTotals(BaseModel):
    attempts_used: int = Field(ge=0, le=28)
    responses_completed: int = Field(ge=0, le=28)
    failures_recorded: int = Field(ge=0, le=1)
    http_hops_used: int = Field(ge=0, le=109)
    response_body_bytes: int = Field(ge=0, le=8_388_608)
    active_elapsed_milliseconds: int = Field(ge=0, le=1_305_000)
    durable_storage_bytes: int = Field(ge=0, le=33_554_432)

    model_config = ConfigDict(extra="forbid")


class V4P02TerminalResult(BaseModel):
    schema_version: Literal[
        "aurex-v4-p02-source-census-terminal-result-v1"
    ] = "aurex-v4-p02-source-census-terminal-result-v1"
    terminal_kind: Literal["COMPLETE", "REJECT", "TRANSPORT_STOP"]
    terminal_timestamp: datetime
    builder_and_contract_hashes: dict[str, str]
    completed_and_failed_request_ids: dict[str, list[str]]
    decision: str
    execution_gate_results: list[V4P02ExecutionGateResult] = Field(
        min_length=17,
        max_length=17,
    )
    metadata_observation_hashes: list[str] = Field(max_length=1)
    header_observation_hashes: list[str] = Field(max_length=27)
    metadata_gate_hash: str | None
    parsed_and_prohibited_field_manifest: dict[str, list[str]]
    request_journal_hash: str
    storage_projection: V4P02StorageProjection | None
    resource_totals: V4P02ResourceTotals
    selection_and_permission_boundary: dict[str, bool]
    failed_request_id_and_attempt: dict[str, str | int] | None = None
    failure_class_and_message: dict[str, str] | None = None
    partial_byte_count_and_sha256: dict[str, str | int] | None = None
    request_intent_record_hash: str | None = None
    response_headers_if_received: dict[str, str] | None = None
    redirect_chain_if_received: list[V4P02RedirectHop] | None = None
    unconsumed_request_hop_and_byte_budgets: dict[str, int] | None = None
    unreconciled_intent_status: str | None = None
    selects_primary: Literal[False] = False
    authorizes_dataset_payload_gets: Literal[False] = False
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
        "metadata_gate_hash",
        "request_intent_record_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @field_validator(
        "metadata_observation_hashes",
        "header_observation_hashes",
    )
    @classmethod
    def normalize_observation_hashes(cls, value: list[str]) -> list[str]:
        return [normalize_sha256(item) for item in value]

    @field_validator("builder_and_contract_hashes")
    @classmethod
    def normalize_hash_map(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            key: normalize_sha256(item)
            for key, item in sorted(value.items())
        }

    @model_validator(mode="after")
    def validate_terminal_result(self) -> V4P02TerminalResult:
        if [item.gate_id for item in self.execution_gate_results] != (
            V4P02_REQUIRED_GATE_IDS
        ):
            raise ValueError("V4P02 terminal execution gate order changed")
        transport_fields = (
            self.failed_request_id_and_attempt,
            self.failure_class_and_message,
            self.partial_byte_count_and_sha256,
            self.request_intent_record_hash,
            self.response_headers_if_received,
            self.redirect_chain_if_received,
            self.unconsumed_request_hop_and_byte_budgets,
            self.unreconciled_intent_status,
        )
        if self.terminal_kind == "TRANSPORT_STOP":
            if any(item is None for item in transport_fields):
                raise ValueError("V4P02 transport stop evidence is incomplete")
        elif any(item is not None for item in transport_fields):
            raise ValueError("V4P02 non-transport result has transport fields")
        statuses = {item.status for item in self.execution_gate_results}
        if self.terminal_kind == "COMPLETE" and statuses != {"PASS"}:
            raise ValueError("V4P02 complete result requires all gates to pass")
        if self.terminal_kind == "REJECT" and statuses == {"PASS"}:
            raise ValueError("V4P02 reject result requires a non-passing gate")
        if self.selection_and_permission_boundary != V4P02_PERMISSION_BOUNDARY:
            raise ValueError("V4P02 terminal permission boundary changed")
        if self.parsed_and_prohibited_field_manifest != {
            "permitted_observation_fields": (
                V4P02_PERMITTED_OBSERVATION_FIELDS
            ),
            "prohibited_parsed_fields": V4P02_PROHIBITED_PARSED_FIELDS,
        }:
            raise ValueError("V4P02 parsed/prohibited field manifest changed")
        if set(self.builder_and_contract_hashes) != {
            "contract_evidence_hash",
            "contract_builder_hash",
            "runner_contract_hash",
            "discovery_charter_evidence_hash",
            "proposal_register_evidence_hash",
            "proposal_evidence_hash",
        }:
            raise ValueError("V4P02 terminal lineage map changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("V4P02 terminal result hash does not match")
        return self


def build_v4_p02_terminal_result(**values) -> V4P02TerminalResult:
    payload = {
        "schema_version": "aurex-v4-p02-source-census-terminal-result-v1",
        "failed_request_id_and_attempt": None,
        "failure_class_and_message": None,
        "partial_byte_count_and_sha256": None,
        "request_intent_record_hash": None,
        "response_headers_if_received": None,
        "redirect_chain_if_received": None,
        "unconsumed_request_hop_and_byte_budgets": None,
        "unreconciled_intent_status": None,
        "selects_primary": False,
        "authorizes_dataset_payload_gets": False,
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
    return V4P02TerminalResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def unresolved_execution_gates() -> list[V4P02ExecutionGateResult]:
    return [
        V4P02ExecutionGateResult(
            gate_id=gate_id,
            status="UNRESOLVED",
            evidence_hashes=[],
            reason=(
                "This hard gate has not been evidenced by the bounded V4P02 "
                "metadata and dataset-header census."
            ),
        )
        for gate_id in V4P02_REQUIRED_GATE_IDS
    ]


def audit_v4_p02_terminal_result(result: V4P02TerminalResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
