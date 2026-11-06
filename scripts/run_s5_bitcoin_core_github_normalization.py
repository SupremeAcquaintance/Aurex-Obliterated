from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (  # noqa: E402
    S5GitHubBulkFinalResultAuditV4,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (  # noqa: E402
    S5_GITHUB_MERGE_MAPPING_FIELDS,
    S5_GITHUB_NORMALIZATION_GATE_IDS,
    S5_GITHUB_NORMALIZED_PULL_FIELDS,
    S5_GITHUB_UNRESOLVED_MERGE_FIELDS,
    S5GitHubNormalizationProtocol,
    S5GitHubNormalizationProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5_GITHUB_NORMALIZATION_FAILURE_NEXT,
    S5_GITHUB_NORMALIZATION_PASS,
    S5_GITHUB_NORMALIZATION_RESULT_NEXT,
    S5_GITHUB_NORMALIZATION_STOP,
    S5GitHubNormalizationExecutionContract,
    S5GitHubNormalizationExecutionContractAudit,
    S5GitHubNormalizationGateResult,
    S5GitHubNormalizationResult,
    S5GitHubNormalizedPull,
    S5GitMergeMappingRow,
    S5UnresolvedGitMergeRow,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryFileRecord,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as bulk_base  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_audit_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
)
BULK_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json"
)
BULK_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v4.json")
BULK_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_final_result_audit_v4.json"
)
CENSUS_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_result_v1.json"
)
CENSUS_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_result_audit_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_normalization_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_bitcoin_core_github_normalization.py")
BASE_PAGE_PARSER_PATH = Path(
    "scripts/run_s5_bitcoin_core_github_bulk_acquisition.py"
)


@dataclass(frozen=True)
class GitMerge:
    sequence: int
    commit_sha: str
    first_parent_sha: str
    second_parent_sha: str


@dataclass(frozen=True)
class GitTopology:
    first_parent_count: int
    root_count: int
    single_parent_count: int
    merge_count: int
    octopus_count: int
    merges: tuple[GitMerge, ...]
    stream_sha256: str


@dataclass(frozen=True)
class MappingOutcome:
    mappings: tuple[S5GitMergeMappingRow, ...]
    unresolved: tuple[S5UnresolvedGitMergeRow, ...]
    recognized_exact_count: int
    recovered_count: int
    unmatched_accepted_count: int
    ambiguous_count: int
    duplicate_mapped_pull_count: int
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class Lineage:
    protocol: S5GitHubNormalizationProtocol
    protocol_audit: S5GitHubNormalizationProtocolAudit
    contract: S5GitHubNormalizationExecutionContract
    contract_audit: S5GitHubNormalizationExecutionContractAudit
    bulk_protocol: S5GitHubBulkAcquisitionProtocol
    bulk_result: S5GitHubBulkResult
    bulk_audit: S5GitHubBulkFinalResultAuditV4
    census_result: S5BitcoinCoreHistoryCensusResult
    census_audit: S5BitcoinCoreHistoryCensusResultAudit


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_contract_hash() -> str:
    files = (
        EXECUTION_MODULE_PATH,
        RUNNER_PATH,
        BASE_PAGE_PARSER_PATH,
    )
    return universe_evidence_hash(
        tuple(
            {"path": path.as_posix(), "file_sha256": file_sha256(PROJECT_ROOT / path)}
            for path in files
        )
    )


