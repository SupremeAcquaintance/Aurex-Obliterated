from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_overlap_census import (  # noqa: E402
    PeriodicFlowOverlapCensusProtocol,
    audit_overlap_census_protocol,
    build_overlap_census_protocol,
)
from aurex.backtest_engine.periodic_flow_payload_gap_remediation import (  # noqa: E402
    Q1_GAP_FAIL_AUTHORIZATION,
    Q1_GAP_FAIL_DECISION,
    PeriodicFlowGapRemediationAudit,
    PeriodicFlowGapRemediationResult,
    audit_gap_remediation_audit,
    audit_gap_remediation_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PARENT_RESULT = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_result_v1.json"
)
DEFAULT_PARENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_overlap_census_protocol_v1.json"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "freeze_periodic_flow_overlap_census.py",
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


def load_parent(
    result_path: Path,
    audit_path: Path,
) -> tuple[PeriodicFlowGapRemediationResult, PeriodicFlowGapRemediationAudit]:
    result = PeriodicFlowGapRemediationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    audit = PeriodicFlowGapRemediationAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_gap_remediation_result(result)
        or not audit_gap_remediation_audit(audit)
        or audit.result_file_sha256 != file_sha256(result_path)
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.protocol_evidence_hash != result.protocol_evidence_hash
        or result.decision != Q1_GAP_FAIL_DECISION
        or result.next_authorization != Q1_GAP_FAIL_AUTHORIZATION
        or result.raw_trade_range_overlap_count != 1
        or result.aggregate_trade_id_gap_count != 0
        or result.aggregate_trade_id_non_increasing_count != 0
        or result.raw_trade_span_invalid_count != 0
        or result.timestamp_regression_count != 0
        or result.network_requests_made
        or result.price_or_quantity_values_parsed
        or result.return_metrics_calculated
        or result.strategy_candidates_created
        or result.strategy_executions
        or result.orders_submitted
    ):
        raise ValueError("Q1 overlap census parent failure is not isolated")
    return result, audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    parent_result_path: Path,
    parent_audit_path: Path,
) -> PeriodicFlowOverlapCensusProtocol:
    result, audit = load_parent(parent_result_path, parent_audit_path)
    archive_path = Path(
        "data/evidence/source_snapshots/q1_periodic_flow_payload_pilot_v1/"
        "USD_M_PERPETUAL/BTCUSDT-aggTrades-2020-01.zip"
    )
    if not archive_path.is_file() or file_sha256(archive_path) != result.archive_sha256:
        raise ValueError("Q1 overlap census archive lineage failed")
    return build_overlap_census_protocol(
        frozen_at=frozen_at,
        parent_result_file_sha256=file_sha256(parent_result_path),
        parent_result_evidence_hash=result.result_evidence_hash,
        parent_audit_file_sha256=file_sha256(parent_audit_path),
        parent_audit_evidence_hash=audit.audit_evidence_hash,
        target_archive_sha256=result.archive_sha256,
        builder_contract_hash=builder_contract_hash(),
        limitations=(
            "The two upstream STOP results remain immutable and unsuperseded.",
            "Only the single known USD-M raw-range overlap may be localized.",
            "The overlap UTC day is derived mechanically from its current-row timestamp.",
            "Only two official daily CHECKSUM text files may be requested.",
            "No daily ZIP payload, price, quantity, return, or outcome may be accessed.",
            "A pass authorizes only a separate daily cross-source payload protocol.",
            "No candidate, Pine, paper, strategy-order, production, or live authority is created.",
            "Daily source availability cannot resolve the overlap by itself.",
            "Real net profit remains zero dollars.",
        ),
    )


def write_protocol(path: Path, protocol: PeriodicFlowOverlapCensusProtocol) -> None:
    if path.exists():
        raise ValueError("Q1 overlap census protocol exists; use --check")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if PeriodicFlowOverlapCensusProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 overlap census protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 overlap protocol transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowOverlapCensusProtocol:
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "payload_requests=0 market_values=0",
        flush=True,
    )
    return protocol


def run_check(args) -> PeriodicFlowOverlapCensusProtocol:
    protocol = PeriodicFlowOverlapCensusProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    if protocol != expected or not audit_overlap_census_protocol(protocol):
        raise ValueError("Q1 overlap census protocol is not reproducible")
    print(
        f"PASS q1_overlap_protocol={protocol.protocol_evidence_hash} "
        "checksum_targets=2",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or check the Q1 overlap daily-source census protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--parent-result", type=Path, default=DEFAULT_PARENT_RESULT)
    parser.add_argument("--parent-audit", type=Path, default=DEFAULT_PARENT_AUDIT)
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
