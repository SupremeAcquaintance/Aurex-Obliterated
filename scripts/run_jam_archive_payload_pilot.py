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

from aurex.backtest_engine.jam_archive_payload_pilot import (
    JAM_PAYLOAD_PILOT_AGGTRADES_HEADER,
    JAM_PAYLOAD_PILOT_EXPECTED_MINUTES,
    JAM_PAYLOAD_PILOT_KLINES_HEADER,
    JamPayloadArchiveEvidence,
    JamPayloadHeadObservation,
    JamPayloadPilotProtocol,
    JamPayloadPilotResult,
    JamPayloadPilotTarget,
    JamPayloadReconciliationEvidence,
    audit_jam_payload_pilot_protocol,
    audit_jam_payload_pilot_result,
    build_jam_payload_pilot_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = Path(
    "data/evidence/jam_archive_payload_pilot_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_payload_pilot_result_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
PILOT_STORAGE_DIRECTORY = "jam_archive_payload_pilot_v1"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
MONTH_START_MS = 1_546_300_800_000
MONTH_END_MS = 1_548_979_200_000


class RedirectRejectedError(RuntimeError):
    pass


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRejectedError(
            f"Jam payload pilot rejected HTTP redirect {code}: {newurl}"
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
            / "freeze_jam_archive_payload_pilot_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_payload_pilot.py",
        ]
    )


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_jam_archive_payload_pilot.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_payload_pilot.py",
        ]
    )


def load_protocol(path: Path) -> JamPayloadPilotProtocol:
    protocol = JamPayloadPilotProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_payload_pilot_protocol(protocol)
        or protocol.builder_contract_hash != protocol_builder_hash()
    ):
        raise ValueError("Frozen Jam payload pilot protocol audit failed")
    return protocol


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_archive_url(url: str) -> None:
    target_urls = {target.archive_url for target in load_target_constants()}
    if url not in target_urls:
        raise ValueError("Jam payload pilot refused a non-protocol archive URL")


def load_target_constants() -> list[JamPayloadPilotTarget]:
    from aurex.backtest_engine.jam_archive_payload_pilot import (
        authoritative_payload_targets,
    )

    return authoritative_payload_targets()


def target_directory(
    evidence_root: Path,
    target: JamPayloadPilotTarget,
) -> Path:
    return (
        evidence_root
        / PILOT_STORAGE_DIRECTORY
        / target.symbol
        / target.month
        / target.family
    )


def target_archive_path(
    evidence_root: Path,
    target: JamPayloadPilotTarget,
) -> Path:
    return target_directory(evidence_root, target) / PurePosixPath(
        urlparse(target.archive_url).path
    ).name


def _marker_path(
    *,
    evidence_root: Path,
    target: JamPayloadPilotTarget,
    method: str,
    attempt: int,
    kind: str,
) -> Path:
    archive_name = PurePosixPath(
        urlparse(target.archive_url).path
    ).name
    return target_directory(evidence_root, target) / (
        f"{archive_name}.{method.lower()}.{attempt}.{kind}.json"
    )


def _write_json_transactional(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"Jam payload marker already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Jam payload marker exists: {temporary}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_request_marker(
    *,
    evidence_root: Path,
    target: JamPayloadPilotTarget,
    protocol: JamPayloadPilotProtocol,
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
            "schema_version": "aurex-jam-payload-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "family": target.family,
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
    target: JamPayloadPilotTarget,
    protocol: JamPayloadPilotProtocol,
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
            "schema_version": "aurex-jam-payload-http-response-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "family": target.family,
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
    target: JamPayloadPilotTarget,
    method: str,
) -> int:
    directory = target_directory(evidence_root, target)
    if not directory.exists():
        return 0
    archive_name = PurePosixPath(
        urlparse(target.archive_url).path
    ).name
    return len(
        list(directory.glob(f"{archive_name}.{method.lower()}.*.request.json"))
    )


