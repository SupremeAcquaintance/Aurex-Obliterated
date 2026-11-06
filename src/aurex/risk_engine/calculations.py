from decimal import Decimal

from aurex.domain.enums import Direction


def calculate_reward_risk(
    direction: Direction,
    entry_price: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
) -> Decimal:
    if direction == Direction.LONG:
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
    else:
        risk = stop_loss - entry_price
        reward = entry_price - take_profit

    if risk <= 0 or reward <= 0:
        raise ValueError("Invalid price geometry for direction")

    return reward / risk


def calculate_position_size(
    account_equity: Decimal,
    risk_per_trade: Decimal,
    entry_price: Decimal,
    stop_loss: Decimal,
) -> tuple[Decimal, Decimal]:
    risk_per_unit = abs(entry_price - stop_loss)
    if account_equity <= 0:
        raise ValueError("Account equity must be positive")
    if risk_per_trade <= 0:
        raise ValueError("Risk per trade must be positive")
    if risk_per_unit <= 0:
        raise ValueError("Entry price and stop loss cannot be equal")

    risk_amount = account_equity * risk_per_trade
    return risk_amount, risk_amount / risk_per_unit


def calculate_stop_risk_amount(
    entry_price: Decimal,
    stop_loss: Decimal,
    quantity: Decimal,
) -> Decimal:
    return abs(entry_price - stop_loss) * quantity
