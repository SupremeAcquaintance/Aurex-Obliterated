"""Bounded public candle acquisition. No credentials, database, signals or orders."""

import http.client
import json
import os
import re
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aurex.signal_gateway.native_bars import (
    BASE_SECONDS,
    MAX_WINDOW_BARS,
    ClosedBar,
    NativeBarError,
    aware_utc,
    history_hash,
)

PUBLIC_ORIGIN = "https://data-api.binance.vision"
TIME_URL = f"{PUBLIC_ORIGIN}/api/v3/time"
PAGE_LIMIT = 1000
MAX_RESPONSE_BYTES = 512 * 1024
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
REQUEST_SECONDS = 10
MAX_BATCH_SECONDS = 90
CLOCK_TOLERANCE_SECONDS = 2
CLOSE_DELAY_SECONDS = 2
STEP = timedelta(seconds=BASE_SECONDS)
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
DECIMAL_TEXT = re.compile(r"^(?:0|[1-9][0-9]{0,23})(?:\.[0-9]{1,8})?$")


class PublicDataError(NativeBarError):
    def __init__(
        self,
        code: str,
        *,
        status: int | None = None,
        retry_after: int | None = None,
        clock: "PublicExchange | None" = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.retry_after = retry_after
        self.clock = clock


@dataclass(frozen=True)
class PublicResponse:
    status: int
    body: bytes
    content_type: str = "application/json"
    content_encoding: str = "identity"
    retry_after: str | None = None


class EvidenceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PublicExchange(EvidenceModel):
    url: str = Field(max_length=512)
    requested_at: datetime
    received_at: datetime
    elapsed_seconds: float = Field(ge=0, le=REQUEST_SECONDS, allow_inf_nan=False)
    body: str = Field(max_length=MAX_RESPONSE_BYTES)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("requested_at", "received_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return aware_utc(value)


class PublicCandleEvidence(EvidenceModel):
    schema_version: Literal["native_public_candles_v1"] = "native_public_candles_v1"
    feed_id: Literal["binance_spot_public"] = "binance_spot_public"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    timeframe: Literal["15m"] = "15m"
    transport: Literal["public_https", "injected"]
    first_open: datetime
    bar_count: int = Field(ge=1, le=MAX_WINDOW_BARS, strict=True)
    candles_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    clock: PublicExchange
    pages: tuple[PublicExchange, ...] = Field(min_length=1, max_length=5)
    execution_authority: Literal[False] = False
    forward_qualifying: Literal[False] = False

    @field_validator("first_open")
    @classmethod
    def aligned_timestamp(cls, value: datetime) -> datetime:
        return aligned_open(value)


def milliseconds(value: datetime) -> int:
    return (aware_utc(value) - EPOCH) // timedelta(milliseconds=1)


def aligned_open(value: datetime) -> datetime:
    value = aware_utc(value)
    if value < EPOCH or value.microsecond or milliseconds(value) % (BASE_SECONDS * 1000):
        raise PublicDataError("public_open_not_aligned")
    return value


def window_end(first: datetime, count: int) -> datetime:
    try:
        return first + STEP * count
    except OverflowError as exc:
        raise PublicDataError("public_window_time_out_of_range") from exc


def kline_url(first_open: datetime, count: int) -> str:
    if type(count) is not int or not 1 <= count <= PAGE_LIMIT:
        raise PublicDataError("public_page_count_invalid")
    first = aligned_open(first_open)
    start = milliseconds(first)
    return f"{PUBLIC_ORIGIN}/api/v3/klines?" + urlencode(
        {
            "symbol": "BTCUSDT",
            "interval": "15m",
            "timeZone": "0",
            "startTime": start,
            "endTime": milliseconds(window_end(first, count)) - 1,
            "limit": count,
        }
    )


def validate_url(url: str) -> None:
    if url == TIME_URL:
        return
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, strict_parsing=True)
        start = int(query["startTime"][0])
        count = int(query["limit"][0])
        if url != kline_url(EPOCH + timedelta(milliseconds=start), count):
            raise ValueError
    except (KeyError, ValueError, OverflowError) as exc:
        raise PublicDataError("public_url_not_allowed") from exc


def fetch_public(url: str) -> PublicResponse:
    """Fixed TLS origin; no redirect, proxy, credential, retry or alternate-host path."""
    validate_url(url)
    parsed = urlsplit(url)
    connection = http.client.HTTPSConnection(
        "data-api.binance.vision", timeout=REQUEST_SECONDS, context=ssl.create_default_context()
    )
    started = time.monotonic()
    try:
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        connection.request(
            "GET",
            target,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "Aurex-Public-Data/1",
            },
        )
        response = connection.getresponse()
        chunks: list[bytes] = []
        size = 0
        while True:
            if time.monotonic() - started > REQUEST_SECONDS:
                raise PublicDataError("public_request_deadline_exceeded")
            chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise PublicDataError("public_response_too_large")
            chunks.append(chunk)
        return PublicResponse(
            response.status,
            b"".join(chunks),
            response.getheader("Content-Type", ""),
            response.getheader("Content-Encoding", "identity"),
            response.getheader("Retry-After"),
        )
    except (OSError, http.client.HTTPException) as exc:
        raise PublicDataError("public_transport_failed") from exc
    finally:
        connection.close()


