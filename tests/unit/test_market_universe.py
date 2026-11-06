from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    ResearchDataPartition,
    UniverseSelectionRule,
    UniverseSourceReceipt,
    UniverseSymbolEvidence,
    assess_symbol,
    audit_market_universe_manifest,
    build_market_universe_manifest,
)


def rule(*, minimum_decision_markets: int = 1) -> UniverseSelectionRule:
    return UniverseSelectionRule(
        rule_id="binance-usdt-spot-liquidity-v1",
        rule_version="1.0.0",
        quote_asset="USDT",
        timeframe="4h",
        selection_start="2023-01-01T00:00:00Z",
        selection_end="2025-01-01T00:00:00Z",
        required_archive_months=[f"2023-{month:02d}" for month in range(1, 13)]
        + [f"2024-{month:02d}" for month in range(1, 13)],
        minimum_daily_rows=731,
        minimum_active_days=700,
        minimum_median_daily_quote_volume="10000000",
        minimum_p10_daily_quote_volume="1000000",
        minimum_decision_markets=minimum_decision_markets,
        contamination_ledger_hash="9" * 64,
        excluded_base_assets=["USDC"],
        excluded_base_suffixes=["UP", "DOWN", "BULL", "BEAR"],
        development_only_symbols=["BTCUSDT"],
        enumeration_uri="https://s3-ap-northeast-1.amazonaws.com/data.binance.vision",
        archive_base_uri="https://data.binance.vision/data/spot/monthly/klines",
        liquidity_api_uri="https://data-api.binance.vision/api/v3/klines",
        allowed_selection_fields=["open_time", "quote_asset_volume"],
        forbidden_selection_fields=[
            "close",
            "high",
            "low",
            "open",
            "strategy_return",
        ],
    )


def partitions() -> list[ResearchDataPartition]:
    return [
        ResearchDataPartition(
            name="DEVELOPMENT",
            start="2023-01-01T00:00:00Z",
            end="2025-01-01T00:00:00Z",
            access="OPEN_DEVELOPMENT",
            strategy_outcomes_may_be_inspected=True,
        ),
        ResearchDataPartition(
            name="VALIDATION",
            start="2025-01-01T00:00:00Z",
            end="2026-01-01T00:00:00Z",
            access="SEALED",
        ),
        ResearchDataPartition(
            name="HOLDOUT",
            start="2026-01-01T00:00:00Z",
            end="2026-07-01T00:00:00Z",
            access="SEALED",
        ),
        ResearchDataPartition(
            name="FORWARD",
            start="2026-07-01T00:00:00Z",
            end=None,
            access="LOCKED_FORWARD",
        ),
    ]


def evidence(
    symbol: str,
    *,
    median: str = "20000000",
    p10: str = "2000000",
    present_months: list[str] | None = None,
    checksum_months: list[str] | None = None,
    fields: list[str] | None = None,
) -> UniverseSymbolEvidence:
    required = rule().required_archive_months
    return UniverseSymbolEvidence(
        symbol=symbol,
        base_asset=symbol.removesuffix("USDT"),
        quote_asset="USDT",
        archive_listing_evidence_hash="a" * 64,
        required_archive_months_present=present_months
        if present_months is not None
        else required,
        required_checksum_sidecars_present=checksum_months
        if checksum_months is not None
        else required,
        liquidity_source_method="BINANCE_MARKET_DATA_API",
        liquidity_source_evidence_hash="b" * 64,
        daily_quote_volume_evidence_hash="c" * 64,
        daily_row_count=731,
        active_day_count=731,
        duplicate_day_count=0,
        missing_day_count=0,
        median_daily_quote_volume=median,
        p10_daily_quote_volume=p10,
        market_fields_inspected=fields or ["open_time", "quote_asset_volume"],
    )


def receipt() -> UniverseSourceReceipt:
    return UniverseSourceReceipt(
        receipt_id="enumeration-0001",
        purpose="Binance Vision symbol enumeration",
        uri="https://example.test/listing",
        retrieved_at="2026-07-22T12:00:00Z",
        payload_sha256="d" * 64,
        size_bytes=100,
    )


def manifest(
    symbol_evidence: list[UniverseSymbolEvidence],
    *,
    selection_rule: UniverseSelectionRule | None = None,
) -> MarketUniverseManifest:
    return build_market_universe_manifest(
        generated_at=datetime(2026, 7, 22, 12, tzinfo=UTC),
        builder_contract_hash="e" * 64,
        enumeration_bundle_hash="f" * 64,
        liquidity_input_artifact_hash="1" * 64,
        rule=selection_rule or rule(),
        partitions=partitions(),
        source_receipts=[receipt()],
        evidence=symbol_evidence,
        limitations=["Fixture limitation retained."],
    )


