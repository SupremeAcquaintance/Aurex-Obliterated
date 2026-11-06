from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_full_development_runner import (
    PeriodicFlowArchiveEvidence,
    PeriodicFlowPairedMonthEvidence,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorExecutionContract(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-v1"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-v1"
    contract_id: Literal["q1-periodic-flow-successor-execution-contract-v1"] = (
        "q1-periodic-flow-successor-execution-contract-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_SOURCE_BOUND_PRE_NETWORK"] = "FROZEN_SOURCE_BOUND_PRE_NETWORK"
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    parent_protocol_audit_file_sha256: str
    parent_protocol_audit_evidence_hash: str
    inherited_v1_execution_contract_evidence_hash: str
    inherited_v1_runner_source_hash: str
    runner_source_hash: str
    processing_order: Literal[
        "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    ] = "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_ONLY_IF_SPOT_QUALIFIES"
    inherited_transport_primitives: Literal[
        "V1_FULL_GET_MARKERS_RETRY_CHECKSUM_ZIP_STRUCTURAL_PARSER"
    ] = "V1_FULL_GET_MARKERS_RETRY_CHECKSUM_ZIP_STRUCTURAL_PARSER"
    maximum_get_attempts_per_target: Literal[3] = 3
    transient_http_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    retry_delays_seconds: tuple[int, ...] = (5, 20)
    request_timeout_seconds: Literal[300] = 300
    stream_chunk_bytes: Literal[1_048_576] = 1_048_576
    request_user_agent: Literal["Aurex/1.0 (+source-quality-acquisition)"] = (
        "Aurex/1.0 (+source-quality-acquisition)"
    )
    request_accept: Literal["application/zip"] = "application/zip"
    request_accept_encoding: Literal["identity"] = "identity"
    maximum_redirects: Literal[0] = 0
    head_requests_permitted: Literal[False] = False
    range_requests_permitted: Literal[False] = False
    resume_partial_downloads_permitted: Literal[False] = False
    completed_archive_reuse_requires_exact_hash: Literal[True] = True
    checkpoint_write_policy: Literal[
        "ATOMIC_AFTER_EACH_INSPECTION_EXCLUSION_AND_PAIRED_MONTH"
    ] = "ATOMIC_AFTER_EACH_INSPECTION_EXCLUSION_AND_PAIRED_MONTH"
    structural_failure_policy: Literal[
        "RECORD_EXCLUDE_MONTH_CONTINUE_WITH_NEXT_MONTH"
    ] = "RECORD_EXCLUDE_MONTH_CONTINUE_WITH_NEXT_MONTH"
    transport_integrity_failure_policy: Literal[
        "WRITE_TERMINAL_STOP_PRESERVE_CHECKPOINT"
    ] = "WRITE_TERMINAL_STOP_PRESERVE_CHECKPOINT"
    terminal_result_immutable: Literal[True] = True
    required_free_disk_bytes_before_acquisition: Literal[120_000_000_000] = (
        120_000_000_000
    )
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    strategy_or_order_authority: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=10)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_protocol_file_sha256",
        "parent_protocol_evidence_hash",
        "parent_protocol_audit_file_sha256",
        "parent_protocol_audit_evidence_hash",
        "inherited_v1_execution_contract_evidence_hash",
        "inherited_v1_runner_source_hash",
        "runner_source_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> PeriodicFlowSuccessorExecutionContract:
        if (
            self.transient_http_statuses
            != tuple(sorted(set(self.transient_http_statuses)))
            or self.retry_delays_seconds != (5, 20)
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor execution contract changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("Q1 successor execution contract hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-audit-v1"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-audit-v1"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    parent_protocol_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    inherited_transport_lineage_verified: Literal[True] = True
    no_outcome_boundary_verified: Literal[True] = True
    network_requests_made: Literal[0] = 0
    outcomes_accessed: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "parent_protocol_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorExecutionContractAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor execution contract audit hash changed")
        return self


class PeriodicFlowSuccessorExecutionContractV2(
    PeriodicFlowSuccessorExecutionContract
):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-v2"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-v2"
    contract_id: Literal["q1-periodic-flow-successor-execution-contract-v2"] = (
        "q1-periodic-flow-successor-execution-contract-v2"
    )
    status: Literal["FROZEN_POST_BUFFERED_READ_STALL_PRE_NETWORK_RETRY"] = (
        "FROZEN_POST_BUFFERED_READ_STALL_PRE_NETWORK_RETRY"
    )
    parent_v1_contract_file_sha256: str
    parent_v1_contract_evidence_hash: str
    parent_v1_contract_audit_file_sha256: str
    parent_v1_contract_audit_evidence_hash: str
    stalled_request_marker_path: str
    stalled_request_marker_file_sha256: str
    stalled_target_key: Literal["2020-05|USD_M_PERPETUAL"] = (
        "2020-05|USD_M_PERPETUAL"
    )
    stalled_attempt: Literal[1] = 1
    stalled_partial_bytes: int = Field(gt=0, le=5_000_000_000)
    stalled_partial_file_sha256: str
    stalled_response_marker_exists: Literal[False] = False
    stalled_terminal_result_exists: Literal[False] = False
    stalled_attempt_preserved_in_v1_root: Literal[True] = True
    retry_uses_fresh_acquisition_root: Literal[True] = True
    stream_read_method: Literal["HTTP_RESPONSE_READ1"] = "HTTP_RESPONSE_READ1"
    stream_chunk_bytes: Literal[65_536] = 65_536
    idle_read_timeout_seconds: Literal[60] = 60
    total_archive_deadline_seconds: Literal[3_600] = 3_600

    @field_validator(
        "parent_v1_contract_file_sha256",
        "parent_v1_contract_evidence_hash",
        "parent_v1_contract_audit_file_sha256",
        "parent_v1_contract_audit_evidence_hash",
        "stalled_request_marker_file_sha256",
        "stalled_partial_file_sha256",
    )
    @classmethod
    def normalize_v2_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class PeriodicFlowSuccessorExecutionContractAuditV2(
    PeriodicFlowSuccessorExecutionContractAudit
):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-execution-contract-audit-v2"
    ] = "aurex-q1-periodic-flow-successor-execution-contract-audit-v2"
    parent_v1_contract_evidence_hash: str
    stalled_request_marker_file_sha256: str
    stalled_partial_file_sha256: str
    stalled_partial_bytes: int = Field(gt=0, le=5_000_000_000)
    interrupted_buffered_read_reconstructed: Literal[True] = True
    fresh_root_isolation_verified: Literal[True] = True
    wall_clock_bounds_verified: Literal[True] = True

    @field_validator(
        "parent_v1_contract_evidence_hash",
        "stalled_request_marker_file_sha256",
        "stalled_partial_file_sha256",
    )
    @classmethod
    def normalize_v2_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class PeriodicFlowExcludedMonthEvidence(BaseModel):
    month: str
    failed_stage: Literal["SPOT_ARCHIVE", "USDM_ARCHIVE", "PAIRED_CLOCK"]
    failed_product: Literal["SPOT", "USD_M_PERPETUAL", "PAIRED"]
    reason_codes: tuple[str, ...] = Field(min_length=1)
    archive_sha256: str | None = None
    source_mode: Literal["REUSED_LOCAL", "NETWORK_ACQUIRED"] | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("archive_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_exclusion(self) -> PeriodicFlowExcludedMonthEvidence:
        expected_product = {
            "SPOT_ARCHIVE": "SPOT",
            "USDM_ARCHIVE": "USD_M_PERPETUAL",
            "PAIRED_CLOCK": "PAIRED",
        }[self.failed_stage]
        if (
            self.failed_product != expected_product
            or self.reason_codes != tuple(sorted(set(self.reason_codes)))
            or (self.failed_stage == "PAIRED_CLOCK")
            != (self.archive_sha256 is None and self.source_mode is None)
        ):
            raise ValueError("Q1 successor exclusion evidence changed")
        return self


class PeriodicFlowSuccessorCheckpoint(BaseModel):
    schema_version: Literal["aurex-q1-periodic-flow-successor-checkpoint-v1"] = (
        "aurex-q1-periodic-flow-successor-checkpoint-v1"
    )
    checkpoint_id: Literal["q1-periodic-flow-successor-checkpoint-v1"] = (
        "q1-periodic-flow-successor-checkpoint-v1"
    )
    updated_at: datetime
    protocol_evidence_hash: str
    execution_contract_evidence_hash: str
    runner_source_hash: str
    archive_evidence: tuple[PeriodicFlowArchiveEvidence, ...]
    paired_month_evidence: tuple[PeriodicFlowPairedMonthEvidence, ...]
    excluded_month_evidence: tuple[PeriodicFlowExcludedMonthEvidence, ...]
    request_marker_count: int = Field(ge=0, le=144)
    response_marker_count: int = Field(ge=0, le=144)
    request_marker_manifest_hash: str
    cumulative_payload_bytes_received: int = Field(ge=0, le=100_000_000_000)
    total_new_archive_bytes: int = Field(ge=0, le=100_000_000_000)
    total_member_uncompressed_bytes: int = Field(ge=0, le=1_000_000_000_000)
    checkpoint_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "execution_contract_evidence_hash",
        "runner_source_hash",
        "request_marker_manifest_hash",
        "checkpoint_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_checkpoint(self) -> PeriodicFlowSuccessorCheckpoint:
        archive_keys = [item.key for item in self.archive_evidence]
        pair_months = [item.month for item in self.paired_month_evidence]
        excluded_months = [item.month for item in self.excluded_month_evidence]
        passed_archive_keys = {
            item.key for item in self.archive_evidence if item.archive_pass
        }
        if (
            archive_keys != sorted(archive_keys)
            or len(archive_keys) != len(set(archive_keys))
            or pair_months != sorted(pair_months)
            or len(pair_months) != len(set(pair_months))
            or excluded_months != sorted(excluded_months)
            or len(excluded_months) != len(set(excluded_months))
            or set(pair_months) & set(excluded_months)
            or any(
                (month, "SPOT") not in passed_archive_keys
                or (month, "USD_M_PERPETUAL") not in passed_archive_keys
                for month in pair_months
            )
            or any(not item.paired_clock_pass for item in self.paired_month_evidence)
            or self.request_marker_count != self.response_marker_count
            or self.total_new_archive_bytes
            != sum(item.new_archive_bytes for item in self.archive_evidence)
            or self.total_member_uncompressed_bytes
            != sum(item.zip_uncompressed_bytes_total for item in self.archive_evidence)
        ):
            raise ValueError("Q1 successor checkpoint state changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"checkpoint_evidence_hash"})
        )
        if self.checkpoint_evidence_hash != expected:
            raise ValueError("Q1 successor checkpoint hash changed")
        return self


class PeriodicFlowSuccessorAcquisitionResult(BaseModel):
    schema_version: Literal["aurex-q1-periodic-flow-successor-result-v1"] = (
        "aurex-q1-periodic-flow-successor-result-v1"
    )
    result_id: Literal["q1-periodic-flow-successor-result-v1"] = (
        "q1-periodic-flow-successor-result-v1"
    )
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_source_hash: str
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    inspected_archive_count: int = Field(ge=0, le=74)
    qualified_paired_month_count: int = Field(ge=0, le=37)
    excluded_month_count: int = Field(ge=0, le=37)
    completed_month_count: int = Field(ge=0, le=37)
    qualified_months_by_year: dict[str, int]
    qualified_quarter_count: int = Field(ge=0, le=16)
    request_marker_count: int = Field(ge=0, le=144)
    cumulative_payload_bytes_received: int = Field(ge=0, le=100_000_000_000)
    total_new_archive_bytes: int = Field(ge=0, le=100_000_000_000)
    hard_failure_target_key: str | None = None
    hard_failure_reason: str | None = None
    decision: Literal[
        "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL",
        "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED",
        "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_SUCCESSOR_PAIRED_MEASUREMENT_PROTOCOL_ONLY",
        "NONE_SOURCE_SUFFICIENCY_FAILED",
        "NONE_ACQUISITION_INTEGRITY_FAILED",
    ]
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    features_calculated: tuple[str, ...] = ()
    parameters_defined: tuple[str, ...] = ()
    returns_calculated: tuple[str, ...] = ()
    validation_accessed: Literal[False] = False
    holdout_accessed: Literal[False] = False
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=10)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "runner_source_hash",
        "checkpoint_file_sha256",
        "checkpoint_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> PeriodicFlowSuccessorAcquisitionResult:
        hard_failed = self.hard_failure_target_key is not None
        sufficient = (
            not hard_failed
            and self.completed_month_count == 37
            and self.qualified_paired_month_count >= 30
            and all(
                self.qualified_months_by_year.get(str(year), 0) >= 6
                for year in range(2020, 2024)
            )
            and self.qualified_quarter_count == 16
        )
        expected_decision = (
            "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
            if hard_failed
            else (
                "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
                if sufficient
                else "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED"
            )
        )
        expected_authorization = {
            "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED": (
                "NONE_ACQUISITION_INTEGRITY_FAILED"
            ),
            "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL": (
                "AUTHORIZE_Q1_SUCCESSOR_PAIRED_MEASUREMENT_PROTOCOL_ONLY"
            ),
            "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED": (
                "NONE_SOURCE_SUFFICIENCY_FAILED"
            ),
        }[expected_decision]
        if (
            self.completed_month_count
            != self.qualified_paired_month_count + self.excluded_month_count
            or hard_failed != (self.hard_failure_reason is not None)
            or self.decision != expected_decision
            or self.next_authorization != expected_authorization
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 successor acquisition result changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 successor acquisition result hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    data = provisional.model_dump()
    data[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(data)


def build_execution_contract(**values) -> PeriodicFlowSuccessorExecutionContract:
    payload = dict(values)
    payload["transient_http_statuses"] = tuple(
        sorted(set(payload.get("transient_http_statuses", (408, 425, 429, 500, 502, 503, 504))))
    )
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowSuccessorExecutionContract, "contract_evidence_hash", payload)


def build_execution_contract_audit(
    **values,
) -> PeriodicFlowSuccessorExecutionContractAudit:
    return _build(
        PeriodicFlowSuccessorExecutionContractAudit,
        "audit_evidence_hash",
        values,
    )


def build_execution_contract_v2(
    **values,
) -> PeriodicFlowSuccessorExecutionContractV2:
    payload = dict(values)
    payload["transient_http_statuses"] = tuple(
        sorted(set(payload.get("transient_http_statuses", (408, 425, 429, 500, 502, 503, 504))))
    )
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowSuccessorExecutionContractV2,
        "contract_evidence_hash",
        payload,
    )


def build_execution_contract_audit_v2(
    **values,
) -> PeriodicFlowSuccessorExecutionContractAuditV2:
    return _build(
        PeriodicFlowSuccessorExecutionContractAuditV2,
        "audit_evidence_hash",
        values,
    )


def build_checkpoint(**values) -> PeriodicFlowSuccessorCheckpoint:
    payload = dict(values)
    payload["archive_evidence"] = tuple(
        sorted(payload["archive_evidence"], key=lambda item: item.key)
    )
    payload["paired_month_evidence"] = tuple(
        sorted(payload["paired_month_evidence"], key=lambda item: item.month)
    )
    payload["excluded_month_evidence"] = tuple(
        sorted(payload["excluded_month_evidence"], key=lambda item: item.month)
    )
    return _build(PeriodicFlowSuccessorCheckpoint, "checkpoint_evidence_hash", payload)


def build_acquisition_result(**values) -> PeriodicFlowSuccessorAcquisitionResult:
    payload = dict(values)
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    hard_failed = payload.get("hard_failure_target_key") is not None
    sufficient = (
        not hard_failed
        and payload["completed_month_count"] == 37
        and payload["qualified_paired_month_count"] >= 30
        and all(
            payload["qualified_months_by_year"].get(str(year), 0) >= 6
            for year in range(2020, 2024)
        )
        and payload["qualified_quarter_count"] == 16
    )
    payload["decision"] = (
        "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        if hard_failed
        else (
            "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
            if sufficient
            else "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED"
        )
    )
    payload["next_authorization"] = {
        "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED": (
            "NONE_ACQUISITION_INTEGRITY_FAILED"
        ),
        "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL": (
            "AUTHORIZE_Q1_SUCCESSOR_PAIRED_MEASUREMENT_PROTOCOL_ONLY"
        ),
        "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED": (
            "NONE_SOURCE_SUFFICIENCY_FAILED"
        ),
    }[payload["decision"]]
    return _build(PeriodicFlowSuccessorAcquisitionResult, "result_evidence_hash", payload)


def audit_hash(model: BaseModel, hash_field: str) -> bool:
    return getattr(model, hash_field) == universe_evidence_hash(
        model.model_dump(exclude={hash_field})
    )
