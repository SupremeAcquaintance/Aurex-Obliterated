from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_full_acquisition import (  # noqa: E402
    S1NfciFullAcquisitionProtocol,
)
from aurex.backtest_engine.s1_nfci_full_execution import (  # noqa: E402
    S1_NFCI_ACQUISITION_PASS,
    S1NfciAcquisitionCheckpoint,
    S1NfciFullAcquisitionAudit,
    S1NfciFullAcquisitionResult,
)
from aurex.backtest_engine.s1_nfci_full_execution_v2 import (  # noqa: E402
    S1NfciAcquisitionExecutionAmendmentV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_full_acquisition import (  # noqa: E402
    RUNNER_PATH,
    build_checkpoint,
    build_result,
    runner_contract_hash,
    verify_checkpoint_raw,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_nfci_full_acquisition_protocol_v1.json")
DEFAULT_ADDENDUM = Path("data/evidence/s1_nfci_acquisition_execution_amendment_v2.json")
DEFAULT_CHECKPOINT = Path("data/evidence/s1_nfci_full_acquisition_checkpoint_v1.json")
DEFAULT_RESULT = Path("data/evidence/s1_nfci_full_acquisition_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_full_acquisition_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_nfci_full_acquisition.py")


def build_audit(
    *,
    protocol_path: Path,
    addendum_path: Path,
    checkpoint_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S1NfciFullAcquisitionAudit:
    protocol = S1NfciFullAcquisitionProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    addendum = S1NfciAcquisitionExecutionAmendmentV2.model_validate_json(
        addendum_path.read_text(encoding="utf-8")
    )
    checkpoint = S1NfciAcquisitionCheckpoint.model_validate_json(
        checkpoint_path.read_text(encoding="utf-8")
    )
    result = S1NfciFullAcquisitionResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        result.decision != S1_NFCI_ACQUISITION_PASS
        or checkpoint.classified_target_count != protocol.target_count
        or checkpoint.complete_target_count != protocol.target_count
        or checkpoint.failed_target_count != 0
        or runner_contract_hash() != checkpoint.runner_contract_hash
        or file_sha256(PROJECT_ROOT / RUNNER_PATH) == "0" * 64
    ):
        raise ValueError("S1 NFCI acquisition did not reach the pass boundary")
    verify_checkpoint_raw(checkpoint, protocol)
    expected_checkpoint = build_checkpoint(
        started_at=checkpoint.started_at,
        updated_at=checkpoint.updated_at,
        protocol_path=protocol_path,
        protocol=protocol,
        addendum_path=addendum_path,
        addendum=addendum,
        target_evidence=checkpoint.target_evidence,
    )
    if checkpoint != expected_checkpoint:
        raise ValueError("S1 NFCI checkpoint differs from reconstruction")
    expected_result = build_result(
        checkpoint_path=checkpoint_path,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=result.completed_at,
    )
    if result != expected_result:
        raise ValueError("S1 NFCI result differs from reconstruction")
    raw_hashes = {
        item.target_id: item.raw_file_sha256
        for item in checkpoint.target_evidence
        if item.raw_file_sha256 is not None
    }
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "checkpoint_file_sha256": file_sha256(checkpoint_path),
        "checkpoint_evidence_hash": checkpoint.checkpoint_evidence_hash,
        "runner_contract_hash": checkpoint.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "raw_file_sha256": raw_hashes,
        "aggregate_raw_bytes": checkpoint.persisted_raw_bytes,
    }
    provisional = S1NfciFullAcquisitionAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S1NfciFullAcquisitionAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1NfciFullAcquisitionAudit) -> None:
    if path.exists():
        raise ValueError(f"S1 full-acquisition audit exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 full-acquisition audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1NfciFullAcquisitionAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 full-acquisition audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S1 NFCI full acquisition.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--addendum", type=Path, default=DEFAULT_ADDENDUM)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciFullAcquisitionAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(
            protocol_path=args.protocol,
            addendum_path=args.addendum,
            checkpoint_path=args.checkpoint,
            result_path=args.result,
            audited_at=stored.audited_at,
        )
        if stored != expected:
            raise SystemExit("Stored S1 full-acquisition audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(
        protocol_path=args.protocol,
        addendum_path=args.addendum,
        checkpoint_path=args.checkpoint,
        result_path=args.result,
        audited_at=datetime.now(UTC),
    )
    write_atomic(args.output, audit)
    print(
        f"AUDITED {args.output} {audit.audit_evidence_hash} "
        f"raw_files={audit.raw_file_count} bytes={audit.aggregate_raw_bytes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
