import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.binance_vision import (
    file_sha256,
    parse_checksum_file,
)
from aurex.backtest_engine.development_bundle import (
    inspect_canonical_ohlcv_csv,
    normalize_relative_path,
    safe_evidence_path,
)
from aurex.backtest_engine.research_r4_protocol import (
    R4_DECISION_SYMBOLS,
    R4_REQUIRED_MONTHS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

VALIDATION_BUNDLE_SCHEMA_VERSION = "aurex-r4-validation-dataset-bundle-v1"
ArchiveRequestStatus = Literal["CHECKSUM_VERIFIED", "UNAVAILABLE_404"]
AvailabilityShape = Literal[
    "FULL_CONTINUOUS",
    "CONTIGUOUS_TERMINAL_SUFFIX_MISSING",
    "BLOCKED",
]
ValidationDatasetStatus = Literal["READY", "BLOCKED"]


class ValidationArchiveRequest(BaseModel):
    month: str = Field(pattern=r"^2025-(0[1-9]|1[0-2])$")
    archive_name: str = Field(min_length=1, max_length=200)
    archive_uri: str = Field(min_length=10, max_length=1000)
    checksum_uri: str = Field(min_length=10, max_length=1000)
    observed_at: datetime
    status: ArchiveRequestStatus
    archive_relative_path: str | None = Field(default=None, max_length=1000)
    checksum_relative_path: str | None = Field(default=None, max_length=1000)
    archive_sha256: str | None = None
    checksum_file_sha256: str | None = None
    expected_archive_sha256: str | None = None
    archive_size_bytes: int | None = Field(default=None, gt=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("archive_relative_path", "checksum_relative_path")
    @classmethod
    def normalize_optional_path(cls, value: str | None) -> str | None:
        return normalize_relative_path(value) if value is not None else None

    @field_validator(
        "archive_sha256",
        "checksum_file_sha256",
        "expected_archive_sha256",
    )
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_receipt(self) -> "ValidationArchiveRequest":
        if not self.archive_name.endswith(f"-{self.month}.zip"):
            raise ValueError("Validation archive name does not match its month")
        artifact_values = (
            self.archive_relative_path,
            self.checksum_relative_path,
            self.archive_sha256,
            self.checksum_file_sha256,
            self.expected_archive_sha256,
            self.archive_size_bytes,
        )
        if self.status == "CHECKSUM_VERIFIED":
            if any(value is None for value in artifact_values):
                raise ValueError("Verified validation archive requires complete evidence")
            if self.archive_sha256 != self.expected_archive_sha256:
                raise ValueError("Validation archive checksum evidence does not match")
        elif any(value is not None for value in artifact_values):
            raise ValueError("Unavailable validation archive cannot name local artifacts")
        if not self.archive_uri.startswith("https://"):
            raise ValueError("Validation archive URI must use HTTPS")
        if self.checksum_uri != f"{self.archive_uri}.CHECKSUM":
            raise ValueError("Validation checksum URI must match its archive URI")
        return self


class ValidationDatasetEntry(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    universe_role: Literal["DECISION_CANDIDATE"] = "DECISION_CANDIDATE"
    timeframe: Literal["4h"] = "4h"
    partition_name: Literal["VALIDATION"] = "VALIDATION"
    partition_start: datetime
    partition_end: datetime
    archive_directory_relative_path: str = Field(min_length=1, max_length=1000)
    csv_relative_path: str = Field(min_length=1, max_length=1000)
    source_manifest_relative_path: str = Field(min_length=1, max_length=1000)
    source_manifest_sha256: str
    source_artifact_bundle_hash: str
    canonical_csv_sha256: str
    archive_requests: list[ValidationArchiveRequest] = Field(
        min_length=12, max_length=12
    )
    verified_archive_count: int = Field(ge=0, le=12)
    unavailable_archive_count: int = Field(ge=0, le=12)
    unavailable_archive_months: list[str]
    row_count: int = Field(ge=0)
    expected_row_count: Literal[2190] = 2190
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    missing_timestamps: list[datetime]
    availability_shape: AvailabilityShape
    terminal_missing_start: datetime | None = None
    timestamp_units: list[str] = Field(min_length=1)
    inspected_market_fields: list[str]
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    status: ValidationDatasetStatus
    entry_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "partition_start",
        "partition_end",
        "first_timestamp",
        "last_timestamp",
        "terminal_missing_start",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None

    @field_validator(
        "archive_directory_relative_path",
        "csv_relative_path",
        "source_manifest_relative_path",
    )
    @classmethod
    def normalize_paths(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator(
        "source_manifest_sha256",
        "source_artifact_bundle_hash",
        "canonical_csv_sha256",
        "entry_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("missing_timestamps")
    @classmethod
    def normalize_missing(cls, value: list[datetime]) -> list[datetime]:
        return sorted({normalize_timestamp(item) for item in value})

    @field_validator(
        "unavailable_archive_months",
        "timestamp_units",
        "inspected_market_fields",
        "strategy_outcome_fields_inspected",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_entry(self) -> "ValidationDatasetEntry":
        if self.symbol not in R4_DECISION_SYMBOLS:
            raise ValueError("Validation dataset symbol is outside the frozen universe")
        if self.partition_start.isoformat() != "2025-01-01T00:00:00+00:00":
            raise ValueError("Validation dataset start is fixed")
        if self.partition_end.isoformat() != "2026-01-01T00:00:00+00:00":
            raise ValueError("Validation dataset end is fixed")
        months = [request.month for request in self.archive_requests]
        if months != list(R4_REQUIRED_MONTHS):
            raise ValueError("Validation archive requests must cover every 2025 month")
        if len(months) != len(set(months)):
            raise ValueError("Validation archive requests must be unique")
        verified = sum(
            request.status == "CHECKSUM_VERIFIED"
            for request in self.archive_requests
        )
        unavailable = sum(
            request.status == "UNAVAILABLE_404"
            for request in self.archive_requests
        )
        if (
            self.verified_archive_count != verified
            or self.unavailable_archive_count != unavailable
            or verified + unavailable != 12
        ):
            raise ValueError("Validation archive request summary is inconsistent")
        expected_unavailable = sorted(
            request.month
            for request in self.archive_requests
            if request.status == "UNAVAILABLE_404"
        )
        if self.unavailable_archive_months != expected_unavailable:
            raise ValueError("Validation unavailable months do not match receipts")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("Validation data acquisition cannot inspect outcomes")
        if self.inspected_market_fields != [
            "close",
            "high",
            "low",
            "open",
            "timestamp",
            "volume",
        ]:
            raise ValueError("Validation data inspection is limited to exact OHLCV")
        expected_shape, expected_terminal = classify_availability(
            partition_start=self.partition_start,
            partition_end=self.partition_end,
            row_count=self.row_count,
            expected_row_count=self.expected_row_count,
            first_timestamp=self.first_timestamp,
            last_timestamp=self.last_timestamp,
            missing_timestamps=self.missing_timestamps,
        )
        if (
            self.availability_shape != expected_shape
            or self.terminal_missing_start != expected_terminal
        ):
            raise ValueError("Validation availability classification is inconsistent")
        expected_status: ValidationDatasetStatus = (
            "READY"
            if self.availability_shape
            in {"FULL_CONTINUOUS", "CONTIGUOUS_TERMINAL_SUFFIX_MISSING"}
            else "BLOCKED"
        )
        if self.status != expected_status:
            raise ValueError("Validation dataset status does not match availability")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"entry_evidence_hash"})
        )
        if self.entry_evidence_hash != expected_hash:
            raise ValueError("Validation dataset entry hash does not match evidence")
        return self


class ValidationDatasetBundleSummary(BaseModel):
    dataset_count: Literal[35] = 35
    ready_dataset_count: int = Field(ge=0, le=35)
    blocked_dataset_count: int = Field(ge=0, le=35)
    full_continuous_count: int = Field(ge=0, le=35)
    terminal_unavailable_count: int = Field(ge=0, le=35)
    total_rows: int = Field(ge=0)
    verified_archive_count: int = Field(ge=0, le=420)
    unavailable_archive_count: int = Field(ge=0, le=420)
    symbols: list[str] = Field(min_length=35, max_length=35)
    blocked_symbols: list[str]
    terminal_unavailable_symbols: list[str]

    model_config = ConfigDict(extra="forbid")


class ValidationDatasetBundle(BaseModel):
    schema_version: Literal["aurex-r4-validation-dataset-bundle-v1"] = (
        VALIDATION_BUNDLE_SCHEMA_VERSION
    )
    generated_at: datetime
    r4_candidate_protocol_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    contamination_ledger_hash: str
    builder_contract_hash: str
    partition_name: Literal["VALIDATION"] = "VALIDATION"
    partition_start: datetime
    partition_end: datetime
    timeframe: Literal["4h"] = "4h"
    entries: list[ValidationDatasetEntry] = Field(min_length=35, max_length=35)
    summary: ValidationDatasetBundleSummary
    limitations: list[str] = Field(min_length=1)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    status: ValidationDatasetStatus
    bundle_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at", "partition_start", "partition_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "r4_candidate_protocol_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "contamination_ledger_hash",
        "builder_contract_hash",
        "bundle_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("limitations", "strategy_outcome_fields_inspected")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_bundle(self) -> "ValidationDatasetBundle":
        if self.partition_start.isoformat() != "2025-01-01T00:00:00+00:00":
            raise ValueError("Validation bundle start is fixed")
        if self.partition_end.isoformat() != "2026-01-01T00:00:00+00:00":
            raise ValueError("Validation bundle end is fixed")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("Validation bundle cannot inspect strategy outcomes")
        symbols = [entry.symbol for entry in self.entries]
        if tuple(symbols) != R4_DECISION_SYMBOLS:
            raise ValueError("Validation bundle must preserve the exact R4 universe")
        expected_summary = build_summary(self.entries)
        if self.summary != expected_summary:
            raise ValueError("Validation bundle summary is inconsistent")
        expected_status: ValidationDatasetStatus = (
            "READY" if self.summary.blocked_dataset_count == 0 else "BLOCKED"
        )
        if self.status != expected_status:
            raise ValueError("Validation bundle status does not match its entries")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"bundle_evidence_hash"})
        )
        if self.bundle_evidence_hash != expected_hash:
            raise ValueError("Validation bundle hash does not match evidence")
        return self


