import argparse
import hashlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    ResearchDataPartition,
    UniverseSelectionRule,
    UniverseSymbolEvidence,
    audit_market_universe_manifest,
    build_market_universe_manifest,
    universe_evidence_hash,
)
from aurex.backtest_engine.universe_sources import (
    HistoricalMarketArchiveIndex,
    S3ListingSnapshot,
    StoredSourcePayload,
    SymbolLiquidityInput,
    UniverseEnumerationInputArtifact,
    UniverseLiquidityInputArtifact,
    artifact_receipts,
    build_enumeration_artifact,
    build_liquidity_artifact,
    build_s3_listing_url,
    build_symbol_liquidity_input,
    market_archive_index,
    parse_api_daily_quote_volumes,
    parse_checksum_payload,
    parse_daily_archive_quote_volumes,
    parse_s3_listing_xml,
    summarize_daily_liquidity,
    symbols_from_common_prefixes,
    verify_stored_payload,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ENUMERATION_OUTPUT = DEFAULT_EVIDENCE_ROOT / "market_universe_enumeration_v1.json"
DEFAULT_LIQUIDITY_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "market_universe_liquidity_inputs_v1.json"
)
DEFAULT_MANIFEST_OUTPUT = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_SOURCE_ROOT = DEFAULT_EVIDENCE_ROOT / "market_universe_sources_v1"
DEFAULT_CONTAMINATION_LEDGER = (
    DEFAULT_EVIDENCE_ROOT / "strategy_contamination_ledger_v1.json"
)

S3_ENDPOINT = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
S3_ROOT_PREFIX = "data/spot/monthly/klines/"
BINANCE_ARCHIVE_BASE_URI = "https://data.binance.vision/data/spot/monthly/klines"
BINANCE_MARKET_DATA_API_URI = "https://data-api.binance.vision/api/v3/klines"
QUOTE_ASSET = "USDT"
TIMEFRAME = "4h"
SELECTION_START = datetime(2023, 1, 1, tzinfo=UTC)
SELECTION_END = datetime(2025, 1, 1, tzinfo=UTC)
MAX_S3_LISTING_BYTES = 5 * 1024 * 1024
MAX_API_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_DAILY_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MAX_LISTING_PAGES = 100

CASH_LIKE_BASE_ASSETS = [
    "AEUR",
    "AUD",
    "BIDR",
    "BRL",
    "BUSD",
    "BVND",
    "DAI",
    "EUR",
    "FDUSD",
    "GBP",
    "IDRT",
    "NGN",
    "PAX",
    "RUB",
    "TRY",
    "TUSD",
    "UAH",
    "USDC",
    "USDP",
    "USDS",
    "USDSB",
    "UST",
    "USTC",
    "VAI",
]
LEVERAGED_TOKEN_SUFFIXES = ["BEAR", "BULL", "DOWN", "UP"]


def authoritative_rule(
    contamination_ledger: StrategyContaminationLedger,
) -> UniverseSelectionRule:
    if not audit_contamination_ledger(contamination_ledger):
        raise ValueError("Contamination ledger failed its evidence-hash audit")
    development_only_symbols = sorted(
        {
            symbol
            for record in contamination_ledger.records
            for symbol in record.symbols
            if symbol.endswith(QUOTE_ASSET)
        }
    )
    return UniverseSelectionRule(
        rule_id="binance-usdt-spot-development-liquidity-v1",
        rule_version="1.0.0",
        quote_asset=QUOTE_ASSET,
        timeframe=TIMEFRAME,
        selection_start=SELECTION_START,
        selection_end=SELECTION_END,
        required_archive_months=required_months(SELECTION_START, SELECTION_END),
        minimum_daily_rows=731,
        minimum_active_days=700,
        minimum_median_daily_quote_volume=10_000_000,
        minimum_p10_daily_quote_volume=1_000_000,
        minimum_decision_markets=12,
        contamination_ledger_hash=contamination_ledger.ledger_evidence_hash,
        excluded_base_assets=CASH_LIKE_BASE_ASSETS,
        excluded_base_suffixes=LEVERAGED_TOKEN_SUFFIXES,
        development_only_symbols=development_only_symbols,
        enumeration_uri=S3_ENDPOINT,
        archive_base_uri=BINANCE_ARCHIVE_BASE_URI,
        liquidity_api_uri=BINANCE_MARKET_DATA_API_URI,
        allowed_selection_fields=["open_time", "quote_asset_volume"],
        forbidden_selection_fields=[
            "close",
            "close_time",
            "high",
            "low",
            "number_of_trades",
            "open",
            "strategy_expectancy",
            "strategy_profit_factor",
            "strategy_return",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "volume",
        ],
    )