def _unique_object(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise PublicDataError("public_duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise PublicDataError("public_nonfinite_json")


def strict_json(raw: str) -> object:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise PublicDataError("public_invalid_json") from exc


def _exchange_payload(exchange: PublicExchange, expected_url: str) -> object:
    if exchange.url != expected_url:
        raise PublicDataError("public_request_scope_changed")
    elapsed = (exchange.received_at - exchange.requested_at).total_seconds()
    if not 0 <= elapsed <= REQUEST_SECONDS or abs(elapsed - exchange.elapsed_seconds) > 1:
        raise PublicDataError("public_request_clock_changed")
    try:
        raw = exchange.body.encode("utf-8")
    except UnicodeError as exc:
        raise PublicDataError("public_response_encoding_invalid") from exc
    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise PublicDataError("public_response_size_invalid")
    if sha256(raw).hexdigest() != exchange.body_sha256:
        raise PublicDataError("public_response_hash_mismatch")
    return strict_json(exchange.body)


def _closed_cutoff(clock: PublicExchange) -> datetime:
    payload = _exchange_payload(clock, TIME_URL)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"serverTime"}
        or type(payload["serverTime"]) is not int
        or not 0 <= payload["serverTime"] <= 253402300799000
    ):
        raise PublicDataError("public_server_time_invalid")
    server = EPOCH + timedelta(milliseconds=payload["serverTime"])
    tolerance = timedelta(seconds=CLOCK_TOLERANCE_SECONDS)
    if not clock.requested_at - tolerance <= server <= clock.received_at + tolerance:
        raise PublicDataError("public_server_clock_skew", clock=clock)
    return min(server, clock.requested_at) - timedelta(seconds=CLOSE_DELAY_SECONDS)


def _decimal(value: object) -> Decimal:
    if not isinstance(value, str) or DECIMAL_TEXT.fullmatch(value) is None:
        raise PublicDataError("public_kline_decimal_invalid")
    return Decimal(value)


def _parse_page(payload: object, first_open: datetime, count: int) -> list[ClosedBar]:
    if not isinstance(payload, list) or len(payload) != count:
        raise PublicDataError("public_kline_count_mismatch")
    bars = []
    for index, row in enumerate(payload):
        expected = first_open + STEP * index
        if not isinstance(row, list) or len(row) != 12:
            raise PublicDataError("public_kline_shape_invalid")
        if (
            type(row[0]) is not int
            or row[0] != milliseconds(expected)
            or type(row[6]) is not int
            or row[6] != milliseconds(expected + STEP) - 1
        ):
            raise PublicDataError("public_kline_time_or_continuity_invalid")
        if type(row[8]) is not int or not 0 <= row[8] <= 2**63 - 1 or row[11] != "0":
            raise PublicDataError("public_kline_metadata_invalid")
        numbers = {index: _decimal(row[index]) for index in (1, 2, 3, 4, 5, 7, 9, 10)}
        if numbers[9] > numbers[5] or numbers[10] > numbers[7]:
            raise PublicDataError("public_kline_volume_inconsistent")
        bars.append(
            ClosedBar(
                timestamp=expected,
                open=numbers[1],
                high=numbers[2],
                low=numbers[3],
                close=numbers[4],
                volume=numbers[5],
            )
        )
    return bars


def verify_public_evidence(evidence: PublicCandleEvidence) -> tuple[ClosedBar, ...]:
    """Reconstruct retained bytes, not TLS authenticity or permission to trade.

    Transport labels and local hashes are not signatures. A database/filesystem
    administrator can replace a whole artifact; offline replay cannot detect that.
    """
    evidence = PublicCandleEvidence.model_validate(evidence.model_dump(mode="json"))
    cutoff = _closed_cutoff(evidence.clock)
    if window_end(evidence.first_open, evidence.bar_count) > cutoff:
        raise PublicDataError("public_requested_candle_not_closed")
    bars: list[ClosedBar] = []
    previous_received = evidence.clock.received_at
    for page in evidence.pages:
        count = min(PAGE_LIMIT, evidence.bar_count - len(bars))
        if count <= 0:
            raise PublicDataError("public_page_sequence_invalid")
        _check_page_clock(page, evidence.clock, previous_received)
        first = evidence.first_open + STEP * len(bars)
        payload = _exchange_payload(page, kline_url(first, count))
        bars.extend(_parse_page(payload, first, count))
        previous_received = page.received_at
    if len(bars) != evidence.bar_count or history_hash(bars) != evidence.candles_sha256:
        raise PublicDataError("public_normalized_history_mismatch")
    return tuple(bars)


