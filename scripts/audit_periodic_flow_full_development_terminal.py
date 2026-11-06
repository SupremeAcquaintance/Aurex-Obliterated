from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from itertools import chain
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JamArchiveQualityAudit,
    JamArchiveQualityResult,
    audit_jam_archive_quality_audit,
    audit_jam_archive_quality_result,
)
from aurex.backtest_engine.periodic_flow_full_development_acquisition import (  # noqa: E402
    PeriodicFlowFullDevelopmentProtocol,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    PeriodicFlowAcquisitionCheckpoint,
    PeriodicFlowAcquisitionResult,
    source_contract_hash,
)
from aurex.backtest_engine.periodic_flow_full_development_terminal_audit import (  # noqa: E402
    PeriodicFlowObservedGap,
    PeriodicFlowTerminalAcquisitionAudit,
    audit_terminal_acquisition_audit,
    build_terminal_acquisition_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_full_development_execution_contract_v1.json"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_checkpoint_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_result_v1.json"
)
DEFAULT_REMEDIATION_RESULT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_REMEDIATION_AUDIT = Path(
    "data/evidence/jam_archive_quality_remediation_audit_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_v1"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_full_development_terminal_audit_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_full_development_terminal_audit.py"
)
SCRIPT_PATH = Path("scripts/audit_periodic_flow_full_development_terminal.py")


@dataclass(frozen=True)
class SpotStructuralScan:
    archive_sha256: str
    archive_bytes: int
    member_name: str
    row_count: int
    unique_minute_count: int
    expected_minute_count: int
    maximum_event_gap_minutes: int
    maximum_missing_minute_run: int
    gaps: tuple[PeriodicFlowObservedGap, ...]
    reason_codes: tuple[str, ...]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def month_bounds(month: str) -> tuple[int, int, int]:
    year, month_number = (int(part) for part in month.split("-"))
    start = datetime(year, month_number, 1, tzinfo=UTC)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=UTC)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    return start_ms, end_ms, (end_ms - start_ms) // 60_000


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("Q1 terminal audit found an invalid buyer-maker value")


