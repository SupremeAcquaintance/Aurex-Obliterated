from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import combinations
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JamArchiveQualityResult,
)
from aurex.backtest_engine.jam_successor_distribution_protocol import (  # noqa: E402
    JAM_DISTRIBUTION_GATES,
    JAM_DISTRIBUTION_MONTHS,
    JAM_DISTRIBUTION_QUANTILES,
    JamDevelopmentArchiveTarget,
    JamSuccessorDevelopmentDistributionProtocol,
    audit_jam_successor_distribution_protocol,
)
from aurex.backtest_engine.jam_successor_distribution_result import (  # noqa: E402
    JamDevelopmentArchiveEvidence,
    JamDevelopmentMonthProfile,
    JamDistributionGateResult,
    JamFeatureDistributionMetric,
    JamFeaturePairwiseCorrelation,
    JamFeatureTailConcentration,
    JamSuccessorDevelopmentDistributionResult,
    audit_jam_successor_distribution_result,
    build_jam_successor_distribution_result,
)
from aurex.backtest_engine.jam_successor_feature_specification import (  # noqa: E402
    JAM_FEATURE_IDS,
    JAM_FEATURE_QUALITY_STATES,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_jam_successor_distribution_protocol import (  # noqa: E402
    DEFAULT_FEATURE_AUDIT,
    DEFAULT_FEATURE_PROTOCOL,
    DEFAULT_FEATURE_SPECIFICATION,
    DEFAULT_FULL_AUDIT,
    DEFAULT_FULL_PROTOCOL,
    DEFAULT_FULL_RESULT,
    DEFAULT_QUALITY_RESULT,
    authoritative_protocol,
    development_quarantine,
    load_inputs,
)

DEFAULT_PROTOCOL = Path("data/evidence/jam_successor_development_distribution_protocol_v1.json")
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_FEATURE_ROWS = Path("data/evidence/jam_successor_development_feature_rows_v1.parquet")
DEFAULT_OUTPUT = Path("data/evidence/jam_successor_development_distribution_result_v1.json")
DEFAULT_TEMP_ROOT = Path(".tmp/jam_successor_development_distribution")
DECIMAL_QUANTUM = Decimal("0.000000000000000001")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path) for path in paths
            }
        }
    )