def _successful_head_from_markers(
    *,
    evidence_root: Path,
    target: JamPayloadPilotTarget,
    protocol: JamPayloadPilotProtocol,
) -> JamPayloadHeadObservation | None:
    directory = target_directory(evidence_root, target)
    if not directory.exists():
        return None
    archive_name = PurePosixPath(
        urlparse(target.archive_url).path
    ).name
    for path in sorted(
        directory.glob(f"{archive_name}.head.*.response.json"),
        reverse=True,
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version")
            != "aurex-jam-payload-http-response-v1"
            or payload.get("protocol_evidence_hash")
            != protocol.protocol_evidence_hash
            or payload.get("family") != target.family
            or payload.get("method") != "HEAD"
            or payload.get("url") != target.archive_url
            or payload.get("status") != 200
            or payload.get("final_url") != target.archive_url
            or not isinstance(payload.get("content_length"), int)
        ):
            continue
        return JamPayloadHeadObservation(
            family=target.family,
            archive_url=target.archive_url,
            final_url=target.archive_url,
            observed_at=datetime.fromisoformat(payload["completed_at"]),
            http_status=200,
            content_length_bytes=payload["content_length"],
            accept_ranges=payload.get("accept_ranges", ""),
            request_attempt_count=_request_marker_count(
                evidence_root=evidence_root,
                target=target,
                method="HEAD",
            ),
            redirect_count=0,
        )
    return None


