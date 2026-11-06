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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_payload_pilot import (  # noqa: E402
    PeriodicFlowPairedClockEvidence,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_evidence_v2 import (  # noqa: E402
    RawTradesPayloadPilotResultV2,
    audit_raw_payload_result_v2,
    build_raw_payload_result_v2,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    RAW_LOCAL_PATH,
    RAW_PAYLOAD_EXPECTED_MINUTES,
    RAW_TRADE_COLUMNS,
    SPOT_LOCAL_PATH,
    RawTradesArchiveEvidence,
    RawTradesPayloadPilotProtocol,
    RawTradesPayloadProtocolAudit,
    audit_raw_payload_protocol,
    audit_raw_payload_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.audit_periodic_flow_raw_trades_payload_protocol import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL_AUDIT,
)
from scripts.audit_periodic_flow_raw_trades_payload_protocol import (  # noqa: E402
    auditor_contract_hash as protocol_auditor_contract_hash,
)
from scripts.freeze_periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    MODULE_PATH,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_result_v2.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
RUNNER_PATH = Path("scripts/run_periodic_flow_raw_trades_payload_pilot.py")
MONTH_START_MS = 1_577_836_800_000
MONTH_END_MS = 1_580_515_200_000
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
HEADER_ALIASES = {
    "id": "trade_id",
    "trade_id": "trade_id",
    "price": "price",
    "qty": "quantity",
    "quantity": "quantity",
    "quoteqty": "quote_quantity",
    "quote_qty": "quote_quantity",
    "quote_quantity": "quote_quantity",
    "time": "timestamp",
    "timestamp": "timestamp",
    "is_buyer_maker": "buyer_was_maker",
    "buyer_was_maker": "buyer_was_maker",
}
SPOT_HEADER_ALIASES = {
    "agg_trade_id": "aggregate_trade_id",
    "aggregate_trade_id": "aggregate_trade_id",
    "price": "price",
    "quantity": "quantity",
    "first_trade_id": "first_trade_id",
    "last_trade_id": "last_trade_id",
    "transact_time": "timestamp",
    "timestamp": "timestamp",
    "is_buyer_maker": "buyer_was_maker",
    "buyer_was_maker": "buyer_was_maker",
    "is_best_match": "best_price_match",
    "best_price_match": "best_price_match",
}
SPOT_COLUMNS = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "buyer_was_maker",
    "best_price_match",
)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                MODULE_PATH.as_posix(): file_sha256(PROJECT_ROOT / MODULE_PATH),
                RUNNER_PATH.as_posix(): file_sha256(PROJECT_ROOT / RUNNER_PATH),
            }
        }
    )


def load_protocol(
    protocol_path: Path,
    protocol_audit_path: Path,
) -> tuple[RawTradesPayloadPilotProtocol, RawTradesPayloadProtocolAudit]:
    protocol = RawTradesPayloadPilotProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = RawTradesPayloadProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_raw_payload_protocol(protocol)
        or not audit_raw_payload_protocol_audit(audit)
        or protocol.builder_contract_hash != builder_contract_hash()
        or audit.protocol_file_sha256 != file_sha256(protocol_path)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.auditor_contract_hash != protocol_auditor_contract_hash()
        or not audit.authorizes_one_raw_payload
        or audit.authorizes_full_acquisition
        or audit.authorizes_outcomes
        or audit.authorizes_trading
        or protocol.price_or_quantity_parsing_permitted
        or protocol.return_calculation_permitted
        or protocol.paper_operation_permitted
        or protocol.testnet_strategy_orders_permitted
        or protocol.live_permitted
    ):
        raise ValueError("Frozen Q1 raw payload protocol or audit is not intact")
    return protocol, audit


def raw_archive_path(evidence_root: Path) -> Path:
    return evidence_root / RAW_LOCAL_PATH


def spot_archive_path(evidence_root: Path) -> Path:
    return evidence_root / SPOT_LOCAL_PATH


def marker_directory(evidence_root: Path) -> Path:
    return (
        evidence_root
        / "source_snapshots"
        / "q1_periodic_flow_raw_trades_payload_pilot_v1"
        / "request_markers"
    )