def runner_contract_hash() -> str:
    source_hash = source_contract_hash(
        [
            PROJECT_ROOT / "pyproject.toml",
            PROJECT_ROOT / "scripts" / "run_jam_successor_development_distribution.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_distribution_result.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_distribution_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_feature_specification.py",
        ]
    )
    return universe_evidence_hash(
        {
            "source_contract_hash": source_hash,
            "processing_engine": "duckdb",
            "processing_engine_version": duckdb.__version__,
        }
    )


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _validated_temp_root(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError("Jam distribution temp root must remain under .tmp")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    return resolved


def _write_result(
    path: Path,
    result: JamSuccessorDevelopmentDistributionResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if JamSuccessorDevelopmentDistributionResult.model_validate_json(serialized) != result:
        raise ValueError("Jam distribution result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def load_run_inputs(
    *,
    protocol_path: Path,
    feature_protocol_path: Path,
    feature_specification_path: Path,
    feature_audit_path: Path,
    full_protocol_path: Path,
    full_result_path: Path,
    full_audit_path: Path,
    quality_result_path: Path,
) -> tuple[
    JamSuccessorDevelopmentDistributionProtocol,
    tuple,
    JamArchiveQualityResult,
]:
    inputs = load_inputs(
        feature_protocol_path=feature_protocol_path,
        feature_specification_path=feature_specification_path,
        feature_audit_path=feature_audit_path,
        full_protocol_path=full_protocol_path,
        full_result_path=full_result_path,
        full_audit_path=full_audit_path,
        quality_result_path=quality_result_path,
    )
    protocol = JamSuccessorDevelopmentDistributionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=inputs,
        feature_protocol_path=feature_protocol_path,
        feature_specification_path=feature_specification_path,
        feature_audit_path=feature_audit_path,
    )
    if (
        protocol != expected
        or not audit_jam_successor_distribution_protocol(protocol)
        or duckdb.__version__ != protocol.processing_engine_version
        or protocol.network_access_permitted
        or protocol.validation_2021_access_permitted
        or protocol.holdout_2022_access_permitted
        or protocol.future_label_definition_permitted
        or protocol.event_threshold_definition_permitted
        or protocol.return_calculation_permitted
        or protocol.outcome_access_permitted
        or protocol.strategy_creation_permitted
        or protocol.signal_creation_permitted
        or protocol.candidate_creation_permitted
        or protocol.paper_eligibility_permitted
        or protocol.testnet_strategy_orders_permitted
        or protocol.production_permitted
        or protocol.live_permitted
    ):
        raise ValueError("Jam distribution protocol or frozen lineage changed")
    quality_result = inputs[6]
    quarantine = development_quarantine(quality_result)
    if (
        len(quarantine) != protocol.development_quarantine_minute_count
        or universe_evidence_hash({"minutes": quarantine})
        != protocol.development_quarantine_manifest_hash
    ):
        raise ValueError("Jam development quarantine changed")
    return protocol, inputs, quality_result


def _extract_canonical_member(
    *,
    target: JamDevelopmentArchiveTarget,
    archive_path: Path,
    extracted_path: Path,
) -> int:
    if (
        archive_path.stat().st_size != target.archive_bytes
        or file_sha256(archive_path) != target.archive_sha256
    ):
        raise ValueError(f"Jam archive identity changed: {target.month}")
    with zipfile.ZipFile(archive_path) as archive:
        canonical = [
            member
            for member in archive.infolist()
            if not member.is_dir() and member.filename == target.csv_member_name
        ]
        if len(canonical) != 1:
            raise ValueError(f"Jam canonical archive member changed: {target.month}")
        member = canonical[0]
        if member.file_size != target.csv_member_bytes:
            raise ValueError(f"Jam archive member size changed: {target.month}")
        with archive.open(member) as source, extracted_path.open("xb") as output:
            shutil.copyfileobj(source, output, length=8 * 1_048_576)
    if extracted_path.stat().st_size != target.csv_member_bytes:
        raise ValueError(f"Jam archive extraction changed: {target.month}")
    return extracted_path.stat().st_size


def build_minute_primitive(
    *,
    target: JamDevelopmentArchiveTarget,
    evidence_root: Path,
    temp_root: Path,
) -> JamDevelopmentArchiveEvidence:
    archive_path = evidence_root / target.local_path
    if not archive_path.is_file():
        raise ValueError(f"Jam archive is missing: {target.local_path}")
    extracted_path = temp_root / f"{target.month}-aggTrades.csv"
    primitive_path = temp_root / "primitives" / f"{target.month}.parquet"
    primitive_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_bytes = _extract_canonical_member(
        target=target,
        archive_path=archive_path,
        extracted_path=extracted_path,
    )
    header = "true" if target.header_present else "false"
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("SET threads = 4")
        connection.execute("SET preserve_insertion_order = true")
        connection.execute(
            f"""
            CREATE VIEW source AS
            SELECT
                aggregate_trade_id,
                price,
                quantity,
                first_trade_id,
                last_trade_id,
                CASE
                    WHEN transact_time >= 1000000000000000
                    THEN floor(transact_time / 1000)::BIGINT
                    ELSE transact_time
                END AS transact_time_ms,
                is_buyer_maker
            FROM read_csv(
                '{_sql_path(extracted_path)}',
                columns={{
                    'aggregate_trade_id': 'BIGINT',
                    'price': 'DECIMAL(38,8)',
                    'quantity': 'DECIMAL(38,8)',
                    'first_trade_id': 'BIGINT',
                    'last_trade_id': 'BIGINT',
                    'transact_time': 'BIGINT',
                    'is_buyer_maker': 'BOOLEAN',
                    'is_best_match': 'BOOLEAN'
                }},
                header={header},
                auto_detect=false,
                delim=',',
                quote='',
                escape='',
                strict_mode=true,
                parallel=true
            )
            """
        )
        connection.execute(
            f"""
            COPY (
                WITH minute_rows AS (
                    SELECT
                        floor(transact_time_ms / 60000)::BIGINT
                            * 60000 AS open_time_ms,
                        aggregate_trade_id,
                        transact_time_ms,
                        price,
                        quantity,
                        first_trade_id,
                        last_trade_id,
                        is_buyer_maker
                    FROM source
                )
                SELECT
                    open_time_ms,
                    first(
                        price ORDER BY transact_time_ms, aggregate_trade_id
                    ) AS open_price,
                    max(price) AS high_price,
                    min(price) AS low_price,
                    last(
                        price ORDER BY transact_time_ms, aggregate_trade_id
                    ) AS close_price,
                    sum(quantity) AS base_volume,
                    sum(price * quantity) AS quote_volume,
                    sum(
                        CASE
                            WHEN NOT is_buyer_maker THEN price * quantity
                            ELSE 0::DECIMAL(38,16)
                        END
                    ) AS taker_buy_quote_volume,
                    sum(
                        CASE
                            WHEN is_buyer_maker THEN price * quantity
                            ELSE 0::DECIMAL(38,16)
                        END
                    ) AS taker_sell_quote_volume,
                    sum(last_trade_id - first_trade_id + 1)::HUGEINT
                        AS raw_trade_count,
                    count(*)::BIGINT AS aggregate_row_count
                FROM minute_rows
                GROUP BY open_time_ms
                ORDER BY open_time_ms
            ) TO '{_sql_path(primitive_path)}'
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)
            """
        )
        (
            primitive_count,
            source_rows,
            minimum_time,
            maximum_time,
            unaligned_count,
            invalid_ohlc_count,
            invalid_volume_count,
            side_reconciliation_count,
        ) = connection.execute(
            """
            SELECT
                count(*),
                sum(aggregate_row_count),
                min(open_time_ms),
                max(open_time_ms),
                count(*) FILTER (WHERE open_time_ms % 60000 != 0),
                count(*) FILTER (
                    WHERE high_price < greatest(
                        open_price, low_price, close_price
                    )
                    OR low_price > least(
                        open_price, high_price, close_price
                    )
                ),
                count(*) FILTER (
                    WHERE base_volume <= 0 OR quote_volume <= 0
                    OR raw_trade_count <= 0
                ),
                count(*) FILTER (
                    WHERE quote_volume != (
                        taker_buy_quote_volume + taker_sell_quote_volume
                    )
                )
            FROM read_parquet(?)
            """,
            [str(primitive_path)],
        ).fetchone()
    finally:
        connection.close()
        if extracted_path.exists():
            extracted_path.unlink()
    month_start = int(
        datetime.strptime(target.month, "%Y-%m").replace(tzinfo=UTC).timestamp() * 1_000
    )
    if target.month == "2020-12":
        month_end = int(datetime(2021, 1, 1, tzinfo=UTC).timestamp() * 1_000)
    else:
        year, month = (int(value) for value in target.month.split("-"))
        next_year = year + (month == 12)
        next_month = 1 if month == 12 else month + 1
        month_end = int(datetime(next_year, next_month, 1, tzinfo=UTC).timestamp() * 1_000)
    if (
        int(primitive_count) != target.source_minute_count
        or int(source_rows) != target.source_row_count
        or not month_start <= int(minimum_time) <= int(maximum_time) < month_end
        or any(
            int(value)
            for value in (
                unaligned_count,
                invalid_ohlc_count,
                invalid_volume_count,
                side_reconciliation_count,
            )
        )
    ):
        raise ValueError(f"Jam minute primitive invariant changed: {target.month}")
    evidence = JamDevelopmentArchiveEvidence(
        month=target.month,
        archive_path=target.local_path,
        archive_sha256=target.archive_sha256,
        source_row_count=int(source_rows),
        primitive_minute_count=int(primitive_count),
        extracted_member_bytes=extracted_bytes,
        parquet_bytes=primitive_path.stat().st_size,
        archive_pass=True,
    )
    print(
        f"PRIMITIVE {target.month} rows={evidence.source_row_count} "
        f"minutes={evidence.primitive_minute_count} "
        f"parquet_bytes={evidence.parquet_bytes}",
        flush=True,
    )
    return evidence


def feature_rows_query(
    *,
    primitives_glob: Path,
    start_ms: int,
    end_exclusive_ms: int,
) -> str:
    feature_expressions = {
        "baseline_sell_quote_median_120m": "sell_quote_median",
        "baseline_sell_quote_mad_120m": "sell_quote_mad",
        "baseline_sell_share_median_120m": "sell_share_median",
        "baseline_sell_share_mad_120m": "sell_share_mad",
        "pre_shock_vwap_5m": "pre_vwap",
        "shock_sell_quote_mean_5m": "shock_sell_mean",
        "shock_sell_flow_robust_z_5m": (
            "(shock_sell_mean - sell_quote_median) / (1.4826 * sell_quote_mad)"
        ),
        "shock_sell_share_5m": "shock_sell_share",
        "shock_price_impact_bps_5m": ("10000 * (shock_final_close / pre_vwap - 1)"),
        "shock_low_bps_vs_pre_shock_vwap": ("10000 * (shock_low / pre_vwap - 1)"),
        "confirmation_sell_quote_mean_3m": "confirmation_sell_mean",
        "confirmation_sell_flow_robust_z_3m": (
            "(confirmation_sell_mean - sell_quote_median) / (1.4826 * sell_quote_mad)"
        ),
        "confirmation_sell_share_3m": "confirmation_sell_share",
        "sell_flow_decay_ratio_3m_vs_5m": ("confirmation_sell_mean / shock_sell_mean"),
        "sell_share_decay_delta_5m_to_3m": ("shock_sell_share - confirmation_sell_share"),
        "reclaim_bps_vs_pre_shock_vwap": ("10000 * (confirmation_final_close / pre_vwap - 1)"),
        "bounce_bps_from_shock_low": ("10000 * (confirmation_final_close / shock_low - 1)"),
    }
    if tuple(feature_expressions) != JAM_FEATURE_IDS:
        raise ValueError("Jam SQL feature matrix changed")
    output_features = ",\n".join(
        (
            "CAST(CASE WHEN quality_state = 'READY' "
            f"THEN {expression} ELSE NULL END AS DECIMAL(38,18)) "
            f'AS "{feature_id}"'
        )
        for feature_id, expression in feature_expressions.items()
    )
    return f"""
        WITH calendar AS (
            SELECT
                range::BIGINT AS open_time_ms,
                row_number() OVER () - 1 AS calendar_index
            FROM range({start_ms}, {end_exclusive_ms}, 60000)
        ),
        joined AS (
            SELECT
                c.open_time_ms,
                c.calendar_index,
                strftime(epoch_ms(c.open_time_ms), '%Y-%m') AS month,
                p.open_time_ms IS NOT NULL AS primitive_present,
                q.open_time_ms IS NOT NULL AS quarantined,
                p.close_price,
                p.low_price,
                p.base_volume,
                p.quote_volume,
                p.taker_sell_quote_volume,
                CAST(
                    p.taker_sell_quote_volume / nullif(p.quote_volume, 0)
                    AS DOUBLE
                ) AS sell_share
            FROM calendar c
            LEFT JOIN read_parquet('{_sql_path(primitives_glob)}') p
                USING (open_time_ms)
            LEFT JOIN quarantine q USING (open_time_ms)
        ),
        rolling AS (
            SELECT
                *,
                count(*) FILTER (
                    WHERE primitive_present AND NOT quarantined
                ) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 132 PRECEDING AND CURRENT ROW
                ) AS valid_window_count,
                list(taker_sell_quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 132 PRECEDING AND 13 PRECEDING
                ) AS baseline_sell_quotes,
                list(sell_share) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 132 PRECEDING AND 13 PRECEDING
                ) AS baseline_sell_shares,
                sum(quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 12 PRECEDING AND 8 PRECEDING
                ) AS pre_quote,
                sum(base_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 12 PRECEDING AND 8 PRECEDING
                ) AS pre_base,
                sum(quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 7 PRECEDING AND 3 PRECEDING
                ) AS shock_quote,
                sum(taker_sell_quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 7 PRECEDING AND 3 PRECEDING
                ) / 5 AS shock_sell_mean,
                min(low_price) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 7 PRECEDING AND 3 PRECEDING
                ) AS shock_low,
                lag(close_price, 3) OVER (
                    ORDER BY open_time_ms
                ) AS shock_final_close,
                sum(quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) AS confirmation_quote,
                sum(taker_sell_quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) / 3 AS confirmation_sell_mean,
                close_price AS confirmation_final_close,
                sum(taker_sell_quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 7 PRECEDING AND 3 PRECEDING
                ) AS shock_sell_quote,
                sum(taker_sell_quote_volume) OVER (
                    ORDER BY open_time_ms
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) AS confirmation_sell_quote
            FROM joined
        ),
        centers AS (
            SELECT
                *,
                list_median(baseline_sell_quotes) AS sell_quote_median,
                list_median(baseline_sell_shares) AS sell_share_median
            FROM rolling
        ),
        components AS (
            SELECT
                *,
                list_median(
                    list_transform(
                        baseline_sell_quotes,
                        value -> abs(value - sell_quote_median)
                    )
                ) AS sell_quote_mad,
                list_median(
                    list_transform(
                        baseline_sell_shares,
                        value -> abs(value - sell_share_median)
                    )
                ) AS sell_share_mad,
                pre_quote / nullif(pre_base, 0) AS pre_vwap,
                shock_sell_quote / nullif(shock_quote, 0)
                    AS shock_sell_share,
                confirmation_sell_quote / nullif(confirmation_quote, 0)
                    AS confirmation_sell_share
            FROM centers
        ),
        states AS (
            SELECT
                *,
                CASE
                    WHEN quarantined THEN 'SOURCE_QUARANTINE'
                    WHEN NOT primitive_present THEN 'NO_AGGTRADE_MINUTE'
                    WHEN calendar_index < 132 THEN 'PARTITION_RESET_WARMUP'
                    WHEN valid_window_count != 133 THEN 'POST_DEFECT_WARMUP'
                    WHEN sell_quote_mad = 0 THEN 'DEGENERATE_ROBUST_SCALE'
                    WHEN pre_base = 0
                        OR shock_quote = 0
                        OR confirmation_quote = 0
                        OR shock_sell_mean = 0
                        OR shock_low = 0
                    THEN 'DEGENERATE_DENOMINATOR'
                    ELSE 'READY'
                END AS quality_state
            FROM components
        )
        SELECT
            open_time_ms,
            month,
            quality_state,
            {output_features}
        FROM states
        ORDER BY open_time_ms
    """


def build_feature_rows(
    *,
    protocol: JamSuccessorDevelopmentDistributionProtocol,
    quarantine: list[dict[str, int | str]],
    temp_root: Path,
    output_path: Path,
) -> tuple[str, int, str]:
    if output_path.exists():
        raise ValueError(f"Jam feature-row output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_name(f"{output_path.name}.part")
    if temporary_output.exists():
        raise ValueError(f"Stale transactional feature output exists: {temporary_output}")
    database_path = temp_root / "distribution.duckdb"
    connection = duckdb.connect(database=str(database_path))
    try:
        connection.execute("SET threads = 1")
        connection.execute("SET memory_limit = '6GB'")
        connection.execute("SET preserve_insertion_order = true")
        connection.execute(f"SET temp_directory = '{_sql_path(temp_root / 'duckdb-spill')}'")
        connection.execute("CREATE TABLE quarantine(open_time_ms BIGINT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO quarantine VALUES (?)",
            [(int(item["open_time_ms"]),) for item in quarantine],
        )
        query = feature_rows_query(
            primitives_glob=temp_root / "primitives" / "*.parquet",
            start_ms=protocol.development_start_ms,
            end_exclusive_ms=protocol.development_end_exclusive_ms,
        )
        connection.execute(
            f"""
            COPY ({query}) TO '{_sql_path(temporary_output)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD,
                ROW_GROUP_SIZE 122880
            )
            """
        )
    finally:
        connection.close()
    temporary_output.replace(output_path)
    size = output_path.stat().st_size
    if size > protocol.maximum_output_parquet_bytes:
        raise ValueError("Jam feature-row Parquet exceeds frozen byte limit")
    connection = duckdb.connect(database=":memory:")
    try:
        description = connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)",
            [str(output_path)],
        ).fetchall()
        row = connection.execute(
            """
            SELECT
                count(*),
                count(DISTINCT open_time_ms),
                min(open_time_ms),
                max(open_time_ms),
                count(*) FILTER (WHERE open_time_ms % 60000 != 0)
            FROM read_parquet(?)
            """,
            [str(output_path)],
        ).fetchone()
    finally:
        connection.close()
    expected_columns = (
        "open_time_ms",
        "month",
        "quality_state",
        *JAM_FEATURE_IDS,
    )
    if (
        tuple(item[0] for item in description) != expected_columns
        or int(row[0]) != protocol.expected_calendar_row_count
        or int(row[1]) != protocol.expected_calendar_row_count
        or int(row[2]) != protocol.development_start_ms
        or int(row[3]) != protocol.development_end_exclusive_ms - 60_000
        or int(row[4])
    ):
        raise ValueError("Jam feature-row Parquet invariant changed")
    schema_payload = [
        {
            "column_name": item[0],
            "column_type": item[1],
            "null": item[2],
            "key": item[3],
            "default": item[4],
            "extra": item[5],
        }
        for item in description
    ]
    schema_hash = universe_evidence_hash({"schema": schema_payload})
    output_hash = file_sha256(output_path)
    print(
        f"FEATURE_ROWS rows={row[0]} bytes={size} sha256={output_hash} schema={schema_hash}",
        flush=True,
    )
    return output_hash, size, schema_hash


