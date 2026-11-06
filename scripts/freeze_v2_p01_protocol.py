import argparse
import hashlib
import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
    V2_EXCLUDED_INCOMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v2_metadata_source_audit import (
    V2P01MetadataSourceAuditResult,
    audit_v2_p01_metadata_source_audit_result,
)
from aurex.backtest_engine.research_v2_p01_protocol import (
    V2_P01_CURRENT_FILTER_FIELDS,
    V2_P01_CURRENT_METADATA_URLS,
    V2_P01_DIRECT_HISTORICAL_REQUIREMENTS,
    V2_P01_FORBIDDEN_PARTITIONS,
    V2_P01_NO_OVERRIDE_REQUIREMENTS,
    V2_P01_NORMALIZED_FIELDS,
    V2_P01_OVERRIDE_REQUIREMENTS,
    V2_P01_REQUIRED_DIAGNOSTICS,
    P01CostProtocol,
    P01ExecutionProtocol,
    P01Fold,
    P01FullAcquisitionProtocol,
    P01Gates,
    P01MarginProtocol,
    P01MetadataTreatment,
    P01PortfolioProtocol,
    P01RunSpec,
    P01SelectionControl,
    P01SignalProtocol,
    P01TransformationProtocol,
    V2P01PrimaryProtocol,
    audit_v2_p01_primary_protocol,
    build_v2_p01_primary_protocol,
)
from aurex.backtest_engine.research_v2_pilot_acquisition import (
    V2PilotAcquisitionResult,
    audit_v2_pilot_acquisition_result,
)
from aurex.backtest_engine.research_v2_source_census import (
    V2SourceCensusResult,
    audit_v2_source_census_result,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_MONTHS,
    V2_REQUIRED_FAMILY_IDS,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_metadata_runner = import_module(
    "scripts.run_v2_p01_metadata_source_audit"
)
_census_runner = import_module("scripts.run_v2_source_census")
_pilot_runner = import_module("scripts.run_v2_acquisition_pilot")

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_FOUNDATION_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_FOUNDATION_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_result_v1.json"
)
DEFAULT_CHARTER = DEFAULT_EVIDENCE_ROOT / "v2_mechanism_discovery_charter_v1.json"
DEFAULT_THEORY_SCREEN = (
    DEFAULT_EVIDENCE_ROOT / "v2_mechanism_theory_screen_v1.json"
)
DEFAULT_SUPERSEDED_METADATA_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1.json"
)
DEFAULT_METADATA_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1_1.json"
)
DEFAULT_METADATA_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_audit_v1_1.json"
)
DEFAULT_SOURCE_CENSUS_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_source_census_contract_v1.json"
)
DEFAULT_SOURCE_CENSUS_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_source_census_result_v1.json"
)
DEFAULT_PILOT_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_acquisition_protocol_v1.json"
)
DEFAULT_PILOT_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_pilot_acquisition_result_v1.json"
)
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "v2_p01_primary_protocol_v1.json"
DEFAULT_SUCCESSOR_ARTIFACTS = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_full_acquisition_result_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_p01_primary_development_result_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_p01_validation_protocol_v1.json",
)


