from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)

REST_ALL_TICKERS = "https://api.binance.com/api/v3/ticker/bookTicker"

PriceCallback = Callable[[dict[str, BidAsk]], Any]


class PriceAggregator:
    """
    Price feed from Binance via REST polling.
    Polls every ~1 second for near-real-time updates.
    """

    def __init__(self) -> None:
        self._tickers: dict[str, BidAsk] = {}
        self._callbacks: list[PriceCallback] = []
        self._running = False
        self._update_count = 0
        self._last_update: datetime | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def tickers(self) -> dict[str, BidAsk]:
        return self._tickers

    @property
    def connected(self) -> bool:
        return len(self._tickers) > 0

    @property
    def update_count(self) -> int:
        return self._update_count

    def on_update(self, callback: PriceCallback) -> None:
        self._callbacks.append(callback)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def fetch_tickers(self) -> dict[str, BidAsk]:
        """Fetch all tickers via REST."""
        try:
            client = await self._get_client()
            resp = await client.get(REST_ALL_TICKERS)
            resp.raise_for_status()
            data = resp.json()

            tickers = {}
            for item in data:
                symbol = item.get("symbol", "")
                bid = float(item.get("bidPrice", 0))
                ask = float(item.get("askPrice", 0))
                if bid > 0 and ask > 0 and bid < ask:
                    tickers[symbol] = BidAsk(
                        bid=bid,
                        ask=ask,
                        bid_qty=float(item.get("bidQty", 0)),
                        ask_qty=float(item.get("askQty", 0)),
                    )

            self._tickers = tickers
            self._update_count += 1
            self._last_update = datetime.now()
            return tickers

        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            return self._tickers

    async def start(self, interval_sec: float = 1.0) -> None:
        """Start continuous polling loop."""
        self._running = True
        logger.info(f"Starting price polling (interval: {interval_sec}s)")

        while self._running:
            try:
                tickers = await self.fetch_tickers()
                if tickers:
                    for cb in self._callbacks:
                        try:
                            cb(tickers)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
            except Exception as e:
                logger.error(f"Poll error: {e}")
            await asyncio.sleep(interval_sec)

    def filter_usdt_pairs(
        self, tickers: dict[str, BidAsk], min_qty: float = 100.0
    ) -> dict[str, BidAsk]:
        filtered = {}
        for symbol, bidask in tickers.items():
            if not symbol.endswith("USDT"):
                continue
            if bidask.ask * bidask.ask_qty >= min_qty:
                filtered[symbol] = bidask
        return filtered

    def get_quote_prices(self, tickers: dict[str, BidAsk]) -> dict[str, BidAsk]:
        quotes = {"USDT", "USDC", "BTC", "ETH", "BNB", "BUSD", "SOL", "DOGE"}
        filtered = {}
        for symbol, bidask in tickers.items():
            for quote in sorted(quotes, key=len, reverse=True):
                if symbol.endswith(quote) and len(symbol) > len(quote):
                    filtered[symbol] = bidask
                    break
        return filtered

    def stop(self) -> None:
        self._running = False

    async def close(self) -> None:
        self.stop()
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def get_stats(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "pairs_loaded": len(self._tickers),
            "total_updates": self._update_count,
            "last_update": (
                self._last_update.isoformat() if self._last_update else None
            ),
        }
