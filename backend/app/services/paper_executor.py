from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PaperOrder:
    """A simulated order."""

    pair: str
    side: str  # "BUY" or "SELL"
    quantity: float
    price: float
    fee: float
    timestamp: float


@dataclass
class PaperPosition:
    """Currency balance in paper portfolio."""

    currency: str
    amount: float


@dataclass
class PaperTrade:
    """A completed simulated trade (3-leg cycle)."""

    id: int
    currencies: list[str]
    pairs: list[str]
    sides: list[str]
    initial_amount: float
    final_amount: float
    profit_usdt: float
    profit_pct: float
    total_fees: float
    orders: list[PaperOrder]
    executed_at: datetime
    latency_ms: float  # Simulated execution time


class PaperExecutor:
    """
    Simulates trade execution without real orders.
    Uses real market prices to track hypothetical P&L.
    """

    def __init__(
        self,
        initial_balance: float = 150.0,
        fee_rate: float = 0.001,
        slippage_pct: float = 0.001,
    ) -> None:
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        self.slippage_pct = slippage_pct
        self.balance_usdt = initial_balance
        self.trades: list[PaperTrade] = []
        self.trade_count = 0
        self.total_fees_paid = 0.0
        self.total_profit = 0.0
        self.consecutive_losses = 0
        self.balance_history: list[dict[str, Any]] = []
        self._record_balance("initial")

    @property
    def net_profit(self) -> float:
        return self.balance_usdt - self.initial_balance

    @property
    def net_profit_pct(self) -> float:
        if self.initial_balance <= 0:
            return 0.0
        return (self.net_profit / self.initial_balance) * 100

    @property
    def success_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.profit_usdt > 0)
        return (wins / len(self.trades)) * 100

    def execute_cycle(
        self,
        cycle: dict[str, Any],
        tickers: dict[str, BidAsk],
    ) -> PaperTrade | None:
        """
        Simulate executing a triangular cycle.

        Uses real bid/ask prices from tickers to calculate actual outcome.
        Each leg uses the appropriate bid/ask based on side (buy=ask, sell=bid).
        """
        legs = cycle.get("legs", [])
        if len(legs) < 3:
            return None

        start_time = time.time()

        # Simulate each leg
        current_amount = self.balance_usdt
        orders: list[PaperOrder] = []
        pairs_used: list[str] = []
        sides_used: list[str] = []

        for leg in legs:
            pair = leg["pair"]
            side = leg["side"]

            if pair not in tickers:
                logger.warning(f"Ticker not found for {pair}, skipping trade")
                return None

            ticker = tickers[pair]

            if side == "buy":
                # Buying base with quote: pay ask price, get base
                price = ticker.ask
                quantity = current_amount / price
                fee = current_amount * self.fee_rate
                current_amount = quantity - (fee / price) if price > 0 else 0
            else:
                # Selling base for quote: receive bid price
                price = ticker.bid
                revenue = current_amount * price
                fee = revenue * self.fee_rate
                current_amount = revenue - fee

            # Apply slippage
            current_amount *= 1 - self.slippage_pct

            orders.append(
                PaperOrder(
                    pair=pair,
                    side=side.upper(),
                    quantity=current_amount,
                    price=price,
                    fee=fee,
                    timestamp=time.time(),
                )
            )
            pairs_used.append(pair)
            sides_used.append(side.upper())
            self.total_fees_paid += fee

        # Calculate results
        final_amount = current_amount
        profit = final_amount - self.balance_usdt
        profit_pct = (profit / self.balance_usdt) * 100 if self.balance_usdt > 0 else 0
        total_fees = sum(o.fee for o in orders)
        latency_ms = (time.time() - start_time) * 1000

        # Update state
        self.trade_count += 1
        if profit > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        self.balance_usdt = final_amount
        self.total_profit += profit

        trade = PaperTrade(
            id=self.trade_count,
            currencies=cycle["currencies"],
            pairs=pairs_used,
            sides=sides_used,
            initial_amount=self.balance_usdt - profit,  # amount before trade
            final_amount=final_amount,
            profit_usdt=profit,
            profit_pct=profit_pct,
            total_fees=total_fees,
            orders=orders,
            executed_at=datetime.now(),
            latency_ms=round(latency_ms, 2),
        )

        self.trades.append(trade)
        self._record_balance(f"trade #{self.trade_count}")

        status = "PROFIT" if profit > 0 else "LOSS"
        logger.info(
            f"Paper trade #{self.trade_count}: {status} "
            f"${profit:.6f} ({profit_pct:.4f}%) | "
            f"Balance: ${self.balance_usdt:.6f}"
        )

        return trade

    def _record_balance(self, event: str) -> None:
        """Record balance snapshot."""
        self.balance_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "balance": round(self.balance_usdt, 6),
                "event": event,
                "profit_pct": round(self.net_profit_pct, 4),
            }
        )

    def get_stats(self) -> dict[str, Any]:
        """Get paper trading statistics."""
        return {
            "initial_balance": self.initial_balance,
            "current_balance": round(self.balance_usdt, 6),
            "net_profit": round(self.net_profit, 6),
            "net_profit_pct": round(self.net_profit_pct, 4),
            "total_trades": len(self.trades),
            "total_fees_paid": round(self.total_fees_paid, 6),
            "success_rate": round(self.success_rate, 2),
            "consecutive_losses": self.consecutive_losses,
            "avg_profit_per_trade": round(self.total_profit / len(self.trades), 6)
            if self.trades
            else 0,
            "best_trade": round(max((t.profit_usdt for t in self.trades), default=0), 6),
            "worst_trade": round(min((t.profit_usdt for t in self.trades), default=0), 6),
            "avg_latency_ms": round(sum(t.latency_ms for t in self.trades) / len(self.trades), 2)
            if self.trades
            else 0,
        }

    def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Get recent paper trades."""
        recent = self.trades[-limit:]
        return [
            {
                "id": t.id,
                "currencies": t.currencies,
                "pairs": t.pairs,
                "sides": t.sides,
                "initial_amount": round(t.initial_amount, 6),
                "final_amount": round(t.final_amount, 6),
                "profit_usdt": round(t.profit_usdt, 6),
                "profit_pct": round(t.profit_pct, 4),
                "total_fees": round(t.total_fees, 6),
                "latency_ms": t.latency_ms,
                "executed_at": t.executed_at.isoformat(),
            }
            for t in reversed(recent)
        ]
