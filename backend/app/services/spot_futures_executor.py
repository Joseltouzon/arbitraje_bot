from __future__ import annotations

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


@dataclass
class SpotFuturesPosition:
    symbol: str
    direction: str
    spot_quantity: Decimal
    spot_price: float
    futures_quantity: Decimal
    futures_price: float
    premium_pct: float
    initial_spot_usdt: float = 0.0
    initial_futures_usdt: float = 0.0
    opened_at: datetime = field(default_factory=datetime.now)


class SpotFuturesExecutor:
    def __init__(self, spot: BinanceAdapter, futures: BinanceFuturesAdapter) -> None:
        self.spot = spot
        self.futures = futures
        self._enabled = False
        self._confirmed = False
        self._position: SpotFuturesPosition | None = None
        self._trades: list[dict[str, Any]] = []
        self._trade_count = 0

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

    async def execute(self, opportunity: dict[str, Any]) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        if self.has_position:
            return None

        symbol = opportunity["symbol"]
        direction = opportunity["direction"]
        spot_price = opportunity["spot_price"]
        futures_price = opportunity["futures_price"]
        premium_pct = opportunity["premium_pct"]
        net_profit_pct = opportunity["net_profit_pct"]

        if net_profit_pct <= 0:
            logger.info(f"SKIP {symbol}: net_profit={net_profit_pct:.4f}% <= 0")
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

        spot_spend = spot_usdt * Decimal("0.90")
        futures_spend = futures_usdt * Decimal("0.90")
        start_time = time.time()

        logger.info(f"Executing SF: {symbol} {direction} premium={premium_pct:.3f}%")

        try:
            if direction == "futures_premium":
                spot_qty = await self._buy_spot(symbol, spot_spend)
                if spot_qty <= Decimal("0"):
                    logger.error(f"Spot buy returned 0 for {symbol}")
                    return None

                futures_qty = await self._sell_futures(symbol, spot_qty)
                if futures_qty <= Decimal("0"):
                    logger.error("Futures sell failed, rolling back spot")
                    await self._sell_spot(symbol, spot_qty)
                    return None
            else:
                futures_qty = await self._buy_futures(symbol, futures_spend)
                if futures_qty <= Decimal("0"):
                    logger.error(f"Futures buy returned 0 for {symbol}")
                    return None
                spot_qty = Decimal("0")

            self._position = SpotFuturesPosition(
                symbol=symbol,
                direction=direction,
                spot_quantity=spot_qty,
                spot_price=spot_price,
                futures_quantity=futures_qty,
                futures_price=futures_price,
                premium_pct=premium_pct,
                initial_spot_usdt=float(spot_usdt),
                initial_futures_usdt=float(futures_usdt),
            )

            self._trade_count += 1
            duration = (time.time() - start_time) * 1000

            result = {
                "trade_id": self._trade_count,
                "symbol": symbol,
                "direction": direction,
                "spot_quantity": float(spot_qty),
                "futures_quantity": float(futures_qty),
                "status": "opened",
                "duration_ms": round(duration, 2),
            }

            logger.info(f"Position opened: {symbol} {direction}")
            return result

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return None

    async def close_position(self, spot_tickers: dict[str, BidAsk]) -> dict[str, Any] | None:
        if not self._position:
            return None

        pos = self._position
        logger.info(f"Closing position: {pos.symbol} {pos.direction}")

        try:
            if pos.direction == "futures_premium":
                await self.spot.create_market_order(
                    symbol=pos.symbol,
                    side="SELL",
                    quantity=pos.spot_quantity,
                )
                await self.futures.create_futures_market_order(
                    symbol=pos.symbol,
                    side="BUY",
                    quantity=pos.futures_quantity,
                )
            else:
                await self._close_futures_long(pos.symbol, pos.futures_quantity)

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

            result = {
                "trade_id": self._trade_count,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "status": "closed",
                "pnl_usdt": round(pnl_usdt, 4),
                "pnl_pct": round(pnl_pct, 4),
                "initial_balance": round(initial_total, 2),
                "final_balance": round(final_total, 2),
            }

            self._trades.append(result)
            self._position = None
            logger.info(f"Position closed: P&L={pnl_usdt:.4f}")
            return result

        except Exception as e:
            logger.error(f"Close failed: {e}")
            return None

    async def should_close(self, spot_tickers: dict[str, BidAsk]) -> bool:
        if not self._position:
            return False

        pos = self._position
        if pos.symbol not in spot_tickers:
            return False

        spot_mid = (spot_tickers[pos.symbol].bid + spot_tickers[pos.symbol].ask) / 2

        try:
            futures_price = await self.futures.get_futures_price(pos.symbol)
        except Exception:
            return False

        if spot_mid <= 0:
            return False

        current_premium = (futures_price - spot_mid) / spot_mid * 100

        if pos.direction == "futures_premium" and current_premium < 0.05:
            return True

        return bool(pos.direction == "futures_discount" and current_premium > -0.05)

    async def _buy_spot(self, symbol: str, amount: Decimal) -> Decimal:
        ticker = await self.spot.get_ticker(symbol)
        qty = (amount * Decimal("0.99") / Decimal(str(ticker.ask))).quantize(
            Decimal("0.00001"), rounding=ROUND_DOWN
        )
        result = await self.spot.create_market_order(symbol, "BUY", qty)
        actual = Decimal(str(result.quantity))
        logger.info(f"Spot BUY: {actual} {symbol}")
        return actual

    async def _sell_spot(self, symbol: str, quantity: Decimal) -> None:
        qty = quantity.quantize(Decimal("0.00001"), rounding=ROUND_DOWN)
        await self.spot.create_market_order(symbol, "SELL", qty)
        logger.info(f"Spot SELL: {qty} {symbol}")

    async def _sell_futures(self, symbol: str, quantity: Decimal) -> Decimal:
        qty = quantity.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
        if qty <= 0:
            return Decimal("0")
        await self.futures.create_futures_market_order(symbol, "SELL", qty)
        logger.info(f"Futures SELL: {qty} {symbol}")
        return qty

    async def _buy_futures(self, symbol: str, amount_usdt: Decimal) -> Decimal:
        price = await self.futures.get_futures_price(symbol)
        if price <= 0:
            return Decimal("0")
        qty = (amount_usdt * Decimal("0.99") / Decimal(str(price))).quantize(
            Decimal("0.001"), rounding=ROUND_DOWN
        )
        if qty <= 0:
            return Decimal("0")
        await self.futures.create_futures_market_order(symbol, "BUY", qty)
        logger.info(f"Futures BUY: {qty} {symbol}")
        return qty

    async def _close_futures_long(self, symbol: str, quantity: Decimal) -> None:
        qty = quantity.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
        await self.futures.create_futures_market_order(symbol, "SELL", qty)
        logger.info(f"Futures close: SELL {qty} {symbol}")

    def get_stats(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "confirmed": self._confirmed,
            "has_position": self.has_position,
            "position": (
                {
                    "symbol": self._position.symbol,
                    "direction": self._position.direction,
                    "premium_pct": self._position.premium_pct,
                    "opened_at": self._position.opened_at.isoformat(),
                }
                if self._position
                else None
            ),
            "total_trades": len(self._trades),
            "trades": self._trades[-10:],
        }
