from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    operation_mode: str | None = None
    auto_trade: bool | None = None
    min_profit_threshold_pct: float | None = None
    trade_amount_usdt: float | None = None


@router.get("/")
async def get_settings():
    """Get current application settings."""
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


@router.put("/")
async def update_settings(update: SettingsUpdate):
    """Update application settings at runtime."""
    if update.operation_mode is not None:
        settings.operation_mode = update.operation_mode
    if update.auto_trade is not None:
        settings.auto_trade = update.auto_trade
    if update.min_profit_threshold_pct is not None:
        settings.min_profit_threshold_pct = update.min_profit_threshold_pct
    if update.trade_amount_usdt is not None:
        settings.trade_amount_usdt = update.trade_amount_usdt

    return {"status": "updated", "settings": await get_settings()}
