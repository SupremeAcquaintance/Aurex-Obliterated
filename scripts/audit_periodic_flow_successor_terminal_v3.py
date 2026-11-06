from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v3 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV3,
    PeriodicFlowSuccessorTransportAttemptAuditV3,
    audit_successor_terminal_audit_v3,
    build_successor_terminal_audit_v3,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV3,
    PeriodicFlowSuccessorCheckpointV3,
    audit_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    source_contract_hash,
    target_archive_path,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    _attempt_path,
    current_runner_source_hash_v3,
    load_context,
    marker_state_v3,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v3.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_terminal_audit_v3.py"
)
SCRIPT_PATH = Path("scripts/audit_periodic_flow_successor_terminal_v3.py")


def auditor_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def _attempts(*, root: Path, target, context):
    records = []
    for attempt in range(1, 13):
        request_path = _attempt_path(root, target, attempt, "request")
        response_path = _attempt_path(root, target, attempt, "response")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        common = {
            "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
            "transport_amendment_evidence_hash": (
                context.protocol.amendment_evidence_hash
            ),
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "target_key": "2020-08|USD_M_PERPETUAL",
            "month": "2020-08",
            "product": "USD_M_PERPETUAL",
            "family": "trades",
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
        }
        if (
            any(request.get(key) != value for key, value in common.items())
            or any(response.get(key) != value for key, value in common.items())
            or request.get("range_start") != (0 if attempt == 1 else 86_150_831)
            or response.get("final_url") != target.archive_url
            or response.get("content_encoding") != "identity"
            or response.get("outcome") != "TRANSIENT"
        ):
            raise ValueError(f"Q1 successor v3 attempt {attempt} marker changed")
        records.append(
            PeriodicFlowSuccessorTransportAttemptAuditV3(
                attempt=attempt,
                request_file_sha256=file_sha256(request_path),
                response_file_sha256=file_sha256(response_path),
                range_start=request["range_start"],
                status=response["status"],
                expected_total_bytes=response["expected_total_bytes"],
                bytes_received=response["bytes_received"],
                partial_bytes_after_attempt=response["partial_bytes_after_attempt"],
                failure_class=response["failure_class"],
                exception_type=response["exception_type"],
                exception_message=response["exception_message"],
            )
        )
    return tuple(records)


def authoritative_audit(
    *, args: argparse.Namespace, audited_at: datetime
) -> PeriodicFlowSuccessorTerminalAuditV3:
    context = load_context(args)
    checkpoint = PeriodicFlowSuccessorCheckpointV3.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV3.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        not audit_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_hash(result, "result_evidence_hash")
        or checkpoint.runner_source_hash != current_runner_source_hash_v3()
        or result.runner_source_hash != current_runner_source_hash_v3()
        or result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
        or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        or result.decision != "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        or result.hard_failure_target_key != "2020-08|USD_M_PERPETUAL"
        or result.hard_failure_reason is None
        or "getaddrinfo failed" not in result.hard_failure_reason
        or len(checkpoint.archive_evidence) != 7
        or len(checkpoint.paired_month_evidence) != 2
        or len(checkpoint.excluded_month_evidence) != 1
    ):
        raise ValueError("Q1 successor v3 terminal lineage changed")
    target = next(
        item
        for item in context.protocol.targets
        if item.month == "2020-08" and item.product == "USD_M_PERPETUAL"
    )
    destination = target_archive_path(args.acquisition_root, target)
    partial = destination.with_name(f"{destination.name}.part")
    state = marker_state_v3(args.acquisition_root)
    attempts = _attempts(
        root=args.acquisition_root,
        target=target,
        context=context,
    )
    relative_partial = partial.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    if (
        state.request_count != 17
        or state.response_count != 17
        or state.payload_bytes_received != 583_285_471
        or state.manifest_hash != checkpoint.request_marker_manifest_hash
        or destination.exists()
        or not partial.is_file()
        or partial.stat().st_size != 86_150_831
        or sum(item.bytes_received for item in attempts) != 86_150_831
    ):
        raise ValueError("Q1 successor v3 terminal transport evidence changed")
    return build_successor_terminal_audit_v3(
        audited_at=audited_at,
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        transport_amendment_file_sha256=file_sha256(args.amendment),
        transport_amendment_evidence_hash=context.protocol.amendment_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        execution_contract_audit_file_sha256=file_sha256(
            args.execution_contract_audit
        ),
        execution_contract_audit_evidence_hash=(
            context.contract_audit.audit_evidence_hash
        ),
        runner_source_hash=current_runner_source_hash_v3(),
        auditor_contract_hash=auditor_contract_hash(),
        frozen_failure_reason=result.hard_failure_reason,
        attempts=attempts,
        request_marker_manifest_hash=state.manifest_hash,
        partial_archive_path=relative_partial,
        partial_archive_file_sha256=file_sha256(partial),
        findings=(
            "All 17 v3 request markers have exactly one matching response marker.",
            "Attempts two through twelve failed before receiving a response body "
            "because DNS resolution failed.",
            "The first August USD-M attempt preserved an exact 86150831-byte partial "
            "after an incomplete body.",
            "The completed August USD-M archive does not exist and no archive-integrity "
            "verdict was made.",
            "The terminal stop is valid and immutable but cannot be resumed within the "
            "exhausted v3 contract.",
            "The surviving partial may seed only a separately frozen transport continuation.",
            "No price, quantity, feature, parameter, return, outcome, strategy, or order "
            "was created.",
        ),
    )


def _write(path: Path, audit: PeriodicFlowSuccessorTerminalAuditV3) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v3 terminal audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor v3 terminal audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorTerminalAuditV3.model_validate_json(serialized) != audit:
        raise ValueError("Q1 successor v3 terminal audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the terminal Q1 successor v3 transport stop."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT
    )
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT
    )
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
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
            stored = PeriodicFlowSuccessorTerminalAuditV3.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_successor_terminal_audit_v3(stored):
                raise ValueError("Stored Q1 successor v3 terminal audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                "requests=17 payload_bytes=583285471 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        _write(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "requests=17 payload_bytes=583285471 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