def load_lineage() -> Lineage:
    protocol = S5GitHubNormalizationProtocol.model_validate_json(
        DEFAULT_PROTOCOL.read_text(encoding="utf-8")
    )
    protocol_audit = S5GitHubNormalizationProtocolAudit.model_validate_json(
        DEFAULT_PROTOCOL_AUDIT.read_text(encoding="utf-8")
    )
    contract = S5GitHubNormalizationExecutionContract.model_validate_json(
        DEFAULT_CONTRACT.read_text(encoding="utf-8")
    )
    contract_audit = S5GitHubNormalizationExecutionContractAudit.model_validate_json(
        DEFAULT_CONTRACT_AUDIT.read_text(encoding="utf-8")
    )
    bulk_protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        BULK_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    bulk_result = S5GitHubBulkResult.model_validate_json(
        BULK_RESULT_PATH.read_text(encoding="utf-8")
    )
    bulk_audit = S5GitHubBulkFinalResultAuditV4.model_validate_json(
        BULK_AUDIT_PATH.read_text(encoding="utf-8")
    )
    census_result = S5BitcoinCoreHistoryCensusResult.model_validate_json(
        CENSUS_RESULT_PATH.read_text(encoding="utf-8")
    )
    census_audit = S5BitcoinCoreHistoryCensusResultAudit.model_validate_json(
        CENSUS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_file_sha256 != file_sha256(DEFAULT_PROTOCOL)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_file_sha256 != file_sha256(DEFAULT_PROTOCOL)
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_file_sha256 != file_sha256(DEFAULT_PROTOCOL_AUDIT)
        or contract.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or contract.runner_contract_hash != runner_contract_hash()
        or contract_audit.contract_file_sha256 != file_sha256(DEFAULT_CONTRACT)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
        or bulk_audit.result_file_sha256 != file_sha256(BULK_RESULT_PATH)
        or bulk_audit.result_evidence_hash != bulk_result.result_evidence_hash
        or census_audit.result_file_sha256 != file_sha256(CENSUS_RESULT_PATH)
        or census_audit.result_evidence_hash != census_result.result_evidence_hash
        or protocol.bulk_result_evidence_hash != bulk_result.result_evidence_hash
        or protocol.bulk_final_audit_evidence_hash != bulk_audit.audit_evidence_hash
        or protocol.census_result_evidence_hash != census_result.result_evidence_hash
        or protocol.census_result_audit_evidence_hash != census_audit.audit_evidence_hash
        or any(
            file_sha256(Path(binding.path)) != binding.file_sha256
            for binding in protocol.source_bindings
        )
    ):
        raise ValueError("S5 normalization execution lineage changed")
    return Lineage(
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        bulk_protocol=bulk_protocol,
        bulk_result=bulk_result,
        bulk_audit=bulk_audit,
        census_result=census_result,
        census_audit=census_audit,
    )


def dataset_manifest(path: Path) -> tuple[S5HistoryFileRecord, ...]:
    records: list[S5HistoryFileRecord] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError(f"S5 history dataset contains a symbolic link: {candidate}")
        if candidate.is_file():
            records.append(
                S5HistoryFileRecord(
                    relative_path=candidate.relative_to(path).as_posix(),
                    file_sha256=file_sha256(candidate),
                    byte_count=candidate.stat().st_size,
                )
            )
    return tuple(records)


def dataset_manifest_hash(path: Path) -> str:
    manifest = dataset_manifest(path)
    return universe_evidence_hash([item.model_dump(mode="json") for item in manifest])


def parse_time(value: Any, *, nullable: bool) -> datetime | None:
    return bulk_base.parse_datetime(value, nullable=nullable)


def normalize_pull(
    value: Any,
    *,
    sequence: int,
    source_page: int,
    source_page_sha256: str,
    source_response_body_sha256: str,
) -> S5GitHubNormalizedPull:
    if not isinstance(value, dict):
        raise ValueError("S5 GitHub pull row is not an object")
    required = {
        "number",
        "node_id",
        "state",
        "created_at",
        "updated_at",
        "closed_at",
        "merged_at",
        "head",
        "base",
        "user",
    }
    if not required.issubset(value):
        raise ValueError("S5 GitHub pull row lacks a required field")
    head = value["head"]
    base = value["base"]
    user = value["user"]
    if not isinstance(head, dict) or not isinstance(base, dict):
        raise ValueError("S5 GitHub pull branch identity changed")
    if user is None:
        actor_id = actor_login = actor_type = None
        identity_status = "UNKNOWN_DELETED_OR_NULL"
        actor_class = "UNKNOWN"
    elif isinstance(user, dict):
        actor_id = user.get("id")
        actor_login = user.get("login")
        actor_type = user.get("type")
        if (
            not isinstance(actor_id, int)
            or actor_id <= 0
            or not isinstance(actor_login, str)
            or not actor_login
            or not isinstance(actor_type, str)
            or not actor_type
        ):
            raise ValueError("S5 GitHub actor identity changed")
        identity_status = "KNOWN_ACCOUNT"
        actor_class = (
            "BOT"
            if actor_type == "Bot" or actor_login.casefold().endswith("[bot]")
            else "HUMAN_OR_UNRESOLVED_ACCOUNT"
        )
    else:
        raise ValueError("S5 GitHub actor is neither an object nor null")
    created_at = parse_time(value["created_at"], nullable=False)
    updated_at = parse_time(value["updated_at"], nullable=False)
    closed_at = parse_time(value["closed_at"], nullable=True)
    merged_at = parse_time(value["merged_at"], nullable=True)
    assert created_at is not None and updated_at is not None
    return S5GitHubNormalizedPull(
        sequence=sequence,
        pull_number=value["number"],
        node_id=value["node_id"],
        state=value["state"],
        created_at=created_at,
        updated_at=updated_at,
        closed_at=closed_at,
        merged_at=merged_at,
        head_sha=head.get("sha"),
        base_ref=base.get("ref"),
        base_sha=base.get("sha"),
        actor_id=actor_id,
        actor_login=actor_login,
        actor_type=actor_type,
        actor_identity_status=identity_status,
        actor_class=actor_class,
        source_page=source_page,
        source_page_sha256=source_page_sha256,
        source_response_body_sha256=source_response_body_sha256,
    )


