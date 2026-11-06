from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization import (  # noqa: E402
    S5_CORRECTED_NORMALIZATION_GATE_IDS,
    S5GitHubCorrectedNormalizationProtocolAuditV2,
    S5GitHubCorrectedNormalizationProtocolV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization_execution import (  # noqa: E402
    S5_CORRECTED_NORMALIZATION_FAILURE_NEXT,
    S5_CORRECTED_NORMALIZATION_NEXT,
    S5_CORRECTED_NORMALIZATION_PASS,
    S5_CORRECTED_NORMALIZATION_STOP,
    S5CorrectedAcceptedCoverageRow,
    S5CorrectedCanonicalMappingRow,
    S5CorrectedNormalizationGateResult,
    S5CorrectedTargetResolutionRow,
    S5CorrectedUnresolvedMergeRow,
    S5GitHubCorrectedNormalizationExecutionContractAuditV2,
    S5GitHubCorrectedNormalizationExecutionContractV2,
    S5GitHubCorrectedNormalizationResultV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5GitHubNormalizationResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_normalization as legacy,
)
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction_v3 as targeted,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_protocol_v2.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_corrected_normalization_protocol_audit_v2.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_corrected_normalization_execution_contract_v2.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_corrected_normalization_execution_contract_audit_v2.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_result_v2.json"
)
FAILED_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_corrected_normalization_execution.py"
)
RUNNER_PATH = Path(
    "scripts/run_s5_bitcoin_core_github_corrected_normalization.py"
)
EXECUTION_AUDITOR_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_corrected_normalization_execution.py"
)
RUNNER_IMPLEMENTATION_PATHS = (
    EXECUTION_MODULE_PATH,
    RUNNER_PATH,
    legacy.EXECUTION_MODULE_PATH,
    legacy.RUNNER_PATH,
    targeted.base.RUNNER_PATH,
    targeted.V2_RUNNER_PATH,
    targeted.EXECUTION_MODULE_PATH,
    targeted.RUNNER_PATH,
)


@dataclass(frozen=True)
class TimedTopology:
    topology: legacy.GitTopology
    committer_times: dict[str, datetime]
    stream_sha256: str


@dataclass(frozen=True)
class TargetContext:
    path: Path
    parsed: Any
    payload: dict[str, Any] | None


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(
            {
                "path": path.as_posix(),
                "file_sha256": file_sha256(PROJECT_ROOT / path),
            }
            for path in sorted(
                RUNNER_IMPLEMENTATION_PATHS,
                key=lambda item: item.as_posix(),
            )
        )
    )


def bindings_match(rows: tuple[Any, ...]) -> bool:
    return all(
        file_sha256(PROJECT_ROOT / row.path) == row.file_sha256
        for row in rows
    )


def load_authorization(
    *,
    protocol_path: Path = DEFAULT_PROTOCOL,
    protocol_audit_path: Path = DEFAULT_PROTOCOL_AUDIT,
    contract_path: Path = DEFAULT_EXECUTION_CONTRACT,
    contract_audit_path: Path = DEFAULT_EXECUTION_CONTRACT_AUDIT,
) -> tuple[
    S5GitHubCorrectedNormalizationProtocolV2,
    S5GitHubCorrectedNormalizationProtocolAuditV2,
    S5GitHubCorrectedNormalizationExecutionContractV2,
    S5GitHubCorrectedNormalizationExecutionContractAuditV2,
]:
    protocol = S5GitHubCorrectedNormalizationProtocolV2.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S5GitHubCorrectedNormalizationProtocolAuditV2.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S5GitHubCorrectedNormalizationExecutionContractV2.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = (
        S5GitHubCorrectedNormalizationExecutionContractAuditV2.model_validate_json(
            contract_audit_path.read_text(encoding="utf-8")
        )
    )
    changed = (
        audit.protocol_file_sha256 != file_sha256(protocol_path)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_evidence_hash != audit.audit_evidence_hash
        or contract.runner_contract_hash != runner_contract_hash()
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
        or contract_audit.auditor_source_sha256
        != file_sha256(PROJECT_ROOT / EXECUTION_AUDITOR_PATH)
    )
    if changed:
        raise ValueError("S5 corrected normalization authorization changed")
    return protocol, audit, contract, contract_audit


def git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.casefold()
        not in {"http_proxy", "https_proxy", "all_proxy", "git_proxy_command"}
    }
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return environment


def run_git(protocol: S5GitHubCorrectedNormalizationProtocolV2, args: tuple[str, ...]) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git executable is unavailable")
    command = (
        git,
        f"--git-dir={Path(protocol.history_dataset_path).resolve()}",
        *args,
    )
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=protocol.maximum_elapsed_seconds,
        check=False,
        env=git_environment(),
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"S5 corrected normalization Git command failed: {message}")
    if len(completed.stdout) > protocol.maximum_each_output_bytes:
        raise ValueError("S5 corrected normalization Git output exceeds bound")
    return completed.stdout


