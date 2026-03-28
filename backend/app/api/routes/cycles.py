from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.deps import get_scanner
from app.services.cycle_scanner import CycleScanner

router = APIRouter()


@router.get("/")
async def get_cycles(scanner: CycleScanner = Depends(get_scanner)):
    """Get current profitable cycles."""
    return {
        "cycles": scanner.cycles,
        "count": len(scanner.cycles),
        "scan_count": scanner.scan_count,
    }


@router.post("/scan")
async def trigger_scan(scanner: CycleScanner = Depends(get_scanner)):
    """Manually trigger a single scan."""
    cycles = await scanner.scan_once()
    return {
        "status": "ok",
        "cycles_found": len(cycles),
        "cycles": cycles,
    }


@router.get("/stats")
async def get_cycle_stats(scanner: CycleScanner = Depends(get_scanner)):
    """Get cycle detection statistics."""
    return {
        **scanner.get_stats(),
        "config": {
            "start_currency": settings.start_currency,
            "min_profit_pct": settings.min_profit_threshold_pct,
            "max_cycle_length": settings.max_cycle_length,
            "poll_interval_ms": settings.poll_interval_ms,
            "trade_amount_usdt": settings.trade_amount_usdt,
        },
    }