def classify_availability(
    *,
    partition_start: datetime,
    partition_end: datetime,
    row_count: int,
    expected_row_count: int,
    first_timestamp: datetime | None,
    last_timestamp: datetime | None,
    missing_timestamps: list[datetime],
) -> tuple[AvailabilityShape, datetime | None]:
    start = normalize_timestamp(partition_start)
    end = normalize_timestamp(partition_end)
    missing = sorted({normalize_timestamp(item) for item in missing_timestamps})
    if (
        end <= start
        or expected_row_count != 2190
        or row_count + len(missing) != expected_row_count
        or first_timestamp is None
        or last_timestamp is None
        or normalize_timestamp(first_timestamp) != start
    ):
        return "BLOCKED", None
    last = normalize_timestamp(last_timestamp)
    if not missing:
        expected_last = end - timedelta(hours=4)
        return (
            ("FULL_CONTINUOUS", None)
            if row_count == expected_row_count and last == expected_last
            else ("BLOCKED", None)
        )
    terminal_start = missing[0]
    expected_terminal = list(iter_4h_timestamps(terminal_start, end))
    if (
        missing == expected_terminal
        and last + timedelta(hours=4) == terminal_start
        and row_count > 0
    ):
        return "CONTIGUOUS_TERMINAL_SUFFIX_MISSING", terminal_start
    return "BLOCKED", None