def fetch_head_observation(
    *,
    target: JamPayloadPilotTarget,
    protocol: JamPayloadPilotProtocol,
    evidence_root: Path,
) -> JamPayloadHeadObservation:
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
    last_error: Exception | None = None
    opener = urllib.request.build_opener(RejectRedirectHandler())
    for attempt in range(attempts_used + 1, protocol.maximum_retries_per_request + 2):
        _write_request_marker(
            evidence_root=evidence_root,
            target=target,
            protocol=protocol,
            method="HEAD",
            attempt=attempt,
        )
        _validate_archive_url(target.archive_url)
        request = urllib.request.Request(
            target.archive_url,
            headers={
                "Accept": "application/zip",
                "Accept-Encoding": "identity",
                "User-Agent": "Aurex-Jam-Payload-Pilot/1.0",
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
                content_length_text = response.headers.get("Content-Length")
                accept_ranges = response.headers.get("Accept-Ranges", "")
                if final_url != target.archive_url:
                    raise RedirectRejectedError(
                        f"Jam payload HEAD final URL changed: {final_url}"
                    )
                if status != 200 or content_length_text is None:
                    raise ValueError("Jam payload HEAD response is incomplete")
                content_length = int(content_length_text)
                if (
                    content_length <= 0
                    or content_length > protocol.maximum_archive_bytes
                ):
                    raise ValueError(
                        "Jam payload HEAD exceeds frozen archive byte limit"
                    )
                _write_response_marker(
                    evidence_root=evidence_root,
                    target=target,
                    protocol=protocol,
                    method="HEAD",
                    attempt=attempt,
                    status=status,
                    final_url=final_url,
                    content_length=content_length,
                    bytes_received=0,
                    outcome="PASS",
                    accept_ranges=accept_ranges,
                )
                response_path = _marker_path(
                    evidence_root=evidence_root,
                    target=target,
                    method="HEAD",
                    attempt=attempt,
                    kind="response",
                )
                response_payload = json.loads(
                    response_path.read_text(encoding="utf-8")
                )
                return JamPayloadHeadObservation(
                    family=target.family,
                    archive_url=target.archive_url,
                    final_url=final_url,
                    observed_at=datetime.fromisoformat(
                        response_payload["completed_at"]
                    ),
                    http_status=200,
                    content_length_bytes=content_length,
                    accept_ranges=accept_ranges,
                    request_attempt_count=attempt,
                    redirect_count=0,
                )
        except urllib.error.HTTPError as exc:
            status = exc.code
            last_error = exc
            _write_response_marker(
                evidence_root=evidence_root,
                target=target,
                protocol=protocol,
                method="HEAD",
                attempt=attempt,
                status=status,
                final_url=exc.geturl(),
                content_length=None,
                bytes_received=0,
                outcome="TRANSIENT" if status in TRANSIENT_HTTP_STATUS else "FAIL",
            )
            if status not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"Jam payload HEAD HTTP {status}: {target.family}"
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
        if attempt <= protocol.maximum_retries_per_request:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError(
        f"Jam payload HEAD unresolved after three attempts: {target.family}"
    ) from last_error


def ensure_disk_capacity(
    *,
    evidence_root: Path,
    observations: list[JamPayloadHeadObservation],
    protocol: JamPayloadPilotProtocol,
) -> None:
    total = sum(item.content_length_bytes for item in observations)
    if total > protocol.maximum_total_archive_bytes:
        raise ValueError("Jam payload pilot total archive size exceeds frozen limit")
    evidence_root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(evidence_root).free
    if free < protocol.minimum_free_disk_bytes + total:
        raise ValueError("Jam payload pilot free-disk gate failed")


def _parse_content_range(value: str, start: int, total: int) -> None:
    expected_prefix = f"bytes {start}-"
    if not value.startswith(expected_prefix) or not value.endswith(f"/{total}"):
        raise ValueError("Jam payload pilot Content-Range changed")


def ensure_verified_archive(
    *,
    target: JamPayloadPilotTarget,
    observation: JamPayloadHeadObservation,
    protocol: JamPayloadPilotProtocol,
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
            archive_path.stat().st_size != observation.content_length_bytes
            or file_sha256(archive_path) != target.published_archive_sha256
            or attempts_used < 1
        ):
            raise ValueError(f"Existing Jam payload archive conflicts: {target.family}")
        return archive_path, attempts_used
    if temporary.exists() and temporary.stat().st_size > observation.content_length_bytes:
        raise ValueError("Jam payload partial file exceeds HEAD size")
    if attempts_used >= 3:
        raise ValueError("Jam payload GET attempt budget is exhausted")

    opener = urllib.request.build_opener(RejectRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(attempts_used + 1, protocol.maximum_retries_per_request + 2):
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
            "User-Agent": "Aurex-Jam-Payload-Pilot/1.0",
        }
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(
            target.archive_url,
            headers=headers,
            method="GET",
        )
        _validate_archive_url(target.archive_url)
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
                        f"Jam payload GET final URL changed: {final_url}"
                    )
                if offset and status == 206:
                    _parse_content_range(
                        response.headers.get("Content-Range", ""),
                        offset,
                        observation.content_length_bytes,
                    )
                    mode = "ab"
                elif status == 200:
                    mode = "wb"
                    offset = 0
                else:
                    raise RuntimeError(
                        f"Jam payload GET HTTP {status}: {target.family}"
                    )
                with temporary.open(mode) as destination:
                    while True:
                        chunk = response.read(protocol.download_chunk_bytes)
                        if not chunk:
                            break
                        bytes_this_attempt += len(chunk)
                        if (
                            offset + bytes_this_attempt
                            > observation.content_length_bytes
                            or offset + bytes_this_attempt
                            > protocol.maximum_archive_bytes
                        ):
                            raise ValueError(
                                "Jam payload GET exceeded frozen byte limit"
                            )
                        destination.write(chunk)
                current_size = temporary.stat().st_size
                completed = current_size == observation.content_length_bytes
                if not completed:
                    _write_response_marker(
                        evidence_root=evidence_root,
                        target=target,
                        protocol=protocol,
                        method="GET",
                        attempt=attempt,
                        status=status,
                        final_url=final_url,
                        content_length=observation.content_length_bytes,
                        bytes_received=bytes_this_attempt,
                        outcome="TRANSIENT",
                    )
                    last_error = RuntimeError(
                        f"Jam payload GET ended at {current_size} bytes"
                    )
                else:
                    observed_sha256 = file_sha256(temporary)
                    if observed_sha256 != target.published_archive_sha256:
                        raise ValueError(
                            f"Jam payload checksum mismatch: {target.family}"
                        )
                    _write_response_marker(
                        evidence_root=evidence_root,
                        target=target,
                        protocol=protocol,
                        method="GET",
                        attempt=attempt,
                        status=status,
                        final_url=final_url,
                        content_length=observation.content_length_bytes,
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
                    f"Jam payload GET HTTP {exc.code}: {target.family}"
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
        if attempt <= protocol.maximum_retries_per_request:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError(
        f"Jam payload GET unresolved after three attempts: {target.family}"
    ) from last_error


def _normalized_header(row: list[str]) -> tuple[str, ...]:
    return tuple(item.strip().lower().replace(" ", "_") for item in row)


def _validate_zip_member(
    *,
    archive: zipfile.ZipFile,
    target: JamPayloadPilotTarget,
    protocol: JamPayloadPilotProtocol,
) -> zipfile.ZipInfo:
    files = [member for member in archive.infolist() if not member.is_dir()]
    if len(files) != 1 or files[0].filename != target.expected_csv_member:
        raise ValueError("Jam payload ZIP must contain its exact single CSV member")
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
        or member.CRC == 0
    ):
        raise ValueError("Jam payload ZIP member is unsafe")
    if (
        member.compress_size <= 0
        or member.file_size <= 0
        or member.file_size > protocol.maximum_member_uncompressed_bytes
        or member.file_size
        > member.compress_size * protocol.maximum_zip_expansion_ratio
    ):
        raise ValueError("Jam payload ZIP exceeds frozen expansion limits")
    return member


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Jam payload {field} is not decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"Jam payload {field} is not finite")
    return parsed


