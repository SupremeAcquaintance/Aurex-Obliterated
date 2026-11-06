from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResult,
    PeriodicFlowSuccessorCheckpoint,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorExecutionContractV3,
    PeriodicFlowSuccessorTransportAmendmentAuditV3,
    PeriodicFlowSuccessorTransportAmendmentV3,
    audit_hash,
    build_execution_contract_v3,
)
from scripts.audit_periodic_flow_successor_transport_amendment_v3 import (  # noqa: E402
    DEFAULT_AUDIT_OUTPUT as DEFAULT_AMENDMENT_AUDIT,
)
from scripts.freeze_periodic_flow_successor_transport_amendment_v3 import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_AMENDMENT,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_CHECKPOINT,
    DEFAULT_RESULT,
    DEFAULT_V2_CHECKPOINT,
    DEFAULT_V2_RESULT,
    current_runner_source_hash_v3,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v3.json"
)


def authoritative_contract(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorExecutionContractV3:
    amendment = PeriodicFlowSuccessorTransportAmendmentV3.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV3.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
    )
    checkpoint = PeriodicFlowSuccessorCheckpoint.model_validate_json(
        args.v2_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResult.model_validate_json(
        args.v2_result.read_text(encoding="utf-8")
    )
    request_markers = tuple(args.acquisition_root.rglob("*.request.json"))
    response_markers = tuple(args.acquisition_root.rglob("*.response.json"))
    partials = tuple(args.acquisition_root.rglob("*.part"))
    if (
        not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or amendment_audit.amendment_evidence_hash
        != amendment.amendment_evidence_hash
        or file_sha256(args.v2_checkpoint)
        != amendment.terminal_v2_checkpoint_file_sha256
        or checkpoint.checkpoint_evidence_hash
        != amendment.terminal_v2_checkpoint_evidence_hash
        or file_sha256(args.v2_result) != amendment.terminal_v2_result_file_sha256
        or result.result_evidence_hash != amendment.terminal_v2_result_evidence_hash
        or len(checkpoint.archive_evidence) != 3
        or len(checkpoint.paired_month_evidence) != 1
        or checkpoint.excluded_month_evidence
        or request_markers
        or response_markers
        or partials
        or args.checkpoint.exists()
        or args.result.exists()
    ):
        raise ValueError("Q1 successor v3 execution-contract lineage changed")
    return build_execution_contract_v3(
        frozen_at=frozen_at,
        amendment_file_sha256=file_sha256(args.amendment),
        amendment_evidence_hash=amendment.amendment_evidence_hash,
        amendment_audit_file_sha256=file_sha256(args.amendment_audit),
        amendment_audit_evidence_hash=amendment_audit.audit_evidence_hash,
        runner_source_hash=current_runner_source_hash_v3(),
        seed_v2_checkpoint_file_sha256=file_sha256(args.v2_checkpoint),
        seed_v2_checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        seed_v2_result_file_sha256=file_sha256(args.v2_result),
        seed_v2_result_evidence_hash=result.result_evidence_hash,
        limitations=(
            "This contract executes only the frozen v3 transport amendment.",
            "The v2 checkpoint contributes three exact archive records and one paired month.",
            "Every seed archive is revalidated by file size and SHA-256 before use.",
            "The preserved bootstrap partial is copied atomically and remains source immutable.",
            "Positive offsets require exact HTTP 206 and Content-Range identity.",
            "Transient failures retain partial bytes and record their bounded exception detail.",
            "A completed archive requires the published SHA-256 before atomic rename.",
            "Marker, range, size, checksum, ZIP, parser, or checkpoint conflicts hard-stop.",
            "The v1 and v2 evidence generations remain immutable and non-resumable.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet strategy order, production, or live "
            "authority exists.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def write_contract(
    path: Path, contract: PeriodicFlowSuccessorExecutionContractV3
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v3 contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor v3 contract transaction: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorExecutionContractV3.model_validate_json(
        serialized
    ) != contract:
        raise ValueError("Q1 successor v3 contract did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the source-bound Q1 successor v3 execution contract."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT
    )
    parser.add_argument("--v2-checkpoint", type=Path, default=DEFAULT_V2_CHECKPOINT)
    parser.add_argument("--v2-result", type=Path, default=DEFAULT_V2_RESULT)
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
            stored = PeriodicFlowSuccessorExecutionContractV3.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "contract_evidence_hash"):
                raise ValueError("Stored Q1 successor v3 contract changed")
            print(
                f"PASS {args.output} {stored.contract_evidence_hash} "
                f"runner={stored.runner_source_hash} network_requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        contract = authoritative_contract(args=args, frozen_at=datetime.now(UTC))
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            f"runner={contract.runner_source_hash} network_requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
