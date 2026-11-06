from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_development_charter import (  # noqa: E402
    S5BitcoinCoreDevelopmentCharter,
    S5BitcoinCoreDevelopmentCharterAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5_GITHUB_BULK_NEXT,
    S5_GITHUB_BULK_PASS,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkProtocolAudit,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (  # noqa: E402
    S5GitHubBulkFinalResultAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentV4,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (  # noqa: E402
    S5_GITHUB_NORMALIZATION_GATE_IDS,
    S5GitHubNormalizationProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (  # noqa: E402
    S5_CENSUS_NEXT,
    S5_CENSUS_PASS,
    S5BitcoinCoreHistoryCensusProtocol,
    S5BitcoinCoreHistoryCensusProtocolAudit,
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5_HISTORY_NEXT,
    S5_HISTORY_PASS,
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (  # noqa: E402
    S5BitcoinCoreHistoryPayloadResultAuditV2,
    S5BitcoinCoreHistoryPayloadResultV2,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_normalization.py"
)
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_normalization.py")

CHARTER_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_v1.json")
CHARTER_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_development_charter_audit_v1.json"
)
HISTORY_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_v2.json"
)
HISTORY_AUDIT_PATH = Path(
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
CENSUS_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_census_result_audit_v1.json"
)
BULK_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json"
)
BULK_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
MONOTONIC_AMENDMENT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.json"
)
MONOTONIC_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_audit_v4.json"
)
BULK_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_github_bulk_result_v4.json")
BULK_FINAL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_final_result_audit_v4.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v34.json"
)
READINESS_AUDIT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v34.json"
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
                CHARTER_PATH,
                CHARTER_AUDIT_PATH,
                HISTORY_RESULT_PATH,
                HISTORY_AUDIT_PATH,
                CENSUS_PROTOCOL_PATH,
                CENSUS_PROTOCOL_AUDIT_PATH,
                CENSUS_RESULT_PATH,
                CENSUS_AUDIT_PATH,
                BULK_PROTOCOL_PATH,
                BULK_PROTOCOL_AUDIT_PATH,
                MONOTONIC_AMENDMENT_PATH,
                MONOTONIC_AUDIT_PATH,
                BULK_RESULT_PATH,
                BULK_FINAL_AUDIT_PATH,
                READINESS_RESULT_PATH,
                READINESS_AUDIT_PATH,
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
    charter = S5BitcoinCoreDevelopmentCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )
    charter_audit = S5BitcoinCoreDevelopmentCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )
    history = S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(
        HISTORY_RESULT_PATH.read_text(encoding="utf-8")
    )
    history_audit = S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate_json(
        HISTORY_AUDIT_PATH.read_text(encoding="utf-8")
    )
    census_protocol = S5BitcoinCoreHistoryCensusProtocol.model_validate_json(
        CENSUS_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    census_protocol_audit = S5BitcoinCoreHistoryCensusProtocolAudit.model_validate_json(
        CENSUS_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    census = S5BitcoinCoreHistoryCensusResult.model_validate_json(
        CENSUS_RESULT_PATH.read_text(encoding="utf-8")
    )
    census_audit = S5BitcoinCoreHistoryCensusResultAudit.model_validate_json(
        CENSUS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    bulk_protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        BULK_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    bulk_protocol_audit = S5GitHubBulkProtocolAudit.model_validate_json(
        BULK_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    amendment = S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate_json(
        MONOTONIC_AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    amendment_audit = S5GitHubBulkMonotonicTerminalAmendmentAuditV4.model_validate_json(
        MONOTONIC_AUDIT_PATH.read_text(encoding="utf-8")
    )
    bulk = S5GitHubBulkResult.model_validate_json(
        BULK_RESULT_PATH.read_text(encoding="utf-8")
    )
    bulk_audit = S5GitHubBulkFinalResultAuditV4.model_validate_json(
        BULK_FINAL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )

    changed = (
        charter_audit.charter_file_sha256 != file_sha256(CHARTER_PATH)
        or charter_audit.charter_evidence_hash != charter.charter_evidence_hash
        or history_audit.result_file_sha256 != file_sha256(HISTORY_RESULT_PATH)
        or history_audit.result_evidence_hash != history.result_evidence_hash
        or history.decision != S5_HISTORY_PASS
        or history.next_authorization != S5_HISTORY_NEXT
        or census_protocol_audit.protocol_file_sha256
        != file_sha256(CENSUS_PROTOCOL_PATH)
        or census_protocol_audit.protocol_evidence_hash
        != census_protocol.protocol_evidence_hash
        or census_audit.result_file_sha256 != file_sha256(CENSUS_RESULT_PATH)
        or census_audit.result_evidence_hash != census.result_evidence_hash
        or census.decision != S5_CENSUS_PASS
        or census.next_authorization != S5_CENSUS_NEXT
        or bulk_protocol_audit.protocol_file_sha256 != file_sha256(BULK_PROTOCOL_PATH)
        or bulk_protocol_audit.protocol_evidence_hash
        != bulk_protocol.protocol_evidence_hash
        or amendment_audit.amendment_file_sha256
        != file_sha256(MONOTONIC_AMENDMENT_PATH)
        or amendment_audit.amendment_evidence_hash != amendment.amendment_evidence_hash
        or bulk_audit.result_file_sha256 != file_sha256(BULK_RESULT_PATH)
        or bulk_audit.result_evidence_hash != bulk.result_evidence_hash
        or bulk_audit.amendment_evidence_hash != amendment.amendment_evidence_hash
        or bulk.decision != S5_GITHUB_BULK_PASS
        or bulk.next_authorization != S5_GITHUB_BULK_NEXT
        or readiness_audit.result_file_sha256 != file_sha256(READINESS_RESULT_PATH)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
        or history.dataset_directory_sha256 != census.dataset_directory_sha256
        or history.source_cutoff_commit != census.source_cutoff_commit
        or census.first_parent_commit_count != 17_543
        or census.root_commit_count != 1
        or census.single_parent_commit_count != 821
        or census.merge_commit_count != 16_721
        or census.octopus_merge_commit_count != 0
        or census.recognized_pull_merge_count != 7_961
        or census.unrecognized_merge_count != 8_760
        or census.distinct_pull_request_count != 7_961
        or bulk.terminal_page_count != 245
        or bulk.raw_record_count != 24_407
        or bulk.cohort_record_count != 24_398
        or bulk.post_cutoff_record_count != 9
        or bulk.duplicate_pull_number_count != 0
        or bulk.failed_gate_count != 0
        or bulk.btc_market_values_read != 0
        or bulk.returns_calculated != 0
        or bulk.orders_submitted != 0
        or bulk_audit.page_count != 245
        or bulk_audit.cohort_record_count != 24_398
        or bulk_audit.every_page_file_hash_reverified is not True
        or bulk_audit.every_response_body_hash_reverified is not True
    )
    if changed:
        raise ValueError("S5 GitHub normalization predecessor lineage changed")
    return {
        "charter": charter,
        "charter_audit": charter_audit,
        "history": history,
        "history_audit": history_audit,
        "census": census,
        "census_audit": census_audit,
        "bulk_protocol": bulk_protocol,
        "bulk_protocol_audit": bulk_protocol_audit,
        "amendment": amendment,
        "amendment_audit": amendment_audit,
        "bulk": bulk,
        "bulk_audit": bulk_audit,
        "readiness": readiness,
        "readiness_audit": readiness_audit,
    }


def build_protocol(*, frozen_at: datetime) -> S5GitHubNormalizationProtocol:
    lineage = load_lineage()
    bindings = source_bindings()
    charter = lineage["charter"]
    charter_audit = lineage["charter_audit"]
    history = lineage["history"]
    history_audit = lineage["history_audit"]
    census = lineage["census"]
    census_audit = lineage["census_audit"]
    bulk_protocol = lineage["bulk_protocol"]
    bulk_protocol_audit = lineage["bulk_protocol_audit"]
    amendment = lineage["amendment"]
    amendment_audit = lineage["amendment_audit"]
    bulk = lineage["bulk"]
    bulk_audit = lineage["bulk_audit"]
    readiness = lineage["readiness"]
    readiness_audit = lineage["readiness_audit"]
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": bindings,
        "source_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in bindings)
        ),
        "readiness_v34_result_evidence_hash": readiness.result_evidence_hash,
        "readiness_v34_audit_evidence_hash": readiness_audit.audit_evidence_hash,
        "charter_evidence_hash": charter.charter_evidence_hash,
        "charter_audit_evidence_hash": charter_audit.audit_evidence_hash,
        "history_result_evidence_hash": history.result_evidence_hash,
        "history_result_audit_evidence_hash": history_audit.audit_evidence_hash,
        "census_result_evidence_hash": census.result_evidence_hash,
        "census_result_audit_evidence_hash": census_audit.audit_evidence_hash,
        "bulk_protocol_evidence_hash": bulk_protocol.protocol_evidence_hash,
        "bulk_protocol_audit_evidence_hash": bulk_protocol_audit.audit_evidence_hash,
        "monotonic_amendment_evidence_hash": amendment.amendment_evidence_hash,
        "monotonic_amendment_audit_evidence_hash": amendment_audit.audit_evidence_hash,
        "bulk_result_evidence_hash": bulk.result_evidence_hash,
        "bulk_final_audit_evidence_hash": bulk_audit.audit_evidence_hash,
        "history_dataset_directory_sha256": history.dataset_directory_sha256,
        "source_cutoff_commit": history.source_cutoff_commit,
        "bulk_page_manifest_evidence_hash": universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in bulk.page_bindings)
        ),
        "cohort_created_at_cutoff": bulk_protocol.cohort_created_at_cutoff,
        "required_gate_ids": S5_GITHUB_NORMALIZATION_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This protocol freezes source normalization and measurable "
                    "completeness gates only.",
                    "GitHub's current list endpoint cannot prove that every deleted "
                    "historical record is preserved.",
                    "A complete match of recognized Git references is a sentinel, "
                    "not proof against unknown deleted records.",
                    "GitHub merged_at is an event-time proxy and not an archived "
                    "ingestion timestamp.",
                    "Mutable post-event GitHub fields can reflect state observed "
                    "after the historical event.",
                    "Git author, committer, and timestamp headers remain prohibited in this stage.",
                    "Unrecognized Git merges can be branch or legacy integration events "
                    "and are never guessed to be pull requests.",
                    "A GitHub user ID is the primary account key but does not prove one "
                    "unique human contributor.",
                    "Distinct GitHub user IDs are not alias-merged and can overstate "
                    "human breadth.",
                    "Shared, renamed, deleted, automated, or organizational accounts "
                    "can understate or distort human breadth.",
                    "Bots are classified only from public user type or the exact login "
                    "suffix rule.",
                    "Passing this stage establishes a reproducible accepted-event "
                    "dataset, not predictive usefulness.",
                    "No development feature, threshold, lookback, signal, or strategy "
                    "is defined here.",
                    "No BTC market value, return, candidate, paper trade, Testnet "
                    "strategy order, or live order is permitted.",
                    "Source failure stops S5 pending a separately frozen correction; "
                    "it cannot be relaxed after inspection.",
                    "All result datasets must be independently reconstructed byte for "
                    "byte before measurement is authorized.",
                )
            )
        ),
    }
    provisional = S5GitHubNormalizationProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5GitHubNormalizationProtocol.model_validate(complete)


def output_paths() -> tuple[Path, ...]:
    fields = S5GitHubNormalizationProtocol.model_fields
    return (
        Path(fields["pull_output_path"].default),
        Path(fields["mapping_output_path"].default),
        Path(fields["unresolved_output_path"].default),
        Path(fields["result_path"].default),
    )


def ensure_outputs_absent() -> None:
    existing = tuple(path.as_posix() for path in output_paths() if path.exists())
    if existing:
        raise ValueError(f"S5 normalization outputs already exist: {existing}")


def write_atomic(path: Path, protocol: S5GitHubNormalizationProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 normalization protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 normalization protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5GitHubNormalizationProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 normalization protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or check the S5 GitHub normalization protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5GitHubNormalizationProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_protocol(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 GitHub normalization protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    ensure_outputs_absent()
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(f"FROZEN {args.output} {protocol.protocol_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
