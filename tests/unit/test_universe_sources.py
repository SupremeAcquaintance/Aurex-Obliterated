import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.universe_sources import (
    DailyQuoteVolumePoint,
    S3ListingSnapshot,
    StoredSourcePayload,
    UniverseEnumerationInputArtifact,
    UniverseLiquidityInputArtifact,
    build_enumeration_artifact,
    build_liquidity_artifact,
    build_s3_listing_url,
    build_symbol_liquidity_input,
    market_archive_index,
    parse_api_daily_quote_volumes,
    parse_daily_archive_quote_volumes,
    parse_s3_listing_xml,
    summarize_daily_liquidity,
    verify_stored_payload,
)


def stored_payload(
    receipt_id: str,
    *,
    payload_bytes: bytes = b"fixture",
    relative_path: str | None = None,
) -> StoredSourcePayload:
    return StoredSourcePayload(
        receipt_id=receipt_id,
        purpose="Official source fixture",
        uri=f"https://example.test/{receipt_id}",
        retrieved_at="2026-07-22T13:00:00Z",
        payload_sha256=hashlib.sha256(payload_bytes).hexdigest(),
        size_bytes=len(payload_bytes),
        relative_path=relative_path or f"sources/{receipt_id}.bin",
    )


def listing_snapshot(
    receipt_id: str,
    *,
    prefix: str,
    common_prefixes: list[str] | None = None,
    keys: list[str] | None = None,
) -> S3ListingSnapshot:
    return S3ListingSnapshot(
        prefix=prefix,
        delimiter="/" if common_prefixes is not None else None,
        marker=None,
        next_marker=None,
        is_truncated=False,
        common_prefixes=common_prefixes or [],
        keys=keys or [],
        payload=stored_payload(receipt_id),
    )


