from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_release_tag_source_remediation import (  # noqa: E402
    S5_RELEASE_REMEDIATION_AUDIT_DECISION,
    S5_RELEASE_REMEDIATION_GATES,
    S5_RELEASE_REMEDIATION_NEXT,
    S5ReleaseTagSourceRemediationProtocolAuditV1,
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (  # noqa: E402
    S5_RELEASE_REMEDIATION_PASS,
    S5_RELEASE_REMEDIATION_RESULT_NEXT,
    S5_RELEASE_REMEDIATION_RUN,
    S5_RELEASE_REMEDIATION_STOP,
    S5ReleaseRemediationGateResult,
    S5ReleaseTagDiscoveryRecord,
    S5ReleaseTagProcessTranscript,
    S5ReleaseTagSourceRemediationExecutionContractAuditV1,
    S5ReleaseTagSourceRemediationExecutionContractV1,
    S5ReleaseTagSourceRemediationResultV1,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_audit_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_release_tag_source_remediation_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_release_tag_source_remediation.py")

PROCESS_ROLES = (
    "REMOTE_TAG_DISCOVERY",
    "LOCAL_REACHABLE_COMMITS",
    "REMOTE_EXACT_TAG_FETCH",
    "LOCAL_TAG_VERIFICATION",
)


@dataclass
class RemediationState:
    started_at: datetime
    protocol: S5ReleaseTagSourceRemediationProtocolV1 | None = None
    protocol_audit: S5ReleaseTagSourceRemediationProtocolAuditV1 | None = None
    contract: S5ReleaseTagSourceRemediationExecutionContractV1 | None = None
    contract_audit: S5ReleaseTagSourceRemediationExecutionContractAuditV1 | None = None
    original_hash: str = "0" * 64
    original_unchanged: bool = False
    destination_copy_completed: bool = False
    destination_prefetch_hash: str | None = None
    destination_final_hash: str | None = None
    destination_initial_bytes: int | None = None
    destination_final_bytes: int | None = None
    destination_growth_bytes: int | None = None
    transcripts: list[tuple[Path, S5ReleaseTagProcessTranscript]] = field(
        default_factory=list
    )
    remote_record_count: int | None = None
    reachable_commit_count: int | None = None
    selected: tuple[S5ReleaseTagDiscoveryRecord, ...] = ()
    selected_manifest_hash: str | None = None
    verified_tag_count: int | None = None
    remote_ref_drift_count: int | None = None
    gates: dict[str, tuple[bool, str]] = field(default_factory=dict)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_hashed[ModelT: BaseModel](
    model: type[ModelT],
    hash_field: str,
    values: dict,
) -> ModelT:
    payload = dict(values)
    payload[hash_field] = "0" * 64
    preliminary = model.model_construct(**payload)
    payload[hash_field] = universe_evidence_hash(
        preliminary.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def implementation_bindings() -> tuple[S5HistoryBinding, ...]:
    paths = tuple(
        sorted((EXECUTION_MODULE_PATH, RUNNER_PATH), key=lambda path: path.as_posix())
    )
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in implementation_bindings())
    )


def binding_manifest_hash(bindings: tuple[S5HistoryBinding, ...]) -> str:
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in bindings)
    )


def bindings_match(bindings: tuple[S5HistoryBinding, ...]) -> bool:
    return all(
        (PROJECT_ROOT / binding.path).is_file()
        and file_sha256(PROJECT_ROOT / binding.path) == binding.file_sha256
        for binding in bindings
    )


def directory_manifest_hash(path: Path) -> str:
    records: list[dict] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError(f"S5 release dataset contains a symbolic link: {candidate}")
        if candidate.is_file():
            records.append(
                {
                    "relative_path": candidate.relative_to(path).as_posix(),
                    "file_sha256": file_sha256(candidate),
                    "byte_count": candidate.stat().st_size,
                }
            )
    if not records:
        raise ValueError(f"S5 release dataset is empty: {path}")
    return universe_evidence_hash(records)


