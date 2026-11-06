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
from aurex.backtest_engine.s5_complete_release_tag_source_remediation import (  # noqa: E402
    S5_COMPLETE_RELEASE_REMEDIATION_AUDIT_DECISION,
    S5_COMPLETE_RELEASE_REMEDIATION_GATES,
    S5_COMPLETE_RELEASE_REMEDIATION_NEXT,
    S5CompleteReleaseTagSourceRemediationProtocolAuditV1,
    S5CompleteReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_complete_release_tag_source_remediation_execution import (  # noqa: E402
    S5_COMPLETE_RELEASE_PASS,
    S5_COMPLETE_RELEASE_RESULT_NEXT,
    S5_COMPLETE_RELEASE_RUN,
    S5_COMPLETE_RELEASE_STOP,
    S5CompleteReleaseExecutionContractAuditV1,
    S5CompleteReleaseExecutionContractV1,
    S5CompleteReleaseGateResult,
    S5CompleteReleaseProcessTranscript,
    S5CompleteReleaseRemediationResultV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation import (  # noqa: E402
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (  # noqa: E402
    S5ReleaseTagDiscoveryRecord,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_complete_release_tag_source_remediation import (  # noqa: E402
    PRIOR_PROTOCOL,
    complete_tag_manifest,
    directory_manifest_hash,
)
from scripts.freeze_s5_complete_release_tag_source_remediation import (  # noqa: E402
    builder_contract_hash as protocol_builder_contract_hash,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_execution_contract_audit_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_complete_release_tag_source_remediation_result_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_complete_release_tag_source_remediation_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_complete_release_tag_source_remediation.py")
PROCESS_ROLES = (
    "REMOTE_EXACT_COMPLETE_TAG_FETCH",
    "LOCAL_COMPLETE_TAG_VERIFICATION",
)


@dataclass
class CompleteRemediationState:
    started_at: datetime
    protocol: S5CompleteReleaseTagSourceRemediationProtocolV1 | None = None
    protocol_audit: S5CompleteReleaseTagSourceRemediationProtocolAuditV1 | None = None
    contract: S5CompleteReleaseExecutionContractV1 | None = None
    contract_audit: S5CompleteReleaseExecutionContractAuditV1 | None = None
    original_hash: str = "0" * 64
    original_unchanged: bool = False
    incomplete_hash: str = "0" * 64
    incomplete_unchanged: bool = False
    destination_copy_completed: bool = False
    destination_prefetch_hash: str | None = None
    destination_final_hash: str | None = None
    destination_initial_bytes: int | None = None
    destination_final_bytes: int | None = None
    destination_growth_bytes: int | None = None
    transcripts: list[tuple[Path, S5CompleteReleaseProcessTranscript]] = field(
        default_factory=list
    )
    manifest: tuple[S5ReleaseTagDiscoveryRecord, ...] = ()
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


def directory_byte_count(path: Path) -> int:
    total = 0
    for candidate in path.rglob("*"):
        if candidate.is_symlink():
            raise ValueError("S5 complete release repository contains a symbolic link")
        if candidate.is_file():
            total += candidate.stat().st_size
    return total


def git_environment(*, safe_directory: Path) -> dict[str, str]:
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
            "GIT_CONFIG_COUNT": "3",
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "",
            "GIT_CONFIG_KEY_1": "http.extraHeader",
            "GIT_CONFIG_VALUE_1": "",
            "GIT_CONFIG_KEY_2": "safe.directory",
            "GIT_CONFIG_VALUE_2": str(safe_directory.resolve()),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_OPTIONAL_LOCKS": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
        }
    )
    return environment


def atomic_write_model(path: Path, model: BaseModel) -> None:
    if path.exists():
        raise ValueError(f"S5 complete release evidence already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise ValueError(f"S5 complete release temporary path exists: {temporary}")
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
) -> tuple[bytes, S5CompleteReleaseProcessTranscript]:
    if sequence != PROCESS_ROLES.index(role) + 1 or not command or command[0] != "git":
        raise ValueError("S5 complete release process command changed")
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
        raise ValueError("S5 complete release process output exceeded the byte limit")
    transcript = build_hashed(
        S5CompleteReleaseProcessTranscript,
        "transcript_evidence_hash",
        {
            "sequence": sequence,
            "process_role": role,
            "started_at": started_at,
            "completed_at": completed_at,
            "command": command,
            "network_process": sequence == 1,
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


def require_process_success(transcript: S5CompleteReleaseProcessTranscript) -> None:
    if transcript.return_code != 0:
        stderr = base64.b64decode(transcript.stderr_base64, validate=True)
        detail = stderr.decode("utf-8", errors="replace").strip()[-1_000:]
        raise ValueError(
            f"S5 complete release process {transcript.sequence} failed "
            f"({transcript.return_code}): {detail}"
        )


def parse_verified_tags(payload: bytes) -> dict[str, tuple[str, str, str]]:
    records: dict[str, tuple[str, str, str]] = {}
    for raw_record in payload.split(b"\x1e"):
        record = raw_record.strip(b"\r\n")
        if record.endswith(b"\x00"):
            record = record[:-1]
        if not record:
            continue
        fields = record.split(b"\x00")
        if len(fields) != 4:
            raise ValueError("S5 complete release verification framing changed")
        ref_name, object_type, object_sha, peeled_sha = (
            field.decode("ascii") for field in fields
        )
        if (
            ref_name in records
            or not ref_name.startswith("refs/tags/")
            or object_type not in {"tag", "commit"}
            or not re.fullmatch(r"[0-9a-f]{40}", object_sha)
            or (peeled_sha and not re.fullmatch(r"[0-9a-f]{40}", peeled_sha))
        ):
            raise ValueError("S5 complete release verification identity changed")
        records[ref_name] = (object_type, object_sha, peeled_sha)
    return records


def tag_identity_drift_count(
    manifest: tuple[S5ReleaseTagDiscoveryRecord, ...],
    verified: dict[str, tuple[str, str, str]],
) -> int:
    expected_refs = {item.ref_name for item in manifest}
    drift = len(expected_refs.symmetric_difference(verified))
    for item in manifest:
        expected = (
            "tag" if item.tag_type == "ANNOTATED" else "commit",
            item.object_sha,
            item.peeled_commit_sha if item.tag_type == "ANNOTATED" else "",
        )
        if item.ref_name in verified and verified[item.ref_name] != expected:
            drift += 1
    return drift


def expand_command(
    template: tuple[str, ...],
    *,
    protocol: S5CompleteReleaseTagSourceRemediationProtocolV1,
) -> tuple[str, ...]:
    replacements = {
        "{destination_history_dataset_path}": str(
            PROJECT_ROOT / protocol.destination_history_dataset_path
        )
    }
    return tuple(replacements.get(token, token) for token in template)


def load_authorization(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
) -> tuple[
    S5CompleteReleaseTagSourceRemediationProtocolV1,
    S5CompleteReleaseTagSourceRemediationProtocolAuditV1,
    S5CompleteReleaseExecutionContractV1,
    S5CompleteReleaseExecutionContractAuditV1,
]:
    protocol = S5CompleteReleaseTagSourceRemediationProtocolV1.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S5CompleteReleaseTagSourceRemediationProtocolAuditV1.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S5CompleteReleaseExecutionContractV1.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = S5CompleteReleaseExecutionContractAuditV1.model_validate_json(
        contract_audit_path.read_text(encoding="utf-8")
    )
    if (
        protocol.next_authorization != S5_COMPLETE_RELEASE_REMEDIATION_NEXT
        or protocol.builder_contract_hash != protocol_builder_contract_hash()
        or protocol_audit.decision != S5_COMPLETE_RELEASE_REMEDIATION_AUDIT_DECISION
        or protocol_audit.next_authorization != S5_COMPLETE_RELEASE_REMEDIATION_NEXT
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
        or not bindings_match(protocol_audit.auditor_implementation_bindings)
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or contract_audit.contract_file_sha256 != file_sha256(contract_path)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.builder_contract_hash != contract.builder_contract_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
        or not bindings_match(contract_audit.auditor_implementation_bindings)
        or contract_audit.next_authorization != S5_COMPLETE_RELEASE_RUN
    ):
        raise ValueError("S5 complete release execution authorization changed")
    return protocol, protocol_audit, contract, contract_audit


def gate_results(
    state: CompleteRemediationState,
    *,
    successful: bool,
) -> tuple[S5CompleteReleaseGateResult, ...]:
    values = dict(state.gates)
    if not successful:
        values["ANY_DRIFT_TIMEOUT_LIMIT_OR_COPY_MISMATCH_STOPS_THE_RUN"] = (
            False,
            "run stopped before complete-source authorization",
        )
        values.setdefault(
            "ZERO_MARKET_VALUES_RETURNS_PARAMETERS_CANDIDATES_SIGNALS_OR_ORDERS",
            (True, "zero market, strategy, signal, and order operations"),
        )
        values.setdefault(
            "PASS_AUTHORIZES_AMENDED_MEASUREMENT_PROTOCOL_ONLY",
            (False, "no complete-source pass was issued"),
        )
    return tuple(
        S5CompleteReleaseGateResult(
            gate_id=gate,
            status="PASS" if values.get(gate, (False, "not reached"))[0] else "FAIL",
            evidence=values.get(gate, (False, "not reached"))[1],
        )
        for gate in S5_COMPLETE_RELEASE_REMEDIATION_GATES
    )


def build_result(
    state: CompleteRemediationState,
    *,
    completed_at: datetime,
    failure: BaseException | None,
) -> S5CompleteReleaseRemediationResultV1:
    successful = failure is None
    gates = gate_results(state, successful=successful)
    transcript_paths = tuple(
        path.relative_to(PROJECT_ROOT).as_posix() for path, _ in state.transcripts
    )
    transcript_hashes = tuple(file_sha256(path) for path, _ in state.transcripts)
    local_count = sum(not item.network_process for _, item in state.transcripts)
    network_count = sum(item.network_process for _, item in state.transcripts)
    protocol_hash = state.protocol.protocol_evidence_hash if state.protocol else "0" * 64
    protocol_audit_hash = (
        state.protocol_audit.audit_evidence_hash if state.protocol_audit else "0" * 64
    )
    contract_hash = state.contract.contract_evidence_hash if state.contract else "0" * 64
    contract_audit_hash = (
        state.contract_audit.audit_evidence_hash if state.contract_audit else "0" * 64
    )
    safe_growth = state.destination_growth_bytes
    if safe_growth is not None and safe_growth > 536_870_912:
        safe_growth = None
    failure_type = type(failure).__name__ if failure is not None else None
    failure_message = None
    if failure is not None:
        failure_message = str(failure).replace("\x00", "")[:2_000] or failure_type
    manifest_hash = (
        universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in state.manifest)
        )
        if state.manifest
        else None
    )
    return build_hashed(
        S5CompleteReleaseRemediationResultV1,
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
            "original_repository_directory_sha256": state.original_hash,
            "original_repository_unchanged": state.original_unchanged,
            "incomplete_repository_directory_sha256": state.incomplete_hash,
            "incomplete_repository_unchanged": state.incomplete_unchanged,
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
            "complete_stable_tag_count": len(state.manifest) if state.manifest else None,
            "complete_annotated_tag_count": (
                sum(item.tag_type == "ANNOTATED" for item in state.manifest)
                if state.manifest
                else None
            ),
            "complete_lightweight_tag_count": (
                sum(item.tag_type == "LIGHTWEIGHT" for item in state.manifest)
                if state.manifest
                else None
            ),
            "complete_tag_manifest_evidence_hash": manifest_hash,
            "verified_tag_count": state.verified_tag_count,
            "remote_ref_drift_count": state.remote_ref_drift_count,
            "gate_results": gates,
            "passed_gate_count": sum(item.status == "PASS" for item in gates),
            "failed_gate_count": sum(item.status == "FAIL" for item in gates),
            "decision": S5_COMPLETE_RELEASE_PASS if successful else S5_COMPLETE_RELEASE_STOP,
            "next_authorization": (
                S5_COMPLETE_RELEASE_RESULT_NEXT
                if successful
                else (
                    "FREEZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_"
                    "FAILURE_ADJUDICATION_ONLY"
                )
            ),
            "authorizes_amended_measurement_protocol": successful,
            "failure_type": failure_type,
            "failure_message": failure_message,
            "limitations": tuple(
                sorted(
                    (
                        "A pass repairs release-tag source completeness only.",
                        "Annotated measurement-time filtering remains a later step.",
                        "Git tag signatures were not cryptographically verified.",
                        "No market value, return, strategy, signal, or order was created.",
                        "Prior repositories and evidence remain immutable.",
                        "Production and live trading remain prohibited.",
                        "Qualified strategies and real net profit remain zero.",
                        "The complete repository requires an independent result audit.",
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
) -> S5CompleteReleaseRemediationResultV1:
    state = CompleteRemediationState(started_at=datetime.now(UTC))
    failure: BaseException | None = None
    try:
        if DEFAULT_RESULT.exists():
            raise ValueError(f"S5 complete release result already exists: {DEFAULT_RESULT}")
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
        incomplete = PROJECT_ROOT / protocol.incomplete_release_dataset_path
        destination = PROJECT_ROOT / protocol.destination_history_dataset_path
        transcript_paths = (
            PROJECT_ROOT / protocol.fetch_transcript_path,
            PROJECT_ROOT / protocol.verification_transcript_path,
        )
        if (
            destination.exists()
            or (PROJECT_ROOT / protocol.transcript_directory).exists()
            or any(path.exists() for path in transcript_paths)
        ):
            raise ValueError("S5 complete release destination or transcripts are not new")
        state.original_hash = directory_manifest_hash(original)
        state.incomplete_hash = directory_manifest_hash(incomplete)
        if (
            state.original_hash != protocol.original_history_dataset_directory_sha256
            or state.incomplete_hash
            != protocol.incomplete_release_dataset_directory_sha256
        ):
            raise ValueError("S5 complete release source repository changed")
        prior_protocol = S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(
            PRIOR_PROTOCOL.read_text(encoding="utf-8")
        )
        state.manifest = complete_tag_manifest(prior_protocol)
        manifest_hash = universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in state.manifest)
        )
        if (
            len(state.manifest) != protocol.complete_stable_tag_count
            or manifest_hash != protocol.complete_stable_tag_manifest_evidence_hash
        ):
            raise ValueError("S5 complete release frozen tag manifest changed")
        shutil.copytree(incomplete, destination, symlinks=False)
        state.destination_copy_completed = True
        state.destination_initial_bytes = directory_byte_count(destination)
        state.destination_prefetch_hash = directory_manifest_hash(destination)
        if state.destination_prefetch_hash != state.incomplete_hash:
            raise ValueError("S5 complete release destination prefetch copy changed")
        environment = git_environment(safe_directory=destination)
        fetch_command = expand_command(protocol.fetch_command_prefix, protocol=protocol) + tuple(
            item.fetch_refspec for item in state.manifest
        )
        _, transcript = run_git_process(
            sequence=1,
            role=PROCESS_ROLES[0],
            command=fetch_command,
            transcript_path=transcript_paths[0],
            timeout_seconds=protocol.maximum_process_seconds,
            maximum_stdout_bytes=protocol.maximum_single_stdout_bytes,
            environment=environment,
        )
        state.transcripts.append((transcript_paths[0], transcript))
        require_process_success(transcript)
        verification_payload, transcript = run_git_process(
            sequence=2,
            role=PROCESS_ROLES[1],
            command=expand_command(protocol.verification_command, protocol=protocol),
            transcript_path=transcript_paths[1],
            timeout_seconds=protocol.maximum_process_seconds,
            maximum_stdout_bytes=protocol.maximum_single_stdout_bytes,
            environment=environment,
        )
        state.transcripts.append((transcript_paths[1], transcript))
        require_process_success(transcript)
        verified = parse_verified_tags(verification_payload)
        state.verified_tag_count = len(verified)
        state.remote_ref_drift_count = tag_identity_drift_count(state.manifest, verified)
        if state.verified_tag_count != 132 or state.remote_ref_drift_count != 0:
            raise ValueError(
                "S5 complete release fetched identities changed: "
                f"count={state.verified_tag_count} drift={state.remote_ref_drift_count}"
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
                f"S5 complete release destination growth changed: "
                f"{state.destination_growth_bytes}"
            )
        state.destination_final_hash = directory_manifest_hash(destination)
        state.original_unchanged = directory_manifest_hash(original) == state.original_hash
        state.incomplete_unchanged = (
            directory_manifest_hash(incomplete) == state.incomplete_hash
        )
        if not state.original_unchanged or not state.incomplete_unchanged:
            raise ValueError("S5 complete release prior repository was mutated")
        evidence = {
            "PRIOR_REMEDIATION_REJECTION_LINEAGE_IS_HASH_BOUND": "ten sources matched",
            "FOUR_PRIOR_PROCESS_TRANSCRIPTS_ARE_HASH_BOUND": "four prior transcripts matched",
            "FROZEN_DISCOVERY_CONTAINS_132_EXACT_STABLE_BASE_REFS": "132 stable refs",
            "ALL_104_ANNOTATED_STABLE_REFS_ARE_INCLUDED_REGARDLESS_OF_MASTER_ANCESTRY": (
                "104 annotated refs included"
            ),
            "ALL_28_LIGHTWEIGHT_STABLE_REFS_REMAIN_CUTOFF_REACHABLE": (
                "28 lightweight refs retained"
            ),
            "COMPLETE_132_TAG_OBJECT_AND_PEELED_IDENTITY_MANIFEST_IS_FROZEN": manifest_hash,
            "ORIGINAL_AND_42_TAG_REPOSITORIES_REMAIN_IMMUTABLE": "both hashes unchanged",
            "NEW_COMPLETE_DESTINATION_AND_TRANSCRIPT_PATHS_ARE_REQUIRED": (
                "new destination and two transcripts created"
            ),
            "OFFICIAL_BITCOIN_CORE_HTTPS_REMOTE_IS_EXACT": protocol.official_remote_url,
            "NO_NEW_REMOTE_DISCOVERY_IS_PERMITTED": "zero discovery processes",
            "ONE_EXACT_SORTED_132_REFSPEC_FETCH_PROCESS_ONLY": "one network fetch",
            "ONE_LOCAL_132_TAG_IDENTITY_VERIFICATION_PROCESS_ONLY": (
                "132 identities; zero drift"
            ),
            "ANNOTATED_TAGGER_TIME_CUTOFF_IS_DEFERRED_TO_AMENDED_MEASUREMENT": (
                "no tagger-time filtering performed"
            ),
            "LIGHTWEIGHT_COMMITTER_TIME_UNCERTAINTY_IS_PRESERVED": (
                "lightweight uncertainty preserved"
            ),
            "ALL_PROCESS_TRANSCRIPTS_ARE_ATOMIC_AND_HASH_PRESERVED": (
                "two transcripts persisted"
            ),
            "ANY_DRIFT_TIMEOUT_LIMIT_OR_COPY_MISMATCH_STOPS_THE_RUN": (
                "zero drift and all limits held"
            ),
            "ZERO_MARKET_VALUES_RETURNS_PARAMETERS_CANDIDATES_SIGNALS_OR_ORDERS": (
                "zero market, strategy, signal, and order operations"
            ),
            "PASS_AUTHORIZES_AMENDED_MEASUREMENT_PROTOCOL_ONLY": (
                S5_COMPLETE_RELEASE_RESULT_NEXT
            ),
        }
        state.gates = {
            gate: (True, evidence[gate])
            for gate in S5_COMPLETE_RELEASE_REMEDIATION_GATES
        }
    except BaseException as exc:
        failure = exc
        if state.protocol is not None:
            try:
                state.original_unchanged = (
                    directory_manifest_hash(
                        PROJECT_ROOT / state.protocol.original_history_dataset_path
                    )
                    == state.original_hash
                )
                state.incomplete_unchanged = (
                    directory_manifest_hash(
                        PROJECT_ROOT / state.protocol.incomplete_release_dataset_path
                    )
                    == state.incomplete_hash
                )
            except (OSError, ValueError):
                state.original_unchanged = False
                state.incomplete_unchanged = False
    completed_at = datetime.now(UTC)
    if (
        failure is None
        and state.protocol is not None
        and (completed_at - state.started_at).total_seconds()
        > state.protocol.maximum_total_seconds
    ):
        failure = TimeoutError("S5 complete release remediation exceeded total runtime")
    result = build_result(state, completed_at=completed_at, failure=failure)
    atomic_write_model(PROJECT_ROOT / DEFAULT_RESULT, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen complete S5 release-tag remediation exactly once."
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
    print(
        f"{result.decision} {DEFAULT_RESULT} {result.result_evidence_hash} "
        f"tags={result.complete_stable_tag_count or 0} "
        f"git_processes={result.process_count} network={result.network_process_count} "
        "market_values=0 returns=0 candidates=0 signals=0 orders=0",
        flush=True,
    )
    return 0 if result.decision == S5_COMPLETE_RELEASE_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
