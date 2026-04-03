from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from decimal import Decimal
from typing import Any
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
        resp = await self.client.get("/api/v3/ticker/bookTicker", params={"symbol": symbol})
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
        resp = await self.client.get("/api/v3/depth", params={"symbol": symbol, "limit": depth})
        resp.raise_for_status()
        data = resp.json()
        return OrderBook(
            symbol=symbol,
            bids=[OrderBookLevel(price=float(p), quantity=float(q)) for p, q in data["bids"]],
            asks=[OrderBookLevel(price=float(p), quantity=float(q)) for p, q in data["asks"]],
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
        self, symbol: str, side: str, quantity: Decimal, client_order_id: str | None = None
    ) -> TradeResult:
        """POST /api/v3/order (market) - requires API key + secret"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret required for trading")

        params: dict = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(quantity),
        }
        if client_order_id:
            params["newClientOrderId"] = client_order_id

        params = self._sign(params)
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

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str | None = None,
    ) -> TradeResult:
        """POST /api/v3/order (LIMIT) - place a limit order."""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret required for trading")

        params: dict = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": str(quantity),
            "price": str(price),
        }
        if client_order_id:
            params["newClientOrderId"] = client_order_id

        params = self._sign(params)
        resp = await self.client.post("/api/v3/order", params=params)
        resp.raise_for_status()
        data = resp.json()

        return TradeResult(
            order_id=str(data["orderId"]),
            symbol=data["symbol"],
            side=data["side"],
            quantity=float(data.get("executedQty", 0)),
            price=float(data.get("price", 0)),
            fee=0,
            status=data["status"],
            timestamp=datetime.now(),
        )

    async def get_order_status(self, symbol: str, order_id: str) -> dict:
        """GET /api/v3/order - check order status."""
        params = self._sign({"symbol": symbol, "orderId": order_id})
        resp = await self.client.get("/api/v3/order", params=params)
        resp.raise_for_status()
        return resp.json()

    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """DELETE /api/v3/order - cancel an open order."""
        params = self._sign({"symbol": symbol, "orderId": order_id})
        resp = await self.client.delete("/api/v3/order", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_all_balances(self) -> list[dict]:
        """GET /api/v3/account - get all non-zero balances."""
        if not self.api_key or not self.api_secret:
            return []
        params = self._sign({})
        resp = await self.client.get("/api/v3/account", params=params)
        resp.raise_for_status()
        balances = []
        for b in resp.json().get("balances", []):
            free = float(b["free"])
            if free > 0:
                balances.append({"asset": b["asset"], "free": free})
        return balances

    async def convert_dust(self, assets: list[str]) -> dict:
        """POST /sapi/v1/asset/dust - convert small balances to BNB."""
        if not self.api_key or not self.api_secret or not assets:
            return {}
        params: dict[str, Any] = {
            "timestamp": int(time.time() * 1000),
        }
        # Binance expects: asset=BTC&asset=ETH&asset=USDC
        query_parts = [f"asset={a}" for a in assets]
        query_parts.append(f"timestamp={params['timestamp']}")
        query_string = "&".join(query_parts)
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        query_string += f"&signature={signature}"

        resp = await self.client.post(
            f"/sapi/v1/asset/dust?{query_string}",
            headers={"X-MBX-APIKEY": self.api_key},
        )
        resp.raise_for_status()
        return resp.json()

    async def cleanup_dust(self) -> dict[str, Any]:
        """
        Clean up small remaining balances after a trade.
        1. Sell any balance > $1 directly
        2. Convert tiny balances to BNB via dust API
        3. Sell BNB to USDT
        """
        from decimal import Decimal

        result = {"sold": [], "dust_converted": [], "total_recovered": 0.0}
        balances = await self.get_all_balances()
        dust_assets = []

        for bal in balances:
            asset = bal["asset"]
            free = bal["free"]

            if asset in ("USDT", "BNB"):
                continue

            # Get approximate value in USDT
            try:
                symbol = f"{asset}USDT"
                ticker = await self.get_ticker(symbol)
                value = free * ticker.bid
            except Exception:
                value = 0

            if value >= 5.0:
                # Sell directly
                try:
                    qty = Decimal(str(free)).quantize(
                        Decimal("0.00001"), rounding=Decimal.ROUND_DOWN
                    )
                    if qty > 0:
                        await self.create_market_order(symbol, "SELL", qty)
                        result["sold"].append(asset)
                        result["total_recovered"] += value
                except Exception:
                    dust_assets.append(asset)
            elif value > 0.01:
                dust_assets.append(asset)

        # Convert dust to BNB
        if dust_assets:
            try:
                await self.convert_dust(dust_assets)
                result["dust_converted"] = dust_assets
            except Exception as e:
                logger.error(f"Dust conversion failed: {e}")

        # Sell BNB to USDT if enough value (min notional ~$5)
        try:
            bnb_bal = await self.get_balance("BNB")
            bnb_ticker = await self.get_ticker("BNBUSDT")
            bnb_value = float(bnb_bal) * bnb_ticker.bid
            if bnb_value >= 5.0:
                bnb_qty = bnb_bal.quantize(Decimal("0.001"), rounding=Decimal.ROUND_DOWN)
                await self.create_market_order("BNBUSDT", "SELL", bnb_qty)
                result["sold"].append("BNB")
                result["total_recovered"] += bnb_value
        except Exception:
            pass

        return result

    async def close(self) -> None:
        await self.client.aclose()
