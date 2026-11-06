from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from aurex.backtest_engine.derivatives_foundation import (
    DerivativesFoundationError,
    DuplicateEventError,
    FoundationSnapshot,
    PairState,
    SyntheticDerivativesEngine,
    SyntheticOrderStatus,
)
from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2DerivativesFoundationProtocol,
)

PROTOCOL_PATH = Path(
    "data/evidence/v2_derivatives_foundation_protocol_v1.json"
)
T0 = datetime(2026, 7, 28, 4, tzinfo=UTC)
FEE = Decimal("0.0005")


@pytest.fixture(scope="module")
def protocol() -> V2DerivativesFoundationProtocol:
    return V2DerivativesFoundationProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def fully_open(
    engine: SyntheticDerivativesEngine,
    *,
    quantity: Decimal = Decimal("1"),
) -> None:
    engine.open_pair(
        spot_order_id="spot-open",
        perp_order_id="perp-open",
        quantity=quantity,
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0,
    )
    engine.apply_fill(
        order_id="spot-open",
        fill_id="spot-open-fill",
        quantity=quantity,
        price=Decimal("100"),
        fee_rate=FEE,
        occurred_at=T0 + timedelta(seconds=1),
    )
    engine.apply_fill(
        order_id="perp-open",
        fill_id="perp-open-fill",
        quantity=quantity,
        price=Decimal("100"),
        fee_rate=FEE,
        occurred_at=T0 + timedelta(seconds=2),
    )


