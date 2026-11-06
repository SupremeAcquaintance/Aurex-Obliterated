import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.research_post_v4_capability_review import (  # noqa: E402
    POST_V4_ALLOWED_NEXT_TRACKS,
    PostV4CapabilityAssessment,
    PostV4CapabilityGapReview,
    PostV4OperatorDecision,
    audit_post_v4_capability_gap_review,
    build_post_v4_capability_gap_review,
)
from aurex.backtest_engine.research_v4_feasibility_screen import (  # noqa: E402
    V4MechanismFeasibilityScreen,
    audit_v4_mechanism_feasibility_screen,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v4_feasibility_screen import (  # noqa: E402
    authoritative_screen,
)
from scripts.freeze_v4_feasibility_screen import (  # noqa: E402
    builder_contract_hash as v4_screen_builder_hash,
)
from scripts.freeze_v4_feasibility_screen import (  # noqa: E402
    load_inputs as load_v4_inputs,
)

DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
DEFAULT_P01_ADDENDUM = Path(
    "data/evidence/v4_p01_terminal_audit_addendum_v1.json"
)
DEFAULT_P02_CONTRACT = Path(
    "data/evidence/v4_p02_feasibility_contract_v1.json"
)
DEFAULT_V4_SCREEN = Path(
    "data/evidence/v4_mechanism_feasibility_screen_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/post_v4_capability_gap_review_v1.json"
)


def source_contract_hash(paths: list[Path]) -> str:
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


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_post_v4_capability_review.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_post_v4_capability_review.py",
        ]
    )


def load_inputs(args):
    v4_evidence = load_v4_inputs(args)
    screen = V4MechanismFeasibilityScreen.model_validate_json(
        args.v4_screen.read_text(encoding="utf-8")
    )
    expected = authoritative_screen(
        frozen_at=screen.frozen_at,
        charter=v4_evidence[0],
        register=v4_evidence[1],
        p01=v4_evidence[2],
        p02_contract=v4_evidence[3],
        p02=v4_evidence[4],
    )
    if (
        screen != expected
        or not audit_v4_mechanism_feasibility_screen(screen)
        or screen.builder_contract_hash != v4_screen_builder_hash()
        or screen.selected_primary_count != 0
        or not screen.v4_closed
        or screen.authorizes_return_testing
    ):
        raise ValueError("Frozen V4 feasibility screen audit failed")
    return v4_evidence[0], v4_evidence[1], screen


def capability(
    capability_id: str,
    status: str,
    evidence_artifacts: list[str],
    implication: str,
) -> PostV4CapabilityAssessment:
    return PostV4CapabilityAssessment(
        capability_id=capability_id,
        status=status,
        evidence_artifacts=evidence_artifacts,
        implication=implication,
    )


def operator_decision(
    decision_id: str,
    required_value: str,
    reason: str,
) -> PostV4OperatorDecision:
    return PostV4OperatorDecision(
        decision_id=decision_id,
        required_value=required_value,
        why_it_blocks_successor_discovery=reason,
    )


