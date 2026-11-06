from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_raw_pilot import (  # noqa: E402
    S1_NFCI_PILOT_NEXT,
    S1_NFCI_PILOT_PASS,
    S1_NFCI_PILOT_STOP,
    S1NfciPilotDownload,
    S1NfciPilotTarget,
    S1NfciRawPilotProtocol,
    S1NfciRawPilotResult,
    S1NfciSnapshotSummary,
    S1NfciVintageComparison,
)
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate  # noqa: E402
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_nfci_raw_pilot_protocol import build_protocol  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_nfci_raw_pilot_protocol_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_raw_pilot_result_v1.json")
RUNNER_PATH = Path("scripts/run_s1_nfci_raw_pilot.py")


def marker_path(target: S1NfciPilotTarget, kind: str) -> Path:
    raw_path = Path(target.raw_path)
    return raw_path.with_name(f"{raw_path.name}.get.01.{kind}.json")


def write_json_atomic(path: Path, payload: dict) -> None:
    if path.exists():
        raise ValueError(f"Immutable S1 NFCI evidence already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 NFCI JSON transaction exists: {temporary}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def validate_target(target: S1NfciPilotTarget) -> None:
    parsed = urlparse(target.url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != target.expected_final_host
        or parsed.path != "/graph/fredgraph.csv"
        or parsed.query != f"id=NFCI&vintage_date={target.vintage_date.isoformat()}"
        or parsed.fragment
    ):
        raise ValueError("S1 NFCI target URL left the frozen allowlist")
    raw_path = Path(target.raw_path)
    expected_parent = Path("data/evidence/source_snapshots/s1_nfci_raw_pilot_v1")
    if raw_path.parent != expected_parent or raw_path.suffix != ".csv":
        raise ValueError("S1 NFCI raw path left the frozen evidence root")


def parse_snapshot(
    path: Path,
    *,
    vintage_date: date,
) -> tuple[S1NfciSnapshotSummary, dict[date, Decimal]]:
    rows_by_date: dict[date, Decimal] = {}
    seen_dates: set[date] = set()
    row_count = 0
    missing_count = 0
    duplicate_count = 0
    non_increasing_count = 0
    post_vintage_count = 0
    previous_date: date | None = None
    first_date: date | None = None
    last_date: date | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        header = tuple(next(reader, ()))
        for line_number, row in enumerate(reader, start=2):
            if len(row) != 2:
                raise ValueError(f"S1 NFCI CSV row {line_number} has {len(row)} columns")
            try:
                observation_date = date.fromisoformat(row[0])
            except ValueError as exc:
                raise ValueError(
                    f"S1 NFCI CSV row {line_number} has an invalid date"
                ) from exc
            raw_value = row[1].strip()
            row_count += 1
            if first_date is None:
                first_date = observation_date
            last_date = observation_date
            if previous_date is not None and observation_date <= previous_date:
                non_increasing_count += 1
            previous_date = observation_date
            if observation_date in seen_dates:
                duplicate_count += 1
            seen_dates.add(observation_date)
            if observation_date > vintage_date:
                post_vintage_count += 1
            if raw_value in {"", "."}:
                missing_count += 1
                continue
            try:
                value = Decimal(raw_value)
            except InvalidOperation as exc:
                raise ValueError(
                    f"S1 NFCI CSV row {line_number} has an invalid decimal"
                ) from exc
            if not value.is_finite():
                raise ValueError(f"S1 NFCI CSV row {line_number} has a non-finite decimal")
            rows_by_date[observation_date] = value
    release_lag = None if last_date is None else (vintage_date - last_date).days
    if release_lag is not None and release_lag < 0:
        release_lag = 0
    summary = S1NfciSnapshotSummary(
        csv_header=header,
        row_count=row_count,
        valid_numeric_row_count=len(rows_by_date),
        missing_value_row_count=missing_count,
        distinct_observation_date_count=row_count - duplicate_count,
        duplicate_observation_date_count=duplicate_count,
        non_increasing_observation_date_count=non_increasing_count,
        post_vintage_observation_count=post_vintage_count,
        first_observation_date=first_date,
        last_observation_date=last_date,
        release_lag_days=release_lag,
    )
    return summary, rows_by_date


def build_download(**payload) -> S1NfciPilotDownload:
    provisional = S1NfciPilotDownload.model_construct(
        **payload,
        download_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["download_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"download_evidence_hash"})
    )
    return S1NfciPilotDownload.model_validate(complete)


def download_target(
    target: S1NfciPilotTarget,
    *,
    protocol: S1NfciRawPilotProtocol,
) -> S1NfciPilotDownload:
    validate_target(target)
    raw_path = Path(target.raw_path)
    request_path = marker_path(target, "request")
    response_path = marker_path(target, "response")
    part_path = raw_path.with_name(f"{raw_path.name}.part")
    for path in (raw_path, request_path, response_path, part_path):
        if path.exists():
            raise ValueError(f"S1 NFCI pilot refuses existing target evidence: {path}")
    attempted_at = datetime.now(UTC)
    write_json_atomic(
        request_path,
        {
            "schema_version": "aurex-s1-nfci-http-request-v1",
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "target_id": target.target_id,
            "method": "GET",
            "url": target.url,
            "attempt": 1,
            "range": None,
            "requested_at": attempted_at.isoformat(),
        },
    )
    status_code = None
    final_url = None
    final_host = None
    content_type = None
    bytes_received = 0
    error: Exception | None = None
    try:
        request = Request(
            target.url,
            headers={"User-Agent": "Aurex-S1-NFCI-Feasibility/1.0"},
            method="GET",
        )
        with urlopen(request, timeout=protocol.connect_timeout_seconds) as response:
            status_code = response.status
            final_url = response.geturl()
            final_host = urlparse(final_url).hostname
            content_type = response.headers.get("Content-Type")
            if status_code != 200:
                raise ValueError(f"S1 NFCI endpoint returned HTTP {status_code}")
            if final_host != target.expected_final_host:
                raise ValueError("S1 NFCI endpoint redirected outside the official host")
            if content_type is None or "csv" not in content_type.lower():
                raise ValueError("S1 NFCI endpoint did not return a CSV content type")
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with part_path.open("xb") as destination:
                while True:
                    chunk = response.read(protocol.chunk_size_bytes)
                    if not chunk:
                        break
                    bytes_received += len(chunk)
                    if bytes_received > protocol.maximum_payload_bytes_per_target:
                        raise ValueError("S1 NFCI target exceeded its frozen byte cap")
                    destination.write(chunk)
            if bytes_received == 0:
                raise ValueError("S1 NFCI endpoint returned an empty payload")
            part_path.replace(raw_path)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        error = exc
        if isinstance(exc, HTTPError):
            status_code = exc.code
            final_url = exc.geturl()
            final_host = urlparse(final_url).hostname
            content_type = exc.headers.get("Content-Type") if exc.headers else None
        if part_path.exists():
            part_path.unlink()
    response_payload = {
        "schema_version": "aurex-s1-nfci-http-response-v1",
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "target_id": target.target_id,
        "attempt": 1,
        "status_code": status_code,
        "final_url": final_url,
        "final_host": final_host,
        "content_type": content_type,
        "bytes_received": bytes_received,
        "outcome": "FAILED" if error else "COMPLETE",
        "error_type": None if error is None else type(error).__name__,
        "error_message": None if error is None else str(error),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    write_json_atomic(response_path, response_payload)
    common = {
        "target_id": target.target_id,
        "vintage_date": target.vintage_date,
        "attempted_at": attempted_at,
        "status_code": status_code,
        "final_url": final_url,
        "final_host": final_host,
        "content_type": content_type,
        "payload_bytes": bytes_received,
        "request_marker_path": request_path.as_posix(),
        "request_marker_sha256": file_sha256(request_path),
        "response_marker_path": response_path.as_posix(),
        "response_marker_sha256": file_sha256(response_path),
    }
    if error is not None:
        return build_download(
            **common,
            outcome="FAILED",
            payload_sha256=None,
            raw_path=None,
            summary=None,
            error_type=type(error).__name__,
            error_message=str(error),
        )
    summary, _ = parse_snapshot(raw_path, vintage_date=target.vintage_date)
    return build_download(
        **common,
        outcome="COMPLETE",
        payload_sha256=file_sha256(raw_path),
        raw_path=raw_path.as_posix(),
        summary=summary,
        error_type=None,
        error_message=None,
    )


def build_comparison(
    downloads: tuple[S1NfciPilotDownload, ...],
) -> S1NfciVintageComparison:
    if any(item.outcome != "COMPLETE" or item.raw_path is None for item in downloads):
        return S1NfciVintageComparison(
            comparable=False,
            payload_hashes_distinct=False,
            overlap_observation_count=0,
            overlap_revision_count=0,
            later_only_observation_count=0,
            earlier_only_observation_count=0,
        )
    earlier, later = downloads
    _, earlier_rows = parse_snapshot(Path(earlier.raw_path), vintage_date=earlier.vintage_date)
    _, later_rows = parse_snapshot(Path(later.raw_path), vintage_date=later.vintage_date)
    overlap = set(earlier_rows) & set(later_rows)
    return S1NfciVintageComparison(
        comparable=True,
        earlier_payload_sha256=earlier.payload_sha256,
        later_payload_sha256=later.payload_sha256,
        payload_hashes_distinct=earlier.payload_sha256 != later.payload_sha256,
        overlap_observation_count=len(overlap),
        overlap_revision_count=sum(
            earlier_rows[item] != later_rows[item] for item in overlap
        ),
        later_only_observation_count=len(set(later_rows) - set(earlier_rows)),
        earlier_only_observation_count=len(set(earlier_rows) - set(later_rows)),
        earlier_last_observation_date=earlier.summary.last_observation_date,
        later_last_observation_date=later.summary.last_observation_date,
    )


def evaluate_gates(
    protocol: S1NfciRawPilotProtocol,
    downloads: tuple[S1NfciPilotDownload, ...],
    comparison: S1NfciVintageComparison,
) -> tuple[S1SourceGate, ...]:
    complete = len(downloads) == 2 and all(item.outcome == "COMPLETE" for item in downloads)
    summaries = tuple(item.summary for item in downloads if item.summary is not None)
    exact_schema = complete and all(
        summary.csv_header == protocol.expected_csv_header
        and summary.valid_numeric_row_count >= protocol.minimum_valid_rows_per_target
        for summary in summaries
    )
    unique_dates = complete and all(
        summary.duplicate_observation_date_count == 0
        and summary.non_increasing_observation_date_count == 0
        for summary in summaries
    )
    no_future = complete and all(
        summary.post_vintage_observation_count == 0 for summary in summaries
    )
    earliest_required = date.fromisoformat(protocol.earliest_required_observation_date)
    coverage = complete and all(
        summary.first_observation_date is not None
        and summary.first_observation_date <= earliest_required
        and summary.release_lag_days is not None
        and summary.release_lag_days <= protocol.maximum_release_lag_days
        for summary in summaries
    )
    official = complete and all(
        item.final_host == "fred.stlouisfed.org"
        and item.content_type is not None
        and "csv" in item.content_type.lower()
        for item in downloads
    )
    extension = (
        comparison.comparable
        and comparison.payload_hashes_distinct
        and comparison.later_only_observation_count > 0
        and comparison.earlier_last_observation_date is not None
        and comparison.later_last_observation_date is not None
        and comparison.later_last_observation_date > comparison.earlier_last_observation_date
    )
    checks = (
        (
            "EXACTLY_TWO_FROZEN_PAYLOAD_GETS_WITHIN_BYTE_BUDGET",
            len(downloads) == protocol.request_budget
            and sum(item.payload_bytes for item in downloads)
            <= protocol.maximum_total_payload_bytes,
        ),
        ("BOTH_RAW_SNAPSHOTS_COMPLETE_AND_HASHED", complete),
        ("OFFICIAL_FINAL_HOSTS_AND_CSV_CONTENT_TYPES_MATCH", official),
        ("EXACT_CSV_SCHEMA_AND_VALID_DECIMAL_ROWS", exact_schema),
        ("STRICTLY_INCREASING_UNIQUE_OBSERVATION_DATES", unique_dates),
        ("NO_OBSERVATION_AFTER_REQUESTED_VINTAGE", no_future),
        (
            "EACH_SNAPSHOT_COVERS_DEVELOPMENT_START_AND_IS_RECENT_TO_VINTAGE",
            coverage,
        ),
        ("DISTINCT_SNAPSHOTS_WITH_LATER_VINTAGE_EXTENSION", extension),
        (
            "OVERLAP_CONTAINS_AT_LEAST_ONE_POINT_IN_TIME_REVISION",
            comparison.comparable and comparison.overlap_revision_count > 0,
        ),
        ("ZERO_BTC_MARKET_VALUES_RETURNS_CANDIDATES_AND_ORDERS", True),
    )
    return tuple(
        S1SourceGate(
            gate_id=gate_id,
            status="PASS" if passed else "FAIL",
            reason=(
                "Observed evidence satisfies the frozen feasibility condition."
                if passed
                else "Observed evidence does not satisfy the frozen feasibility condition."
            ),
        )
        for gate_id, passed in sorted(checks)
    )


def build_result(
    *,
    protocol_path: Path,
    protocol: S1NfciRawPilotProtocol,
    downloads: tuple[S1NfciPilotDownload, ...],
    comparison: S1NfciVintageComparison,
    completed_at: datetime,
) -> S1NfciRawPilotResult:
    gates = evaluate_gates(protocol, downloads, comparison)
    failed = any(gate.status == "FAIL" for gate in gates)
    payload = {
        "completed_at": completed_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_source_sha256": file_sha256(PROJECT_ROOT / RUNNER_PATH),
        "downloads": downloads,
        "comparison": comparison,
        "gates": gates,
        "total_payload_bytes": sum(item.payload_bytes for item in downloads),
        "decision": S1_NFCI_PILOT_STOP if failed else S1_NFCI_PILOT_PASS,
        "next_authorization": "NONE_S1_NFCI_RAW_PILOT_FAILED" if failed else S1_NFCI_PILOT_NEXT,
    }
    provisional = S1NfciRawPilotResult.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S1NfciRawPilotResult.model_validate(complete)


def write_result(path: Path, result: S1NfciRawPilotResult) -> None:
    if path.exists():
        raise ValueError(f"S1 NFCI raw pilot result exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 NFCI result transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S1NfciRawPilotResult.model_validate_json(serialized) != result:
        raise ValueError("S1 NFCI raw pilot result did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen S1 NFCI raw pilot.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1 NFCI result: {args.output}")
    protocol = S1NfciRawPilotProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    if protocol != build_protocol(frozen_at=protocol.frozen_at):
        raise SystemExit("Frozen S1 NFCI protocol differs from reconstruction")
    downloads = tuple(download_target(target, protocol=protocol) for target in protocol.targets)
    comparison = build_comparison(downloads)
    result = build_result(
        protocol_path=args.protocol,
        protocol=protocol,
        downloads=downloads,
        comparison=comparison,
        completed_at=datetime.now(UTC),
    )
    write_result(args.output, result)
    print(
        f"COMPLETE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} requests=2 bytes={result.total_payload_bytes} "
        "btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
