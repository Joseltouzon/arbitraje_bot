from __future__ import annotations

from app.exchanges.binance_ws import BinanceWsStream
from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PriceAggregator:
    """
    Real-time price feed using Binance WebSocket.
    Falls back to REST if WebSocket fails.
    """

    def __init__(self) -> None:
        self.ws = BinanceWsStream()
        self._running = False
        self._update_count = 0

    @property
    def tickers(self) -> dict[str, BidAsk]:
        return self.ws.tickers

    @property
    def connected(self) -> bool:
        return self.ws.connected

    async def start(self) -> None:
        """Start the WebSocket price stream."""
        self._running = True
        logger.info("Starting WebSocket price stream...")
        await self.ws.start()

    async def fetch_tickers(self) -> dict[str, BidAsk]:
        """Get current tickers (from WebSocket cache)."""
        return self.ws.tickers

    def filter_usdt_pairs(
        self, tickers: dict[str, BidAsk], min_qty: float = 100.0
    ) -> dict[str, BidAsk]:
        """Filter to USDT pairs with sufficient liquidity."""
        filtered = {}
        for symbol, bidask in tickers.items():
            if not symbol.endswith("USDT"):
                continue
            liquidity = bidask.ask * bidask.ask_qty
            if liquidity >= min_qty:
                filtered[symbol] = bidask
        return filtered

    def get_quote_prices(self, tickers: dict[str, BidAsk]) -> dict[str, BidAsk]:
        """Get tickers for pairs quoted in major currencies."""
        quotes = {
            "USDT", "USDC", "BTC", "ETH", "BNB", "BUSD", "SOL", "DOGE",
        }
        filtered = {}
        for symbol, bidask in tickers.items():
            for quote in sorted(quotes, key=len, reverse=True):
                if symbol.endswith(quote) and len(symbol) > len(quote):
                    filtered[symbol] = bidask
                    break
        return filtered

    def stop(self) -> None:
        """Stop the price stream."""
        self._running = False
        self.ws.stop()

    def get_stats(self) -> dict:
        """Get aggregator statistics."""
        return {
            "connected": self.ws.connected,
            "pairs_loaded": len(self.ws.tickers),
            "total_updates": self.ws.update_count,
            **self.ws.get_stats(),
        }