def builder_contract_hash() -> str:
    paths = [
        PROJECT_ROOT / "scripts" / "freeze_v2_p01_protocol.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_p01_protocol.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_inputs(args):
    metadata_contract = _metadata_runner.load_contract(args)
    metadata_result = V2P01MetadataSourceAuditResult.model_validate_json(
        args.metadata_result.read_text(encoding="utf-8")
    )
    metadata_audit = audit_v2_p01_metadata_source_audit_result(
        result=metadata_result,
        contract=metadata_contract,
        current_runner_contract_hash=_metadata_runner.runner_contract_hash(),
    )
    if metadata_audit["status"] != "PASS":
        raise ValueError(
            f"P01 metadata predecessor failed: {metadata_audit['reasons']}"
        )
    if metadata_result.decision != (
        "PERMIT_P01_PROTOCOL_DESIGN_WITH_MANDATORY_METADATA_OVERRIDES"
    ):
        raise ValueError("P01 metadata predecessor does not permit protocol design")

    census_contract = _census_runner.load_contract(
        args.source_census_contract
    )
    census_result = V2SourceCensusResult.model_validate_json(
        args.source_census_result.read_text(encoding="utf-8")
    )
    census_audit = audit_v2_source_census_result(
        result=census_result,
        contract=census_contract,
        current_runner_contract_hash=_census_runner.runner_contract_hash(),
    )
    if census_audit["status"] != "PASS":
        raise ValueError(
            f"P01 source census predecessor failed: {census_audit['reasons']}"
        )
    if census_result.summary.complete_symbols != V2_COMPLETE_SYMBOLS:
        raise ValueError("P01 source-complete symbols changed")

    pilot_protocol = _pilot_runner.load_protocol(args.pilot_protocol)
    pilot_result = V2PilotAcquisitionResult.model_validate_json(
        args.pilot_result.read_text(encoding="utf-8")
    )
    pilot_audit = audit_v2_pilot_acquisition_result(
        result=pilot_result,
        protocol=pilot_protocol,
        current_runner_contract_hash=_pilot_runner.runner_contract_hash(),
        evidence_root=args.evidence_root,
        inspect_local_archives=True,
    )
    if pilot_audit["status"] != "PASS":
        raise ValueError(
            f"P01 pilot predecessor failed: {pilot_audit['reasons']}"
        )
    if pilot_result.decision != (
        "PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL"
    ):
        raise ValueError("P01 pilot does not permit a full acquisition protocol")

    if metadata_result.source_census_result_evidence_hash != (
        census_result.result_evidence_hash
    ):
        raise ValueError("P01 metadata and census lineage disagree")
    if metadata_contract.pilot_result_evidence_hash != (
        pilot_result.result_evidence_hash
    ):
        raise ValueError("P01 metadata and pilot lineage disagree")
    return (
        metadata_contract,
        metadata_result,
        census_contract,
        census_result,
        pilot_protocol,
        pilot_result,
    )


def full_source_target_manifest_hash(
    census_result: V2SourceCensusResult,
) -> str:
    allowed_symbols = set(V2_COMPLETE_SYMBOLS)
    manifest = [
        {
            "symbol": record.symbol,
            "month": record.month,
            "family_id": record.family_id,
            "archive_url": record.archive_url,
            "checksum_url": record.checksum_url,
            "checksum_sha256": record.checksum_sha256,
        }
        for record in census_result.records
        if record.symbol in allowed_symbols
    ]
    if len(manifest) != 4464:
        raise ValueError("P01 full source target manifest count changed")
    if any(item["checksum_sha256"] is None for item in manifest):
        raise ValueError("P01 full source target manifest contains a missing source")
    return universe_evidence_hash({"targets": manifest})


def authoritative_folds() -> list[P01Fold]:
    boundaries = [
        ("fold-01-2023q1", datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 4, 1, tzinfo=UTC)),
        ("fold-02-2023q2", datetime(2023, 4, 1, tzinfo=UTC), datetime(2023, 7, 1, tzinfo=UTC)),
        ("fold-03-2023q3", datetime(2023, 7, 1, tzinfo=UTC), datetime(2023, 10, 1, tzinfo=UTC)),
        ("fold-04-2023q4", datetime(2023, 10, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)),
        ("fold-05-2024q1", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 4, 1, tzinfo=UTC)),
        ("fold-06-2024q2", datetime(2024, 4, 1, tzinfo=UTC), datetime(2024, 7, 1, tzinfo=UTC)),
        ("fold-07-2024q3", datetime(2024, 7, 1, tzinfo=UTC), datetime(2024, 10, 1, tzinfo=UTC)),
        ("fold-08-2024q4", datetime(2024, 10, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)),
    ]
    return [
        P01Fold(
            fold_id=fold_id,
            evaluation_start=start,
            evaluation_end=end,
        )
        for fold_id, start, end in boundaries
    ]


def authoritative_run_matrix() -> list[P01RunSpec]:
    runs = [
        P01RunSpec(
            run_id="primary-base-cost",
            run_kind="PRIMARY",
            cost_multiplier="1",
            selectable=True,
        ),
        P01RunSpec(
            run_id="diagnostic-zero-cost",
            run_kind="COST_DIAGNOSTIC",
            cost_multiplier="0",
            selectable=False,
        ),
        P01RunSpec(
            run_id="diagnostic-1p5-cost",
            run_kind="COST_DIAGNOSTIC",
            cost_multiplier="1.5",
            selectable=False,
        ),
        P01RunSpec(
            run_id="diagnostic-double-cost",
            run_kind="COST_DIAGNOSTIC",
            cost_multiplier="2",
            selectable=False,
        ),
    ]
    runs.extend(
        P01RunSpec(
            run_id=f"leave-one-out-{symbol.lower()}",
            run_kind="LEAVE_ONE_SYMBOL_OUT",
            cost_multiplier="1",
            excluded_symbol=symbol,
            selectable=False,
        )
        for symbol in V2_COMPLETE_SYMBOLS
    )
    return runs


