from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    PeriodicFlowExecutionContract as V1ExecutionContract,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    audit_execution_contract as audit_v1_execution_contract,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionProtocol,
    PeriodicFlowSuccessorAcquisitionProtocolAudit,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    audit_hash as audit_protocol_hash,
)
from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    PeriodicFlowSuccessorExecutionContract,
    audit_hash,
    build_execution_contract,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
)
from scripts.run_periodic_flow_successor_acquisition import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_V1_EXECUTION_CONTRACT,
    current_runner_source_hash,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v1.json"
)


def authoritative_contract(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorExecutionContract:
    protocol = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowSuccessorAcquisitionProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    v1_contract = V1ExecutionContract.model_validate_json(
        args.v1_execution_contract.read_text(encoding="utf-8")
    )
    if (
        protocol.next_authorization
        != "FREEZE_Q1_SUCCESSOR_ACQUISITION_EXECUTION_CONTRACT_ONLY"
        or not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not audit_v1_execution_contract(v1_contract)
    ):
        raise ValueError("Q1 successor execution-contract authority changed")
    return build_execution_contract(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(args.protocol),
        parent_protocol_evidence_hash=protocol.protocol_evidence_hash,
        parent_protocol_audit_file_sha256=file_sha256(args.protocol_audit),
        parent_protocol_audit_evidence_hash=protocol_audit.audit_evidence_hash,
        inherited_v1_execution_contract_evidence_hash=v1_contract.contract_evidence_hash,
        inherited_v1_runner_source_hash=v1_contract.runner_source_hash,
        runner_source_hash=current_runner_source_hash(),
        limitations=(
            "This contract implements structural acquisition only and cannot establish edge.",
            "The audited v1 full-GET, marker, retry, checksum, ZIP, and parser "
            "primitives are inherited.",
            "The v1 protocol, checkpoint, result, and terminal audit remain immutable.",
            "Structural source failures exclude one month and continue under a new checkpoint.",
            "Transport, checksum, ZIP, or checkpoint integrity failures hard-stop the successor.",
            "No partial download may be resumed or treated as complete.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet order, production, or live authority exists.",
            "A terminal result is immutable and cannot be resumed or overwritten.",
            "The 120 GB preflight floor preserves the 100 GB byte ceiling and 20 GB reserve.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def write_contract(path: Path, contract: PeriodicFlowSuccessorExecutionContract) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor execution contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor execution-contract transaction: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorExecutionContract.model_validate_json(serialized) != contract:
        raise ValueError("Q1 successor execution contract did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the source-bound Q1 successor execution contract."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--v1-execution-contract", type=Path, default=DEFAULT_V1_EXECUTION_CONTRACT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorExecutionContract.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "contract_evidence_hash"):
                raise ValueError("Stored Q1 successor execution contract changed")
            print(
                f"PASS {args.output} {stored.contract_evidence_hash} "
                "requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        contract = authoritative_contract(args=args, frozen_at=datetime.now(UTC))
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            f"runner={contract.runner_source_hash} requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
