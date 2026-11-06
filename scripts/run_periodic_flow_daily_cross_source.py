from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_daily_cross_source import (  # noqa: E402
    PeriodicFlowDailyArchiveEvidence,
    PeriodicFlowDailyCrossSourceProtocol,
    PeriodicFlowDailyCrossSourceResult,
    PeriodicFlowDailyPayloadTarget,
    audit_daily_cross_protocol,
    audit_daily_cross_result,
    build_daily_cross_result,
)
from aurex.backtest_engine.periodic_flow_overlap_census import (  # noqa: E402
    PeriodicFlowOverlapEvent,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_result_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


class RedirectRejectedError(RuntimeError):
    pass


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRejectedError(f"Q1 daily payload redirect rejected: {newurl}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "run_periodic_flow_daily_cross_source.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "periodic_flow_daily_cross_source.py",
    )
    return universe_evidence_hash(
        {
            path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
            for path in paths
        }
    )


def load_protocol(path: Path) -> PeriodicFlowDailyCrossSourceProtocol:
    protocol = PeriodicFlowDailyCrossSourceProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_daily_cross_protocol(protocol):
        raise ValueError("Q1 daily cross-source protocol hash failed")
    return protocol


def target_path(
    evidence_root: Path,
    target: PeriodicFlowDailyPayloadTarget,
) -> Path:
    return (
        evidence_root
        / "source_snapshots"
        / "q1_periodic_flow_daily_cross_source_v1"
        / target.family
        / f"BTCUSDT-{target.family}-2020-01-15.zip"
    )


def relative_path(target: PeriodicFlowDailyPayloadTarget) -> str:
    return (
        "source_snapshots/q1_periodic_flow_daily_cross_source_v1/"
        f"{target.family}/BTCUSDT-{target.family}-2020-01-15.zip"
    )


def ensure_archive(
    *,
    target: PeriodicFlowDailyPayloadTarget,
    protocol: PeriodicFlowDailyCrossSourceProtocol,
    evidence_root: Path,
) -> tuple[Path, int]:
    path = target_path(evidence_root, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if file_sha256(path) != target.published_archive_sha256:
            raise ValueError("Q1 existing daily archive checksum changed")
        return path, 1
    temporary = path.with_name(f"{path.name}.part")
    opener = urllib.request.build_opener(RejectRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(1, protocol.maximum_attempts_per_archive + 1):
        if temporary.exists():
            temporary.unlink()
        request = urllib.request.Request(
            target.archive_url,
            headers={
                "Accept": "application/zip",
                "Accept-Encoding": "identity",
                "User-Agent": "Aurex-Q1-Daily-Cross-Source/1.0",
            },
            method="GET",
        )
        received = 0
        try:
            with opener.open(
                request,
                timeout=protocol.request_timeout_seconds,
            ) as response:
                if response.getcode() != 200 or response.geturl() != target.archive_url:
                    raise ValueError("Q1 daily payload response identity changed")
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > (
                    protocol.maximum_archive_bytes_each
                ):
                    raise ValueError("Q1 daily payload Content-Length exceeds budget")
                digest = hashlib.sha256()
                with temporary.open("wb") as sink:
                    while chunk := response.read(1024 * 1024):
                        received += len(chunk)
                        if received > protocol.maximum_archive_bytes_each:
                            raise ValueError("Q1 daily payload exceeds byte budget")
                        sink.write(chunk)
                        digest.update(chunk)
                if content_length is not None and received != int(content_length):
                    raise ValueError("Q1 daily payload length changed")
                if digest.hexdigest() != target.published_archive_sha256:
                    raise ValueError("Q1 daily payload checksum failed")
                temporary.replace(path)
                return path, attempt
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise
        except (OSError, TimeoutError) as exc:
            last_error = exc
        if attempt < protocol.maximum_attempts_per_archive:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError(
        f"Q1 daily payload unresolved: {target.family}"
    ) from last_error


def _event_from_rows(
    previous: tuple[int, int, int, int],
    current: tuple[int, int, int, int],
) -> PeriodicFlowOverlapEvent | None:
    prev_aggregate, prev_first, prev_last, prev_timestamp = previous
    aggregate, first_raw, last_raw, timestamp = current
    overlap_first = max(prev_first, first_raw)
    overlap_last = min(prev_last, last_raw)
    if overlap_last < overlap_first:
        return None
    return PeriodicFlowOverlapEvent(
        preceding_aggregate_trade_id=prev_aggregate,
        current_aggregate_trade_id=aggregate,
        preceding_first_raw_trade_id=prev_first,
        preceding_last_raw_trade_id=prev_last,
        current_first_raw_trade_id=first_raw,
        current_last_raw_trade_id=last_raw,
        preceding_timestamp_ms=prev_timestamp,
        current_timestamp_ms=timestamp,
        overlap_raw_trade_id_count=overlap_last - overlap_first + 1,
        first_overlapped_raw_trade_id=overlap_first,
        last_overlapped_raw_trade_id=overlap_last,
        utc_day="2020-01-15",
    )


def inspect_archive(
    *,
    target: PeriodicFlowDailyPayloadTarget,
    protocol: PeriodicFlowDailyCrossSourceProtocol,
    archive_path: Path,
    evidence_root: Path,
    attempt_count: int,
) -> PeriodicFlowDailyArchiveEvidence:
    archive_hash = file_sha256(archive_path)
    if archive_hash != target.published_archive_sha256:
        raise ValueError("Q1 daily local archive checksum changed")
    row_count = 0
    first_id = 0
    last_id = 0
    previous_id: int | None = None
    previous_timestamp: int | None = None
    non_increasing = 0
    gaps = 0
    timestamp_regressions = 0
    previous_agg: tuple[int, int, int, int] | None = None
    overlap_events: list[PeriodicFlowOverlapEvent] = []
    target_occurrences = 0
    target_timestamp: int | None = None

    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != target.expected_member_name:
            raise ValueError("Q1 daily ZIP structure changed")
        member = members[0]
        if (
            member.is_dir()
            or member.flag_bits & 0x1
            or member.file_size > protocol.maximum_member_uncompressed_bytes_each
            or member.compress_size <= 0
            or member.file_size
            > member.compress_size * protocol.maximum_zip_expansion_ratio
        ):
            raise ValueError("Q1 daily ZIP member violates resource bounds")
        with archive.open(member, "r") as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                for row in csv.reader(text):
                    if len(row) != target.expected_column_count:
                        raise ValueError("Q1 daily CSV column count changed")
                    if row_count == 0:
                        try:
                            int(row[0])
                        except ValueError as exc:
                            expected_header = (
                                (
                                    "agg_trade_id",
                                    "price",
                                    "quantity",
                                    "first_trade_id",
                                    "last_trade_id",
                                    "transact_time",
                                    "is_buyer_maker",
                                )
                                if target.family == "aggTrades"
                                else (
                                    "id",
                                    "price",
                                    "qty",
                                    "quote_qty",
                                    "time",
                                    "is_buyer_maker",
                                )
                            )
                            if tuple(value.strip().lower() for value in row) != (
                                expected_header
                            ):
                                raise ValueError(
                                    "Q1 daily CSV header changed"
                                ) from exc
                            continue
                    if target.family == "aggTrades":
                        if not row[1].strip() or not row[2].strip():
                            raise ValueError("Q1 daily excluded aggregate value is empty")
                        current_id = int(row[0])
                        first_raw = int(row[3])
                        last_raw = int(row[4])
                        timestamp = int(row[5])
                        current_agg = current_id, first_raw, last_raw, timestamp
                        if previous_agg is not None:
                            event = _event_from_rows(previous_agg, current_agg)
                            if event is not None:
                                overlap_events.append(event)
                        previous_agg = current_agg
                    else:
                        if any(not row[index].strip() for index in (1, 2, 3)):
                            raise ValueError("Q1 daily excluded raw value is empty")
                        current_id = int(row[0])
                        timestamp = int(row[4])
                        if (
                            current_id
                            == protocol.parent_overlap_event.first_overlapped_raw_trade_id
                        ):
                            target_occurrences += 1
                            target_timestamp = timestamp
                    if previous_id is not None:
                        if current_id <= previous_id:
                            non_increasing += 1
                        if current_id != previous_id + 1:
                            gaps += 1
                    if previous_timestamp is not None and timestamp < previous_timestamp:
                        timestamp_regressions += 1
                    if row_count == 0:
                        first_id = current_id
                    last_id = current_id
                    previous_id = current_id
                    previous_timestamp = timestamp
                    row_count += 1
    if row_count == 0:
        raise ValueError("Q1 daily archive contains no rows")
    if target.family == "aggTrades":
        unexpected = [
            event
            for event in overlap_events
            if event != protocol.parent_overlap_event
        ]
        if unexpected:
            raise ValueError("Q1 daily aggregate contains an unexpected overlap")
        match_count = sum(
            event == protocol.parent_overlap_event for event in overlap_events
        )
        target_occurrences = 0
        target_timestamp = None
        parsed = (
            "aggregate_trade_id",
            "first_trade_id",
            "last_trade_id",
            "timestamp",
        )
        excluded = ("price", "quantity")
    else:
        match_count = 0
        parsed = ("trade_id", "timestamp")
        excluded = ("price", "quantity", "quote_quantity")
    reasons = []
    if non_increasing:
        reasons.append("ID_NOT_STRICTLY_INCREASING")
    if timestamp_regressions:
        reasons.append("TIMESTAMP_REGRESSION")
    if target.family == "aggTrades" and match_count != 1:
        reasons.append("MONTHLY_OVERLAP_NOT_EXACTLY_REPRODUCED")
    if target.family == "trades" and target_occurrences != 1:
        reasons.append("TARGET_RAW_TRADE_ID_NOT_UNIQUE")
    if target.family == "trades" and target_timestamp is None:
        reasons.append("TARGET_RAW_TRADE_TIMESTAMP_MISSING")
    return PeriodicFlowDailyArchiveEvidence(
        family=target.family,
        local_path=relative_path(target),
        archive_sha256=archive_hash,
        published_archive_sha256=target.published_archive_sha256,
        archive_bytes=archive_path.stat().st_size,
        member_name=member.filename,
        member_compressed_bytes=member.compress_size,
        member_uncompressed_bytes=member.file_size,
        row_count=row_count,
        first_id=first_id,
        last_id=last_id,
        id_non_increasing_count=non_increasing,
        id_gap_count=gaps,
        timestamp_regression_count=timestamp_regressions,
        monthly_overlap_event_match_count=match_count,
        target_raw_trade_id_occurrence_count=target_occurrences,
        target_raw_trade_timestamp_ms=target_timestamp,
        payload_get_attempt_count=attempt_count,
        archive_pass=not reasons,
        reason_codes=tuple(sorted(reasons)),
        parsed_numeric_fields=parsed,
        excluded_numeric_fields=excluded,
    )


def inspect_pair(
    *,
    protocol: PeriodicFlowDailyCrossSourceProtocol,
    evidence_root: Path,
    attempt_counts: dict[str, int],
) -> tuple[PeriodicFlowDailyArchiveEvidence, ...]:
    return tuple(
        inspect_archive(
            target=target,
            protocol=protocol,
            archive_path=target_path(evidence_root, target),
            evidence_root=evidence_root,
            attempt_count=attempt_counts[target.family],
        )
        for target in protocol.targets
    )


def authoritative_result(
    *,
    generated_at: datetime,
    protocol_path: Path,
    protocol: PeriodicFlowDailyCrossSourceProtocol,
    evidence: tuple[PeriodicFlowDailyArchiveEvidence, ...],
) -> PeriodicFlowDailyCrossSourceResult:
    return build_daily_cross_result(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        parent_overlap_event=protocol.parent_overlap_event,
        archive_evidence=evidence,
        payload_get_attempt_count=sum(
            item.payload_get_attempt_count for item in evidence
        ),
        total_archive_bytes=sum(item.archive_bytes for item in evidence),
        limitations=(
            "The daily aggregate archive exactly reproduced the monthly duplicate raw reference.",
            "The daily raw-trades archive was used only for IDs and timestamps.",
            "Price, quantity, quote quantity, returns, and outcomes were not accessed.",
            "A pass rejects USD-M aggTrades as the Q1 source and authorizes only "
            "a raw-trades metadata census.",
            "Spot aggTrades source status is unchanged by this USD-M adjudication.",
            "No feature, parameter, signal, candidate, Pine, paper, or order was created.",
            "Production and live authority remain false.",
            "Cross-source identity evidence cannot establish edge or profitability.",
            "Real net profit remains zero dollars.",
        ),
    )


def write_result(path: Path, result: PeriodicFlowDailyCrossSourceResult) -> None:
    if path.exists():
        raise ValueError("Q1 daily cross-source result exists; use --check")
    serialized = result.model_dump_json(indent=2) + "\n"
    if PeriodicFlowDailyCrossSourceResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 daily cross-source result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 daily result transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowDailyCrossSourceResult:
    protocol = load_protocol(args.protocol)
    attempts = {}
    for target in protocol.targets:
        path, count = ensure_archive(
            target=target,
            protocol=protocol,
            evidence_root=args.evidence_root,
        )
        attempts[target.family] = count
        print(
            f"VERIFIED family={target.family} bytes={path.stat().st_size} "
            f"sha256={file_sha256(path)}",
            flush=True,
        )
    evidence = inspect_pair(
        protocol=protocol,
        evidence_root=args.evidence_root,
        attempt_counts=attempts,
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol_path=args.protocol,
        protocol=protocol,
        evidence=evidence,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def run_check(args) -> PeriodicFlowDailyCrossSourceResult:
    protocol = load_protocol(args.protocol)
    result = PeriodicFlowDailyCrossSourceResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_daily_cross_result(result)
        or result.protocol_file_sha256 != file_sha256(args.protocol)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Q1 daily cross-source result lineage changed")
    attempts = {
        item.family: item.payload_get_attempt_count for item in result.archive_evidence
    }
    evidence = inspect_pair(
        protocol=protocol,
        evidence_root=args.evidence_root,
        attempt_counts=attempts,
    )
    expected = authoritative_result(
        generated_at=result.generated_at,
        protocol_path=args.protocol,
        protocol=protocol,
        evidence=evidence,
    )
    if result != expected:
        raise ValueError("Q1 daily cross-source result is not reproducible")
    print(
        f"PASS q1_daily_cross_result={result.result_evidence_hash} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or check Q1 USD-M daily cross-source adjudication."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
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
