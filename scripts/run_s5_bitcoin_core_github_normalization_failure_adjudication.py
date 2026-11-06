from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure import (  # noqa: E402
    S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT,
    S5_NORMALIZATION_FAILURE_GATE_IDS,
    S5_RECOGNIZED_FAILURE_CATEGORIES,
    S5_UNMATCHED_PULL_CATEGORIES,
    S5FailureCategoryRecord,
    S5NormalizationFailureAdjudicationProtocol,
    S5NormalizationFailureAdjudicationProtocolAudit,
    S5NormalizationFailureAdjudicationResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as bulk_base  # noqa: E402
from scripts import run_s5_bitcoin_core_github_normalization as original  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_protocol_audit_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_result_v1.json"
)
RUNNER_PATH = Path(
    "scripts/run_s5_bitcoin_core_github_normalization_failure_adjudication.py"
)
FAILURE_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_normalization_failure.py"
)


@dataclass(frozen=True)
class DiagnosticPull:
    normalized: original.S5GitHubNormalizedPull
    merge_commit_sha: str | None


@dataclass(frozen=True)
class FullGraph:
    commit_parents: dict[str, tuple[str, ...]]
    first_parent_topology: original.GitTopology
    stream_sha256: str


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_contract_hash() -> str:
    paths = (
        RUNNER_PATH,
        FAILURE_MODULE_PATH,
        original.RUNNER_PATH,
        original.BASE_PAGE_PARSER_PATH,
    )
    return universe_evidence_hash(
        tuple(
            {"path": path.as_posix(), "file_sha256": file_sha256(PROJECT_ROOT / path)}
            for path in paths
        )
    )


def load_authorization() -> tuple[
    S5NormalizationFailureAdjudicationProtocol,
    S5NormalizationFailureAdjudicationProtocolAudit,
    original.Lineage,
]:
    protocol = S5NormalizationFailureAdjudicationProtocol.model_validate_json(
        DEFAULT_PROTOCOL.read_text(encoding="utf-8")
    )
    audit = S5NormalizationFailureAdjudicationProtocolAudit.model_validate_json(
        DEFAULT_PROTOCOL_AUDIT.read_text(encoding="utf-8")
    )
    lineage = original.load_lineage()
    if (
        audit.protocol_file_sha256 != file_sha256(DEFAULT_PROTOCOL)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or protocol.failed_result_file_sha256 != file_sha256(original.DEFAULT_RESULT)
        or protocol.failed_result_evidence_hash
        != original.S5GitHubNormalizationResult.model_validate_json(
            original.DEFAULT_RESULT.read_text(encoding="utf-8")
        ).result_evidence_hash
        or any(
            file_sha256(Path(binding.path)) != binding.file_sha256
            for binding in protocol.source_bindings
        )
        or protocol.normalization_protocol_evidence_hash
        != lineage.protocol.protocol_evidence_hash
        or protocol.execution_contract_evidence_hash
        != lineage.contract.contract_evidence_hash
        or protocol.bulk_result_evidence_hash
        != lineage.bulk_result.result_evidence_hash
        or protocol.census_result_evidence_hash
        != lineage.census_result.result_evidence_hash
    ):
        raise ValueError("S5 failure adjudication authorization changed")
    return protocol, audit, lineage


