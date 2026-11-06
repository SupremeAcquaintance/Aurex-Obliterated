from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    FULL_DEVELOPMENT_MONTHS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

RUNNER_SOURCE_PATHS = (
    Path("src/aurex/backtest_engine/periodic_flow_full_development_runner.py"),
    Path("scripts/run_periodic_flow_full_development_acquisition.py"),
)
EXECUTION_CONTRACT_SCHEMA = (
    "aurex-q1-periodic-flow-full-development-execution-contract-v1"
)
EXECUTION_CONTRACT_AUDIT_SCHEMA = (
    "aurex-q1-periodic-flow-full-development-execution-contract-audit-v1"
)
CHECKPOINT_SCHEMA = "aurex-q1-periodic-flow-full-development-checkpoint-v1"
RESULT_SCHEMA = "aurex-q1-periodic-flow-full-development-result-v1"
PASS_DECISION = "PERMIT_Q1_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
FAIL_DECISION = "STOP_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_FAILED"
PASS_AUTHORIZATION = "AUTHORIZE_Q1_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"
FAIL_AUTHORIZATION = "NONE_ACQUISITION_FAILED"


def source_contract_hash(project_root: Path, paths: tuple[Path, ...]) -> str:
    import hashlib

    return universe_evidence_hash(
        {
            "source_files": {
                path.as_posix(): hashlib.sha256(
                    (project_root / path).read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def month_bounds_ms(month: str) -> tuple[int, int, int]:
    if month not in FULL_DEVELOPMENT_MONTHS:
        raise ValueError("Q1 full-development month is outside the frozen partition")
    year, month_number = (int(value) for value in month.split("-"))
    start = datetime(year, month_number, 1, tzinfo=UTC)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=UTC)
    expected_minutes = monthrange(year, month_number)[1] * 24 * 60
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000), expected_minutes


class PeriodicFlowExecutionContract(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-execution-contract-v1"
    ] = EXECUTION_CONTRACT_SCHEMA
    contract_id: Literal[
        "q1-periodic-flow-full-development-execution-contract-v1"
    ] = "q1-periodic-flow-full-development-execution-contract-v1"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_EXECUTION_NO_NETWORK_REQUESTS"] = (
        "FROZEN_PRE_EXECUTION_NO_NETWORK_REQUESTS"
    )
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    parent_protocol_audit_file_sha256: str
    parent_protocol_audit_evidence_hash: str
    builder_contract_hash: str
    runner_source_hash: str
    processing_order: Literal["CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_RAW"] = (
        "CHRONOLOGICAL_MONTH_SPOT_THEN_USDM_RAW"
    )
    processing_manifest_hash: str
    halt_on_first_target_or_pair_failure: Literal[True] = True
    later_targets_after_failure_permitted: Literal[False] = False
    reuse_failure_policy: Literal["FAIL_CLOSED_NO_NETWORK_FALLBACK"] = (
        "FAIL_CLOSED_NO_NETWORK_FALLBACK"
    )
    network_methods: tuple[Literal["GET"], ...] = ("GET",)
    head_requests_permitted: Literal[False] = False
    range_requests_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    content_encoding: Literal["identity"] = "identity"
    absent_content_length_permitted: Literal[True] = True
    invalid_or_oversized_content_length_policy: Literal["FAIL_CLOSED"] = (
        "FAIL_CLOSED"
    )
    transient_http_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    integrity_failure_retry_permitted: Literal[False] = False
    request_marker_before_socket_open_required: Literal[True] = True
    response_marker_after_every_attempt_required: Literal[True] = True
    unmatched_request_policy: Literal[
        "COUNT_ATTEMPT_RECORD_INTERRUPTION_DELETE_PARTIAL"
    ] = "COUNT_ATTEMPT_RECORD_INTERRUPTION_DELETE_PARTIAL"
    verified_destination_recovery_policy: Literal[
        "RECOVER_ONLY_EXACT_HASH_AFTER_UNMATCHED_REQUEST"
    ] = "RECOVER_ONLY_EXACT_HASH_AFTER_UNMATCHED_REQUEST"
    unmatched_response_policy: Literal["FAIL_CLOSED"] = "FAIL_CLOSED"
    partial_archive_policy: Literal["NEVER_RESUME_NEVER_PARSE"] = (
        "NEVER_RESUME_NEVER_PARSE"
    )
    checkpoint_policy: Literal[
        "ATOMIC_AFTER_EACH_QUALIFIED_ARCHIVE_AND_PAIRED_MONTH"
    ] = "ATOMIC_AFTER_EACH_QUALIFIED_ARCHIVE_AND_PAIRED_MONTH"
    checkpoint_resume_policy: Literal[
        "EXACT_PROTOCOL_CONTRACT_HASH_AND_ARCHIVE_REVALIDATION"
    ] = "EXACT_PROTOCOL_CONTRACT_HASH_AND_ARCHIVE_REVALIDATION"
    byte_accounting_policy: Literal[
        "COUNT_ALL_RECEIVED_BYTES_AND_FINAL_NEW_ARCHIVE_BYTES"
    ] = "COUNT_ALL_RECEIVED_BYTES_AND_FINAL_NEW_ARCHIVE_BYTES"
    preflight_free_disk_policy: Literal[
        "REQUIRE_MAX_NEW_BYTES_PLUS_MINIMUM_REMAINING"
    ] = "REQUIRE_MAX_NEW_BYTES_PLUS_MINIMUM_REMAINING"
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
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
        "builder_contract_hash",
        "runner_source_hash",
        "processing_manifest_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> PeriodicFlowExecutionContract:
        if (
            self.transient_http_statuses
            != tuple(sorted(set(self.transient_http_statuses)))
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 execution contract set ordering changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("Q1 execution contract hash changed")
        return self


class PeriodicFlowExecutionContractAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-execution-contract-audit-v1"
    ] = EXECUTION_CONTRACT_AUDIT_SCHEMA
    audit_id: Literal[
        "q1-periodic-flow-full-development-execution-contract-audit-v1"
    ] = "q1-periodic-flow-full-development-execution-contract-audit-v1"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    parent_protocol_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    network_requests_made: Literal[0] = 0
    payload_bytes_received: Literal[0] = 0
    prices_or_quantities_parsed: Literal[0] = 0
    outcomes_accessed: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_acquisition_execution_only: Literal[True] = True
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
    def validate_audit(self) -> PeriodicFlowExecutionContractAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 execution-contract audit hash changed")
        return self


class PeriodicFlowArchiveEvidence(BaseModel):
    month: str
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    family: Literal["aggTrades", "trades"]
    source_mode: Literal["REUSED_LOCAL", "NETWORK_ACQUIRED"]
    archive_url: str
    local_path: str
    archive_bytes: int = Field(gt=0, le=5_000_000_000)
    archive_sha256: str
    checksum_verified: Literal[True] = True
    zip_member_count: int = Field(ge=1, le=2)
    selected_member_name: str
    zip_compressed_bytes_total: int = Field(gt=0)
    zip_uncompressed_bytes_total: int = Field(gt=0, le=60_000_000_000)
    selected_member_uncompressed_bytes: int = Field(gt=0, le=30_000_000_000)
    zip_crc_verified: Literal[True] = True
    duplicate_member_name: str | None = None
    canonical_member_sha256: str | None = None
    duplicate_member_sha256: str | None = None
    duplicate_member_byte_identical: bool | None = None
    column_count: Literal[6, 8]
    header_present: bool
    row_count: int = Field(gt=0)
    first_timestamp_ms: int = Field(gt=0)
    last_timestamp_ms: int = Field(gt=0)
    unique_minute_count: int = Field(gt=0)
    expected_minute_count: int = Field(gt=0)
    minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    maximum_event_gap_minutes: int = Field(ge=0)
    first_primary_id: int = Field(ge=0)
    last_primary_id: int = Field(ge=0)
    primary_id_non_increasing_count: int = Field(ge=0)
    primary_id_duplicate_count: int = Field(ge=0)
    primary_id_forward_gap_count: int = Field(ge=0)
    primary_id_skipped_count: int = Field(ge=0)
    primary_id_skipped_fraction: Decimal = Field(ge=0, le=1)
    maximum_single_primary_id_skip_count: int = Field(ge=0)
    first_raw_trade_id: int | None = Field(default=None, ge=0)
    last_raw_trade_id: int | None = Field(default=None, ge=0)
    raw_range_gap_count: int | None = Field(default=None, ge=0)
    raw_range_non_increasing_count: int | None = Field(default=None, ge=0)
    timestamp_regression_count: int = Field(ge=0)
    buyer_maker_values_observed: tuple[bool, ...]
    payload_get_attempt_count: int = Field(ge=0, le=3)
    new_archive_bytes: int = Field(ge=0, le=5_000_000_000)
    archive_pass: bool
    reason_codes: tuple[str, ...]
    parsed_numeric_fields: tuple[str, ...]
    excluded_numeric_fields: tuple[str, ...] = (
        "price",
        "quantity",
        "quote_quantity",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("archive_sha256", "canonical_member_sha256", "duplicate_member_sha256")
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> PeriodicFlowArchiveEvidence:
        start_ms, end_ms, expected_minutes = month_bounds_ms(self.month)
        is_spot = self.product == "SPOT"
        expected_family = "aggTrades" if is_spot else "trades"
        expected_columns = 8 if is_spot else 6
        expected_parsed = (
            ("aggregate_trade_id", "first_trade_id", "last_trade_id", "timestamp")
            if is_spot
            else ("timestamp", "trade_id")
        )
        if (
            self.family != expected_family
            or self.column_count != expected_columns
            or self.expected_minute_count != expected_minutes
            or not start_ms <= self.first_timestamp_ms <= self.last_timestamp_ms < end_ms
            or self.minute_coverage_fraction
            != Decimal(self.unique_minute_count) / Decimal(expected_minutes)
            or self.zip_compressed_bytes_total > self.archive_bytes
            or self.zip_uncompressed_bytes_total
            > self.zip_compressed_bytes_total * 100
            or self.parsed_numeric_fields != expected_parsed
            or self.excluded_numeric_fields != ("price", "quantity", "quote_quantity")
            or self.reason_codes != tuple(sorted(set(self.reason_codes)))
        ):
            raise ValueError("Q1 archive structural evidence changed")
        if self.source_mode == "REUSED_LOCAL":
            if self.payload_get_attempt_count != 0 or self.new_archive_bytes != 0:
                raise ValueError("Q1 reused archive has network evidence")
        elif (
            self.payload_get_attempt_count == 0
            or self.new_archive_bytes != self.archive_bytes
        ):
            raise ValueError("Q1 network archive request accounting changed")
        span = self.last_primary_id - self.first_primary_id + 1
        expected_skip_fraction = (
            Decimal(self.primary_id_skipped_count) / Decimal(span)
            if span > 0
            else Decimal(0)
        )
        if self.primary_id_skipped_fraction != expected_skip_fraction:
            raise ValueError("Q1 primary-ID skipped fraction changed")
        special = is_spot and self.month == "2021-12"
        duplicate_fields = (
            self.duplicate_member_name,
            self.canonical_member_sha256,
            self.duplicate_member_sha256,
            self.duplicate_member_byte_identical,
        )
        if special:
            if (
                self.zip_member_count != 2
                or any(value is None for value in duplicate_fields)
                or self.duplicate_member_byte_identical is not True
                or self.canonical_member_sha256 != self.duplicate_member_sha256
            ):
                raise ValueError("Q1 2021-12 duplicate-member proof changed")
        elif self.zip_member_count != 1 or any(value is not None for value in duplicate_fields):
            raise ValueError("Q1 ordinary ZIP member matrix changed")
        reasons = []
        if self.row_count < 100_000:
            reasons.append("ROW_COUNT_BELOW_100000")
        if self.minute_coverage_fraction < Decimal("0.99"):
            reasons.append("MINUTE_COVERAGE_BELOW_0_99")
        if self.maximum_event_gap_minutes > 15:
            reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
        if self.primary_id_non_increasing_count:
            reasons.append("PRIMARY_ID_NOT_STRICTLY_INCREASING")
        if self.primary_id_duplicate_count:
            reasons.append("PRIMARY_ID_DUPLICATE")
        if self.timestamp_regression_count:
            reasons.append("TIMESTAMP_REGRESSION")
        if self.buyer_maker_values_observed != (False, True):
            reasons.append("BUYER_MAKER_DOMAIN_INCOMPLETE")
        if is_spot:
            if self.primary_id_forward_gap_count:
                reasons.append("SPOT_AGGREGATE_ID_GAP")
            if self.raw_range_gap_count:
                reasons.append("SPOT_RAW_RANGE_GAP")
            if self.raw_range_non_increasing_count:
                reasons.append("SPOT_RAW_RANGE_OVERLAP_OR_REGRESSION")
            if (
                self.first_raw_trade_id is None
                or self.last_raw_trade_id is None
                or self.primary_id_skipped_count
                or self.maximum_single_primary_id_skip_count
            ):
                raise ValueError("Q1 Spot ID evidence shape changed")
        else:
            if any(
                value is not None
                for value in (
                    self.first_raw_trade_id,
                    self.last_raw_trade_id,
                    self.raw_range_gap_count,
                    self.raw_range_non_increasing_count,
                )
            ):
                raise ValueError("Q1 raw-trades ID evidence shape changed")
            if self.primary_id_skipped_fraction > Decimal("0.001"):
                reasons.append("SKIPPED_TRADE_ID_FRACTION_EXCEEDS_0_001")
            if self.maximum_single_primary_id_skip_count > 100:
                reasons.append("SINGLE_SKIPPED_TRADE_ID_COUNT_EXCEEDS_100")
        expected_reasons = tuple(sorted(reasons))
        if self.reason_codes != expected_reasons or self.archive_pass != (not reasons):
            raise ValueError("Q1 archive decision changed")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.month, self.product


class PeriodicFlowPairedMonthEvidence(BaseModel):
    month: str
    spot_unique_minute_count: int = Field(gt=0)
    raw_unique_minute_count: int = Field(gt=0)
    paired_unique_minute_count: int = Field(gt=0)
    expected_minute_count: int = Field(gt=0)
    paired_minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    paired_clock_pass: bool
    reason_codes: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_pair(self) -> PeriodicFlowPairedMonthEvidence:
        _, _, expected = month_bounds_ms(self.month)
        reasons = []
        if self.paired_minute_coverage_fraction < Decimal("0.99"):
            reasons.append("PAIRED_MINUTE_COVERAGE_BELOW_0_99")
        if (
            self.expected_minute_count != expected
            or self.paired_unique_minute_count
            > min(self.spot_unique_minute_count, self.raw_unique_minute_count)
            or self.paired_minute_coverage_fraction
            != Decimal(self.paired_unique_minute_count) / Decimal(expected)
            or self.reason_codes != tuple(sorted(reasons))
            or self.paired_clock_pass != (not reasons)
        ):
            raise ValueError("Q1 paired-month evidence changed")
        return self


class PeriodicFlowAcquisitionCheckpoint(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-checkpoint-v1"
    ] = CHECKPOINT_SCHEMA
    checkpoint_id: Literal[
        "q1-periodic-flow-full-development-checkpoint-v1"
    ] = "q1-periodic-flow-full-development-checkpoint-v1"
    updated_at: datetime
    protocol_evidence_hash: str
    execution_contract_evidence_hash: str
    runner_source_hash: str
    archive_evidence: tuple[PeriodicFlowArchiveEvidence, ...]
    paired_month_evidence: tuple[PeriodicFlowPairedMonthEvidence, ...]
    request_marker_count: int = Field(ge=0, le=177)
    response_marker_count: int = Field(ge=0, le=177)
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
    def validate_checkpoint(self) -> PeriodicFlowAcquisitionCheckpoint:
        archive_keys = [item.key for item in self.archive_evidence]
        pair_months = [item.month for item in self.paired_month_evidence]
        archived = set(archive_keys)
        if (
            archive_keys != sorted(archive_keys)
            or len(archive_keys) != len(set(archive_keys))
            or pair_months != sorted(pair_months)
            or len(pair_months) != len(set(pair_months))
            or any(
                (month, "SPOT") not in archived
                or (month, "USD_M_PERPETUAL") not in archived
                for month in pair_months
            )
            or any(not item.archive_pass for item in self.archive_evidence)
            or any(not item.paired_clock_pass for item in self.paired_month_evidence)
            or self.request_marker_count != self.response_marker_count
            or self.total_new_archive_bytes
            != sum(item.new_archive_bytes for item in self.archive_evidence)
            or self.total_member_uncompressed_bytes
            != sum(item.zip_uncompressed_bytes_total for item in self.archive_evidence)
        ):
            raise ValueError("Q1 acquisition checkpoint state changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"checkpoint_evidence_hash"})
        )
        if self.checkpoint_evidence_hash != expected:
            raise ValueError("Q1 acquisition checkpoint hash changed")
        return self


class PeriodicFlowAcquisitionResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-result-v1"
    ] = RESULT_SCHEMA
    result_id: Literal["q1-periodic-flow-full-development-result-v1"] = (
        "q1-periodic-flow-full-development-result-v1"
    )
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_source_hash: str
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    completed_archive_count: int = Field(ge=0, le=96)
    completed_paired_month_count: int = Field(ge=0, le=48)
    request_marker_count: int = Field(ge=0, le=177)
    cumulative_payload_bytes_received: int = Field(ge=0, le=100_000_000_000)
    total_new_archive_bytes: int = Field(ge=0, le=100_000_000_000)
    failed_target_key: str | None = None
    failure_reason: str | None = None
    decision: Literal[
        "PERMIT_Q1_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL",
        "STOP_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY",
        "NONE_ACQUISITION_FAILED",
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
    authorizes_pine: Literal[False] = False
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
    def validate_result(self) -> PeriodicFlowAcquisitionResult:
        passed = self.completed_archive_count == 96 and self.completed_paired_month_count == 48
        if (
            self.decision != (PASS_DECISION if passed else FAIL_DECISION)
            or self.next_authorization
            != (PASS_AUTHORIZATION if passed else FAIL_AUTHORIZATION)
            or (passed and (self.failed_target_key is not None or self.failure_reason is not None))
            or (not passed and (not self.failed_target_key or not self.failure_reason))
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 acquisition result authority changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 acquisition result hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_execution_contract(**values) -> PeriodicFlowExecutionContract:
    payload = dict(values)
    payload["transient_http_statuses"] = tuple(
        sorted(set(payload.get("transient_http_statuses", (408, 425, 429, 500, 502, 503, 504))))
    )
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowExecutionContract, "contract_evidence_hash", payload)


def build_execution_contract_audit(**values) -> PeriodicFlowExecutionContractAudit:
    return _build(PeriodicFlowExecutionContractAudit, "audit_evidence_hash", values)


def build_checkpoint(**values) -> PeriodicFlowAcquisitionCheckpoint:
    payload = dict(values)
    payload["archive_evidence"] = tuple(
        sorted(payload["archive_evidence"], key=lambda item: item.key)
    )
    payload["paired_month_evidence"] = tuple(
        sorted(payload["paired_month_evidence"], key=lambda item: item.month)
    )
    return _build(PeriodicFlowAcquisitionCheckpoint, "checkpoint_evidence_hash", payload)


def build_acquisition_result(**values) -> PeriodicFlowAcquisitionResult:
    payload = dict(values)
    passed = (
        payload["completed_archive_count"] == 96
        and payload["completed_paired_month_count"] == 48
    )
    payload["decision"] = PASS_DECISION if passed else FAIL_DECISION
    payload["next_authorization"] = PASS_AUTHORIZATION if passed else FAIL_AUTHORIZATION
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowAcquisitionResult, "result_evidence_hash", payload)


def audit_execution_contract(contract: PeriodicFlowExecutionContract) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )


def audit_execution_contract_audit(audit: PeriodicFlowExecutionContractAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
