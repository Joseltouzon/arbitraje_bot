from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

from app.config import settings
from app.exchanges.binance import BinanceAdapter
from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Step sizes per symbol (Binance LOT_SIZE filters)
STEP_SIZES: dict[str, Decimal] = {
    "BTCUSDT": Decimal("0.00001"),
    "ETHUSDT": Decimal("0.0001"),
    "BNBUSDT": Decimal("0.01"),
    "SOLUSDT": Decimal("0.01"),
}

FUTURES_STEP_SIZES: dict[str, Decimal] = {
    "BTCUSDT": Decimal("0.001"),
    "ETHUSDT": Decimal("0.001"),
    "BNBUSDT": Decimal("0.01"),
    "SOLUSDT": Decimal("0.01"),
}

DEFAULT_STEP = Decimal("0.00001")
DEFAULT_FUTURES_STEP = Decimal("0.001")

# Exit threshold: close position when funding rate drops below this (per 8h)
EXIT_FUNDING_RATE = 0.002  # 0.002% per 8h


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    """Round DOWN to nearest step size."""
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


@dataclass
class FundingPosition:
    symbol: str
    direction: str  # "funding_positive" or "funding_negative"
    spot_quantity: Decimal
    spot_price: float
    futures_quantity: Decimal
    futures_price: float
    entry_funding_rate: float
    funding_collected: float = 0.0  # cumulative funding collected in USDT
    settlements_count: int = 0
    initial_spot_usdt: float = 0.0
    initial_futures_usdt: float = 0.0
    opened_at: datetime = field(default_factory=datetime.now)