def build_validation_dataset_entry(
    *,
    evidence_root: Path,
    symbol: str,
    partition_start: datetime,
    partition_end: datetime,
    archive_directory_relative_path: str,
    csv_relative_path: str,
    source_manifest_relative_path: str,
) -> ValidationDatasetEntry:
    normalized_symbol = symbol.strip().upper()
    archive_relative = normalize_relative_path(archive_directory_relative_path)
    csv_relative = normalize_relative_path(csv_relative_path)
    manifest_relative = normalize_relative_path(source_manifest_relative_path)
    archive_directory = safe_evidence_path(evidence_root, archive_relative)
    csv_path = safe_evidence_path(evidence_root, csv_relative)
    manifest_path = safe_evidence_path(evidence_root, manifest_relative)
    if (
        not archive_directory.is_dir()
        or not csv_path.is_file()
        or not manifest_path.is_file()
    ):
        raise ValueError(f"Validation dataset files are incomplete for {normalized_symbol}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Validation source manifest is invalid JSON") from exc
    if (
        manifest.get("symbol") != normalized_symbol
        or manifest.get("timeframe") != "4h"
    ):
        raise ValueError("Validation source manifest identity does not match")
    if manifest.get("strategy_outcome_fields_inspected") != []:
        raise ValueError("Validation source manifest inspected strategy outcomes")
    requests = [
        ValidationArchiveRequest.model_validate(item)
        for item in manifest.get("validation_archive_requests", [])
    ]
    if len(requests) != 12:
        raise ValueError("Validation source manifest requires 12 archive requests")
    verify_archive_requests(
        requests,
        evidence_root=evidence_root,
        expected_symbol=normalized_symbol,
        expected_archive_directory=archive_directory,
    )
    verified_names = sorted(
        request.archive_name
        for request in requests
        if request.status == "CHECKSUM_VERIFIED"
    )
    source_artifacts = manifest.get("source_artifacts")
    if not isinstance(source_artifacts, list) or sorted(
        item.get("filename")
        for item in source_artifacts
        if isinstance(item, dict)
    ) != verified_names:
        raise ValueError("Validation source artifacts do not match archive receipts")
    receipt_by_name = {
        request.archive_name: request
        for request in requests
        if request.status == "CHECKSUM_VERIFIED"
    }
    for artifact in source_artifacts:
        receipt = receipt_by_name[artifact["filename"]]
        if (
            artifact.get("sha256") != receipt.archive_sha256
            or artifact.get("checksum_file_sha256")
            != receipt.checksum_file_sha256
            or artifact.get("expected_sha256")
            != receipt.expected_archive_sha256
            or artifact.get("size_bytes") != receipt.archive_size_bytes
            or artifact.get("checksum_verified") is not True
        ):
            raise ValueError(
                "Validation source artifact evidence differs from its receipt"
            )
    inspection = inspect_canonical_ohlcv_csv(
        csv_path,
        partition_start=partition_start,
        partition_end=partition_end,
    )
    if manifest.get("canonical_csv_sha256") != inspection.canonical_csv_sha256:
        raise ValueError("Validation source manifest CSV hash does not match")
    if manifest.get("row_count") != inspection.row_count:
        raise ValueError("Validation source manifest row count does not match")
    shape, terminal_start = classify_availability(
        partition_start=partition_start,
        partition_end=partition_end,
        row_count=inspection.row_count,
        expected_row_count=inspection.expected_row_count,
        first_timestamp=inspection.first_timestamp,
        last_timestamp=inspection.last_timestamp,
        missing_timestamps=inspection.missing_timestamps,
    )
    payload = {
        "symbol": normalized_symbol,
        "universe_role": "DECISION_CANDIDATE",
        "timeframe": "4h",
        "partition_name": "VALIDATION",
        "partition_start": normalize_timestamp(partition_start),
        "partition_end": normalize_timestamp(partition_end),
        "archive_directory_relative_path": archive_relative,
        "csv_relative_path": csv_relative,
        "source_manifest_relative_path": manifest_relative,
        "source_manifest_sha256": file_sha256(manifest_path),
        "source_artifact_bundle_hash": universe_evidence_hash(requests),
        "canonical_csv_sha256": inspection.canonical_csv_sha256,
        "archive_requests": requests,
        "verified_archive_count": sum(
            request.status == "CHECKSUM_VERIFIED" for request in requests
        ),
        "unavailable_archive_count": sum(
            request.status == "UNAVAILABLE_404" for request in requests
        ),
        "unavailable_archive_months": [
            request.month
            for request in requests
            if request.status == "UNAVAILABLE_404"
        ],
        "row_count": inspection.row_count,
        "expected_row_count": inspection.expected_row_count,
        "first_timestamp": inspection.first_timestamp,
        "last_timestamp": inspection.last_timestamp,
        "missing_timestamps": inspection.missing_timestamps,
        "availability_shape": shape,
        "terminal_missing_start": terminal_start,
        "timestamp_units": manifest["transformation"]["timestamp_units"],
        "inspected_market_fields": [
            "close",
            "high",
            "low",
            "open",
            "timestamp",
            "volume",
        ],
        "strategy_outcome_fields_inspected": [],
        "status": (
            "READY"
            if shape
            in {"FULL_CONTINUOUS", "CONTIGUOUS_TERMINAL_SUFFIX_MISSING"}
            else "BLOCKED"
        ),
    }
    return ValidationDatasetEntry(
        **payload,
        entry_evidence_hash=universe_evidence_hash(payload),
    )


