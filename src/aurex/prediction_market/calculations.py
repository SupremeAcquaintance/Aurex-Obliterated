from decimal import Decimal

from aurex.domain.enums import PredictionMarketSide

MONEY_QUANTUM = Decimal("0.00000001")
DEFAULT_BINARY_FEE_RATE = Decimal("0.07")


def validate_probability_price(price: Decimal, *, field_name: str = "price") -> Decimal:
    if price < 0 or price > 1:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return price


def validate_positive_quantity(quantity: Decimal) -> Decimal:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    return quantity


def calculate_binary_notional(quantity: Decimal, price: Decimal) -> Decimal:
    validate_positive_quantity(quantity)
    validate_probability_price(price)
    return (quantity * price).quantize(MONEY_QUANTUM)


def estimate_binary_contract_fee(
    quantity: Decimal,
    price: Decimal,
    fee_rate: Decimal = DEFAULT_BINARY_FEE_RATE,
) -> Decimal:
    """Estimate paper-trading fees for binary contracts.

    This intentionally stays a configurable paper model. A live adapter must replace this
    with venue-confirmed fees from broker statements and fills before real capital is used.
    """

    validate_positive_quantity(quantity)
    validate_probability_price(price)
    if fee_rate < 0:
        raise ValueError("Fee rate cannot be negative")
    fee = quantity * fee_rate * price * (Decimal("1") - price)
    return fee.quantize(MONEY_QUANTUM)


def calculate_binary_entry_cost(
    quantity: Decimal,
    price: Decimal,
    fees: Decimal = Decimal("0"),
) -> Decimal:
    if fees < 0:
        raise ValueError("Fees cannot be negative")
    return (calculate_binary_notional(quantity, price) + fees).quantize(MONEY_QUANTUM)


def calculate_binary_gross_payout(
    side: PredictionMarketSide,
    quantity: Decimal,
    settlement_value: Decimal,
) -> Decimal:
    validate_positive_quantity(quantity)
    validate_probability_price(settlement_value, field_name="settlement value")
    payout_per_contract = (
        settlement_value
        if side == PredictionMarketSide.YES
        else Decimal("1") - settlement_value
    )
    return (quantity * payout_per_contract).quantize(MONEY_QUANTUM)


def calculate_binary_settlement_pl(
    side: PredictionMarketSide,
    quantity: Decimal,
    entry_price: Decimal,
    settlement_value: Decimal,
    fees: Decimal = Decimal("0"),
) -> Decimal:
    if fees < 0:
        raise ValueError("Fees cannot be negative")
    validate_probability_price(entry_price, field_name="entry price")
    gross_payout = calculate_binary_gross_payout(side, quantity, settlement_value)
    entry_cost = calculate_binary_notional(quantity, entry_price)
    return (gross_payout - entry_cost - fees).quantize(MONEY_QUANTUM)


def calculate_average_fill_price(
    existing_quantity: Decimal,
    existing_average_price: Decimal | None,
    fill_quantity: Decimal,
    fill_price: Decimal,
) -> Decimal:
    if existing_quantity < 0:
        raise ValueError("Existing quantity cannot be negative")
    validate_positive_quantity(fill_quantity)
    validate_probability_price(fill_price, field_name="fill price")
    if existing_quantity == 0:
        return fill_price
    if existing_average_price is None:
        raise ValueError("Existing average price is required when existing quantity is nonzero")
    validate_probability_price(existing_average_price, field_name="existing average price")
    total_quantity = existing_quantity + fill_quantity
    average = (
        (existing_quantity * existing_average_price) + (fill_quantity * fill_price)
    ) / total_quantity
    return average.quantize(MONEY_QUANTUM)
