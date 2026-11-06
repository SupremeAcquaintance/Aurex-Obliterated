import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_u1_discovery_charter import (
    U1MechanismDiscoveryCharter,
    audit_u1_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_u1_theory_screen import (
    U1_THEORY_SELECTION_RULES,
    U1MechanismProposal,
    U1MechanismTheoryScreen,
    U1TheorySource,
    audit_u1_mechanism_theory_screen,
    build_u1_mechanism_theory_screen,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_CHARTER = DEFAULT_EVIDENCE_ROOT / "u1_mechanism_discovery_charter_v1.json"
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "u1_mechanism_theory_screen_v1.json"
DEFAULT_PRIMARY_ARTIFACTS = (
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_protocol_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_execution_spec_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_run_package_v1.json",
    DEFAULT_EVIDENCE_ROOT / "u1_primary_mechanism_result_v1.json",
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_u1_mechanism_theory_screen.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_u1_theory_screen.py",
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


def primary_sources() -> dict[str, U1TheorySource]:
    return {
        "MOREIRA_MUIR_2017": U1TheorySource(
            source_id="MOREIRA_MUIR_2017",
            title="Volatility-Managed Portfolios",
            authors=["Alan Moreira", "Tyler Muir"],
            publication_date="2017-08-01",
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://www.nber.org/papers/w22208",
            relevance=(
                "Establishes the ex-ante premise that scaling market exposure down "
                "when volatility rises can improve risk-adjusted compounding."
            ),
        ),
        "LIU_TSYVINSKI_WU_2022": U1TheorySource(
            source_id="LIU_TSYVINSKI_WU_2022",
            title="Common Risk Factors in Cryptocurrency",
            authors=["Yukun Liu", "Aleh Tsyvinski", "Xi Wu"],
            publication_date="2022-04-01",
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://www.nber.org/papers/w25882",
            relevance=(
                "Supports treating broad cryptocurrency market exposure as a distinct "
                "priced factor without validating any Aurex implementation."
            ),
        ),
        "ZHANG_ZHAO_2023": U1TheorySource(
            source_id="ZHANG_ZHAO_2023",
            title=(
                "Good Volatility, Bad Volatility, and the Cross Section of "
                "Cryptocurrency Returns"
            ),
            authors=["Zehua Zhang", "Ran Zhao"],
            publication_date="2023-10-01",
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1016/j.irfa.2023.102712",
            relevance=(
                "Provides a crypto-specific premise that realized signed jump "
                "variation may contain cross-sectional return information."
            ),
        ),
        "PATTON_SHEPPARD_2015": U1TheorySource(
            source_id="PATTON_SHEPPARD_2015",
            title=(
                "Good Volatility, Bad Volatility: Signed Jumps and the Persistence "
                "of Volatility"
            ),
            authors=["Andrew J. Patton", "Kevin Sheppard"],
            publication_date="2015-07-01",
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://doi.org/10.1162/REST_a_00503",
            relevance=(
                "Defines the high-frequency signed-jump and realized-semivariance "
                "foundation required to test the proposed jump-risk mechanism."
            ),
        ),
        "CHRISTIN_ET_AL_2022": U1TheorySource(
            source_id="CHRISTIN_ET_AL_2022",
            title="The Crypto Carry Trade",
            authors=[
                "Nicolas Christin",
                "Bryan Routledge",
                "Kyle Soska",
                "Ariel Zetlin-Jones",
            ],
            publication_date="2022-01-01",
            source_kind="INSTITUTIONAL_WORKING_PAPER",
            url="https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf",
            relevance=(
                "Documents the economic basis for hedged spot-futures carry while "
                "leaving venue, collateral, basis, and liquidation risk unresolved."
            ),
        ),
        "HE_ET_AL_2023": U1TheorySource(
            source_id="HE_ET_AL_2023",
            title="Fundamentals of Perpetual Futures",
            authors=["Songrun He", "Asaf Manela", "Omri Ross", "Victor von Wachter"],
            publication_date="2023-01-01",
            source_kind="INSTITUTIONAL_WORKING_PAPER",
            url="https://arxiv.org/abs/2212.06888",
            relevance=(
                "Provides the perpetual-futures pricing and funding mechanics needed "
                "to define carry, hedge slippage, and basis risk."
            ),
        ),
    }


def authoritative_proposals() -> list[U1MechanismProposal]:
    sources = primary_sources()
    return [
        U1MechanismProposal(
            proposal_id="P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA",
            mechanism_name="Volatility-managed broad spot market beta",
            economic_premise=(
                "A broad, survivorship-aware cryptocurrency spot basket may earn a "
                "market risk premium, while realized risk changes faster than expected "
                "return. Holding less cash-funded spot exposure after high measured "
                "volatility may improve geometric compounding and drawdown without "
                "forecasting which coin has the strongest price path."
            ),
            expected_payoff_source=(
                "Compensation for broad cryptocurrency market risk combined with lower "
                "exposure during high-variance states; this is not an arbitrage claim."
            ),
            ex_ante_directional_prediction=(
                "A fixed, unlevered inverse-variance exposure rule should retain "
                "positive cost-net returns while improving drawdown or risk-adjusted "
                "performance versus a preregistered static broad-spot benchmark."
            ),
            primary_sources=[
                sources["MOREIRA_MUIR_2017"],
                sources["LIU_TSYVINSKI_WU_2022"],
            ],
            current_required_fields=[
                "close",
                "high",
                "low",
                "open",
                "timestamp",
                "volume",
            ],
            current_data_reproducible=True,
            current_long_only_spot_execution_supported=True,
            requires_shorting_or_leverage=False,
            expected_turnover="LOW",
            model_complexity="LOW",
            independent_of_retired_lineages=True,
            blocking_reasons=[],
            disposition="SELECT_FOR_PRIMARY_PROTOCOL_DESIGN",
            decision_rationale=(
                "It is the only proposal with two supporting primary sources, complete "
                "current point-in-time data, current long-only spot expressibility, no "
                "leverage requirement, low expected turnover, and no dependency on a "
                "retired Aurex signal or R4 outcome bucket."
            ),
        ),
        U1MechanismProposal(
            proposal_id="P02_SIGNED_JUMP_RISK_PREMIUM",
            mechanism_name="Cross-sectional signed-jump risk premium",
            economic_premise=(
                "Asymmetric realized jump variation may proxy investor attention and "
                "priced jump risk. Coins with different ex-ante signed-jump exposure "
                "may therefore have different subsequent expected returns independently "
                "of endpoint momentum or path-quality ranking."
            ),
            expected_payoff_source=(
                "Compensation or mispricing associated with asymmetric jump risk and "
                "attention to unusually discontinuous price moves."
            ),
            ex_ante_directional_prediction=(
                "A preregistered cross-sectional sort on signed-jump variation should "
                "produce a stable cost-net return difference in the direction declared "
                "by the primary crypto study."
            ),
            primary_sources=[
                sources["PATTON_SHEPPARD_2015"],
                sources["ZHANG_ZHAO_2023"],
            ],
            current_required_fields=["timestamp"],
            additional_required_fields=[
                "point_in_time_high_frequency_prices_at_5m_or_finer"
            ],
            current_data_reproducible=False,
            current_long_only_spot_execution_supported=True,
            requires_shorting_or_leverage=False,
            expected_turnover="MEDIUM",
            model_complexity="MEDIUM",
            independent_of_retired_lineages=True,
            blocking_reasons=[
                "CURRENT_4H_BARS_CANNOT_REPRODUCE_HIGH_FREQUENCY_SIGNED_JUMP_MEASURES"
            ],
            disposition="DEFER_UNTIL_DATA_FOUNDATION_EXISTS",
            decision_rationale=(
                "The mechanism is distinct and research-supported, but approximating "
                "its defining high-frequency statistic from four-hour candles would "
                "change the mechanism before it is tested."
            ),
        ),
        U1MechanismProposal(
            proposal_id="P03_DELTA_NEUTRAL_FUNDING_CARRY",
            mechanism_name="Delta-neutral spot-perpetual funding carry",
            economic_premise=(
                "Persistent futures basis and perpetual funding can compensate a "
                "hedged trader for supplying balance sheet and convergence capital. "
                "The payoff is structurally different from forecasting spot-price "
                "direction, but remains exposed to basis, collateral, venue, and "
                "liquidation risk."
            ),
            expected_payoff_source=(
                "Funding and basis paid by directional or leverage-constrained "
                "perpetual-futures demand to a spot-perpetual hedged position."
            ),
            ex_ante_directional_prediction=(
                "A fully costed and collateralized spot-long/perpetual-short position "
                "should earn positive net carry only when prospective funding exceeds "
                "fees, basis slippage, financing, and tail-risk reserves."
            ),
            primary_sources=[
                sources["CHRISTIN_ET_AL_2022"],
                sources["HE_ET_AL_2023"],
            ],
            current_required_fields=["spot_ohlcv"],
            additional_required_fields=[
                "collateral_and_liquidation_state",
                "historical_fee_schedule",
                "perpetual_funding_payments",
                "perpetual_mark_and_index_prices",
                "point_in_time_spot_perpetual_basis",
            ],
            current_data_reproducible=False,
            current_long_only_spot_execution_supported=False,
            requires_shorting_or_leverage=True,
            expected_turnover="LOW",
            model_complexity="HIGH",
            independent_of_retired_lineages=True,
            blocking_reasons=[
                "AUREX_HAS_NO_QUALIFIED_DERIVATIVES_EXECUTION_OR_RECONCILIATION_PATH",
                "CURRENT_EVIDENCE_HAS_NO_POINT_IN_TIME_FUNDING_BASIS_OR_COLLATERAL_DATA",
            ],
            disposition="DEFER_UNTIL_EXECUTION_FOUNDATION_EXISTS",
            decision_rationale=(
                "The premise is economically distinct, but selecting it now would "
                "require unqualified derivatives execution, leverage, liquidation "
                "modeling, and historical datasets that Aurex has not frozen."
            ),
        ),
    ]


def authoritative_screen(
    *,
    frozen_at: datetime,
    charter: U1MechanismDiscoveryCharter,
) -> U1MechanismTheoryScreen:
    return build_u1_mechanism_theory_screen(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposals=authoritative_proposals(),
        selection_rules=U1_THEORY_SELECTION_RULES,
        strategy_outcome_fields_inspected=[],
        return_metrics_calculated=[],
        preexisting_primary_artifacts=[],
        builder_contract_hash=builder_contract_hash(),
    )


def load_charter(path: Path) -> U1MechanismDiscoveryCharter:
    charter = U1MechanismDiscoveryCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_u1_mechanism_discovery_charter(charter):
        raise ValueError("U1 discovery charter failed its hash audit")
    if charter.maximum_theory_proposals != 3:
        raise ValueError("U1 theory screen exceeds its charter budget")
    return charter


def write_screen(path: Path, screen: U1MechanismTheoryScreen) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = screen.model_dump_json(indent=2) + "\n"
    if U1MechanismTheoryScreen.model_validate_json(serialized) != screen:
        raise ValueError("U1 theory screen JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> U1MechanismTheoryScreen:
    if args.output.exists():
        raise ValueError("Frozen U1 theory screen exists; use --check")
    preexisting = [path.as_posix() for path in args.primary_artifact if path.exists()]
    if preexisting:
        raise ValueError(f"Primary artifact predates theory screen: {preexisting}")
    charter = load_charter(args.charter)
    screen = authoritative_screen(frozen_at=datetime.now(UTC), charter=charter)
    write_screen(args.output, screen)
    stored = U1MechanismTheoryScreen.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != screen or not audit_u1_mechanism_theory_screen(stored):
        raise ValueError("U1 theory screen failed reload verification")
    print(
        f"WROTE {args.output} {stored.screen_evidence_hash} "
        f"selected={stored.selected_proposal_id}",
        flush=True,
    )
    return stored


def run_check(args) -> U1MechanismTheoryScreen:
    charter = load_charter(args.charter)
    stored = U1MechanismTheoryScreen.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_screen(frozen_at=stored.frozen_at, charter=charter)
    if stored != expected or not audit_u1_mechanism_theory_screen(stored):
        raise ValueError("Stored U1 theory screen differs from rebuild")
    print(
        f"PASS u1_theory_screen={stored.screen_evidence_hash} "
        f"selected={stored.selected_proposal_id}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the no-return U1 mechanism theory screen."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--primary-artifact",
        type=Path,
        nargs="*",
        default=list(DEFAULT_PRIMARY_ARTIFACTS),
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
