from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_source_feasibility import S1SourceGate
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_NFCI_PILOT_PASS = "PASS_S1_NFCI_POINT_IN_TIME_RAW_PILOT"
S1_NFCI_PILOT_STOP = "STOP_S1_NFCI_POINT_IN_TIME_RAW_PILOT_FAILED"
S1_NFCI_PILOT_NEXT = "AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY"


class S1NfciPilotTarget(BaseModel):
    target_id: Literal["01-nfci-vintage-2020", "02-nfci-vintage-2021"]
    vintage_date: date
    url: str = Field(min_length=20)
    expected_final_host: Literal["fred.stlouisfed.org"] = "fred.stlouisfed.org"
    raw_path: str = Field(min_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1NfciRawPilotProtocol(BaseModel):
    schema_version: Literal["aurex-s1-nfci-raw-pilot-protocol-v1"] = (
        "aurex-s1-nfci-raw-pilot-protocol-v1"
    )
    protocol_id: Literal["s1-nfci-raw-pilot-protocol-v1"] = (
        "s1-nfci-raw-pilot-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    charter_file_sha256: str
    charter_evidence_hash: str
    v2_result_file_sha256: str
    v2_result_evidence_hash: str
    v2_audit_file_sha256: str
    v2_audit_evidence_hash: str
    v2_decision: Literal[
        "PASS_S1_V2_NO_KEY_VINTAGE_TRANSPORT_AWAIT_RAW_PILOT_PROTOCOL"
    ]
    v2_next_authorization: Literal[
        "AUTHORIZE_S1_RAW_NFCI_TWO_VINTAGE_PILOT_PROTOCOL_ONLY"
    ]
    targets: tuple[S1NfciPilotTarget, ...] = Field(min_length=2, max_length=2)
    request_budget: Literal[2] = 2
    retry_budget: Literal[0] = 0
    maximum_payload_bytes_per_target: Literal[1000000] = 1_000_000
    maximum_total_payload_bytes: Literal[2000000] = 2_000_000
    connect_timeout_seconds: Literal[60] = 60
    chunk_size_bytes: Literal[65536] = 65_536
    expected_csv_header: tuple[Literal["observation_date"], Literal["NFCI"]] = (
        "observation_date",
        "NFCI",
    )
    earliest_required_observation_date: Literal["2017-08-17"] = "2017-08-17"
    maximum_release_lag_days: Literal[21] = 21
    minimum_valid_rows_per_target: Literal[100] = 100
    feasibility_gates: tuple[str, ...] = Field(min_length=1)
    macro_numeric_fields_inspected: tuple[Literal["NFCI"], ...] = ("NFCI",)
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    authorizes_exactly_two_payload_gets: Literal[True] = True
    authorizes_raw_payload_persistence: Literal[True] = True
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
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
        "v2_result_file_sha256",
        "v2_result_evidence_hash",
        "v2_audit_file_sha256",
        "v2_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1NfciRawPilotProtocol:
        ids = tuple(target.target_id for target in self.targets)
        vintages = tuple(target.vintage_date for target in self.targets)
        if ids != ("01-nfci-vintage-2020", "02-nfci-vintage-2021"):
            raise ValueError("S1 NFCI pilot target identities changed")
        if vintages != (date(2020, 1, 1), date(2021, 1, 1)):
            raise ValueError("S1 NFCI pilot vintage dates changed")
        if self.maximum_total_payload_bytes != (
            self.maximum_payload_bytes_per_target * self.request_budget
        ):
            raise ValueError("S1 NFCI pilot byte budget changed")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 NFCI pilot cannot inspect BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 NFCI pilot protocol evidence hash changed")
        return self


class S1NfciSnapshotSummary(BaseModel):
    csv_header: tuple[str, ...]
    row_count: int = Field(ge=0)
    valid_numeric_row_count: int = Field(ge=0)
    missing_value_row_count: int = Field(ge=0)
    distinct_observation_date_count: int = Field(ge=0)
    duplicate_observation_date_count: int = Field(ge=0)
    non_increasing_observation_date_count: int = Field(ge=0)
    post_vintage_observation_count: int = Field(ge=0)
    first_observation_date: date | None
    last_observation_date: date | None
    release_lag_days: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_counts(self) -> S1NfciSnapshotSummary:
        if self.valid_numeric_row_count + self.missing_value_row_count != self.row_count:
            raise ValueError("S1 NFCI snapshot row counts do not reconcile")
        if self.distinct_observation_date_count + self.duplicate_observation_date_count != (
            self.row_count
        ):
            raise ValueError("S1 NFCI snapshot date counts do not reconcile")
        if self.row_count == 0 and any(
            value is not None
            for value in (
                self.first_observation_date,
                self.last_observation_date,
                self.release_lag_days,
            )
        ):
            raise ValueError("Empty S1 NFCI snapshot cannot have date bounds")
        return self


class S1NfciPilotDownload(BaseModel):
    target_id: str = Field(min_length=1)
    vintage_date: date
    attempted_at: datetime
    outcome: Literal["COMPLETE", "FAILED"]
    status_code: int | None = Field(default=None, ge=100, le=599)
    final_url: str | None = None
    final_host: str | None = None
    content_type: str | None = None
    payload_bytes: int = Field(ge=0)
    payload_sha256: str | None = None
    raw_path: str | None = None
    request_marker_path: str
    request_marker_sha256: str
    response_marker_path: str
    response_marker_sha256: str
    summary: S1NfciSnapshotSummary | None = None
    error_type: str | None = None
    error_message: str | None = None
    download_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("attempted_at")
    @classmethod
    def normalize_attempted_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "payload_sha256",
        "request_marker_sha256",
        "response_marker_sha256",
        "download_evidence_hash",
    )
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_download(self) -> S1NfciPilotDownload:
        complete_fields = (
            self.status_code,
            self.final_url,
            self.final_host,
            self.content_type,
            self.payload_sha256,
            self.raw_path,
            self.summary,
        )
        if self.outcome == "COMPLETE" and (
            any(value is None for value in complete_fields)
            or self.status_code != 200
            or self.payload_bytes == 0
            or self.error_type is not None
        ):
            raise ValueError("Complete S1 NFCI download evidence is incomplete")
        if self.outcome == "FAILED" and not self.error_type:
            raise ValueError("Failed S1 NFCI download requires an error type")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"download_evidence_hash"})
        )
        if self.download_evidence_hash != expected:
            raise ValueError("S1 NFCI download evidence hash changed")
        return self


