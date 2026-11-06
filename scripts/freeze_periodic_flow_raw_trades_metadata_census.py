from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_daily_cross_source import (  # noqa: E402
    Q1_DAILY_CROSS_PASS_AUTHORIZATION,
    Q1_DAILY_CROSS_PASS_DECISION,
    PeriodicFlowDailyCrossSourceAudit,
    PeriodicFlowDailyCrossSourceResult,
    audit_daily_cross_audit,
    audit_daily_cross_result,
)
from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    RawTradesMetadataCensusProtocol,
    audit_raw_trades_protocol,
    build_raw_trades_protocol,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PARENT_RESULT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_result_v1.json"
)
DEFAULT_PARENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_audit_v1.json"
)
DEFAULT_READINESS_RESULT = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v6.json"
)
DEFAULT_READINESS_AUDIT = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v6.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_raw_trades_metadata_census.py"
)
SCRIPT_PATH = Path("scripts/freeze_periodic_flow_raw_trades_metadata_census.py")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_contract_hash(paths: tuple[Path, ...]) -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                path.as_posix(): file_sha256(PROJECT_ROOT / path)
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash((MODULE_PATH, SCRIPT_PATH))


def load_inputs(
    *,
    parent_result_path: Path,
    parent_audit_path: Path,
    readiness_result_path: Path,
    readiness_audit_path: Path,
) -> tuple[
    PeriodicFlowDailyCrossSourceResult,
    PeriodicFlowDailyCrossSourceAudit,
    StrategyFactoryReadinessResult,
    StrategyFactoryReadinessAudit,
]:
    parent = PeriodicFlowDailyCrossSourceResult.model_validate_json(
        parent_result_path.read_text(encoding="utf-8")
    )
    parent_audit = PeriodicFlowDailyCrossSourceAudit.model_validate_json(
        parent_audit_path.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        readiness_result_path.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        readiness_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_daily_cross_result(parent)
        or not audit_daily_cross_audit(parent_audit)
        or parent_audit.result_file_sha256 != file_sha256(parent_result_path)
        or parent_audit.result_evidence_hash != parent.result_evidence_hash
        or parent.decision != Q1_DAILY_CROSS_PASS_DECISION
        or parent.next_authorization != Q1_DAILY_CROSS_PASS_AUTHORIZATION
        or not parent.authorizes_usdm_raw_trades_metadata_census_protocol
        or parent.authorizes_paper_operation
        or parent.authorizes_testnet_strategy_orders
        or parent.authorizes_production
        or parent.authorizes_live
        or not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_file_sha256 != file_sha256(readiness_result_path)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or not readiness.strategy_research_ready
        or readiness.strategy_candidates_created != 0
        or readiness.orders_submitted != 0
    ):
        raise ValueError("Q1 raw-trades census parent authority is not intact")
    return parent, parent_audit, readiness, readiness_audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    parent_result_path: Path,
    parent_audit_path: Path,
    readiness_result_path: Path,
    readiness_audit_path: Path,
) -> RawTradesMetadataCensusProtocol:
    parent, parent_audit, readiness, readiness_audit = load_inputs(
        parent_result_path=parent_result_path,
        parent_audit_path=parent_audit_path,
        readiness_result_path=readiness_result_path,
        readiness_audit_path=readiness_audit_path,
    )
    return build_raw_trades_protocol(
        frozen_at=frozen_at,
        parent_result_file_sha256=file_sha256(parent_result_path),
        parent_result_evidence_hash=parent.result_evidence_hash,
        parent_audit_file_sha256=file_sha256(parent_audit_path),
        parent_audit_evidence_hash=parent_audit.audit_evidence_hash,
        readiness_result_evidence_hash=readiness.result_evidence_hash,
        readiness_audit_evidence_hash=readiness_audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        source_semantics=(
            "ARCHIVE_FAMILY_USDM_MONTHLY_RAW_TRADES",
            "MARKET_TRADES_ONLY_EXCLUDING_INSURANCE_FUND_AND_ADL",
            "PRICE_QUANTITY_AND_QUOTE_QUANTITY_FORBIDDEN_IN_THIS_STAGE",
        ),
        limitations=(
            "A complete checksum census establishes publication coverage only.",
            "Archive payload, row schema, timestamps, and continuity remain untested.",
            "Checksum text contains no price, quantity, or quote quantity values.",
            "Development and validation market outcomes remain unopened.",
            "No threshold, horizon, signal, strategy, or candidate is created.",
            "A pass permits only a separate one-month payload protocol.",
            "Paper and Testnet strategy-order authority remain false.",
            "Production, live, real-capital authority, and profit remain false.",
        ),
    )


def write_protocol(path: Path, protocol: RawTradesMetadataCensusProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if RawTradesMetadataCensusProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 raw-trades protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale protocol transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Q1 USD-M raw-trades checksum census protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--parent-result", type=Path, default=DEFAULT_PARENT_RESULT)
    parser.add_argument("--parent-audit", type=Path, default=DEFAULT_PARENT_AUDIT)
    parser.add_argument(
        "--readiness-result", type=Path, default=DEFAULT_READINESS_RESULT
    )
    parser.add_argument(
        "--readiness-audit", type=Path, default=DEFAULT_READINESS_AUDIT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = RawTradesMetadataCensusProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_protocol(
                frozen_at=stored.frozen_at,
                parent_result_path=args.parent_result,
                parent_audit_path=args.parent_audit,
                readiness_result_path=args.readiness_result,
                readiness_audit_path=args.readiness_audit,
            )
            if stored != expected or not audit_raw_trades_protocol(stored):
                raise ValueError("Stored Q1 raw-trades protocol changed")
            print(
                f"PASS {args.output} {stored.protocol_evidence_hash} "
                "targets=72 requests=0 payloads=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite frozen protocol: {args.output}")
        protocol = authoritative_protocol(
            frozen_at=datetime.now(UTC),
            parent_result_path=args.parent_result,
            parent_audit_path=args.parent_audit,
            readiness_result_path=args.readiness_result,
            readiness_audit_path=args.readiness_audit,
        )
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "targets=72 requests=0 payloads=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