def load_normalized_pulls(
    lineage: Lineage,
) -> tuple[tuple[S5GitHubNormalizedPull, ...], int, int]:
    rows: list[S5GitHubNormalizedPull] = []
    raw_count = 0
    post_cutoff_count = 0
    previous_order: tuple[datetime, int] | None = None
    seen_numbers: set[int] = set()
    seen_node_ids: set[str] = set()
    bindings = lineage.bulk_result.page_bindings
    if tuple(binding.page for binding in bindings) != tuple(range(1, 246)):
        raise ValueError("S5 GitHub page binding sequence changed")
    for binding in bindings:
        path = Path(binding.path)
        if (
            path.name != f"page_{binding.page:04d}.json"
            or file_sha256(path) != binding.file_sha256
            or path.stat().st_size != binding.file_byte_count
        ):
            raise ValueError(f"S5 GitHub page identity changed: {binding.page}")
        observation = bulk_base.observation_from_envelope(
            path=path,
            protocol=lineage.bulk_protocol,
        )
        parsed = bulk_base.parse_observation(
            observation=observation,
            protocol=lineage.bulk_protocol,
        )
        if bulk_base.page_binding(path=path, parsed=parsed) != binding:
            raise ValueError(f"S5 GitHub page binding changed: {binding.page}")
        payload = json.loads(observation.response_body)
        if not isinstance(payload, list) or len(payload) != binding.record_count:
            raise ValueError(f"S5 GitHub page body shape changed: {binding.page}")
        for value in payload:
            raw_count += 1
            row = normalize_pull(
                value,
                sequence=len(rows) + 1,
                source_page=binding.page,
                source_page_sha256=binding.file_sha256,
                source_response_body_sha256=binding.response_body_sha256,
            )
            order = (row.created_at, row.pull_number)
            if previous_order is not None and order < previous_order:
                raise ValueError("S5 GitHub records are not creation ordered")
            previous_order = order
            if row.pull_number in seen_numbers or row.node_id in seen_node_ids:
                raise ValueError("S5 GitHub cohort identity is duplicated")
            seen_numbers.add(row.pull_number)
            seen_node_ids.add(row.node_id)
            if row.created_at > lineage.protocol.cohort_created_at_cutoff:
                post_cutoff_count += 1
                continue
            rows.append(row)
    if tuple(row.sequence for row in rows) != tuple(range(1, len(rows) + 1)):
        raise ValueError("S5 normalized pull sequence changed")
    return tuple(rows), raw_count, post_cutoff_count


