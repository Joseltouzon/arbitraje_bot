from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.config import settings
from app.core.calculator import calculate_cycle_profit
from app.core.graph import bellman_ford_cycles, build_currency_graph
from app.models.primitives import BidAsk
from app.services.price_aggregator import PriceAggregator
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Type for cycle update callback
CycleCallback = Callable[[list[dict[str, Any]]], Any]


class CycleScanner:
    """
    Continuously scans for profitable triangular cycles.
    Runs: price fetch → graph build → Bellman-Ford cycle detection.
    """

    def __init__(self, aggregator: PriceAggregator) -> None:
        self.aggregator = aggregator
        self._cycles: list[dict[str, Any]] = []
        self._tickers: dict[str, BidAsk] = {}
        self._running = False
        self._scan_count = 0
        self._last_scan_time: datetime | None = None
        self._callbacks: list[CycleCallback] = []
        self._scan_errors = 0

    @property
    def cycles(self) -> list[dict[str, Any]]:
        return self._cycles

    @property
    def tickers(self) -> dict[str, BidAsk]:
        return self._tickers

    @property
    def scan_count(self) -> int:
        return self._scan_count

    def on_cycle_update(self, callback: CycleCallback) -> None:
        """Register a callback for when cycles are updated."""
        self._callbacks.append(callback)

    async def scan_once(self) -> list[dict[str, Any]]:
        """Run a single scan cycle."""
        tickers = await self.aggregator.fetch_tickers()
        if not tickers:
            return []

        self._tickers = tickers

        # Filter to pairs with sufficient liquidity
        filtered = self.aggregator.get_quote_prices(tickers)
        if len(filtered) < 3:
            logger.warning("Not enough pairs for cycle detection")
            return []

        # Build currency graph
        graph, metadata = build_currency_graph(filtered)

        # Find profitable cycles using Bellman-Ford + DFS
        cycles = bellman_ford_cycles(
            graph=graph,
            metadata=metadata,
            start_currency=settings.start_currency,
            min_profit_pct=settings.min_profit_threshold_pct,
            max_cycle_length=settings.max_cycle_length,
        )

        # Enrich with exact profit calculations
        enriched = []
        for cycle in cycles:
            result = calculate_cycle_profit(
                initial_amount=settings.trade_amount_usdt,
                rates=[leg["rate"] for leg in cycle["legs"]],
                fee_rate=0.001,
                slippage_pct=0.001,
            )
            cycle["calculated"] = result
            cycle["timestamp"] = datetime.now().isoformat()
            enriched.append(cycle)

        self._cycles = enriched
        self._scan_count += 1
        self._last_scan_time = datetime.now()

        if enriched:
            logger.info(
                f"Scan #{self._scan_count}: {len(enriched)} profitable cycles | "
                f"best: +{enriched[0]['net_profit_pct']:.2f}%"
            )
            # Notify callbacks
            for cb in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(enriched)
                    else:
                        cb(enriched)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

        return enriched

    async def start_scanning(self) -> None:
        """Start continuous scanning loop."""
        self._running = True
        interval = settings.poll_interval_ms / 1000.0
        logger.info(f"Starting cycle scanner (interval: {interval}s)")

        while self._running:
            try:
                await self.scan_once()
            except Exception as e:
                self._scan_errors += 1
                logger.error(f"Scan error #{self._scan_errors}: {e}")
                if self._scan_errors > 10:
                    logger.error("Too many scan errors, pausing for 5s")
                    await asyncio.sleep(5)
                    self._scan_errors = 0
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Stop the scanning loop."""
        self._running = False
        logger.info("Cycle scanner stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get scanner statistics."""
        return {
            "scan_count": self._scan_count,
            "scan_errors": self._scan_errors,
            "last_scan": (
                self._last_scan_time.isoformat() if self._last_scan_time else None
            ),
            "current_cycles": len(self._cycles),
            "top_profit": self._cycles[0]["net_profit_pct"] if self._cycles else 0,
            "tickers_loaded": len(self._tickers),
        }