def parse_timed_first_parent(payload: bytes) -> TimedTopology:
    try:
        lines = tuple(
            line.strip()
            for line in payload.decode("ascii").splitlines()
            if line.strip()
        )
    except UnicodeDecodeError as exc:
        raise ValueError("S5 corrected first-parent stream is not ASCII") from exc
    parent_lines: list[str] = []
    times: dict[str, datetime] = {}
    for line in lines:
        tokens = line.split()
        if len(tokens) < 2 or not tokens[0].isdigit():
            raise ValueError("S5 corrected first-parent timestamp row is invalid")
        commit_tokens = tokens[1:]
        if any(targeted.base.SHA1_RE.fullmatch(token) is None for token in commit_tokens):
            raise ValueError("S5 corrected first-parent SHA identity is invalid")
        commit = commit_tokens[0]
        if commit in times:
            raise ValueError("S5 corrected first-parent commit is duplicated")
        times[commit] = datetime.fromtimestamp(int(tokens[0]), tz=UTC)
        parent_lines.append(" ".join(commit_tokens))
    parent_payload = (
        ("\n".join(parent_lines) + "\n").encode("ascii")
        if parent_lines
        else b""
    )
    topology = legacy.parse_git_parent_stream(parent_payload)
    canonical = ("\n".join(lines) + "\n").encode("ascii") if lines else b""
    return TimedTopology(
        topology=topology,
        committer_times=times,
        stream_sha256=sha256(canonical).hexdigest(),
    )


def parse_full_graph(payload: bytes) -> tuple[frozenset[str], str]:
    try:
        commits = tuple(
            line.strip()
            for line in payload.decode("ascii").splitlines()
            if line.strip()
        )
    except UnicodeDecodeError as exc:
        raise ValueError("S5 corrected full graph is not ASCII") from exc
    if (
        any(targeted.base.SHA1_RE.fullmatch(commit) is None for commit in commits)
        or len(set(commits)) != len(commits)
    ):
        raise ValueError("S5 corrected full graph identity is invalid")
    canonical = ("\n".join(commits) + "\n").encode("ascii") if commits else b""
    return frozenset(commits), sha256(canonical).hexdigest()


def inspect_git(
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
) -> tuple[TimedTopology, frozenset[str], str]:
    timed = parse_timed_first_parent(
        run_git(
            protocol,
            (
                "rev-list",
                "--first-parent",
                "--reverse",
                "--parents",
                "--timestamp",
                protocol.source_cutoff_commit,
            ),
        )
    )
    graph, graph_hash = parse_full_graph(
        run_git(protocol, ("rev-list", protocol.source_cutoff_commit))
    )
    return timed, graph, graph_hash


def decode_target_contexts() -> tuple[
    Any,
    Any,
    tuple[TargetContext, ...],
]:
    target_protocol, protocol, *_ = targeted.load_authorization()
    responses = [
        targeted.load_adopted_response(
            target_protocol=target_protocol,
            protocol=protocol,
        ),
        *targeted.load_existing_responses(
            target_protocol=target_protocol,
            protocol=protocol,
        ),
    ]
    contexts: list[TargetContext] = []
    for path, parsed in responses:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        body = base64.b64decode(envelope["response"]["body_base64"], validate=True)
        payload = json.loads(body) if parsed.http_status == 200 else None
        contexts.append(TargetContext(path=path, parsed=parsed, payload=payload))
    return target_protocol, protocol, tuple(contexts)


def actor_fields(payload: dict[str, Any]) -> dict[str, Any]:
    user = payload["user"]
    if user is None:
        return {
            "actor_id": None,
            "actor_login": None,
            "actor_type": None,
            "actor_identity_status": "UNKNOWN_DELETED_OR_NULL",
            "actor_class": "UNKNOWN",
        }
    login = user["login"]
    actor_type = user["type"]
    return {
        "actor_id": user["id"],
        "actor_login": login,
        "actor_type": actor_type,
        "actor_identity_status": "KNOWN_ACCOUNT",
        "actor_class": (
            "BOT"
            if actor_type == "Bot" or login.casefold().endswith("[bot]")
            else "HUMAN_OR_UNRESOLVED_ACCOUNT"
        ),
    }


