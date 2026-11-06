from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_accepted_development_measurement_execution import (  # noqa: E402
    S5_MEASUREMENT_FAILURE_NEXT,
    S5_MEASUREMENT_PASS,
    S5_MEASUREMENT_RESULT_NEXT,
    S5_MEASUREMENT_STOP,
    S5AcceptedDevelopmentMeasurementExecutionContractAuditV1,
    S5AcceptedDevelopmentMeasurementExecutionContractV1,
    S5AcceptedDevelopmentMeasurementResultV1,
    S5AcceptedDevelopmentMonthlyMeasurementRow,
    S5MeasurementGateResult,
    S5StableReleaseTagRecord,
)
from aurex.backtest_engine.s5_accepted_development_measurement_protocol import (  # noqa: E402
    S5_MEASUREMENT_GATES,
    S5_MEASUREMENT_INPUT_FILE_SHA256S,
    S5_MEASUREMENT_INPUT_ROW_MANIFEST_HASHES,
    S5AcceptedDevelopmentMeasurementProtocolAuditV1,
    S5AcceptedDevelopmentMeasurementProtocolV1,
)
from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization_execution import (  # noqa: E402
    S5CorrectedAcceptedCoverageRow,
    S5CorrectedCanonicalMappingRow,
    S5CorrectedTargetResolutionRow,
    S5CorrectedUnresolvedMergeRow,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5GitHubNormalizedPull,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_accepted_development_measurement_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_accepted_development_measurement_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s5_accepted_development_measurement_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s5_accepted_development_measurement_execution_contract_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_accepted_development_measurement_result_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_accepted_development_measurement_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_accepted_development_measurements.py")


@dataclass
class MonthAccumulator:
    primary_events: list[dict] = field(default_factory=list)
    primary_source_commits: set[str] = field(default_factory=set)
    all_accepted_pull_count: int = 0
    source_unverified_accepted_pull_count: int = 0
    human_actor_ids: set[int] = field(default_factory=set)
    bot_actor_ids: set[int] = field(default_factory=set)
    unknown_actor_event_count: int = 0
    canonical_events: list[dict] = field(default_factory=list)
    canonical_github_time_count: int = 0
    canonical_git_fallback_time_count: int = 0
    component_keys: set[str] = field(default_factory=set)
    unresolved_git_merge_count: int = 0
    release_tags: list[S5StableReleaseTagRecord] = field(default_factory=list)


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
    paths = tuple(sorted((EXECUTION_MODULE_PATH, RUNNER_PATH), key=lambda path: path.as_posix()))
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in implementation_bindings())
    )


def bindings_match(bindings: tuple[S5HistoryBinding, ...]) -> bool:
    return all(
        (PROJECT_ROOT / binding.path).is_file()
        and file_sha256(PROJECT_ROOT / binding.path) == binding.file_sha256
        for binding in bindings
    )


def binding_manifest_hash(bindings: tuple[S5HistoryBinding, ...]) -> str:
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in bindings)
    )


def dataset_manifest_hash(path: Path) -> str:
    records: list[dict] = []
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ValueError("S5 history dataset contains a symbolic link")
        if candidate.is_file():
            records.append(
                {
                    "relative_path": candidate.relative_to(path).as_posix(),
                    "file_sha256": file_sha256(candidate),
                    "byte_count": candidate.stat().st_size,
                }
            )
    return universe_evidence_hash(records)