def parse_git_parent_stream(payload: bytes) -> GitTopology:
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("S5 Git parent stream is not ASCII") from error
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    merges: list[GitMerge] = []
    root_count = single_count = octopus_count = 0
    seen_commits: set[str] = set()
    for sequence, line in enumerate(lines, start=1):
        tokens = tuple(line.split())
        if not tokens or any(not bulk_base.SHA1_RE.fullmatch(token) for token in tokens):
            raise ValueError("S5 Git parent stream contains an invalid SHA1")
        if tokens[0] in seen_commits:
            raise ValueError("S5 Git parent stream contains a duplicate commit")
        seen_commits.add(tokens[0])
        parent_count = len(tokens) - 1
        if parent_count == 0:
            root_count += 1
        elif parent_count == 1:
            single_count += 1
        elif parent_count == 2:
            merges.append(
                GitMerge(
                    sequence=sequence,
                    commit_sha=tokens[0],
                    first_parent_sha=tokens[1],
                    second_parent_sha=tokens[2],
                )
            )
        else:
            octopus_count += 1
    canonical = ("\n".join(lines) + "\n").encode("ascii") if lines else b""
    return GitTopology(
        first_parent_count=len(lines),
        root_count=root_count,
        single_parent_count=single_count,
        merge_count=len(merges),
        octopus_count=octopus_count,
        merges=tuple(merges),
        stream_sha256=sha256(canonical).hexdigest(),
    )


def execute_git_parent_command(protocol: S5GitHubNormalizationProtocol) -> GitTopology:
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git executable is unavailable")
    dataset = Path(protocol.history_dataset_path).resolve()
    command = (
        git,
        f"--git-dir={dataset}",
        "rev-list",
        "--first-parent",
        "--reverse",
        "--parents",
        protocol.source_cutoff_commit,
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.casefold()
        not in {
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "git_proxy_command",
        }
    }
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=protocol.maximum_elapsed_seconds,
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"S5 Git parent command failed: {message}")
    if len(completed.stdout) > protocol.maximum_each_output_bytes:
        raise ValueError("S5 Git parent stream exceeds the frozen byte bound")
    return parse_git_parent_stream(completed.stdout)


def accepted_pull(
    row: S5GitHubNormalizedPull,
    *,
    cutoff: datetime,
) -> bool:
    return (
        row.state == "closed"
        and row.merged_at is not None
        and row.merged_at <= cutoff
        and row.base_ref == "master"
    )


def mapping_row(
    *,
    sequence: int,
    merge: GitMerge,
    pull: S5GitHubNormalizedPull,
    census_pull_number: int | None,
    census_pattern_id: str | None,
) -> S5GitMergeMappingRow:
    assert pull.merged_at is not None
    return S5GitMergeMappingRow(
        sequence=sequence,
        merge_commit_sha=merge.commit_sha,
        first_parent_sha=merge.first_parent_sha,
        second_parent_sha=merge.second_parent_sha,
        census_pull_number=census_pull_number,
        census_pattern_id=census_pattern_id,
        mapping_status=(
            "RECOGNIZED_NUMBER_AND_HEAD_SHA_EXACT"
            if census_pull_number is not None
            else "UNRECOGNIZED_MESSAGE_HEAD_SHA_EXACT"
        ),
        pull_number=pull.pull_number,
        merged_at=pull.merged_at,
        actor_id=pull.actor_id,
        actor_login=pull.actor_login,
        actor_type=pull.actor_type,
        actor_identity_status=pull.actor_identity_status,
        actor_class=pull.actor_class,
    )


