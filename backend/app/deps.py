from __future__ import annotations

from app.core.risk import RiskManager
from app.exchanges.binance import BinanceAdapter
from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.exchanges.binance_ws import BinanceWsStream
from app.services.cycle_logger import CycleLogger
from app.services.cycle_scanner import CycleScanner
from app.services.live_executor import LiveExecutor
from app.services.paper_trader import PaperTrader
from app.services.price_aggregator import PriceAggregator
from app.services.redis_cache import RedisCache
from app.services.spot_futures import SpotFuturesDetector
from app.services.spot_futures_executor import SpotFuturesExecutor
from app.services.telegram import TelegramNotifier
from app.services.volatility import VolatilityMonitor

# Global instances
redis_cache = RedisCache()
ws_stream = BinanceWsStream()
exchange = BinanceAdapter()
futures_exchange = BinanceFuturesAdapter()
aggregator = PriceAggregator(redis_cache=redis_cache, ws_stream=ws_stream)
scanner = CycleScanner(aggregator=aggregator)
spot_futures = SpotFuturesDetector(futures_exchange)
sf_executor = SpotFuturesExecutor(spot=exchange, futures=futures_exchange)
cycle_logger = CycleLogger()
risk_manager = RiskManager()

paper_trader = PaperTrader(
    initial_balance=150.0,
    min_profit_pct=0.2,
)
live_executor = LiveExecutor(
    exchange=exchange,
    risk_manager=risk_manager,
)
telegram = TelegramNotifier()
volatility = VolatilityMonitor()


def get_scanner() -> CycleScanner:
    return scanner


def get_aggregator() -> PriceAggregator:
    return aggregator


def get_paper_trader() -> PaperTrader:
    return paper_trader


def get_live_executor() -> LiveExecutor:
    return live_executor


def get_spot_futures() -> SpotFuturesDetector:
    return spot_futures


def get_sf_executor() -> SpotFuturesExecutor:
    return sf_executor
