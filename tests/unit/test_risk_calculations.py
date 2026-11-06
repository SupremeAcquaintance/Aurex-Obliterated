from decimal import Decimal

import pytest

from aurex.domain.enums import Direction
from aurex.risk_engine.calculations import calculate_position_size, calculate_reward_risk


def test_calculate_reward_risk_for_long_trade() -> None:
    result = calculate_reward_risk(
        Direction.LONG,
        Decimal("100"),
        Decimal("95"),
        Decimal("110"),
    )

    assert result == Decimal("2")


def test_calculate_reward_risk_for_short_trade() -> None:
    result = calculate_reward_risk(
        Direction.SHORT,
        Decimal("100"),
        Decimal("105"),
        Decimal("90"),
    )

    assert result == Decimal("2")


def test_calculate_reward_risk_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="Invalid price geometry"):
        calculate_reward_risk(
            Direction.LONG,
            Decimal("100"),
            Decimal("101"),
            Decimal("110"),
        )


def test_calculate_position_size() -> None:
    risk_amount, position_size = calculate_position_size(
        Decimal("1000"),
        Decimal("0.005"),
        Decimal("100"),
        Decimal("95"),
    )

    assert risk_amount == Decimal("5.000")
    assert position_size == Decimal("1.000")