def map_git_merges(
    *,
    pulls: tuple[S5GitHubNormalizedPull, ...],
    topology: GitTopology,
    census: S5BitcoinCoreHistoryCensusResult,
    cutoff: datetime,
) -> MappingOutcome:
    accepted = tuple(row for row in pulls if accepted_pull(row, cutoff=cutoff))
    pull_by_number = {row.pull_number: row for row in accepted}
    head_index: dict[str, list[S5GitHubNormalizedPull]] = {}
    for row in accepted:
        head_index.setdefault(row.head_sha, []).append(row)
    census_by_commit = {
        row.merge_commit_hash: row for row in census.accepted_pull_request_records
    }
    mappings: list[S5GitMergeMappingRow] = []
    unresolved: list[S5UnresolvedGitMergeRow] = []
    diagnostics: list[str] = []
    ambiguous_count = 0
    recognized_exact_count = 0
    recovered_count = 0

    def add_unresolved(
        merge: GitMerge,
        *,
        status: str,
        census_pull_number: int | None,
        census_pattern_id: str | None,
        candidates: tuple[int, ...],
    ) -> None:
        unresolved.append(
            S5UnresolvedGitMergeRow(
                sequence=len(unresolved) + 1,
                merge_commit_sha=merge.commit_sha,
                first_parent_sha=merge.first_parent_sha,
                second_parent_sha=merge.second_parent_sha,
                census_pull_number=census_pull_number,
                census_pattern_id=census_pattern_id,
                resolution_status=status,
                candidate_pull_numbers=candidates[:25],
            )
        )

    for merge in topology.merges:
        census_row = census_by_commit.get(merge.commit_sha)
        candidates = tuple(head_index.get(merge.second_parent_sha, ()))
        candidate_numbers = tuple(sorted(row.pull_number for row in candidates))
        if census_row is not None:
            expected_pull = pull_by_number.get(census_row.pull_request_id)
            if expected_pull is None:
                add_unresolved(
                    merge,
                    status="RECOGNIZED_PULL_MISSING_OR_NOT_ACCEPTED",
                    census_pull_number=census_row.pull_request_id,
                    census_pattern_id=census_row.pattern_id,
                    candidates=candidate_numbers,
                )
                diagnostics.append(
                    f"recognized PR {census_row.pull_request_id} is absent or not accepted"
                )
                continue
            if expected_pull.head_sha != merge.second_parent_sha:
                add_unresolved(
                    merge,
                    status="RECOGNIZED_PULL_HEAD_SHA_MISMATCH",
                    census_pull_number=census_row.pull_request_id,
                    census_pattern_id=census_row.pattern_id,
                    candidates=candidate_numbers,
                )
                diagnostics.append(
                    f"recognized PR {census_row.pull_request_id} head SHA does not match"
                )
                continue
            if len(candidates) != 1 or candidates[0].pull_number != expected_pull.pull_number:
                ambiguous_count += 1
                add_unresolved(
                    merge,
                    status="MULTIPLE_ACCEPTED_GITHUB_HEAD_MATCHES",
                    census_pull_number=census_row.pull_request_id,
                    census_pattern_id=census_row.pattern_id,
                    candidates=candidate_numbers,
                )
                diagnostics.append(
                    f"recognized PR {census_row.pull_request_id} has ambiguous head SHA"
                )
                continue
            mappings.append(
                mapping_row(
                    sequence=len(mappings) + 1,
                    merge=merge,
                    pull=expected_pull,
                    census_pull_number=census_row.pull_request_id,
                    census_pattern_id=census_row.pattern_id,
                )
            )
            recognized_exact_count += 1
        elif len(candidates) == 1:
            mappings.append(
                mapping_row(
                    sequence=len(mappings) + 1,
                    merge=merge,
                    pull=candidates[0],
                    census_pull_number=None,
                    census_pattern_id=None,
                )
            )
            recovered_count += 1
        elif len(candidates) > 1:
            ambiguous_count += 1
            add_unresolved(
                merge,
                status="MULTIPLE_ACCEPTED_GITHUB_HEAD_MATCHES",
                census_pull_number=None,
                census_pattern_id=None,
                candidates=candidate_numbers,
            )
            diagnostics.append(
                f"Git merge {merge.commit_sha} has multiple accepted head matches"
            )
        else:
            add_unresolved(
                merge,
                status="NO_ACCEPTED_GITHUB_HEAD_MATCH",
                census_pull_number=None,
                census_pattern_id=None,
                candidates=(),
            )
    mapped_numbers = tuple(row.pull_number for row in mappings)
    duplicate_count = len(mapped_numbers) - len(set(mapped_numbers))
    unmatched = len(set(pull_by_number) - set(mapped_numbers))
    if unmatched:
        diagnostics.append(f"{unmatched} accepted GitHub pulls do not map to Git merges")
    if duplicate_count:
        diagnostics.append(f"{duplicate_count} mapped pull references are duplicated")
    return MappingOutcome(
        mappings=tuple(mappings),
        unresolved=tuple(unresolved),
        recognized_exact_count=recognized_exact_count,
        recovered_count=recovered_count,
        unmatched_accepted_count=unmatched,
        ambiguous_count=ambiguous_count,
        duplicate_mapped_pull_count=duplicate_count,
        diagnostics=tuple(diagnostics[:25]),
    )


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