def build_validation_dataset_bundle(
    *,
    generated_at: datetime,
    r4_candidate_protocol_evidence_hash: str,
    universe_manifest_evidence_hash: str,
    development_dataset_bundle_evidence_hash: str,
    contamination_ledger_hash: str,
    builder_contract_hash: str,
    entries: list[ValidationDatasetEntry],
    limitations: list[str],
) -> ValidationDatasetBundle:
    ordered = sorted(entries, key=lambda entry: entry.symbol)
    summary = build_summary(ordered)
    payload = {
        "schema_version": VALIDATION_BUNDLE_SCHEMA_VERSION,
        "generated_at": normalize_timestamp(generated_at),
        "r4_candidate_protocol_evidence_hash": (
            r4_candidate_protocol_evidence_hash
        ),
        "universe_manifest_evidence_hash": universe_manifest_evidence_hash,
        "development_dataset_bundle_evidence_hash": (
            development_dataset_bundle_evidence_hash
        ),
        "contamination_ledger_hash": contamination_ledger_hash,
        "builder_contract_hash": builder_contract_hash,
        "partition_name": "VALIDATION",
        "partition_start": normalize_timestamp(
            datetime.fromisoformat("2025-01-01T00:00:00+00:00")
        ),
        "partition_end": normalize_timestamp(
            datetime.fromisoformat("2026-01-01T00:00:00+00:00")
        ),
        "timeframe": "4h",
        "entries": ordered,
        "summary": summary,
        "limitations": sorted(set(limitations)),
        "strategy_outcome_fields_inspected": [],
        "status": "READY" if summary.blocked_dataset_count == 0 else "BLOCKED",
    }
    return ValidationDatasetBundle(
        **payload,
        bundle_evidence_hash=universe_evidence_hash(payload),
    )


