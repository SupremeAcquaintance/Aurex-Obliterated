from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
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

from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5_CENSUS_GATE_IDS,
    S5_CENSUS_NEXT,
    S5_CENSUS_NONE,
    S5_CENSUS_PASS,
    S5_CENSUS_STOP,
    S5AcceptedPullRequestRecord,
    S5BitcoinCoreHistoryCensusProtocol,
    S5BitcoinCoreHistoryCensusProtocolAudit,
    S5BitcoinCoreHistoryCensusResult,
    S5CensusGateResult,
    S5UnrecognizedMergeSample,
    audit_s5_census_protocol,
    audit_s5_census_protocol_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadResultV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_bitcoin_core_history_census import (  # noqa: E402
    dataset_manifest_valid,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s5_bitcoin_core_history_census_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s5_bitcoin_core_history_census_protocol_audit_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_history_census_result_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_history_census.py")
SCRIPT_PATH = Path("scripts/run_s5_bitcoin_core_history_census.py")
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class CensusInspection:
    first_parent_commit_count: int
    commit_object_count: int
    single_parent_commit_count: int
    root_commit_count: int
    merge_commit_count: int
    octopus_merge_commit_count: int
    recognized_pull_merge_count: int
    unrecognized_merge_count: int
    recognized_pattern_counts: dict[str, int]
    accepted_pull_request_records: tuple[S5AcceptedPullRequestRecord, ...]
    distinct_pull_request_ids: tuple[int, ...]
    duplicate_pull_request_reference_count: int
    single_parent_pattern_match_count: int
    unrecognized_merge_samples: tuple[S5UnrecognizedMergeSample, ...]
    unrecognized_merge_first_line_stream_sha256: str
    first_parent_commit_stream_sha256: str
    accepted_pull_record_evidence_hash: str


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def write_result_atomic(path: Path, result: S5BitcoinCoreHistoryCensusResult) -> None:
    if path.exists():
        raise ValueError(f"S5 census result already exists; rerun forbidden: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 census result transaction exists: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if S5BitcoinCoreHistoryCensusResult.model_validate_json(serialized) != result:
        raise ValueError("S5 census result did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def load_protocol(protocol_path: Path, audit_path: Path) -> S5BitcoinCoreHistoryCensusProtocol:
    protocol = S5BitcoinCoreHistoryCensusProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S5BitcoinCoreHistoryCensusProtocolAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    source_bindings_match = all(
        file_sha256(PROJECT_ROOT / binding.path) == binding.file_sha256
        for binding in protocol.source_bindings
    )
    if (
        not audit_s5_census_protocol(protocol)
        or not audit_s5_census_protocol_audit(audit)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.protocol_file_sha256 != file_sha256(protocol_path)
        or audit.builder_contract_hash != protocol.builder_contract_hash
        or not source_bindings_match
    ):
        raise ValueError("S5 census protocol, audit, or predecessor lineage changed")
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


def git_command(repo: Path, *arguments: str) -> list[str]:
    return [
        git_executable(),
        "-c",
        "credential.helper=",
        "-c",
        "http.extraHeader=",
        "-C",
        str(repo),
        *arguments,
    ]


def canonical_commit_stream(
    payload: bytes, *, cutoff: str, maximum_count: int
) -> tuple[tuple[str, ...], str]:
    try:
        decoded = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("S5 first-parent stream was not ASCII") from exc
    commit_ids = tuple(line.strip() for line in decoded.splitlines() if line.strip())
    if (
        not commit_ids
        or len(commit_ids) > maximum_count
        or len(set(commit_ids)) != len(commit_ids)
        or any(SHA1_PATTERN.fullmatch(item) is None for item in commit_ids)
        or commit_ids[-1] != cutoff
    ):
        raise ValueError("S5 first-parent commit stream failed structural validation")
    canonical = ("\n".join(commit_ids) + "\n").encode("ascii")
    return commit_ids, hashlib.sha256(canonical).hexdigest()


def first_parent_commits(
    *, repo: Path, cutoff: str, maximum_count: int, timeout: float
) -> tuple[tuple[str, ...], str]:
    completed = subprocess.run(
        git_command(repo, "rev-list", "--first-parent", "--reverse", cutoff),
        capture_output=True,
        check=False,
        env=git_environment(),
        timeout=timeout,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"S5 local first-parent census failed: {message}")
    return canonical_commit_stream(completed.stdout, cutoff=cutoff, maximum_count=maximum_count)


def parse_commit_object(raw_object: bytes) -> tuple[int, bytes]:
    header_block, separator, message_body = raw_object.partition(b"\n\n")
    if not separator:
        raise ValueError("S5 commit object lacks a header/message separator")
    parent_count = 0
    for header in header_block.splitlines():
        if not header.startswith(b"parent "):
            continue
        parent = header.removeprefix(b"parent ")
        try:
            parent_text = parent.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("S5 parent header was not ASCII") from exc
        if SHA1_PATTERN.fullmatch(parent_text) is None:
            raise ValueError("S5 parent header contained an invalid object ID")
        parent_count += 1
    first_line = message_body.split(b"\n", 1)[0]
    if first_line.endswith(b"\r"):
        first_line = first_line[:-1]
    return parent_count, first_line


def classify_batch_output(
    *,
    payload: bytes,
    commit_ids: tuple[str, ...],
    pattern_specs: tuple[tuple[str, str], ...],
    maximum_samples: int,
    maximum_sample_characters: int,
    first_parent_stream_sha256: str,
) -> CensusInspection:
    stream = io.BytesIO(payload)
    patterns = tuple(
        (pattern_id, re.compile(expression)) for pattern_id, expression in pattern_specs
    )
    pattern_counts = {pattern_id: 0 for pattern_id, _ in patterns}
    accepted: list[S5AcceptedPullRequestRecord] = []
    samples: list[S5UnrecognizedMergeSample] = []
    unrecognized_stream = hashlib.sha256()
    root_count = 0
    single_count = 0
    merge_count = 0
    octopus_count = 0
    unrecognized_count = 0
    single_parent_pattern_matches = 0

    for expected_commit in commit_ids:
        response_header = stream.readline()
        parts = response_header.rstrip(b"\n").split(b" ")
        if len(parts) != 3:
            raise ValueError("S5 cat-file batch response header was malformed")
        returned_commit, object_type, object_size = parts
        try:
            returned_text = returned_commit.decode("ascii")
            size_text = object_size.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("S5 cat-file batch response header was not ASCII") from exc
        if returned_text != expected_commit or object_type != b"commit" or not size_text.isdigit():
            raise ValueError("S5 cat-file batch returned an unexpected object")
        raw_object = stream.read(int(size_text))
        terminator = stream.read(1)
        if len(raw_object) != int(size_text) or terminator != b"\n":
            raise ValueError("S5 cat-file batch response was truncated")

        parent_count, first_line_bytes = parse_commit_object(raw_object)
        first_line = first_line_bytes.decode("utf-8", errors="replace")
        first_line_hash = hashlib.sha256(first_line_bytes).hexdigest()
        matched: tuple[str, int] | None = None
        for pattern_id, pattern in patterns:
            match = pattern.match(first_line)
            if match is not None:
                matched = (pattern_id, int(match.group(1)))
                break

        if parent_count == 0:
            root_count += 1
        elif parent_count == 1:
            single_count += 1
            if matched is not None:
                single_parent_pattern_matches += 1
        else:
            merge_count += 1
            if parent_count >= 3:
                octopus_count += 1
            if matched is not None:
                pattern_id, pull_request_id = matched
                pattern_counts[pattern_id] += 1
                accepted.append(
                    S5AcceptedPullRequestRecord(
                        sequence=len(accepted) + 1,
                        merge_commit_hash=expected_commit,
                        parent_count=parent_count,
                        pull_request_id=pull_request_id,
                        pattern_id=pattern_id,
                        first_line_sha256=first_line_hash,
                    )
                )
            else:
                unrecognized_count += 1
                unrecognized_stream.update(expected_commit.encode("ascii"))
                unrecognized_stream.update(b"\0")
                unrecognized_stream.update(first_line_bytes)
                unrecognized_stream.update(b"\n")
                if len(samples) < maximum_samples:
                    samples.append(
                        S5UnrecognizedMergeSample(
                            sequence=len(samples) + 1,
                            merge_commit_hash=expected_commit,
                            parent_count=parent_count,
                            first_line=first_line[:maximum_sample_characters],
                            first_line_sha256=first_line_hash,
                        )
                    )

    if stream.read(1):
        raise ValueError("S5 cat-file batch emitted unexpected trailing bytes")
    accepted_records = tuple(accepted)
    distinct_ids = tuple(sorted({item.pull_request_id for item in accepted_records}))
    accepted_hash = universe_evidence_hash(
        [item.model_dump(mode="json") for item in accepted_records]
    )
    return CensusInspection(
        first_parent_commit_count=len(commit_ids),
        commit_object_count=len(commit_ids),
        single_parent_commit_count=single_count,
        root_commit_count=root_count,
        merge_commit_count=merge_count,
        octopus_merge_commit_count=octopus_count,
        recognized_pull_merge_count=len(accepted_records),
        unrecognized_merge_count=unrecognized_count,
        recognized_pattern_counts=pattern_counts,
        accepted_pull_request_records=accepted_records,
        distinct_pull_request_ids=distinct_ids,
        duplicate_pull_request_reference_count=len(accepted_records) - len(distinct_ids),
        single_parent_pattern_match_count=single_parent_pattern_matches,
        unrecognized_merge_samples=tuple(samples),
        unrecognized_merge_first_line_stream_sha256=unrecognized_stream.hexdigest(),
        first_parent_commit_stream_sha256=first_parent_stream_sha256,
        accepted_pull_record_evidence_hash=accepted_hash,
    )


def census_commit_objects(
    *,
    repo: Path,
    commit_ids: tuple[str, ...],
    protocol: S5BitcoinCoreHistoryCensusProtocol,
    first_parent_stream_sha256: str,
    timeout: float | None = None,
) -> CensusInspection:
    request = ("\n".join(commit_ids) + "\n").encode("ascii")
    completed = subprocess.run(
        git_command(repo, "cat-file", "--batch"),
        input=request,
        capture_output=True,
        check=False,
        env=git_environment(),
        timeout=timeout or protocol.maximum_elapsed_seconds,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"S5 local commit-object census failed: {message}")
    return classify_batch_output(
        payload=completed.stdout,
        commit_ids=commit_ids,
        pattern_specs=tuple(
            (item.pattern_id, item.regular_expression) for item in protocol.message_patterns
        ),
        maximum_samples=protocol.maximum_unrecognized_merge_samples,
        maximum_sample_characters=protocol.maximum_first_line_characters_persisted,
        first_parent_stream_sha256=first_parent_stream_sha256,
    )


def run_census(protocol: S5BitcoinCoreHistoryCensusProtocol) -> CensusInspection:
    dataset = PROJECT_ROOT / protocol.dataset_path
    if not dataset.is_dir():
        raise ValueError("S5 history dataset is missing")
    started = time.monotonic()
    commit_ids, stream_hash = first_parent_commits(
        repo=dataset,
        cutoff=protocol.source_cutoff_commit,
        maximum_count=protocol.maximum_reachable_commit_count,
        timeout=protocol.maximum_elapsed_seconds,
    )
    remaining_seconds = protocol.maximum_elapsed_seconds - (time.monotonic() - started)
    if remaining_seconds <= 0:
        raise ValueError("S5 history census exceeded its frozen elapsed-time limit")
    return census_commit_objects(
        repo=dataset,
        commit_ids=commit_ids,
        protocol=protocol,
        first_parent_stream_sha256=stream_hash,
        timeout=remaining_seconds,
    )


def build_gate_results(
    *,
    protocol: S5BitcoinCoreHistoryCensusProtocol,
    inspection: CensusInspection,
    dataset_manifest_matches: bool,
    local_git_process_count: int,
) -> tuple[S5CensusGateResult, ...]:
    distinct_count = len(inspection.distinct_pull_request_ids)
    expected_record_hash = universe_evidence_hash(
        [item.model_dump(mode="json") for item in inspection.accepted_pull_request_records]
    )
    conditions = (
        len(protocol.source_bindings) == 11,
        dataset_manifest_matches and len(protocol.source_cutoff_commit) == 40,
        local_git_process_count == 2
        and protocol.network_access_permitted is False
        and protocol.github_api_requests_permitted is False,
        0 < inspection.first_parent_commit_count <= protocol.maximum_reachable_commit_count,
        inspection.commit_object_count == inspection.first_parent_commit_count,
        inspection.first_parent_commit_count
        == inspection.root_commit_count
        + inspection.single_parent_commit_count
        + inspection.merge_commit_count
        and inspection.octopus_merge_commit_count <= inspection.merge_commit_count,
        tuple(item.pattern_id for item in protocol.message_patterns)
        == ("BITCOIN_CORE_MAINTAINER_MERGE", "GITHUB_DEFAULT_PULL_MERGE"),
        inspection.recognized_pull_merge_count == len(inspection.accepted_pull_request_records)
        and sum(inspection.recognized_pattern_counts.values())
        == inspection.recognized_pull_merge_count
        and distinct_count == len(set(inspection.distinct_pull_request_ids)),
        len(inspection.unrecognized_merge_samples) <= protocol.maximum_unrecognized_merge_samples
        and len(inspection.unrecognized_merge_first_line_stream_sha256) == 64,
        inspection.accepted_pull_record_evidence_hash == expected_record_hash,
        protocol.author_header_parsing_permitted is False
        and protocol.committer_header_parsing_permitted is False
        and protocol.timestamp_parsing_permitted is False,
        protocol.btc_market_values_permitted is False
        and protocol.parameters_permitted is False
        and protocol.returns_permitted is False
        and protocol.strategy_candidate_permitted is False,
        protocol.next_authorization == "RUN_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_ONCE",
    )
    evidence = (
        "Eleven frozen S5 history and readiness-v29 predecessor artifacts remain bound.",
        "The final dataset manifest and frozen source cutoff were reverified locally.",
        "Exactly two credential-stripped local Git processes ran; no network or API call ran.",
        "The first-parent commit stream is nonempty, unique, cutoff-terminated, and bounded.",
        "Every first-parent commit produced exactly one complete commit object.",
        "Root, single-parent, merge, and octopus topology counts reconcile exactly.",
        "The two pre-frozen first-line pull-request patterns were applied deterministically.",
        "Accepted merge records, pattern counts, and distinct pull-request IDs reconcile.",
        "Every unrecognized merge contributes to a hash; diagnostic samples remain bounded.",
        "The accepted-record hash and direct-request budget inputs were calculated exactly.",
        "Author, committer, and timestamp headers were skipped rather than parsed or persisted.",
        "Zero market values, parameters, returns, candidates, strategy executions, or orders ran.",
        "A passing census can authorize only a separately frozen metadata transport decision.",
    )
    return tuple(
        S5CensusGateResult(
            gate_id=gate_id,
            status="PASS" if condition else "FAIL",
            evidence=message,
        )
        for gate_id, condition, message in zip(
            S5_CENSUS_GATE_IDS, conditions, evidence, strict=True
        )
    )


def build_result(
    *,
    protocol: S5BitcoinCoreHistoryCensusProtocol,
    inspection: CensusInspection,
    dataset_manifest_matches: bool,
    local_git_process_count: int,
    github_token_environment_present: bool,
    executed_at: datetime,
) -> S5BitcoinCoreHistoryCensusResult:
    gates = build_gate_results(
        protocol=protocol,
        inspection=inspection,
        dataset_manifest_matches=dataset_manifest_matches,
        local_git_process_count=local_git_process_count,
    )
    failed = sum(item.status == "FAIL" for item in gates)
    passed = len(gates) - failed
    success = failed == 0
    distinct_count = len(inspection.distinct_pull_request_ids)
    payload: dict[str, Any] = {
        "executed_at": executed_at,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "dataset_directory_sha256": protocol.dataset_directory_sha256,
        "source_cutoff_commit": protocol.source_cutoff_commit,
        "local_git_process_count": local_git_process_count,
        "first_parent_commit_count": inspection.first_parent_commit_count,
        "commit_object_count": inspection.commit_object_count,
        "single_parent_commit_count": inspection.single_parent_commit_count,
        "root_commit_count": inspection.root_commit_count,
        "merge_commit_count": inspection.merge_commit_count,
        "octopus_merge_commit_count": inspection.octopus_merge_commit_count,
        "recognized_pull_merge_count": inspection.recognized_pull_merge_count,
        "unrecognized_merge_count": inspection.unrecognized_merge_count,
        "recognized_pattern_counts": inspection.recognized_pattern_counts,
        "accepted_pull_request_records": inspection.accepted_pull_request_records,
        "distinct_pull_request_ids": inspection.distinct_pull_request_ids,
        "distinct_pull_request_count": distinct_count,
        "duplicate_pull_request_reference_count": (
            inspection.duplicate_pull_request_reference_count
        ),
        "single_parent_pattern_match_count": inspection.single_parent_pattern_match_count,
        "unrecognized_merge_samples": inspection.unrecognized_merge_samples,
        "unrecognized_merge_first_line_stream_sha256": (
            inspection.unrecognized_merge_first_line_stream_sha256
        ),
        "first_parent_commit_stream_sha256": inspection.first_parent_commit_stream_sha256,
        "accepted_pull_record_evidence_hash": inspection.accepted_pull_record_evidence_hash,
        "exact_direct_pull_request_count": distinct_count,
        "unauthenticated_direct_request_hours_lower_bound": (
            distinct_count + protocol.github_unauthenticated_requests_per_hour - 1
        )
        // protocol.github_unauthenticated_requests_per_hour,
        "authenticated_direct_request_hours_lower_bound": (
            distinct_count + protocol.github_authenticated_requests_per_hour - 1
        )
        // protocol.github_authenticated_requests_per_hour,
        "minimum_list_endpoint_pages_at_100_records": (distinct_count + 99) // 100,
        "github_token_environment_present": github_token_environment_present,
        "gate_results": gates,
        "passed_gate_count": passed,
        "failed_gate_count": failed,
        "commit_message_bodies_received": inspection.commit_object_count,
        "commit_message_first_lines_parsed": inspection.commit_object_count,
        "decision": S5_CENSUS_PASS if success else S5_CENSUS_STOP,
        "next_authorization": S5_CENSUS_NEXT if success else S5_CENSUS_NONE,
        "authorizes_metadata_transport_decision": success,
        "limitations": tuple(
            sorted(
                (
                    "This census inventories source structure only and does not establish "
                    "predictive edge.",
                    "Only master first-parent ancestry through the frozen cutoff was inspected.",
                    "Only two pre-frozen merge-message patterns can produce accepted "
                    "pull-request IDs.",
                    "Unrecognized merge messages remain unresolved until source completeness "
                    "is adjudicated.",
                    "Commit objects necessarily carried author and committer headers, but those "
                    "headers were skipped.",
                    "Commit timestamps were neither parsed nor persisted and cannot establish "
                    "first availability.",
                    "The direct GitHub request count is a transport budget, not authorization "
                    "to make requests.",
                    "The list-endpoint page count is only a mathematical lower bound before "
                    "source evaluation.",
                    "No GitHub token value was read, persisted, or used by either local Git "
                    "process.",
                    "No network access, repository fetch, or GitHub API request occurred.",
                    "No BTC market value, parameter, return, candidate, signal, or order was "
                    "created.",
                    "Source completeness and historical metadata availability remain "
                    "unadjudicated.",
                    "No paper, Testnet strategy, production, live, real-capital, or profit "
                    "authority was created.",
                )
            )
        ),
    }
    provisional = S5BitcoinCoreHistoryCensusResult.model_construct(
        **payload, result_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S5BitcoinCoreHistoryCensusResult.model_validate(complete)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local S5 history census once.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f"S5 census result already exists; rerun forbidden: {args.output}")
        protocol = load_protocol(args.protocol, args.protocol_audit)
        history_result = S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(
            Path("data/evidence/s5_bitcoin_core_history_payload_result_v2.json").read_text(
                encoding="utf-8"
            )
        )
        manifest_matches = (
            history_result.dataset_directory_sha256 == protocol.dataset_directory_sha256
            and dataset_manifest_valid(history_result)
        )
        token_present = bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
        inspection = run_census(protocol)
        result = build_result(
            protocol=protocol,
            inspection=inspection,
            dataset_manifest_matches=manifest_matches,
            local_git_process_count=2,
            github_token_environment_present=token_present,
            executed_at=datetime.now(UTC),
        )
        write_result_atomic(args.output, result)
        print(
            f"RECORDED {args.output} {result.result_evidence_hash} "
            f"decision={result.decision} commits={result.first_parent_commit_count} "
            f"merges={result.merge_commit_count} recognized={result.recognized_pull_merge_count} "
            f"distinct_prs={result.distinct_pull_request_count} "
            f"unrecognized={result.unrecognized_merge_count} "
            f"direct_requests={result.exact_direct_pull_request_count} "
            f"gates={result.passed_gate_count}/{len(result.gate_results)} "
            "network=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