def load_authorization(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
) -> tuple[
    S5AcceptedDevelopmentMeasurementProtocolV1,
    S5AcceptedDevelopmentMeasurementProtocolAuditV1,
    S5AcceptedDevelopmentMeasurementExecutionContractV1,
    S5AcceptedDevelopmentMeasurementExecutionContractAuditV1,
]:
    protocol = S5AcceptedDevelopmentMeasurementProtocolV1.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S5AcceptedDevelopmentMeasurementProtocolAuditV1.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S5AcceptedDevelopmentMeasurementExecutionContractV1.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = (
        S5AcceptedDevelopmentMeasurementExecutionContractAuditV1.model_validate_json(
            contract_audit_path.read_text(encoding="utf-8")
        )
    )
    if (
        protocol_audit.protocol_file_sha256 != file_sha256(protocol_path)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or contract.runner_contract_hash != runner_contract_hash()
        or contract.implementation_bindings != implementation_bindings()
        or not bindings_match(contract.source_bindings)
        or not bindings_match(contract.implementation_bindings)
        or contract.source_binding_manifest_evidence_hash
        != binding_manifest_hash(contract.source_bindings)
        or contract.implementation_binding_manifest_evidence_hash
        != binding_manifest_hash(contract.implementation_bindings)
        or contract_audit.contract_file_sha256 != file_sha256(contract_path)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_contract_hash != contract.runner_contract_hash
    ):
        raise ValueError("S5 measurement execution authorization changed")
    return protocol, protocol_audit, contract, contract_audit


def load_jsonl[ModelT: BaseModel](path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    rows: list[ModelT] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for sequence, line in enumerate(handle, start=1):
            if not line.endswith("\n") or line.endswith("\r\n") or not line.strip():
                raise ValueError(f"S5 measurement JSONL framing changed: {path}")
            row = model.model_validate(json.loads(line))
            if getattr(row, "sequence", None) != sequence:
                raise ValueError(f"S5 measurement JSONL sequence changed: {path}")
            rows.append(row)
    return tuple(rows)


def row_manifest_hash(rows: tuple[BaseModel, ...]) -> str:
    return universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in rows)
    )


def month_starts(start: date, end_exclusive: date) -> tuple[date, ...]:
    values: list[date] = []
    current = start
    while current < end_exclusive:
        values.append(current)
        current = date(
            current.year + (1 if current.month == 12 else 0),
            1 if current.month == 12 else current.month + 1,
            1,
        )
    return tuple(values)


def next_month(value: date) -> date:
    return date(
        value.year + (1 if value.month == 12 else 0),
        1 if value.month == 12 else value.month + 1,
        1,
    )


def event_month(
    value: datetime,
    *,
    start: date,
    end_exclusive: date,
) -> date | None:
    normalized = value.astimezone(UTC)
    month = date(normalized.year, normalized.month, 1)
    return month if start <= month < end_exclusive else None


def component_key(path: str) -> str:
    if not path or "\\" in path or "\r" in path or "\n" in path:
        raise ValueError("S5 component path is not canonical")
    segments = path.split("/")
    if any(not segment or segment in {".", ".."} for segment in segments):
        raise ValueError("S5 component path segment is invalid")
    if len(segments) == 1:
        return "ROOT"
    if segments[0] != "src":
        return segments[0]
    if len(segments) >= 3:
        return f"src/{segments[1]}"
    return "src/_root"


def parse_first_parent_diff_stream(payload: bytes) -> dict[str, tuple[str, ...]]:
    records: dict[str, tuple[str, ...]] = {}
    for raw_record in payload.split(b"\x1e"):
        record = raw_record.strip(b"\r\n\x00")
        if not record:
            continue
        fields = record.split(b"\x00")
        commit_sha = fields[0].strip(b"\r\n").decode("ascii")
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha) or commit_sha in records:
            raise ValueError("S5 first-parent diff commit identity changed")
        paths: list[str] = []
        for raw_path in fields[1:]:
            candidate = raw_path.strip(b"\r\n")
            if not candidate:
                continue
            path = candidate.decode("utf-8")
            component_key(path)
            paths.append(path)
        if len(paths) != len(set(paths)):
            raise ValueError("S5 first-parent diff path duplication changed")
        records[commit_sha] = tuple(paths)
    return records


def parse_reachable_commits(payload: bytes) -> frozenset[str]:
    commits = tuple(line for line in payload.decode("ascii").splitlines() if line)
    if any(not re.fullmatch(r"[0-9a-f]{40}", item) for item in commits):
        raise ValueError("S5 reachable commit stream changed")
    if len(commits) != len(set(commits)):
        raise ValueError("S5 reachable commit stream contains duplicates")
    return frozenset(commits)


