import argparse
import hashlib
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    audit_development_dataset_bundle,
)
from aurex.backtest_engine.research_study import (
    R3AdvancementGates,
    R3CostModel,
    R3MechanismStudyProtocol,
    R3PortfolioConstruction,
    R3StudyFold,
    R3StudyVariant,
    audit_r3_mechanism_study_protocol,
    build_r3_mechanism_study_protocol,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_UNIVERSE_MANIFEST = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_DATASET_BUNDLE = DEFAULT_EVIDENCE_ROOT / "development_4h_dataset_bundle_v1.json"
DEFAULT_PROTOCOL_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "r3_cross_sectional_momentum_study_v1.json"
)
RESULT_GLOB = "r3_cross_sectional_momentum_result*.json"


def load_universe_manifest(path: Path) -> MarketUniverseManifest:
    manifest = MarketUniverseManifest.model_validate_json(path.read_text(encoding="utf-8"))
    audit = audit_market_universe_manifest(manifest)
    if audit["status"] != "PASS" or manifest.status != "READY":
        raise ValueError("R3 requires a ready, audit-valid market universe")
    return manifest


def expected_universe_roles(manifest: MarketUniverseManifest) -> dict[str, str]:
    return dict(
        sorted(
            {
                assessment.evidence.symbol: assessment.role
                for assessment in manifest.assessments
                if assessment.role in {"DECISION_CANDIDATE", "DEVELOPMENT_ONLY"}
            }.items()
        )
    )


def development_builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "build_development_dataset_bundle.py",
        project_root / "src" / "aurex" / "backtest_engine" / "binance_vision.py",
        project_root / "src" / "aurex" / "backtest_engine" / "development_bundle.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in contract_paths
            }
        }
    )


def load_verified_inputs(
    *,
    evidence_root: Path,
    universe_path: Path,
    bundle_path: Path,
) -> tuple[MarketUniverseManifest, DevelopmentDatasetBundle]:
    universe = load_universe_manifest(universe_path)
    bundle = DevelopmentDatasetBundle.model_validate_json(
        bundle_path.read_text(encoding="utf-8")
    )
    if bundle.status != "READY":
        raise ValueError("R3 dataset bundle is not ready")
    if bundle.universe_manifest_evidence_hash != universe.manifest_evidence_hash:
        raise ValueError("R3 dataset bundle does not match the frozen universe")
    audit = audit_development_dataset_bundle(
        bundle,
        evidence_root=evidence_root,
        expected_roles=expected_universe_roles(universe),
        current_builder_contract_hash=development_builder_contract_hash(),
    )
    if audit["status"] != "PASS":
        raise ValueError(f"R3 dataset bundle audit failed: {audit['reasons']}")
    return universe, bundle


