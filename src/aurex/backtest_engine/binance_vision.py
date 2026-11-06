import csv
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

BINANCE_KLINE_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
)
PREPARER_VERSION = "1.1.0"
DEFAULT_BINANCE_VISION_KLINE_URI = (
    "https://data.binance.vision/data/spot/monthly/klines"
)
MAX_ARCHIVE_DOWNLOAD_BYTES = 200 * 1024 * 1024
MAX_CHECKSUM_DOWNLOAD_BYTES = 4096


@dataclass(frozen=True)
class PreparedBinanceVisionDataset:
    csv_text: str
    manifest: dict


def monthly_archive_names(
    *,
    symbol: str,
    timeframe: str,
    data_start: datetime,
    data_end: datetime,
) -> list[str]:
    start = ensure_utc(data_start)
    end = ensure_utc(data_end)
    if start >= end:
        raise ValueError("Dataset start must be before dataset end")
    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip()
    if not normalized_symbol or not normalized_timeframe:
        raise ValueError("Symbol and timeframe are required")

    cursor = datetime(start.year, start.month, 1, tzinfo=UTC)
    names: list[str] = []
    while cursor < end:
        names.append(
            f"{normalized_symbol}-{normalized_timeframe}-{cursor.year:04d}-{cursor.month:02d}.zip"
        )
        cursor = next_month(cursor)
    return names


def download_binance_vision_archives(
    *,
    destination: Path,
    symbol: str,
    timeframe: str,
    data_start: datetime,
    data_end: datetime,
    base_uri: str = DEFAULT_BINANCE_VISION_KLINE_URI,
    fetch: Callable[[str, int], bytes] | None = None,
) -> list[Path]:
    normalized_base_uri = base_uri.rstrip("/")
    if not normalized_base_uri.startswith("https://"):
        raise ValueError("Binance Vision base URI must use HTTPS")
    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip()
    target_dir = destination.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    fetch_bytes = fetch or fetch_url_bytes

    archive_paths: list[Path] = []
    for archive_name in monthly_archive_names(
        symbol=normalized_symbol,
        timeframe=normalized_timeframe,
        data_start=data_start,
        data_end=data_end,
    ):
        archive_path = target_dir / archive_name
        checksum_path = Path(f"{archive_path}.CHECKSUM")
        if not local_archive_is_verified(archive_path, checksum_path):
            relative_uri = f"{normalized_symbol}/{normalized_timeframe}/{archive_name}"
            checksum_bytes = fetch_bytes(
                f"{normalized_base_uri}/{relative_uri}.CHECKSUM",
                MAX_CHECKSUM_DOWNLOAD_BYTES,
            )
            archive_bytes = fetch_bytes(
                f"{normalized_base_uri}/{relative_uri}",
                MAX_ARCHIVE_DOWNLOAD_BYTES,
            )
            atomic_write(checksum_path, checksum_bytes)
            atomic_write(archive_path, archive_bytes)
            if not local_archive_is_verified(archive_path, checksum_path):
                raise ValueError(f"Downloaded checksum mismatch for {archive_name}")
        archive_paths.append(archive_path)
    return archive_paths


