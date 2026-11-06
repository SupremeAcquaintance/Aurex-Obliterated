from decimal import Decimal

import pytest

from aurex.domain.enums import PredictionMarketSide
from aurex.prediction_market.calculations import (
    calculate_average_fill_price,
    calculate_binary_entry_cost,
    calculate_binary_gross_payout,
    calculate_binary_notional,
    calculate_binary_settlement_pl,
    estimate_binary_contract_fee,
)


def test_binary_contract_fee_and_entry_cost_are_fee_net() -> None:
    fee = estimate_binary_contract_fee(Decimal("10"), Decimal("0.60"))

    assert fee == Decimal("0.16800000")
    assert calculate_binary_notional(Decimal("10"), Decimal("0.60")) == Decimal("6.00000000")
    assert calculate_binary_entry_cost(Decimal("10"), Decimal("0.60"), fee) == Decimal("6.16800000")


def test_yes_contract_settlement_profit_is_after_fees() -> None:
    result = calculate_binary_settlement_pl(
        PredictionMarketSide.YES,
        Decimal("10"),
        Decimal("0.60"),
        Decimal("1"),
        Decimal("0.16800000"),
    )

    assert calculate_binary_gross_payout(
        PredictionMarketSide.YES,
        Decimal("10"),
        Decimal("1"),
    ) == Decimal("10.00000000")
    assert result == Decimal("3.83200000")


def test_no_contract_settlement_uses_inverse_outcome() -> None:
    result = calculate_binary_settlement_pl(
        PredictionMarketSide.NO,
        Decimal("4"),
        Decimal("0.25"),
        Decimal("0"),
        Decimal("0.05000000"),
    )

    assert result == Decimal("2.95000000")


def test_average_fill_price_is_quantity_weighted() -> None:
    result = calculate_average_fill_price(
        Decimal("4"),
        Decimal("0.50"),
        Decimal("6"),
        Decimal("0.60"),
    )

    assert result == Decimal("0.56000000")


def test_prediction_market_calculations_reject_impossible_prices() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        estimate_binary_contract_fee(Decimal("10"), Decimal("1.20"))