def build_summary(
    entries: list[ValidationDatasetEntry],
) -> ValidationDatasetBundleSummary:
    return ValidationDatasetBundleSummary(
        ready_dataset_count=sum(entry.status == "READY" for entry in entries),
        blocked_dataset_count=sum(entry.status == "BLOCKED" for entry in entries),
        full_continuous_count=sum(
            entry.availability_shape == "FULL_CONTINUOUS" for entry in entries
        ),
        terminal_unavailable_count=sum(
            entry.availability_shape
            == "CONTIGUOUS_TERMINAL_SUFFIX_MISSING"
            for entry in entries
        ),
        total_rows=sum(entry.row_count for entry in entries),
        verified_archive_count=sum(
            entry.verified_archive_count for entry in entries
        ),
        unavailable_archive_count=sum(
            entry.unavailable_archive_count for entry in entries
        ),
        symbols=[entry.symbol for entry in entries],
        blocked_symbols=[
            entry.symbol for entry in entries if entry.status == "BLOCKED"
        ],
        terminal_unavailable_symbols=[
            entry.symbol
            for entry in entries
            if entry.availability_shape
            == "CONTIGUOUS_TERMINAL_SUFFIX_MISSING"
        ],
    )


def audit_validation_dataset_bundle(
    bundle: ValidationDatasetBundle,
    *,
    evidence_root: Path,
    current_builder_contract_hash: str,
) -> dict[str, object]:
    reasons: list[str] = []
    if bundle.builder_contract_hash != current_builder_contract_hash:
        reasons.append("builder_contract_hash_mismatch")
    rebuilt_entries: list[ValidationDatasetEntry] = []
    for entry in bundle.entries:
        try:
            rebuilt = build_validation_dataset_entry(
                evidence_root=evidence_root,
                symbol=entry.symbol,
                partition_start=bundle.partition_start,
                partition_end=bundle.partition_end,
                archive_directory_relative_path=(
                    entry.archive_directory_relative_path
                ),
                csv_relative_path=entry.csv_relative_path,
                source_manifest_relative_path=entry.source_manifest_relative_path,
            )
        except (OSError, ValueError) as exc:
            reasons.append(f"{entry.symbol}:{type(exc).__name__}:{exc}")
            continue
        if rebuilt != entry:
            reasons.append(f"{entry.symbol}:entry_rebuild_mismatch")
        rebuilt_entries.append(rebuilt)
    if len(rebuilt_entries) == len(bundle.entries):
        rebuilt = build_validation_dataset_bundle(
            generated_at=bundle.generated_at,
            r4_candidate_protocol_evidence_hash=(
                bundle.r4_candidate_protocol_evidence_hash
            ),
            universe_manifest_evidence_hash=bundle.universe_manifest_evidence_hash,
            development_dataset_bundle_evidence_hash=(
                bundle.development_dataset_bundle_evidence_hash
            ),
            contamination_ledger_hash=bundle.contamination_ledger_hash,
            builder_contract_hash=current_builder_contract_hash,
            entries=rebuilt_entries,
            limitations=bundle.limitations,
        )
        if rebuilt != bundle:
            reasons.append("bundle_rebuild_mismatch")
    return {
        "status": "PASS" if not reasons else "BLOCKED",
        "reasons": reasons,
        "bundle_evidence_hash": bundle.bundle_evidence_hash,
    }


