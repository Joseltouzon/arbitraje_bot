from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RiskManager:
    """Manages trading risk limits and safety checks."""

    def __init__(self) -> None:
        self.trades_this_hour: list[datetime] = []
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.is_paused = False

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed right now."""
        if self.is_paused:
            return False, "Risk manager is paused"

        # Check hourly trade limit
        now = datetime.now()
        cutoff = now.replace(minute=0, second=0, microsecond=0)
        recent_trades = [t for t in self.trades_this_hour if t >= cutoff]

        if len(recent_trades) >= settings.max_trades_per_hour:
            return False, f"Hourly trade limit reached ({settings.max_trades_per_hour})"

        # Check consecutive losses
        if self.consecutive_losses >= settings.max_consecutive_losses:
            return False, f"Too many consecutive losses ({self.consecutive_losses})"

        # Check daily stop-loss
        if self.daily_pnl < 0:
            loss_pct = abs(self.daily_pnl) / (settings.trade_amount_usdt or 1)
            if loss_pct * 100 >= settings.stop_loss_pct:
                return False, f"Daily stop-loss triggered ({loss_pct:.2f}%)"

        return True, "OK"

    def record_trade(self, profit: float) -> None:
        """Record a completed trade."""
        self.trades_this_hour.append(datetime.now())
        self.daily_pnl += profit

        if profit < 0:
            self.consecutive_losses += 1
            logger.warning(
                f"Loss recorded. Consecutive losses: {self.consecutive_losses}"
            )
        else:
            self.consecutive_losses = 0

    def reset_daily(self) -> None:
        """Reset daily counters."""
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.is_paused = False
        logger.info("Daily risk counters reset")

    def pause(self) -> None:
        """Pause all trading."""
        self.is_paused = True
        logger.warning("Trading paused by risk manager")

    def resume(self) -> None:
        """Resume trading."""
        self.is_paused = False
        logger.info("Trading resumed")