def _parse_bool(value: str, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Jam payload {field} is not boolean")


def _local_path(archive_path: Path, evidence_root: Path) -> str:
    try:
        return archive_path.relative_to(evidence_root).as_posix()
    except ValueError as exc:
        raise ValueError("Jam payload archive is outside evidence root") from exc


def inspect_aggregate_trades(
    *,
    target: JamPayloadPilotTarget,
    archive_path: Path,
    evidence_root: Path,
    protocol: JamPayloadPilotProtocol,
    request_count: int,
) -> tuple[JamPayloadArchiveEvidence, dict[int, MinuteAggregate]]:
    archive_sha256 = file_sha256(archive_path)
    if archive_sha256 != target.published_archive_sha256:
        raise ValueError("Jam aggregate-trade archive checksum changed")
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
        member = _validate_zip_member(
            archive=archive,
            target=target,
            protocol=protocol,
        )
        with archive.open(member) as binary:
            reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline=""))
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("Jam aggregate-trade CSV is empty") from exc
            if len(first_row) != 8:
                raise ValueError("Jam aggregate-trade column count changed")
            try:
                int(first_row[0])
            except ValueError:
                header_present = True
                if _normalized_header(first_row) != JAM_PAYLOAD_PILOT_AGGTRADES_HEADER:
                    raise ValueError("Jam aggregate-trade header changed") from None
                rows = reader
            else:
                rows = chain((first_row,), reader)
            for row in rows:
                if len(row) != 8:
                    raise ValueError("Jam aggregate-trade column count changed")
                try:
                    agg_id = int(row[0])
                    first_trade_id = int(row[3])
                    last_trade_id = int(row[4])
                    timestamp = int(row[5])
                except ValueError as exc:
                    raise ValueError(
                        "Jam aggregate-trade integer field is invalid"
                    ) from exc
                price = _parse_decimal(row[1], "aggregate price")
                quantity = _parse_decimal(row[2], "aggregate quantity")
                buyer_maker = _parse_bool(row[6], "is_buyer_maker")
                _parse_bool(row[7], "is_best_match")
                if (
                    price <= 0
                    or quantity <= 0
                    or first_trade_id > last_trade_id
                    or not MONTH_START_MS <= timestamp < MONTH_END_MS
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
                    raise ValueError("Jam aggregate-trade row invariant failed")
                if previous_agg_id is not None:
                    gap_count += agg_id - previous_agg_id - 1
                if previous_last_trade_id is not None:
                    gap_count += first_trade_id - previous_last_trade_id - 1
                minute = (timestamp - MONTH_START_MS) // 60_000
                raw_trade_count = last_trade_id - first_trade_id + 1
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
                        raw_trade_count=raw_trade_count,
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
                    existing.raw_trade_count += raw_trade_count
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
        zip_crc_verified = True

    if row_count == 0 or first_timestamp is None or last_timestamp is None:
        raise ValueError("Jam aggregate-trade CSV has no data rows")
    reasons = []
    if gap_count:
        reasons.append("AGGREGATE_OR_RAW_TRADE_ID_GAP")
    return (
        JamPayloadArchiveEvidence(
            family=target.family,
            archive_url=target.archive_url,
            local_path=_local_path(archive_path, evidence_root),
            archive_bytes=archive_path.stat().st_size,
            archive_sha256=archive_sha256,
            published_archive_sha256=target.published_archive_sha256,
            checksum_verified=True,
            csv_member_name=member.filename,
            zip_compressed_bytes=member.compress_size,
            zip_uncompressed_bytes=member.file_size,
            zip_crc_verified=zip_crc_verified,
            column_count=8,
            header_present=header_present,
            row_count=row_count,
            first_timestamp_ms=first_timestamp,
            last_timestamp_ms=last_timestamp,
            unique_primary_key_count=row_count,
            duplicate_primary_key_count=0,
            out_of_order_count=0,
            gap_count=gap_count,
            unique_minute_count=len(minutes),
            expected_minute_count=JAM_PAYLOAD_PILOT_EXPECTED_MINUTES,
            inspected_field_names=list(JAM_PAYLOAD_PILOT_AGGTRADES_HEADER),
            payload_get_request_count=request_count,
            archive_pass=not reasons,
            reason_codes=reasons,
        ),
        minutes,
    )


def inspect_klines(
    *,
    target: JamPayloadPilotTarget,
    archive_path: Path,
    evidence_root: Path,
    protocol: JamPayloadPilotProtocol,
    request_count: int,
) -> tuple[JamPayloadArchiveEvidence, dict[int, KlineMinute]]:
    archive_sha256 = file_sha256(archive_path)
    if archive_sha256 != target.published_archive_sha256:
        raise ValueError("Jam kline archive checksum changed")
    rows_by_minute: dict[int, KlineMinute] = {}
    first_timestamp: int | None = None
    last_timestamp: int | None = None
    previous_open_time: int | None = None
    gap_count = 0
    header_present = False
    row_count = 0
    tolerance = Decimal(protocol.decimal_reconciliation_tolerance)

    with zipfile.ZipFile(archive_path) as archive:
        member = _validate_zip_member(
            archive=archive,
            target=target,
            protocol=protocol,
        )
        with archive.open(member) as binary:
            reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline=""))
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("Jam kline CSV is empty") from exc
            if len(first_row) != 12:
                raise ValueError("Jam kline column count changed")
            try:
                int(first_row[0])
            except ValueError:
                header_present = True
                if _normalized_header(first_row) != JAM_PAYLOAD_PILOT_KLINES_HEADER:
                    raise ValueError("Jam kline header changed") from None
                rows = reader
            else:
                rows = chain((first_row,), reader)
            for row in rows:
                if len(row) != 12:
                    raise ValueError("Jam kline column count changed")
                try:
                    open_time = int(row[0])
                    close_time = int(row[6])
                    raw_trade_count = int(row[8])
                except ValueError as exc:
                    raise ValueError("Jam kline integer field is invalid") from exc
                open_price = _parse_decimal(row[1], "kline open")
                high_price = _parse_decimal(row[2], "kline high")
                low_price = _parse_decimal(row[3], "kline low")
                close_price = _parse_decimal(row[4], "kline close")
                base_volume = _parse_decimal(row[5], "kline volume")
                quote_volume = _parse_decimal(row[7], "kline quote volume")
                taker_base = _parse_decimal(row[9], "kline taker base")
                taker_quote = _parse_decimal(row[10], "kline taker quote")
                _parse_decimal(row[11], "kline ignore")
                if (
                    not MONTH_START_MS <= open_time < MONTH_END_MS
                    or (open_time - MONTH_START_MS) % 60_000
                    or close_time != open_time + 59_999
                    or min(
                        open_price,
                        high_price,
                        low_price,
                        close_price,
                    )
                    <= 0
                    or high_price < max(open_price, low_price, close_price)
                    or low_price > min(open_price, high_price, close_price)
                    or min(base_volume, quote_volume, taker_base, taker_quote) < 0
                    or taker_base - base_volume > tolerance
                    or taker_quote - quote_volume > tolerance
                    or raw_trade_count < 0
                ):
                    raise ValueError("Jam kline row invariant failed")
                minute = (open_time - MONTH_START_MS) // 60_000
                if minute in rows_by_minute:
                    raise ValueError("Jam kline primary key is duplicated")
                if previous_open_time is not None:
                    if open_time <= previous_open_time:
                        raise ValueError("Jam kline rows are out of order")
                    gap_count += (open_time - previous_open_time) // 60_000 - 1
                rows_by_minute[minute] = KlineMinute(
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    base_volume=base_volume,
                    quote_volume=quote_volume,
                    raw_trade_count=raw_trade_count,
                    taker_buy_base_volume=taker_base,
                    taker_buy_quote_volume=taker_quote,
                )
                if first_timestamp is None:
                    first_timestamp = open_time
                last_timestamp = open_time
                previous_open_time = open_time
                row_count += 1
        zip_crc_verified = True

    if row_count == 0 or first_timestamp is None or last_timestamp is None:
        raise ValueError("Jam kline CSV has no data rows")
    reasons = []
    if (
        row_count != JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
        or len(rows_by_minute) != JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
        or gap_count
        or first_timestamp != MONTH_START_MS
        or last_timestamp != MONTH_END_MS - 60_000
    ):
        reasons.append("KLINE_MONTH_CONTINUITY_FAILED")
    return (
        JamPayloadArchiveEvidence(
            family=target.family,
            archive_url=target.archive_url,
            local_path=_local_path(archive_path, evidence_root),
            archive_bytes=archive_path.stat().st_size,
            archive_sha256=archive_sha256,
            published_archive_sha256=target.published_archive_sha256,
            checksum_verified=True,
            csv_member_name=member.filename,
            zip_compressed_bytes=member.compress_size,
            zip_uncompressed_bytes=member.file_size,
            zip_crc_verified=zip_crc_verified,
            column_count=12,
            header_present=header_present,
            row_count=row_count,
            first_timestamp_ms=first_timestamp,
            last_timestamp_ms=last_timestamp,
            unique_primary_key_count=len(rows_by_minute),
            duplicate_primary_key_count=0,
            out_of_order_count=0,
            gap_count=gap_count,
            unique_minute_count=len(rows_by_minute),
            expected_minute_count=JAM_PAYLOAD_PILOT_EXPECTED_MINUTES,
            inspected_field_names=list(JAM_PAYLOAD_PILOT_KLINES_HEADER),
            payload_get_request_count=request_count,
            archive_pass=not reasons,
            reason_codes=reasons,
        ),
        rows_by_minute,
    )


