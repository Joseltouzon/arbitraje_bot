from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BinanceFuturesAdapter:
    """
    Binance USDⓈ-M Futures API adapter.
    Used for spot-futures arbitrage.
    """

    BASE_URL = "https://fapi.binance.com"

    def __init__(self) -> None:
        self.api_key = settings.binance_api_key
        self.api_secret = settings.binance_api_secret
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(10.0),
            headers={"X-MBX-APIKEY": self.api_key} if self.api_key else {},
        )

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    async def get_futures_price(self, symbol: str) -> float:
        """GET /fapi/v1/ticker/price - get current futures price."""
        resp = await self.client.get("/fapi/v1/ticker/price", params={"symbol": symbol})
        resp.raise_for_status()
        return float(resp.json()["price"])

    async def get_all_futures_prices(self) -> dict[str, float]:
        """GET /fapi/v1/ticker/price - get all futures prices."""
        resp = await self.client.get("/fapi/v1/ticker/price")
        resp.raise_for_status()
        return {item["symbol"]: float(item["price"]) for item in resp.json()}

    async def get_funding_rate(self, symbol: str) -> dict[str, Any]:
        """GET /fapi/v1/fundingRate - get funding rate history."""
        resp = await self.client.get(
            "/fapi/v1/fundingRate",
            params={"symbol": symbol, "limit": 1},
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return {
                "symbol": data[0]["symbol"],
                "funding_rate": float(data[0]["fundingRate"]),
                "funding_time": data[0]["fundingTime"],
            }
        return {"symbol": symbol, "funding_rate": 0.0, "funding_time": 0}

    async def get_all_funding_rates(self) -> list[dict[str, Any]]:
        """GET /fapi/v1/premiumIndex - current funding rate for all symbols."""
        resp = await self.client.get("/fapi/v1/premiumIndex")
        resp.raise_for_status()
        result = []
        for item in resp.json():
            try:
                result.append(
                    {
                        "symbol": item["symbol"],
                        "mark_price": float(item.get("markPrice", 0)),
                        "index_price": float(item.get("indexPrice", 0)),
                        "funding_rate": float(item.get("lastFundingRate", 0)),
                        "next_funding_time": item.get("nextFundingTime", 0),
                    }
                )
            except (KeyError, ValueError, TypeError):
                continue
        return result

    async def get_futures_balance(self) -> dict[str, Decimal]:
        """GET /fapi/v2/balance - get futures account balance."""
        params = self._sign({})
        resp = await self.client.get("/fapi/v2/balance", params=params)
        resp.raise_for_status()
        balances = {}
        for item in resp.json():
            if float(item["balance"]) > 0:
                balances[item["asset"]] = Decimal(item["balance"])
        return balances

    async def get_futures_usdt_balance(self) -> Decimal:
        """Get available USDT in futures wallet."""
        balances = await self.get_futures_balance()
        return balances.get("USDT", Decimal("0"))

    async def create_futures_market_order(
        self, symbol: str, side: str, quantity: Decimal
    ) -> dict[str, Any]:
        """POST /fapi/v1/order - place a futures market order."""
        params = self._sign(
            {
                "symbol": symbol,
                "side": side.upper(),
                "type": "MARKET",
                "quantity": str(quantity),
            }
        )
        resp = await self.client.post("/fapi/v1/order", params=params)
        resp.raise_for_status()
        return resp.json()

    async def transfer_spot_to_futures(self, asset: str, amount: Decimal) -> dict[str, Any]:
        """POST /sapi/v1/futures/transfer - transfer from spot to futures."""
        params = self._sign(
            {
                "asset": asset,
                "amount": str(amount),
                "type": 1,  # 1 = spot to futures
            }
        )
        resp = await self.client.post("/sapi/v1/futures/transfer", params=params)
        resp.raise_for_status()
        return resp.json()

    async def transfer_futures_to_spot(self, asset: str, amount: Decimal) -> dict[str, Any]:
        """POST /sapi/v1/futures/transfer - transfer from futures to spot."""
        params = self._sign(
            {
                "asset": asset,
                "amount": str(amount),
                "type": 2,  # 2 = futures to spot
            }
        )
        resp = await self.client.post("/sapi/v1/futures/transfer", params=params)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self.client.aclose()
