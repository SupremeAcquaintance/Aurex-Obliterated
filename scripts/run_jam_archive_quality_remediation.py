from __future__ import annotations

import argparse
import csv
import hashlib
import io
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from itertools import chain
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_full_acquisition import (  # noqa: E402
    JAM_FULL_ACQUISITION_FAIL_DECISION,
    JAM_FULL_KLINES_HEADER,
    JAM_FULL_MONTHS,
    JamFullAcquisitionAudit,
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    JamFullAcquisitionTarget,
    month_bounds_ms,
)
from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JAM_QUALITY_DIMENSIONS,
    JAM_QUALITY_MAXIMUM_ISSUE_RECORDS,
    JamArchiveQualityProtocol,
    JamArchiveQualityResult,
    JamCrossFamilyMismatch,
    JamDuplicateMemberEvidence,
    JamKlineGapInterval,
    JamKlineRowDefect,
    JamMinuteValues,
    audit_jam_archive_quality_protocol,
    audit_jam_archive_quality_result,
    build_jam_archive_quality_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_jam_archive_quality_remediation_protocol import (  # noqa: E402
    authoritative_protocol,
    load_parent_inputs,
)
from scripts.run_jam_archive_full_acquisition import (  # noqa: E402
    MinuteAggregate,
    _normalized_header,
    _parse_decimal,
    _validate_zip_member,
    file_sha256,
    inspect_klines,
    reconcile_month,
    target_archive_path,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/jam_archive_quality_remediation_protocol_v1.json"
)
DEFAULT_PARENT_PROTOCOL = Path(
    "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
)
DEFAULT_PARENT_RESULT = Path(
    "data/evidence/jam_archive_full_acquisition_result_v1.json"
)
DEFAULT_PARENT_AUDIT = Path(
    "data/evidence/jam_archive_full_acquisition_audit_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_TEMP_ROOT = Path(".tmp/jam_archive_quality_remediation")


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
                for path in paths
            }
        }
    )


def runner_contract_hash() -> str:
    files_hash = source_contract_hash(
        [
            PROJECT_ROOT / "pyproject.toml",
            PROJECT_ROOT
            / "scripts"
            / "run_jam_archive_quality_remediation.py",
            PROJECT_ROOT
            / "scripts"
            / "run_jam_archive_full_acquisition.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_quality_remediation.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_full_acquisition.py",
        ]
    )
    return universe_evidence_hash(
        {
            "source_contract_hash": files_hash,
            "processing_engine": "duckdb",
            "processing_engine_version": duckdb.__version__,
        }
    )


def load_inputs(
    *,
    protocol_path: Path,
    parent_protocol_path: Path,
    parent_result_path: Path,
    parent_audit_path: Path,
) -> tuple[
    JamArchiveQualityProtocol,
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    JamFullAcquisitionAudit,
]:
    parent_protocol, parent_result, parent_audit = load_parent_inputs(
        protocol_path=parent_protocol_path,
        result_path=parent_result_path,
        audit_path=parent_audit_path,
    )
    protocol = JamArchiveQualityProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected_protocol = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        parent_protocol_path=parent_protocol_path,
        parent_result_path=parent_result_path,
        parent_audit_path=parent_audit_path,
    )
    if (
        protocol != expected_protocol
        or not audit_jam_archive_quality_protocol(protocol)
        or protocol.parent_protocol_evidence_hash
        != parent_protocol.protocol_evidence_hash
        or protocol.parent_result_evidence_hash
        != parent_result.result_evidence_hash
        or protocol.parent_audit_evidence_hash
        != parent_audit.audit_evidence_hash
        or protocol.raw_manifest_hash != parent_audit.raw_manifest_hash
        or parent_result.decision != JAM_FULL_ACQUISITION_FAIL_DECISION
        or protocol.network_access_permitted
        or protocol.feature_calculation_permitted
        or protocol.parameter_definition_permitted
        or protocol.threshold_definition_permitted
        or protocol.return_calculation_permitted
        or protocol.strategy_execution_permitted
        or protocol.candidate_creation_permitted
        or protocol.paper_eligibility_permitted
        or protocol.testnet_strategy_orders_permitted
        or protocol.production_permitted
        or protocol.live_permitted
    ):
        raise ValueError("Jam quality protocol or parent lineage changed")
    return protocol, parent_protocol, parent_result, parent_audit