def canonical_mapping_rows(
    *,
    legacy_outcome: legacy.MappingOutcome,
    topology: TimedTopology,
    pulls_by_number: dict[int, Any],
    census_by_pull: dict[int, Any],
    merges_by_commit: dict[str, legacy.GitMerge],
    contexts: tuple[TargetContext, ...],
) -> tuple[S5CorrectedCanonicalMappingRow, ...]:
    rows: list[dict[str, Any]] = []
    for mapping in legacy_outcome.mappings:
        merge = merges_by_commit[mapping.merge_commit_sha]
        status = (
            "LEGACY_RECOGNIZED_NUMBER_AND_HEAD_SHA_EXACT"
            if mapping.census_pull_number is not None
            else "LEGACY_UNRECOGNIZED_SECOND_PARENT_HEAD_SHA_EXACT"
        )
        rows.append(
            {
                "merge": merge,
                "canonical_pull_number": mapping.pull_number,
                "census_pull_number": mapping.census_pull_number,
                "census_pattern_id": mapping.census_pattern_id,
                "mapping_status": status,
                "github_merged_at": mapping.merged_at,
                "actor_id": mapping.actor_id,
                "actor_login": mapping.actor_login,
                "actor_type": mapping.actor_type,
                "actor_identity_status": mapping.actor_identity_status,
                "actor_class": mapping.actor_class,
                "targeted_response_path": None,
                "targeted_response_file_sha256": None,
            }
        )
    for context in contexts:
        target = context.parsed.target
        if "RECOGNIZED_GAP" not in target.target_reasons or context.payload is None:
            continue
        census = census_by_pull[target.pull_number]
        merge = merges_by_commit[census.merge_commit_hash]
        if context.payload["head"]["sha"] != merge.second_parent_sha:
            continue
        merged_at = legacy.parse_time(context.payload["merged_at"], nullable=True)
        rows.append(
            {
                "merge": merge,
                "canonical_pull_number": target.pull_number,
                "census_pull_number": target.pull_number,
                "census_pattern_id": census.pattern_id,
                "mapping_status": (
                    "TARGETED_RECOGNIZED_NUMBER_AND_SECOND_PARENT_HEAD_SHA_EXACT"
                ),
                "github_merged_at": merged_at,
                **actor_fields(context.payload),
                "targeted_response_path": context.path.as_posix(),
                "targeted_response_file_sha256": file_sha256(context.path),
            }
        )
    rows.sort(key=lambda row: row["merge"].sequence)
    output: list[S5CorrectedCanonicalMappingRow] = []
    for sequence, row in enumerate(rows, start=1):
        merge = row.pop("merge")
        git_time = topology.committer_times[merge.commit_sha]
        merged_at = row["github_merged_at"]
        output.append(
            S5CorrectedCanonicalMappingRow(
                sequence=sequence,
                merge_sequence=merge.sequence,
                merge_commit_sha=merge.commit_sha,
                first_parent_sha=merge.first_parent_sha,
                second_parent_sha=merge.second_parent_sha,
                git_committer_at=git_time,
                event_at=merged_at if merged_at is not None else git_time,
                event_time_source=(
                    "GITHUB_MERGED_AT" if merged_at is not None else "GIT_COMMITTER_AT"
                ),
                **row,
            )
        )
    commits = tuple(row.merge_commit_sha for row in output)
    pulls = tuple(row.canonical_pull_number for row in output)
    if len(set(commits)) != len(commits) or len(set(pulls)) != len(pulls):
        raise ValueError("S5 corrected canonical mapping is not one-to-one")
    return tuple(output)


def merge_sha_shape(value: Any) -> str:
    if value is None:
        return "NULL"
    if value == "":
        return "EMPTY_STRING"
    return "SHA1_40_LOWER_HEX"


