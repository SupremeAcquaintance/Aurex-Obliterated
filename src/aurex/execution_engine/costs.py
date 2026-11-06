from decimal import Decimal

BPS_DENOMINATOR = Decimal("10000")
MONEY_QUANTUM = Decimal("0.00000001")


def quantized_money(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANTUM)


def modeled_execution_costs(
    *,
    price: Decimal,
    quantity: Decimal,
    commission_bps: Decimal,
    half_spread_bps: Decimal,
    market_impact_bps: Decimal,
) -> tuple[Decimal, Decimal]:
    notional = abs(price * quantity)
    fees = quantized_money(notional * commission_bps / BPS_DENOMINATOR)
    slippage = quantized_money(notional * (half_spread_bps + market_impact_bps) / BPS_DENOMINATOR)
    return fees, slippage