def _target(
    parent_protocol: JamFullAcquisitionProtocol,
    *,
    family: str,
    month: str,
) -> JamFullAcquisitionTarget:
    matches = [
        target
        for target in parent_protocol.targets
        if target.family == family and target.month == month
    ]
    if len(matches) != 1:
        raise ValueError(f"Jam quality target matrix changed: {(family, month)}")
    return matches[0]


def _rows(
    *,
    archive: zipfile.ZipFile,
    target: JamFullAcquisitionTarget,
    parent_protocol: JamFullAcquisitionProtocol,
    expected_header: tuple[str, ...],
):
    member, zip_reasons, _, _ = _validate_zip_member(
        archive=archive,
        target=target,
        protocol=parent_protocol,
    )
    with archive.open(member) as binary:
        reader = csv.reader(
            io.TextIOWrapper(binary, encoding="utf-8", newline="")
        )
        try:
            first_row = next(reader)
        except StopIteration as exc:
            raise ValueError("Jam quality CSV is empty") from exc
        if len(first_row) != len(expected_header):
            raise ValueError("Jam quality CSV column count changed")
        try:
            int(first_row[0])
        except ValueError:
            if _normalized_header(first_row) != expected_header:
                raise ValueError("Jam quality CSV header changed") from None
            yield from reader
        else:
            yield from chain((first_row,), reader)
    if zip_reasons:
        raise ValueError(f"Jam quality unexpected kline ZIP issue: {target.key}")


def _row_defect_reasons(
    *,
    open_time: int,
    close_time: int,
    open_price: Decimal,
    high_price: Decimal,
    low_price: Decimal,
    close_price: Decimal,
    base_volume: Decimal,
    quote_volume: Decimal,
    taker_base: Decimal,
    taker_quote: Decimal,
    raw_trade_count: int,
    tolerance: Decimal,
) -> list[str]:
    reasons = []
    if close_time != open_time + 59_999:
        reasons.append("CLOSE_TIME_MISMATCH")
    if min(open_price, high_price, low_price, close_price) <= 0:
        reasons.append("NONPOSITIVE_PRICE")
    if high_price < max(open_price, low_price, close_price):
        reasons.append("HIGH_BOUND_FAILED")
    if low_price > min(open_price, high_price, close_price):
        reasons.append("LOW_BOUND_FAILED")
    if min(base_volume, quote_volume, taker_base, taker_quote) < 0:
        reasons.append("NEGATIVE_VOLUME")
    if taker_base - base_volume > tolerance:
        reasons.append("TAKER_BASE_EXCEEDS_BASE")
    if taker_quote - quote_volume > tolerance:
        reasons.append("TAKER_QUOTE_EXCEEDS_QUOTE")
    if raw_trade_count < 0:
        reasons.append("NEGATIVE_TRADE_COUNT")
    return reasons


def _gap_intervals(
    *,
    month: str,
    start_ms: int,
    expected_minutes: int,
    observed_minutes: set[int],
) -> list[JamKlineGapInterval]:
    missing = [
        minute
        for minute in range(expected_minutes)
        if minute not in observed_minutes
    ]
    if not missing:
        return []
    intervals = []
    interval_start = missing[0]
    previous = missing[0]
    for minute in missing[1:] + [None]:
        if minute is not None and minute == previous + 1:
            previous = minute
            continue
        intervals.append(
            JamKlineGapInterval(
                month=month,
                start_open_time_ms=start_ms + interval_start * 60_000,
                end_open_time_ms=start_ms + previous * 60_000,
                missing_minute_count=previous - interval_start + 1,
                preceding_open_time_ms=(
                    None
                    if interval_start == 0
                    else start_ms + (interval_start - 1) * 60_000
                ),
                following_open_time_ms=(
                    None
                    if previous == expected_minutes - 1
                    else start_ms + (previous + 1) * 60_000
                ),
                aggregate_covered_minute_count=0,
            )
        )
        if minute is not None:
            interval_start = minute
            previous = minute
    return intervals


