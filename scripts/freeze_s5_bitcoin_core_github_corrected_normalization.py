from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization import (  # noqa: E402
    S5_CORRECTED_NORMALIZATION_GATE_IDS,
    S5GitHubCorrectedNormalizationProtocolV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (  # noqa: E402
    S5_GITHUB_NORMALIZED_PULL_FIELDS,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5_GITHUB_NORMALIZATION_STOP,
    S5GitHubNormalizationResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure import (  # noqa: E402
    S5NormalizationFailureAdjudicationResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure_audit import (  # noqa: E402
    S5NormalizationFailureAdjudicationResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (  # noqa: E402
    S5_TARGETED_CORRECTION_PASS,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3_execution import (  # noqa: E402
    S5TargetedCompletenessCorrectionResultV3,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3_result_audit import (  # noqa: E402
    S5TargetedCorrectionV3ResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_corrected_normalization_protocol_v2.json"
)
MODEL_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_corrected_normalization.py"
)
SCRIPT_PATH = Path(
    "scripts/freeze_s5_bitcoin_core_github_corrected_normalization.py"
)
FAILED_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
)
FAILURE_RESULT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_result_v1.json"
)
FAILURE_RESULT_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_result_audit_v1.json"
)
TARGETED_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v3.json"
)
TARGETED_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_audit_v3.json"
)
SOURCE_PATHS = (
    Path("data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"),
    Path("data/evidence/s5_bitcoin_core_github_normalization_protocol_audit_v1.json"),
    Path(
        "data/evidence/"
        "s5_bitcoin_core_github_normalization_execution_contract_v1.json"
    ),
    Path(
        "data/evidence/"
        "s5_bitcoin_core_github_normalization_execution_contract_audit_v1.json"
    ),
    FAILED_RESULT_PATH,
    Path(
        "data/evidence/"
        "s5_bitcoin_core_github_normalization_failure_adjudication_protocol_v1.json"
    ),
    Path(
        "data/evidence/"
        "s5_bitcoin_core_github_normalization_failure_adjudication_protocol_audit_v1.json"
    ),
    FAILURE_RESULT_PATH,
    FAILURE_RESULT_AUDIT_PATH,
    Path("data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v1.json"),
    Path("data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v3.json"),
    Path(
        "data/evidence/"
        "s5_bitcoin_core_github_targeted_correction_execution_contract_v3.json"
    ),
    Path(
        "data/evidence/"
        "s5_bitcoin_core_github_targeted_correction_execution_contract_audit_v3.json"
    ),
    TARGETED_RESULT_PATH,
    TARGETED_RESULT_AUDIT_PATH,
)
OUTPUT_PATHS = (
    Path("data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_canonical_merge_mapping_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_target_resolution_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_accepted_source_coverage_v2.jsonl"),
    Path("data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v2.jsonl"),
    Path(
        "data/evidence/"
        "s5_bitcoin_core_github_corrected_normalization_result_v2.json"
    ),
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def bindings(paths: tuple[Path, ...]) -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(
            path=path.as_posix(),
            file_sha256=file_sha256(PROJECT_ROOT / path),
        )
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def manifest_hash(rows: tuple[S5HistoryBinding, ...]) -> str:
    return universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in rows)
    )


def builder_contract_hash() -> str:
    return manifest_hash(bindings((MODEL_PATH, SCRIPT_PATH)))


