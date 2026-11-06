from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
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
)
from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    audit_hash as audit_v2_hash,
)
from aurex.backtest_engine.periodic_flow_successor_terminal_audit import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAudit,
    audit_successor_terminal_audit,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentV3,
    audit_hash,
    build_transport_amendment_v3,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_V2_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v2.json"
)
DEFAULT_V2_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v2.json"
)
DEFAULT_V2_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v2.json"
)
DEFAULT_V2_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v2.json"
)
DEFAULT_V2_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v2.json"
)
DEFAULT_BOOTSTRAP_PARTIAL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v1/BTCUSDT/2020-05/"
    "trades/BTCUSDT-trades-2020-05.zip.part"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v3.json"
)


def authoritative_amendment(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorTransportAmendmentV3:
    protocol = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowSuccessorAcquisitionProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV2.model_validate_json(
        args.v2_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV2.model_validate_json(
        args.v2_contract_audit.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResult.model_validate_json(
        args.v2_result.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowSuccessorCheckpoint.model_validate_json(
        args.v2_checkpoint.read_text(encoding="utf-8")
    )
    terminal_audit = PeriodicFlowSuccessorTerminalAudit.model_validate_json(
        args.v2_terminal_audit.read_text(encoding="utf-8")
    )
    if (
        not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or not audit_v2_hash(contract, "contract_evidence_hash")
        or not audit_v2_hash(contract_audit, "audit_evidence_hash")
        or not audit_v2_hash(result, "result_evidence_hash")
        or not audit_v2_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_successor_terminal_audit(terminal_audit)
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or contract.parent_protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract_audit.contract_file_sha256 != file_sha256(args.v2_contract)
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.checkpoint_file_sha256 != file_sha256(args.v2_checkpoint)
        or terminal_audit.result_file_sha256 != file_sha256(args.v2_result)
        or terminal_audit.checkpoint_file_sha256 != file_sha256(args.v2_checkpoint)
        or terminal_audit.execution_contract_file_sha256
        != file_sha256(args.v2_contract)
        or terminal_audit.next_authorization
        != "FREEZE_Q1_SUCCESSOR_TRANSPORT_V3_CORRECTION_ONLY"
        or not args.bootstrap_partial.is_file()
        or args.bootstrap_partial.stat().st_size != contract.stalled_partial_bytes
        or file_sha256(args.bootstrap_partial) != contract.stalled_partial_file_sha256
    ):
        raise ValueError("Q1 successor v3 transport-amendment lineage changed")
    return build_transport_amendment_v3(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(args.protocol),
        parent_protocol_evidence_hash=protocol.protocol_evidence_hash,
        parent_protocol_audit_file_sha256=file_sha256(args.protocol_audit),
        parent_protocol_audit_evidence_hash=protocol_audit.audit_evidence_hash,
        parent_v2_contract_file_sha256=file_sha256(args.v2_contract),
        parent_v2_contract_evidence_hash=contract.contract_evidence_hash,
        parent_v2_contract_audit_file_sha256=file_sha256(args.v2_contract_audit),
        parent_v2_contract_audit_evidence_hash=contract_audit.audit_evidence_hash,
        terminal_v2_result_file_sha256=file_sha256(args.v2_result),
        terminal_v2_result_evidence_hash=result.result_evidence_hash,
        terminal_v2_checkpoint_file_sha256=file_sha256(args.v2_checkpoint),
        terminal_v2_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        terminal_v2_audit_file_sha256=file_sha256(args.v2_terminal_audit),
        terminal_v2_audit_evidence_hash=terminal_audit.audit_evidence_hash,
        bootstrap_partial_path=(
            args.bootstrap_partial.resolve()
            .relative_to(PROJECT_ROOT.resolve())
            .as_posix()
        ),
        bootstrap_partial_file_sha256=file_sha256(args.bootstrap_partial),
        limitations=(
            "This amendment changes transport recovery only; the source manifest is unchanged.",
            "The exact preserved v1 partial may be copied, never moved or overwritten.",
            "Every resumed response must prove its exact byte offset and total length.",
            "A completed archive must match the published SHA-256 before atomic rename.",
            "Transient failures preserve partial bytes and record bounded exception detail.",
            "Non-transient HTTP, range, size, checksum, or marker conflicts hard-stop.",
            "The v1 and v2 roots, markers, checkpoints, results, and audits remain immutable.",
            "No HEAD request or redirect is permitted.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet strategy order, production, or live "
            "authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def write_amendment(
    path: Path, amendment: PeriodicFlowSuccessorTransportAmendmentV3
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v3 amendment: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor v3 amendment transaction: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorTransportAmendmentV3.model_validate_json(
        serialized
    ) != amendment:
        raise ValueError("Q1 successor v3 amendment did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the Q1 successor v3 resumable-transport amendment."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--v2-contract", type=Path, default=DEFAULT_V2_CONTRACT)
    parser.add_argument(
        "--v2-contract-audit", type=Path, default=DEFAULT_V2_CONTRACT_AUDIT
    )
    parser.add_argument("--v2-result", type=Path, default=DEFAULT_V2_RESULT)
    parser.add_argument("--v2-checkpoint", type=Path, default=DEFAULT_V2_CHECKPOINT)
    parser.add_argument(
        "--v2-terminal-audit", type=Path, default=DEFAULT_V2_TERMINAL_AUDIT
    )
    parser.add_argument(
        "--bootstrap-partial", type=Path, default=DEFAULT_BOOTSTRAP_PARTIAL
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTransportAmendmentV3.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_amendment(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "amendment_evidence_hash"):
                raise ValueError("Stored Q1 successor v3 amendment changed")
            print(
                f"PASS {args.output} {stored.amendment_evidence_hash} "
                "network_requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        amendment = authoritative_amendment(args=args, frozen_at=datetime.now(UTC))
        write_amendment(args.output, amendment)
        print(
            f"FROZEN {args.output} {amendment.amendment_evidence_hash} "
            "network_requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
