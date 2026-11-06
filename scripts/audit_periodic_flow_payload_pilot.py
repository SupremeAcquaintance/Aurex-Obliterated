from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_payload_pilot import (  # noqa: E402
    PeriodicFlowPayloadPilotAudit,
    PeriodicFlowPayloadPilotProtocol,
    PeriodicFlowPayloadPilotResult,
    audit_periodic_flow_payload_audit,
    audit_periodic_flow_payload_protocol,
    audit_periodic_flow_payload_result,
    build_periodic_flow_payload_audit,
)
from scripts.run_periodic_flow_payload_pilot import (  # noqa: E402
    file_sha256,
    inspect_pair,
    target_archive_path,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_audit_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")


def load_inputs(
    protocol_path: Path,
    result_path: Path,
) -> tuple[PeriodicFlowPayloadPilotProtocol, PeriodicFlowPayloadPilotResult]:
    protocol = PeriodicFlowPayloadPilotProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = PeriodicFlowPayloadPilotResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_periodic_flow_payload_protocol(protocol)
        or not audit_periodic_flow_payload_result(result)
        or result.protocol_file_sha256 != file_sha256(protocol_path)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.payload_get_attempt_count > protocol.maximum_payload_get_attempts
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
        raise ValueError("Q1 payload result lineage or authority boundary failed")
    return protocol, result


def reconstruct(
    *,
    protocol: PeriodicFlowPayloadPilotProtocol,
    result: PeriodicFlowPayloadPilotResult,
    evidence_root: Path,
) -> tuple[dict[str, str], dict[str, int]]:
    request_counts = {
        item.product: item.payload_get_attempt_count
        for item in result.archive_evidence
    }
    rebuilt_evidence, rebuilt_clock = inspect_pair(
        protocol=protocol,
        evidence_root=evidence_root,
        request_counts=request_counts,
    )
    if (
        rebuilt_evidence != result.archive_evidence
        or rebuilt_clock != result.paired_clock_evidence
    ):
        raise ValueError("Q1 payload raw-archive reconstruction changed")
    archive_hashes = {}
    archive_bytes = {}
    for target in protocol.targets:
        path = target_archive_path(evidence_root, target)
        digest = file_sha256(path)
        if digest != target.published_archive_sha256:
            raise ValueError(f"Q1 payload raw hash changed: {target.product}")
        archive_hashes[target.product] = digest
        archive_bytes[target.product] = path.stat().st_size
    return archive_hashes, archive_bytes


def authoritative_audit(
    *,
    audited_at: datetime,
    result_path: Path,
    result: PeriodicFlowPayloadPilotResult,
    archive_hashes: dict[str, str],
    archive_bytes: dict[str, int],
) -> PeriodicFlowPayloadPilotAudit:
    return build_periodic_flow_payload_audit(
        audited_at=audited_at,
        result_path=result_path.as_posix(),
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        archive_file_sha256=archive_hashes,
        archive_file_bytes=archive_bytes,
        decision=result.decision,
    )


def write_audit(path: Path, audit: PeriodicFlowPayloadPilotAudit) -> None:
    if path.exists():
        raise ValueError("Q1 payload pilot audit already exists; use --check")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowPayloadPilotAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 payload audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 payload audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowPayloadPilotAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    archive_hashes, archive_bytes = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        result_path=args.result,
        result=result,
        archive_hashes=archive_hashes,
        archive_bytes=archive_bytes,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"archives={audit.archive_count} decision={audit.decision}",
        flush=True,
    )
    return audit


def run_check(args) -> PeriodicFlowPayloadPilotAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    archive_hashes, archive_bytes = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = PeriodicFlowPayloadPilotAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        result_path=args.result,
        result=result,
        archive_hashes=archive_hashes,
        archive_bytes=archive_bytes,
    )
    if audit != expected or not audit_periodic_flow_payload_audit(audit):
        raise ValueError("Q1 payload pilot audit is not reproducible")
    print(
        f"PASS q1_payload_audit={audit.audit_evidence_hash} "
        f"result_file={audit.result_file_sha256} archives={audit.archive_count} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Independently rebuild and audit the Q1 paired payload pilot."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
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