def _decimal_string(value) -> str:
    if value is None:
        raise ValueError("Jam distribution metric is undefined")
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    if not decimal_value.is_finite():
        raise ValueError("Jam distribution metric is non-finite")
    return format(decimal_value, "f")


def _decimal_ratio(numerator: int, denominator: int) -> str:
    return format(Decimal(numerator) / Decimal(denominator), "f")


def _quantized_correlation(value) -> str:
    decimal_value = Decimal(str(value)).quantize(
        DECIMAL_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )
    if decimal_value > 1 and decimal_value - 1 <= DECIMAL_QUANTUM:
        decimal_value = Decimal(1)
    if decimal_value < -1 and -1 - decimal_value <= DECIMAL_QUANTUM:
        decimal_value = Decimal(-1)
    return format(decimal_value, "f")


def profile_quality(
    *,
    connection: duckdb.DuckDBPyConnection,
    feature_rows_path: Path,
    primitive_glob: Path,
    quarantine: list[dict[str, int | str]],
) -> tuple[dict[str, int], list[JamDevelopmentMonthProfile], int, int]:
    state_rows = connection.execute(
        """
        SELECT quality_state, count(*)
        FROM read_parquet(?)
        GROUP BY quality_state
        """,
        [str(feature_rows_path)],
    ).fetchall()
    quality_counts = {state: 0 for state in JAM_FEATURE_QUALITY_STATES}
    for state, count in state_rows:
        if state not in quality_counts:
            raise ValueError(f"Unknown Jam quality state: {state}")
        quality_counts[state] = int(count)
    primitive_rows = connection.execute(
        f"""
        SELECT
            strftime(epoch_ms(open_time_ms), '%Y-%m') AS month,
            count(*)
        FROM read_parquet('{_sql_path(primitive_glob)}')
        GROUP BY month
        ORDER BY month
        """
    ).fetchall()
    primitive_counts = {month: int(count) for month, count in primitive_rows}
    quarantine_counts = {month: 0 for month in JAM_DISTRIBUTION_MONTHS}
    for item in quarantine:
        quarantine_counts[str(item["month"])] += 1
    monthly_rows = connection.execute(
        """
        SELECT month, quality_state, count(*)
        FROM read_parquet(?)
        GROUP BY month, quality_state
        ORDER BY month, quality_state
        """,
        [str(feature_rows_path)],
    ).fetchall()
    monthly_state_counts = {
        month: {state: 0 for state in JAM_FEATURE_QUALITY_STATES}
        for month in JAM_DISTRIBUTION_MONTHS
    }
    for month, state, count in monthly_rows:
        monthly_state_counts[month][state] = int(count)
    profiles = []
    for month in JAM_DISTRIBUTION_MONTHS:
        state_counts = monthly_state_counts[month]
        calendar_count = sum(state_counts.values())
        ready_count = state_counts["READY"]
        profiles.append(
            JamDevelopmentMonthProfile(
                month=month,
                calendar_row_count=calendar_count,
                primitive_minute_count=primitive_counts.get(month, 0),
                quarantine_minute_count=quarantine_counts[month],
                ready_row_count=ready_count,
                ready_row_rate=_decimal_ratio(
                    ready_count,
                    calendar_count,
                ),
                quality_state_counts=state_counts,
            )
        )
    return (
        quality_counts,
        profiles,
        sum(primitive_counts.values()),
        quality_counts["READY"],
    )


