import argparse
import hashlib
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v2_p01_acquisition_result import (
    V2P01FullAcquisitionResult,
    audit_v2_p01_full_acquisition_result,
)
from aurex.backtest_engine.research_v2_p01_protocol import (
    V2P01PrimaryProtocol,
    audit_v2_p01_primary_protocol,
)
from aurex.backtest_engine.research_v2_pilot_acquisition import month_bounds
from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v3_p01_coverage_result import (
    V3_P01_SYNC_FAMILIES,
    V3P01CoverageSummary,
    V3P01MonthCoverageEvidence,
    V3P01SymbolCoverageQualification,
    V3P01TimestampCoverageResult,
    audit_v3_p01_timestamp_coverage_result,
    build_v3_p01_timestamp_coverage_result,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposalRegister,
    V3ProposalCoverageContract,
    audit_v3_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_CHARTER = (
    DEFAULT_EVIDENCE_ROOT / "v3_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = (
    DEFAULT_EVIDENCE_ROOT / "v3_mechanism_proposal_register_v1.json"
)
DEFAULT_P01_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_primary_protocol_v1.json"
)
DEFAULT_P01_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_full_acquisition_result_v1.json"
)
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "v3_p01_timestamp_coverage_result_v1.json"
)


@dataclass(frozen=True, slots=True)
class ArchiveTimestampSource:
    family_id: str
    path: Path
    archive_sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class CoverageTask:
    symbol: str
    month: str
    sources: tuple[ArchiveTimestampSource, ...]


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


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p01_timestamp_coverage.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p01_coverage_result.py",
        ]
    )


def charter_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v3_discovery_charter.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_discovery_charter.py",
        ]
    )


def register_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v3_proposal_register.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_proposal_register.py",
        ]
    )


def p01_runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v2_p01_full_acquisition.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v2_p01_acquisition_result.py",
        ]
    )


def load_inputs(args):
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        args.charter.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_contract_hash()
    ):
        raise ValueError("V3 charter audit failed")
    register = V3MechanismProposalRegister.model_validate_json(
        args.register.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_proposal_register(register)
        or register.builder_contract_hash != register_builder_contract_hash()
        or register.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
    ):
        raise ValueError("V3 proposal register audit failed")
    protocol = V2P01PrimaryProtocol.model_validate_json(
        args.p01_protocol.read_text(encoding="utf-8")
    )
    if not audit_v2_p01_primary_protocol(protocol):
        raise ValueError("P01 protocol audit failed")
    p01_result = V2P01FullAcquisitionResult.model_validate_json(
        args.p01_result.read_text(encoding="utf-8")
    )
    p01_audit = audit_v2_p01_full_acquisition_result(
        result=p01_result,
        protocol=protocol,
        current_runner_contract_hash=p01_runner_contract_hash(),
        evidence_root=args.evidence_root,
        inspect_local_files=False,
    )
    if p01_audit["status"] != "PASS":
        raise ValueError(f"P01 result audit failed: {p01_audit['reasons']}")
    if (
        register.proposals[0].proposal_id
        != "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE"
    ):
        raise ValueError("V3P01 proposal identity changed")
    return charter, register, protocol, p01_result


def render_tasks(
    *,
    evidence_root: Path,
    p01_result: V2P01FullAcquisitionResult,
) -> list[CoverageTask]:
    records = {
        record.key: record
        for record in p01_result.records
        if record.family_id in V3_P01_SYNC_FAMILIES
    }
    tasks = []
    for symbol in sorted(
        {record.symbol for record in p01_result.records}
    ):
        for year in (2023, 2024):
            for month_number in range(1, 13):
                month = f"{year}-{month_number:02d}"
                sources = []
                for family_id in V3_P01_SYNC_FAMILIES:
                    record = records[(symbol, month, family_id)]
                    sources.append(
                        ArchiveTimestampSource(
                            family_id=family_id,
                            path=evidence_root / record.archive_relative_path,
                            archive_sha256=record.archive_sha256,
                            row_count=record.row_count,
                        )
                    )
                tasks.append(
                    CoverageTask(
                        symbol=symbol,
                        month=month,
                        sources=tuple(sources),
                    )
                )
    tasks.sort(key=lambda item: (item.symbol, item.month))
    if len(tasks) != 744:
        raise ValueError("V3P01 coverage task matrix changed")
    return tasks


