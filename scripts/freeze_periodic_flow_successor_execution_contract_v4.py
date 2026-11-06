# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v3 import (
    PeriodicFlowSuccessorTerminalAuditV3,
    audit_successor_terminal_audit_v3,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (
    PeriodicFlowSuccessorAcquisitionResultV3,
    PeriodicFlowSuccessorCheckpointV3,
    audit_hash as audit_v3_hash,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v4 import (
    PeriodicFlowSuccessorExecutionContractV4,
    PeriodicFlowSuccessorTransportAmendmentAuditV4,
    PeriodicFlowSuccessorTransportAmendmentV4,
    audit_hash,
    build_execution_contract_v4,
)
from scripts.audit_periodic_flow_successor_transport_amendment_v4 import (
    DEFAULT_AUDIT_OUTPUT as DEFAULT_AMENDMENT_AUDIT,
)
from scripts.freeze_periodic_flow_successor_transport_amendment_v4 import (
    DEFAULT_OUTPUT as DEFAULT_AMENDMENT,
)
from scripts.run_periodic_flow_full_development_acquisition import (
    file_sha256,
)
from scripts.run_periodic_flow_successor_acquisition_v4 import (
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_CHECKPOINT,
    DEFAULT_RESULT,
    DEFAULT_V3_CHECKPOINT,
    DEFAULT_V3_RESULT,
    DEFAULT_V3_TERMINAL_AUDIT,
    current_runner_source_hash_v4,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v4.json"
)


def authoritative_contract(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorExecutionContractV4:
    amendment = PeriodicFlowSuccessorTransportAmendmentV4.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV4.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
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
        not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or not audit_v3_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_v3_hash(result, "result_evidence_hash")
        or not audit_successor_terminal_audit_v3(terminal_audit)
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or amendment_audit.amendment_evidence_hash
        != amendment.amendment_evidence_hash
        or file_sha256(args.v3_checkpoint)
        != amendment.terminal_v3_checkpoint_file_sha256
        or file_sha256(args.v3_result) != amendment.terminal_v3_result_file_sha256
        or file_sha256(args.v3_terminal_audit)
        != amendment.terminal_v3_audit_file_sha256
        or tuple(args.acquisition_root.rglob("*.request.json"))
        or tuple(args.acquisition_root.rglob("*.response.json"))
        or tuple(args.acquisition_root.rglob("*.part"))
        or args.checkpoint.exists()
        or args.result.exists()
    ):
        raise ValueError("Q1 successor v4 execution contract lineage changed")
    return build_execution_contract_v4(
        frozen_at=frozen_at,
        amendment_file_sha256=file_sha256(args.amendment),
        amendment_evidence_hash=amendment.amendment_evidence_hash,
        amendment_audit_file_sha256=file_sha256(args.amendment_audit),
        amendment_audit_evidence_hash=amendment_audit.audit_evidence_hash,
        runner_source_hash=current_runner_source_hash_v4(),
        seed_v3_checkpoint_file_sha256=file_sha256(args.v3_checkpoint),
        seed_v3_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        seed_v3_result_file_sha256=file_sha256(args.v3_result),
        seed_v3_result_evidence_hash=result.result_evidence_hash,
        seed_v3_terminal_audit_file_sha256=file_sha256(args.v3_terminal_audit),
        seed_v3_terminal_audit_evidence_hash=terminal_audit.audit_evidence_hash,
        limitations=(
            "This contract executes only the frozen v4 transport continuation.",
            "The v3 checkpoint contributes seven archives, two paired months, and one exclusion.",
            "Every seed archive is revalidated by file size and SHA-256 before use.",
            "The exact v3 partial is copied atomically and remains source immutable.",
            "Positive offsets require exact HTTP 206 and Content-Range identity.",
            "Transient failures retain partial bytes and bounded exception detail.",
            "Completed archives require the published SHA-256 before atomic rename.",
            "Marker, range, size, checksum, ZIP, parser, or checkpoint conflicts hard-stop.",
            "The v1, v2, and v3 evidence generations remain immutable.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet strategy order, production, or live "
            "authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path: Path, contract: PeriodicFlowSuccessorExecutionContractV4) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v4 contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorExecutionContractV4.model_validate_json(
        serialized
    ) != contract:
        raise ValueError("Q1 successor v4 contract did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze Q1 successor v4 contract.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT
    )
    parser.add_argument("--v3-checkpoint", type=Path, default=DEFAULT_V3_CHECKPOINT)
    parser.add_argument("--v3-result", type=Path, default=DEFAULT_V3_RESULT)
    parser.add_argument(
        "--v3-terminal-audit", type=Path, default=DEFAULT_V3_TERMINAL_AUDIT
    )
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
        if args.check:
            stored = PeriodicFlowSuccessorExecutionContractV4.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "contract_evidence_hash"):
                raise ValueError("Stored Q1 successor v4 contract changed")
            print(
                f"PASS {args.output} {stored.contract_evidence_hash} "
                f"runner={stored.runner_source_hash}",
                flush=True,
            )
            return 0
        contract = authoritative_contract(args=args, frozen_at=datetime.now(UTC))
        _write(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            f"runner={contract.runner_source_hash}",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
