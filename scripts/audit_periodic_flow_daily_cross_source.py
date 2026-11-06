from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_daily_cross_source import (  # noqa: E402
    PeriodicFlowDailyCrossSourceAudit,
    PeriodicFlowDailyCrossSourceProtocol,
    PeriodicFlowDailyCrossSourceResult,
    audit_daily_cross_audit,
    audit_daily_cross_protocol,
    audit_daily_cross_result,
    build_daily_cross_audit,
)
from scripts.run_periodic_flow_daily_cross_source import (  # noqa: E402
    file_sha256,
    inspect_pair,
    target_path,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_audit_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")


def load_inputs(
    protocol_path: Path,
    result_path: Path,
) -> tuple[PeriodicFlowDailyCrossSourceProtocol, PeriodicFlowDailyCrossSourceResult]:
    protocol = PeriodicFlowDailyCrossSourceProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = PeriodicFlowDailyCrossSourceResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_daily_cross_protocol(protocol)
        or not audit_daily_cross_result(result)
        or result.protocol_file_sha256 != file_sha256(protocol_path)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
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
        raise ValueError("Q1 daily cross-source lineage or authority failed")
    return protocol, result


def reconstruct(
    *,
    protocol: PeriodicFlowDailyCrossSourceProtocol,
    result: PeriodicFlowDailyCrossSourceResult,
    evidence_root: Path,
) -> dict[str, str]:
    attempts = {
        item.family: item.payload_get_attempt_count for item in result.archive_evidence
    }
    rebuilt = inspect_pair(
        protocol=protocol,
        evidence_root=evidence_root,
        attempt_counts=attempts,
    )
    if rebuilt != result.archive_evidence:
        raise ValueError("Q1 daily cross-source raw reconstruction changed")
    hashes = {}
    for target in protocol.targets:
        path = target_path(evidence_root, target)
        digest = file_sha256(path)
        if digest != target.published_archive_sha256:
            raise ValueError("Q1 daily cross-source archive hash changed")
        hashes[target.family] = digest
    return hashes


def authoritative_audit(
    *,
    audited_at: datetime,
    result_path: Path,
    result: PeriodicFlowDailyCrossSourceResult,
    archive_hashes: dict[str, str],
) -> PeriodicFlowDailyCrossSourceAudit:
    return build_daily_cross_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        archive_file_sha256=archive_hashes,
        decision=result.decision,
    )


def write_audit(path: Path, audit: PeriodicFlowDailyCrossSourceAudit) -> None:
    if path.exists():
        raise ValueError("Q1 daily cross-source audit exists; use --check")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowDailyCrossSourceAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 daily cross-source audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 daily audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowDailyCrossSourceAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    hashes = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        result_path=args.result,
        result=result,
        archive_hashes=hashes,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} decision={audit.decision}",
        flush=True,
    )
    return audit


def run_check(args) -> PeriodicFlowDailyCrossSourceAudit:
    protocol, result = load_inputs(args.protocol, args.result)
    hashes = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = PeriodicFlowDailyCrossSourceAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        result_path=args.result,
        result=result,
        archive_hashes=hashes,
    )
    if audit != expected or not audit_daily_cross_audit(audit):
        raise ValueError("Q1 daily cross-source audit is not reproducible")
    print(
        f"PASS q1_daily_cross_audit={audit.audit_evidence_hash} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit Q1 USD-M daily cross-source adjudication."
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
