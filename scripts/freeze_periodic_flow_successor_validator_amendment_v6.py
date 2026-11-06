# ruff: noqa: I001

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v5 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV5,
    audit_successor_terminal_audit_v5,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV5,
    PeriodicFlowSuccessorCheckpointV5,
    PeriodicFlowSuccessorExecutionContractAuditV5,
    PeriodicFlowSuccessorExecutionContractV5,
    PeriodicFlowSuccessorTransportAmendmentV5,
    audit_hash as audit_v5_hash,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    PeriodicFlowSuccessorValidatorAmendmentV6,
    audit_hash,
    build_validator_amendment_v6,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_V5_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v5.json"
)
DEFAULT_V5_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v5.json"
)
DEFAULT_V5_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v5.json"
)
DEFAULT_V5_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v5.json"
)
DEFAULT_V5_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v5.json"
)
DEFAULT_V5_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v5.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_validator_amendment_v6.json"
)


def authoritative_amendment(*, args, frozen_at):
    v5_amendment = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        args.v5_amendment.read_text(encoding="utf-8")
    )
    v5_contract = PeriodicFlowSuccessorExecutionContractV5.model_validate_json(
        args.v5_contract.read_text(encoding="utf-8")
    )
    v5_contract_audit = PeriodicFlowSuccessorExecutionContractAuditV5.model_validate_json(
        args.v5_contract_audit.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowSuccessorCheckpointV5.model_validate_json(
        args.v5_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV5.model_validate_json(
        args.v5_result.read_text(encoding="utf-8")
    )
    terminal_audit = PeriodicFlowSuccessorTerminalAuditV5.model_validate_json(
        args.v5_terminal_audit.read_text(encoding="utf-8")
    )
    if (
        not audit_v5_hash(v5_amendment, "amendment_evidence_hash")
        or not audit_v5_hash(v5_contract, "contract_evidence_hash")
        or not audit_v5_hash(v5_contract_audit, "audit_evidence_hash")
        or not audit_v5_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_v5_hash(result, "result_evidence_hash")
        or not audit_successor_terminal_audit_v5(terminal_audit)
        or terminal_audit.next_authorization
        != "FREEZE_Q1_SUCCESSOR_VALIDATOR_V6_CONTINUATION_ONLY"
        or result.decision != "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        or terminal_audit.validator_evidence_model_failure_observed is not True
    ):
        raise ValueError("Q1 successor v6 validator amendment lineage changed")
    return build_validator_amendment_v6(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(args.protocol),
        parent_protocol_evidence_hash=terminal_audit.protocol_evidence_hash,
        parent_v5_amendment_file_sha256=file_sha256(args.v5_amendment),
        parent_v5_amendment_evidence_hash=v5_amendment.amendment_evidence_hash,
        parent_v5_contract_file_sha256=file_sha256(args.v5_contract),
        parent_v5_contract_evidence_hash=v5_contract.contract_evidence_hash,
        parent_v5_contract_audit_file_sha256=file_sha256(args.v5_contract_audit),
        parent_v5_contract_audit_evidence_hash=v5_contract_audit.audit_evidence_hash,
        terminal_v5_result_file_sha256=file_sha256(args.v5_result),
        terminal_v5_result_evidence_hash=result.result_evidence_hash,
        terminal_v5_checkpoint_file_sha256=file_sha256(args.v5_checkpoint),
        terminal_v5_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        terminal_v5_audit_file_sha256=file_sha256(args.v5_terminal_audit),
        terminal_v5_audit_evidence_hash=terminal_audit.audit_evidence_hash,
        limitations=(
            "This amendment changes only the domain of ordered raw-ID gap metrics.",
            "A non-increasing raw-ID observation makes ordered gap metrics inapplicable.",
            "Inapplicable gap fields are encoded as zero and never interpreted as a pass.",
            "Every non-monotonic archive is excluded whole without row mutation.",
            "Source rows may not be sorted, reordered, dropped, deduplicated, or synthesized.",
            "Ordered raw-trade archives retain every inherited ID-gap threshold.",
            "Spot archive gates, paired-clock gates, and sufficiency gates are unchanged.",
            "The v5 checkpoint is the exact seed and all prior generations are immutable.",
            "The terminal January archive requires its exact published SHA-256 before reuse.",
            "Inherited DNS, Range, timeout, marker, checksum, and disk rules are unchanged.",
            "No price, quantity, feature, parameter, return, or outcome may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet strategy order, production, or live "
            "authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path, model):
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v6 amendment: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze Q1 successor v6 amendment.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--v5-amendment", type=Path, default=DEFAULT_V5_AMENDMENT)
    parser.add_argument("--v5-contract", type=Path, default=DEFAULT_V5_CONTRACT)
    parser.add_argument(
        "--v5-contract-audit", type=Path, default=DEFAULT_V5_CONTRACT_AUDIT
    )
    parser.add_argument("--v5-checkpoint", type=Path, default=DEFAULT_V5_CHECKPOINT)
    parser.add_argument("--v5-result", type=Path, default=DEFAULT_V5_RESULT)
    parser.add_argument(
        "--v5-terminal-audit", type=Path, default=DEFAULT_V5_TERMINAL_AUDIT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorValidatorAmendmentV6.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_amendment(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "amendment_evidence_hash"):
                raise ValueError("Stored Q1 successor v6 amendment changed")
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
