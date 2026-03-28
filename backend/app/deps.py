from __future__ import annotations

from app.core.risk import RiskManager
from app.exchanges.binance import BinanceAdapter
from app.services.cycle_logger import CycleLogger
from app.services.cycle_scanner import CycleScanner
from app.services.live_executor import LiveExecutor
from app.services.paper_trader import PaperTrader
from app.services.price_aggregator import PriceAggregator

# Global instances
exchange = BinanceAdapter()
aggregator = PriceAggregator()
scanner = CycleScanner(aggregator=aggregator)
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


def get_scanner() -> CycleScanner:
    return scanner


def get_aggregator() -> PriceAggregator:
    return aggregator


def get_paper_trader() -> PaperTrader:
    return paper_trader


def get_live_executor() -> LiveExecutor:
    return live_executor