def structural_reason_codes(
    *,
    row_count: int,
    coverage: Decimal,
    maximum_event_gap_minutes: int,
    non_increasing: int,
    duplicates: int,
    primary_gaps: int,
    raw_range_gaps: int,
    raw_range_non_increasing: int,
    timestamp_regressions: int,
    makers: tuple[bool, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if row_count < 100_000:
        reasons.append("ROW_COUNT_BELOW_100000")
    if coverage < Decimal("0.99"):
        reasons.append("MINUTE_COVERAGE_BELOW_0_99")
    if maximum_event_gap_minutes > 15:
        reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
    if non_increasing:
        reasons.append("PRIMARY_ID_NOT_STRICTLY_INCREASING")
    if duplicates:
        reasons.append("PRIMARY_ID_DUPLICATE")
    if primary_gaps:
        reasons.append("SPOT_AGGREGATE_ID_GAP")
    if raw_range_gaps:
        reasons.append("SPOT_RAW_RANGE_GAP")
    if raw_range_non_increasing:
        reasons.append("SPOT_RAW_RANGE_OVERLAP_OR_REGRESSION")
    if timestamp_regressions:
        reasons.append("TIMESTAMP_REGRESSION")
    if makers != (False, True):
        reasons.append("BUYER_MAKER_DOMAIN_INCOMPLETE")
    return tuple(sorted(reasons))


def scan_spot_archive(*, path: Path, month: str, expected_member: str) -> SpotStructuralScan:
    start_ms, end_ms, expected_minutes = month_bounds(month)
    minutes: set[int] = set()
    makers: set[bool] = set()
    row_count = 0
    previous_primary: int | None = None
    previous_last_raw: int | None = None
    previous_timestamp: int | None = None
    non_increasing = 0
    duplicates = 0
    primary_gaps = 0
    raw_range_gaps = 0
    raw_range_non_increasing = 0
    timestamp_regressions = 0
    with zipfile.ZipFile(path) as archive:
        files = [member for member in archive.infolist() if not member.is_dir()]
        if len(files) != 1 or files[0].filename != expected_member:
            raise ValueError("Q1 failed Spot archive member policy changed")
        member = files[0]
        with archive.open(member) as binary:
            reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline=""))
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("Q1 failed Spot archive is empty") from exc
            if len(first_row) != 8:
                raise ValueError("Q1 failed Spot archive column count changed")
            try:
                int(first_row[0])
            except ValueError as exc:
                raise ValueError("Q1 failed Spot archive unexpectedly has a header") from exc
            for row in chain((first_row,), reader):
                if len(row) != 8:
                    raise ValueError("Q1 failed Spot archive column count changed")
                primary_id = int(row[0])
                first_raw = int(row[3])
                last_raw = int(row[4])
                timestamp = int(row[5])
                maker = parse_bool(row[6])
                if first_raw > last_raw or not start_ms <= timestamp < end_ms:
                    raise ValueError("Q1 failed Spot archive structural row changed")
                if previous_primary is not None:
                    if primary_id <= previous_primary:
                        non_increasing += 1
                        if primary_id == previous_primary:
                            duplicates += 1
                    elif primary_id > previous_primary + 1:
                        primary_gaps += 1
                if previous_last_raw is not None:
                    if first_raw <= previous_last_raw:
                        raw_range_non_increasing += 1
                    elif first_raw > previous_last_raw + 1:
                        raw_range_gaps += 1
                if previous_timestamp is not None and timestamp < previous_timestamp:
                    timestamp_regressions += 1
                previous_primary = primary_id
                previous_last_raw = last_raw
                previous_timestamp = timestamp
                makers.add(maker)
                minutes.add((timestamp - start_ms) // 60_000)
                row_count += 1
    ordered = sorted(minutes)
    gaps = tuple(
        PeriodicFlowObservedGap(
            preceding_observed_minute_ms=start_ms + previous * 60_000,
            missing_start_minute_ms=start_ms + (previous + 1) * 60_000,
            missing_end_minute_ms=start_ms + (current - 1) * 60_000,
            following_observed_minute_ms=start_ms + current * 60_000,
            observed_minute_distance=current - previous,
            missing_minute_count=current - previous - 1,
        )
        for previous, current in zip(ordered, ordered[1:], strict=False)
        if current - previous > 1
    )
    maximum_event_gap = max(
        (item.observed_minute_distance for item in gaps), default=0
    )
    maximum_missing_run = max((item.missing_minute_count for item in gaps), default=0)
    coverage = Decimal(len(minutes)) / Decimal(expected_minutes)
    reasons = structural_reason_codes(
        row_count=row_count,
        coverage=coverage,
        maximum_event_gap_minutes=maximum_event_gap,
        non_increasing=non_increasing,
        duplicates=duplicates,
        primary_gaps=primary_gaps,
        raw_range_gaps=raw_range_gaps,
        raw_range_non_increasing=raw_range_non_increasing,
        timestamp_regressions=timestamp_regressions,
        makers=tuple(sorted(makers)),
    )
    return SpotStructuralScan(
        archive_sha256=file_sha256(path),
        archive_bytes=path.stat().st_size,
        member_name=member.filename,
        row_count=row_count,
        unique_minute_count=len(minutes),
        expected_minute_count=expected_minutes,
        maximum_event_gap_minutes=maximum_event_gap,
        maximum_missing_minute_run=maximum_missing_run,
        gaps=gaps,
        reason_codes=reasons,
    )


def auditor_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def authoritative_audit(
    *, args: argparse.Namespace, audited_at: datetime
) -> PeriodicFlowTerminalAcquisitionAudit:
    protocol = PeriodicFlowFullDevelopmentProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    result = PeriodicFlowAcquisitionResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowAcquisitionCheckpoint.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    remediation = JamArchiveQualityResult.model_validate_json(
        args.remediation_result.read_text(encoding="utf-8")
    )
    remediation_audit = JamArchiveQualityAudit.model_validate_json(
        args.remediation_audit.read_text(encoding="utf-8")
    )
    if (
        result.decision != "STOP_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_FAILED"
        or result.failed_target_key != "2020-02|SPOT"
        or result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
        or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        or result.protocol_file_sha256 != file_sha256(args.protocol)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.execution_contract_file_sha256 != file_sha256(args.execution_contract)
        or len(checkpoint.archive_evidence) != 2
        or len(checkpoint.paired_month_evidence) != 1
        or not audit_jam_archive_quality_result(remediation)
        or not audit_jam_archive_quality_audit(remediation_audit)
        or remediation_audit.result_file_sha256 != file_sha256(args.remediation_result)
        or remediation_audit.result_evidence_hash != remediation.result_evidence_hash
        or remediation.generated_at >= protocol.frozen_at
    ):
        raise ValueError("Q1 terminal audit lineage changed")
    target = next(
        item
        for item in protocol.targets
        if item.month == "2020-02" and item.product == "SPOT"
    )
    if target.reuse_candidate_path is None:
        raise ValueError("Q1 failed target is no longer a local reuse candidate")
    archive_path = (args.evidence_root / target.reuse_candidate_path).resolve()
    if not archive_path.is_relative_to(args.evidence_root.resolve()):
        raise ValueError("Q1 failed target escapes evidence root")
    scan = scan_spot_archive(
        path=archive_path,
        month=target.month,
        expected_member=target.expected_member_name,
    )
    if (
        scan.archive_sha256 != target.published_archive_sha256
        or scan.reason_codes != ("EVENT_GAP_EXCEEDS_15_MINUTES",)
        or result.failure_reason
        != "Archive structural gates failed: ('EVENT_GAP_EXCEEDS_15_MINUTES',)"
    ):
        raise ValueError("Q1 terminal failure did not reconstruct")
    prior_gaps = tuple(
        item
        for item in remediation.kline_gap_intervals
        if item.month == target.month
        and item.classification == "PAIRED_SOURCE_OBSERVABILITY_GAP"
        and item.aggregate_covered_minute_count == 0
    )
    expected_prior = tuple(
        (
            item.preceding_open_time_ms,
            item.start_open_time_ms,
            item.end_open_time_ms,
            item.following_open_time_ms,
            item.missing_minute_count,
        )
        for item in prior_gaps
    )
    observed = tuple(
        (
            item.preceding_observed_minute_ms,
            item.missing_start_minute_ms,
            item.missing_end_minute_ms,
            item.following_observed_minute_ms,
            item.missing_minute_count,
        )
        for item in scan.gaps
    )
    if observed != expected_prior:
        raise ValueError("Q1 terminal gaps do not match prior remediation evidence")
    request_markers = tuple(args.acquisition_root.rglob("*.request.json"))
    response_markers = tuple(args.acquisition_root.rglob("*.response.json"))
    if request_markers or response_markers:
        raise ValueError("Q1 terminal audit expected zero network markers")
    if checkpoint.request_marker_manifest_hash != universe_evidence_hash(
        {"marker_files": {}}
    ):
        raise ValueError("Q1 empty request-marker manifest changed")
    return build_terminal_acquisition_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=result.execution_contract_evidence_hash,
        runner_source_hash=result.runner_source_hash,
        auditor_contract_hash=auditor_contract_hash(),
        prior_remediation_result_file_sha256=file_sha256(args.remediation_result),
        prior_remediation_result_evidence_hash=remediation.result_evidence_hash,
        prior_remediation_audit_file_sha256=file_sha256(args.remediation_audit),
        prior_remediation_audit_evidence_hash=remediation_audit.audit_evidence_hash,
        failed_archive_local_path=target.reuse_candidate_path,
        failed_archive_sha256=scan.archive_sha256,
        failed_archive_bytes=scan.archive_bytes,
        failed_archive_member_name=scan.member_name,
        failed_archive_row_count=scan.row_count,
        expected_minute_count=scan.expected_minute_count,
        unique_minute_count=scan.unique_minute_count,
        minute_coverage_fraction=(
            Decimal(scan.unique_minute_count) / Decimal(scan.expected_minute_count)
        ),
        maximum_event_gap_minutes=scan.maximum_event_gap_minutes,
        maximum_missing_minute_run=scan.maximum_missing_minute_run,
        observed_gaps=scan.gaps,
        reconstructed_reason_codes=scan.reason_codes,
        frozen_failure_reason=result.failure_reason,
        prior_matching_gap_count=len(prior_gaps),
        findings=(
            "February 2020 Spot contains two genuine paired-source observability gaps.",
            "The largest gap spans 354 missing minutes and exceeds the frozen gate "
            "under either gap convention.",
            "The v1 runner followed its frozen first-failure stop contract and must "
            "not be resumed or overwritten.",
            "The runtime preflight checked checksum, ZIP policy, and disk capacity "
            "but did not inspect event gaps.",
            "The stricter Q1 policy conflicted with source gaps documented before "
            "the protocol was frozen.",
            "A successor may begin only with a frozen no-outcome source-quality census protocol.",
        ),
    )


def write_audit(path: Path, audit: PeriodicFlowTerminalAcquisitionAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 terminal audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 terminal audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowTerminalAcquisitionAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 terminal audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the terminal Q1 v1 acquisition failure."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument(
        "--remediation-result", type=Path, default=DEFAULT_REMEDIATION_RESULT
    )
    parser.add_argument(
        "--remediation-audit", type=Path, default=DEFAULT_REMEDIATION_AUDIT
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowTerminalAcquisitionAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_terminal_acquisition_audit(stored):
                raise ValueError("Stored Q1 terminal audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                f"decision={stored.decision} requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"max_event_gap={audit.maximum_event_gap_minutes} "
            f"max_missing_run={audit.maximum_missing_minute_run} requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