def profile_features(
    *,
    connection: duckdb.DuckDBPyConnection,
    feature_rows_path: Path,
    calendar_row_count: int,
) -> list[JamFeatureDistributionMetric]:
    metrics = []
    for feature in JAM_FEATURE_IDS:
        quantiles = ",\n".join(
            f'quantile_cont("{feature}", {quantile}) AS q{index}'
            for index, quantile in enumerate(JAM_DISTRIBUTION_QUANTILES)
        )
        row = connection.execute(
            f"""
            SELECT
                count("{feature}"),
                count(DISTINCT "{feature}"),
                min("{feature}"),
                max("{feature}"),
                avg("{feature}"),
                stddev_pop("{feature}"),
                {quantiles},
                count(*) FILTER (WHERE "{feature}" < 0),
                count(*) FILTER (WHERE "{feature}" = 0),
                count(*) FILTER (WHERE "{feature}" > 0)
            FROM read_parquet(?)
            """,
            [str(feature_rows_path)],
        ).fetchone()
        ready_count = int(row[0])
        quantile_values = {
            quantile: _decimal_string(row[6 + index])
            for index, quantile in enumerate(JAM_DISTRIBUTION_QUANTILES)
        }
        iqr = Decimal(quantile_values["0.75"]) - Decimal(quantile_values["0.25"])
        metric = JamFeatureDistributionMetric(
            feature_id=feature,
            calendar_row_count=calendar_row_count,
            ready_value_count=ready_count,
            null_value_count=calendar_row_count - ready_count,
            unique_value_count=int(row[1]),
            minimum=_decimal_string(row[2]),
            maximum=_decimal_string(row[3]),
            mean=_decimal_string(row[4]),
            population_standard_deviation=_decimal_string(row[5]),
            quantiles=quantile_values,
            interquartile_range=format(iqr, "f"),
            negative_value_count=int(row[15]),
            zero_value_count=int(row[16]),
            positive_value_count=int(row[17]),
        )
        metrics.append(metric)
        print(
            f"FEATURE {feature} ready={metric.ready_value_count} "
            f"unique={metric.unique_value_count} "
            f"iqr={metric.interquartile_range}",
            flush=True,
        )
    return metrics


