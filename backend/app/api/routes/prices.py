from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_scanner
from app.services.cycle_scanner import CycleScanner

router = APIRouter()


@router.get("/tickers")
async def get_all_tickers(scanner: CycleScanner = Depends(get_scanner)):
    """Get all tickers from Binance."""
    tickers = scanner.tickers
    result = {}
    for symbol, bidask in list(tickers.items())[:50]:  # First 50 for display
        result[symbol] = {
            "bid": bidask.bid,
            "ask": bidask.ask,
            "spread_pct": round((bidask.ask - bidask.bid) / bidask.bid * 100, 4),
        }
    return {
        "tickers": result,
        "total": len(tickers),
    }


@router.get("/{symbol}")
async def get_pair_price(
    symbol: str,
    scanner: CycleScanner = Depends(get_scanner),
):
    """Get price for a specific pair."""
    tickers = scanner.tickers
    if symbol not in tickers:
        return {"error": f"Symbol {symbol} not found"}

    bidask = tickers[symbol]
    return {
        "symbol": symbol,
        "bid": bidask.bid,
        "ask": bidask.ask,
        "spread_pct": round((bidask.ask - bidask.bid) / bidask.bid * 100, 4),
    }
