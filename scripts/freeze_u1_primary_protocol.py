import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.development_bundle import DevelopmentDatasetBundle
from aurex.backtest_engine.research_r4_protocol import R4_DECISION_SYMBOLS
from aurex.backtest_engine.research_u1_discovery_charter import (
    U1MechanismDiscoveryCharter,
    audit_u1_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_u1_primary_protocol import (
    U1_FORBIDDEN_PARTITIONS,
    U1_REQUIRED_DIAGNOSTICS,
    U1PrimaryAvailabilityProtocol,
    U1PrimaryBenchmarkProtocol,
    U1PrimaryCostProtocol,
    U1PrimaryFold,
    U1PrimaryGates,
    U1PrimaryPortfolioProtocol,
    U1PrimaryProtocol,
    U1PrimarySelectionControl,
    U1PrimarySignalProtocol,
    audit_u1_primary_protocol,
    build_u1_primary_protocol,
)
from aurex.backtest_engine.research_u1_theory_screen import (
    U1MechanismTheoryScreen,
    audit_u1_mechanism_theory_screen,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_CHARTER = DEFAULT_EVIDENCE_ROOT / "u1_mechanism_discovery_charter_v1.json"
DEFAULT_SCREEN = DEFAULT_EVIDENCE_ROOT / "u1_mechanism_theory_screen_v1.json"
DEFAULT_CONTAMINATION = (
    DEFAULT_EVIDENCE_ROOT / "strategy_contamination_ledger_v1.json"
)
DEFAULT_UNIVERSE = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_DEVELOPMENT = (
    DEFAULT_EVIDENCE_ROOT / "development_4h_dataset_bundle_v1.json"
)
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_protocol_v1.json"
DEFAULT_POST_PROTOCOL_ARTIFACTS = (
    DEFAULT_EVIDENCE_ROOT / "u1_primary_execution_spec_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_run_package_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_result_v1.json",
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_u1_primary_protocol.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_u1_primary_protocol.py",
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


def load_inputs(args):
    charter = U1MechanismDiscoveryCharter.model_validate_json(
        args.charter.read_text(encoding="utf-8")
    )
    screen = U1MechanismTheoryScreen.model_validate_json(
        args.screen.read_text(encoding="utf-8")
    )
    contamination = StrategyContaminationLedger.model_validate_json(
        args.contamination.read_text(encoding="utf-8")
    )
    universe = MarketUniverseManifest.model_validate_json(
        args.universe.read_text(encoding="utf-8")
    )
    development = DevelopmentDatasetBundle.model_validate_json(
        args.development.read_text(encoding="utf-8")
    )
    if not audit_u1_mechanism_discovery_charter(charter):
        raise ValueError("U1 charter failed its hash audit")
    if not audit_u1_mechanism_theory_screen(screen):
        raise ValueError("U1 theory screen failed its hash audit")
    if not audit_contamination_ledger(contamination):
        raise ValueError("Contamination ledger failed its hash audit")
    if audit_market_universe_manifest(universe)["status"] != "PASS":
        raise ValueError("Universe manifest failed its hash audit")
    if (
        screen.discovery_charter_evidence_hash != charter.charter_evidence_hash
        or screen.selected_proposal_id
        != "P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
        or screen.return_tested_mechanisms != 0
    ):
        raise ValueError("U1 theory selection is not the frozen no-return primary")
    if (
        charter.contamination_ledger_evidence_hash
        != contamination.ledger_evidence_hash
        or charter.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
        or charter.development_dataset_bundle_evidence_hash
        != development.bundle_evidence_hash
        or universe.rule.contamination_ledger_hash
        != contamination.ledger_evidence_hash
        or development.contamination_ledger_hash
        != contamination.ledger_evidence_hash
        or development.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
    ):
        raise ValueError("U1 primary inputs do not share one evidence lineage")
    if universe.status != "READY" or development.status != "READY":
        raise ValueError("U1 primary requires ready development inputs")
    return charter, screen, contamination, universe, development


def authoritative_folds() -> list[U1PrimaryFold]:
    boundaries = [
        ("fold-01-2023-partial-q1", "2023-02-01T00:00:00Z", "2023-04-01T00:00:00Z"),
        ("fold-02-2023q2", "2023-04-01T00:00:00Z", "2023-07-01T00:00:00Z"),
        ("fold-03-2023q3", "2023-07-01T00:00:00Z", "2023-10-01T00:00:00Z"),
        ("fold-04-2023q4", "2023-10-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        ("fold-05-2024q1", "2024-01-01T00:00:00Z", "2024-04-01T00:00:00Z"),
        ("fold-06-2024q2", "2024-04-01T00:00:00Z", "2024-07-01T00:00:00Z"),
        ("fold-07-2024q3", "2024-07-01T00:00:00Z", "2024-10-01T00:00:00Z"),
        ("fold-08-2024q4", "2024-10-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ]
    return [
        U1PrimaryFold(
            fold_id=fold_id,
            evaluation_start=datetime.fromisoformat(start.replace("Z", "+00:00")),
            evaluation_end=datetime.fromisoformat(end.replace("Z", "+00:00")),
        )
        for fold_id, start, end in boundaries
    ]


def authoritative_protocol(
    *,
    registered_at: datetime,
    charter: U1MechanismDiscoveryCharter,
    screen: U1MechanismTheoryScreen,
    contamination: StrategyContaminationLedger,
    universe: MarketUniverseManifest,
    development: DevelopmentDatasetBundle,
) -> U1PrimaryProtocol:
    return build_u1_primary_protocol(
        registered_at=registered_at,
        hypothesis=(
            "For the fixed survivorship-aware Aurex spot universe, a broad equal-weight "
            "market basket may earn a positive crypto market risk premium, while "
            "scaling unlevered exposure by a fixed inverse-realized-variance rule should "
            "reduce risk during high-variance states and improve drawdown or "
            "return-to-drawdown efficiency against an otherwise identical static "
            "100%-exposed broad-spot benchmark after realistic costs."
        ),
        falsification_claim=(
            "The mechanism is unsupported if its one fixed primary misses any frozen "
            "profitability, profit-factor, drawdown, sample-size, temporal, double-cost, "
            "leave-one-market-out, concentration, realized-volatility, or benchmark "
            "efficiency gate. Any failure stops this mechanism without another target, "
            "lookback, rebalance interval, basket rule, exposure transform, or rescue "
            "variant."
        ),
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        theory_screen_evidence_hash=screen.screen_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=development.bundle_evidence_hash,
        contamination_ledger_evidence_hash=contamination.ledger_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        development_data_start=development.partition_start,
        development_data_end=development.partition_end,
        evaluation_start=datetime(2023, 2, 1, tzinfo=UTC),
        evaluation_end=datetime(2025, 1, 1, tzinfo=UTC),
        decision_symbols=list(R4_DECISION_SYMBOLS),
        forbidden_partitions=U1_FORBIDDEN_PARTITIONS,
        signal=U1PrimarySignalProtocol(),
        benchmark=U1PrimaryBenchmarkProtocol(),
        folds=authoritative_folds(),
        portfolio=U1PrimaryPortfolioProtocol(),
        availability=U1PrimaryAvailabilityProtocol(),
        costs=U1PrimaryCostProtocol(stress_multipliers=["1", "1.5", "2"]),
        gates=U1PrimaryGates(),
        selection_control=U1PrimarySelectionControl(),
        required_diagnostics=U1_REQUIRED_DIAGNOSTICS,
        outcome_fields_inspected=[],
        preexisting_result_artifacts=[],
    )


def write_protocol(path: Path, protocol: U1PrimaryProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if U1PrimaryProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("U1 primary protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> U1PrimaryProtocol:
    if args.output.exists():
        raise ValueError("Frozen U1 primary protocol exists; use --check")
    preexisting = [
        path.as_posix() for path in args.post_protocol_artifact if path.exists()
    ]
    if preexisting:
        raise ValueError(f"U1 artifact predates primary protocol: {preexisting}")
    inputs = load_inputs(args)
    protocol = authoritative_protocol(
        registered_at=datetime.now(UTC),
        charter=inputs[0],
        screen=inputs[1],
        contamination=inputs[2],
        universe=inputs[3],
        development=inputs[4],
    )
    write_protocol(args.output, protocol)
    stored = U1PrimaryProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != protocol or not audit_u1_primary_protocol(stored):
        raise ValueError("U1 primary protocol failed reload verification")
    print(
        f"WROTE {args.output} {stored.protocol_evidence_hash} "
        f"folds={len(stored.folds)} symbols={len(stored.decision_symbols)}",
        flush=True,
    )
    return stored


def run_check(args) -> U1PrimaryProtocol:
    inputs = load_inputs(args)
    stored = U1PrimaryProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        registered_at=stored.registered_at,
        charter=inputs[0],
        screen=inputs[1],
        contamination=inputs[2],
        universe=inputs[3],
        development=inputs[4],
    )
    if stored != expected or not audit_u1_primary_protocol(stored):
        raise ValueError("Stored U1 primary protocol differs from rebuild")
    print(
        f"PASS u1_primary_protocol={stored.protocol_evidence_hash} "
        f"folds={len(stored.folds)} symbols={len(stored.decision_symbols)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the pre-outcome U1 primary protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--screen", type=Path, default=DEFAULT_SCREEN)
    parser.add_argument("--contamination", type=Path, default=DEFAULT_CONTAMINATION)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--development", type=Path, default=DEFAULT_DEVELOPMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--post-protocol-artifact",
        type=Path,
        nargs="*",
        default=list(DEFAULT_POST_PROTOCOL_ARTIFACTS),
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