class S1NfciVintageComparison(BaseModel):
    comparable: bool
    earlier_payload_sha256: str | None = None
    later_payload_sha256: str | None = None
    payload_hashes_distinct: bool
    overlap_observation_count: int = Field(ge=0)
    overlap_revision_count: int = Field(ge=0)
    later_only_observation_count: int = Field(ge=0)
    earlier_only_observation_count: int = Field(ge=0)
    earlier_last_observation_date: date | None = None
    later_last_observation_date: date | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("earlier_payload_sha256", "later_payload_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)


class S1NfciRawPilotResult(BaseModel):
    schema_version: Literal["aurex-s1-nfci-raw-pilot-result-v1"] = (
        "aurex-s1-nfci-raw-pilot-result-v1"
    )
    result_id: Literal["s1-nfci-raw-pilot-result-v1"] = (
        "s1-nfci-raw-pilot-result-v1"
    )
    completed_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    runner_source_sha256: str
    downloads: tuple[S1NfciPilotDownload, ...] = Field(min_length=2, max_length=2)
    comparison: S1NfciVintageComparison
    gates: tuple[S1SourceGate, ...] = Field(min_length=1)
    request_count: Literal[2] = 2
    retry_count: Literal[0] = 0
    total_payload_bytes: int = Field(ge=0)
    macro_numeric_fields_inspected: tuple[Literal["NFCI"], ...] = ("NFCI",)
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal[
        "PASS_S1_NFCI_POINT_IN_TIME_RAW_PILOT",
        "STOP_S1_NFCI_POINT_IN_TIME_RAW_PILOT_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY",
        "NONE_S1_NFCI_RAW_PILOT_FAILED",
    ]
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
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
    def validate_result(self) -> S1NfciRawPilotResult:
        ids = tuple(download.target_id for download in self.downloads)
        if ids != ("01-nfci-vintage-2020", "02-nfci-vintage-2021"):
            raise ValueError("S1 NFCI result download identity changed")
        if self.total_payload_bytes != sum(item.payload_bytes for item in self.downloads):
            raise ValueError("S1 NFCI result payload bytes do not reconcile")
        failed = any(gate.status == "FAIL" for gate in self.gates)
        if self.decision != (S1_NFCI_PILOT_STOP if failed else S1_NFCI_PILOT_PASS):
            raise ValueError("S1 NFCI result decision does not match gates")
        expected_next = "NONE_S1_NFCI_RAW_PILOT_FAILED" if failed else S1_NFCI_PILOT_NEXT
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


class S1NfciRawPilotAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-raw-pilot-audit-v1"] = (
        "aurex-s1-nfci-raw-pilot-audit-v1"
    )
    audit_id: Literal["s1-nfci-raw-pilot-audit-v1"] = (
        "s1-nfci-raw-pilot-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    runner_source_sha256: str
    auditor_source_sha256: str
    raw_file_sha256: dict[str, str]
    raw_file_bytes: dict[str, int]
    raw_file_count: int = Field(ge=0, le=2)
    reconstructed_exactly: Literal[True] = True
    decision: Literal[
        "PASS_S1_NFCI_RAW_PILOT_RECONSTRUCTED",
        "STOP_S1_NFCI_RAW_PILOT_RECONSTRUCTED",
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

    @field_validator("raw_file_sha256")
    @classmethod
    def normalize_raw_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: normalize_sha256(digest) for key, digest in sorted(value.items())}

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciRawPilotAudit:
        if self.raw_file_count != len(self.raw_file_sha256):
            raise ValueError("S1 NFCI audit raw-file count changed")
        if set(self.raw_file_sha256) != set(self.raw_file_bytes):
            raise ValueError("S1 NFCI audit raw-file maps changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI audit evidence hash changed")
        return self
