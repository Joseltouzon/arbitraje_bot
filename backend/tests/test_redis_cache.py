import asyncio

from app.services.redis_cache import RedisCache


def test_redis_cache_not_connected_by_default():
    cache = RedisCache()
    assert cache.connected is False


def test_redis_cache_get_stats_disconnected():
    cache = RedisCache()
    stats = asyncio.run(cache.get_stats())
    assert stats["connected"] is False


def test_redis_cache_save_tickers_noop_when_disconnected():
    cache = RedisCache()
    # Should not raise
    asyncio.run(cache.save_tickers({"BTCUSDT": {"bid": 1, "ask": 2, "bid_qty": 1, "ask_qty": 1}}))


def test_redis_cache_load_tickers_empty_when_disconnected():
    cache = RedisCache()
    result = asyncio.run(cache.load_tickers())
    assert result == {}


def test_redis_cache_save_paper_state_noop_when_disconnected():
    cache = RedisCache()
    asyncio.run(cache.save_paper_state({"balance": 150}))


def test_redis_cache_load_paper_state_empty_when_disconnected():
    cache = RedisCache()
    result = asyncio.run(cache.load_paper_state())
    assert result == {}


def test_redis_cache_save_cycles_noop_when_disconnected():
    cache = RedisCache()
    asyncio.run(cache.save_cycles([{"currencies": ["USDT", "BTC", "ETH"]}]))


def test_redis_cache_save_settings_noop_when_disconnected():
    cache = RedisCache()
    asyncio.run(cache.save_settings({"min_profit_threshold_pct": 0.3}))


def test_redis_cache_load_settings_empty_when_disconnected():
    cache = RedisCache()
    result = asyncio.run(cache.load_settings())
    assert result == {}