def parse_git_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("S5 Git timestamp lacks a timezone")
    return parsed.astimezone(UTC)


def parse_stable_release_tags(
    payload: bytes,
    *,
    stable_release_tag_regex: str,
    reachable_commits: frozenset[str],
) -> tuple[S5StableReleaseTagRecord, ...]:
    pattern = re.compile(stable_release_tag_regex)
    records: list[S5StableReleaseTagRecord] = []
    seen_refs: set[str] = set()
    for raw_record in payload.split(b"\x1e"):
        record = raw_record.strip(b"\r\n")
        if record.endswith(b"\x00"):
            record = record[:-1]
        if not record:
            continue
        fields = record.split(b"\x00")
        if len(fields) != 7:
            raise ValueError("S5 tag inventory framing changed")
        (
            raw_ref,
            raw_object_type,
            raw_object_sha,
            raw_peeled_sha,
            raw_tagger_at,
            raw_creator_at,
            raw_signature,
        ) = fields
        ref_name = raw_ref.decode("utf-8")
        if ref_name in seen_refs:
            raise ValueError("S5 tag inventory contains duplicate refs")
        seen_refs.add(ref_name)
        if not pattern.fullmatch(ref_name):
            continue
        object_type = raw_object_type.decode("ascii")
        object_sha = raw_object_sha.decode("ascii")
        peeled_sha = raw_peeled_sha.decode("ascii")
        if object_type == "tag":
            if not peeled_sha or not raw_tagger_at:
                raise ValueError("S5 annotated stable tag identity is incomplete")
            event_at = parse_git_datetime(raw_tagger_at.decode("ascii"))
            signature_state = (
                "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED"
                if raw_signature
                else "ANNOTATED_UNSIGNED"
            )
            event_time_source = "ANNOTATED_TAGGER_AT"
        elif object_type == "commit":
            if peeled_sha or not raw_creator_at:
                raise ValueError("S5 lightweight stable tag identity changed")
            peeled_sha = object_sha
            event_at = parse_git_datetime(raw_creator_at.decode("ascii"))
            signature_state = "LIGHTWEIGHT_UNVERIFIED"
            event_time_source = "LIGHTWEIGHT_COMMITTER_AT"
        else:
            raise ValueError("S5 stable tag does not peel to a commit")
        if peeled_sha not in reachable_commits:
            raise ValueError("S5 stable tag commit is unreachable from cutoff")
        records.append(
            S5StableReleaseTagRecord(
                ref_name=ref_name,
                object_type=object_type,
                object_sha=object_sha,
                peeled_commit_sha=peeled_sha,
                event_at=event_at,
                event_time_source=event_time_source,
                signature_state=signature_state,
            )
        )
    return tuple(sorted(records, key=lambda item: item.ref_name))


def git_environment(contract: S5AcceptedDevelopmentMeasurementExecutionContractV1) -> dict:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
        }
    )
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        environment.pop(key, None)
    if contract.git_environment != (
        "GIT_CONFIG_NOSYSTEM=1",
        "GIT_CONFIG_GLOBAL=OS_DEVNULL",
        "GIT_NO_LAZY_FETCH=1",
        "GIT_OPTIONAL_LOCKS=0",
        "LANG=C",
        "LC_ALL=C",
        "TZ=UTC",
    ):
        raise ValueError("S5 Git environment contract changed")
    return environment


def expand_command(
    command: tuple[str, ...],
    protocol: S5AcceptedDevelopmentMeasurementProtocolV1,
) -> tuple[str, ...]:
    replacements = {
        "{history_dataset_path}": str(PROJECT_ROOT / protocol.history_dataset_path),
        "{source_cutoff_commit}": protocol.source_cutoff_commit,
    }
    return tuple(replacements.get(token, token) for token in command)