def authoritative_partitions() -> list[ResearchDataPartition]:
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


def required_months(start: datetime, end: datetime) -> list[str]:
    cursor = datetime(start.year, start.month, 1, tzinfo=UTC)
    months: list[str] = []
    while cursor < end:
        months.append(f"{cursor.year:04d}-{cursor.month:02d}")
        if cursor.month == 12:
            cursor = datetime(cursor.year + 1, 1, 1, tzinfo=UTC)
        else:
            cursor = datetime(cursor.year, cursor.month + 1, 1, tzinfo=UTC)
    return months


def load_contamination_ledger(path: Path) -> StrategyContaminationLedger:
    ledger = StrategyContaminationLedger.model_validate_json(path.read_text(encoding="utf-8"))
    if not audit_contamination_ledger(ledger):
        raise ValueError("Stored contamination ledger failed its evidence-hash audit")
    return ledger


def acquire_listing_pages(
    *,
    endpoint: str,
    prefix: str,
    delimiter: str | None,
    evidence_root: Path,
    relative_directory: str,
    receipt_prefix: str,
    purpose: str,
) -> list[S3ListingSnapshot]:
    pages: list[S3ListingSnapshot] = []
    marker: str | None = None
    seen_markers: set[str] = set()
    for page_number in range(1, MAX_LISTING_PAGES + 1):
        uri = build_s3_listing_url(
            endpoint,
            prefix=prefix,
            delimiter=delimiter,
            marker=marker,
        )
        stored = fetch_and_store(
            uri=uri,
            evidence_root=evidence_root,
            relative_path=f"{relative_directory}/page-{page_number:04d}.xml",
            receipt_id=f"{receipt_prefix}-{page_number:04d}",
            purpose=purpose,
            maximum_bytes=MAX_S3_LISTING_BYTES,
        )
        if stored.http_status != 200:
            raise ValueError(f"S3 listing returned HTTP {stored.http_status}: {uri}")
        parsed = parse_s3_listing_xml(read_stored_payload(stored, evidence_root))
        if parsed.prefix != prefix:
            raise ValueError("S3 listing response prefix does not match its request")
        if marker is not None and parsed.marker not in (None, marker):
            raise ValueError("S3 listing response marker does not match its request")
        pages.append(S3ListingSnapshot(**parsed.model_dump(), payload=stored))
        if not parsed.is_truncated:
            return pages
        if parsed.next_marker in seen_markers:
            raise ValueError("S3 listing pagination repeated a continuation marker")
        seen_markers.add(parsed.next_marker)
        marker = parsed.next_marker
    raise ValueError(f"S3 listing exceeded {MAX_LISTING_PAGES} pages for {prefix}")