def profile_tails(
    *,
    connection: duckdb.DuckDBPyConnection,
    feature_rows_path: Path,
    metrics: list[JamFeatureDistributionMetric],
) -> list[JamFeatureTailConcentration]:
    results = []
    for metric in metrics:
        feature = metric.feature_id
        lower = metric.quantiles["0.01"]
        upper = metric.quantiles["0.99"]
        rows = connection.execute(
            f"""
            SELECT
                month,
                count(*) FILTER (WHERE "{feature}" <= ?),
                count(*) FILTER (WHERE "{feature}" >= ?)
            FROM read_parquet(?)
            GROUP BY month
            ORDER BY month
            """,
            [Decimal(lower), Decimal(upper), str(feature_rows_path)],
        ).fetchall()
        lower_counts = [(month, int(count)) for month, count, _ in rows]
        upper_counts = [(month, int(count)) for month, _, count in rows]
        lower_total = sum(count for _, count in lower_counts)
        upper_total = sum(count for _, count in upper_counts)
        largest_lower = min(
            lower_counts,
            key=lambda item: (-item[1], item[0]),
        )
        largest_upper = min(
            upper_counts,
            key=lambda item: (-item[1], item[0]),
        )
        results.append(
            JamFeatureTailConcentration(
                feature_id=feature,
                lower_threshold=lower,
                upper_threshold=upper,
                lower_tail_count=lower_total,
                upper_tail_count=upper_total,
                largest_lower_tail_month=largest_lower[0],
                largest_lower_tail_month_share=_decimal_ratio(
                    largest_lower[1],
                    lower_total,
                ),
                largest_upper_tail_month=largest_upper[0],
                largest_upper_tail_month_share=_decimal_ratio(
                    largest_upper[1],
                    upper_total,
                ),
            )
        )
    return results


