from app.core.calculator import calculate_cycle_profit


def test_profitable_cycle():
    """
    Test a cycle with a clear price inconsistency.

    USDT -> BTC: ask 85000 (get 1/85000 BTC per USDT)
    BTC -> ETH: ask 0.0377 (get 1/0.0377 ETH per BTC = ~26.5 ETH)
    ETH -> USDT: bid 3240 (sell ETH for USDT)

    Product of rates: (1/85000) * (1/0.0377) * 3240 = 1.0075 (0.75% gross profit)
    After 3x slippage (0.1%) and 3x fees (0.1%): ~0.15% net profit
    """
    rates = [
        1 / 85000,  # USDT -> BTC (buy BTC, get rate = 1/ask)
        1 / 0.0377,  # BTC -> ETH (buy ETH, get rate = 1/ask)
        3240,  # ETH -> USDT (sell ETH, get rate = bid)
    ]

    result = calculate_cycle_profit(
        initial_amount=150.0,
        rates=rates,
        fee_rate=0.001,
        slippage_pct=0.001,
    )

    # With the right rates, final should be > initial
    assert result["final_amount"] > result["initial_amount"], (
        f"Expected profit but got loss: {result}"
    )
    assert result["net_profit"] > 0
    assert result["trade_count"] == 3


def test_loss_cycle():
    """Test a cycle that results in a loss."""
    rates = [
        1 / 85010,  # Buy BTC (high ask)
        1 / 0.0377,  # Buy ETH
        3190,  # Sell ETH low (not enough gap)
    ]

    result = calculate_cycle_profit(
        initial_amount=150.0,
        rates=rates,
        fee_rate=0.001,
        slippage_pct=0.001,
    )

    assert result["final_amount"] < result["initial_amount"]
    assert result["net_profit"] < 0


def test_higher_fees_reduce_profit():
    """Higher fees should result in less profit."""
    rates = [1 / 85000, 1 / 0.0377, 3250]  # ~1% gross profit

    low_fee = calculate_cycle_profit(150.0, rates, fee_rate=0.001)
    high_fee = calculate_cycle_profit(150.0, rates, fee_rate=0.005)

    assert low_fee["net_profit"] > high_fee["net_profit"]
