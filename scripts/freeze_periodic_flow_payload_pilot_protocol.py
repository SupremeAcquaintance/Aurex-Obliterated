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
    Q1_CENSUS_PASS_AUTHORIZATION,
    Q1_CENSUS_PASS_DECISION,
    PeriodicFlowMetadataCensusAudit,
    PeriodicFlowMetadataCensusContract,
    PeriodicFlowMetadataCensusResult,
    audit_metadata_census_audit,
    audit_metadata_census_contract,
    audit_metadata_census_result,
)
from aurex.backtest_engine.periodic_flow_payload_pilot import (  # noqa: E402
    Q1_PAYLOAD_PILOT_MONTH,
    PeriodicFlowPayloadPilotProtocol,
    PeriodicFlowPayloadTarget,
    audit_periodic_flow_payload_protocol,
    build_periodic_flow_payload_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_contract_v1.json"
)
DEFAULT_CENSUS_RESULT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_result_v1.json"
)
DEFAULT_CENSUS_AUDIT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_protocol_v1.json"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    paths = (
        PROJECT_ROOT / "scripts" / "freeze_periodic_flow_payload_pilot_protocol.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "periodic_flow_payload_pilot.py",
    )
    return universe_evidence_hash(
        {
            path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
            for path in paths
        }
    )


def load_lineage(
    contract_path: Path,
    result_path: Path,
    audit_path: Path,
) -> tuple[
    PeriodicFlowMetadataCensusContract,
    PeriodicFlowMetadataCensusResult,
    PeriodicFlowMetadataCensusAudit,
]:
    contract = PeriodicFlowMetadataCensusContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    result = PeriodicFlowMetadataCensusResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    audit = PeriodicFlowMetadataCensusAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_metadata_census_contract(contract)
        or not audit_metadata_census_result(result)
        or not audit_metadata_census_audit(audit)
        or result.contract_evidence_hash != contract.contract_evidence_hash
        or audit.contract_evidence_hash != contract.contract_evidence_hash
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.contract_file_sha256 != file_sha256(contract_path)
        or audit.result_file_sha256 != file_sha256(result_path)
        or result.decision != Q1_CENSUS_PASS_DECISION
        or result.next_authorization != Q1_CENSUS_PASS_AUTHORIZATION
        or not result.authorizes_separate_payload_pilot_protocol
        or result.archive_head_requests_made != 0
        or result.archive_payload_requests_made != 0
        or result.archive_payload_bytes != 0
        or result.market_numeric_fields_inspected
        or result.parameters_defined
        or result.return_metrics_calculated
        or result.strategy_candidates_created
        or result.strategy_executions
        or result.orders_submitted
    ):
        raise ValueError("Q1 metadata census lineage or authority boundary failed")
    return contract, result, audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    contract_path: Path,
    result_path: Path,
    audit_path: Path,
) -> PeriodicFlowPayloadPilotProtocol:
    contract, result, audit = load_lineage(
        contract_path,
        result_path,
        audit_path,
    )
    selected = tuple(
        record
        for record in result.records
        if record.month == Q1_PAYLOAD_PILOT_MONTH
    )
    if (
        len(selected) != 2
        or tuple(record.product for record in selected)
        != ("SPOT", "USD_M_PERPETUAL")
        or any(record.archive_sha256 is None for record in selected)
    ):
        raise ValueError("Q1 earliest development pair is incomplete")
    targets = tuple(
        PeriodicFlowPayloadTarget(
            product=record.product,
            archive_url=record.archive_url,
            published_archive_sha256=record.archive_sha256,
            expected_columns=(
                next(
                    schema.columns
                    for schema in contract.schema_register
                    if schema.product == record.product
                )
            ),
            expected_column_count=(8 if record.product == "SPOT" else 7),
        )
        for record in selected
    )
    return build_periodic_flow_payload_protocol(
        frozen_at=frozen_at,
        census_contract_file_sha256=file_sha256(contract_path),
        census_contract_evidence_hash=contract.contract_evidence_hash,
        census_result_file_sha256=file_sha256(result_path),
        census_result_evidence_hash=result.result_evidence_hash,
        census_audit_file_sha256=file_sha256(audit_path),
        census_audit_evidence_hash=audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        targets=targets,
        target_manifest_hash=universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets]}
        ),
        limitations=(
            "A pass authorizes only a separate full-development payload acquisition protocol.",
            "Only checksum-pinned BTCUSDT Spot and USD-M January 2020 archives may be requested.",
            "Price and quantity are excluded from parsing, persistence, and analysis.",
            "The pilot measures structural integrity and paired clock coverage only.",
            "No feature, parameter, signal, candidate, trade, PnL, or return may be calculated.",
            "Validation, future holdout, and forward outcomes remain inaccessible.",
            "USD-M perpetual data is research input and grants no futures order authority.",
            "Pine, paper, testnet strategy-order, production, and live authority remain false.",
            "This feasibility result cannot establish edge, reliability, or profitability.",
        ),
    )


def write_protocol(path: Path, protocol: PeriodicFlowPayloadPilotProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("Q1 payload pilot protocol already exists; use --check")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if PeriodicFlowPayloadPilotProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 payload protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 payload protocol transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> PeriodicFlowPayloadPilotProtocol:
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        contract_path=args.census_contract,
        result_path=args.census_result,
        audit_path=args.census_audit,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"targets={len(protocol.targets)} payload_requests=0",
        flush=True,
    )
    return protocol


def run_check(args) -> PeriodicFlowPayloadPilotProtocol:
    protocol = PeriodicFlowPayloadPilotProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        contract_path=args.census_contract,
        result_path=args.census_result,
        audit_path=args.census_audit,
    )
    if protocol != expected or not audit_periodic_flow_payload_protocol(protocol):
        raise ValueError("Q1 payload pilot protocol is not reproducible")
    print(
        f"PASS q1_payload_protocol={protocol.protocol_evidence_hash} "
        f"targets={len(protocol.targets)} month={Q1_PAYLOAD_PILOT_MONTH}",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or check the Q1 paired one-month payload pilot protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--census-contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--census-result", type=Path, default=DEFAULT_CENSUS_RESULT)
    parser.add_argument("--census-audit", type=Path, default=DEFAULT_CENSUS_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write:
            run_write(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
