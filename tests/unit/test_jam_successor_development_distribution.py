from __future__ import annotations

import calendar
from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations
from pathlib import Path

import duckdb

from aurex.backtest_engine.jam_successor_distribution_protocol import (
    JAM_DISTRIBUTION_GATES,
    JAM_DISTRIBUTION_MONTHS,
    JAM_DISTRIBUTION_QUANTILES,
)
from aurex.backtest_engine.jam_successor_distribution_result import (
    JamDevelopmentArchiveEvidence,
    JamDevelopmentMonthProfile,
    JamDistributionGateResult,
    JamFeatureDistributionMetric,
    JamFeaturePairwiseCorrelation,
    JamFeatureTailConcentration,
    audit_jam_successor_distribution_result,
    build_jam_successor_distribution_result,
)
from aurex.backtest_engine.jam_successor_feature_specification import (
    JAM_FEATURE_IDS,
    JAM_FEATURE_QUALITY_STATES,
    JamFeatureMinute,
    compute_feature_row,
)
from scripts.run_jam_successor_development_distribution import feature_rows_query


def _minute(start_ms: int, index: int) -> JamFeatureMinute:
    price = Decimal("100") + Decimal(index) / Decimal("100")
    sell_quote = Decimal(10 + (index * 7) % 17)
    buy_quote = Decimal(20 + (index * 5) % 13)
    quote = sell_quote + buy_quote
    return JamFeatureMinute(
        open_time_ms=start_ms + index * 60_000,
        open_price=price,
        high_price=price + Decimal("0.02"),
        low_price=price - Decimal("0.02"),
        close_price=price + Decimal("0.01"),
        base_volume=quote / price,
        quote_volume=quote,
        taker_buy_quote_volume=buy_quote,
        taker_sell_quote_volume=sell_quote,
        raw_trade_count=index + 1,
    )


