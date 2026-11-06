from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization_execution import (  # noqa: E402
    S5_CORRECTED_NORMALIZATION_PASS,
    S5CorrectedAcceptedCoverageRow,
    S5CorrectedCanonicalMappingRow,
    S5CorrectedTargetResolutionRow,
    S5CorrectedUnresolvedMergeRow,
    S5GitHubCorrectedNormalizationResultV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization_result_audit import (  # noqa: E402
    S5GitHubCorrectedNormalizationResultAuditV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5GitHubNormalizationResult,
    S5GitHubNormalizedPull,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_corrected_normalization as runner,
)
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_normalization as legacy,
)

DEFAULT_RESULT = runner.DEFAULT_RESULT
DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_corrected_normalization_result_audit_v2.json"
)
MODEL_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_corrected_normalization_result_audit.py"
)
SCRIPT_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_corrected_normalization_result.py"
)
AUDITOR_PATHS = (MODEL_PATH, SCRIPT_PATH)
ModelT = TypeVar("ModelT", bound=BaseModel)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def implementation_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(
            path=path.as_posix(),
            file_sha256=file_sha256(PROJECT_ROOT / path),
        )
        for path in sorted(AUDITOR_PATHS, key=lambda item: item.as_posix())
    )


def load_jsonl[ModelT: BaseModel](
    path: Path,
    model: type[ModelT],
) -> tuple[ModelT, ...]:
    rows = tuple(
        model.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )
    return rows


def output_manifest_hash(result: S5GitHubCorrectedNormalizationResultV2) -> str:
    return universe_evidence_hash(
        tuple(
            {
                "path": path,
                "file_sha256": file_hash,
                "byte_count": byte_count,
                "row_count": row_count,
                "row_manifest_evidence_hash": row_hash,
            }
            for path, file_hash, byte_count, row_count, row_hash in zip(
                result.output_paths,
                result.output_file_sha256s,
                result.output_byte_counts,
                result.output_row_counts,
                result.output_row_manifest_evidence_hashes,
                strict=True,
            )
        )
    )