def profile_correlations(
    *,
    connection: duckdb.DuckDBPyConnection,
    feature_rows_path: Path,
) -> list[JamFeaturePairwiseCorrelation]:
    pairs = list(combinations(JAM_FEATURE_IDS, 2))
    expressions = ",\n".join(
        (f'corr(CAST("{left}" AS DOUBLE), CAST("{right}" AS DOUBLE)) AS c{index:03d}')
        for index, (left, right) in enumerate(pairs)
    )
    row = connection.execute(
        f"""
        SELECT {expressions}
        FROM read_parquet(?)
        WHERE quality_state = 'READY'
        """,
        [str(feature_rows_path)],
    ).fetchone()
    correlations = [
        JamFeaturePairwiseCorrelation(
            left_feature_id=left,
            right_feature_id=right,
            pearson_correlation=_quantized_correlation(row[index]),
        )
        for index, (left, right) in enumerate(pairs)
    ]
    maximum = max(
        correlations,
        key=lambda item: abs(Decimal(item.pearson_correlation)),
    )
    print(
        "CORRELATIONS "
        f"pairs={len(correlations)} "
        f"maximum={maximum.left_feature_id}|{maximum.right_feature_id} "
        f"value={maximum.pearson_correlation}",
        flush=True,
    )
    return correlations


