from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_paper_trader
from app.services.paper_trader import PaperTrader

router = APIRouter()


@router.get("/status")
async def get_paper_status(pt: PaperTrader = Depends(get_paper_trader)):
    """Get paper trading status and statistics."""
    return pt.get_stats()


@router.post("/enable")
async def enable_paper(pt: PaperTrader = Depends(get_paper_trader)):
    """Enable paper trading."""
    pt.enable()
    return {"status": "enabled"}


@router.post("/disable")
async def disable_paper(pt: PaperTrader = Depends(get_paper_trader)):
    """Disable paper trading."""
    pt.disable()
    return {"status": "disabled"}


@router.get("/trades")
async def get_paper_trades(
    limit: int = 20,
    pt: PaperTrader = Depends(get_paper_trader),
):
    """Get recent paper trades."""
    return {
        "trades": pt.get_recent_trades(limit=limit),
        "count": len(pt.executor.trades),
    }


@router.get("/balance-history")
async def get_balance_history(pt: PaperTrader = Depends(get_paper_trader)):
    """Get balance history for charting."""
    return {
        "history": pt.get_balance_history(),
    }


@router.post("/reset")
async def reset_paper(pt: PaperTrader = Depends(get_paper_trader)):
    """Reset paper trading state (clear balance and trades)."""
    from app.services.paper_executor import PaperExecutor

    pt.executor = PaperExecutor(
        initial_balance=pt.executor.initial_balance,
        fee_rate=pt.executor.fee_rate,
        slippage_pct=pt.executor.slippage_pct,
    )
    return {"status": "reset", "stats": pt.get_stats()}