def write_marker(
    *,
    evidence_root: Path,
    protocol: RawTradesPayloadPilotProtocol,
    attempt: int,
    status: int | None,
    bytes_received: int,
    outcome: str,
) -> None:
    directory = marker_directory(evidence_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"attempt-{attempt:02d}.json"
    if path.exists():
        raise ValueError(f"Raw payload request marker already exists: {path}")
    payload = {
        "schema_version": "aurex-q1-raw-payload-request-marker-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "archive_url": protocol.target.archive_url,
        "attempt": attempt,
        "http_status": status,
        "bytes_received": bytes_received,
        "outcome": outcome,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def existing_attempt_count(evidence_root: Path) -> int:
    directory = marker_directory(evidence_root)
    return len(tuple(directory.glob("attempt-*.json"))) if directory.exists() else 0


def request_marker_manifest(
    *,
    evidence_root: Path,
    protocol: RawTradesPayloadPilotProtocol,
) -> tuple[str, int, tuple[dict, ...]]:
    directory = marker_directory(evidence_root)
    paths = tuple(sorted(directory.glob("attempt-*.json")))
    records = tuple(json.loads(path.read_text(encoding="utf-8")) for path in paths)
    if (
        not records
        or len(records) > protocol.maximum_attempts_per_archive
        or tuple(item.get("attempt") for item in records)
        != tuple(range(1, len(records) + 1))
        or any(
            item.get("protocol_evidence_hash") != protocol.protocol_evidence_hash
            or item.get("archive_url") != protocol.target.archive_url
            for item in records
        )
        or records[-1].get("outcome") != "PASS"
        or sum(item.get("outcome") == "PASS" for item in records) != 1
        or int(records[-1].get("bytes_received", 0)) <= 0
    ):
        raise ValueError("Q1 raw payload request-marker lineage changed")
    return (
        universe_evidence_hash({"markers": records}),
        len(records),
        records,
    )


def ensure_raw_archive(
    *,
    protocol: RawTradesPayloadPilotProtocol,
    evidence_root: Path,
) -> tuple[Path, int]:
    target = protocol.target
    destination = raw_archive_path(evidence_root)
    if destination.exists():
        digest = file_sha256(destination)
        if digest != target.published_archive_sha256:
            raise ValueError("Existing Q1 raw payload archive checksum changed")
        attempts = existing_attempt_count(evidence_root)
        if not 1 <= attempts <= protocol.maximum_attempts_per_archive:
            raise ValueError("Existing raw archive has no bounded request evidence")
        return destination, attempts
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(f"{destination.name}.part")
    if part.exists():
        raise ValueError(f"Stale raw payload transaction exists: {part}")
    completed_attempts = existing_attempt_count(evidence_root)
    if completed_attempts >= protocol.maximum_attempts_per_archive:
        raise ValueError("Raw payload request budget is already exhausted")
    opener = urllib.request.build_opener(NoRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(
        completed_attempts + 1,
        protocol.maximum_attempts_per_archive + 1,
    ):
        received = 0
        status: int | None = None
        try:
            free = shutil.disk_usage(evidence_root.resolve()).free
            if free < (
                protocol.maximum_archive_bytes
                + protocol.minimum_free_disk_bytes_after_download
            ):
                raise ValueError("Insufficient free disk for frozen raw payload budget")
            request = urllib.request.Request(
                target.archive_url,
                headers={
                    "Accept": "application/zip",
                    "User-Agent": "Aurex-Q1-Raw-Trades-Payload-Pilot/1.0",
                },
                method="GET",
            )
            with opener.open(request, timeout=protocol.request_timeout_seconds) as response:
                status = response.getcode()
                if status != 200 or response.geturl() != target.archive_url:
                    raise RuntimeError("Raw payload HTTP identity changed")
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > protocol.maximum_archive_bytes:
                    raise ValueError("Raw payload Content-Length exceeds frozen budget")
                digest = hashlib.sha256()
                with part.open("xb") as output:
                    while chunk := response.read(1024 * 1024):
                        received += len(chunk)
                        if received > protocol.maximum_archive_bytes:
                            raise ValueError("Raw payload bytes exceed frozen budget")
                        digest.update(chunk)
                        output.write(chunk)
            if digest.hexdigest() != target.published_archive_sha256:
                raise ValueError("Downloaded raw payload checksum mismatch")
            part.replace(destination)
            write_marker(
                evidence_root=evidence_root,
                protocol=protocol,
                attempt=attempt,
                status=status,
                bytes_received=received,
                outcome="PASS",
            )
            return destination, attempt
        except urllib.error.HTTPError as exc:
            last_error = exc
            if part.exists():
                part.unlink()
            write_marker(
                evidence_root=evidence_root,
                protocol=protocol,
                attempt=attempt,
                status=exc.code,
                bytes_received=received,
                outcome=(
                    "TRANSIENT" if exc.code in TRANSIENT_HTTP_STATUS else "FAIL"
                ),
            )
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(f"Raw payload HTTP {exc.code}") from exc
        except (OSError, TimeoutError) as exc:
            last_error = exc
            if part.exists():
                part.unlink()
            write_marker(
                evidence_root=evidence_root,
                protocol=protocol,
                attempt=attempt,
                status=status,
                bytes_received=received,
                outcome="TRANSIENT",
            )
        if attempt < protocol.maximum_attempts_per_archive:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError("Raw payload unresolved after frozen attempts") from last_error


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("Q1 raw payload invalid buyer-maker boolean")


def normalized_header(row: list[str], aliases: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        aliases.get(value.strip().lower(), value.strip().lower()) for value in row
    )


def validate_member(
    archive: zipfile.ZipFile,
    *,
    expected_name: str,
    maximum_bytes: int,
    maximum_ratio: int,
) -> zipfile.ZipInfo:
    members = archive.infolist()
    if len(members) != 1:
        raise ValueError("Q1 raw payload ZIP must contain exactly one member")
    member = members[0]
    parts = PurePosixPath(member.filename).parts
    if (
        member.is_dir()
        or member.filename != expected_name
        or member.flag_bits & 0x1
        or not parts
        or ".." in parts
        or member.filename.startswith(("/", "\\"))
        or "\\" in member.filename
        or member.file_size <= 0
        or member.file_size > maximum_bytes
        or member.compress_size <= 0
        or member.file_size > member.compress_size * maximum_ratio
    ):
        raise ValueError("Q1 raw payload ZIP member is unsafe or changed")
    return member


def raw_evidence_reasons(
    *,
    row_count: int,
    minute_coverage_fraction: Decimal,
    maximum_event_gap_minutes: int,
    trade_id_non_increasing_count: int,
    trade_id_duplicate_count: int,
    skipped_trade_id_fraction: Decimal,
    maximum_single_skipped_trade_id_count: int,
    timestamp_regression_count: int,
    buyer_maker_values_observed: tuple[bool, ...],
) -> tuple[str, ...]:
    reasons = []
    if row_count < 100_000:
        reasons.append("ROW_COUNT_BELOW_100000")
    if minute_coverage_fraction < Decimal("0.99"):
        reasons.append("MINUTE_COVERAGE_BELOW_0_99")
    if maximum_event_gap_minutes > 15:
        reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
    if trade_id_non_increasing_count:
        reasons.append("TRADE_ID_NOT_STRICTLY_INCREASING")
    if trade_id_duplicate_count:
        reasons.append("TRADE_ID_DUPLICATE")
    if skipped_trade_id_fraction > Decimal("0.001"):
        reasons.append("SKIPPED_TRADE_ID_FRACTION_EXCEEDS_0_001")
    if maximum_single_skipped_trade_id_count > 100:
        reasons.append("SINGLE_SKIPPED_TRADE_ID_COUNT_EXCEEDS_100")
    if timestamp_regression_count:
        reasons.append("TIMESTAMP_REGRESSION")
    if buyer_maker_values_observed != (False, True):
        reasons.append("BUYER_MAKER_DOMAIN_INCOMPLETE")
    return tuple(sorted(reasons))


def inspect_raw_archive(
    *,
    protocol: RawTradesPayloadPilotProtocol,
    archive_path: Path,
    payload_get_attempt_count: int,
) -> tuple[RawTradesArchiveEvidence, set[int]]:
    if file_sha256(archive_path) != protocol.target.published_archive_sha256:
        raise ValueError("Q1 raw payload local checksum changed")
    row_count = 0
    first_timestamp = 0
    last_timestamp = 0
    first_trade_id = 0
    last_trade_id = 0
    previous_trade_id: int | None = None
    previous_timestamp: int | None = None
    non_increasing = 0
    duplicates = 0
    forward_gaps = 0
    skipped_ids = 0
    max_single_skipped = 0
    timestamp_regressions = 0
    buyer_values: set[bool] = set()
    minute_indexes: set[int] = set()
    header_present = False

    with zipfile.ZipFile(archive_path) as archive:
        member = validate_member(
            archive,
            expected_name=protocol.target.expected_member_name,
            maximum_bytes=protocol.maximum_member_uncompressed_bytes,
            maximum_ratio=protocol.maximum_zip_expansion_ratio,
        )
        with archive.open(member, "r") as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                for row in csv.reader(text):
                    if not row or all(not value.strip() for value in row):
                        raise ValueError("Q1 raw payload contains an empty CSV row")
                    if row_count == 0:
                        try:
                            int(row[0])
                        except ValueError as exc:
                            if normalized_header(row, HEADER_ALIASES) != RAW_TRADE_COLUMNS:
                                raise ValueError("Q1 raw payload header changed") from exc
                            header_present = True
                            continue
                    if len(row) != 6:
                        raise ValueError("Q1 raw payload column count changed")
                    if any(not row[index].strip() for index in (1, 2, 3)):
                        raise ValueError("Q1 excluded numeric field is lexically empty")
                    trade_id = int(row[0])
                    timestamp = int(row[4])
                    buyer_values.add(parse_bool(row[5]))
                    if not MONTH_START_MS <= timestamp < MONTH_END_MS:
                        raise ValueError("Q1 raw payload timestamp outside frozen month")
                    if previous_trade_id is not None:
                        if trade_id <= previous_trade_id:
                            non_increasing += 1
                        if trade_id == previous_trade_id:
                            duplicates += 1
                        if trade_id > previous_trade_id + 1:
                            skipped = trade_id - previous_trade_id - 1
                            forward_gaps += 1
                            skipped_ids += skipped
                            max_single_skipped = max(max_single_skipped, skipped)
                    if previous_timestamp is not None and timestamp < previous_timestamp:
                        timestamp_regressions += 1
                    if row_count == 0:
                        first_trade_id = trade_id
                        first_timestamp = timestamp
                    last_trade_id = trade_id
                    last_timestamp = timestamp
                    previous_trade_id = trade_id
                    previous_timestamp = timestamp
                    minute_indexes.add((timestamp - MONTH_START_MS) // 60_000)
                    row_count += 1
    if row_count == 0:
        raise ValueError("Q1 raw payload contains no data rows")
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
    span = last_trade_id - first_trade_id + 1
    skipped_fraction = Decimal(skipped_ids) / Decimal(span)
    coverage = Decimal(len(minute_indexes)) / Decimal(
        RAW_PAYLOAD_EXPECTED_MINUTES
    )
    buyer_tuple = tuple(sorted(buyer_values))
    reasons = raw_evidence_reasons(
        row_count=row_count,
        minute_coverage_fraction=coverage,
        maximum_event_gap_minutes=maximum_gap,
        trade_id_non_increasing_count=non_increasing,
        trade_id_duplicate_count=duplicates,
        skipped_trade_id_fraction=skipped_fraction,
        maximum_single_skipped_trade_id_count=max_single_skipped,
        timestamp_regression_count=timestamp_regressions,
        buyer_maker_values_observed=buyer_tuple,
    )
    evidence = RawTradesArchiveEvidence(
        archive_bytes=archive_path.stat().st_size,
        zip_compressed_bytes=member.compress_size,
        zip_uncompressed_bytes=member.file_size,
        header_present=header_present,
        row_count=row_count,
        first_timestamp_ms=first_timestamp,
        last_timestamp_ms=last_timestamp,
        unique_minute_count=len(minute_indexes),
        minute_coverage_fraction=coverage,
        maximum_event_gap_minutes=maximum_gap,
        first_trade_id=first_trade_id,
        last_trade_id=last_trade_id,
        trade_id_non_increasing_count=non_increasing,
        trade_id_duplicate_count=duplicates,
        forward_gap_count=forward_gaps,
        skipped_trade_id_count=skipped_ids,
        skipped_trade_id_fraction=skipped_fraction,
        maximum_single_skipped_trade_id_count=max_single_skipped,
        timestamp_regression_count=timestamp_regressions,
        buyer_maker_values_observed=buyer_tuple,
        payload_get_attempt_count=payload_get_attempt_count,
        archive_pass=not reasons,
        reason_codes=reasons,
    )
    return evidence, minute_indexes


def inspect_spot_minutes(
    *,
    protocol: RawTradesPayloadPilotProtocol,
    evidence_root: Path,
) -> set[int]:
    reference = protocol.qualified_spot_reference
    path = spot_archive_path(evidence_root)
    if file_sha256(path) != reference.archive_sha256:
        raise ValueError("Qualified Spot archive checksum changed")
    minutes: set[int] = set()
    row_count = 0
    first_timestamp = 0
    last_timestamp = 0
    with zipfile.ZipFile(path) as archive:
        member = validate_member(
            archive,
            expected_name="BTCUSDT-aggTrades-2020-01.csv",
            maximum_bytes=10_000_000_000,
            maximum_ratio=100,
        )
        with archive.open(member, "r") as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                for row in csv.reader(text):
                    if row_count == 0:
                        try:
                            int(row[0])
                        except ValueError as exc:
                            if normalized_header(row, SPOT_HEADER_ALIASES) != SPOT_COLUMNS:
                                raise ValueError("Qualified Spot header changed") from exc
                            continue
                    if len(row) != 8:
                        raise ValueError("Qualified Spot column count changed")
                    timestamp = int(row[5])
                    if not MONTH_START_MS <= timestamp < MONTH_END_MS:
                        raise ValueError("Qualified Spot timestamp outside frozen month")
                    if row_count == 0:
                        first_timestamp = timestamp
                    last_timestamp = timestamp
                    minutes.add((timestamp - MONTH_START_MS) // 60_000)
                    row_count += 1
    if (
        row_count != reference.row_count
        or first_timestamp != reference.first_timestamp_ms
        or last_timestamp != reference.last_timestamp_ms
        or len(minutes) != reference.unique_minute_count
    ):
        raise ValueError("Qualified Spot structural reference changed")
    return minutes


def paired_clock(
    spot_minutes: set[int],
    raw_minutes: set[int],
) -> PeriodicFlowPairedClockEvidence:
    paired = spot_minutes & raw_minutes
    union = spot_minutes | raw_minutes
    paired_month_fraction = Decimal(len(paired)) / Decimal(44_640)
    reasons = (
        ("PAIRED_MONTH_COVERAGE_BELOW_0_99",)
        if paired_month_fraction < Decimal("0.99")
        else ()
    )
    return PeriodicFlowPairedClockEvidence(
        spot_unique_minute_count=len(spot_minutes),
        usd_m_unique_minute_count=len(raw_minutes),
        paired_minute_count=len(paired),
        union_minute_count=len(union),
        paired_month_coverage_fraction=paired_month_fraction,
        paired_union_overlap_fraction=Decimal(len(paired)) / Decimal(len(union)),
        spot_only_minute_count=len(spot_minutes - raw_minutes),
        usd_m_only_minute_count=len(raw_minutes - spot_minutes),
        paired_clock_pass=not reasons,
        reason_codes=reasons,
    )


def inspect_pilot(
    *,
    protocol: RawTradesPayloadPilotProtocol,
    evidence_root: Path,
    payload_get_attempt_count: int,
) -> tuple[RawTradesArchiveEvidence, PeriodicFlowPairedClockEvidence]:
    raw_evidence, raw_minutes = inspect_raw_archive(
        protocol=protocol,
        archive_path=raw_archive_path(evidence_root),
        payload_get_attempt_count=payload_get_attempt_count,
    )
    spot_minutes = inspect_spot_minutes(
        protocol=protocol,
        evidence_root=evidence_root,
    )
    return raw_evidence, paired_clock(spot_minutes, raw_minutes)


def authoritative_result(
    *,
    generated_at: datetime,
    protocol_path: Path,
    protocol_audit_path: Path,
    protocol: RawTradesPayloadPilotProtocol,
    protocol_audit: RawTradesPayloadProtocolAudit,
    raw_evidence: RawTradesArchiveEvidence,
    clock: PeriodicFlowPairedClockEvidence,
    request_marker_manifest_hash: str,
    request_marker_count: int,
) -> RawTradesPayloadPilotResultV2:
    return build_raw_payload_result_v2(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        protocol_audit_file_sha256=file_sha256(protocol_audit_path),
        protocol_audit_evidence_hash=protocol_audit.audit_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        raw_archive_evidence=raw_evidence,
        paired_clock_evidence=clock,
        request_marker_manifest_hash=request_marker_manifest_hash,
        request_marker_count=request_marker_count,
        payload_get_attempt_count=raw_evidence.payload_get_attempt_count,
        total_new_archive_bytes=raw_evidence.archive_bytes,
        limitations=(
            "Only one checksum-pinned USD-M raw-trades archive was newly requested.",
            "The paired Spot archive was reused locally and not re-requested.",
            "Only IDs, timestamps, and buyer-maker booleans were parsed.",
            "Price, quantity, quote quantity, features, and outcomes remain unopened.",
            "Forward ID omissions remain explicitly measured and bounded.",
            "Validation, holdout, and forward outcomes remain sealed.",
            "A pass permits only a separate paired full-development acquisition protocol.",
            "Paper and Testnet strategy-order authority remain false.",
            "Production, live, real-capital authority, and profit remain false.",
        ),
    )


def write_result(path: Path, result: RawTradesPayloadPilotResultV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite raw payload result: {path}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if RawTradesPayloadPilotResultV2.model_validate_json(serialized) != result:
        raise ValueError("Q1 raw payload result did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale raw payload result transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or verify the frozen Q1 one-month raw-trades payload pilot."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        protocol, protocol_audit = load_protocol(
            args.protocol, args.protocol_audit
        )
        if args.check:
            stored = RawTradesPayloadPilotResultV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            raw_evidence, clock = inspect_pilot(
                protocol=protocol,
                evidence_root=args.evidence_root,
                payload_get_attempt_count=stored.payload_get_attempt_count,
            )
            marker_hash, marker_count, marker_records = request_marker_manifest(
                evidence_root=args.evidence_root,
                protocol=protocol,
            )
            if int(marker_records[-1]["bytes_received"]) != raw_evidence.archive_bytes:
                raise ValueError("Raw payload marker byte count changed")
            expected = authoritative_result(
                generated_at=stored.generated_at,
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                protocol=protocol,
                protocol_audit=protocol_audit,
                raw_evidence=raw_evidence,
                clock=clock,
                request_marker_manifest_hash=marker_hash,
                request_marker_count=marker_count,
            )
            if stored != expected or not audit_raw_payload_result_v2(stored):
                raise ValueError("Stored Q1 raw payload result changed")
            print(
                f"PASS {args.output} {stored.result_evidence_hash} "
                f"decision={stored.decision} outcomes=0 orders=0",
                flush=True,
            )
            return 0
        path, attempts = ensure_raw_archive(
            protocol=protocol,
            evidence_root=args.evidence_root,
        )
        print(
            f"VERIFIED raw_archive bytes={path.stat().st_size} "
            f"sha256={file_sha256(path)} attempts={attempts}",
            flush=True,
        )
        raw_evidence, clock = inspect_pilot(
            protocol=protocol,
            evidence_root=args.evidence_root,
            payload_get_attempt_count=attempts,
        )
        marker_hash, marker_count, marker_records = request_marker_manifest(
            evidence_root=args.evidence_root,
            protocol=protocol,
        )
        if int(marker_records[-1]["bytes_received"]) != raw_evidence.archive_bytes:
            raise ValueError("Raw payload marker byte count does not match archive")
        result = authoritative_result(
            generated_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            protocol=protocol,
            protocol_audit=protocol_audit,
            raw_evidence=raw_evidence,
            clock=clock,
            request_marker_manifest_hash=marker_hash,
            request_marker_count=marker_count,
        )
        write_result(args.output, result)
        print(
            f"WROTE {args.output} {result.result_evidence_hash} "
            f"rows={raw_evidence.row_count} minutes={raw_evidence.unique_minute_count} "
            f"skipped_fraction={raw_evidence.skipped_trade_id_fraction} "
            f"decision={result.decision} outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
