from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_metadata_census import (  # noqa: E402
    PeriodicFlowMetadataCensusContract,
    audit_metadata_census_contract,
    build_metadata_census_contract,
)
from aurex.backtest_engine.periodic_flow_spot_charter import (  # noqa: E402
    PERIODIC_FLOW_NEXT_AUTHORIZATION,
    PeriodicFlowSpotCharter,
    PeriodicFlowSpotCharterAudit,
    audit_periodic_flow_spot_charter,
    audit_periodic_flow_spot_charter_audit,
)
from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_CHARTER = Path("data/evidence/periodic_flow_spot_charter_v1.json")
DEFAULT_CHARTER_AUDIT = Path(
    "data/evidence/periodic_flow_spot_charter_audit_v1.json"
)
DEFAULT_READINESS_RESULT = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_result_v4.json"
)
DEFAULT_READINESS_AUDIT = Path(
    "data/evidence/aurex_strategy_factory_readiness_current_audit_v4.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_contract_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_metadata_census.py"
)
SCRIPT_PATH = Path("scripts/freeze_periodic_flow_metadata_census_contract.py")


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
    charter_path: Path,
    charter_audit_path: Path,
    readiness_result_path: Path,
    readiness_audit_path: Path,
) -> tuple[
    PeriodicFlowSpotCharter,
    PeriodicFlowSpotCharterAudit,
    StrategyFactoryReadinessResult,
    StrategyFactoryReadinessAudit,
]:
    charter = PeriodicFlowSpotCharter.model_validate_json(
        charter_path.read_text(encoding="utf-8")
    )
    charter_audit = PeriodicFlowSpotCharterAudit.model_validate_json(
        charter_audit_path.read_text(encoding="utf-8")
    )
    readiness = StrategyFactoryReadinessResult.model_validate_json(
        readiness_result_path.read_text(encoding="utf-8")
    )
    readiness_audit = StrategyFactoryReadinessAudit.model_validate_json(
        readiness_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_periodic_flow_spot_charter(charter)
        or not audit_periodic_flow_spot_charter_audit(charter_audit)
        or charter_audit.charter_file_sha256 != file_sha256(charter_path)
        or charter_audit.charter_evidence_hash != charter.charter_evidence_hash
        or charter.next_authorization != PERIODIC_FLOW_NEXT_AUTHORIZATION
        or charter.authorizes_archive_payload_download
        or charter.authorizes_parameter_definition
        or charter.authorizes_return_testing
        or charter.authorizes_testnet_strategy_orders
        or charter.authorizes_live
    ):
        raise ValueError("Q1 charter or independent audit lineage changed")
    if (
        not audit_readiness_result(readiness)
        or not audit_readiness_audit(readiness_audit)
        or readiness_audit.result_file_sha256 != file_sha256(readiness_result_path)
        or readiness_audit.result_evidence_hash != readiness.result_evidence_hash
        or not readiness.strategy_research_ready
        or readiness.paper_operation_ready
        or readiness.sandbox_strategy_use_ready
        or readiness.production_ready
        or readiness.live_ready
        or readiness.qualified_strategy_count != 0
    ):
        raise ValueError("Q1 census requires intact non-authorizing readiness v4")
    return charter, charter_audit, readiness, readiness_audit


def authoritative_contract(
    *,
    frozen_at: datetime,
    charter_path: Path,
    charter_audit_path: Path,
    readiness_result_path: Path,
    readiness_audit_path: Path,
) -> PeriodicFlowMetadataCensusContract:
    charter, charter_audit, readiness, readiness_audit = load_inputs(
        charter_path=charter_path,
        charter_audit_path=charter_audit_path,
        readiness_result_path=readiness_result_path,
        readiness_audit_path=readiness_audit_path,
    )
    return build_metadata_census_contract(
        frozen_at=frozen_at,
        charter_file_sha256=file_sha256(charter_path),
        charter_evidence_hash=charter.charter_evidence_hash,
        charter_audit_file_sha256=file_sha256(charter_audit_path),
        charter_audit_evidence_hash=charter_audit.audit_evidence_hash,
        readiness_result_evidence_hash=readiness.result_evidence_hash,
        readiness_audit_evidence_hash=readiness_audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=(
            "Only the 144 frozen Binance checksum URLs may receive GET requests.",
            "No archive HEAD or ZIP payload request is permitted by this contract.",
            "Checksum text proves publication identity, not payload quality or edge.",
            "The schema and timestamp register is documentary and awaits payload proof.",
            "No price, quantity, side, signal, trade, PnL, or return may be inspected.",
            "All 144 targets and all 72 paired months must be present to pass.",
            "A pass permits only a separately frozen one-month paired payload protocol.",
            "No candidate, Pine, paper, Testnet strategy-order, production, or live "
            "authority is created.",
        ),
    )


def write_contract(
    path: Path,
    contract: PeriodicFlowMetadataCensusContract,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if PeriodicFlowMetadataCensusContract.model_validate_json(serialized) != contract:
        raise ValueError("Q1 census contract did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 census contract transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-network Q1 metadata census contract."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument(
        "--charter-audit",
        type=Path,
        default=DEFAULT_CHARTER_AUDIT,
    )
    parser.add_argument(
        "--readiness-result",
        type=Path,
        default=DEFAULT_READINESS_RESULT,
    )
    parser.add_argument(
        "--readiness-audit",
        type=Path,
        default=DEFAULT_READINESS_AUDIT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowMetadataCensusContract.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(
                frozen_at=stored.frozen_at,
                charter_path=args.charter,
                charter_audit_path=args.charter_audit,
                readiness_result_path=args.readiness_result,
                readiness_audit_path=args.readiness_audit,
            )
            if stored != expected or not audit_metadata_census_contract(stored):
                raise ValueError("Stored Q1 census contract changed")
            print(f"PASS {args.output} {stored.contract_evidence_hash}", flush=True)
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite frozen Q1 contract: {args.output}")
        contract = authoritative_contract(
            frozen_at=datetime.now(UTC),
            charter_path=args.charter,
            charter_audit_path=args.charter_audit,
            readiness_result_path=args.readiness_result,
            readiness_audit_path=args.readiness_audit,
        )
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            "targets=144 payload_requests=0 market_values=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
