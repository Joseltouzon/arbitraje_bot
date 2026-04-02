from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.db.models import CycleSnapshot, SpotFuturesHistory, TradeHistory
from app.db.session import async_session_factory
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CycleLogger:
    """Persists detected cycles and trades to PostgreSQL."""

    async def log_cycle(self, cycle: dict[str, Any]) -> int | None:
        """Log a detected profitable cycle."""
        try:
            async with async_session_factory() as session:
                snapshot = CycleSnapshot(
                    currencies=",".join(cycle["currencies"]),
                    pairs=",".join(leg["pair"] for leg in cycle["legs"]),
                    sides=",".join(leg["side"] for leg in cycle["legs"]),
                    net_profit_pct=cycle["net_profit_pct"],
                    net_profit_usdt=cycle.get("calculated", {}).get("net_profit", 0),
                    initial_amount=cycle.get("calculated", {}).get("initial_amount", 0),
                    final_amount=cycle.get("calculated", {}).get("final_amount", 0),
                    total_fees=cycle.get("calculated", {}).get("total_fees", 0),
                    total_slippage=cycle.get("calculated", {}).get("total_slippage", 0),
                    raw_rate_product=cycle.get("raw_rate_product", 0),
                    legs_json=json.dumps(cycle["legs"]),
                )
                session.add(snapshot)
                await session.commit()
                await session.refresh(snapshot)
                return snapshot.id
        except Exception as e:
            logger.error(f"Failed to log cycle: {e}")
            return None

    async def log_trade(
        self,
        cycle: dict[str, Any],
        mode: str,
        result: dict[str, Any],
    ) -> int | None:
        """Log an executed trade (paper or live)."""
        try:
            async with async_session_factory() as session:
                trade = TradeHistory(
                    mode=mode,
                    currencies=",".join(cycle["currencies"]),
                    pairs=",".join(leg["pair"] for leg in cycle["legs"]),
                    sides=",".join(leg["side"] for leg in cycle["legs"]),
                    initial_amount=result.get("initial_amount", 0),
                    final_amount=result.get("final_amount", 0),
                    profit_usdt=result.get("net_profit", 0),
                    profit_pct=result.get("net_profit_pct", 0),
                    total_fees=result.get("total_fees", 0),
                    status=result.get("status", "completed"),
                )
                session.add(trade)
                await session.commit()
                await session.refresh(trade)
                return trade.id
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")
            return None

    async def get_recent_cycles(self, limit: int = 50) -> list[dict]:
        """Get most recent detected cycles."""
        try:
            async with async_session_factory() as session:
                from sqlalchemy import desc, select

                stmt = select(CycleSnapshot).order_by(desc(CycleSnapshot.detected_at)).limit(limit)
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "currencies": r.currencies.split(","),
                        "pairs": r.pairs.split(","),
                        "net_profit_pct": r.net_profit_pct,
                        "net_profit_usdt": r.net_profit_usdt,
                        "detected_at": r.detected_at.isoformat(),
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get recent cycles: {e}")
            return []

    async def get_recent_trades(self, limit: int = 50) -> list[dict]:
        """Get most recent trades."""
        try:
            async with async_session_factory() as session:
                from sqlalchemy import desc, select

                stmt = select(TradeHistory).order_by(desc(TradeHistory.executed_at)).limit(limit)
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "mode": r.mode,
                        "currencies": r.currencies.split(","),
                        "profit_usdt": r.profit_usdt,
                        "profit_pct": r.profit_pct,
                        "status": r.status,
                        "executed_at": r.executed_at.isoformat(),
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []

    async def log_spot_futures(self, opp: dict[str, Any]) -> int | None:
        """Log a detected spot-futures opportunity."""
        try:
            async with async_session_factory() as session:
                record = SpotFuturesHistory(
                    symbol=opp.get("symbol", ""),
                    spot_price=opp.get("spot_price", 0),
                    futures_price=opp.get("futures_price", 0),
                    premium_pct=opp.get("premium_pct", 0),
                    net_profit_pct=opp.get("net_profit_pct", 0),
                    direction=opp.get("direction", ""),
                    funding_rate=opp.get("funding_rate", 0),
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)
                return record.id
        except Exception as e:
            logger.error(f"Failed to log spot-futures: {e}")
            return None

    async def get_recent_spot_futures(self, limit: int = 50) -> list[dict]:
        """Get recent spot-futures opportunities."""
        try:
            async with async_session_factory() as session:
                from sqlalchemy import desc

                stmt = (
                    select(SpotFuturesHistory)
                    .order_by(desc(SpotFuturesHistory.detected_at))
                    .limit(limit)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "symbol": r.symbol,
                        "spot_price": r.spot_price,
                        "futures_price": r.futures_price,
                        "premium_pct": r.premium_pct,
                        "net_profit_pct": r.net_profit_pct,
                        "direction": r.direction,
                        "funding_rate": r.funding_rate,
                        "detected_at": r.detected_at.isoformat(),
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get spot-futures history: {e}")
            return []
