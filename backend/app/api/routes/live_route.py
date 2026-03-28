from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.deps import get_live_executor
from app.services.live_executor import LiveExecutor

router = APIRouter()


@router.get("/status")
async def get_live_status(le: LiveExecutor = Depends(get_live_executor)):
    """Get live trading status and statistics."""
    return le.get_stats()


@router.post("/enable")
async def enable_live(le: LiveExecutor = Depends(get_live_executor)):
    """Enable live trading (requires AUTO_TRADE=true in .env)."""
    result = le.enable()
    return result


@router.post("/confirm")
async def confirm_live(le: LiveExecutor = Depends(get_live_executor)):
    """Final confirmation to start placing real orders."""
    result = le.confirm()
    return result


@router.post("/disable")
async def disable_live(le: LiveExecutor = Depends(get_live_executor)):
    """Immediately stop live trading."""
    result = le.disable()
    return result


@router.post("/pause")
async def pause_live(le: LiveExecutor = Depends(get_live_executor)):
    """Pause trading (risk manager will block new trades)."""
    le.risk.pause()
    return {"status": "paused"}


@router.post("/resume")
async def resume_live(le: LiveExecutor = Depends(get_live_executor)):
    """Resume trading after pause."""
    le.risk.resume()
    return {"status": "resumed"}


@router.get("/trades")
async def get_live_trades(
    limit: int = 20,
    le: LiveExecutor = Depends(get_live_executor),
):
    """Get recent live trades."""
    return {
        "trades": le.get_recent_trades(limit=limit),
        "count": len(le.trades),
    }


@router.get("/config")
async def get_live_config():
    """Get current live trading configuration."""
    return {
        "auto_trade": settings.auto_trade,
        "operation_mode": settings.operation_mode,
        "min_profit_pct": settings.min_profit_threshold_pct,
        "trade_amount_usdt": settings.trade_amount_usdt,
        "max_trades_per_hour": settings.max_trades_per_hour,
        "max_consecutive_losses": settings.max_consecutive_losses,
        "stop_loss_pct": settings.stop_loss_pct,
    }
