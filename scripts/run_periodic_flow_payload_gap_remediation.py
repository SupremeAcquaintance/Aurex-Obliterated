from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_payload_gap_remediation import (  # noqa: E402
    PeriodicFlowGapRecord,
    PeriodicFlowGapRemediationProtocol,
    PeriodicFlowGapRemediationResult,
    audit_gap_remediation_protocol,
    audit_gap_remediation_result,
    build_gap_remediation_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_result_v1.json"
)
MONTH_START_MS = 1_577_836_800_000
MONTH_END_MS = 1_580_515_200_000
EXPECTED_MEMBER = "BTCUSDT-aggTrades-2020-01.csv"
EXPECTED_HEADER = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "buyer_was_maker",
)
HEADER_ALIASES = {
    "agg_trade_id": "aggregate_trade_id",
    "transact_time": "timestamp",
    "is_buyer_maker": "buyer_was_maker",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "run_periodic_flow_payload_gap_remediation.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "periodic_flow_payload_gap_remediation.py",
    )
    return universe_evidence_hash(
        {
            path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
            for path in paths
        }
    )


def load_protocol(path: Path) -> PeriodicFlowGapRemediationProtocol:
    protocol = PeriodicFlowGapRemediationProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_gap_remediation_protocol(protocol):
        raise ValueError("Q1 gap remediation protocol hash failed")
    return protocol


def _normalized_header(row: list[str]) -> tuple[str, ...]:
    return tuple(
        HEADER_ALIASES.get(value.strip().lower(), value.strip().lower())
        for value in row
    )


def _gap_buckets(gaps: tuple[PeriodicFlowGapRecord, ...]) -> dict[str, int]:
    buckets = {
        "1": 0,
        "2_TO_10": 0,
        "11_TO_100": 0,
        "101_TO_1000": 0,
        "OVER_1000": 0,
    }
    for gap in gaps:
        size = gap.skipped_raw_trade_id_count
        if size == 1:
            buckets["1"] += 1
        elif size <= 10:
            buckets["2_TO_10"] += 1
        elif size <= 100:
            buckets["11_TO_100"] += 1
        elif size <= 1000:
            buckets["101_TO_1000"] += 1
        else:
            buckets["OVER_1000"] += 1
    return buckets


