# ruff: noqa: I001

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v4 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV4,
    audit_successor_terminal_audit_v4,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v4 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV4,
    PeriodicFlowSuccessorCheckpointV4,
    PeriodicFlowSuccessorExecutionContractAuditV4,
    PeriodicFlowSuccessorExecutionContractV4,
    PeriodicFlowSuccessorTransportAmendmentV4,
    audit_hash as audit_v4_hash,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentV5,
    audit_hash,
    build_transport_amendment_v5,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_V4_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v4.json"
)
DEFAULT_V4_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v4.json"
)
DEFAULT_V4_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v4.json"
)
DEFAULT_V4_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v4.json"
)
DEFAULT_V4_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v4.json"
)
DEFAULT_V4_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v4.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v5.json"
)


def authoritative_amendment(*, args, frozen_at):
    amendment = PeriodicFlowSuccessorTransportAmendmentV4.model_validate_json(
        args.v4_amendment.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV4.model_validate_json(
        args.v4_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV4.model_validate_json(
        args.v4_contract_audit.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowSuccessorCheckpointV4.model_validate_json(
        args.v4_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV4.model_validate_json(
        args.v4_result.read_text(encoding="utf-8")
    )
    terminal_audit = PeriodicFlowSuccessorTerminalAuditV4.model_validate_json(
        args.v4_terminal_audit.read_text(encoding="utf-8")
    )
    if (
        not audit_v4_hash(amendment, "amendment_evidence_hash")
        or not audit_v4_hash(contract, "contract_evidence_hash")
        or not audit_v4_hash(contract_audit, "audit_evidence_hash")
        or not audit_v4_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_v4_hash(result, "result_evidence_hash")
        or not audit_successor_terminal_audit_v4(terminal_audit)
        or terminal_audit.next_authorization
        != "FREEZE_Q1_SUCCESSOR_TRANSPORT_V5_CONTINUATION_ONLY"
        or result.decision != "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
    ):
        raise ValueError("Q1 successor v5 amendment lineage changed")
    return build_transport_amendment_v5(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(args.protocol),
        parent_protocol_evidence_hash=terminal_audit.protocol_evidence_hash,
        parent_v4_amendment_file_sha256=file_sha256(args.v4_amendment),
        parent_v4_amendment_evidence_hash=amendment.amendment_evidence_hash,
        parent_v4_contract_file_sha256=file_sha256(args.v4_contract),
        parent_v4_contract_evidence_hash=contract.contract_evidence_hash,
        parent_v4_contract_audit_file_sha256=file_sha256(args.v4_contract_audit),
        parent_v4_contract_audit_evidence_hash=contract_audit.audit_evidence_hash,
        terminal_v4_result_file_sha256=file_sha256(args.v4_result),
        terminal_v4_result_evidence_hash=result.result_evidence_hash,
        terminal_v4_checkpoint_file_sha256=file_sha256(args.v4_checkpoint),
        terminal_v4_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        terminal_v4_audit_file_sha256=file_sha256(args.v4_terminal_audit),
        terminal_v4_audit_evidence_hash=terminal_audit.audit_evidence_hash,
        limitations=(
            "This amendment changes DNS and transient transport resilience only.",
            "The complete v4 checkpoint is the exact seed; no partial is copied.",
            "Source manifest, archive checksums, and structural gates are unchanged.",
            "Every network target requires a successful DNS check before its first GET.",
            "GET attempts remain finite and every attempt retains immutable markers.",
            "Completed archives require the published SHA-256 before atomic rename.",
            "All prior evidence generations remain immutable.",
            "No HEAD request or redirect is permitted.",
            "No price, quantity, feature, parameter, return, or outcome may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet strategy order, production, or live "
            "authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path, model):
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v5 amendment: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze Q1 successor v5 amendment.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--v4-amendment", type=Path, default=DEFAULT_V4_AMENDMENT)
    parser.add_argument("--v4-contract", type=Path, default=DEFAULT_V4_CONTRACT)
    parser.add_argument("--v4-contract-audit", type=Path, default=DEFAULT_V4_CONTRACT_AUDIT)
    parser.add_argument("--v4-checkpoint", type=Path, default=DEFAULT_V4_CHECKPOINT)
    parser.add_argument("--v4-result", type=Path, default=DEFAULT_V4_RESULT)
    parser.add_argument("--v4-terminal-audit", type=Path, default=DEFAULT_V4_TERMINAL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_amendment(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "amendment_evidence_hash"):
                raise ValueError("Stored Q1 successor v5 amendment changed")
            print(f"PASS {args.output} {stored.amendment_evidence_hash}")
            return 0
        model = authoritative_amendment(args=args, frozen_at=datetime.now(UTC))
        _write(args.output, model)
        print(f"FROZEN {args.output} {model.amendment_evidence_hash}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