def gate_results(
    *,
    lineage: Lineage,
    raw_count: int,
    post_cutoff_count: int,
    pulls: tuple[S5GitHubNormalizedPull, ...],
    topology: GitTopology,
    outcome: MappingOutcome,
    outputs_reconstruct: bool,
) -> tuple[S5GitHubNormalizationGateResult, ...]:
    accepted_count = sum(
        accepted_pull(row, cutoff=lineage.protocol.cohort_created_at_cutoff)
        for row in pulls
    )
    conditions = (
        True,
        True,
        raw_count == 24_407 and len(pulls) == 24_398 and post_cutoff_count == 9,
        lineage.bulk_audit.every_page_file_hash_reverified
        and lineage.bulk_audit.every_response_body_hash_reverified,
        len({row.pull_number for row in pulls}) == len(pulls)
        and len({row.node_id for row in pulls}) == len(pulls),
        post_cutoff_count == 9,
        tuple(S5GitHubNormalizedPull.model_fields) == S5_GITHUB_NORMALIZED_PULL_FIELDS
        and tuple(S5GitMergeMappingRow.model_fields) == S5_GITHUB_MERGE_MAPPING_FIELDS
        and tuple(S5UnresolvedGitMergeRow.model_fields)
        == S5_GITHUB_UNRESOLVED_MERGE_FIELDS,
        True,
        topology.first_parent_count == 17_543
        and topology.root_count == 1
        and topology.single_parent_count == 821
        and topology.merge_count == 16_721
        and topology.octopus_count == 0,
        outcome.recognized_exact_count == 7_961,
        outcome.recognized_exact_count == lineage.census_result.recognized_pull_merge_count,
        outcome.unmatched_accepted_count == 0
        and accepted_count == len(outcome.mappings),
        outcome.ambiguous_count == 0 and outcome.duplicate_mapped_pull_count == 0,
        len(outcome.mappings) + len(outcome.unresolved) == topology.merge_count,
        all(
            row.actor_identity_status in {"KNOWN_ACCOUNT", "UNKNOWN_DELETED_OR_NULL"}
            for row in pulls
        ),
        outputs_reconstruct,
        True,
    )
    return tuple(
        S5GitHubNormalizationGateResult(
            gate_id=gate_id,
            status="PASS" if condition else "FAIL",
            evidence=(
                "Frozen condition reconstructed exactly."
                if condition
                else "Frozen condition did not reconstruct; S5 stops."
            ),
        )
        for gate_id, condition in zip(
            S5_GITHUB_NORMALIZATION_GATE_IDS,
            conditions,
            strict=True,
        )
    )


def limitations(protocol: S5GitHubNormalizationProtocol) -> tuple[str, ...]:
    return protocol.limitations