def authoritative_protocol(
    *,
    registered_at: datetime,
    universe: MarketUniverseManifest,
    bundle: DevelopmentDatasetBundle,
) -> R3MechanismStudyProtocol:
    return build_r3_mechanism_study_protocol(
        study_id="r3-cross-sectional-momentum-spot-v1",
        study_version="1.0.0",
        registered_at=registered_at,
        status="FROZEN_PRE_OUTCOME",
        mechanism_family="CROSS_SECTIONAL_MOMENTUM",
        hypothesis=(
            "Among mechanically selected liquid Binance USDT spot markets, positive "
            "intermediate-horizon relative strength will persist long enough for a "
            "diversified long-only rotation portfolio to retain positive net returns "
            "after conservative two-sided trading costs and shared-capital limits."
        ),
        falsification_claim=(
            "The mechanism is not supported if the fixed 84-day primary loses after "
            "costs, depends on one market or one quarter, fails double-cost stress, or "
            "has no same-sign support at either the predeclared faster or slower horizon."
        ),
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=bundle.bundle_evidence_hash,
        contamination_ledger_hash=universe.rule.contamination_ledger_hash,
        builder_contract_hash=builder_contract_hash(),
        venue="BINANCE",
        market_type="SPOT",
        quote_asset="USDT",
        timeframe="4h",
        development_data_start=bundle.partition_start,
        development_data_end=bundle.partition_end,
        evaluation_start="2023-07-01T00:00:00Z",
        evaluation_end="2025-01-01T00:00:00Z",
        decision_symbols=universe.summary.decision_symbols,
        diagnostic_only_symbols=universe.summary.development_only_symbols,
        forbidden_partitions=["VALIDATION", "HOLDOUT", "FORWARD"],
        variants=[
            R3StudyVariant(
                variant_id="xsmom_168d_28d_falsification_slow",
                role="FALSIFICATION",
                lookback_bars=1008,
                rebalance_bars=168,
                volatility_lookback_bars=168,
                atr_lookback_bars=84,
                catastrophe_stop_atr_multiple="3",
                selected_fraction="0.20",
            ),
            R3StudyVariant(
                variant_id="xsmom_28d_7d_falsification_fast",
                role="FALSIFICATION",
                lookback_bars=168,
                rebalance_bars=42,
                volatility_lookback_bars=168,
                atr_lookback_bars=84,
                catastrophe_stop_atr_multiple="3",
                selected_fraction="0.20",
            ),
            R3StudyVariant(
                variant_id="xsmom_84d_14d_primary",
                role="PRIMARY",
                lookback_bars=504,
                rebalance_bars=84,
                volatility_lookback_bars=168,
                atr_lookback_bars=84,
                catastrophe_stop_atr_multiple="3",
                selected_fraction="0.20",
            ),
        ],
        folds=[
            R3StudyFold(
                fold_id="fold-01-2023q3",
                evaluation_start="2023-07-01T00:00:00Z",
                evaluation_end="2023-10-01T00:00:00Z",
            ),
            R3StudyFold(
                fold_id="fold-02-2023q4",
                evaluation_start="2023-10-01T00:00:00Z",
                evaluation_end="2024-01-01T00:00:00Z",
            ),
            R3StudyFold(
                fold_id="fold-03-2024q1",
                evaluation_start="2024-01-01T00:00:00Z",
                evaluation_end="2024-04-01T00:00:00Z",
            ),
            R3StudyFold(
                fold_id="fold-04-2024q2",
                evaluation_start="2024-04-01T00:00:00Z",
                evaluation_end="2024-07-01T00:00:00Z",
            ),
            R3StudyFold(
                fold_id="fold-05-2024q3",
                evaluation_start="2024-07-01T00:00:00Z",
                evaluation_end="2024-10-01T00:00:00Z",
            ),
            R3StudyFold(
                fold_id="fold-06-2024q4",
                evaluation_start="2024-10-01T00:00:00Z",
                evaluation_end="2025-01-01T00:00:00Z",
            ),
        ],
        portfolio=R3PortfolioConstruction(
            initial_capital="1000",
            risk_per_position_percent="0.50",
            max_symbol_exposure_percent="20",
            max_gross_exposure_percent="100",
            max_open_positions=7,
            minimum_ranked_positions=3,
            quantity_increment_assumption="0.00000001",
            price_increment_assumption="0.00000001",
        ),
        costs=R3CostModel(
            commission_percent_per_side="0.10",
            adverse_slippage_percent_per_side="0.05",
            stress_multipliers=[Decimal("1"), Decimal("1.5"), Decimal("2")],
        ),
        gates=R3AdvancementGates(
            minimum_primary_profit_factor="1.10",
            maximum_primary_drawdown_percent="20",
            minimum_primary_completed_trades=100,
            minimum_positive_quarterly_folds=4,
            total_quarterly_folds=6,
            minimum_leave_one_market_out_positive_fraction="0.80",
            maximum_single_symbol_gross_profit_fraction="0.30",
            maximum_top_five_gross_profit_fraction="0.65",
            minimum_supportive_falsification_variants=1,
            supportive_variant_minimum_positive_folds=3,
        ),
        required_diagnostics=[
            "accepted_and_rejected_opportunities",
            "active_days",
            "cost_decomposition",
            "cost_stress",
            "exposure_over_time",
            "gross_and_net_profit_factor",
            "leave_one_market_out",
            "maximum_drawdown",
            "monthly_net_returns",
            "quarterly_fold_results",
            "symbol_gross_profit_concentration",
            "top_five_gross_profit_concentration",
            "turnover",
        ],
        source_references=[
            "docs/11_STRATEGY_RESEARCH_DOCTRINE.md",
            "docs/16_STRATEGY_RESEARCH_RESET.md",
            "https://www.nber.org/papers/w24877",
            "https://www.nber.org/papers/w25882",
            "https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf",
        ],
        preexisting_result_artifacts=[],
        outcome_fields_inspected=[],
        decision_rule=(
            "ADVANCE_PRIMARY_TO_R4_ONLY_IF_ALL_GATES_PASS_ELSE_NO_CANDIDATE"
        ),
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "freeze_r3_mechanism_study.py",
        project_root / "src" / "aurex" / "backtest_engine" / "research_study.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in contract_paths
            }
        }
    )


