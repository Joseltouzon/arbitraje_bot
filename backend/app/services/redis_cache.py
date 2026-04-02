from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Key prefixes
TICKERS_KEY = "arb:tickers"
TICKERS_META_KEY = "arb:tickers:meta"
PAPER_STATE_KEY = "arb:paper:state"
CYCLES_KEY = "arb:cycles:latest"
SETTINGS_KEY = "arb:settings"


class RedisCache:
    """Async Redis cache for price data and application state."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await self._redis.ping()
            logger.info(f"Redis connected: {settings.redis_url}")
        except Exception as e:
            logger.warning(f"Redis unavailable, running without cache: {e}")
            self._redis = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("Redis connection closed")

    @property
    def connected(self) -> bool:
        return self._redis is not None

    async def save_tickers(self, tickers: dict[str, Any]) -> None:
        """Save tickers hash to Redis."""
        if not self._redis:
            return
        try:
            pipe = self._redis.pipeline()
            pipe.delete(TICKERS_KEY)
            if tickers:
                # Serialize BidAsk objects to JSON strings
                serialized = {
                    symbol: json.dumps(
                        {
                            "bid": ba["bid"],
                            "ask": ba["ask"],
                            "bid_qty": ba["bid_qty"],
                            "ask_qty": ba["ask_qty"],
                        }
                        if isinstance(ba, dict)
                        else {
                            "bid": ba.bid,
                            "ask": ba.ask,
                            "bid_qty": ba.bid_qty,
                            "ask_qty": ba.ask_qty,
                        }
                    )
                    for symbol, ba in tickers.items()
                }
                pipe.hset(TICKERS_KEY, mapping=serialized)
            pipe.set(TICKERS_META_KEY, json.dumps({"count": len(tickers)}))
            await pipe.execute()
        except Exception as e:
            logger.debug(f"Redis save_tickers error: {e}")

    async def load_tickers(self) -> dict[str, Any]:
        """Load tickers from Redis. Returns empty dict if unavailable."""
        if not self._redis:
            return {}
        try:
            data = await self._redis.hgetall(TICKERS_KEY)
            if not data:
                return {}
            from app.models.primitives import BidAsk

            tickers = {}
            for symbol, raw in data.items():
                try:
                    parsed = json.loads(raw)
                    tickers[symbol] = BidAsk(
                        bid=parsed["bid"],
                        ask=parsed["ask"],
                        bid_qty=parsed["bid_qty"],
                        ask_qty=parsed["ask_qty"],
                    )
                except (json.JSONDecodeError, KeyError):
                    continue
            logger.info(f"Restored {len(tickers)} tickers from Redis")
            return tickers
        except Exception as e:
            logger.debug(f"Redis load_tickers error: {e}")
            return {}

    async def save_paper_state(self, state: dict[str, Any]) -> None:
        """Save paper trading state to Redis."""
        if not self._redis:
            return
        try:
            await self._redis.set(PAPER_STATE_KEY, json.dumps(state))
        except Exception as e:
            logger.debug(f"Redis save_paper_state error: {e}")

    async def load_paper_state(self) -> dict[str, Any]:
        """Load paper trading state from Redis."""
        if not self._redis:
            return {}
        try:
            raw = await self._redis.get(PAPER_STATE_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.debug(f"Redis load_paper_state error: {e}")
        return {}

    async def save_cycles(self, cycles: list[dict[str, Any]]) -> None:
        """Save latest detected cycles to Redis."""
        if not self._redis:
            return
        try:
            await self._redis.set(
                CYCLES_KEY,
                json.dumps(cycles, default=str),
                ex=300,  # Expire after 5 minutes
            )
        except Exception as e:
            logger.debug(f"Redis save_cycles error: {e}")

    async def save_settings(self, settings_dict: dict[str, Any]) -> None:
        """Save runtime settings to Redis."""
        if not self._redis:
            return
        try:
            await self._redis.set(SETTINGS_KEY, json.dumps(settings_dict))
        except Exception as e:
            logger.debug(f"Redis save_settings error: {e}")

    async def load_settings(self) -> dict[str, Any]:
        """Load runtime settings from Redis."""
        if not self._redis:
            return {}
        try:
            raw = await self._redis.get(SETTINGS_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.debug(f"Redis load_settings error: {e}")
        return {}

    async def get_stats(self) -> dict[str, Any]:
        """Get Redis connection stats."""
        if not self._redis:
            return {"connected": False}
        try:
            info = await self._redis.info("memory")
            return {
                "connected": True,
                "tickers_cached": await self._redis.hlen(TICKERS_KEY),
                "memory_used": info.get("used_memory_human", "unknown"),
            }
        except Exception:
            return {"connected": True, "error": "stats unavailable"}