def run_git(
    command: tuple[str, ...],
    *,
    environment: dict,
    timeout_seconds: int,
    maximum_stdout_bytes: int,
) -> bytes:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        shell=False,
        check=False,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace")[:1_000]
        raise ValueError(f"S5 Git command failed: {message}")
    if len(completed.stdout) > maximum_stdout_bytes:
        raise ValueError("S5 Git command exceeded the stdout ceiling")
    return completed.stdout


def actor_manifest_id(actor_id: int | None) -> str | None:
    return None if actor_id is None else universe_evidence_hash({"actor_id": actor_id})


def build_measurements(
    *,
    protocol: S5AcceptedDevelopmentMeasurementProtocolV1,
    pulls: tuple[S5GitHubNormalizedPull, ...],
    canonical_rows: tuple[S5CorrectedCanonicalMappingRow, ...],
    coverage_rows: tuple[S5CorrectedAcceptedCoverageRow, ...],
    unresolved_rows: tuple[S5CorrectedUnresolvedMergeRow, ...],
    diff_records: dict[str, tuple[str, ...]],
    release_tags: tuple[S5StableReleaseTagRecord, ...],
) -> tuple[tuple[S5AcceptedDevelopmentMonthlyMeasurementRow, ...], dict[str, int]]:
    months = month_starts(
        protocol.measurement_period_start_month,
        protocol.measurement_period_end_exclusive,
    )
    accumulators = {month: MonthAccumulator() for month in months}
    pulls_by_number = {row.pull_number: row for row in pulls}
    if len(pulls_by_number) != len(pulls):
        raise ValueError("S5 normalized pull identity duplication changed")
    excluded = defaultdict(int)

    for coverage in coverage_rows:
        pull = pulls_by_number.get(coverage.pull_number)
        if pull is None or pull.merged_at != coverage.github_merged_at:
            raise ValueError("S5 accepted coverage pull join changed")
        month = event_month(
            coverage.github_merged_at,
            start=protocol.measurement_period_start_month,
            end_exclusive=protocol.measurement_period_end_exclusive,
        )
        if month is None:
            excluded["all_accepted"] += 1
            if coverage.local_source_link_verified:
                excluded["primary"] += 1
            continue
        accumulator = accumulators[month]
        accumulator.all_accepted_pull_count += 1
        if not coverage.local_source_link_verified:
            accumulator.source_unverified_accepted_pull_count += 1
            continue
        if coverage.local_source_commit_sha is None:
            raise ValueError("S5 verified accepted event lacks a source commit")
        accumulator.primary_source_commits.add(coverage.local_source_commit_sha)
        accumulator.primary_events.append(
            {
                "pull_number": coverage.pull_number,
                "github_merged_at": coverage.github_merged_at.isoformat(),
                "local_source_commit_sha": coverage.local_source_commit_sha,
                "actor_manifest_id": actor_manifest_id(pull.actor_id),
                "actor_class": pull.actor_class,
                "actor_identity_status": pull.actor_identity_status,
            }
        )
        if pull.actor_identity_status == "UNKNOWN_DELETED_OR_NULL":
            accumulator.unknown_actor_event_count += 1
        elif pull.actor_id is None:
            raise ValueError("S5 known accepted actor lacks an account ID")
        elif pull.actor_class == "BOT":
            accumulator.bot_actor_ids.add(pull.actor_id)
        elif pull.actor_class == "HUMAN_OR_UNRESOLVED_ACCOUNT":
            accumulator.human_actor_ids.add(pull.actor_id)
        else:
            raise ValueError("S5 known accepted actor class changed")

    if len(diff_records) != 17_543:
        raise ValueError("S5 first-parent diff record count changed")
    for canonical in canonical_rows:
        paths = diff_records.get(canonical.merge_commit_sha)
        if paths is None:
            raise ValueError("S5 canonical merge is absent from the diff stream")
        month = event_month(
            canonical.event_at,
            start=protocol.measurement_period_start_month,
            end_exclusive=protocol.measurement_period_end_exclusive,
        )
        if month is None:
            excluded["canonical"] += 1
            continue
        accumulator = accumulators[month]
        accumulator.canonical_events.append(
            {
                "merge_commit_sha": canonical.merge_commit_sha,
                "canonical_pull_number": canonical.canonical_pull_number,
                "event_at": canonical.event_at.isoformat(),
                "event_time_source": canonical.event_time_source,
            }
        )
        if canonical.event_time_source == "GITHUB_MERGED_AT":
            accumulator.canonical_github_time_count += 1
        else:
            accumulator.canonical_git_fallback_time_count += 1
        accumulator.component_keys.update(component_key(path) for path in paths)

    for unresolved in unresolved_rows:
        month = event_month(
            unresolved.git_committer_at,
            start=protocol.measurement_period_start_month,
            end_exclusive=protocol.measurement_period_end_exclusive,
        )
        if month is None:
            excluded["unresolved"] += 1
        else:
            accumulators[month].unresolved_git_merge_count += 1

    for release in release_tags:
        month = event_month(
            release.event_at,
            start=protocol.measurement_period_start_month,
            end_exclusive=protocol.measurement_period_end_exclusive,
        )
        if month is not None:
            accumulators[month].release_tags.append(release)

    rows: list[S5AcceptedDevelopmentMonthlyMeasurementRow] = []
    for sequence, month in enumerate(months, start=1):
        accumulator = accumulators[month]
        primary_events = tuple(
            sorted(accumulator.primary_events, key=lambda item: item["pull_number"])
        )
        canonical_events = tuple(
            sorted(
                accumulator.canonical_events,
                key=lambda item: item["merge_commit_sha"],
            )
        )
        component_keys = tuple(sorted(accumulator.component_keys))
        release_manifest = tuple(
            item.model_dump(mode="json")
            for item in sorted(accumulator.release_tags, key=lambda item: item.ref_name)
        )
        primary_count = len(primary_events)
        rows.append(
            S5AcceptedDevelopmentMonthlyMeasurementRow(
                sequence=sequence,
                month_start=month,
                month_end_exclusive=next_month(month),
                measurement_available_at=datetime.combine(
                    next_month(month) + timedelta(days=7),
                    datetime.min.time(),
                    tzinfo=UTC,
                ),
                primary_source_verified_accepted_pull_count=primary_count,
                primary_distinct_local_source_commit_count=len(
                    accumulator.primary_source_commits
                ),
                primary_many_to_one_excess_count=(
                    primary_count - len(accumulator.primary_source_commits)
                ),
                all_accepted_pull_count=accumulator.all_accepted_pull_count,
                source_unverified_accepted_pull_count=(
                    accumulator.source_unverified_accepted_pull_count
                ),
                canonical_integration_count=len(canonical_events),
                canonical_github_time_count=accumulator.canonical_github_time_count,
                canonical_git_fallback_time_count=(
                    accumulator.canonical_git_fallback_time_count
                ),
                known_human_or_unresolved_actor_count=len(accumulator.human_actor_ids),
                unknown_actor_event_count=accumulator.unknown_actor_event_count,
                human_contributor_lower_bound=len(accumulator.human_actor_ids),
                human_contributor_upper_bound=(
                    len(accumulator.human_actor_ids)
                    + accumulator.unknown_actor_event_count
                ),
                known_bot_actor_count=len(accumulator.bot_actor_ids),
                canonical_component_key_count=len(component_keys),
                unresolved_git_merge_count=accumulator.unresolved_git_merge_count,
                stable_release_tag_count=len(release_manifest),
                signed_annotated_stable_release_tag_count=sum(
                    item.signature_state
                    == "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED"
                    for item in accumulator.release_tags
                ),
                primary_event_manifest_evidence_hash=universe_evidence_hash(
                    primary_events
                ),
                canonical_event_manifest_evidence_hash=universe_evidence_hash(
                    canonical_events
                ),
                component_key_manifest_evidence_hash=universe_evidence_hash(
                    component_keys
                ),
                release_tag_manifest_evidence_hash=universe_evidence_hash(
                    release_manifest
                ),
                source_normalization_result_evidence_hash=(
                    protocol.corrected_normalization_result_evidence_hash
                ),
            )
        )
    return tuple(rows), dict(excluded)


