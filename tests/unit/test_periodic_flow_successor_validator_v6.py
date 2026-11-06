from __future__ import annotations

import hashlib
import zipfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    RAW_COLUMNS,
    PeriodicFlowDevelopmentTarget,
)
from scripts.run_periodic_flow_successor_acquisition_v6 import inspect_archive_v6


def _write_raw_zip(path: Path, rows: tuple[tuple[object, ...], ...]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "id,price,qty,quote_qty,time,is_buyer_maker\n" + "".join(
        ",".join(str(value) for value in row) + "\n" for row in rows
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-trades-2023-01.csv", payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _target(digest: str) -> PeriodicFlowDevelopmentTarget:
    return PeriodicFlowDevelopmentTarget.model_construct(
        product="USD_M_PERPETUAL",
        family="trades",
        symbol="BTCUSDT",
        month="2023-01",
        partition_role="DEVELOPMENT",
        archive_url=(
            "https://data.binance.vision/data/futures/um/monthly/trades/"
            "BTCUSDT/BTCUSDT-trades-2023-01.zip"
        ),
        published_archive_sha256=digest,
        expected_member_name="BTCUSDT-trades-2023-01.csv",
        expected_columns=RAW_COLUMNS,
        expected_timestamp_unit="MILLISECONDS",
        reuse_candidate_path=None,
        reuse_candidate_file_sha256=None,
        reuse_revalidation_required=True,
        member_policy="EXACT_EXPECTED_MEMBER_ONLY",
    )


def _protocol():
    return SimpleNamespace(
        maximum_member_uncompressed_bytes_each=30_000_000_000,
        maximum_zip_expansion_ratio=100,
    )


def test_v6_preserves_gap_metrics_for_ordered_raw_stream(tmp_path: Path) -> None:
    path = tmp_path / "BTCUSDT-trades-2023-01.zip"
    digest = _write_raw_zip(
        path,
        (
            (1, "NO_PRICE", "NO_QTY", "NO_QUOTE", 1_672_531_200_000, "true"),
            (3, "NO_PRICE", "NO_QTY", "NO_QUOTE", 1_672_531_260_000, "false"),
        ),
    )

    evidence = inspect_archive_v6(
        target=_target(digest),
        archive_path=path,
        evidence_root=tmp_path,
        protocol=_protocol(),
        source_mode="REUSED_LOCAL",
        get_attempt_count=0,
    ).evidence

    assert evidence.primary_id_non_increasing_count == 0
    assert evidence.primary_id_forward_gap_count == 1
    assert evidence.primary_id_skipped_count == 1
    assert evidence.primary_id_skipped_fraction == Decimal(1) / Decimal(3)
    assert evidence.maximum_single_primary_id_skip_count == 1


def test_v6_excludes_interleaved_stream_without_inventing_gap_fraction(
    tmp_path: Path,
) -> None:
    path = tmp_path / "BTCUSDT-trades-2023-01.zip"
    digest = _write_raw_zip(
        path,
        (
            (1, "NO_PRICE", "NO_QTY", "NO_QUOTE", 1_672_531_200_000, "true"),
            (100, "NO_PRICE", "NO_QTY", "NO_QUOTE", 1_672_531_320_000, "false"),
            (2, "NO_PRICE", "NO_QTY", "NO_QUOTE", 1_672_531_260_000, "true"),
            (101, "NO_PRICE", "NO_QTY", "NO_QUOTE", 1_672_531_380_000, "false"),
        ),
    )

    evidence = inspect_archive_v6(
        target=_target(digest),
        archive_path=path,
        evidence_root=tmp_path,
        protocol=_protocol(),
        source_mode="REUSED_LOCAL",
        get_attempt_count=0,
    ).evidence

    assert evidence.primary_id_non_increasing_count == 1
    assert evidence.timestamp_regression_count == 1
    assert evidence.primary_id_forward_gap_count == 0
    assert evidence.primary_id_skipped_count == 0
    assert evidence.primary_id_skipped_fraction == 0
    assert evidence.maximum_single_primary_id_skip_count == 0
    assert evidence.archive_pass is False
    assert "PRIMARY_ID_NOT_STRICTLY_INCREASING" in evidence.reason_codes
    assert "TIMESTAMP_REGRESSION" in evidence.reason_codes
    assert evidence.excluded_numeric_fields == (
        "price",
        "quantity",
        "quote_quantity",
    )
