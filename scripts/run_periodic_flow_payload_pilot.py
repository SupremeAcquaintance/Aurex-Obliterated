from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_payload_pilot import (  # noqa: E402
    Q1_PAYLOAD_EXPECTED_MINUTES,
    PeriodicFlowArchiveEvidence,
    PeriodicFlowPairedClockEvidence,
    PeriodicFlowPayloadPilotProtocol,
    PeriodicFlowPayloadPilotResult,
    PeriodicFlowPayloadTarget,
    audit_periodic_flow_payload_protocol,
    audit_periodic_flow_payload_result,
    build_periodic_flow_payload_result,
)
from aurex.backtest_engine.periodic_flow_payload_transport_amendment import (  # noqa: E402
    PeriodicFlowPayloadTransportAmendment,
    audit_periodic_flow_transport_amendment,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_result_v1.json"
)
DEFAULT_TRANSPORT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_payload_transport_amendment_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
MONTH_START_MS = 1_577_836_800_000
MONTH_END_MS = 1_580_515_200_000
CSV_MEMBER_NAME = "BTCUSDT-aggTrades-2020-01.csv"
HEADER_ALIASES = {
    "agg_trade_id": "aggregate_trade_id",
    "transact_time": "timestamp",
    "is_buyer_maker": "buyer_was_maker",
    "is_best_match": "best_price_match",
}


class RedirectRejectedError(RuntimeError):
    pass


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRejectedError(f"Q1 payload redirect rejected: {newurl}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "run_periodic_flow_payload_pilot.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "periodic_flow_payload_pilot.py",
    )
    return universe_evidence_hash(
        {
            path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
            for path in paths
        }
    )


def load_protocol(path: Path) -> PeriodicFlowPayloadPilotProtocol:
    protocol = PeriodicFlowPayloadPilotProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_periodic_flow_payload_protocol(protocol):
        raise ValueError("Q1 payload pilot protocol hash failed")
    return protocol


def load_transport_amendment(
    path: Path,
    protocol_path: Path,
    protocol: PeriodicFlowPayloadPilotProtocol,
) -> PeriodicFlowPayloadTransportAmendment | None:
    if not path.exists():
        return None
    amendment = PeriodicFlowPayloadTransportAmendment.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_periodic_flow_transport_amendment(amendment)
        or amendment.parent_protocol_file_sha256 != file_sha256(protocol_path)
        or amendment.parent_protocol_evidence_hash
        != protocol.protocol_evidence_hash
    ):
        raise ValueError("Q1 transport amendment lineage changed")
    for marker_path, digest in amendment.marker_file_sha256.items():
        marker = Path(marker_path)
        if not marker.is_file() or file_sha256(marker) != digest:
            raise ValueError("Q1 frozen transport-denial marker changed")
    return amendment


def target_archive_path(
    evidence_root: Path,
    target: PeriodicFlowPayloadTarget,
) -> Path:
    return (
        evidence_root
        / "source_snapshots"
        / "q1_periodic_flow_payload_pilot_v1"
        / target.product
        / "BTCUSDT-aggTrades-2020-01.zip"
    )


def relative_archive_path(target: PeriodicFlowPayloadTarget) -> str:
    return (
        "source_snapshots/q1_periodic_flow_payload_pilot_v1/"
        f"{target.product}/BTCUSDT-aggTrades-2020-01.zip"
    )


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.binance.vision"
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith("/BTCUSDT-aggTrades-2020-01.zip")
    ):
        raise ValueError("Q1 payload URL left the frozen official allowlist")


def _marker_path(
    evidence_root: Path,
    target: PeriodicFlowPayloadTarget,
    marker_sequence: int,
    kind: str,
) -> Path:
    archive_path = target_archive_path(evidence_root, target)
    return archive_path.with_name(
        f"{archive_path.name}.get.{marker_sequence:02d}.{kind}.json"
    )


