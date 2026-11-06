from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (  # noqa: E402
    S5GitHubNormalizationProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5_GITHUB_NORMALIZATION_STOP,
    S5GitHubNormalizationResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure import (  # noqa: E402
    S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT,
    S5NormalizationFailureAdjudicationProtocol,
    S5NormalizationFailureAdjudicationProtocolAudit,
    S5NormalizationFailureAdjudicationResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure_audit import (  # noqa: E402
    S5NormalizationFailureAdjudicationResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (  # noqa: E402
    S5_TARGETED_CORRECTION_GATE_IDS,
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCorrectionTarget,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_targeted_correction.py"
)
SCRIPT_PATH = Path(
    "scripts/freeze_s5_bitcoin_core_github_targeted_correction.py"
)
NORMALIZATION_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
)
FAILED_NORMALIZATION_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
)
ADJUDICATION_PROTOCOL_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_protocol_v1.json"
)
ADJUDICATION_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_protocol_audit_v1.json"
)
ADJUDICATION_RESULT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_result_v1.json"
)
ADJUDICATION_RESULT_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_result_audit_v1.json"
)
CENSUS_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_result_v1.json"
)
CENSUS_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_result_audit_v1.json"
)
BULK_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json"
)
BULK_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v4.json")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                NORMALIZATION_PROTOCOL_PATH,
                FAILED_NORMALIZATION_RESULT_PATH,
                ADJUDICATION_PROTOCOL_PATH,
                ADJUDICATION_PROTOCOL_AUDIT_PATH,
                ADJUDICATION_RESULT_PATH,
                ADJUDICATION_RESULT_AUDIT_PATH,
                CENSUS_RESULT_PATH,
                CENSUS_RESULT_AUDIT_PATH,
                BULK_PROTOCOL_PATH,
                BULK_RESULT_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_lineage() -> dict[str, object]:
    normalization = S5GitHubNormalizationProtocol.model_validate_json(
        NORMALIZATION_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    failed = S5GitHubNormalizationResult.model_validate_json(
        FAILED_NORMALIZATION_RESULT_PATH.read_text(encoding="utf-8")
    )
    adjudication = S5NormalizationFailureAdjudicationProtocol.model_validate_json(
        ADJUDICATION_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    adjudication_audit = (
        S5NormalizationFailureAdjudicationProtocolAudit.model_validate_json(
            ADJUDICATION_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
        )
    )
    adjudication_result = S5NormalizationFailureAdjudicationResult.model_validate_json(
        ADJUDICATION_RESULT_PATH.read_text(encoding="utf-8")
    )
    adjudication_result_audit = (
        S5NormalizationFailureAdjudicationResultAudit.model_validate_json(
            ADJUDICATION_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
        )
    )
    census = S5BitcoinCoreHistoryCensusResult.model_validate_json(
        CENSUS_RESULT_PATH.read_text(encoding="utf-8")
    )
    census_audit = S5BitcoinCoreHistoryCensusResultAudit.model_validate_json(
        CENSUS_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    bulk_protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        BULK_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    bulk_result = S5GitHubBulkResult.model_validate_json(
        BULK_RESULT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        failed.protocol_evidence_hash != normalization.protocol_evidence_hash
        or failed.decision != S5_GITHUB_NORMALIZATION_STOP
        or failed.passed_gate_count != 13
        or failed.failed_gate_count != 4
        or failed.recognized_pull_merge_count != 7_961
        or failed.recognized_exact_mapping_count != 7_878
        or failed.accepted_github_pull_count != 16_279
        or failed.total_exact_mapping_count != 16_167
        or failed.unmatched_accepted_github_pull_count != 112
        or failed.ambiguous_git_merge_count != 1
        or adjudication.failed_result_evidence_hash != failed.result_evidence_hash
        or adjudication_audit.protocol_file_sha256
        != file_sha256(ADJUDICATION_PROTOCOL_PATH)
        or adjudication_audit.protocol_evidence_hash
        != adjudication.protocol_evidence_hash
        or adjudication_result.protocol_evidence_hash
        != adjudication.protocol_evidence_hash
        or adjudication_result.protocol_audit_evidence_hash
        != adjudication_audit.audit_evidence_hash
        or adjudication_result.failed_result_evidence_hash
        != failed.result_evidence_hash
        or adjudication_result.decision
        != "PASS_S5_NORMALIZATION_FAILURE_ADJUDICATION"
        or adjudication_result.next_authorization
        != S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT
        or adjudication_result.reconstructed_recognized_gap_count != 83
        or adjudication_result.reconstructed_unmatched_accepted_pull_count != 112
        or adjudication_result.reconstructed_ambiguous_count != 1
        or adjudication_result.structurally_unexplained_count != 187
        or adjudication_result_audit.result_file_sha256
        != file_sha256(ADJUDICATION_RESULT_PATH)
        or adjudication_result_audit.result_evidence_hash
        != adjudication_result.result_evidence_hash
        or adjudication_result_audit.protocol_evidence_hash
        != adjudication.protocol_evidence_hash
        or adjudication_result_audit.protocol_audit_evidence_hash
        != adjudication_audit.audit_evidence_hash
        or census_audit.result_file_sha256 != file_sha256(CENSUS_RESULT_PATH)
        or census_audit.result_evidence_hash != census.result_evidence_hash
        or bulk_result.protocol_evidence_hash != bulk_protocol.protocol_evidence_hash
        or normalization.census_result_evidence_hash != census.result_evidence_hash
        or normalization.bulk_result_evidence_hash != bulk_result.result_evidence_hash
        or any(
            value != 0
            for value in (
                adjudication_result.btc_market_values_read,
                adjudication_result.parameters_defined,
                adjudication_result.returns_calculated,
                adjudication_result.candidates_created,
                adjudication_result.orders_submitted,
            )
        )
    )
    if changed:
        raise ValueError("S5 targeted correction lineage changed")
    return {
        "normalization": normalization,
        "failed": failed,
        "adjudication": adjudication,
        "adjudication_audit": adjudication_audit,
        "adjudication_result": adjudication_result,
        "adjudication_result_audit": adjudication_result_audit,
        "census": census,
        "census_audit": census_audit,
        "bulk_protocol": bulk_protocol,
        "bulk_result": bulk_result,
    }


def build_target_manifest(
    *,
    adjudication_result: S5NormalizationFailureAdjudicationResult,
    census: S5BitcoinCoreHistoryCensusResult,
) -> tuple[S5TargetedCorrectionTarget, ...]:
    recognized_categories: dict[int, str] = {}
    for category in adjudication_result.recognized_categories:
        if category.category == "EXACT_PRIOR_MAPPING":
            continue
        if category.count != len(category.pull_numbers):
            raise ValueError("S5 recognized correction category is not exhaustive")
        for pull_number in category.pull_numbers:
            if pull_number in recognized_categories:
                raise ValueError("S5 recognized correction target is duplicated")
            recognized_categories[pull_number] = category.category

    unmatched_categories: dict[int, str] = {}
    for category in adjudication_result.unmatched_categories:
        if category.count != len(category.pull_numbers):
            raise ValueError("S5 unmatched correction category is not exhaustive")
        for pull_number in category.pull_numbers:
            if pull_number in unmatched_categories:
                raise ValueError("S5 unmatched correction target is duplicated")
            unmatched_categories[pull_number] = category.category

    if (len(recognized_categories), len(unmatched_categories)) != (83, 112):
        raise ValueError("S5 targeted correction category counts changed")
    overlap = set(recognized_categories) & set(unmatched_categories)
    targets = sorted(set(recognized_categories) | set(unmatched_categories))
    if len(overlap) != 1 or len(targets) != 194:
        raise ValueError("S5 targeted correction union changed")

    census_by_pull: dict[int, object] = {}
    for row in census.accepted_pull_request_records:
        if row.pull_request_id in census_by_pull:
            raise ValueError("S5 census pull identity is duplicated")
        census_by_pull[row.pull_request_id] = row
    if set(recognized_categories) - set(census_by_pull):
        raise ValueError("S5 recognized correction target is absent from census")

    manifest: list[S5TargetedCorrectionTarget] = []
    for sequence, pull_number in enumerate(targets, start=1):
        reasons: list[str] = []
        if pull_number in recognized_categories:
            reasons.append("RECOGNIZED_GAP")
        if pull_number in unmatched_categories:
            reasons.append("UNMATCHED_ACCEPTED_PULL")
        census_row = census_by_pull.get(pull_number)
        manifest.append(
            S5TargetedCorrectionTarget(
                sequence=sequence,
                pull_number=pull_number,
                target_reasons=tuple(sorted(reasons)),
                recognized_failure_category=recognized_categories.get(pull_number),
                unmatched_failure_category=unmatched_categories.get(pull_number),
                census_merge_commit_sha=(
                    census_row.merge_commit_hash
                    if pull_number in recognized_categories
                    else None
                ),
                census_pattern_id=(
                    census_row.pattern_id
                    if pull_number in recognized_categories
                    else None
                ),
            )
        )
    return tuple(manifest)


def build_protocol(
    *, frozen_at: datetime
) -> S5TargetedCompletenessCorrectionProtocol:
    lineage = load_lineage()
    bindings = source_bindings()
    normalization = lineage["normalization"]
    failed = lineage["failed"]
    adjudication = lineage["adjudication"]
    adjudication_audit = lineage["adjudication_audit"]
    adjudication_result = lineage["adjudication_result"]
    adjudication_result_audit = lineage["adjudication_result_audit"]
    census = lineage["census"]
    census_audit = lineage["census_audit"]
    bulk_protocol = lineage["bulk_protocol"]
    bulk_result = lineage["bulk_result"]
    manifest = build_target_manifest(
        adjudication_result=adjudication_result,
        census=census,
    )
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": bindings,
        "source_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(binding.model_dump(mode="json") for binding in bindings)
        ),
        "normalization_protocol_evidence_hash": normalization.protocol_evidence_hash,
        "failed_normalization_result_evidence_hash": failed.result_evidence_hash,
        "adjudication_protocol_evidence_hash": adjudication.protocol_evidence_hash,
        "adjudication_protocol_audit_evidence_hash": (
            adjudication_audit.audit_evidence_hash
        ),
        "adjudication_result_evidence_hash": adjudication_result.result_evidence_hash,
        "adjudication_result_audit_evidence_hash": (
            adjudication_result_audit.audit_evidence_hash
        ),
        "census_result_evidence_hash": census.result_evidence_hash,
        "census_result_audit_evidence_hash": census_audit.audit_evidence_hash,
        "bulk_protocol_evidence_hash": bulk_protocol.protocol_evidence_hash,
        "bulk_result_evidence_hash": bulk_result.result_evidence_hash,
        "target_manifest": manifest,
        "target_manifest_evidence_hash": universe_evidence_hash(
            tuple(target.model_dump(mode="json") for target in manifest)
        ),
        "required_gate_ids": S5_TARGETED_CORRECTION_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This protocol authorizes evidence acquisition only; it does "
                    "not correct normalization.",
                    "The original normalization STOP remains binding throughout acquisition.",
                    "The target set is limited to the 194 pull numbers fixed by the "
                    "adjudication result.",
                    "Each target permits at most one credential-free GitHub request "
                    "across the complete run.",
                    "A GitHub 404 is preserved as source evidence and is not retried or guessed.",
                    "Current GitHub metadata can reflect changes made after the "
                    "historical pull event.",
                    "GitHub merge_commit_sha semantics vary across merge, squash, and "
                    "rebase methods.",
                    "The 83 census message first lines are diagnostic evidence and "
                    "cannot change a mapping.",
                    "Full Git reachability proves local ancestry only, not historical "
                    "public availability.",
                    "No new accepted event or causal timestamp may be created in this stage.",
                    "No mapping rule or completeness threshold may be changed after "
                    "responses are opened.",
                    "Any corrected normalization requires a separately frozen and "
                    "audited protocol.",
                    "No BTC market value, return, parameter, strategy candidate, or "
                    "order is authorized.",
                    "Unauthenticated GitHub rate limits can require several hours of "
                    "serial waiting.",
                )
            )
        ),
    }
    provisional = S5TargetedCompletenessCorrectionProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5TargetedCompletenessCorrectionProtocol.model_validate(complete)


def write_atomic(
    path: Path, protocol: S5TargetedCompletenessCorrectionProtocol
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted correction protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted correction transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        serialized
    ) != protocol:
        raise ValueError("S5 targeted correction protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S5 targeted correction.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5TargetedCompletenessCorrectionProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_protocol(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 targeted correction protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    if Path(protocol.result_path).exists():
        raise ValueError("S5 targeted correction result already exists")
    write_atomic(args.output, protocol)
    print(f"FROZEN {args.output} {protocol.protocol_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
