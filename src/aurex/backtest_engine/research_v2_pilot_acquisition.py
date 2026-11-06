from __future__ import annotations

import csv
import io
import stat
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from itertools import chain
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.binance_vision import (
    file_sha256,
    parse_binance_timestamp,
)
from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2AcquisitionTarget,
    V2DerivativesAcquisitionProtocol,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_REQUIRED_FAMILY_IDS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_PILOT_RESULT_SCHEMA_VERSION = (
    "aurex-v2-derivatives-pilot-acquisition-result-v1"
)
V2_PILOT_PASS_DECISION = (
    "PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL"
)
KLINE_SCHEMA_ID = "BINANCE_POSITIONAL_KLINE_12_COLUMNS_V1"
FUNDING_SCHEMA_ID = "BINANCE_FUNDING_RATE_EVENT_V1"
KLINE_HEADER_FIRST_FIELDS = {"open_time", "opentime"}
FUNDING_HEADER_SCHEMAS = {
    (
        "calc_time",
        "funding_interval_hours",
        "last_funding_rate",
    ): (0, (1, 2)),
    (
        "symbol",
        "fundingtime",
        "fundingrate",
        "markprice",
    ): (1, (2, 3)),
}


class V2PilotArchiveEvidence(BaseModel):
    symbol: str
    month: str
    family_id: str
    archive_url: str
    checksum_url: str
    census_checksum_sha256: str
    refreshed_checksum_sha256: str
    checksum_checked_at: datetime
    checksum_file_sha256: str
    preflight_checked_at: datetime
    archive_http_status: Literal[200] = 200
    archive_content_length: int = Field(gt=0)
    archive_last_modified: str | None = Field(default=None, max_length=128)
    archive_etag: str | None = Field(default=None, max_length=256)
    archive_relative_path: str
    checksum_relative_path: str
    archive_sha256: str
    archive_size_bytes: int = Field(gt=0)
    zip_compressed_bytes: int = Field(ge=0)
    zip_uncompressed_bytes: int = Field(gt=0)
    csv_member_name: str
    csv_header: list[str]
    csv_column_count: int = Field(gt=0)
    row_count: int = Field(gt=0)
    first_timestamp: datetime
    last_timestamp: datetime
    timestamp_unit: Literal["milliseconds"] = "milliseconds"
    duplicate_timestamp_count: Literal[0] = 0
    out_of_month_row_count: Literal[0] = 0
    non_finite_numeric_count: Literal[0] = 0
    unexpected_column_count: Literal[0] = 0
    schema_id: Literal[
        "BINANCE_POSITIONAL_KLINE_12_COLUMNS_V1",
        "BINANCE_FUNDING_RATE_EVENT_V1",
    ]

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "census_checksum_sha256",
        "refreshed_checksum_sha256",
        "checksum_file_sha256",
        "archive_sha256",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "checksum_checked_at",
        "preflight_checked_at",
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
    def validate_evidence(self) -> V2PilotArchiveEvidence:
        if not (
            self.census_checksum_sha256
            == self.refreshed_checksum_sha256
            == self.archive_sha256
        ):
            raise ValueError("V2 pilot checksum lineage disagrees")
        if self.archive_size_bytes != self.archive_content_length:
            raise ValueError("V2 pilot archive size changed after preflight")
        if self.first_timestamp > self.last_timestamp:
            raise ValueError("V2 pilot timestamp bounds are reversed")
        month_start, month_end = month_bounds(self.month)
        if not (
            month_start <= self.first_timestamp
            and self.last_timestamp < month_end
        ):
            raise ValueError("V2 pilot timestamp bounds are outside the target month")
        if self.checksum_url != f"{self.archive_url}.CHECKSUM":
            raise ValueError("V2 pilot checksum URL changed")
        archive_relative = PurePosixPath(self.archive_relative_path)
        checksum_relative = PurePosixPath(self.checksum_relative_path)
        if archive_relative.is_absolute() or ".." in archive_relative.parts:
            raise ValueError("V2 pilot archive path must be relative")
        if checksum_relative.is_absolute() or ".." in checksum_relative.parts:
            raise ValueError("V2 pilot checksum path must be relative")
        if self.checksum_relative_path != f"{self.archive_relative_path}.CHECKSUM":
            raise ValueError("V2 pilot local checksum path changed")
        is_funding = self.family_id == "um_funding_rate_events"
        if is_funding != (self.schema_id == FUNDING_SCHEMA_ID):
            raise ValueError("V2 pilot schema does not match its family")
        expected_columns = 3 if is_funding else 12
        if (
            self.schema_id == FUNDING_SCHEMA_ID
            and self.csv_column_count not in {3, 4}
        ) or (
            self.schema_id == KLINE_SCHEMA_ID
            and self.csv_column_count != expected_columns
        ):
            raise ValueError("V2 pilot column count does not match its schema")
        return self

    @property
    def key(self) -> tuple[str, str, str]:
        return self.symbol, self.month, self.family_id


