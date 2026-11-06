from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadResult,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
    S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    S5BitcoinCoreHistoryPayloadResultAuditV2,
    S5BitcoinCoreHistoryPayloadResultV2,
    S5BitcoinCoreHistoryVerifierFailureAudit,
    audit_s5_history_result_audit_v2,
    audit_s5_history_result_v2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_history_local_verifier_v2 import (  # noqa: E402
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_FAILURE_AUDIT,
    DEFAULT_PRIOR_RESULT,
    DEFAULT_PROTOCOL,
    MODULE_PATH,
    build_result_v2,
    inspect_dataset_v2,
    runner_contract_hash,
)

DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_history_payload_result_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_payload_result_audit_v2.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_history_payload_result_v2.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def reconstruct_result(result_path: Path) -> S5BitcoinCoreHistoryPayloadResultV2:
    protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
        DEFAULT_PROTOCOL.read_text(encoding="utf-8")
    )
    prior = S5BitcoinCoreHistoryPayloadResult.model_validate_json(
        DEFAULT_PRIOR_RESULT.read_text(encoding="utf-8")
    )
    failure = S5BitcoinCoreHistoryVerifierFailureAudit.model_validate_json(
        DEFAULT_FAILURE_AUDIT.read_text(encoding="utf-8")
    )
    amendment = S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate_json(
        DEFAULT_AMENDMENT.read_text(encoding="utf-8")
    )
    amendment_audit = S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2.model_validate_json(
        DEFAULT_AMENDMENT_AUDIT.read_text(encoding="utf-8")
    )
    result = S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if not audit_s5_history_result_v2(result):
        raise ValueError("S5 corrected history result hash failed")
    if result.runner_contract_hash != runner_contract_hash():
        raise ValueError("S5 corrected history runner source changed")
    dataset_path = Path(result.dataset_path or "")
    if not result.dataset_path or not dataset_path.exists():
        raise ValueError("S5 corrected history dataset is missing")
    inspection, missing_count = inspect_dataset_v2(
        path=dataset_path,
        protocol=protocol,
        amendment=amendment,
    )
    if (
        inspection.manifest != result.dataset_file_manifest
        or inspection.directory_sha256 != result.dataset_directory_sha256
        or inspection.byte_count != result.dataset_byte_count
        or missing_count != result.missing_promised_object_count
    ):
        raise ValueError("S5 corrected history dataset or object stream changed")
    expected = build_result_v2(
        protocol=protocol,
        prior=prior,
        failure=failure,
        amendment=amendment,
        amendment_audit=amendment_audit,
        inspection=inspection,
        missing_promised_object_count=missing_count,
        dataset_path=dataset_path,
        executed_at=result.executed_at,
    )
    if result != expected:
        raise ValueError("S5 corrected history result differs from reconstruction")
    return result


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5BitcoinCoreHistoryPayloadResultAuditV2:
    result = reconstruct_result(result_path)
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "transcript_reverified": True,
        "dataset_manifest_reverified": True,
        "local_git_integrity_reverified": True,
        "passed_gate_count": result.passed_gate_count,
        "failed_gate_count": result.failed_gate_count,
        "dataset_file_count": result.dataset_file_count,
        "dataset_byte_count": result.dataset_byte_count,
        "cutoff_commit_count": result.cutoff_commit_count,
        "next_authorization": result.next_authorization,
        "prior_result_evidence_hash": result.prior_result_evidence_hash,
        "failure_audit_evidence_hash": result.failure_audit_evidence_hash,
        "verifier_amendment_evidence_hash": result.verifier_amendment_evidence_hash,
        "verifier_amendment_audit_evidence_hash": (result.verifier_amendment_audit_evidence_hash),
        "missing_promised_object_count": result.missing_promised_object_count,
    }
    provisional = S5BitcoinCoreHistoryPayloadResultAuditV2.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate(complete)


def write_atomic(path: Path, audit: S5BitcoinCoreHistoryPayloadResultAuditV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 corrected result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 corrected result-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("S5 corrected history result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the corrected S5 history result v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
            if stored != expected or not audit_s5_history_result_audit_v2(stored):
                raise ValueError("Stored S5 corrected result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"files={audit.dataset_file_count} bytes={audit.dataset_byte_count} "
            f"commits={audit.cutoff_commit_count} "
            f"promised_missing={audit.missing_promised_object_count} "
            f"gates={audit.passed_gate_count}/14 additional_network=0 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
