from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_nfci_raw_pilot import S1NfciSnapshotSummary
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_NFCI_EXECUTION_NEXT = "AUTHORIZE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
S1_NFCI_ACQUISITION_PASS = "PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
S1_NFCI_ACQUISITION_STOP = "STOP_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION_FAILED"
S1_NFCI_ACQUISITION_NEXT = "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_PROTOCOL_ONLY"


class S1NfciAcquisitionAttempt(BaseModel):
    sequence: int = Field(ge=1, le=281)
    attempt: int = Field(ge=1, le=3)
    requested_at: datetime
    completed_at: datetime
    status_code: int | None = Field(default=None, ge=100, le=599)
    final_url: str | None = None
    final_host: str | None = None
    content_type: str | None = None
    bytes_received: int = Field(ge=0, le=200000)
    outcome: Literal["COMPLETE", "TRANSIENT_FAILURE", "PERMANENT_FAILURE"]
    error_type: str | None = None
    error_message: str | None = None
    request_marker_path: str = Field(min_length=10)
    request_marker_sha256: str
    response_marker_path: str = Field(min_length=10)
    response_marker_sha256: str
    attempt_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("requested_at", "completed_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "request_marker_sha256",
        "response_marker_sha256",
        "attempt_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S1NfciAcquisitionAttempt:
        if self.completed_at < self.requested_at:
            raise ValueError("S1 NFCI attempt completion precedes request")
        if self.outcome == "COMPLETE" and (
            self.status_code != 200
            or self.bytes_received == 0
            or self.error_type is not None
        ):
            raise ValueError("Complete S1 NFCI attempt is incomplete")
        if self.outcome != "COMPLETE" and not self.error_type:
            raise ValueError("Failed S1 NFCI attempt requires an error type")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"attempt_evidence_hash"})
        )
        if self.attempt_evidence_hash != expected:
            raise ValueError("S1 NFCI attempt evidence hash changed")
        return self


class S1NfciAcquisitionTargetEvidence(BaseModel):
    sequence: int = Field(ge=1, le=281)
    target_id: str = Field(min_length=10)
    vintage_date: date
    outcome: Literal["COMPLETE", "FAILED"]
    attempts: tuple[S1NfciAcquisitionAttempt, ...] = Field(min_length=1, max_length=3)
    raw_path: str | None = None
    raw_file_sha256: str | None = None
    raw_file_bytes: int = Field(ge=0, le=200000)
    summary: S1NfciSnapshotSummary | None = None
    failure_gate: str | None = None
    target_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("raw_file_sha256", "target_evidence_hash")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> S1NfciAcquisitionTargetEvidence:
        attempt_numbers = tuple(item.attempt for item in self.attempts)
        if attempt_numbers != tuple(range(1, len(self.attempts) + 1)):
            raise ValueError("S1 NFCI target attempt sequence changed")
        if any(item.sequence != self.sequence for item in self.attempts):
            raise ValueError("S1 NFCI attempt target sequence changed")
        if self.outcome == "COMPLETE" and (
            self.attempts[-1].outcome != "COMPLETE"
            or self.raw_path is None
            or self.raw_file_sha256 is None
            or self.raw_file_bytes == 0
            or self.summary is None
            or self.failure_gate is not None
        ):
            raise ValueError("Complete S1 NFCI target evidence is incomplete")
        if self.outcome == "FAILED" and not self.failure_gate:
            raise ValueError("Failed S1 NFCI target requires a failure gate")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"target_evidence_hash"})
        )
        if self.target_evidence_hash != expected:
            raise ValueError("S1 NFCI target evidence hash changed")
        return self


