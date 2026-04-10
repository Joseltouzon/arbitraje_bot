from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

from app.config import MAX_TRADES_IN_MEMORY, settings
from app.core.risk import RiskManager
from app.exchanges.binance import BinanceAdapter
from app.models.primitives import BidAsk, TradeResult
from app.services.alerts import alerts_service
from app.services.telegram import get_telegram
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
        self.trades: deque[LiveTrade] = deque(maxlen=MAX_TRADES_IN_MEMORY)  # Circular buffer
        self.total_profit = Decimal("0")
        self.total_fees = Decimal("0")
        self._last_balance_check: dict[str, Decimal] = {}

        # Circuit breaker
        self._consecutive_errors = 0
        self._circuit_broken = False
        self._circuit_breaker_threshold = 5
        self._circuit_reset_timeout = 60  # seconds
        self._circuit_reset_task: asyncio.Task | None = None  # Track reset task

        # Retry settings
        self._max_retries = 3
        self._base_delay = 0.5  # seconds

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
                logger.warning(f"Insufficient {currency} balance: have {balance}, need {required}")
                return False
            return True
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return False

    async def _reset_circuit_breaker(self) -> None:
        """Reset circuit breaker after cooldown period."""
        await asyncio.sleep(self._circuit_reset_timeout)
        self._circuit_broken = False
        self._consecutive_errors = 0
        logger.info("Circuit breaker reset - trading resumed")

    async def _retry_with_backoff(self, func, *args, max_retries: int | None = None, **kwargs):
        """Execute function with exponential backoff retry."""
        retries = max_retries or self._max_retries
        last_error = None

        for attempt in range(retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    delay = self._base_delay * (2**attempt)
                    logger.warning(f"Retry {attempt + 1}/{retries} after {delay}s: {e}")
                    await asyncio.sleep(delay)

        raise last_error

    async def execute_cycle(
        self,
        cycle: dict[str, Any],
        tickers: dict[str, BidAsk],
    ) -> LiveTrade | None:
        """
        Execute a triangular cycle with real orders.

        Uses LIMIT orders first (less slippage), with fallback to MARKET
        if limit order doesn't fill within timeout.
        Includes circuit breaker and retry logic.
        """
        if not self.enabled:
            return None

        # Circuit breaker check
        if self._circuit_broken:
            logger.warning("Circuit breaker tripped - skipping execution")
            alerts_service.warning(
                "Circuit breaker active - trades paused", reason="circuit_breaker"
            )
            return None

        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            logger.warning(f"Risk check failed: {reason}")
            alerts_service.warning(f"Risk blocked trade: {reason}", reason="risk_check")
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

        # Pre-validate: check spread only (balance is tracked via expected_amounts)
        for leg in legs:
            pair = leg["pair"]
            if pair not in tickers:
                logger.warning(f"SKIP: no ticker for {pair}")
                alerts_service.warning(f"No ticker for {pair}", pair=pair)
                return None
            ticker = tickers[pair]

            # Check spread
            spread = (ticker.ask - ticker.bid) / ticker.bid * 100 if ticker.bid > 0 else 100
            if spread > 0.5:
                logger.warning(f"SKIP: {pair} spread too high ({spread:.2f}%)")
                alerts_service.warning(f"Spread too high for {pair}", pair=pair, spread=spread)
                await get_telegram().notify_warning(
                    f"Spread too high: {pair} ({spread:.2f}%)", {"spread": spread}
                )
                return None

        try:
            # Track expected balances during execution
            # Start with initial USDT balance
            expected_balances: dict[str, Decimal] = {"USDT": initial_balance}

            for leg in legs:
                leg_start = time.time()
                pair = leg["pair"]
                side = leg["side"].upper()
                from_currency = leg.get("from_currency", "")
                to_currency = leg.get("to_currency", "")

                # Get expected balance for the currency we're spending
                # For BUY: spend from_currency to get to_currency
                # For SELL: spend from_currency to get to_currency
                spend_currency = from_currency
                spend_balance = expected_balances.get(spend_currency, Decimal("0"))

                if spend_balance <= 0:
                    logger.error(f"FAIL: no expected balance for {spend_currency}")
                    alerts_service.error(
                        f"No expected balance for {spend_currency}",
                        currency=spend_currency,
                        expected_balances=str(expected_balances),
                    )
                    status = "failed"
                    break

                # Verify orderbook has liquidity for SELL orders
                if side == "SELL":
                    try:
                        orderbook = await self.exchange.get_orderbook(pair, depth=10)
                        available_sell = sum(level.quantity for level in orderbook.bids[:5])
                        # For SELL, we need to sell `spend_balance` amount of base currency
                        needed_sell = float(spend_balance)
                        if available_sell < needed_sell:
                            logger.warning(
                                f"SKIP: {pair} insufficient SELL depth "
                                f"(need {needed_sell:.4f}, have {available_sell:.4f})"
                            )
                            alerts_service.warning(
                                f"Low SELL depth for {pair}",
                                pair=pair,
                                needed=needed_sell,
                                available=available_sell,
                            )
                            await get_telegram().notify_warning(
                                f"Low SELL depth: {pair}",
                                {"needed": needed_sell, "available": available_sell},
                            )
                            status = "failed"
                            break
                    except Exception as e:
                        logger.warning(f"SKIP: {pair} orderbook check failed: {e}")
                        alerts_service.warning(
                            f"Orderbook check failed for {pair}", pair=pair, error=str(e)
                        )
                        status = "failed"
                        break

                quantity = await self._calculate_quantity(pair, side, leg, tickers)

                if quantity <= 0:
                    logger.error(f"FAIL: quantity=0 for {pair} {side}")
                    alerts_service.error(
                        f"Order quantity is zero: {pair} {side}",
                        pair=pair,
                        side=side,
                        leg=leg,
                    )
                    await get_telegram().notify_warning(
                        f"Quantity zero: {pair}",
                        {"pair": pair, "side": side, "leg": str(leg)},
                    )
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
                    result = await self._place_order_with_fallback(pair, side, quantity, tickers)
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

                    # Update expected balances after successful order
                    fee_mult = Decimal("0.999")  # Account for ~0.1% fee
                    if side == "BUY":
                        # Bought `to_currency`, spent `from_currency`
                        received = Decimal(str(result.quantity)) * fee_mult
                        expected_balances[to_currency] = (
                            expected_balances.get(to_currency, Decimal("0")) + received
                        )
                        # Deduct from spent currency
                        if from_currency in expected_balances:
                            expected_balances[from_currency] = Decimal("0")
                    else:
                        # Sold `from_currency`, received `to_currency`
                        received_usd = (
                            Decimal(str(result.quantity)) * Decimal(str(result.price)) * fee_mult
                        )
                        expected_balances[to_currency] = (
                            expected_balances.get(to_currency, Decimal("0")) + received_usd
                        )
                        # Deduct from spent currency
                        if from_currency in expected_balances:
                            expected_balances[from_currency] = Decimal("0")

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
                                    f"Reverted: {revert_side} {completed.quantity} {completed.pair}"
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
            logger.error(f"Trade execution error: {e}", exc_info=True)
            alerts_service.error(f"Trade execution failed: {str(e)}", error=str(e))
            await get_telegram().notify_error(f"Trade execution error: {str(e)}")
            final_balance = initial_balance
            status = "failed"

        # Calculate P&L
        total_duration = (time.time() - start_time) * 1000
        profit = final_balance - initial_balance
        profit_pct = float(profit / initial_balance * 100) if initial_balance > 0 else 0
        total_fees = sum(
            Decimal(str(leg.order_result.fee)) for leg in trade_legs if leg.order_result
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

        # Circuit breaker logic
        if status == "completed":
            self._consecutive_errors = 0
            alerts_service.trade_success(
                f"Trade completed: {' → '.join(cycle['currencies'])}",
                currencies=cycle["currencies"],
                profit=float(profit),
                profit_pct=profit_pct,
                duration_ms=total_duration,
            )
        else:
            self._consecutive_errors += 1
            alerts_service.trade_failed(
                f"Trade {status}: {' → '.join(cycle['currencies'])}",
                currencies=cycle["currencies"],
                status=status,
                consecutive_errors=self._consecutive_errors,
            )
            await get_telegram().notify_trade_failed(
                cycle["currencies"],
                status,
                self._consecutive_errors,
            )
            if self._consecutive_errors >= self._circuit_breaker_threshold:
                self._circuit_broken = True
                logger.error(
                    f"CIRCUIT BREAKER TRIPPED after {self._consecutive_errors} consecutive errors. "
                    f"Pausing trading for {self._circuit_reset_timeout}s"
                )
                alerts_service.circuit_breaker(
                    f"Circuit breaker triggered after {self._consecutive_errors} errors",
                    consecutive_errors=self._consecutive_errors,
                    timeout=self._circuit_reset_timeout,
                )
                await get_telegram().notify_circuit_breaker(
                    f"Triggered after {self._consecutive_errors} consecutive errors",
                    self._consecutive_errors,
                    self._circuit_reset_timeout,
                )
                # Only start reset task if none is running
                if self._circuit_reset_task is None or self._circuit_reset_task.done():
                    self._circuit_reset_task = asyncio.create_task(self._reset_circuit_breaker())

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

        # Log to database
        with contextlib.suppress(Exception):
            await self._log_trade(trade, status)

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
        Uses idempotency keys to prevent duplicate orders.
        """
        ticker = tickers.get(pair)
        if not ticker:
            raise ValueError(f"No ticker for {pair}")

        client_order_id = f"arb_{uuid.uuid4().hex[:16]}"

        # Set limit price at best available
        limit_price = Decimal(str(ticker.bid)) if side == "BUY" else Decimal(str(ticker.ask))

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
                        sum(float(f["price"]) * float(f["qty"]) for f in fills)
                        / float(status.get("executedQty", 1))
                        if fills
                        else float(status.get("price", 0))
                    )
                    logger.info(f"Limit order FILLED after wait: {pair} {side}")
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
            logger.info(f"Limit order cancelled (timeout), falling back to MARKET: {pair} {side}")

        except Exception as e:
            logger.warning(f"Limit order failed: {e}, trying MARKET")

        # Fallback to market order with idempotency key
        return await self.exchange.create_market_order(
            symbol=pair, side=side, quantity=quantity, client_order_id=client_order_id
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

        # Parse base/quote from pair using leg context
        from_currency = leg.get("from_currency", "")
        to_currency = leg.get("to_currency", "")

        if side == "BUY":
            # Buying base with quote: use quote currency balance
            # e.g. BUY BTC on BTCUSDT → quote = USDT
            quote = to_currency if to_currency else self._extract_quote(pair)
            if not quote:
                quote = "USDT"

            balance = await self.exchange.get_balance(quote)
            available = balance * Decimal("0.99")
            price = Decimal(str(ticker.ask))

            if price <= 0:
                return Decimal("0")

            quantity = available / price
            quantity = quantity.quantize(Decimal("0.00001"), rounding=ROUND_DOWN)
            return quantity

        else:
            # Selling base: use base currency balance
            # e.g. SELL BTC on BTCUSDT → base = BTC
            base = from_currency if from_currency else self._extract_base(pair)
            if not base:
                return Decimal("0")

            balance = await self.exchange.get_balance(base)
            quantity = balance * Decimal("0.99")
            quantity = quantity.quantize(Decimal("0.00001"), rounding=ROUND_DOWN)
            return quantity

    @staticmethod
    def _extract_quote(pair: str) -> str:
        """Extract quote currency from pair string (e.g. BTCUSDT → USDT)."""
        from app.core.graph import QUOTE_CURRENCIES

        for quote in sorted(QUOTE_CURRENCIES, key=len, reverse=True):
            if pair.endswith(quote) and len(pair) > len(quote):
                return quote
        return ""

    @staticmethod
    def _extract_base(pair: str) -> str:
        """Extract base currency from pair string (e.g. BTCUSDT → BTC)."""
        from app.core.graph import QUOTE_CURRENCIES

        for quote in sorted(QUOTE_CURRENCIES, key=len, reverse=True):
            if pair.endswith(quote) and len(pair) > len(quote):
                return pair[: -len(quote)]
        return ""

    async def _log_trade(self, trade, status: str) -> None:
        """Log trade to database."""
        from app.db.models import TradeHistory
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            record = TradeHistory(
                mode="triangular",
                currencies=",".join(trade.currencies),
                pairs=",".join(trade.pairs),
                sides=",".join(trade.sides),
                initial_amount=float(trade.initial_balance),
                final_amount=float(trade.final_balance),
                profit_usdt=float(trade.profit_usdt),
                profit_pct=trade.profit_pct,
                total_fees=float(trade.total_fees),
                status=status,
            )
            session.add(record)
            await session.commit()

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
            "success_rate": round(profitable / len(self.trades) * 100, 2) if self.trades else 0,
            "total_profit_usdt": float(self.total_profit),
            "total_fees_usdt": float(self.total_fees),
            "net_profit_usdt": float(self.total_profit),
            "circuit_breaker": {
                "broken": self._circuit_broken,
                "consecutive_errors": self._consecutive_errors,
                "threshold": self._circuit_breaker_threshold,
            },
            "risk": {
                "paused": self.risk.is_paused,
                "consecutive_losses": self.risk.consecutive_losses,
                "daily_pnl": self.risk.daily_pnl,
            },
        }

    def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Get recent live trades."""
        recent = list(self.trades)[-limit:]
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
