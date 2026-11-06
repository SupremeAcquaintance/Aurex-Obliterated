import csv
import io
import json
import math
import re
import urllib.parse
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.binance_vision import parse_binance_timestamp
from aurex.backtest_engine.universe import (
    LiquiditySourceMethod,
    UniverseSourceReceipt,
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

ENUMERATION_ARTIFACT_SCHEMA_VERSION = "aurex-universe-enumeration-input-v1"
LIQUIDITY_ARTIFACT_SCHEMA_VERSION = "aurex-universe-liquidity-input-v1"


class StoredSourcePayload(UniverseSourceReceipt):
    relative_path: str = Field(min_length=1, max_length=1000)
    http_status: int = Field(default=200, ge=100, le=599)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        candidate = PurePosixPath(normalized)
        if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
            raise ValueError("Stored source payload path must remain inside its evidence root")
        if normalized.endswith("/"):
            raise ValueError("Stored source payload path must identify a file")
        return normalized

    def receipt(self) -> UniverseSourceReceipt:
        return UniverseSourceReceipt.model_validate(
            self.model_dump(exclude={"relative_path", "http_status"})
        )


class ParsedS3Listing(BaseModel):
    prefix: str
    delimiter: str | None
    marker: str | None
    next_marker: str | None
    is_truncated: bool
    common_prefixes: list[str]
    keys: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("common_prefixes", "keys")
    @classmethod
    def sort_unique_values(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_pagination(self) -> "ParsedS3Listing":
        if self.is_truncated and not self.next_marker:
            raise ValueError("Truncated S3 listings require a continuation marker")
        return self


class S3ListingSnapshot(ParsedS3Listing):
    payload: StoredSourcePayload


class HistoricalMarketArchiveIndex(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    base_asset: str = Field(min_length=1, max_length=32)
    quote_asset: str = Field(min_length=1, max_length=32)
    listing_pages: list[S3ListingSnapshot] = Field(min_length=1)
    archive_months: list[str]
    checksum_sidecar_months: list[str]
    archive_keys: list[str]
    checksum_sidecar_keys: list[str]
    listing_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol", "base_asset", "quote_asset")
    @classmethod
    def normalize_upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "archive_months",
        "checksum_sidecar_months",
        "archive_keys",
        "checksum_sidecar_keys",
    )
    @classmethod
    def sort_unique_values(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @field_validator("listing_evidence_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_symbol_and_hash(self) -> "HistoricalMarketArchiveIndex":
        if self.symbol != f"{self.base_asset}{self.quote_asset}":
            raise ValueError("Historical market symbol must equal base plus quote asset")
        expected = market_listing_evidence_hash(
            symbol=self.symbol,
            listing_pages=self.listing_pages,
            archive_keys=self.archive_keys,
            checksum_sidecar_keys=self.checksum_sidecar_keys,
        )
        if self.listing_evidence_hash != expected:
            raise ValueError("Historical market listing evidence hash does not match inputs")
        return self


class UniverseEnumerationInputArtifact(BaseModel):
    schema_version: Literal["aurex-universe-enumeration-input-v1"] = (
        ENUMERATION_ARTIFACT_SCHEMA_VERSION
    )
    generated_at: datetime
    endpoint: str = Field(min_length=1, max_length=2000)
    root_prefix: str = Field(min_length=1, max_length=500)
    quote_asset: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(min_length=1, max_length=16)
    root_pages: list[S3ListingSnapshot] = Field(min_length=1)
    all_historical_symbols: list[str] = Field(min_length=1)
    markets: list[HistoricalMarketArchiveIndex]
    enumeration_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("quote_asset")
    @classmethod
    def normalize_quote_asset(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timeframe")
    @classmethod
    def normalize_timeframe(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("all_historical_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})

    @field_validator("enumeration_evidence_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_artifact(self) -> "UniverseEnumerationInputArtifact":
        if not self.endpoint.startswith("https://"):
            raise ValueError("Universe enumeration endpoint must use HTTPS")
        market_symbols = [market.symbol for market in self.markets]
        if market_symbols != sorted(market_symbols) or len(market_symbols) != len(
            set(market_symbols)
        ):
            raise ValueError("Historical markets must be uniquely sorted by symbol")
        expected_symbols = [
            symbol for symbol in self.all_historical_symbols if symbol.endswith(self.quote_asset)
        ]
        if market_symbols != expected_symbols:
            raise ValueError("Historical quote-asset markets must preserve every enumerated symbol")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"enumeration_evidence_hash"})
        )
        if self.enumeration_evidence_hash != expected_hash:
            raise ValueError("Universe enumeration evidence hash does not match inputs")
        return self

    def source_payloads(self) -> list[StoredSourcePayload]:
        payloads = [page.payload for page in self.root_pages]
        payloads.extend(
            page.payload for market in self.markets for page in market.listing_pages
        )
        return sorted(payloads, key=lambda item: item.receipt_id)


class DailyQuoteVolumePoint(BaseModel):
    open_time: datetime
    quote_asset_volume: Decimal = Field(ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("open_time")
    @classmethod
    def normalize_open_time(cls, value: datetime) -> datetime:
        timestamp = normalize_timestamp(value)
        if timestamp.time() != datetime.min.time():
            raise ValueError("Daily liquidity points must open at 00:00:00 UTC")
        return timestamp


class SymbolLiquidityInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    source_method: LiquiditySourceMethod
    source_payloads: list[StoredSourcePayload]
    points: list[DailyQuoteVolumePoint]
    source_evidence_hash: str | None = None
    daily_quote_volume_evidence_hash: str | None = None
    source_error: str | None = Field(default=None, max_length=500)
    market_fields_inspected: list[str]
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("market_fields_inspected", "strategy_outcome_fields_inspected")
    @classmethod
    def normalize_fields(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @field_validator("source_evidence_hash", "daily_quote_volume_evidence_hash")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_series(self) -> "SymbolLiquidityInput":
        if self.strategy_outcome_fields_inspected:
            raise ValueError("Liquidity selection inputs cannot inspect strategy outcomes")
        if self.market_fields_inspected != ["open_time", "quote_asset_volume"]:
            raise ValueError("Liquidity inputs may inspect only open time and quote volume")
        ordered_points = sorted(
            self.points,
            key=lambda point: (point.open_time, point.quote_asset_volume),
        )
        if self.points != ordered_points:
            raise ValueError("Daily quote-volume points must be sorted")
        receipt_ids = [payload.receipt_id for payload in self.source_payloads]
        if receipt_ids != sorted(receipt_ids) or len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("Liquidity source payloads must be uniquely sorted")
        if self.source_method == "UNAVAILABLE":
            if self.points or self.source_error is None:
                raise ValueError("Unavailable liquidity inputs require no daily points")
            expected_source_hash = (
                source_payload_bundle_hash(self.source_payloads)
                if self.source_payloads
                else None
            )
            if self.source_evidence_hash != expected_source_hash:
                raise ValueError("Unavailable source evidence hash does not match payloads")
            if self.daily_quote_volume_evidence_hash:
                raise ValueError("Unavailable liquidity inputs cannot contain daily evidence")
            return self
        if not self.points or not self.source_payloads or self.source_error is not None:
            raise ValueError("Available liquidity inputs require points and source payloads")
        expected_source_hash = source_payload_bundle_hash(self.source_payloads)
        expected_daily_hash = daily_quote_volume_evidence_hash(self.points)
        if self.source_evidence_hash != expected_source_hash:
            raise ValueError("Liquidity source evidence hash does not match payloads")
        if self.daily_quote_volume_evidence_hash != expected_daily_hash:
            raise ValueError("Daily quote-volume evidence hash does not match points")
        return self


class UniverseLiquidityInputArtifact(BaseModel):
    schema_version: Literal["aurex-universe-liquidity-input-v1"] = (
        LIQUIDITY_ARTIFACT_SCHEMA_VERSION
    )
    generated_at: datetime
    selection_start: datetime
    selection_end: datetime
    series: list[SymbolLiquidityInput]
    liquidity_input_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at", "selection_start", "selection_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("liquidity_input_evidence_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_artifact(self) -> "UniverseLiquidityInputArtifact":
        if self.selection_end <= self.selection_start:
            raise ValueError("Liquidity selection end must be later than its start")
        symbols = [item.symbol for item in self.series]
        if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
            raise ValueError("Liquidity input series must be uniquely sorted by symbol")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"liquidity_input_evidence_hash"})
        )
        if self.liquidity_input_evidence_hash != expected_hash:
            raise ValueError("Universe liquidity input evidence hash does not match inputs")
        return self

    def source_payloads(self) -> list[StoredSourcePayload]:
        return sorted(
            [payload for item in self.series for payload in item.source_payloads],
            key=lambda payload: payload.receipt_id,
        )


class DailyLiquiditySummary(BaseModel):
    daily_row_count: int = Field(ge=0)
    active_day_count: int = Field(ge=0)
    duplicate_day_count: int = Field(ge=0)
    missing_day_count: int = Field(ge=0)
    median_daily_quote_volume: Decimal | None = Field(default=None, ge=0)
    p10_daily_quote_volume: Decimal | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


def parse_s3_listing_xml(payload: bytes) -> ParsedS3Listing:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid S3 listing XML") from exc
    if local_name(root.tag) != "ListBucketResult":
        raise ValueError("Unexpected S3 listing root element")

    prefix = child_text(root, "Prefix") or ""
    delimiter = child_text(root, "Delimiter")
    marker = child_text(root, "Marker")
    next_marker = child_text(root, "NextMarker")
    is_truncated = (child_text(root, "IsTruncated") or "false").lower() == "true"
    common_prefixes = [
        child_text(element, "Prefix") or ""
        for element in children_named(root, "CommonPrefixes")
    ]
    keys = [
        child_text(element, "Key") or ""
        for element in children_named(root, "Contents")
    ]
    common_prefixes = [value for value in common_prefixes if value]
    keys = [value for value in keys if value]
    if is_truncated and not next_marker:
        candidates = sorted([*common_prefixes, *keys])
        next_marker = candidates[-1] if candidates else None
    return ParsedS3Listing(
        prefix=prefix,
        delimiter=delimiter,
        marker=marker,
        next_marker=next_marker,
        is_truncated=is_truncated,
        common_prefixes=common_prefixes,
        keys=keys,
    )


def build_s3_listing_url(
    endpoint: str,
    *,
    prefix: str,
    delimiter: str | None = None,
    marker: str | None = None,
) -> str:
    if not endpoint.startswith("https://"):
        raise ValueError("S3 listing endpoint must use HTTPS")
    query: list[tuple[str, str]] = [("prefix", prefix)]
    if delimiter is not None:
        query.append(("delimiter", delimiter))
    if marker is not None:
        query.append(("marker", marker))
    return f"{endpoint}?{urllib.parse.urlencode(query)}"


def symbols_from_common_prefixes(prefixes: list[str], root_prefix: str) -> list[str]:
    symbols: list[str] = []
    for prefix in prefixes:
        if not prefix.startswith(root_prefix):
            raise ValueError("S3 symbol prefix escaped the requested root")
        remainder = prefix.removeprefix(root_prefix).strip("/")
        if not remainder or "/" in remainder:
            raise ValueError("S3 symbol prefix has an unexpected shape")
        symbols.append(remainder.upper())
    return sorted(set(symbols))


def market_archive_index(
    *,
    symbol: str,
    quote_asset: str,
    timeframe: str,
    listing_pages: list[S3ListingSnapshot],
) -> HistoricalMarketArchiveIndex:
    normalized_symbol = symbol.strip().upper()
    normalized_quote = quote_asset.strip().upper()
    if not normalized_symbol.endswith(normalized_quote):
        raise ValueError("Market symbol does not end with the requested quote asset")
    archive_pattern = re.compile(
        rf"/{re.escape(normalized_symbol)}-{re.escape(timeframe)}-(\d{{4}}-\d{{2}})\.zip$"
    )
    checksum_pattern = re.compile(
        rf"/{re.escape(normalized_symbol)}-{re.escape(timeframe)}-(\d{{4}}-\d{{2}})"
        r"\.zip\.CHECKSUM$"
    )
    keys = sorted({key for page in listing_pages for key in page.keys})
    archive_keys = [key for key in keys if archive_pattern.search(key)]
    checksum_keys = [key for key in keys if checksum_pattern.search(key)]
    archive_months = [archive_pattern.search(key).group(1) for key in archive_keys]
    checksum_months = [checksum_pattern.search(key).group(1) for key in checksum_keys]
    listing_hash = market_listing_evidence_hash(
        symbol=normalized_symbol,
        listing_pages=listing_pages,
        archive_keys=archive_keys,
        checksum_sidecar_keys=checksum_keys,
    )
    return HistoricalMarketArchiveIndex(
        symbol=normalized_symbol,
        base_asset=normalized_symbol.removesuffix(normalized_quote),
        quote_asset=normalized_quote,
        listing_pages=listing_pages,
        archive_months=archive_months,
        checksum_sidecar_months=checksum_months,
        archive_keys=archive_keys,
        checksum_sidecar_keys=checksum_keys,
        listing_evidence_hash=listing_hash,
    )


def build_enumeration_artifact(
    *,
    generated_at: datetime,
    endpoint: str,
    root_prefix: str,
    quote_asset: str,
    timeframe: str,
    root_pages: list[S3ListingSnapshot],
    markets: list[HistoricalMarketArchiveIndex],
) -> UniverseEnumerationInputArtifact:
    all_symbols = symbols_from_common_prefixes(
        [prefix for page in root_pages for prefix in page.common_prefixes],
        root_prefix,
    )
    payload = {
        "schema_version": ENUMERATION_ARTIFACT_SCHEMA_VERSION,
        "generated_at": normalize_timestamp(generated_at),
        "endpoint": endpoint,
        "root_prefix": root_prefix,
        "quote_asset": quote_asset,
        "timeframe": timeframe,
        "root_pages": root_pages,
        "all_historical_symbols": all_symbols,
        "markets": sorted(markets, key=lambda market: market.symbol),
    }
    return UniverseEnumerationInputArtifact(
        **payload,
        enumeration_evidence_hash=universe_evidence_hash(payload),
    )


def parse_api_daily_quote_volumes(
    payload: bytes,
    *,
    selection_start: datetime,
    selection_end: datetime,
) -> list[DailyQuoteVolumePoint]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Binance market-data API JSON") from exc
    if isinstance(decoded, dict):
        message = str(decoded.get("msg", "Binance market-data API returned an error"))
        raise ValueError(message[:300])
    if not isinstance(decoded, list):
        raise ValueError("Binance market-data API response must be a list")
    return parse_kline_rows_quote_volumes(
        decoded,
        selection_start=selection_start,
        selection_end=selection_end,
    )


def parse_daily_archive_quote_volumes(
    payload: bytes,
    *,
    archive_name: str,
    selection_start: datetime,
    selection_end: datetime,
) -> list[DailyQuoteVolumePoint]:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(members) != 1:
                raise ValueError("Daily Binance archive must contain exactly one CSV")
            if Path(members[0]).name != archive_name.removesuffix(".zip") + ".csv":
                raise ValueError("Daily Binance archive member name does not match archive")
            with archive.open(members[0]) as source:
                text = io.TextIOWrapper(source, encoding="utf-8", newline="")
                rows = list(csv.reader(text))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid Binance daily archive ZIP") from exc
    return parse_kline_rows_quote_volumes(
        rows,
        selection_start=selection_start,
        selection_end=selection_end,
    )


def parse_kline_rows_quote_volumes(
    rows: list,
    *,
    selection_start: datetime,
    selection_end: datetime,
) -> list[DailyQuoteVolumePoint]:
    start = normalize_timestamp(selection_start)
    end = normalize_timestamp(selection_end)
    if end <= start:
        raise ValueError("Liquidity selection end must be later than its start")
    points: list[DailyQuoteVolumePoint] = []
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)) or len(row) < 8:
            raise ValueError(f"Binance daily kline row {row_number} has fewer than 8 fields")
        if str(row[0]).strip().lower() == "open_time":
            continue
        timestamp, _unit = parse_binance_timestamp(str(row[0]))
        if timestamp < start or timestamp >= end:
            continue
        try:
            quote_volume = Decimal(str(row[7]))
        except InvalidOperation as exc:
            raise ValueError(
                f"Invalid quote asset volume in daily kline row {row_number}"
            ) from exc
        if not quote_volume.is_finite() or quote_volume < 0:
            raise ValueError("Daily quote asset volume must be finite and non-negative")
        points.append(
            DailyQuoteVolumePoint(
                open_time=timestamp,
                quote_asset_volume=quote_volume,
            )
        )
    return sorted(points, key=lambda point: (point.open_time, point.quote_asset_volume))


def build_symbol_liquidity_input(
    *,
    symbol: str,
    source_method: LiquiditySourceMethod,
    source_payloads: list[StoredSourcePayload],
    points: list[DailyQuoteVolumePoint],
    source_error: str | None = None,
) -> SymbolLiquidityInput:
    ordered_payloads = sorted(source_payloads, key=lambda item: item.receipt_id)
    ordered_points = sorted(
        points,
        key=lambda point: (point.open_time, point.quote_asset_volume),
    )
    available = source_method != "UNAVAILABLE"
    return SymbolLiquidityInput(
        symbol=symbol,
        source_method=source_method,
        source_payloads=ordered_payloads,
        points=ordered_points,
        source_evidence_hash=(
            source_payload_bundle_hash(ordered_payloads) if ordered_payloads else None
        ),
        daily_quote_volume_evidence_hash=(
            daily_quote_volume_evidence_hash(ordered_points) if available else None
        ),
        source_error=source_error,
        market_fields_inspected=["open_time", "quote_asset_volume"],
        strategy_outcome_fields_inspected=[],
    )


def build_liquidity_artifact(
    *,
    generated_at: datetime,
    selection_start: datetime,
    selection_end: datetime,
    series: list[SymbolLiquidityInput],
) -> UniverseLiquidityInputArtifact:
    payload = {
        "schema_version": LIQUIDITY_ARTIFACT_SCHEMA_VERSION,
        "generated_at": normalize_timestamp(generated_at),
        "selection_start": normalize_timestamp(selection_start),
        "selection_end": normalize_timestamp(selection_end),
        "series": sorted(series, key=lambda item: item.symbol),
    }
    return UniverseLiquidityInputArtifact(
        **payload,
        liquidity_input_evidence_hash=universe_evidence_hash(payload),
    )


def summarize_daily_liquidity(
    points: list[DailyQuoteVolumePoint],
    *,
    selection_start: datetime,
    selection_end: datetime,
) -> DailyLiquiditySummary:
    start = normalize_timestamp(selection_start)
    end = normalize_timestamp(selection_end)
    if end <= start:
        raise ValueError("Liquidity selection end must be later than its start")
    expected_days = (end.date() - start.date()).days
    by_timestamp: dict[datetime, list[Decimal]] = {}
    for point in points:
        if point.open_time < start or point.open_time >= end:
            raise ValueError("Daily liquidity point falls outside the selection window")
        by_timestamp.setdefault(point.open_time, []).append(point.quote_asset_volume)
    duplicate_count = sum(len(values) - 1 for values in by_timestamp.values())
    unique_volumes = [sorted(values)[0] for _, values in sorted(by_timestamp.items())]
    missing_count = expected_days - len(by_timestamp)
    if missing_count < 0:
        raise ValueError("Daily liquidity input contains more dates than the selection window")
    if not unique_volumes:
        return DailyLiquiditySummary(
            daily_row_count=len(points),
            active_day_count=0,
            duplicate_day_count=duplicate_count,
            missing_day_count=missing_count,
            median_daily_quote_volume=None,
            p10_daily_quote_volume=None,
        )
    ordered = sorted(unique_volumes)
    midpoint = len(ordered) // 2
    median = (
        ordered[midpoint]
        if len(ordered) % 2
        else (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)
    )
    p10_rank = max(1, math.ceil(Decimal("0.10") * len(ordered)))
    return DailyLiquiditySummary(
        daily_row_count=len(points),
        active_day_count=sum(volume > 0 for volume in unique_volumes),
        duplicate_day_count=duplicate_count,
        missing_day_count=missing_count,
        median_daily_quote_volume=median,
        p10_daily_quote_volume=ordered[p10_rank - 1],
    )


def parse_checksum_payload(payload: bytes, archive_name: str) -> str:
    try:
        value = payload.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("Binance checksum is not UTF-8") from exc
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", value)
    if match is None or Path(match.group(2)).name != archive_name:
        raise ValueError(f"Malformed checksum for {archive_name}")
    return match.group(1).lower()


def verify_stored_payload(payload: StoredSourcePayload, evidence_root: Path) -> bool:
    candidate = (evidence_root.resolve() / payload.relative_path).resolve()
    if evidence_root.resolve() not in candidate.parents:
        return False
    if not candidate.is_file() or candidate.stat().st_size != payload.size_bytes:
        return False
    from hashlib import sha256

    return sha256(candidate.read_bytes()).hexdigest() == payload.payload_sha256


def source_payload_bundle_hash(payloads: list[StoredSourcePayload]) -> str:
    return universe_evidence_hash(
        [
            payload.model_dump()
            for payload in sorted(payloads, key=lambda item: item.receipt_id)
        ]
    )


def daily_quote_volume_evidence_hash(points: list[DailyQuoteVolumePoint]) -> str:
    return universe_evidence_hash(
        [
            point.model_dump()
            for point in sorted(
                points,
                key=lambda item: (item.open_time, item.quote_asset_volume),
            )
        ]
    )


def market_listing_evidence_hash(
    *,
    symbol: str,
    listing_pages: list[S3ListingSnapshot],
    archive_keys: list[str],
    checksum_sidecar_keys: list[str],
) -> str:
    return universe_evidence_hash(
        {
            "symbol": symbol.strip().upper(),
            "listing_pages": listing_pages,
            "archive_keys": sorted(set(archive_keys)),
            "checksum_sidecar_keys": sorted(set(checksum_sidecar_keys)),
        }
    )


def artifact_receipts(
    enumeration: UniverseEnumerationInputArtifact,
    liquidity: UniverseLiquidityInputArtifact,
) -> list[UniverseSourceReceipt]:
    payloads = [*enumeration.source_payloads(), *liquidity.source_payloads()]
    receipt_ids = [payload.receipt_id for payload in payloads]
    if len(receipt_ids) != len(set(receipt_ids)):
        raise ValueError("Universe source receipt IDs collide across input artifacts")
    return [payload.receipt() for payload in sorted(payloads, key=lambda item: item.receipt_id)]


def iter_expected_days(start: datetime, end: datetime):
    cursor = normalize_timestamp(start)
    boundary = normalize_timestamp(end)
    while cursor < boundary:
        yield cursor
        cursor += timedelta(days=1)


def child_text(element: ElementTree.Element, name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name:
            return child.text
    return None


def children_named(element: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in element if local_name(child.tag) == name]


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
