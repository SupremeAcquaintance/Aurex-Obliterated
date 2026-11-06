from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorCheckpointV3,
    PeriodicFlowSuccessorExecutionContractAuditV3,
    PeriodicFlowSuccessorExecutionContractV3,
    PeriodicFlowSuccessorTransportAmendmentAuditV3,
    PeriodicFlowSuccessorTransportAmendmentV3,
    audit_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    current_runner_source_hash_v3,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify immutable Q1 successor v3 lineage after network evidence exists."
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
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        amendment = PeriodicFlowSuccessorTransportAmendmentV3.model_validate_json(
            args.amendment.read_text(encoding="utf-8")
        )
        amendment_audit = (
            PeriodicFlowSuccessorTransportAmendmentAuditV3.model_validate_json(
                args.amendment_audit.read_text(encoding="utf-8")
            )
        )
        contract = PeriodicFlowSuccessorExecutionContractV3.model_validate_json(
            args.execution_contract.read_text(encoding="utf-8")
        )
        contract_audit = (
            PeriodicFlowSuccessorExecutionContractAuditV3.model_validate_json(
                args.execution_contract_audit.read_text(encoding="utf-8")
            )
        )
        checkpoint = PeriodicFlowSuccessorCheckpointV3.model_validate_json(
            args.checkpoint.read_text(encoding="utf-8")
        )
        runner_hash = current_runner_source_hash_v3()
        if (
            not audit_hash(amendment, "amendment_evidence_hash")
            or not audit_hash(amendment_audit, "audit_evidence_hash")
            or not audit_hash(contract, "contract_evidence_hash")
            or not audit_hash(contract_audit, "audit_evidence_hash")
            or not audit_hash(checkpoint, "checkpoint_evidence_hash")
            or amendment_audit.amendment_file_sha256
            != file_sha256(args.amendment)
            or amendment_audit.amendment_evidence_hash
            != amendment.amendment_evidence_hash
            or contract.amendment_file_sha256 != file_sha256(args.amendment)
            or contract.amendment_evidence_hash != amendment.amendment_evidence_hash
            or contract.amendment_audit_file_sha256
            != file_sha256(args.amendment_audit)
            or contract.amendment_audit_evidence_hash
            != amendment_audit.audit_evidence_hash
            or contract_audit.contract_file_sha256
            != file_sha256(args.execution_contract)
            or contract_audit.contract_evidence_hash
            != contract.contract_evidence_hash
            or contract.runner_source_hash != runner_hash
            or contract_audit.runner_source_hash != runner_hash
            or checkpoint.execution_contract_evidence_hash
            != contract.contract_evidence_hash
            or checkpoint.runner_source_hash != runner_hash
        ):
            raise ValueError("Q1 successor v3 post-network lineage changed")
        print(
            f"PASS contract={contract.contract_evidence_hash} "
            f"audit={contract_audit.audit_evidence_hash} runner={runner_hash} "
            f"checkpoint={checkpoint.checkpoint_evidence_hash} "
            f"requests={checkpoint.request_marker_count} "
            f"payload_bytes={checkpoint.cumulative_payload_bytes_received} "
            "outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
