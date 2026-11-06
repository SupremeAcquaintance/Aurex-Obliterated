from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure import (  # noqa: E402
    S5NormalizationFailureAdjudicationResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure_audit import (  # noqa: E402
    S5NormalizationFailureAdjudicationResultAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_normalization_failure_adjudication as runner,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_result_audit_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_normalization_failure_audit.py"
)
AUDITOR_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_normalization_failure_adjudication_result.py"
)


def auditor_contract_hash() -> str:
    paths = (MODULE_PATH, AUDITOR_PATH)
    return universe_evidence_hash(
        tuple(
            {"path": path.as_posix(), "file_sha256": runner.file_sha256(PROJECT_ROOT / path)}
            for path in paths
        )
    )


def reconstruct(
    stored: S5NormalizationFailureAdjudicationResult,
) -> S5NormalizationFailureAdjudicationResult:
    protocol, audit, lineage = runner.load_authorization()
    dataset_hash = runner.original.dataset_manifest_hash(
        Path(lineage.protocol.history_dataset_path)
    )
    if dataset_hash != lineage.protocol.history_dataset_directory_sha256:
        raise ValueError("S5 failure audit history dataset identity changed")
    pulls = runner.load_diagnostic_pulls(lineage)
    full_graph = runner.execute_full_graph_command(protocol, lineage)
    topology = full_graph.first_parent_topology
    normalized = tuple(row.normalized for row in pulls)
    original_outcome = runner.original.map_git_merges(
        pulls=normalized,
        topology=topology,
        census=lineage.census_result,
        cutoff=lineage.protocol.cohort_created_at_cutoff,
    )
    recognized = runner.classify_recognized(
        pulls=pulls,
        topology=topology,
        lineage=lineage,
    )
    unmatched, unmatched_rows = runner.classify_unmatched(
        pulls=pulls,
        topology=topology,
        full_graph=full_graph,
        original_outcome=original_outcome,
        cutoff=lineage.protocol.cohort_created_at_cutoff,
    )
    gates = runner.build_gate_results(
        protocol=protocol,
        lineage=lineage,
        full_graph=full_graph,
        recognized=recognized,
        unmatched=unmatched,
        original_outcome=original_outcome,
    )
    return runner.build_result(
        completed_at=stored.completed_at,
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


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5NormalizationFailureAdjudicationResultAudit:
    stored = S5NormalizationFailureAdjudicationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    expected = reconstruct(stored)
    if stored != expected:
        raise ValueError("S5 failure adjudication result differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": runner.file_sha256(result_path),
        "result_evidence_hash": stored.result_evidence_hash,
        "protocol_evidence_hash": stored.protocol_evidence_hash,
        "protocol_audit_evidence_hash": stored.protocol_audit_evidence_hash,
        "runner_contract_hash": stored.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
    }
    provisional = S5NormalizationFailureAdjudicationResultAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5NormalizationFailureAdjudicationResultAudit.model_validate(complete)


def write_atomic(
    path: Path, audit: S5NormalizationFailureAdjudicationResultAudit
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 failure result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 failure result audit: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5NormalizationFailureAdjudicationResultAudit.model_validate_json(
        serialized
    ) != audit:
        raise ValueError("S5 failure result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S5 failure result.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=runner.DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5NormalizationFailureAdjudicationResultAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
        if stored != expected:
            raise SystemExit("Stored S5 failure result audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
