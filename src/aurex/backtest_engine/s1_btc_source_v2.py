from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_btc_source_acquisition import S1BtcSourceTarget
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_1_TIMING_NEXT = "AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION_PROTOCOL_ONLY"
S1_1_SOURCE_NEXT = (
    "AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
)
S1_1_SOURCE_GATES = (
    "ALL_277_FRIDAY_TARGETS_CLASSIFIED",
    "EVERY_ZIP_MATCHES_ITS_PUBLISHED_SHA256",
    "EVERY_ZIP_HAS_EXACTLY_ONE_SAFE_EXPECTED_CSV_MEMBER",
    "EVERY_CSV_ROW_HAS_EXACTLY_12_KLINE_FIELDS",
    "OPEN_TIMES_ARE_UNIQUE_STRICTLY_INCREASING_AND_WITHIN_TARGET_DATE",
    "FIRST_AVAILABLE_OPEN_EXISTS_ONCE_PER_TARGET_DATE",
    "SELECTED_OPEN_IS_EARLIEST_OBSERVED_OPEN_ON_OR_AFTER_00_00_UTC",
    "SELECTED_OPEN_IS_POSITIVE_FINITE_DECIMAL_SOURCE_TEXT",
    "REUSE_AND_NETWORK_EVIDENCE_RECONCILE_EXACTLY",
    "OUTPUT_HAS_277_CHRONOLOGICAL_HASH_LINKED_PRICE_ROWS",
    "ZERO_RETURNS_CANDIDATE_OUTCOMES_VALIDATION_HOLDOUT_AND_ORDERS",
)


class S1SourceTimingAmendmentV2(BaseModel):
    schema_version: Literal["aurex-s1-source-timing-amendment-v2"] = (
        "aurex-s1-source-timing-amendment-v2"
    )
    amendment_id: Literal["s1-source-timing-amendment-v2"] = (
        "s1-source-timing-amendment-v2"
    )
    frozen_at: datetime
    builder_contract_hash: str
    strategy_preregistration_file_sha256: str
    strategy_preregistration_evidence_hash: str
    strategy_preregistration_audit_file_sha256: str
    strategy_preregistration_audit_evidence_hash: str
    failed_source_result_file_sha256: str
    failed_source_result_evidence_hash: str
    failed_source_audit_file_sha256: str
    failed_source_audit_evidence_hash: str
    failed_source_decision: Literal[
        "STOP_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_FAILED"
    ]
    independent_failure_diagnosis: Literal[
        "MISSING_EXACT_00_00_UTC_TARGET_OPEN"
    ] = "MISSING_EXACT_00_00_UTC_TARGET_OPEN"
    failed_target_id: Literal["022-btcusdt-1h-2018-02-09"] = (
        "022-btcusdt-1h-2018-02-09"
    )
    failed_target_expected_open_time_ms: Literal[1518134400000] = 1_518_134_400_000
    failed_target_first_observed_open_time_ms: Literal[1518170400000] = 1_518_170_400_000
    prior_classified_target_count: Literal[22] = 22
    prior_materialized_execution_price_count: Literal[21] = 21
    prior_return_count: Literal[0] = 0
    prior_strategy_outcome_count: Literal[0] = 0
    development_attempt_index: Literal[2] = 2
    contamination_scope: Literal[
        "DEVELOPMENT_SOURCE_AVAILABILITY_AND_21_EXECUTION_PRICE_VALUES"
    ] = "DEVELOPMENT_SOURCE_AVAILABILITY_AND_21_EXECUTION_PRICE_VALUES"
    old_activation_rule: Literal[
        "SOURCE_VINTAGE_PLUS_1_CALENDAR_DAY_AT_00_00_UTC"
    ] = "SOURCE_VINTAGE_PLUS_1_CALENDAR_DAY_AT_00_00_UTC"
    old_execution_price_rule: Literal[
        "EXACT_1H_KLINE_OPEN_AT_ACTIVATION_TIMESTAMP"
    ] = "EXACT_1H_KLINE_OPEN_AT_ACTIVATION_TIMESTAMP"
    new_activation_rule: Literal[
        "SOURCE_VINTAGE_PLUS_1_CALENDAR_DAY_FIRST_AVAILABLE_BINANCE_1H_BAR"
    ] = "SOURCE_VINTAGE_PLUS_1_CALENDAR_DAY_FIRST_AVAILABLE_BINANCE_1H_BAR"
    new_execution_price_rule: Literal[
        "EARLIEST_1H_KLINE_OPEN_WITHIN_TARGET_FRIDAY"
    ] = "EARLIEST_1H_KLINE_OPEN_WITHIN_TARGET_FRIDAY"
    missing_execution_price_policy: Literal[
        "STOP_IF_TARGET_FRIDAY_HAS_ZERO_VALID_1H_BARS"
    ] = "STOP_IF_TARGET_FRIDAY_HAS_ZERO_VALID_1H_BARS"
    maximum_activation_delay_minutes: Literal[1439] = 1439
    economic_hypothesis_changed: Literal[False] = False
    candidate_rules_changed: Literal[False] = False
    candidate_roles_changed: Literal[False] = False
    costs_changed: Literal[False] = False
    development_gates_changed: Literal[False] = False
    development_dates_changed: Literal[False] = False
    validation_remains_sealed: Literal[True] = True
    holdout_remains_sealed: Literal[True] = True
    authorizes_timing_amendment_only: Literal[True] = True
    authorizes_new_network_acquisition_now: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate_outcome: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ] = S1_1_TIMING_NEXT
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "strategy_preregistration_file_sha256",
        "strategy_preregistration_evidence_hash",
        "strategy_preregistration_audit_file_sha256",
        "strategy_preregistration_audit_evidence_hash",
        "failed_source_result_file_sha256",
        "failed_source_result_evidence_hash",
        "failed_source_audit_file_sha256",
        "failed_source_audit_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S1SourceTimingAmendmentV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S1.1 source timing amendment hash changed")
        return self


