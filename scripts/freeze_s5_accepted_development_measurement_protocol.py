from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_accepted_development_measurement_protocol import (  # noqa: E402
    S5_MEASUREMENT_DEFINITION_ROWS,
    S5_MEASUREMENT_GATES,
    S5_MEASUREMENT_SOURCE_PATHS,
    S5AcceptedDevelopmentMeasurementProtocolV1,
    S5MeasurementDefinition,
    S5MeasurementEventUniverse,
)
from aurex.backtest_engine.s5_bitcoin_core_development_charter import (  # noqa: E402
    S5BitcoinCoreDevelopmentCharter,
    S5BitcoinCoreDevelopmentCharterAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization import (  # noqa: E402
    S5GitHubCorrectedNormalizationProtocolAuditV2,
    S5GitHubCorrectedNormalizationProtocolV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization_execution import (  # noqa: E402
    S5_CORRECTED_NORMALIZATION_NEXT,
    S5_CORRECTED_NORMALIZATION_PASS,
    S5GitHubCorrectedNormalizationExecutionContractAuditV2,
    S5GitHubCorrectedNormalizationExecutionContractV2,
    S5GitHubCorrectedNormalizationResultV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization_result_audit import (  # noqa: E402
    S5GitHubCorrectedNormalizationResultAuditV2,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_accepted_development_measurement_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_accepted_development_measurement_protocol.py"
)
CHARTER_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_v1.json")
CHARTER_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_development_charter_audit_v1.json"
)
HISTORY_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json"
)
HISTORY_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_protocol_audit_v1.json"
)
HISTORY_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_v2.json"
)
HISTORY_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_audit_v2.json"
)
CENSUS_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_protocol_v1.json"
)
CENSUS_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_protocol_audit_v1.json"
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
BULK_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
BULK_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v4.json")
BULK_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_final_result_audit_v4.json"
)
CORRECTED_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_protocol_v2.json"
)
CORRECTED_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_protocol_audit_v2.json"
)
CORRECTED_EXECUTION_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_execution_contract_v2.json"
)
CORRECTED_EXECUTION_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_execution_contract_audit_v2.json"
)
CORRECTED_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_result_v2.json"
)
CORRECTED_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_result_audit_v2.json"
)
INPUT_PATHS = (
    Path("data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_canonical_merge_mapping_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_target_resolution_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_accepted_source_coverage_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v2.jsonl"),
)
SOURCE_PATHS = tuple(
    sorted(
        (
            CHARTER_PATH,
            CHARTER_AUDIT_PATH,
            HISTORY_PROTOCOL_PATH,
            HISTORY_PROTOCOL_AUDIT_PATH,
            HISTORY_RESULT_PATH,
            HISTORY_RESULT_AUDIT_PATH,
            CENSUS_PROTOCOL_PATH,
            CENSUS_PROTOCOL_AUDIT_PATH,
            CENSUS_RESULT_PATH,
            CENSUS_RESULT_AUDIT_PATH,
            BULK_PROTOCOL_PATH,
            BULK_PROTOCOL_AUDIT_PATH,
            BULK_RESULT_PATH,
            BULK_RESULT_AUDIT_PATH,
            CORRECTED_PROTOCOL_PATH,
            CORRECTED_PROTOCOL_AUDIT_PATH,
            CORRECTED_EXECUTION_PATH,
            CORRECTED_EXECUTION_AUDIT_PATH,
            CORRECTED_RESULT_PATH,
            CORRECTED_RESULT_AUDIT_PATH,
            *INPUT_PATHS,
        ),
        key=lambda path: path.as_posix(),
    )
)


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


def builder_contract_hash() -> str:
    bindings = (
        S5HistoryBinding(path=MODULE_PATH.as_posix(), file_sha256=file_sha256(MODULE_PATH)),
        S5HistoryBinding(
            path=Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            file_sha256=file_sha256(Path(__file__)),
        ),
    )
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in sorted(bindings, key=lambda row: row.path))
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    if len(SOURCE_PATHS) != 25 or not all(path.is_file() for path in SOURCE_PATHS):
        raise ValueError("S5 measurement protocol source set is incomplete")
    if tuple(path.as_posix() for path in SOURCE_PATHS) != S5_MEASUREMENT_SOURCE_PATHS:
        raise ValueError("S5 measurement protocol source path contract changed")
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in SOURCE_PATHS
    )