def acquire_enumeration(
    *,
    generated_at: datetime,
    evidence_root: Path,
    workers: int,
) -> UniverseEnumerationInputArtifact:
    root_pages = acquire_listing_pages(
        endpoint=S3_ENDPOINT,
        prefix=S3_ROOT_PREFIX,
        delimiter="/",
        evidence_root=evidence_root,
        relative_directory="market_universe_sources_v1/enumeration/root",
        receipt_prefix="universe-s3-root",
        purpose="Binance Vision historical spot-kline symbol enumeration",
    )
    all_symbols = symbols_from_common_prefixes(
        [prefix for page in root_pages for prefix in page.common_prefixes],
        S3_ROOT_PREFIX,
    )
    quote_symbols = [symbol for symbol in all_symbols if symbol.endswith(QUOTE_ASSET)]
    print(
        f"Enumerated {len(all_symbols)} historical spot symbols; "
        f"capturing {len(quote_symbols)} {QUOTE_ASSET} archive listings.",
        flush=True,
    )

    def acquire_market(symbol: str) -> HistoricalMarketArchiveIndex:
        storage_id = source_symbol_id(symbol)
        prefix = f"{S3_ROOT_PREFIX}{symbol}/{TIMEFRAME}/"
        pages = acquire_listing_pages(
            endpoint=S3_ENDPOINT,
            prefix=prefix,
            delimiter=None,
            evidence_root=evidence_root,
            relative_directory=(
                f"market_universe_sources_v1/enumeration/markets/{storage_id}"
            ),
            receipt_prefix=f"universe-s3-market-{storage_id}",
            purpose=f"Binance Vision {symbol} {TIMEFRAME} monthly archive listing",
        )
        return market_archive_index(
            symbol=symbol,
            quote_asset=QUOTE_ASSET,
            timeframe=TIMEFRAME,
            listing_pages=pages,
        )

    markets: list[HistoricalMarketArchiveIndex] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(acquire_market, symbol): symbol for symbol in quote_symbols}
        for completed, future in enumerate(as_completed(futures), start=1):
            symbol = futures[future]
            try:
                markets.append(future.result())
            except Exception as exc:
                raise RuntimeError(f"Archive listing acquisition failed for {symbol}") from exc
            if completed % 25 == 0 or completed == len(futures):
                print(
                    f"Archive listings captured: {completed}/{len(futures)}",
                    flush=True,
                )
    return build_enumeration_artifact(
        generated_at=generated_at,
        endpoint=S3_ENDPOINT,
        root_prefix=S3_ROOT_PREFIX,
        quote_asset=QUOTE_ASSET,
        timeframe=TIMEFRAME,
        root_pages=root_pages,
        markets=markets,
    )


def structural_liquidity_skip_reason(
    rule: UniverseSelectionRule,
    market: HistoricalMarketArchiveIndex,
) -> str | None:
    required = set(rule.required_archive_months)
    missing_archives = sorted(required - set(market.archive_months))
    missing_checksums = sorted(required - set(market.checksum_sidecar_months))
    reasons: list[str] = []
    if market.base_asset in rule.excluded_base_assets:
        reasons.append("cash-like base asset excluded before liquidity acquisition")
    if any(market.base_asset.endswith(suffix) for suffix in rule.excluded_base_suffixes):
        reasons.append("leveraged-token suffix excluded before liquidity acquisition")
    if missing_archives:
        reasons.append(f"missing required 4h archives: {','.join(missing_archives)}")
    if missing_checksums:
        reasons.append(f"missing required checksum sidecars: {','.join(missing_checksums)}")
    return "; ".join(reasons)[:500] if reasons else None


def market_data_api_uri(symbol: str, start: datetime, end: datetime) -> str:
    query = urllib.parse.urlencode(
        [
            ("symbol", symbol),
            ("interval", "1d"),
            ("startTime", int(start.timestamp() * 1000)),
            ("endTime", int(end.timestamp() * 1000) - 1),
            ("limit", 1000),
        ]
    )
    return f"{BINANCE_MARKET_DATA_API_URI}?{query}"