def reconcile_archives(
    *,
    aggregate_minutes: dict[int, MinuteAggregate],
    kline_minutes: dict[int, KlineMinute],
    protocol: JamPayloadPilotProtocol,
) -> JamPayloadReconciliationEvidence:
    tolerance = Decimal(protocol.decimal_reconciliation_tolerance)
    outside = len(
        set(aggregate_minutes) - set(range(JAM_PAYLOAD_PILOT_EXPECTED_MINUTES))
    )
    raw_count_mismatches = 0
    ohlc_mismatches = 0
    base_mismatches = 0
    quote_mismatches = 0
    taker_base_mismatches = 0
    taker_quote_mismatches = 0
    for minute in range(JAM_PAYLOAD_PILOT_EXPECTED_MINUTES):
        kline = kline_minutes.get(minute)
        if kline is None:
            raise ValueError("Jam reconciliation lacks a frozen kline minute")
        aggregate = aggregate_minutes.get(minute)
        if aggregate is None:
            raw_count_mismatches += kline.raw_trade_count != 0
            base_mismatches += abs(kline.base_volume) > tolerance
            quote_mismatches += abs(kline.quote_volume) > tolerance
            taker_base_mismatches += (
                abs(kline.taker_buy_base_volume) > tolerance
            )
            taker_quote_mismatches += (
                abs(kline.taker_buy_quote_volume) > tolerance
            )
            continue
        raw_count_mismatches += (
            aggregate.raw_trade_count != kline.raw_trade_count
        )
        ohlc_mismatches += (
            aggregate.open_price != kline.open_price
            or aggregate.high_price != kline.high_price
            or aggregate.low_price != kline.low_price
            or aggregate.close_price != kline.close_price
        )
        base_mismatches += (
            abs(aggregate.base_volume - kline.base_volume) > tolerance
        )
        quote_mismatches += (
            abs(aggregate.quote_volume - kline.quote_volume) > tolerance
        )
        taker_base_mismatches += (
            abs(
                aggregate.taker_buy_base_volume
                - kline.taker_buy_base_volume
            )
            > tolerance
        )
        taker_quote_mismatches += (
            abs(
                aggregate.taker_buy_quote_volume
                - kline.taker_buy_quote_volume
            )
            > tolerance
        )
    reasons = []
    mismatches = {
        "AGGREGATE_TRADE_OUTSIDE_KLINE": outside,
        "RAW_TRADE_COUNT_MISMATCH": raw_count_mismatches,
        "OHLC_MISMATCH": ohlc_mismatches,
        "BASE_VOLUME_MISMATCH": base_mismatches,
        "QUOTE_VOLUME_MISMATCH": quote_mismatches,
        "TAKER_BUY_BASE_VOLUME_MISMATCH": taker_base_mismatches,
        "TAKER_BUY_QUOTE_VOLUME_MISMATCH": taker_quote_mismatches,
    }
    reasons.extend(key for key, value in mismatches.items() if value)
    return JamPayloadReconciliationEvidence(
        aggregate_trade_covered_minute_count=len(aggregate_minutes),
        empty_trade_minute_count=(
            JAM_PAYLOAD_PILOT_EXPECTED_MINUTES - len(aggregate_minutes)
        ),
        aggregate_trade_outside_kline_count=outside,
        raw_trade_count_mismatch_count=raw_count_mismatches,
        ohlc_mismatch_count=ohlc_mismatches,
        base_volume_mismatch_count=base_mismatches,
        quote_volume_mismatch_count=quote_mismatches,
        taker_buy_base_volume_mismatch_count=taker_base_mismatches,
        taker_buy_quote_volume_mismatch_count=taker_quote_mismatches,
        tolerance=protocol.decimal_reconciliation_tolerance,
        reconciliation_pass=not reasons,
        reason_codes=reasons,
    )


