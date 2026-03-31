from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.config import settings
from app.exchanges.binance import BinanceAdapter
from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SpotFuturesPosition:
    """An open spot-futures position."""
    symbol: str
    direction: str  # "futures_premium" or "futures_discount"
    spot_quantity: Decimal
    spot_price: float
    futures_quantity: Decimal
    futures_price: float
    premium_pct: float
    opened_at: datetime = field(default_factory=datetime.now)


class SpotFuturesExecutor:
    """
    Executes spot-futures arbitrage.

    Flow (futures_premium = buy spot + sell futures):
    1. Transfer USDT spot → futures (for margin)
    2. Buy asset in spot
    3. Short asset in futures
    4. Monitor for convergence
    5. Sell asset in spot
    6. Buy back futures (close short)
    7. Transfer USDT futures → spot
    """

    def __init__(
        self,
        spot: BinanceAdapter,
        futures: BinanceFuturesAdapter,
    ) -> None:
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
        return {"status": "enabled", "message": "Spot-futures enabled. Call /confirm to finalize."}

    def confirm(self) -> dict[str, str]:
        if not self._enabled:
            return {"status": "error", "message": "Enable first"}
        self._confirmed = True
        return {"status": "confirmed", "message": "Spot-futures trading active"}

    def disable(self) -> dict[str, str]:
        self._enabled = False
        self._confirmed = False
        return {"status": "disabled", "message": "Spot-futures stopped"}

    async def execute(self, opportunity: dict[str, Any]) -> dict[str, Any] | None:
        """
        Execute a spot-futures arbitrage opportunity.
        Returns result dict or None if can't execute.
        """
        if not self.enabled:
            return None

        if self.has_position:
            logger.info("Already have a position, skipping")
            return None

        symbol = opportunity["symbol"]
        direction = opportunity["direction"]
        spot_price = opportunity["spot_price"]
        futures_price = opportunity["futures_price"]
        premium_pct = opportunity["premium_pct"]
        net_profit_pct = opportunity["net_profit_pct"]

        # Only execute if net profit is positive
        if net_profit_pct <= 0:
            return None

        self._trade_count += 1
        start_time = time.time()

        # Get available balances
        try:
            spot_usdt = await self.spot.get_balance("USDT")
            futures_usdt = await self.futures.get_futures_usdt_balance()
        except Exception as e:
            logger.error(f"Failed to get balances: {e}")
            return None

        if spot_usdt < Decimal("10"):
            logger.warning(f"Insufficient spot USDT: {spot_usdt}")
            return None

        if futures_usdt < Decimal("5"):
            logger.warning(f"Insufficient futures USDT: {futures_usdt}")
            return None

        # Use 90% of available spot USDT
        spot_spend = spot_usdt * Decimal("0.90")
        asset = symbol.replace("USDT", "")

        logger.info(
            f"Executing spot-futures #{self._trade_count}: "
            f"{symbol} {direction} premium={premium_pct:.3f}%"
        )

        try:
            if direction == "futures_premium":
                # Buy spot + Sell futures
                spot_qty = await self._buy_spot(symbol, asset, spot_spend)
                if spot_qty <= Decimal("0"):
                    return None

                futures_qty = await self._sell_futures(symbol, spot_qty)
                if futures_qty <= Decimal("0"):
                    # Rollback: sell spot
                    await self._sell_spot(symbol, asset, spot_qty)
                    return None

            else:
                # futures_discount: Futures cheaper than spot
                # Strategy: Buy futures (long) + hold until discount closes
                futures_qty = await self._buy_futures(symbol, spot_spend)
                if futures_qty <= Decimal("0"):
                    return None

                spot_qty = Decimal("0")  # No spot position for discount

            # Open position
            self._position = SpotFuturesPosition(
                symbol=symbol,
                direction=direction,
                spot_quantity=spot_qty,
                spot_price=spot_price,
                futures_quantity=futures_qty,
                futures_price=futures_price,
                premium_pct=premium_pct,
            )

            duration = (time.time() - start_time) * 1000

            result = {
                "trade_id": self._trade_count,
                "symbol": symbol,
                "direction": direction,
                "spot_quantity": float(spot_qty),
                "futures_quantity": float(futures_qty),
                "spot_price": spot_price,
                "futures_price": futures_price,
                "premium_pct": premium_pct,
                "status": "opened",
                "duration_ms": round(duration, 2),
                "message": f"Position opened: {direction} {symbol}",
            }

            logger.info(f"Position opened: {result}")
            return result

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return None

    async def close_position(
        self, spot_tickers: dict[str, BidAsk]
    ) -> dict[str, Any] | None:
        """
        Close an open position when premium has converged.
        Sell spot + Buy back futures.
        """
        if not self._position:
            return None

        pos = self._position
        pos.symbol.replace("USDT", "")

        logger.info(f"Closing position: {pos.symbol} {pos.direction}")

        try:
            if pos.direction == "futures_premium":
                # Premium: had spot long + futures short
                # Close: sell spot + buy back futures
                sell_result = await self.spot.create_market_order(
                    symbol=pos.symbol,
                    side="SELL",
                    quantity=pos.spot_quantity,
                )
                await self.futures.create_futures_market_order(
                    symbol=pos.symbol,
                    side="BUY",
                    quantity=pos.futures_quantity,
                )
                spot_pnl = float(sell_result.get("cummulativeQuoteQty", 0))
            else:
                # Discount: had futures long
                # Close: sell futures
                await self._close_futures_long(pos.symbol, pos.futures_quantity)
                spot_pnl = 0

            # Transfer profit from futures to spot
            futures_bal = await self.futures.get_futures_usdt_balance()
            if futures_bal > Decimal("1"):
                await self.futures.transfer_futures_to_spot(
                    "USDT", futures_bal * Decimal("0.99")
                )

            self._trade_count += 1

            result = {
                "trade_id": self._trade_count,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "status": "closed",
                "spot_sell_usdt": spot_pnl,
                "message": f"Position closed: {pos.symbol}",
            }

            self._trades.append(result)
            self._position = None

            logger.info(f"Position closed: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return None

    async def should_close(self, spot_tickers: dict[str, BidAsk]) -> bool:
        """Check if position should be closed (premium converged)."""
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

        # Close when premium drops below 0.05% (converged)
        if pos.direction == "futures_premium" and current_premium < 0.05:
            return True

        # Close when discount converges (premium rises above -0.05%)
        return bool(pos.direction == "futures_discount" and current_premium > -0.05)

    async def _buy_spot(self, symbol: str, asset: str, amount: Decimal) -> Decimal:
        """Buy asset in spot."""
        ticker = await self.spot.get_ticker(symbol)
        qty = (amount * Decimal("0.99")) / Decimal(str(ticker.ask))
        qty = qty.quantize(Decimal("0.00001"))
        await self.spot.create_market_order(
            symbol=symbol,
            side="BUY",
            quantity=qty,
        )
        # Use quoteOrderQty approach via the adapter
        # For now, calculate quantity from amount and price
        ticker = await self.spot.get_ticker(symbol)
        qty = (amount * Decimal("0.99")) / Decimal(str(ticker.ask))
        qty = qty.quantize(Decimal("0.00001"))

        await self.spot.create_market_order(
            symbol=symbol,
            side="BUY",
            quantity=qty,
        )
        logger.info(f"Bought {qty} {asset} in spot")
        return qty

    async def _sell_spot(self, symbol: str, asset: str, quantity: Decimal) -> dict:
        """Sell asset in spot."""
        result = await self.spot.create_market_order(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
        )
        logger.info(f"Sold {quantity} {asset} in spot")
        return result

    async def _sell_futures(self, symbol: str, quantity: Decimal) -> Decimal:
        """Short asset in futures."""
        qty = quantity.quantize(Decimal("0.001"))
        await self.futures.create_futures_market_order(
            symbol=symbol,
            side="SELL",
            quantity=qty,
        )
        logger.info(f"Shorted {qty} {symbol} in futures")
        return qty

    async def _buy_futures(self, symbol: str, amount_usdt: Decimal) -> Decimal:
        """Buy asset in futures (long)."""
        price = await self.futures.get_futures_price(symbol)
        if price <= 0:
            return Decimal("0")
        qty = (amount_usdt * Decimal("0.99")) / Decimal(str(price))
        qty = qty.quantize(Decimal("0.001"))
        await self.futures.create_futures_market_order(
            symbol=symbol,
            side="BUY",
            quantity=qty,
        )
        logger.info(f"Bought {qty} {symbol} futures (long)")
        return qty

    async def _close_futures_long(self, symbol: str, quantity: Decimal) -> dict:
        """Close a futures long position (sell)."""
        qty = quantity.quantize(Decimal("0.001"))
        result = await self.futures.create_futures_market_order(
            symbol=symbol,
            side="SELL",
            quantity=qty,
        )
        logger.info(f"Closed futures long: sold {qty} {symbol}")
        return result

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
