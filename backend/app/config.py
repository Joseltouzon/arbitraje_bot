from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/arbitrage"
    redis_url: str = "redis://localhost:6379/0"

    # Binance
    binance_api_key: str = ""
    binance_api_secret: str = ""

    # Operation
    operation_mode: str = "detect"
    auto_trade: bool = False

    # Arbitrage
    min_profit_threshold_pct: float = 0.2
    start_currencies: str = "USDT,BTC,ETH,BNB"
    max_cycle_length: int = 4
    poll_interval_ms: int = 500
    trade_amount_usdt: float = 150.0
    min_liquidity_usdt: float = 5000.0

    # Risk
    max_trades_per_hour: int = 20
    max_consecutive_losses: int = 3
    stop_loss_pct: float = 5.0

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}

    @property
    def start_currency_list(self) -> list[str]:
        return [c.strip() for c in self.start_currencies.split(",") if c.strip()]


settings = Settings()
