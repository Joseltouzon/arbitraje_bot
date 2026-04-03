from __future__ import annotations


def calculate_cycle_profit(
    initial_amount: float,
    rates: list[float],
    fee_rate: float = 0.001,
    slippage_pct: float = 0.001,
) -> dict[str, float]:
    """
    Calculate exact profit for a triangular cycle with fees and slippage.

    For cycle USDT → BTC → ETH → USDT:
    1. Buy BTC:  get_btc = usdt / (btc_rate * (1 + fee))
    2. Buy ETH:  get_eth = get_btc * eth_btc_rate * (1 - fee)
    3. Sell ETH: final_usdt = get_eth * eth_usdt_rate * (1 - fee)

    Args:
        initial_amount: starting amount in USDT
        rates: list of exchange rates for each leg
        fee_rate: trading fee per leg (default 0.1%)
        slippage_pct: estimated slippage (default 0.1%)

    Returns:
        dict with profit breakdown
    """
    current = initial_amount
    total_fees_paid = 0.0
    total_slippage_cost = 0.0

    for rate in rates:
        # Apply fee first: reduce amount after trade
        before_fee = current * rate
        fee = before_fee * fee_rate
        current = before_fee - fee

        # Apply slippage: reduce final amount
        slippage_cost = current * slippage_pct
        current = current - slippage_cost

        total_fees_paid += fee
        total_slippage_cost += slippage_cost

    final_amount = current
    gross_profit = final_amount - initial_amount
    net_profit = gross_profit

    return {
        "initial_amount": round(initial_amount, 8),
        "final_amount": round(final_amount, 8),
        "gross_profit": round(gross_profit, 8),
        "net_profit": round(net_profit, 8),
        "net_profit_pct": round(net_profit / initial_amount * 100, 4) if initial_amount > 0 else 0,
        "total_fees": round(total_fees_paid, 8),
        "total_slippage": round(total_slippage_cost, 8),
        "trade_count": len(rates),
    }


def estimate_slippage(
    order_quantity: float,
    available_quantity: float,
) -> float:
    """
    Estimate slippage based on order size vs available liquidity.

    Larger orders relative to available liquidity = more slippage.
    """
    if available_quantity <= 0:
        return 0.01  # 1% default if no liquidity info

    ratio = order_quantity / available_quantity
    if ratio < 0.01:
        return 0.0001  # 0.01% for tiny orders
    elif ratio < 0.1:
        return 0.0005  # 0.05% for medium orders
    elif ratio < 0.5:
        return 0.002  # 0.2% for large orders
    else:
        return 0.01  # 1% for very large orders
