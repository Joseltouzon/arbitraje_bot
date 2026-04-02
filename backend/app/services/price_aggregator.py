from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from app.models.primitives import BidAsk
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.exchanges.binance_ws import BinanceWsStream
    from app.services.redis_cache import RedisCache

logger = get_logger(__name__)

REST_ALL_TICKERS = "https://api.binance.com/api/v3/ticker/bookTicker"

PriceCallback = Callable[[dict[str, BidAsk]], Any]


class PriceAggregator:
    """
    Price feed from Binance.
    Supports WebSocket streaming (primary) with REST polling fallback.
    Persists tickers to Redis for crash recovery.
    """

    def __init__(
        self,
        redis_cache: RedisCache | None = None,
        ws_stream: BinanceWsStream | None = None,
    ) -> None:
        self._tickers: dict[str, BidAsk] = {}
        self._callbacks: list[PriceCallback] = []
        self._running = False
        self._update_count = 0
        self._last_update: datetime | None = None
        self._client: httpx.AsyncClient | None = None
        self._redis = redis_cache
        self._ws = ws_stream
        self._mode = "rest"  # will be set to "ws" if WS starts ok

    @property
    def tickers(self) -> dict[str, BidAsk]:
        return self._tickers

    @property
    def connected(self) -> bool:
        return len(self._tickers) > 0

    @property
    def update_count(self) -> int:
        return self._update_count

    @property
    def mode(self) -> str:
        return self._mode

    def on_update(self, callback: PriceCallback) -> None:
        self._callbacks.append(callback)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def fetch_tickers_rest(self) -> dict[str, BidAsk]:
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

            if self._redis:
                await self._redis.save_tickers(tickers)

            return tickers

        except Exception as e:
            logger.error(f"REST price fetch error: {e}")
            return self._tickers

    async def start(self, interval_sec: float = 1.0) -> None:
        """
        Start price feed. Tries WebSocket first, falls back to REST.
        """
        self._running = True

        # Restore from Redis cache first
        if self._redis:
            cached = await self._redis.load_tickers()
            if cached:
                self._tickers = cached
                self._update_count += 1
                logger.info(f"Restored {len(cached)} tickers from Redis cache")

        # Try WebSocket mode
        if self._ws:
            try:
                self._ws.on_update(self._on_ws_update)
                ws_task = asyncio.create_task(self._ws.start())
                # Give WS a moment to connect and load snapshot
                await asyncio.sleep(3)
                if self._ws.connected and len(self._ws.tickers) > 0:
                    self._mode = "ws"
                    self._tickers = self._ws.tickers
                    logger.info(f"Price feed: WebSocket mode ({len(self._tickers)} pairs)")
                    # WS runs on its own task, keep aggregator alive
                    self._ws_task = ws_task
                    # Also run a periodic Redis persist loop
                    await self._ws_persist_loop()
                    return
                else:
                    ws_task.cancel()
                    logger.warning("WS didn't connect, falling back to REST")
            except Exception as e:
                logger.warning(f"WS start failed: {e}, falling back to REST")

        # REST polling mode
        self._mode = "rest"
        logger.info(f"Price feed: REST polling mode (interval: {interval_sec}s)")

        while self._running:
            try:
                tickers = await self.fetch_tickers_rest()
                if tickers:
                    for cb in self._callbacks:
                        try:
                            cb(tickers)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
            except Exception as e:
                logger.error(f"Poll error: {e}")
            await asyncio.sleep(interval_sec)

    async def _ws_persist_loop(self) -> None:
        """Periodically persist WS tickers to Redis and fire callbacks."""
        while self._running and self._ws and self._ws.connected:
            try:
                self._tickers = self._ws.tickers
                self._update_count = self._ws.update_count

                # Fire callbacks
                for cb in self._callbacks:
                    try:
                        cb(self._tickers)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

                # Persist to Redis every ~5 seconds
                if self._redis and self._update_count % 5 == 0:
                    await self._redis.save_tickers(self._tickers)

            except Exception as e:
                logger.error(f"WS persist loop error: {e}")
            await asyncio.sleep(1)

    def _on_ws_update(self, tickers: dict[str, BidAsk]) -> None:
        """Callback from WS stream — update internal state."""
        self._tickers = tickers
        self._update_count = self._ws.update_count if self._ws else self._update_count
        self._last_update = datetime.now()

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
        from app.core.graph import QUOTE_CURRENCIES

        filtered = {}
        for symbol, bidask in tickers.items():
            for quote in sorted(QUOTE_CURRENCIES, key=len, reverse=True):
                if symbol.endswith(quote) and len(symbol) > len(quote):
                    filtered[symbol] = bidask
                    break
        return filtered

    def stop(self) -> None:
        self._running = False
        if self._ws:
            self._ws.stop()

    async def close(self) -> None:
        self.stop()
        if self._ws:
            await self._ws.close()
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def get_stats(self) -> dict[str, Any]:
        stats = {
            "mode": self._mode,
            "connected": self.connected,
            "pairs_loaded": len(self._tickers),
            "total_updates": self._update_count,
            "last_update": (self._last_update.isoformat() if self._last_update else None),
            "redis_enabled": self._redis is not None and self._redis.connected,
        }
        if self._ws:
            stats["ws"] = self._ws.get_stats()
        return stats
