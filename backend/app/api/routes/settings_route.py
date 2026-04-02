from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()

_settings_lock = asyncio.Lock()


class SettingsUpdate(BaseModel):
    operation_mode: str | None = None
    auto_trade: bool | None = None
    min_profit_threshold_pct: float | None = None
    trade_amount_usdt: float | None = None
    max_trades_per_hour: int | None = None
    stop_loss_pct: float | None = None
    poll_interval_ms: int | None = None


def _get_settings_dict() -> dict:
    """Read current settings (safe to call without lock for reads)."""
    return {
        "operation_mode": settings.operation_mode,
        "auto_trade": settings.auto_trade,
        "min_profit_threshold_pct": settings.min_profit_threshold_pct,
        "start_currencies": settings.start_currency_list,
        "max_cycle_length": settings.max_cycle_length,
        "poll_interval_ms": settings.poll_interval_ms,
        "trade_amount_usdt": settings.trade_amount_usdt,
        "max_trades_per_hour": settings.max_trades_per_hour,
        "stop_loss_pct": settings.stop_loss_pct,
    }


@router.get("/")
async def get_settings():
    """Get current application settings."""
    return _get_settings_dict()


@router.put("/")
async def update_settings(update: SettingsUpdate):
    """Update application settings at runtime (thread-safe)."""
    async with _settings_lock:
        if update.operation_mode is not None:
            settings.operation_mode = update.operation_mode
        if update.auto_trade is not None:
            settings.auto_trade = update.auto_trade
        if update.min_profit_threshold_pct is not None:
            settings.min_profit_threshold_pct = update.min_profit_threshold_pct
        if update.trade_amount_usdt is not None:
            settings.trade_amount_usdt = update.trade_amount_usdt
        if update.max_trades_per_hour is not None:
            settings.max_trades_per_hour = update.max_trades_per_hour
        if update.stop_loss_pct is not None:
            settings.stop_loss_pct = update.stop_loss_pct
        if update.poll_interval_ms is not None:
            settings.poll_interval_ms = update.poll_interval_ms

        # Persist to Redis
        try:
            from app.deps import redis_cache

            if redis_cache.connected:
                await redis_cache.save_settings(_get_settings_dict())
        except Exception:
            pass

    return {"status": "updated", "settings": _get_settings_dict()}


async def restore_settings_from_redis():
    """Restore runtime settings from Redis on startup."""
    try:
        from app.deps import redis_cache

        saved = await redis_cache.load_settings()
        if not saved:
            return

        async with _settings_lock:
            for key, value in saved.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
    except Exception:
        pass
