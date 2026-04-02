from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.models.primitives import BidAsk, OrderBook, TradeResult


class ExchangeAdapter(ABC):
    name: str

    @abstractmethod
    async def get_all_tickers(self) -> dict[str, BidAsk]:
        """Get bid/ask for ALL trading pairs (one API call)."""
        ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> BidAsk:
        """Get bid/ask for a single pair."""
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book snapshot."""
        ...

    @abstractmethod
    async def get_balance(self, currency: str) -> Decimal:
        """Get available balance for a currency."""
        ...

    @abstractmethod
    async def create_market_order(self, symbol: str, side: str, quantity: Decimal) -> TradeResult:
        """Place a market order."""
        ...

    @abstractmethod
    async def get_fee_rate(self, symbol: str) -> Decimal:
        """Get taker fee for a pair."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        ...