def authoritative_review(
    *,
    frozen_at: datetime,
    charter,
    register,
    screen: V4MechanismFeasibilityScreen,
) -> PostV4CapabilityGapReview:
    assessments = [
        capability(
            "AUTHENTICATED_EXTERNAL_TRADINGVIEW_DELIVERY",
            "IMPLEMENTED_NOT_EXTERNALLY_PROVEN",
            [
                "docs/12_TRADINGVIEW_WEBHOOK_EVIDENCE.md",
                "docs/10_PROJECT_CONTROL.md",
            ],
            (
                "Authentication, receipt hashing, idempotency, normalization, "
                "risk routing, and monitoring exist, but no genuine TradingView "
                "alert has produced external delivery evidence."
            ),
        ),
        capability(
            "DETERMINISTIC_PRODUCTION_EXCHANGE_ADAPTER",
            "ABSENT",
            ["docs/10_PROJECT_CONTROL.md"],
            (
                "No qualified live-venue adapter proves client IDs, acknowledgements, "
                "retry semantics, fills, balances, positions, fees, reconciliation, "
                "or kill switches against a selected execution venue."
            ),
        ),
        capability(
            "EVIDENCE_GRADE_BAR_REPLAY",
            "PROVEN",
            [
                "docs/05_HISTORICAL_DATASETS.md",
                "docs/06_REFERENCE_REPLAY.md",
                "docs/10_PROJECT_CONTROL.md",
            ],
            (
                "Immutable chronological bar replay, realistic modeled costs, "
                "walk-forward evaluation, and rejection evidence are operational "
                "for compatible bar-based strategies."
            ),
        ),
        capability(
            "EXECUTION_GRADE_HISTORICAL_TICK_OR_L2",
            "ABSENT",
            [
                "data/evidence/v4_mechanism_feasibility_screen_v1.json",
                "data/evidence/v3_mechanism_feasibility_screen_v1.json",
            ],
            (
                "Aurex has not qualified complete revision-bound tick or sequence-"
                "aware L2 evidence with disconnect recovery for a selectable "
                "short-horizon, passive, arbitrage, or options mechanism."
            ),
        ),
        capability(
            "FORWARD_PAPER_ENGINE_AND_RISK_CONTROLS",
            "IMPLEMENTED_NOT_EXTERNALLY_PROVEN",
            ["docs/10_PROJECT_CONTROL.md"],
            (
                "Evidence-grade costed paper execution and risk controls exist, "
                "but no eligible strategy has opened a forward campaign and no "
                "long-duration external operation has qualified them."
            ),
        ),
        capability(
            "OPERATOR_CAPITAL_AND_LOSS_BUDGET",
            "OPERATOR_INPUT_REQUIRED",
            [],
            (
                "Starting capital, maximum tolerable loss, daily stop, and research "
                "or data budget are not frozen, so capacity and risk design cannot "
                "be economically or operationally grounded."
            ),
        ),
        capability(
            "OPERATOR_JURISDICTION_ACCOUNT_AND_PRODUCT_ACCESS",
            "OPERATOR_INPUT_REQUIRED",
            [],
            (
                "The intended venue, jurisdiction, KYC account state, permitted "
                "spot or derivatives products, API access, and restrictions are "
                "not evidenced; public data access cannot substitute."
            ),
        ),
        capability(
            "PINE_TO_AUREX_TRADE_LEVEL_PARITY",
            "ABSENT",
            [
                "docs/07_TRADINGVIEW_PARITY.md",
                "docs/09_FROZEN_TRADINGVIEW_RUN.md",
            ],
            (
                "The rejected trend_pullback_v1 v1.3 package has not completed "
                "trade-level TradingView parity, so the local engine still lacks "
                "an externally compared Pine-semantics proof."
            ),
        ),
        capability(
            "POINT_IN_TIME_FEES_FILTERS_AND_VENUE_RULES",
            "PARTIAL",
            [
                "data/evidence/v4_p01_terminal_audit_addendum_v1.json",
                "data/evidence/v4_mechanism_feasibility_screen_v1.json",
            ],
            (
                "Modeled costs support conservative bar research, but complete "
                "historical account-tier fees, filters, product state, margin, "
                "settlement, and venue rules are not qualified for new execution-"
                "sensitive mechanisms."
            ),
        ),
        capability(
            "PROVEN_POSITIVE_NET_STRATEGY_EDGE",
            "ABSENT",
            [
                "docs/10_PROJECT_CONTROL.md",
                "data/evidence/v4_mechanism_feasibility_screen_v1.json",
            ],
            (
                "Every completed candidate is rejected or retired and V3/V4 "
                "selected zero primaries; Aurex currently has no positive net "
                "expectancy claim, eligible strategy, or profit basis."
            ),
        ),
        capability(
            "QUALIFIED_EXCHANGE_SANDBOX_OPERATION",
            "ABSENT",
            ["docs/10_PROJECT_CONTROL.md"],
            (
                "No selected venue and account have completed deterministic "
                "sandbox order lifecycle, balance, position, fee, reconciliation, "
                "monitoring, stale-data, and kill-switch drills."
            ),
        ),
    ]
    decisions = [
        operator_decision(
            "ACCOUNT_AND_API_ACCESS",
            (
                "Document whether a verified account exists, its KYC state, API "
                "availability, permission scopes, and sandbox or testnet access."
            ),
            (
                "Adapter design and execution feasibility depend on the actual "
                "account's capabilities; public documentation and market data "
                "cannot prove account-specific access."
            ),
        ),
        operator_decision(
            "DATA_ACQUISITION_BUDGET",
            (
                "Set the maximum one-time and monthly amount available for "
                "historical tick/L2 data, metadata, storage, and transfer."
            ),
            (
                "Microstructure, arbitrage, and options research repeatedly failed "
                "on free-source completeness; a budget determines whether those "
                "families are feasible or must remain excluded."
            ),
        ),
        operator_decision(
            "INTENDED_EXECUTION_VENUE",
            (
                "Name the exact exchange and account environment intended for "
                "future sandbox and, only after qualification, micro-live use."
            ),
            (
                "Fees, symbols, filters, order semantics, market access, APIs, "
                "maintenance behavior, and legal restrictions are venue-specific."
            ),
        ),
        operator_decision(
            "MAXIMUM_ACCEPTABLE_LOSS",
            (
                "Set absolute total, daily, per-trade, and evidence-breach loss "
                "limits that Aurex may never exceed."
            ),
            (
                "No capital-protection or capacity policy is meaningful without "
                "a human-owned maximum loss boundary independent of hoped-for "
                "returns."
            ),
        ),
        operator_decision(
            "PERMITTED_PRODUCT_SCOPE",
            (
                "Choose spot-only, spot plus perpetuals, or another explicitly "
                "legal and account-enabled product set; do not assume leverage."
            ),
            (
                "Product scope determines required data, financing, margin, "
                "liquidation, settlement, tail-risk, and execution foundations."
            ),
        ),
        operator_decision(
            "STARTING_TRADING_CAPITAL",
            (
                "Set the capital actually available for eventual micro-live use, "
                "excluding emergency funds and without borrowing."
            ),
            (
                "The first $100 milestone, minimum order sizes, fees, capacity, "
                "drawdown limits, and realistic time horizon cannot be designed "
                "without a real capital denominator."
            ),
        ),
    ]
    return build_post_v4_capability_gap_review(
        frozen_at=frozen_at,
        v4_discovery_charter_evidence_hash=charter.charter_evidence_hash,
        v4_proposal_register_evidence_hash=register.register_evidence_hash,
        v4_feasibility_screen_evidence_hash=screen.screen_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        capability_assessments=assessments,
        required_operator_decisions=decisions,
        allowed_next_tracks=POST_V4_ALLOWED_NEXT_TRACKS,
        recommended_sequence=[
            (
                "01_PRESERVE_V4_ZERO_SELECTION_AND_FORBID_RETRY_OR_RESIZE"
            ),
            (
                "02_COLLECT_AND_FREEZE_THE_SIX_OPERATOR_ACCESS_CAPITAL_AND_"
                "DATA_DECISIONS"
            ),
            (
                "03_COMPLETE_REJECTED_V1_3_PARITY_ONLY_WITH_EXPLICIT_"
                "TRADINGVIEW_AUTHORITY"
            ),
            (
                "04_COMPLETE_ONE_GENUINE_AUTHENTICATED_WEBHOOK_DELIVERY_TO_"
                "PAPER_SAFE_REJECTION"
            ),
            (
                "05_CHOOSE_A_SUCCESSOR_RESEARCH_DOMAIN_ONLY_FROM_PROVEN_"
                "ACCESSIBLE_CAPABILITIES"
            ),
            (
                "06_FREEZE_A_NEW_DISCOVERY_CHARTER_BEFORE_ANY_SOURCE_REQUEST_"
                "PARAMETER_OR_OUTCOME"
            ),
        ],
        limitations=[
            (
                "This review diagnoses capability and operator-input gaps; it "
                "does not propose or select a trading mechanism."
            ),
            (
                "No positive edge, reliability, expected profit, time-to-profit, "
                "or first-$100 probability is claimed."
            ),
            (
                "A paid data budget would enable investigation, not guarantee a "
                "selectable mechanism or profitable strategy."
            ),
            (
                "A venue account and API access would enable sandbox evidence, "
                "not live-trading eligibility."
            ),
            (
                "Rejected v1.3 parity validates engine semantics only and cannot "
                "promote or rescue the rejected strategy."
            ),
            (
                "Webhook delivery evidence must terminate at paper-safe rejection "
                "while no strategy is eligible."
            ),
            (
                "No TradingView mutation is authorized by this artifact; explicit "
                "human authority remains mandatory."
            ),
            (
                "No successor discovery, network request, market import, parameter, "
                "return, candidate, paper eligibility, sandbox eligibility, live "
                "eligibility, or capital permission exists."
            ),
        ],
    )


