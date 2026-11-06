import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.schemas import (
    OhlcvCandle,
    OhlcvDatasetAuditResponse,
    OhlcvDatasetCsvRequest,
    OhlcvDatasetPreflightResponse,
    OhlcvDatasetResponse,
    OhlcvDocumentedGap,
    OhlcvSourceArtifact,
    OhlcvTransformationEvidence,
)
from aurex.db.base import utc_now
from aurex.db.models import BacktestDataset, BacktestDatasetCandle
from aurex.observability.system_events import SystemEventRecorder

OHLCV_HEADER_ALIASES = {
    "timestamp": ("timestamp", "time", "date_time", "datetime", "date"),
    "open": ("open", "open_price"),
    "high": ("high", "high_price"),
    "low": ("low", "low_price"),
    "close": ("close", "close_price"),
    "volume": ("volume", "vol", "base_volume"),
}
DATASET_SCHEMA_VERSION = "aurex-ohlcv-dataset-v1"


@dataclass(frozen=True)
class OhlcvDatasetPreflight:
    response: OhlcvDatasetPreflightResponse
    candles: list[OhlcvCandle]


@dataclass(frozen=True)
class OhlcvObservedGap:
    previous_timestamp: datetime
    start: datetime
    end: datetime
    next_timestamp: datetime
    missing_interval_count: int

    @property
    def window(self) -> tuple[datetime, datetime]:
        return self.start, self.end


