import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.binance_vision import file_sha256, parse_checksum_file
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

DEVELOPMENT_BUNDLE_SCHEMA_VERSION = "aurex-development-dataset-bundle-v1"
DatasetRole = Literal["DECISION_CANDIDATE", "DEVELOPMENT_ONLY"]
DatasetStatus = Literal["READY", "BLOCKED"]


class CanonicalOhlcvInspection(BaseModel):
    row_count: int = Field(ge=0)
    expected_row_count: int = Field(gt=0)
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    missing_timestamps: list[datetime]
    canonical_csv_sha256: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("first_timestamp", "last_timestamp")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None

    @field_validator("missing_timestamps")
    @classmethod
    def normalize_missing_timestamps(cls, value: list[datetime]) -> list[datetime]:
        return sorted({normalize_timestamp(item) for item in value})

    @field_validator("canonical_csv_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class DevelopmentDatasetEntry(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    universe_role: DatasetRole
    timeframe: Literal["4h"] = "4h"
    partition_name: Literal["DEVELOPMENT"] = "DEVELOPMENT"
    partition_start: datetime
    partition_end: datetime
    archive_directory_relative_path: str = Field(min_length=1, max_length=1000)
    csv_relative_path: str = Field(min_length=1, max_length=1000)
    source_manifest_relative_path: str = Field(min_length=1, max_length=1000)
    source_manifest_sha256: str
    source_artifact_bundle_hash: str
    canonical_csv_sha256: str
    archive_count: int = Field(gt=0)
    row_count: int = Field(ge=0)
    expected_row_count: int = Field(gt=0)
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    missing_timestamps: list[datetime]
    timestamp_units: list[str] = Field(min_length=1)
    ohlcv_fields_inspected: list[str]
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    status: DatasetStatus
    entry_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("partition_start", "partition_end", "first_timestamp", "last_timestamp")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None

    @field_validator(
        "archive_directory_relative_path",
        "csv_relative_path",
        "source_manifest_relative_path",
    )
    @classmethod
    def validate_relative_paths(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator(
        "source_manifest_sha256",
        "source_artifact_bundle_hash",
        "canonical_csv_sha256",
        "entry_evidence_hash",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("missing_timestamps")
    @classmethod
    def normalize_missing(cls, value: list[datetime]) -> list[datetime]:
        return sorted({normalize_timestamp(item) for item in value})

    @field_validator(
        "timestamp_units",
        "ohlcv_fields_inspected",
        "strategy_outcome_fields_inspected",
    )
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_entry(self) -> "DevelopmentDatasetEntry":
        if self.partition_end <= self.partition_start:
            raise ValueError("Development dataset partition end must follow its start")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("Development dataset acquisition cannot inspect strategy outcomes")
        if self.ohlcv_fields_inspected != [
            "close",
            "high",
            "low",
            "open",
            "timestamp",
            "volume",
        ]:
            raise ValueError("Development dataset acquisition requires exact OHLCV fields")
        expected_status: DatasetStatus = (
            "READY"
            if self.row_count == self.expected_row_count and not self.missing_timestamps
            else "BLOCKED"
        )
        if self.status != expected_status:
            raise ValueError("Development dataset status does not match continuity evidence")
        expected_hash = universe_evidence_hash(self.model_dump(exclude={"entry_evidence_hash"}))
        if self.entry_evidence_hash != expected_hash:
            raise ValueError("Development dataset entry evidence hash does not match inputs")
        return self


class DevelopmentDatasetBundleSummary(BaseModel):
    dataset_count: int = Field(ge=0)
    decision_dataset_count: int = Field(ge=0)
    development_only_dataset_count: int = Field(ge=0)
    ready_dataset_count: int = Field(ge=0)
    blocked_dataset_count: int = Field(ge=0)
    total_rows: int = Field(ge=0)
    symbols: list[str]
    blocked_symbols: list[str]

    model_config = ConfigDict(extra="forbid")


class DevelopmentDatasetBundle(BaseModel):
    schema_version: Literal["aurex-development-dataset-bundle-v1"] = (
        DEVELOPMENT_BUNDLE_SCHEMA_VERSION
    )
    generated_at: datetime
    universe_manifest_evidence_hash: str
    contamination_ledger_hash: str
    builder_contract_hash: str
    partition_name: Literal["DEVELOPMENT"] = "DEVELOPMENT"
    partition_start: datetime
    partition_end: datetime
    timeframe: Literal["4h"] = "4h"
    entries: list[DevelopmentDatasetEntry]
    summary: DevelopmentDatasetBundleSummary
    limitations: list[str] = Field(min_length=1)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    status: DatasetStatus
    bundle_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at", "partition_start", "partition_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "universe_manifest_evidence_hash",
        "contamination_ledger_hash",
        "builder_contract_hash",
        "bundle_evidence_hash",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("limitations", "strategy_outcome_fields_inspected")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_bundle(self) -> "DevelopmentDatasetBundle":
        if self.partition_end <= self.partition_start:
            raise ValueError("Development bundle partition end must follow its start")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("Development dataset bundle cannot inspect strategy outcomes")
        symbols = [entry.symbol for entry in self.entries]
        if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
            raise ValueError("Development dataset entries must be uniquely sorted by symbol")
        expected_hash = universe_evidence_hash(self.model_dump(exclude={"bundle_evidence_hash"}))
        if self.bundle_evidence_hash != expected_hash:
            raise ValueError("Development dataset bundle evidence hash does not match inputs")
        return self


def inspect_canonical_ohlcv_csv(
    path: Path,
    *,
    partition_start: datetime,
    partition_end: datetime,
    interval: timedelta = timedelta(hours=4),
) -> CanonicalOhlcvInspection:
    start = normalize_timestamp(partition_start)
    end = normalize_timestamp(partition_end)
    if end <= start or interval.total_seconds() <= 0:
        raise ValueError("Invalid development OHLCV partition or interval")
    expected = list(iter_timestamps(start, end, interval))
    timestamps: list[datetime] = []
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.reader(source)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("Canonical OHLCV CSV is empty") from exc
        if header != ["timestamp", "open", "high", "low", "close", "volume"]:
            raise ValueError("Canonical OHLCV CSV header is not exact")
        previous: datetime | None = None
        for row_number, row in enumerate(reader, start=2):
            if len(row) != 6:
                raise ValueError(f"Canonical OHLCV row {row_number} must have six fields")
            timestamp = parse_utc_timestamp(row[0])
            if timestamp < start or timestamp >= end:
                raise ValueError("Canonical OHLCV contains a candle outside development")
            if (timestamp - start).total_seconds() % interval.total_seconds() != 0:
                raise ValueError("Canonical OHLCV timestamp is not aligned to 4h")
            if previous is not None and timestamp <= previous:
                raise ValueError("Canonical OHLCV timestamps must be strictly increasing")
            validate_ohlcv_values(row[1:], row_number)
            timestamps.append(timestamp)
            previous = timestamp
    observed = set(timestamps)
    missing = [timestamp for timestamp in expected if timestamp not in observed]
    return CanonicalOhlcvInspection(
        row_count=len(timestamps),
        expected_row_count=len(expected),
        first_timestamp=timestamps[0] if timestamps else None,
        last_timestamp=timestamps[-1] if timestamps else None,
        missing_timestamps=missing,
        canonical_csv_sha256=file_sha256(path),
    )


def build_development_dataset_entry(
    *,
    evidence_root: Path,
    symbol: str,
    universe_role: DatasetRole,
    partition_start: datetime,
    partition_end: datetime,
    archive_directory_relative_path: str,
    csv_relative_path: str,
    source_manifest_relative_path: str,
) -> DevelopmentDatasetEntry:
    normalized_symbol = symbol.strip().upper()
    archive_relative = normalize_relative_path(archive_directory_relative_path)
    csv_relative = normalize_relative_path(csv_relative_path)
    manifest_relative = normalize_relative_path(source_manifest_relative_path)
    archive_directory = safe_evidence_path(evidence_root, archive_relative)
    csv_path = safe_evidence_path(evidence_root, csv_relative)
    manifest_path = safe_evidence_path(evidence_root, manifest_relative)
    if not archive_directory.is_dir() or not csv_path.is_file() or not manifest_path.is_file():
        raise ValueError(f"Development dataset files are incomplete for {normalized_symbol}")
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Development source manifest is invalid JSON") from exc
    validate_prepared_manifest_identity(
        manifest,
        symbol=normalized_symbol,
        partition_start=partition_start,
        partition_end=partition_end,
    )
    inspection = inspect_canonical_ohlcv_csv(
        csv_path,
        partition_start=partition_start,
        partition_end=partition_end,
    )
    if manifest["canonical_csv_sha256"] != inspection.canonical_csv_sha256:
        raise ValueError("Prepared source manifest CSV hash does not match the dataset")
    if manifest["row_count"] != inspection.row_count:
        raise ValueError("Prepared source manifest row count does not match the dataset")
    source_artifacts = verify_source_artifacts(
        archive_directory,
        manifest["source_artifacts"],
        symbol=normalized_symbol,
        partition_start=partition_start,
        partition_end=partition_end,
    )
    payload = {
        "symbol": normalized_symbol,
        "universe_role": universe_role,
        "timeframe": "4h",
        "partition_name": "DEVELOPMENT",
        "partition_start": normalize_timestamp(partition_start),
        "partition_end": normalize_timestamp(partition_end),
        "archive_directory_relative_path": archive_relative,
        "csv_relative_path": csv_relative,
        "source_manifest_relative_path": manifest_relative,
        "source_manifest_sha256": file_sha256(manifest_path),
        "source_artifact_bundle_hash": universe_evidence_hash(source_artifacts),
        "canonical_csv_sha256": inspection.canonical_csv_sha256,
        "archive_count": len(source_artifacts),
        "row_count": inspection.row_count,
        "expected_row_count": inspection.expected_row_count,
        "first_timestamp": inspection.first_timestamp,
        "last_timestamp": inspection.last_timestamp,
        "missing_timestamps": inspection.missing_timestamps,
        "timestamp_units": manifest["transformation"]["timestamp_units"],
        "ohlcv_fields_inspected": [
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
            if inspection.row_count == inspection.expected_row_count
            and not inspection.missing_timestamps
            else "BLOCKED"
        ),
    }
    return DevelopmentDatasetEntry(
        **payload,
        entry_evidence_hash=universe_evidence_hash(payload),
    )


def build_development_dataset_bundle(
    *,
    generated_at: datetime,
    universe_manifest_evidence_hash: str,
    contamination_ledger_hash: str,
    builder_contract_hash: str,
    partition_start: datetime,
    partition_end: datetime,
    expected_roles: dict[str, DatasetRole],
    entries: list[DevelopmentDatasetEntry],
    limitations: list[str],
) -> DevelopmentDatasetBundle:
    ordered = sorted(entries, key=lambda entry: entry.symbol)
    roles = {symbol.strip().upper(): role for symbol, role in expected_roles.items()}
    if {entry.symbol: entry.universe_role for entry in ordered} != dict(sorted(roles.items())):
        raise ValueError("Development dataset entries do not match frozen universe roles")
    blocked = [entry.symbol for entry in ordered if entry.status == "BLOCKED"]
    summary = DevelopmentDatasetBundleSummary(
        dataset_count=len(ordered),
        decision_dataset_count=sum(
            entry.universe_role == "DECISION_CANDIDATE" for entry in ordered
        ),
        development_only_dataset_count=sum(
            entry.universe_role == "DEVELOPMENT_ONLY" for entry in ordered
        ),
        ready_dataset_count=sum(entry.status == "READY" for entry in ordered),
        blocked_dataset_count=len(blocked),
        total_rows=sum(entry.row_count for entry in ordered),
        symbols=[entry.symbol for entry in ordered],
        blocked_symbols=blocked,
    )
    payload = {
        "schema_version": DEVELOPMENT_BUNDLE_SCHEMA_VERSION,
        "generated_at": normalize_timestamp(generated_at),
        "universe_manifest_evidence_hash": normalize_sha256(
            universe_manifest_evidence_hash
        ),
        "contamination_ledger_hash": normalize_sha256(contamination_ledger_hash),
        "builder_contract_hash": normalize_sha256(builder_contract_hash),
        "partition_name": "DEVELOPMENT",
        "partition_start": normalize_timestamp(partition_start),
        "partition_end": normalize_timestamp(partition_end),
        "timeframe": "4h",
        "entries": ordered,
        "summary": summary,
        "limitations": sorted(set(limitations)),
        "strategy_outcome_fields_inspected": [],
        "status": "READY" if not blocked and ordered else "BLOCKED",
    }
    return DevelopmentDatasetBundle(
        **payload,
        bundle_evidence_hash=universe_evidence_hash(payload),
    )


def audit_development_dataset_bundle(
    bundle: DevelopmentDatasetBundle,
    *,
    evidence_root: Path,
    expected_roles: dict[str, DatasetRole],
    current_builder_contract_hash: str,
) -> dict[str, object]:
    reasons: list[str] = []
    rebuilt_entries: list[DevelopmentDatasetEntry] = []
    for entry in bundle.entries:
        try:
            rebuilt_entries.append(
                build_development_dataset_entry(
                    evidence_root=evidence_root,
                    symbol=entry.symbol,
                    universe_role=entry.universe_role,
                    partition_start=bundle.partition_start,
                    partition_end=bundle.partition_end,
                    archive_directory_relative_path=(
                        entry.archive_directory_relative_path
                    ),
                    csv_relative_path=entry.csv_relative_path,
                    source_manifest_relative_path=entry.source_manifest_relative_path,
                )
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reasons.append(f"entry_rebuild_failed:{entry.symbol}:{type(exc).__name__}")
    builder_matches = bundle.builder_contract_hash == normalize_sha256(
        current_builder_contract_hash
    )
    if not builder_matches:
        reasons.append("builder_contract_hash_mismatch")
    rebuilt: DevelopmentDatasetBundle | None = None
    if len(rebuilt_entries) == len(bundle.entries):
        try:
            rebuilt = build_development_dataset_bundle(
                generated_at=bundle.generated_at,
                universe_manifest_evidence_hash=(
                    bundle.universe_manifest_evidence_hash
                ),
                contamination_ledger_hash=bundle.contamination_ledger_hash,
                builder_contract_hash=current_builder_contract_hash,
                partition_start=bundle.partition_start,
                partition_end=bundle.partition_end,
                expected_roles=expected_roles,
                entries=rebuilt_entries,
                limitations=bundle.limitations,
            )
        except (ValueError, TypeError) as exc:
            reasons.append(f"bundle_rebuild_failed:{type(exc).__name__}")
    deterministic_match = rebuilt == bundle
    if not deterministic_match:
        reasons.append("deterministic_bundle_rebuild_mismatch")
    return {
        "status": "PASS" if not reasons else "BLOCKED",
        "builder_contract_hash_matches": builder_matches,
        "deterministic_bundle_rebuild_matches": deterministic_match,
        "recomputed_bundle_evidence_hash": (
            rebuilt.bundle_evidence_hash if rebuilt is not None else None
        ),
        "reasons": reasons,
    }


def verify_source_artifacts(
    archive_directory: Path,
    source_artifacts: list[dict],
    *,
    symbol: str,
    partition_start: datetime,
    partition_end: datetime,
) -> list[dict]:
    expected_names = {
        f"{symbol}-4h-{month}.zip"
        for month in required_months(partition_start, partition_end)
    }
    names = [artifact.get("filename") for artifact in source_artifacts]
    if set(names) != expected_names or len(names) != len(expected_names):
        raise ValueError("Prepared source artifacts do not match the development months")
    verified: list[dict] = []
    for artifact in sorted(source_artifacts, key=lambda item: item["filename"]):
        name = artifact["filename"]
        archive_path = archive_directory / name
        checksum_path = Path(f"{archive_path}.CHECKSUM")
        if not archive_path.is_file() or not checksum_path.is_file():
            raise ValueError(f"Development archive or checksum missing for {name}")
        expected_hash = parse_checksum_file(checksum_path, name)
        actual_hash = file_sha256(archive_path)
        if expected_hash != actual_hash:
            raise ValueError(f"Development archive checksum mismatch for {name}")
        if artifact.get("sha256") != actual_hash:
            raise ValueError(f"Prepared source artifact hash mismatch for {name}")
        if artifact.get("expected_sha256") != expected_hash:
            raise ValueError(f"Prepared expected checksum mismatch for {name}")
        if artifact.get("checksum_file_sha256") != file_sha256(checksum_path):
            raise ValueError(f"Prepared checksum file hash mismatch for {name}")
        if artifact.get("checksum_verified") is not True:
            raise ValueError(f"Prepared source artifact is not checksum-verified: {name}")
        verified.append(artifact)
    return verified


def validate_prepared_manifest_identity(
    manifest: dict,
    *,
    symbol: str,
    partition_start: datetime,
    partition_end: datetime,
) -> None:
    if manifest.get("schema_version") != "aurex-binance-vision-source-v1":
        raise ValueError("Unexpected prepared Binance Vision manifest schema")
    if manifest.get("source") != "binance-vision":
        raise ValueError("Development dataset source must be Binance Vision")
    if manifest.get("symbol") != symbol or manifest.get("timeframe") != "4h":
        raise ValueError("Prepared manifest identity does not match its universe market")
    transformation = manifest.get("transformation")
    if not isinstance(transformation, dict) or transformation.get("input_format") != (
        "binance_spot_kline_csv"
    ):
        raise ValueError("Prepared manifest transformation contract is missing")
    if transformation.get("output_schema") != "aurex_ohlcv_v1":
        raise ValueError("Prepared manifest output schema is not Aurex OHLCV")
    if not manifest.get("source_artifacts"):
        raise ValueError("Prepared manifest has no source artifacts")
    start = parse_utc_timestamp(manifest["data_start"])
    end = parse_utc_timestamp(manifest["data_end"])
    if start < normalize_timestamp(partition_start) or end >= normalize_timestamp(
        partition_end
    ):
        raise ValueError("Prepared manifest contains data outside development")


def validate_ohlcv_values(values: list[str], row_number: int) -> None:
    try:
        open_price, high, low, close, volume = [Decimal(value) for value in values]
    except InvalidOperation as exc:
        raise ValueError(f"Canonical OHLCV row {row_number} contains invalid decimals") from exc
    if not all(value.is_finite() for value in (open_price, high, low, close, volume)):
        raise ValueError(f"Canonical OHLCV row {row_number} contains non-finite values")
    if min(open_price, high, low, close) <= 0 or volume < 0:
        raise ValueError(f"Canonical OHLCV row {row_number} violates price or volume bounds")
    if high < max(open_price, low, close) or low > min(open_price, high, close):
        raise ValueError(f"Canonical OHLCV row {row_number} violates high/low bounds")


def required_months(start: datetime, end: datetime) -> list[str]:
    cursor = datetime(start.year, start.month, 1, tzinfo=UTC)
    boundary = normalize_timestamp(end)
    months: list[str] = []
    while cursor < boundary:
        months.append(f"{cursor.year:04d}-{cursor.month:02d}")
        cursor = (
            datetime(cursor.year + 1, 1, 1, tzinfo=UTC)
            if cursor.month == 12
            else datetime(cursor.year, cursor.month + 1, 1, tzinfo=UTC)
        )
    return months


def iter_timestamps(start: datetime, end: datetime, interval: timedelta):
    cursor = start
    while cursor < end:
        yield cursor
        cursor += interval


def parse_utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid canonical OHLCV timestamp {value!r}") from exc
    if parsed.utcoffset() is None:
        raise ValueError("Canonical OHLCV timestamps must include UTC timezone")
    normalized = parsed.astimezone(UTC)
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("Canonical OHLCV timestamps must be encoded in UTC")
    return normalized


def normalize_relative_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        raise ValueError("Development evidence paths must remain inside their root")
    if normalized.endswith("/"):
        raise ValueError("Development evidence path must identify a file or directory")
    return normalized


def safe_evidence_path(evidence_root: Path, relative_path: str) -> Path:
    root = evidence_root.resolve()
    candidate = (root / normalize_relative_path(relative_path)).resolve()
    if root not in candidate.parents:
        raise ValueError("Development evidence path escaped its root")
    return candidate