def acquire_symbol_liquidity(
    *,
    market: HistoricalMarketArchiveIndex,
    rule: UniverseSelectionRule,
    evidence_root: Path,
) -> SymbolLiquidityInput:
    skip_reason = structural_liquidity_skip_reason(rule, market)
    if skip_reason:
        return build_symbol_liquidity_input(
            symbol=market.symbol,
            source_method="UNAVAILABLE",
            source_payloads=[],
            points=[],
            source_error=skip_reason,
        )

    source_payloads: list[StoredSourcePayload] = []
    storage_id = source_symbol_id(market.symbol)
    api_failure = ""
    try:
        api_payload = fetch_and_store(
            uri=market_data_api_uri(
                market.symbol,
                rule.selection_start,
                rule.selection_end,
            ),
            evidence_root=evidence_root,
            relative_path=(
                f"market_universe_sources_v1/liquidity/api/{storage_id}.json"
            ),
            receipt_id=f"universe-liquidity-api-{storage_id}",
            purpose=(
                f"Binance market-data-only daily quote volume for {market.symbol}"
            ),
            maximum_bytes=MAX_API_RESPONSE_BYTES,
        )
        source_payloads.append(api_payload)
        if 200 <= api_payload.http_status < 300:
            api_points = parse_api_daily_quote_volumes(
                read_stored_payload(api_payload, evidence_root),
                selection_start=rule.selection_start,
                selection_end=rule.selection_end,
            )
            api_summary = summarize_daily_liquidity(
                api_points,
                selection_start=rule.selection_start,
                selection_end=rule.selection_end,
            )
            if (
                api_summary.daily_row_count >= rule.minimum_daily_rows
                and api_summary.duplicate_day_count == 0
                and api_summary.missing_day_count == 0
            ):
                return build_symbol_liquidity_input(
                    symbol=market.symbol,
                    source_method="BINANCE_MARKET_DATA_API",
                    source_payloads=source_payloads,
                    points=api_points,
                )
            api_failure = (
                "market-data API coverage incomplete "
                f"(rows={api_summary.daily_row_count}, "
                f"duplicates={api_summary.duplicate_day_count}, "
                f"missing={api_summary.missing_day_count})"
            )
        else:
            api_failure = f"market-data API HTTP {api_payload.http_status}"
    except Exception as exc:
        api_failure = f"market-data API unavailable: {type(exc).__name__}: {exc}"

    try:
        archive_points = []
        for month in rule.required_archive_months:
            archive_name = f"{market.symbol}-1d-{month}.zip"
            archive_uri = binance_archive_uri(market.symbol, "1d", archive_name)
            checksum_payload = fetch_and_store(
                uri=f"{archive_uri}.CHECKSUM",
                evidence_root=evidence_root,
                relative_path=(
                    "market_universe_sources_v1/liquidity/archives/"
                    f"{storage_id}/{source_archive_name(storage_id, month)}.CHECKSUM"
                ),
                receipt_id=(
                    f"universe-liquidity-archive-{storage_id}-{month}-checksum"
                ),
                purpose=f"Binance Vision checksum for {market.symbol} 1d {month}",
                maximum_bytes=MAX_CHECKSUM_BYTES,
            )
            archive_payload = fetch_and_store(
                uri=archive_uri,
                evidence_root=evidence_root,
                relative_path=(
                    "market_universe_sources_v1/liquidity/archives/"
                    f"{storage_id}/{source_archive_name(storage_id, month)}"
                ),
                receipt_id=f"universe-liquidity-archive-{storage_id}-{month}",
                purpose=f"Binance Vision daily kline archive for {market.symbol} {month}",
                maximum_bytes=MAX_DAILY_ARCHIVE_BYTES,
            )
            source_payloads.extend([archive_payload, checksum_payload])
            if archive_payload.http_status != 200 or checksum_payload.http_status != 200:
                raise ValueError(f"daily archive or checksum HTTP failure for {month}")
            archive_bytes = read_stored_payload(archive_payload, evidence_root)
            checksum_bytes = read_stored_payload(checksum_payload, evidence_root)
            expected_hash = parse_checksum_payload(checksum_bytes, archive_name)
            if hashlib.sha256(archive_bytes).hexdigest() != expected_hash:
                raise ValueError(f"daily archive checksum mismatch for {month}")
            archive_points.extend(
                parse_daily_archive_quote_volumes(
                    archive_bytes,
                    archive_name=archive_name,
                    selection_start=rule.selection_start,
                    selection_end=rule.selection_end,
                )
            )
        return build_symbol_liquidity_input(
            symbol=market.symbol,
            source_method="BINANCE_VISION_ARCHIVES",
            source_payloads=source_payloads,
            points=archive_points,
        )
    except Exception as exc:
        source_error = (
            f"{api_failure}; archive fallback failed: {type(exc).__name__}: {exc}"
        )[:500]
        return build_symbol_liquidity_input(
            symbol=market.symbol,
            source_method="UNAVAILABLE",
            source_payloads=source_payloads,
            points=[],
            source_error=source_error,
        )


def acquire_liquidity(
    *,
    generated_at: datetime,
    enumeration: UniverseEnumerationInputArtifact,
    rule: UniverseSelectionRule,
    evidence_root: Path,
    workers: int,
) -> UniverseLiquidityInputArtifact:
    series: list[SymbolLiquidityInput] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                acquire_symbol_liquidity,
                market=market,
                rule=rule,
                evidence_root=evidence_root,
            ): market.symbol
            for market in enumeration.markets
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            symbol = futures[future]
            try:
                series.append(future.result())
            except Exception as exc:
                raise RuntimeError(f"Liquidity acquisition failed for {symbol}") from exc
            if completed % 25 == 0 or completed == len(futures):
                print(f"Liquidity inputs captured: {completed}/{len(futures)}", flush=True)
    return build_liquidity_artifact(
        generated_at=generated_at,
        selection_start=rule.selection_start,
        selection_end=rule.selection_end,
        series=series,
    )