def test_assessment_roles_are_mechanical() -> None:
    decision = assess_symbol(rule(), evidence("ETHUSDT"))
    development = assess_symbol(rule(), evidence("BTCUSDT"))
    low_liquidity = assess_symbol(rule(), evidence("ADAUSDT", median="1", p10="1"))

    assert decision.role == "DECISION_CANDIDATE"
    assert decision.decision_eligible is True
    assert development.role == "DEVELOPMENT_ONLY"
    assert development.included is True
    assert low_liquidity.role == "EXCLUDED"
    assert low_liquidity.exclusion_reasons == [
        "median_daily_quote_volume_below_minimum",
        "p10_daily_quote_volume_below_minimum",
    ]


def test_missing_archives_and_checksums_are_preserved_in_reasons() -> None:
    required = rule().required_archive_months
    assessment = assess_symbol(
        rule(),
        evidence(
            "ETHUSDT",
            present_months=required[1:],
            checksum_months=required[:-1],
        ),
    )

    assert assessment.role == "EXCLUDED"
    assert assessment.exclusion_reasons == [
        "required_archives_missing:2023-01",
        "required_checksum_sidecars_missing:2024-12",
    ]


def test_forbidden_market_field_blocks_selection() -> None:
    assessment = assess_symbol(
        rule(),
        evidence("ETHUSDT", fields=["open_time", "quote_asset_volume", "close"]),
    )

    assert assessment.role == "EXCLUDED"
    assert assessment.exclusion_reasons == [
        "forbidden_selection_field_inspected",
        "selection_fields_not_allowed:close",
    ]


def test_manifest_is_sorted_hash_stable_and_auditable() -> None:
    first = manifest([evidence("SOLUSDT"), evidence("ETHUSDT")])
    second = manifest([evidence("ETHUSDT"), evidence("SOLUSDT")])

    assert first.status == "READY"
    assert first.summary.decision_symbols == ["ETHUSDT", "SOLUSDT"]
    assert first.manifest_evidence_hash == second.manifest_evidence_hash
    assert audit_market_universe_manifest(first)["status"] == "PASS"


def test_manifest_blocks_when_minimum_market_count_is_not_met() -> None:
    blocked = manifest(
        [evidence("ETHUSDT")],
        selection_rule=rule(minimum_decision_markets=2),
    )

    assert blocked.status == "BLOCKED"
    assert blocked.summary.decision_market_count == 1


def test_manifest_audit_detects_tampering() -> None:
    original = manifest([evidence("ETHUSDT")])
    payload = original.model_dump()
    payload["summary"]["decision_market_count"] = 99
    tampered = MarketUniverseManifest.model_validate(payload)

    audit = audit_market_universe_manifest(tampered)

    assert audit["status"] == "BLOCKED"
    assert audit["manifest_evidence_hash_matches"] is False
    assert audit["deterministic_rebuild_matches"] is False


def test_nonempty_strategy_outcome_fields_are_refused() -> None:
    payload = evidence("ETHUSDT").model_dump()
    payload["strategy_outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="cannot inspect strategy outcomes"):
        UniverseSymbolEvidence.model_validate(payload)


def test_partitions_must_be_canonical_and_contiguous() -> None:
    invalid = partitions()
    invalid[1] = invalid[1].model_copy(
        update={"start": datetime(2025, 1, 2, tzinfo=UTC)}
    )

    with pytest.raises(ValueError, match="contiguous"):
        build_market_universe_manifest(
            generated_at=datetime(2026, 7, 22, 12, tzinfo=UTC),
            builder_contract_hash="e" * 64,
            enumeration_bundle_hash="f" * 64,
            liquidity_input_artifact_hash="1" * 64,
            rule=rule(),
            partitions=invalid,
            source_receipts=[receipt()],
            evidence=[evidence("ETHUSDT")],
            limitations=["Fixture limitation retained."],
        )


def test_rule_refuses_impossible_sample_requirements() -> None:
    payload = rule().model_dump()
    payload["minimum_daily_rows"] = 732

    with pytest.raises(ValidationError, match="cannot exceed selection calendar days"):
        UniverseSelectionRule.model_validate(payload)


def test_decimal_metrics_remain_exact() -> None:
    assessment = assess_symbol(rule(), evidence("ETHUSDT"))

    assert assessment.evidence.median_daily_quote_volume == Decimal("20000000")