class S1SourceTimingAmendmentAuditV2(BaseModel):
    schema_version: Literal["aurex-s1-source-timing-amendment-audit-v2"] = (
        "aurex-s1-source-timing-amendment-audit-v2"
    )
    audit_id: Literal["s1-source-timing-amendment-audit-v2"] = (
        "s1-source-timing-amendment-audit-v2"
    )
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    builder_contract_hash: str
    failed_source_result_evidence_hash: str
    failed_source_audit_evidence_hash: str
    auditor_source_sha256: str
    prior_materialized_execution_price_count: Literal[21] = 21
    prior_return_count: Literal[0] = 0
    prior_strategy_outcome_count: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_1_SOURCE_TIMING_AMENDMENT_RECONSTRUCTED"] = (
        "PASS_S1_1_SOURCE_TIMING_AMENDMENT_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ] = S1_1_TIMING_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "amendment_file_sha256",
        "amendment_evidence_hash",
        "builder_contract_hash",
        "failed_source_result_evidence_hash",
        "failed_source_audit_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1SourceTimingAmendmentAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1.1 source timing amendment audit hash changed")
        return self


class S1BtcReuseArtifactV2(BaseModel):
    sequence: int = Field(ge=1, le=22)
    target_id: str
    activation_date: date
    archive_path: str
    archive_file_sha256: str
    archive_bytes: int = Field(ge=1, le=200000)
    checksum_path: str
    checksum_file_sha256: str
    checksum_bytes: int = Field(ge=1, le=512)
    published_archive_sha256: str
    reuse_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "archive_file_sha256",
        "checksum_file_sha256",
        "published_archive_sha256",
        "reuse_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_reuse(self) -> S1BtcReuseArtifactV2:
        if self.archive_file_sha256 != self.published_archive_sha256:
            raise ValueError("S1.1 reuse archive does not match its published hash")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"reuse_evidence_hash"})
        )
        if self.reuse_evidence_hash != expected:
            raise ValueError("S1.1 reuse artifact hash changed")
        return self