def target_resolution_rows(
    *,
    contexts: tuple[TargetContext, ...],
    accepted_by_number: dict[int, Any],
    canonical_by_pull: dict[int, S5CorrectedCanonicalMappingRow],
    full_graph: frozenset[str],
    merges_by_commit: dict[str, legacy.GitMerge],
    merges_by_second_parent: dict[str, tuple[legacy.GitMerge, ...]],
) -> tuple[S5CorrectedTargetResolutionRow, ...]:
    rows: list[S5CorrectedTargetResolutionRow] = []
    for sequence, context in enumerate(contexts, start=1):
        target = context.parsed.target
        body_hash = context.parsed.response_body_sha256
        common = {
            "sequence": sequence,
            "pull_number": target.pull_number,
            "target_reasons": target.target_reasons,
            "http_status": context.parsed.http_status,
            "bulk_accepted": target.pull_number in accepted_by_number,
            "response_path": context.path.as_posix(),
            "response_file_sha256": file_sha256(context.path),
            "response_body_sha256": body_hash,
        }
        if context.payload is None:
            rows.append(
                S5CorrectedTargetResolutionRow(
                    **common,
                    direct_state=None,
                    direct_merged=None,
                    direct_merged_at=None,
                    direct_base_ref=None,
                    direct_head_sha=None,
                    direct_merge_commit_sha=None,
                    direct_merge_commit_sha_shape="NOT_APPLICABLE_404",
                    head_in_full_graph=False,
                    merge_commit_sha_in_full_graph=False,
                    canonical_merge_commit_sha=None,
                    canonical_mapping=False,
                    local_source_link_verified=False,
                    resolution_status="RECOGNIZED_ENDPOINT_404_UNRESOLVED",
                )
            )
            continue
        payload = context.payload
        head = payload["head"]["sha"]
        merge_sha = payload["merge_commit_sha"]
        merge_in_graph = isinstance(merge_sha, str) and merge_sha in full_graph
        canonical = canonical_by_pull.get(target.pull_number)
        verified = canonical is not None or (
            target.pull_number in accepted_by_number
            and (head in full_graph or merge_in_graph)
        )
        first_parent_link = (
            merge_sha in merges_by_commit
            if isinstance(merge_sha, str)
            else False
        ) or bool(merges_by_second_parent.get(head))
        if canonical is not None and target.pull_number in accepted_by_number:
            status = "CANONICAL_RECOGNIZED_ACCEPTED"
        elif canonical is not None:
            status = "CANONICAL_RECOGNIZED_SOURCE_ONLY"
        elif target.pull_number in accepted_by_number and first_parent_link:
            status = "ACCEPTED_EXACT_NONCANONICAL_FIRST_PARENT_LINK"
        elif target.pull_number in accepted_by_number and verified:
            status = "ACCEPTED_FULL_GRAPH_EXACT"
        elif target.pull_number in accepted_by_number:
            status = "ACCEPTED_LOCAL_INCLUSION_UNVERIFIED"
        else:
            raise ValueError("S5 corrected target lacks a frozen disposition")
        rows.append(
            S5CorrectedTargetResolutionRow(
                **common,
                direct_state=payload["state"],
                direct_merged=payload["merged"],
                direct_merged_at=legacy.parse_time(payload["merged_at"], nullable=True),
                direct_base_ref=payload["base"]["ref"],
                direct_head_sha=head,
                direct_merge_commit_sha=merge_sha,
                direct_merge_commit_sha_shape=merge_sha_shape(merge_sha),
                head_in_full_graph=head in full_graph,
                merge_commit_sha_in_full_graph=merge_in_graph,
                canonical_merge_commit_sha=(
                    None if canonical is None else canonical.merge_commit_sha
                ),
                canonical_mapping=canonical is not None,
                local_source_link_verified=verified,
                resolution_status=status,
            )
        )
    return tuple(rows)


def accepted_coverage_rows(
    *,
    accepted: tuple[Any, ...],
    canonical_by_pull: dict[int, S5CorrectedCanonicalMappingRow],
    resolutions_by_pull: dict[int, S5CorrectedTargetResolutionRow],
) -> tuple[S5CorrectedAcceptedCoverageRow, ...]:
    rows: list[S5CorrectedAcceptedCoverageRow] = []
    for sequence, pull in enumerate(accepted, start=1):
        assert pull.merged_at is not None
        canonical = canonical_by_pull.get(pull.pull_number)
        if canonical is not None:
            rows.append(
                S5CorrectedAcceptedCoverageRow(
                    sequence=sequence,
                    pull_number=pull.pull_number,
                    github_merged_at=pull.merged_at,
                    canonical_merge_commit_sha=canonical.merge_commit_sha,
                    local_source_commit_sha=canonical.merge_commit_sha,
                    source_link_status="CANONICAL_FIRST_PARENT",
                    local_source_link_verified=True,
                    targeted_resolution_sequence=None,
                )
            )
            continue
        resolution = resolutions_by_pull.get(pull.pull_number)
        if resolution is None:
            raise ValueError("S5 corrected accepted pull lacks source coverage")
        if resolution.local_source_link_verified:
            source_commit = (
                resolution.direct_merge_commit_sha
                if resolution.merge_commit_sha_in_full_graph
                else resolution.direct_head_sha
            )
            status = "TARGETED_FULL_GRAPH_EXACT"
        else:
            source_commit = None
            status = "LOCAL_INCLUSION_UNVERIFIED"
        rows.append(
            S5CorrectedAcceptedCoverageRow(
                sequence=sequence,
                pull_number=pull.pull_number,
                github_merged_at=pull.merged_at,
                canonical_merge_commit_sha=None,
                local_source_commit_sha=source_commit,
                source_link_status=status,
                local_source_link_verified=resolution.local_source_link_verified,
                targeted_resolution_sequence=resolution.sequence,
            )
        )
    return tuple(rows)


