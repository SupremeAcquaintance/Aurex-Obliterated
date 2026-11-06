from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_overlap_census import (  # noqa: E402
    PeriodicFlowOverlapCensusAudit,
    PeriodicFlowOverlapCensusProtocol,
    PeriodicFlowOverlapCensusResult,
    audit_overlap_census_audit,
    audit_overlap_census_protocol,
    audit_overlap_census_result,
    build_overlap_census_audit,
)
from scripts.run_periodic_flow_overlap_census import (  # noqa: E402
    file_sha256,
    localize_overlap,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_overlap_census_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_overlap_census_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_overlap_census_audit_v1.json"
)


def load_inputs(
    protocol_path: Path,
    result_path: Path,
) -> tuple[PeriodicFlowOverlapCensusProtocol, PeriodicFlowOverlapCensusResult]:
    protocol = PeriodicFlowOverlapCensusProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = PeriodicFlowOverlapCensusResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_overlap_census_protocol(protocol)
        or not audit_overlap_census_result(result)
        or result.protocol_file_sha256 != file_sha256(protocol_path)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.archive_payload_requests_made
        or result.archive_payload_bytes
        or result.price_or_quantity_values_parsed
        or result.return_metrics_calculated
        or result.strategy_candidates_created
        or result.orders_submitted
        or result.authorizes_paper_operation
        or result.authorizes_testnet_strategy_orders
        or result.authorizes_production
        or result.authorizes_live
        or result.real_net_profit_usd != "0"
    ):
        raise ValueError("Q1 overlap census lineage or authority boundary failed")
    return protocol, result


def authoritative_audit(
    *,
    audited_at: datetime,
    result_path: Path,
    result: PeriodicFlowOverlapCensusResult,
) -> PeriodicFlowOverlapCensusAudit:
    return build_overlap_census_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        overlap_event=result.overlap_event,
        checksum_archive_sha256={
            item.family: item.archive_sha256
            for item in result.checksum_records
            if item.archive_sha256 is not None
        },
        decision=result.decision,
    )


def reconstruct(
    protocol: PeriodicFlowOverlapCensusProtocol,
    result: PeriodicFlowOverlapCensusResult,
) -> None:
    if localize_overlap(protocol) != result.overlap_event:
        raise ValueError("Q1 overlap localization reconstruction changed")
    for record in result.checksum_records:
        if record.availability != "PRESENT" or record.archive_sha256 is None:
            raise ValueError("Q1 overlap audit requires both daily checksums")


def write_audit(path: Path, audit: PeriodicFlowOverlapCensusAudit) -> None:
    if path.exists():
        raise ValueError("Q1 overlap census audit exists; use --check")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowOverlapCensusAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 overlap census audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 overlap audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowOverlapCensusAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    reconstruct(protocol, result)
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        result_path=args.result,
        result=result,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"day={audit.overlap_event.utc_day} decision={audit.decision}",
        flush=True,
    )
    return audit


def run_check(args) -> PeriodicFlowOverlapCensusAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    reconstruct(protocol, result)
    audit = PeriodicFlowOverlapCensusAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        result_path=args.result,
        result=result,
    )
    if audit != expected or not audit_overlap_census_audit(audit):
        raise ValueError("Q1 overlap census audit is not reproducible")
    print(
        f"PASS q1_overlap_audit={audit.audit_evidence_hash} "
        f"day={audit.overlap_event.utc_day} decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit Q1 overlap localization and daily checksum evidence."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
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