def reconstruct_kline_issues(
    *,
    parent_protocol: JamFullAcquisitionProtocol,
    parent_result: JamFullAcquisitionResult,
    evidence_root: Path,
) -> tuple[list[JamKlineGapInterval], list[JamKlineRowDefect]]:
    parent_months = {month.month: month for month in parent_result.months}
    tolerance = Decimal(parent_protocol.decimal_reconciliation_tolerance)
    all_gaps = []
    all_defects = []
    for month in JAM_FULL_MONTHS:
        target = _target(parent_protocol, family="klines_1m", month=month)
        archive_path = target_archive_path(evidence_root, target)
        if file_sha256(archive_path) != target.published_archive_sha256:
            raise ValueError(f"Jam quality kline archive hash changed: {month}")
        start_ms, end_ms, expected_minutes = month_bounds_ms(month)
        observed_minutes: set[int] = set()
        defects = []
        row_count = 0
        with zipfile.ZipFile(archive_path) as archive:
            for row in _rows(
                archive=archive,
                target=target,
                parent_protocol=parent_protocol,
                expected_header=JAM_FULL_KLINES_HEADER,
            ):
                if len(row) != 12:
                    raise ValueError("Jam quality kline column count changed")
                try:
                    open_time = int(row[0])
                    close_time = int(row[6])
                    raw_trade_count = int(row[8])
                except ValueError as exc:
                    raise ValueError("Jam quality kline integer invalid") from exc
                open_price = _parse_decimal(row[1], "quality kline open")
                high_price = _parse_decimal(row[2], "quality kline high")
                low_price = _parse_decimal(row[3], "quality kline low")
                close_price = _parse_decimal(row[4], "quality kline close")
                base_volume = _parse_decimal(row[5], "quality kline volume")
                quote_volume = _parse_decimal(
                    row[7],
                    "quality kline quote volume",
                )
                taker_base = _parse_decimal(
                    row[9],
                    "quality kline taker base",
                )
                taker_quote = _parse_decimal(
                    row[10],
                    "quality kline taker quote",
                )
                _parse_decimal(row[11], "quality kline ignore")
                if (
                    not start_ms <= open_time < end_ms
                    or (open_time - start_ms) % 60_000
                ):
                    raise ValueError(
                        f"Jam quality kline timestamp changed: {month}"
                    )
                minute = (open_time - start_ms) // 60_000
                if minute in observed_minutes:
                    raise ValueError(
                        f"Jam quality kline primary key duplicated: {month}"
                    )
                observed_minutes.add(minute)
                reasons = _row_defect_reasons(
                    open_time=open_time,
                    close_time=close_time,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    base_volume=base_volume,
                    quote_volume=quote_volume,
                    taker_base=taker_base,
                    taker_quote=taker_quote,
                    raw_trade_count=raw_trade_count,
                    tolerance=tolerance,
                )
                if reasons:
                    defects.append(
                        JamKlineRowDefect(
                            month=month,
                            open_time_ms=open_time,
                            reason_codes=reasons,
                            observed_close_time_ms=close_time,
                            expected_close_time_ms=open_time + 59_999,
                        )
                    )
                row_count += 1
        gaps = _gap_intervals(
            month=month,
            start_ms=start_ms,
            expected_minutes=expected_minutes,
            observed_minutes=observed_minutes,
        )
        parent = parent_months[month].klines_1m
        missing_count = sum(item.missing_minute_count for item in gaps)
        expected_reasons = []
        if missing_count:
            expected_reasons.append("KLINE_MONTH_CONTINUITY_FAILED")
        if defects:
            expected_reasons.append("KLINE_ROW_INVARIANT_FAILED")
        if (
            row_count != parent.row_count
            or len(observed_minutes) != parent.unique_minute_count
            or missing_count != expected_minutes - parent.unique_minute_count
            or parent.gap_count != missing_count + len(defects)
            or sorted(expected_reasons) != parent.reason_codes
        ):
            raise ValueError(
                f"Jam quality kline reconstruction changed: {month}"
            )
        all_gaps.extend(gaps)
        all_defects.extend(defects)
        print(
            f"KLINE {month} gaps={missing_count} intervals={len(gaps)} "
            f"row_defects={len(defects)}",
            flush=True,
        )
    return all_gaps, all_defects