def authoritative_protocol(
    *,
    frozen_at: datetime,
    inputs,
) -> V2P01PrimaryProtocol:
    (
        metadata_contract,
        metadata_result,
        census_contract,
        census_result,
        pilot_protocol,
        pilot_result,
    ) = inputs
    return build_v2_p01_primary_protocol(
        frozen_at=frozen_at,
        hypothesis=(
            "When USD-M perpetual traders repeatedly pay materially positive funding, "
            "a base-quantity-matched long spot and short perpetual position should "
            "harvest that transfer while removing most directional beta. The fixed "
            "30% trailing annualized entry hurdle and 10% exit hurdle create cost "
            "hysteresis; profitability must survive conservative execution, fees, "
            "margin treatment, concentration controls, and double-cost stress."
        ),
        falsification_claim=(
            "The mechanism is rejected if its one frozen parameter set fails any "
            "required development gate, including net profitability, profit factor, "
            "drawdown, temporal robustness, double-cost profitability, funding "
            "receipts exceeding execution costs, concentration, hedge integrity, "
            "reconciliation, liquidation, ADL, or rollback safety. No threshold "
            "change, symbol substitution, or rescue variant is allowed after returns."
        ),
        theory_screen_evidence_hash=(
            metadata_result.theory_screen_evidence_hash
        ),
        metadata_source_contract_evidence_hash=(
            metadata_contract.contract_evidence_hash
        ),
        metadata_source_audit_result_evidence_hash=(
            metadata_result.result_evidence_hash
        ),
        source_census_contract_evidence_hash=(
            census_contract.contract_evidence_hash
        ),
        source_census_result_evidence_hash=(
            census_result.result_evidence_hash
        ),
        pilot_protocol_evidence_hash=pilot_protocol.protocol_evidence_hash,
        pilot_result_evidence_hash=pilot_result.result_evidence_hash,
        derivatives_foundation_result_evidence_hash=(
            metadata_result.derivatives_foundation_result_evidence_hash
        ),
        contamination_ledger_evidence_hash=(
            metadata_contract.contamination_ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        development_start=datetime(2023, 1, 1, tzinfo=UTC),
        development_end=datetime(2025, 1, 1, tzinfo=UTC),
        forbidden_partitions=V2_P01_FORBIDDEN_PARTITIONS,
        acquisition=P01FullAcquisitionProtocol(
            complete_source_symbols=V2_COMPLETE_SYMBOLS,
            excluded_incomplete_symbols=V2_EXCLUDED_INCOMPLETE_SYMBOLS,
            months=V2_MONTHS,
            family_ids=V2_REQUIRED_FAMILY_IDS,
            source_target_manifest_hash=full_source_target_manifest_hash(
                census_result
            ),
            retry_backoff_seconds=[2, 5],
            current_metadata_urls=V2_P01_CURRENT_METADATA_URLS,
            normalized_fields=V2_P01_NORMALIZED_FIELDS,
            current_filter_fields=V2_P01_CURRENT_FILTER_FIELDS,
        ),
        metadata_treatment=P01MetadataTreatment(
            direct_historical_requirement_ids=(
                V2_P01_DIRECT_HISTORICAL_REQUIREMENTS
            ),
            conservative_override_requirement_ids=(
                V2_P01_OVERRIDE_REQUIREMENTS
            ),
            no_override_requirement_ids=(
                V2_P01_NO_OVERRIDE_REQUIREMENTS
            ),
        ),
        transformations=P01TransformationProtocol(),
        signal=P01SignalProtocol(
            exit_rules=[
                "TRAILING_ANNUALIZED_FUNDING_AT_OR_BELOW_0.10",
                "NONPOSITIVE_LATEST_SETTLED_FUNDING",
                "RISK_KILL_SWITCH",
                "DATA_OR_LIFECYCLE_INTEGRITY_BREACH",
                "FORCED_END_OF_DEVELOPMENT_WINDOW",
            ]
        ),
        portfolio=P01PortfolioProtocol(),
        execution=P01ExecutionProtocol(),
        costs=P01CostProtocol(stress_multipliers=["0", "1", "1.5", "2"]),
        margin=P01MarginProtocol(),
        folds=authoritative_folds(),
        run_matrix=authoritative_run_matrix(),
        gates=P01Gates(),
        selection_control=P01SelectionControl(),
        required_diagnostics=V2_P01_REQUIRED_DIAGNOSTICS,
        outcome_fields_inspected=[],
        preexisting_result_artifacts=[],
        limitations=[
            (
                "Historical spot and futures order filters are unavailable; current "
                "public exchangeInfo snapshots are applied only as conservative proxies."
            ),
            (
                "Historical account fee tiers are unavailable; fixed taker fees are "
                "research overrides and cannot prove realized account costs."
            ),
            (
                "Historical leverage, maintenance margin, collateral, liquidation, "
                "and ADL rules are unavailable and use explicit adverse overrides."
            ),
            (
                "Complete archives and strict timestamp continuity cannot prove every "
                "historical listing, suspension, or venue-operability state."
            ),
            (
                "One-minute OHLCV has no order book; adverse execution and volume "
                "participation are modeled proxies rather than fill evidence."
            ),
            (
                "A development pass permits only a separately frozen 2025 validation "
                "protocol and creates no Pine, paper, sandbox, or live eligibility."
            ),
            (
                "The 2026 holdout, forward evidence, production credentials, and real "
                "capital remain sealed and outside this protocol."
            ),
        ],
    )


def write_protocol(path: Path, protocol: V2P01PrimaryProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if V2P01PrimaryProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("P01 protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2P01PrimaryProtocol:
    if args.output.exists():
        raise ValueError("Frozen P01 protocol exists; use --check")
    preexisting = [
        path.as_posix() for path in args.successor_artifact if path.exists()
    ]
    if preexisting:
        raise ValueError(f"P01 successor predates protocol: {preexisting}")
    inputs = load_inputs(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        inputs=inputs,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"targets={protocol.acquisition.source_target_count} "
        f"runs={len(protocol.run_matrix)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2P01PrimaryProtocol:
    inputs = load_inputs(args)
    stored = V2P01PrimaryProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=stored.frozen_at,
        inputs=inputs,
    )
    if stored != expected or not audit_v2_p01_primary_protocol(stored):
        raise ValueError("Stored P01 protocol differs from deterministic rebuild")
    print(
        "PASS "
        f"v2_p01_protocol={stored.protocol_evidence_hash} "
        f"development_before_acquisition="
        f"{stored.return_calculation_permitted_before_acquisition_pass} "
        f"live={stored.creates_live_eligibility}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the integrated P01 acquisition/development protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument(
        "--foundation-protocol",
        type=Path,
        default=DEFAULT_FOUNDATION_PROTOCOL,
    )
    parser.add_argument(
        "--foundation-result",
        type=Path,
        default=DEFAULT_FOUNDATION_RESULT,
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument(
        "--theory-screen",
        type=Path,
        default=DEFAULT_THEORY_SCREEN,
    )
    parser.add_argument(
        "--superseded-contract",
        type=Path,
        default=DEFAULT_SUPERSEDED_METADATA_CONTRACT,
    )
    parser.add_argument(
        "--metadata-contract",
        type=Path,
        default=DEFAULT_METADATA_CONTRACT,
    )
    parser.add_argument(
        "--metadata-result",
        type=Path,
        default=DEFAULT_METADATA_RESULT,
    )
    parser.add_argument(
        "--source-census-contract",
        type=Path,
        default=DEFAULT_SOURCE_CENSUS_CONTRACT,
    )
    parser.add_argument(
        "--source-census-result",
        type=Path,
        default=DEFAULT_SOURCE_CENSUS_RESULT,
    )
    parser.add_argument(
        "--pilot-protocol",
        type=Path,
        default=DEFAULT_PILOT_PROTOCOL,
    )
    parser.add_argument(
        "--pilot-result",
        type=Path,
        default=DEFAULT_PILOT_RESULT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--successor-artifact",
        type=Path,
        action="append",
        default=list(DEFAULT_SUCCESSOR_ARTIFACTS),
    )
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
