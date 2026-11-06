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
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_overlap_census import (  # noqa: E402
    PeriodicFlowDailyChecksumRecord,
    PeriodicFlowOverlapCensusProtocol,
    PeriodicFlowOverlapCensusResult,
    PeriodicFlowOverlapEvent,
    audit_overlap_census_protocol,
    audit_overlap_census_result,
    build_overlap_census_result,
    daily_archive_url,
)
from aurex.backtest_engine.research_v2_source_census import (  # noqa: E402
    parse_v2_checksum_text,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_overlap_census_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_overlap_census_result_v1.json"
)
TARGET_ARCHIVE = Path(
    "data/evidence/source_snapshots/q1_periodic_flow_payload_pilot_v1/"
    "USD_M_PERPETUAL/BTCUSDT-aggTrades-2020-01.zip"
)
EXPECTED_MEMBER = "BTCUSDT-aggTrades-2020-01.csv"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "run_periodic_flow_overlap_census.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "periodic_flow_overlap_census.py",
    )
    return universe_evidence_hash(
        {
            path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
            for path in paths
        }
    )


def load_protocol(path: Path) -> PeriodicFlowOverlapCensusProtocol:
    protocol = PeriodicFlowOverlapCensusProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_overlap_census_protocol(protocol):
        raise ValueError("Q1 overlap census protocol hash failed")
    return protocol


def localize_overlap(
    protocol: PeriodicFlowOverlapCensusProtocol,
) -> PeriodicFlowOverlapEvent:
    if file_sha256(TARGET_ARCHIVE) != protocol.target_archive_sha256:
        raise ValueError("Q1 overlap census archive checksum changed")
    previous: tuple[int, int, int, int] | None = None
    events = []
    with zipfile.ZipFile(TARGET_ARCHIVE) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != EXPECTED_MEMBER:
            raise ValueError("Q1 overlap census ZIP structure changed")
        with archive.open(members[0], "r") as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                for row in csv.reader(text):
                    if len(row) != 7:
                        raise ValueError("Q1 overlap census column count changed")
                    aggregate_id = int(row[0])
                    first_raw = int(row[3])
                    last_raw = int(row[4])
                    timestamp = int(row[5])
                    if previous is not None:
                        prev_aggregate, prev_first, prev_last, prev_timestamp = previous
                        overlap_first = max(prev_first, first_raw)
                        overlap_last = min(prev_last, last_raw)
                        if overlap_last >= overlap_first:
                            events.append(
                                PeriodicFlowOverlapEvent(
                                    preceding_aggregate_trade_id=prev_aggregate,
                                    current_aggregate_trade_id=aggregate_id,
                                    preceding_first_raw_trade_id=prev_first,
                                    preceding_last_raw_trade_id=prev_last,
                                    current_first_raw_trade_id=first_raw,
                                    current_last_raw_trade_id=last_raw,
                                    preceding_timestamp_ms=prev_timestamp,
                                    current_timestamp_ms=timestamp,
                                    overlap_raw_trade_id_count=(
                                        overlap_last - overlap_first + 1
                                    ),
                                    first_overlapped_raw_trade_id=overlap_first,
                                    last_overlapped_raw_trade_id=overlap_last,
                                    utc_day=datetime.fromtimestamp(
                                        timestamp / 1000,
                                        tz=UTC,
                                    ).date().isoformat(),
                                )
                            )
                    previous = aggregate_id, first_raw, last_raw, timestamp
    if len(events) != protocol.expected_overlap_event_count:
        raise ValueError("Q1 overlap event count changed")
    return events[0]


def _validate_checksum_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.binance.vision"
        or not parsed.path.endswith(".zip.CHECKSUM")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Q1 overlap checksum URL left official allowlist")