def _check_page_clock(
    page: PublicExchange, clock: PublicExchange, previous_received: datetime
) -> None:
    if page.requested_at < previous_received:
        raise PublicDataError("public_page_sequence_invalid")
    if page.received_at - clock.requested_at > timedelta(seconds=MAX_BATCH_SECONDS):
        raise PublicDataError("public_batch_deadline_exceeded")


class PublicCandleClient:
    def __init__(
        self,
        *,
        transport: Callable[[str], PublicResponse] | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._transport = transport or fetch_public
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._kind = (
            "public_https"
            if transport is None and now is None and monotonic is None
            else "injected"
        )

    def _get(self, url: str) -> PublicExchange:
        validate_url(url)
        requested_at = aware_utc(self._now())
        start = self._monotonic()
        response = self._transport(url)
        elapsed = self._monotonic() - start
        received_at = aware_utc(self._now())
        if not 0 <= elapsed <= REQUEST_SECONDS:
            raise PublicDataError("public_request_deadline_exceeded")
        if response.status != 200:
            retry = response.retry_after
            seconds = int(retry) if retry and re.fullmatch(r"[0-9]{1,9}", retry) else None
            raise PublicDataError(
                "public_http_rejected", status=response.status, retry_after=seconds
            )
        if response.content_type.split(";", 1)[0].strip().lower() != "application/json":
            raise PublicDataError("public_content_type_invalid")
        if response.content_encoding.lower() != "identity":
            raise PublicDataError("public_content_encoding_invalid")
        if not isinstance(response.body, bytes) or not 0 < len(response.body) <= MAX_RESPONSE_BYTES:
            raise PublicDataError("public_response_size_invalid")
        try:
            body = response.body.decode("utf-8")
        except UnicodeError as exc:
            raise PublicDataError("public_response_encoding_invalid") from exc
        exchange = PublicExchange(
            url=url,
            requested_at=requested_at,
            received_at=received_at,
            elapsed_seconds=elapsed,
            body=body,
            body_sha256=sha256(response.body).hexdigest(),
        )
        _exchange_payload(exchange, url)
        return exchange

    def acquire(
        self, *, count: int = 1000, first_open: datetime | None = None
    ) -> PublicCandleEvidence:
        if type(count) is not int or not 1 <= count <= MAX_WINDOW_BARS:
            raise PublicDataError("public_window_size_invalid")
        first = aligned_open(first_open) if first_open is not None else None
        if first is not None:
            window_end(first, count)
        started = self._monotonic()
        clock = self._get(TIME_URL)
        cutoff = _closed_cutoff(clock)
        if first is None:
            boundary = EPOCH + STEP * ((cutoff - EPOCH) // STEP)
            first = aligned_open(boundary - STEP * count)
        if window_end(first, count) > cutoff:
            raise PublicDataError("public_requested_candle_not_closed")
        pages: list[PublicExchange] = []
        bars: list[ClosedBar] = []
        previous_received = clock.received_at
        while len(bars) < count:
            if self._monotonic() - started > MAX_BATCH_SECONDS:
                raise PublicDataError("public_batch_deadline_exceeded")
            page_count = min(PAGE_LIMIT, count - len(bars))
            page_first = first + STEP * len(bars)
            page = self._get(kline_url(page_first, page_count))
            _check_page_clock(page, clock, previous_received)
            bars.extend(_parse_page(strict_json(page.body), page_first, page_count))
            pages.append(page)
            previous_received = page.received_at
        if not 0 <= self._monotonic() - started <= MAX_BATCH_SECONDS:
            raise PublicDataError("public_batch_deadline_exceeded")
        evidence = PublicCandleEvidence(
            transport=self._kind,
            first_open=first,
            bar_count=count,
            candles_sha256=history_hash(bars),
            clock=clock,
            pages=tuple(pages),
        )
        verify_public_evidence(evidence)
        return evidence


def write_public_evidence(evidence: PublicCandleEvidence, path: Path) -> str:
    verify_public_evidence(evidence)
    raw = evidence.model_dump_json(indent=2).encode("utf-8") + b"\n"
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise PublicDataError("public_artifact_too_large")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves prior observations. A crash-truncated file must
    # fail readback verification; it is never a committed processing checkpoint.
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha256(raw).hexdigest()


def read_public_evidence(path: Path) -> PublicCandleEvidence:
    with path.open("rb") as handle:
        raw = handle.read(MAX_ARTIFACT_BYTES + 1)
    if not raw or len(raw) > MAX_ARTIFACT_BYTES:
        raise PublicDataError("public_artifact_size_invalid")
    try:
        evidence = PublicCandleEvidence.model_validate(strict_json(raw.decode("utf-8")))
    except UnicodeError as exc:
        raise PublicDataError("public_artifact_encoding_invalid") from exc
    verify_public_evidence(evidence)
    return evidence
