from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5_HISTORY_GATE_IDS,
    S5_HISTORY_NEXT,
    S5_HISTORY_NONE,
    S5_HISTORY_PASS,
    S5_HISTORY_STOP,
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadProtocolAudit,
    S5BitcoinCoreHistoryPayloadResult,
    S5HistoryCloneAttempt,
    S5HistoryFileRecord,
    S5HistoryGateResult,
    audit_s5_history_protocol,
    audit_s5_history_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_history_payload_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_history_payload.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_history_payload.py")


@dataclass(frozen=True)
class DatasetInspection:
    manifest: tuple[S5HistoryFileRecord, ...] = ()
    directory_sha256: str | None = None
    byte_count: int = 0
    fetched_master_head: str | None = None
    cutoff_commit_present: bool = False
    cutoff_is_ancestor: bool = False
    repository_is_bare: bool = False
    repository_is_shallow: bool | None = None
    remote_origin_url: str | None = None
    remote_promisor: bool = False
    remote_partial_clone_filter: str | None = None
    local_branch_refs: tuple[str, ...] = ()
    local_tag_ref_count: int = 0
    reachable_object_id_count: int = 0
    reachable_object_id_stream_sha256: str | None = None
    cutoff_commit_count: int = 0


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if path.exists() or temporary.exists():
        raise ValueError(f"Refusing to overwrite S5 history artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_result_atomic(path: Path, result: S5BitcoinCoreHistoryPayloadResult) -> None:
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryPayloadResult.model_validate_json(serialized) != result:
        raise ValueError("S5 history payload result did not round-trip")
    write_bytes_atomic(path, serialized.encode("utf-8"))


def load_protocol(protocol_path: Path, audit_path: Path) -> S5BitcoinCoreHistoryPayloadProtocol:
    protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S5BitcoinCoreHistoryPayloadProtocolAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_s5_history_protocol(protocol)
        or not audit_s5_history_protocol_audit(audit)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.protocol_file_sha256 != file_sha256(protocol_path)
    ):
        raise ValueError("S5 history protocol or audit failed before execution")
    return protocol


def git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
        }
    )
    environment.pop("GITHUB_TOKEN", None)
    environment.pop("GH_TOKEN", None)
    return environment


def git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        raise ValueError("Git executable is unavailable")
    return executable