def scan_archive(
    protocol: PeriodicFlowGapRemediationProtocol,
) -> dict:
    archive_path = Path(protocol.target_archive_path)
    archive_hash = file_sha256(archive_path)
    if archive_hash != protocol.target_archive_sha256:
        raise ValueError("Q1 gap remediation archive checksum changed")

    row_count = 0
    first_aggregate_id = 0
    last_aggregate_id = 0
    first_raw_id = 0
    last_raw_id = 0
    first_timestamp = 0
    last_timestamp = 0
    previous_aggregate_id: int | None = None
    previous_last_raw_id: int | None = None
    previous_timestamp: int | None = None
    aggregate_gap_count = 0
    aggregate_non_increasing_count = 0
    raw_span_invalid_count = 0
    raw_overlap_count = 0
    timestamp_regression_count = 0
    minute_indexes: set[int] = set()
    gaps: list[PeriodicFlowGapRecord] = []

    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if (
            len(members) != 1
            or members[0].filename != EXPECTED_MEMBER
            or members[0].is_dir()
            or members[0].flag_bits & 0x1
        ):
            raise ValueError("Q1 gap remediation ZIP structure changed")
        with archive.open(members[0], "r") as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                for row in csv.reader(text):
                    if not row:
                        raise ValueError("Q1 gap remediation found empty CSV row")
                    if row_count == 0:
                        try:
                            int(row[0])
                        except ValueError as exc:
                            if _normalized_header(row) != EXPECTED_HEADER:
                                raise ValueError(
                                    "Q1 gap remediation header changed"
                                ) from exc
                            continue
                    if len(row) != 7:
                        raise ValueError("Q1 gap remediation column count changed")
                    if not row[1].strip() or not row[2].strip():
                        raise ValueError("Q1 excluded numeric field is empty")
                    aggregate_id = int(row[0])
                    current_first_raw_id = int(row[3])
                    current_last_raw_id = int(row[4])
                    timestamp = int(row[5])
                    if not MONTH_START_MS <= timestamp < MONTH_END_MS:
                        raise ValueError("Q1 gap remediation timestamp left month")
                    if current_first_raw_id > current_last_raw_id:
                        raw_span_invalid_count += 1
                    if previous_aggregate_id is not None:
                        if aggregate_id <= previous_aggregate_id:
                            aggregate_non_increasing_count += 1
                        if aggregate_id != previous_aggregate_id + 1:
                            aggregate_gap_count += 1
                    if previous_last_raw_id is not None:
                        if current_first_raw_id <= previous_last_raw_id:
                            raw_overlap_count += 1
                        elif current_first_raw_id > previous_last_raw_id + 1:
                            assert previous_aggregate_id is not None
                            gaps.append(
                                PeriodicFlowGapRecord(
                                    preceding_aggregate_trade_id=(
                                        previous_aggregate_id
                                    ),
                                    current_aggregate_trade_id=aggregate_id,
                                    preceding_last_raw_trade_id=(
                                        previous_last_raw_id
                                    ),
                                    current_first_raw_trade_id=(
                                        current_first_raw_id
                                    ),
                                    skipped_raw_trade_id_count=(
                                        current_first_raw_id
                                        - previous_last_raw_id
                                        - 1
                                    ),
                                    current_timestamp_ms=timestamp,
                                )
                            )
                    if previous_timestamp is not None and timestamp < previous_timestamp:
                        timestamp_regression_count += 1
                    if row_count == 0:
                        first_aggregate_id = aggregate_id
                        first_raw_id = current_first_raw_id
                        first_timestamp = timestamp
                    last_aggregate_id = aggregate_id
                    last_raw_id = current_last_raw_id
                    last_timestamp = timestamp
                    previous_aggregate_id = aggregate_id
                    previous_last_raw_id = current_last_raw_id
                    previous_timestamp = timestamp
                    minute_indexes.add((timestamp - MONTH_START_MS) // 60_000)
                    row_count += 1
    if row_count == 0:
        raise ValueError("Q1 gap remediation archive contains no rows")
    gap_tuple = tuple(gaps)
    raw_span = last_raw_id - first_raw_id + 1
    total_skipped = sum(item.skipped_raw_trade_id_count for item in gap_tuple)
    return {
        "archive_sha256": archive_hash,
        "row_count": row_count,
        "first_aggregate_trade_id": first_aggregate_id,
        "last_aggregate_trade_id": last_aggregate_id,
        "aggregate_trade_id_gap_count": aggregate_gap_count,
        "aggregate_trade_id_non_increasing_count": (
            aggregate_non_increasing_count
        ),
        "first_raw_trade_id": first_raw_id,
        "last_raw_trade_id": last_raw_id,
        "raw_trade_span_invalid_count": raw_span_invalid_count,
        "raw_trade_range_overlap_count": raw_overlap_count,
        "gap_records": gap_tuple,
        "gap_manifest_hash": universe_evidence_hash(
            {"gaps": [item.model_dump() for item in gap_tuple]}
        ),
        "gap_event_count": len(gap_tuple),
        "total_skipped_raw_trade_ids": total_skipped,
        "maximum_single_gap_skipped_raw_ids": max(
            (item.skipped_raw_trade_id_count for item in gap_tuple),
            default=0,
        ),
        "raw_trade_id_span": raw_span,
        "skipped_raw_trade_id_fraction": Decimal(total_skipped)
        / Decimal(raw_span),
        "gap_size_buckets": _gap_buckets(gap_tuple),
        "first_timestamp_ms": first_timestamp,
        "last_timestamp_ms": last_timestamp,
        "timestamp_regression_count": timestamp_regression_count,
        "unique_minute_count": len(minute_indexes),
        "minute_coverage_fraction": Decimal(len(minute_indexes))
        / Decimal(44_640),
    }


def authoritative_result(
    *,
    generated_at: datetime,
    protocol_path: Path,
    protocol: PeriodicFlowGapRemediationProtocol,
    scan: dict,
) -> PeriodicFlowGapRemediationResult:
    return build_gap_remediation_result(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        **scan,
        limitations=(
            "The original paired payload pilot remains an immutable STOP result.",
            "The forward raw-ID gaps are compatible with documented exclusions "
            "but are not individually classified.",
            "Aggregate IDs, raw ranges, timestamps, gap magnitude, and clock "
            "coverage were inspected.",
            "Price and quantity values were neither parsed nor persisted.",
            "No network request, feature, parameter, signal, candidate, return, "
            "or trade was created.",
            "Validation, future holdout, and forward outcomes remain inaccessible.",
            "A pass authorizes only a separate full-development acquisition protocol.",
            "Pine, paper, testnet strategy-order, production, and live authority remain false.",
            "This source-semantic result cannot establish edge, reliability, or profitability.",
            "Real net profit remains zero dollars.",
        ),
    )


def write_result(path: Path, result: PeriodicFlowGapRemediationResult) -> None:
    if path.exists():
        raise ValueError("Q1 gap remediation result exists; use --check")
    serialized = result.model_dump_json(indent=2) + "\n"
    if PeriodicFlowGapRemediationResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 gap remediation result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 gap result transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowGapRemediationResult:
    protocol = load_protocol(args.protocol)
    scan = scan_archive(protocol)
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol_path=args.protocol,
        protocol=protocol,
        scan=scan,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"gaps={result.gap_event_count} skipped={result.total_skipped_raw_trade_ids} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def run_check(args) -> PeriodicFlowGapRemediationResult:
    protocol = load_protocol(args.protocol)
    result = PeriodicFlowGapRemediationResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_gap_remediation_result(result)
        or result.protocol_file_sha256 != file_sha256(args.protocol)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Q1 gap remediation result lineage changed")
    expected = authoritative_result(
        generated_at=result.generated_at,
        protocol_path=args.protocol,
        protocol=protocol,
        scan=scan_archive(protocol),
    )
    if result != expected:
        raise ValueError("Q1 gap remediation result is not reproducible")
    print(
        f"PASS q1_gap_result={result.result_evidence_hash} "
        f"gaps={result.gap_event_count} skipped={result.total_skipped_raw_trade_ids} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or check the local Q1 USD-M raw-ID gap diagnosis."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_write(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