def test_full_pair_funding_close_and_reconciliation(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    fully_open(engine)

    assert engine.state == PairState.HEDGED
    assert engine.net_base_delta == 0
    assert engine.cash == Decimal("9899.9000")

    funding = engine.settle_funding(
        funding_event_id="funding-1",
        funding_rate=Decimal("0.0001"),
        mark_price=Decimal("100"),
        occurred_at=T0 + timedelta(hours=8),
    )
    assert funding == Decimal("0.0100")

    engine.begin_close(
        spot_order_id="spot-close",
        perp_order_id="perp-close",
        occurred_at=T0 + timedelta(hours=9),
    )
    engine.apply_fill(
        order_id="spot-close",
        fill_id="spot-close-fill",
        quantity=Decimal("1"),
        price=Decimal("102"),
        fee_rate=FEE,
        occurred_at=T0 + timedelta(hours=9, seconds=1),
    )
    engine.apply_fill(
        order_id="perp-close",
        fill_id="perp-close-fill",
        quantity=Decimal("1"),
        price=Decimal("101"),
        fee_rate=FEE,
        occurred_at=T0 + timedelta(hours=9, seconds=2),
    )

    assert engine.state == PairState.FLAT
    assert engine.cash == Decimal("10000.8085")
    assert engine.perp_realized_pl == Decimal("-1")
    assert engine.cumulative_fees == Decimal("0.2015")
    assert engine.cumulative_funding == Decimal("0.0100")
    reconciliation = engine.reconcile(
        external=engine.snapshot(),
        reconciliation_id="matched",
        occurred_at=T0 + timedelta(hours=10),
    )
    assert reconciliation.status == "MATCHED"
    assert reconciliation.discrepancies == {}


def test_partial_first_leg_rejection_rolls_back_with_fees(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    engine.open_pair(
        spot_order_id="spot",
        perp_order_id="perp",
        quantity=Decimal("1"),
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0,
    )
    engine.apply_fill(
        order_id="spot",
        fill_id="spot-partial",
        quantity=Decimal("0.4"),
        price=Decimal("100"),
        fee_rate=FEE,
        occurred_at=T0 + timedelta(seconds=1),
    )
    engine.reject_order(
        order_id="perp",
        reason="VENUE_REJECTED",
        occurred_at=T0 + timedelta(seconds=2),
    )
    engine.begin_rollback(
        spot_order_id="spot-rollback",
        perp_order_id=None,
        occurred_at=T0 + timedelta(seconds=3),
        reason="SECOND_LEG_REJECTED",
    )
    engine.apply_fill(
        order_id="spot-rollback",
        fill_id="spot-rollback-fill",
        quantity=Decimal("0.4"),
        price=Decimal("99"),
        fee_rate=FEE,
        occurred_at=T0 + timedelta(seconds=4),
    )

    assert engine.state == PairState.FLAT
    assert engine.spot_quantity == 0
    assert engine.perp_quantity == 0
    assert engine.cumulative_fees == Decimal("0.03980")
    assert engine.cash == Decimal("9999.56020")
    assert engine.orders["spot"].status == SyntheticOrderStatus.CANCELLED


def test_duplicate_fill_and_funding_are_idempotent(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    fully_open(engine)
    snapshot_before = engine.snapshot()
    ledger_before = engine.ledger_head_hash

    with pytest.raises(DuplicateEventError, match="Duplicate fill"):
        engine.apply_fill(
            order_id="spot-open",
            fill_id="spot-open-fill",
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee_rate=FEE,
            occurred_at=T0 + timedelta(seconds=3),
        )

    assert engine.snapshot() == snapshot_before
    assert engine.ledger_head_hash == ledger_before

    engine.settle_funding(
        funding_event_id="funding",
        funding_rate=Decimal("0.0001"),
        mark_price=Decimal("100"),
        occurred_at=T0 + timedelta(hours=8),
    )
    snapshot_after_funding = engine.snapshot()
    ledger_after_funding = engine.ledger_head_hash
    with pytest.raises(DuplicateEventError, match="Duplicate funding"):
        engine.settle_funding(
            funding_event_id="funding",
            funding_rate=Decimal("0.0001"),
            mark_price=Decimal("100"),
            occurred_at=T0 + timedelta(hours=8),
        )
    assert engine.snapshot() == snapshot_after_funding
    assert engine.ledger_head_hash == ledger_after_funding


def test_open_timeout_cancels_and_creates_reduce_only_rollback(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    engine.open_pair(
        spot_order_id="spot",
        perp_order_id="perp",
        quantity=Decimal("1"),
        spot_price=Decimal("100"),
        perp_price=Decimal("100"),
        occurred_at=T0,
    )
    engine.apply_fill(
        order_id="spot",
        fill_id="spot-fill",
        quantity=Decimal("0.25"),
        price=Decimal("100"),
        fee_rate=FEE,
        occurred_at=T0 + timedelta(seconds=1),
    )

    rollback = engine.expire_opening(
        now=T0 + timedelta(seconds=6),
        spot_rollback_order_id="spot-rollback",
        perp_rollback_order_id=None,
    )

    assert engine.state == PairState.ROLLBACK
    assert len(rollback) == 1
    assert rollback[0].reduce_only is True
    assert engine.orders["spot"].status == SyntheticOrderStatus.CANCELLED
    assert engine.orders["perp"].status == SyntheticOrderStatus.CANCELLED


def test_pretrade_margin_rejects_before_orders(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol, cash=Decimal("5"))

    with pytest.raises(DerivativesFoundationError, match="margin"):
        engine.open_pair(
            spot_order_id="spot",
            perp_order_id="perp",
            quantity=Decimal("1"),
            spot_price=Decimal("100"),
            perp_price=Decimal("100"),
            occurred_at=T0,
        )

    assert engine.state == PairState.FLAT
    assert engine.orders == {}
    assert engine.ledger[-1].event_type == "PRETRADE_MARGIN_REJECTED"


def test_maintenance_breach_liquidates_and_kills(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    fully_open(engine)

    assert engine.should_liquidate(
        spot_mark_price=Decimal("100"),
        perp_mark_price=Decimal("11000"),
    )
    engine.apply_liquidation(
        event_id="liquidation-1",
        spot_price=Decimal("100"),
        perp_price=Decimal("11000"),
        occurred_at=T0 + timedelta(hours=1),
    )

    assert engine.state == PairState.LIQUIDATED
    assert engine.kill_switch_enabled is True
    assert engine.spot_quantity == 0
    assert engine.perp_quantity == 0
    assert engine.cumulative_liquidation_fees == Decimal("55.000")


def test_adl_reduction_enables_kill_and_reduce_only_flatten(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    fully_open(engine)

    realized = engine.apply_adl_reduction(
        event_id="adl-1",
        quantity=Decimal("0.5"),
        price=Decimal("95"),
        occurred_at=T0 + timedelta(hours=1),
    )

    assert realized == Decimal("2.5")
    assert engine.perp_quantity == Decimal("-0.5")
    assert engine.net_base_delta == Decimal("0.5")
    assert engine.kill_switch_enabled is True
    assert engine.state == PairState.KILLED

    orders = engine.begin_close(
        spot_order_id="spot-flatten",
        perp_order_id="perp-flatten",
        occurred_at=T0 + timedelta(hours=1, seconds=1),
    )
    assert all(order.reduce_only for order in orders)


def test_reconciliation_drift_records_field_and_kills(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    fully_open(engine)
    internal = engine.snapshot()
    external = FoundationSnapshot(
        cash=internal.cash,
        spot_quantity=Decimal("0.9"),
        perp_quantity=internal.perp_quantity,
        perp_average_entry=internal.perp_average_entry,
        perp_realized_pl=internal.perp_realized_pl,
        cumulative_fees=internal.cumulative_fees + Decimal("1"),
        cumulative_funding=internal.cumulative_funding,
    )

    result = engine.reconcile(
        external=external,
        reconciliation_id="drift",
        occurred_at=T0 + timedelta(hours=1),
    )

    assert result.status == "FAIL"
    assert set(result.discrepancies) == {"spot_quantity", "cumulative_fees"}
    assert engine.kill_switch_enabled is True
    assert engine.state == PairState.KILLED


def test_negative_funding_debits_short_and_hash_chain_is_contiguous(
    protocol: V2DerivativesFoundationProtocol,
) -> None:
    engine = SyntheticDerivativesEngine(protocol)
    fully_open(engine)
    before = engine.cash

    cashflow = engine.settle_funding(
        funding_event_id="negative",
        funding_rate=Decimal("-0.0002"),
        mark_price=Decimal("100"),
        occurred_at=T0 + timedelta(hours=8),
    )

    assert cashflow == Decimal("-0.0200")
    assert engine.cash == before - Decimal("0.0200")
    previous = "0" * 64
    for event in engine.ledger:
        assert event.previous_hash == previous
        previous = event.event_hash
