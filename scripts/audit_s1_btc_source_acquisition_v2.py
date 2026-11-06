from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_execution_v2 import (  # noqa: E402
    S1BtcAcquisitionCheckpointV2,
    S1BtcSourceAcquisitionResultV2,
    S1BtcSourceExecutionContractV2,
)
from aurex.backtest_engine.s1_btc_source_result_audit_v2 import (  # noqa: E402
    S1BtcSourceAcquisitionAuditV2,
)
from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1BtcSourceAcquisitionProtocolV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256, project_path  # noqa: E402
from scripts.run_s1_btc_source_acquisition_v2 import (  # noqa: E402
    build_result,
    dataset_bytes,
    verify_partial_checkpoint,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v2.json")
DEFAULT_CONTRACT = Path("data/evidence/s1_btc_source_execution_contract_v2.json")
DEFAULT_CHECKPOINT = Path("data/evidence/s1_btc_source_acquisition_checkpoint_v2.json")
DEFAULT_RESULT = Path("data/evidence/s1_btc_source_acquisition_result_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_acquisition_audit_v2.json")
AUDITOR_PATH = Path("scripts/audit_s1_btc_source_acquisition_v2.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the complete S1.1 BTC source result.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol = S1BtcSourceAcquisitionProtocolV2.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    contract = S1BtcSourceExecutionContractV2.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    checkpoint = S1BtcAcquisitionCheckpointV2.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    result = S1BtcSourceAcquisitionResultV2.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    verify_partial_checkpoint(
        checkpoint,
        protocol=protocol,
        contract=contract,
    )
    reconstructed = build_result(
        checkpoint_path=args.checkpoint,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=result.completed_at,
    )
    if reconstructed != result:
        raise SystemExit("S1.1 source result did not reconstruct exactly")
    dataset_path = project_path(protocol.output_path)
    if (
        dataset_path.read_bytes() != dataset_bytes(result.price_rows)
        or file_sha256(dataset_path) != result.dataset_file_sha256
    ):
        raise SystemExit("S1.1 source dataset did not reconstruct exactly")
    delayed = [row for row in result.price_rows if row.activation_delay_minutes > 0]
    if len(delayed) != 1:
        raise SystemExit("S1.1 delayed activation evidence changed")
    payload = {
        "audited_at": datetime.now(UTC),
        "protocol_file_sha256": file_sha256(args.protocol),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "execution_contract_file_sha256": file_sha256(args.contract),
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "checkpoint_file_sha256": file_sha256(args.checkpoint),
        "checkpoint_evidence_hash": checkpoint.checkpoint_evidence_hash,
        "result_file_sha256": file_sha256(args.result),
        "result_evidence_hash": result.result_evidence_hash,
        "dataset_file_sha256": result.dataset_file_sha256,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "delayed_target_id": delayed[0].source_target_id,
        "delayed_target_selected_open_time_ms": delayed[0].selected_open_time_ms,
    }
    provisional = S1BtcSourceAcquisitionAuditV2.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S1BtcSourceAcquisitionAuditV2.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1.1 source audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} rows={audit.price_rows_reconstructed} "
        f"delayed={audit.delayed_activation_target_count} returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