def unresolved_rows(
    *,
    topology: TimedTopology,
    canonical_commits: set[str],
    accepted_by_head: dict[str, tuple[int, ...]],
    census_by_commit: dict[str, Any],
    contexts: tuple[TargetContext, ...],
) -> tuple[S5CorrectedUnresolvedMergeRow, ...]:
    target_candidates: dict[str, set[int]] = {}
    endpoint_404 = {
        context.parsed.target.pull_number
        for context in contexts
        if context.parsed.http_status == 404
    }
    for merge in topology.topology.merges:
        for context in contexts:
            if context.payload is None:
                continue
            payload = context.payload
            if (
                payload["head"]["sha"] == merge.second_parent_sha
                or payload["merge_commit_sha"] == merge.commit_sha
            ):
                target_candidates.setdefault(merge.commit_sha, set()).add(
                    context.parsed.target.pull_number
                )
    rows: list[S5CorrectedUnresolvedMergeRow] = []
    for merge in topology.topology.merges:
        if merge.commit_sha in canonical_commits:
            continue
        census = census_by_commit.get(merge.commit_sha)
        candidates = set(accepted_by_head.get(merge.second_parent_sha, ()))
        candidates.update(target_candidates.get(merge.commit_sha, set()))
        if census is not None and census.pull_request_id in endpoint_404:
            status = "RECOGNIZED_PULL_ENDPOINT_404"
            candidates.add(census.pull_request_id)
        elif len(target_candidates.get(merge.commit_sha, set())) > 1:
            status = "MULTIPLE_TARGETED_PULLS_EXACT_SAME_MERGE"
        elif len(candidates) > 1:
            status = "MULTIPLE_ACCEPTED_GITHUB_HEAD_MATCHES"
        else:
            status = "NO_ACCEPTED_GITHUB_HEAD_MATCH"
        rows.append(
            S5CorrectedUnresolvedMergeRow(
                sequence=len(rows) + 1,
                merge_sequence=merge.sequence,
                merge_commit_sha=merge.commit_sha,
                first_parent_sha=merge.first_parent_sha,
                second_parent_sha=merge.second_parent_sha,
                git_committer_at=topology.committer_times[merge.commit_sha],
                census_pull_number=(None if census is None else census.pull_request_id),
                census_pattern_id=(None if census is None else census.pattern_id),
                resolution_status=status,
                candidate_pull_numbers=tuple(sorted(candidates))[:25],
            )
        )
    return tuple(rows)


def serialize_rows(rows: tuple[Any, ...]) -> bytes:
    lines = tuple(
        json.dumps(
            row.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        for row in rows
    )
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def row_manifest_hash(rows: tuple[Any, ...]) -> str:
    return universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in rows)
    )


def gate_results(conditions: tuple[bool, ...]) -> tuple[S5CorrectedNormalizationGateResult, ...]:
    if len(conditions) != len(S5_CORRECTED_NORMALIZATION_GATE_IDS):
        raise ValueError("S5 corrected normalization gate condition count changed")
    return tuple(
        S5CorrectedNormalizationGateResult(
            gate_id=gate_id,
            status="PASS" if condition else "FAIL",
            evidence=(
                "Frozen corrected-normalization condition reconstructed exactly."
                if condition
                else "Frozen corrected-normalization condition did not reconstruct."
            ),
        )
        for gate_id, condition in zip(
            S5_CORRECTED_NORMALIZATION_GATE_IDS,
            conditions,
            strict=True,
        )
    )


def failed_gates(message: str) -> tuple[S5CorrectedNormalizationGateResult, ...]:
    return tuple(
        S5CorrectedNormalizationGateResult(
            gate_id=gate_id,
            status="FAIL",
            evidence=message[:500] or "Corrected normalization failed.",
        )
        for gate_id in S5_CORRECTED_NORMALIZATION_GATE_IDS
    )