def verify_archive_requests(
    requests: list[ValidationArchiveRequest],
    *,
    evidence_root: Path,
    expected_symbol: str,
    expected_archive_directory: Path,
) -> None:
    resolved_archive_directory = expected_archive_directory.resolve()
    for request in requests:
        expected_name = f"{expected_symbol}-4h-{request.month}.zip"
        if request.archive_name != expected_name:
            raise ValueError("Validation archive request symbol is inconsistent")
        if request.status == "CHECKSUM_VERIFIED":
            archive_path = safe_evidence_path(
                evidence_root, request.archive_relative_path or ""
            )
            checksum_path = safe_evidence_path(
                evidence_root, request.checksum_relative_path or ""
            )
            if (
                archive_path.parent != resolved_archive_directory
                or archive_path.name != expected_name
                or checksum_path
                != Path(f"{resolved_archive_directory / expected_name}.CHECKSUM")
            ):
                raise ValueError("Validation receipt paths changed scope")
            if not archive_path.is_file() or not checksum_path.is_file():
                raise ValueError("Verified validation archive files are missing")
            if (
                file_sha256(archive_path) != request.archive_sha256
                or file_sha256(checksum_path) != request.checksum_file_sha256
                or archive_path.stat().st_size != request.archive_size_bytes
            ):
                raise ValueError("Validation archive file evidence changed")
            expected = parse_checksum_file(checksum_path, archive_path.name)
            if (
                expected != request.expected_archive_sha256
                or expected != request.archive_sha256
            ):
                raise ValueError("Validation archive checksum no longer verifies")
        else:
            if request.archive_relative_path or request.checksum_relative_path:
                raise ValueError("Unavailable request unexpectedly names artifacts")
            unavailable_archive = resolved_archive_directory / expected_name
            unavailable_checksum = Path(f"{unavailable_archive}.CHECKSUM")
            if unavailable_archive.exists() or unavailable_checksum.exists():
                raise ValueError("Unavailable validation archive now has local files")


def iter_4h_timestamps(start: datetime, end: datetime):
    cursor = normalize_timestamp(start)
    boundary = normalize_timestamp(end)
    while cursor < boundary:
        yield cursor
        cursor += timedelta(hours=4)
