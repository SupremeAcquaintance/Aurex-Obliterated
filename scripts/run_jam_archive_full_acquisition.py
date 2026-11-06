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
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from itertools import chain
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from aurex.backtest_engine.jam_archive_full_acquisition import (
    JAM_FULL_AGGTRADES_HEADER,
    JAM_FULL_KLINES_HEADER,
    JAM_FULL_MONTHS,
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    JamFullAcquisitionTarget,
    JamFullArchiveEvidence,
    JamFullMonthEvidence,
    JamFullMonthReconciliation,
    audit_jam_full_acquisition_protocol,
    audit_jam_full_acquisition_result,
    build_jam_full_acquisition_result,
    month_bounds_ms,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = Path(
    "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_full_acquisition_result_v1.json"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/jam_archive_full_acquisition_checkpoint_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
FULL_STORAGE_DIRECTORY = "jam_archive_full_acquisition_v1"
PILOT_STORAGE_DIRECTORY = "jam_archive_payload_pilot_v1"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


class RedirectRejectedError(RuntimeError):
    pass


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRejectedError(
            f"Jam full acquisition rejected HTTP redirect {code}: {newurl}"
        )


@dataclass(slots=True)
class MinuteAggregate:
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    raw_trade_count: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal


@dataclass(frozen=True, slots=True)
class KlineMinute:
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    raw_trade_count: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal


@dataclass(frozen=True, slots=True)
class HeadObservation:
    content_length_bytes: int
    request_count: int
    accept_ranges: str


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
            / "freeze_jam_archive_full_acquisition_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_full_acquisition.py",
        ]
    )


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_jam_archive_full_acquisition.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_full_acquisition.py",
        ]
    )


def load_protocol(path: Path) -> JamFullAcquisitionProtocol:
    protocol = JamFullAcquisitionProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_full_acquisition_protocol(protocol)
        or protocol.builder_contract_hash != protocol_builder_hash()
    ):
        raise ValueError("Frozen Jam full acquisition protocol audit failed")
    return protocol


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def target_directory(
    evidence_root: Path,
    target: JamFullAcquisitionTarget,
) -> Path:
    storage = (
        PILOT_STORAGE_DIRECTORY
        if target.reuse_verified_pilot_file
        else FULL_STORAGE_DIRECTORY
    )
    return (
        evidence_root
        / storage
        / target.symbol
        / target.month
        / target.family
    )


def target_archive_path(
    evidence_root: Path,
    target: JamFullAcquisitionTarget,
) -> Path:
    return target_directory(evidence_root, target) / PurePosixPath(
        urlparse(target.archive_url).path
    ).name


def _marker_path(
    *,
    evidence_root: Path,
    target: JamFullAcquisitionTarget,
    method: str,
    attempt: int,
    kind: str,
) -> Path:
    archive_name = PurePosixPath(urlparse(target.archive_url).path).name
    return target_directory(evidence_root, target) / (
        f"{archive_name}.{method.lower()}.{attempt}.{kind}.json"
    )


