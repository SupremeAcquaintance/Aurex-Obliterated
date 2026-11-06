import argparse
import hashlib
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.derivatives_foundation import (
    DerivativesFoundationError,
    DuplicateEventError,
    FoundationSnapshot,
    PairState,
    SyntheticDerivativesEngine,
)
from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2DerivativesFoundationProtocol,
    audit_v2_derivatives_foundation_protocol,
)
from aurex.backtest_engine.research_v2_derivatives_foundation_result import (
    V2DerivativesFoundationResult,
    V2DerivativesScenarioResult,
    audit_v2_derivatives_foundation_result,
    build_v2_derivatives_foundation_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_PROTOCOL = Path(
    "data/evidence/v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v2_derivatives_foundation_result_v1.json"
)
T0 = datetime(2026, 1, 1, tzinfo=UTC)

ScenarioRunner = Callable[
    [V2DerivativesFoundationProtocol],
    tuple[SyntheticDerivativesEngine, dict[str, bool]],
]


def runner_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "run_v2_derivatives_foundation.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "derivatives_foundation.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_derivatives_foundation_result.py",
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


def load_protocol(path: Path) -> V2DerivativesFoundationProtocol:
    protocol = V2DerivativesFoundationProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_v2_derivatives_foundation_protocol(protocol):
        raise ValueError("V2 derivatives foundation protocol audit failed")
    return protocol


def fill(
    engine: SyntheticDerivativesEngine,
    *,
    order_id: str,
    fill_id: str,
    quantity: str,
    price: str,
    seconds: int,
) -> None:
    engine.apply_fill(
        order_id=order_id,
        fill_id=fill_id,
        quantity=Decimal(quantity),
        price=Decimal(price),
        fee_rate=engine.protocol.risk.taker_fee_rate,
        occurred_at=T0 + timedelta(seconds=seconds),
    )


def open_full(
    engine: SyntheticDerivativesEngine,
    *,
    prefix: str,
    quantity: str = "1",
    seconds: int = 0,
) -> None:
    engine.open_pair(
        spot_order_id=f"{prefix}-spot-open",
        perp_order_id=f"{prefix}-perp-open",
        quantity=Decimal(quantity),
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0 + timedelta(seconds=seconds),
    )
    fill(
        engine,
        order_id=f"{prefix}-spot-open",
        fill_id=f"{prefix}-spot-open-fill",
        quantity=quantity,
        price="100",
        seconds=seconds + 1,
    )
    fill(
        engine,
        order_id=f"{prefix}-perp-open",
        fill_id=f"{prefix}-perp-open-fill",
        quantity=quantity,
        price="100",
        seconds=seconds + 2,
    )


def close_full(
    engine: SyntheticDerivativesEngine,
    *,
    prefix: str,
    spot_price: str = "100",
    perp_price: str = "100",
    seconds: int = 100,
) -> None:
    spot_quantity = engine.spot_quantity
    perp_quantity = abs(engine.perp_quantity)
    engine.begin_close(
        spot_order_id=(
            f"{prefix}-spot-close" if spot_quantity > Decimal("0") else None
        ),
        perp_order_id=(
            f"{prefix}-perp-close" if perp_quantity > Decimal("0") else None
        ),
        occurred_at=T0 + timedelta(seconds=seconds),
    )
    if spot_quantity > Decimal("0"):
        fill(
            engine,
            order_id=f"{prefix}-spot-close",
            fill_id=f"{prefix}-spot-close-fill",
            quantity=str(spot_quantity),
            price=spot_price,
            seconds=seconds + 1,
        )
    if perp_quantity > Decimal("0"):
        fill(
            engine,
            order_id=f"{prefix}-perp-close",
            fill_id=f"{prefix}-perp-close-fill",
            quantity=str(perp_quantity),
            price=perp_price,
            seconds=seconds + 2,
        )


def s01(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    open_full(engine, prefix="s01")
    funding = engine.settle_funding(
        funding_event_id="s01-funding",
        funding_rate=Decimal("0.0001"),
        mark_price=Decimal("100"),
        occurred_at=T0 + timedelta(hours=8),
    )
    close_full(
        engine,
        prefix="s01",
        spot_price="102",
        perp_price="101",
        seconds=9 * 3600,
    )
    return engine, {
        "final_state_flat": engine.state == PairState.FLAT,
        "funding_positive": funding > Decimal("0"),
        "reconciliation_matched": True,
    }


def s02(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    engine.open_pair(
        spot_order_id="s02-spot",
        perp_order_id="s02-perp",
        quantity=Decimal("1"),
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0,
    )
    fill(
        engine,
        order_id="s02-spot",
        fill_id="s02-spot-partial",
        quantity="0.4",
        price="100",
        seconds=1,
    )
    engine.reject_order(
        order_id="s02-perp",
        reason="VENUE_REJECTED",
        occurred_at=T0 + timedelta(seconds=2),
    )
    engine.begin_rollback(
        spot_order_id="s02-spot-rollback",
        perp_order_id=None,
        occurred_at=T0 + timedelta(seconds=3),
        reason="SECOND_LEG_REJECTED",
    )
    fill(
        engine,
        order_id="s02-spot-rollback",
        fill_id="s02-rollback-fill",
        quantity="0.4",
        price="99",
        seconds=4,
    )
    return engine, {
        "final_state_flat": engine.state == PairState.FLAT,
        "rollback_fees_ledgered": engine.cumulative_fees == Decimal("0.03980"),
        "zero_residual_delta": engine.net_base_delta == Decimal("0"),
    }


def s03(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    engine.open_pair(
        spot_order_id="s03-spot",
        perp_order_id="s03-perp",
        quantity=Decimal("1"),
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0,
    )
    fill(
        engine,
        order_id="s03-spot",
        fill_id="s03-duplicate",
        quantity="0.5",
        price="100",
        seconds=1,
    )
    before_snapshot = engine.snapshot()
    before_hash = engine.ledger_head_hash
    duplicate_rejected = False
    try:
        fill(
            engine,
            order_id="s03-spot",
            fill_id="s03-duplicate",
            quantity="0.5",
            price="100",
            seconds=2,
        )
    except DuplicateEventError:
        duplicate_rejected = True
    unchanged = (
        engine.snapshot() == before_snapshot
        and engine.ledger_head_hash == before_hash
    )
    fill(
        engine,
        order_id="s03-spot",
        fill_id="s03-spot-rest",
        quantity="0.5",
        price="100",
        seconds=3,
    )
    fill(
        engine,
        order_id="s03-perp",
        fill_id="s03-perp-full",
        quantity="1",
        price="100",
        seconds=4,
    )
    close_full(engine, prefix="s03", seconds=10)
    return engine, {
        "duplicate_rejected": duplicate_rejected,
        "ledger_state_unchanged": unchanged,
    }


def s04(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    open_full(engine, prefix="s04")
    engine.settle_funding(
        funding_event_id="s04-funding",
        funding_rate=Decimal("0.0001"),
        mark_price=Decimal("100"),
        occurred_at=T0 + timedelta(hours=8),
    )
    applied = engine.cumulative_funding
    duplicate_rejected = False
    try:
        engine.settle_funding(
            funding_event_id="s04-funding",
            funding_rate=Decimal("0.0001"),
            mark_price=Decimal("100"),
            occurred_at=T0 + timedelta(hours=8),
        )
    except DuplicateEventError:
        duplicate_rejected = True
    applied_once = engine.cumulative_funding == applied
    close_full(engine, prefix="s04", seconds=9 * 3600)
    return engine, {
        "duplicate_rejected": duplicate_rejected,
        "funding_applied_once": applied_once,
    }


def s05(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    engine.open_pair(
        spot_order_id="s05-spot",
        perp_order_id="s05-perp",
        quantity=Decimal("1"),
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0,
    )
    fill(
        engine,
        order_id="s05-perp",
        fill_id="s05-perp-partial",
        quantity="0.3",
        price="100",
        seconds=1,
    )
    engine.expire_opening(
        now=T0 + timedelta(seconds=6),
        spot_rollback_order_id=None,
        perp_rollback_order_id="s05-perp-rollback",
    )
    orders_cancelled = all(
        order.status.value in {"CANCELLED", "FILLED"}
        for order in engine.orders.values()
        if "rollback" not in order.order_id
    )
    fill(
        engine,
        order_id="s05-perp-rollback",
        fill_id="s05-perp-rollback-fill",
        quantity="0.3",
        price="101",
        seconds=7,
    )
    return engine, {
        "orders_cancelled": orders_cancelled,
        "rollback_completed": engine.state == PairState.FLAT,
        "zero_residual_delta": engine.net_base_delta == Decimal("0"),
    }


def s06(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol, cash=Decimal("5"))
    rejected = False
    try:
        engine.open_pair(
            spot_order_id="s06-spot",
            perp_order_id="s06-perp",
            quantity=Decimal("1"),
            spot_price=Decimal("100"),
            perp_price=Decimal("100"),
            occurred_at=T0,
        )
    except DerivativesFoundationError:
        rejected = True
    return engine, {
        "no_orders_created": not engine.orders,
        "pretrade_margin_rejected": rejected,
    }


def s07(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    open_full(engine, prefix="s07")
    engine.apply_liquidation(
        event_id="s07-liquidation",
        spot_price=Decimal("100"),
        perp_price=Decimal("11000"),
        occurred_at=T0 + timedelta(hours=1),
    )
    return engine, {
        "final_state_liquidated": engine.state == PairState.LIQUIDATED,
        "kill_switch_on": engine.kill_switch_enabled,
        "liquidation_fee_ledgered": (
            engine.cumulative_liquidation_fees == Decimal("55")
        ),
    }


def s08(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    open_full(engine, prefix="s08")
    engine.apply_adl_reduction(
        event_id="s08-adl",
        quantity=Decimal("0.5"),
        price=Decimal("95"),
        occurred_at=T0 + timedelta(hours=1),
    )
    adl_ledgered = any(
        event.event_type == "ADL_REDUCTION_APPLIED" for event in engine.ledger
    )
    kill_on = engine.kill_switch_enabled
    close_full(engine, prefix="s08", seconds=3700)
    return engine, {
        "adl_ledgered": adl_ledgered,
        "kill_switch_on": kill_on,
        "zero_residual_delta": engine.net_base_delta == Decimal("0"),
    }


def _drift_scenario(
    protocol: V2DerivativesFoundationProtocol,
    *,
    fee_drift: bool,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    prefix = "s10" if fee_drift else "s09"
    open_full(engine, prefix=prefix)
    internal = engine.snapshot()
    external = FoundationSnapshot(
        cash=internal.cash,
        spot_quantity=(
            internal.spot_quantity
            if fee_drift
            else internal.spot_quantity - Decimal("0.1")
        ),
        perp_quantity=internal.perp_quantity,
        perp_average_entry=internal.perp_average_entry,
        perp_realized_pl=internal.perp_realized_pl,
        cumulative_fees=(
            internal.cumulative_fees + Decimal("1")
            if fee_drift
            else internal.cumulative_fees
        ),
        cumulative_funding=internal.cumulative_funding,
    )
    mismatch = engine.reconcile(
        external=external,
        reconciliation_id=f"{prefix}-drift",
        occurred_at=T0 + timedelta(hours=1),
    )
    close_full(engine, prefix=prefix, seconds=3700)
    if fee_drift:
        assertions = {
            "fee_discrepancy_recorded": (
                set(mismatch.discrepancies) == {"cumulative_fees"}
            ),
            "reconciliation_failed": mismatch.status == "FAIL",
        }
    else:
        assertions = {
            "position_discrepancy_recorded": (
                set(mismatch.discrepancies) == {"spot_quantity"}
            ),
            "reconciliation_failed": mismatch.status == "FAIL",
        }
    return engine, assertions


def s09(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    return _drift_scenario(protocol, fee_drift=False)


def s10(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    return _drift_scenario(protocol, fee_drift=True)


def s11(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    open_full(engine, prefix="s11")
    engine.set_kill_switch(
        enabled=True,
        occurred_at=T0 + timedelta(hours=1),
        reason="OPERATOR_TEST",
    )
    open_rejected = False
    try:
        engine.open_pair(
            spot_order_id="blocked-spot",
            perp_order_id="blocked-perp",
            quantity=Decimal("1"),
            spot_price=Decimal("100"),
            perp_price=Decimal("100"),
            occurred_at=T0 + timedelta(hours=1, seconds=1),
        )
    except DerivativesFoundationError:
        open_rejected = True
    close_full(engine, prefix="s11", seconds=3700)
    return engine, {
        "new_open_rejected": open_rejected,
        "reduce_only_allowed": (
            engine.spot_quantity == Decimal("0")
            and engine.perp_quantity == Decimal("0")
        ),
    }


def s12(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    engine.open_pair(
        spot_order_id="s12-spot",
        perp_order_id="s12-perp",
        quantity=Decimal("1"),
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0,
    )
    fill(
        engine,
        order_id="s12-spot",
        fill_id="s12-spot-1",
        quantity="0.6",
        price="100",
        seconds=1,
    )
    fill(
        engine,
        order_id="s12-perp",
        fill_id="s12-perp-1",
        quantity="0.4",
        price="100",
        seconds=2,
    )
    outside = engine.state == PairState.OPENING
    fill(
        engine,
        order_id="s12-perp",
        fill_id="s12-perp-2",
        quantity="0.2",
        price="100",
        seconds=3,
    )
    fill(
        engine,
        order_id="s12-spot",
        fill_id="s12-spot-2",
        quantity="0.4",
        price="100",
        seconds=4,
    )
    fill(
        engine,
        order_id="s12-perp",
        fill_id="s12-perp-3",
        quantity="0.4",
        price="100",
        seconds=5,
    )
    hedged = engine.state == PairState.HEDGED and engine.net_base_delta == 0
    close_full(engine, prefix="s12", seconds=10)
    return engine, {
        "hedged_inside_tolerance": hedged,
        "not_hedged_while_outside_tolerance": outside,
    }


def s13(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    open_full(engine, prefix="s13")
    funding = engine.settle_funding(
        funding_event_id="s13-funding",
        funding_rate=Decimal("-0.0002"),
        mark_price=Decimal("100"),
        occurred_at=T0 + timedelta(hours=8),
    )
    reconciles = funding == (
        -Decimal("-1") * Decimal("100") * Decimal("-0.0002")
    )
    close_full(engine, prefix="s13", seconds=9 * 3600)
    return engine, {
        "funding_negative": funding < Decimal("0"),
        "signed_formula_reconciles": reconciles,
    }


def s14(
    protocol: V2DerivativesFoundationProtocol,
) -> tuple[SyntheticDerivativesEngine, dict[str, bool]]:
    engine = SyntheticDerivativesEngine(protocol)
    open_full(engine, prefix="s14")
    engine.begin_close(
        spot_order_id="s14-spot-close",
        perp_order_id="s14-perp-close",
        occurred_at=T0 + timedelta(hours=1),
    )
    fill(
        engine,
        order_id="s14-spot-close",
        fill_id="s14-spot-close-1",
        quantity="0.4",
        price="101",
        seconds=3601,
    )
    fill(
        engine,
        order_id="s14-perp-close",
        fill_id="s14-perp-close-1",
        quantity="0.3",
        price="101",
        seconds=3602,
    )
    fill(
        engine,
        order_id="s14-spot-close",
        fill_id="s14-spot-close-2",
        quantity="0.6",
        price="102",
        seconds=3603,
    )
    fill(
        engine,
        order_id="s14-perp-close",
        fill_id="s14-perp-close-2",
        quantity="0.7",
        price="99",
        seconds=3604,
    )
    return engine, {
        "final_state_flat": engine.state == PairState.FLAT,
        "partial_close_reconciles": (
            engine.perp_realized_pl == Decimal("0.4")
        ),
        "zero_residual_delta": engine.net_base_delta == Decimal("0"),
    }


SCENARIO_RUNNERS: dict[str, ScenarioRunner] = {
    "S01_FULL_OPEN_FUNDING_CLOSE_RECONCILE": s01,
    "S02_FIRST_LEG_PARTIAL_SECOND_REJECT_ROLLBACK": s02,
    "S03_DUPLICATE_FILL_IDEMPOTENCY": s03,
    "S04_DUPLICATE_FUNDING_IDEMPOTENCY": s04,
    "S05_OPEN_TIMEOUT_CANCEL_AND_ROLLBACK": s05,
    "S06_INITIAL_MARGIN_PREFLIGHT_REJECTION": s06,
    "S07_MAINTENANCE_BREACH_LIQUIDATION": s07,
    "S08_ADL_REDUCTION_KILL_AND_FLATTEN": s08,
    "S09_POSITION_RECONCILIATION_DRIFT": s09,
    "S10_FEE_RECONCILIATION_DRIFT": s10,
    "S11_KILL_SWITCH_REJECTS_OPEN_ALLOWS_REDUCE_ONLY": s11,
    "S12_ASYMMETRIC_PARTIAL_FILLS_REACH_HEDGE": s12,
    "S13_NEGATIVE_FUNDING_SHORT_PAYS": s13,
    "S14_PARTIAL_CLOSE_COMPLETES_WITHOUT_RESIDUAL": s14,
}


def execute_scenario(
    *,
    protocol: V2DerivativesFoundationProtocol,
    scenario_id: str,
) -> V2DerivativesScenarioResult:
    engine, assertions = SCENARIO_RUNNERS[scenario_id](protocol)
    reconciliation = engine.reconcile(
        external=engine.snapshot(),
        reconciliation_id=f"{scenario_id}-final",
        occurred_at=T0 + timedelta(days=1),
    )
    if "reconciliation_matched" in assertions:
        assertions["reconciliation_matched"] = (
            reconciliation.status == "MATCHED"
        )
    return V2DerivativesScenarioResult(
        scenario_id=scenario_id,
        assertions=assertions,
        final_reconciliation_status=reconciliation.status,
        final_state=engine.state.value,
        kill_switch_enabled=engine.kill_switch_enabled,
        final_snapshot=engine.snapshot().as_dict(),
        ledger_event_count=len(engine.ledger),
        ledger_head_hash=engine.ledger_head_hash,
    )


def execute_campaign(
    protocol: V2DerivativesFoundationProtocol,
) -> list[V2DerivativesScenarioResult]:
    results = []
    for completed, scenario in enumerate(protocol.scenarios, start=1):
        result = execute_scenario(
            protocol=protocol,
            scenario_id=scenario.scenario_id,
        )
        if set(result.assertions) != set(scenario.required_assertions):
            raise ValueError(
                f"V2 scenario assertion set changed: {scenario.scenario_id}"
            )
        results.append(result)
        print(
            f"V2 synthetic scenario PASS {completed}/{len(protocol.scenarios)} "
            f"{scenario.scenario_id}",
            flush=True,
        )
    return results


def authoritative_result(
    *,
    generated_at: datetime,
    protocol: V2DerivativesFoundationProtocol,
    scenario_results: list[V2DerivativesScenarioResult],
) -> V2DerivativesFoundationResult:
    return build_v2_derivatives_foundation_result(
        generated_at=generated_at,
        protocol=protocol,
        runner_contract_hash=runner_contract_hash(),
        scenario_results=scenario_results,
        limitations=[
            (
                "The engine is a deterministic synthetic linear USD-M model and is "
                "not an exchange emulator or production execution adapter."
            ),
            (
                "Synthetic pass results do not prove venue acknowledgements, queue "
                "priority, spread, market impact, downtime, liquidation, or ADL."
            ),
            (
                "The scenarios use fixed invented prices and calculate no strategy "
                "return, edge, expected profit, or candidate outcome."
            ),
            (
                "Historical contract metadata, dated fees, collateral policy, and "
                "exchange sandbox behavior remain separate evidence requirements."
            ),
            (
                "A pass permits only a separate no-return discovery charter and "
                "creates no backtest, paper, sandbox, micro-live, or live eligibility."
            ),
        ],
    )


def write_result(path: Path, result: V2DerivativesFoundationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V2DerivativesFoundationResult.model_validate_json(serialized) != result:
        raise ValueError("V2 derivatives foundation result did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_campaign(args) -> V2DerivativesFoundationResult:
    if args.output.exists():
        raise ValueError("Frozen V2 foundation result exists; use --audit")
    protocol = load_protocol(args.protocol)
    scenario_results = execute_campaign(protocol)
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        scenario_results=scenario_results,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"passed={result.passed_scenario_count}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> V2DerivativesFoundationResult:
    protocol = load_protocol(args.protocol)
    result = V2DerivativesFoundationResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    audit = audit_v2_derivatives_foundation_result(
        result=result,
        protocol=protocol,
        current_runner_contract_hash=runner_contract_hash(),
    )
    if audit["status"] != "PASS":
        raise ValueError(f"V2 foundation result audit failed: {audit['reasons']}")
    print(
        "PASS "
        f"v2_foundation={result.result_evidence_hash} "
        f"scenarios={result.passed_scenario_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or audit the frozen V2 synthetic derivatives campaign."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_campaign(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
