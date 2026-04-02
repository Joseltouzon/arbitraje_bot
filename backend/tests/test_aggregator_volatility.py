from app.models.primitives import BidAsk
from app.services.price_aggregator import PriceAggregator
from app.services.volatility import VolatilityMonitor


def test_price_aggregator_initial_state():
    agg = PriceAggregator()
    assert agg.connected is False
    assert agg.update_count == 0
    assert len(agg.tickers) == 0
    assert agg.mode == "rest"


def test_price_aggregator_with_redis():
    from app.services.redis_cache import RedisCache

    redis = RedisCache()
    agg = PriceAggregator(redis_cache=redis)
    stats = agg.get_stats()
    assert stats["redis_enabled"] is False  # Not connected


def test_price_aggregator_filter_usdt_pairs():
    agg = PriceAggregator()
    tickers = {
        "BTCUSDT": BidAsk(bid=85000, ask=85010, bid_qty=1, ask_qty=1),
        "ETHBTC": BidAsk(bid=0.037, ask=0.038, bid_qty=100, ask_qty=100),
        "ADAUSDT": BidAsk(bid=0.5, ask=0.51, bid_qty=200, ask_qty=200),
    }
    # min_qty=100 → BTCUSDT: 85010*1=85010 ✓, ADAUSDT: 0.51*200=102 ✓
    filtered = agg.filter_usdt_pairs(tickers, min_qty=100)
    assert "BTCUSDT" in filtered
    assert "ADAUSDT" in filtered
    assert "ETHBTC" not in filtered

    # Higher threshold excludes ADAUSDT
    filtered2 = agg.filter_usdt_pairs(tickers, min_qty=500)
    assert "ADAUSDT" not in filtered2


def test_price_aggregator_get_quote_prices():
    agg = PriceAggregator()
    tickers = {
        "BTCUSDT": BidAsk(bid=85000, ask=85010, bid_qty=1, ask_qty=1),
        "ETHBTC": BidAsk(bid=0.037, ask=0.038, bid_qty=100, ask_qty=100),
        "INVALIDXYZ": BidAsk(bid=1, ask=2, bid_qty=1, ask_qty=1),
    }
    filtered = agg.get_quote_prices(tickers)
    assert "BTCUSDT" in filtered
    assert "ETHBTC" in filtered


def test_volatility_monitor_initial_state():
    vm = VolatilityMonitor()
    assert vm.volatility_score == 0.0
    assert vm.is_volatile is False


def test_volatility_monitor_update():
    vm = VolatilityMonitor()
    tickers = {
        "BTCUSDT": BidAsk(bid=85000, ask=85010, bid_qty=10, ask_qty=10),
        "ETHUSDT": BidAsk(bid=3200, ask=3201, bid_qty=50, ask_qty=50),
    }
    vm.update(tickers)
    assert vm._update_count == 1


def test_volatility_monitor_multiple_updates():
    vm = VolatilityMonitor()
    for i in range(10):
        tickers = {
            "BTCUSDT": BidAsk(bid=85000 + i * 100, ask=85010 + i * 100, bid_qty=10, ask_qty=10),
            "ETHUSDT": BidAsk(bid=3200 + i * 10, ask=3201 + i * 10, bid_qty=50, ask_qty=50),
        }
        vm.update(tickers)
    assert vm._update_count == 10
    stats = vm.get_stats()
    assert "volatility_score" in stats
    assert "indicators" in stats


def test_volatility_monitor_high_volatility():
    """Big price swings should increase volatility score."""
    vm = VolatilityMonitor()
    base = 85000
    for i in range(30):
        price = base + (i % 2) * base * 0.02
        tickers = {
            "BTCUSDT": BidAsk(bid=price, ask=price + 10, bid_qty=10, ask_qty=10),
            "ETHUSDT": BidAsk(bid=3200, ask=3201, bid_qty=50, ask_qty=50),
        }
        vm.update(tickers)
    assert vm.volatility_score > 0
