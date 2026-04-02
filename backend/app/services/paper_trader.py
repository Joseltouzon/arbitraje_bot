from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db.models import TradeHistory
from app.db.session import async_session_factory
from app.services.paper_executor import PaperExecutor
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PaperTrader:
    """
    Integrates paper trading with the cycle scanner.
    Automatically executes detected profitable cycles in paper mode.
    """

    def __init__(
        self,
        initial_balance: float = 150.0,
        min_profit_pct: float = 0.2,
        max_trades_per_hour: int = 20,
    ) -> None:
        self.executor = PaperExecutor(initial_balance=initial_balance)
        self.min_profit_pct = min_profit_pct
        self.max_trades_per_hour = max_trades_per_hour
        self._enabled = False
        self._trades_this_hour: list[datetime] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        logger.info("Paper trading ENABLED")

    def disable(self) -> None:
        self._enabled = False
        logger.info("Paper trading DISABLED")

    def should_execute(self, cycle: dict[str, Any]) -> bool:
        """Check if a cycle should be executed."""
        if not self._enabled:
            return False

        # Check profit threshold
        profit = cycle.get("net_profit_pct", 0)
        if profit < self.min_profit_pct:
            return False

        # Check hourly trade limit
        now = datetime.now()
        cutoff = now.replace(minute=0, second=0, microsecond=0)
        self._trades_this_hour = [t for t in self._trades_this_hour if t >= cutoff]
        return len(self._trades_this_hour) < self.max_trades_per_hour

    async def try_execute(
        self,
        cycle: dict[str, Any],
        tickers: dict,
    ) -> dict[str, Any] | None:
        """Try to execute a cycle in paper mode."""
        if not self.should_execute(cycle):
            return None

        trade = self.executor.execute_cycle(cycle, tickers)
        if trade is None:
            return None

        self._trades_this_hour.append(datetime.now())

        # Log to database
        await self._log_trade(trade)

        return {
            "trade_id": trade.id,
            "currencies": trade.currencies,
            "profit_usdt": round(trade.profit_usdt, 6),
            "profit_pct": round(trade.profit_pct, 4),
            "balance": round(self.executor.balance_usdt, 6),
        }

    async def _log_trade(self, trade) -> None:
        """Log paper trade to database."""
        try:
            async with async_session_factory() as session:
                record = TradeHistory(
                    mode="paper",
                    currencies=",".join(trade.currencies),
                    pairs=",".join(trade.pairs),
                    sides=",".join(trade.sides),
                    initial_amount=trade.initial_amount,
                    final_amount=trade.final_amount,
                    profit_usdt=trade.profit_usdt,
                    profit_pct=trade.profit_pct,
                    total_fees=trade.total_fees,
                    status="completed",
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log paper trade: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get paper trading stats."""
        return {
            "enabled": self._enabled,
            **self.executor.get_stats(),
        }

    async def restore_from_redis(self, redis_cache) -> None:
        """Restore paper trading state from Redis cache."""
        try:
            state = await redis_cache.load_paper_state()
            if not state:
                return
            balance = state.get("current_balance")
            if balance and balance > 0:
                self.executor.balance_usdt = balance
                self.executor.initial_balance = state.get("initial_balance", balance)
                logger.info(
                    f"Paper state restored: balance=${balance:.6f} "
                    f"({state.get('total_trades', 0)} trades)"
                )
        except Exception as e:
            logger.debug(f"Paper state restore failed: {e}")

    def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Get recent paper trades."""
        return self.executor.get_recent_trades(limit=limit)

    def get_balance_history(self) -> list[dict]:
        """Get balance history for charting."""
        return self.executor.balance_history
