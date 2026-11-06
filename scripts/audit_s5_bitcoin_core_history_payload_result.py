from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryPayloadResultAudit,
    audit_s5_history_protocol,
    audit_s5_history_result,
    audit_s5_history_result_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_history_payload import (  # noqa: E402
    MODULE_PATH,
    DatasetInspection,
    build_result,
    inspect_dataset,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
DEFAULT_RESULT = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_payload_result_audit_v1.json")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_history_payload_result.py")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def verify_transcript(result: S5BitcoinCoreHistoryPayloadResult) -> bool:
    attempt = result.attempt
    if not attempt.attempted:
        return attempt.transcript_path is None and attempt.transcript_file_sha256 is None
    if attempt.transcript_path is None or attempt.transcript_file_sha256 is None:
        raise ValueError("Attempted S5 history clone has no transcript")
    path = Path(attempt.transcript_path)
    if (
        file_sha256(path) != attempt.transcript_file_sha256
        or path.stat().st_size != attempt.transcript_byte_count
    ):
        raise ValueError("S5 history clone transcript changed")
    payload = json.loads(path.read_text(encoding="utf-8"))
    base64.b64decode(payload["stdout_base64"], validate=True)
    base64.b64decode(payload["stderr_base64"], validate=True)
    if (
        payload["attempt_id"] != attempt.attempt_id
        or payload["started_at"] != attempt.started_at.isoformat()
        or payload["completed_at"] != attempt.completed_at.isoformat()
        or payload["elapsed_seconds"] != attempt.elapsed_seconds
        or payload["exit_code"] != attempt.exit_code
        or payload["credential_helper_disabled"] is not True
        or payload["interactive_prompt_disabled"] is not True
    ):
        raise ValueError("S5 history transcript-to-attempt binding changed")
    return True


def reconstruct_result(
    *, protocol_path: Path, result_path: Path
) -> tuple[S5BitcoinCoreHistoryPayloadResult, bool, bool, bool]:
    protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = S5BitcoinCoreHistoryPayloadResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if not audit_s5_history_protocol(protocol) or not audit_s5_history_result(result):
        raise ValueError("S5 history protocol or result evidence hash failed")
    if result.protocol_evidence_hash != protocol.protocol_evidence_hash:
        raise ValueError("S5 history result protocol binding changed")
    if result.runner_contract_hash != runner_contract_hash():
        raise ValueError("S5 history result runner source changed")
    transcript_verified = verify_transcript(result)

    dataset_path: Path | None = None
    if result.dataset_path is not None:
        dataset_path = Path(result.dataset_path)
    elif result.partial_dataset_path is not None:
        dataset_path = Path(result.partial_dataset_path)
    inspection = DatasetInspection()
    recorded_inspection_failure_verified = False
    if dataset_path is not None:
        if not dataset_path.exists():
            raise ValueError("S5 history dataset path is missing")
        try:
            inspection = inspect_dataset(path=dataset_path, protocol=protocol)
        except ValueError as exc:
            recorded_inspection_failure_verified = (
                result.failed_gate_count > 0
                and result.attempt.error_type == type(exc).__name__
                and result.attempt.error_message == str(exc)[:2000]
                and result.dataset_file_count == 0
                and result.dataset_byte_count == 0
            )
            if not recorded_inspection_failure_verified:
                raise
    manifest_verified = (
        inspection.manifest == result.dataset_file_manifest
        and inspection.directory_sha256 == result.dataset_directory_sha256
        and inspection.byte_count == result.dataset_byte_count
    )
    if not manifest_verified:
        raise ValueError("S5 history dataset manifest changed")
    local_integrity_verified = recorded_inspection_failure_verified or (
        inspection.fetched_master_head == result.fetched_master_head
        and inspection.cutoff_commit_present == result.cutoff_commit_present
        and inspection.cutoff_is_ancestor == result.cutoff_is_ancestor_of_fetched_master
        and inspection.repository_is_bare == result.repository_is_bare
        and inspection.repository_is_shallow == result.repository_is_shallow
        and inspection.remote_origin_url == result.remote_origin_url
        and inspection.remote_promisor == result.remote_promisor
        and inspection.remote_partial_clone_filter == result.remote_partial_clone_filter
        and inspection.local_branch_refs == result.local_branch_refs
        and inspection.local_tag_ref_count == result.local_tag_ref_count
        and inspection.reachable_object_id_count == result.reachable_object_id_count
        and inspection.reachable_object_id_stream_sha256 == result.reachable_object_id_stream_sha256
        and inspection.cutoff_commit_count == result.cutoff_commit_count
    )
    if not local_integrity_verified:
        raise ValueError("S5 history local Git integrity observations changed")
    expected = build_result(
        protocol=protocol,
        attempt=result.attempt,
        inspection=inspection,
        dataset_path=dataset_path,
        free_disk_bytes_before=result.free_disk_bytes_before,
        network_process_count=result.network_process_count,
        executed_at=result.executed_at,
    )
    if result != expected:
        raise ValueError("S5 history result differs from independent reconstruction")
    return result, transcript_verified, manifest_verified, local_integrity_verified


def build_audit(
    *, protocol_path: Path, result_path: Path, audited_at: datetime
) -> S5BitcoinCoreHistoryPayloadResultAudit:
    result, transcript_verified, manifest_verified, local_integrity_verified = reconstruct_result(
        protocol_path=protocol_path, result_path=result_path
    )
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "transcript_reverified": transcript_verified,
        "dataset_manifest_reverified": manifest_verified,
        "local_git_integrity_reverified": local_integrity_verified,
        "passed_gate_count": result.passed_gate_count,
        "failed_gate_count": result.failed_gate_count,
        "dataset_file_count": result.dataset_file_count,
        "dataset_byte_count": result.dataset_byte_count,
        "cutoff_commit_count": result.cutoff_commit_count,
        "next_authorization": result.next_authorization,
    }
    provisional = S5BitcoinCoreHistoryPayloadResultAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5BitcoinCoreHistoryPayloadResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5BitcoinCoreHistoryPayloadResultAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 history result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 history result audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryPayloadResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 history result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the frozen S5 history payload result.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreHistoryPayloadResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                protocol_path=args.protocol,
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected or not audit_s5_history_result_audit(stored):
                raise ValueError("Stored S5 history result audit differs from reconstruction")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            protocol_path=args.protocol,
            result_path=args.result,
            audited_at=datetime.now(UTC),
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"files={audit.dataset_file_count} bytes={audit.dataset_byte_count} "
            f"commits={audit.cutoff_commit_count} gates={audit.passed_gate_count}/14 "
            "market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