class OhlcvDatasetLab:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preflight(self, payload: OhlcvDatasetCsvRequest) -> OhlcvDatasetPreflight:
        return preflight_ohlcv_dataset(payload)

    def import_csv(
        self,
        payload: OhlcvDatasetCsvRequest,
    ) -> tuple[BacktestDataset, bool]:
        preflight = self.preflight(payload)
        if preflight.response.status != "READY" or preflight.response.evidence_hash is None:
            reasons = ", ".join(preflight.response.rejection_reasons) or "unknown data error"
            raise ValueError(f"OHLCV dataset preflight must be READY before import: {reasons}")

        existing = self.session.execute(
            select(BacktestDataset).where(
                BacktestDataset.evidence_hash == preflight.response.evidence_hash
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, True

        dataset = BacktestDataset(
            symbol=preflight.response.symbol,
            timeframe=preflight.response.timeframe,
            source=preflight.response.source,
            source_reference=preflight.response.source_reference,
            csv_timezone=preflight.response.csv_timezone,
            continuity=preflight.response.continuity,
            data_start=preflight.response.data_start,
            data_end=preflight.response.data_end,
            row_count=len(preflight.candles),
            evidence_hash=preflight.response.evidence_hash,
            quality_snapshot=preflight.response.quality_snapshot,
            imported_at=utc_now(),
        )
        self.session.add(dataset)
        self.session.flush()
        self.session.add_all(
            [
                BacktestDatasetCandle(
                    dataset_id=dataset.id,
                    sequence=index,
                    timestamp=candle.timestamp,
                    open=decimal_string(candle.open),
                    high=decimal_string(candle.high),
                    low=decimal_string(candle.low),
                    close=decimal_string(candle.close),
                    volume=decimal_string(candle.volume),
                )
                for index, candle in enumerate(preflight.candles, start=1)
            ]
        )
        SystemEventRecorder(self.session).info(
            "backtest_dataset",
            "Immutable OHLCV dataset imported",
            {
                "dataset_id": dataset.id,
                "symbol": dataset.symbol,
                "timeframe": dataset.timeframe,
                "row_count": dataset.row_count,
                "evidence_hash": dataset.evidence_hash,
            },
        )
        self.session.flush()
        return dataset, False

    def list_datasets(self, limit: int = 100) -> list[BacktestDataset]:
        return list(
            self.session.execute(
                select(BacktestDataset)
                .order_by(BacktestDataset.imported_at.desc())
                .limit(limit)
            ).scalars()
        )

    def get_dataset(self, dataset_id: str) -> BacktestDataset | None:
        return self.session.get(BacktestDataset, dataset_id)

    def audit(self, dataset: BacktestDataset) -> OhlcvDatasetAuditResponse:
        current_hash = build_persisted_dataset_hash(dataset)
        current_count = len(dataset.candles)
        reasons: list[str] = []
        if current_hash != dataset.evidence_hash:
            reasons.append("dataset_evidence_hash_mismatch")
        if current_count != dataset.row_count:
            reasons.append("dataset_row_count_mismatch")
        if dataset.candles:
            ordered = sorted(dataset.candles, key=lambda item: item.sequence)
            if ensure_utc(ordered[0].timestamp) != ensure_utc(dataset.data_start):
                reasons.append("dataset_data_start_mismatch")
            if ensure_utc(ordered[-1].timestamp) != ensure_utc(dataset.data_end):
                reasons.append("dataset_data_end_mismatch")
        return OhlcvDatasetAuditResponse(
            dataset_id=dataset.id,
            status="PASS" if not reasons else "BLOCKED",
            stored_evidence_hash=dataset.evidence_hash,
            current_evidence_hash=current_hash,
            evidence_hash_matches=current_hash == dataset.evidence_hash,
            stored_row_count=dataset.row_count,
            current_row_count=current_count,
            row_count_matches=current_count == dataset.row_count,
            reasons=reasons,
            checked_at=utc_now(),
        )


def preflight_ohlcv_dataset(payload: OhlcvDatasetCsvRequest) -> OhlcvDatasetPreflight:
    symbol = normalize_symbol(payload.symbol)
    if not symbol:
        raise ValueError("OHLCV dataset symbol is required")
    timeframe, expected_interval_seconds = normalize_timeframe(payload.timeframe)
    timezone = parse_timezone(payload.csv_timezone)
    source = payload.source.strip()
    source_reference = payload.source_reference.strip()
    if not source:
        raise ValueError("OHLCV dataset source is required")
    if not source_reference:
        raise ValueError("OHLCV dataset source reference is required")

    source_artifacts = sorted(
        [source_artifact_snapshot(artifact) for artifact in payload.source_artifacts],
        key=lambda artifact: (artifact["filename"], artifact["uri"]),
    )
    source_artifact_bundle_hash = (
        sha256(
            json.dumps(source_artifacts, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if source_artifacts
        else None
    )
    source_artifacts_verified = bool(source_artifacts) and all(
        bool(artifact["checksum_verified"]) for artifact in source_artifacts
    )

    reader = csv.DictReader(io.StringIO(payload.csv_text.lstrip("\ufeff")))
    header_map = resolve_ohlcv_headers(reader.fieldnames)
    candles: list[OhlcvCandle] = []
    input_timestamps: list[datetime] = []
    row_errors: list[dict] = []
    rows_received = 0

    for row_number, row in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in row.values()):
            continue
        rows_received += 1
        reasons: list[str] = []
        try:
            timestamp = parse_dataset_timestamp(row[header_map["timestamp"]], timezone)
            open_price = parse_finite_decimal(row[header_map["open"]], "open")
            high_price = parse_finite_decimal(row[header_map["high"]], "high")
            low_price = parse_finite_decimal(row[header_map["low"]], "low")
            close_price = parse_finite_decimal(row[header_map["close"]], "close")
            volume = parse_finite_decimal(row[header_map["volume"]], "volume")
            reasons.extend(
                candle_geometry_reasons(
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                )
            )
        except (InvalidOperation, TypeError, ValueError) as exc:
            reasons.append(str(exc))

        if reasons:
            row_errors.append({"row": row_number, "reasons": list(dict.fromkeys(reasons))})
            continue

        candle = OhlcvCandle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )
        candles.append(candle)
        input_timestamps.append(timestamp)

    rejection_reasons: list[str] = []
    warnings: list[str] = []
    if rows_received == 0:
        rejection_reasons.append("ohlcv_dataset_has_no_data_rows")
    if row_errors:
        rejection_reasons.append("ohlcv_dataset_contains_invalid_rows")

    timestamp_counts = Counter(input_timestamps)
    duplicate_count = sum(count - 1 for count in timestamp_counts.values() if count > 1)
    if duplicate_count:
        rejection_reasons.append("ohlcv_dataset_contains_duplicate_timestamps")

    canonical_order = input_order(input_timestamps)
    if canonical_order == "MIXED":
        rejection_reasons.append("ohlcv_dataset_timestamps_are_not_monotonic")
    elif canonical_order == "DESCENDING_REVERSED":
        warnings.append("Input rows were descending and were canonicalized to ascending order.")

    candles.sort(key=lambda candle: candle.timestamp)
    canonical_csv_sha256 = build_canonical_csv_sha256(candles)
    (
        gap_count,
        missing_interval_count,
        interval_mismatch_count,
        observed_gaps,
    ) = interval_quality(
        candles,
        expected_interval_seconds,
    )
    documented_gaps = sorted(
        payload.documented_gaps,
        key=lambda gap: (gap.start, gap.end, gap.source_reference),
    )
    observed_windows = {gap.window for gap in observed_gaps}
    documented_windows = {(gap.start, gap.end) for gap in documented_gaps}
    undocumented_gaps = [gap for gap in observed_gaps if gap.window not in documented_windows]
    unmatched_documented_gaps = [
        gap for gap in documented_gaps if (gap.start, gap.end) not in observed_windows
    ]
    documented_gap_count = len(observed_gaps) - len(undocumented_gaps)
    undocumented_gap_count = len(undocumented_gaps)
    if interval_mismatch_count:
        rejection_reasons.append("ohlcv_dataset_contains_off_interval_timestamps")
    if gap_count and payload.continuity == "continuous_24_7":
        rejection_reasons.append("continuous_ohlcv_dataset_contains_missing_intervals")
    elif payload.continuity == "continuous_24_7_with_documented_outages":
        if undocumented_gaps:
            rejection_reasons.append(
                "continuous_ohlcv_dataset_contains_undocumented_missing_intervals"
            )
        if unmatched_documented_gaps:
            rejection_reasons.append(
                "documented_outage_evidence_does_not_match_observed_gap"
            )
        if observed_gaps and not undocumented_gaps and not unmatched_documented_gaps:
            warnings.append(
                f"All {gap_count} observed 24/7 gap(s) exactly match documented outage "
                "evidence; replay will preserve the discontinuity."
            )
    elif gap_count:
        warnings.append(
            "Session-based dataset contains larger timestamp gaps; exchange-session coverage "
            "must be verified before replay."
        )
    if len(candles) < 200:
        warnings.append(
            "Dataset has fewer than 200 valid candles and is not sufficient for long-indicator "
            "warm-up without additional history."
        )

    rejection_reasons = list(dict.fromkeys(rejection_reasons))
    status = "READY" if not rejection_reasons else "REJECTED"
    data_start = candles[0].timestamp if candles else None
    data_end = candles[-1].timestamp if candles else None
    quality_snapshot = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "status": status,
        "rows_received": rows_received,
        "valid_rows": len(candles),
        "rejected_rows": len(row_errors),
        "canonical_order": canonical_order,
        "expected_interval_seconds": expected_interval_seconds,
        "gap_count": gap_count,
        "missing_interval_count": missing_interval_count,
        "duplicate_count": duplicate_count,
        "interval_mismatch_count": interval_mismatch_count,
        "meets_200_candle_baseline": len(candles) >= 200,
        "canonical_csv_sha256": canonical_csv_sha256,
        "source_artifact_bundle_hash": source_artifact_bundle_hash,
        "source_artifacts_verified": source_artifacts_verified,
        "source_artifacts": source_artifacts,
        "transformation": transformation_snapshot(payload.transformation),
        "rejection_reasons": rejection_reasons,
        "warnings": warnings,
    }
    if observed_gaps:
        quality_snapshot["observed_gaps"] = [
            observed_gap_snapshot(gap) for gap in observed_gaps
        ]
    if documented_gaps:
        quality_snapshot.update(
            {
                "documented_gap_count": documented_gap_count,
                "undocumented_gap_count": undocumented_gap_count,
                "documented_gaps": [
                    documented_gap_snapshot(gap) for gap in documented_gaps
                ],
                "unmatched_documented_gaps": [
                    documented_gap_snapshot(gap) for gap in unmatched_documented_gaps
                ],
            }
        )
    evidence_hash = (
        build_dataset_evidence_hash(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            source_reference=source_reference,
            csv_timezone=timezone.key,
            continuity=payload.continuity,
            candles=candles,
            quality_snapshot=quality_snapshot,
        )
        if status == "READY"
        else None
    )
    response = OhlcvDatasetPreflightResponse(
        status=status,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        source_reference=source_reference,
        csv_timezone=timezone.key,
        continuity=payload.continuity,
        evidence_hash=evidence_hash,
        canonical_csv_sha256=canonical_csv_sha256,
        source_artifact_bundle_hash=source_artifact_bundle_hash,
        source_artifacts_verified=source_artifacts_verified,
        rows_received=rows_received,
        valid_rows=len(candles),
        rejected_rows=len(row_errors),
        data_start=data_start,
        data_end=data_end,
        expected_interval_seconds=expected_interval_seconds,
        canonical_order=canonical_order,
        gap_count=gap_count,
        missing_interval_count=missing_interval_count,
        documented_gap_count=documented_gap_count,
        undocumented_gap_count=undocumented_gap_count,
        duplicate_count=duplicate_count,
        interval_mismatch_count=interval_mismatch_count,
        warnings=warnings,
        rejection_reasons=rejection_reasons,
        row_errors=row_errors[:100],
        quality_snapshot=quality_snapshot,
        checked_at=utc_now(),
        mutates_ledger=False,
    )
    return OhlcvDatasetPreflight(response=response, candles=candles)


def source_artifact_snapshot(artifact: OhlcvSourceArtifact) -> dict:
    snapshot = artifact.model_dump(mode="json")
    if artifact.timestamp_units is None:
        snapshot.pop("timestamp_units", None)
    return snapshot


def transformation_snapshot(
    transformation: OhlcvTransformationEvidence | None,
) -> dict | None:
    if transformation is None:
        return None
    snapshot = transformation.model_dump(mode="json")
    if transformation.timestamp_units is None:
        snapshot.pop("timestamp_units", None)
    return snapshot


def observed_gap_snapshot(gap: OhlcvObservedGap) -> dict:
    return {
        "previous_timestamp": utc_iso(gap.previous_timestamp),
        "start": utc_iso(gap.start),
        "end": utc_iso(gap.end),
        "next_timestamp": utc_iso(gap.next_timestamp),
        "missing_interval_count": gap.missing_interval_count,
    }


def documented_gap_snapshot(gap: OhlcvDocumentedGap) -> dict:
    snapshot = gap.model_dump(mode="json")
    if gap.source_title is None:
        snapshot.pop("source_title", None)
    return snapshot


def dataset_response(
    dataset: BacktestDataset,
    *,
    reused_existing: bool = False,
) -> OhlcvDatasetResponse:
    return OhlcvDatasetResponse(
        id=dataset.id,
        symbol=dataset.symbol,
        timeframe=dataset.timeframe,
        source=dataset.source,
        source_reference=dataset.source_reference,
        csv_timezone=dataset.csv_timezone,
        continuity=dataset.continuity,
        data_start=ensure_utc(dataset.data_start),
        data_end=ensure_utc(dataset.data_end),
        row_count=dataset.row_count,
        evidence_hash=dataset.evidence_hash,
        canonical_csv_sha256=dataset.quality_snapshot.get("canonical_csv_sha256"),
        source_artifact_bundle_hash=dataset.quality_snapshot.get(
            "source_artifact_bundle_hash"
        ),
        source_artifacts_verified=bool(
            dataset.quality_snapshot.get("source_artifacts_verified")
        ),
        quality_snapshot=dataset.quality_snapshot,
        imported_at=ensure_utc(dataset.imported_at),
        immutable=True,
        reused_existing=reused_existing,
    )


def build_dataset_evidence_hash(
    *,
    symbol: str,
    timeframe: str,
    source: str,
    source_reference: str,
    csv_timezone: str,
    continuity: str,
    candles: list[OhlcvCandle],
    quality_snapshot: dict,
) -> str:
    rows = [
        {
            "timestamp": ensure_utc(candle.timestamp).isoformat(),
            "open": decimal_string(candle.open),
            "high": decimal_string(candle.high),
            "low": decimal_string(candle.low),
            "close": decimal_string(candle.close),
            "volume": decimal_string(candle.volume),
        }
        for candle in candles
    ]
    return hash_dataset_rows(
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        source_reference=source_reference,
        csv_timezone=csv_timezone,
        continuity=continuity,
        rows=rows,
        quality_snapshot=quality_snapshot,
    )


def build_canonical_csv_sha256(candles: list[OhlcvCandle]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
    for candle in candles:
        writer.writerow(
            [
                ensure_utc(candle.timestamp).isoformat().replace("+00:00", "Z"),
                decimal_string(candle.open),
                decimal_string(candle.high),
                decimal_string(candle.low),
                decimal_string(candle.close),
                decimal_string(candle.volume),
            ]
        )
    return sha256(output.getvalue().encode("utf-8")).hexdigest()


def build_persisted_dataset_hash(dataset: BacktestDataset) -> str:
    rows = [
        {
            "timestamp": ensure_utc(candle.timestamp).isoformat(),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in sorted(dataset.candles, key=lambda item: item.sequence)
    ]
    return hash_dataset_rows(
        symbol=dataset.symbol,
        timeframe=dataset.timeframe,
        source=dataset.source,
        source_reference=dataset.source_reference,
        csv_timezone=dataset.csv_timezone,
        continuity=dataset.continuity,
        rows=rows,
        quality_snapshot=dataset.quality_snapshot,
    )


def hash_dataset_rows(
    *,
    symbol: str,
    timeframe: str,
    source: str,
    source_reference: str,
    csv_timezone: str,
    continuity: str,
    rows: list[dict[str, str]],
    quality_snapshot: dict,
) -> str:
    snapshot = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "source": source,
        "source_reference": source_reference,
        "csv_timezone": csv_timezone,
        "continuity": continuity,
        "quality_snapshot": canonical_quality_snapshot(quality_snapshot),
        "candles": rows,
    }
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def canonical_quality_snapshot(quality_snapshot: dict) -> dict:
    normalized = dict(quality_snapshot)
    normalized["canonical_order"] = "ASCENDING"
    normalized["warnings"] = [
        warning
        for warning in normalized.get("warnings", [])
        if not str(warning).startswith("Input rows were descending")
    ]
    return normalized


def resolve_ohlcv_headers(fieldnames: list[str] | None) -> dict[str, str]:
    if fieldnames is None:
        raise ValueError("OHLCV CSV must include a header row")
    normalized = {normalize_header(field): field for field in fieldnames}
    resolved: dict[str, str] = {}
    for field, aliases in OHLCV_HEADER_ALIASES.items():
        match = next((normalized[alias] for alias in aliases if alias in normalized), None)
        if match is None:
            raise ValueError(
                "OHLCV CSV must include timestamp, open, high, low, close, volume"
            )
        resolved[field] = match
    return resolved


def normalize_header(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.strip().lower())).strip("_")


def normalize_symbol(value: str) -> str:
    return value.strip().upper().replace(" ", "")


def normalize_timeframe(value: str) -> tuple[str, int]:
    raw = value.strip()
    if not raw:
        raise ValueError("OHLCV timeframe is required")
    if raw.isdigit():
        count = int(raw)
        if count <= 0:
            raise ValueError("OHLCV timeframe must be positive")
        return f"{count}m", count * 60
    match = re.fullmatch(r"(\d+)?(min|m|h|d|w)", raw.lower())
    if match is None:
        raise ValueError("Unsupported OHLCV timeframe; use minutes, hours, days, or weeks")
    count = int(match.group(1) or "1")
    if count <= 0:
        raise ValueError("OHLCV timeframe must be positive")
    unit = match.group(2)
    if unit == "min":
        unit = "m"
    seconds_per_unit = {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
    return f"{count}{unit}", count * seconds_per_unit


def parse_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value.strip())
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown OHLCV CSV timezone: {value}") from exc


def parse_dataset_timestamp(value: str | None, timezone: ZoneInfo) -> datetime:
    candidate = str(value or "").strip()
    if not candidate:
        raise ValueError("timestamp_is_required")
    if re.fullmatch(r"\d{10,13}", candidate):
        raw = int(candidate)
        seconds = Decimal(raw) / Decimal("1000") if len(candidate) == 13 else Decimal(raw)
        return datetime.fromtimestamp(float(seconds), tz=UTC)
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp_is_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(UTC)


def parse_finite_decimal(value: str | None, field: str) -> Decimal:
    candidate = str(value or "").strip().replace(",", "")
    if not candidate:
        raise ValueError(f"{field}_is_required")
    parsed = Decimal(candidate)
    if not parsed.is_finite():
        raise ValueError(f"{field}_must_be_finite")
    return parsed


def candle_geometry_reasons(
    open_price: Decimal,
    high_price: Decimal,
    low_price: Decimal,
    close_price: Decimal,
    volume: Decimal,
) -> list[str]:
    reasons: list[str] = []
    if min(open_price, high_price, low_price, close_price) <= 0:
        reasons.append("ohlc_prices_must_be_positive")
    if volume < 0:
        reasons.append("volume_cannot_be_negative")
    if high_price < max(open_price, low_price, close_price):
        reasons.append("high_is_below_ohlc_value")
    if low_price > min(open_price, high_price, close_price):
        reasons.append("low_is_above_ohlc_value")
    return reasons


def input_order(timestamps: list[datetime]) -> str:
    if len(timestamps) < 2:
        return "ASCENDING"
    if all(left < right for left, right in zip(timestamps, timestamps[1:], strict=False)):
        return "ASCENDING"
    if all(left > right for left, right in zip(timestamps, timestamps[1:], strict=False)):
        return "DESCENDING_REVERSED"
    return "MIXED"


def interval_quality(
    candles: list[OhlcvCandle],
    expected_interval_seconds: int,
) -> tuple[int, int, int, list[OhlcvObservedGap]]:
    gap_count = 0
    missing_interval_count = 0
    interval_mismatch_count = 0
    observed_gaps: list[OhlcvObservedGap] = []
    expected = timedelta(seconds=expected_interval_seconds)
    for previous, current in zip(candles, candles[1:], strict=False):
        delta = current.timestamp - previous.timestamp
        if delta < expected or delta % expected != timedelta(0):
            interval_mismatch_count += 1
            continue
        if delta > expected:
            gap_count += 1
            gap_missing_intervals = (delta // expected) - 1
            missing_interval_count += gap_missing_intervals
            observed_gaps.append(
                OhlcvObservedGap(
                    previous_timestamp=previous.timestamp,
                    start=previous.timestamp + expected,
                    end=current.timestamp,
                    next_timestamp=current.timestamp,
                    missing_interval_count=gap_missing_intervals,
                )
            )
    return gap_count, missing_interval_count, interval_mismatch_count, observed_gaps


def decimal_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_iso(value: datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")
