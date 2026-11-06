from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v3 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV3,
    audit_successor_terminal_audit_v3,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV3,
    PeriodicFlowSuccessorCheckpointV3,
    PeriodicFlowSuccessorExecutionContractAuditV3,
    PeriodicFlowSuccessorExecutionContractV3,
    PeriodicFlowSuccessorTransportAmendmentV3,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    audit_hash as audit_v3_hash,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v4 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentV4,
    audit_hash,
    build_transport_amendment_v4,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_V3_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v3.json"
)
DEFAULT_V3_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v3.json"
)
DEFAULT_V3_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v3.json"
)
DEFAULT_V3_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v3.json"
)
DEFAULT_V3_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v3.json"
)
DEFAULT_V3_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v3.json"
)
DEFAULT_BOOTSTRAP_PARTIAL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v3/BTCUSDT/2020-08/"
    "trades/BTCUSDT-trades-2020-08.zip.part"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v4.json"
)


def authoritative_amendment(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorTransportAmendmentV4:
    amendment = PeriodicFlowSuccessorTransportAmendmentV3.model_validate_json(
        args.v3_amendment.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV3.model_validate_json(
        args.v3_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV3.model_validate_json(
        args.v3_contract_audit.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowSuccessorCheckpointV3.model_validate_json(
        args.v3_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV3.model_validate_json(
        args.v3_result.read_text(encoding="utf-8")
    )
    terminal_audit = PeriodicFlowSuccessorTerminalAuditV3.model_validate_json(
        args.v3_terminal_audit.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_hash(amendment, "amendment_evidence_hash")
        or not audit_v3_hash(contract, "contract_evidence_hash")
        or not audit_v3_hash(contract_audit, "audit_evidence_hash")
        or not audit_v3_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_v3_hash(result, "result_evidence_hash")
        or not audit_successor_terminal_audit_v3(terminal_audit)
        or contract.amendment_file_sha256 != file_sha256(args.v3_amendment)
        or contract_audit.contract_file_sha256 != file_sha256(args.v3_contract)
        or result.checkpoint_file_sha256 != file_sha256(args.v3_checkpoint)
        or terminal_audit.result_file_sha256 != file_sha256(args.v3_result)
        or terminal_audit.checkpoint_file_sha256 != file_sha256(args.v3_checkpoint)
        or terminal_audit.next_authorization
        != "FREEZE_Q1_SUCCESSOR_TRANSPORT_V4_CONTINUATION_ONLY"
        or not args.bootstrap_partial.is_file()
        or args.bootstrap_partial.stat().st_size != 86_150_831
        or file_sha256(args.bootstrap_partial)
        != terminal_audit.partial_archive_file_sha256
    ):
        raise ValueError("Q1 successor v4 transport amendment lineage changed")
    return build_transport_amendment_v4(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(args.protocol),
        parent_protocol_evidence_hash=terminal_audit.protocol_evidence_hash,
        parent_v3_amendment_file_sha256=file_sha256(args.v3_amendment),
        parent_v3_amendment_evidence_hash=amendment.amendment_evidence_hash,
        parent_v3_contract_file_sha256=file_sha256(args.v3_contract),
        parent_v3_contract_evidence_hash=contract.contract_evidence_hash,
        parent_v3_contract_audit_file_sha256=file_sha256(args.v3_contract_audit),
        parent_v3_contract_audit_evidence_hash=contract_audit.audit_evidence_hash,
        terminal_v3_result_file_sha256=file_sha256(args.v3_result),
        terminal_v3_result_evidence_hash=result.result_evidence_hash,
        terminal_v3_checkpoint_file_sha256=file_sha256(args.v3_checkpoint),
        terminal_v3_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        terminal_v3_audit_file_sha256=file_sha256(args.v3_terminal_audit),
        terminal_v3_audit_evidence_hash=terminal_audit.audit_evidence_hash,
        bootstrap_partial_path=(
            args.bootstrap_partial.resolve()
            .relative_to(PROJECT_ROOT.resolve())
            .as_posix()
        ),
        bootstrap_partial_file_sha256=file_sha256(args.bootstrap_partial),
        limitations=(
            "This amendment changes transport continuation only; the source manifest is unchanged.",
            "The exact preserved v3 partial may be copied, never moved or overwritten.",
            "Every resumed response must prove its exact byte offset and total length.",
            "A completed archive must match the published SHA-256 before atomic rename.",
            "Transient failures preserve partial bytes and bounded exception detail.",
            "Non-transient HTTP, range, size, checksum, or marker conflicts hard-stop.",
            "The v1, v2, and v3 evidence generations remain immutable.",
            "No HEAD request or redirect is permitted by the acquisition runner.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet strategy order, production, or live "
            "authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path: Path, amendment: PeriodicFlowSuccessorTransportAmendmentV4) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v4 amendment: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor v4 amendment transaction: {temporary}")
    serialized = amendment.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorTransportAmendmentV4.model_validate_json(
        serialized
    ) != amendment:
        raise ValueError("Q1 successor v4 amendment did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze Q1 successor v4 continuation.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--v3-amendment", type=Path, default=DEFAULT_V3_AMENDMENT)
    parser.add_argument("--v3-contract", type=Path, default=DEFAULT_V3_CONTRACT)
    parser.add_argument(
        "--v3-contract-audit", type=Path, default=DEFAULT_V3_CONTRACT_AUDIT
    )
    parser.add_argument("--v3-checkpoint", type=Path, default=DEFAULT_V3_CHECKPOINT)
    parser.add_argument("--v3-result", type=Path, default=DEFAULT_V3_RESULT)
    parser.add_argument(
        "--v3-terminal-audit", type=Path, default=DEFAULT_V3_TERMINAL_AUDIT
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
            stored = PeriodicFlowSuccessorTransportAmendmentV4.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_amendment(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "amendment_evidence_hash"):
                raise ValueError("Stored Q1 successor v4 amendment changed")
            print(
                f"PASS {args.output} {stored.amendment_evidence_hash} "
                "network_requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        amendment = authoritative_amendment(args=args, frozen_at=datetime.now(UTC))
        _write(args.output, amendment)
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