def inspect_and_reconcile(
    *,
    protocol: JamPayloadPilotProtocol,
    evidence_root: Path,
    request_counts: dict[str, int],
) -> tuple[
    list[JamPayloadArchiveEvidence],
    JamPayloadReconciliationEvidence,
]:
    targets = {target.family: target for target in protocol.targets}
    aggregate_evidence, aggregate_minutes = inspect_aggregate_trades(
        target=targets["aggTrades"],
        archive_path=target_archive_path(
            evidence_root,
            targets["aggTrades"],
        ),
        evidence_root=evidence_root,
        protocol=protocol,
        request_count=request_counts["aggTrades"],
    )
    kline_evidence, kline_minutes = inspect_klines(
        target=targets["klines_1m"],
        archive_path=target_archive_path(
            evidence_root,
            targets["klines_1m"],
        ),
        evidence_root=evidence_root,
        protocol=protocol,
        request_count=request_counts["klines_1m"],
    )
    if (
        aggregate_evidence.zip_uncompressed_bytes
        + kline_evidence.zip_uncompressed_bytes
        > protocol.maximum_total_member_uncompressed_bytes
    ):
        raise ValueError("Jam payload total member bytes exceed frozen limit")
    reconciliation = reconcile_archives(
        aggregate_minutes=aggregate_minutes,
        kline_minutes=kline_minutes,
        protocol=protocol,
    )
    return [aggregate_evidence, kline_evidence], reconciliation


