from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_NFCI_FULL_NEXT = "AUTHORIZE_S1_NFCI_DEVELOPMENT_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"


class S1NfciFullAcquisitionTarget(BaseModel):
    sequence: int = Field(ge=1, le=281)
    target_id: str = Field(pattern=r"^[0-9]{3}-nfci-vintage-[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    vintage_date: date
    url: str = Field(min_length=20)
    expected_final_host: Literal["alfred.stlouisfed.org"] = "alfred.stlouisfed.org"
    expected_value_column: str = Field(pattern=r"^NFCI_[0-9]{8}$")
    raw_path: str = Field(min_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1NfciFullAcquisitionProtocol(BaseModel):
    schema_version: Literal["aurex-s1-nfci-full-acquisition-protocol-v1"] = (
        "aurex-s1-nfci-full-acquisition-protocol-v1"
    )
    protocol_id: Literal["s1-nfci-full-acquisition-protocol-v1"] = (
        "s1-nfci-full-acquisition-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    recovery_protocol_file_sha256: str
    recovery_protocol_evidence_hash: str
    recovery_result_file_sha256: str
    recovery_result_evidence_hash: str
    recovery_audit_file_sha256: str
    recovery_audit_evidence_hash: str
    recovery_decision: Literal["PASS_S1_ALFRED_POINT_IN_TIME_SOURCE_RECOVERY"]
    recovery_next_authorization: Literal[
        "AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY"
    ]
    acquisition_scope: Literal["DEVELOPMENT_MACRO_SOURCE_ONLY"] = (
        "DEVELOPMENT_MACRO_SOURCE_ONLY"
    )
    schedule_rule: Literal[
        "EVERY_THURSDAY_AS_OF_AFTER_PRIOR_WEDNESDAY_NFCI_RELEASE"
    ] = "EVERY_THURSDAY_AS_OF_AFTER_PRIOR_WEDNESDAY_NFCI_RELEASE"
    development_start: Literal["2017-08-17"] = "2017-08-17"
    development_end_exclusive: Literal["2023-01-01"] = "2023-01-01"
    first_vintage_date: Literal["2017-08-17"] = "2017-08-17"
    last_vintage_date: Literal["2022-12-29"] = "2022-12-29"
    interval_days: Literal[7] = 7
    targets: tuple[S1NfciFullAcquisitionTarget, ...] = Field(
        min_length=281,
        max_length=281,
    )
    target_count: Literal[281] = 281
    maximum_attempts_per_target: Literal[3] = 3
    maximum_get_attempts: Literal[843] = 843
    maximum_payload_bytes_per_target: Literal[200000] = 200_000
    maximum_total_payload_bytes: Literal[56200000] = 56_200_000
    minimum_free_disk_bytes: Literal[250000000] = 250_000_000
    connect_timeout_seconds: Literal[60] = 60
    chunk_size_bytes: Literal[65536] = 65_536
    polite_delay_milliseconds: Literal[250] = 250
    transient_http_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    retryable_errors: tuple[str, ...] = (
        "ConnectionError",
        "TimeoutError",
        "URLError",
    )
    expected_observation_column: Literal["observation_date"] = "observation_date"
    earliest_required_observation_date: Literal["2017-08-17"] = "2017-08-17"
    maximum_release_lag_days: Literal[21] = 21
    minimum_valid_rows_per_target: Literal[100] = 100
    quality_gates: tuple[str, ...] = Field(min_length=1)
    requires_pre_attempt_marker: Literal[True] = True
    requires_post_attempt_marker: Literal[True] = True
    requires_atomic_raw_rename: Literal[True] = True
    requires_per_target_checkpoint: Literal[True] = True
    permits_exact_hash_local_reuse: Literal[True] = True
    permits_partial_file_reuse: Literal[False] = False
    permits_redirects: Literal[False] = False
    macro_numeric_fields_authorized: tuple[Literal["NFCI"], ...] = ("NFCI",)
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    authorizes_protocol_only: Literal[True] = True
    authorizes_network_acquisition_now: Literal[False] = False
    authorizes_runner_implementation: Literal[True] = True
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_NFCI_FULL_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "recovery_protocol_file_sha256",
        "recovery_protocol_evidence_hash",
        "recovery_result_file_sha256",
        "recovery_result_evidence_hash",
        "recovery_audit_file_sha256",
        "recovery_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1NfciFullAcquisitionProtocol:
        sequences = tuple(target.sequence for target in self.targets)
        dates = tuple(target.vintage_date for target in self.targets)
        if sequences != tuple(range(1, self.target_count + 1)):
            raise ValueError("S1 full-acquisition target sequence changed")
        if dates[0] != date(2017, 8, 17) or dates[-1] != date(2022, 12, 29):
            raise ValueError("S1 full-acquisition date bounds changed")
        intervals = zip(dates, dates[1:], strict=False)
        if any(
            (current - previous).days != self.interval_days
            for previous, current in intervals
        ):
            raise ValueError("S1 full-acquisition Thursday schedule changed")
        if any(target.vintage_date.weekday() != 3 for target in self.targets):
            raise ValueError("S1 full-acquisition target is not a Thursday")
        if self.maximum_get_attempts != self.target_count * self.maximum_attempts_per_target:
            raise ValueError("S1 full-acquisition request budget changed")
        if self.maximum_total_payload_bytes != (
            self.target_count * self.maximum_payload_bytes_per_target
        ):
            raise ValueError("S1 full-acquisition byte budget changed")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 full acquisition cannot inspect BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 full-acquisition protocol evidence hash changed")
        return self


class S1NfciFullAcquisitionProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-full-acquisition-protocol-audit-v1"] = (
        "aurex-s1-nfci-full-acquisition-protocol-audit-v1"
    )
    audit_id: Literal["s1-nfci-full-acquisition-protocol-audit-v1"] = (
        "s1-nfci-full-acquisition-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_source_sha256: str
    target_count: Literal[281] = 281
    first_vintage_date: Literal["2017-08-17"] = "2017-08-17"
    last_vintage_date: Literal["2022-12-29"] = "2022-12-29"
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    payload_bytes_observed: Literal[0] = 0
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal["PASS_S1_NFCI_FULL_ACQUISITION_PROTOCOL_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_FULL_ACQUISITION_PROTOCOL_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_NFCI_FULL_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciFullAcquisitionProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 full-acquisition protocol audit hash changed")
        return self