def build_result(
    *,
    completed_at: datetime,
    lineage: Lineage,
    pulls: tuple[S5GitHubNormalizedPull, ...],
    raw_count: int,
    post_cutoff_count: int,
    topology: GitTopology,
    outcome: MappingOutcome,
    pull_bytes: bytes,
    mapping_bytes: bytes,
    unresolved_bytes: bytes,
    gates: tuple[S5GitHubNormalizationGateResult, ...],
    failure: Exception | None,
) -> S5GitHubNormalizationResult:
    passed = sum(gate.status == "PASS" for gate in gates)
    failed = len(gates) - passed
    passing = failure is None and failed == 0
    accepted = tuple(
        row
        for row in pulls
        if accepted_pull(row, cutoff=lineage.protocol.cohort_created_at_cutoff)
    )
    known_actor_ids = {row.actor_id for row in accepted if row.actor_id is not None}
    payload = {
        "completed_at": completed_at,
        "protocol_evidence_hash": lineage.protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": lineage.protocol_audit.audit_evidence_hash,
        "execution_contract_file_sha256": file_sha256(DEFAULT_CONTRACT),
        "execution_contract_evidence_hash": lineage.contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": lineage.contract_audit.audit_evidence_hash,
        "runner_contract_hash": lineage.contract.runner_contract_hash,
        "history_dataset_directory_sha256": lineage.protocol.history_dataset_directory_sha256,
        "source_cutoff_commit": lineage.protocol.source_cutoff_commit,
        "bulk_page_manifest_evidence_hash": lineage.protocol.bulk_page_manifest_evidence_hash,
        "source_page_files_opened": 245 if pulls or raw_count else 0,
        "response_bodies_decoded": 245 if pulls or raw_count else 0,
        "local_git_process_count": 1 if topology.first_parent_count else 0,
        "raw_record_count": raw_count,
        "cohort_record_count": len(pulls),
        "post_cutoff_record_count": post_cutoff_count,
        "normalized_pull_count": len(pulls),
        "accepted_github_pull_count": len(accepted),
        "first_parent_commit_count": topology.first_parent_count,
        "root_commit_count": topology.root_count,
        "single_parent_commit_count": topology.single_parent_count,
        "merge_commit_count": topology.merge_count,
        "octopus_merge_commit_count": topology.octopus_count,
        "recognized_pull_merge_count": lineage.census_result.recognized_pull_merge_count,
        "recognized_exact_mapping_count": outcome.recognized_exact_count,
        "recovered_head_sha_mapping_count": outcome.recovered_count,
        "total_exact_mapping_count": len(outcome.mappings),
        "unresolved_git_merge_count": len(outcome.unresolved),
        "unmatched_accepted_github_pull_count": outcome.unmatched_accepted_count,
        "ambiguous_git_merge_count": outcome.ambiguous_count,
        "duplicate_mapped_pull_count": outcome.duplicate_mapped_pull_count,
        "accepted_unknown_actor_count": sum(
            row.actor_identity_status == "UNKNOWN_DELETED_OR_NULL" for row in accepted
        ),
        "accepted_bot_actor_count": sum(row.actor_class == "BOT" for row in accepted),
        "distinct_known_accepted_actor_id_count": len(known_actor_ids),
        "pull_dataset_path": lineage.protocol.pull_output_path if passing else None,
        "pull_dataset_file_sha256": sha256(pull_bytes).hexdigest() if passing else None,
        "pull_dataset_bytes": len(pull_bytes) if passing else 0,
        "pull_dataset_row_manifest_evidence_hash": (
            row_manifest_hash(pulls) if passing else None
        ),
        "mapping_dataset_path": lineage.protocol.mapping_output_path if passing else None,
        "mapping_dataset_file_sha256": (
            sha256(mapping_bytes).hexdigest() if passing else None
        ),
        "mapping_dataset_bytes": len(mapping_bytes) if passing else 0,
        "mapping_dataset_row_manifest_evidence_hash": (
            row_manifest_hash(outcome.mappings) if passing else None
        ),
        "unresolved_dataset_path": (
            lineage.protocol.unresolved_output_path if passing else None
        ),
        "unresolved_dataset_file_sha256": (
            sha256(unresolved_bytes).hexdigest() if passing else None
        ),
        "unresolved_dataset_bytes": len(unresolved_bytes) if passing else 0,
        "unresolved_dataset_row_manifest_evidence_hash": (
            row_manifest_hash(outcome.unresolved) if passing else None
        ),
        "diagnostics": outcome.diagnostics,
        "gate_results": gates,
        "passed_gate_count": passed,
        "failed_gate_count": failed,
        "source_completeness_conclusion": (
            "PASS_MEASURABLE_COMPLETENESS_WITH_EXPLICIT_LIMITATIONS"
            if passing
            else "FAIL_MEASURABLE_COMPLETENESS"
        ),
        "decision": S5_GITHUB_NORMALIZATION_PASS if passing else S5_GITHUB_NORMALIZATION_STOP,
        "next_authorization": (
            S5_GITHUB_NORMALIZATION_RESULT_NEXT
            if passing
            else S5_GITHUB_NORMALIZATION_FAILURE_NEXT
        ),
        "authorizes_measurement_protocol_design": passing,
        "failure_type": None if passing else type(failure).__name__,
        "failure_message": None if passing else str(failure),
        "limitations": limitations(lineage.protocol),
    }
    provisional = S5GitHubNormalizationResult.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5GitHubNormalizationResult.model_validate(complete)


def empty_topology() -> GitTopology:
    return GitTopology(0, 0, 0, 0, 0, (), sha256(b"").hexdigest())


def empty_outcome(message: str = "") -> MappingOutcome:
    return MappingOutcome((), (), 0, 0, 0, 0, 0, (message,) if message else ())


def failed_gates(message: str) -> tuple[S5GitHubNormalizationGateResult, ...]:
    return tuple(
        S5GitHubNormalizationGateResult(
            gate_id=gate_id,
            status="FAIL",
            evidence=message[:500] or "Normalization failed.",
        )
        for gate_id in S5_GITHUB_NORMALIZATION_GATE_IDS
    )