def build_manifest_from_inputs(
    *,
    enumeration: UniverseEnumerationInputArtifact,
    liquidity: UniverseLiquidityInputArtifact,
    rule: UniverseSelectionRule,
    builder_hash: str,
) -> MarketUniverseManifest:
    if enumeration.quote_asset != rule.quote_asset or enumeration.timeframe != rule.timeframe:
        raise ValueError("Enumeration artifact does not match the frozen universe rule")
    if (
        liquidity.selection_start != rule.selection_start
        or liquidity.selection_end != rule.selection_end
    ):
        raise ValueError("Liquidity artifact does not match the frozen selection window")
    liquidity_by_symbol = {item.symbol: item for item in liquidity.series}
    market_symbols = [market.symbol for market in enumeration.markets]
    if sorted(liquidity_by_symbol) != market_symbols:
        raise ValueError("Liquidity artifact must preserve every enumerated quote market")

    evidence: list[UniverseSymbolEvidence] = []
    required = set(rule.required_archive_months)
    expected_days = (rule.selection_end.date() - rule.selection_start.date()).days
    for market in enumeration.markets:
        inputs = liquidity_by_symbol[market.symbol]
        if inputs.source_method == "UNAVAILABLE":
            summary = summarize_daily_liquidity(
                [],
                selection_start=rule.selection_start,
                selection_end=rule.selection_end,
            )
            if summary.missing_day_count != expected_days:
                raise AssertionError("Unavailable liquidity summary is internally inconsistent")
        else:
            summary = summarize_daily_liquidity(
                inputs.points,
                selection_start=rule.selection_start,
                selection_end=rule.selection_end,
            )
        evidence.append(
            UniverseSymbolEvidence(
                symbol=market.symbol,
                base_asset=market.base_asset,
                quote_asset=market.quote_asset,
                archive_listing_evidence_hash=market.listing_evidence_hash,
                required_archive_months_present=sorted(
                    required & set(market.archive_months)
                ),
                required_checksum_sidecars_present=sorted(
                    required & set(market.checksum_sidecar_months)
                ),
                liquidity_source_method=inputs.source_method,
                liquidity_source_evidence_hash=inputs.source_evidence_hash,
                daily_quote_volume_evidence_hash=(
                    inputs.daily_quote_volume_evidence_hash
                ),
                daily_row_count=summary.daily_row_count,
                active_day_count=summary.active_day_count,
                duplicate_day_count=summary.duplicate_day_count,
                missing_day_count=summary.missing_day_count,
                median_daily_quote_volume=summary.median_daily_quote_volume,
                p10_daily_quote_volume=summary.p10_daily_quote_volume,
                source_error=inputs.source_error,
                market_fields_inspected=inputs.market_fields_inspected,
                strategy_outcome_fields_inspected=[],
            )
        )
    return build_market_universe_manifest(
        generated_at=enumeration.generated_at,
        builder_contract_hash=builder_hash,
        enumeration_bundle_hash=enumeration.enumeration_evidence_hash,
        liquidity_input_artifact_hash=liquidity.liquidity_input_evidence_hash,
        rule=rule,
        partitions=authoritative_partitions(),
        source_receipts=artifact_receipts(enumeration, liquidity),
        evidence=evidence,
        limitations=[
            (
                "Binance Vision archive directories are a historical data-availability "
                "snapshot, not authoritative listing or delisting metadata."
            ),
            (
                "Complete January 2023 through December 2024 4h archives are required; "
                "markets listed later or lacking retained files are excluded mechanically."
            ),
            (
                "Liquidity eligibility uses only development-window daily quote asset "
                "volume; no OHLC value, return, trade, or strategy outcome is inspected."
            ),
            (
                "Binance quote volume does not prove cross-venue liquidity or guarantee "
                "future spread, depth, slippage, or executable capacity."
            ),
            (
                "The raw official payload snapshot is retained because public archive "
                "availability and API responses can change after selection."
            ),
            (
                "Symbols present in the contamination ledger are development-only even "
                "when they pass mechanical data and liquidity thresholds."
            ),
        ],
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "build_market_universe.py",
        project_root / "src" / "aurex" / "backtest_engine" / "universe.py",
        project_root / "src" / "aurex" / "backtest_engine" / "universe_sources.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in contract_paths
            }
        }
    )


