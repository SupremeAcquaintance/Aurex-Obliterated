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

DEFAULT_OUTPUT_DIRECTORY = Path(
    "data/evidence/q1_periodic_flow_successor_interruption_recoveries_v3"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile the next interrupted Q1 successor v3 request offline."
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
    parser.add_argument(
        "--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY
    )
    return parser.parse_args()


def _unmatched_request_paths(root: Path) -> tuple[Path, ...]:
    unmatched: list[Path] = []
    for request in sorted(root.rglob("*.request.json")):
        response = request.with_name(request.name.replace(".request.json", ".response.json"))
        if not response.exists():
            unmatched.append(request)
    return tuple(unmatched)


def main() -> int:
    args = parse_args()
    try:
        if args.result.exists():
            raise ValueError("Q1 successor v3 terminal result already exists")
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
        unmatched = _unmatched_request_paths(args.acquisition_root)
        if len(unmatched) != 1:
            raise ValueError(
                f"Expected one interrupted Q1 successor v3 request, found {len(unmatched)}"
            )
        request_path = unmatched[0]
        request = json.loads(request_path.read_text(encoding="utf-8"))
        target_key = request.get("target_key", "")
        try:
            month, product = target_key.split("|", 1)
        except ValueError as exc:
            raise ValueError("Interrupted Q1 successor v3 target key changed") from exc
        target = next(
            item
            for item in context.protocol.targets
            if item.month == month and item.product == product
        )
        attempt = request.get("attempt")
        if not isinstance(attempt, int) or attempt < 1:
            raise ValueError("Interrupted Q1 successor v3 attempt changed")
        response_path = request_path.with_name(
            request_path.name.replace(".request.json", ".response.json")
        )
        destination = target_archive_path(args.acquisition_root, target)
        partial = destination.with_name(f"{destination.name}.part")
        partial_bytes = partial.stat().st_size if partial.exists() else 0
        partial_sha256 = file_sha256(partial) if partial.exists() else None
        range_start = request.get("range_start")
        if not isinstance(range_start, int) or partial_bytes < range_start:
            raise ValueError("Interrupted Q1 successor v3 partial offset changed")
        before = marker_state_v3(args.acquisition_root)
        if (
            checkpoint.request_marker_count != before.request_count - 1
            or checkpoint.response_marker_count != before.response_count
            or before.request_count != before.response_count + 1
        ):
            raise ValueError("Q1 successor v3 checkpoint is not one request behind")
        attempts = reconcile_target_markers_v3(
            root=args.acquisition_root,
            target=target,
            context=context,
        )
        if attempts != attempt or not response_path.is_file():
            raise ValueError("Q1 successor v3 interruption did not reconcile")
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if (
            response.get("outcome")
            not in {"INTERRUPTED_RESUMABLE", "PASS"}
            or response.get("bytes_received") != partial_bytes - range_start
            or response.get("partial_bytes_after_attempt") != partial_bytes
        ):
            raise ValueError("Q1 successor v3 interruption accounting changed")
        refreshed = write_checkpoint_v3(
            args=args,
            context=context,
            archives=list(checkpoint.archive_evidence),
            pairs=list(checkpoint.paired_month_evidence),
            exclusions=list(checkpoint.excluded_month_evidence),
        )
        output = args.output_directory / (
            f"{month}-{product.lower()}-attempt-{attempt}.json"
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
            "target_key": target_key,
            "attempt": attempt,
            "request_marker_file_sha256": file_sha256(request_path),
            "response_marker_file_sha256": file_sha256(response_path),
            "range_start": range_start,
            "partial_file_sha256": partial_sha256,
            "partial_bytes": partial_bytes,
            "reconciled_payload_bytes": partial_bytes - range_start,
            "reconciled_outcome": response["outcome"],
            "checkpoint_file_sha256": file_sha256(args.checkpoint),
            "checkpoint_evidence_hash": refreshed.checkpoint_evidence_hash,
            "network_requests_made_by_recovery": 0,
            "outcomes_accessed": 0,
            "orders_submitted": 0,
            "next_action": "RESUME_Q1_SUCCESSOR_V3_ACQUISITION",
        }
        evidence["recovery_evidence_hash"] = universe_evidence_hash(evidence)
        _write_json_transactional(output, evidence, overwrite=False)
        print(
            f"RECONCILED {output} {evidence['recovery_evidence_hash']} "
            f"target={target_key} attempt={attempt} partial_bytes={partial_bytes} "
            f"payload_bytes={partial_bytes - range_start} "
            "network_requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, StopIteration, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