def find_result_artifacts(evidence_root: Path) -> list[str]:
    return sorted(
        path.relative_to(evidence_root).as_posix()
        for path in evidence_root.glob(RESULT_GLOB)
        if path.is_file()
    )


def write_protocol(path: Path, protocol: R3MechanismStudyProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(protocol.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R3MechanismStudyProtocol:
    if args.protocol_output.exists():
        raise ValueError("Frozen R3 protocol already exists; use --check")
    result_artifacts = find_result_artifacts(args.evidence_root)
    if result_artifacts:
        raise ValueError(
            f"R3 result artifacts already exist before protocol freeze: {result_artifacts}"
        )
    universe, bundle = load_verified_inputs(
        evidence_root=args.evidence_root,
        universe_path=args.universe_manifest,
        bundle_path=args.dataset_bundle,
    )
    protocol = authoritative_protocol(
        registered_at=datetime.now(UTC),
        universe=universe,
        bundle=bundle,
    )
    write_protocol(args.protocol_output, protocol)
    stored = R3MechanismStudyProtocol.model_validate_json(
        args.protocol_output.read_text(encoding="utf-8")
    )
    if stored != protocol or not audit_r3_mechanism_study_protocol(stored):
        raise ValueError("R3 protocol failed reload verification")
    print(f"WROTE {args.protocol_output} {stored.protocol_evidence_hash}", flush=True)
    return stored


def run_check(args) -> R3MechanismStudyProtocol:
    universe, bundle = load_verified_inputs(
        evidence_root=args.evidence_root,
        universe_path=args.universe_manifest,
        bundle_path=args.dataset_bundle,
    )
    stored = R3MechanismStudyProtocol.model_validate_json(
        args.protocol_output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        registered_at=stored.registered_at,
        universe=universe,
        bundle=bundle,
    )
    if stored != expected or not audit_r3_mechanism_study_protocol(stored):
        raise ValueError("Stored R3 protocol differs from authoritative offline rebuild")
    print(
        "PASS "
        f"protocol={stored.protocol_evidence_hash} "
        f"decision_symbols={len(stored.decision_symbols)} "
        f"variants={len(stored.variants)} folds={len(stored.folds)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or offline-verify the pre-outcome Aurex R3 mechanism study."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--universe-manifest",
        type=Path,
        default=DEFAULT_UNIVERSE_MANIFEST,
    )
    parser.add_argument(
        "--dataset-bundle",
        type=Path,
        default=DEFAULT_DATASET_BUNDLE,
    )
    parser.add_argument(
        "--protocol-output",
        type=Path,
        default=DEFAULT_PROTOCOL_OUTPUT,
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