def local_git(
    repo: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    command = [
        git_executable(),
        "-c",
        "credential.helper=",
        "-c",
        "http.extraHeader=",
        "-C",
        str(repo),
        *arguments,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=git_environment(),
        timeout=120,
    )
    if check and completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Local Git integrity command failed: {message}")
    return completed


def canonical_lines(payload: bytes) -> tuple[str, ...]:
    return tuple(line.strip() for line in payload.decode("ascii").splitlines() if line.strip())


def manifest_for_directory(path: Path) -> tuple[S5HistoryFileRecord, ...]:
    records: list[S5HistoryFileRecord] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError(f"S5 history dataset contains a symbolic link: {candidate}")
        if not candidate.is_file():
            continue
        records.append(
            S5HistoryFileRecord(
                relative_path=candidate.relative_to(path).as_posix(),
                file_sha256=file_sha256(candidate),
                byte_count=candidate.stat().st_size,
            )
        )
    return tuple(records)


def manifest_hash(manifest: tuple[S5HistoryFileRecord, ...]) -> str:
    return universe_evidence_hash([item.model_dump(mode="json") for item in manifest])


def inspect_dataset(
    *, path: Path, protocol: S5BitcoinCoreHistoryPayloadProtocol
) -> DatasetInspection:
    bare = canonical_lines(local_git(path, "rev-parse", "--is-bare-repository").stdout) == ("true",)
    shallow_output = canonical_lines(local_git(path, "rev-parse", "--is-shallow-repository").stdout)
    shallow = None if not shallow_output else shallow_output == ("true",)
    origin_output = canonical_lines(
        local_git(path, "config", "--get", "remote.origin.url", check=False).stdout
    )
    promisor_output = canonical_lines(
        local_git(path, "config", "--bool", "--get", "remote.origin.promisor", check=False).stdout
    )
    filter_output = canonical_lines(
        local_git(path, "config", "--get", "remote.origin.partialclonefilter", check=False).stdout
    )
    master_output = canonical_lines(
        local_git(path, "rev-parse", "refs/heads/master^{commit}").stdout
    )
    fetched_master = master_output[0] if len(master_output) == 1 else None
    cutoff_check = local_git(
        path, "cat-file", "-e", f"{protocol.source_cutoff_commit}^{{commit}}", check=False
    )
    cutoff_present = cutoff_check.returncode == 0
    ancestor = False
    if cutoff_present and fetched_master is not None:
        ancestor = (
            local_git(
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
    object_ids: tuple[str, ...] = ()
    commit_count = 0
    object_stream_hash = None
    if cutoff_present:
        raw_ids = canonical_lines(
            local_git(
                path,
                "rev-list",
                "--objects",
                "--no-object-names",
                protocol.source_cutoff_commit,
            ).stdout
        )
        if any(
            len(value) != 40 or any(char not in "0123456789abcdef" for char in value)
            for value in raw_ids
        ):
            raise ValueError("S5 reachable object stream contains a non-SHA1 identifier")
        object_ids = tuple(sorted(set(raw_ids)))
        canonical_stream = ("\n".join(object_ids) + "\n").encode("ascii")
        object_stream_hash = hashlib.sha256(canonical_stream).hexdigest()
        count_output = canonical_lines(
            local_git(path, "rev-list", "--count", protocol.source_cutoff_commit).stdout
        )
        if len(count_output) != 1 or not count_output[0].isdigit():
            raise ValueError("S5 cutoff commit count is invalid")
        commit_count = int(count_output[0])
    manifest = manifest_for_directory(path)
    return DatasetInspection(
        manifest=manifest,
        directory_sha256=manifest_hash(manifest),
        byte_count=sum(item.byte_count for item in manifest),
        fetched_master_head=fetched_master,
        cutoff_commit_present=cutoff_present,
        cutoff_is_ancestor=ancestor,
        repository_is_bare=bare,
        repository_is_shallow=shallow,
        remote_origin_url=origin_output[0] if len(origin_output) == 1 else None,
        remote_promisor=promisor_output == ("true",),
        remote_partial_clone_filter=filter_output[0] if len(filter_output) == 1 else None,
        local_branch_refs=branch_refs,
        local_tag_ref_count=len(tag_refs),
        reachable_object_id_count=len(object_ids),
        reachable_object_id_stream_sha256=object_stream_hash,
        cutoff_commit_count=commit_count,
    )


def empty_attempt() -> S5HistoryCloneAttempt:
    return S5HistoryCloneAttempt(
        attempted=False,
        succeeded=False,
        started_at=None,
        completed_at=None,
        elapsed_seconds=None,
        exit_code=None,
        transcript_path=None,
        transcript_file_sha256=None,
        transcript_byte_count=0,
        error_type=None,
        error_message=None,
    )


def transcript_bytes(
    *,
    protocol: S5BitcoinCoreHistoryPayloadProtocol,
    started_at: datetime,
    completed_at: datetime,
    elapsed_seconds: float,
    exit_code: int,
    stdout: bytes,
    stderr: bytes,
    error_type: str | None,
    error_message: str | None,
) -> bytes:
    payload = {
        "schema_version": "aurex-s5-bitcoin-core-history-clone-transcript-v1",
        "attempt_id": "01_GIT_BLOBLESS_BARE_CLONE",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "remote_url": protocol.clone_spec.remote_url,
        "git_arguments": list(protocol.clone_spec.git_arguments),
        "destination": protocol.clone_spec.partial_dataset_path,
        "credential_helper_disabled": True,
        "interactive_prompt_disabled": True,
        "exit_code": exit_code,
        "stdout_base64": base64.b64encode(stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(stderr).decode("ascii"),
        "error_type": error_type,
        "error_message": error_message,
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def run_clone(
    *, protocol: S5BitcoinCoreHistoryPayloadProtocol
) -> tuple[S5HistoryCloneAttempt, DatasetInspection, Path | None, int]:
    spec = protocol.clone_spec
    final_path = Path(spec.final_dataset_path)
    partial_path = Path(spec.partial_dataset_path)
    transcript_path = Path(spec.raw_transcript_path)
    for path in (final_path, partial_path, transcript_path):
        if path.exists():
            raise ValueError(f"S5 history one-run destination already exists: {path}")
    free_disk = shutil.disk_usage(PROJECT_ROOT).free
    if free_disk < spec.minimum_free_disk_bytes:
        return empty_attempt(), DatasetInspection(), None, free_disk

    partial_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        git_executable(),
        "-c",
        "credential.helper=",
        "-c",
        "http.extraHeader=",
        "-c",
        "protocol.version=2",
        *spec.git_arguments,
        spec.remote_url,
        str(partial_path),
    ]
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    stdout = b""
    stderr = b""
    exit_code = -1
    error_type = None
    error_message = None
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=git_environment(),
            timeout=spec.maximum_elapsed_seconds,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
        if exit_code != 0:
            error_type = "GitCloneExitError"
            error_message = stderr.decode("utf-8", errors="replace").strip()[:2000]
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        error_type = "GitCloneTimeout"
        error_message = f"Clone exceeded {spec.maximum_elapsed_seconds} seconds"
    completed_at = datetime.now(UTC)
    elapsed = round(time.monotonic() - started_clock, 6)
    transcript = transcript_bytes(
        protocol=protocol,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=elapsed,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        error_type=error_type,
        error_message=error_message,
    )
    if len(transcript) > spec.maximum_transcript_bytes:
        raise ValueError("S5 history clone transcript exceeded its frozen byte limit")
    write_bytes_atomic(transcript_path, transcript)
    attempt = S5HistoryCloneAttempt(
        attempted=True,
        succeeded=exit_code == 0,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=elapsed,
        exit_code=exit_code,
        transcript_path=transcript_path.as_posix(),
        transcript_file_sha256=file_sha256(transcript_path),
        transcript_byte_count=transcript_path.stat().st_size,
        error_type=error_type,
        error_message=error_message,
    )
    inspection = DatasetInspection()
    if partial_path.exists():
        try:
            inspection = inspect_dataset(path=partial_path, protocol=protocol)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            if error_type is None:
                attempt = attempt.model_copy(
                    update={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:2000],
                    }
                )
    integrity_pass = (
        attempt.succeeded
        and inspection.repository_is_bare
        and inspection.repository_is_shallow is False
        and inspection.remote_origin_url == spec.remote_url
        and inspection.remote_promisor
        and inspection.remote_partial_clone_filter == "blob:none"
        and inspection.local_branch_refs == ("refs/heads/master",)
        and inspection.local_tag_ref_count == 0
        and inspection.cutoff_commit_present
        and inspection.cutoff_is_ancestor
        and inspection.reachable_object_id_count > 0
        and inspection.cutoff_commit_count > 0
        and 0 < inspection.byte_count <= spec.maximum_dataset_bytes
    )
    if integrity_pass:
        partial_path.replace(final_path)
        return attempt, inspection, final_path, free_disk
    return attempt, inspection, partial_path if partial_path.exists() else None, free_disk


def build_gate_results(
    *,
    protocol: S5BitcoinCoreHistoryPayloadProtocol,
    attempt: S5HistoryCloneAttempt,
    inspection: DatasetInspection,
    dataset_path: Path | None,
    free_disk_bytes_before: int,
    network_process_count: int,
) -> tuple[S5HistoryGateResult, ...]:
    spec = protocol.clone_spec
    final_path = Path(spec.final_dataset_path)
    conditions = (
        len(protocol.source_bindings) == 8,
        spec.remote_url == "https://github.com/bitcoin/bitcoin.git" and spec.branch == "master",
        len(protocol.source_cutoff_commit) == 40 and len(protocol.source_v30_tag_object) == 40,
        network_process_count == 1 and attempt.attempted,
        inspection.repository_is_bare
        and inspection.local_branch_refs == ("refs/heads/master",)
        and inspection.local_tag_ref_count == 0,
        free_disk_bytes_before >= spec.minimum_free_disk_bytes
        and 0 < inspection.byte_count <= spec.maximum_dataset_bytes,
        attempt.succeeded and dataset_path == final_path,
        inspection.cutoff_commit_present and inspection.cutoff_is_ancestor,
        inspection.repository_is_shallow is False,
        inspection.remote_origin_url == spec.remote_url
        and inspection.remote_promisor
        and inspection.remote_partial_clone_filter == "blob:none",
        bool(inspection.manifest)
        and inspection.directory_sha256 is not None
        and inspection.byte_count == sum(item.byte_count for item in inspection.manifest),
        inspection.reachable_object_id_count > 0
        and inspection.reachable_object_id_stream_sha256 is not None
        and inspection.cutoff_commit_count > 0,
        protocol.market_values_permitted is False
        and protocol.parameters_permitted is False
        and protocol.returns_permitted is False
        and protocol.orders_submitted == 0,
        protocol.history_semantic_parsing_permitted is False
        and protocol.github_api_requests_permitted is False
        and protocol.paper_permitted is False
        and protocol.live_permitted is False,
    )
    evidence = (
        "Eight frozen S5 charter, source, and readiness-v28 artifacts are hash-bound.",
        "The canonical public Bitcoin Core Git remote and master branch are fixed.",
        "The source cutoff and v30.0 tag object identities were frozen before history access.",
        "Exactly one credential-free, noninteractive Git clone process must execute.",
        "The resulting repository must be bare with only master and zero local tag refs.",
        "Pre-run free disk and the two-gigabyte dataset ceiling must both pass.",
        "The clone must complete and move atomically to the frozen final dataset path.",
        "The frozen source cutoff commit must exist and be an ancestor of fetched master.",
        "The repository must report complete, non-shallow history.",
        "Origin must be canonical and Git must preserve promisor plus blob:none filter metadata.",
        "Every regular dataset file must be hashed into a complete deterministic manifest.",
        "Only opaque cutoff-reachable object IDs and a commit count may be integrity-hashed.",
        "The protocol permits zero market values, parameters, returns, candidates, and orders.",
        "A PASS can authorize only a separately frozen completeness-census protocol.",
    )
    return tuple(
        S5HistoryGateResult(
            gate_id=gate_id,
            status="PASS" if condition else "FAIL",
            evidence=message,
        )
        for gate_id, condition, message in zip(
            S5_HISTORY_GATE_IDS, conditions, evidence, strict=True
        )
    )


def build_result(
    *,
    protocol: S5BitcoinCoreHistoryPayloadProtocol,
    attempt: S5HistoryCloneAttempt,
    inspection: DatasetInspection,
    dataset_path: Path | None,
    free_disk_bytes_before: int,
    network_process_count: int,
    executed_at: datetime,
) -> S5BitcoinCoreHistoryPayloadResult:
    gates = build_gate_results(
        protocol=protocol,
        attempt=attempt,
        inspection=inspection,
        dataset_path=dataset_path,
        free_disk_bytes_before=free_disk_bytes_before,
        network_process_count=network_process_count,
    )
    failed = sum(item.status == "FAIL" for item in gates)
    passed = len(gates) - failed
    success = failed == 0
    final_path = Path(protocol.clone_spec.final_dataset_path)
    partial_path = Path(protocol.clone_spec.partial_dataset_path)
    payload: dict[str, Any] = {
        "executed_at": executed_at,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "attempt": attempt,
        "dataset_path": final_path.as_posix() if dataset_path == final_path else None,
        "partial_dataset_path": (partial_path.as_posix() if dataset_path == partial_path else None),
        "dataset_file_manifest": inspection.manifest,
        "dataset_file_count": len(inspection.manifest),
        "dataset_byte_count": inspection.byte_count,
        "dataset_directory_sha256": inspection.directory_sha256,
        "free_disk_bytes_before": free_disk_bytes_before,
        "fetched_master_head": inspection.fetched_master_head,
        "source_cutoff_commit": protocol.source_cutoff_commit,
        "cutoff_commit_present": inspection.cutoff_commit_present,
        "cutoff_is_ancestor_of_fetched_master": inspection.cutoff_is_ancestor,
        "repository_is_bare": inspection.repository_is_bare,
        "repository_is_shallow": inspection.repository_is_shallow,
        "remote_origin_url": inspection.remote_origin_url,
        "remote_promisor": inspection.remote_promisor,
        "remote_partial_clone_filter": inspection.remote_partial_clone_filter,
        "local_branch_refs": inspection.local_branch_refs,
        "local_tag_ref_count": inspection.local_tag_ref_count,
        "reachable_object_id_count": inspection.reachable_object_id_count,
        "reachable_object_id_stream_sha256": inspection.reachable_object_id_stream_sha256,
        "cutoff_commit_count": inspection.cutoff_commit_count,
        "newer_remote_state_incidentally_acquired": (
            inspection.fetched_master_head is not None
            and inspection.fetched_master_head != protocol.source_cutoff_commit
        ),
        "gate_results": gates,
        "passed_gate_count": passed,
        "failed_gate_count": failed,
        "network_process_count": network_process_count,
        "repository_history_records_acquired": inspection.cutoff_commit_count,
        "payload_conclusion": (
            "CANONICAL_HISTORY_PAYLOAD_ACQUIRED_FOR_INTEGRITY_CENSUS_ONLY"
            if success
            else "PAYLOAD_NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL"
        ),
        "decision": S5_HISTORY_PASS if success else S5_HISTORY_STOP,
        "next_authorization": S5_HISTORY_NEXT if success else S5_HISTORY_NONE,
        "authorizes_history_completeness_census_protocol": success,
        "limitations": tuple(
            sorted(
                (
                    "This result establishes only canonical Git payload acquisition and integrity.",
                    "Commit counts and object identifiers were used only for integrity and are "
                    "nonqualifying.",
                    "No commit message, author identity, author timestamp, or pull-request "
                    "identifier was read.",
                    "A newer fetched master, when present, was acquired incidentally and is barred "
                    "from analysis after the frozen cutoff.",
                    "The blob:none filter minimizes file payloads but does not remove commit "
                    "or tree topology.",
                    "Git transport success does not prove GitHub REST capacity for pull-request "
                    "metadata.",
                    "No predictive relationship, strategy, or profitable edge was tested or "
                    "established.",
                    "A PASS authorizes only a separately frozen history-completeness census "
                    "protocol.",
                    "The dataset cannot be used for parameter selection, signal construction, or "
                    "market comparison at this stage.",
                    "No BTC market value, return, candidate, signal, paper order, Testnet strategy "
                    "order, production action, live action, real capital, or profit was created.",
                    "The public repository can change after acquisition; frozen hashes preserve "
                    "the exact local payload received.",
                    "Partial clone integrity does not imply historical point-in-time availability "
                    "of later pull-request metadata.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreHistoryPayloadResult.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5BitcoinCoreHistoryPayloadResult.model_validate(complete)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the S5 history payload acquisition once.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S5 history result already exists; rerun forbidden: {args.output}")
        protocol = load_protocol(args.protocol, args.protocol_audit)
        attempt, inspection, dataset_path, free_disk = run_clone(protocol=protocol)
        result = build_result(
            protocol=protocol,
            attempt=attempt,
            inspection=inspection,
            dataset_path=dataset_path,
            free_disk_bytes_before=free_disk,
            network_process_count=1 if attempt.attempted else 0,
            executed_at=datetime.now(UTC),
        )
        write_result_atomic(args.output, result)
        print(
            f"RECORDED {args.output} {result.result_evidence_hash} "
            f"decision={result.decision} network={result.network_process_count} "
            f"files={result.dataset_file_count} bytes={result.dataset_byte_count} "
            f"commits={result.cutoff_commit_count} gates="
            f"{result.passed_gate_count}/{len(result.gate_results)} market_values=0 "
            "returns=0 orders=0"
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