class S1NfciAcquisitionCheckpoint(BaseModel):
    schema_version: Literal["aurex-s1-nfci-acquisition-checkpoint-v1"] = (
        "aurex-s1-nfci-acquisition-checkpoint-v1"
    )
    checkpoint_id: Literal["s1-nfci-acquisition-checkpoint-v1"] = (
        "s1-nfci-acquisition-checkpoint-v1"
    )
    started_at: datetime
    updated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_addendum_file_sha256: str
    execution_addendum_evidence_hash: str
    runner_contract_hash: str
    target_evidence: tuple[S1NfciAcquisitionTargetEvidence, ...] = ()
    classified_target_count: int = Field(ge=0, le=281)
    complete_target_count: int = Field(ge=0, le=281)
    failed_target_count: int = Field(ge=0, le=1)
    get_attempt_count: int = Field(ge=0, le=843)
    network_body_bytes: int = Field(ge=0, le=168600000)
    persisted_raw_bytes: int = Field(ge=0, le=56200000)
    next_sequence: int | None = Field(default=None, ge=1, le=281)
    terminal: bool
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    orders_submitted: Literal[0] = 0
    checkpoint_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("started_at", "updated_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_addendum_file_sha256",
        "execution_addendum_evidence_hash",
        "runner_contract_hash",
        "checkpoint_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_checkpoint(self) -> S1NfciAcquisitionCheckpoint:
        sequences = tuple(item.sequence for item in self.target_evidence)
        if sequences != tuple(range(1, len(sequences) + 1)):
            raise ValueError("S1 NFCI checkpoint target sequence changed")
        if self.classified_target_count != len(self.target_evidence):
            raise ValueError("S1 NFCI classified count changed")
        if self.complete_target_count != sum(
            item.outcome == "COMPLETE" for item in self.target_evidence
        ):
            raise ValueError("S1 NFCI complete count changed")
        if self.failed_target_count != sum(
            item.outcome == "FAILED" for item in self.target_evidence
        ):
            raise ValueError("S1 NFCI failed count changed")
        if self.get_attempt_count != sum(len(item.attempts) for item in self.target_evidence):
            raise ValueError("S1 NFCI attempt count changed")
        if self.persisted_raw_bytes != sum(
            item.raw_file_bytes for item in self.target_evidence
        ):
            raise ValueError("S1 NFCI persisted byte count changed")
        expected_next = (
            None
            if self.terminal or self.classified_target_count == 281
            else self.classified_target_count + 1
        )
        if self.next_sequence != expected_next:
            raise ValueError("S1 NFCI checkpoint next sequence changed")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 NFCI checkpoint cannot contain BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"checkpoint_evidence_hash"})
        )
        if self.checkpoint_evidence_hash != expected:
            raise ValueError("S1 NFCI checkpoint evidence hash changed")
        return self


class S1NfciAcquisitionExecutionAddendum(BaseModel):
    schema_version: Literal["aurex-s1-nfci-acquisition-execution-addendum-v1"] = (
        "aurex-s1-nfci-acquisition-execution-addendum-v1"
    )
    addendum_id: Literal["s1-nfci-acquisition-execution-addendum-v1"] = (
        "s1-nfci-acquisition-execution-addendum-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    evidence_root: Literal[
        "data/evidence/source_snapshots/s1_nfci_full_acquisition_v1"
    ] = "data/evidence/source_snapshots/s1_nfci_full_acquisition_v1"
    evidence_root_was_absent_or_empty: Literal[True] = True
    free_disk_bytes_observed: int = Field(ge=250000000)
    target_count: Literal[281] = 281
    maximum_get_attempts: Literal[843] = 843
    maximum_total_payload_bytes: Literal[56200000] = 56_200_000
    synthetic_test_ids: tuple[str, ...] = Field(min_length=1)
    authorizes_network_acquisition: Literal[True] = True
    authorizes_macro_source_values_only: Literal[True] = True
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
    ] = S1_NFCI_EXECUTION_NEXT
    addendum_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "addendum_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_addendum(self) -> S1NfciAcquisitionExecutionAddendum:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"addendum_evidence_hash"})
        )
        if self.addendum_evidence_hash != expected:
            raise ValueError("S1 NFCI execution addendum hash changed")
        return self


class S1NfciAcquisitionExecutionAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-acquisition-execution-audit-v1"] = (
        "aurex-s1-nfci-acquisition-execution-audit-v1"
    )
    audit_id: Literal["s1-nfci-acquisition-execution-audit-v1"] = (
        "s1-nfci-acquisition-execution-audit-v1"
    )
    audited_at: datetime
    addendum_file_sha256: str
    addendum_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    payload_bytes_observed: Literal[0] = 0
    decision: Literal["PASS_S1_NFCI_EXECUTION_CONTRACT_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_EXECUTION_CONTRACT_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
    ] = S1_NFCI_EXECUTION_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "addendum_file_sha256",
        "addendum_evidence_hash",
        "protocol_evidence_hash",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciAcquisitionExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI execution audit hash changed")
        return self


class S1NfciFullAcquisitionResult(BaseModel):
    schema_version: Literal["aurex-s1-nfci-full-acquisition-result-v1"] = (
        "aurex-s1-nfci-full-acquisition-result-v1"
    )
    result_id: Literal["s1-nfci-full-acquisition-result-v1"] = (
        "s1-nfci-full-acquisition-result-v1"
    )
    completed_at: datetime
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    protocol_evidence_hash: str
    execution_addendum_evidence_hash: str
    runner_contract_hash: str
    target_evidence: tuple[S1NfciAcquisitionTargetEvidence, ...] = Field(min_length=1)
    gates: tuple[S1SourceGate, ...] = Field(min_length=1)
    classified_target_count: int = Field(ge=1, le=281)
    complete_target_count: int = Field(ge=0, le=281)
    failed_target_count: int = Field(ge=0, le=1)
    get_attempt_count: int = Field(ge=1, le=843)
    network_body_bytes: int = Field(ge=0, le=168600000)
    persisted_raw_bytes: int = Field(ge=0, le=56200000)
    distinct_payload_hash_count: int = Field(ge=0, le=281)
    decision: Literal[
        "PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION",
        "STOP_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_PROTOCOL_ONLY",
        "NONE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION_FAILED",
    ]
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
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
        "checkpoint_file_sha256",
        "checkpoint_evidence_hash",
        "protocol_evidence_hash",
        "execution_addendum_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S1NfciFullAcquisitionResult:
        if self.classified_target_count != len(self.target_evidence):
            raise ValueError("S1 NFCI result classified count changed")
        failed = any(gate.status == "FAIL" for gate in self.gates)
        if self.decision != (
            S1_NFCI_ACQUISITION_STOP if failed else S1_NFCI_ACQUISITION_PASS
        ):
            raise ValueError("S1 NFCI result decision does not match gates")
        expected_next = (
            "NONE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION_FAILED"
            if failed
            else S1_NFCI_ACQUISITION_NEXT
        )
        if self.next_authorization != expected_next:
            raise ValueError("S1 NFCI result next authorization changed")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 NFCI result cannot contain BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 NFCI result evidence hash changed")
        return self


class S1NfciFullAcquisitionAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-full-acquisition-audit-v1"] = (
        "aurex-s1-nfci-full-acquisition-audit-v1"
    )
    audit_id: Literal["s1-nfci-full-acquisition-audit-v1"] = (
        "s1-nfci-full-acquisition-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    raw_file_count: Literal[281] = 281
    raw_file_sha256: dict[str, str]
    aggregate_raw_bytes: int = Field(ge=1, le=56200000)
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_NFCI_FULL_ACQUISITION_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_FULL_ACQUISITION_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_PROTOCOL_ONLY"
    ] = S1_NFCI_ACQUISITION_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "checkpoint_file_sha256",
        "checkpoint_evidence_hash",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("raw_file_sha256")
    @classmethod
    def normalize_raw_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: normalize_sha256(digest) for key, digest in sorted(value.items())}

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciFullAcquisitionAudit:
        if len(self.raw_file_sha256) != self.raw_file_count:
            raise ValueError("S1 NFCI acquisition audit raw-file count changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI acquisition audit evidence hash changed")
        return self