class S1BtcSourceAcquisitionProtocolV2(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-protocol-v2"] = (
        "aurex-s1-btc-source-acquisition-protocol-v2"
    )
    protocol_id: Literal["s1-btc-source-acquisition-protocol-v2"] = (
        "s1-btc-source-acquisition-protocol-v2"
    )
    frozen_at: datetime
    builder_contract_hash: str
    timing_amendment_file_sha256: str
    timing_amendment_evidence_hash: str
    timing_amendment_audit_file_sha256: str
    timing_amendment_audit_evidence_hash: str
    prior_checkpoint_file_sha256: str
    prior_checkpoint_evidence_hash: str
    prior_result_file_sha256: str
    prior_result_evidence_hash: str
    reuse_artifacts: tuple[S1BtcReuseArtifactV2, ...] = Field(
        min_length=22,
        max_length=22,
    )
    reuse_target_count: Literal[22] = 22
    network_target_count: Literal[255] = 255
    targets: tuple[S1BtcSourceTarget, ...] = Field(min_length=277, max_length=277)
    target_count: Literal[277] = 277
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    interval: Literal["1h"] = "1h"
    archive_granularity: Literal["DAILY"] = "DAILY"
    first_activation_date: Literal["2017-09-15"] = "2017-09-15"
    last_activation_date: Literal["2022-12-30"] = "2022-12-30"
    requests_per_attempt: Literal[2] = 2
    maximum_attempts_per_resource: Literal[3] = 3
    maximum_network_requests: Literal[1530] = 1530
    maximum_archive_bytes_per_target: Literal[200000] = 200_000
    maximum_checksum_bytes_per_target: Literal[512] = 512
    maximum_total_payload_bytes: Literal[51130560] = 51_130_560
    minimum_free_disk_bytes: Literal[250000000] = 250_000_000
    connect_timeout_seconds: Literal[60] = 60
    chunk_size_bytes: Literal[65536] = 65_536
    polite_delay_milliseconds: Literal[100] = 100
    transient_http_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    permits_redirects: Literal[False] = False
    requires_pre_attempt_marker: Literal[True] = True
    requires_post_attempt_marker: Literal[True] = True
    requires_atomic_file_rename: Literal[True] = True
    requires_per_target_checkpoint: Literal[True] = True
    requires_partial_checkpoint_resume: Literal[True] = True
    permits_exact_hash_local_reuse: Literal[True] = True
    permits_partial_file_reuse: Literal[False] = False
    timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"
    selection_rule: Literal[
        "EARLIEST_1H_KLINE_OPEN_WITHIN_TARGET_FRIDAY"
    ] = "EARLIEST_1H_KLINE_OPEN_WITHIN_TARGET_FRIDAY"
    maximum_activation_delay_minutes: Literal[1439] = 1439
    output_path: Literal[
        "data/evidence/datasets/s1_1_btcusdt_friday_first_opens_v2.jsonl"
    ] = "data/evidence/datasets/s1_1_btcusdt_friday_first_opens_v2.jsonl"
    quality_gates: tuple[str, ...] = Field(min_length=11, max_length=11)
    prior_materialized_execution_price_count_declared: Literal[21] = 21
    btc_market_values_read_during_protocol_freeze: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    authorizes_protocol_only: Literal[True] = True
    authorizes_runner_implementation: Literal[True] = True
    authorizes_network_acquisition_now: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate_outcome: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_1_SOURCE_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "timing_amendment_file_sha256",
        "timing_amendment_evidence_hash",
        "timing_amendment_audit_file_sha256",
        "timing_amendment_audit_evidence_hash",
        "prior_checkpoint_file_sha256",
        "prior_checkpoint_evidence_hash",
        "prior_result_file_sha256",
        "prior_result_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1BtcSourceAcquisitionProtocolV2:
        if tuple(item.sequence for item in self.targets) != tuple(range(1, 278)):
            raise ValueError("S1.1 target sequence changed")
        if tuple(item.sequence for item in self.reuse_artifacts) != tuple(range(1, 23)):
            raise ValueError("S1.1 reuse sequence changed")
        if tuple(item.target_id for item in self.reuse_artifacts) != tuple(
            target.target_id for target in self.targets[:22]
        ):
            raise ValueError("S1.1 reuse target identity changed")
        if self.maximum_network_requests != (
            self.network_target_count
            * self.requests_per_attempt
            * self.maximum_attempts_per_resource
        ):
            raise ValueError("S1.1 network request budget changed")
        if self.maximum_total_payload_bytes != self.network_target_count * (
            self.maximum_archive_bytes_per_target
            + self.maximum_checksum_bytes_per_target
        ):
            raise ValueError("S1.1 payload budget changed")
        if self.quality_gates != S1_1_SOURCE_GATES:
            raise ValueError("S1.1 source gates changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1.1 source protocol hash changed")
        return self


class S1BtcSourceAcquisitionProtocolAuditV2(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-protocol-audit-v2"] = (
        "aurex-s1-btc-source-acquisition-protocol-audit-v2"
    )
    audit_id: Literal["s1-btc-source-acquisition-protocol-audit-v2"] = (
        "s1-btc-source-acquisition-protocol-audit-v2"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    timing_amendment_evidence_hash: str
    timing_amendment_audit_evidence_hash: str
    prior_result_evidence_hash: str
    auditor_source_sha256: str
    reuse_target_count: Literal[22] = 22
    network_target_count: Literal[255] = 255
    target_count: Literal[277] = 277
    prior_materialized_execution_price_count_declared: Literal[21] = 21
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_1_BTC_SOURCE_PROTOCOL_RECONSTRUCTED"] = (
        "PASS_S1_1_BTC_SOURCE_PROTOCOL_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_1_SOURCE_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "timing_amendment_evidence_hash",
        "timing_amendment_audit_evidence_hash",
        "prior_result_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1BtcSourceAcquisitionProtocolAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1.1 source protocol audit hash changed")
        return self