def prepare_binance_vision_dataset(
    *,
    archive_paths: list[Path],
    symbol: str,
    timeframe: str,
    data_start: datetime,
    data_end: datetime,
    base_uri: str = DEFAULT_BINANCE_VISION_KLINE_URI,
) -> PreparedBinanceVisionDataset:
    if not archive_paths:
        raise ValueError("At least one Binance Vision archive is required")
    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip()
    start = ensure_utc(data_start)
    end = ensure_utc(data_end)
    if start >= end:
        raise ValueError("Dataset start must be before dataset end")

    artifacts: list[dict] = []
    candles: dict[datetime, list[str]] = {}
    timestamp_units: set[str] = set()
    expected_prefix = f"{normalized_symbol}-{normalized_timeframe}-"

    for archive_path in sorted(archive_paths, key=lambda path: path.name):
        archive = archive_path.resolve()
        if not archive.is_file() or not archive.name.startswith(expected_prefix):
            raise ValueError(f"Unexpected Binance archive for requested scope: {archive.name}")
        checksum_path = Path(f"{archive}.CHECKSUM")
        if not checksum_path.is_file():
            raise ValueError(f"Checksum file missing for {archive.name}")

        expected_sha256 = parse_checksum_file(checksum_path, archive.name)
        actual_sha256 = file_sha256(archive)
        if actual_sha256 != expected_sha256:
            raise ValueError(f"Checksum mismatch for {archive.name}")

        member, rows = read_kline_archive(archive)
        archive_timestamp_units: set[str] = set()
        for row_number, row in enumerate(rows, start=1):
            if len(row) != len(BINANCE_KLINE_COLUMNS):
                raise ValueError(
                    f"{archive.name}:{row_number} has {len(row)} fields; expected 12"
                )
            if row[0].strip().lower() == "open_time":
                continue
            timestamp, unit = parse_binance_timestamp(row[0])
            timestamp_units.add(unit)
            archive_timestamp_units.add(unit)
            if timestamp < start or timestamp > end:
                continue
            if timestamp in candles:
                raise ValueError(f"Duplicate Binance candle timestamp {timestamp.isoformat()}")
            candles[timestamp] = [
                timestamp.isoformat().replace("+00:00", "Z"),
                normalize_decimal(row[1], "open"),
                normalize_decimal(row[2], "high"),
                normalize_decimal(row[3], "low"),
                normalize_decimal(row[4], "close"),
                normalize_decimal(row[5], "volume"),
            ]

        relative_uri = f"{normalized_symbol}/{normalized_timeframe}/{archive.name}"
        artifacts.append(
            {
                "uri": f"{base_uri.rstrip('/')}/{relative_uri}",
                "filename": archive.name,
                "sha256": actual_sha256,
                "size_bytes": archive.stat().st_size,
                "checksum_uri": f"{base_uri.rstrip('/')}/{relative_uri}.CHECKSUM",
                "checksum_file_sha256": file_sha256(checksum_path),
                "expected_sha256": expected_sha256,
                "archive_member": member,
                "checksum_verified": True,
                "timestamp_units": sorted(archive_timestamp_units),
            }
        )

    if not candles:
        raise ValueError("No Binance candles fall inside the requested data window")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
    for timestamp in sorted(candles):
        writer.writerow(candles[timestamp])
    csv_text = output.getvalue()
    csv_sha256 = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    normalized_timestamp_units = sorted(timestamp_units)
    timestamp_unit = (
        normalized_timestamp_units[0]
        if len(normalized_timestamp_units) == 1
        else "mixed"
    )
    manifest = {
        "schema_version": "aurex-binance-vision-source-v1",
        "source": "binance-vision",
        "source_reference": (
            f"binance-public-data://spot/monthly/klines/{normalized_symbol}/"
            f"{normalized_timeframe}/{start.date().isoformat()}_{end.date().isoformat()}"
        ),
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "data_start": min(candles).isoformat().replace("+00:00", "Z"),
        "data_end": max(candles).isoformat().replace("+00:00", "Z"),
        "row_count": len(candles),
        "canonical_csv_sha256": csv_sha256,
        "source_artifacts": artifacts,
        "transformation": {
            "tool": "aurex.backtest_engine.binance_vision",
            "version": PREPARER_VERSION,
            "input_format": "binance_spot_kline_csv",
            "timestamp_unit": timestamp_unit,
            "timestamp_units": normalized_timestamp_units,
            "output_schema": "aurex_ohlcv_v1",
        },
    }
    return PreparedBinanceVisionDataset(csv_text=csv_text, manifest=manifest)


def read_kline_archive(archive_path: Path) -> tuple[str, list[list[str]]]:
    with zipfile.ZipFile(archive_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"{archive_path.name} must contain exactly one CSV member")
        member = members[0]
        with archive.open(member) as source:
            text = io.TextIOWrapper(source, encoding="utf-8", newline="")
            return member, list(csv.reader(text))


def parse_checksum_file(checksum_path: Path, archive_name: str) -> str:
    value = checksum_path.read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", value)
    if match is None or Path(match.group(2)).name != archive_name:
        raise ValueError(f"Malformed checksum file for {archive_name}")
    return match.group(1).lower()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_archive_is_verified(archive_path: Path, checksum_path: Path) -> bool:
    if not archive_path.is_file() or not checksum_path.is_file():
        return False
    try:
        expected = parse_checksum_file(checksum_path, archive_path.name)
    except (OSError, ValueError):
        return False
    return file_sha256(archive_path) == expected


def fetch_url_bytes(url: str, maximum_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Aurex/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise ValueError(f"Download exceeds {maximum_bytes} bytes: {url}")
    return payload


def atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_bytes(payload)
    temporary.replace(path)


def next_month(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1, tzinfo=UTC)
    return datetime(value.year, value.month + 1, 1, tzinfo=UTC)


def parse_binance_timestamp(value: str) -> tuple[datetime, str]:
    raw = int(value)
    magnitude = len(str(abs(raw)))
    if magnitude >= 19:
        divisor, unit = 1_000_000_000, "nanoseconds"
    elif magnitude >= 16:
        divisor, unit = 1_000_000, "microseconds"
    elif magnitude >= 13:
        divisor, unit = 1_000, "milliseconds"
    else:
        divisor, unit = 1, "seconds"
    seconds, remainder = divmod(raw, divisor)
    microseconds = remainder * 1_000_000 // divisor
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=microseconds), unit


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_decimal(value: str, field: str) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid Binance {field} value {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"Binance {field} value must be finite")
    if parsed == 0:
        return "0"
    return format(parsed.normalize(), "f")


def write_prepared_dataset(
    prepared: PreparedBinanceVisionDataset,
    *,
    csv_path: Path,
    manifest_path: Path,
) -> None:
    csv_path.write_text(prepared.csv_text, encoding="utf-8", newline="")
    manifest_path.write_text(
        json.dumps(prepared.manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )
