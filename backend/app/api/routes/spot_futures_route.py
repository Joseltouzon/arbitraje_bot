from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_spot_futures
from app.services.spot_futures import SpotFuturesDetector

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