def _write_primitives(path: Path, minutes: list[JamFeatureMinute]) -> None:
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE primitives(
                open_time_ms BIGINT,
                close_price DECIMAL(38,18),
                low_price DECIMAL(38,18),
                base_volume DECIMAL(38,18),
                quote_volume DECIMAL(38,18),
                taker_sell_quote_volume DECIMAL(38,18)
            )
            """
        )
        connection.executemany(
            "INSERT INTO primitives VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    minute.open_time_ms,
                    minute.close_price,
                    minute.low_price,
                    minute.base_volume,
                    minute.quote_volume,
                    minute.taker_sell_quote_volume,
                )
                for minute in minutes
            ],
        )
        escaped = path.resolve().as_posix().replace("'", "''")
        connection.execute(f"COPY primitives TO '{escaped}' (FORMAT PARQUET)")
    finally:
        connection.close()


def test_duckdb_feature_windows_match_frozen_reference(tmp_path: Path) -> None:
    start_ms = 1_546_300_800_000
    minutes = [_minute(start_ms, index) for index in range(140)]
    primitive_path = tmp_path / "primitives.parquet"
    _write_primitives(primitive_path, minutes)
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("CREATE TABLE quarantine(open_time_ms BIGINT PRIMARY KEY)")
        query = feature_rows_query(
            primitives_glob=primitive_path,
            start_ms=start_ms,
            end_exclusive_ms=start_ms + len(minutes) * 60_000,
        )
        row = connection.execute(
            f"""
            SELECT quality_state, {", ".join(JAM_FEATURE_IDS)}
            FROM ({query})
            WHERE open_time_ms = ?
            """,
            [minutes[-1].open_time_ms],
        ).fetchone()
    finally:
        connection.close()
    expected = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=minutes[-1].open_time_ms,
        partition_start_ms=start_ms,
    )
    assert row[0] == expected.quality_state == "READY"
    observed = {feature: row[index + 1] for index, feature in enumerate(JAM_FEATURE_IDS)}
    for feature in JAM_FEATURE_IDS:
        reference = expected.feature_values[feature]
        tolerance = max(
            Decimal("0.000000001"),
            abs(reference) * Decimal("0.000000000001"),
        )
        assert abs(observed[feature] - reference) <= tolerance


def test_duckdb_feature_state_precedence(tmp_path: Path) -> None:
    start_ms = 1_546_300_800_000
    minutes = [_minute(start_ms, index) for index in range(140)]
    primitive_path = tmp_path / "primitives.parquet"
    _write_primitives(primitive_path, minutes)
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("CREATE TABLE quarantine(open_time_ms BIGINT PRIMARY KEY)")
        connection.execute(
            "INSERT INTO quarantine VALUES (?)",
            [minutes[10].open_time_ms],
        )
        query = feature_rows_query(
            primitives_glob=primitive_path,
            start_ms=start_ms,
            end_exclusive_ms=start_ms + len(minutes) * 60_000,
        )
        states = dict(
            connection.execute(
                f"""
                SELECT open_time_ms, quality_state
                FROM ({query})
                WHERE open_time_ms IN (?, ?, ?)
                ORDER BY open_time_ms
                """,
                [
                    minutes[4].open_time_ms,
                    minutes[10].open_time_ms,
                    minutes[-1].open_time_ms,
                ],
            ).fetchall()
        )
    finally:
        connection.close()
    assert states[minutes[4].open_time_ms] == "PARTITION_RESET_WARMUP"
    assert states[minutes[10].open_time_ms] == "SOURCE_QUARANTINE"
    assert states[minutes[-1].open_time_ms] == "POST_DEFECT_WARMUP"


def test_distribution_result_builder_hashes_complete_payload() -> None:
    hash_value = "a" * 64
    month_counts = {
        month: calendar.monthrange(*(int(value) for value in month.split("-")))[1] * 1_440
        for month in JAM_DISTRIBUTION_MONTHS
    }
    quality_counts = {
        state: (1_052_640 if state == "READY" else 0) for state in JAM_FEATURE_QUALITY_STATES
    }
    archives = [
        JamDevelopmentArchiveEvidence(
            month=month,
            archive_path=f"data/{month}.zip",
            archive_sha256=hash_value,
            source_row_count=count,
            primitive_minute_count=count,
            extracted_member_bytes=count,
            parquet_bytes=count,
        )
        for month, count in month_counts.items()
    ]
    profiles = [
        JamDevelopmentMonthProfile(
            month=month,
            calendar_row_count=count,
            primitive_minute_count=count,
            quarantine_minute_count=0,
            ready_row_count=count,
            ready_row_rate="1",
            quality_state_counts={
                state: (count if state == "READY" else 0) for state in JAM_FEATURE_QUALITY_STATES
            },
        )
        for month, count in month_counts.items()
    ]
    quantiles = {
        key: value
        for key, value in zip(
            JAM_DISTRIBUTION_QUANTILES,
            ("0", "0.01", "0.05", "0.25", "0.5", "0.75", "0.95", "0.99", "1"),
            strict=True,
        )
    }
    metrics = [
        JamFeatureDistributionMetric(
            feature_id=feature,
            calendar_row_count=1_052_640,
            ready_value_count=1_052_640,
            null_value_count=0,
            unique_value_count=1_000,
            minimum="0",
            maximum="1",
            mean="0.5",
            population_standard_deviation="0.2",
            quantiles=quantiles,
            interquartile_range="0.5",
            negative_value_count=0,
            zero_value_count=1,
            positive_value_count=1_052_639,
        )
        for feature in JAM_FEATURE_IDS
    ]
    tails = [
        JamFeatureTailConcentration(
            feature_id=feature,
            lower_threshold="0.01",
            upper_threshold="0.99",
            lower_tail_count=100,
            upper_tail_count=100,
            largest_lower_tail_month=JAM_DISTRIBUTION_MONTHS[0],
            largest_lower_tail_month_share="0.1",
            largest_upper_tail_month=JAM_DISTRIBUTION_MONTHS[0],
            largest_upper_tail_month_share="0.1",
        )
        for feature in JAM_FEATURE_IDS
    ]
    correlations = [
        JamFeaturePairwiseCorrelation(
            left_feature_id=left,
            right_feature_id=right,
            pearson_correlation="0",
        )
        for left, right in combinations(JAM_FEATURE_IDS, 2)
    ]
    gates = [
        JamDistributionGateResult(
            gate_id=gate,
            passed=True,
            observed="synthetic pass",
        )
        for gate in JAM_DISTRIBUTION_GATES
    ]
    result = build_jam_successor_distribution_result(
        generated_at=datetime(2026, 8, 4, tzinfo=UTC),
        protocol_evidence_hash=hash_value,
        runner_contract_hash=hash_value,
        feature_specification_evidence_hash=hash_value,
        archive_target_manifest_hash=hash_value,
        development_quarantine_manifest_hash=hash_value,
        archive_evidence=archives,
        feature_rows_file_sha256=hash_value,
        feature_rows_bytes=1,
        feature_rows_schema_hash=hash_value,
        primitive_minute_count=1_052_640,
        development_quarantine_minute_count=0,
        ready_row_count=1_052_640,
        ready_row_rate="1",
        quality_state_counts=quality_counts,
        monthly_profiles=profiles,
        feature_distributions=metrics,
        tail_concentrations=tails,
        pairwise_correlations=correlations,
        gates=gates,
        limitations=[f"limitation-{index}" for index in range(16)],
    )
    assert audit_jam_successor_distribution_result(result)
    assert result.result_evidence_hash != hash_value
