from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_payload_gap_remediation import (  # noqa: E402
    PeriodicFlowGapRemediationProtocol,
    audit_gap_remediation_protocol,
    build_gap_remediation_protocol,
)
from aurex.backtest_engine.periodic_flow_payload_pilot import (  # noqa: E402
    Q1_PAYLOAD_FAIL_AUTHORIZATION,
    Q1_PAYLOAD_FAIL_DECISION,
    PeriodicFlowPayloadPilotAudit,
    PeriodicFlowPayloadPilotProtocol,
    PeriodicFlowPayloadPilotResult,
    audit_periodic_flow_payload_audit,
    audit_periodic_flow_payload_protocol,
    audit_periodic_flow_payload_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PARENT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_protocol_v1.json"
)
DEFAULT_PARENT_RESULT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_result_v1.json"
)
DEFAULT_PARENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_payload_gap_remediation_protocol_v1.json"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "freeze_periodic_flow_payload_gap_remediation.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "periodic_flow_payload_gap_remediation.py",
    )
    return universe_evidence_hash(
        {
            path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
            for path in paths
        }
    )


def load_parent(
    protocol_path: Path,
    result_path: Path,
    audit_path: Path,
) -> tuple[
    PeriodicFlowPayloadPilotProtocol,
    PeriodicFlowPayloadPilotResult,
    PeriodicFlowPayloadPilotAudit,
]:
    protocol = PeriodicFlowPayloadPilotProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = PeriodicFlowPayloadPilotResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    audit = PeriodicFlowPayloadPilotAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    evidence = {item.product: item for item in result.archive_evidence}
    spot = evidence["SPOT"]
    usd_m = evidence["USD_M_PERPETUAL"]
    if (
        not audit_periodic_flow_payload_protocol(protocol)
        or not audit_periodic_flow_payload_result(result)
        or not audit_periodic_flow_payload_audit(audit)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.result_file_sha256 != file_sha256(result_path)
        or result.decision != Q1_PAYLOAD_FAIL_DECISION
        or result.next_authorization != Q1_PAYLOAD_FAIL_AUTHORIZATION
        or result.authorizes_separate_full_development_acquisition_protocol
        or not spot.archive_pass
        or spot.reason_codes
        or usd_m.archive_pass
        or usd_m.reason_codes != ("RAW_TRADE_ID_GAP",)
        or usd_m.aggregate_trade_id_gap_count != 0
        or usd_m.aggregate_trade_id_non_increasing_count != 0
        or usd_m.raw_trade_span_invalid_count != 0
        or usd_m.timestamp_regression_count != 0
        or not result.paired_clock_evidence.paired_clock_pass
        or result.price_or_quantity_values_parsed
        or result.return_metrics_calculated
        or result.strategy_candidates_created
        or result.strategy_executions
        or result.orders_submitted
    ):
        raise ValueError("Q1 gap remediation parent failure is not narrowly isolated")
    return protocol, result, audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    parent_protocol_path: Path,
    parent_result_path: Path,
    parent_audit_path: Path,
) -> PeriodicFlowGapRemediationProtocol:
    protocol, result, audit = load_parent(
        parent_protocol_path,
        parent_result_path,
        parent_audit_path,
    )
    usd_m = next(
        item for item in result.archive_evidence if item.product == "USD_M_PERPETUAL"
    )
    archive_path = Path("data/evidence") / usd_m.local_path
    if (
        not archive_path.is_file()
        or file_sha256(archive_path) != usd_m.archive_sha256
    ):
        raise ValueError("Q1 gap remediation raw archive lineage failed")
    return build_gap_remediation_protocol(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(parent_protocol_path),
        parent_protocol_evidence_hash=protocol.protocol_evidence_hash,
        parent_result_file_sha256=file_sha256(parent_result_path),
        parent_result_evidence_hash=result.result_evidence_hash,
        parent_audit_file_sha256=file_sha256(parent_audit_path),
        parent_audit_evidence_hash=audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        target_archive_sha256=usd_m.archive_sha256,
        limitations=(
            "The original paired payload pilot remains an immutable STOP result.",
            "This remediation addresses only forward USD-M raw-trade ID discontinuities.",
            "Official documentation motivates an inference; it does not classify individual gaps.",
            "Aggregate IDs must remain contiguous and raw-trade ranges must not overlap.",
            "Gap count, maximum size, and omitted-ID fraction must pass frozen bounds.",
            "Only the existing checksum-pinned local archive may be scanned; "
            "network access is forbidden.",
            "Price, quantity, features, parameters, returns, and outcomes remain forbidden.",
            "A pass authorizes only a separate full-development acquisition protocol.",
            "Pine, paper, testnet strategy-order, production, and live authority remain false.",
            "This source-semantic result cannot establish edge or profitability.",
        ),
    )


def write_protocol(path: Path, protocol: PeriodicFlowGapRemediationProtocol) -> None:
    if path.exists():
        raise ValueError("Q1 gap remediation protocol exists; use --check")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if PeriodicFlowGapRemediationProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 gap remediation protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 gap protocol transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowGapRemediationProtocol:
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        parent_protocol_path=args.parent_protocol,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "network=0 gap_magnitude_unobserved=true",
        flush=True,
    )
    return protocol


def run_check(args) -> PeriodicFlowGapRemediationProtocol:
    protocol = PeriodicFlowGapRemediationProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        parent_protocol_path=args.parent_protocol,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    if protocol != expected or not audit_gap_remediation_protocol(protocol):
        raise ValueError("Q1 gap remediation protocol is not reproducible")
    print(
        f"PASS q1_gap_protocol={protocol.protocol_evidence_hash} "
        "network=0 outcomes=0",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or check the Q1 USD-M raw-ID gap remediation protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--parent-protocol", type=Path, default=DEFAULT_PARENT_PROTOCOL
    )
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
