from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.analytics import Analytics
from app.services.cycle_logger import CycleLogger

router = APIRouter()

_cycle_logger = CycleLogger()
_analytics = Analytics()


@router.get("/cycles")
async def get_cycle_history(limit: int = Query(default=50, ge=1, le=1000)):
    """Get recent detected cycles from database."""
    cycles = await _cycle_logger.get_recent_cycles(limit=limit)
    return {"cycles": cycles, "count": len(cycles)}


@router.get("/trades")
async def get_trade_history(limit: int = Query(default=50, ge=1, le=1000)):
    """Get recent trades from database."""
    trades = await _cycle_logger.get_recent_trades(limit=limit)
    return {"trades": trades, "count": len(trades)}


@router.get("/analytics/summary")
async def get_analytics_summary():
    """Get overall performance summary."""
    return await _analytics.get_summary()


@router.get("/analytics/timeseries")
async def get_profit_timeseries(hours: int = Query(default=24, ge=1, le=168)):
    """Get profit over time for charting."""
    data = await _analytics.get_profit_timeseries(hours=hours)
    return {"timeseries": data, "hours": hours}


@router.get("/analytics/top")
async def get_top_cycles(limit: int = Query(default=10, ge=1, le=100)):
    """Get top cycles by profit percentage."""
    cycles = await _analytics.get_top_cycles(limit=limit)
    return {"cycles": cycles}


@router.get("/spot-futures")
async def get_spot_futures_history(limit: int = Query(default=50, ge=1, le=1000)):
    """Get recent spot-futures opportunities from database."""
    records = await _cycle_logger.get_recent_spot_futures(limit=limit)
    return {"records": records, "count": len(records)}