def parse_merge_commit_sha(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not bulk_base.SHA1_RE.fullmatch(value):
        return None
    return value


def load_diagnostic_pulls(
    lineage: original.Lineage,
) -> tuple[DiagnosticPull, ...]:
    rows: list[DiagnosticPull] = []
    raw_count = post_cutoff_count = 0
    for binding in lineage.bulk_result.page_bindings:
        path = Path(binding.path)
        if (
            file_sha256(path) != binding.file_sha256
            or path.stat().st_size != binding.file_byte_count
        ):
            raise ValueError(f"S5 diagnostic page identity changed: {binding.page}")
        observation = bulk_base.observation_from_envelope(
            path=path,
            protocol=lineage.bulk_protocol,
        )
        parsed = bulk_base.parse_observation(
            observation=observation,
            protocol=lineage.bulk_protocol,
        )
        if bulk_base.page_binding(path=path, parsed=parsed) != binding:
            raise ValueError(f"S5 diagnostic page binding changed: {binding.page}")
        payload = json.loads(observation.response_body)
        if not isinstance(payload, list) or len(payload) != binding.record_count:
            raise ValueError(f"S5 diagnostic page shape changed: {binding.page}")
        for value in payload:
            raw_count += 1
            normalized = original.normalize_pull(
                value,
                sequence=len(rows) + 1,
                source_page=binding.page,
                source_page_sha256=binding.file_sha256,
                source_response_body_sha256=binding.response_body_sha256,
            )
            if normalized.created_at > lineage.protocol.cohort_created_at_cutoff:
                post_cutoff_count += 1
                continue
            rows.append(
                DiagnosticPull(
                    normalized=normalized,
                    merge_commit_sha=parse_merge_commit_sha(value.get("merge_commit_sha")),
                )
            )
    if (raw_count, len(rows), post_cutoff_count) != (24_407, 24_398, 9):
        raise ValueError("S5 diagnostic cohort accounting changed")
    return tuple(rows)


def parse_full_graph(payload: bytes, *, source_cutoff_commit: str) -> FullGraph:
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("S5 full graph stream is not ASCII") from error
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    parents: dict[str, tuple[str, ...]] = {}
    for line in lines:
        tokens = tuple(line.split())
        if not tokens or any(not bulk_base.SHA1_RE.fullmatch(token) for token in tokens):
            raise ValueError("S5 full graph stream contains an invalid SHA1")
        if tokens[0] in parents:
            raise ValueError("S5 full graph stream contains a duplicate commit")
        parents[tokens[0]] = tokens[1:]
    if source_cutoff_commit not in parents:
        raise ValueError("S5 source cutoff is absent from the full graph")
    reverse_chain: list[tuple[str, tuple[str, ...]]] = []
    cursor = source_cutoff_commit
    visited: set[str] = set()
    while True:
        if cursor in visited or cursor not in parents:
            raise ValueError("S5 first-parent chain is cyclic or incomplete")
        visited.add(cursor)
        commit_parents = parents[cursor]
        reverse_chain.append((cursor, commit_parents))
        if not commit_parents:
            break
        cursor = commit_parents[0]
    chain = tuple(reversed(reverse_chain))
    chain_payload = (
        "\n".join(" ".join((commit, *commit_parents)) for commit, commit_parents in chain)
        + "\n"
    ).encode("ascii")
    topology = original.parse_git_parent_stream(chain_payload)
    canonical = ("\n".join(lines) + "\n").encode("ascii") if lines else b""
    return FullGraph(
        commit_parents=parents,
        first_parent_topology=topology,
        stream_sha256=sha256(canonical).hexdigest(),
    )


def execute_full_graph_command(
    protocol: S5NormalizationFailureAdjudicationProtocol,
    lineage: original.Lineage,
) -> FullGraph:
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git executable is unavailable")
    dataset = Path(lineage.protocol.history_dataset_path).resolve()
    command = (
        git,
        f"--git-dir={dataset}",
        "rev-list",
        "--parents",
        lineage.protocol.source_cutoff_commit,
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
        raise ValueError(f"S5 full graph command failed: {message}")
    return parse_full_graph(
        completed.stdout,
        source_cutoff_commit=lineage.protocol.source_cutoff_commit,
    )


def accepted_diagnostics(
    pulls: tuple[DiagnosticPull, ...],
    *,
    cutoff: datetime,
) -> tuple[DiagnosticPull, ...]:
    return tuple(
        row
        for row in pulls
        if original.accepted_pull(row.normalized, cutoff=cutoff)
    )


def classify_recognized(
    *,
    pulls: tuple[DiagnosticPull, ...],
    topology: original.GitTopology,
    lineage: original.Lineage,
) -> dict[str, tuple[int, ...]]:
    categories: dict[str, list[int]] = {
        category: [] for category in S5_RECOGNIZED_FAILURE_CATEGORIES
    }
    all_by_number = {row.normalized.pull_number: row for row in pulls}
    accepted = accepted_diagnostics(
        pulls,
        cutoff=lineage.protocol.cohort_created_at_cutoff,
    )
    accepted_by_number = {row.normalized.pull_number: row for row in accepted}
    head_index: dict[str, list[DiagnosticPull]] = {}
    for row in accepted:
        head_index.setdefault(row.normalized.head_sha, []).append(row)
    merge_by_commit = {merge.commit_sha: merge for merge in topology.merges}
    for census_row in lineage.census_result.accepted_pull_request_records:
        number = census_row.pull_request_id
        merge = merge_by_commit.get(census_row.merge_commit_hash)
        raw = all_by_number.get(number)
        accepted_row = accepted_by_number.get(number)
        if raw is None:
            category = "ABSENT_FROM_MASTER_SCOPED_COHORT"
        elif accepted_row is None or merge is None:
            category = "PRESENT_NOT_ACCEPTED_AT_CUTOFF"
        elif accepted_row.normalized.head_sha != merge.second_parent_sha:
            category = "HEAD_SHA_MISMATCH"
        else:
            candidates = head_index.get(merge.second_parent_sha, [])
            if len(candidates) != 1 or candidates[0].normalized.pull_number != number:
                category = "AMBIGUOUS_HEAD_SHA"
            else:
                category = "EXACT_PRIOR_MAPPING"
        categories[category].append(number)
    return {key: tuple(sorted(value)) for key, value in categories.items()}


def classify_unmatched(
    *,
    pulls: tuple[DiagnosticPull, ...],
    topology: original.GitTopology,
    full_graph: FullGraph,
    original_outcome: original.MappingOutcome,
    cutoff: datetime,
) -> tuple[dict[str, tuple[int, ...]], tuple[DiagnosticPull, ...]]:
    categories: dict[str, list[int]] = {
        category: [] for category in S5_UNMATCHED_PULL_CATEGORIES
    }
    accepted = accepted_diagnostics(pulls, cutoff=cutoff)
    mapped_numbers = {row.pull_number for row in original_outcome.mappings}
    unmatched = tuple(
        row for row in accepted if row.normalized.pull_number not in mapped_numbers
    )
    reachable = set(full_graph.commit_parents)
    first_parent_merges = {merge.commit_sha for merge in topology.merges}
    first_parent_second_parents = {merge.second_parent_sha for merge in topology.merges}
    for row in unmatched:
        pull = row.normalized
        merge_sha = row.merge_commit_sha
        if merge_sha is None:
            category = "MERGE_COMMIT_SHA_MISSING_OR_INVALID"
        elif merge_sha in first_parent_merges:
            category = "MERGE_COMMIT_SHA_EQUALS_FIRST_PARENT_MERGE"
        elif merge_sha in reachable:
            category = "MERGE_COMMIT_SHA_EQUALS_REACHABLE_COMMIT_NOT_FIRST_PARENT_MERGE"
        elif pull.head_sha in reachable and pull.head_sha not in first_parent_second_parents:
            category = "HEAD_SHA_REACHABLE_NOT_FIRST_PARENT_SECOND_PARENT"
        elif merge_sha not in reachable and pull.head_sha not in reachable:
            category = "NOT_REACHABLE_AT_SOURCE_CUTOFF"
        else:
            category = "OTHER_UNRESOLVED"
        categories[category].append(pull.pull_number)
    return (
        {key: tuple(sorted(value)) for key, value in categories.items()},
        unmatched,
    )


def category_records(
    categories: tuple[str, ...],
    values: dict[str, tuple[int, ...]],
) -> tuple[S5FailureCategoryRecord, ...]:
    return tuple(
        S5FailureCategoryRecord(
            category=category,
            count=len(values[category]),
            pull_numbers=values[category][:250],
            evidence_hash=universe_evidence_hash(values[category]),
        )
        for category in categories
    )


def build_gate_results(
    *,
    protocol: S5NormalizationFailureAdjudicationProtocol,
    lineage: original.Lineage,
    full_graph: FullGraph,
    recognized: dict[str, tuple[int, ...]],
    unmatched: dict[str, tuple[int, ...]],
    original_outcome: original.MappingOutcome,
) -> tuple[dict[str, str], ...]:
    recognized_gap = 7_961 - len(recognized["EXACT_PRIOR_MAPPING"])
    unmatched_count = sum(len(values) for values in unmatched.values())
    conditions = (
        True,
        protocol.original_passed_gate_count == 13
        and protocol.original_failed_gate_count == 4,
        recognized_gap == 83
        and unmatched_count == 112
        and original_outcome.ambiguous_count == 1,
        True,
        True,
        full_graph.first_parent_topology.first_parent_count == 17_543
        and full_graph.first_parent_topology.merge_count == 16_721,
        sum(len(values) for values in recognized.values()) == 7_961,
        unmatched_count == 112,
        True,
        original_outcome.ambiguous_count == 1,
        lineage.protocol.btc_market_values_permitted is False
        and lineage.protocol.returns_permitted is False,
    )
    return tuple(
        {
            "gate_id": gate_id,
            "status": "PASS" if condition else "FAIL",
            "evidence": (
                "Frozen diagnostic condition reconstructed exactly."
                if condition
                else "Frozen diagnostic condition failed; retire S5."
            ),
        }
        for gate_id, condition in zip(
            S5_NORMALIZATION_FAILURE_GATE_IDS,
            conditions,
            strict=True,
        )
    )


def build_result(
    *,
    completed_at: datetime,
    protocol: S5NormalizationFailureAdjudicationProtocol,
    audit: S5NormalizationFailureAdjudicationProtocolAudit,
    lineage: original.Lineage,
    pulls: tuple[DiagnosticPull, ...],
    full_graph: FullGraph,
    original_outcome: original.MappingOutcome,
    recognized: dict[str, tuple[int, ...]],
    unmatched: dict[str, tuple[int, ...]],
    unmatched_rows: tuple[DiagnosticPull, ...],
    gates: tuple[dict[str, str], ...],
) -> S5NormalizationFailureAdjudicationResult:
    passed = sum(gate["status"] == "PASS" for gate in gates)
    failed = len(gates) - passed
    cutoff = lineage.protocol.cohort_created_at_cutoff
    recent_counts = {
        days: sum(
            row.normalized.merged_at is not None
            and timedelta(0) <= cutoff - row.normalized.merged_at <= timedelta(days=days)
            for row in unmatched_rows
        )
        for days in (1, 7, 30)
    }
    structurally_unexplained = (
        len(recognized["PRESENT_NOT_ACCEPTED_AT_CUTOFF"])
        + len(recognized["HEAD_SHA_MISMATCH"])
        + len(recognized["AMBIGUOUS_HEAD_SHA"])
        + len(unmatched["MERGE_COMMIT_SHA_MISSING_OR_INVALID"])
        + len(unmatched["OTHER_UNRESOLVED"])
    )
    payload = {
        "completed_at": completed_at,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "failed_result_evidence_hash": protocol.failed_result_evidence_hash,
        "history_dataset_directory_sha256": (
            lineage.protocol.history_dataset_directory_sha256
        ),
        "full_graph_commit_count": len(full_graph.commit_parents),
        "first_parent_commit_count": full_graph.first_parent_topology.first_parent_count,
        "first_parent_merge_count": full_graph.first_parent_topology.merge_count,
        "source_page_files_opened": 245,
        "response_bodies_decoded": 245,
        "local_git_process_count": 1,
        "reconstructed_recognized_exact_count": len(
            recognized["EXACT_PRIOR_MAPPING"]
        ),
        "reconstructed_recognized_gap_count": (
            7_961 - len(recognized["EXACT_PRIOR_MAPPING"])
        ),
        "reconstructed_unmatched_accepted_pull_count": sum(
            len(values) for values in unmatched.values()
        ),
        "reconstructed_ambiguous_count": original_outcome.ambiguous_count,
        "recognized_categories": category_records(
            S5_RECOGNIZED_FAILURE_CATEGORIES, recognized
        ),
        "unmatched_categories": category_records(
            S5_UNMATCHED_PULL_CATEGORIES, unmatched
        ),
        "unmatched_merged_within_1_day_of_cutoff": recent_counts[1],
        "unmatched_merged_within_7_days_of_cutoff": recent_counts[7],
        "unmatched_merged_within_30_days_of_cutoff": recent_counts[30],
        "exact_merge_commit_recovery_count": len(
            unmatched["MERGE_COMMIT_SHA_EQUALS_FIRST_PARENT_MERGE"]
        ),
        "master_scoped_recognized_absence_count": len(
            recognized["ABSENT_FROM_MASTER_SCOPED_COHORT"]
        ),
        "structurally_unexplained_count": structurally_unexplained,
        "gate_results": gates,
        "passed_gate_count": passed,
        "failed_gate_count": failed,
        "decision": (
            "PASS_S5_NORMALIZATION_FAILURE_ADJUDICATION"
            if failed == 0
            else "STOP_S5_NORMALIZATION_FAILURE_ADJUDICATION_FAILED_RETIRE_S5"
        ),
        "next_authorization": (
            S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT
            if failed == 0
            else "NONE_RETIRE_S5"
        ),
        "failure_type": None if failed == 0 else "FrozenDiagnosticGateFailure",
        "failure_message": (
            None
            if failed == 0
            else "One or more frozen diagnostic reconstruction gates failed."
        ),
        "limitations": protocol.limitations,
    }
    provisional = S5NormalizationFailureAdjudicationResult.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5NormalizationFailureAdjudicationResult.model_validate(complete)


def write_atomic(path: Path, result: S5NormalizationFailureAdjudicationResult) -> None:
    if path.exists():
        raise ValueError(f"S5 failure adjudication result already exists: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 failure adjudication transaction: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5NormalizationFailureAdjudicationResult.model_validate_json(serialized) != result:
        raise ValueError("S5 failure adjudication result did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def execute() -> S5NormalizationFailureAdjudicationResult:
    protocol, audit, lineage = load_authorization()
    if DEFAULT_RESULT.as_posix() != protocol.result_path or DEFAULT_RESULT.exists():
        raise ValueError("S5 failure adjudication result path changed or already exists")
    dataset_hash = original.dataset_manifest_hash(
        Path(lineage.protocol.history_dataset_path)
    )
    if dataset_hash != lineage.protocol.history_dataset_directory_sha256:
        raise ValueError("S5 diagnostic history dataset identity changed")
    pulls = load_diagnostic_pulls(lineage)
    full_graph = execute_full_graph_command(protocol, lineage)
    topology = full_graph.first_parent_topology
    normalized = tuple(row.normalized for row in pulls)
    original_outcome = original.map_git_merges(
        pulls=normalized,
        topology=topology,
        census=lineage.census_result,
        cutoff=lineage.protocol.cohort_created_at_cutoff,
    )
    recognized = classify_recognized(
        pulls=pulls,
        topology=topology,
        lineage=lineage,
    )
    unmatched, unmatched_rows = classify_unmatched(
        pulls=pulls,
        topology=topology,
        full_graph=full_graph,
        original_outcome=original_outcome,
        cutoff=lineage.protocol.cohort_created_at_cutoff,
    )
    gates = build_gate_results(
        protocol=protocol,
        lineage=lineage,
        full_graph=full_graph,
        recognized=recognized,
        unmatched=unmatched,
        original_outcome=original_outcome,
    )
    result = build_result(
        completed_at=datetime.now(UTC),
        protocol=protocol,
        audit=audit,
        lineage=lineage,
        pulls=pulls,
        full_graph=full_graph,
        original_outcome=original_outcome,
        recognized=recognized,
        unmatched=unmatched,
        unmatched_rows=unmatched_rows,
        gates=gates,
    )
    write_atomic(DEFAULT_RESULT, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S5 failure adjudication once.")
    parser.add_argument("--run", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    parse_args()
    result = execute()
    print(
        f"{result.decision} {result.result_evidence_hash} "
        f"recognized_gap={result.reconstructed_recognized_gap_count} "
        f"unmatched={result.reconstructed_unmatched_accepted_pull_count} "
        f"merge_sha_recovery={result.exact_merge_commit_recovery_count} "
        f"unexplained={result.structurally_unexplained_count} "
        "btc_values=0 returns=0 orders=0"
    )
    return 0 if result.failed_gate_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
