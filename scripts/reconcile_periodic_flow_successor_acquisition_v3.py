from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorCheckpointV3,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    _write_json_transactional,
    file_sha256,
    target_archive_path,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    DEFAULT_V2_CHECKPOINT,
    DEFAULT_V2_RESULT,
    DEFAULT_V2_TERMINAL_AUDIT,
    load_context,
    marker_state_v3,
    reconcile_target_markers_v3,
    verify_checkpoint_archives_v3,
    write_checkpoint_v3,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_interruption_recovery_v3.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile an interrupted Q1 successor v3 request without network access."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
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
    parser.add_argument("--v2-checkpoint", type=Path, default=DEFAULT_V2_CHECKPOINT)
    parser.add_argument("--v2-result", type=Path, default=DEFAULT_V2_RESULT)
    parser.add_argument(
        "--v2-terminal-audit", type=Path, default=DEFAULT_V2_TERMINAL_AUDIT
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
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
        if args.result.exists():
            raise ValueError("Q1 successor v3 terminal result already exists")
        if args.output.exists():
            raise ValueError("Q1 successor v3 interruption recovery is already frozen")
        context = load_context(args)
        checkpoint = PeriodicFlowSuccessorCheckpointV3.model_validate_json(
            args.checkpoint.read_text(encoding="utf-8")
        )
        if (
            checkpoint.protocol_evidence_hash
            != context.protocol.protocol_evidence_hash
            or checkpoint.execution_contract_evidence_hash
            != context.contract.contract_evidence_hash
            or checkpoint.runner_source_hash != context.contract.runner_source_hash
        ):
            raise ValueError("Q1 successor v3 interrupted checkpoint lineage changed")
        verify_checkpoint_archives_v3(
            checkpoint=checkpoint, evidence_root=args.evidence_root
        )
        target = next(
            item
            for item in context.protocol.targets
            if f"{item.month}|{item.product}"
            == context.protocol.bootstrap_target_key
        )
        destination = target_archive_path(args.acquisition_root, target)
        partial = destination.with_name(f"{destination.name}.part")
        request = destination.with_name(f"{destination.name}.get.1.request.json")
        response = destination.with_name(f"{destination.name}.get.1.response.json")
        before = marker_state_v3(args.acquisition_root)
        if (
            before.request_count != 1
            or before.response_count != 0
            or not request.is_file()
            or response.exists()
            or not partial.is_file()
            or partial.stat().st_size <= context.protocol.bootstrap_partial_bytes
        ):
            raise ValueError("Q1 successor v3 interruption state changed")
        partial_bytes = partial.stat().st_size
        partial_sha256 = file_sha256(partial)
        attempts = reconcile_target_markers_v3(
            root=args.acquisition_root,
            target=target,
            context=context,
        )
        if attempts != 1 or not response.is_file():
            raise ValueError("Q1 successor v3 interruption did not reconcile")
        response_payload = json.loads(response.read_text(encoding="utf-8"))
        expected_delta = partial_bytes - context.protocol.bootstrap_partial_bytes
        if (
            response_payload.get("outcome") != "INTERRUPTED_RESUMABLE"
            or response_payload.get("failure_class") != "PROCESS_INTERRUPTED"
            or response_payload.get("bytes_received") != expected_delta
            or response_payload.get("partial_bytes_after_attempt") != partial_bytes
        ):
            raise ValueError("Q1 successor v3 recovery byte accounting changed")
        refreshed = write_checkpoint_v3(
            args=args,
            context=context,
            archives=list(checkpoint.archive_evidence),
            pairs=list(checkpoint.paired_month_evidence),
            exclusions=list(checkpoint.excluded_month_evidence),
        )
        evidence = {
            "schema_version": "aurex-q1-periodic-flow-successor-interruption-recovery-v3",
            "recovered_at": datetime.now(UTC).isoformat(),
            "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
            "transport_amendment_evidence_hash": (
                context.protocol.amendment_evidence_hash
            ),
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "runner_source_hash": context.contract.runner_source_hash,
            "recovery_script_file_sha256": file_sha256(Path(__file__)),
            "target_key": context.protocol.bootstrap_target_key,
            "request_marker_file_sha256": file_sha256(request),
            "response_marker_file_sha256": file_sha256(response),
            "partial_file_sha256": partial_sha256,
            "partial_bytes": partial_bytes,
            "bootstrap_bytes": context.protocol.bootstrap_partial_bytes,
            "reconciled_payload_bytes": expected_delta,
            "checkpoint_file_sha256": file_sha256(args.checkpoint),
            "checkpoint_evidence_hash": refreshed.checkpoint_evidence_hash,
            "network_requests_made_by_recovery": 0,
            "outcomes_accessed": 0,
            "orders_submitted": 0,
            "next_action": "RESUME_Q1_SUCCESSOR_V3_ACQUISITION",
        }
        evidence["recovery_evidence_hash"] = universe_evidence_hash(evidence)
        _write_json_transactional(args.output, evidence, overwrite=False)
        print(
            f"RECONCILED {args.output} {evidence['recovery_evidence_hash']} "
            f"partial_bytes={partial_bytes} payload_bytes={expected_delta} "
            "network_requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