def reconstruct_duplicate_member(
    *,
    parent_protocol: JamFullAcquisitionProtocol,
    evidence_root: Path,
) -> JamDuplicateMemberEvidence:
    target = _target(parent_protocol, family="aggTrades", month="2021-12")
    archive_path = target_archive_path(evidence_root, target)
    archive_hash = file_sha256(archive_path)
    if archive_hash != target.published_archive_sha256:
        raise ValueError("Jam quality duplicate archive hash changed")
    with zipfile.ZipFile(archive_path) as archive:
        files = [member for member in archive.infolist() if not member.is_dir()]
        canonical = [
            member
            for member in files
            if member.filename == target.expected_csv_member
        ]
        duplicates = [
            member
            for member in files
            if member.filename != target.expected_csv_member
        ]
        if len(files) != 2 or len(canonical) != 1 or len(duplicates) != 1:
            raise ValueError("Jam quality duplicate member matrix changed")

        def member_hash(member: zipfile.ZipInfo) -> str:
            digest = hashlib.sha256()
            with archive.open(member) as handle:
                for chunk in iter(lambda: handle.read(1_048_576), b""):
                    digest.update(chunk)
            return digest.hexdigest()

        canonical_hash = member_hash(canonical[0])
        duplicate_hash = member_hash(duplicates[0])
        result = JamDuplicateMemberEvidence(
            archive_path=archive_path.relative_to(evidence_root).as_posix(),
            archive_sha256=archive_hash,
            duplicate_member_name=duplicates[0].filename,
            canonical_member_bytes=canonical[0].file_size,
            duplicate_member_bytes=duplicates[0].file_size,
            canonical_member_sha256=canonical_hash,
            duplicate_member_sha256=duplicate_hash,
            byte_identical=(
                canonical[0].file_size == duplicates[0].file_size
                and canonical_hash == duplicate_hash
            ),
            policy_pass=(
                canonical[0].file_size == duplicates[0].file_size
                and canonical_hash == duplicate_hash
            ),
        )
    print(
        f"DUPLICATE 2021-12 identical={result.byte_identical} "
        f"canonical={result.canonical_member_sha256}",
        flush=True,
    )
    return result


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _minute_values(value) -> JamMinuteValues:
    return JamMinuteValues(
        open_price=_decimal(value.open_price),
        high_price=_decimal(value.high_price),
        low_price=_decimal(value.low_price),
        close_price=_decimal(value.close_price),
        base_volume=_decimal(value.base_volume),
        quote_volume=_decimal(value.quote_volume),
        raw_trade_count=value.raw_trade_count,
        taker_buy_base_volume=_decimal(value.taker_buy_base_volume),
        taker_buy_quote_volume=_decimal(value.taker_buy_quote_volume),
    )


