from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.exchanges.base import ExchangeAdapter
from app.models.primitives import BidAsk, OrderBook, OrderBookLevel, TradeResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BinanceAdapter(ExchangeAdapter):
    name = "binance"
    BASE_URL = "https://api.binance.com"
    FEE_RATE = Decimal("0.001")  # 0.1% standard taker fee

    def __init__(self) -> None:
        self.api_key = settings.binance_api_key
        self.api_secret = settings.binance_api_secret
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(10.0),
            headers={"X-MBX-APIKEY": self.api_key} if self.api_key else {},
        )

    def _sign(self, params: dict) -> dict:
        """Sign request with HMAC SHA256."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    async def get_all_tickers(self) -> dict[str, BidAsk]:
        """
        Single API call gets ALL bid/ask prices.
        GET /api/v3/ticker/bookTicker
        Weight: 40 (one request = all pairs)
        """
        resp = await self.client.get("/api/v3/ticker/bookTicker")
        resp.raise_for_status()
        data = resp.json()

        result = {}
        for item in data:
            symbol = item["symbol"]
            bid = float(item["bidPrice"])
            ask = float(item["askPrice"])

            # Skip zero price or inverted spread
            if bid <= 0 or ask <= 0 or bid >= ask:
                continue

            result[symbol] = BidAsk(
                bid=bid,
                ask=ask,
                bid_qty=float(item["bidQty"]),
                ask_qty=float(item["askQty"]),
            )

        logger.info(f"Fetched {len(result)} tickers from Binance")
        return result

    async def get_ticker(self, symbol: str) -> BidAsk:
        """GET /api/v3/ticker/bookTicker?symbol=BTCUSDT"""
        resp = await self.client.get(
            "/api/v3/ticker/bookTicker", params={"symbol": symbol}
        )
        resp.raise_for_status()
        data = resp.json()
        return BidAsk(
            bid=float(data["bidPrice"]),
            ask=float(data["askPrice"]),
            bid_qty=float(data["bidQty"]),
            ask_qty=float(data["askQty"]),
        )

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """GET /api/v3/depth?symbol=BTCUSDT&limit=20"""
        resp = await self.client.get(
            "/api/v3/depth", params={"symbol": symbol, "limit": depth}
        )
        resp.raise_for_status()
        data = resp.json()
        return OrderBook(
            symbol=symbol,
            bids=[
                OrderBookLevel(price=float(p), quantity=float(q))
                for p, q in data["bids"]
            ],
            asks=[
                OrderBookLevel(price=float(p), quantity=float(q))
                for p, q in data["asks"]
            ],
            timestamp=datetime.now(),
        )

    async def get_balance(self, currency: str) -> Decimal:
        """GET /api/v3/account (requires API key + signature)"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret required for balance check")

        params = self._sign({})
        resp = await self.client.get("/api/v3/account", params=params)
        resp.raise_for_status()
        data = resp.json()

        for balance in data.get("balances", []):
            if balance["asset"] == currency:
                return Decimal(balance["free"])
        return Decimal("0")

    async def create_market_order(
        self, symbol: str, side: str, quantity: Decimal
    ) -> TradeResult:
        """POST /api/v3/order (market) - requires API key + secret"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret required for trading")

        params = self._sign(
            {
                "symbol": symbol,
                "side": side.upper(),
                "type": "MARKET",
                "quantity": str(quantity),
            }
        )
        resp = await self.client.post("/api/v3/order", params=params)
        resp.raise_for_status()
        data = resp.json()

        fills = data.get("fills", [])
        total_fee = sum(float(f["commission"]) for f in fills)
        avg_price = (
            sum(float(f["price"]) * float(f["qty"]) for f in fills) / float(data["executedQty"])
            if float(data.get("executedQty", 0)) > 0
            else 0
        )

        return TradeResult(
            order_id=str(data["orderId"]),
            symbol=data["symbol"],
            side=data["side"],
            quantity=float(data["executedQty"]),
            price=avg_price,
            fee=total_fee,
            status=data["status"],
            timestamp=datetime.now(),
        )

    async def get_fee_rate(self, symbol: str) -> Decimal:
        """Return standard taker fee (can be overridden per VIP level)."""
        return self.FEE_RATE

    async def close(self) -> None:
        await self.client.aclose()
