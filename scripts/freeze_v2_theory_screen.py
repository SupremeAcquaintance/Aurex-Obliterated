import argparse
import hashlib
import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

from aurex.backtest_engine.research_v2_discovery_charter import (
    V2MechanismDiscoveryCharter,
    audit_v2_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v2_theory_screen import (
    V2_THEORY_SELECTION_RULES,
    V2MechanismTheoryProposal,
    V2MechanismTheoryScreen,
    V2TheoryFeasibility,
    V2TheorySource,
    audit_v2_mechanism_theory_screen,
    build_v2_mechanism_theory_screen,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_discovery_charter_module = import_module(
    "scripts.freeze_v2_discovery_charter"
)
authoritative_charter = _discovery_charter_module.authoritative_charter
load_inputs = _discovery_charter_module.load_inputs

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_CHARTER = DEFAULT_EVIDENCE_ROOT / "v2_mechanism_discovery_charter_v1.json"
DEFAULT_FOUNDATION_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_FOUNDATION_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_result_v1.json"
)
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "v2_mechanism_theory_screen_v1.json"
DEFAULT_SUCCESSOR_ARTIFACTS = (
    DEFAULT_EVIDENCE_ROOT / "v2_full_acquisition_protocol_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_full_dataset_manifest_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_primary_development_protocol_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_primary_development_result_v1.json",
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v2_theory_screen.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_theory_screen.py",
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


def primary_sources(accessed_at: datetime) -> dict[str, V2TheorySource]:
    return {
        "BINANCE_FUNDING_2026": V2TheorySource(
            source_id="BINANCE_FUNDING_2026",
            title="What Are Funding Rates in Crypto Markets?",
            authors_or_publisher=["Binance Academy"],
            publication_or_revision_date="2026-06-25",
            accessed_at=accessed_at,
            source_kind="OFFICIAL_EXCHANGE_DOCUMENTATION",
            url=(
                "https://academy.binance.com/en/articles/"
                "what-are-funding-rates-in-crypto-markets"
            ),
            supported_claims=[
                "Funding direction reverses with the sign of the funding rate.",
                "Funding depends on interest and premium components and can change.",
                "Funding intervals and contract terms cannot be assumed constant.",
            ],
        ),
        "BINANCE_MARGIN_CATALOG_2026": V2TheorySource(
            source_id="BINANCE_MARGIN_CATALOG_2026",
            title="Binance Developer API Catalog - Margin",
            authors_or_publisher=["Binance"],
            publication_or_revision_date=None,
            accessed_at=accessed_at,
            source_kind="OFFICIAL_EXCHANGE_DOCUMENTATION",
            url="https://developers.binance.com/en/docs/catalog",
            supported_claims=[
                "The current Margin API exposes account, borrow, and repay surfaces.",
                (
                    "Current API availability does not prove historical borrow "
                    "availability, rates, limits, recalls, or executable inventory."
                ),
            ],
        ),
        "HE_ET_AL_2022": V2TheorySource(
            source_id="HE_ET_AL_2022",
            title="Fundamentals of Perpetual Futures",
            authors_or_publisher=[
                "Asaf Manela",
                "Omri Ross",
                "Songrun He",
                "Victor von Wachter",
            ],
            publication_or_revision_date="2022-12-13",
            accessed_at=accessed_at,
            source_kind="INSTITUTIONAL_WORKING_PAPER",
            url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4301150",
            supported_claims=[
                "Perpetuals have no expiry date that forces spot convergence.",
                "Funding anchors perpetual and spot prices but leaves basis risk.",
                "Trading costs change no-arbitrage bounds and executable conclusions.",
            ],
        ),
        "ACKERER_ET_AL_2025": V2TheorySource(
            source_id="ACKERER_ET_AL_2025",
            title="Perpetual Futures Pricing",
            authors_or_publisher=[
                "Damien Ackerer",
                "Julien Hugonnier",
                "Urban Jermann",
            ],
            publication_or_revision_date="2025-11-20",
            accessed_at=accessed_at,
            source_kind="PEER_REVIEWED_ARTICLE",
            url="https://onlinelibrary.wiley.com/doi/full/10.1111/mafi.70018",
            supported_claims=[
                "Periodic funding is the anchoring mechanism for perpetual futures.",
                "Funding specification and interest rates affect perpetual pricing.",
                "A spot-perpetual relation is not a guaranteed realized trading profit.",
            ],
        ),
        "GORNALL_ET_AL_2024": V2TheorySource(
            source_id="GORNALL_ET_AL_2024",
            title="Perpetual Futures and Basis Risk: Evidence from Cryptocurrency",
            authors_or_publisher=[
                "Martin Rinaldi",
                "Will Gornall",
                "Yizhou Xiao",
            ],
            publication_or_revision_date="2024-11-27",
            accessed_at=accessed_at,
            source_kind="INSTITUTIONAL_WORKING_PAPER",
            url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5036933",
            supported_claims=[
                "Constrained arbitrage capital can permit material futures basis risk.",
                "Funding can improve alignment without eliminating dislocations.",
                "Collateral and crisis liquidity remain part of the mechanism risk.",
            ],
        ),
    }


def authoritative_proposals(frozen_at: datetime) -> list[V2MechanismTheoryProposal]:
    sources = primary_sources(frozen_at)
    common_data = [
        "funding_event_timestamp_interval_and_rate",
        "index_price_klines",
        "mark_price_klines",
        "premium_index_klines",
        "spot_klines",
        "usd_m_perpetual_contract_klines",
    ]
    common_metadata = [
        "contract_listing_delisting_and_status_history",
        "funding_formula_caps_floors_and_interval_history",
        "historical_margin_tiers_and_collateral_rules",
        "historical_spot_and_usd_m_fee_schedule",
        "point_in_time_tick_step_minimum_and_notional_rules",
    ]
    return [
        V2MechanismTheoryProposal(
            proposal_id="P01_POSITIVE_FUNDING_SPOT_PERP_CARRY",
            mechanism_name="Positive-funding long-spot short-perpetual carry",
            economic_premise=(
                "When a USD-M perpetual has positive funding, the short side receives "
                "the periodic transfer. Pairing a cash-funded long spot position with "
                "an equal-base-quantity short perpetual can reduce first-order spot "
                "directional exposure while supplying balance sheet to leveraged "
                "perpetual demand. The remaining payoff is carry and basis movement "
                "after all costs, collateral constraints, and failure paths."
            ),
            ex_ante_payoff_direction=(
                "The paired position may receive funding only during positive-rate "
                "intervals. It has an economically positive premise only when funding "
                "and admissible basis effects exceed spot and perpetual fees, spread, "
                "slippage, financing, collateral drag, hedge error, and tail reserves."
            ),
            exact_point_in_time_data_requirements=common_data,
            historical_metadata_requirements=common_metadata,
            paired_execution_path=(
                "Buy cash-funded spot and sell the same base quantity of the USD-M "
                "perpetual; settle signed funding at the official event time; maintain "
                "collateral and hedge tolerance; then close both legs with rollback, "
                "kill-switch, liquidation, ADL, and reconciliation evidence."
            ),
            principal_risks=[
                "basis_widening_and_no_expiry_forced_convergence",
                "collateral_and_liquidation_loss",
                "contract_or_funding_rule_change",
                "fees_spread_slippage_and_hedge_imbalance",
                "funding_sign_reversal_or_collapse",
                "partial_fill_venue_and_stablecoin_risk",
            ],
            falsification_condition=(
                "Stop before return testing if a frozen full dataset cannot reconstruct "
                "funding, spot, perpetual, mark, index, premium, contract, fee, and "
                "margin state at each decision time, or if the paired execution protocol "
                "cannot model both legs and every declared failure path deterministically."
            ),
            primary_sources=[
                sources["BINANCE_FUNDING_2026"],
                sources["HE_ET_AL_2022"],
                sources["ACKERER_ET_AL_2025"],
            ],
            feasibility=V2TheoryFeasibility(
                theory_support="SUPPORTED",
                point_in_time_data="FEASIBLE_PENDING_FROZEN_FULL_ACQUISITION",
                execution_fit="SYNTHETICALLY_PROVEN_RESEARCH_ONLY",
                first_order_directional_risk=(
                    "LOWER_THAN_UNHEDGED_SPOT_BUT_NOT_ZERO"
                ),
                fits_synthetic_long_spot_short_perp_foundation=True,
                requires_spot_borrowing=False,
                related_to_selected_primary=False,
            ),
            nonselection_reasons=[],
            disposition="SELECT_FOR_FULL_DATA_AND_PROTOCOL_DESIGN",
            decision_rationale=(
                "This is the only screened premise whose required direction matches "
                "Aurex's audited long-spot/short-perpetual synthetic foundation without "
                "spot borrowing. The source census and pilot support bounded data "
                "feasibility. Selection authorizes only a separately frozen full-data "
                "and development-protocol design."
            ),
        ),
        V2MechanismTheoryProposal(
            proposal_id="P02_PREMIUM_CONVERGENCE_SPOT_PERP_BASIS",
            mechanism_name="Spot-perpetual premium convergence",
            economic_premise=(
                "A perpetual trading above its point-in-time spot or index reference "
                "may converge as funding encourages the opposing paired position and "
                "constrained arbitrage capital enters. A long-spot short-perpetual pair "
                "could therefore isolate some premium compression, but a perpetual has "
                "no expiry date that guarantees convergence."
            ),
            ex_ante_payoff_direction=(
                "The proposed pair benefits only if the observed premium compresses "
                "enough to exceed both-leg execution costs, funding paid or received, "
                "collateral drag, hedge error, and adverse basis expansion."
            ),
            exact_point_in_time_data_requirements=common_data,
            historical_metadata_requirements=common_metadata,
            paired_execution_path=(
                "Buy cash-funded spot and short the same-base USD-M perpetual while "
                "tracking mark, index, premium, funding, hedge tolerance, collateral, "
                "and paired close or rollback evidence."
            ),
            principal_risks=[
                "basis_can_widen_before_or_instead_of_converging",
                "no_contract_expiry_forces_convergence",
                "overlap_with_positive_funding_carry_primary",
                "turnover_and_execution_cost",
            ],
            falsification_condition=(
                "Do not elevate this related premise if the later primary protocol "
                "cannot distinguish ex-ante premium compression from funding carry, "
                "or if point-in-time premium and executable paired-leg costs cannot be "
                "reconstructed without outcome-conditioned thresholds."
            ),
            primary_sources=[
                sources["ACKERER_ET_AL_2025"],
                sources["GORNALL_ET_AL_2024"],
                sources["HE_ET_AL_2022"],
            ],
            feasibility=V2TheoryFeasibility(
                theory_support="SUPPORTED",
                point_in_time_data="FEASIBLE_PENDING_FROZEN_FULL_ACQUISITION",
                execution_fit="SYNTHETICALLY_PROVEN_RESEARCH_ONLY",
                first_order_directional_risk=(
                    "LOWER_THAN_UNHEDGED_SPOT_BUT_NOT_ZERO"
                ),
                fits_synthetic_long_spot_short_perp_foundation=True,
                requires_spot_borrowing=False,
                related_to_selected_primary=True,
            ),
            nonselection_reasons=[
                "NO_EXPIRY_DATE_GUARANTEES_PREMIUM_CONVERGENCE",
                "RELATED_TO_SELECTED_POSITIVE_FUNDING_PRIMARY",
                "SECOND_SELECTABLE_PRIMARY_WOULD_BREACH_CHARTER_BUDGET",
            ],
            disposition="DEFER_AS_NONSELECTABLE_RELATED_DIAGNOSTIC",
            decision_rationale=(
                "The premise is research-supported and mechanically expressible, but "
                "it overlaps the selected carry pair and has no expiry-forced terminal "
                "convergence. It may only become a nonselectable diagnostic defined "
                "inside a later frozen protocol, never a second best-result candidate."
            ),
        ),
        V2MechanismTheoryProposal(
            proposal_id="P03_NEGATIVE_FUNDING_REVERSE_CARRY",
            mechanism_name="Negative-funding short-spot long-perpetual reverse carry",
            economic_premise=(
                "When funding is negative, the perpetual long receives the periodic "
                "transfer. Hedging that exposure would require shorting the underlying "
                "spot asset against the long perpetual, making borrow availability, "
                "interest, limits, recall, liquidation, and close-out behavior part of "
                "the mechanism rather than optional implementation details."
            ),
            ex_ante_payoff_direction=(
                "The reverse pair may receive negative funding only if the spot short "
                "can be borrowed and maintained. Any funding receipt must exceed borrow "
                "interest, both-leg costs, basis movement, recall risk, collateral "
                "drag, and liquidation reserves."
            ),
            exact_point_in_time_data_requirements=[
                *common_data,
                "spot_borrow_availability_rate_limit_recall_and_inventory_history",
            ],
            historical_metadata_requirements=[
                *common_metadata,
                "historical_margin_borrow_eligibility_and_repayment_rules",
            ],
            paired_execution_path=(
                "Borrow and short spot, buy the same base quantity of the USD-M "
                "perpetual, settle negative funding to the long, accrue borrow costs, "
                "and reconcile borrow, spot, perpetual, collateral, repayment, recall, "
                "liquidation, and close-out state."
            ),
            principal_risks=[
                "borrow_unavailable_recalled_or_rate_spike",
                "long_perpetual_liquidation",
                "negative_funding_sign_reversal",
                "unmodeled_reverse_pair_execution",
            ],
            falsification_condition=(
                "Reject under this charter unless point-in-time historical borrow "
                "availability, rates, limits, recalls, and repayment state can be "
                "reconstructed and a separately audited reverse-carry execution model "
                "covers both legs, borrow accounting, and forced close-out."
            ),
            primary_sources=[
                sources["BINANCE_FUNDING_2026"],
                sources["BINANCE_MARGIN_CATALOG_2026"],
                sources["HE_ET_AL_2022"],
            ],
            feasibility=V2TheoryFeasibility(
                theory_support="SUPPORTED",
                point_in_time_data="BLOCKED_BY_POINT_IN_TIME_BORROW_HISTORY",
                execution_fit="UNMODELED_REVERSE_CARRY_AND_SPOT_BORROW",
                first_order_directional_risk=(
                    "LOWER_THAN_UNHEDGED_SPOT_BUT_NOT_ZERO"
                ),
                fits_synthetic_long_spot_short_perp_foundation=False,
                requires_spot_borrowing=True,
                related_to_selected_primary=False,
            ),
            nonselection_reasons=[
                "AUREX_FOUNDATION_SUPPORTS_LONG_SPOT_SHORT_PERPETUAL_ONLY",
                "POINT_IN_TIME_SPOT_BORROW_HISTORY_IS_NOT_QUALIFIED",
                "SPOT_BORROW_RECALL_REPAYMENT_AND_FORCED_CLOSE_ARE_UNMODELED",
            ],
            disposition=(
                "REJECT_CURRENT_CHARTER_BORROW_AND_EXECUTION_INFEASIBLE"
            ),
            decision_rationale=(
                "The funding direction is economically coherent, but the required "
                "spot-borrow history and reverse-pair lifecycle are absent. Current "
                "Margin API existence cannot reconstruct 2023-2024 borrow inventory "
                "or make the path executable, so this premise is rejected under V2."
            ),
        ),
    ]


def authoritative_screen(
    *,
    frozen_at: datetime,
    charter: V2MechanismDiscoveryCharter,
) -> V2MechanismTheoryScreen:
    return build_v2_mechanism_theory_screen(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        capability_audit_evidence_hash=charter.capability_audit_evidence_hash,
        source_census_result_evidence_hash=(
            charter.source_census_result_evidence_hash
        ),
        acquisition_protocol_evidence_hash=(
            charter.acquisition_protocol_evidence_hash
        ),
        pilot_result_evidence_hash=charter.pilot_result_evidence_hash,
        derivatives_foundation_protocol_evidence_hash=(
            charter.derivatives_foundation_protocol_evidence_hash
        ),
        derivatives_foundation_result_evidence_hash=(
            charter.derivatives_foundation_result_evidence_hash
        ),
        contamination_ledger_evidence_hash=(
            charter.contamination_ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        proposals=authoritative_proposals(frozen_at),
        selection_rules=V2_THEORY_SELECTION_RULES,
        limitations=[
            (
                "The screen uses theory and source/execution feasibility only; it "
                "contains no Aurex market value, signal, trade, return, or parameter."
            ),
            (
                "Selecting P01 does not prove positive funding persistence, net carry, "
                "capacity, robustness, or profitability."
            ),
            (
                "The synthetic engine proves internal arithmetic invariants only, not "
                "historical or future Binance execution, margin, liquidation, or ADL."
            ),
            (
                "The 31 source-complete symbols are a data-feasibility set and not a "
                "selected trading universe."
            ),
            (
                "Full archive acquisition requires a separate frozen resource, "
                "integrity, normalization, metadata, and partition protocol."
            ),
            (
                "Development, validation, holdout, forward paper, sandbox, live, and "
                "capital permissions remain closed."
            ),
        ],
    )


def load_charter(args) -> V2MechanismDiscoveryCharter:
    protocol, result = load_inputs(args)
    charter = V2MechanismDiscoveryCharter.model_validate_json(
        args.charter.read_text(encoding="utf-8")
    )
    if not audit_v2_mechanism_discovery_charter(charter):
        raise ValueError("V2 discovery charter hash audit failed")
    expected = authoritative_charter(
        registered_at=charter.registered_at,
        protocol=protocol,
        result=result,
    )
    if charter != expected:
        raise ValueError("V2 discovery charter is not reproducible")
    if charter.maximum_theory_proposals != 3:
        raise ValueError("V2 theory screen proposal budget changed")
    if charter.maximum_selected_primary_mechanisms != 1:
        raise ValueError("V2 selected-primary budget changed")
    if charter.maximum_return_tested_mechanisms_under_charter != 0:
        raise ValueError("V2 charter unexpectedly permits return testing")
    return charter


def write_screen(path: Path, screen: V2MechanismTheoryScreen) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = screen.model_dump_json(indent=2) + "\n"
    if V2MechanismTheoryScreen.model_validate_json(serialized) != screen:
        raise ValueError("V2 theory screen JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2MechanismTheoryScreen:
    if args.output.exists():
        raise ValueError("Frozen V2 theory screen exists; use --check")
    preexisting = [
        path.as_posix() for path in args.successor_artifact if path.exists()
    ]
    if preexisting:
        raise ValueError(
            f"Successor artifact predates V2 theory screen: {preexisting}"
        )
    charter = load_charter(args)
    screen = authoritative_screen(
        frozen_at=datetime.now(UTC),
        charter=charter,
    )
    write_screen(args.output, screen)
    print(
        f"WROTE {args.output} {screen.screen_evidence_hash} "
        f"selected={screen.selected_proposal_id}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2MechanismTheoryScreen:
    charter = load_charter(args)
    stored = V2MechanismTheoryScreen.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_screen(
        frozen_at=stored.frozen_at,
        charter=charter,
    )
    if stored != expected or not audit_v2_mechanism_theory_screen(stored):
        raise ValueError("Stored V2 theory screen differs from rebuild")
    print(
        "PASS "
        f"v2_theory_screen={stored.screen_evidence_hash} "
        f"selected={stored.selected_proposal_id} "
        f"return_tests={stored.return_tested_mechanism_count}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the V2 no-return mechanism theory screen."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--successor-artifact",
        type=Path,
        nargs="*",
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
