from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadResult,
    S5HistoryCloneAttempt,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
    S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    S5BitcoinCoreHistoryPayloadResultV2,
    S5BitcoinCoreHistoryVerifierFailureAudit,
    audit_verifier_amendment,
    audit_verifier_amendment_audit,
    audit_verifier_failure,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s5_bitcoin_core_history_payload import (  # noqa: E402
    DatasetInspection,
    build_result,
    canonical_lines,
    git_environment,
    git_executable,
    local_git,
    manifest_for_directory,
    manifest_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
DEFAULT_PRIOR_RESULT = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
DEFAULT_FAILURE_AUDIT = Path("data/evidence/s5_bitcoin_core_history_verifier_failure_audit_v1.json")
DEFAULT_AMENDMENT = Path("data/evidence/s5_bitcoin_core_history_local_verifier_amendment_v2.json")
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_history_local_verifier_amendment_audit_v2.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_payload_result_v2.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_history_payload_transport.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_history_local_verifier_v2.py")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def one_line(repo: Path, *arguments: str) -> str:
    output = canonical_lines(local_git(repo, *arguments).stdout)
    if len(output) != 1:
        raise ValueError(f"Expected one local Git line for {arguments}")
    return output[0]


def stream_reachable_object_ids(
    *, repo: Path, cutoff: str, timeout_seconds: int
) -> tuple[int, int, str]:
    command = [
        git_executable(),
        "-c",
        "credential.helper=",
        "-c",
        "http.extraHeader=",
        "-C",
        str(repo),
        "rev-list",
        "--objects",
        "--no-object-names",
        "--missing=print",
        cutoff,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_environment(),
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise ValueError("Corrected S5 object stream pipes are unavailable")
    digest = hashlib.sha256()
    count = 0
    missing_count = 0
    started = time.monotonic()
    try:
        for raw_line in process.stdout:
            if time.monotonic() - started > timeout_seconds:
                process.kill()
                raise ValueError("Corrected S5 object stream exceeded its frozen timeout")
            line = raw_line.strip()
            if not line:
                continue
            missing = line.startswith(b"?")
            object_id = line[1:] if missing else line
            if len(object_id) != 40 or any(byte not in b"0123456789abcdef" for byte in object_id):
                process.kill()
                raise ValueError("Corrected S5 object stream contains an invalid identifier")
            digest.update(line + b"\n")
            count += 1
            missing_count += int(missing)
        stderr = process.stderr.read()
        exit_code = process.wait(timeout=30)
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=30)
        raise
    if exit_code != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Corrected S5 object stream failed: {message}")
    if count == 0:
        raise ValueError("Corrected S5 object stream is empty")
    return count, missing_count, digest.hexdigest()


def inspect_dataset_v2(
    *,
    path: Path,
    protocol: S5BitcoinCoreHistoryPayloadProtocol,
    amendment: S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
) -> tuple[DatasetInspection, int]:
    bare = one_line(path, "rev-parse", "--is-bare-repository") == "true"
    shallow = one_line(path, "rev-parse", "--is-shallow-repository") == "true"
    origin = one_line(path, "config", "--get", "remote.origin.url")
    promisor = one_line(path, "config", "--bool", "--get", "remote.origin.promisor") == "true"
    partial_filter = one_line(path, "config", "--get", "remote.origin.partialclonefilter")
    fetched_master = one_line(path, "rev-parse", "refs/heads/master^{commit}")
    cutoff_present = (
        local_git(
            path,
            "cat-file",
            "-e",
            f"{protocol.source_cutoff_commit}^{{commit}}",
            check=False,
        ).returncode
        == 0
    )
    ancestor = (
        cutoff_present
        and local_git(
            path,
            "merge-base",
            "--is-ancestor",
            protocol.source_cutoff_commit,
            fetched_master,
            check=False,
        ).returncode
        == 0
    )
    branch_refs = canonical_lines(
        local_git(path, "for-each-ref", "--format=%(refname)", "refs/heads").stdout
    )
    tag_refs = canonical_lines(
        local_git(path, "for-each-ref", "--format=%(refname)", "refs/tags").stdout
    )
    commit_count_text = one_line(path, "rev-list", "--count", protocol.source_cutoff_commit)
    if not commit_count_text.isdigit():
        raise ValueError("Corrected S5 cutoff commit count is invalid")
    object_count, missing_count, stream_hash = stream_reachable_object_ids(
        repo=path,
        cutoff=protocol.source_cutoff_commit,
        timeout_seconds=amendment.corrected_stream_timeout_seconds,
    )
    manifest = manifest_for_directory(path)
    inspection = DatasetInspection(
        manifest=manifest,
        directory_sha256=manifest_hash(manifest),
        byte_count=sum(item.byte_count for item in manifest),
        fetched_master_head=fetched_master,
        cutoff_commit_present=cutoff_present,
        cutoff_is_ancestor=ancestor,
        repository_is_bare=bare,
        repository_is_shallow=shallow,
        remote_origin_url=origin,
        remote_promisor=promisor,
        remote_partial_clone_filter=partial_filter,
        local_branch_refs=branch_refs,
        local_tag_ref_count=len(tag_refs),
        reachable_object_id_count=object_count,
        reachable_object_id_stream_sha256=stream_hash,
        cutoff_commit_count=int(commit_count_text),
    )
    return inspection, missing_count


def load_inputs(
    *,
    protocol_path: Path,
    prior_result_path: Path,
    failure_audit_path: Path,
    amendment_path: Path,
    amendment_audit_path: Path,
) -> tuple[
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryVerifierFailureAudit,
    S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
]:
    protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    prior = S5BitcoinCoreHistoryPayloadResult.model_validate_json(
        prior_result_path.read_text(encoding="utf-8")
    )
    failure = S5BitcoinCoreHistoryVerifierFailureAudit.model_validate_json(
        failure_audit_path.read_text(encoding="utf-8")
    )
    amendment = S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    amendment_audit = S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2.model_validate_json(
        amendment_audit_path.read_text(encoding="utf-8")
    )
    changed = (
        not audit_verifier_failure(failure)
        or not audit_verifier_amendment(amendment)
        or not audit_verifier_amendment_audit(amendment_audit)
        or prior.protocol_evidence_hash != protocol.protocol_evidence_hash
        or failure.result_evidence_hash != prior.result_evidence_hash
        or amendment.protocol_evidence_hash != protocol.protocol_evidence_hash
        or amendment.prior_result_evidence_hash != prior.result_evidence_hash
        or amendment.failure_audit_evidence_hash != failure.audit_evidence_hash
        or amendment_audit.amendment_evidence_hash != amendment.amendment_evidence_hash
        or amendment.additional_network_process_count != 0
        or amendment.network_access_permitted is not False
    )
    if changed:
        raise ValueError("S5 corrected local-verifier lineage changed")
    return protocol, prior, failure, amendment, amendment_audit


def cleaned_attempt(prior: S5BitcoinCoreHistoryPayloadResult) -> S5HistoryCloneAttempt:
    return S5HistoryCloneAttempt.model_validate(
        {
            **prior.attempt.model_dump(mode="json"),
            "error_type": None,
            "error_message": None,
        }
    )


def build_result_v2(
    *,
    protocol: S5BitcoinCoreHistoryPayloadProtocol,
    prior: S5BitcoinCoreHistoryPayloadResult,
    failure: S5BitcoinCoreHistoryVerifierFailureAudit,
    amendment: S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    amendment_audit: S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
    inspection: DatasetInspection,
    missing_promised_object_count: int,
    dataset_path: Path,
    executed_at: datetime,
) -> S5BitcoinCoreHistoryPayloadResultV2:
    base = build_result(
        protocol=protocol,
        attempt=cleaned_attempt(prior),
        inspection=inspection,
        dataset_path=dataset_path,
        free_disk_bytes_before=prior.free_disk_bytes_before,
        network_process_count=1,
        executed_at=executed_at,
    )
    payload = base.model_dump(mode="json", exclude={"result_evidence_hash"})
    payload.update(
        {
            "schema_version": "aurex-s5-bitcoin-core-history-payload-result-v2",
            "result_id": "s5-bitcoin-core-history-payload-result-v2",
            "runner_contract_hash": runner_contract_hash(),
            "prior_result_file_sha256": file_sha256(DEFAULT_PRIOR_RESULT),
            "prior_result_evidence_hash": prior.result_evidence_hash,
            "prior_result_audit_evidence_hash": failure.result_audit_evidence_hash,
            "failure_audit_evidence_hash": failure.audit_evidence_hash,
            "verifier_amendment_file_sha256": file_sha256(DEFAULT_AMENDMENT),
            "verifier_amendment_evidence_hash": amendment.amendment_evidence_hash,
            "verifier_amendment_audit_evidence_hash": amendment_audit.audit_evidence_hash,
            "additional_network_process_count": 0,
            "missing_promised_object_count": missing_promised_object_count,
            "object_stream_transport_order_preserved": True,
        }
    )
    provisional = S5BitcoinCoreHistoryPayloadResultV2.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5BitcoinCoreHistoryPayloadResultV2.model_validate(complete)


def stage_result_v2(path: Path, result: S5BitcoinCoreHistoryPayloadResultV2) -> Path:
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(serialized) != result:
        raise ValueError("S5 corrected history result did not round-trip")
    if path.exists() or path.with_name(f"{path.name}.part").exists():
        raise ValueError(f"Refusing to overwrite S5 corrected history result: {path}")
    temporary = path.with_name(f"{path.name}.part")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    return temporary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the zero-network S5 verifier v2 once.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--prior-result", type=Path, default=DEFAULT_PRIOR_RESULT)
    parser.add_argument("--failure-audit", type=Path, default=DEFAULT_FAILURE_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S5 corrected result exists; rerun forbidden: {args.output}")
        protocol, prior, failure, amendment, amendment_audit = load_inputs(
            protocol_path=args.protocol,
            prior_result_path=args.prior_result,
            failure_audit_path=args.failure_audit,
            amendment_path=args.amendment,
            amendment_audit_path=args.amendment_audit,
        )
        partial_path = Path(amendment.preserved_partial_dataset_path)
        final_path = Path(amendment.final_dataset_path)
        if not partial_path.exists() or final_path.exists():
            raise ValueError("S5 corrected verifier dataset paths are not in the frozen state")
        inspection, missing_count = inspect_dataset_v2(
            path=partial_path, protocol=protocol, amendment=amendment
        )
        result = build_result_v2(
            protocol=protocol,
            prior=prior,
            failure=failure,
            amendment=amendment,
            amendment_audit=amendment_audit,
            inspection=inspection,
            missing_promised_object_count=missing_count,
            dataset_path=final_path,
            executed_at=datetime.now(UTC),
        )
        if result.failed_gate_count != 0:
            raise ValueError("S5 corrected verifier did not pass every unchanged gate")
        staged_result = stage_result_v2(args.output, result)
        partial_path.replace(final_path)
        staged_result.replace(args.output)
        print(
            f"RECORDED {args.output} {result.result_evidence_hash} "
            f"decision={result.decision} additional_network=0 "
            f"files={result.dataset_file_count} bytes={result.dataset_byte_count} "
            f"commits={result.cutoff_commit_count} objects={result.reachable_object_id_count} "
            f"promised_missing={result.missing_promised_object_count} "
            f"gates={result.passed_gate_count}/14 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