def evaluate_gates(
    *,
    protocol: JamSuccessorDevelopmentDistributionProtocol,
    archive_evidence: list[JamDevelopmentArchiveEvidence],
    quality_counts: dict[str, int],
    monthly_profiles: list[JamDevelopmentMonthProfile],
    metrics: list[JamFeatureDistributionMetric],
    connection: duckdb.DuckDBPyConnection,
    feature_rows_path: Path,
) -> list[JamDistributionGateResult]:
    ready_count = quality_counts["READY"]
    ready_rate = Decimal(ready_count) / Decimal(protocol.expected_calendar_row_count)
    null_ready_rows = int(
        connection.execute(
            f"""
            SELECT count(*)
            FROM read_parquet(?)
            WHERE quality_state = 'READY'
            AND ({" OR ".join(f'"{feature}" IS NULL' for feature in JAM_FEATURE_IDS)})
            """,
            [str(feature_rows_path)],
        ).fetchone()[0]
    )
    gate_values = {
        JAM_DISTRIBUTION_GATES[0]: (
            len(archive_evidence) == 24 and all(item.archive_pass for item in archive_evidence),
            f"verified_archives={len(archive_evidence)}/24",
        ),
        JAM_DISTRIBUTION_GATES[1]: (
            sum(item.calendar_row_count for item in monthly_profiles)
            == protocol.expected_calendar_row_count,
            f"calendar_rows={sum(item.calendar_row_count for item in monthly_profiles)}",
        ),
        JAM_DISTRIBUTION_GATES[2]: (
            ready_rate >= Decimal(protocol.ready_row_rate_minimum),
            f"ready_row_rate={format(ready_rate, 'f')}",
        ),
        JAM_DISTRIBUTION_GATES[3]: (
            null_ready_rows == 0 and all(item.ready_value_count == ready_count for item in metrics),
            f"ready_rows_with_null_feature={null_ready_rows}",
        ),
        JAM_DISTRIBUTION_GATES[4]: (
            all(
                item.unique_value_count >= protocol.minimum_unique_values_per_feature
                for item in metrics
            ),
            f"minimum_unique_values={min(item.unique_value_count for item in metrics)}",
        ),
        JAM_DISTRIBUTION_GATES[5]: (
            all(Decimal(item.interquartile_range) > 0 for item in metrics),
            "minimum_interquartile_range="
            f"{min(Decimal(item.interquartile_range) for item in metrics)}",
        ),
        JAM_DISTRIBUTION_GATES[6]: (
            all(
                Decimal(item.ready_row_rate) >= Decimal(protocol.monthly_ready_row_rate_minimum)
                for item in monthly_profiles
            ),
            "minimum_monthly_ready_row_rate="
            f"{min(Decimal(item.ready_row_rate) for item in monthly_profiles)}",
        ),
    }
    gates = [
        JamDistributionGateResult(
            gate_id=gate_id,
            passed=gate_values[gate_id][0],
            observed=gate_values[gate_id][1],
        )
        for gate_id in JAM_DISTRIBUTION_GATES
    ]
    for gate in gates:
        print(
            f"GATE {gate.gate_id} {'PASS' if gate.passed else 'FAIL'} {gate.observed}",
            flush=True,
        )
    return gates


