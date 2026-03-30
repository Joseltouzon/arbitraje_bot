from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_sf_executor, get_spot_futures
from app.services.spot_futures import SpotFuturesDetector
from app.services.spot_futures_executor import SpotFuturesExecutor

router = APIRouter()


@router.get("/opportunities")
async def get_spot_futures_opportunities(
    sf: SpotFuturesDetector = Depends(get_spot_futures),
):
    """Get current spot-futures arbitrage opportunities."""
    return {
        "opportunities": sf._opportunities,
        "count": len(sf._opportunities),
    }


@router.post("/scan")
async def trigger_spot_futures_scan(
    sf: SpotFuturesDetector = Depends(get_spot_futures),
):
    """Manually trigger a spot-futures scan."""
    from app.deps import aggregator

    opportunities = await sf.scan(aggregator.tickers)
    return {
        "status": "ok",
        "opportunities": opportunities,
    }


@router.get("/stats")
async def get_spot_futures_stats(
    sf: SpotFuturesDetector = Depends(get_spot_futures),
):
    """Get spot-futures scanner stats."""
    return sf.get_stats()


@router.get("/executor/status")
async def get_sf_executor_status(
    ex: SpotFuturesExecutor = Depends(get_sf_executor),
):
    """Get spot-futures executor status."""
    return ex.get_stats()


@router.post("/executor/enable")
async def enable_sf_executor(
    ex: SpotFuturesExecutor = Depends(get_sf_executor),
):
    return ex.enable()


@router.post("/executor/confirm")
async def confirm_sf_executor(
    ex: SpotFuturesExecutor = Depends(get_sf_executor),
):
    return ex.confirm()


@router.post("/executor/disable")
async def disable_sf_executor(
    ex: SpotFuturesExecutor = Depends(get_sf_executor),
):
    return ex.disable()


@router.post("/executor/close")
async def close_sf_position(
    ex: SpotFuturesExecutor = Depends(get_sf_executor),
):
    """Manually close current position."""
    from app.deps import aggregator

    result = await ex.close_position(aggregator.tickers)
    return result or {"status": "no_position"}