def test_s3_listing_parser_preserves_pagination_and_derives_marker() -> None:
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
      <Prefix>data/spot/monthly/klines/</Prefix>
      <Marker></Marker><Delimiter>/</Delimiter><IsTruncated>true</IsTruncated>
      <CommonPrefixes><Prefix>data/spot/monthly/klines/ADAUSDT/</Prefix></CommonPrefixes>
      <CommonPrefixes><Prefix>data/spot/monthly/klines/BTCUSDT/</Prefix></CommonPrefixes>
    </ListBucketResult>"""

    parsed = parse_s3_listing_xml(payload)

    assert parsed.is_truncated is True
    assert parsed.next_marker == "data/spot/monthly/klines/BTCUSDT/"
    assert parsed.common_prefixes == [
        "data/spot/monthly/klines/ADAUSDT/",
        "data/spot/monthly/klines/BTCUSDT/",
    ]
    assert build_s3_listing_url(
        "https://example.test/bucket",
        prefix=parsed.prefix,
        delimiter=parsed.delimiter,
        marker=parsed.next_marker,
    ) == (
        "https://example.test/bucket?prefix=data%2Fspot%2Fmonthly%2Fklines%2F"
        "&delimiter=%2F&marker=data%2Fspot%2Fmonthly%2Fklines%2FBTCUSDT%2F"
    )


def test_market_archive_index_distinguishes_archives_and_checksum_sidecars() -> None:
    prefix = "data/spot/monthly/klines/BTCUSDT/4h/"
    page = listing_snapshot(
        "btc-listing",
        prefix=prefix,
        keys=[
            f"{prefix}BTCUSDT-4h-2023-01.zip.CHECKSUM",
            f"{prefix}BTCUSDT-4h-2023-02.zip",
            f"{prefix}BTCUSDT-4h-2023-01.zip",
            f"{prefix}BTCUSDT-1d-2023-01.zip",
        ],
    )

    market = market_archive_index(
        symbol="btcusdt",
        quote_asset="usdt",
        timeframe="4h",
        listing_pages=[page],
    )

    assert market.archive_months == ["2023-01", "2023-02"]
    assert market.checksum_sidecar_months == ["2023-01"]
    assert len(market.archive_keys) == 2
    assert len(market.checksum_sidecar_keys) == 1


def test_enumeration_artifact_preserves_every_historical_quote_market() -> None:
    root_prefix = "data/spot/monthly/klines/"
    root_page = listing_snapshot(
        "root",
        prefix=root_prefix,
        common_prefixes=[
            f"{root_prefix}ETHBTC/",
            f"{root_prefix}BTCUSDT/",
            f"{root_prefix}ADAUSDT/",
        ],
    )
    markets = []
    for symbol in ("BTCUSDT", "ADAUSDT"):
        prefix = f"{root_prefix}{symbol}/4h/"
        markets.append(
            market_archive_index(
                symbol=symbol,
                quote_asset="USDT",
                timeframe="4h",
                listing_pages=[listing_snapshot(f"{symbol}-listing", prefix=prefix)],
            )
        )

    artifact = build_enumeration_artifact(
        generated_at=datetime(2026, 7, 22, 13, tzinfo=UTC),
        endpoint="https://example.test/bucket",
        root_prefix=root_prefix,
        quote_asset="USDT",
        timeframe="4h",
        root_pages=[root_page],
        markets=markets,
    )

    assert artifact.all_historical_symbols == ["ADAUSDT", "BTCUSDT", "ETHBTC"]
    assert [market.symbol for market in artifact.markets] == ["ADAUSDT", "BTCUSDT"]
    assert len(artifact.source_payloads()) == 3

    tampered = artifact.model_dump()
    tampered["markets"].pop()
    with pytest.raises(ValidationError, match="preserve every enumerated symbol"):
        UniverseEnumerationInputArtifact.model_validate(tampered)


def test_api_parser_uses_only_open_time_and_quote_volume() -> None:
    start = datetime(2023, 1, 1, tzinfo=UTC)
    rows = [
        [
            int(start.timestamp() * 1000),
            "not-a-price",
            None,
            {"ignored": True},
            "still-not-a-price",
            [],
            "ignored-close-time",
            "12345678.901",
        ],
        [
            int((start + timedelta(days=1)).timestamp() * 1000),
            "ignored",
            "ignored",
            "ignored",
            "ignored",
            "ignored",
            "ignored",
            "2.5",
        ],
    ]

    points = parse_api_daily_quote_volumes(
        json.dumps(rows).encode(),
        selection_start=start,
        selection_end=start + timedelta(days=1),
    )

    assert points == [
        DailyQuoteVolumePoint(
            open_time=start,
            quote_asset_volume=Decimal("12345678.901"),
        )
    ]


def test_api_parser_preserves_official_error_without_treating_it_as_data() -> None:
    with pytest.raises(ValueError, match="Invalid symbol"):
        parse_api_daily_quote_volumes(
            b'{"code":-1121,"msg":"Invalid symbol."}',
            selection_start=datetime(2023, 1, 1, tzinfo=UTC),
            selection_end=datetime(2023, 1, 2, tzinfo=UTC),
        )


def test_daily_archive_parser_reads_quote_volume_without_ohlc() -> None:
    start = datetime(2023, 1, 1, tzinfo=UTC)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w") as archive:
        archive.writestr(
            "BTCUSDT-1d-2023-01.csv",
            f"{int(start.timestamp() * 1000)},bad,bad,bad,bad,bad,bad,42.125\n",
        )

    points = parse_daily_archive_quote_volumes(
        archive_bytes.getvalue(),
        archive_name="BTCUSDT-1d-2023-01.zip",
        selection_start=start,
        selection_end=start + timedelta(days=1),
    )

    assert points[0].quote_asset_volume == Decimal("42.125")


def test_daily_liquidity_summary_uses_exact_median_and_nearest_rank_p10() -> None:
    start = datetime(2023, 1, 1, tzinfo=UTC)
    points = [
        DailyQuoteVolumePoint(
            open_time=start + timedelta(days=index),
            quote_asset_volume=Decimal(index + 1),
        )
        for index in range(10)
    ]
    points.append(
        DailyQuoteVolumePoint(
            open_time=start,
            quote_asset_volume=Decimal("999"),
        )
    )

    summary = summarize_daily_liquidity(
        points,
        selection_start=start,
        selection_end=start + timedelta(days=10),
    )

    assert summary.daily_row_count == 11
    assert summary.active_day_count == 10
    assert summary.duplicate_day_count == 1
    assert summary.missing_day_count == 0
    assert summary.median_daily_quote_volume == Decimal("5.5")
    assert summary.p10_daily_quote_volume == Decimal("1")


def test_liquidity_artifact_is_hash_bound_and_refuses_outcomes() -> None:
    start = datetime(2023, 1, 1, tzinfo=UTC)
    raw = b"[[1672531200000,0,0,0,0,0,0,10000000]]"
    payload = stored_payload("api-eth", payload_bytes=raw)
    series = build_symbol_liquidity_input(
        symbol="ETHUSDT",
        source_method="BINANCE_MARKET_DATA_API",
        source_payloads=[payload],
        points=[
            DailyQuoteVolumePoint(
                open_time=start,
                quote_asset_volume="10000000",
            )
        ],
    )
    artifact = build_liquidity_artifact(
        generated_at=datetime(2026, 7, 22, 13, tzinfo=UTC),
        selection_start=start,
        selection_end=start + timedelta(days=1),
        series=[series],
    )

    assert artifact.series[0].market_fields_inspected == [
        "open_time",
        "quote_asset_volume",
    ]
    tampered = artifact.model_dump()
    tampered["series"][0]["points"][0]["quote_asset_volume"] = Decimal("1")
    with pytest.raises(ValidationError, match="evidence hash does not match points"):
        UniverseLiquidityInputArtifact.model_validate(tampered)

    outcome_payload = series.model_dump()
    outcome_payload["strategy_outcome_fields_inspected"] = ["net_pl"]
    with pytest.raises(ValidationError, match="cannot inspect strategy outcomes"):
        type(series).model_validate(outcome_payload)


def test_unavailable_liquidity_input_contains_no_synthetic_metrics() -> None:
    series = build_symbol_liquidity_input(
        symbol="NEWUSDT",
        source_method="UNAVAILABLE",
        source_payloads=[],
        points=[],
        source_error="Required 4h archives are incomplete.",
    )

    assert series.source_evidence_hash is None
    assert series.daily_quote_volume_evidence_hash is None
    assert series.source_error is not None


def test_stored_payload_verification_detects_tampering(tmp_path) -> None:
    raw = b"official evidence"
    target = tmp_path / "sources" / "payload.bin"
    target.parent.mkdir()
    target.write_bytes(raw)
    payload = stored_payload(
        "payload",
        payload_bytes=raw,
        relative_path="sources/payload.bin",
    )

    assert verify_stored_payload(payload, tmp_path) is True
    target.write_bytes(b"tampered evidence")
    assert verify_stored_payload(payload, tmp_path) is False