def load_lineage() -> tuple[
    S5BitcoinCoreDevelopmentCharter,
    S5BitcoinCoreDevelopmentCharterAudit,
    S5GitHubCorrectedNormalizationProtocolV2,
    S5GitHubCorrectedNormalizationProtocolAuditV2,
    S5GitHubCorrectedNormalizationExecutionContractV2,
    S5GitHubCorrectedNormalizationExecutionContractAuditV2,
    S5GitHubCorrectedNormalizationResultV2,
    S5GitHubCorrectedNormalizationResultAuditV2,
    datetime,
]:
    charter = S5BitcoinCoreDevelopmentCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    charter_audit = S5BitcoinCoreDevelopmentCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    protocol = S5GitHubCorrectedNormalizationProtocolV2.model_validate_json(
        CORRECTED_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5GitHubCorrectedNormalizationProtocolAuditV2.model_validate_json(
        CORRECTED_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    execution = S5GitHubCorrectedNormalizationExecutionContractV2.model_validate_json(
        CORRECTED_EXECUTION_PATH.read_text(encoding="utf-8")
    )
    execution_audit = (
        S5GitHubCorrectedNormalizationExecutionContractAuditV2.model_validate_json(
            CORRECTED_EXECUTION_AUDIT_PATH.read_text(encoding="utf-8")
        )
    )
    result = S5GitHubCorrectedNormalizationResultV2.model_validate_json(
        CORRECTED_RESULT_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5GitHubCorrectedNormalizationResultAuditV2.model_validate_json(
        CORRECTED_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    bulk_protocol = json.loads(BULK_PROTOCOL_PATH.read_text(encoding="utf-8"))
    cohort_cutoff = datetime.fromisoformat(
        str(bulk_protocol["cohort_created_at_cutoff"]).replace("Z", "+00:00")
    )
    expected_paths = tuple(path.as_posix() for path in INPUT_PATHS)
    if (
        charter.charter_evidence_hash != charter_audit.charter_evidence_hash
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or execution.protocol_evidence_hash != protocol.protocol_evidence_hash
        or execution.contract_evidence_hash != execution_audit.contract_evidence_hash
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.execution_contract_evidence_hash != execution.contract_evidence_hash
        or result.decision != S5_CORRECTED_NORMALIZATION_PASS
        or result.next_authorization != S5_CORRECTED_NORMALIZATION_NEXT
        or not result.authorizes_measurement_protocol_design
        or result.result_evidence_hash != result_audit.result_evidence_hash
        or result_audit.next_authorization != S5_CORRECTED_NORMALIZATION_NEXT
        or result.output_paths != expected_paths
        or result.output_row_counts != (24_398, 16_242, 194, 16_279, 479)
        or result.accepted_source_linked_count != 16_271
        or result.accepted_source_unverified_count != 8
        or result.canonical_mapping_count != 16_242
        or result.history_dataset_directory_sha256
        != "02a3ca331a09dd2d94732968edf554ccdf927ed0042e56cf229d3a3a015c0a90"
        or cohort_cutoff != datetime(2026, 9, 2, 21, 43, 33, 504800, tzinfo=UTC)
    ):
        raise ValueError("S5 measurement predecessor lineage did not reconcile")
    if tuple(file_sha256(path) for path in INPUT_PATHS) != result.output_file_sha256s:
        raise ValueError("S5 measurement input files changed")
    return (
        charter,
        charter_audit,
        protocol,
        protocol_audit,
        execution,
        execution_audit,
        result,
        result_audit,
        cohort_cutoff,
    )


def event_universes() -> tuple[S5MeasurementEventUniverse, ...]:
    return (
        S5MeasurementEventUniverse(
            universe_id="SOURCE_VERIFIED_ACCEPTED_GITHUB_PULLS",
            role="PRIMARY",
            row_count=16_271,
            event_key="PULL_NUMBER",
            event_time="GITHUB_MERGED_AT",
            source_link_required=True,
            canonical_owner_required=False,
            many_to_one_policy=(
                "COUNT_PULL_EVENTS_AND_REPORT_DISTINCT_SOURCE_COMMITS_SEPARATELY"
            ),
            eligible_for_primary_measurement=True,
        ),
        S5MeasurementEventUniverse(
            universe_id="ALL_ACCEPTED_GITHUB_PULLS_SENSITIVITY",
            role="SENSITIVITY",
            row_count=16_279,
            event_key="PULL_NUMBER",
            event_time="GITHUB_MERGED_AT",
            source_link_required=False,
            canonical_owner_required=False,
            many_to_one_policy=(
                "COUNT_PULL_EVENTS_AND_REPORT_DISTINCT_SOURCE_COMMITS_SEPARATELY"
            ),
            eligible_for_primary_measurement=False,
        ),
        S5MeasurementEventUniverse(
            universe_id="CANONICAL_FIRST_PARENT_INTEGRATIONS",
            role="CORROBORATION",
            row_count=16_242,
            event_key="MERGE_COMMIT_SHA",
            event_time="SOURCE_LABELED_CANONICAL_EVENT_AT",
            source_link_required=True,
            canonical_owner_required=True,
            many_to_one_policy="COUNT_EACH_CANONICAL_FIRST_PARENT_MERGE_ONCE",
            eligible_for_primary_measurement=False,
        ),
    )


def measurement_definitions() -> tuple[S5MeasurementDefinition, ...]:
    return tuple(
        S5MeasurementDefinition(
            measurement_id=measurement_id,
            formula=formula,
            source_universe=source_universe,
            candidate_feature_eligible=candidate_feature_eligible,
        )
        for measurement_id, formula, source_universe, candidate_feature_eligible in (
            S5_MEASUREMENT_DEFINITION_ROWS
        )
    )


def build_protocol(*, frozen_at: datetime) -> S5AcceptedDevelopmentMeasurementProtocolV1:
    (
        charter,
        charter_audit,
        corrected_protocol,
        corrected_protocol_audit,
        corrected_execution,
        corrected_execution_audit,
        corrected_result,
        corrected_result_audit,
        cohort_cutoff,
    ) = load_lineage()
    bindings = source_bindings()
    values = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": bindings,
        "source_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in bindings)
        ),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "charter_audit_evidence_hash": charter_audit.audit_evidence_hash,
        "corrected_normalization_protocol_evidence_hash": (
            corrected_protocol.protocol_evidence_hash
        ),
        "corrected_normalization_protocol_audit_evidence_hash": (
            corrected_protocol_audit.audit_evidence_hash
        ),
        "corrected_normalization_execution_contract_evidence_hash": (
            corrected_execution.contract_evidence_hash
        ),
        "corrected_normalization_execution_contract_audit_evidence_hash": (
            corrected_execution_audit.audit_evidence_hash
        ),
        "corrected_normalization_result_evidence_hash": (
            corrected_result.result_evidence_hash
        ),
        "corrected_normalization_result_audit_evidence_hash": (
            corrected_result_audit.audit_evidence_hash
        ),
        "history_dataset_directory_sha256": (
            corrected_result.history_dataset_directory_sha256
        ),
        "github_cohort_created_at_cutoff": cohort_cutoff,
        "input_paths": corrected_result.output_paths,
        "input_file_sha256s": corrected_result.output_file_sha256s,
        "input_row_counts": corrected_result.output_row_counts,
        "input_row_manifest_evidence_hashes": (
            corrected_result.output_row_manifest_evidence_hashes
        ),
        "event_universes": event_universes(),
        "measurement_definitions": measurement_definitions(),
        "quality_gates": S5_MEASUREMENT_GATES,
        "limitations": tuple(
            sorted(
                (
                    (
                        "All historical repository and BTC periods are outcome-aware "
                        "and nonqualifying."
                    ),
                    "Eight accepted GitHub events lack verified local source inclusion.",
                    (
                        "Historical GitHub metadata is a current snapshot, not a "
                        "revision-time archive."
                    ),
                    "Identity aliases are not retroactively merged with a current mailmap.",
                    (
                        "Monthly counts can reflect governance workflow changes rather "
                        "than economic demand."
                    ),
                    (
                        "No GitHub review-event history has been acquired, so review "
                        "continuity is ineligible."
                    ),
                    (
                        "No market value or return may be read while building or "
                        "executing measurements."
                    ),
                    "Release signature presence is not cryptographic signature verification.",
                    (
                        "Release continuity remains candidate-ineligible until signer "
                        "identity is proven."
                    ),
                    (
                        "Source-component breadth measures touched path groups, not "
                        "code quality or impact."
                    ),
                    (
                        "The 479 unresolved first-parent merges remain an explicit "
                        "coverage limitation."
                    ),
                    (
                        "The seven-day availability lag is conservative and not "
                        "evidence of optimality."
                    ),
                    "Two many-to-one source-link groups require separate event and commit counts.",
                    "A measurement pass cannot create a strategy, signal, position, or order.",
                    "Prospective validation and future holdout remain sealed.",
                    "Qualified strategies, trading authority, and real net profit remain zero.",
                )
            )
        ),
    }
    return build_hashed(
        S5AcceptedDevelopmentMeasurementProtocolV1,
        "protocol_evidence_hash",
        values,
    )


def write_protocol(
    path: Path,
    protocol: S5AcceptedDevelopmentMeasurementProtocolV1,
) -> None:
    if path.exists():
        raise ValueError(f"S5 measurement protocol already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5AcceptedDevelopmentMeasurementProtocolV1.model_validate_json(serialized) != protocol:
        raise ValueError("S5 measurement protocol did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the S5 accepted-development measurement protocol."
    )
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "source_rows_parsed=0 git_processes=0 network=0 market_values=0 "
            "returns=0 candidates=0 signals=0 orders=0",
            flush=True,
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