def source_symbol_id(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if re.fullmatch(r"[A-Z0-9]+", normalized):
        return normalized
    return f"unicode-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]}"


def source_archive_name(storage_id: str, month: str) -> str:
    return f"{storage_id}-1d-{month}.zip"


def binance_archive_uri(symbol: str, timeframe: str, archive_name: str) -> str:
    encoded = "/".join(
        urllib.parse.quote(part, safe="")
        for part in (symbol, timeframe, archive_name)
    )
    return f"{BINANCE_ARCHIVE_BASE_URI}/{encoded}"


def fetch_and_store(
    *,
    uri: str,
    evidence_root: Path,
    relative_path: str,
    receipt_id: str,
    purpose: str,
    maximum_bytes: int,
) -> StoredSourcePayload:
    destination = safe_evidence_path(evidence_root, relative_path)
    receipt_path = destination.with_name(f"{destination.name}.receipt.json")
    if destination.is_file() and receipt_path.is_file():
        stored = StoredSourcePayload.model_validate_json(
            receipt_path.read_text(encoding="utf-8")
        )
        if (
            stored.uri != uri
            or stored.receipt_id != receipt_id
            or stored.relative_path != relative_path.replace("\\", "/")
            or not verify_stored_payload(stored, evidence_root)
        ):
            raise ValueError(f"Cached source receipt mismatch for {relative_path}")
        return stored

    payload, status = fetch_http_bytes(uri, maximum_bytes)
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(destination, payload)
    stored = StoredSourcePayload(
        receipt_id=receipt_id,
        purpose=purpose,
        uri=uri,
        retrieved_at=datetime.now(UTC),
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        relative_path=relative_path,
        http_status=status,
    )
    atomic_write(receipt_path, (stored.model_dump_json(indent=2) + "\n").encode())
    return stored


def fetch_http_bytes(uri: str, maximum_bytes: int) -> tuple[bytes, int]:
    request = urllib.request.Request(uri, headers={"User-Agent": "Aurex/1.0"})
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        payload = response.read(maximum_bytes + 1)
        status = response.status
    if len(payload) > maximum_bytes:
        raise ValueError(f"Source payload exceeds {maximum_bytes} bytes: {uri}")
    if not payload:
        raise ValueError(f"Source payload is empty: {uri}")
    return payload, status


def read_stored_payload(payload: StoredSourcePayload, evidence_root: Path) -> bytes:
    if not verify_stored_payload(payload, evidence_root):
        raise ValueError(f"Stored source payload failed verification: {payload.relative_path}")
    return safe_evidence_path(evidence_root, payload.relative_path).read_bytes()


def safe_evidence_path(evidence_root: Path, relative_path: str) -> Path:
    root = evidence_root.resolve()
    candidate = (root / relative_path).resolve()
    if root not in candidate.parents:
        raise ValueError("Evidence payload path escaped the evidence root")
    return candidate


def atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_model(path: Path, model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, (model.model_dump_json(indent=2) + "\n").encode())


def load_inputs(
    enumeration_path: Path,
    liquidity_path: Path,
    manifest_path: Path,
) -> tuple[
    UniverseEnumerationInputArtifact,
    UniverseLiquidityInputArtifact,
    MarketUniverseManifest,
]:
    enumeration = UniverseEnumerationInputArtifact.model_validate_json(
        enumeration_path.read_text(encoding="utf-8")
    )
    liquidity = UniverseLiquidityInputArtifact.model_validate_json(
        liquidity_path.read_text(encoding="utf-8")
    )
    manifest = MarketUniverseManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    return enumeration, liquidity, manifest


def verify_all_source_payloads(
    enumeration: UniverseEnumerationInputArtifact,
    liquidity: UniverseLiquidityInputArtifact,
    evidence_root: Path,
) -> None:
    payloads = [*enumeration.source_payloads(), *liquidity.source_payloads()]
    paths = [payload.relative_path for payload in payloads]
    if len(paths) != len(set(paths)):
        raise ValueError("Stored source payload paths must be unique")
    failed = [
        payload.relative_path
        for payload in payloads
        if not verify_stored_payload(payload, evidence_root)
    ]
    if failed:
        raise ValueError(f"Stored source payload verification failed: {failed[:5]}")


def run_check(args) -> MarketUniverseManifest:
    enumeration, liquidity, stored_manifest = load_inputs(
        args.enumeration_output,
        args.liquidity_output,
        args.manifest_output,
    )
    verify_all_source_payloads(enumeration, liquidity, args.evidence_root)
    ledger = load_contamination_ledger(args.contamination_ledger)
    rebuilt = build_manifest_from_inputs(
        enumeration=enumeration,
        liquidity=liquidity,
        rule=authoritative_rule(ledger),
        builder_hash=builder_contract_hash(),
    )
    audit = audit_market_universe_manifest(stored_manifest)
    if audit["status"] != "PASS":
        raise ValueError(f"Stored market universe audit failed: {audit['reasons']}")
    if rebuilt != stored_manifest:
        raise ValueError("Stored market universe differs from deterministic offline rebuild")
    if stored_manifest.status != "READY":
        raise ValueError(
            "Market universe is structurally valid but blocked: only "
            f"{stored_manifest.summary.decision_market_count} decision markets passed"
        )
    print(
        "PASS "
        f"manifest={stored_manifest.manifest_evidence_hash} "
        f"enumerated={stored_manifest.summary.enumerated_usdt_markets} "
        f"decision={stored_manifest.summary.decision_market_count} "
        f"development_only={stored_manifest.summary.development_only_market_count} "
        f"excluded={stored_manifest.summary.excluded_market_count}",
        flush=True,
    )
    return stored_manifest


def run_acquire(args) -> MarketUniverseManifest:
    if args.manifest_output.exists():
        raise ValueError(
            "The frozen market-universe manifest already exists; use --check instead of "
            "overwriting evidence"
        )
    ledger = load_contamination_ledger(args.contamination_ledger)
    rule = authoritative_rule(ledger)
    if args.enumeration_output.exists():
        enumeration = UniverseEnumerationInputArtifact.model_validate_json(
            args.enumeration_output.read_text(encoding="utf-8")
        )
        freeze_timestamp = enumeration.generated_at
        print("Resuming from the frozen enumeration input artifact.", flush=True)
    else:
        freeze_timestamp = datetime.now(UTC)
        enumeration = acquire_enumeration(
            generated_at=freeze_timestamp,
            evidence_root=args.evidence_root,
            workers=args.workers,
        )
        write_model(args.enumeration_output, enumeration)
        print(
            f"WROTE {args.enumeration_output} {enumeration.enumeration_evidence_hash}",
            flush=True,
        )
    if args.liquidity_output.exists():
        liquidity = UniverseLiquidityInputArtifact.model_validate_json(
            args.liquidity_output.read_text(encoding="utf-8")
        )
        print("Resuming from the frozen liquidity input artifact.", flush=True)
    else:
        liquidity = acquire_liquidity(
            generated_at=freeze_timestamp,
            enumeration=enumeration,
            rule=rule,
            evidence_root=args.evidence_root,
            workers=args.workers,
        )
        write_model(args.liquidity_output, liquidity)
        print(
            f"WROTE {args.liquidity_output} {liquidity.liquidity_input_evidence_hash}",
            flush=True,
        )
    verify_all_source_payloads(enumeration, liquidity, args.evidence_root)
    manifest = build_manifest_from_inputs(
        enumeration=enumeration,
        liquidity=liquidity,
        rule=rule,
        builder_hash=builder_contract_hash(),
    )
    write_model(args.manifest_output, manifest)
    print(f"WROTE {args.manifest_output} {manifest.manifest_evidence_hash}", flush=True)
    return run_check(args)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Acquire or offline-verify Aurex's frozen survivorship-aware market universe."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--acquire", action="store_true", help="Capture official source data")
    mode.add_argument("--check", action="store_true", help="Verify frozen data without network")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--enumeration-output", type=Path, default=DEFAULT_ENUMERATION_OUTPUT)
    parser.add_argument("--liquidity-output", type=Path, default=DEFAULT_LIQUIDITY_OUTPUT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument(
        "--contamination-ledger",
        type=Path,
        default=DEFAULT_CONTAMINATION_LEDGER,
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.acquire:
            run_acquire(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