class V2PilotFamilySummary(BaseModel):
    family_id: str
    target_count: Literal[9] = 9
    archive_bytes: int = Field(gt=0)
    uncompressed_bytes: int = Field(gt=0)
    row_count: int = Field(gt=0)
    schema_ids: list[str] = Field(min_length=1, max_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("schema_ids")
    @classmethod
    def normalize_schema_ids(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class V2PilotAcquisitionSummary(BaseModel):
    target_count: Literal[54] = 54
    checksum_match_count: Literal[54] = 54
    verified_archive_count: Literal[54] = 54
    classified_family_count: Literal[6] = 6
    total_archive_bytes: int = Field(gt=0)
    total_uncompressed_bytes: int = Field(gt=0)
    total_rows: int = Field(gt=0)
    family_summaries: list[V2PilotFamilySummary] = Field(
        min_length=6, max_length=6
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_summary(self) -> V2PilotAcquisitionSummary:
        if [item.family_id for item in self.family_summaries] != (
            V2_REQUIRED_FAMILY_IDS
        ):
            raise ValueError("V2 pilot family summaries changed")
        if sum(item.archive_bytes for item in self.family_summaries) != (
            self.total_archive_bytes
        ):
            raise ValueError("V2 pilot archive-byte summary does not reconcile")
        if sum(item.uncompressed_bytes for item in self.family_summaries) != (
            self.total_uncompressed_bytes
        ):
            raise ValueError("V2 pilot uncompressed-byte summary does not reconcile")
        if sum(item.row_count for item in self.family_summaries) != self.total_rows:
            raise ValueError("V2 pilot row summary does not reconcile")
        return self


class V2PilotAcquisitionResult(BaseModel):
    schema_version: Literal[
        "aurex-v2-derivatives-pilot-acquisition-result-v1"
    ] = V2_PILOT_RESULT_SCHEMA_VERSION
    result_id: Literal["v2-derivatives-pilot-acquisition-result-v1"] = (
        "v2-derivatives-pilot-acquisition-result-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE"] = "COMPLETE"
    acquisition_protocol_evidence_hash: str
    source_census_result_evidence_hash: str
    runner_contract_hash: str
    records: list[V2PilotArchiveEvidence] = Field(min_length=54, max_length=54)
    summary: V2PilotAcquisitionSummary
    decision: Literal[
        "PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL"
    ] = V2_PILOT_PASS_DECISION
    unresolved_request_count: Literal[0] = 0
    integrity_failure_count: Literal[0] = 0
    resource_gate_failure_count: Literal[0] = 0
    schema_failure_count: Literal[0] = 0
    permits_full_acquisition_protocol_design: Literal[True] = True
    authorizes_full_archive_payload_download: Literal[False] = False
    authorizes_market_data_import: Literal[False] = False
    authorizes_strategy_return_calculation: Literal[False] = False
    authorizes_mechanism_selection: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_strategy_eligibility: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    validation_data_loaded: Literal[False] = False
    holdout_data_loaded: Literal[False] = False
    forward_data_loaded: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=5)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "acquisition_protocol_evidence_hash",
        "source_census_result_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("strategy_outcome_fields_inspected", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V2PilotAcquisitionResult:
        if self.strategy_outcome_fields_inspected:
            raise ValueError("V2 pilot result cannot inspect strategy outcomes")
        if self.records != sorted(self.records, key=lambda item: item.key):
            raise ValueError("V2 pilot records are not canonical")
        if len({record.key for record in self.records}) != 54:
            raise ValueError("V2 pilot record matrix is incomplete")
        if _build_summary(self.records) != self.summary:
            raise ValueError("V2 pilot summary does not match its records")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V2 pilot result hash does not match")
        return self


def month_bounds(month: str) -> tuple[datetime, datetime]:
    year, month_number = (int(part) for part in month.split("-"))
    start = datetime(year, month_number, 1, tzinfo=UTC)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=UTC)
    return start, end


def _normalized_header(row: list[str]) -> tuple[str, ...]:
    return tuple(item.strip().lower().replace(" ", "_") for item in row)


def _finite_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"V2 pilot value is not numeric: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"V2 pilot value is not finite: {value!r}")
    return parsed


def _validate_zip_members(
    archive: zipfile.ZipFile,
    *,
    maximum_uncompressed_bytes: int,
    maximum_expansion_ratio: int,
) -> tuple[zipfile.ZipInfo, int, int]:
    files = [member for member in archive.infolist() if not member.is_dir()]
    if len(files) != 1 or not files[0].filename.lower().endswith(".csv"):
        raise ValueError("V2 pilot archive must contain exactly one CSV file")
    member = files[0]
    member_path = PurePosixPath(member.filename)
    if (
        member_path.is_absolute()
        or len(member_path.parts) != 1
        or ".." in member_path.parts
        or "\\" in member.filename
    ):
        raise ValueError("V2 pilot archive contains an unsafe nested member")
    if member.flag_bits & 0x1:
        raise ValueError("V2 pilot archive contains an encrypted member")
    unix_mode = (member.external_attr >> 16) & 0o170000
    if unix_mode == stat.S_IFLNK:
        raise ValueError("V2 pilot archive contains a symlink")
    compressed = sum(item.compress_size for item in files)
    uncompressed = sum(item.file_size for item in files)
    if uncompressed <= 0 or uncompressed > maximum_uncompressed_bytes:
        raise ValueError("V2 pilot archive exceeds its uncompressed-byte limit")
    if uncompressed > max(compressed, 1) * maximum_expansion_ratio:
        raise ValueError("V2 pilot archive exceeds its expansion-ratio limit")
    return member, compressed, uncompressed


def _inspect_csv_rows(
    *,
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    target: V2AcquisitionTarget,
) -> dict[str, object]:
    start, end = month_bounds(target.month)
    is_funding = target.family_id == "um_funding_rate_events"
    expected_columns = None
    timestamp_index = 0
    numeric_indexes: tuple[int, ...] = ()
    schema_id = FUNDING_SCHEMA_ID if is_funding else KLINE_SCHEMA_ID
    header: list[str] = []
    row_count = 0
    timestamps: list[datetime] = []
    timestamp_units: set[str] = set()
    previous_timestamp: datetime | None = None
    seen_timestamps: set[datetime] = set()

    with archive.open(member) as source:
        text = io.TextIOWrapper(source, encoding="utf-8", newline="")
        reader = csv.reader(text)
        try:
            first_row = next(reader)
        except StopIteration as exc:
            raise ValueError("V2 pilot CSV is empty") from exc
        normalized_first = _normalized_header(first_row)
        first_is_header = False
        try:
            int(first_row[0])
        except (ValueError, IndexError):
            first_is_header = True

        if is_funding:
            if not first_is_header or normalized_first not in FUNDING_HEADER_SCHEMAS:
                raise ValueError("V2 pilot funding schema is unknown")
            header = [item.strip() for item in first_row]
            timestamp_index, numeric_indexes = FUNDING_HEADER_SCHEMAS[normalized_first]
            expected_columns = len(first_row)
            data_rows = reader
        else:
            expected_columns = 12
            numeric_indexes = tuple(range(1, 12))
            if first_is_header:
                if (
                    len(first_row) != expected_columns
                    or normalized_first[0] not in KLINE_HEADER_FIRST_FIELDS
                ):
                    raise ValueError("V2 pilot kline header is unknown")
                header = [item.strip() for item in first_row]
                data_rows = reader
            else:
                data_rows = chain((first_row,), reader)

        for row in data_rows:
            if len(row) != expected_columns:
                raise ValueError("V2 pilot CSV has an unexpected column count")
            try:
                timestamp, unit = parse_binance_timestamp(row[timestamp_index])
            except (ValueError, IndexError) as exc:
                raise ValueError("V2 pilot timestamp is invalid") from exc
            if unit != "milliseconds":
                raise ValueError("V2 pilot timestamp unit is not milliseconds")
            if timestamp < start or timestamp >= end:
                raise ValueError("V2 pilot row is outside its target month")
            if timestamp in seen_timestamps:
                raise ValueError("V2 pilot CSV has a duplicate timestamp")
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError("V2 pilot timestamps are not strictly increasing")
            for index in numeric_indexes:
                _finite_decimal(row[index])
            seen_timestamps.add(timestamp)
            timestamps.append(timestamp)
            timestamp_units.add(unit)
            previous_timestamp = timestamp
            row_count += 1
    if row_count == 0:
        raise ValueError("V2 pilot CSV contains no data rows")
    if timestamp_units != {"milliseconds"}:
        raise ValueError("V2 pilot timestamp units are inconsistent")
    return {
        "csv_header": header,
        "csv_column_count": expected_columns,
        "row_count": row_count,
        "first_timestamp": timestamps[0],
        "last_timestamp": timestamps[-1],
        "timestamp_unit": "milliseconds",
        "duplicate_timestamp_count": 0,
        "out_of_month_row_count": 0,
        "non_finite_numeric_count": 0,
        "unexpected_column_count": 0,
        "schema_id": schema_id,
    }


def inspect_v2_pilot_archive(
    *,
    target: V2AcquisitionTarget,
    archive_path: Path,
    checksum_path: Path,
    evidence_root: Path,
    checksum_checked_at: datetime,
    preflight_checked_at: datetime,
    archive_content_length: int,
    archive_last_modified: str | None,
    archive_etag: str | None,
    protocol: V2DerivativesAcquisitionProtocol,
) -> V2PilotArchiveEvidence:
    archive_sha256 = file_sha256(archive_path)
    if archive_sha256 != target.census_checksum_sha256:
        raise ValueError("V2 pilot archive does not match its census checksum")
    archive_size = archive_path.stat().st_size
    if archive_size != archive_content_length:
        raise ValueError("V2 pilot archive does not match preflight content length")
    checksum_file_sha256 = file_sha256(checksum_path)
    with zipfile.ZipFile(archive_path) as archive:
        member, compressed, uncompressed = _validate_zip_members(
            archive,
            maximum_uncompressed_bytes=(
                protocol.resource_limits.maximum_single_archive_uncompressed_bytes
            ),
            maximum_expansion_ratio=(
                protocol.resource_limits.maximum_zip_expansion_ratio
            ),
        )
        row_evidence = _inspect_csv_rows(
            archive=archive,
            member=member,
            target=target,
        )
    return V2PilotArchiveEvidence(
        symbol=target.symbol,
        month=target.month,
        family_id=target.family_id,
        archive_url=target.archive_url,
        checksum_url=target.checksum_url,
        census_checksum_sha256=target.census_checksum_sha256,
        refreshed_checksum_sha256=target.census_checksum_sha256,
        checksum_checked_at=checksum_checked_at,
        checksum_file_sha256=checksum_file_sha256,
        preflight_checked_at=preflight_checked_at,
        archive_content_length=archive_content_length,
        archive_last_modified=archive_last_modified,
        archive_etag=archive_etag,
        archive_relative_path=archive_path.relative_to(evidence_root).as_posix(),
        checksum_relative_path=checksum_path.relative_to(evidence_root).as_posix(),
        archive_sha256=archive_sha256,
        archive_size_bytes=archive_size,
        zip_compressed_bytes=compressed,
        zip_uncompressed_bytes=uncompressed,
        csv_member_name=member.filename,
        **row_evidence,
    )


def _build_summary(
    records: list[V2PilotArchiveEvidence],
) -> V2PilotAcquisitionSummary:
    family_summaries = []
    for family_id in V2_REQUIRED_FAMILY_IDS:
        family_records = [
            record for record in records if record.family_id == family_id
        ]
        family_summaries.append(
            V2PilotFamilySummary(
                family_id=family_id,
                archive_bytes=sum(
                    record.archive_size_bytes for record in family_records
                ),
                uncompressed_bytes=sum(
                    record.zip_uncompressed_bytes for record in family_records
                ),
                row_count=sum(record.row_count for record in family_records),
                schema_ids=sorted(
                    {record.schema_id for record in family_records}
                ),
            )
        )
    return V2PilotAcquisitionSummary(
        total_archive_bytes=sum(record.archive_size_bytes for record in records),
        total_uncompressed_bytes=sum(
            record.zip_uncompressed_bytes for record in records
        ),
        total_rows=sum(record.row_count for record in records),
        family_summaries=family_summaries,
    )


def build_v2_pilot_acquisition_result(
    *,
    generated_at: datetime,
    protocol: V2DerivativesAcquisitionProtocol,
    runner_contract_hash: str,
    records: list[V2PilotArchiveEvidence],
    limitations: list[str],
) -> V2PilotAcquisitionResult:
    canonical_records = sorted(records, key=lambda item: item.key)
    if len(canonical_records) != len(protocol.targets):
        raise ValueError("V2 pilot result is incomplete")
    for target, record in zip(protocol.targets, canonical_records, strict=True):
        if (
            target.key != record.key
            or target.archive_url != record.archive_url
            or target.checksum_url != record.checksum_url
            or target.census_checksum_sha256 != record.census_checksum_sha256
        ):
            raise ValueError("V2 pilot result target lineage changed")
    summary = _build_summary(canonical_records)
    if summary.total_archive_bytes > (
        protocol.resource_limits.maximum_pilot_compressed_bytes
    ):
        raise ValueError("V2 pilot compressed-byte ceiling was exceeded")
    if summary.total_uncompressed_bytes > (
        protocol.resource_limits.maximum_pilot_uncompressed_bytes
    ):
        raise ValueError("V2 pilot uncompressed-byte ceiling was exceeded")
    payload = {
        "schema_version": V2_PILOT_RESULT_SCHEMA_VERSION,
        "result_id": "v2-derivatives-pilot-acquisition-result-v1",
        "result_version": "1.0.0",
        "generated_at": normalize_timestamp(generated_at),
        "status": "COMPLETE",
        "acquisition_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "source_census_result_evidence_hash": (
            protocol.source_census_result_evidence_hash
        ),
        "runner_contract_hash": normalize_sha256(runner_contract_hash),
        "records": canonical_records,
        "summary": summary,
        "decision": V2_PILOT_PASS_DECISION,
        "unresolved_request_count": 0,
        "integrity_failure_count": 0,
        "resource_gate_failure_count": 0,
        "schema_failure_count": 0,
        "permits_full_acquisition_protocol_design": True,
        "authorizes_full_archive_payload_download": False,
        "authorizes_market_data_import": False,
        "authorizes_strategy_return_calculation": False,
        "authorizes_mechanism_selection": False,
        "creates_candidate": False,
        "creates_strategy_eligibility": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "validation_data_loaded": False,
        "holdout_data_loaded": False,
        "forward_data_loaded": False,
        "strategy_outcome_fields_inspected": [],
        "limitations": sorted(set(limitations)),
    }
    return V2PilotAcquisitionResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_pilot_acquisition_result(
    *,
    result: V2PilotAcquisitionResult,
    protocol: V2DerivativesAcquisitionProtocol,
    current_runner_contract_hash: str,
    evidence_root: Path,
    inspect_local_archives: bool = True,
) -> dict[str, object]:
    reasons: list[str] = []
    if result.acquisition_protocol_evidence_hash != protocol.protocol_evidence_hash:
        reasons.append("pilot acquisition protocol binding changed")
    if result.runner_contract_hash != normalize_sha256(
        current_runner_contract_hash
    ):
        reasons.append("pilot runner contract changed")
    if inspect_local_archives:
        for record in result.records:
            archive_path = evidence_root / record.archive_relative_path
            checksum_path = evidence_root / record.checksum_relative_path
            if not archive_path.is_file() or not checksum_path.is_file():
                reasons.append(f"pilot local file is missing: {record.key}")
                continue
            if (
                archive_path.stat().st_size != record.archive_size_bytes
                or file_sha256(archive_path) != record.archive_sha256
                or file_sha256(checksum_path) != record.checksum_file_sha256
            ):
                reasons.append(f"pilot local file integrity changed: {record.key}")
    try:
        rebuilt = build_v2_pilot_acquisition_result(
            generated_at=result.generated_at,
            protocol=protocol,
            runner_contract_hash=result.runner_contract_hash,
            records=result.records,
            limitations=result.limitations,
        )
    except ValueError as exc:
        reasons.append(str(exc))
    else:
        if rebuilt != result:
            reasons.append("pilot result is not reproducible")
    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "result_evidence_hash": result.result_evidence_hash,
        "target_count": result.summary.target_count,
        "total_archive_bytes": result.summary.total_archive_bytes,
        "total_rows": result.summary.total_rows,
        "decision": result.decision,
    }