def _write_json_transactional(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"Q1 immutable request marker already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 request marker transaction exists: {temporary}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def request_count(evidence_root: Path, target: PeriodicFlowPayloadTarget) -> int:
    directory = target_archive_path(evidence_root, target).parent
    if not directory.exists():
        return 0
    return len(list(directory.glob("*.zip.get.*.request.json")))


def actual_request_count(
    evidence_root: Path,
    target: PeriodicFlowPayloadTarget,
    amendment: PeriodicFlowPayloadTransportAmendment | None,
) -> int:
    directory = target_archive_path(evidence_root, target).parent
    if not directory.exists():
        return 0
    count = 0
    for path in directory.glob("*.zip.get.*.request.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        marker_amendment = payload.get("amendment_evidence_hash")
        if amendment is None:
            count += marker_amendment is None
        else:
            count += marker_amendment == amendment.amendment_evidence_hash
    return count


def _write_request_marker(
    *,
    evidence_root: Path,
    target: PeriodicFlowPayloadTarget,
    protocol: PeriodicFlowPayloadPilotProtocol,
    amendment: PeriodicFlowPayloadTransportAmendment | None,
    attempt: int,
    marker_sequence: int,
) -> None:
    _write_json_transactional(
        _marker_path(evidence_root, target, marker_sequence, "request"),
        {
            "schema_version": "aurex-q1-payload-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "product": target.product,
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
            "marker_sequence": marker_sequence,
            "amendment_evidence_hash": (
                None if amendment is None else amendment.amendment_evidence_hash
            ),
            "range": None,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )


def _write_response_marker(
    *,
    evidence_root: Path,
    target: PeriodicFlowPayloadTarget,
    protocol: PeriodicFlowPayloadPilotProtocol,
    amendment: PeriodicFlowPayloadTransportAmendment | None,
    attempt: int,
    marker_sequence: int,
    status: int | None,
    final_url: str,
    bytes_received: int,
    outcome: str,
) -> None:
    _write_json_transactional(
        _marker_path(evidence_root, target, marker_sequence, "response"),
        {
            "schema_version": "aurex-q1-payload-http-response-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "product": target.product,
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
            "marker_sequence": marker_sequence,
            "amendment_evidence_hash": (
                None if amendment is None else amendment.amendment_evidence_hash
            ),
            "status": status,
            "final_url": final_url,
            "bytes_received": bytes_received,
            "outcome": outcome,
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )


def ensure_disk_capacity(
    evidence_root: Path,
    protocol: PeriodicFlowPayloadPilotProtocol,
) -> None:
    evidence_root.mkdir(parents=True, exist_ok=True)
    required = (
        protocol.maximum_total_archive_bytes
        + protocol.minimum_free_disk_bytes_after_download
    )
    if shutil.disk_usage(evidence_root).free < required:
        raise ValueError("Q1 payload pilot free-disk gate failed")


def ensure_verified_archive(
    *,
    target: PeriodicFlowPayloadTarget,
    protocol: PeriodicFlowPayloadPilotProtocol,
    amendment: PeriodicFlowPayloadTransportAmendment | None,
    evidence_root: Path,
) -> tuple[Path, int]:
    archive_path = target_archive_path(evidence_root, target)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    attempts_used = actual_request_count(evidence_root, target, amendment)
    if archive_path.exists():
        if (
            attempts_used < 1
            or archive_path.stat().st_size > protocol.maximum_archive_bytes_each
            or file_sha256(archive_path) != target.published_archive_sha256
        ):
            raise ValueError("Q1 existing archive lacks valid request lineage")
        return archive_path, attempts_used
    if attempts_used >= protocol.maximum_attempts_per_archive:
        raise ValueError(f"Q1 payload GET budget exhausted: {target.product}")

    temporary = archive_path.with_name(f"{archive_path.name}.part")
    opener = urllib.request.build_opener(RejectRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(
        attempts_used + 1,
        protocol.maximum_attempts_per_archive + 1,
    ):
        marker_sequence = request_count(evidence_root, target) + 1
        if temporary.exists():
            temporary.unlink()
        _write_request_marker(
            evidence_root=evidence_root,
            target=target,
            protocol=protocol,
            amendment=amendment,
            attempt=attempt,
            marker_sequence=marker_sequence,
        )
        _validate_url(target.archive_url)
        request = urllib.request.Request(
            target.archive_url,
            headers={
                "Accept": "application/zip",
                "Accept-Encoding": "identity",
                "User-Agent": "Aurex-Q1-Paired-Payload-Pilot/1.0",
            },
            method="GET",
        )
        received = 0
        try:
            with opener.open(
                request,
                timeout=protocol.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                final_url = response.geturl()
                if status != 200 or final_url != target.archive_url:
                    raise ValueError("Q1 payload response identity changed")
                content_length_text = response.headers.get("Content-Length")
                if content_length_text is not None:
                    content_length = int(content_length_text)
                    if (
                        content_length <= 0
                        or content_length > protocol.maximum_archive_bytes_each
                    ):
                        raise ValueError("Q1 payload Content-Length exceeds budget")
                digest = hashlib.sha256()
                with temporary.open("wb") as sink:
                    while chunk := response.read(1024 * 1024):
                        received += len(chunk)
                        if received > protocol.maximum_archive_bytes_each:
                            raise ValueError("Q1 payload stream exceeds byte budget")
                        sink.write(chunk)
                        digest.update(chunk)
                if content_length_text is not None and received != int(
                    content_length_text
                ):
                    raise ValueError("Q1 payload length does not reconcile")
                if digest.hexdigest() != target.published_archive_sha256:
                    raise ValueError("Q1 payload checksum does not reconcile")
                temporary.replace(archive_path)
                _write_response_marker(
                    evidence_root=evidence_root,
                    target=target,
                    protocol=protocol,
                    amendment=amendment,
                    attempt=attempt,
                    marker_sequence=marker_sequence,
                    status=status,
                    final_url=final_url,
                    bytes_received=received,
                    outcome="PASS",
                )
                return archive_path, attempt
        except urllib.error.HTTPError as exc:
            last_error = exc
            _write_response_marker(
                evidence_root=evidence_root,
                target=target,
                protocol=protocol,
                amendment=amendment,
                attempt=attempt,
                marker_sequence=marker_sequence,
                status=exc.code,
                final_url=exc.geturl(),
                bytes_received=received,
                outcome="TRANSIENT" if exc.code in TRANSIENT_HTTP_STATUS else "FAIL",
            )
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"Q1 payload HTTP {exc.code}: {target.product}"
                ) from exc
        except (OSError, TimeoutError) as exc:
            last_error = exc
            _write_response_marker(
                evidence_root=evidence_root,
                target=target,
                protocol=protocol,
                amendment=amendment,
                attempt=attempt,
                marker_sequence=marker_sequence,
                status=None,
                final_url=target.archive_url,
                bytes_received=received,
                outcome="TRANSIENT",
            )
        if attempt < protocol.maximum_attempts_per_archive:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError(
        f"Q1 payload unresolved after frozen attempts: {target.product}"
    ) from last_error


def _parse_bool(value: str, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Q1 payload invalid {field} boolean")


def _normalized_header(row: list[str]) -> tuple[str, ...]:
    return tuple(
        HEADER_ALIASES.get(value.strip().lower(), value.strip().lower())
        for value in row
    )


def _validate_member(
    archive: zipfile.ZipFile,
    target: PeriodicFlowPayloadTarget,
    protocol: PeriodicFlowPayloadPilotProtocol,
) -> zipfile.ZipInfo:
    members = archive.infolist()
    if len(members) != 1:
        raise ValueError("Q1 payload ZIP must contain exactly one member")
    member = members[0]
    parts = PurePosixPath(member.filename).parts
    if (
        member.is_dir()
        or member.filename != CSV_MEMBER_NAME
        or member.flag_bits & 0x1
        or not parts
        or ".." in parts
        or member.filename.startswith(("/", "\\"))
        or "\\" in member.filename
        or member.file_size <= 0
        or member.file_size > protocol.maximum_member_uncompressed_bytes_each
        or member.compress_size <= 0
        or member.file_size
        > member.compress_size * protocol.maximum_zip_expansion_ratio
    ):
        raise ValueError(f"Q1 payload unsafe ZIP member: {target.product}")
    return member


def _evidence_reasons(
    *,
    row_count: int,
    minute_coverage: Decimal,
    maximum_gap: int,
    aggregate_gap_count: int,
    aggregate_non_increasing_count: int,
    raw_span_invalid_count: int,
    raw_gap_count: int,
    timestamp_regression_count: int,
    buyer_values: tuple[bool, ...],
    product: str,
    best_values: tuple[bool, ...],
) -> tuple[str, ...]:
    reasons = []
    if row_count < 100_000:
        reasons.append("ROW_COUNT_BELOW_100000")
    if minute_coverage < Decimal("0.99"):
        reasons.append("MINUTE_COVERAGE_BELOW_0_99")
    if maximum_gap > 15:
        reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
    if aggregate_gap_count:
        reasons.append("AGGREGATE_TRADE_ID_GAP")
    if aggregate_non_increasing_count:
        reasons.append("AGGREGATE_TRADE_ID_NOT_STRICTLY_INCREASING")
    if raw_span_invalid_count:
        reasons.append("RAW_TRADE_SPAN_INVALID")
    if raw_gap_count:
        reasons.append("RAW_TRADE_ID_GAP")
    if timestamp_regression_count:
        reasons.append("TIMESTAMP_REGRESSION")
    if buyer_values != (False, True):
        reasons.append("BUYER_MAKER_DOMAIN_INCOMPLETE")
    if product == "SPOT" and not best_values:
        reasons.append("BEST_PRICE_MATCH_DOMAIN_EMPTY")
    return tuple(sorted(reasons))


def inspect_archive(
    *,
    target: PeriodicFlowPayloadTarget,
    protocol: PeriodicFlowPayloadPilotProtocol,
    archive_path: Path,
    evidence_root: Path,
    payload_get_attempt_count: int,
) -> tuple[PeriodicFlowArchiveEvidence, set[int]]:
    archive_hash = file_sha256(archive_path)
    if archive_hash != target.published_archive_sha256:
        raise ValueError(f"Q1 local checksum changed: {target.product}")

    row_count = 0
    first_timestamp = 0
    last_timestamp = 0
    first_aggregate_id = 0
    last_aggregate_id = 0
    previous_aggregate_id: int | None = None
    previous_raw_last_id: int | None = None
    previous_timestamp: int | None = None
    aggregate_gap_count = 0
    aggregate_non_increasing_count = 0
    raw_span_invalid_count = 0
    raw_gap_count = 0
    timestamp_regression_count = 0
    buyer_values: set[bool] = set()
    best_values: set[bool] = set()
    minute_indexes: set[int] = set()
    header_present = False

    with zipfile.ZipFile(archive_path) as archive:
        member = _validate_member(archive, target, protocol)
        with archive.open(member, "r") as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                reader = csv.reader(text)
                for row in reader:
                    if not row or all(not value.strip() for value in row):
                        raise ValueError("Q1 payload contains an empty CSV row")
                    if row_count == 0:
                        try:
                            int(row[0])
                        except ValueError as exc:
                            if _normalized_header(row) != target.expected_columns:
                                raise ValueError(
                                    f"Q1 payload header changed: {target.product}"
                                ) from exc
                            header_present = True
                            continue
                    if len(row) != target.expected_column_count:
                        raise ValueError(
                            f"Q1 payload column count changed: {target.product}"
                        )
                    if not row[1].strip() or not row[2].strip():
                        raise ValueError("Q1 excluded numeric field is lexically empty")
                    aggregate_id = int(row[0])
                    first_raw_id = int(row[3])
                    last_raw_id = int(row[4])
                    timestamp = int(row[5])
                    buyer_values.add(_parse_bool(row[6], "buyer_was_maker"))
                    if target.product == "SPOT":
                        best_values.add(_parse_bool(row[7], "best_price_match"))
                    if not MONTH_START_MS <= timestamp < MONTH_END_MS:
                        raise ValueError(
                            f"Q1 timestamp outside frozen month: {target.product}"
                        )
                    if first_raw_id > last_raw_id:
                        raw_span_invalid_count += 1
                    if previous_aggregate_id is not None:
                        if aggregate_id <= previous_aggregate_id:
                            aggregate_non_increasing_count += 1
                        if aggregate_id != previous_aggregate_id + 1:
                            aggregate_gap_count += 1
                    if (
                        previous_raw_last_id is not None
                        and first_raw_id != previous_raw_last_id + 1
                    ):
                        raw_gap_count += 1
                    if previous_timestamp is not None and timestamp < previous_timestamp:
                        timestamp_regression_count += 1
                    if row_count == 0:
                        first_timestamp = timestamp
                        first_aggregate_id = aggregate_id
                    last_timestamp = timestamp
                    last_aggregate_id = aggregate_id
                    previous_aggregate_id = aggregate_id
                    previous_raw_last_id = last_raw_id
                    previous_timestamp = timestamp
                    minute_indexes.add((timestamp - MONTH_START_MS) // 60_000)
                    row_count += 1

        if row_count == 0:
            raise ValueError(f"Q1 payload contains no data rows: {target.product}")
    ordered_minutes = sorted(minute_indexes)
    maximum_gap = max(
        (
            current - previous
            for previous, current in zip(
                ordered_minutes,
                ordered_minutes[1:],
                strict=False,
            )
        ),
        default=0,
    )
    coverage = Decimal(len(minute_indexes)) / Decimal(Q1_PAYLOAD_EXPECTED_MINUTES)
    buyer_tuple = tuple(sorted(buyer_values))
    best_tuple = tuple(sorted(best_values))
    reasons = _evidence_reasons(
        row_count=row_count,
        minute_coverage=coverage,
        maximum_gap=maximum_gap,
        aggregate_gap_count=aggregate_gap_count,
        aggregate_non_increasing_count=aggregate_non_increasing_count,
        raw_span_invalid_count=raw_span_invalid_count,
        raw_gap_count=raw_gap_count,
        timestamp_regression_count=timestamp_regression_count,
        buyer_values=buyer_tuple,
        product=target.product,
        best_values=best_tuple,
    )
    return (
        PeriodicFlowArchiveEvidence(
            product=target.product,
            archive_url=target.archive_url,
            local_path=relative_archive_path(target),
            archive_bytes=archive_path.stat().st_size,
            archive_sha256=archive_hash,
            published_archive_sha256=target.published_archive_sha256,
            zip_compressed_bytes=member.compress_size,
            zip_uncompressed_bytes=member.file_size,
            column_count=target.expected_column_count,
            header_present=header_present,
            row_count=row_count,
            first_timestamp_ms=first_timestamp,
            last_timestamp_ms=last_timestamp,
            unique_minute_count=len(minute_indexes),
            minute_coverage_fraction=coverage,
            maximum_event_gap_minutes=maximum_gap,
            first_aggregate_trade_id=first_aggregate_id,
            last_aggregate_trade_id=last_aggregate_id,
            aggregate_trade_id_gap_count=aggregate_gap_count,
            aggregate_trade_id_non_increasing_count=(
                aggregate_non_increasing_count
            ),
            raw_trade_span_invalid_count=raw_span_invalid_count,
            raw_trade_id_gap_count=raw_gap_count,
            timestamp_regression_count=timestamp_regression_count,
            buyer_maker_values_observed=buyer_tuple,
            best_price_match_values_observed=best_tuple,
            payload_get_attempt_count=payload_get_attempt_count,
            archive_pass=not reasons,
            reason_codes=reasons,
        ),
        minute_indexes,
    )


def paired_clock_evidence(
    spot_minutes: set[int],
    usd_m_minutes: set[int],
) -> PeriodicFlowPairedClockEvidence:
    paired = spot_minutes & usd_m_minutes
    union = spot_minutes | usd_m_minutes
    paired_month_fraction = Decimal(len(paired)) / Decimal(
        Q1_PAYLOAD_EXPECTED_MINUTES
    )
    reasons = (
        ("PAIRED_MONTH_COVERAGE_BELOW_0_99",)
        if paired_month_fraction < Decimal("0.99")
        else ()
    )
    return PeriodicFlowPairedClockEvidence(
        spot_unique_minute_count=len(spot_minutes),
        usd_m_unique_minute_count=len(usd_m_minutes),
        paired_minute_count=len(paired),
        union_minute_count=len(union),
        paired_month_coverage_fraction=paired_month_fraction,
        paired_union_overlap_fraction=Decimal(len(paired)) / Decimal(len(union)),
        spot_only_minute_count=len(spot_minutes - usd_m_minutes),
        usd_m_only_minute_count=len(usd_m_minutes - spot_minutes),
        paired_clock_pass=not reasons,
        reason_codes=reasons,
    )


def inspect_pair(
    *,
    protocol: PeriodicFlowPayloadPilotProtocol,
    evidence_root: Path,
    request_counts: dict[str, int],
) -> tuple[
    tuple[PeriodicFlowArchiveEvidence, ...],
    PeriodicFlowPairedClockEvidence,
]:
    evidence = []
    minutes = {}
    for target in protocol.targets:
        item, minute_set = inspect_archive(
            target=target,
            protocol=protocol,
            archive_path=target_archive_path(evidence_root, target),
            evidence_root=evidence_root,
            payload_get_attempt_count=request_counts[target.product],
        )
        evidence.append(item)
        minutes[target.product] = minute_set
    return tuple(evidence), paired_clock_evidence(
        minutes["SPOT"],
        minutes["USD_M_PERPETUAL"],
    )


def authoritative_result(
    *,
    generated_at: datetime,
    protocol_path: Path,
    protocol: PeriodicFlowPayloadPilotProtocol,
    archive_evidence: tuple[PeriodicFlowArchiveEvidence, ...],
    clock_evidence: PeriodicFlowPairedClockEvidence,
) -> PeriodicFlowPayloadPilotResult:
    return build_periodic_flow_payload_result(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        archive_evidence=archive_evidence,
        paired_clock_evidence=clock_evidence,
        payload_get_attempt_count=sum(
            item.payload_get_attempt_count for item in archive_evidence
        ),
        total_archive_bytes=sum(item.archive_bytes for item in archive_evidence),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes for item in archive_evidence
        ),
        limitations=(
            "A pass authorizes only a separate full-development payload acquisition protocol.",
            "Only January 2020 BTCUSDT Spot and USD-M structural compatibility was tested.",
            "Price and quantity values were neither parsed nor persisted.",
            "No feature, parameter, signal, candidate, trade, PnL, or return was calculated.",
            "Validation, future holdout, and forward outcomes were not accessed.",
            "USD-M perpetual data remains research-only and grants no futures order authority.",
            "Pine, paper, testnet strategy-order, production, and live authority remain false.",
            "Structural feasibility does not establish edge, reliability, or profitability.",
            "Real net profit remains zero dollars.",
        ),
    )


def write_result(path: Path, result: PeriodicFlowPayloadPilotResult) -> None:
    if path.exists():
        raise ValueError("Q1 payload pilot result already exists; use --check")
    serialized = result.model_dump_json(indent=2) + "\n"
    if PeriodicFlowPayloadPilotResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 payload result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 payload result transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_pilot(args) -> PeriodicFlowPayloadPilotResult:
    if args.output.exists():
        raise ValueError("Q1 payload pilot result exists; use --check")
    protocol = load_protocol(args.protocol)
    amendment = load_transport_amendment(
        args.transport_amendment,
        args.protocol,
        protocol,
    )
    ensure_disk_capacity(args.evidence_root, protocol)
    request_counts = {}
    for target in protocol.targets:
        path, count = ensure_verified_archive(
            target=target,
            protocol=protocol,
            amendment=amendment,
            evidence_root=args.evidence_root,
        )
        request_counts[target.product] = count
        print(
            f"VERIFIED product={target.product} bytes={path.stat().st_size} "
            f"attempts={count} sha256={file_sha256(path)}",
            flush=True,
        )
    if sum(request_counts.values()) > protocol.maximum_payload_get_attempts:
        raise ValueError("Q1 total payload GET budget exceeded")
    archive_evidence, clock_evidence = inspect_pair(
        protocol=protocol,
        evidence_root=args.evidence_root,
        request_counts=request_counts,
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol_path=args.protocol,
        protocol=protocol,
        archive_evidence=archive_evidence,
        clock_evidence=clock_evidence,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"paired_minutes={result.paired_clock_evidence.paired_minute_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def run_check(args) -> PeriodicFlowPayloadPilotResult:
    protocol = load_protocol(args.protocol)
    result = PeriodicFlowPayloadPilotResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_periodic_flow_payload_result(result)
        or result.protocol_file_sha256 != file_sha256(args.protocol)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Q1 payload result lineage changed")
    request_counts = {
        item.product: item.payload_get_attempt_count
        for item in result.archive_evidence
    }
    rebuilt_evidence, rebuilt_clock = inspect_pair(
        protocol=protocol,
        evidence_root=args.evidence_root,
        request_counts=request_counts,
    )
    expected = authoritative_result(
        generated_at=result.generated_at,
        protocol_path=args.protocol,
        protocol=protocol,
        archive_evidence=rebuilt_evidence,
        clock_evidence=rebuilt_clock,
    )
    if result != expected:
        raise ValueError("Q1 payload result is not reproducible from raw archives")
    print(
        f"PASS q1_payload_result={result.result_evidence_hash} "
        f"archives={len(result.archive_evidence)} "
        f"paired_minutes={result.paired_clock_evidence.paired_minute_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or independently check the Q1 paired payload pilot."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--transport-amendment",
        type=Path,
        default=DEFAULT_TRANSPORT_AMENDMENT,
    )
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
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
