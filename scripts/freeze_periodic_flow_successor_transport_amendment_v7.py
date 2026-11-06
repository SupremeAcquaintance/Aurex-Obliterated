# ruff: noqa: I001

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v6 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV6,
    audit_successor_terminal_audit_v6,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentV5,
    audit_hash as audit_v5_hash,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v7 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentV7,
    audit_hash,
    build_transport_amendment_v7,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV6,
    PeriodicFlowSuccessorCheckpointV6,
    PeriodicFlowSuccessorExecutionContractAuditV6,
    PeriodicFlowSuccessorExecutionContractV6,
    PeriodicFlowSuccessorValidatorAmendmentV6,
    audit_hash as audit_v6_hash,
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
DEFAULT_V6_VALIDATOR_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_validator_amendment_v6.json"
)
DEFAULT_V6_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v6.json"
)
DEFAULT_V6_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v6.json"
)
DEFAULT_V6_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v6.json"
)
DEFAULT_V6_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v6.json"
)
DEFAULT_V6_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v6.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v7.json"
)


def authoritative_amendment(*, args, frozen_at):
    v5 = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        args.v5_amendment.read_text(encoding="utf-8")
    )
    validator = PeriodicFlowSuccessorValidatorAmendmentV6.model_validate_json(
        args.v6_validator_amendment.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV6.model_validate_json(
        args.v6_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV6.model_validate_json(
        args.v6_contract_audit.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowSuccessorCheckpointV6.model_validate_json(
        args.v6_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV6.model_validate_json(
        args.v6_result.read_text(encoding="utf-8")
    )
    terminal = PeriodicFlowSuccessorTerminalAuditV6.model_validate_json(
        args.v6_terminal_audit.read_text(encoding="utf-8")
    )
    if (
        not audit_v5_hash(v5, "amendment_evidence_hash")
        or not audit_v6_hash(validator, "amendment_evidence_hash")
        or not audit_v6_hash(contract, "contract_evidence_hash")
        or not audit_v6_hash(contract_audit, "audit_evidence_hash")
        or not audit_v6_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_v6_hash(result, "result_evidence_hash")
        or not audit_successor_terminal_audit_v6(terminal)
        or terminal.next_authorization
        != "FREEZE_Q1_SUCCESSOR_TRANSPORT_V7_CONTINUATION_ONLY"
        or result.decision != "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        or checkpoint.total_new_archive_bytes != 30_282_986_798
    ):
        raise ValueError("Q1 successor v7 amendment lineage changed")
    inherited = v5.model_dump(
        exclude={
            "schema_version",
            "amendment_id",
            "frozen_at",
            "status",
            "request_marker_schema",
            "response_marker_schema",
            "next_authorization",
            "limitations",
            "amendment_evidence_hash",
        }
    )
    return build_transport_amendment_v7(
        **inherited,
        frozen_at=frozen_at,
        parent_v6_validator_amendment_file_sha256=file_sha256(
            args.v6_validator_amendment
        ),
        parent_v6_validator_amendment_evidence_hash=validator.amendment_evidence_hash,
        parent_v6_contract_file_sha256=file_sha256(args.v6_contract),
        parent_v6_contract_evidence_hash=contract.contract_evidence_hash,
        parent_v6_contract_audit_file_sha256=file_sha256(args.v6_contract_audit),
        parent_v6_contract_audit_evidence_hash=contract_audit.audit_evidence_hash,
        terminal_v6_result_file_sha256=file_sha256(args.v6_result),
        terminal_v6_result_evidence_hash=result.result_evidence_hash,
        terminal_v6_checkpoint_file_sha256=file_sha256(args.v6_checkpoint),
        terminal_v6_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        terminal_v6_audit_file_sha256=file_sha256(args.v6_terminal_audit),
        terminal_v6_audit_evidence_hash=terminal.audit_evidence_hash,
        limitations=(
            "This amendment authorizes only a fresh bounded transport continuation.",
            "The complete v6 checkpoint is the exact seed.",
            "The failed v6 partial remains immutable evidence and is not copied.",
            "The April USD-M target starts from byte zero in the v7 evidence root.",
            "The v6 validator and every structural and sufficiency gate are unchanged.",
            "The original 100000000000-byte corpus cap is reduced by seed bytes.",
            "The remaining v7 payload cap is exactly 69717013202 bytes.",
            "The 20000000000-byte post-acquisition disk reserve is unchanged.",
            "GET and DNS attempts remain finite and every attempt is immutable.",
            "Completed archives require the published SHA-256 before atomic rename.",
            "All prior evidence generations remain immutable.",
            "No HEAD request or redirect is permitted.",
            "No price, quantity, feature, parameter, return, or outcome may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet order, production, or live authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path, model):
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v7 amendment: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze Q1 successor v7 amendment.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--v5-amendment", type=Path, default=DEFAULT_V5_AMENDMENT)
    parser.add_argument(
        "--v6-validator-amendment",
        type=Path,
        default=DEFAULT_V6_VALIDATOR_AMENDMENT,
    )
    parser.add_argument("--v6-contract", type=Path, default=DEFAULT_V6_CONTRACT)
    parser.add_argument(
        "--v6-contract-audit", type=Path, default=DEFAULT_V6_CONTRACT_AUDIT
    )
    parser.add_argument("--v6-checkpoint", type=Path, default=DEFAULT_V6_CHECKPOINT)
    parser.add_argument("--v6-result", type=Path, default=DEFAULT_V6_RESULT)
    parser.add_argument(
        "--v6-terminal-audit", type=Path, default=DEFAULT_V6_TERMINAL_AUDIT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTransportAmendmentV7.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_amendment(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "amendment_evidence_hash"):
                raise ValueError("Stored Q1 successor v7 amendment changed")
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