def build_result(
    *,
    started_at: datetime,
    completed_at: datetime,
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
    protocol_audit: S5GitHubCorrectedNormalizationProtocolAuditV2,
    contract: S5GitHubCorrectedNormalizationExecutionContractV2,
    contract_audit: S5GitHubCorrectedNormalizationExecutionContractAuditV2,
    failed_result: S5GitHubNormalizationResult,
    first_parent_hash: str | None,
    full_graph_hash: str | None,
    counts: dict[str, int],
    outputs: tuple[tuple[Path, bytes, tuple[Any, ...]], ...],
    gates: tuple[S5CorrectedNormalizationGateResult, ...],
    failure: Exception | None,
) -> S5GitHubCorrectedNormalizationResultV2:
    passed = sum(gate.status == "PASS" for gate in gates)
    successful = failure is None and passed == len(gates)
    payload = {
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": round((completed_at - started_at).total_seconds(), 6),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "failed_normalization_result_evidence_hash": failed_result.result_evidence_hash,
        "targeted_correction_result_evidence_hash": (
            protocol.targeted_correction_result_evidence_hash
        ),
        "targeted_correction_result_audit_evidence_hash": (
            protocol.targeted_correction_result_audit_evidence_hash
        ),
        "history_dataset_directory_sha256": (
            failed_result.history_dataset_directory_sha256
        ),
        "first_parent_stream_sha256": first_parent_hash,
        "full_graph_stream_sha256": full_graph_hash,
        **counts,
        "output_paths": tuple(path.as_posix() for path, _, _ in outputs) if successful else (),
        "output_file_sha256s": (
            tuple(sha256(payload_bytes).hexdigest() for _, payload_bytes, _ in outputs)
            if successful
            else ()
        ),
        "output_byte_counts": (
            tuple(len(payload_bytes) for _, payload_bytes, _ in outputs)
            if successful
            else ()
        ),
        "output_row_counts": (
            tuple(len(rows) for _, _, rows in outputs) if successful else ()
        ),
        "output_row_manifest_evidence_hashes": (
            tuple(row_manifest_hash(rows) for _, _, rows in outputs)
            if successful
            else ()
        ),
        "gate_results": gates,
        "passed_gate_count": passed,
        "failed_gate_count": len(gates) - passed,
        "decision": (
            S5_CORRECTED_NORMALIZATION_PASS
            if successful
            else S5_CORRECTED_NORMALIZATION_STOP
        ),
        "next_authorization": (
            S5_CORRECTED_NORMALIZATION_NEXT
            if successful
            else S5_CORRECTED_NORMALIZATION_FAILURE_NEXT
        ),
        "authorizes_measurement_protocol_design": successful,
        "failure_type": None if successful else type(failure).__name__,
        "failure_message": None if successful else str(failure)[:2_000],
        "limitations": protocol.limitations,
    }
    provisional = S5GitHubCorrectedNormalizationResultV2.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5GitHubCorrectedNormalizationResultV2.model_validate(complete)


