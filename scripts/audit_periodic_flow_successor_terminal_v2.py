from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionProtocol,
    PeriodicFlowSuccessorAcquisitionProtocolAudit,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    audit_hash as audit_protocol_hash,
)
from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResult,
    PeriodicFlowSuccessorCheckpoint,
    PeriodicFlowSuccessorExecutionContractAuditV2,
    PeriodicFlowSuccessorExecutionContractV2,
    audit_hash,
)
from aurex.backtest_engine.periodic_flow_successor_terminal_audit import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAudit,
    PeriodicFlowSuccessorTransportAttemptAudit,
    audit_successor_terminal_audit,
    build_successor_terminal_audit,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    marker_state,
    source_contract_hash,
    target_archive_path,
)
from scripts.run_periodic_flow_successor_acquisition import (  # noqa: E402
    current_runner_source_hash,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v2.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v2.json"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v2.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v2.json"
)
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v2"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v2.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_terminal_audit.py"
)
SCRIPT_PATH = Path("scripts/audit_periodic_flow_successor_terminal_v2.py")


def auditor_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def _elapsed_seconds(start: datetime, end: datetime) -> Decimal:
    elapsed = end - start
    return Decimal(
        elapsed.days * 86_400 * 1_000_000
        + elapsed.seconds * 1_000_000
        + elapsed.microseconds
    ) / Decimal(1_000_000)


def _load_attempts(
    *, root: Path, target, protocol_hash: str, contract_hash: str
) -> tuple[PeriodicFlowSuccessorTransportAttemptAudit, ...]:
    destination = target_archive_path(root, target)
    attempts: list[PeriodicFlowSuccessorTransportAttemptAudit] = []
    for attempt in range(1, 4):
        request_path = destination.with_name(
            f"{destination.name}.get.{attempt}.request.json"
        )
        response_path = destination.with_name(
            f"{destination.name}.get.{attempt}.response.json"
        )
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        expected_common = {
            "protocol_evidence_hash": protocol_hash,
            "execution_contract_evidence_hash": contract_hash,
            "target_key": "2020-05|USD_M_PERPETUAL",
            "month": "2020-05",
            "product": "USD_M_PERPETUAL",
            "family": "trades",
            "method": "GET",
            "url": target.archive_url,
            "attempt": attempt,
        }
        if (
            any(request.get(key) != value for key, value in expected_common.items())
            or any(response.get(key) != value for key, value in expected_common.items())
            or request.get("range") is not None
            or request.get("accept") != "application/zip"
            or request.get("accept_encoding") != "identity"
            or response.get("final_url") != target.archive_url
            or response.get("content_encoding") != "identity"
            or response.get("outcome") != "TRANSIENT"
            or set(response)
            != {
                "attempt",
                "bytes_received",
                "completed_at",
                "content_encoding",
                "content_length",
                "execution_contract_evidence_hash",
                "family",
                "final_url",
                "method",
                "month",
                "outcome",
                "product",
                "protocol_evidence_hash",
                "schema_version",
                "status",
                "target_key",
                "url",
            }
        ):
            raise ValueError(f"Q1 successor v2 attempt {attempt} marker changed")
        requested_at = datetime.fromisoformat(request["requested_at"])
        completed_at = datetime.fromisoformat(response["completed_at"])
        attempts.append(
            PeriodicFlowSuccessorTransportAttemptAudit(
                attempt=attempt,
                request_file_sha256=file_sha256(request_path),
                response_file_sha256=file_sha256(response_path),
                requested_at=requested_at,
                completed_at=completed_at,
                duration_seconds=_elapsed_seconds(requested_at, completed_at),
                status=response["status"],
                content_length=response["content_length"],
                bytes_received=response["bytes_received"],
            )
        )
    return tuple(attempts)


