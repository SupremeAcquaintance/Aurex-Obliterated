from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_payload_gap_remediation import (  # noqa: E402
    PeriodicFlowGapRemediationAudit,
    PeriodicFlowGapRemediationProtocol,
    PeriodicFlowGapRemediationResult,
    audit_gap_remediation_audit,
    audit_gap_remediation_protocol,
    audit_gap_remediation_result,
    build_gap_remediation_audit,
)
from scripts.run_periodic_flow_payload_gap_remediation import (  # noqa: E402
    authoritative_result,
    file_sha256,
    scan_archive,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_audit_v1.json"
)


def load_inputs(
    protocol_path: Path,
    result_path: Path,
) -> tuple[PeriodicFlowGapRemediationProtocol, PeriodicFlowGapRemediationResult]:
    protocol = PeriodicFlowGapRemediationProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = PeriodicFlowGapRemediationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_gap_remediation_protocol(protocol)
        or not audit_gap_remediation_result(result)
        or result.protocol_file_sha256 != file_sha256(protocol_path)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.network_requests_made
        or result.price_or_quantity_values_parsed
        or result.features_calculated
        or result.parameters_defined
        or result.return_metrics_calculated
        or result.validation_outcomes_accessed
        or result.holdout_accessed
        or result.strategy_candidates_created
        or result.strategy_executions
        or result.orders_submitted
        or result.authorizes_pine_deployment
        or result.authorizes_paper_operation
        or result.authorizes_testnet_strategy_orders
        or result.authorizes_production
        or result.authorizes_live
        or result.real_net_profit_usd != "0"
    ):
        raise ValueError("Q1 gap remediation lineage or authority boundary failed")
    return protocol, result


def reconstruct(
    *,
    protocol_path: Path,
    protocol: PeriodicFlowGapRemediationProtocol,
    result: PeriodicFlowGapRemediationResult,
) -> None:
    rebuilt = authoritative_result(
        generated_at=result.generated_at,
        protocol_path=protocol_path,
        protocol=protocol,
        scan=scan_archive(protocol),
    )
    if rebuilt != result:
        raise ValueError("Q1 gap remediation raw reconstruction changed")


def authoritative_audit(
    *,
    audited_at: datetime,
    result_path: Path,
    result: PeriodicFlowGapRemediationResult,
) -> PeriodicFlowGapRemediationAudit:
    return build_gap_remediation_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        archive_sha256=result.archive_sha256,
        gap_manifest_hash=result.gap_manifest_hash,
        gap_event_count=result.gap_event_count,
        total_skipped_raw_trade_ids=result.total_skipped_raw_trade_ids,
        decision=result.decision,
    )


def write_audit(path: Path, audit: PeriodicFlowGapRemediationAudit) -> None:
    if path.exists():
        raise ValueError("Q1 gap remediation audit exists; use --check")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowGapRemediationAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 gap remediation audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 gap audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowGapRemediationAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    reconstruct(protocol_path=args.protocol, protocol=protocol, result=result)
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        result_path=args.result,
        result=result,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"gaps={audit.gap_event_count} decision={audit.decision}",
        flush=True,
    )
    return audit


def run_check(args) -> PeriodicFlowGapRemediationAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    reconstruct(protocol_path=args.protocol, protocol=protocol, result=result)
    audit = PeriodicFlowGapRemediationAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        result_path=args.result,
        result=result,
    )
    if audit != expected or not audit_gap_remediation_audit(audit):
        raise ValueError("Q1 gap remediation audit is not reproducible")
    print(
        f"PASS q1_gap_audit={audit.audit_evidence_hash} "
        f"gaps={audit.gap_event_count} decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Independently audit the local Q1 USD-M gap remediation."
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