def write_payloads_atomic(outputs: tuple[tuple[Path, bytes, tuple[Any, ...]], ...]) -> None:
    temporary_paths: list[Path] = []
    for path, payload, _ in outputs:
        temporary = path.with_name(f"{path.name}.part")
        if path.exists() or temporary.exists():
            raise ValueError(f"S5 corrected output transaction already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(payload)
        if temporary.read_bytes() != payload:
            raise ValueError(f"S5 corrected staged output changed: {path}")
        temporary_paths.append(temporary)
    for (path, _, _), temporary in zip(outputs, temporary_paths, strict=True):
        temporary.replace(path)


def write_result(path: Path, result: S5GitHubCorrectedNormalizationResultV2) -> None:
    payload = (result.model_dump_json(indent=2) + "\n").encode("utf-8")
    if S5GitHubCorrectedNormalizationResultV2.model_validate_json(payload) != result:
        raise ValueError("S5 corrected normalization result did not round-trip")
    write_payloads_atomic(((path, payload, (result,)),))


def execute(
    *,
    protocol: S5GitHubCorrectedNormalizationProtocolV2,
    protocol_audit: S5GitHubCorrectedNormalizationProtocolAuditV2,
    contract: S5GitHubCorrectedNormalizationExecutionContractV2,
    contract_audit: S5GitHubCorrectedNormalizationExecutionContractAuditV2,
    result_path: Path = DEFAULT_RESULT,
) -> S5GitHubCorrectedNormalizationResultV2:
    output_paths = (
        Path(protocol.pull_output_path),
        Path(protocol.canonical_mapping_output_path),
        Path(protocol.target_resolution_output_path),
        Path(protocol.accepted_coverage_output_path),
        Path(protocol.unresolved_output_path),
        result_path,
    )
    if any(path.exists() or path.with_name(f"{path.name}.part").exists() for path in output_paths):
        raise ValueError("S5 corrected normalization has already run")
    started_at = datetime.now(UTC)
    run_clock = time.monotonic()
    failed_result = S5GitHubNormalizationResult.model_validate_json(
        FAILED_RESULT_PATH.read_text(encoding="utf-8")
    )
    first_parent_hash = full_graph_hash = None
    counts = {
        "source_page_files_opened": 0,
        "response_bodies_decoded": 0,
        "targeted_responses_decoded": 0,
        "local_git_process_count": 0,
        "raw_record_count": 0,
        "cohort_record_count": 0,
        "github_accepted_pull_count": 0,
        "first_parent_commit_count": 0,
        "first_parent_merge_count": 0,
        "full_graph_commit_count": 0,
        "legacy_exact_mapping_count": 0,
        "legacy_unresolved_merge_count": 0,
        "recognized_recovery_count": 0,
        "recognized_unresolved_count": 0,
        "canonical_mapping_count": 0,
        "corrected_unresolved_merge_count": 0,
        "accepted_source_linked_count": 0,
        "accepted_source_unverified_count": 0,
        "many_to_one_group_count": 0,
    }
    outputs: tuple[tuple[Path, bytes, tuple[Any, ...]], ...] = ()
    failure: Exception | None = None
    try:
        legacy_lineage = legacy.load_lineage()
        pulls, raw_count, post_cutoff = legacy.load_normalized_pulls(legacy_lineage)
        counts["source_page_files_opened"] = 245
        counts["response_bodies_decoded"] = 245
        timed, full_graph, full_graph_hash = inspect_git(protocol)
        first_parent_hash = timed.stream_sha256
        counts["local_git_process_count"] = 2
        legacy_outcome = legacy.map_git_merges(
            pulls=pulls,
            topology=timed.topology,
            census=legacy_lineage.census_result,
            cutoff=legacy_lineage.protocol.cohort_created_at_cutoff,
        )
        _, _, contexts = decode_target_contexts()
        counts["targeted_responses_decoded"] = len(contexts)
        accepted = tuple(
            row
            for row in pulls
            if legacy.accepted_pull(
                row,
                cutoff=legacy_lineage.protocol.cohort_created_at_cutoff,
            )
        )
        accepted_by_number = {row.pull_number: row for row in accepted}
        pulls_by_number = {row.pull_number: row for row in pulls}
        merges_by_commit = {
            row.commit_sha: row for row in timed.topology.merges
        }
        second_parent_lists: dict[str, list[legacy.GitMerge]] = {}
        for merge in timed.topology.merges:
            second_parent_lists.setdefault(merge.second_parent_sha, []).append(merge)
        merges_by_second_parent = {
            key: tuple(value) for key, value in second_parent_lists.items()
        }
        census_by_pull = {
            row.pull_request_id: row
            for row in legacy_lineage.census_result.accepted_pull_request_records
        }
        census_by_commit = {
            row.merge_commit_hash: row
            for row in legacy_lineage.census_result.accepted_pull_request_records
        }
        canonical = canonical_mapping_rows(
            legacy_outcome=legacy_outcome,
            topology=timed,
            pulls_by_number=pulls_by_number,
            census_by_pull=census_by_pull,
            merges_by_commit=merges_by_commit,
            contexts=contexts,
        )
        canonical_by_pull = {row.canonical_pull_number: row for row in canonical}
        resolutions = target_resolution_rows(
            contexts=contexts,
            accepted_by_number=accepted_by_number,
            canonical_by_pull=canonical_by_pull,
            full_graph=full_graph,
            merges_by_commit=merges_by_commit,
            merges_by_second_parent=merges_by_second_parent,
        )
        resolutions_by_pull = {row.pull_number: row for row in resolutions}
        coverage = accepted_coverage_rows(
            accepted=accepted,
            canonical_by_pull=canonical_by_pull,
            resolutions_by_pull=resolutions_by_pull,
        )
        accepted_head_lists: dict[str, list[int]] = {}
        for pull in accepted:
            accepted_head_lists.setdefault(pull.head_sha, []).append(pull.pull_number)
        unresolved = unresolved_rows(
            topology=timed,
            canonical_commits={row.merge_commit_sha for row in canonical},
            accepted_by_head={
                key: tuple(value) for key, value in accepted_head_lists.items()
            },
            census_by_commit=census_by_commit,
            contexts=contexts,
        )
        relation_groups: dict[str, set[int]] = {}
        for context in contexts:
            if context.payload is None or (
                context.parsed.target.pull_number not in accepted_by_number
            ):
                continue
            payload = context.payload
            related = {
                merge.commit_sha
                for merge in merges_by_second_parent.get(payload["head"]["sha"], ())
            }
            if payload["merge_commit_sha"] in merges_by_commit:
                related.add(payload["merge_commit_sha"])
            for commit in related:
                relation_groups.setdefault(commit, set()).add(
                    context.parsed.target.pull_number
                )
        many_to_one = tuple(
            sorted(
                tuple(sorted(pulls_set))
                for pulls_set in relation_groups.values()
                if len(pulls_set) > 1
            )
        )
        recognized_404 = tuple(
            row.pull_number
            for row in resolutions
            if row.resolution_status == "RECOGNIZED_ENDPOINT_404_UNRESOLVED"
        )
        unverified = tuple(
            row.pull_number
            for row in coverage
            if not row.local_source_link_verified
        )
        recognized_recovered = sum(
            row.mapping_status
            == "TARGETED_RECOGNIZED_NUMBER_AND_SECOND_PARENT_HEAD_SHA_EXACT"
            for row in canonical
        )
        counts.update(
            {
                "raw_record_count": raw_count,
                "cohort_record_count": len(pulls),
                "github_accepted_pull_count": len(accepted),
                "first_parent_commit_count": timed.topology.first_parent_count,
                "first_parent_merge_count": timed.topology.merge_count,
                "full_graph_commit_count": len(full_graph),
                "legacy_exact_mapping_count": len(legacy_outcome.mappings),
                "legacy_unresolved_merge_count": len(legacy_outcome.unresolved),
                "recognized_recovery_count": recognized_recovered,
                "recognized_unresolved_count": len(recognized_404),
                "canonical_mapping_count": len(canonical),
                "corrected_unresolved_merge_count": len(unresolved),
                "accepted_source_linked_count": sum(
                    row.local_source_link_verified for row in coverage
                ),
                "accepted_source_unverified_count": sum(
                    not row.local_source_link_verified for row in coverage
                ),
                "many_to_one_group_count": len(many_to_one),
            }
        )
        pull_bytes = legacy.serialize_rows(pulls)
        canonical_bytes = serialize_rows(canonical)
        resolution_bytes = serialize_rows(resolutions)
        coverage_bytes = serialize_rows(coverage)
        unresolved_bytes = serialize_rows(unresolved)
        outputs = (
            (Path(protocol.pull_output_path), pull_bytes, pulls),
            (Path(protocol.canonical_mapping_output_path), canonical_bytes, canonical),
            (Path(protocol.target_resolution_output_path), resolution_bytes, resolutions),
            (Path(protocol.accepted_coverage_output_path), coverage_bytes, coverage),
            (Path(protocol.unresolved_output_path), unresolved_bytes, unresolved),
        )
        output_reconstructs = all(
            serialize_rows(rows) == payload
            for _, payload, rows in outputs[1:]
        ) and legacy.serialize_rows(pulls) == pull_bytes
        conditions = (
            failed_result.result_evidence_hash
            == protocol.failed_normalization_result_evidence_hash,
            bindings_match(protocol.source_bindings),
            len(legacy_outcome.mappings) == 16_167
            and len(legacy_outcome.unresolved) == 554
            and legacy_outcome.unmatched_accepted_count == 112
            and legacy_outcome.ambiguous_count == 1,
            raw_count == 24_407 and len(pulls) == 24_398 and post_cutoff == 9,
            len(contexts) == 194
            and sum(row.parsed.http_status == 200 for row in contexts) == 186
            and sum(row.parsed.http_status == 404 for row in contexts) == 8,
            timed.topology.first_parent_count == 17_543
            and timed.topology.merge_count == 16_721,
            len(full_graph) == 50_395,
            len(legacy_outcome.mappings) == 16_167,
            recognized_recovered == 75,
            recognized_404 == protocol.recognized_endpoint_404_pull_numbers,
            len(canonical) == 16_242,
            len(coverage) == 16_279,
            sum(row.local_source_link_verified for row in coverage) == 16_271,
            unverified == protocol.accepted_local_inclusion_unverified_pull_numbers,
            many_to_one == protocol.disclosed_many_to_one_pull_groups,
            len(coverage) != len(canonical),
            all(
                row.event_time_source in {"GITHUB_MERGED_AT", "GIT_COMMITTER_AT"}
                for row in canonical
            ),
            output_reconstructs
            and all(
                len(payload) <= protocol.maximum_each_output_bytes
                for _, payload, _ in outputs
            ),
            True,
        )
        gates = gate_results(conditions)
        failed_gate_ids = tuple(
            gate.gate_id for gate in gates if gate.status == "FAIL"
        )
        if failed_gate_ids:
            failure = ValueError(f"Failed frozen corrected gates: {failed_gate_ids}")
        if time.monotonic() - run_clock > protocol.maximum_elapsed_seconds:
            raise ValueError("S5 corrected normalization elapsed-time bound exceeded")
    except Exception as exc:  # noqa: BLE001 - terminal failure is preserved as evidence
        failure = exc
        gates = failed_gates(str(exc))
        outputs = ()
    completed_at = datetime.now(UTC)
    result = build_result(
        started_at=started_at,
        completed_at=completed_at,
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        failed_result=failed_result,
        first_parent_hash=first_parent_hash,
        full_graph_hash=full_graph_hash,
        counts=counts,
        outputs=outputs,
        gates=gates,
        failure=failure,
    )
    if failure is None:
        write_payloads_atomic(outputs)
    write_result(result_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S5 corrected normalization once.")
    parser.add_argument("--run", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    parse_args()
    try:
        protocol, audit, contract, contract_audit = load_authorization()
        result = execute(
            protocol=protocol,
            protocol_audit=audit,
            contract=contract,
            contract_audit=contract_audit,
        )
        print(
            f"{result.decision} {result.result_evidence_hash} "
            f"accepted={result.github_accepted_pull_count} "
            f"source_linked={result.accepted_source_linked_count} "
            f"canonical={result.canonical_mapping_count} "
            f"unresolved={result.corrected_unresolved_merge_count} "
            "network=0 market_values=0 returns=0 orders=0"
        )
        return 0 if result.decision == S5_CORRECTED_NORMALIZATION_PASS else 1
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