def fetch_checksum(
    *,
    family: str,
    day: str,
    protocol: PeriodicFlowOverlapCensusProtocol,
) -> PeriodicFlowDailyChecksumRecord:
    archive = daily_archive_url(family, day)
    checksum_url = f"{archive}.CHECKSUM"
    _validate_checksum_url(checksum_url)
    last_error: Exception | None = None
    for attempt in range(1, protocol.maximum_retries + 2):
        request = urllib.request.Request(
            checksum_url,
            headers={
                "Accept": "text/plain",
                "Accept-Encoding": "identity",
                "User-Agent": "Aurex-Q1-Overlap-Census/1.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=protocol.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                if status != 200 or response.geturl() != checksum_url:
                    raise ValueError("Q1 overlap checksum response changed")
                payload = response.read(protocol.maximum_checksum_response_bytes + 1)
                if len(payload) > protocol.maximum_checksum_response_bytes:
                    raise ValueError("Q1 overlap checksum response exceeds budget")
                text = payload.decode("utf-8").strip()
                archive_name = archive.rsplit("/", maxsplit=1)[-1]
                digest = parse_v2_checksum_text(text, archive_name)
                return PeriodicFlowDailyChecksumRecord(
                    family=family,
                    utc_day=day,
                    archive_url=archive,
                    checksum_url=checksum_url,
                    checked_at=datetime.now(UTC),
                    http_status=200,
                    checksum_response_bytes=len(payload),
                    checksum_text=text,
                    checksum_text_sha256=hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                    archive_sha256=digest,
                    availability="PRESENT",
                    request_attempt_count=attempt,
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return PeriodicFlowDailyChecksumRecord(
                    family=family,
                    utc_day=day,
                    archive_url=archive,
                    checksum_url=checksum_url,
                    checked_at=datetime.now(UTC),
                    http_status=404,
                    checksum_response_bytes=0,
                    availability="MISSING",
                    request_attempt_count=attempt,
                )
            last_error = exc
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise
        except (OSError, TimeoutError) as exc:
            last_error = exc
        if attempt <= protocol.maximum_retries:
            time.sleep(protocol.retry_backoff_seconds[attempt - 1])
    raise RuntimeError(
        f"Q1 overlap checksum unresolved: {family}"
    ) from last_error


def authoritative_result(
    *,
    generated_at: datetime,
    protocol_path: Path,
    protocol: PeriodicFlowOverlapCensusProtocol,
    event: PeriodicFlowOverlapEvent,
    records: tuple[PeriodicFlowDailyChecksumRecord, ...],
) -> PeriodicFlowOverlapCensusResult:
    return build_overlap_census_result(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        overlap_event=event,
        checksum_records=records,
        checksum_get_attempt_count=sum(
            item.request_attempt_count for item in records
        ),
        limitations=(
            "The upstream pilot and gap-remediation STOP results remain immutable.",
            "Only one structural overlap was localized from the existing monthly archive.",
            "Only official daily aggTrades and trades CHECKSUM text was requested.",
            "No daily archive payload, price, quantity, feature, return, or outcome was accessed.",
            "A pass authorizes only a separate daily cross-source payload protocol.",
            "Checksum availability alone does not resolve duplication or source semantics.",
            "No candidate, Pine, paper, strategy-order, production, or live authority was created.",
            "Real net profit remains zero dollars.",
        ),
    )


def write_result(path: Path, result: PeriodicFlowOverlapCensusResult) -> None:
    if path.exists():
        raise ValueError("Q1 overlap census result exists; use --check")
    serialized = result.model_dump_json(indent=2) + "\n"
    if PeriodicFlowOverlapCensusResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 overlap census result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 overlap result transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowOverlapCensusResult:
    protocol = load_protocol(args.protocol)
    event = localize_overlap(protocol)
    records = tuple(
        fetch_checksum(family=family, day=event.utc_day, protocol=protocol)
        for family in protocol.checksum_families
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol_path=args.protocol,
        protocol=protocol,
        event=event,
        records=records,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"day={event.utc_day} overlap_ids={event.overlap_raw_trade_id_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def run_check(args) -> PeriodicFlowOverlapCensusResult:
    protocol = load_protocol(args.protocol)
    result = PeriodicFlowOverlapCensusResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_overlap_census_result(result)
        or result.protocol_file_sha256 != file_sha256(args.protocol)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or localize_overlap(protocol) != result.overlap_event
    ):
        raise ValueError("Q1 overlap census result lineage changed")
    expected = authoritative_result(
        generated_at=result.generated_at,
        protocol_path=args.protocol,
        protocol=protocol,
        event=result.overlap_event,
        records=result.checksum_records,
    )
    if result != expected:
        raise ValueError("Q1 overlap census result is not reproducible")
    print(
        f"PASS q1_overlap_result={result.result_evidence_hash} "
        f"day={result.overlap_event.utc_day} decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or check Q1 overlap localization and daily checksum census."
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
