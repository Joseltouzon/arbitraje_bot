from __future__ import annotations

from datetime import datetime

from app.exchanges.base import ExchangeAdapter
from app.exchanges.binance import BinanceAdapter
from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PriceAggregator:
    """
    Fetches and caches price data from exchanges.
    Handles the polling loop and stores snapshots in Redis.
    """

    def __init__(self, exchange: ExchangeAdapter | None = None) -> None:
        self.exchange = exchange or BinanceAdapter()
        self._last_snapshot: dict[str, BidAsk] = {}
        self._last_update: datetime | None = None
        self._running = False

    @property
    def last_snapshot(self) -> dict[str, BidAsk]:
        return self._last_snapshot

    @property
    def last_update(self) -> datetime | None:
        return self._last_update

    async def fetch_tickers(self) -> dict[str, BidAsk]:
        """Fetch all tickers from the exchange."""
        try:
            tickers = await self.exchange.get_all_tickers()
            self._last_snapshot = tickers
            self._last_update = datetime.now()
            return tickers
        except Exception as e:
            logger.error(f"Failed to fetch tickers: {e}")
            return self._last_snapshot

    def filter_usdt_pairs(
        self, tickers: dict[str, BidAsk], min_qty: float = 100.0
    ) -> dict[str, BidAsk]:
        """
        Filter to only USDT pairs with sufficient liquidity.

        Args:
            tickers: all tickers from exchange
            min_qty: minimum quantity in USDT for the ask side (bid_price * ask_qty)
        """
        filtered = {}
        for symbol, bidask in tickers.items():
            if not symbol.endswith("USDT"):
                continue
            liquidity = bidask.ask * bidask.ask_qty
            if liquidity >= min_qty:
                filtered[symbol] = bidask

        logger.info(f"Filtered to {len(filtered)} USDT pairs (min liquidity: {min_qty})")
        return filtered

    def get_quote_prices(self, tickers: dict[str, BidAsk]) -> dict[str, BidAsk]:
        """
        Get tickers for pairs quoted in major currencies.
        Useful for building the full currency graph.
        """
        quotes = {"USDT", "USDC", "BTC", "ETH", "BNB", "BUSD", "SOL", "DOGE"}
        filtered = {}
        for symbol, bidask in tickers.items():
            for quote in sorted(quotes, key=len, reverse=True):
                if symbol.endswith(quote) and len(symbol) > len(quote):
                    filtered[symbol] = bidask
                    break
        return filtered

    async def close(self) -> None:
        await self.exchange.close()
