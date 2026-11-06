import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_ALLOWED_PILOT_INSPECTION_FIELDS,
    V2_COMPLETE_SYMBOLS,
    V2_EXCLUDED_INCOMPLETE_SYMBOLS,
    V2_PILOT_MONTHS,
    V2_PILOT_SYMBOLS,
    V2AcquisitionInspectionProtocol,
    V2AcquisitionIntegrityProtocol,
    V2AcquisitionPilotDecisionRule,
    V2AcquisitionResourceLimits,
    V2AcquisitionTarget,
    V2DerivativesAcquisitionProtocol,
    audit_v2_derivatives_acquisition_protocol,
    build_v2_derivatives_acquisition_protocol,
)
from aurex.backtest_engine.research_v2_source_census import (
    V2_CENSUS_PASS_DECISION,
    V2SourceCensusResult,
    audit_v2_source_census_result,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_REQUIRED_FAMILY_IDS,
    V2SourceCensusContract,
    audit_v2_source_census_contract,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_CENSUS_CONTRACT = Path(
    "data/evidence/v2_derivatives_source_census_contract_v1.json"
)
DEFAULT_CENSUS_RESULT = Path(
    "data/evidence/v2_derivatives_source_census_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v2_derivatives_acquisition_protocol_v1.json"
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v2_acquisition_protocol.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_acquisition_protocol.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def source_census_runner_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "run_v2_source_census.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_source_census.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_inputs(
    args,
) -> tuple[V2SourceCensusContract, V2SourceCensusResult]:
    contract = V2SourceCensusContract.model_validate_json(
        args.census_contract.read_text(encoding="utf-8")
    )
    if not audit_v2_source_census_contract(contract):
        raise ValueError("V2 census contract audit failed")
    result = V2SourceCensusResult.model_validate_json(
        args.census_result.read_text(encoding="utf-8")
    )
    result_audit = audit_v2_source_census_result(
        result=result,
        contract=contract,
        current_runner_contract_hash=source_census_runner_contract_hash(),
    )
    if result_audit["status"] != "PASS":
        raise ValueError(f"V2 census result audit failed: {result_audit['reasons']}")
    if result.decision != V2_CENSUS_PASS_DECISION:
        raise ValueError("V2 census did not authorize an acquisition protocol")
    if result.summary.complete_symbols != V2_COMPLETE_SYMBOLS:
        raise ValueError("V2 complete source-symbol set changed")
    if result.summary.incomplete_symbols != V2_EXCLUDED_INCOMPLETE_SYMBOLS:
        raise ValueError("V2 incomplete source-symbol set changed")
    return contract, result


def authoritative_protocol(
    *,
    frozen_at: datetime,
    contract: V2SourceCensusContract,
    result: V2SourceCensusResult,
) -> V2DerivativesAcquisitionProtocol:
    record_by_key = {record.key: record for record in result.records}
    targets = []
    for symbol in V2_PILOT_SYMBOLS:
        for month in V2_PILOT_MONTHS:
            for family_id in V2_REQUIRED_FAMILY_IDS:
                record = record_by_key[(symbol, month, family_id)]
                if not record.is_present or record.checksum_sha256 is None:
                    raise ValueError("V2 pilot target is not present in the census")
                targets.append(
                    V2AcquisitionTarget(
                        symbol=symbol,
                        month=month,
                        family_id=family_id,
                        archive_url=record.archive_url,
                        checksum_url=record.checksum_url,
                        census_checksum_sha256=record.checksum_sha256,
                    )
                )
    return build_v2_derivatives_acquisition_protocol(
        frozen_at=frozen_at,
        source_census_contract_evidence_hash=contract.contract_evidence_hash,
        source_census_result_evidence_hash=result.result_evidence_hash,
        capability_audit_evidence_hash=contract.capability_audit_evidence_hash,
        universe_manifest_evidence_hash=contract.universe_manifest_evidence_hash,
        contamination_ledger_evidence_hash=(
            contract.contamination_ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        official_documentation_urls=[
            "https://data.binance.vision/",
            "https://developers.binance.com/en/docs/catalog",
            "https://github.com/binance/binance-public-data/blob/master/README.md",
        ],
        complete_source_symbols=V2_COMPLETE_SYMBOLS,
        excluded_incomplete_symbols=V2_EXCLUDED_INCOMPLETE_SYMBOLS,
        pilot_symbols=V2_PILOT_SYMBOLS,
        pilot_months=V2_PILOT_MONTHS,
        family_ids=V2_REQUIRED_FAMILY_IDS,
        targets=targets,
        resource_limits=V2AcquisitionResourceLimits(
            retry_backoff_seconds=[2, 5]
        ),
        integrity=V2AcquisitionIntegrityProtocol(),
        inspection=V2AcquisitionInspectionProtocol(
            allowed_inspection_fields=V2_ALLOWED_PILOT_INSPECTION_FIELDS
        ),
        decision_rule=V2AcquisitionPilotDecisionRule(),
        limitations=[
            (
                "The pilot is a deterministic first/median/last source sample and "
                "does not estimate strategy performance."
            ),
            (
                "Checksum equality establishes byte integrity, not economic "
                "correctness, executable liquidity, or future archive availability."
            ),
            (
                "The pilot may inspect schemas and timestamps but may not calculate "
                "returns, signals, trades, gates, or strategy outcomes."
            ),
            (
                "A passing pilot permits only a separate full-acquisition protocol; "
                "it does not automatically authorize the remaining 4,410 archives."
            ),
            (
                "No result from this protocol creates backtest, paper, sandbox, "
                "micro-live, or live eligibility."
            ),
            (
                "CFXUSDT, LUNCUSDT, SHIBUSDT, and STXUSDT remain excluded because "
                "their 2023-2024 six-family archive coverage is incomplete."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: V2DerivativesAcquisitionProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if V2DerivativesAcquisitionProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("V2 acquisition protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2DerivativesAcquisitionProtocol:
    if args.output.exists():
        raise ValueError("Frozen V2 acquisition protocol exists; use --check")
    contract, result = load_inputs(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        contract=contract,
        result=result,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"pilot_targets={protocol.pilot_target_count}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2DerivativesAcquisitionProtocol:
    contract, result = load_inputs(args)
    protocol = V2DerivativesAcquisitionProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        contract=contract,
        result=result,
    )
    if protocol != expected:
        raise ValueError("V2 acquisition protocol is not reproducible")
    if not audit_v2_derivatives_acquisition_protocol(protocol):
        raise ValueError("V2 acquisition protocol hash audit failed")
    print(
        "PASS "
        f"v2_acquisition_protocol={protocol.protocol_evidence_hash} "
        f"pilot_targets={protocol.pilot_target_count} "
        f"full_download_authorized="
        f"{protocol.authorizes_full_archive_payload_download}",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the V2 derivatives pilot-acquisition protocol."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--census-contract",
        type=Path,
        default=DEFAULT_CENSUS_CONTRACT,
    )
    parser.add_argument(
        "--census-result",
        type=Path,
        default=DEFAULT_CENSUS_RESULT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            run_freeze(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
