from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CycleSnapshot(Base):
    """Stores every detected profitable cycle for history/analytics."""

    __tablename__ = "cycle_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currencies: Mapped[str] = mapped_column(String(200))  # "USDT,BTC,ETH,USDT"
    pairs: Mapped[str] = mapped_column(String(500))  # "BTCUSDT,ETHBTC,ETHUSDT"
    sides: Mapped[str] = mapped_column(String(100))  # "buy,buy,sell"
    net_profit_pct: Mapped[float] = mapped_column(Float)
    net_profit_usdt: Mapped[float] = mapped_column(Float)
    initial_amount: Mapped[float] = mapped_column(Float)
    final_amount: Mapped[float] = mapped_column(Float)
    total_fees: Mapped[float] = mapped_column(Float)
    total_slippage: Mapped[float] = mapped_column(Float)
    raw_rate_product: Mapped[float] = mapped_column(Float)
    legs_json: Mapped[str] = mapped_column(Text)  # Full leg details as JSON
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class TradeHistory(Base):
    """Stores executed trades (for paper/live mode)."""

    __tablename__ = "trade_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(20))  # "paper" or "live"
    currencies: Mapped[str] = mapped_column(String(200))
    pairs: Mapped[str] = mapped_column(String(500))
    sides: Mapped[str] = mapped_column(String(100))
    initial_amount: Mapped[float] = mapped_column(Float)
    final_amount: Mapped[float] = mapped_column(Float)
    profit_usdt: Mapped[float] = mapped_column(Float)
    profit_pct: Mapped[float] = mapped_column(Float)
    total_fees: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))  # "completed", "failed"
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class DailyStats(Base):
    """Aggregated daily statistics."""

    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10))  # "2026-03-28"
    total_cycles_detected: Mapped[int] = mapped_column(Integer, default=0)
    total_trades_executed: Mapped[int] = mapped_column(Integer, default=0)
    total_profit_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    avg_profit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    best_profit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
