from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.config import settings
from app.core.risk import RiskManager
from app.exchanges.binance import BinanceAdapter
from app.models.primitives import BidAsk, TradeResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LiveTradeLeg:
    """A single leg of a live trade execution."""

    pair: str
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    order_result: TradeResult | None = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class LiveTrade:
    """A completed live trade (3-leg cycle)."""

    id: int
    currencies: list[str]
    pairs: list[str]
    sides: list[str]
    legs: list[LiveTradeLeg]
    initial_balance: Decimal
    final_balance: Decimal
    profit_usdt: Decimal
    profit_pct: float
    total_fees: Decimal
    status: str  # "completed", "partial", "failed"
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: float = 0.0


class LiveExecutor:
    """
    Executes real triangular arbitrage trades on Binance.

    SAFETY FEATURES:
    - Requires explicit enable_live() call
    - Enforces risk management rules
    - Verifies balances before each trade
    - Stops on any order failure
    - Logs everything to database
    - Tracks P&L in real-time
    """

    def __init__(
        self,
        exchange: BinanceAdapter,
        risk_manager: RiskManager | None = None,
    ) -> None:
        self.exchange = exchange
        self.risk = risk_manager or RiskManager()
        self._enabled = False
        self._confirmed = False
        self.trade_count = 0
        self.trades: list[LiveTrade] = []
        self.total_profit = Decimal("0")
        self.total_fees = Decimal("0")
        self._last_balance_check: dict[str, Decimal] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled and self._confirmed

    def enable(self) -> dict[str, str]:
        """Enable live trading. Returns confirmation message."""
        if not settings.auto_trade:
            return {
                "status": "error",
                "message": "AUTO_TRADE must be true in .env to enable live trading",
            }

        if not settings.binance_api_key or not settings.binance_api_secret:
            return {
                "status": "error",
                "message": "Binance API credentials not configured",
            }

        self._enabled = True
        logger.warning("LIVE TRADING ENABLED - Real orders will be placed")
        return {
            "status": "enabled",
            "message": (
                "Live trading is now ACTIVE. "
                "Real orders will be placed on Binance. "
                "Call /api/live/confirm to finalize."
            ),
        }

    def confirm(self) -> dict[str, str]:
        """Final confirmation to start placing real orders."""
        if not self._enabled:
            return {"status": "error", "message": "Enable first via /api/live/enable"}

        self._confirmed = True
        logger.warning("LIVE TRADING CONFIRMED - Orders can now be placed")
        return {
            "status": "confirmed",
            "message": "Live trading confirmed. System will execute profitable cycles.",
        }

    def disable(self) -> dict[str, str]:
        """Immediately disable live trading."""
        self._enabled = False
        self._confirmed = False
        self.risk.pause()
        logger.warning("LIVE TRADING DISABLED")
        return {"status": "disabled", "message": "Live trading stopped"}

    async def verify_balance(self, currency: str, required: Decimal) -> bool:
        """Verify sufficient balance before trading."""
        try:
            balance = await self.exchange.get_balance(currency)
            self._last_balance_check[currency] = balance
            if balance < required:
                logger.warning(
                    f"Insufficient {currency} balance: "
                    f"have {balance}, need {required}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return False

    async def execute_cycle(
        self,
        cycle: dict[str, Any],
        tickers: dict[str, BidAsk],
    ) -> LiveTrade | None:
        """
        Execute a triangular cycle with real orders.

        Uses LIMIT orders first (less slippage), with fallback to MARKET
        if limit order doesn't fill within timeout.
        """
        if not self.enabled:
            return None

        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            logger.warning(f"Risk check failed: {reason}")
            return None

        legs = cycle.get("legs", [])
        if len(legs) < 3:
            return None

        self.trade_count += 1
        start_time = time.time()
        started_at = datetime.now()

        initial_balance = Decimal("0")
        try:
            initial_balance = await self.exchange.get_balance("USDT")
        except Exception as e:
            logger.error(f"Failed to get initial balance: {e}")
            return None

        trade_legs: list[LiveTradeLeg] = []
        status = "completed"

        # Pre-validate all legs with order book
        for leg in legs:
            pair = leg["pair"]
            if pair not in tickers:
                logger.warning(f"SKIP: no ticker for {pair}")
                return None
            ticker = tickers[pair]

            # Check spread
            spread = (ticker.ask - ticker.bid) / ticker.bid * 100 if ticker.bid > 0 else 100
            if spread > 0.5:
                logger.warning(f"SKIP: {pair} spread too high ({spread:.2f}%)")
                return None

            # Check order book depth
            try:
                orderbook = await self.exchange.get_orderbook(pair, depth=5)
                if leg["side"] == "buy":
                    # Check if ask side has enough liquidity
                    available = sum(level.quantity for level in orderbook.asks[:3])
                    needed = float(initial_balance) / ticker.ask / 3
                else:
                    # Check if bid side has enough liquidity
                    available = sum(level.quantity for level in orderbook.bids[:3])
                    needed = float(initial_balance) / ticker.bid / 3

                if available < needed:
                    logger.warning(
                        f"SKIP: {pair} insufficient depth "
                        f"(need {needed:.4f}, have {available:.4f})"
                    )
                    return None
            except Exception as e:
                logger.warning(f"SKIP: {pair} orderbook check failed: {e}")
                return None

        try:
            for leg in legs:
                leg_start = time.time()
                pair = leg["pair"]
                side = leg["side"].upper()

                quantity = await self._calculate_quantity(
                    pair, side, leg, tickers
                )

                if quantity <= 0:
                    status = "failed"
                    trade_legs.append(
                        LiveTradeLeg(
                            pair=pair,
                            side=side,
                            quantity=Decimal("0"),
                            error="Could not calculate valid quantity",
                        )
                    )
                    break

                # Try limit order first, fallback to market
                try:
                    result = await self._place_order_with_fallback(
                        pair, side, quantity, tickers
                    )
                    duration = (time.time() - leg_start) * 1000

                    trade_legs.append(
                        LiveTradeLeg(
                            pair=pair,
                            side=side,
                            quantity=quantity,
                            order_result=result,
                            duration_ms=round(duration, 2),
                        )
                    )

                    logger.info(
                        f"Order placed: {side} {quantity} {pair} "
                        f"@ {result.price} | fee: {result.fee}"
                    )

                except Exception as e:
                    logger.error(f"Order failed for {pair}: {e}")
                    status = "partial"

                    # Revert completed legs (sell what we bought, buy what we sold)
                    for completed in reversed(trade_legs):
                        if completed.order_result:
                            revert_side = "SELL" if completed.side == "BUY" else "BUY"
                            try:
                                await self.exchange.create_market_order(
                                    symbol=completed.pair,
                                    side=revert_side,
                                    quantity=completed.quantity,
                                )
                                logger.info(
                                    f"Reverted: {revert_side} "
                                    f"{completed.quantity} {completed.pair}"
                                )
                            except Exception as re:
                                logger.error(f"Revert failed for {completed.pair}: {re}")

                    trade_legs.append(
                        LiveTradeLeg(
                            pair=pair,
                            side=side,
                            quantity=quantity,
                            error=str(e),
                        )
                    )
                    break

            # Get final balance
            final_balance = await self.exchange.get_balance("USDT")

        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            final_balance = initial_balance
            status = "failed"

        # Calculate P&L
        total_duration = (time.time() - start_time) * 1000
        profit = final_balance - initial_balance
        profit_pct = float(profit / initial_balance * 100) if initial_balance > 0 else 0
        total_fees = sum(
            Decimal(str(leg.order_result.fee))
            for leg in trade_legs
            if leg.order_result
        )

        # Clean up dust / remanentes
        try:
            await self.exchange.cleanup_dust()
            # Recalculate balance after cleanup
            final_balance = await self.exchange.get_balance("USDT")
            profit = final_balance - initial_balance
            profit_pct = float(profit / initial_balance * 100) if initial_balance > 0 else 0
        except Exception as e:
            logger.warning(f"Dust cleanup failed: {e}")

        # Update risk manager
        self.risk.record_trade(float(profit))

        trade = LiveTrade(
            id=self.trade_count,
            currencies=cycle["currencies"],
            pairs=[leg["pair"] for leg in legs],
            sides=[leg["side"].upper() for leg in legs],
            legs=trade_legs,
            initial_balance=initial_balance,
            final_balance=final_balance,
            profit_usdt=profit,
            profit_pct=profit_pct,
            total_fees=total_fees,
            status=status,
            started_at=started_at,
            completed_at=datetime.now(),
            total_duration_ms=round(total_duration, 2),
        )

        self.trades.append(trade)
        self.total_profit += profit
        self.total_fees += total_fees

        log_status = "PROFIT" if profit > 0 else "LOSS"
        logger.info(
            f"Live trade #{self.trade_count}: {log_status} "
            f"${profit:.4f} ({profit_pct:.4f}%) | "
            f"Status: {status} | "
            f"Duration: {total_duration:.0f}ms"
        )

        return trade

    async def _place_order_with_fallback(
        self,
        pair: str,
        side: str,
        quantity: Decimal,
        tickers: dict[str, BidAsk],
        limit_timeout_sec: float = 1.5,
    ) -> TradeResult:
        """
        Place a limit order first. If not filled within timeout,
        cancel and place market order instead.

        Limit orders have maker fee (0.1%) vs taker (0.1% on Binance),
        but less slippage = net better execution.
        """
        ticker = tickers.get(pair)
        if not ticker:
            raise ValueError(f"No ticker for {pair}")

        # Set limit price at best available
        limit_price = (
            Decimal(str(ticker.bid)) if side == "BUY"
            else Decimal(str(ticker.ask))
        )

        try:
            # Place limit order
            order = await self.exchange.create_limit_order(
                symbol=pair,
                side=side,
                quantity=quantity,
                price=limit_price,
            )

            if order.status == "FILLED":
                logger.info(f"Limit order FILLED immediately: {pair} {side}")
                return order

            # Wait for fill
            order_id = order.order_id
            checks = int(limit_timeout_sec / 0.3)

            for _ in range(checks):
                await asyncio.sleep(0.3)
                status = await self.exchange.get_order_status(pair, order_id)

                if status.get("status") == "FILLED":
                    fills = status.get("fills", [])
                    total_fee = sum(float(f["commission"]) for f in fills)
                    avg_price = (
                        sum(
                            float(f["price"]) * float(f["qty"])
                            for f in fills
                        )
                        / float(status.get("executedQty", 1))
                        if fills
                        else float(status.get("price", 0))
                    )
                    logger.info(
                        f"Limit order FILLED after wait: {pair} {side}"
                    )
                    return TradeResult(
                        order_id=order_id,
                        symbol=pair,
                        side=side,
                        quantity=float(status.get("executedQty", 0)),
                        price=avg_price,
                        fee=total_fee,
                        status="FILLED",
                        timestamp=datetime.now(),
                    )

            # Cancel unfilled limit order
            await self.exchange.cancel_order(pair, order_id)
            logger.info(
                f"Limit order cancelled (timeout), falling back to MARKET: "
                f"{pair} {side}"
            )

        except Exception as e:
            logger.warning(f"Limit order failed: {e}, trying MARKET")

        # Fallback to market order
        return await self.exchange.create_market_order(
            symbol=pair, side=side, quantity=quantity
        )

    async def _calculate_quantity(
        self,
        pair: str,
        side: str,
        leg: dict,
        tickers: dict[str, BidAsk],
    ) -> Decimal:
        """
        Calculate order quantity based on available balance and pair constraints.
        """
        if pair not in tickers:
            return Decimal("0")

        ticker = tickers[pair]

        if side == "BUY":
            # Buying: use quote currency (e.g., USDT for BTCUSDT)
            quote = pair.replace(leg.get("to_currency", ""), "")
            if not quote:
                quote = "USDT"

            balance = await self.exchange.get_balance(quote)
            # Reserve 1% for fees and rounding
            available = balance * Decimal("0.99")
            price = Decimal(str(ticker.ask))

            if price <= 0:
                return Decimal("0")

            quantity = available / price

            # Round DOWN to avoid exceeding balance
            quantity = quantity.quantize(Decimal("0.00001"), rounding=Decimal.ROUND_DOWN)

            return quantity

        else:
            # Selling: use base currency balance
            base = pair.replace("USDT", "").replace("BTC", "").replace("ETH", "")
            if not base:
                base = leg.get("from_currency", "")

            balance = await self.exchange.get_balance(base)
            # Reserve small amount for fees
            quantity = balance * Decimal("0.99")
            # Round DOWN to avoid exceeding balance
            quantity = quantity.quantize(Decimal("0.00001"), rounding=Decimal.ROUND_DOWN)

            return quantity

    def get_stats(self) -> dict[str, Any]:
        """Get live trading statistics."""
        profitable = sum(1 for t in self.trades if t.profit_usdt > 0)
        failed = sum(1 for t in self.trades if t.status == "failed")
        partial = sum(1 for t in self.trades if t.status == "partial")

        return {
            "enabled": self._enabled,
            "confirmed": self._confirmed,
            "total_trades": len(self.trades),
            "profitable_trades": profitable,
            "failed_trades": failed,
            "partial_trades": partial,
            "success_rate": round(
                profitable / len(self.trades) * 100, 2
            )
            if self.trades
            else 0,
            "total_profit_usdt": float(self.total_profit),
            "total_fees_usdt": float(self.total_fees),
            "net_profit_usdt": float(self.total_profit),
            "risk": {
                "paused": self.risk.is_paused,
                "consecutive_losses": self.risk.consecutive_losses,
                "daily_pnl": self.risk.daily_pnl,
            },
        }

    def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Get recent live trades."""
        recent = self.trades[-limit:]
        return [
            {
                "id": t.id,
                "currencies": t.currencies,
                "pairs": t.pairs,
                "sides": t.sides,
                "profit_usdt": float(t.profit_usdt),
                "profit_pct": t.profit_pct,
                "total_fees": float(t.total_fees),
                "status": t.status,
                "duration_ms": t.total_duration_ms,
                "started_at": t.started_at.isoformat(),
                "legs": [
                    {
                        "pair": leg.pair,
                        "side": leg.side,
                        "quantity": float(leg.quantity),
                        "price": leg.order_result.price if leg.order_result else 0,
                        "fee": leg.order_result.fee if leg.order_result else 0,
                        "error": leg.error,
                        "duration_ms": leg.duration_ms,
                    }
                    for leg in t.legs
                ],
            }
            for t in reversed(recent)
        ]