def authoritative_result(
    *,
    generated_at: datetime,
    protocol: JamPayloadPilotProtocol,
    head_observations: list[JamPayloadHeadObservation],
    archive_evidence: list[JamPayloadArchiveEvidence],
    reconciliation: JamPayloadReconciliationEvidence,
) -> JamPayloadPilotResult:
    return build_jam_payload_pilot_result(
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        head_observations=head_observations,
        archive_evidence=archive_evidence,
        reconciliation=reconciliation,
        limitations=[
            (
                "This one-month pilot inspected only BTCUSDT January 2019 aggregate "
                "trades and one-minute klines."
            ),
            (
                "Published SHA-256 identities, ZIP safety, CSV schemas, timestamp "
                "continuity, row invariants, and cross-family arithmetic were checked."
            ),
            (
                "Market numeric fields were opened only for data-capability "
                "validation; no feature, threshold, signal, trade, return, or PnL "
                "was calculated."
            ),
            (
                "The pilot month was fixed as the earliest provisional month before "
                "payload access and was not selected for favorable behavior."
            ),
            (
                "One passing month cannot establish quality or continuity across all "
                "remaining 2019-2022 archives."
            ),
            (
                "Historical source consistency does not establish predictive edge, "
                "execution quality, capacity, or profitability."
            ),
            (
                "A pass permits only a separately authorized, frozen full historical "
                "archive acquisition protocol."
            ),
            (
                "This result creates no candidate, paper eligibility, Testnet "
                "strategy-order authority, production authority, live eligibility, "
                "or capital permission."
            ),
        ],
    )


