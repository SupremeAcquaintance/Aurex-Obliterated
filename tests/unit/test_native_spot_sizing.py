from decimal import Decimal

import pytest

from aurex.config.settings import Settings
from aurex.risk_engine.native_spot import size_native_spot


def size(**changes):
    inputs = {
        "entry": Decimal("100"),
        "stop": Decimal("95"),
        "target": Decimal("112"),
        "available_quote": Decimal("100"),
        "risk_budget": Decimal("0.5"),
        "minimum_reward_risk": Decimal("2"),
        "settings": Settings(
            _env_file=None,
            paper_commission_bps=Decimal("10"),
            paper_half_spread_bps=Decimal("2.5"),
            paper_market_impact_bps=Decimal("2.5"),
        ),
    }
    inputs.update(changes)
    return size_native_spot(**inputs)


@pytest.mark.parametrize("entry,stop,target", [("100", "95", "112"), ("64000", "63999", "66000")])
@pytest.mark.parametrize("budget", ["0.5", "0.01", "0.0001"])
@pytest.mark.parametrize("cash", ["100", "0.01"])
def test_sizing_obeys_both_costed_stop_and_quote_bounds(entry, stop, target, budget, cash):
    entry, stop, target = map(Decimal, (entry, stop, target))
    result = size(
        entry=entry,
        stop=stop,
        target=target,
        risk_budget=Decimal(budget),
        available_quote=Decimal(cash),
    )
    q = result.quantity
    quantum = Decimal("0.00000001")

    # Independent arithmetic uses the execution engine's per-leg rounding contract.
    def fee(price):
        return (price * q * Decimal("0.001")).quantize(quantum)

    def slip(price):
        return (price * q * Decimal("0.0005")).quantize(quantum)

    actual_loss = ((entry - stop) * q + fee(entry) + slip(entry) + fee(stop) + slip(stop)).quantize(
        quantum
    )
    assert actual_loss <= result.modeled_stop_loss <= Decimal(budget)
    assert entry * q + fee(entry) + slip(entry) <= Decimal(cash)
    assert result.net_reward_risk >= 2
    assert q.as_tuple().exponent == -12
    assert result.snapshot["gap_loss_guaranteed"] is False
    assert result.snapshot["venue_filters_verified"] is False


def test_tight_stop_cannot_create_leveraged_position():
    result = size(entry=Decimal("64000"), stop=Decimal("63999"), target=Decimal("66000"))
    assert result.quantity * Decimal("64000") < 100
    assert result.modeled_stop_loss < Decimal("0.5")


def test_gross_two_to_one_does_not_pass_net_two_to_one():
    with pytest.raises(ValueError, match="net reward:risk"):
        size(target=Decimal("110"))


@pytest.mark.parametrize("key", ["entry", "stop", "target", "available_quote", "risk_budget"])
@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_nonpositive_or_nonfinite_values_fail_closed(key, value):
    with pytest.raises(ValueError):
        size(**{key: Decimal(value)})


@pytest.mark.parametrize(
    "key", ["paper_commission_bps", "paper_half_spread_bps", "paper_market_impact_bps"]
)
def test_native_costs_cannot_be_reduced_below_conservative_floor(key):
    settings = Settings(_env_file=None).model_copy(update={key: Decimal("0")})
    with pytest.raises(ValueError, match="cost floors"):
        size(settings=settings)


def test_dust_risk_budget_is_not_rounded_up_into_a_trade():
    with pytest.raises(ValueError, match="precision"):
        size(risk_budget=Decimal("0.00000001"))


@pytest.mark.parametrize("price", ["100.000000001", "1000000000000"])
def test_prices_cannot_change_when_persisted_to_ledger(price):
    with pytest.raises(ValueError, match="ledger's 8-decimal"):
        size(entry=Decimal(price))
