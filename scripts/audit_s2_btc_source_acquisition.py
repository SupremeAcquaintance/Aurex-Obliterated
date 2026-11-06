from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_btc_source_execution import (  # noqa: E402
    S2_BTC_ACQUISITION_PASS,
    S2BtcAcquisitionCheckpoint,
    S2BtcSourceAcquisitionAudit,
    S2BtcSourceAcquisitionResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s2_btc_source_acquisition import (  # noqa: E402
    DEFAULT_CHECKPOINT,
    DEFAULT_CONTRACT,
    DEFAULT_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    build_hashed,
    build_result,
    dataset_bytes,
    file_sha256,
    load_authority,
    project_path,
    runner_contract_hash,
    verify_checkpoint_sources,
)

DEFAULT_OUTPUT = Path("data/evidence/s2_btc_source_acquisition_audit_v1.json")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "auditor_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "auditor_sha256": file_sha256(Path(__file__)),
        }
    )


def build_audit(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
    checkpoint_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S2BtcSourceAcquisitionAudit:
    protocol, contract = load_authority(
        protocol_path, protocol_audit_path, contract_path, contract_audit_path
    )
    checkpoint = S2BtcAcquisitionCheckpoint.model_validate_json(
        checkpoint_path.read_text(encoding="utf-8")
    )
    result = S2BtcSourceAcquisitionResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        result.decision != S2_BTC_ACQUISITION_PASS
        or result.classified_target_count != 273
        or result.complete_target_count != 273
        or result.failed_target_count != 0
        or result.network_request_count != 546
        or len(result.price_rows) != 273
        or result.dataset_path != protocol.output_path
        or result.dataset_file_sha256 is None
        or result.checkpoint_file_sha256 != file_sha256(checkpoint_path)
        or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        or checkpoint.protocol_evidence_hash != protocol.protocol_evidence_hash
        or checkpoint.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.return_metrics_calculated
        or result.orders_submitted != 0
    ):
        raise ValueError("S2 BTC source result lineage or terminal counts changed")
    verify_checkpoint_sources(checkpoint, protocol=protocol, contract=contract)
    reconstructed = build_result(
        checkpoint_path=checkpoint_path,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=result.completed_at,
    )
    if reconstructed != result:
        raise ValueError("S2 BTC source result did not reconstruct exactly")
    dataset_path = project_path(result.dataset_path)
    reconstructed_dataset = dataset_bytes(reconstructed.price_rows)
    if (
        dataset_path.read_bytes() != reconstructed_dataset
        or file_sha256(dataset_path) != result.dataset_file_sha256
        or dataset_path.stat().st_size != result.dataset_bytes
    ):
        raise ValueError("S2 BTC price dataset did not reconstruct byte-for-byte")
    price_manifest = universe_evidence_hash(
        {
            "dataset_file_sha256": result.dataset_file_sha256,
            "price_row_evidence_hashes": tuple(
                row.price_evidence_hash for row in reconstructed.price_rows
            ),
        }
    )
    return build_hashed(
        S2BtcSourceAcquisitionAudit,
        "audit_evidence_hash",
        audited_at=audited_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(contract_path),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        checkpoint_file_sha256=file_sha256(checkpoint_path),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        dataset_file_sha256=result.dataset_file_sha256,
        price_row_manifest_evidence_hash=price_manifest,
        runner_contract_hash=result.runner_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
        classified_target_count=result.classified_target_count,
        complete_target_count=result.complete_target_count,
        failed_target_count=result.failed_target_count,
        price_rows_reconstructed=len(reconstructed.price_rows),
        btc_price_values_read_during_audit=len(reconstructed.price_rows),
        decision="PASS_S2_BTC_SOURCE_ACQUISITION_AUDIT",
        lineage_next_authorization=result.next_authorization,
    )


def write_audit(path: Path, audit: S2BtcSourceAcquisitionAudit) -> None:
    if path.exists():
        raise ValueError(f"S2 BTC source acquisition audit exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S2BtcSourceAcquisitionAudit.model_validate_json(serialized) != audit:
        raise ValueError("S2 BTC source acquisition audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 BTC result audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently reconstruct the complete S2 BTC source result."
    )
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        audit = build_audit(
            protocol_path=project_path(args.protocol),
            protocol_audit_path=project_path(args.protocol_audit),
            contract_path=project_path(args.contract),
            contract_audit_path=project_path(args.contract_audit),
            checkpoint_path=project_path(args.checkpoint),
            result_path=project_path(args.result),
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"result={audit.result_evidence_hash} prices={audit.price_rows_reconstructed} "
            "returns=0 outcomes=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