def write_review(path: Path, review: PostV4CapabilityGapReview) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (review.model_dump_json(indent=2) + "\n").encode("utf-8")
    if PostV4CapabilityGapReview.model_validate_json(serialized) != review:
        raise ValueError("Post-V4 capability review JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale capability review output exists: {temporary}")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def run_freeze(args) -> PostV4CapabilityGapReview:
    if args.output.exists():
        raise ValueError("Post-V4 capability review exists; use --check")
    charter, register, screen = load_inputs(args)
    review = authoritative_review(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
        screen=screen,
    )
    write_review(args.output, review)
    print(
        f"WROTE {args.output} {review.review_evidence_hash} "
        f"decision={review.decision} "
        f"operator_decisions={len(review.required_operator_decisions)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> PostV4CapabilityGapReview:
    charter, register, screen = load_inputs(args)
    review = PostV4CapabilityGapReview.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_review(
        frozen_at=review.frozen_at,
        charter=charter,
        register=register,
        screen=screen,
    )
    if (
        review != expected
        or not audit_post_v4_capability_gap_review(review)
    ):
        raise ValueError("Post-V4 capability review is not reproducible")
    print(
        f"PASS post_v4_review={review.review_evidence_hash} "
        f"decision={review.decision} "
        f"operator_decisions={len(review.required_operator_decisions)} "
        f"returns={review.return_metrics_calculated}",
        flush=True,
    )
    return review


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the post-V4 capability-gap review."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--p01-addendum",
        type=Path,
        default=DEFAULT_P01_ADDENDUM,
    )
    parser.add_argument(
        "--p02-contract",
        type=Path,
        default=DEFAULT_P02_CONTRACT,
    )
    parser.add_argument("--v4-screen", type=Path, default=DEFAULT_V4_SCREEN)
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
