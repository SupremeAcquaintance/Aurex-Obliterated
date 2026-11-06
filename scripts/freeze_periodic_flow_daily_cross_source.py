from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_daily_cross_source import (  # noqa: E402
    PeriodicFlowDailyCrossSourceProtocol,
    PeriodicFlowDailyPayloadTarget,
    audit_daily_cross_protocol,
    build_daily_cross_protocol,
)
from aurex.backtest_engine.periodic_flow_overlap_census import (  # noqa: E402
    Q1_OVERLAP_PASS_AUTHORIZATION,
    Q1_OVERLAP_PASS_DECISION,
    PeriodicFlowOverlapCensusAudit,
    PeriodicFlowOverlapCensusResult,
    audit_overlap_census_audit,
    audit_overlap_census_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_CENSUS_RESULT = Path(
    "data/evidence/q1_periodic_flow_overlap_census_result_v1.json"
)
DEFAULT_CENSUS_AUDIT = Path(
    "data/evidence/q1_periodic_flow_overlap_census_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_protocol_v1.json"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "freeze_periodic_flow_daily_cross_source.py",
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


def load_inputs(
    result_path: Path,
    audit_path: Path,
) -> tuple[PeriodicFlowOverlapCensusResult, PeriodicFlowOverlapCensusAudit]:
    result = PeriodicFlowOverlapCensusResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    audit = PeriodicFlowOverlapCensusAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_overlap_census_result(result)
        or not audit_overlap_census_audit(audit)
        or audit.result_file_sha256 != file_sha256(result_path)
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.protocol_evidence_hash != result.protocol_evidence_hash
        or audit.overlap_event != result.overlap_event
        or result.decision != Q1_OVERLAP_PASS_DECISION
        or result.next_authorization != Q1_OVERLAP_PASS_AUTHORIZATION
        or not result.authorizes_daily_cross_source_payload_protocol
        or result.overlap_event.utc_day != "2020-01-15"
        or result.overlap_event.overlap_raw_trade_id_count != 1
        or any(
            item.availability != "PRESENT" or item.archive_sha256 is None
            for item in result.checksum_records
        )
        or result.archive_payload_requests_made
        or result.archive_payload_bytes
        or result.price_or_quantity_values_parsed
        or result.return_metrics_calculated
        or result.strategy_candidates_created
        or result.orders_submitted
    ):
        raise ValueError("Q1 daily cross-source authorization lineage failed")
    return result, audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    census_result_path: Path,
    census_audit_path: Path,
) -> PeriodicFlowDailyCrossSourceProtocol:
    result, audit = load_inputs(census_result_path, census_audit_path)
    targets = tuple(
        PeriodicFlowDailyPayloadTarget(
            family=record.family,
            archive_url=record.archive_url,
            published_archive_sha256=record.archive_sha256,
            expected_column_count=7 if record.family == "aggTrades" else 6,
            expected_member_name=(
                f"BTCUSDT-{record.family}-{record.utc_day}.csv"
            ),
        )
        for record in result.checksum_records
    )
    return build_daily_cross_protocol(
        frozen_at=frozen_at,
        census_result_file_sha256=file_sha256(census_result_path),
        census_result_evidence_hash=result.result_evidence_hash,
        census_audit_file_sha256=file_sha256(census_audit_path),
        census_audit_evidence_hash=audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        parent_overlap_event=result.overlap_event,
        targets=targets,
        target_manifest_hash=universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets]}
        ),
        limitations=(
            "The upstream STOP and checksum-census artifacts remain immutable.",
            "Only the two checksum-pinned USD-M daily archives may be downloaded.",
            "The daily aggregate event must exactly reproduce the monthly overlap.",
            "The overlapped raw trade ID must occur exactly once in raw trades.",
            "Price, quantity, quote quantity, returns, and outcomes remain forbidden.",
            "A pass rejects aggTrades as the USD-M research source and authorizes "
            "only a raw-trades metadata census.",
            "No candidate, Pine, paper, strategy-order, production, or live authority is created.",
            "Cross-source adjudication cannot establish edge or profitability.",
            "Real net profit remains zero dollars.",
        ),
    )


def write_protocol(
    path: Path,
    protocol: PeriodicFlowDailyCrossSourceProtocol,
) -> None:
    if path.exists():
        raise ValueError("Q1 daily cross-source protocol exists; use --check")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if PeriodicFlowDailyCrossSourceProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 daily cross-source protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 daily protocol transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowDailyCrossSourceProtocol:
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        census_result_path=args.census_result,
        census_audit_path=args.census_audit,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "targets=2 payload_requests=0",
        flush=True,
    )
    return protocol


def run_check(args) -> PeriodicFlowDailyCrossSourceProtocol:
    protocol = PeriodicFlowDailyCrossSourceProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        census_result_path=args.census_result,
        census_audit_path=args.census_audit,
    )
    if protocol != expected or not audit_daily_cross_protocol(protocol):
        raise ValueError("Q1 daily cross-source protocol is not reproducible")
    print(
        f"PASS q1_daily_cross_protocol={protocol.protocol_evidence_hash} targets=2",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or check the Q1 daily cross-source payload protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--census-result", type=Path, default=DEFAULT_CENSUS_RESULT)
    parser.add_argument("--census-audit", type=Path, default=DEFAULT_CENSUS_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write:
            run_write(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
