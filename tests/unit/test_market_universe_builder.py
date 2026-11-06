import hashlib
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    UniverseSelectionRule,
    audit_market_universe_manifest,
)
from aurex.backtest_engine.universe_sources import (
    DailyQuoteVolumePoint,
    S3ListingSnapshot,
    StoredSourcePayload,
    UniverseEnumerationInputArtifact,
    UniverseLiquidityInputArtifact,
    build_enumeration_artifact,
    build_liquidity_artifact,
    build_symbol_liquidity_input,
    market_archive_index,
)
from scripts.build_market_universe import (
    S3_ROOT_PREFIX,
    authoritative_rule,
    binance_archive_uri,
    build_manifest_from_inputs,
    builder_contract_hash,
    load_contamination_ledger,
    market_data_api_uri,
    source_symbol_id,
    structural_liquidity_skip_reason,
)


def payload(receipt_id: str) -> StoredSourcePayload:
    raw = receipt_id.encode()
    return StoredSourcePayload(
        receipt_id=receipt_id,
        purpose="Builder fixture",
        uri=f"https://example.test/{receipt_id}",
        retrieved_at="2026-07-22T14:00:00Z",
        payload_sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        relative_path=f"market_universe_sources_v1/{receipt_id}.bin",
    )


def page(
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
        payload=payload(receipt_id),
    )


def market(symbol: str, months: list[str]):
    prefix = f"{S3_ROOT_PREFIX}{symbol}/4h/"
    keys = []
    for month in months:
        keys.extend(
            [
                f"{prefix}{symbol}-4h-{month}.zip",
                f"{prefix}{symbol}-4h-{month}.zip.CHECKSUM",
            ]
        )
    return market_archive_index(
        symbol=symbol,
        quote_asset="USDT",
        timeframe="4h",
        listing_pages=[page(f"listing-{symbol}", prefix=prefix, keys=keys)],
    )


def test_authoritative_rule_is_bound_to_contamination_and_non_outcome_fields() -> None:
    ledger = load_contamination_ledger(
        Path("data/evidence/strategy_contamination_ledger_v1.json")
    )
    rule = authoritative_rule(ledger)

    assert rule.contamination_ledger_hash == ledger.ledger_evidence_hash
    assert rule.development_only_symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert rule.required_archive_months[0] == "2023-01"
    assert rule.required_archive_months[-1] == "2024-12"
    assert len(rule.required_archive_months) == 24
    assert rule.allowed_selection_fields == ["open_time", "quote_asset_volume"]
    assert "close" in rule.forbidden_selection_fields
    assert "strategy_return" in rule.forbidden_selection_fields


def test_offline_builder_assigns_roles_and_audits_end_to_end() -> None:
    ledger = load_contamination_ledger(
        Path("data/evidence/strategy_contamination_ledger_v1.json")
    )
    base_rule = authoritative_rule(ledger)
    rule_payload = base_rule.model_dump()
    rule_payload["minimum_decision_markets"] = 1
    rule = UniverseSelectionRule.model_validate(rule_payload)
    symbols = ["ADAUSDT", "BTCUSDT"]
    root = page(
        "root",
        prefix=S3_ROOT_PREFIX,
        common_prefixes=[f"{S3_ROOT_PREFIX}{symbol}/" for symbol in symbols],
    )
    enumeration = build_enumeration_artifact(
        generated_at=datetime(2026, 7, 22, 14, tzinfo=UTC),
        endpoint="https://example.test/bucket",
        root_prefix=S3_ROOT_PREFIX,
        quote_asset="USDT",
        timeframe="4h",
        root_pages=[root],
        markets=[market(symbol, rule.required_archive_months) for symbol in symbols],
    )
    points = [
        DailyQuoteVolumePoint(
            open_time=rule.selection_start + timedelta(days=offset),
            quote_asset_volume="20000000",
        )
        for offset in range(731)
    ]
    liquidity = build_liquidity_artifact(
        generated_at=enumeration.generated_at,
        selection_start=rule.selection_start,
        selection_end=rule.selection_end,
        series=[
            build_symbol_liquidity_input(
                symbol=symbol,
                source_method="BINANCE_MARKET_DATA_API",
                source_payloads=[payload(f"api-{symbol}")],
                points=points,
            )
            for symbol in symbols
        ],
    )

    manifest = build_manifest_from_inputs(
        enumeration=enumeration,
        liquidity=liquidity,
        rule=rule,
        builder_hash="a" * 64,
    )

    assert manifest.status == "READY"
    assert manifest.summary.decision_symbols == ["ADAUSDT"]
    assert manifest.summary.development_only_symbols == ["BTCUSDT"]
    assert manifest.strategy_outcome_fields_inspected == []
    assert audit_market_universe_manifest(manifest)["status"] == "PASS"


