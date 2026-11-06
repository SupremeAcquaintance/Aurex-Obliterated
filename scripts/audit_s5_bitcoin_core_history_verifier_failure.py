from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5_HISTORY_STOP,
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadProtocolAudit,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryPayloadResultAudit,
    S5HistoryBinding,
    audit_s5_history_protocol,
    audit_s5_history_protocol_audit,
    audit_s5_history_result,
    audit_s5_history_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryVerifierFailureAudit,
    audit_verifier_failure,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_history_payload import (  # noqa: E402
    local_git,
    manifest_for_directory,
    manifest_hash,
)

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_verifier_failure_audit_v1.json")
PROTOCOL_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_audit_v1.json")
RESULT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
RESULT_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_audit_v1.json")
TRANSCRIPT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_responses_v1/01_git_clone.json"
)
PARTIAL_DATASET_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_v1.git.partial")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_history_payload_transport.py")
SCRIPT_PATH = Path("scripts/audit_s5_bitcoin_core_history_verifier_failure.py")
MISSING_BLOB_ERROR = re.compile(
    r"^Local Git integrity command failed: fatal: missing blob object '[0-9a-f]{40}'$"
)


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                PROTOCOL_PATH,
                PROTOCOL_AUDIT_PATH,
                RESULT_PATH,
                RESULT_AUDIT_PATH,
                TRANSCRIPT_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def one_line(repo: Path, *arguments: str) -> str:
    completed = local_git(repo, *arguments)
    lines = completed.stdout.decode("utf-8").splitlines()
    if len(lines) != 1:
        raise ValueError(f"Expected one local Git line for {arguments}")
    return lines[0].strip()


def build_audit(*, audited_at: datetime) -> S5BitcoinCoreHistoryVerifierFailureAudit:
    protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5BitcoinCoreHistoryPayloadProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5BitcoinCoreHistoryPayloadResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5BitcoinCoreHistoryPayloadResultAudit.model_validate_json(
        RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    lineage_changed = (
        not audit_s5_history_protocol(protocol)
        or not audit_s5_history_protocol_audit(protocol_audit)
        or not audit_s5_history_result(result)
        or not audit_s5_history_result_audit(result_audit)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result_audit.result_evidence_hash != result.result_evidence_hash
        or result.decision != S5_HISTORY_STOP
        or result.attempt.attempted is not True
        or result.attempt.succeeded is not True
        or result.attempt.exit_code != 0
        or result.attempt.error_type != "ValueError"
        or result.attempt.error_message is None
        or MISSING_BLOB_ERROR.fullmatch(result.attempt.error_message) is None
        or result.network_process_count != 1
        or result.repository_history_records_semantically_parsed != 0
        or result.btc_market_values_read != 0
        or result.returns_calculated != 0
        or result.orders_submitted != 0
    )
    if lineage_changed:
        raise ValueError("S5 verifier-failure lineage changed")
    if result.attempt.transcript_file_sha256 != file_sha256(TRANSCRIPT_PATH):
        raise ValueError("S5 clone transcript changed")
    if not PARTIAL_DATASET_PATH.exists():
        raise ValueError("S5 preserved partial dataset is missing")

    manifest = manifest_for_directory(PARTIAL_DATASET_PATH)
    bare = one_line(PARTIAL_DATASET_PATH, "rev-parse", "--is-bare-repository") == "true"
    shallow = one_line(PARTIAL_DATASET_PATH, "rev-parse", "--is-shallow-repository")
    origin = one_line(PARTIAL_DATASET_PATH, "config", "--get", "remote.origin.url")
    promisor = (
        one_line(PARTIAL_DATASET_PATH, "config", "--bool", "--get", "remote.origin.promisor")
        == "true"
    )
    partial_filter = one_line(
        PARTIAL_DATASET_PATH, "config", "--get", "remote.origin.partialclonefilter"
    )
    cutoff_check = local_git(
        PARTIAL_DATASET_PATH,
        "cat-file",
        "-e",
        f"{protocol.source_cutoff_commit}^{{commit}}",
        check=False,
    )
    commit_count_text = one_line(
        PARTIAL_DATASET_PATH, "rev-list", "--count", protocol.source_cutoff_commit
    )
    if (
        not manifest
        or not bare
        or shallow != "false"
        or origin != protocol.clone_spec.remote_url
        or not promisor
        or partial_filter != "blob:none"
        or cutoff_check.returncode != 0
        or not commit_count_text.isdigit()
        or int(commit_count_text) <= 0
    ):
        raise ValueError("S5 promised-blob failure could not be independently adjudicated")
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(RESULT_PATH),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "transcript_reverified": True,
        "dataset_manifest_reverified": True,
        "local_git_integrity_reverified": True,
        "passed_gate_count": result.passed_gate_count,
        "failed_gate_count": result.failed_gate_count,
        "dataset_file_count": len(manifest),
        "dataset_byte_count": sum(item.byte_count for item in manifest),
        "cutoff_commit_count": int(commit_count_text),
        "source_bindings": bindings(),
        "result_audit_evidence_hash": result_audit.audit_evidence_hash,
        "transcript_file_sha256": file_sha256(TRANSCRIPT_PATH),
        "partial_dataset_file_manifest": manifest,
        "partial_dataset_directory_sha256": manifest_hash(manifest),
        "verifier_error_message": result.attempt.error_message,
        "source_cutoff_commit": protocol.source_cutoff_commit,
    }
    provisional = S5BitcoinCoreHistoryVerifierFailureAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5BitcoinCoreHistoryVerifierFailureAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5BitcoinCoreHistoryVerifierFailureAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 verifier-failure audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 verifier-failure audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryVerifierFailureAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 verifier-failure audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit or check the S5 verifier failure.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5BitcoinCoreHistoryVerifierFailureAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(audited_at=stored.audited_at)
            if stored != expected or not audit_verifier_failure(stored):
                raise ValueError("Stored S5 verifier-failure audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"clone_success=1 files={audit.dataset_file_count} "
            f"bytes={audit.dataset_byte_count} commits={audit.cutoff_commit_count} "
            "additional_network=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