def read_timestamps(
    *,
    source: ArchiveTimestampSource,
    month: str,
) -> set[int]:
    if (
        not source.path.is_file()
        or file_sha256(source.path) != source.archive_sha256
    ):
        raise ValueError(f"V3P01 archive hash failed: {source.path}")
    start, end = month_bounds(month)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    timestamps: set[int] = set()
    previous: int | None = None
    with zipfile.ZipFile(source.path) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) != 1 or not members[0].filename.lower().endswith(".csv"):
            raise ValueError("V3P01 archive member changed")
        with archive.open(members[0]) as rows:
            for line_number, raw_line in enumerate(rows):
                first_field = raw_line.partition(b",")[0].strip()
                try:
                    timestamp_ms = int(first_field)
                except ValueError:
                    if line_number == 0:
                        continue
                    raise ValueError("V3P01 timestamp field is invalid") from None
                if not start_ms <= timestamp_ms < end_ms:
                    raise ValueError("V3P01 timestamp is outside target month")
                if previous is not None and timestamp_ms <= previous:
                    raise ValueError("V3P01 timestamps are not increasing")
                timestamps.add(timestamp_ms)
                previous = timestamp_ms
    if len(timestamps) != source.row_count:
        raise ValueError("V3P01 timestamp count differs from P01 evidence")
    return timestamps


