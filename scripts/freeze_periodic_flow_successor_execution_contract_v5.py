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
    audit_hash as audit_v4_hash,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorExecutionContractV5,
    PeriodicFlowSuccessorTransportAmendmentAuditV5,
    PeriodicFlowSuccessorTransportAmendmentV5,
    audit_hash,
    build_execution_contract_v5,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)
from scripts.run_periodic_flow_successor_acquisition_v5 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_CHECKPOINT,
    DEFAULT_RESULT,
    DEFAULT_V4_CHECKPOINT,
    DEFAULT_V4_RESULT,
    DEFAULT_V4_TERMINAL_AUDIT,
    current_runner_source_hash_v5,
)

DEFAULT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v5.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_audit_v5.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v5.json"
)


def authoritative_contract(args, frozen_at):
    amendment = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV5.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
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
        not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or not audit_v4_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_v4_hash(result, "result_evidence_hash")
        or not audit_successor_terminal_audit_v4(terminal_audit)
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or tuple(args.acquisition_root.rglob("*.request.json"))
        or tuple(args.acquisition_root.rglob("*.response.json"))
        or tuple(args.acquisition_root.rglob("*.part"))
        or args.checkpoint.exists()
        or args.result.exists()
    ):
        raise ValueError("Q1 successor v5 execution contract lineage changed")
    return build_execution_contract_v5(
        frozen_at=frozen_at,
        amendment_file_sha256=file_sha256(args.amendment),
        amendment_evidence_hash=amendment.amendment_evidence_hash,
        amendment_audit_file_sha256=file_sha256(args.amendment_audit),
        amendment_audit_evidence_hash=amendment_audit.audit_evidence_hash,
        runner_source_hash=current_runner_source_hash_v5(),
        seed_v4_checkpoint_file_sha256=file_sha256(args.v4_checkpoint),
        seed_v4_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        seed_v4_result_file_sha256=file_sha256(args.v4_result),
        seed_v4_result_evidence_hash=result.result_evidence_hash,
        seed_v4_terminal_audit_file_sha256=file_sha256(args.v4_terminal_audit),
        seed_v4_terminal_audit_evidence_hash=terminal_audit.audit_evidence_hash,
        limitations=(
            "This contract executes only the frozen v5 DNS-resilient continuation.",
            "The v4 checkpoint seeds 45 archives, 16 pairs, and six exclusions.",
            "Every seed archive is revalidated by exact size and SHA-256.",
            "DNS resolution is required before each network target.",
            "Range, size, checksum, ZIP, parser, or marker conflicts hard-stop.",
            "Transient requests remain finite and fully marker-accounted.",
            "Completed archives require published SHA-256 before atomic rename.",
            "All prior evidence generations remain immutable.",
            "No price, quantity, feature, parameter, return, or outcome may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet strategy order, production, or live "
            "authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path, model):
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v5 contract: {path}")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze Q1 successor v5 contract.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--v4-checkpoint", type=Path, default=DEFAULT_V4_CHECKPOINT)
    parser.add_argument("--v4-result", type=Path, default=DEFAULT_V4_RESULT)
    parser.add_argument("--v4-terminal-audit", type=Path, default=DEFAULT_V4_TERMINAL_AUDIT)
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorExecutionContractV5.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(args, stored.frozen_at)
            if stored != expected or not audit_hash(stored, "contract_evidence_hash"):
                raise ValueError("Stored Q1 successor v5 contract changed")
            print(f"PASS {args.output} {stored.contract_evidence_hash}")
            return 0
        model = authoritative_contract(args, datetime.now(UTC))
        _write(args.output, model)
        print(
            f"FROZEN {args.output} {model.contract_evidence_hash} "
            f"runner={model.runner_source_hash}"
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
