from __future__ import annotations

from datetime import datetime
from typing import Any

from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Key symbols for spot-futures arbitrage
FUTURES_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]


class SpotFuturesDetector:
    """
    Detects spot-futures arbitrage opportunities.

    Strategy: Cash and Carry
    - When futures price > spot price (premium): buy spot + sell futures
    - When futures price < spot price (discount): sell spot + buy futures
    - Profit = |premium/discount| - fees (0.1% spot + 0.02% futures)
    """

    def __init__(self, futures_adapter: BinanceFuturesAdapter) -> None:
        self.futures = futures_adapter
        self._opportunities: list[dict[str, Any]] = []
        self._last_scan: datetime | None = None

    async def scan(
        self,
        spot_tickers: dict[str, BidAsk],
        min_premium_pct: float = 0.15,
    ) -> list[dict[str, Any]]:
        """
        Scan for spot-futures arbitrage opportunities.

        Args:
            spot_tickers: current spot prices from aggregator
            min_premium_pct: minimum premium to consider (default 0.15%)
        """
        opportunities = []

        try:
            futures_prices = await self.futures.get_all_futures_prices()
        except Exception as e:
            logger.error(f"Failed to fetch futures prices: {e}")
            return []

        for symbol in FUTURES_SYMBOLS:
            if symbol not in spot_tickers or symbol not in futures_prices:
                continue

            spot_bid = spot_tickers[symbol].bid
            spot_ask = spot_tickers[symbol].ask
            spot_mid = (spot_bid + spot_ask) / 2
            futures_price = futures_prices[symbol]

            if spot_mid <= 0:
                continue

            # Calculate premium
            premium_pct = (futures_price - spot_mid) / spot_mid * 100

            # Total fees: 0.1% spot + 0.02% futures = 0.12%
            total_fees_pct = 0.12
            net_profit_pct = abs(premium_pct) - total_fees_pct

            if net_profit_pct < min_premium_pct:
                continue

            # Get funding rate
            try:
                funding = await self.futures.get_funding_rate(symbol)
                funding_rate = funding.get("funding_rate", 0)
            except Exception:
                funding_rate = 0

            opportunity = {
                "symbol": symbol,
                "spot_price": round(spot_mid, 2),
                "futures_price": round(futures_price, 2),
                "premium_pct": round(premium_pct, 4),
                "net_profit_pct": round(net_profit_pct, 4),
                "direction": "futures_premium" if premium_pct > 0 else "futures_discount",
                "strategy": (
                    "buy_spot_sell_futures" if premium_pct > 0 else "sell_spot_buy_futures"
                ),
                "funding_rate": funding_rate,
                "funding_profit_8h": round(funding_rate * 100, 4),
                "timestamp": datetime.now().isoformat(),
            }

            opportunities.append(opportunity)

            logger.info(
                f"Spot-Futures: {symbol} premium={premium_pct:.3f}% "
                f"net={net_profit_pct:.3f}% funding={funding_rate:.6f}"
            )

        # Sort by profit descending
        opportunities.sort(key=lambda o: o["net_profit_pct"], reverse=True)
        self._opportunities = opportunities
        self._last_scan = datetime.now()

        return opportunities

    def get_stats(self) -> dict[str, Any]:
        return {
            "opportunities": len(self._opportunities),
            "last_scan": (self._last_scan.isoformat() if self._last_scan else None),
            "top_opportunity": self._opportunities[0] if self._opportunities else None,
        }
