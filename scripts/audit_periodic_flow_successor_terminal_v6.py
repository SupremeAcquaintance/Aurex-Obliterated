from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v6 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV6,
    PeriodicFlowSuccessorTransportAttemptAuditV6,
    audit_successor_terminal_audit_v6,
    build_successor_terminal_audit_v6,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV6,
    PeriodicFlowSuccessorCheckpointV6,
    audit_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    source_contract_hash,
    target_archive_path,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    _attempt_path,
    marker_state_v3,
)
from scripts.run_periodic_flow_successor_acquisition_v6 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    DEFAULT_V5_CHECKPOINT,
    DEFAULT_V5_RESULT,
    DEFAULT_V5_TERMINAL_AUDIT,
    DEFAULT_V5_TRANSPORT_AMENDMENT,
    current_runner_source_hash_v6,
    load_context,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v6.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_terminal_audit_v6.py"
)
SCRIPT_PATH = Path("scripts/audit_periodic_flow_successor_terminal_v6.py")


def auditor_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def authoritative_audit(*, args, audited_at):
    context = load_context(args)
    checkpoint = PeriodicFlowSuccessorCheckpointV6.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV6.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        not audit_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_hash(result, "result_evidence_hash")
        or result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
        or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        or result.runner_source_hash != current_runner_source_hash_v6()
        or result.decision != "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        or result.hard_failure_target_key != "2023-04|USD_M_PERPETUAL"
        or result.hard_failure_reason is None
        or "getaddrinfo failed" not in result.hard_failure_reason
        or len(checkpoint.archive_evidence) != 56
        or len(checkpoint.paired_month_evidence) != 17
        or len(checkpoint.excluded_month_evidence) != 11
    ):
        raise ValueError("Q1 successor v6 terminal lineage changed")
    target = next(
        item
        for item in context.protocol.targets
        if item.month == "2023-04" and item.product == "USD_M_PERPETUAL"
    )
    attempts = []
    for number in range(1, 25):
        request_path = _attempt_path(args.acquisition_root, target, number, "request")
        response_path = _attempt_path(args.acquisition_root, target, number, "response")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if (
            request.get("target_key") != "2023-04|USD_M_PERPETUAL"
            or response.get("target_key") != "2023-04|USD_M_PERPETUAL"
        ):
            raise ValueError(f"Q1 successor v6 attempt {number} marker changed")
        attempts.append(
            PeriodicFlowSuccessorTransportAttemptAuditV6(
                attempt=number,
                request_file_sha256=file_sha256(request_path),
                response_file_sha256=file_sha256(response_path),
                range_start=request["range_start"],
                status=response["status"],
                bytes_received=response["bytes_received"],
                partial_bytes_after_attempt=response["partial_bytes_after_attempt"],
                failure_class=response["failure_class"],
                exception_type=response["exception_type"],
                exception_message=response["exception_message"],
            )
        )
    destination = target_archive_path(args.acquisition_root, target)
    partial = destination.with_name(f"{destination.name}.part")
    state = marker_state_v3(args.acquisition_root)
    if (
        state.request_count != 38
        or state.response_count != 38
        or state.payload_bytes_received != 6_658_445_428
        or state.manifest_hash != checkpoint.request_marker_manifest_hash
        or destination.exists()
        or not partial.is_file()
        or partial.stat().st_size != 184_135_287
        or file_sha256(partial)
        != "1b94bfc412aa3683c7b88c3af1ca5848d3d76219f155872877791cee4b177fd2"
    ):
        raise ValueError("Q1 successor v6 terminal transport evidence changed")
    return build_successor_terminal_audit_v6(
        audited_at=audited_at,
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        validator_amendment_file_sha256=file_sha256(args.amendment),
        validator_amendment_evidence_hash=context.protocol.amendment_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        execution_contract_audit_file_sha256=file_sha256(
            args.execution_contract_audit
        ),
        execution_contract_audit_evidence_hash=(
            context.contract_audit.audit_evidence_hash
        ),
        runner_source_hash=current_runner_source_hash_v6(),
        auditor_contract_hash=auditor_contract_hash(),
        frozen_failure_reason=result.hard_failure_reason,
        attempts=tuple(attempts),
        request_marker_manifest_hash=state.manifest_hash,
        findings=(
            "All 38 v6 request markers have exactly one matching response marker.",
            "Attempt 14 received 184135287 bytes before an incomplete body.",
            "Attempts 15 through 24 preserved the exact partial byte count.",
            "DNS resolution failure exhausted the frozen per-target attempt budget.",
            "The failed target has no completed archive and one hash-bound partial.",
            "The partial remains immutable v6 evidence and is not adopted by v7.",
            "The 56 inspected archive records remain checksum-verifiable.",
            "The April Spot archive passed before the USD-M transport stop.",
            "A fresh continuation may seed the complete v6 checkpoint.",
            "No outcome, strategy, signal, execution, or order was created.",
        ),
    )


def _write(path: Path, audit: PeriodicFlowSuccessorTerminalAuditV6) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v6 audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(
        audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Q1 successor v6 stop.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--v5-checkpoint", type=Path, default=DEFAULT_V5_CHECKPOINT)
    parser.add_argument("--v5-result", type=Path, default=DEFAULT_V5_RESULT)
    parser.add_argument(
        "--v5-terminal-audit", type=Path, default=DEFAULT_V5_TERMINAL_AUDIT
    )
    parser.add_argument(
        "--v5-transport-amendment",
        type=Path,
        default=DEFAULT_V5_TRANSPORT_AMENDMENT,
    )
    parser.add_argument(
        "--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTerminalAuditV6.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_successor_terminal_audit_v6(stored):
                raise ValueError("Stored Q1 successor v6 audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        _write(args.output, audit)
        print(f"AUDITED {args.output} {audit.audit_evidence_hash}", flush=True)
        return 0
    except (OSError, StopIteration, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
