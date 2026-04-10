from __future__ import annotations

from datetime import datetime
from typing import Any

from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Symbols eligible for funding rate carry
FUNDING_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "MATICUSDT",
    "UNIUSDT",
]


class SpotFuturesDetector:
    """
    Scans for funding rate carry opportunities.

    Strategy: Cash-and-Carry (funding rate harvesting)
    - When funding_rate > 0: longs pay shorts → buy spot + short futures → collect funding
    - When funding_rate < 0: shorts pay longs → sell spot + long futures → collect funding
    - Funding settles every 8h (00:00, 08:00, 16:00 UTC)
    - Entry: |funding_rate| >= min_threshold
    - Exit: |funding_rate| drops below exit_threshold or flips sign
    """

    def __init__(self, futures_adapter: BinanceFuturesAdapter) -> None:
        self.futures = futures_adapter
        self._opportunities: list[dict[str, Any]] = []
        self._last_scan: datetime | None = None

    async def scan(
        self,
        spot_tickers: dict[str, BidAsk],
        min_funding_rate: float = 0.001,  # 0.001% per 8h = ~0.11% monthly
    ) -> list[dict[str, Any]]:
        """
        Scan for funding rate carry opportunities.

        Args:
            spot_tickers: current spot prices
            min_funding_rate: minimum |funding_rate| to enter (default 0.001%)
        """
        try:
            funding_data = await self.futures.get_all_funding_rates()
        except Exception as e:
            logger.error(f"Failed to fetch funding rates: {e}")
            return []

        # Index by symbol
        funding_by_symbol = {d["symbol"]: d for d in funding_data}

        opportunities = []

        for symbol in FUNDING_SYMBOLS:
            if symbol not in funding_by_symbol:
                continue

            fr_data = funding_by_symbol[symbol]
            funding_rate = fr_data["funding_rate"]
            abs_rate = abs(funding_rate)

            if abs_rate < min_funding_rate:
                continue

            # Need spot price for the UI
            spot_price = 0.0
            if symbol in spot_tickers:
                spot_mid = (spot_tickers[symbol].bid + spot_tickers[symbol].ask) / 2
                spot_price = round(spot_mid, 2)

            # Calculate projected returns
            # Funding rate * 3 settlements/day * 30 days = monthly %
            daily_rate = abs_rate * 3  # 3 settlements per day
            monthly_rate = daily_rate * 30
            annual_rate = daily_rate * 365

            direction = "funding_positive" if funding_rate > 0 else "funding_negative"

            opportunity = {
                "symbol": symbol,
                "funding_rate": round(funding_rate, 6),
                "funding_rate_pct": round(funding_rate * 100, 4),
                "abs_rate_pct": round(abs_rate * 100, 4),
                "daily_return_pct": round(daily_rate * 100, 4),
                "monthly_return_pct": round(monthly_rate * 100, 2),
                "annual_return_pct": round(annual_rate * 100, 1),
                "net_profit_pct": round(daily_rate * 100, 4),  # used by executor for ranking
                "direction": direction,
                "spot_price": spot_price,
                "next_funding_time": fr_data.get("next_funding_time", 0),
                "timestamp": datetime.now().isoformat(),
            }

            opportunities.append(opportunity)

            logger.info(
                f"Funding opportunity: {symbol} rate={funding_rate:.6f} "
                f"({abs_rate * 100:.4f}%/8h, ~{monthly_rate * 100:.2f}%/mo) "
                f"dir={direction}"
            )

        # Sort by absolute funding rate descending
        opportunities.sort(key=lambda o: abs(o["funding_rate"]), reverse=True)
        self._opportunities = opportunities
        self._last_scan = datetime.now()

        if not opportunities:
            # Log top rates even if below threshold for debugging
            top_rates = []
            for symbol in FUNDING_SYMBOLS[:5]:
                if symbol in funding_by_symbol:
                    fr = funding_by_symbol[symbol]["funding_rate"]
                    top_rates.append(f"{symbol}:{fr * 100:.4f}%")
            if top_rates:
                logger.info(
                    f"Funding scan: no opportunities above {min_funding_rate * 100:.3f}%. "
                    f"Top rates: {', '.join(top_rates)}"
                )
        else:
            best = opportunities[0]
            logger.info(
                f"Funding scan: {len(opportunities)} opportunities. "
                f"Best: {best['symbol']} {best['funding_rate_pct']:.4f}%/8h"
            )

        return opportunities

    def get_stats(self) -> dict[str, Any]:
        return {
            "opportunities": len(self._opportunities),
            "last_scan": (self._last_scan.isoformat() if self._last_scan else None),
            "top_opportunity": self._opportunities[0] if self._opportunities else None,
        }