def test_structural_skip_is_decided_before_liquidity_or_returns() -> None:
    ledger = load_contamination_ledger(
        Path("data/evidence/strategy_contamination_ledger_v1.json")
    )
    rule = authoritative_rule(ledger)
    incomplete = market("ADAUSDT", rule.required_archive_months[:-1])
    cash_like = market("USDCUSDT", rule.required_archive_months)

    assert "missing required 4h archives: 2024-12" in structural_liquidity_skip_reason(
        rule, incomplete
    )
    assert "cash-like base asset" in structural_liquidity_skip_reason(rule, cash_like)


def test_market_data_api_window_is_exact_and_contract_hash_is_stable() -> None:
    uri = market_data_api_uri(
        "BTCUSDT",
        datetime(2023, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 1, tzinfo=UTC),
    )

    assert "startTime=1672531200000" in uri
    assert "endTime=1735689599999" in uri
    assert "limit=1000" in uri
    assert builder_contract_hash() == builder_contract_hash()
    assert len(builder_contract_hash()) == 64


def test_unicode_market_identity_is_preserved_but_storage_path_is_ascii_safe() -> None:
    symbol = "\u5e01\u5b89\u4eba\u751fUSDT"

    storage_id = source_symbol_id(symbol)
    uri = binance_archive_uri(symbol, "1d", f"{symbol}-1d-2024-12.zip")

    assert storage_id.startswith("unicode-")
    assert storage_id.isascii()
    assert "%E5%B8%81" in uri
    assert symbol not in uri
    assert source_symbol_id("BTCUSDT") == "BTCUSDT"


def test_authoritative_universe_artifacts_rebuild_without_network() -> None:
    enumeration = UniverseEnumerationInputArtifact.model_validate_json(
        Path("data/evidence/market_universe_enumeration_v1.json").read_text(
            encoding="utf-8"
        )
    )
    liquidity = UniverseLiquidityInputArtifact.model_validate_json(
        Path("data/evidence/market_universe_liquidity_inputs_v1.json").read_text(
            encoding="utf-8"
        )
    )
    stored = MarketUniverseManifest.model_validate_json(
        Path("data/evidence/market_universe_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    ledger = load_contamination_ledger(
        Path("data/evidence/strategy_contamination_ledger_v1.json")
    )

    rebuilt = build_manifest_from_inputs(
        enumeration=enumeration,
        liquidity=liquidity,
        rule=authoritative_rule(ledger),
        builder_hash=builder_contract_hash(),
    )

    assert rebuilt == stored
    assert audit_market_universe_manifest(stored)["status"] == "PASS"
    assert stored.manifest_evidence_hash == (
        "dacc57f649846f716b8134aa0abba5accc78b0f1607d653addb0df3d9e132a74"
    )
    assert stored.status == "READY"
    assert stored.summary.enumerated_usdt_markets == 680
    assert stored.summary.decision_market_count == 35
    assert stored.summary.development_only_market_count == 3
    assert stored.summary.excluded_market_count == 642
    assert len(stored.source_receipts) == 1534
    assert Counter(item.source_method for item in liquidity.series) == {
        "UNAVAILABLE": 406,
        "BINANCE_MARKET_DATA_API": 262,
        "BINANCE_VISION_ARCHIVES": 12,
    }
    assert all(not item.strategy_outcome_fields_inspected for item in liquidity.series)
    assert all(
        not item.evidence.strategy_outcome_fields_inspected
        for item in stored.assessments
    )
