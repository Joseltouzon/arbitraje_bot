from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx
import websockets

from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Binance WebSocket endpoints
WS_ALL_BOOK_TICKERS = "wss://stream.binance.com:9443/ws/!bookTicker"
REST_ALL_TICKERS = "https://api.binance.com/api/v3/ticker/bookTicker"

# Type for update callback
PriceCallback = Callable[[dict[str, BidAsk]], Any]


class BinanceWsStream:
    """
    Real-time price feed from Binance via WebSocket.
    Receives bid/ask updates the instant they change.
    Falls back to REST if WebSocket fails.
    """

    def __init__(self) -> None:
        self._tickers: dict[str, BidAsk] = {}
        self._callbacks: list[PriceCallback] = []
        self._running = False
        self._ws = None
        self._update_count = 0
        self._last_update: datetime | None = None
        self._connected = False
        self._reconnect_delay = 1.0

    @property
    def tickers(self) -> dict[str, BidAsk]:
        return self._tickers

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def update_count(self) -> int:
        return self._update_count

    def on_update(self, callback: PriceCallback) -> None:
        """Register a callback for price updates."""
        self._callbacks.append(callback)

    async def load_initial_snapshot(self) -> dict[str, BidAsk]:
        """Load initial snapshot via REST (fast bootstrap)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(REST_ALL_TICKERS)
                resp.raise_for_status()
                data = resp.json()

                for item in data:
                    symbol = item["s"]
                    bid = float(item["b"])
                    ask = float(item["a"])

                    if bid > 0 and ask > 0 and bid < ask:
                        self._tickers[symbol] = BidAsk(
                            bid=bid,
                            ask=ask,
                            bid_qty=float(item["B"]),
                            ask_qty=float(item["A"]),
                        )

                logger.info(
                    f"WebSocket: initial snapshot loaded "
                    f"({len(self._tickers)} pairs)"
                )
                return self._tickers

        except Exception as e:
            logger.error(f"Failed to load initial snapshot: {e}")
            return {}

    async def start(self) -> None:
        """Start the WebSocket stream."""
        self._running = True

        # Load initial snapshot via REST
        await self.load_initial_snapshot()

        # Start WebSocket streaming
        while self._running:
            try:
                await self._connect_and_stream()
            except Exception as e:
                self._connected = False
                logger.error(f"WebSocket error: {e}. Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    async def _connect_and_stream(self) -> None:
        """Connect to Binance WebSocket and stream bookTicker updates."""
        async with websockets.connect(
            WS_ALL_BOOK_TICKERS,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            self._ws = ws
            self._connected = True
            self._reconnect_delay = 1.0
            logger.info("WebSocket connected to Binance bookTicker stream")

            async for message in ws:
                if not self._running:
                    break

                try:
                    data = json.loads(message)
                    self._process_ticker_update(data)
                except Exception as e:
                    logger.error(f"WebSocket parse error: {e}")

    def _process_ticker_update(self, data: dict) -> None:
        """Process a single ticker update from WebSocket."""
        symbol = data.get("s", "")
        if not symbol:
            return

        bid = float(data.get("b", 0))
        ask = float(data.get("a", 0))

        if bid <= 0 or ask <= 0 or bid >= ask:
            return

        bid_qty = float(data.get("B", 0))
        ask_qty = float(data.get("A", 0))

        self._tickers[symbol] = BidAsk(
            bid=bid,
            ask=ask,
            bid_qty=bid_qty,
            ask_qty=ask_qty,
        )

        self._update_count += 1
        self._last_update = datetime.now()

        # Notify callbacks every 50 updates (batch for performance)
        if self._update_count % 50 == 0:
            for cb in self._callbacks:
                try:
                    cb(self._tickers)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

    def stop(self) -> None:
        """Stop the WebSocket stream."""
        self._running = False
        self._connected = False
        logger.info("WebSocket stream stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get stream statistics."""
        return {
            "connected": self._connected,
            "pairs_loaded": len(self._tickers),
            "total_updates": self._update_count,
            "last_update": (
                self._last_update.isoformat() if self._last_update else None
            ),
        }