def maximum_gap_minutes(
    *,
    timestamps: set[int],
    start_ms: int,
    end_ms: int,
) -> int:
    previous = start_ms - 60_000
    maximum = 0
    for timestamp_ms in sorted(timestamps):
        maximum = max(maximum, (timestamp_ms - previous) // 60_000 - 1)
        previous = timestamp_ms
    maximum = max(maximum, (end_ms - previous) // 60_000 - 1)
    return maximum


def inspect_task(
    *,
    task: CoverageTask,
    contract: V3ProposalCoverageContract,
) -> V3P01MonthCoverageEvidence:
    start, end = month_bounds(task.month)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    expected_minutes = int((end - start).total_seconds() // 60)
    timestamps_by_family = {
        source.family_id: read_timestamps(source=source, month=task.month)
        for source in task.sources
    }
    synchronized = set.intersection(*timestamps_by_family.values())
    synchronized_count = len(synchronized)
    fraction = Decimal(synchronized_count) / Decimal(expected_minutes)
    maximum_gap = maximum_gap_minutes(
        timestamps=synchronized,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    reasons = []
    if fraction < contract.minimum_calendar_month_coverage_fraction:
        reasons.append("MONTH_COVERAGE_BELOW_FLOOR")
    if maximum_gap > contract.maximum_single_gap_minutes:
        reasons.append("MAXIMUM_GAP_EXCEEDS_LIMIT")
    return V3P01MonthCoverageEvidence(
        symbol=task.symbol,
        month=task.month,
        family_archive_sha256={
            source.family_id: source.archive_sha256
            for source in task.sources
        },
        family_row_counts={
            source.family_id: source.row_count for source in task.sources
        },
        expected_minute_count=expected_minutes,
        synchronized_minute_count=synchronized_count,
        missing_synchronized_minute_count=(
            expected_minutes - synchronized_count
        ),
        synchronized_coverage_fraction=fraction,
        maximum_consecutive_gap_minutes=maximum_gap,
        first_synchronized_timestamp_ms=(
            min(synchronized) if synchronized else None
        ),
        last_synchronized_timestamp_ms=(
            max(synchronized) if synchronized else None
        ),
        month_coverage_pass=not reasons,
        reason_codes=reasons,
    )


def collect_month_records(
    *,
    tasks: list[CoverageTask],
    contract: V3ProposalCoverageContract,
    workers: int,
) -> list[V3P01MonthCoverageEvidence]:
    records = []
    executor = ProcessPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(inspect_task, task=task, contract=contract): task
        for task in tasks
    }
    try:
        for completed, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:
                for pending in futures:
                    pending.cancel()
                raise RuntimeError(
                    "V3P01 timestamp coverage aborted at "
                    f"{task.symbol}/{task.month}: {type(exc).__name__}: {exc}"
                ) from exc
            if completed % 25 == 0 or completed == len(futures):
                print(
                    f"V3P01 timestamp coverage: {completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return sorted(records, key=lambda item: item.key)


def build_qualifications(
    *,
    month_records: list[V3P01MonthCoverageEvidence],
    p01_result: V2P01FullAcquisitionResult,
    contract: V3ProposalCoverageContract,
) -> list[V3P01SymbolCoverageQualification]:
    p01_qualifications = {
        item.symbol: item for item in p01_result.symbol_qualifications
    }
    funding_counts = {
        symbol: sum(
            record.symbol == symbol
            and record.family_id == "um_funding_rate_events"
            for record in p01_result.records
        )
        for symbol in p01_qualifications
    }
    qualifications = []
    for symbol in sorted(p01_qualifications):
        records = [item for item in month_records if item.symbol == symbol]
        expected = sum(item.expected_minute_count for item in records)
        synchronized = sum(
            item.synchronized_minute_count for item in records
        )
        fraction = Decimal(synchronized) / Decimal(expected)
        p01_qualification = p01_qualifications[symbol]
        reasons = []
        if fraction < contract.minimum_total_coverage_fraction:
            reasons.append("TOTAL_COVERAGE_BELOW_FLOOR")
        if not all(item.month_coverage_pass for item in records):
            reasons.append("ONE_OR_MORE_MONTHS_FAIL")
        if funding_counts[symbol] != 24:
            reasons.append("FUNDING_ARCHIVE_MATRIX_INCOMPLETE")
        if not (
            p01_qualification.current_spot_filter_proxy_pass
            and p01_qualification.current_futures_filter_proxy_pass
        ):
            reasons.append("CURRENT_FILTER_PROXY_FAIL")
        qualifications.append(
            V3P01SymbolCoverageQualification(
                symbol=symbol,
                expected_minute_count=expected,
                synchronized_minute_count=synchronized,
                synchronized_coverage_fraction=fraction,
                passing_month_count=sum(
                    item.month_coverage_pass for item in records
                ),
                maximum_consecutive_gap_minutes=max(
                    item.maximum_consecutive_gap_minutes for item in records
                ),
                funding_archive_count=funding_counts[symbol],
                current_spot_filter_proxy_pass=(
                    p01_qualification.current_spot_filter_proxy_pass
                ),
                current_futures_filter_proxy_pass=(
                    p01_qualification.current_futures_filter_proxy_pass
                ),
                qualification_pass=not reasons,
                reason_codes=reasons,
            )
        )
    return qualifications


def build_summary(
    *,
    month_records: list[V3P01MonthCoverageEvidence],
    qualifications: list[V3P01SymbolCoverageQualification],
) -> V3P01CoverageSummary:
    qualified = sorted(
        item.symbol for item in qualifications if item.qualification_pass
    )
    disqualified = sorted(
        item.symbol for item in qualifications if not item.qualification_pass
    )
    expected = sum(item.expected_minute_count for item in month_records)
    synchronized = sum(
        item.synchronized_minute_count for item in month_records
    )
    return V3P01CoverageSummary(
        expected_minute_count=expected,
        synchronized_minute_count=synchronized,
        missing_synchronized_minute_count=expected - synchronized,
        qualified_symbol_count=len(qualified),
        disqualified_symbol_count=len(disqualified),
        qualified_symbols=qualified,
        disqualified_symbols=disqualified,
    )


def authoritative_result(
    *,
    generated_at: datetime,
    charter: V3MechanismDiscoveryCharter,
    register: V3MechanismProposalRegister,
    p01_result: V2P01FullAcquisitionResult,
    month_records: list[V3P01MonthCoverageEvidence],
) -> V3P01TimestampCoverageResult:
    contract = register.proposals[0].coverage_contract
    qualifications = build_qualifications(
        month_records=month_records,
        p01_result=p01_result,
        contract=contract,
    )
    summary = build_summary(
        month_records=month_records,
        qualifications=qualifications,
    )
    return build_v3_p01_timestamp_coverage_result(
        generated_at=generated_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        p01_acquisition_result_evidence_hash=(
            p01_result.result_evidence_hash
        ),
        runner_contract_hash=runner_contract_hash(),
        coverage_contract=contract,
        month_records=month_records,
        symbol_qualifications=qualifications,
        summary=summary,
        limitations=[
            (
                "This result inspects source identity, row structure, and timestamp "
                "coverage only; no market numeric value was parsed."
            ),
            (
                "Coverage feasibility cannot prove cointegration, convergence, "
                "positive expectancy, or profitability."
            ),
            (
                "Current spot and futures filters remain nonhistorical proxies and "
                "cannot prove 2023-2024 order acceptance."
            ),
            (
                "Historical fee, filter, funding-rule, margin, liquidation, and ADL "
                "metadata remain separate execution dependencies."
            ),
            (
                "A pass permits only a separate cross-asset synthetic foundation and "
                "metadata protocol, not primary selection or return testing."
            ),
            (
                "Pair selection, hedge estimation, signal arithmetic, parameters, "
                "costs, and development gates remain undefined."
            ),
            (
                "Validation, holdout, forward, Pine, paper, sandbox, live, and capital "
                "permissions remain closed."
            ),
        ],
    )


def write_result(
    path: Path,
    result: V3P01TimestampCoverageResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V3P01TimestampCoverageResult.model_validate_json(serialized) != result:
        raise ValueError("V3P01 coverage result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale V3P01 output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run(args) -> V3P01TimestampCoverageResult:
    if args.output.exists():
        raise ValueError("V3P01 coverage result exists; use --audit")
    charter, register, _, p01_result = load_inputs(args)
    tasks = render_tasks(
        evidence_root=args.evidence_root,
        p01_result=p01_result,
    )
    month_records = collect_month_records(
        tasks=tasks,
        contract=register.proposals[0].coverage_contract,
        workers=args.workers,
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        charter=charter,
        register=register,
        p01_result=p01_result,
        month_records=month_records,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"qualified={result.summary.qualified_symbol_count}",
        flush=True,
    )
    return audit(args)


def audit(args) -> V3P01TimestampCoverageResult:
    charter, register, _, p01_result = load_inputs(args)
    result = V3P01TimestampCoverageResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p01_timestamp_coverage_result(result)
        or result.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
        or result.proposal_register_evidence_hash
        != register.register_evidence_hash
        or result.p01_acquisition_result_evidence_hash
        != p01_result.result_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.coverage_contract
        != register.proposals[0].coverage_contract
    ):
        raise ValueError("V3P01 coverage result audit failed")
    print(
        "PASS "
        f"v3p01_coverage={result.result_evidence_hash} "
        f"qualified={result.summary.qualified_symbol_count} "
        f"decision={result.decision} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit V3P01 timestamp-only synchronized source coverage."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--p01-protocol",
        type=Path,
        default=DEFAULT_P01_PROTOCOL,
    )
    parser.add_argument("--p01-result", type=Path, default=DEFAULT_P01_RESULT)
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
            run(args)
        else:
            audit(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