def build_distribution_result(
    *,
    protocol: JamSuccessorDevelopmentDistributionProtocol,
    feature_specification,
    generated_at: datetime,
    archive_evidence: list[JamDevelopmentArchiveEvidence],
    quarantine: list[dict[str, int | str]],
    temp_root: Path,
    feature_rows_path: Path,
    feature_rows_hash: str,
    feature_rows_bytes: int,
    feature_rows_schema_hash: str,
) -> JamSuccessorDevelopmentDistributionResult:
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("SET threads = 1")
        quality_counts, monthly_profiles, primitive_count, ready_count = profile_quality(
            connection=connection,
            feature_rows_path=feature_rows_path,
            primitive_glob=temp_root / "primitives" / "*.parquet",
            quarantine=quarantine,
        )
        metrics = profile_features(
            connection=connection,
            feature_rows_path=feature_rows_path,
            calendar_row_count=protocol.expected_calendar_row_count,
        )
        tails = profile_tails(
            connection=connection,
            feature_rows_path=feature_rows_path,
            metrics=metrics,
        )
        correlations = profile_correlations(
            connection=connection,
            feature_rows_path=feature_rows_path,
        )
        gates = evaluate_gates(
            protocol=protocol,
            archive_evidence=archive_evidence,
            quality_counts=quality_counts,
            monthly_profiles=monthly_profiles,
            metrics=metrics,
            connection=connection,
            feature_rows_path=feature_rows_path,
        )
    finally:
        connection.close()
    result = build_jam_successor_distribution_result(
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        feature_specification_evidence_hash=(feature_specification.specification_evidence_hash),
        archive_target_manifest_hash=protocol.archive_target_manifest_hash,
        development_quarantine_manifest_hash=(protocol.development_quarantine_manifest_hash),
        archive_evidence=archive_evidence,
        feature_rows_file_sha256=feature_rows_hash,
        feature_rows_bytes=feature_rows_bytes,
        feature_rows_schema_hash=feature_rows_schema_hash,
        primitive_minute_count=primitive_count,
        development_quarantine_minute_count=len(quarantine),
        ready_row_count=ready_count,
        ready_row_rate=_decimal_ratio(
            ready_count,
            protocol.expected_calendar_row_count,
        ),
        quality_state_counts=quality_counts,
        monthly_profiles=monthly_profiles,
        feature_distributions=metrics,
        tail_concentrations=tails,
        pairwise_correlations=correlations,
        gates=gates,
        limitations=[
            *protocol.limitations,
            (
                "The result describes feature structure only and supplies no "
                "evidence of predictive power or profitability."
            ),
            (
                "Pairwise Pearson correlation measures linear dependence only "
                "and does not authorize feature removal."
            ),
            ("Development tail concentration is descriptive and cannot define an event cutoff."),
            (
                "DuckDB evaluates division through binary floating-point before "
                "the frozen eighteen-decimal output cast; synthetic conformance "
                "requires absolute error below one-billionth or relative error "
                "below one-trillionth against the Decimal reference."
            ),
        ],
    )
    if not audit_jam_successor_distribution_result(result):
        raise ValueError("Jam distribution result failed internal audit")
    return result


def run_distribution(args) -> JamSuccessorDevelopmentDistributionResult:
    if args.output.exists():
        raise ValueError(f"Jam distribution result already exists: {args.output}")
    if args.feature_rows.exists():
        raise ValueError(f"Jam distribution feature rows already exist: {args.feature_rows}")
    protocol, inputs, quality_result = load_run_inputs(
        protocol_path=args.protocol,
        feature_protocol_path=args.feature_protocol,
        feature_specification_path=args.feature_specification,
        feature_audit_path=args.feature_audit,
        full_protocol_path=args.full_protocol,
        full_result_path=args.full_result,
        full_audit_path=args.full_audit,
        quality_result_path=args.quality_result,
    )
    temp_root = _validated_temp_root(args.temp_root)
    quarantine = development_quarantine(quality_result)
    archive_evidence = []
    try:
        for target in protocol.archive_targets:
            archive_evidence.append(
                build_minute_primitive(
                    target=target,
                    evidence_root=args.evidence_root,
                    temp_root=temp_root,
                )
            )
        feature_hash, feature_bytes, schema_hash = build_feature_rows(
            protocol=protocol,
            quarantine=quarantine,
            temp_root=temp_root,
            output_path=args.feature_rows,
        )
        generated_at = (
            datetime.fromisoformat(args.generated_at.replace("Z", "+00:00"))
            if args.generated_at
            else datetime.now(UTC)
        )
        result = build_distribution_result(
            protocol=protocol,
            feature_specification=inputs[1],
            generated_at=generated_at,
            archive_evidence=archive_evidence,
            quarantine=quarantine,
            temp_root=temp_root,
            feature_rows_path=args.feature_rows,
            feature_rows_hash=feature_hash,
            feature_rows_bytes=feature_bytes,
            feature_rows_schema_hash=schema_hash,
        )
        _write_result(args.output, result)
    except Exception:
        if args.feature_rows.exists() and not args.output.exists():
            args.feature_rows.unlink()
        raise
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} ready={result.ready_row_count} "
        f"returns=False orders=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Calculate frozen Jam successor features and structural "
            "distributions on 2019-2020 development data only."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--feature-protocol",
        type=Path,
        default=DEFAULT_FEATURE_PROTOCOL,
    )
    parser.add_argument(
        "--feature-specification",
        type=Path,
        default=DEFAULT_FEATURE_SPECIFICATION,
    )
    parser.add_argument(
        "--feature-audit",
        type=Path,
        default=DEFAULT_FEATURE_AUDIT,
    )
    parser.add_argument(
        "--full-protocol",
        type=Path,
        default=DEFAULT_FULL_PROTOCOL,
    )
    parser.add_argument(
        "--full-result",
        type=Path,
        default=DEFAULT_FULL_RESULT,
    )
    parser.add_argument(
        "--full-audit",
        type=Path,
        default=DEFAULT_FULL_AUDIT,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    parser.add_argument(
        "--generated-at",
        help="Optional fixed UTC timestamp used only for reconstruction audits.",
    )
    return parser.parse_args()


def main() -> int:
    try:
        run_distribution(parse_args())
    except (duckdb.Error, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
