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

CycleCallback = Callable[[list[dict[str, Any]]], Any]


class CycleScanner:
    """
    Continuously scans for profitable triangular cycles.
    Scans from multiple start currencies (USDT, BTC, ETH, BNB).
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
        self._callbacks.append(callback)

    async def scan_once(self) -> list[dict[str, Any]]:
        """Run a single scan cycle across all start currencies."""
        tickers = self.aggregator.tickers
        if not tickers:
            return []

        self._tickers = tickers

        # Filter to pairs with sufficient liquidity
        filtered = self.aggregator.get_quote_prices(tickers)
        if len(filtered) < 3:
            return []

        # Build currency graph once
        graph, metadata = build_currency_graph(filtered)

        # Scan from each start currency
        all_cycles: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()

        for start_cur in settings.start_currency_list:
            if start_cur not in graph:
                continue

            cycles = bellman_ford_cycles(
                graph=graph,
                metadata=metadata,
                start_currency=start_cur,
                min_profit_pct=settings.min_profit_threshold_pct,
                max_cycle_length=settings.max_cycle_length,
            )

            for cycle in cycles:
                key = tuple(cycle["currencies"])
                if key not in seen:
                    seen.add(key)

                    # Enrich with profit calculations
                    result = calculate_cycle_profit(
                        initial_amount=settings.trade_amount_usdt,
                        rates=[leg["rate"] for leg in cycle["legs"]],
                        fee_rate=0.001,
                        slippage_pct=0.001,
                    )
                    cycle["calculated"] = result
                    cycle["timestamp"] = datetime.now().isoformat()
                    cycle["start_currency"] = start_cur
                    all_cycles.append(cycle)

        # Sort by profit descending
        all_cycles.sort(key=lambda c: c["net_profit_pct"], reverse=True)

        self._cycles = all_cycles
        self._scan_count += 1
        self._last_scan_time = datetime.now()

        if all_cycles:
            top = all_cycles[0]
            logger.info(
                f"Scan #{self._scan_count}: {len(all_cycles)} cycles | "
                f"best: {top['currencies']} +{top['net_profit_pct']:.3f}%"
            )
            for cb in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(all_cycles)
                    else:
                        cb(all_cycles)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

        return all_cycles

    async def start_scanning(self) -> None:
        self._running = True
        interval = settings.poll_interval_ms / 1000.0
        logger.info(
            f"Starting cycle scanner (interval: {interval}s) | "
            f"currencies: {settings.start_currencies}"
        )

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
        self._running = False
        logger.info("Cycle scanner stopped")

    def get_stats(self) -> dict[str, Any]:
        return {
            "scan_count": self._scan_count,
            "scan_errors": self._scan_errors,
            "last_scan": (
                self._last_scan_time.isoformat() if self._last_scan_time else None
            ),
            "current_cycles": len(self._cycles),
            "top_profit": self._cycles[0]["net_profit_pct"] if self._cycles else 0,
            "tickers_loaded": len(self._tickers),
            "start_currencies": settings.start_currency_list,
        }