def directory_byte_count(path: Path) -> int:
    total = 0
    for candidate in path.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(f"S5 release dataset contains a symbolic link: {candidate}")
        if candidate.is_file():
            total += candidate.stat().st_size
    return total


def git_environment(
    *,
    safe_directories: tuple[Path, ...] = (),
) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(
            marker in key.upper()
            for marker in (
                "PROXY",
                "TOKEN",
                "PASSWORD",
                "CREDENTIAL",
                "AUTHORIZATION",
                "GIT_ASKPASS",
                "SSH_ASKPASS",
            )
        )
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_OPTIONAL_LOCKS": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
        }
    )
    config_entries = (
        ("credential.helper", ""),
        ("http.extraHeader", ""),
        *(
            ("safe.directory", str(path.resolve()))
            for path in sorted(set(safe_directories), key=lambda item: str(item.resolve()))
        ),
    )
    environment["GIT_CONFIG_COUNT"] = str(len(config_entries))
    for index, (key, value) in enumerate(config_entries):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    return environment


def atomic_write_model(path: Path, model: BaseModel) -> None:
    if path.exists():
        raise ValueError(f"S5 release evidence path already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise ValueError(f"S5 release temporary evidence path already exists: {temporary}")
    serialized = model.model_dump_json(indent=2) + "\n"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def run_git_process(
    *,
    sequence: int,
    role: str,
    command: tuple[str, ...],
    transcript_path: Path,
    timeout_seconds: int,
    maximum_stdout_bytes: int,
    environment: dict[str, str],
) -> tuple[bytes, S5ReleaseTagProcessTranscript]:
    if sequence != PROCESS_ROLES.index(role) + 1:
        raise ValueError("S5 release Git process sequence changed")
    if not command or command[0] != "git":
        raise ValueError("S5 release Git executable changed")
    started_at = datetime.now(UTC)
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = (exc.stderr or b"") + b"\nAUREX_PROCESS_TIMEOUT\n"
        return_code = 124
    except OSError as exc:
        stdout = b""
        stderr = f"AUREX_PROCESS_START_FAILURE: {type(exc).__name__}: {exc}\n".encode(
            "utf-8", errors="replace"
        )
        return_code = 127
    completed_at = datetime.now(UTC)
    if len(stdout) > maximum_stdout_bytes or len(stderr) > maximum_stdout_bytes:
        raise ValueError("S5 release Git process output exceeded the frozen byte limit")
    transcript = build_hashed(
        S5ReleaseTagProcessTranscript,
        "transcript_evidence_hash",
        {
            "sequence": sequence,
            "process_role": role,
            "started_at": started_at,
            "completed_at": completed_at,
            "command": command,
            "network_process": role
            in {"REMOTE_TAG_DISCOVERY", "REMOTE_EXACT_TAG_FETCH"},
            "return_code": return_code,
            "stdout_byte_count": len(stdout),
            "stderr_byte_count": len(stderr),
            "stdout_sha256": sha256(stdout).hexdigest(),
            "stderr_sha256": sha256(stderr).hexdigest(),
            "stdout_base64": base64.b64encode(stdout).decode("ascii"),
            "stderr_base64": base64.b64encode(stderr).decode("ascii"),
        },
    )
    atomic_write_model(transcript_path, transcript)
    return stdout, transcript


def require_process_success(transcript: S5ReleaseTagProcessTranscript) -> None:
    if transcript.return_code != 0:
        stderr = base64.b64decode(transcript.stderr_base64, validate=True)
        detail = stderr.decode("utf-8", errors="replace").strip()[-1_000:]
        raise ValueError(
            f"S5 release Git process {transcript.sequence} failed "
            f"({transcript.return_code}): {detail}"
        )


def parse_ls_remote_tags(payload: bytes) -> dict[str, str]:
    records: dict[str, str] = {}
    for raw_line in payload.splitlines():
        if not raw_line:
            continue
        fields = raw_line.split(b"\t")
        if len(fields) != 2:
            raise ValueError("S5 remote tag discovery framing changed")
        object_sha = fields[0].decode("ascii")
        ref_name = fields[1].decode("utf-8")
        if (
            not re.fullmatch(r"[0-9a-f]{40}", object_sha)
            or not ref_name.startswith("refs/tags/")
            or ref_name in records
        ):
            raise ValueError("S5 remote tag discovery identity changed")
        records[ref_name] = object_sha
    if not records:
        raise ValueError("S5 remote tag discovery returned no tag refs")
    return records


def parse_reachable_commits(payload: bytes) -> frozenset[str]:
    commits = tuple(line for line in payload.decode("ascii").splitlines() if line)
    if any(not re.fullmatch(r"[0-9a-f]{40}", item) for item in commits):
        raise ValueError("S5 release reachable commit stream changed")
    if len(commits) != len(set(commits)):
        raise ValueError("S5 release reachable commit stream contains duplicates")
    if not commits:
        raise ValueError("S5 release reachable commit stream is empty")
    return frozenset(commits)


def select_stable_tags(
    remote_records: dict[str, str],
    *,
    stable_release_tag_regex: str,
    reachable_commits: frozenset[str],
    maximum_selected: int,
) -> tuple[S5ReleaseTagDiscoveryRecord, ...]:
    pattern = re.compile(stable_release_tag_regex)
    selected: list[S5ReleaseTagDiscoveryRecord] = []
    stable_base_refs = tuple(
        sorted(ref_name for ref_name in remote_records if pattern.fullmatch(ref_name))
    )
    for peeled_ref in remote_records:
        if peeled_ref.endswith("^{}"):
            base_ref = peeled_ref[:-3]
            if pattern.fullmatch(base_ref) and base_ref not in remote_records:
                raise ValueError("S5 stable annotated tag has no base ref")
    for ref_name in stable_base_refs:
        object_sha = remote_records[ref_name]
        peeled_sha = remote_records.get(f"{ref_name}^{{}}")
        if peeled_sha is None:
            if object_sha not in reachable_commits:
                continue
            peeled_sha = object_sha
            tag_type = "LIGHTWEIGHT"
        else:
            if peeled_sha not in reachable_commits:
                continue
            tag_type = "ANNOTATED"
        selected.append(
            S5ReleaseTagDiscoveryRecord(
                ref_name=ref_name,
                object_sha=object_sha,
                peeled_commit_sha=peeled_sha,
                tag_type=tag_type,
                fetch_refspec=f"+{ref_name}:{ref_name}",
            )
        )
    if not selected:
        raise ValueError("S5 release discovery selected no reachable stable tags")
    if len(selected) > maximum_selected:
        raise ValueError("S5 release discovery exceeded the stable-tag limit")
    return tuple(selected)


def parse_local_tags(payload: bytes) -> dict[str, tuple[str, str, str]]:
    records: dict[str, tuple[str, str, str]] = {}
    for raw_record in payload.split(b"\x1e"):
        record = raw_record.strip(b"\r\n")
        if record.endswith(b"\x00"):
            record = record[:-1]
        if not record:
            continue
        fields = record.split(b"\x00")
        if len(fields) != 4:
            raise ValueError("S5 fetched tag verification framing changed")
        ref_name, object_type, object_sha, peeled_sha = (
            field.decode("ascii") for field in fields
        )
        if (
            not ref_name.startswith("refs/tags/")
            or object_type not in {"commit", "tag"}
            or not re.fullmatch(r"[0-9a-f]{40}", object_sha)
            or (peeled_sha and not re.fullmatch(r"[0-9a-f]{40}", peeled_sha))
            or ref_name in records
        ):
            raise ValueError("S5 fetched tag verification identity changed")
        records[ref_name] = (object_type, object_sha, peeled_sha)
    return records


def compare_fetched_tags(
    selected: tuple[S5ReleaseTagDiscoveryRecord, ...],
    local_records: dict[str, tuple[str, str, str]],
) -> int:
    expected_refs = {item.ref_name for item in selected}
    drift = len(expected_refs.symmetric_difference(local_records))
    for item in selected:
        actual = local_records.get(item.ref_name)
        expected = (
            "tag" if item.tag_type == "ANNOTATED" else "commit",
            item.object_sha,
            item.peeled_commit_sha if item.tag_type == "ANNOTATED" else "",
        )
        if actual is not None and actual != expected:
            drift += 1
    return drift


def expand_command(
    template: tuple[str, ...],
    *,
    protocol: S5ReleaseTagSourceRemediationProtocolV1,
) -> tuple[str, ...]:
    replacements = {
        "{original_history_dataset_path}": str(
            PROJECT_ROOT / protocol.original_history_dataset_path
        ),
        "{destination_history_dataset_path}": str(
            PROJECT_ROOT / protocol.destination_history_dataset_path
        ),
        "{source_cutoff_commit}": protocol.source_cutoff_commit,
    }
    return tuple(replacements.get(token, token) for token in template)


def load_authorization(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
) -> tuple[
    S5ReleaseTagSourceRemediationProtocolV1,
    S5ReleaseTagSourceRemediationProtocolAuditV1,
    S5ReleaseTagSourceRemediationExecutionContractV1,
    S5ReleaseTagSourceRemediationExecutionContractAuditV1,
]:
    protocol = S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S5ReleaseTagSourceRemediationProtocolAuditV1.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S5ReleaseTagSourceRemediationExecutionContractV1.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = (
        S5ReleaseTagSourceRemediationExecutionContractAuditV1.model_validate_json(
            contract_audit_path.read_text(encoding="utf-8")
        )
    )
    if (
        protocol.next_authorization != S5_RELEASE_REMEDIATION_NEXT
        or protocol_audit.decision != S5_RELEASE_REMEDIATION_AUDIT_DECISION
        or protocol_audit.next_authorization != S5_RELEASE_REMEDIATION_NEXT
        or protocol_audit.protocol_file_sha256 != file_sha256(protocol_path)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or not contract.authorizes_single_remediation_run
        or contract.runner_contract_hash != runner_contract_hash()
        or contract.implementation_bindings != implementation_bindings()
        or contract.source_binding_manifest_evidence_hash
        != binding_manifest_hash(contract.source_bindings)
        or contract.implementation_binding_manifest_evidence_hash
        != binding_manifest_hash(contract.implementation_bindings)
        or not bindings_match(protocol.source_bindings)
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or contract_audit.contract_file_sha256 != file_sha256(contract_path)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.builder_contract_hash != contract.builder_contract_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
        or contract_audit.source_binding_manifest_evidence_hash
        != contract.source_binding_manifest_evidence_hash
        or contract_audit.implementation_binding_manifest_evidence_hash
        != contract.implementation_binding_manifest_evidence_hash
        or not bindings_match(contract_audit.auditor_implementation_bindings)
        or contract_audit.next_authorization != S5_RELEASE_REMEDIATION_RUN
    ):
        raise ValueError("S5 release remediation execution authorization changed")
    return protocol, protocol_audit, contract, contract_audit


def gate_results(
    state: RemediationState,
    *,
    successful: bool,
) -> tuple[S5ReleaseRemediationGateResult, ...]:
    if successful:
        values = {
            gate: (True, state.gates.get(gate, (True, "verified"))[1])
            for gate in S5_RELEASE_REMEDIATION_GATES
        }
    else:
        values = dict(state.gates)
        values["ANY_REF_DRIFT_SCHEMA_LIMIT_TIMEOUT_OR_COPY_MISMATCH_STOPS_THE_RUN"] = (
            False,
            "run stopped before remediation authorization",
        )
        values.setdefault(
            "ZERO_MARKET_VALUES_RETURNS_PARAMETERS_CANDIDATES_SIGNALS_OR_ORDERS",
            (True, "zero market, strategy, signal, and order operations"),
        )
        values.setdefault(
            "PASS_AUTHORIZES_AMENDED_MEASUREMENT_PROTOCOL_ONLY",
            (False, "no remediation pass was issued"),
        )
    return tuple(
        S5ReleaseRemediationGateResult(
            gate_id=gate,
            status="PASS" if values.get(gate, (False, "not reached"))[0] else "FAIL",
            evidence=values.get(gate, (False, "not reached"))[1],
        )
        for gate in S5_RELEASE_REMEDIATION_GATES
    )


def build_result(
    state: RemediationState,
    *,
    completed_at: datetime,
    failure: BaseException | None,
) -> S5ReleaseTagSourceRemediationResultV1:
    successful = failure is None
    gates = gate_results(state, successful=successful)
    protocol_hash = state.protocol.protocol_evidence_hash if state.protocol else "0" * 64
    protocol_audit_hash = (
        state.protocol_audit.audit_evidence_hash if state.protocol_audit else "0" * 64
    )
    contract_hash = state.contract.contract_evidence_hash if state.contract else "0" * 64
    contract_audit_hash = (
        state.contract_audit.audit_evidence_hash if state.contract_audit else "0" * 64
    )
    transcript_paths = tuple(
        path.relative_to(PROJECT_ROOT).as_posix() for path, _ in state.transcripts
    )
    transcript_hashes = tuple(file_sha256(path) for path, _ in state.transcripts)
    local_count = sum(not item.network_process for _, item in state.transcripts)
    network_count = sum(item.network_process for _, item in state.transcripts)
    safe_growth = state.destination_growth_bytes
    if safe_growth is not None and safe_growth > 536_870_912:
        safe_growth = None
    message = None
    failure_type = None
    if failure is not None:
        failure_type = type(failure).__name__
        message = str(failure).replace("\x00", "")[:2_000] or failure_type
    return build_hashed(
        S5ReleaseTagSourceRemediationResultV1,
        "result_evidence_hash",
        {
            "started_at": state.started_at,
            "completed_at": completed_at,
            "elapsed_seconds": (completed_at - state.started_at).total_seconds(),
            "protocol_evidence_hash": protocol_hash,
            "protocol_audit_evidence_hash": protocol_audit_hash,
            "execution_contract_evidence_hash": contract_hash,
            "execution_contract_audit_evidence_hash": contract_audit_hash,
            "runner_contract_hash": runner_contract_hash(),
            "original_history_dataset_directory_sha256": state.original_hash,
            "original_history_dataset_unchanged": state.original_unchanged,
            "destination_copy_completed": state.destination_copy_completed,
            "destination_prefetch_directory_sha256": state.destination_prefetch_hash,
            "destination_final_directory_sha256": state.destination_final_hash,
            "destination_initial_byte_count": state.destination_initial_bytes,
            "destination_final_byte_count": state.destination_final_bytes,
            "destination_growth_bytes": safe_growth,
            "transcript_paths": transcript_paths,
            "transcript_file_sha256s": transcript_hashes,
            "process_count": len(state.transcripts),
            "local_process_count": local_count,
            "network_process_count": network_count,
            "remote_tag_ref_record_count": state.remote_record_count,
            "reachable_commit_count": state.reachable_commit_count,
            "selected_stable_tag_count": len(state.selected) if state.selected else None,
            "selected_annotated_tag_count": (
                sum(item.tag_type == "ANNOTATED" for item in state.selected)
                if state.selected
                else None
            ),
            "selected_lightweight_tag_count": (
                sum(item.tag_type == "LIGHTWEIGHT" for item in state.selected)
                if state.selected
                else None
            ),
            "selected_tag_manifest_evidence_hash": state.selected_manifest_hash,
            "verified_tag_count": state.verified_tag_count,
            "remote_ref_drift_count": state.remote_ref_drift_count,
            "gate_results": gates,
            "passed_gate_count": sum(item.status == "PASS" for item in gates),
            "failed_gate_count": sum(item.status == "FAIL" for item in gates),
            "decision": S5_RELEASE_REMEDIATION_PASS if successful else S5_RELEASE_REMEDIATION_STOP,
            "next_authorization": (
                S5_RELEASE_REMEDIATION_RESULT_NEXT
                if successful
                else "FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_FAILURE_ADJUDICATION_ONLY"
            ),
            "authorizes_amended_measurement_protocol": successful,
            "failure_type": failure_type,
            "failure_message": message,
            "limitations": tuple(
                sorted(
                    (
                        "A remediation pass repairs release-tag source availability only.",
                        "Fetched Git tags do not prove signer identity or signature validity.",
                        "Market values and returns were not read or calculated.",
                        "No strategy candidate, parameter, signal, or order was created.",
                        "Original no-tags evidence and rejected measurements remain immutable.",
                        "Production and live trading remain prohibited.",
                        "Qualified strategies and real net profit remain zero.",
                        "Release counts require a separately frozen amended measurement protocol.",
                    )
                )
            ),
        },
    )


def execute_remediation(
    *,
    protocol_path: Path = DEFAULT_PROTOCOL,
    protocol_audit_path: Path = DEFAULT_PROTOCOL_AUDIT,
    contract_path: Path = DEFAULT_CONTRACT,
    contract_audit_path: Path = DEFAULT_CONTRACT_AUDIT,
) -> S5ReleaseTagSourceRemediationResultV1:
    state = RemediationState(started_at=datetime.now(UTC))
    result_path = PROJECT_ROOT / S5ReleaseTagSourceRemediationExecutionContractV1.model_fields[
        "result_path"
    ].default
    failure: BaseException | None = None
    try:
        if result_path.exists():
            raise ValueError(f"S5 release result already exists: {result_path}")
        (
            state.protocol,
            state.protocol_audit,
            state.contract,
            state.contract_audit,
        ) = load_authorization(
            protocol_path=protocol_path,
            protocol_audit_path=protocol_audit_path,
            contract_path=contract_path,
            contract_audit_path=contract_audit_path,
        )
        protocol = state.protocol
        original = PROJECT_ROOT / protocol.original_history_dataset_path
        destination = PROJECT_ROOT / protocol.destination_history_dataset_path
        transcript_paths = tuple(
            PROJECT_ROOT / path
            for path in (
                protocol.discovery_transcript_path,
                protocol.reachability_transcript_path,
                protocol.fetch_transcript_path,
                protocol.verification_transcript_path,
            )
        )
        if (
            destination.exists()
            or (PROJECT_ROOT / protocol.transcript_directory).exists()
            or any(path.exists() for path in transcript_paths)
        ):
            raise ValueError("S5 release destination or transcript evidence is not new")
        state.gates["DESTINATION_REPOSITORY_AND_TRANSCRIPT_PATHS_ARE_NEW"] = (
            True,
            "destination repository and four transcript paths were absent",
        )
        state.gates["ALL_ELEVEN_SOURCE_BINDINGS_MATCH"] = (
            True,
            "all eleven protocol source bindings and execution bindings matched",
        )
        state.gates["MEASUREMENT_RESULT_REJECTION_AUDIT_IS_VALID_AND_TERMINAL"] = (
            True,
            "terminal rejection audit lineage matched",
        )
        if protocol.official_remote_url != "https://github.com/bitcoin/bitcoin.git":
            raise ValueError("S5 release official remote changed")
        state.gates["OFFICIAL_BITCOIN_CORE_HTTPS_REMOTE_IS_EXACT"] = (
            True,
            protocol.official_remote_url,
        )
        state.original_hash = directory_manifest_hash(original)
        if (
            state.original_hash != protocol.original_history_dataset_directory_sha256
            or file_sha256(original / "config")
            != protocol.original_repository_config_file_sha256
            or file_sha256(original / "packed-refs")
            != protocol.original_repository_packed_refs_file_sha256
        ):
            raise ValueError("S5 release original repository evidence changed")
        state.gates[
            "ORIGINAL_NO_TAGS_REPOSITORY_HASH_CONFIG_AND_PACKED_REFS_MATCH"
        ] = (True, state.original_hash)
        shutil.copytree(original, destination, symlinks=False)
        state.destination_copy_completed = True
        state.destination_initial_bytes = directory_byte_count(destination)
        state.destination_prefetch_hash = directory_manifest_hash(destination)
        if state.destination_prefetch_hash != state.original_hash:
            raise ValueError("S5 release destination prefetch copy hash changed")

        environment = git_environment(safe_directories=(original, destination))
        discovery_command = expand_command(protocol.discovery_command, protocol=protocol)
        if discovery_command != protocol.discovery_command:
            raise ValueError("S5 release discovery command changed")
        discovery_payload, transcript = run_git_process(
            sequence=1,
            role=PROCESS_ROLES[0],
            command=discovery_command,
            transcript_path=transcript_paths[0],
            timeout_seconds=protocol.maximum_process_seconds,
            maximum_stdout_bytes=protocol.maximum_single_stdout_bytes,
            environment=environment,
        )
        state.transcripts.append((transcript_paths[0], transcript))
        require_process_success(transcript)
        remote_records = parse_ls_remote_tags(discovery_payload)
        state.remote_record_count = len(remote_records)
        state.gates["REMOTE_TAG_DISCOVERY_IS_CREDENTIAL_FREE_AND_BYTE_BOUNDED"] = (
            True,
            f"{len(remote_records)} remote tag records; transcript {transcript.stdout_sha256}",
        )

        reachable_command = expand_command(
            protocol.reachable_commit_command, protocol=protocol
        )
        reachable_payload, transcript = run_git_process(
            sequence=2,
            role=PROCESS_ROLES[1],
            command=reachable_command,
            transcript_path=transcript_paths[1],
            timeout_seconds=protocol.maximum_process_seconds,
            maximum_stdout_bytes=protocol.maximum_single_stdout_bytes,
            environment=environment,
        )
        state.transcripts.append((transcript_paths[1], transcript))
        require_process_success(transcript)
        reachable = parse_reachable_commits(reachable_payload)
        state.reachable_commit_count = len(reachable)
        if len(reachable) != 50_395:
            raise ValueError(
                f"S5 release reachable commit count changed: {len(reachable)}"
            )
        state.selected = select_stable_tags(
            remote_records,
            stable_release_tag_regex=protocol.stable_release_tag_regex,
            reachable_commits=reachable,
            maximum_selected=protocol.maximum_selected_stable_tag_refs,
        )
        state.selected_manifest_hash = universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in state.selected)
        )
        state.gates["ONLY_EXACT_STABLE_TAG_NAMES_ARE_ELIGIBLE"] = (
            True,
            f"{len(state.selected)} exact stable-name refs selected",
        )
        state.gates["ANNOTATED_AND_LIGHTWEIGHT_TAG_IDENTITIES_ARE_UNAMBIGUOUS"] = (
            True,
            "base and peeled identities classified before fetch",
        )
        state.gates["PEELED_RELEASE_COMMIT_MUST_BE_REACHABLE_FROM_FROZEN_CUTOFF"] = (
            True,
            f"all selected tags resolve within {len(reachable)} reachable commits",
        )
        state.gates["AT_MOST_500_EXACT_TAG_REFS_CAN_BE_FETCHED"] = (
            True,
            f"{len(state.selected)} exact refspecs",
        )

        fetch_command = expand_command(protocol.fetch_command_prefix, protocol=protocol) + tuple(
            item.fetch_refspec for item in state.selected
        )
        _, transcript = run_git_process(
            sequence=3,
            role=PROCESS_ROLES[2],
            command=fetch_command,
            transcript_path=transcript_paths[2],
            timeout_seconds=protocol.maximum_process_seconds,
            maximum_stdout_bytes=protocol.maximum_single_stdout_bytes,
            environment=environment,
        )
        state.transcripts.append((transcript_paths[2], transcript))
        require_process_success(transcript)

        verification_command = expand_command(
            protocol.verification_command, protocol=protocol
        )
        verification_payload, transcript = run_git_process(
            sequence=4,
            role=PROCESS_ROLES[3],
            command=verification_command,
            transcript_path=transcript_paths[3],
            timeout_seconds=protocol.maximum_process_seconds,
            maximum_stdout_bytes=protocol.maximum_single_stdout_bytes,
            environment=environment,
        )
        state.transcripts.append((transcript_paths[3], transcript))
        require_process_success(transcript)
        local_records = parse_local_tags(verification_payload)
        state.verified_tag_count = len(local_records)
        state.remote_ref_drift_count = compare_fetched_tags(state.selected, local_records)
        if state.remote_ref_drift_count != 0:
            raise ValueError(
                f"S5 release fetched tag identity drift: {state.remote_ref_drift_count}"
            )
        state.gates["FETCHED_TAG_OBJECT_IDS_MUST_MATCH_DISCOVERY_EXACTLY"] = (
            True,
            f"{len(local_records)} fetched tag refs matched discovery",
        )
        if len(state.transcripts) != 4:
            raise ValueError("S5 release transcript count changed")
        state.gates["ALL_NETWORK_AND_GIT_TRANSCRIPTS_ARE_HASH_PRESERVED"] = (
            True,
            "four process transcripts were atomically persisted",
        )
        state.destination_final_bytes = directory_byte_count(destination)
        state.destination_growth_bytes = (
            state.destination_final_bytes - state.destination_initial_bytes
        )
        if (
            state.destination_growth_bytes < 0
            or state.destination_growth_bytes > protocol.maximum_destination_growth_bytes
        ):
            raise ValueError(
                f"S5 release destination growth changed: {state.destination_growth_bytes}"
            )
        state.destination_final_hash = directory_manifest_hash(destination)
        state.original_unchanged = directory_manifest_hash(original) == state.original_hash
        if not state.original_unchanged:
            raise ValueError("S5 release original evidence repository was mutated")
        state.gates["ORIGINAL_EVIDENCE_REPOSITORY_IS_NEVER_MUTATED"] = (
            True,
            state.original_hash,
        )
        state.gates[
            "ANY_REF_DRIFT_SCHEMA_LIMIT_TIMEOUT_OR_COPY_MISMATCH_STOPS_THE_RUN"
        ] = (True, "zero drift and all frozen limits held")
        state.gates[
            "ZERO_MARKET_VALUES_RETURNS_PARAMETERS_CANDIDATES_SIGNALS_OR_ORDERS"
        ] = (True, "zero market, strategy, signal, and order operations")
        state.gates["PASS_AUTHORIZES_AMENDED_MEASUREMENT_PROTOCOL_ONLY"] = (
            True,
            S5_RELEASE_REMEDIATION_RESULT_NEXT,
        )
        if set(state.gates) != set(S5_RELEASE_REMEDIATION_GATES) or any(
            not passed for passed, _ in state.gates.values()
        ):
            raise ValueError("S5 release remediation gate set is incomplete")
    except BaseException as exc:
        failure = exc
        if state.protocol is not None:
            original = PROJECT_ROOT / state.protocol.original_history_dataset_path
            try:
                state.original_unchanged = (
                    directory_manifest_hash(original) == state.original_hash
                )
            except (OSError, ValueError):
                state.original_unchanged = False
    completed_at = datetime.now(UTC)
    if (
        failure is None
        and state.protocol is not None
        and (completed_at - state.started_at).total_seconds()
        > state.protocol.maximum_total_seconds
    ):
        failure = TimeoutError("S5 release remediation exceeded the frozen total runtime")
    result = build_result(state, completed_at=completed_at, failure=failure)
    atomic_write_model(result_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen S5 release-tag source remediation exactly once."
    )
    parser.add_argument("--run", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    parse_args()
    try:
        result = execute_remediation()
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    result_path = DEFAULT_CONTRACT.parent / "s5_release_tag_source_remediation_result_v1.json"
    print(
        f"{result.decision} {result_path} "
        f"{result.result_evidence_hash} tags={result.selected_stable_tag_count or 0} "
        f"git_processes={result.process_count} network={result.network_process_count} "
        "market_values=0 returns=0 candidates=0 signals=0 orders=0",
        flush=True,
    )
    return 0 if result.decision == S5_RELEASE_REMEDIATION_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
