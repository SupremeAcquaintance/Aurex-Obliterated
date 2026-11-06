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
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (  # noqa: E402
    S5GitHubBulkFinalResultAuditV4,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (  # noqa: E402
    S5GitHubNormalizationProtocol,
    S5GitHubNormalizationProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5_GITHUB_NORMALIZATION_FAILURE_NEXT,
    S5_GITHUB_NORMALIZATION_STOP,
    S5GitHubNormalizationExecutionContract,
    S5GitHubNormalizationExecutionContractAudit,
    S5GitHubNormalizationResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure import (  # noqa: E402
    S5_NORMALIZATION_FAILURE_GATE_IDS,
    S5NormalizationFailureAdjudicationProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadResultAuditV2,
    S5BitcoinCoreHistoryPayloadResultV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_normalization_failure_adjudication_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_normalization_failure.py"
)
SCRIPT_PATH = Path(
    "scripts/freeze_s5_bitcoin_core_github_normalization_failure_adjudication.py"
)
NORMALIZATION_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
)
NORMALIZATION_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_protocol_audit_v1.json"
)
EXECUTION_CONTRACT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_v1.json"
)
EXECUTION_CONTRACT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_audit_v1.json"
)
FAILED_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
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
HISTORY_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_v2.json"
)
HISTORY_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_audit_v2.json"
)


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
                NORMALIZATION_PROTOCOL_AUDIT_PATH,
                EXECUTION_CONTRACT_PATH,
                EXECUTION_CONTRACT_AUDIT_PATH,
                FAILED_RESULT_PATH,
                BULK_RESULT_PATH,
                BULK_AUDIT_PATH,
                CENSUS_RESULT_PATH,
                CENSUS_AUDIT_PATH,
                HISTORY_RESULT_PATH,
                HISTORY_AUDIT_PATH,
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
    normalization_audit = S5GitHubNormalizationProtocolAudit.model_validate_json(
        NORMALIZATION_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    contract = S5GitHubNormalizationExecutionContract.model_validate_json(
        EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    contract_audit = S5GitHubNormalizationExecutionContractAudit.model_validate_json(
        EXECUTION_CONTRACT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    failed = S5GitHubNormalizationResult.model_validate_json(
        FAILED_RESULT_PATH.read_text(encoding="utf-8")
    )
    bulk = S5GitHubBulkResult.model_validate_json(
        BULK_RESULT_PATH.read_text(encoding="utf-8")
    )
    bulk_audit = S5GitHubBulkFinalResultAuditV4.model_validate_json(
        BULK_AUDIT_PATH.read_text(encoding="utf-8")
    )
    census = S5BitcoinCoreHistoryCensusResult.model_validate_json(
        CENSUS_RESULT_PATH.read_text(encoding="utf-8")
    )
    census_audit = S5BitcoinCoreHistoryCensusResultAudit.model_validate_json(
        CENSUS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    history = S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(
        HISTORY_RESULT_PATH.read_text(encoding="utf-8")
    )
    history_audit = S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate_json(
        HISTORY_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        normalization_audit.protocol_file_sha256
        != file_sha256(NORMALIZATION_PROTOCOL_PATH)
        or normalization_audit.protocol_evidence_hash
        != normalization.protocol_evidence_hash
        or contract_audit.contract_file_sha256 != file_sha256(EXECUTION_CONTRACT_PATH)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or failed.execution_contract_evidence_hash != contract.contract_evidence_hash
        or failed.decision != S5_GITHUB_NORMALIZATION_STOP
        or failed.next_authorization != S5_GITHUB_NORMALIZATION_FAILURE_NEXT
        or failed.passed_gate_count != 13
        or failed.failed_gate_count != 4
        or failed.recognized_pull_merge_count != 7_961
        or failed.recognized_exact_mapping_count != 7_878
        or failed.accepted_github_pull_count != 16_279
        or failed.total_exact_mapping_count != 16_167
        or failed.unmatched_accepted_github_pull_count != 112
        or failed.ambiguous_git_merge_count != 1
        or failed.unresolved_git_merge_count != 554
        or failed.btc_market_values_read != 0
        or failed.returns_calculated != 0
        or failed.orders_submitted != 0
        or bulk_audit.result_file_sha256 != file_sha256(BULK_RESULT_PATH)
        or bulk_audit.result_evidence_hash != bulk.result_evidence_hash
        or census_audit.result_file_sha256 != file_sha256(CENSUS_RESULT_PATH)
        or census_audit.result_evidence_hash != census.result_evidence_hash
        or history_audit.result_file_sha256 != file_sha256(HISTORY_RESULT_PATH)
        or history_audit.result_evidence_hash != history.result_evidence_hash
        or normalization.bulk_result_evidence_hash != bulk.result_evidence_hash
        or normalization.census_result_evidence_hash != census.result_evidence_hash
        or normalization.history_result_evidence_hash != history.result_evidence_hash
    )
    if changed:
        raise ValueError("S5 normalization failure lineage changed")
    return {
        "normalization": normalization,
        "normalization_audit": normalization_audit,
        "contract": contract,
        "contract_audit": contract_audit,
        "failed": failed,
        "bulk": bulk,
        "bulk_audit": bulk_audit,
        "census": census,
        "census_audit": census_audit,
        "history": history,
        "history_audit": history_audit,
    }


def build_protocol(
    *, frozen_at: datetime
) -> S5NormalizationFailureAdjudicationProtocol:
    lineage = load_lineage()
    bindings = source_bindings()
    normalization = lineage["normalization"]
    normalization_audit = lineage["normalization_audit"]
    contract = lineage["contract"]
    contract_audit = lineage["contract_audit"]
    failed = lineage["failed"]
    bulk = lineage["bulk"]
    bulk_audit = lineage["bulk_audit"]
    census = lineage["census"]
    census_audit = lineage["census_audit"]
    history = lineage["history"]
    history_audit = lineage["history_audit"]
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": bindings,
        "source_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(binding.model_dump(mode="json") for binding in bindings)
        ),
        "normalization_protocol_evidence_hash": normalization.protocol_evidence_hash,
        "normalization_protocol_audit_evidence_hash": (
            normalization_audit.audit_evidence_hash
        ),
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "failed_result_file_sha256": file_sha256(FAILED_RESULT_PATH),
        "failed_result_evidence_hash": failed.result_evidence_hash,
        "bulk_result_evidence_hash": bulk.result_evidence_hash,
        "bulk_final_audit_evidence_hash": bulk_audit.audit_evidence_hash,
        "census_result_evidence_hash": census.result_evidence_hash,
        "census_result_audit_evidence_hash": census_audit.audit_evidence_hash,
        "history_result_evidence_hash": history.result_evidence_hash,
        "history_result_audit_evidence_hash": history_audit.audit_evidence_hash,
        "required_gate_ids": S5_NORMALIZATION_FAILURE_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This is a diagnostic protocol and the original normalization STOP "
                    "remains binding.",
                    "The preserved GitHub pages are scoped to pull requests whose "
                    "current base is master.",
                    "A missing pull number cannot distinguish deletion from a different "
                    "base without new metadata.",
                    "GitHub merge_commit_sha is inspected only as a diagnostic and "
                    "cannot alter prior mappings.",
                    "Full Git reachability at the frozen cutoff does not establish "
                    "public availability time.",
                    "Git author, committer, message, and timestamp fields remain prohibited.",
                    "Current GitHub metadata can reflect mutations after the historical "
                    "merge event.",
                    "Fixed one, seven, and thirty day windows describe cutoff proximity only.",
                    "A diagnostic category is not evidence of predictive edge or strategy value.",
                    "No network request, direct pull lookup, or repository fetch is authorized.",
                    "No market value, parameter, return, candidate, or order is authorized.",
                    "Any correction requires a new frozen protocol and independent audit.",
                )
            )
        ),
    }
    provisional = S5NormalizationFailureAdjudicationProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5NormalizationFailureAdjudicationProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5NormalizationFailureAdjudicationProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 failure protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 failure protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5NormalizationFailureAdjudicationProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 failure protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S5 normalization failure audit.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5NormalizationFailureAdjudicationProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_protocol(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 normalization failure protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    if Path(protocol.result_path).exists():
        raise ValueError("S5 normalization failure adjudication result already exists")
    write_atomic(args.output, protocol)
    print(f"FROZEN {args.output} {protocol.protocol_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