def _validated_temp_root(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError("Jam quality temp root must remain under .tmp")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def aggregate_minutes_duckdb(
    *,
    target: JamFullAcquisitionTarget,
    archive_path: Path,
    parent_row_count: int,
    parent_header_present: bool,
    temp_root: Path,
) -> dict[int, MinuteAggregate]:
    if file_sha256(archive_path) != target.published_archive_sha256:
        raise ValueError(f"Jam quality aggregate archive hash changed: {target.month}")
    temporary = temp_root / f"{target.month}-aggTrades.csv"
    if temporary.exists():
        temporary.unlink()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            canonical = [
                member
                for member in archive.infolist()
                if not member.is_dir()
                and member.filename == target.expected_csv_member
            ]
            if len(canonical) != 1:
                raise ValueError(
                    f"Jam quality canonical aggregate member changed: {target.month}"
                )
            with archive.open(canonical[0]) as source, temporary.open("xb") as output:
                shutil.copyfileobj(source, output, length=8 * 1_048_576)
            if temporary.stat().st_size != canonical[0].file_size:
                raise ValueError(
                    f"Jam quality extracted aggregate size changed: {target.month}"
                )

        header = "true" if parent_header_present else "false"
        query = f"""
            WITH source AS (
                SELECT
                    aggregate_trade_id,
                    price,
                    quantity,
                    first_trade_id,
                    last_trade_id,
                    transact_time,
                    is_buyer_maker
                FROM read_csv(
                    ?,
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
            ),
            minute_rows AS (
                SELECT
                    floor((transact_time - ?) / 60000)::BIGINT AS minute,
                    aggregate_trade_id,
                    transact_time,
                    price,
                    quantity,
                    first_trade_id,
                    last_trade_id,
                    is_buyer_maker
                FROM source
            )
            SELECT
                minute,
                first(price ORDER BY transact_time, aggregate_trade_id) AS open_price,
                max(price) AS high_price,
                min(price) AS low_price,
                last(price ORDER BY transact_time, aggregate_trade_id) AS close_price,
                sum(quantity) AS base_volume,
                sum(price * quantity) AS quote_volume,
                sum(last_trade_id - first_trade_id + 1)::HUGEINT AS raw_trade_count,
                sum(
                    CASE
                        WHEN NOT is_buyer_maker THEN quantity
                        ELSE 0::DECIMAL(38,8)
                    END
                ) AS taker_buy_base_volume,
                sum(
                    CASE
                        WHEN NOT is_buyer_maker THEN price * quantity
                        ELSE 0::DECIMAL(38,16)
                    END
                ) AS taker_buy_quote_volume,
                sum(count(*)) OVER ()::HUGEINT AS archive_row_count
            FROM minute_rows
            GROUP BY minute
            ORDER BY minute
        """
        start_ms = month_bounds_ms(target.month)[0]
        connection = duckdb.connect(database=":memory:")
        try:
            connection.execute("SET threads = 4")
            rows = connection.execute(
                query,
                [str(temporary), start_ms],
            ).fetchall()
        finally:
            connection.close()
        if not rows or int(rows[0][10]) != parent_row_count:
            raise ValueError(
                f"Jam quality aggregate row count changed: {target.month}"
            )
        result = {}
        for row in rows:
            minute = int(row[0])
            if minute in result:
                raise ValueError(
                    f"Jam quality aggregate minute duplicated: {target.month}"
                )
            result[minute] = MinuteAggregate(
                open_price=Decimal(row[1]),
                high_price=Decimal(row[2]),
                low_price=Decimal(row[3]),
                close_price=Decimal(row[4]),
                base_volume=Decimal(row[5]),
                quote_volume=Decimal(row[6]),
                raw_trade_count=int(row[7]),
                taker_buy_base_volume=Decimal(row[8]),
                taker_buy_quote_volume=Decimal(row[9]),
            )
        return result
    finally:
        if temporary.exists():
            temporary.unlink()


def _mismatch_dimensions(*, aggregate, kline, tolerance: Decimal) -> list[str]:
    dimensions = []
    if aggregate is None:
        if kline.raw_trade_count:
            dimensions.append("RAW_TRADE_COUNT")
        if abs(kline.base_volume) > tolerance:
            dimensions.append("BASE_VOLUME")
        if abs(kline.quote_volume) > tolerance:
            dimensions.append("QUOTE_VOLUME")
        if abs(kline.taker_buy_base_volume) > tolerance:
            dimensions.append("TAKER_BUY_BASE_VOLUME")
        if abs(kline.taker_buy_quote_volume) > tolerance:
            dimensions.append("TAKER_BUY_QUOTE_VOLUME")
        return dimensions
    if aggregate.raw_trade_count != kline.raw_trade_count:
        dimensions.append("RAW_TRADE_COUNT")
    if (
        aggregate.open_price != kline.open_price
        or aggregate.high_price != kline.high_price
        or aggregate.low_price != kline.low_price
        or aggregate.close_price != kline.close_price
    ):
        dimensions.append("OHLC")
    if abs(aggregate.base_volume - kline.base_volume) > tolerance:
        dimensions.append("BASE_VOLUME")
    if abs(aggregate.quote_volume - kline.quote_volume) > tolerance:
        dimensions.append("QUOTE_VOLUME")
    if (
        abs(
            aggregate.taker_buy_base_volume
            - kline.taker_buy_base_volume
        )
        > tolerance
    ):
        dimensions.append("TAKER_BUY_BASE_VOLUME")
    if (
        abs(
            aggregate.taker_buy_quote_volume
            - kline.taker_buy_quote_volume
        )
        > tolerance
    ):
        dimensions.append("TAKER_BUY_QUOTE_VOLUME")
    return dimensions


def reconstruct_cross_family_mismatches(
    *,
    parent_protocol: JamFullAcquisitionProtocol,
    parent_result: JamFullAcquisitionResult,
    evidence_root: Path,
    temp_root: Path,
) -> tuple[list[JamCrossFamilyMismatch], int]:
    tolerance = Decimal(parent_protocol.decimal_reconciliation_tolerance)
    mismatch_months = [
        item
        for item in parent_result.months
        if not item.reconciliation.reconciliation_pass
    ]
    records = []
    for parent_month in mismatch_months:
        month = parent_month.month
        aggregate_target = _target(
            parent_protocol,
            family="aggTrades",
            month=month,
        )
        kline_target = _target(
            parent_protocol,
            family="klines_1m",
            month=month,
        )
        aggregates = aggregate_minutes_duckdb(
            target=aggregate_target,
            archive_path=target_archive_path(
                evidence_root,
                aggregate_target,
            ),
            parent_row_count=parent_month.aggregate_trades.row_count,
            parent_header_present=parent_month.aggregate_trades.header_present,
            temp_root=temp_root,
        )
        kline_evidence, klines = inspect_klines(
            target=kline_target,
            archive_path=target_archive_path(evidence_root, kline_target),
            evidence_root=evidence_root,
            protocol=parent_protocol,
            head_count=parent_month.klines_1m.head_request_count,
            get_count=parent_month.klines_1m.payload_get_request_count,
        )
        reconciliation = reconcile_month(
            month=month,
            aggregates=aggregates,
            klines=klines,
            protocol=parent_protocol,
        )
        if (
            kline_evidence != parent_month.klines_1m
            or reconciliation != parent_month.reconciliation
        ):
            raise ValueError(
                f"Jam quality parent reconciliation changed: {month}"
            )
        start_ms, _, expected_minutes = month_bounds_ms(month)
        month_records = []
        for minute in range(expected_minutes):
            kline = klines.get(minute)
            if kline is None:
                continue
            aggregate = aggregates.get(minute)
            dimensions = _mismatch_dimensions(
                aggregate=aggregate,
                kline=kline,
                tolerance=tolerance,
            )
            if not dimensions:
                continue
            month_records.append(
                JamCrossFamilyMismatch(
                    month=month,
                    open_time_ms=start_ms + minute * 60_000,
                    mismatch_dimensions=dimensions,
                    aggregate_values=(
                        None if aggregate is None else _minute_values(aggregate)
                    ),
                    kline_values=_minute_values(kline),
                )
            )
        expected_counts = {
            "RAW_TRADE_COUNT": (
                reconciliation.raw_trade_count_mismatch_count
            ),
            "OHLC": reconciliation.ohlc_mismatch_count,
            "BASE_VOLUME": reconciliation.base_volume_mismatch_count,
            "QUOTE_VOLUME": reconciliation.quote_volume_mismatch_count,
            "TAKER_BUY_BASE_VOLUME": (
                reconciliation.taker_buy_base_volume_mismatch_count
            ),
            "TAKER_BUY_QUOTE_VOLUME": (
                reconciliation.taker_buy_quote_volume_mismatch_count
            ),
        }
        actual_counts = {
            dimension: sum(
                dimension in item.mismatch_dimensions
                for item in month_records
            )
            for dimension in JAM_QUALITY_DIMENSIONS
        }
        if actual_counts != expected_counts:
            raise ValueError(
                f"Jam quality mismatch dimensions changed: {month}"
            )
        records.extend(month_records)
        print(
            f"RECON {month} mismatch_minutes={len(month_records)} "
            f"dimensions={sum(actual_counts.values())}",
            flush=True,
        )
    if (
        len(records) > JAM_QUALITY_MAXIMUM_ISSUE_RECORDS
        or sum(
            item.reconciliation.aggregate_trade_outside_kline_count
            for item in parent_result.months
        )
        != 0
    ):
        raise ValueError("Jam quality mismatch issue budget or coverage changed")
    return records, len(mismatch_months)


def aggregate_source_qualified(
    *,
    parent_result: JamFullAcquisitionResult,
    parent_audit: JamFullAcquisitionAudit,
    duplicate: JamDuplicateMemberEvidence,
    gaps: list[JamKlineGapInterval],
    row_defects: list[JamKlineRowDefect],
    mismatches: list[JamCrossFamilyMismatch],
) -> bool:
    aggregate_archives = [
        month.aggregate_trades for month in parent_result.months
    ]
    parent_counts = {
        "RAW_TRADE_COUNT": sum(
            item.reconciliation.raw_trade_count_mismatch_count
            for item in parent_result.months
        ),
        "OHLC": sum(
            item.reconciliation.ohlc_mismatch_count
            for item in parent_result.months
        ),
        "BASE_VOLUME": sum(
            item.reconciliation.base_volume_mismatch_count
            for item in parent_result.months
        ),
        "QUOTE_VOLUME": sum(
            item.reconciliation.quote_volume_mismatch_count
            for item in parent_result.months
        ),
        "TAKER_BUY_BASE_VOLUME": sum(
            item.reconciliation.taker_buy_base_volume_mismatch_count
            for item in parent_result.months
        ),
        "TAKER_BUY_QUOTE_VOLUME": sum(
            item.reconciliation.taker_buy_quote_volume_mismatch_count
            for item in parent_result.months
        ),
    }
    actual_counts = {
        dimension: sum(
            dimension in item.mismatch_dimensions for item in mismatches
        )
        for dimension in JAM_QUALITY_DIMENSIONS
    }
    parent_missing = sum(
        month.klines_1m.expected_minute_count
        - month.klines_1m.unique_minute_count
        for month in parent_result.months
    )
    return (
        parent_audit.raw_archive_count == 96
        and parent_audit.checksum_verified_count == 96
        and parent_audit.reconstructed_month_count == 48
        and all(item.checksum_verified for item in aggregate_archives)
        and all(item.duplicate_primary_key_count == 0 for item in aggregate_archives)
        and all(item.out_of_order_count == 0 for item in aggregate_archives)
        and all(
            "AGGREGATE_OR_RAW_TRADE_ID_GAP" not in item.reason_codes
            for item in aggregate_archives
        )
        and duplicate.policy_pass
        and parent_missing
        == sum(item.missing_minute_count for item in gaps)
        and sum(
            "KLINE_ROW_INVARIANT_FAILED" in month.klines_1m.reason_codes
            for month in parent_result.months
        )
        == len({item.month for item in row_defects})
        and actual_counts == parent_counts
        and len(gaps) + len(row_defects) + len(mismatches)
        <= JAM_QUALITY_MAXIMUM_ISSUE_RECORDS
    )


def authoritative_result(
    *,
    generated_at: datetime,
    protocol: JamArchiveQualityProtocol,
    parent_result: JamFullAcquisitionResult,
    parent_audit: JamFullAcquisitionAudit,
    duplicate: JamDuplicateMemberEvidence,
    gaps: list[JamKlineGapInterval],
    row_defects: list[JamKlineRowDefect],
    mismatches: list[JamCrossFamilyMismatch],
) -> JamArchiveQualityResult:
    qualified = aggregate_source_qualified(
        parent_result=parent_result,
        parent_audit=parent_audit,
        duplicate=duplicate,
        gaps=gaps,
        row_defects=row_defects,
        mismatches=mismatches,
    )
    return build_jam_archive_quality_result(
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        parent_result_evidence_hash=parent_result.result_evidence_hash,
        parent_audit_evidence_hash=parent_audit.audit_evidence_hash,
        duplicate_member=duplicate,
        kline_gap_intervals=gaps,
        kline_row_defects=row_defects,
        cross_family_mismatches=mismatches,
        aggregate_primary_source_qualified=qualified,
        evidence_partitions=protocol.evidence_partitions,
        contaminated_or_excluded_periods=[
            (
                "2023-01 through 2025-12 is consumed Jam research evidence and "
                "is excluded from successor qualification."
            ),
            (
                "2026-01 onward remains outside this remediation pool; existing "
                "exploratory and forward-lock boundaries remain authoritative."
            ),
        ],
        limitations=[
            (
                "This result assesses source fitness and deterministic quarantine "
                "policy only; it does not establish any market edge."
            ),
            (
                "Aggregate trades are primary because the proposed Jam mechanism "
                "requires aggressor-side flow unavailable in candles alone."
            ),
            (
                "Official one-minute klines remain a secondary quality reference "
                "and are not allowed to overwrite aggregate-trade observations."
            ),
            (
                "All missing kline minutes are observability gaps and are excluded "
                "without synthetic tradable bars or zero-flow substitution."
            ),
            (
                "All invalid kline rows and cross-family mismatch minutes are "
                "quarantined even when aggregate trades become primary."
            ),
            (
                "The canonical 2021-12 aggregate member is acceptable only if its "
                "bytes exactly match the duplicate member."
            ),
            (
                "Any future stateful feature must reset at a quarantined boundary "
                "and complete its maximum causal lookback before eligibility."
            ),
            (
                "The warm-up duration is deliberately not numeric because feature "
                "lookbacks have not been authorized or defined."
            ),
            (
                "The 2019-2020, 2021, and 2022 evidence roles are frozen before "
                "feature or outcome access."
            ),
            (
                "The 2023-2025 period remains contaminated by prior Jam work and "
                "cannot be used as clean successor evidence."
            ),
            (
                "No Pine or candle-only parity claim is created; aggressor-flow "
                "research remains backend-only."
            ),
            (
                "No feature, threshold, directional label, return, PnL, ranking, "
                "optimization, signal, order, or strategy execution was performed."
            ),
            (
                "This result grants no candidate, paper, Testnet strategy-order, "
                "production, live, capital, or profit authority."
            ),
        ],
    )


def reconstruct(
    *,
    parent_protocol: JamFullAcquisitionProtocol,
    parent_result: JamFullAcquisitionResult,
    parent_audit: JamFullAcquisitionAudit,
    evidence_root: Path,
    temp_root: Path,
) -> tuple[
    JamDuplicateMemberEvidence,
    list[JamKlineGapInterval],
    list[JamKlineRowDefect],
    list[JamCrossFamilyMismatch],
    int,
]:
    gaps, row_defects = reconstruct_kline_issues(
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        evidence_root=evidence_root,
    )
    duplicate = reconstruct_duplicate_member(
        parent_protocol=parent_protocol,
        evidence_root=evidence_root,
    )
    mismatches, mismatch_month_count = reconstruct_cross_family_mismatches(
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        evidence_root=evidence_root,
        temp_root=temp_root,
    )
    if not aggregate_source_qualified(
        parent_result=parent_result,
        parent_audit=parent_audit,
        duplicate=duplicate,
        gaps=gaps,
        row_defects=row_defects,
        mismatches=mismatches,
    ):
        print(
            "QUALIFICATION aggregate_primary=False; result will remain stopped",
            flush=True,
        )
    return duplicate, gaps, row_defects, mismatches, mismatch_month_count


def write_result(path: Path, result: JamArchiveQualityResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if JamArchiveQualityResult.model_validate_json(serialized) != result:
        raise ValueError("Jam quality result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> JamArchiveQualityResult:
    if args.output.exists():
        raise ValueError("Jam quality result exists; use --check")
    protocol, parent_protocol, parent_result, parent_audit = load_inputs(
        protocol_path=args.protocol,
        parent_protocol_path=args.parent_protocol,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    duplicate, gaps, row_defects, mismatches, _ = reconstruct(
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        evidence_root=args.evidence_root,
        temp_root=_validated_temp_root(args.temp_root),
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        duplicate=duplicate,
        gaps=gaps,
        row_defects=row_defects,
        mismatches=mismatches,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"gaps={result.kline_missing_minute_count} "
        f"row_defects={result.kline_row_defect_count} "
        f"mismatches={result.cross_family_mismatch_minute_count} "
        f"quarantined={result.quarantined_minute_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def run_check(args) -> JamArchiveQualityResult:
    protocol, parent_protocol, parent_result, parent_audit = load_inputs(
        protocol_path=args.protocol,
        parent_protocol_path=args.parent_protocol,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    result = JamArchiveQualityResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    duplicate, gaps, row_defects, mismatches, _ = reconstruct(
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        evidence_root=args.evidence_root,
        temp_root=_validated_temp_root(args.temp_root),
    )
    expected = authoritative_result(
        generated_at=result.generated_at,
        protocol=protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        duplicate=duplicate,
        gaps=gaps,
        row_defects=row_defects,
        mismatches=mismatches,
    )
    if result != expected or not audit_jam_archive_quality_result(result):
        raise ValueError("Jam quality result is not reproducible")
    print(
        "PASS "
        f"jam_quality_result={result.result_evidence_hash} "
        f"issue_manifest={result.issue_manifest_hash} "
        f"quarantine_manifest={result.quarantined_minute_manifest_hash} "
        f"returns={bool(result.return_metrics_calculated)} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or verify Jam archive quality remediation."
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--parent-protocol",
        type=Path,
        default=DEFAULT_PARENT_PROTOCOL,
    )
    parser.add_argument(
        "--parent-result",
        type=Path,
        default=DEFAULT_PARENT_RESULT,
    )
    parser.add_argument(
        "--parent-audit",
        type=Path,
        default=DEFAULT_PARENT_AUDIT,
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_check(args) if args.check else run_write(args)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