def reconstruct(
    result_path: Path,
) -> tuple[S5GitHubCorrectedNormalizationResultV2, tuple[tuple[Any, ...], ...]]:
    protocol, protocol_audit, contract, contract_audit = runner.load_authorization()
    result = S5GitHubCorrectedNormalizationResultV2.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.execution_contract_audit_evidence_hash
        != contract_audit.audit_evidence_hash
        or result.runner_contract_hash != runner.runner_contract_hash()
        or result.decision != S5_CORRECTED_NORMALIZATION_PASS
        or result.failed_gate_count != 0
        or result.failure_type is not None
        or result.failure_message is not None
    ):
        raise ValueError("S5 corrected normalization result is not an auditable PASS")
    expected_paths = (
        protocol.pull_output_path,
        protocol.canonical_mapping_output_path,
        protocol.target_resolution_output_path,
        protocol.accepted_coverage_output_path,
        protocol.unresolved_output_path,
    )
    if result.output_paths != expected_paths:
        raise ValueError("S5 corrected normalization output paths changed")
    models: tuple[type[BaseModel], ...] = (
        S5GitHubNormalizedPull,
        S5CorrectedCanonicalMappingRow,
        S5CorrectedTargetResolutionRow,
        S5CorrectedAcceptedCoverageRow,
        S5CorrectedUnresolvedMergeRow,
    )
    stored_rows = tuple(
        load_jsonl(Path(path), model)
        for path, model in zip(result.output_paths, models, strict=True)
    )
    for index, (path_text, rows) in enumerate(
        zip(result.output_paths, stored_rows, strict=True)
    ):
        path = Path(path_text)
        payload = path.read_bytes()
        expected_payload = (
            legacy.serialize_rows(rows)
            if index == 0
            else runner.serialize_rows(rows)
        )
        if (
            payload != expected_payload
            or file_sha256(path) != result.output_file_sha256s[index]
            or len(payload) != result.output_byte_counts[index]
            or len(rows) != result.output_row_counts[index]
            or runner.row_manifest_hash(rows)
            != result.output_row_manifest_evidence_hashes[index]
        ):
            raise ValueError("S5 corrected normalization output changed")
    lineage = legacy.load_lineage()
    pulls, raw_count, post_cutoff = legacy.load_normalized_pulls(lineage)
    timed, graph, graph_hash = runner.inspect_git(protocol)
    original = legacy.map_git_merges(
        pulls=pulls,
        topology=timed.topology,
        census=lineage.census_result,
        cutoff=lineage.protocol.cohort_created_at_cutoff,
    )
    _, _, contexts = runner.decode_target_contexts()
    accepted = tuple(
        row
        for row in pulls
        if legacy.accepted_pull(
            row,
            cutoff=lineage.protocol.cohort_created_at_cutoff,
        )
    )
    accepted_by_number = {row.pull_number: row for row in accepted}
    merges_by_commit = {row.commit_sha: row for row in timed.topology.merges}
    second_parent_lists: dict[str, list[legacy.GitMerge]] = {}
    for merge in timed.topology.merges:
        second_parent_lists.setdefault(merge.second_parent_sha, []).append(merge)
    merges_by_second_parent = {
        key: tuple(value) for key, value in second_parent_lists.items()
    }
    census_by_pull = {
        row.pull_request_id: row
        for row in lineage.census_result.accepted_pull_request_records
    }
    census_by_commit = {
        row.merge_commit_hash: row
        for row in lineage.census_result.accepted_pull_request_records
    }
    canonical = runner.canonical_mapping_rows(
        legacy_outcome=original,
        topology=timed,
        pulls_by_number={row.pull_number: row for row in pulls},
        census_by_pull=census_by_pull,
        merges_by_commit=merges_by_commit,
        contexts=contexts,
    )
    canonical_by_pull = {row.canonical_pull_number: row for row in canonical}
    resolutions = runner.target_resolution_rows(
        contexts=contexts,
        accepted_by_number=accepted_by_number,
        canonical_by_pull=canonical_by_pull,
        full_graph=graph,
        merges_by_commit=merges_by_commit,
        merges_by_second_parent=merges_by_second_parent,
    )
    coverage = runner.accepted_coverage_rows(
        accepted=accepted,
        canonical_by_pull=canonical_by_pull,
        resolutions_by_pull={row.pull_number: row for row in resolutions},
    )
    accepted_head_lists: dict[str, list[int]] = {}
    for pull in accepted:
        accepted_head_lists.setdefault(pull.head_sha, []).append(pull.pull_number)
    unresolved = runner.unresolved_rows(
        topology=timed,
        canonical_commits={row.merge_commit_sha for row in canonical},
        accepted_by_head={
            key: tuple(value) for key, value in accepted_head_lists.items()
        },
        census_by_commit=census_by_commit,
        contexts=contexts,
    )
    reconstructed_rows: tuple[tuple[Any, ...], ...] = (
        pulls,
        canonical,
        resolutions,
        coverage,
        unresolved,
    )
    if reconstructed_rows != stored_rows:
        raise ValueError("S5 corrected normalization rows differ from reconstruction")
    failed_result = S5GitHubNormalizationResult.model_validate_json(
        runner.FAILED_RESULT_PATH.read_text(encoding="utf-8")
    )
    counts = {
        "source_page_files_opened": 245,
        "response_bodies_decoded": 245,
        "targeted_responses_decoded": len(contexts),
        "local_git_process_count": 2,
        "raw_record_count": raw_count,
        "cohort_record_count": len(pulls),
        "github_accepted_pull_count": len(accepted),
        "first_parent_commit_count": timed.topology.first_parent_count,
        "first_parent_merge_count": timed.topology.merge_count,
        "full_graph_commit_count": len(graph),
        "legacy_exact_mapping_count": len(original.mappings),
        "legacy_unresolved_merge_count": len(original.unresolved),
        "recognized_recovery_count": sum(
            row.mapping_status
            == "TARGETED_RECOGNIZED_NUMBER_AND_SECOND_PARENT_HEAD_SHA_EXACT"
            for row in canonical
        ),
        "recognized_unresolved_count": sum(
            row.resolution_status == "RECOGNIZED_ENDPOINT_404_UNRESOLVED"
            for row in resolutions
        ),
        "canonical_mapping_count": len(canonical),
        "corrected_unresolved_merge_count": len(unresolved),
        "accepted_source_linked_count": sum(
            row.local_source_link_verified for row in coverage
        ),
        "accepted_source_unverified_count": sum(
            not row.local_source_link_verified for row in coverage
        ),
        "many_to_one_group_count": 2,
    }
    outputs = tuple(
        (Path(path), Path(path).read_bytes(), rows)
        for path, rows in zip(result.output_paths, reconstructed_rows, strict=True)
    )
    gates = runner.gate_results((True,) * 19)
    reconstructed_result = runner.build_result(
        started_at=result.started_at,
        completed_at=result.completed_at,
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        failed_result=failed_result,
        first_parent_hash=timed.stream_sha256,
        full_graph_hash=graph_hash,
        counts=counts,
        outputs=outputs,
        gates=gates,
        failure=None,
    )
    if reconstructed_result != result or post_cutoff != 9:
        raise ValueError("S5 corrected normalization result differs from reconstruction")
    return result, reconstructed_rows


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5GitHubCorrectedNormalizationResultAuditV2:
    result, rows = reconstruct(result_path)
    implementation = implementation_bindings()
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "protocol_audit_evidence_hash": result.protocol_audit_evidence_hash,
        "execution_contract_evidence_hash": result.execution_contract_evidence_hash,
        "execution_contract_audit_evidence_hash": (
            result.execution_contract_audit_evidence_hash
        ),
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_implementation_bindings": implementation,
        "auditor_contract_hash": universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in implementation)
        ),
        "output_file_manifest_evidence_hash": output_manifest_hash(result),
        "output_row_manifest_evidence_hash": universe_evidence_hash(
            tuple(runner.row_manifest_hash(output_rows) for output_rows in rows)
        ),
    }
    provisional = S5GitHubCorrectedNormalizationResultAuditV2.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubCorrectedNormalizationResultAuditV2.model_validate(complete)


def write_atomic(
    path: Path,
    audit: S5GitHubCorrectedNormalizationResultAuditV2,
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 corrected result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 corrected result-audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubCorrectedNormalizationResultAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("S5 corrected normalization result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S5 corrected result v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = S5GitHubCorrectedNormalizationResultAuditV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected:
                raise ValueError("Stored S5 corrected result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            result_path=args.result,
            audited_at=datetime.now(UTC),
        )
        write_atomic(args.output, audit)
        audited_row_count = sum(
            (
                audit.normalized_pull_count,
                audit.canonical_mapping_count,
                audit.target_resolution_count,
                audit.accepted_coverage_count,
                audit.unresolved_merge_count,
            )
        )
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"rows={audited_row_count} "
            "git_processes=2 github_requests=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