def _write_json_transactional(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"Jam full marker already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Jam full marker exists: {temporary}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_request_marker(
    *,
    evidence_root: Path,
    target: JamFullAcquisitionTarget,
    protocol: JamFullAcquisitionProtocol,
    method: str,
    attempt: int,
    range_start: int | None = None,
) -> None:
    _write_json_transactional(
        _marker_path(
            evidence_root=evidence_root,
            target=target,
            method=method,
            attempt=attempt,
            kind="request",
        ),
        {
            "schema_version": "aurex-jam-full-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "family": target.family,
            "month": target.month,
            "method": method,
            "url": target.archive_url,
            "attempt": attempt,
            "range_start": range_start,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )


def _write_response_marker(
    *,
    evidence_root: Path,
    target: JamFullAcquisitionTarget,
    protocol: JamFullAcquisitionProtocol,
    method: str,
    attempt: int,
    status: int | None,
    final_url: str,
    content_length: int | None,
    bytes_received: int,
    outcome: str,
    accept_ranges: str = "",
) -> None:
    _write_json_transactional(
        _marker_path(
            evidence_root=evidence_root,
            target=target,
            method=method,
            attempt=attempt,
            kind="response",
        ),
        {
            "schema_version": "aurex-jam-full-http-response-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "family": target.family,
            "month": target.month,
            "method": method,
            "url": target.archive_url,
            "attempt": attempt,
            "status": status,
            "final_url": final_url,
            "content_length": content_length,
            "bytes_received": bytes_received,
            "outcome": outcome,
            "accept_ranges": accept_ranges,
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )


def _request_marker_count(
    *,
    evidence_root: Path,
    target: JamFullAcquisitionTarget,
    method: str,
) -> int:
    directory = target_directory(evidence_root, target)
    if not directory.exists():
        return 0
    archive_name = PurePosixPath(urlparse(target.archive_url).path).name
    return len(
        list(directory.glob(f"{archive_name}.{method.lower()}.*.request.json"))
    )


def _successful_head_from_markers(
    *,
    evidence_root: Path,
    target: JamFullAcquisitionTarget,
    protocol: JamFullAcquisitionProtocol,
) -> HeadObservation | None:
    directory = target_directory(evidence_root, target)
    if not directory.exists():
        return None
    archive_name = PurePosixPath(urlparse(target.archive_url).path).name
    for path in sorted(
        directory.glob(f"{archive_name}.head.*.response.json"),
        reverse=True,
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version") == "aurex-jam-full-http-response-v1"
            and payload.get("protocol_evidence_hash")
            == protocol.protocol_evidence_hash
            and payload.get("family") == target.family
            and payload.get("month") == target.month
            and payload.get("method") == "HEAD"
            and payload.get("url") == target.archive_url
            and payload.get("status") == 200
            and payload.get("final_url") == target.archive_url
            and isinstance(payload.get("content_length"), int)
        ):
            return HeadObservation(
                content_length_bytes=payload["content_length"],
                request_count=_request_marker_count(
                    evidence_root=evidence_root,
                    target=target,
                    method="HEAD",
                ),
                accept_ranges=payload.get("accept_ranges", ""),
            )
    return None


def _validate_url(
    target: JamFullAcquisitionTarget,
    protocol: JamFullAcquisitionProtocol,
) -> None:
    if (
        target.reuse_verified_pilot_file
        or target.archive_url
        not in {
            item.archive_url
            for item in protocol.targets
            if not item.reuse_verified_pilot_file
        }
    ):
        raise ValueError("Jam full acquisition refused a non-network target")


def fetch_head(
    *,
    target: JamFullAcquisitionTarget,
    protocol: JamFullAcquisitionProtocol,
    evidence_root: Path,
) -> HeadObservation:
    existing = _successful_head_from_markers(
        evidence_root=evidence_root,
        target=target,
        protocol=protocol,
    )
    if existing is not None:
        return existing
    attempts_used = _request_marker_count(
        evidence_root=evidence_root,
        target=target,
        method="HEAD",
    )
    if attempts_used >= 3:
        raise ValueError(f"Jam full HEAD budget exhausted: {target.key}")
    opener = urllib.request.build_opener(RejectRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(attempts_used + 1, 4):
        _write_request_marker(
            evidence_root=evidence_root,
            target=target,
            protocol=protocol,
            method="HEAD",
            attempt=attempt,
        )
        _validate_url(target, protocol)
        request = urllib.request.Request(
            target.archive_url,
            headers={
                "Accept": "application/zip",
                "Accept-Encoding": "identity",
                "User-Agent": "Aurex-Jam-Full-Acquisition/1.0",
            },
            method="HEAD",
        )
        try:
            with opener.open(
                request,
                timeout=protocol.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                final_url = response.geturl()
                length_text = response.headers.get("Content-Length")
                accept_ranges = response.headers.get("Accept-Ranges", "")
                if final_url != target.archive_url:
                    raise RedirectRejectedError(
                        f"Jam full HEAD final URL changed: {final_url}"
                    )
                if status != 200 or length_text is None:
                    raise ValueError("Jam full HEAD response is incomplete")
                length = int(length_text)
                if length <= 0 or length > protocol.maximum_archive_bytes:
                    raise ValueError("Jam full HEAD exceeds archive byte limit")
                _write_response_marker(
                    evidence_root=evidence_root,
                    target=target,
                    protocol=protocol,
                    method="HEAD",
                    attempt=attempt,
                    status=status,
                    final_url=final_url,
                    content_length=length,
                    bytes_received=0,
                    outcome="PASS",
                    accept_ranges=accept_ranges,
                )
                return HeadObservation(length, attempt, accept_ranges)
        except urllib.error.HTTPError as exc:
            last_error = exc
            _write_response_marker(
                evidence_root=evidence_root,
                target=target,
                protocol=protocol,
                method="HEAD",
                attempt=attempt,
                status=exc.code,
                final_url=exc.geturl(),
                content_length=None,
                bytes_received=0,
                outcome=(
                    "TRANSIENT"
                    if exc.code in TRANSIENT_HTTP_STATUS
                    else "FAIL"
                ),
            )
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"Jam full HEAD HTTP {exc.code}: {target.key}"
                ) from exc
        except (OSError, TimeoutError) as exc:
            last_error = exc
            _write_response_marker(
                evidence_root=evidence_root,
                target=target,
                protocol=protocol,
                method="HEAD",
                attempt=attempt,
                status=None,
                final_url=target.archive_url,
                content_length=None,
                bytes_received=0,
                outcome="TRANSIENT",
            )
        if attempt < 3:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError(
        f"Jam full HEAD unresolved after three attempts: {target.key}"
    ) from last_error


def ensure_resource_capacity(
    *,
    evidence_root: Path,
    protocol: JamFullAcquisitionProtocol,
    heads: dict[tuple[str, str], HeadObservation],
) -> None:
    pilot_bytes = sum(
        target_archive_path(evidence_root, target).stat().st_size
        for target in protocol.targets
        if target.reuse_verified_pilot_file
    )
    total = pilot_bytes + sum(item.content_length_bytes for item in heads.values())
    if total > protocol.maximum_total_archive_bytes:
        raise ValueError("Jam full observed total exceeds compressed byte limit")
    evidence_root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(evidence_root).free
    missing_bytes = sum(
        observation.content_length_bytes
        for key, observation in heads.items()
        if not target_archive_path(
            evidence_root,
            next(target for target in protocol.targets if target.key == key),
        ).exists()
    )
    if free - missing_bytes < protocol.minimum_post_acquisition_free_disk_bytes:
        raise ValueError("Jam full post-acquisition free-disk gate failed")


def _parse_content_range(value: str, start: int, total: int) -> None:
    if not value.startswith(f"bytes {start}-") or not value.endswith(f"/{total}"):
        raise ValueError("Jam full acquisition Content-Range changed")


def ensure_verified_archive(
    *,
    target: JamFullAcquisitionTarget,
    head: HeadObservation,
    protocol: JamFullAcquisitionProtocol,
    evidence_root: Path,
) -> tuple[Path, int]:
    archive_path = target_archive_path(evidence_root, target)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive_path.with_name(f"{archive_path.name}.part")
    attempts_used = _request_marker_count(
        evidence_root=evidence_root,
        target=target,
        method="GET",
    )
    if archive_path.exists():
        if (
            archive_path.stat().st_size != head.content_length_bytes
            or file_sha256(archive_path) != target.published_archive_sha256
            or attempts_used < 1
        ):
            raise ValueError(f"Existing Jam full archive conflicts: {target.key}")
        return archive_path, attempts_used
    if temporary.exists() and temporary.stat().st_size > head.content_length_bytes:
        raise ValueError("Jam full partial file exceeds HEAD size")
    if attempts_used >= 3:
        raise ValueError(f"Jam full GET budget exhausted: {target.key}")
    opener = urllib.request.build_opener(RejectRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(attempts_used + 1, 4):
        offset = temporary.stat().st_size if temporary.exists() else 0
        _write_request_marker(
            evidence_root=evidence_root,
            target=target,
            protocol=protocol,
            method="GET",
            attempt=attempt,
            range_start=offset if offset else None,
        )
        headers = {
            "Accept": "application/zip",
            "Accept-Encoding": "identity",
            "User-Agent": "Aurex-Jam-Full-Acquisition/1.0",
        }
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(
            target.archive_url,
            headers=headers,
            method="GET",
        )
        _validate_url(target, protocol)
        bytes_this_attempt = 0
        try:
            with opener.open(
                request,
                timeout=protocol.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                final_url = response.geturl()
                if final_url != target.archive_url:
                    raise RedirectRejectedError(
                        f"Jam full GET final URL changed: {final_url}"
                    )
                if offset and status == 206:
                    _parse_content_range(
                        response.headers.get("Content-Range", ""),
                        offset,
                        head.content_length_bytes,
                    )
                    mode = "ab"
                elif status == 200:
                    mode = "wb"
                    offset = 0
                else:
                    raise RuntimeError(
                        f"Jam full GET HTTP {status}: {target.key}"
                    )
                with temporary.open(mode) as destination:
                    while True:
                        chunk = response.read(protocol.download_chunk_bytes)
                        if not chunk:
                            break
                        bytes_this_attempt += len(chunk)
                        if (
                            offset + bytes_this_attempt > head.content_length_bytes
                            or offset + bytes_this_attempt
                            > protocol.maximum_archive_bytes
                        ):
                            raise ValueError("Jam full GET exceeded byte limit")
                        destination.write(chunk)
                current_size = temporary.stat().st_size
                if current_size != head.content_length_bytes:
                    _write_response_marker(
                        evidence_root=evidence_root,
                        target=target,
                        protocol=protocol,
                        method="GET",
                        attempt=attempt,
                        status=status,
                        final_url=final_url,
                        content_length=head.content_length_bytes,
                        bytes_received=bytes_this_attempt,
                        outcome="TRANSIENT",
                    )
                    last_error = RuntimeError(
                        f"Jam full GET ended at {current_size} bytes"
                    )
                else:
                    digest = file_sha256(temporary)
                    if digest != target.published_archive_sha256:
                        raise ValueError(
                            f"Jam full checksum mismatch: {target.key}"
                        )
                    _write_response_marker(
                        evidence_root=evidence_root,
                        target=target,
                        protocol=protocol,
                        method="GET",
                        attempt=attempt,
                        status=status,
                        final_url=final_url,
                        content_length=head.content_length_bytes,
                        bytes_received=bytes_this_attempt,
                        outcome="PASS",
                    )
                    temporary.replace(archive_path)
                    return archive_path, attempt
        except urllib.error.HTTPError as exc:
            last_error = exc
            _write_response_marker(
                evidence_root=evidence_root,
                target=target,
                protocol=protocol,
                method="GET",
                attempt=attempt,
                status=exc.code,
                final_url=exc.geturl(),
                content_length=None,
                bytes_received=bytes_this_attempt,
                outcome=(
                    "TRANSIENT"
                    if exc.code in TRANSIENT_HTTP_STATUS
                    else "FAIL"
                ),
            )
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"Jam full GET HTTP {exc.code}: {target.key}"
                ) from exc
        except (OSError, TimeoutError) as exc:
            last_error = exc
            _write_response_marker(
                evidence_root=evidence_root,
                target=target,
                protocol=protocol,
                method="GET",
                attempt=attempt,
                status=None,
                final_url=target.archive_url,
                content_length=None,
                bytes_received=bytes_this_attempt,
                outcome="TRANSIENT",
            )
        if attempt < 3:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError(
        f"Jam full GET unresolved after three attempts: {target.key}"
    ) from last_error


def verify_reused_pilot_archive(
    *,
    target: JamFullAcquisitionTarget,
    evidence_root: Path,
) -> Path:
    path = target_archive_path(evidence_root, target)
    if (
        not path.exists()
        or file_sha256(path) != target.published_archive_sha256
    ):
        raise ValueError(f"Jam reused pilot archive changed: {target.key}")
    return path


def _normalized_header(row: list[str]) -> tuple[str, ...]:
    return tuple(item.strip().lower().replace(" ", "_") for item in row)


def _validate_zip_member(
    *,
    archive: zipfile.ZipFile,
    target: JamFullAcquisitionTarget,
    protocol: JamFullAcquisitionProtocol,
) -> tuple[zipfile.ZipInfo, list[str], int, int]:
    files = [member for member in archive.infolist() if not member.is_dir()]
    canonical = [
        member
        for member in files
        if member.filename == target.expected_csv_member
        and len(PurePosixPath(member.filename).parts) == 1
    ]
    if len(canonical) != 1:
        raise ValueError(f"Jam full ZIP member changed: {target.key}")
    reasons = []
    if len(files) != 1:
        reasons.append("ZIP_MEMBER_MATRIX_FAILED")
    selected = canonical[0]
    for member in files:
        member_path = PurePosixPath(member.filename)
        unix_mode = (member.external_attr >> 16) & 0o170000
        unsafe = (
            member_path.is_absolute()
            or len(member_path.parts) != 1
            or ".." in member_path.parts
            or "\\" in member.filename
            or member.flag_bits & 0x1
            or unix_mode == stat.S_IFLNK
            or member.CRC == 0
        )
        expansion_failed = (
            member.compress_size <= 0
            or member.file_size <= 0
            or member.file_size > protocol.maximum_member_uncompressed_bytes
            or member.file_size
            > member.compress_size * protocol.maximum_zip_expansion_ratio
        )
        if member is selected and unsafe:
            raise ValueError(f"Jam full canonical ZIP member is unsafe: {target.key}")
        if member is selected and expansion_failed:
            raise ValueError(
                f"Jam full canonical ZIP expansion failed: {target.key}"
            )
        if unsafe:
            reasons.append("ZIP_MEMBER_SAFETY_FAILED")
        if expansion_failed:
            reasons.append("ZIP_MEMBER_EXPANSION_FAILED")
    return (
        selected,
        sorted(set(reasons)),
        sum(member.compress_size for member in files),
        sum(member.file_size for member in files),
    )


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Jam full {field} is not decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"Jam full {field} is not finite")
    return parsed


def _parse_bool(value: str, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Jam full {field} is not boolean")


def _local_path(path: Path, evidence_root: Path) -> str:
    try:
        return path.relative_to(evidence_root).as_posix()
    except ValueError as exc:
        raise ValueError("Jam full archive is outside evidence root") from exc


def inspect_aggregate_trades(
    *,
    target: JamFullAcquisitionTarget,
    archive_path: Path,
    evidence_root: Path,
    protocol: JamFullAcquisitionProtocol,
    head_count: int,
    get_count: int,
) -> tuple[JamFullArchiveEvidence, dict[int, MinuteAggregate]]:
    archive_hash = file_sha256(archive_path)
    if archive_hash != target.published_archive_sha256:
        raise ValueError(f"Jam full aggregate hash changed: {target.month}")
    start_ms, end_ms, expected_minutes = month_bounds_ms(target.month)
    row_count = 0
    first_timestamp: int | None = None
    last_timestamp: int | None = None
    previous_timestamp: int | None = None
    previous_agg_id: int | None = None
    previous_last_trade_id: int | None = None
    gap_count = 0
    header_present = False
    minutes: dict[int, MinuteAggregate] = {}
    with zipfile.ZipFile(archive_path) as archive:
        member, zip_reasons, zip_compressed_bytes, zip_uncompressed_bytes = (
            _validate_zip_member(
            archive=archive,
            target=target,
            protocol=protocol,
        )
        )
        with archive.open(member) as binary:
            reader = csv.reader(
                io.TextIOWrapper(binary, encoding="utf-8", newline="")
            )
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("Jam full aggregate CSV is empty") from exc
            if len(first_row) != 8:
                raise ValueError("Jam full aggregate column count changed")
            try:
                int(first_row[0])
            except ValueError:
                header_present = True
                if _normalized_header(first_row) != JAM_FULL_AGGTRADES_HEADER:
                    raise ValueError("Jam full aggregate header changed") from None
                rows = reader
            else:
                rows = chain((first_row,), reader)
            for row in rows:
                if len(row) != 8:
                    raise ValueError("Jam full aggregate column count changed")
                try:
                    agg_id = int(row[0])
                    first_trade_id = int(row[3])
                    last_trade_id = int(row[4])
                    timestamp = int(row[5])
                except ValueError as exc:
                    raise ValueError("Jam full aggregate integer invalid") from exc
                price = _parse_decimal(row[1], "aggregate price")
                quantity = _parse_decimal(row[2], "aggregate quantity")
                buyer_maker = _parse_bool(row[6], "is_buyer_maker")
                _parse_bool(row[7], "is_best_match")
                if (
                    price <= 0
                    or quantity <= 0
                    or first_trade_id > last_trade_id
                    or not start_ms <= timestamp < end_ms
                    or (previous_agg_id is not None and agg_id <= previous_agg_id)
                    or (
                        previous_timestamp is not None
                        and timestamp < previous_timestamp
                    )
                    or (
                        previous_last_trade_id is not None
                        and first_trade_id <= previous_last_trade_id
                    )
                ):
                    raise ValueError("Jam full aggregate row invariant failed")
                if previous_agg_id is not None:
                    gap_count += agg_id - previous_agg_id - 1
                if previous_last_trade_id is not None:
                    gap_count += first_trade_id - previous_last_trade_id - 1
                minute = (timestamp - start_ms) // 60_000
                raw_count = last_trade_id - first_trade_id + 1
                quote = price * quantity
                existing = minutes.get(minute)
                if existing is None:
                    minutes[minute] = MinuteAggregate(
                        open_price=price,
                        high_price=price,
                        low_price=price,
                        close_price=price,
                        base_volume=quantity,
                        quote_volume=quote,
                        raw_trade_count=raw_count,
                        taker_buy_base_volume=(
                            quantity if not buyer_maker else Decimal(0)
                        ),
                        taker_buy_quote_volume=(
                            quote if not buyer_maker else Decimal(0)
                        ),
                    )
                else:
                    existing.high_price = max(existing.high_price, price)
                    existing.low_price = min(existing.low_price, price)
                    existing.close_price = price
                    existing.base_volume += quantity
                    existing.quote_volume += quote
                    existing.raw_trade_count += raw_count
                    if not buyer_maker:
                        existing.taker_buy_base_volume += quantity
                        existing.taker_buy_quote_volume += quote
                if first_timestamp is None:
                    first_timestamp = timestamp
                last_timestamp = timestamp
                previous_timestamp = timestamp
                previous_agg_id = agg_id
                previous_last_trade_id = last_trade_id
                row_count += 1
        crc_verified = True
    if row_count == 0 or first_timestamp is None or last_timestamp is None:
        raise ValueError("Jam full aggregate CSV has no rows")
    reasons = list(zip_reasons)
    if gap_count:
        reasons.append("AGGREGATE_OR_RAW_TRADE_ID_GAP")
    recorded_gap_count = gap_count + bool(zip_reasons)
    return (
        JamFullArchiveEvidence(
            family=target.family,
            month=target.month,
            archive_url=target.archive_url,
            local_path=_local_path(archive_path, evidence_root),
            reused_pilot_file=target.reuse_verified_pilot_file,
            archive_bytes=archive_path.stat().st_size,
            archive_sha256=archive_hash,
            published_archive_sha256=target.published_archive_sha256,
            checksum_verified=True,
            csv_member_name=member.filename,
            zip_compressed_bytes=zip_compressed_bytes,
            zip_uncompressed_bytes=zip_uncompressed_bytes,
            zip_crc_verified=crc_verified,
            column_count=8,
            header_present=header_present,
            row_count=row_count,
            first_timestamp_ms=first_timestamp,
            last_timestamp_ms=last_timestamp,
            unique_primary_key_count=row_count,
            duplicate_primary_key_count=0,
            out_of_order_count=0,
            gap_count=recorded_gap_count,
            unique_minute_count=len(minutes),
            expected_minute_count=expected_minutes,
            inspected_field_names=list(JAM_FULL_AGGTRADES_HEADER),
            head_request_count=head_count,
            payload_get_request_count=get_count,
            archive_pass=not reasons,
            reason_codes=reasons,
        ),
        minutes,
    )


def inspect_klines(
    *,
    target: JamFullAcquisitionTarget,
    archive_path: Path,
    evidence_root: Path,
    protocol: JamFullAcquisitionProtocol,
    head_count: int,
    get_count: int,
) -> tuple[JamFullArchiveEvidence, dict[int, KlineMinute]]:
    archive_hash = file_sha256(archive_path)
    if archive_hash != target.published_archive_sha256:
        raise ValueError(f"Jam full kline hash changed: {target.month}")
    start_ms, end_ms, expected_minutes = month_bounds_ms(target.month)
    rows_by_minute: dict[int, KlineMinute] = {}
    first_timestamp: int | None = None
    last_timestamp: int | None = None
    previous_open: int | None = None
    gap_count = 0
    row_invariant_failure_count = 0
    header_present = False
    row_count = 0
    tolerance = Decimal(protocol.decimal_reconciliation_tolerance)
    with zipfile.ZipFile(archive_path) as archive:
        member, zip_reasons, zip_compressed_bytes, zip_uncompressed_bytes = (
            _validate_zip_member(
            archive=archive,
            target=target,
            protocol=protocol,
        )
        )
        with archive.open(member) as binary:
            reader = csv.reader(
                io.TextIOWrapper(binary, encoding="utf-8", newline="")
            )
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("Jam full kline CSV is empty") from exc
            if len(first_row) != 12:
                raise ValueError("Jam full kline column count changed")
            try:
                int(first_row[0])
            except ValueError:
                header_present = True
                if _normalized_header(first_row) != JAM_FULL_KLINES_HEADER:
                    raise ValueError("Jam full kline header changed") from None
                rows = reader
            else:
                rows = chain((first_row,), reader)
            for row in rows:
                if len(row) != 12:
                    raise ValueError("Jam full kline column count changed")
                try:
                    open_time = int(row[0])
                    close_time = int(row[6])
                    raw_count = int(row[8])
                except ValueError as exc:
                    raise ValueError("Jam full kline integer invalid") from exc
                open_price = _parse_decimal(row[1], "kline open")
                high_price = _parse_decimal(row[2], "kline high")
                low_price = _parse_decimal(row[3], "kline low")
                close_price = _parse_decimal(row[4], "kline close")
                base_volume = _parse_decimal(row[5], "kline volume")
                quote_volume = _parse_decimal(row[7], "kline quote volume")
                taker_base = _parse_decimal(row[9], "kline taker base")
                taker_quote = _parse_decimal(row[10], "kline taker quote")
                _parse_decimal(row[11], "kline ignore")
                if not start_ms <= open_time < end_ms or (
                    open_time - start_ms
                ) % 60_000:
                    raise ValueError("Jam full kline timestamp structure failed")
                if (
                    close_time != open_time + 59_999
                    or min(open_price, high_price, low_price, close_price) <= 0
                    or high_price < max(open_price, low_price, close_price)
                    or low_price > min(open_price, high_price, close_price)
                    or min(base_volume, quote_volume, taker_base, taker_quote) < 0
                    or taker_base - base_volume > tolerance
                    or taker_quote - quote_volume > tolerance
                    or raw_count < 0
                ):
                    row_invariant_failure_count += 1
                minute = (open_time - start_ms) // 60_000
                if minute in rows_by_minute:
                    raise ValueError("Jam full kline primary key duplicated")
                if previous_open is not None:
                    if open_time <= previous_open:
                        raise ValueError("Jam full kline order changed")
                    gap_count += (open_time - previous_open) // 60_000 - 1
                rows_by_minute[minute] = KlineMinute(
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    base_volume=base_volume,
                    quote_volume=quote_volume,
                    raw_trade_count=raw_count,
                    taker_buy_base_volume=taker_base,
                    taker_buy_quote_volume=taker_quote,
                )
                if first_timestamp is None:
                    first_timestamp = open_time
                last_timestamp = open_time
                previous_open = open_time
                row_count += 1
        crc_verified = True
    if row_count == 0 or first_timestamp is None or last_timestamp is None:
        raise ValueError("Jam full kline CSV has no rows")
    reasons = list(zip_reasons)
    continuity_failed = (
        row_count != expected_minutes
        or len(rows_by_minute) != expected_minutes
        or gap_count
        or first_timestamp != start_ms
        or last_timestamp != end_ms - 60_000
    )
    if continuity_failed:
        reasons.append("KLINE_MONTH_CONTINUITY_FAILED")
    if row_invariant_failure_count:
        reasons.append("KLINE_ROW_INVARIANT_FAILED")
    return (
        JamFullArchiveEvidence(
            family=target.family,
            month=target.month,
            archive_url=target.archive_url,
            local_path=_local_path(archive_path, evidence_root),
            reused_pilot_file=target.reuse_verified_pilot_file,
            archive_bytes=archive_path.stat().st_size,
            archive_sha256=archive_hash,
            published_archive_sha256=target.published_archive_sha256,
            checksum_verified=True,
            csv_member_name=member.filename,
            zip_compressed_bytes=zip_compressed_bytes,
            zip_uncompressed_bytes=zip_uncompressed_bytes,
            zip_crc_verified=crc_verified,
            column_count=12,
            header_present=header_present,
            row_count=row_count,
            first_timestamp_ms=first_timestamp,
            last_timestamp_ms=last_timestamp,
            unique_primary_key_count=len(rows_by_minute),
            duplicate_primary_key_count=0,
            out_of_order_count=0,
            gap_count=(
                gap_count + row_invariant_failure_count + bool(zip_reasons)
            ),
            unique_minute_count=len(rows_by_minute),
            expected_minute_count=expected_minutes,
            inspected_field_names=list(JAM_FULL_KLINES_HEADER),
            head_request_count=head_count,
            payload_get_request_count=get_count,
            archive_pass=not reasons,
            reason_codes=reasons,
        ),
        rows_by_minute,
    )


def reconcile_month(
    *,
    month: str,
    aggregates: dict[int, MinuteAggregate],
    klines: dict[int, KlineMinute],
    protocol: JamFullAcquisitionProtocol,
) -> JamFullMonthReconciliation:
    expected_minutes = month_bounds_ms(month)[2]
    tolerance = Decimal(protocol.decimal_reconciliation_tolerance)
    outside = len(set(aggregates) - set(klines))
    raw_mismatch = 0
    ohlc_mismatch = 0
    base_mismatch = 0
    quote_mismatch = 0
    taker_base_mismatch = 0
    taker_quote_mismatch = 0
    for minute in range(expected_minutes):
        kline = klines.get(minute)
        if kline is None:
            # Archive continuity is evaluated separately. Keep reconciling the
            # complete acquisition so an official source gap is recorded rather
            # than terminating the remaining monthly census.
            continue
        aggregate = aggregates.get(minute)
        if aggregate is None:
            raw_mismatch += kline.raw_trade_count != 0
            base_mismatch += abs(kline.base_volume) > tolerance
            quote_mismatch += abs(kline.quote_volume) > tolerance
            taker_base_mismatch += (
                abs(kline.taker_buy_base_volume) > tolerance
            )
            taker_quote_mismatch += (
                abs(kline.taker_buy_quote_volume) > tolerance
            )
            continue
        raw_mismatch += aggregate.raw_trade_count != kline.raw_trade_count
        ohlc_mismatch += (
            aggregate.open_price != kline.open_price
            or aggregate.high_price != kline.high_price
            or aggregate.low_price != kline.low_price
            or aggregate.close_price != kline.close_price
        )
        base_mismatch += (
            abs(aggregate.base_volume - kline.base_volume) > tolerance
        )
        quote_mismatch += (
            abs(aggregate.quote_volume - kline.quote_volume) > tolerance
        )
        taker_base_mismatch += (
            abs(
                aggregate.taker_buy_base_volume
                - kline.taker_buy_base_volume
            )
            > tolerance
        )
        taker_quote_mismatch += (
            abs(
                aggregate.taker_buy_quote_volume
                - kline.taker_buy_quote_volume
            )
            > tolerance
        )
    mismatch_map = {
        "AGGREGATE_TRADE_OUTSIDE_KLINE": outside,
        "RAW_TRADE_COUNT_MISMATCH": raw_mismatch,
        "OHLC_MISMATCH": ohlc_mismatch,
        "BASE_VOLUME_MISMATCH": base_mismatch,
        "QUOTE_VOLUME_MISMATCH": quote_mismatch,
        "TAKER_BUY_BASE_VOLUME_MISMATCH": taker_base_mismatch,
        "TAKER_BUY_QUOTE_VOLUME_MISMATCH": taker_quote_mismatch,
    }
    reasons = [key for key, value in mismatch_map.items() if value]
    return JamFullMonthReconciliation(
        month=month,
        expected_minute_count=expected_minutes,
        compared_minute_count=expected_minutes,
        aggregate_trade_covered_minute_count=len(aggregates),
        empty_trade_minute_count=expected_minutes - len(aggregates),
        aggregate_trade_outside_kline_count=outside,
        raw_trade_count_mismatch_count=raw_mismatch,
        ohlc_mismatch_count=ohlc_mismatch,
        base_volume_mismatch_count=base_mismatch,
        quote_volume_mismatch_count=quote_mismatch,
        taker_buy_base_volume_mismatch_count=taker_base_mismatch,
        taker_buy_quote_volume_mismatch_count=taker_quote_mismatch,
        tolerance=protocol.decimal_reconciliation_tolerance,
        reconciliation_pass=not reasons,
        reason_codes=reasons,
    )


def inspect_month(
    *,
    month: str,
    protocol: JamFullAcquisitionProtocol,
    evidence_root: Path,
    heads: dict[tuple[str, str], HeadObservation],
    get_counts: dict[tuple[str, str], int],
) -> JamFullMonthEvidence:
    targets = {
        target.family: target
        for target in protocol.targets
        if target.month == month
    }
    aggregate_target = targets["aggTrades"]
    kline_target = targets["klines_1m"]
    aggregate_evidence, aggregates = inspect_aggregate_trades(
        target=aggregate_target,
        archive_path=target_archive_path(evidence_root, aggregate_target),
        evidence_root=evidence_root,
        protocol=protocol,
        head_count=(
            0
            if aggregate_target.reuse_verified_pilot_file
            else heads[aggregate_target.key].request_count
        ),
        get_count=get_counts[aggregate_target.key],
    )
    kline_evidence, klines = inspect_klines(
        target=kline_target,
        archive_path=target_archive_path(evidence_root, kline_target),
        evidence_root=evidence_root,
        protocol=protocol,
        head_count=(
            0
            if kline_target.reuse_verified_pilot_file
            else heads[kline_target.key].request_count
        ),
        get_count=get_counts[kline_target.key],
    )
    reconciliation = reconcile_month(
        month=month,
        aggregates=aggregates,
        klines=klines,
        protocol=protocol,
    )
    reasons = []
    if not aggregate_evidence.archive_pass:
        reasons.append("AGGREGATE_ARCHIVE_FAILED")
    if not kline_evidence.archive_pass:
        reasons.append("KLINE_ARCHIVE_FAILED")
    if not reconciliation.reconciliation_pass:
        reasons.append("CROSS_FAMILY_RECONCILIATION_FAILED")
    return JamFullMonthEvidence(
        month=month,
        aggregate_trades=aggregate_evidence,
        klines_1m=kline_evidence,
        reconciliation=reconciliation,
        month_pass=not reasons,
        reason_codes=reasons,
    )


def _checkpoint_payload(
    *,
    protocol: JamFullAcquisitionProtocol,
    months: list[JamFullMonthEvidence],
    updated_at: datetime,
) -> dict:
    payload = {
        "schema_version": "aurex-jam-full-acquisition-checkpoint-v1",
        "updated_at": updated_at.isoformat(),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "months": [
            item.model_dump(mode="json")
            for item in sorted(months, key=lambda item: item.month)
        ],
    }
    payload["checkpoint_evidence_hash"] = universe_evidence_hash(payload)
    return payload


def load_checkpoint(
    *,
    path: Path,
    protocol: JamFullAcquisitionProtocol,
) -> list[JamFullMonthEvidence]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    evidence_hash = payload.pop("checkpoint_evidence_hash", None)
    if (
        evidence_hash != universe_evidence_hash(payload)
        or payload.get("schema_version")
        != "aurex-jam-full-acquisition-checkpoint-v1"
        or payload.get("protocol_evidence_hash")
        != protocol.protocol_evidence_hash
        or payload.get("runner_contract_hash") != runner_contract_hash()
    ):
        raise ValueError("Jam full acquisition checkpoint audit failed")
    months = [
        JamFullMonthEvidence.model_validate(item)
        for item in payload.get("months", [])
    ]
    if (
        months != sorted(months, key=lambda item: item.month)
        or len({item.month for item in months}) != len(months)
    ):
        raise ValueError("Jam full acquisition checkpoint matrix changed")
    return months


def write_checkpoint(
    *,
    path: Path,
    protocol: JamFullAcquisitionProtocol,
    months: list[JamFullMonthEvidence],
) -> None:
    payload = _checkpoint_payload(
        protocol=protocol,
        months=months,
        updated_at=datetime.now(UTC),
    )
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale checkpoint output exists: {temporary}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def authoritative_result(
    *,
    generated_at: datetime,
    protocol: JamFullAcquisitionProtocol,
    months: list[JamFullMonthEvidence],
) -> JamFullAcquisitionResult:
    return build_jam_full_acquisition_result(
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        months=months,
        limitations=[
            (
                "The result covers BTCUSDT spot monthly aggregate trades and "
                "one-minute klines from January 2019 through December 2022 only."
            ),
            (
                "All archive identities, ZIP members, schemas, timestamps, row "
                "ordering, continuity, and monthly cross-family arithmetic were "
                "validated."
            ),
            (
                "January 2019 reused the independently audited pilot files without "
                "new network requests."
            ),
            (
                "Market values were inspected only for source-quality validation; "
                "no Jam feature, threshold, signal, trade, return, PnL, or ranking "
                "was calculated."
            ),
            (
                "The acquired 2019-2022 pool remains provisional no-return evidence "
                "and has not been assigned development or validation roles."
            ),
            (
                "Source consistency does not establish predictive edge, execution "
                "quality, capacity, or profitability."
            ),
            (
                "A pass permits only a separately authorized no-return feature "
                "specification stage."
            ),
            (
                "Feature implementation must be causally defined before any outcome "
                "window is opened."
            ),
            (
                "The consumed Jam v1.0.1 period remains unavailable for successor "
                "selection or retuning."
            ),
            (
                "This result creates no candidate, paper eligibility, Testnet "
                "strategy-order authority, production authority, live eligibility, "
                "or capital permission."
            ),
        ],
    )


def write_result(path: Path, result: JamFullAcquisitionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if JamFullAcquisitionResult.model_validate_json(serialized) != result:
        raise ValueError("Jam full acquisition result did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale result output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def collect_heads(
    *,
    protocol: JamFullAcquisitionProtocol,
    evidence_root: Path,
) -> dict[tuple[str, str], HeadObservation]:
    heads = {}
    network_targets = [
        target for target in protocol.targets if not target.reuse_verified_pilot_file
    ]
    for index, target in enumerate(network_targets, start=1):
        heads[target.key] = fetch_head(
            target=target,
            protocol=protocol,
            evidence_root=evidence_root,
        )
        if index % 10 == 0 or index == len(network_targets):
            print(f"HEAD progress {index}/{len(network_targets)}", flush=True)
    return heads


def run_acquisition(args) -> JamFullAcquisitionResult:
    if args.output.exists():
        raise ValueError("Jam full acquisition result exists; use --audit")
    protocol = load_protocol(args.protocol)
    for target in protocol.targets:
        if target.reuse_verified_pilot_file:
            verify_reused_pilot_archive(
                target=target,
                evidence_root=args.evidence_root,
            )
    heads = collect_heads(
        protocol=protocol,
        evidence_root=args.evidence_root,
    )
    ensure_resource_capacity(
        evidence_root=args.evidence_root,
        protocol=protocol,
        heads=heads,
    )
    months = load_checkpoint(path=args.checkpoint, protocol=protocol)
    completed_months = {item.month for item in months}
    get_counts: dict[tuple[str, str], int] = {
        target.key: 0
        for target in protocol.targets
        if target.reuse_verified_pilot_file
    }
    for target in protocol.targets:
        if not target.reuse_verified_pilot_file:
            get_counts[target.key] = _request_marker_count(
                evidence_root=args.evidence_root,
                target=target,
                method="GET",
            )
    for index, month in enumerate(JAM_FULL_MONTHS, start=1):
        if month in completed_months:
            print(f"RESUME month {month} already validated", flush=True)
            continue
        month_targets = [
            target for target in protocol.targets if target.month == month
        ]
        for target in month_targets:
            if target.reuse_verified_pilot_file:
                continue
            path, count = ensure_verified_archive(
                target=target,
                head=heads[target.key],
                protocol=protocol,
                evidence_root=args.evidence_root,
            )
            get_counts[target.key] = count
            print(
                f"GET {target.month}/{target.family} "
                f"bytes={path.stat().st_size} attempts={count}",
                flush=True,
            )
        evidence = inspect_month(
            month=month,
            protocol=protocol,
            evidence_root=args.evidence_root,
            heads=heads,
            get_counts=get_counts,
        )
        months.append(evidence)
        months.sort(key=lambda item: item.month)
        write_checkpoint(
            path=args.checkpoint,
            protocol=protocol,
            months=months,
        )
        print(
            f"VALIDATED month {month} pass={evidence.month_pass} "
            f"progress={index}/48",
            flush=True,
        )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        months=months,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"months={result.passed_month_count}/48 "
        f"bytes={result.total_archive_bytes} decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> JamFullAcquisitionResult:
    protocol = load_protocol(args.protocol)
    result = JamFullAcquisitionResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_full_acquisition_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.total_head_request_count > protocol.maximum_head_requests
        or result.total_payload_get_request_count
        > protocol.maximum_payload_get_requests
        or result.total_head_request_count
        + result.total_payload_get_request_count
        > protocol.maximum_requests_total
        or result.total_archive_bytes > protocol.maximum_total_archive_bytes
        or result.total_member_uncompressed_bytes
        > protocol.maximum_total_member_uncompressed_bytes
    ):
        raise ValueError("Jam full result lineage or resource audit failed")
    checkpoint_months = load_checkpoint(
        path=args.checkpoint,
        protocol=protocol,
    )
    if checkpoint_months != result.months:
        raise ValueError("Jam full result differs from checkpoint")
    for target in protocol.targets:
        path = target_archive_path(args.evidence_root, target)
        if (
            not path.exists()
            or file_sha256(path) != target.published_archive_sha256
        ):
            raise ValueError(f"Jam full raw archive changed: {target.key}")
    rebuilt = authoritative_result(
        generated_at=result.generated_at,
        protocol=protocol,
        months=checkpoint_months,
    )
    if rebuilt != result:
        raise ValueError("Jam full result is not reproducible")
    print(
        "PASS "
        f"jam_full_acquisition={result.result_evidence_hash} "
        f"months={result.passed_month_count}/48 "
        f"archives={result.total_archive_count} "
        f"bytes={result.total_archive_bytes} "
        f"returns={result.return_metrics_calculated} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or audit the frozen Jam 2019-2022 archive acquisition."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
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
            run_acquisition(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
