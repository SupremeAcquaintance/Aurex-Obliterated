from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_transport_v7 import (  # noqa: E402
    PeriodicFlowSuccessorCheckpointV7,
    audit_hash,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    _write_json_transactional,
    file_sha256,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    marker_state_v3,
)
from scripts.run_periodic_flow_successor_acquisition_v7 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_INHERITED_TRANSPORT_AMENDMENT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    DEFAULT_V6_CHECKPOINT,
    DEFAULT_V6_RESULT,
    DEFAULT_V6_TERMINAL_AUDIT,
    DEFAULT_VALIDATOR_AMENDMENT,
    load_context,
    write_checkpoint,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_access_interruption_recovery_v7.json"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Reconcile the sandbox-denied Q1 successor v7 attempt episode."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--validator-amendment", type=Path, default=DEFAULT_VALIDATOR_AMENDMENT
    )
    parser.add_argument(
        "--inherited-transport-amendment",
        type=Path,
        default=DEFAULT_INHERITED_TRANSPORT_AMENDMENT,
    )
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
    parser.add_argument("--v6-checkpoint", type=Path, default=DEFAULT_V6_CHECKPOINT)
    parser.add_argument("--v6-result", type=Path, default=DEFAULT_V6_RESULT)
    parser.add_argument(
        "--v6-terminal-audit", type=Path, default=DEFAULT_V6_TERMINAL_AUDIT
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.result.exists() or args.output.exists():
            raise ValueError("Q1 successor v7 recovery is not in a writable state")
        context = load_context(args)
        checkpoint = PeriodicFlowSuccessorCheckpointV7.model_validate_json(
            args.checkpoint.read_text(encoding="utf-8")
        )
        if (
            not audit_hash(checkpoint, "checkpoint_evidence_hash")
            or checkpoint.execution_contract_evidence_hash
            != context.contract.contract_evidence_hash
            or checkpoint.runner_source_hash != context.contract.runner_source_hash
            or checkpoint.request_marker_count != 0
            or checkpoint.response_marker_count != 0
        ):
            raise ValueError("Q1 successor v7 pre-interruption checkpoint changed")
        requests = sorted(args.acquisition_root.rglob("*.request.json"))
        responses = sorted(args.acquisition_root.rglob("*.response.json"))
        if len(requests) != 5 or len(responses) != 5:
            raise ValueError("Q1 successor v7 denied attempt count changed")
        response_hashes = []
        for request_path, response_path in zip(requests, responses, strict=True):
            if response_path != request_path.with_name(
                request_path.name.replace(".request.json", ".response.json")
            ):
                raise ValueError("Q1 successor v7 marker pairing changed")
            response = json.loads(response_path.read_text(encoding="utf-8"))
            if (
                response.get("target_key") != "2023-04|USD_M_PERPETUAL"
                or response.get("outcome") != "TRANSIENT"
                or response.get("failure_class") != "URL_ERROR"
                or response.get("bytes_received") != 0
                or response.get("partial_bytes_after_attempt") != 0
                or "WinError 10013" not in response.get("exception_message", "")
            ):
                raise ValueError("Q1 successor v7 denied response changed")
            response_hashes.append(file_sha256(response_path))
        if tuple(args.acquisition_root.rglob("*.part")):
            raise ValueError("Q1 successor v7 denied episode created a partial")
        state = marker_state_v3(args.acquisition_root)
        if (
            state.request_count != 5
            or state.response_count != 5
            or state.payload_bytes_received != 0
        ):
            raise ValueError("Q1 successor v7 denied marker accounting changed")
        refreshed = write_checkpoint(
            args,
            context,
            list(checkpoint.archive_evidence),
            list(checkpoint.paired_month_evidence),
            list(checkpoint.excluded_month_evidence),
        )
        evidence = {
            "schema_version": (
                "aurex-q1-periodic-flow-successor-access-interruption-recovery-v7"
            ),
            "recovered_at": datetime.now(UTC).isoformat(),
            "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
            "runner_source_hash": context.contract.runner_source_hash,
            "recovery_script_file_sha256": file_sha256(Path(__file__)),
            "target_key": "2023-04|USD_M_PERPETUAL",
            "failure_class": "WINDOWS_SOCKET_ACCESS_DENIED",
            "attempt_count": 5,
            "response_file_sha256s": response_hashes,
            "payload_bytes_received": 0,
            "partial_archive_created": False,
            "checkpoint_file_sha256": file_sha256(args.checkpoint),
            "checkpoint_evidence_hash": refreshed.checkpoint_evidence_hash,
            "network_requests_made_by_recovery": 0,
            "outcomes_accessed": 0,
            "orders_submitted": 0,
            "next_action": "RESUME_FROZEN_V7_WITH_NETWORK_PERMISSION",
        }
        evidence["recovery_evidence_hash"] = universe_evidence_hash(evidence)
        _write_json_transactional(args.output, evidence, overwrite=False)
        print(
            f"RECONCILED {args.output} {evidence['recovery_evidence_hash']} "
            "attempts=5 payload_bytes=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
