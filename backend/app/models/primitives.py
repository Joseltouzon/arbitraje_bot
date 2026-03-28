from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BidAsk(BaseModel):
    bid: float
    ask: float
    bid_qty: float
    ask_qty: float


class Ticker(BaseModel):
    symbol: str
    bid: float
    ask: float
    bid_qty: float
    ask_qty: float
    timestamp: datetime


class OrderBookLevel(BaseModel):
    price: float
    quantity: float


class OrderBook(BaseModel):
    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: datetime


class CycleLeg(BaseModel):
    from_currency: str
    to_currency: str
    pair: str
    side: str  # "buy" or "sell"
    price: float
    fee: float


class TriangularCycle(BaseModel):
    currencies: list[str]  # e.g. ["USDT", "BTC", "ETH", "USDT"]
    legs: list[CycleLeg]
    gross_profit_pct: float
    net_profit_pct: float
    net_profit_usdt: float
    timestamp: datetime


class TradeResult(BaseModel):
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    fee: float
    status: str
    timestamp: datetime


class PnLSnapshot(BaseModel):
    total_profit_usdt: float
    total_trades: int
    success_rate: float
    daily_profit_usdt: float
    timestamp: datetime


class AppSettings(BaseModel):
    operation_mode: str
    auto_trade: bool
    min_profit_threshold_pct: float
    trade_amount_usdt: float
    max_trades_per_hour: int
