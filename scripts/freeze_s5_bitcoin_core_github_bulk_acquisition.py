from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (  # noqa: E402
    S5_GITHUB_BULK_GATE_IDS,
    S5GitHubBulkAcquisitionProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_NEXT,
)
from aurex.backtest_engine.s5_bitcoin_core_github_preflight_correction import (  # noqa: E402
    S5_GITHUB_PREFLIGHT_CORRECTED_PASS,
    S5GitHubPreflightCorrectedResultAuditV2,
    S5GitHubPreflightCorrectedResultV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s5_bitcoin_core_github_bulk.py")
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_bulk_acquisition.py")
PREFLIGHT_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_corrected_result_v2.json"
)
PREFLIGHT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_preflight_corrected_result_audit_v2.json"
)
READINESS_RESULT_PATH = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v33.json"
)
READINESS_AUDIT_PATH = Path("data/evidence/aurex_strategy_factory_readiness_current_audit_v33.json")


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
                PREFLIGHT_RESULT_PATH,
                PREFLIGHT_AUDIT_PATH,
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


def load_inputs() -> tuple[
    S5GitHubPreflightCorrectedResultV2,
    S5GitHubPreflightCorrectedResultAuditV2,
    StrategyFactoryReadinessResult,
]:
    corrected = S5GitHubPreflightCorrectedResultV2.model_validate_json(
        PREFLIGHT_RESULT_PATH.read_text(encoding="utf-8")
    )
    corrected_audit = S5GitHubPreflightCorrectedResultAuditV2.model_validate_json(
        PREFLIGHT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        READINESS_RESULT_PATH.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        READINESS_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        not evidence_hash_valid(corrected, "result_evidence_hash")
        or not evidence_hash_valid(corrected_audit, "audit_evidence_hash")
        or corrected_audit.result_file_sha256 != file_sha256(PREFLIGHT_RESULT_PATH)
        or corrected_audit.result_evidence_hash != corrected.result_evidence_hash
        or corrected_audit.reconstructed_exactly is not True
        or corrected.decision != S5_GITHUB_PREFLIGHT_CORRECTED_PASS
        or corrected.next_authorization != S5_GITHUB_PREFLIGHT_NEXT
        or corrected.passed_gate_count != 14
        or corrected.failed_gate_count != 0
        or corrected.terminal_record_count != 24_012
        or corrected.bulk_request_page_count_at_100 != 241
        or corrected.additional_network_request_count != 0
        or corrected.authorizes_bulk_acquisition_protocol_design is not True
        or corrected.authorizes_bulk_metadata_acquisition_now is not False
        or corrected.btc_market_values_read != 0
        or corrected.returns_calculated != 0
        or corrected.orders_submitted != 0
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_file_sha256 != file_sha256(READINESS_RESULT_PATH)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or readiness.strategy_research_ready is not True
        or readiness.qualified_strategy_count != 0
        or readiness.orders_submitted != 0
        or readiness.real_net_profit_usd != "0"
    )
    if changed:
        raise ValueError("S5 GitHub bulk predecessor lineage changed")
    return corrected, corrected_audit, readiness


def build_protocol(*, frozen_at: datetime) -> S5GitHubBulkAcquisitionProtocol:
    corrected, corrected_audit, readiness = load_inputs()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "corrected_preflight_result_evidence_hash": corrected.result_evidence_hash,
        "corrected_preflight_audit_evidence_hash": corrected_audit.audit_evidence_hash,
        "readiness_v33_result_evidence_hash": readiness.result_evidence_hash,
        "source_bindings": source_bindings(),
        "cohort_created_at_cutoff": frozen_at,
        "required_pull_fields": (
            "number",
            "node_id",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "merged_at",
            "head.sha",
            "base.ref",
            "base.sha",
            "user",
        ),
        "required_gate_ids": S5_GITHUB_BULK_GATE_IDS,
        "limitations": tuple(
            sorted(
                (
                    "This protocol authorizes one bounded logical bulk acquisition only.",
                    "Each page receives one request attempt; any request failure stops the run.",
                    "Existing valid contiguous page artifacts may be resumed without "
                    "rerequesting them.",
                    "A process interruption after request dispatch can require a failure audit.",
                    "The all-state query prevents state transitions from changing page membership.",
                    "A base-branch change or record mutation can still affect pagination.",
                    "Records created after the frozen cutoff are preserved but excluded "
                    "from the cohort.",
                    "Merged-only filtering and Git second-parent matching are deferred "
                    "to normalization.",
                    "Current GitHub metadata cannot prove preservation of deleted "
                    "historical records.",
                    "Shared-IP and secondary rate limits can extend the run beyond five hours.",
                    "No Authorization header, token, environment proxy, redirect, or "
                    "concurrency is used.",
                    "No BTC value, parameter, return, candidate, signal, or order is permitted.",
                    "No paper, Testnet strategy, production, live, real-capital, or "
                    "profit authority exists.",
                    "A transport pass cannot establish source completeness or predictive edge.",
                    "Raw public account identifiers are evidence inputs, not trading "
                    "features by default.",
                )
            )
        ),
    }
    provisional = S5GitHubBulkAcquisitionProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5GitHubBulkAcquisitionProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5GitHubBulkAcquisitionProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite frozen S5 GitHub bulk protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub bulk protocol transaction exists: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkAcquisitionProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 GitHub bulk protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or check the S5 GitHub bulk protocol.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.check:
            stored = S5GitHubBulkAcquisitionProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            if stored != build_protocol(frozen_at=stored.frozen_at):
                raise ValueError("Stored S5 GitHub bulk protocol changed")
            print(f"PASS {stored.protocol_evidence_hash}")
            return 0
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_atomic(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "requests=0 metadata=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
