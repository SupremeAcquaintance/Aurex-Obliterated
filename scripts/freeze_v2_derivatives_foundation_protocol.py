import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2DerivativesAcquisitionProtocol,
    audit_v2_derivatives_acquisition_protocol,
)
from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2DerivativesAccountingProtocol,
    V2DerivativesFoundationProtocol,
    V2DerivativesReconciliationProtocol,
    V2DerivativesRiskProtocol,
    V2DerivativesSyntheticScenario,
    V2PairedExecutionProtocol,
    audit_v2_derivatives_foundation_protocol,
    build_v2_derivatives_foundation_protocol,
)
from aurex.backtest_engine.research_v2_pilot_acquisition import (
    V2_PILOT_PASS_DECISION,
    V2PilotAcquisitionResult,
    audit_v2_pilot_acquisition_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_ACQUISITION_PROTOCOL = Path(
    "data/evidence/v2_derivatives_acquisition_protocol_v1.json"
)
DEFAULT_PILOT_RESULT = Path(
    "data/evidence/v2_derivatives_pilot_acquisition_result_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_OUTPUT = Path(
    "data/evidence/v2_derivatives_foundation_protocol_v1.json"
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root
        / "scripts"
        / "freeze_v2_derivatives_foundation_protocol.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_derivatives_foundation_protocol.py",
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


def pilot_runner_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "run_v2_acquisition_pilot.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_pilot_acquisition.py",
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
) -> tuple[V2DerivativesAcquisitionProtocol, V2PilotAcquisitionResult]:
    acquisition = V2DerivativesAcquisitionProtocol.model_validate_json(
        args.acquisition_protocol.read_text(encoding="utf-8")
    )
    if not audit_v2_derivatives_acquisition_protocol(acquisition):
        raise ValueError("V2 acquisition protocol audit failed")
    pilot = V2PilotAcquisitionResult.model_validate_json(
        args.pilot_result.read_text(encoding="utf-8")
    )
    pilot_audit = audit_v2_pilot_acquisition_result(
        result=pilot,
        protocol=acquisition,
        current_runner_contract_hash=pilot_runner_contract_hash(),
        evidence_root=args.evidence_root,
        inspect_local_archives=True,
    )
    if pilot_audit["status"] != "PASS":
        raise ValueError(f"V2 pilot result audit failed: {pilot_audit['reasons']}")
    if pilot.decision != V2_PILOT_PASS_DECISION:
        raise ValueError("V2 pilot did not permit foundation progression")
    return acquisition, pilot


def scenarios() -> list[V2DerivativesSyntheticScenario]:
    values = [
        (
            "S01_FULL_OPEN_FUNDING_CLOSE_RECONCILE",
            "Open both legs fully, credit positive funding to the short, close both "
            "legs, and reconcile every cash-flow component.",
            ["final_state_flat", "funding_positive", "reconciliation_matched"],
        ),
        (
            "S02_FIRST_LEG_PARTIAL_SECOND_REJECT_ROLLBACK",
            "Partially fill spot, reject the perpetual leg, cancel remainder, and "
            "flatten the exposed spot through fee-bearing rollback.",
            ["final_state_flat", "rollback_fees_ledgered", "zero_residual_delta"],
        ),
        (
            "S03_DUPLICATE_FILL_IDEMPOTENCY",
            "Deliver the same venue fill twice and prove the second delivery cannot "
            "change quantity, cash, fees, or the event chain.",
            ["duplicate_rejected", "ledger_state_unchanged"],
        ),
        (
            "S04_DUPLICATE_FUNDING_IDEMPOTENCY",
            "Deliver one funding settlement twice and prove the event key prevents "
            "a duplicated credit or debit.",
            ["duplicate_rejected", "funding_applied_once"],
        ),
        (
            "S05_OPEN_TIMEOUT_CANCEL_AND_ROLLBACK",
            "Expire an incompletely hedged opening, cancel outstanding orders, and "
            "flatten all filled exposure before accepting another open.",
            ["orders_cancelled", "rollback_completed", "zero_residual_delta"],
        ),
        (
            "S06_INITIAL_MARGIN_PREFLIGHT_REJECTION",
            "Request a pair larger than available collateral and reject it before "
            "either synthetic venue order can exist.",
            ["no_orders_created", "pretrade_margin_rejected"],
        ),
        (
            "S07_MAINTENANCE_BREACH_LIQUIDATION",
            "Apply an adverse mark that breaches maintenance plus liquidation buffer, "
            "force-close both legs, charge liquidation fees, and kill new openings.",
            ["final_state_liquidated", "liquidation_fee_ledgered", "kill_switch_on"],
        ),
        (
            "S08_ADL_REDUCTION_KILL_AND_FLATTEN",
            "Apply an external ADL reduction to the short leg, detect the resulting "
            "delta breach, enable the kill switch, and flatten the residual pair.",
            ["adl_ledgered", "kill_switch_on", "zero_residual_delta"],
        ),
        (
            "S09_POSITION_RECONCILIATION_DRIFT",
            "Compare an external snapshot with a different spot or perpetual "
            "quantity, fail reconciliation, and enable the kill switch.",
            ["position_discrepancy_recorded", "reconciliation_failed"],
        ),
        (
            "S10_FEE_RECONCILIATION_DRIFT",
            "Compare an external cumulative-fee value with the internal ledger, fail "
            "reconciliation, and preserve the exact discrepancy.",
            ["fee_discrepancy_recorded", "reconciliation_failed"],
        ),
        (
            "S11_KILL_SWITCH_REJECTS_OPEN_ALLOWS_REDUCE_ONLY",
            "Enable the kill switch, reject a new opening request, but permit the "
            "reduce-only operation required to flatten existing risk.",
            ["new_open_rejected", "reduce_only_allowed"],
        ),
        (
            "S12_ASYMMETRIC_PARTIAL_FILLS_REACH_HEDGE",
            "Apply asynchronous partial fills on both legs and enter HEDGED only "
            "after the net base delta falls inside the frozen tolerance.",
            ["not_hedged_while_outside_tolerance", "hedged_inside_tolerance"],
        ),
        (
            "S13_NEGATIVE_FUNDING_SHORT_PAYS",
            "Settle a negative funding rate against the short perpetual and prove the "
            "cash flow is a debit with the frozen signed formula.",
            ["funding_negative", "signed_formula_reconciles"],
        ),
        (
            "S14_PARTIAL_CLOSE_COMPLETES_WITHOUT_RESIDUAL",
            "Close both legs through multiple partial fills and prove final cash, "
            "fees, realized P/L, quantities, and reconciliation contain no residue.",
            ["final_state_flat", "partial_close_reconciles", "zero_residual_delta"],
        ),
    ]
    return [
        V2DerivativesSyntheticScenario(
            scenario_id=scenario_id,
            purpose=purpose,
            required_assertions=assertions,
        )
        for scenario_id, purpose, assertions in values
    ]


def authoritative_protocol(
    *,
    frozen_at: datetime,
    acquisition: V2DerivativesAcquisitionProtocol,
    pilot: V2PilotAcquisitionResult,
) -> V2DerivativesFoundationProtocol:
    return build_v2_derivatives_foundation_protocol(
        frozen_at=frozen_at,
        capability_audit_evidence_hash=(
            acquisition.capability_audit_evidence_hash
        ),
        source_census_result_evidence_hash=(
            acquisition.source_census_result_evidence_hash
        ),
        acquisition_protocol_evidence_hash=acquisition.protocol_evidence_hash,
        pilot_result_evidence_hash=pilot.result_evidence_hash,
        contamination_ledger_evidence_hash=(
            acquisition.contamination_ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        accounting=V2DerivativesAccountingProtocol(),
        paired_execution=V2PairedExecutionProtocol(
            lifecycle=[
                "FLAT",
                "OPENING",
                "HEDGED",
                "CLOSING",
                "ROLLBACK",
                "LIQUIDATED",
                "KILLED",
            ],
            target_base_quantity="1",
            hedge_tolerance_base_quantity="0.001",
        ),
        risk=V2DerivativesRiskProtocol(
            synthetic_initial_cash="10000",
            synthetic_reference_price="100",
            taker_fee_rate="0.0005",
            spot_collateral_haircut="0.95",
            initial_margin_rate="0.10",
            maintenance_margin_rate="0.05",
            liquidation_fee_rate="0.005",
            minimum_initial_margin_buffer_ratio="1.25",
        ),
        reconciliation=V2DerivativesReconciliationProtocol(
            required_fields=[
                "cash",
                "cumulative_fees",
                "cumulative_funding",
                "perp_average_entry",
                "perp_quantity",
                "perp_realized_pl",
                "spot_quantity",
            ]
        ),
        scenarios=scenarios(),
        limitations=[
            (
                "Synthetic arithmetic cannot establish exchange-specific margin, "
                "liquidation, ADL, fee, order, or collateral behavior."
            ),
            (
                "The protocol uses one fixed linear USD-M accounting model and does "
                "not cover inverse contracts, options, portfolio margin, or borrowing."
            ),
            (
                "No network, real market data, strategy return, signal, or candidate "
                "is permitted in this foundation campaign."
            ),
            (
                "Passing scenarios prove deterministic internal invariants only; "
                "exchange sandbox qualification and statement reconciliation remain."
            ),
            (
                "A pass permits only a separate no-return discovery charter and "
                "creates no backtest, paper, sandbox, micro-live, or live eligibility."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if V2DerivativesFoundationProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("V2 derivatives foundation protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2DerivativesFoundationProtocol:
    if args.output.exists():
        raise ValueError("Frozen V2 foundation protocol exists; use --check")
    acquisition, pilot = load_inputs(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        acquisition=acquisition,
        pilot=pilot,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"scenarios={len(protocol.scenarios)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2DerivativesFoundationProtocol:
    acquisition, pilot = load_inputs(args)
    protocol = V2DerivativesFoundationProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        acquisition=acquisition,
        pilot=pilot,
    )
    if protocol != expected:
        raise ValueError("V2 foundation protocol is not reproducible")
    if not audit_v2_derivatives_foundation_protocol(protocol):
        raise ValueError("V2 foundation protocol hash audit failed")
    print(
        "PASS "
        f"v2_foundation_protocol={protocol.protocol_evidence_hash} "
        f"scenarios={len(protocol.scenarios)} synthetic_only={protocol.synthetic_only}",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the synthetic V2 derivatives-foundation protocol."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--acquisition-protocol",
        type=Path,
        default=DEFAULT_ACQUISITION_PROTOCOL,
    )
    parser.add_argument(
        "--pilot-result",
        type=Path,
        default=DEFAULT_PILOT_RESULT,
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
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