def load_predecessors() -> tuple[
    S5GitHubNormalizationResult,
    S5NormalizationFailureAdjudicationResult,
    S5NormalizationFailureAdjudicationResultAudit,
    S5TargetedCompletenessCorrectionResultV3,
    S5TargetedCorrectionV3ResultAudit,
]:
    failed = S5GitHubNormalizationResult.model_validate_json(
        FAILED_RESULT_PATH.read_text(encoding="utf-8")
    )
    failure = S5NormalizationFailureAdjudicationResult.model_validate_json(
        FAILURE_RESULT_PATH.read_text(encoding="utf-8")
    )
    failure_audit = S5NormalizationFailureAdjudicationResultAudit.model_validate_json(
        FAILURE_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    targeted = S5TargetedCompletenessCorrectionResultV3.model_validate_json(
        TARGETED_RESULT_PATH.read_text(encoding="utf-8")
    )
    targeted_audit = S5TargetedCorrectionV3ResultAudit.model_validate_json(
        TARGETED_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        failed.decision != S5_GITHUB_NORMALIZATION_STOP
        or failure.failed_result_evidence_hash != failed.result_evidence_hash
        or failure_audit.result_file_sha256 != file_sha256(FAILURE_RESULT_PATH)
        or failure_audit.result_evidence_hash != failure.result_evidence_hash
        or targeted.decision != S5_TARGETED_CORRECTION_PASS
        or targeted_audit.result_file_sha256 != file_sha256(TARGETED_RESULT_PATH)
        or targeted_audit.result_evidence_hash != targeted.result_evidence_hash
        or targeted_audit.response_count != 194
        or targeted_audit.github_requests_executed != 0
    ):
        raise ValueError("S5 corrected normalization predecessor lineage changed")
    return failed, failure, failure_audit, targeted, targeted_audit


def build_protocol(*, frozen_at: datetime) -> S5GitHubCorrectedNormalizationProtocolV2:
    failed, failure, failure_audit, targeted, targeted_audit = load_predecessors()
    sources = bindings(SOURCE_PATHS)
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": sources,
        "source_binding_manifest_evidence_hash": manifest_hash(sources),
        "failed_normalization_result_evidence_hash": failed.result_evidence_hash,
        "failure_adjudication_result_evidence_hash": failure.result_evidence_hash,
        "failure_adjudication_result_audit_evidence_hash": (
            failure_audit.audit_evidence_hash
        ),
        "targeted_correction_result_evidence_hash": targeted.result_evidence_hash,
        "targeted_correction_result_audit_evidence_hash": (
            targeted_audit.audit_evidence_hash
        ),
        "normalized_pull_fields": S5_GITHUB_NORMALIZED_PULL_FIELDS,
        "required_gate_ids": S5_CORRECTED_NORMALIZATION_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "The failed v1 normalization and its STOP remain immutable evidence.",
                    "Protocol counts were informed by disclosed post-acquisition source analysis.",
                    (
                        "Current targeted metadata is supplemental and never overwrites "
                        "frozen bulk metadata."
                    ),
                    "Eight recognized PR endpoints return 404 and remain unresolved.",
                    (
                        "Eight GitHub-accepted pulls lack exact local inclusion evidence "
                        "at the cutoff."
                    ),
                    "A source link does not imply exclusive canonical ownership of a Git merge.",
                    "Two disclosed pull groups share exact source identities and remain explicit.",
                    (
                        "GitHub accepted pulls and Git first-parent integrations are "
                        "different universes."
                    ),
                    "GitHub merged_at and Git committer time are event proxies with source labels.",
                    "Current GitHub responses are not historical snapshots from the event date.",
                    "A 404 is endpoint evidence at acquisition time, not proof a PR never existed.",
                    "No unresolved identity may be guessed or imputed as an accepted event.",
                    "Normalization success will not establish predictive edge or profitability.",
                    (
                        "No market value, parameter, return, candidate, signal, or order "
                        "is authorized."
                    ),
                    "No paper, Testnet strategy, production, live, or capital authority exists.",
                    "Real net profit remains zero.",
                )
            )
        ),
    }
    provisional = S5GitHubCorrectedNormalizationProtocolV2.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5GitHubCorrectedNormalizationProtocolV2.model_validate(complete)


def write_atomic(path: Path, protocol: S5GitHubCorrectedNormalizationProtocolV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 corrected protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 corrected protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5GitHubCorrectedNormalizationProtocolV2.model_validate_json(serialized) != protocol:
        raise ValueError("S5 corrected normalization protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S5 corrected normalization v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5GitHubCorrectedNormalizationProtocolV2.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_protocol(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 corrected normalization protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    if any(path.exists() or path.with_name(f"{path.name}.part").exists() for path in OUTPUT_PATHS):
        raise ValueError("S5 corrected normalization outputs already exist")
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(f"FROZEN {args.output} {protocol.protocol_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
