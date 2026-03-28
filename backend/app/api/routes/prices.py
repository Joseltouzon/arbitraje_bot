from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_aggregator
from app.services.price_aggregator import PriceAggregator

router = APIRouter()


@router.get("/tickers")
async def get_all_tickers(agg: PriceAggregator = Depends(get_aggregator)):
    """Get all tickers from Binance WebSocket."""
    tickers = agg.tickers
    result = {}
    for symbol, bidask in list(tickers.items())[:100]:
        if bidask.bid > 0 and bidask.ask > 0:
            result[symbol] = {
                "bid": bidask.bid,
                "ask": bidask.ask,
                "spread_pct": round(
                    (bidask.ask - bidask.bid) / bidask.bid * 100, 4
                ),
            }
    return {
        "tickers": result,
        "total": len(tickers),
        "ws_connected": agg.connected,
    }


@router.get("/{symbol}")
async def get_pair_price(
    symbol: str,
    agg: PriceAggregator = Depends(get_aggregator),
):
    """Get price for a specific pair."""
    tickers = agg.tickers
    if symbol not in tickers:
        return {"error": f"Symbol {symbol} not found"}

    bidask = tickers[symbol]
    return {
        "symbol": symbol,
        "bid": bidask.bid,
        "ask": bidask.ask,
        "spread_pct": round((bidask.ask - bidask.bid) / bidask.bid * 100, 4),
    }