def serialize_rows(rows: tuple[S5AcceptedDevelopmentMonthlyMeasurementRow, ...]) -> bytes:
    return "".join(
        json.dumps(
            row.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
        for row in rows
    ).encode("utf-8")


def gate_results(*, passed: bool, evidence: str) -> tuple[S5MeasurementGateResult, ...]:
    return tuple(
        S5MeasurementGateResult(
            gate_id=gate_id,
            status="PASS" if passed else "FAIL",
            evidence=evidence,
        )
        for gate_id in S5_MEASUREMENT_GATES
    )


def result_limitations() -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                "All emitted historical measurements are outcome-aware and nonqualifying.",
                "Accepted development activity can reflect workflow changes rather than demand.",
                "Component breadth measures touched path groups, not code quality or impact.",
                "GitHub historical metadata is a current snapshot, not a revision-time archive.",
                "No market value, return, threshold, strategy rule, or signal was created.",
                "Release signature presence was recorded but not cryptographically verified.",
                "Review continuity remains unavailable because review events were not acquired.",
                "The 479 unresolved merges remain an explicit sensitivity limitation.",
                "The eight source-unverified accepted pulls remain sensitivity-only.",
                "Trading authority and real net profit remain zero.",
            )
        )
    )


def write_staged(path: Path, payload: bytes) -> Path:
    staged = Path(f"{path}.part")
    if path.exists() or staged.exists():
        raise ValueError(f"S5 measurement output or partial already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(payload)
    return staged


def build_result(
    *,
    protocol: S5AcceptedDevelopmentMeasurementProtocolV1,
    protocol_audit: S5AcceptedDevelopmentMeasurementProtocolAuditV1,
    contract: S5AcceptedDevelopmentMeasurementExecutionContractV1,
    contract_audit: S5AcceptedDevelopmentMeasurementExecutionContractAuditV1,
    started_at: datetime,
    completed_at: datetime,
    git_process_count: int,
    git_hashes: tuple[str | None, str | None, str | None],
    reachable_commit_count: int | None,
    stable_release_count: int | None,
    counts: dict[str, int] | None,
    output_path: Path | None,
    output_payload: bytes | None,
    rows: tuple[S5AcceptedDevelopmentMonthlyMeasurementRow, ...],
    failure: Exception | None,
) -> S5AcceptedDevelopmentMeasurementResultV1:
    passed = failure is None
    output_manifest = row_manifest_hash(rows) if passed else None
    values = {
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": (completed_at - started_at).total_seconds(),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "runner_contract_hash": contract.runner_contract_hash,
        "input_file_sha256s": protocol.input_file_sha256s,
        "input_row_manifest_evidence_hashes": (
            protocol.input_row_manifest_evidence_hashes
        ),
        "git_process_count": git_process_count,
        "first_parent_diff_stdout_sha256": git_hashes[0],
        "reachable_commit_stdout_sha256": git_hashes[1],
        "tag_inventory_stdout_sha256": git_hashes[2],
        "reachable_commit_count": reachable_commit_count,
        "stable_release_tag_inventory_count": stable_release_count,
        "primary_events_in_complete_months": None if counts is None else counts["primary"],
        "primary_events_excluded_after_complete_months": (
            None if counts is None else counts["primary_excluded"]
        ),
        "all_accepted_events_in_complete_months": (
            None if counts is None else counts["all_accepted"]
        ),
        "all_accepted_events_excluded_after_complete_months": (
            None if counts is None else counts["all_accepted_excluded"]
        ),
        "canonical_events_in_complete_months": (
            None if counts is None else counts["canonical"]
        ),
        "canonical_events_excluded_after_complete_months": (
            None if counts is None else counts["canonical_excluded"]
        ),
        "unresolved_merges_in_complete_months": (
            None if counts is None else counts["unresolved"]
        ),
        "unresolved_merges_excluded_after_complete_months": (
            None if counts is None else counts["unresolved_excluded"]
        ),
        "output_path": None if output_path is None else output_path.as_posix(),
        "output_file_sha256": (
            None if output_payload is None else sha256(output_payload).hexdigest()
        ),
        "output_byte_count": None if output_payload is None else len(output_payload),
        "output_row_count": len(rows),
        "output_row_manifest_evidence_hash": output_manifest,
        "gate_results": gate_results(
            passed=passed,
            evidence=(
                "All frozen measurement construction gates passed."
                if passed
                else f"Run stopped: {type(failure).__name__}: {failure}"[:500]
            ),
        ),
        "passed_gate_count": len(S5_MEASUREMENT_GATES) if passed else 0,
        "failed_gate_count": 0 if passed else len(S5_MEASUREMENT_GATES),
        "decision": S5_MEASUREMENT_PASS if passed else S5_MEASUREMENT_STOP,
        "next_authorization": (
            S5_MEASUREMENT_RESULT_NEXT if passed else S5_MEASUREMENT_FAILURE_NEXT
        ),
        "authorizes_result_audit": passed,
        "failure_type": None if passed else type(failure).__name__,
        "failure_message": None if passed else str(failure)[:2_000],
        "limitations": result_limitations(),
    }
    return build_hashed(
        S5AcceptedDevelopmentMeasurementResultV1,
        "result_evidence_hash",
        values,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen S5 accepted-development measurements once."
    )
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = datetime.now(UTC)
    protocol, protocol_audit, contract, contract_audit = load_authorization(
        protocol_path=args.protocol,
        protocol_audit_path=args.protocol_audit,
        contract_path=args.contract,
        contract_audit_path=args.contract_audit,
    )
    if args.output.as_posix() != contract.output_path or args.result.as_posix() != (
        contract.result_path
    ):
        raise SystemExit("FAIL S5 measurement output paths changed")
    if args.output.exists() or args.result.exists():
        raise SystemExit("FAIL S5 measurement run authority already consumed")
    git_process_count = 0
    git_hashes: list[str | None] = [None, None, None]
    reachable_commit_count: int | None = None
    stable_release_count: int | None = None
    rows: tuple[S5AcceptedDevelopmentMonthlyMeasurementRow, ...] = ()
    counts: dict[str, int] | None = None
    output_payload: bytes | None = None
    failure: Exception | None = None
    try:
        if tuple(file_sha256(PROJECT_ROOT / path) for path in protocol.input_paths) != (
            S5_MEASUREMENT_INPUT_FILE_SHA256S
        ):
            raise ValueError("S5 measurement input file identity changed")
        input_models = (
            S5GitHubNormalizedPull,
            S5CorrectedCanonicalMappingRow,
            S5CorrectedTargetResolutionRow,
            S5CorrectedAcceptedCoverageRow,
            S5CorrectedUnresolvedMergeRow,
        )
        loaded = tuple(
            load_jsonl(PROJECT_ROOT / path, model)
            for path, model in zip(protocol.input_paths, input_models, strict=True)
        )
        if tuple(len(group) for group in loaded) != protocol.input_row_counts:
            raise ValueError("S5 measurement input row count changed")
        if tuple(row_manifest_hash(group) for group in loaded) != (
            S5_MEASUREMENT_INPUT_ROW_MANIFEST_HASHES
        ):
            raise ValueError("S5 measurement input row manifest changed")
        pulls, canonical_rows, _target_rows, coverage_rows, unresolved_rows = loaded
        repository = PROJECT_ROOT / protocol.history_dataset_path
        if dataset_manifest_hash(repository) != protocol.history_dataset_directory_sha256:
            raise ValueError("S5 measurement history dataset identity changed")
        environment = git_environment(contract)
        git_payloads: list[bytes] = []
        for command in (
            contract.first_parent_diff_command,
            contract.reachable_commit_command,
            contract.tag_inventory_command,
        ):
            git_process_count += 1
            payload = run_git(
                expand_command(command, protocol),
                environment=environment,
                timeout_seconds=contract.maximum_process_seconds,
                maximum_stdout_bytes=contract.maximum_single_stdout_bytes,
            )
            git_payloads.append(payload)
        git_hashes = [sha256(payload).hexdigest() for payload in git_payloads]
        diff_records = parse_first_parent_diff_stream(git_payloads[0])
        reachable_commits = parse_reachable_commits(git_payloads[1])
        reachable_commit_count = len(reachable_commits)
        if (
            reachable_commit_count != 50_395
            or protocol.source_cutoff_commit not in reachable_commits
        ):
            raise ValueError("S5 measurement reachable commit universe changed")
        release_tags = parse_stable_release_tags(
            git_payloads[2],
            stable_release_tag_regex=protocol.stable_release_tag_regex,
            reachable_commits=reachable_commits,
        )
        stable_release_count = len(release_tags)
        rows, excluded = build_measurements(
            protocol=protocol,
            pulls=pulls,
            canonical_rows=canonical_rows,
            coverage_rows=coverage_rows,
            unresolved_rows=unresolved_rows,
            diff_records=diff_records,
            release_tags=release_tags,
        )
        if len(rows) != protocol.expected_measurement_month_count:
            raise ValueError("S5 measurement output month count changed")
        counts = {
            "primary": sum(
                row.primary_source_verified_accepted_pull_count for row in rows
            ),
            "primary_excluded": excluded.get("primary", 0),
            "all_accepted": sum(row.all_accepted_pull_count for row in rows),
            "all_accepted_excluded": excluded.get("all_accepted", 0),
            "canonical": sum(row.canonical_integration_count for row in rows),
            "canonical_excluded": excluded.get("canonical", 0),
            "unresolved": sum(row.unresolved_git_merge_count for row in rows),
            "unresolved_excluded": excluded.get("unresolved", 0),
        }
        if (
            counts["primary"] + counts["primary_excluded"] != 16_271
            or counts["all_accepted"] + counts["all_accepted_excluded"] != 16_279
            or counts["canonical"] + counts["canonical_excluded"] != 16_242
            or counts["unresolved"] + counts["unresolved_excluded"] != 479
        ):
            raise ValueError("S5 measurement complete-month event accounting changed")
        output_payload = serialize_rows(rows)
        if len(output_payload) > protocol.maximum_future_output_bytes:
            raise ValueError("S5 measurement output exceeded the byte ceiling")
    except Exception as exc:  # noqa: BLE001 - every run failure must be evidenced
        failure = exc
        rows = ()
        counts = None
        output_payload = None

    completed_at = datetime.now(UTC)
    result = build_result(
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        started_at=started_at,
        completed_at=completed_at,
        git_process_count=git_process_count,
        git_hashes=tuple(git_hashes),
        reachable_commit_count=reachable_commit_count,
        stable_release_count=stable_release_count,
        counts=counts,
        output_path=args.output if failure is None else None,
        output_payload=output_payload,
        rows=rows,
        failure=failure,
    )
    result_payload = (result.model_dump_json(indent=2) + "\n").encode("utf-8")
    if failure is None:
        assert output_payload is not None
        output_staged = write_staged(args.output, output_payload)
        result_staged = write_staged(args.result, result_payload)
        os.replace(output_staged, args.output)
        os.replace(result_staged, args.result)
        print(
            f"PASS {result.result_evidence_hash} rows={len(rows)} "
            f"git_processes={git_process_count} market_values=0 returns=0 orders=0",
            flush=True,
        )
        return 0
    result_staged = write_staged(args.result, result_payload)
    os.replace(result_staged, args.result)
    print(
        f"STOP {result.result_evidence_hash} {result.failure_type}: "
        f"{result.failure_message}",
        file=sys.stderr,
        flush=True,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
