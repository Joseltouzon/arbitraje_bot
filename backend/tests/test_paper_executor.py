from app.models.primitives import BidAsk
from app.services.paper_executor import PaperExecutor
from app.services.paper_trader import PaperTrader


def test_paper_executor_initial_state():
    executor = PaperExecutor(initial_balance=150.0)
    assert executor.balance_usdt == 150.0
    assert executor.net_profit == 0.0
    assert executor.net_profit_pct == 0.0
    assert len(executor.trades) == 0


def test_paper_executor_profitable_cycle():
    """Test executing a profitable paper cycle."""
    executor = PaperExecutor(initial_balance=150.0)

    cycle = {
        "currencies": ["USDT", "BTC", "ETH", "USDT"],
        "net_profit_pct": 0.5,
        "legs": [
            {
                "from_currency": "USDT",
                "to_currency": "BTC",
                "pair": "BTCUSDT",
                "side": "buy",
                "rate": 1 / 85000,
            },
            {
                "from_currency": "BTC",
                "to_currency": "ETH",
                "pair": "ETHBTC",
                "side": "buy",
                "rate": 1 / 0.0374,
            },
            {
                "from_currency": "ETH",
                "to_currency": "USDT",
                "pair": "ETHUSDT",
                "side": "sell",
                "rate": 3220,
            },
        ],
    }

    tickers = {
        "BTCUSDT": BidAsk(bid=85100, ask=85000, bid_qty=10, ask_qty=10),
        "ETHBTC": BidAsk(bid=0.0376, ask=0.0374, bid_qty=50, ask_qty=50),
        "ETHUSDT": BidAsk(bid=3220, ask=3210, bid_qty=100, ask_qty=100),
    }

    trade = executor.execute_cycle(cycle, tickers)

    assert trade is not None
    assert trade.id == 1
    assert len(executor.trades) == 1
    assert executor.balance_usdt != 150.0


def test_paper_executor_losing_cycle():
    """Test executing a losing paper cycle."""
    executor = PaperExecutor(initial_balance=150.0)

    cycle = {
        "currencies": ["USDT", "BTC", "ETH", "USDT"],
        "net_profit_pct": -0.5,
        "legs": [
            {
                "from_currency": "USDT",
                "to_currency": "BTC",
                "pair": "BTCUSDT",
                "side": "buy",
                "rate": 1 / 85000,
            },
            {
                "from_currency": "BTC",
                "to_currency": "ETH",
                "pair": "ETHBTC",
                "side": "buy",
                "rate": 1 / 0.0378,
            },
            {
                "from_currency": "ETH",
                "to_currency": "USDT",
                "pair": "ETHUSDT",
                "side": "sell",
                "rate": 3180,
            },
        ],
    }

    tickers = {
        "BTCUSDT": BidAsk(bid=85100, ask=85000, bid_qty=10, ask_qty=10),
        "ETHBTC": BidAsk(bid=0.0379, ask=0.0378, bid_qty=50, ask_qty=50),
        "ETHUSDT": BidAsk(bid=3180, ask=3175, bid_qty=100, ask_qty=100),
    }

    trade = executor.execute_cycle(cycle, tickers)

    assert trade is not None
    assert trade.profit_usdt < 0
    assert executor.balance_usdt < 150.0
    assert executor.consecutive_losses == 1


def test_paper_executor_fees_tracked():
    """Fees should be tracked across trades."""
    executor = PaperExecutor(initial_balance=150.0)

    cycle = {
        "currencies": ["USDT", "BTC", "ETH", "USDT"],
        "net_profit_pct": 0.5,
        "legs": [
            {
                "from_currency": "USDT",
                "to_currency": "BTC",
                "pair": "BTCUSDT",
                "side": "buy",
                "rate": 1 / 85000,
            },
            {
                "from_currency": "BTC",
                "to_currency": "ETH",
                "pair": "ETHBTC",
                "side": "buy",
                "rate": 1 / 0.0374,
            },
            {
                "from_currency": "ETH",
                "to_currency": "USDT",
                "pair": "ETHUSDT",
                "side": "sell",
                "rate": 3230,
            },
        ],
    }

    tickers = {
        "BTCUSDT": BidAsk(bid=85100, ask=85000, bid_qty=10, ask_qty=10),
        "ETHBTC": BidAsk(bid=0.0376, ask=0.0374, bid_qty=50, ask_qty=50),
        "ETHUSDT": BidAsk(bid=3230, ask=3220, bid_qty=100, ask_qty=100),
    }

    executor.execute_cycle(cycle, tickers)

    assert executor.total_fees_paid > 0
    assert executor.trades[0].total_fees > 0


def test_paper_executor_missing_ticker():
    """Should return None if a required ticker is missing."""
    executor = PaperExecutor(initial_balance=150.0)

    cycle = {
        "currencies": ["USDT", "BTC", "ETH", "USDT"],
        "net_profit_pct": 0.5,
        "legs": [
            {
                "from_currency": "USDT",
                "to_currency": "BTC",
                "pair": "BTCUSDT",
                "side": "buy",
                "rate": 1 / 85000,
            },
            {
                "from_currency": "BTC",
                "to_currency": "ETH",
                "pair": "ETHBTC",
                "side": "buy",
                "rate": 1 / 0.0374,
            },
            {
                "from_currency": "ETH",
                "to_currency": "USDT",
                "pair": "ETHUSDT",
                "side": "sell",
                "rate": 3220,
            },
        ],
    }

    tickers = {
        "BTCUSDT": BidAsk(bid=85100, ask=85000, bid_qty=10, ask_qty=10),
    }

    trade = executor.execute_cycle(cycle, tickers)
    assert trade is None
    assert len(executor.trades) == 0


def test_paper_trader_should_execute():
    """Test paper trader execution decision logic."""
    trader = PaperTrader(initial_balance=150.0, min_profit_pct=0.2)

    cycle = {"net_profit_pct": 0.5, "currencies": [], "legs": []}
    assert trader.should_execute(cycle) is False

    trader.enable()
    assert trader.should_execute(cycle) is True

    low_cycle = {"net_profit_pct": 0.1, "currencies": [], "legs": []}
    assert trader.should_execute(low_cycle) is False


def test_paper_executor_stats():
    """Test stats calculation."""
    executor = PaperExecutor(initial_balance=150.0)
    stats = executor.get_stats()

    assert stats["initial_balance"] == 150.0
    assert stats["current_balance"] == 150.0
    assert stats["total_trades"] == 0
    assert stats["success_rate"] == 0.0
    assert stats["net_profit"] == 0.0


def test_paper_executor_balance_history():
    """Balance history should be recorded."""
    executor = PaperExecutor(initial_balance=150.0)

    assert len(executor.balance_history) == 1
    assert executor.balance_history[0]["event"] == "initial"
    assert executor.balance_history[0]["balance"] == 150.0
