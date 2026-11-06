from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s3_cftc_source_feasibility import build_hashed  # noqa: E402
from aurex.backtest_engine.s3_cftc_source_transport_outcome import (  # noqa: E402
    S3CftcMetadataTransportExecutionReceiptAuditV2,
    S3CftcMetadataTransportExecutionReceiptV2,
    audit_transport_execution_receipt,
    audit_transport_execution_receipt_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.record_s3_cftc_metadata_transport_outcome_v2 import (  # noqa: E402
    MODULE_PATH,
    build_receipt,
    recorder_contract_hash,
)
from scripts.run_s3_cftc_source_feasibility import file_sha256  # noqa: E402

DEFAULT_RECEIPT = Path(
    "data/evidence/s3_cftc_metadata_transport_execution_receipt_v2.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s3_cftc_metadata_transport_execution_receipt_audit_v2.json"
)
SCRIPT_PATH = Path("scripts/audit_s3_cftc_metadata_transport_outcome_v2.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_audit(
    *, receipt_path: Path, audited_at: datetime
) -> S3CftcMetadataTransportExecutionReceiptAuditV2:
    receipt = S3CftcMetadataTransportExecutionReceiptV2.model_validate_json(
        receipt_path.read_text(encoding="utf-8")
    )
    if (
        not audit_transport_execution_receipt(receipt)
        or receipt.recorder_contract_hash != recorder_contract_hash()
        or receipt != build_receipt(recorded_at=receipt.recorded_at)
        or receipt.result_artifact_created is not False
        or receipt.persisted_response_artifact_count != 0
        or receipt.rerun_authority_exhausted is not True
    ):
        raise ValueError("S3 transport execution receipt differs from reconstruction")
    return build_hashed(
        S3CftcMetadataTransportExecutionReceiptAuditV2,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "receipt_file_sha256": file_sha256(receipt_path),
            "receipt_evidence_hash": receipt.receipt_evidence_hash,
            "protocol_evidence_hash": receipt.protocol_evidence_hash,
            "prior_result_evidence_hash": receipt.prior_result_evidence_hash,
            "failure_audit_evidence_hash": receipt.failure_audit_evidence_hash,
            "transport_amendment_evidence_hash": (
                receipt.transport_amendment_evidence_hash
            ),
            "transport_amendment_audit_evidence_hash": (
                receipt.transport_amendment_audit_evidence_hash
            ),
            "runner_contract_hash": receipt.runner_contract_hash,
            "recorder_contract_hash": receipt.recorder_contract_hash,
            "auditor_contract_hash": auditor_contract_hash(),
        },
    )


def write_atomic(
    path: Path, audit: S3CftcMetadataTransportExecutionReceiptAuditV2
) -> None:
    if path.exists():
        raise ValueError(f"S3 transport execution receipt audit exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S3 transport receipt-audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S3CftcMetadataTransportExecutionReceiptAuditV2.model_validate_json(
        serialized
    ) != audit:
        raise ValueError("S3 transport execution receipt audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S3 transport v2 outcome.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = (
                S3CftcMetadataTransportExecutionReceiptAuditV2.model_validate_json(
                    args.output.read_text(encoding="utf-8")
                )
            )
            expected = build_audit(
                receipt_path=args.receipt, audited_at=stored.audited_at
            )
            if stored != expected or not audit_transport_execution_receipt_audit(
                stored
            ):
                raise ValueError("Stored S3 transport execution receipt audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            receipt_path=args.receipt, audited_at=datetime.now(UTC)
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "result_absent=true rerun_exhausted=true values=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
