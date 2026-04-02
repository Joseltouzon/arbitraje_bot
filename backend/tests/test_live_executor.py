import asyncio

from app.models.primitives import BidAsk
from app.services.live_executor import LiveExecutor


class FakeExchange:
    """Minimal fake exchange for testing LiveExecutor logic."""

    def __init__(self):
        self._balances = {"USDT": 150, "BTC": 0, "ETH": 0}
        self.orders = []

    async def get_balance(self, currency):
        from decimal import Decimal

        return Decimal(str(self._balances.get(currency, 0)))

    async def get_orderbook(self, symbol, depth=20):
        from datetime import datetime

        from app.models.primitives import OrderBook, OrderBookLevel

        return OrderBook(
            symbol=symbol,
            bids=[OrderBookLevel(price=100, quantity=1000)] * depth,
            asks=[OrderBookLevel(price=100.1, quantity=1000)] * depth,
            timestamp=datetime.now(),
        )

    async def create_market_order(self, symbol, side, quantity):
        from datetime import datetime

        from app.models.primitives import TradeResult

        self.orders.append({"symbol": symbol, "side": side, "quantity": float(quantity)})
        return TradeResult(
            order_id="123",
            symbol=symbol,
            side=side,
            quantity=float(quantity),
            price=100.0,
            fee=0.1,
            status="FILLED",
            timestamp=datetime.now(),
        )

    async def cleanup_dust(self):
        return {}


def test_live_executor_disabled_by_default():
    executor = LiveExecutor(exchange=FakeExchange())
    assert executor.enabled is False
    assert executor._enabled is False
    assert executor._confirmed is False


def test_live_executor_enable_and_confirm():
    executor = LiveExecutor(exchange=FakeExchange())
    # Confirm before enable should fail
    result = executor.confirm()
    assert result["status"] == "error"
    assert "Enable first" in result["message"]


def test_live_executor_stats_empty():
    executor = LiveExecutor(exchange=FakeExchange())
    stats = executor.get_stats()
    assert stats["total_trades"] == 0
    assert stats["profitable_trades"] == 0
    assert stats["success_rate"] == 0


def test_live_executor_extract_quote():
    assert LiveExecutor._extract_quote("BTCUSDT") == "USDT"
    assert LiveExecutor._extract_quote("ETHBTC") == "BTC"
    assert LiveExecutor._extract_quote("ETHUSDT") == "USDT"
    assert LiveExecutor._extract_quote("SOLFDUSD") == "FDUSD"
    assert LiveExecutor._extract_quote("UNKNOWN") == ""


def test_live_executor_extract_base():
    assert LiveExecutor._extract_base("BTCUSDT") == "BTC"
    assert LiveExecutor._extract_base("ETHBTC") == "ETH"
    assert LiveExecutor._extract_base("ETHUSDT") == "ETH"
    assert LiveExecutor._extract_base("SOLFDUSD") == "SOL"
    assert LiveExecutor._extract_base("UNKNOWN") == ""


def test_live_executor_extract_complex_pairs():
    """Test pairs where simple replace would fail."""
    assert LiveExecutor._extract_base("DOGEUSDT") == "DOGE"
    assert LiveExecutor._extract_quote("DOGEUSDT") == "USDT"
    assert LiveExecutor._extract_base("SHIBUSDT") == "SHIB"
    assert LiveExecutor._extract_quote("SHIBUSDT") == "USDT"


def test_live_executor_execute_returns_none_when_disabled():
    """Disabled executor should return None without touching exchange."""
    executor = LiveExecutor(exchange=FakeExchange())
    cycle = {"legs": [{"pair": "BTCUSDT", "side": "buy"}] * 3}
    tickers = {"BTCUSDT": BidAsk(bid=85000, ask=85010, bid_qty=10, ask_qty=10)}

    result = asyncio.run(executor.execute_cycle(cycle, tickers))
    assert result is None


def test_live_executor_recent_trades_empty():
    executor = LiveExecutor(exchange=FakeExchange())
    recent = executor.get_recent_trades()
    assert recent == []


def test_live_executor_disable():
    executor = LiveExecutor(exchange=FakeExchange())
    result = executor.disable()
    assert result["status"] == "disabled"
    assert executor.enabled is False
