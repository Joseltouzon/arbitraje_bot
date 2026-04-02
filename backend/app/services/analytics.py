from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.db.models import CycleSnapshot, TradeHistory
from app.db.session import async_session_factory
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Analytics:
    """Provides performance analytics from historical data."""

    async def get_summary(self) -> dict[str, Any]:
        """Get overall performance summary."""
        try:
            async with async_session_factory() as session:
                # Total cycles detected
                total_cycles = await session.scalar(select(func.count(CycleSnapshot.id))) or 0

                # Total trades executed
                total_trades = await session.scalar(select(func.count(TradeHistory.id))) or 0

                # Best profit pct
                best_profit = (
                    await session.scalar(select(func.max(CycleSnapshot.net_profit_pct))) or 0.0
                )

                # Avg profit pct
                avg_profit = (
                    await session.scalar(select(func.avg(CycleSnapshot.net_profit_pct))) or 0.0
                )

                # Total profit from trades
                total_profit = (
                    await session.scalar(select(func.sum(TradeHistory.profit_usdt))) or 0.0
                )

                # Success rate (trades with positive profit)
                profitable_trades = (
                    await session.scalar(
                        select(func.count(TradeHistory.id)).where(TradeHistory.profit_usdt > 0)
                    )
                    or 0
                )

                success_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0.0

                return {
                    "total_cycles_detected": total_cycles,
                    "total_trades_executed": total_trades,
                    "best_profit_pct": round(best_profit, 4),
                    "avg_profit_pct": round(avg_profit, 4),
                    "total_profit_usdt": round(total_profit, 6),
                    "success_rate": round(success_rate, 2),
                }
        except Exception as e:
            logger.error(f"Failed to get analytics summary: {e}")
            return {
                "total_cycles_detected": 0,
                "total_trades_executed": 0,
                "best_profit_pct": 0.0,
                "avg_profit_pct": 0.0,
                "total_profit_usdt": 0.0,
                "success_rate": 0.0,
            }

    async def get_profit_timeseries(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get profit over time for charting."""
        try:
            async with async_session_factory() as session:
                cutoff = datetime.now() - timedelta(hours=hours)

                stmt = (
                    select(
                        func.date_trunc("hour", CycleSnapshot.detected_at).label("hour"),
                        func.count(CycleSnapshot.id).label("count"),
                        func.avg(CycleSnapshot.net_profit_pct).label("avg_profit"),
                        func.max(CycleSnapshot.net_profit_pct).label("max_profit"),
                        func.sum(CycleSnapshot.net_profit_usdt).label("total_profit"),
                    )
                    .where(CycleSnapshot.detected_at >= cutoff)
                    .group_by("hour")
                    .order_by("hour")
                )

                result = await session.execute(stmt)
                rows = result.all()

                return [
                    {
                        "timestamp": row.hour.isoformat(),
                        "count": row.count,
                        "avg_profit_pct": round(float(row.avg_profit or 0), 4),
                        "max_profit_pct": round(float(row.max_profit or 0), 4),
                        "total_profit_usdt": round(float(row.total_profit or 0), 6),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get profit timeseries: {e}")
            return []

    async def get_top_cycles(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get top cycles by profit percentage."""
        try:
            async with async_session_factory() as session:
                stmt = (
                    select(CycleSnapshot).order_by(CycleSnapshot.net_profit_pct.desc()).limit(limit)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()

                return [
                    {
                        "id": r.id,
                        "currencies": r.currencies.split(","),
                        "net_profit_pct": r.net_profit_pct,
                        "net_profit_usdt": r.net_profit_usdt,
                        "detected_at": r.detected_at.isoformat(),
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get top cycles: {e}")
            return []
