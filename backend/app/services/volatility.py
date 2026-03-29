from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Key pairs to monitor for volatility
KEY_PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ETHBTC"]


class VolatilityMonitor:
    """
    Monitors market conditions to detect when arbitrage is more likely.

    Tracks:
    - Price velocity (how fast key prices are moving)
    - Spread changes (wider spreads = more room for profit)
    - Volume spikes (high volume = more price movement)
    """

    def __init__(self, window_size: int = 30) -> None:
        # Price history: {symbol: deque of (timestamp, mid_price)}
        self._price_history: dict[str, deque[tuple[datetime, float]]] = {
            s: deque(maxlen=window_size) for s in KEY_PAIRS
        }
        # Spread history: {symbol: deque of (timestamp, spread_pct)}
        self._spread_history: dict[str, deque[tuple[datetime, float]]] = {
            s: deque(maxlen=window_size) for s in KEY_PAIRS
        }
        self._volatility_score = 0.0
        self._last_update: datetime | None = None
        self._update_count = 0

    def update(self, tickers: dict[str, BidAsk]) -> None:
        """Update volatility metrics with new price data."""
        now = datetime.now()

        for symbol in KEY_PAIRS:
            if symbol not in tickers:
                continue

            bidask = tickers[symbol]
            mid_price = (bidask.bid + bidask.ask) / 2
            spread_pct = (
                (bidask.ask - bidask.bid) / bidask.bid * 100
                if bidask.bid > 0
                else 0
            )

            self._price_history[symbol].append((now, mid_price))
            self._spread_history[symbol].append((now, spread_pct))

        self._volatility_score = self._calculate_score()
        self._last_update = now
        self._update_count += 1

    def _calculate_score(self) -> float:
        """Calculate volatility score 0-100."""
        score = 0.0
        factors = 0

        for symbol in KEY_PAIRS:
            prices = self._price_history[symbol]
            if len(prices) < 5:
                continue

            # Price velocity: % change over window
            first_price = prices[0][1]
            last_price = prices[-1][1]
            if first_price > 0:
                price_change_pct = abs(last_price - first_price) / first_price * 100
                # Normalize: 0.5% change = 50 points, 1% = 100
                score += min(price_change_pct * 100, 100)
                factors += 1

            # Spread widening: compare recent vs average
            spreads = [s[1] for s in self._spread_history[symbol]]
            if len(spreads) >= 3:
                recent_spread = sum(spreads[-3:]) / 3
                avg_spread = sum(spreads) / len(spreads)
                if avg_spread > 0:
                    spread_ratio = recent_spread / avg_spread
                    if spread_ratio > 1.5:
                        score += 30  # Spreads widened significantly
                    elif spread_ratio > 1.2:
                        score += 15
                    factors += 1

        return score / max(factors, 1)

    @property
    def volatility_score(self) -> float:
        """0-100 score. >50 = high volatility, more likely to have cycles."""
        return self._volatility_score

    @property
    def is_volatile(self) -> bool:
        """True when volatility is above normal (score > 40)."""
        return self._volatility_score > 40

    def get_indicators(self) -> dict[str, Any]:
        """Get current volatility indicators."""
        indicators = {}

        for symbol in KEY_PAIRS:
            prices = self._price_history[symbol]
            spreads = self._spread_history[symbol]

            if len(prices) < 2:
                continue

            first = prices[0][1]
            last = prices[-1][1]
            change_pct = (last - first) / first * 100 if first > 0 else 0

            indicators[symbol] = {
                "price_change_pct": round(change_pct, 4),
                "current_spread_pct": round(spreads[-1][1], 4) if spreads else 0,
                "avg_spread_pct": round(
                    sum(s[1] for s in spreads) / len(spreads), 4
                )
                if spreads
                else 0,
            }

        return indicators

    def get_stats(self) -> dict[str, Any]:
        return {
            "volatility_score": round(self._volatility_score, 2),
            "is_volatile": self.is_volatile,
            "update_count": self._update_count,
            "last_update": (
                self._last_update.isoformat() if self._last_update else None
            ),
            "indicators": self.get_indicators(),
        }