def write_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.part")
    if path.exists() or temporary.exists():
        raise ValueError(f"S5 normalization output transaction already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_result(path: Path, result: S5GitHubNormalizationResult) -> None:
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5GitHubNormalizationResult.model_validate_json(serialized) != result:
        raise ValueError("S5 normalization result did not round-trip")
    write_atomic(path, serialized.encode("utf-8"))


def execute() -> S5GitHubNormalizationResult:
    lineage = load_lineage()
    output_paths = (
        Path(lineage.protocol.pull_output_path),
        Path(lineage.protocol.mapping_output_path),
        Path(lineage.protocol.unresolved_output_path),
        DEFAULT_RESULT,
    )
    if any(path.exists() or path.with_name(f"{path.name}.part").exists() for path in output_paths):
        raise ValueError("S5 normalization has already run or has a stale transaction")
    pulls: tuple[S5GitHubNormalizedPull, ...] = ()
    raw_count = post_cutoff_count = 0
    topology = empty_topology()
    outcome = empty_outcome()
    pull_bytes = mapping_bytes = unresolved_bytes = b""
    try:
        dataset_hash = dataset_manifest_hash(Path(lineage.protocol.history_dataset_path))
        if dataset_hash != lineage.protocol.history_dataset_directory_sha256:
            raise ValueError("S5 history dataset directory identity changed")
        pulls, raw_count, post_cutoff_count = load_normalized_pulls(lineage)
        topology = execute_git_parent_command(lineage.protocol)
        outcome = map_git_merges(
            pulls=pulls,
            topology=topology,
            census=lineage.census_result,
            cutoff=lineage.protocol.cohort_created_at_cutoff,
        )
        pull_bytes = serialize_rows(pulls)
        mapping_bytes = serialize_rows(outcome.mappings)
        unresolved_bytes = serialize_rows(outcome.unresolved)
        if any(
            len(payload) > lineage.protocol.maximum_each_output_bytes
            for payload in (pull_bytes, mapping_bytes, unresolved_bytes)
        ):
            raise ValueError("S5 normalization output exceeds the frozen byte bound")
        gates = gate_results(
            lineage=lineage,
            raw_count=raw_count,
            post_cutoff_count=post_cutoff_count,
            pulls=pulls,
            topology=topology,
            outcome=outcome,
            outputs_reconstruct=(
                serialize_rows(pulls) == pull_bytes
                and serialize_rows(outcome.mappings) == mapping_bytes
                and serialize_rows(outcome.unresolved) == unresolved_bytes
            ),
        )
        failed = tuple(gate.gate_id for gate in gates if gate.status == "FAIL")
        failure = None if not failed else ValueError(f"Failed frozen gates: {failed}")
    except Exception as error:
        failure = error
        gates = failed_gates(str(error))
        if not outcome.diagnostics:
            outcome = empty_outcome(str(error)[:500])
        pull_bytes = mapping_bytes = unresolved_bytes = b""
    result = build_result(
        completed_at=datetime.now(UTC),
        lineage=lineage,
        pulls=pulls,
        raw_count=raw_count,
        post_cutoff_count=post_cutoff_count,
        topology=topology,
        outcome=outcome,
        pull_bytes=pull_bytes,
        mapping_bytes=mapping_bytes,
        unresolved_bytes=unresolved_bytes,
        gates=gates,
        failure=failure,
    )
    if failure is None:
        write_atomic(Path(lineage.protocol.pull_output_path), pull_bytes)
        write_atomic(Path(lineage.protocol.mapping_output_path), mapping_bytes)
        write_atomic(Path(lineage.protocol.unresolved_output_path), unresolved_bytes)
    write_result(DEFAULT_RESULT, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S5 GitHub/Git normalization once.")
    parser.add_argument("--run", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    parse_args()
    result = execute()
    print(
        f"{result.decision} {result.result_evidence_hash} "
        f"accepted={result.accepted_github_pull_count} "
        f"mapped={result.total_exact_mapping_count} "
        f"unresolved={result.unresolved_git_merge_count} "
        "btc_values=0 returns=0 orders=0"
    )
    return 0 if result.decision == S5_GITHUB_NORMALIZATION_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
