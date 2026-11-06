from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    PeriodicFlowSuccessorExecutionContract,
    PeriodicFlowSuccessorExecutionContractAudit,
    PeriodicFlowSuccessorExecutionContractV2,
    audit_hash,
    build_execution_contract_v2,
)
from scripts.freeze_periodic_flow_successor_execution_contract import file_sha256  # noqa: E402
from scripts.run_periodic_flow_successor_acquisition import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_V1_EXECUTION_CONTRACT,
    current_runner_source_hash,
)

DEFAULT_PARENT_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v1.json"
)
DEFAULT_PARENT_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v1.json"
)
DEFAULT_STALLED_REQUEST_MARKER = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v1/BTCUSDT/2020-05/"
    "trades/BTCUSDT-trades-2020-05.zip.get.1.request.json"
)
DEFAULT_STALLED_RESPONSE_MARKER = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v1/BTCUSDT/2020-05/"
    "trades/BTCUSDT-trades-2020-05.zip.get.1.response.json"
)
DEFAULT_STALLED_PARTIAL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v1/BTCUSDT/2020-05/"
    "trades/BTCUSDT-trades-2020-05.zip.part"
)
DEFAULT_STALLED_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v2.json"
)


def authoritative_contract(
    *, args: argparse.Namespace, frozen_at: datetime
) -> PeriodicFlowSuccessorExecutionContractV2:
    parent = PeriodicFlowSuccessorExecutionContract.model_validate_json(
        args.parent_contract.read_text(encoding="utf-8")
    )
    parent_audit = PeriodicFlowSuccessorExecutionContractAudit.model_validate_json(
        args.parent_contract_audit.read_text(encoding="utf-8")
    )
    marker = json.loads(args.stalled_request_marker.read_text(encoding="utf-8"))
    if (
        not audit_hash(parent, "contract_evidence_hash")
        or not audit_hash(parent_audit, "audit_evidence_hash")
        or parent_audit.contract_file_sha256 != file_sha256(args.parent_contract)
        or parent_audit.contract_evidence_hash != parent.contract_evidence_hash
        or marker.get("target_key") != "2020-05|USD_M_PERPETUAL"
        or marker.get("attempt") != 1
        or marker.get("protocol_evidence_hash") != parent.parent_protocol_evidence_hash
        or marker.get("execution_contract_evidence_hash")
        != parent.contract_evidence_hash
        or args.stalled_response_marker.exists()
        or not args.stalled_partial.is_file()
        or args.stalled_partial.stat().st_size <= 0
        or args.stalled_result.exists()
    ):
        raise ValueError("Q1 successor zero-byte stall evidence changed")
    return build_execution_contract_v2(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=parent.parent_protocol_file_sha256,
        parent_protocol_evidence_hash=parent.parent_protocol_evidence_hash,
        parent_protocol_audit_file_sha256=parent.parent_protocol_audit_file_sha256,
        parent_protocol_audit_evidence_hash=parent.parent_protocol_audit_evidence_hash,
        inherited_v1_execution_contract_evidence_hash=(
            parent.inherited_v1_execution_contract_evidence_hash
        ),
        inherited_v1_runner_source_hash=parent.inherited_v1_runner_source_hash,
        runner_source_hash=current_runner_source_hash(),
        parent_v1_contract_file_sha256=file_sha256(args.parent_contract),
        parent_v1_contract_evidence_hash=parent.contract_evidence_hash,
        parent_v1_contract_audit_file_sha256=file_sha256(args.parent_contract_audit),
        parent_v1_contract_audit_evidence_hash=parent_audit.audit_evidence_hash,
        stalled_request_marker_path=(
            args.stalled_request_marker.resolve()
            .relative_to(PROJECT_ROOT.resolve())
            .as_posix()
        ),
        stalled_request_marker_file_sha256=file_sha256(args.stalled_request_marker),
        stalled_partial_bytes=args.stalled_partial.stat().st_size,
        stalled_partial_file_sha256=file_sha256(args.stalled_partial),
        limitations=(
            "This v2 contract corrects an interrupted buffered-read stall; it does not "
            "inspect market outcomes.",
            "The v1 successor contract, checkpoint, request marker, and empty "
            "partial remain preserved.",
            "The retry uses a fresh root so v1 and v2 request-marker lineage cannot mix.",
            "HTTP read1 uses 64 KB chunks, a 60-second idle bound, and a one-hour total deadline.",
            "The audited v1 checksum, ZIP, parser, checkpoint, and authority "
            "boundaries remain inherited.",
            "Structural source failures exclude one month and continue under a new checkpoint.",
            "Transport, checksum, ZIP, or checkpoint integrity failures hard-stop the successor.",
            "No partial download may be resumed or treated as complete.",
            "No price, quantity, quote quantity, feature, parameter, or return may be parsed.",
            "Validation and holdout outcomes remain sealed.",
            "No candidate, Pine, paper, Testnet order, production, or live authority exists.",
            "A terminal result is immutable and cannot be resumed or overwritten.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def write_contract(path: Path, contract: PeriodicFlowSuccessorExecutionContractV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v2 contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 successor v2 contract transaction: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if PeriodicFlowSuccessorExecutionContractV2.model_validate_json(serialized) != contract:
        raise ValueError("Q1 successor v2 contract did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the wall-clock-bounded Q1 successor v2 execution contract."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--v1-execution-contract", type=Path, default=DEFAULT_V1_EXECUTION_CONTRACT
    )
    parser.add_argument("--parent-contract", type=Path, default=DEFAULT_PARENT_CONTRACT)
    parser.add_argument(
        "--parent-contract-audit", type=Path, default=DEFAULT_PARENT_CONTRACT_AUDIT
    )
    parser.add_argument(
        "--stalled-request-marker", type=Path, default=DEFAULT_STALLED_REQUEST_MARKER
    )
    parser.add_argument(
        "--stalled-response-marker", type=Path, default=DEFAULT_STALLED_RESPONSE_MARKER
    )
    parser.add_argument("--stalled-partial", type=Path, default=DEFAULT_STALLED_PARTIAL)
    parser.add_argument("--stalled-result", type=Path, default=DEFAULT_STALLED_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorExecutionContractV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(args=args, frozen_at=stored.frozen_at)
            if stored != expected or not audit_hash(stored, "contract_evidence_hash"):
                raise ValueError("Stored Q1 successor v2 contract changed")
            print(
                f"PASS {args.output} {stored.contract_evidence_hash} "
                f"stalled_bytes={stored.stalled_partial_bytes} "
                "requests_v2=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        contract = authoritative_contract(args=args, frozen_at=datetime.now(UTC))
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            f"runner={contract.runner_source_hash} "
            f"stalled_bytes={contract.stalled_partial_bytes} "
            "requests_v2=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