class SpotFuturesExecutor:
    """
    Funding rate carry executor.

    Strategy:
    - funding_positive: buy spot + short futures → collect funding from longs every 8h
    - funding_negative: sell spot + long futures → collect funding from shorts every 8h
    - Exit when funding rate drops below threshold or flips sign
    """

    def __init__(self, spot: BinanceAdapter, futures: BinanceFuturesAdapter) -> None:
        self.spot = spot
        self.futures = futures
        self._enabled = False
        self._confirmed = False
        self._position: FundingPosition | None = None
        self._trades: list[dict[str, Any]] = []
        self._trade_count = 0
        self._last_funding_check: datetime | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled and self._confirmed

    @property
    def has_position(self) -> bool:
        return self._position is not None

    def enable(self) -> dict[str, str]:
        if not settings.auto_trade:
            return {"status": "error", "message": "AUTO_TRADE=true required"}
        self._enabled = True
        return {"status": "enabled"}

    def confirm(self) -> dict[str, str]:
        if not self._enabled:
            return {"status": "error", "message": "Enable first"}
        self._confirmed = True
        return {"status": "confirmed"}

    def disable(self) -> dict[str, str]:
        self._enabled = False
        self._confirmed = False
        self._position = None
        return {"status": "disabled"}

    def _get_spot_step(self, symbol: str) -> Decimal:
        return STEP_SIZES.get(symbol, DEFAULT_STEP)

    def _get_futures_step(self, symbol: str) -> Decimal:
        return FUTURES_STEP_SIZES.get(symbol, DEFAULT_FUTURES_STEP)

    async def execute(self, opportunity: dict[str, Any]) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        if self.has_position:
            return None

        symbol = opportunity["symbol"]
        direction = opportunity["direction"]
        funding_rate = opportunity["funding_rate"]
        abs_rate = abs(funding_rate)

        if abs_rate < 0.003:
            logger.info(f"SKIP {symbol}: funding_rate={funding_rate:.6f} too low")
            return None

        try:
            spot_usdt = await self.spot.get_balance("USDT")
            futures_usdt = await self.futures.get_futures_usdt_balance()
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return None

        if spot_usdt < Decimal("10"):
            logger.warning(f"SKIP {symbol}: spot too low {spot_usdt}")
            return None

        if futures_usdt < Decimal("5"):
            logger.warning(f"SKIP {symbol}: futures too low {futures_usdt}")
            return None

        start_time = time.time()
        spot_step = self._get_spot_step(symbol)
        futures_step = self._get_futures_step(symbol)

        logger.info(
            f"Executing funding carry: {symbol} {direction} "
            f"rate={funding_rate:.6f} spot=${spot_usdt:.2f} fut=${futures_usdt:.2f}"
        )

        try:
            if direction == "funding_positive":
                # Buy spot, short futures → collect funding from longs
                spot_qty = await self._buy_spot(symbol, spot_usdt, spot_step)
                if spot_qty <= Decimal("0"):
                    logger.error(f"Spot buy returned 0 for {symbol}")
                    return None

                futures_qty = await self._sell_futures(symbol, spot_qty, futures_step)
                if futures_qty <= Decimal("0"):
                    logger.error("Futures sell failed, rolling back spot")
                    await self._sell_spot(symbol, spot_qty, spot_step)
                    return None
            else:
                # Sell spot, long futures → collect funding from shorts
                spot_qty = await self._sell_spot_for_usdt(symbol, spot_usdt, spot_step)
                if spot_qty <= Decimal("0"):
                    logger.error(f"Spot sell returned 0 for {symbol}")
                    return None

                futures_usdt_avail = await self.futures.get_futures_usdt_balance()
                futures_qty = await self._buy_futures(symbol, futures_usdt_avail, futures_step)
                if futures_qty <= Decimal("0"):
                    logger.error("Futures buy failed, rolling back spot")
                    await self._buy_spot_rollback(symbol, spot_qty, spot_step)
                    return None

            spot_price = float(opportunity.get("spot_price", 0))

            self._position = FundingPosition(
                symbol=symbol,
                direction=direction,
                spot_quantity=spot_qty,
                spot_price=spot_price,
                futures_quantity=futures_qty,
                futures_price=float(opportunity.get("spot_price", 0)),
                entry_funding_rate=funding_rate,
                initial_spot_usdt=float(spot_usdt),
                initial_futures_usdt=float(futures_usdt),
            )

            self._trade_count += 1
            duration = (time.time() - start_time) * 1000

            result = {
                "trade_id": self._trade_count,
                "symbol": symbol,
                "direction": direction,
                "entry_funding_rate": funding_rate,
                "spot_quantity": float(spot_qty),
                "futures_quantity": float(futures_qty),
                "status": "opened",
                "strategy": "funding_rate_carry",
                "duration_ms": round(duration, 2),
            }

            logger.info(f"Funding position opened: {symbol} {direction} rate={funding_rate:.6f}")

            with contextlib.suppress(Exception):
                await self._log_trade({**result, "pnl_usdt": 0, "pnl_pct": 0})

            return result

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return None

    async def close_position(self, spot_tickers: dict[str, BidAsk]) -> dict[str, Any] | None:
        if not self._position:
            return None

        pos = self._position
        spot_step = self._get_spot_step(pos.symbol)
        futures_step = self._get_futures_step(pos.symbol)

        logger.info(f"Closing funding position: {pos.symbol} {pos.direction}")

        try:
            if pos.direction == "funding_positive":
                # Opened: buy spot + short futures
                # Close: sell spot + cover futures (buy)
                await self.spot.create_market_order(
                    symbol=pos.symbol,
                    side="SELL",
                    quantity=_round_down(pos.spot_quantity, spot_step),
                )
                await self.futures.create_futures_market_order(
                    symbol=pos.symbol,
                    side="BUY",
                    quantity=_round_down(pos.futures_quantity, futures_step),
                )
            else:
                # Opened: sell spot + long futures
                # Close: buy spot + cover futures (sell)
                await self.spot.create_market_order(
                    symbol=pos.symbol,
                    side="BUY",
                    quantity=_round_down(pos.spot_quantity, spot_step),
                )
                await self.futures.create_futures_market_order(
                    symbol=pos.symbol,
                    side="SELL",
                    quantity=_round_down(pos.futures_quantity, futures_step),
                )

            # Transfer profit from futures to spot
            futures_bal = await self.futures.get_futures_usdt_balance()
            if futures_bal > Decimal("1"):
                try:
                    await self.futures.transfer_futures_to_spot(
                        "USDT", futures_bal * Decimal("0.99")
                    )
                except Exception as e:
                    logger.warning(f"Transfer failed (need permission): {e}")

            # Calculate P&L
            final_spot = float(await self.spot.get_balance("USDT"))
            final_futures = float(await self.futures.get_futures_usdt_balance())
            initial_total = pos.initial_spot_usdt + pos.initial_futures_usdt
            final_total = final_spot + final_futures
            pnl_usdt = final_total - initial_total
            pnl_pct = (pnl_usdt / initial_total * 100) if initial_total > 0 else 0

            # Calculate holding time
            held_seconds = (datetime.now() - pos.opened_at).total_seconds()
            held_hours = held_seconds / 3600

            result = {
                "trade_id": self._trade_count,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "strategy": "funding_rate_carry",
                "status": "closed",
                "pnl_usdt": round(pnl_usdt, 4),
                "pnl_pct": round(pnl_pct, 4),
                "initial_balance": round(initial_total, 2),
                "final_balance": round(final_total, 2),
                "entry_funding_rate": pos.entry_funding_rate,
                "settlements_count": pos.settlements_count,
                "funding_collected": round(pos.funding_collected, 4),
                "held_hours": round(held_hours, 1),
            }

            self._trades.append(result)
            self._position = None

            with contextlib.suppress(Exception):
                await self.spot.cleanup_dust()

            with contextlib.suppress(Exception):
                await self._log_trade(result)

            logger.info(
                f"Funding position closed: P&L={pnl_usdt:.4f} "
                f"({pos.settlements_count} settlements, {held_hours:.1f}h)"
            )
            return result

        except Exception as e:
            logger.error(f"Close failed: {e}")
            return None

    async def should_close(self, spot_tickers: dict[str, BidAsk]) -> bool:
        """
        Close when funding rate drops below exit threshold or flips sign.
        Don't close before at least one funding settlement (8h).
        """
        if not self._position:
            return False

        pos = self._position

        # Don't close before first settlement (8h)
        held_hours = (datetime.now() - pos.opened_at).total_seconds() / 3600
        if held_hours < 1.0:
            return False

        # Check current funding rate
        try:
            fr_data = await self.futures.get_funding_rate(pos.symbol)
            current_rate = fr_data.get("funding_rate", 0)
        except Exception:
            return False

        # Update funding tracking (estimate: rate * position value per 8h)
        # This is an approximation; real funding is settled by Binance
        self._update_funding_tracking(current_rate)

        # Close if rate dropped below exit threshold
        abs_rate = abs(current_rate)
        if abs_rate < EXIT_FUNDING_RATE:
            logger.info(
                f"Should close {pos.symbol}: funding rate {current_rate:.6f} "
                f"< exit threshold {EXIT_FUNDING_RATE}"
            )
            return True

        # Close if rate flipped sign (we're on the wrong side)
        if pos.direction == "funding_positive" and current_rate < 0:
            logger.info(f"Should close {pos.symbol}: funding flipped negative")
            return True

        if pos.direction == "funding_negative" and current_rate > 0:
            logger.info(f"Should close {pos.symbol}: funding flipped positive")
            return True

        return False

    def _update_funding_tracking(self, current_rate: float) -> None:
        """Update estimated funding collected."""
        if not self._position:
            return

        now = datetime.now()
        if self._last_funding_check is None:
            self._last_funding_check = self._position.opened_at
            return

        elapsed = (now - self._last_funding_check).total_seconds()
        # Funding settles every 8h = 28800s
        settlements = int(elapsed / 28800)

        if settlements > 0:
            self._position.settlements_count += settlements
            # Estimate funding collected: rate * notional value * settlements
            notional = self._position.spot_price * float(self._position.spot_quantity)
            funding_per_settlement = notional * abs(current_rate)
            self._position.funding_collected += funding_per_settlement * settlements
            self._last_funding_check = now

            logger.info(
                f"Funding settlement: {self._position.symbol} "
                f"#{self._position.settlements_count} "
                f"collected=${funding_per_settlement:.4f} "
                f"total=${self._position.funding_collected:.4f}"
            )

    async def _buy_spot(self, symbol: str, balance_usdt: Decimal, step: Decimal) -> Decimal:
        ticker = await self.spot.get_ticker(symbol)
        spend = balance_usdt * Decimal("0.90")
        qty = _round_down(spend / Decimal(str(ticker.ask)), step)
        if qty <= 0:
            return Decimal("0")
        result = await self.spot.create_market_order(symbol, "BUY", qty)
        actual = Decimal(str(result.quantity))
        logger.info(f"Spot BUY: {actual} {symbol}")
        return actual

    async def _sell_spot(self, symbol: str, quantity: Decimal, step: Decimal) -> None:
        qty = _round_down(quantity, step)
        if qty <= 0:
            return
        await self.spot.create_market_order(symbol, "SELL", qty)
        logger.info(f"Spot SELL: {qty} {symbol}")

    async def _sell_spot_for_usdt(
        self, symbol: str, balance_usdt: Decimal, step: Decimal
    ) -> Decimal:
        from app.core.graph import QUOTE_CURRENCIES

        base = ""
        for quote in sorted(QUOTE_CURRENCIES, key=len, reverse=True):
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[: -len(quote)]
                break

        if not base:
            return Decimal("0")

        base_balance = await self.spot.get_balance(base)
        qty = _round_down(base_balance * Decimal("0.99"), step)
        if qty <= 0:
            logger.warning(f"No {base} balance for negative funding strategy")
            return Decimal("0")

        result = await self.spot.create_market_order(symbol, "SELL", qty)
        actual = Decimal(str(result.quantity))
        logger.info(f"Spot SELL (negative funding): {actual} {symbol}")
        return actual

    async def _buy_spot_rollback(self, symbol: str, target_qty: Decimal, step: Decimal) -> None:
        qty = _round_down(target_qty, step)
        if qty <= 0:
            return
        await self.spot.create_market_order(symbol, "BUY", qty)

    async def _sell_futures(self, symbol: str, spot_qty: Decimal, step: Decimal) -> Decimal:
        qty = _round_down(spot_qty, step)
        if qty <= 0:
            return Decimal("0")
        await self.futures.create_futures_market_order(symbol, "SELL", qty)
        logger.info(f"Futures SELL: {qty} {symbol}")
        return qty

    async def _buy_futures(self, symbol: str, amount_usdt: Decimal, step: Decimal) -> Decimal:
        price = await self.futures.get_futures_price(symbol)
        if price <= 0:
            return Decimal("0")
        spend = amount_usdt * Decimal("0.90")
        qty = _round_down(spend / Decimal(str(price)), step)
        if qty <= 0:
            return Decimal("0")
        await self.futures.create_futures_market_order(symbol, "BUY", qty)
        logger.info(f"Futures BUY: {qty} {symbol}")
        return qty

    async def _log_trade(self, trade: dict[str, Any]) -> None:
        from app.db.models import TradeHistory
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            record = TradeHistory(
                mode="funding_rate_carry",
                currencies=trade.get("symbol", ""),
                pairs=trade.get("symbol", ""),
                sides=trade.get("direction", ""),
                initial_amount=trade.get("initial_balance", 0),
                final_amount=trade.get("final_balance", 0),
                profit_usdt=trade.get("pnl_usdt", 0),
                profit_pct=trade.get("pnl_pct", 0),
                total_fees=0,
                status=trade.get("status", "unknown"),
            )
            session.add(record)
            await session.commit()

    def get_stats(self) -> dict[str, Any]:
        pos_stats = None
        if self._position:
            held_hours = (datetime.now() - self._position.opened_at).total_seconds() / 3600
            pos_stats = {
                "symbol": self._position.symbol,
                "direction": self._position.direction,
                "entry_funding_rate": self._position.entry_funding_rate,
                "settlements_count": self._position.settlements_count,
                "funding_collected": round(self._position.funding_collected, 4),
                "held_hours": round(held_hours, 1),
                "opened_at": self._position.opened_at.isoformat(),
            }

        return {
            "enabled": self._enabled,
            "confirmed": self._confirmed,
            "has_position": self.has_position,
            "position": pos_stats,
            "total_trades": len(self._trades),
            "trades": self._trades[-10:],
            "strategy": "funding_rate_carry",
        }
