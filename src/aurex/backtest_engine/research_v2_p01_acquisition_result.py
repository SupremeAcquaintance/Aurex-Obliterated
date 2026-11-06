from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v2_p01_protocol import (
    V2P01PrimaryProtocol,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_REQUIRED_FAMILY_IDS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_P01_ACQUISITION_RESULT_SCHEMA_VERSION = (
    "aurex-v2-p01-full-acquisition-result-v1"
)
V2_P01_ACQUISITION_PASS_DECISION = (
    "PERMIT_FROZEN_P01_DEVELOPMENT_RETURN_RUN"
)
V2_P01_ACQUISITION_FAIL_DECISION = (
    "STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA"
)
V2_P01_QUALIFICATION_REASON_CODES = [
    "ARCHIVE_CONTINUITY_GAP",
    "MISSING_FUTURES_FILTER_PROXY",
    "MISSING_SPOT_FILTER_PROXY",
]


class P01FullArchiveEvidence(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    family_id: str
    archive_url: str = Field(min_length=50, max_length=1000)
    checksum_url: str = Field(min_length=50, max_length=1100)
    census_checksum_sha256: str
    refreshed_checksum_sha256: str
    checksum_checked_at: datetime
    preflight_checked_at: datetime
    inspected_at: datetime
    archive_content_length: int = Field(gt=0)
    archive_last_modified: str | None = Field(default=None, max_length=128)
    archive_etag: str | None = Field(default=None, max_length=256)
    archive_relative_path: str = Field(min_length=10, max_length=1000)
    checksum_relative_path: str = Field(min_length=10, max_length=1100)
    archive_sha256: str
    checksum_file_sha256: str
    archive_size_bytes: int = Field(gt=0)
    zip_compressed_bytes: int = Field(gt=0)
    zip_uncompressed_bytes: int = Field(gt=0)
    csv_member_name: str = Field(min_length=5, max_length=300)
    schema_id: Literal[
        "BINANCE_POSITIONAL_KLINE_12_COLUMNS_V1",
        "BINANCE_FUNDING_RATE_EVENT_V1",
    ]
    csv_header: list[str]
    csv_column_count: int = Field(ge=3, le=12)
    row_count: int = Field(gt=0)
    first_timestamp: datetime
    last_timestamp: datetime
    timestamp_unit: Literal["milliseconds"] = "milliseconds"
    duplicate_timestamp_count: Literal[0] = 0
    out_of_month_row_count: Literal[0] = 0
    non_finite_numeric_count: Literal[0] = 0
    unexpected_column_count: Literal[0] = 0
    expected_minute_count: int | None = Field(default=None, gt=0)
    missing_minute_count: int | None = Field(default=None, ge=0)
    continuity_gap_count: int | None = Field(default=None, ge=0)
    boundary_complete: bool
    continuity_pass: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "census_checksum_sha256",
        "refreshed_checksum_sha256",
        "archive_sha256",
        "checksum_file_sha256",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "checksum_checked_at",
        "preflight_checked_at",
        "inspected_at",
        "first_timestamp",
        "last_timestamp",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("csv_header")
    @classmethod
    def normalize_header(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value]

    @model_validator(mode="after")
    def validate_record(self) -> P01FullArchiveEvidence:
        if self.family_id not in V2_REQUIRED_FAMILY_IDS:
            raise ValueError("P01 archive family changed")
        if self.checksum_url != f"{self.archive_url}.CHECKSUM":
            raise ValueError("P01 archive checksum URL changed")
        if not self.archive_url.startswith("https://data.binance.vision/data/"):
            raise ValueError("P01 archive source is not official")
        for value in (
            self.archive_relative_path,
            self.checksum_relative_path,
        ):
            relative = PurePosixPath(value)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("P01 archive evidence path is unsafe")
        if not (
            self.census_checksum_sha256
            == self.refreshed_checksum_sha256
            == self.archive_sha256
        ):
            raise ValueError("P01 archive checksum lineage disagrees")
        if self.archive_content_length != self.archive_size_bytes:
            raise ValueError("P01 archive size lineage disagrees")
        is_funding = self.family_id == "um_funding_rate_events"
        if is_funding:
            if (
                self.schema_id != "BINANCE_FUNDING_RATE_EVENT_V1"
                or self.expected_minute_count is not None
                or self.missing_minute_count is not None
                or self.continuity_gap_count is not None
                or not self.boundary_complete
                or not self.continuity_pass
            ):
                raise ValueError("P01 funding archive classification changed")
        elif (
            self.schema_id != "BINANCE_POSITIONAL_KLINE_12_COLUMNS_V1"
            or self.expected_minute_count is None
            or self.missing_minute_count is None
            or self.continuity_gap_count is None
            or self.continuity_pass
            != (
                self.boundary_complete
                and self.missing_minute_count == 0
                and self.continuity_gap_count == 0
            )
        ):
            raise ValueError("P01 kline continuity classification changed")
        return self

    @property
    def key(self) -> tuple[str, str, str]:
        return self.symbol, self.month, self.family_id


class P01CurrentMetadataSnapshotEvidence(BaseModel):
    snapshot_kind: Literal["SPOT_EXCHANGE_INFO", "USD_M_EXCHANGE_INFO"]
    requested_url: str = Field(min_length=20, max_length=500)
    final_url: str = Field(min_length=20, max_length=500)
    checked_at: datetime
    http_status: Literal[200] = 200
    content_type: str = Field(min_length=1, max_length=300)
    response_bytes: int = Field(gt=0)
    response_sha256: str
    snapshot_relative_path: str = Field(min_length=10, max_length=1000)
    required_symbol_count: Literal[31] = 31
    present_required_symbols: list[str]
    missing_required_symbols: list[str]
    complete_filter_symbols: list[str]
    incomplete_filter_symbols: list[str]
    historical_rule_proof: Literal[False] = False
    credentials_used: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("response_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "present_required_symbols",
        "missing_required_symbols",
        "complete_filter_symbols",
        "incomplete_filter_symbols",
    )
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_snapshot(self) -> P01CurrentMetadataSnapshotEvidence:
        expected_url = {
            "SPOT_EXCHANGE_INFO": (
                "https://api.binance.com/api/v3/exchangeInfo"
            ),
            "USD_M_EXCHANGE_INFO": (
                "https://fapi.binance.com/fapi/v1/exchangeInfo"
            ),
        }[self.snapshot_kind]
        if self.requested_url != expected_url:
            raise ValueError("P01 metadata snapshot URL changed")
        domain = (urlparse(self.final_url).hostname or "").lower()
        expected_domain = urlparse(expected_url).hostname
        if domain != expected_domain:
            raise ValueError("P01 metadata snapshot final domain changed")
        relative = PurePosixPath(self.snapshot_relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("P01 metadata snapshot path is unsafe")
        required = set(V2_COMPLETE_SYMBOLS)
        if (
            set(self.present_required_symbols)
            | set(self.missing_required_symbols)
            != required
            or set(self.present_required_symbols)
            & set(self.missing_required_symbols)
        ):
            raise ValueError("P01 metadata snapshot symbol coverage changed")
        if (
            set(self.complete_filter_symbols)
            | set(self.incomplete_filter_symbols)
            != required
            or set(self.complete_filter_symbols)
            & set(self.incomplete_filter_symbols)
        ):
            raise ValueError("P01 metadata filter coverage changed")
        if not set(self.complete_filter_symbols).issubset(
            self.present_required_symbols
        ):
            raise ValueError("P01 complete filters require a present symbol")
        return self


class P01SymbolQualification(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    archive_continuity_pass: bool
    current_spot_filter_proxy_pass: bool
    current_futures_filter_proxy_pass: bool
    qualification_pass: bool
    reason_codes: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason_codes")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if not set(normalized).issubset(V2_P01_QUALIFICATION_REASON_CODES):
            raise ValueError("P01 qualification reason changed")
        return normalized

    @model_validator(mode="after")
    def validate_qualification(self) -> P01SymbolQualification:
        expected_reasons = []
        if not self.archive_continuity_pass:
            expected_reasons.append("ARCHIVE_CONTINUITY_GAP")
        if not self.current_spot_filter_proxy_pass:
            expected_reasons.append("MISSING_SPOT_FILTER_PROXY")
        if not self.current_futures_filter_proxy_pass:
            expected_reasons.append("MISSING_FUTURES_FILTER_PROXY")
        if self.reason_codes != sorted(expected_reasons):
            raise ValueError("P01 qualification reasons do not reconcile")
        if self.qualification_pass != (not expected_reasons):
            raise ValueError("P01 qualification decision does not reconcile")
        return self


class P01FullAcquisitionSummary(BaseModel):
    target_count: Literal[4464] = 4464
    verified_archive_count: Literal[4464] = 4464
    checksum_match_count: Literal[4464] = 4464
    schema_pass_count: Literal[4464] = 4464
    total_archive_bytes: int = Field(gt=0)
    total_zip_compressed_bytes: int = Field(gt=0)
    total_zip_uncompressed_bytes: int = Field(gt=0)
    total_rows: int = Field(gt=0)
    kline_archive_count: Literal[3720] = 3720
    funding_archive_count: Literal[744] = 744
    continuous_kline_archive_count: int = Field(ge=0, le=3720)
    discontinuous_kline_archive_count: int = Field(ge=0, le=3720)
    qualified_symbol_count: int = Field(ge=0, le=31)
    disqualified_symbol_count: int = Field(ge=0, le=31)
    qualified_symbols: list[str]
    disqualified_symbols: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("qualified_symbols", "disqualified_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_summary(self) -> P01FullAcquisitionSummary:
        if (
            self.continuous_kline_archive_count
            + self.discontinuous_kline_archive_count
            != self.kline_archive_count
        ):
            raise ValueError("P01 kline continuity counts do not reconcile")
        if (
            self.qualified_symbol_count + self.disqualified_symbol_count != 31
            or self.qualified_symbol_count != len(self.qualified_symbols)
            or self.disqualified_symbol_count != len(self.disqualified_symbols)
        ):
            raise ValueError("P01 symbol qualification counts do not reconcile")
        if (
            set(self.qualified_symbols) | set(self.disqualified_symbols)
            != set(V2_COMPLETE_SYMBOLS)
            or set(self.qualified_symbols) & set(self.disqualified_symbols)
        ):
            raise ValueError("P01 qualification symbol partition changed")
        return self


class V2P01FullAcquisitionResult(BaseModel):
    schema_version: Literal[
        "aurex-v2-p01-full-acquisition-result-v1"
    ] = V2_P01_ACQUISITION_RESULT_SCHEMA_VERSION
    result_id: Literal["v2-p01-full-acquisition-result-v1"] = (
        "v2-p01-full-acquisition-result-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE_NO_RETURN_ACQUISITION_QUALIFICATION"] = (
        "COMPLETE_NO_RETURN_ACQUISITION_QUALIFICATION"
    )
    p01_protocol_evidence_hash: str
    source_target_manifest_hash: str
    runner_contract_hash: str
    records: list[P01FullArchiveEvidence] = Field(
        min_length=4464, max_length=4464
    )
    metadata_snapshots: list[P01CurrentMetadataSnapshotEvidence] = Field(
        min_length=2, max_length=2
    )
    symbol_qualifications: list[P01SymbolQualification] = Field(
        min_length=31, max_length=31
    )
    summary: P01FullAcquisitionSummary
    decision: Literal[
        "PERMIT_FROZEN_P01_DEVELOPMENT_RETURN_RUN",
        "STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA",
    ]
    archive_payload_requests_complete: Literal[True] = True
    metadata_snapshot_requests: Literal[2] = 2
    credentials_used: Literal[False] = False
    private_endpoint_calls_made: Literal[False] = False
    market_data_numeric_values_inspected: Literal[True] = True
    strategy_signals_calculated: Literal[False] = False
    trades_calculated: Literal[False] = False
    return_metrics_calculated: list[str] = Field(default_factory=list)
    authorizes_development_return_under_frozen_protocol: bool
    creates_candidate: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_pine_eligibility: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "p01_protocol_evidence_hash",
        "source_target_manifest_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("return_metrics_calculated", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V2P01FullAcquisitionResult:
        if self.records != sorted(self.records, key=lambda item: item.key):
            raise ValueError("P01 acquisition records are not canonical")
        if len({record.key for record in self.records}) != 4464:
            raise ValueError("P01 acquisition target matrix is incomplete")
        expected_keys = {
            (symbol, month, family_id)
            for symbol in V2_COMPLETE_SYMBOLS
            for month in (
                f"{year}-{month:02d}"
                for year in (2023, 2024)
                for month in range(1, 13)
            )
            for family_id in V2_REQUIRED_FAMILY_IDS
        }
        if {record.key for record in self.records} != expected_keys:
            raise ValueError("P01 acquisition target matrix changed")
        if [
            snapshot.snapshot_kind for snapshot in self.metadata_snapshots
        ] != ["SPOT_EXCHANGE_INFO", "USD_M_EXCHANGE_INFO"]:
            raise ValueError("P01 metadata snapshot ordering changed")
        if [
            item.symbol for item in self.symbol_qualifications
        ] != V2_COMPLETE_SYMBOLS:
            raise ValueError("P01 qualification ordering changed")
        rebuilt_summary = build_p01_full_acquisition_summary(
            records=self.records,
            qualifications=self.symbol_qualifications,
        )
        if self.summary != rebuilt_summary:
            raise ValueError("P01 acquisition summary does not reproduce")
        expected_decision = (
            V2_P01_ACQUISITION_PASS_DECISION
            if self.summary.qualified_symbol_count >= 20
            else V2_P01_ACQUISITION_FAIL_DECISION
        )
        if (
            self.decision != expected_decision
            or self.authorizes_development_return_under_frozen_protocol
            != (self.decision == V2_P01_ACQUISITION_PASS_DECISION)
        ):
            raise ValueError("P01 acquisition decision does not reconcile")
        if self.return_metrics_calculated:
            raise ValueError("P01 acquisition result cannot contain returns")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("P01 acquisition result hash does not match")
        return self


def source_target_manifest_hash(
    records: list[P01FullArchiveEvidence],
) -> str:
    return universe_evidence_hash(
        {
            "targets": [
                {
                    "symbol": record.symbol,
                    "month": record.month,
                    "family_id": record.family_id,
                    "archive_url": record.archive_url,
                    "checksum_url": record.checksum_url,
                    "checksum_sha256": record.census_checksum_sha256,
                }
                for record in records
            ]
        }
    )


def build_p01_full_acquisition_summary(
    *,
    records: list[P01FullArchiveEvidence],
    qualifications: list[P01SymbolQualification],
) -> P01FullAcquisitionSummary:
    kline_records = [
        record
        for record in records
        if record.family_id != "um_funding_rate_events"
    ]
    qualified = sorted(
        item.symbol for item in qualifications if item.qualification_pass
    )
    disqualified = sorted(
        item.symbol for item in qualifications if not item.qualification_pass
    )
    return P01FullAcquisitionSummary(
        total_archive_bytes=sum(item.archive_size_bytes for item in records),
        total_zip_compressed_bytes=sum(
            item.zip_compressed_bytes for item in records
        ),
        total_zip_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes for item in records
        ),
        total_rows=sum(item.row_count for item in records),
        continuous_kline_archive_count=sum(
            item.continuity_pass for item in kline_records
        ),
        discontinuous_kline_archive_count=sum(
            not item.continuity_pass for item in kline_records
        ),
        qualified_symbol_count=len(qualified),
        disqualified_symbol_count=len(disqualified),
        qualified_symbols=qualified,
        disqualified_symbols=disqualified,
    )


def build_v2_p01_full_acquisition_result(
    *,
    generated_at: datetime,
    protocol: V2P01PrimaryProtocol,
    runner_contract_hash: str,
    records: list[P01FullArchiveEvidence],
    metadata_snapshots: list[P01CurrentMetadataSnapshotEvidence],
    symbol_qualifications: list[P01SymbolQualification],
    limitations: list[str],
) -> V2P01FullAcquisitionResult:
    records = sorted(records, key=lambda item: item.key)
    metadata_snapshots = sorted(
        metadata_snapshots, key=lambda item: item.snapshot_kind
    )
    symbol_qualifications = sorted(
        symbol_qualifications, key=lambda item: item.symbol
    )
    summary = build_p01_full_acquisition_summary(
        records=records,
        qualifications=symbol_qualifications,
    )
    decision = (
        V2_P01_ACQUISITION_PASS_DECISION
        if summary.qualified_symbol_count >= 20
        else V2_P01_ACQUISITION_FAIL_DECISION
    )
    payload = {
        "schema_version": V2_P01_ACQUISITION_RESULT_SCHEMA_VERSION,
        "result_id": "v2-p01-full-acquisition-result-v1",
        "result_version": "1.0.0",
        "generated_at": normalize_timestamp(generated_at),
        "status": "COMPLETE_NO_RETURN_ACQUISITION_QUALIFICATION",
        "p01_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "source_target_manifest_hash": source_target_manifest_hash(records),
        "runner_contract_hash": normalize_sha256(runner_contract_hash),
        "records": records,
        "metadata_snapshots": metadata_snapshots,
        "symbol_qualifications": symbol_qualifications,
        "summary": summary,
        "decision": decision,
        "archive_payload_requests_complete": True,
        "metadata_snapshot_requests": 2,
        "credentials_used": False,
        "private_endpoint_calls_made": False,
        "market_data_numeric_values_inspected": True,
        "strategy_signals_calculated": False,
        "trades_calculated": False,
        "return_metrics_calculated": [],
        "authorizes_development_return_under_frozen_protocol": (
            decision == V2_P01_ACQUISITION_PASS_DECISION
        ),
        "creates_candidate": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_pine_eligibility": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "limitations": sorted(set(limitations)),
    }
    return V2P01FullAcquisitionResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_p01_full_acquisition_result(
    *,
    result: V2P01FullAcquisitionResult,
    protocol: V2P01PrimaryProtocol,
    current_runner_contract_hash: str,
    evidence_root: Path,
    inspect_local_files: bool = True,
) -> dict[str, object]:
    reasons: list[str] = []
    if result.p01_protocol_evidence_hash != protocol.protocol_evidence_hash:
        reasons.append("P01_PROTOCOL_HASH_MISMATCH")
    if result.source_target_manifest_hash != (
        protocol.acquisition.source_target_manifest_hash
    ):
        reasons.append("P01_SOURCE_TARGET_MANIFEST_MISMATCH")
    if result.runner_contract_hash != normalize_sha256(
        current_runner_contract_hash
    ):
        reasons.append("P01_ACQUISITION_RUNNER_HASH_MISMATCH")
    try:
        rebuilt = build_v2_p01_full_acquisition_result(
            generated_at=result.generated_at,
            protocol=protocol,
            runner_contract_hash=result.runner_contract_hash,
            records=result.records,
            metadata_snapshots=result.metadata_snapshots,
            symbol_qualifications=result.symbol_qualifications,
            limitations=result.limitations,
        )
    except ValueError as exc:
        reasons.append(str(exc))
    else:
        if rebuilt != result:
            reasons.append("P01_ACQUISITION_RESULT_NOT_REPRODUCIBLE")
    if inspect_local_files:
        for record in result.records:
            archive_path = evidence_root / record.archive_relative_path
            checksum_path = evidence_root / record.checksum_relative_path
            if not archive_path.is_file() or not checksum_path.is_file():
                reasons.append(f"P01_LOCAL_ARCHIVE_MISSING:{record.key}")
                continue
            if (
                archive_path.stat().st_size != record.archive_size_bytes
                or file_sha256(archive_path) != record.archive_sha256
                or file_sha256(checksum_path) != record.checksum_file_sha256
            ):
                reasons.append(f"P01_LOCAL_ARCHIVE_CHANGED:{record.key}")
        for snapshot in result.metadata_snapshots:
            snapshot_path = evidence_root / snapshot.snapshot_relative_path
            if (
                not snapshot_path.is_file()
                or snapshot_path.stat().st_size != snapshot.response_bytes
                or file_sha256(snapshot_path) != snapshot.response_sha256
            ):
                reasons.append(
                    f"P01_METADATA_SNAPSHOT_CHANGED:{snapshot.snapshot_kind}"
                )
    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "result_evidence_hash": result.result_evidence_hash,
        "qualified_symbol_count": result.summary.qualified_symbol_count,
        "decision": result.decision,
    }
