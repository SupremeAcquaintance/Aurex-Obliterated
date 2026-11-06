from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from itertools import chain
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.parse import urlsplit

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v3_p02_payload_pilot import (
    V3_P02_EXPECTED_HEADER,
    V3_P02_FULL_COHORT_SYMBOLS,
    V3_P02_SAMPLE_KEYS,
    V3P02ArchiveSizeObservation,
    V3P02PayloadPilotProtocol,
    V3P02PayloadPilotResult,
    V3P02PayloadTarget,
    V3P02SamplePayloadEvidence,
    audit_v3_p02_payload_pilot_protocol,
    audit_v3_p02_payload_pilot_result,
    build_v3_p02_payload_pilot_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = Path(
    "data/evidence/v3_p02_payload_pilot_protocol_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p02_payload_pilot_result_v1.json"
)
SAMPLE_STORAGE_DIRECTORY = "v3_p02_payload_pilot_v1"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class HeadHttpObservation:
    status: int
    content_length: str | None
    etag: str | None
    last_modified: str | None
    observed_at: datetime


HeadOnce = Callable[[str, int], HeadHttpObservation]
Sleep = Callable[[float], None]


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def protocol_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p02_payload_pilot_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_payload_pilot.py",
        ]
    )


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p02_payload_pilot.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_payload_pilot.py",
        ]
    )


def load_protocol(path: Path) -> V3P02PayloadPilotProtocol:
    protocol = V3P02PayloadPilotProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_payload_pilot_protocol(protocol)
        or protocol.builder_contract_hash != protocol_builder_hash()
    ):
        raise ValueError("Frozen V3P02 payload pilot protocol audit failed")
    return protocol


def _validate_archive_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.binance.vision"
        or not parsed.path.startswith("/data/futures/um/monthly/aggTrades/")
        or not parsed.path.endswith(".zip")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("V3P02 runner refused a non-contract archive URL")


def urllib_head_once(url: str, timeout: int) -> HeadHttpObservation:
    _validate_archive_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/zip",
            "User-Agent": "Aurex-V3P02-Payload-Pilot/1.0",
        },
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HeadHttpObservation(
                status=response.getcode(),
                content_length=response.headers.get("Content-Length"),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                observed_at=datetime.now(UTC),
            )
    except urllib.error.HTTPError as exc:
        return HeadHttpObservation(
            status=exc.code,
            content_length=None,
            etag=None,
            last_modified=None,
            observed_at=datetime.now(UTC),
        )


def fetch_head_observation(
    *,
    target: V3P02PayloadTarget,
    protocol: V3P02PayloadPilotProtocol,
    head_once: HeadOnce = urllib_head_once,
    sleep: Sleep = time.sleep,
) -> V3P02ArchiveSizeObservation:
    attempts = protocol.maximum_head_retries + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            observed = head_once(
                target.archive_url,
                protocol.request_timeout_seconds,
            )
        except (OSError, TimeoutError) as exc:
            last_error = exc
        else:
            if observed.status == 200:
                if observed.content_length is None:
                    raise ValueError(
                        f"V3P02 HEAD has no Content-Length: {target.key}"
                    )
                try:
                    content_length = int(observed.content_length)
                except ValueError as exc:
                    raise ValueError(
                        f"V3P02 HEAD Content-Length is invalid: {target.key}"
                    ) from exc
                if content_length <= 0:
                    raise ValueError(
                        f"V3P02 HEAD Content-Length is not positive: {target.key}"
                    )
                return V3P02ArchiveSizeObservation(
                    symbol=target.symbol,
                    month=target.month,
                    archive_url=target.archive_url,
                    observed_at=observed.observed_at,
                    http_status=200,
                    content_length_bytes=content_length,
                    etag=observed.etag,
                    last_modified=observed.last_modified,
                    request_attempt_count=attempt + 1,
                )
            if observed.status not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"Unexpected V3P02 HEAD HTTP {observed.status}: "
                    f"{target.archive_url}"
                )
            last_error = RuntimeError(
                f"Transient V3P02 HEAD HTTP {observed.status}: "
                f"{target.archive_url}"
            )
        if attempt < protocol.maximum_head_retries:
            sleep(protocol.head_retry_backoff_seconds[attempt])
    raise RuntimeError(
        f"V3P02 HEAD unresolved after {attempts} attempts: {target.key}"
    ) from last_error