def authoritative_audit(
    *, args: argparse.Namespace, audited_at: datetime
) -> PeriodicFlowSuccessorTerminalAudit:
    protocol = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowSuccessorAcquisitionProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV2.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV2.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowSuccessorCheckpoint.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    runner_hash = current_runner_source_hash()
    if (
        not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or not audit_hash(contract, "contract_evidence_hash")
        or not audit_hash(contract_audit, "audit_evidence_hash")
        or not audit_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_hash(result, "result_evidence_hash")
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.parent_protocol_file_sha256 != file_sha256(args.protocol)
        or contract.parent_protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or result.protocol_file_sha256 != file_sha256(args.protocol)
        or result.execution_contract_file_sha256
        != file_sha256(args.execution_contract)
        or result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
        or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        or result.runner_source_hash != runner_hash
        or checkpoint.runner_source_hash != runner_hash
        or result.decision != "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        or result.hard_failure_target_key != "2020-05|USD_M_PERPETUAL"
        or result.hard_failure_reason
        != "Q1 successor payload unresolved for ('2020-05', 'USD_M_PERPETUAL')"
        or len(checkpoint.archive_evidence) != 3
        or len(checkpoint.paired_month_evidence) != 1
        or checkpoint.excluded_month_evidence
    ):
        raise ValueError("Q1 successor v2 terminal lineage changed")
    target = next(
        item
        for item in protocol.targets
        if item.month == "2020-05" and item.product == "USD_M_PERPETUAL"
    )
    if target.reuse_candidate_path is not None:
        raise ValueError("Q1 successor v2 failed target changed to local reuse")
    attempts = _load_attempts(
        root=args.acquisition_root,
        target=target,
        protocol_hash=protocol.protocol_evidence_hash,
        contract_hash=contract.contract_evidence_hash,
    )
    state = marker_state(args.acquisition_root)
    destination = target_archive_path(args.acquisition_root, target)
    partial = destination.with_name(f"{destination.name}.part")
    all_requests = tuple(args.acquisition_root.rglob("*.request.json"))
    all_responses = tuple(args.acquisition_root.rglob("*.response.json"))
    if (
        len(all_requests) != 3
        or len(all_responses) != 3
        or state.request_count != checkpoint.request_marker_count
        or state.response_count != checkpoint.response_marker_count
        or state.payload_bytes_received != checkpoint.cumulative_payload_bytes_received
        or state.manifest_hash != checkpoint.request_marker_manifest_hash
        or destination.exists()
        or partial.exists()
        or tuple(item.bytes_received for item in attempts)
        != (3_597_961, 0, 12_734_069)
        or tuple(item.status for item in attempts) != (200, None, 200)
        or tuple(item.content_length for item in attempts)
        != (370_923_781, None, 370_923_781)
    ):
        raise ValueError("Q1 successor v2 terminal transport evidence changed")
    return build_successor_terminal_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        protocol_audit_file_sha256=file_sha256(args.protocol_audit),
        protocol_audit_evidence_hash=protocol_audit.audit_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        execution_contract_audit_file_sha256=file_sha256(
            args.execution_contract_audit
        ),
        execution_contract_audit_evidence_hash=contract_audit.audit_evidence_hash,
        runner_source_hash=runner_hash,
        auditor_contract_hash=auditor_contract_hash(),
        attempts=attempts,
        request_marker_manifest_hash=state.manifest_hash,
        findings=(
            "All three bounded GET attempts ended as transient transport failures.",
            "Attempts one and three received partial HTTP 200 bodies; attempt two "
            "received no response body.",
            "The response-marker v1 schema records no exception type or message, "
            "so the exact transient cause is not reconstructable.",
            "No completed or partial May 2020 USD-M archive remains in the v2 acquisition root.",
            "No archive checksum or structural inspection was possible for the unresolved target.",
            "The v2 terminal result is internally valid and must not be resumed or overwritten.",
            "A separately frozen v3 transport correction may improve resumability "
            "and failure observability without opening outcomes.",
        ),
    )


def write_audit(path: Path, audit: PeriodicFlowSuccessorTerminalAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor terminal audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor terminal audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorTerminalAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 successor terminal audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the terminal Q1 successor v2 transport stop."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument(
        "--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTerminalAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_successor_terminal_audit(stored):
                raise ValueError("Stored Q1 successor v2 terminal audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} "
                "requests=3 payload_bytes=16332030 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "requests=3 payload_bytes=16332030 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
