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
from aurex.backtest_engine.periodic_flow_successor_transport_v7 import (  # noqa: E402
    PeriodicFlowSuccessorExecutionContractV7,
    PeriodicFlowSuccessorTransportAmendmentAuditV7,
    PeriodicFlowSuccessorTransportAmendmentV7,
    audit_hash,
    build_execution_contract_v7,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV6,
    PeriodicFlowSuccessorCheckpointV6,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    audit_hash as audit_v6_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    verify_checkpoint_archives_v3,
)
from scripts.run_periodic_flow_successor_acquisition_v7 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_RESULT,
    DEFAULT_V6_CHECKPOINT,
    DEFAULT_V6_RESULT,
    DEFAULT_V6_TERMINAL_AUDIT,
    current_runner_source_hash_v7,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v7.json"
)


def authoritative_contract(args, frozen_at):
    amendment = PeriodicFlowSuccessorTransportAmendmentV7.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV7.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
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
    verify_checkpoint_archives_v3(
        checkpoint=checkpoint, evidence_root=args.evidence_root
    )
    if (
        not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or not audit_v6_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_v6_hash(result, "result_evidence_hash")
        or not audit_successor_terminal_audit_v6(terminal)
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or checkpoint.total_new_archive_bytes
        != amendment.seed_total_new_archive_bytes
        or amendment.maximum_remaining_payload_bytes
        + checkpoint.total_new_archive_bytes
        != amendment.inherited_maximum_new_archive_bytes_total
        or tuple(args.acquisition_root.rglob("*.request.json"))
        or tuple(args.acquisition_root.rglob("*.response.json"))
        or tuple(args.acquisition_root.rglob("*.part"))
        or args.checkpoint.exists()
        or args.result.exists()
    ):
        raise ValueError("Q1 successor v7 execution contract lineage changed")
    return build_execution_contract_v7(
        frozen_at=frozen_at,
        amendment_file_sha256=file_sha256(args.amendment),
        amendment_evidence_hash=amendment.amendment_evidence_hash,
        amendment_audit_file_sha256=file_sha256(args.amendment_audit),
        amendment_audit_evidence_hash=amendment_audit.audit_evidence_hash,
        runner_source_hash=current_runner_source_hash_v7(),
        seed_v6_checkpoint_file_sha256=file_sha256(args.v6_checkpoint),
        seed_v6_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        seed_v6_result_file_sha256=file_sha256(args.v6_result),
        seed_v6_result_evidence_hash=result.result_evidence_hash,
        seed_v6_terminal_audit_file_sha256=file_sha256(args.v6_terminal_audit),
        seed_v6_terminal_audit_evidence_hash=terminal.audit_evidence_hash,
        limitations=(
            "This contract executes only the frozen v7 transport continuation.",
            "The v6 checkpoint seeds 56 archives, 17 pairs, and 11 exclusions.",
            "Every seed archive is revalidated by exact size and SHA-256.",
            "The failed v6 partial is not copied into the v7 evidence root.",
            "April USD-M restarts from byte zero under fresh v7 markers.",
            "The remaining payload cap plus seed bytes equals 100000000000 bytes.",
            "Preflight free disk covers the full remaining cap plus 20000000000 bytes.",
            "The v6 validator and all source-quality gates are unchanged.",
            "Non-monotonic source rows remain excluded whole without mutation.",
            "GET and DNS attempts remain finite and marker-bound.",
            "All prior evidence generations remain immutable.",
            "No price, quantity, feature, parameter, return, or outcome may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet order, production, or live authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path, model):
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v7 contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze Q1 successor v7 contract.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
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


def main():
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorExecutionContractV7.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(args, stored.frozen_at)
            if stored != expected or not audit_hash(stored, "contract_evidence_hash"):
                raise ValueError("Stored Q1 successor v7 contract changed")
            print(
                f"PASS {args.output} {stored.contract_evidence_hash} "
                f"runner={stored.runner_source_hash}"
            )
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