def write_result(path: Path, result: JamPayloadPilotResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if JamPayloadPilotResult.model_validate_json(serialized) != result:
        raise ValueError("Jam payload pilot result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional result exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_pilot(args) -> JamPayloadPilotResult:
    if args.output.exists():
        raise ValueError("Jam payload pilot result exists; use --audit")
    protocol = load_protocol(args.protocol)
    observations = []
    for target in protocol.targets:
        observation = fetch_head_observation(
            target=target,
            protocol=protocol,
            evidence_root=args.evidence_root,
        )
        observations.append(observation)
        print(
            f"HEAD {target.family} bytes={observation.content_length_bytes} "
            f"attempts={observation.request_attempt_count}",
            flush=True,
        )
    observations.sort(key=lambda item: item.key)
    ensure_disk_capacity(
        evidence_root=args.evidence_root,
        observations=observations,
        protocol=protocol,
    )
    request_counts = {}
    observations_by_family = {item.family: item for item in observations}
    for target in protocol.targets:
        archive_path, request_count = ensure_verified_archive(
            target=target,
            observation=observations_by_family[target.family],
            protocol=protocol,
            evidence_root=args.evidence_root,
        )
        request_counts[target.family] = request_count
        print(
            f"GET {target.family} bytes={archive_path.stat().st_size} "
            f"attempts={request_count} sha256={file_sha256(archive_path)}",
            flush=True,
        )
    archive_evidence, reconciliation = inspect_and_reconcile(
        protocol=protocol,
        evidence_root=args.evidence_root,
        request_counts=request_counts,
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        head_observations=observations,
        archive_evidence=archive_evidence,
        reconciliation=reconciliation,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"bytes={result.total_archive_bytes} "
        f"reconciled={result.reconciliation.reconciliation_pass} "
        f"decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> JamPayloadPilotResult:
    protocol = load_protocol(args.protocol)
    result = JamPayloadPilotResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_payload_pilot_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.total_head_request_count > protocol.maximum_head_requests
        or result.total_payload_get_request_count
        > protocol.maximum_payload_get_requests
        or result.total_head_request_count
        + result.total_payload_get_request_count
        > protocol.maximum_requests_total
    ):
        raise ValueError("Jam payload pilot result lineage or budget audit failed")
    request_counts = {
        evidence.family: evidence.payload_get_request_count
        for evidence in result.archive_evidence
    }
    rebuilt_evidence, rebuilt_reconciliation = inspect_and_reconcile(
        protocol=protocol,
        evidence_root=args.evidence_root,
        request_counts=request_counts,
    )
    rebuilt = authoritative_result(
        generated_at=result.generated_at,
        protocol=protocol,
        head_observations=result.head_observations,
        archive_evidence=rebuilt_evidence,
        reconciliation=rebuilt_reconciliation,
    )
    if rebuilt != result:
        raise ValueError("Jam payload pilot result is not reproducible")
    rows_by_family = {
        item.family: item.row_count for item in result.archive_evidence
    }
    print(
        "PASS "
        f"jam_payload_pilot={result.result_evidence_hash} "
        f"archive_bytes={result.total_archive_bytes} "
        f"agg_rows={rows_by_family['aggTrades']} "
        f"kline_rows={rows_by_family['klines_1m']} "
        f"reconciled={result.reconciliation.reconciliation_pass} "
        f"returns={result.return_metrics_calculated} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen one-month Jam archive data-capability pilot."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
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
            run_pilot(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