def collect_head_observations(
    *,
    protocol: V3P02PayloadPilotProtocol,
    workers: int,
) -> list[V3P02ArchiveSizeObservation]:
    if not 1 <= workers <= protocol.maximum_head_concurrency:
        raise ValueError("Worker count exceeds the frozen V3P02 limit")
    observations: list[V3P02ArchiveSizeObservation] = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            fetch_head_observation,
            target=target,
            protocol=protocol,
        ): target
        for target in protocol.targets
    }
    try:
        for completed, future in enumerate(as_completed(futures), start=1):
            target = futures[future]
            try:
                observations.append(future.result())
            except Exception as exc:
                for pending in futures:
                    pending.cancel()
                raise RuntimeError(
                    "V3P02 HEAD census aborted without result at "
                    f"{target.symbol}/{target.month}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            if completed % 100 == 0 or completed == len(futures):
                print(
                    f"V3P02 archive size observations: "
                    f"{completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return sorted(observations, key=lambda item: item.key)


def target_paths(
    *,
    evidence_root: Path,
    target: V3P02PayloadTarget,
) -> tuple[Path, Path]:
    archive_name = PurePosixPath(urlsplit(target.archive_url).path).name
    directory = evidence_root / SAMPLE_STORAGE_DIRECTORY / target.symbol
    archive_path = directory / archive_name
    marker_path = directory / f"{archive_name}.request.json"
    return archive_path, marker_path


def _stream_response_to_file(
    response: BinaryIO,
    *,
    temporary: Path,
    expected_bytes: int,
    maximum_bytes: int,
) -> str:
    digest = hashlib.sha256()
    downloaded = 0
    with temporary.open("xb") as destination:
        while True:
            chunk = response.read(DOWNLOAD_CHUNK_BYTES)
            if not chunk:
                break
            downloaded += len(chunk)
            if downloaded > expected_bytes or downloaded > maximum_bytes:
                raise ValueError("V3P02 sample exceeded its frozen byte limit")
            destination.write(chunk)
            digest.update(chunk)
    if downloaded != expected_bytes:
        raise ValueError("V3P02 sample size differs from HEAD observation")
    return digest.hexdigest()


def _request_marker_payload(
    *,
    target: V3P02PayloadTarget,
    protocol: V3P02PayloadPilotProtocol,
    requested_at: datetime,
) -> dict[str, str]:
    return {
        "schema_version": "aurex-v3-p02-sample-request-marker-v1",
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "symbol": target.symbol,
        "month": target.month,
        "archive_url": target.archive_url,
        "requested_at": requested_at.isoformat(),
    }


def _validate_request_marker(
    *,
    marker_path: Path,
    target: V3P02PayloadTarget,
    protocol: V3P02PayloadPilotProtocol,
) -> None:
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    if set(payload) != {
        "schema_version",
        "protocol_evidence_hash",
        "symbol",
        "month",
        "archive_url",
        "requested_at",
    }:
        raise ValueError("V3P02 request marker schema changed")
    try:
        requested_at = datetime.fromisoformat(payload["requested_at"])
    except (TypeError, ValueError) as exc:
        raise ValueError("V3P02 request marker timestamp is invalid") from exc
    expected = _request_marker_payload(
        target=target,
        protocol=protocol,
        requested_at=requested_at,
    )
    if payload != expected or requested_at.tzinfo is None:
        raise ValueError("V3P02 request marker lineage changed")


def _write_request_marker(
    *,
    marker_path: Path,
    target: V3P02PayloadTarget,
    protocol: V3P02PayloadPilotProtocol,
) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    if marker_path.exists():
        raise ValueError(f"V3P02 sample request already recorded: {target.key}")
    temporary = marker_path.with_name(f"{marker_path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale V3P02 request marker exists: {temporary}")
    payload = _request_marker_payload(
        target=target,
        protocol=protocol,
        requested_at=datetime.now(UTC),
    )
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(marker_path)


def ensure_verified_sample_archive(
    *,
    target: V3P02PayloadTarget,
    observation: V3P02ArchiveSizeObservation,
    protocol: V3P02PayloadPilotProtocol,
    archive_path: Path,
    marker_path: Path,
) -> int:
    if target.key != observation.key:
        raise ValueError("V3P02 sample and HEAD observation disagree")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        if not marker_path.exists():
            raise ValueError(
                f"Unlineaged existing V3P02 sample archive: {archive_path}"
            )
        _validate_request_marker(
            marker_path=marker_path,
            target=target,
            protocol=protocol,
        )
        if (
            archive_path.stat().st_size != observation.content_length_bytes
            or file_sha256(archive_path) != target.checksum_sha256
        ):
            raise ValueError(f"Existing V3P02 sample conflicts: {target.key}")
        return 1
    if marker_path.exists():
        _validate_request_marker(
            marker_path=marker_path,
            target=target,
            protocol=protocol,
        )
        raise ValueError(
            f"Prior V3P02 sample request did not produce an archive: {target.key}"
        )

    temporary = archive_path.with_name(f"{archive_path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale V3P02 sample download exists: {temporary}")
    _write_request_marker(
        marker_path=marker_path,
        target=target,
        protocol=protocol,
    )
    request = urllib.request.Request(
        target.archive_url,
        headers={
            "Accept": "application/zip",
            "User-Agent": "Aurex-V3P02-Payload-Pilot/1.0",
        },
        method="GET",
    )
    _validate_archive_url(target.archive_url)
    try:
        with urllib.request.urlopen(
            request,
            timeout=protocol.request_timeout_seconds,
        ) as response:
            if response.getcode() != 200:
                raise RuntimeError(
                    f"V3P02 sample GET HTTP {response.getcode()}: {target.key}"
                )
            content_length = response.headers.get("Content-Length")
            if (
                content_length is None
                or int(content_length) != observation.content_length_bytes
            ):
                raise ValueError(
                    "V3P02 sample GET size differs from HEAD observation"
                )
            observed_sha256 = _stream_response_to_file(
                response,
                temporary=temporary,
                expected_bytes=observation.content_length_bytes,
                maximum_bytes=protocol.maximum_sample_payload_bytes,
            )
        if observed_sha256 != target.checksum_sha256:
            raise ValueError(
                f"V3P02 sample checksum differs from census: {target.key}"
            )
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(archive_path)
    return 1


def _month_bounds_ms(month: str) -> tuple[int, int, int]:
    year, month_number = (int(part) for part in month.split("-"))
    start = datetime(year, month_number, 1, tzinfo=UTC)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=UTC)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    return start_ms, end_ms, (end_ms - start_ms) // 60_000


def _normalized_header(row: list[str]) -> list[str]:
    return [item.strip().lower().replace(" ", "_") for item in row]


def _validate_zip_member(
    *,
    archive: zipfile.ZipFile,
    target: V3P02PayloadTarget,
    protocol: V3P02PayloadPilotProtocol,
) -> zipfile.ZipInfo:
    files = [member for member in archive.infolist() if not member.is_dir()]
    expected_name = f"{target.symbol}-aggTrades-{target.month}.csv"
    if len(files) != 1 or files[0].filename != expected_name:
        raise ValueError("V3P02 sample must contain its exact single CSV member")
    member = files[0]
    member_path = PurePosixPath(member.filename)
    unix_mode = (member.external_attr >> 16) & 0o170000
    if (
        member_path.is_absolute()
        or len(member_path.parts) != 1
        or ".." in member_path.parts
        or "\\" in member.filename
        or member.flag_bits & 0x1
        or unix_mode == stat.S_IFLNK
    ):
        raise ValueError("V3P02 sample ZIP member is unsafe")
    if (
        member.compress_size <= 0
        or member.file_size <= 0
        or member.file_size
        > protocol.maximum_single_sample_uncompressed_bytes
        or member.file_size
        > member.compress_size * protocol.maximum_zip_expansion_ratio
    ):
        raise ValueError("V3P02 sample ZIP exceeds frozen resource limits")
    return member


def inspect_sample_archive(
    *,
    target: V3P02PayloadTarget,
    archive_path: Path,
    evidence_root: Path,
    protocol: V3P02PayloadPilotProtocol,
    payload_request_count: int,
) -> V3P02SamplePayloadEvidence:
    if target.key not in V3_P02_SAMPLE_KEYS or not target.sample_payload:
        raise ValueError("V3P02 inspection refused a non-sample target")
    archive_sha256 = file_sha256(archive_path)
    if archive_sha256 != target.checksum_sha256:
        raise ValueError("V3P02 sample checksum does not match its protocol")
    try:
        local_path = archive_path.relative_to(evidence_root).as_posix()
    except ValueError as exc:
        raise ValueError("V3P02 sample path is outside the evidence root") from exc

    month_start_ms, month_end_ms, expected_minutes = _month_bounds_ms(
        target.month
    )
    row_count = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None
    previous_timestamp_ms: int | None = None
    previous_aggregate_trade_id: int | None = None
    duplicate_timestamp_count = 0
    maximum_gap_ms = 0
    aggregate_trade_id_gap_count = 0
    minute_buckets: set[int] = set()
    header_present = False

    with zipfile.ZipFile(archive_path) as archive:
        member = _validate_zip_member(
            archive=archive,
            target=target,
            protocol=protocol,
        )
        with archive.open(member) as source:
            text = io.TextIOWrapper(source, encoding="utf-8", newline="")
            reader = csv.reader(text)
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("V3P02 sample CSV is empty") from exc
            if len(first_row) != protocol.expected_column_count:
                raise ValueError("V3P02 sample CSV column count changed")
            try:
                int(first_row[protocol.aggregate_trade_id_column_index])
            except ValueError:
                header_present = True
                if _normalized_header(first_row) != V3_P02_EXPECTED_HEADER:
                    raise ValueError(
                        "V3P02 sample CSV header is unknown"
                    ) from None
                rows = reader
            else:
                rows = chain((first_row,), reader)

            for row in rows:
                if len(row) != protocol.expected_column_count:
                    raise ValueError("V3P02 sample CSV column count changed")
                try:
                    aggregate_trade_id = int(
                        row[protocol.aggregate_trade_id_column_index]
                    )
                    timestamp_ms = int(row[protocol.timestamp_column_index])
                except (IndexError, ValueError) as exc:
                    raise ValueError(
                        "V3P02 sample ID or timestamp is invalid"
                    ) from exc
                if not month_start_ms <= timestamp_ms < month_end_ms:
                    raise ValueError(
                        "V3P02 sample timestamp is outside its month"
                    )
                if (
                    previous_aggregate_trade_id is not None
                    and aggregate_trade_id <= previous_aggregate_trade_id
                ):
                    raise ValueError(
                        "V3P02 aggregate-trade IDs are not strictly increasing"
                    )
                if previous_aggregate_trade_id is not None:
                    aggregate_trade_id_gap_count += (
                        aggregate_trade_id
                        - previous_aggregate_trade_id
                        - 1
                    )
                if (
                    previous_timestamp_ms is not None
                    and timestamp_ms < previous_timestamp_ms
                ):
                    raise ValueError(
                        "V3P02 sample timestamps are not nondecreasing"
                    )
                if previous_timestamp_ms is not None:
                    gap_ms = timestamp_ms - previous_timestamp_ms
                    maximum_gap_ms = max(maximum_gap_ms, gap_ms)
                    duplicate_timestamp_count += timestamp_ms == (
                        previous_timestamp_ms
                    )
                if first_timestamp_ms is None:
                    first_timestamp_ms = timestamp_ms
                last_timestamp_ms = timestamp_ms
                previous_timestamp_ms = timestamp_ms
                previous_aggregate_trade_id = aggregate_trade_id
                minute_buckets.add((timestamp_ms - month_start_ms) // 60_000)
                row_count += 1

    if (
        row_count == 0
        or first_timestamp_ms is None
        or last_timestamp_ms is None
    ):
        raise ValueError("V3P02 sample CSV contains no data rows")
    coverage_fraction = Decimal(len(minute_buckets)) / Decimal(expected_minutes)
    maximum_gap_minutes = (maximum_gap_ms + 59_999) // 60_000
    reasons = []
    if coverage_fraction < Decimal(
        protocol.minimum_sample_month_coverage_fraction
    ):
        reasons.append("MINUTE_COVERAGE_BELOW_0_99")
    if maximum_gap_minutes > protocol.maximum_sample_event_gap_minutes:
        reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
    if (
        aggregate_trade_id_gap_count
        > protocol.maximum_sample_aggregate_trade_id_gap_count
    ):
        reasons.append("AGGREGATE_TRADE_ID_GAP")
    return V3P02SamplePayloadEvidence(
        symbol=target.symbol,
        month=target.month,
        archive_url=target.archive_url,
        local_path=local_path,
        archive_bytes=archive_path.stat().st_size,
        archive_sha256=archive_sha256,
        published_checksum_sha256=target.checksum_sha256,
        checksum_verified=True,
        csv_member_name=member.filename,
        zip_compressed_bytes=member.compress_size,
        zip_uncompressed_bytes=member.file_size,
        column_count=protocol.expected_column_count,
        header_present=header_present,
        row_count=row_count,
        first_timestamp_ms=first_timestamp_ms,
        last_timestamp_ms=last_timestamp_ms,
        unique_minute_count=len(minute_buckets),
        expected_minute_count=expected_minutes,
        minute_coverage_fraction=coverage_fraction,
        maximum_event_gap_minutes=maximum_gap_minutes,
        aggregate_trade_id_gap_count=aggregate_trade_id_gap_count,
        duplicate_timestamp_count=duplicate_timestamp_count,
        payload_request_count=payload_request_count,
        sample_pass=not reasons,
        reason_codes=reasons,
        market_numeric_fields_inspected=[],
    )


def sample_targets(
    protocol: V3P02PayloadPilotProtocol,
) -> list[V3P02PayloadTarget]:
    return [
        target
        for target in protocol.targets
        if target.key in V3_P02_SAMPLE_KEYS
    ]


def resource_gates(
    *,
    protocol: V3P02PayloadPilotProtocol,
    observations: list[V3P02ArchiveSizeObservation],
    free_disk_bytes_before_samples: int,
) -> tuple[bool, bool, bool]:
    full_cohort = set(V3_P02_FULL_COHORT_SYMBOLS)
    sample_keys = set(V3_P02_SAMPLE_KEYS)
    full_bytes = sum(
        item.content_length_bytes
        for item in observations
        if item.symbol in full_cohort
    )
    sample_bytes = sum(
        item.content_length_bytes
        for item in observations
        if item.key in sample_keys
    )
    return (
        full_bytes <= protocol.maximum_full_cohort_compressed_bytes,
        sample_bytes <= protocol.maximum_sample_payload_bytes,
        free_disk_bytes_before_samples - full_bytes
        >= protocol.minimum_post_acquisition_free_bytes,
    )


def collect_sample_evidence(
    *,
    protocol: V3P02PayloadPilotProtocol,
    observations: list[V3P02ArchiveSizeObservation],
    evidence_root: Path,
) -> list[V3P02SamplePayloadEvidence]:
    observations_by_key = {item.key: item for item in observations}
    evidence = []
    for target in sample_targets(protocol):
        archive_path, marker_path = target_paths(
            evidence_root=evidence_root,
            target=target,
        )
        request_count = ensure_verified_sample_archive(
            target=target,
            observation=observations_by_key[target.key],
            protocol=protocol,
            archive_path=archive_path,
            marker_path=marker_path,
        )
        record = inspect_sample_archive(
            target=target,
            archive_path=archive_path,
            evidence_root=evidence_root,
            protocol=protocol,
            payload_request_count=request_count,
        )
        evidence.append(record)
        print(
            f"V3P02 sample verified: {target.symbol}/{target.month} "
            f"bytes={record.archive_bytes} rows={record.row_count} "
            f"pass={record.sample_pass}",
            flush=True,
        )
    return sorted(evidence, key=lambda item: (item.symbol, item.month))


def authoritative_result(
    *,
    generated_at: datetime,
    protocol: V3P02PayloadPilotProtocol,
    observations: list[V3P02ArchiveSizeObservation],
    samples: list[V3P02SamplePayloadEvidence],
    free_disk_bytes_before_samples: int,
) -> V3P02PayloadPilotResult:
    return build_v3_p02_payload_pilot_result(
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        size_observations=observations,
        sample_evidence=samples,
        free_disk_bytes_before_samples=free_disk_bytes_before_samples,
        limitations=[
            (
                "The result inspects archive identity, compressed size, ZIP/CSV "
                "structure, aggregate-trade IDs, and timestamps only."
            ),
            (
                "Price, quantity, maker side, signals, trades, PnL, and returns were "
                "not parsed or calculated."
            ),
            (
                "HEAD Content-Length is an observed source header and may differ "
                "from future archive size if Binance republishes an archive."
            ),
            (
                "Three deterministic samples cannot prove structural continuity "
                "for every archive in the ten-symbol cohort."
            ),
            (
                "Checksum and timestamp continuity establish source feasibility, "
                "not clock-phase predictability or economic edge."
            ),
            (
                "The disk projection covers compressed cohort archives and excludes "
                "future derived datasets, indices, backups, and operating headroom."
            ),
            (
                "A passing decision permits only a separately frozen ten-symbol full "
                "payload protocol and grants no candidate, validation, holdout, "
                "forward, Pine, paper, sandbox, live, or capital permission."
            ),
        ],
    )


def write_result(path: Path, result: V3P02PayloadPilotResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V3P02PayloadPilotResult.model_validate_json(serialized) != result:
        raise ValueError("V3P02 payload pilot result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_pilot(args) -> V3P02PayloadPilotResult:
    if args.output.exists():
        raise ValueError("Frozen V3P02 payload result exists; use --audit")
    protocol = load_protocol(args.protocol)
    observations = collect_head_observations(
        protocol=protocol,
        workers=args.workers,
    )
    if (
        len(observations) != len(protocol.targets)
        or sum(item.request_attempt_count for item in observations)
        > protocol.maximum_head_http_attempts
    ):
        raise ValueError("V3P02 HEAD request matrix or budget changed")
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    free_disk = shutil.disk_usage(args.evidence_root).free
    gates = resource_gates(
        protocol=protocol,
        observations=observations,
        free_disk_bytes_before_samples=free_disk,
    )
    print(
        "V3P02 resource gates "
        f"cohort_size={gates[0]} sample_size={gates[1]} "
        f"free_space={gates[2]} free_bytes={free_disk}",
        flush=True,
    )
    samples = (
        collect_sample_evidence(
            protocol=protocol,
            observations=observations,
            evidence_root=args.evidence_root,
        )
        if all(gates)
        else []
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        observations=observations,
        samples=samples,
        free_disk_bytes_before_samples=free_disk,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"cohort_bytes={result.summary.full_cohort_compressed_bytes} "
        f"samples={result.summary.sample_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> V3P02PayloadPilotResult:
    protocol = load_protocol(args.protocol)
    result = V3P02PayloadPilotResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if not audit_v3_p02_payload_pilot_result(result):
        raise ValueError("V3P02 payload pilot result hash audit failed")
    if (
        result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.summary.total_head_http_attempt_count
        > protocol.maximum_head_http_attempts
        or result.summary.sample_payload_request_count
        > protocol.maximum_sample_payload_requests
        or result.summary.sample_payload_bytes
        > protocol.maximum_sample_payload_bytes
    ):
        raise ValueError("V3P02 payload pilot lineage or budget audit failed")
    rebuilt = authoritative_result(
        generated_at=result.generated_at,
        protocol=protocol,
        observations=result.size_observations,
        samples=result.sample_evidence,
        free_disk_bytes_before_samples=(
            result.summary.free_disk_bytes_before_samples
        ),
    )
    if rebuilt != result:
        raise ValueError("V3P02 payload pilot result is not reproducible")

    targets_by_key = {target.key: target for target in protocol.targets}
    for record in result.sample_evidence:
        target = targets_by_key[(record.symbol, record.month)]
        archive_path, marker_path = target_paths(
            evidence_root=args.evidence_root,
            target=target,
        )
        if not marker_path.exists():
            raise ValueError(f"V3P02 request marker is absent: {target.key}")
        _validate_request_marker(
            marker_path=marker_path,
            target=target,
            protocol=protocol,
        )
        inspected = inspect_sample_archive(
            target=target,
            archive_path=archive_path,
            evidence_root=args.evidence_root,
            protocol=protocol,
            payload_request_count=record.payload_request_count,
        )
        if inspected != record:
            raise ValueError(
                f"V3P02 local sample audit changed: {target.key}"
            )
    print(
        "PASS "
        f"v3p02_payload={result.result_evidence_hash} "
        f"heads={result.summary.head_observation_count} "
        f"cohort_bytes={result.summary.full_cohort_compressed_bytes} "
        f"samples={result.summary.sample_count} "
        f"decision={result.decision} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen no-return V3P02 aggregate-trade payload pilot."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_pilot(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
