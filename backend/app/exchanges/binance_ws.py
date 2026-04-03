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

WS_ALL_BOOK_TICKERS = "wss://stream.binance.com:9443/ws/!bookTicker"
REST_ALL_TICKERS = "https://api.binance.com/api/v3/ticker/bookTicker"

PriceCallback = Callable[[dict[str, BidAsk]], Any]


class BinanceWsStream:
    """
    Real-time price feed from Binance via WebSocket.
    Receives bid/ask updates the instant they change.
    Falls back to REST for initial snapshot.
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
        self._ws_messages = 0

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
        self._callbacks.append(callback)

    async def load_initial_snapshot(self) -> dict[str, BidAsk]:
        """Load initial snapshot via REST (fast bootstrap)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(REST_ALL_TICKERS)
                resp.raise_for_status()
                data = resp.json()

                for item in data:
                    symbol = item.get("symbol", "")
                    bid = float(item.get("bidPrice", 0))
                    ask = float(item.get("askPrice", 0))

                    if bid > 0 and ask > 0 and bid < ask:
                        self._tickers[symbol] = BidAsk(
                            bid=bid,
                            ask=ask,
                            bid_qty=float(item.get("bidQty", 0)),
                            ask_qty=float(item.get("askQty", 0)),
                        )

                logger.info(f"WS initial snapshot loaded ({len(self._tickers)} pairs)")
                return self._tickers

        except Exception as e:
            logger.error(f"WS snapshot failed: {e}")
            return {}

    async def start(self) -> None:
        """Start the WebSocket stream with auto-reconnect."""
        self._running = True

        # Load initial snapshot via REST
        await self.load_initial_snapshot()

        # Start WebSocket streaming
        while self._running:
            try:
                await self._connect_and_stream()
            except websockets.exceptions.ConnectionClosed as e:
                self._connected = False
                logger.warning(
                    f"WS closed (code={e.code}). Reconnecting in {self._reconnect_delay}s..."
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)
            except Exception as e:
                self._connected = False
                logger.error(f"WS error: {e}. Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    async def _connect_and_stream(self) -> None:
        """Connect to Binance WebSocket and stream bookTicker updates."""
        async with websockets.connect(
            WS_ALL_BOOK_TICKERS,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
            open_timeout=10,
        ) as ws:
            self._ws = ws
            self._connected = True
            self._reconnect_delay = 1.0
            logger.info("WS connected to Binance !bookTicker stream")

            async for message in ws:
                if not self._running:
                    break

                self._ws_messages += 1
                try:
                    data = json.loads(message)
                    self._process_ticker_update(data)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug(f"WS parse error: {e}")

    def _process_ticker_update(self, data: dict) -> None:
        """Process a single ticker update from WebSocket."""
        symbol = data.get("s", "")
        if not symbol:
            return

        bid = float(data.get("b", 0))
        ask = float(data.get("a", 0))

        if bid <= 0 or ask <= 0 or bid >= ask:
            return

        self._tickers[symbol] = BidAsk(
            bid=bid,
            ask=ask,
            bid_qty=float(data.get("B", 0)),
            ask_qty=float(data.get("A", 0)),
        )

        self._update_count += 1
        self._last_update = datetime.now()

        # Notify callbacks every 50 updates (batch for performance)
        if self._update_count % 50 == 0:
            # Schedule callbacks as tasks to avoid blocking
            for cb in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.create_task(self._safe_callback(cb, self._tickers))
                    else:
                        cb(self._tickers)
                except Exception as e:
                    logger.error(f"WS callback error: {e}")

    async def _safe_callback(self, cb: PriceCallback, tickers: dict[str, BidAsk]) -> None:
        """Safely execute async callback."""
        try:
            await cb(tickers)
        except Exception as e:
            logger.error(f"WS async callback error: {e}")

    def stop(self) -> None:
        self._running = False
        self._connected = False

    async def close(self) -> None:
        self.stop()
        if self._ws:
            await self._ws.close()

    def get_stats(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "pairs_loaded": len(self._tickers),
            "total_updates": self._update_count,
            "ws_messages": self._ws_messages,
            "last_update": (self._last_update.isoformat() if self._last_update else None),
        }
